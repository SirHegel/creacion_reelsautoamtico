"""Project-scoped collaboration; a share never grants a tenant-wide identity."""
from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import secrets
import stat
import threading
import time
from pathlib import Path, PurePosixPath
from contextlib import contextmanager

from .accounts import WORKSPACE_ID, email_address
from .core import StudioError

PROJECT_ID = re.compile(r"p_[0-9a-f]{16}")
SHARE_ID = re.compile(r"sh_[0-9a-f]{32}")
MAX_JSON_BYTES = 32 * 1024 * 1024


class Sharing:
    def __init__(self, accounts):
        self.accounts = accounts
        self.lock = threading.RLock()
        self.project_locks = {}
        with accounts.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS project_shares(
                    id TEXT PRIMARY KEY,
                    owner_workspace TEXT NOT NULL REFERENCES workspaces(id),
                    project_id TEXT NOT NULL,
                    recipient_user TEXT NOT NULL REFERENCES users(id),
                    role TEXT NOT NULL CHECK(role IN ('viewer','editor')),
                    created INTEGER NOT NULL,updated INTEGER NOT NULL,
                    revision INTEGER NOT NULL,
                    UNIQUE(owner_workspace,project_id,recipient_user));
                CREATE INDEX IF NOT EXISTS project_shares_recipient
                    ON project_shares(recipient_user,owner_workspace,project_id);
            """)

    @staticmethod
    def project_id(value):
        if not isinstance(value, str) or not PROJECT_ID.fullmatch(value):
            raise StudioError("Proyecto compartido no válido.", 404)
        return value

    def owner(self, workspace_id):
        if not isinstance(workspace_id, str) or not WORKSPACE_ID.fullmatch(workspace_id):
            raise StudioError("Proyecto compartido no disponible.", 403)
        with self.accounts.connect() as db:
            row = db.execute("SELECT w.id,w.name,w.user_id,u.name user_name FROM workspaces w JOIN users u ON u.id=w.user_id WHERE w.id=?", (workspace_id,)).fetchone()
        if not row:
            raise StudioError("Proyecto compartido no disponible.", 403)
        # Internal backend identity only, never authenticate the actor as this user.
        return {"user": {"id": row["user_id"], "name": row["user_name"]},
                "workspace": {"id": row["id"], "name": row["name"]},
                "kind": "project_backend", "csrf_token": None}

    def root(self, workspace_id):
        self.owner(workspace_id)
        base = self.accounts.root / "workspaces"
        root = base / workspace_id
        if base.is_symlink() or root.is_symlink() or root.resolve() != root or not root.is_relative_to(self.accounts.root):
            raise StudioError("Espacio compartido no válido.", 403)
        return root

    def read_json(self, workspace_id, relative, default=None):
        root = self.root(workspace_id)
        if not isinstance(relative, str) or "\\" in relative or "%" in relative or any(part in ("", ".", "..") for part in relative.split("/")):
            raise StudioError("Archivo compartido no válido.", 403)
        pure = PurePosixPath(relative)
        if pure.is_absolute():
            raise StudioError("Archivo compartido no válido.", 403)
        path = root / relative
        for candidate in [path, *path.parents]:
            if candidate == root.parent:
                break
            if candidate.is_symlink():
                raise StudioError("Archivo compartido no válido.", 403)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return copy.deepcopy(default)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > MAX_JSON_BYTES:
                raise StudioError("Archivo compartido no válido.", 403)
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_JSON_BYTES + 1)
            after = os.fstat(fd)
            if len(raw) != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise StudioError("El proyecto cambió durante la consulta. Recarga.", 409)
            try:
                return json.loads(raw)
            except (UnicodeError, ValueError):
                raise StudioError("Archivo compartido no válido.", 409) from None
        finally:
            os.close(fd)

    def project(self, workspace_id, project_id):
        pid = self.project_id(project_id)
        value = self.read_json(workspace_id, f"projects/{pid}/project.json")
        if not isinstance(value, dict) or value.get("id") != pid or type(value.get("revision")) is not int:
            raise StudioError("Proyecto no encontrado.", 404)
        return value

    def access(self, actor, owner_workspace_id, project_id, *, write=False):
        pid = self.project_id(project_id)
        owner = self.owner(owner_workspace_id)
        if actor["workspace"]["id"] == owner_workspace_id and actor["user"]["id"] == owner["user"]["id"]:
            role = "owner"
        else:
            # Account agent credentials keep their original tenant scope.
            if actor.get("kind") != "session":
                raise StudioError("Proyecto compartido no disponible para esta conexión.", 403)
            with self.accounts.connect() as db:
                row = db.execute("SELECT role FROM project_shares WHERE owner_workspace=? AND project_id=? AND recipient_user=?", (owner_workspace_id, pid, actor["user"]["id"])).fetchone()
            if not row:
                raise StudioError("Proyecto compartido no disponible.", 403)
            role = row["role"]
        if write and role not in ("owner", "editor"):
            raise StudioError("Este proyecto está compartido para lectura.", 403)
        return {"role": role, "owner_workspace_id": owner_workspace_id,
                "actor_workspace_id": actor["workspace"]["id"], "project_id": pid,
                "shared": role != "owner", "can_edit": role in ("owner", "editor"),
                "can_render": role in ("owner", "editor"), "can_export": True,
                "can_automate": role == "owner", "can_share": role == "owner",
                "can_manage_library": role == "owner", "remote_storage": False}

    def _owner_only(self, actor, project_id):
        if actor.get("kind") != "session":
            raise StudioError("Comparte proyectos desde tu cuenta.", 403)
        self.current_actor(actor)
        owner = self.owner(actor['workspace']['id'])
        if owner['user']['id'] != actor['user']['id']:
            raise StudioError('La identidad no corresponde al propietario.', 403)
        pid = self.project_id(project_id)
        self.project(actor["workspace"]["id"], pid)
        return pid

    def current_actor(self, actor):
        if actor.get('kind') != 'session' or not isinstance(actor.get('credential_hash'), str):
            raise StudioError('La sesión de colaboración dejó de estar disponible.', 401)
        with self.accounts.connect() as db:
            row = db.execute('SELECT s.user_id,s.csrf,w.id workspace_id FROM sessions s JOIN workspaces w ON w.user_id=s.user_id WHERE s.hash=? AND s.expires>?',
                             (actor['credential_hash'], int(time.time()))).fetchone()
        if (not row or row['user_id'] != actor['user']['id'] or row['workspace_id'] != actor['workspace']['id'] or
                row['csrf'] != actor.get('csrf_token')):
            raise StudioError('La sesión de colaboración dejó de estar disponible.', 401)

    @contextmanager
    def project_gate(self, workspace_id, project_id):
        """Serialize membership changes with admitted project operations.

        HTTP bodies must be consumed before acquiring this gate. A slow client
        cannot hold a permission open while its owner revokes access.
        """
        self.owner(workspace_id)
        pid = self.project_id(project_id)
        with self.lock:
            lock = self.project_locks.setdefault((workspace_id, pid), threading.RLock())
        with lock:
            directory = self.accounts.root / '.estado' / 'collaboration_locks'
            for candidate in (directory.parent, directory):
                if candidate.is_symlink():
                    raise StudioError('Bloqueo de colaboración no válido.', 403)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = directory / (workspace_id + '_' + pid + '.lock')
            descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, 'a+b') as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise StudioError('Bloqueo de colaboración no válido.', 403)
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    @contextmanager
    def admitted(self, actor, workspace_id, project_id, *, write=False):
        with self.project_gate(workspace_id, project_id):
            self.current_actor(actor)
            yield self.access(actor, workspace_id, project_id, write=write)

    def grant(self, actor, project_id, data):
        pid = self._owner_only(actor, project_id)
        if not isinstance(data, dict) or set(data) != {"email", "role", "expected_revision"}:
            raise StudioError("Compartir requiere correo, permiso y revisión vigente (cero para un permiso nuevo).")
        email = email_address(data["email"])
        role = data["role"]
        if role not in ("viewer", "editor"):
            raise StudioError("Permiso de colaboración no válido.")
        expected = data.get("expected_revision")
        if type(expected) is not int or expected < 0:
            raise StudioError("La revisión del permiso debe ser un entero.")
        self.accounts.limited("project_share", actor["user"]["id"], email, maximum=30)
        stamp = int(time.time())
        with self.project_gate(actor['workspace']['id'], pid), self.accounts.connect() as db:
            self.current_actor(actor)
            db.execute("BEGIN IMMEDIATE")
            user = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            if not user:
                raise StudioError("El destinatario debe tener una cuenta en este servicio.", 404)
            if user["id"] == actor["user"]["id"]:
                raise StudioError("Tu cuenta ya es propietaria del proyecto.", 409)
            old = db.execute("SELECT * FROM project_shares WHERE owner_workspace=? AND project_id=? AND recipient_user=?", (actor["workspace"]["id"], pid, user["id"])).fetchone()
            revision = old["revision"] if old else 0
            if expected != revision:
                raise StudioError("El permiso cambió. Recarga la lista.", 409)
            if old:
                db.execute("UPDATE project_shares SET role=?,updated=?,revision=? WHERE id=?", (role, stamp, revision + 1, old["id"]))
            else:
                db.execute("INSERT INTO project_shares VALUES (?,?,?,?,?,?,?,?)", ("sh_" + secrets.token_hex(16), actor["workspace"]["id"], pid, user["id"], role, stamp, stamp, 1))
        return self.members(actor, pid)

    def members(self, actor, project_id):
        pid = self._owner_only(actor, project_id)
        with self.accounts.connect() as db:
            rows = db.execute("SELECT s.id,s.role,s.created,s.updated,s.revision,u.email,u.name FROM project_shares s JOIN users u ON u.id=s.recipient_user WHERE s.owner_workspace=? AND s.project_id=? ORDER BY s.created,s.id", (actor["workspace"]["id"], pid)).fetchall()
        return {"project_id": pid, "shares": [dict(row) for row in rows], "email_verified": False,
                "identity_scope": "existing_local_account", "public_link": False}

    def revoke(self, actor, project_id, share_id, expected_revision):
        pid = self._owner_only(actor, project_id)
        if not isinstance(share_id, str) or not SHARE_ID.fullmatch(share_id):
            raise StudioError("Permiso no encontrado.", 404)
        if type(expected_revision) is not int or expected_revision < 1:
            raise StudioError("Revocar requiere la revisión vigente del permiso.")
        with self.project_gate(actor['workspace']['id'], pid), self.accounts.connect() as db:
            self.current_actor(actor)
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT revision FROM project_shares WHERE id=? AND owner_workspace=? AND project_id=?',
                             (share_id, actor['workspace']['id'], pid)).fetchone()
            if row and row['revision'] != expected_revision:
                raise StudioError("El permiso cambió antes de revocarlo. Recarga.", 409)
            changed = db.execute("DELETE FROM project_shares WHERE id=? AND owner_workspace=? AND project_id=?", (share_id, actor["workspace"]["id"], pid)).rowcount
        if not changed:
            raise StudioError("Permiso no encontrado.", 404)
        return {"revoked": True, "id": share_id, "project_id": pid}

    def received(self, actor):
        if actor.get("kind") != "session":
            raise StudioError("Abre los proyectos compartidos desde tu cuenta.", 403)
        with self.accounts.connect() as db:
            rows = db.execute("SELECT s.owner_workspace,s.project_id,s.role,u.name owner_name FROM project_shares s JOIN workspaces w ON w.id=s.owner_workspace JOIN users u ON u.id=w.user_id WHERE s.recipient_user=? ORDER BY s.updated DESC,s.id", (actor["user"]["id"],)).fetchall()
        projects = []
        for row in rows:
            try:
                project = self.project(row["owner_workspace"], row["project_id"])
            except StudioError:
                continue
            projects.append({"project_id": row["project_id"], "owner_workspace_id": row["owner_workspace"],
                             "owner_name": row["owner_name"], "role": row["role"], "title": project.get("name", "Proyecto compartido"),
                             "revision": project["revision"], "updated_at": project.get("updated_at"), "stage": project.get("stage"),
                             "editor_url": "/editor?workspace=" + row["owner_workspace"] + "&project=" + row["project_id"]})
        return {"projects": projects, "storage_provider": "local", "remote": False}

    def assets(self, workspace_id, project):
        allowed = {item["id"]: item for item in project.get("assets", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
        catalog = self.read_json(workspace_id, ".estado/assets.json", [])
        if not isinstance(catalog, list):
            raise StudioError("Catálogo compartido no válido.", 409)
        canonical = {item.get("id"): item for item in catalog if isinstance(item, dict)}
        result = []
        for aid, attached in allowed.items():
            item = canonical.get(aid)
            if not item or item.get("sha256") != attached.get("sha256"):
                raise StudioError("Un medio adjunto cambió. El propietario debe revisar el proyecto.", 409)
            result.append(copy.deepcopy(item))
        return result

    @staticmethod
    def validate_edit(project, incoming):
        if not isinstance(incoming, dict) or incoming.get("id") != project["id"]:
            raise StudioError("La edición requiere el mismo proyecto compartido.", 403)
        if incoming.get("source") != project.get("source"):
            raise StudioError("El propietario administra el crudo del proyecto.", 403)
        original = {item.get("id"): item.get("sha256") for item in project.get("assets", []) if isinstance(item, dict)}
        if not isinstance(incoming.get("assets"), list) or any(not isinstance(item, dict) or item.get("id") not in original or item.get("sha256") != original.get(item.get("id")) for item in incoming["assets"]):
            raise StudioError("Solo puedes editar con los medios adjuntos a este proyecto.", 403)
        # The canonical server validates the remaining fonts, scene references,
        # protected review fields, immutable branding and optimistic revision.

    def jobs(self, workspace_id, project_id):
        rows = self.read_json(workspace_id, ".estado/jobs.json", [])
        if isinstance(rows, dict):
            rows = rows.get("jobs", list(rows.values()))
        allowed = {"id", "project_id", "project", "action", "status", "progress", "created_at", "updated_at", "started_at", "finished_at", "message"}
        result = []
        for job in rows if isinstance(rows, list) else []:
            if isinstance(job, dict) and job.get("project_id", job.get("project")) == project_id:
                # Preparation results can contain an owner's wider resource catalog.
                # They never travel through a shared-project response.
                public = {key: value for key, value in job.items() if key in allowed}
                if job.get("error"):
                    public["error"] = "La tarea requiere revisión del propietario."
                result.append(public)
        return result

    def file_allowed(self, workspace_id, project, relative):
        if not isinstance(relative, str) or "\\" in relative or "%" in relative or any(part in ("", ".", "..") for part in relative.split("/")) or relative.startswith("/"):
            return False
        root = self.root(workspace_id)
        target = root / relative
        for candidate in [target, *target.parents]:
            if candidate == root.parent:
                break
            if candidate.is_symlink():
                return False
        if target.resolve() != target:
            return False
        if target.exists() and (not target.is_file() or target.stat().st_nlink != 1):
            return False
        pid = project["id"]
        if relative in (f"exports/{pid}_editable.zip", f"exports/{pid}_pending.json"):
            return True
        # Renderer and snapshot artifacts are project-scoped, never the private state.
        if relative.startswith(f"projects/{pid}/") and Path(relative).suffix.lower() in {".mp4", ".webm", ".png", ".jpg", ".jpeg", ".webp", ".csv", ".srt", ".vtt"}:
            return True
        for item in self.assets(workspace_id, project):
            for key in ("path", "preview_path", "thumbnail", "thumbnail_path", "waveform", "waveform_path"):
                if item.get(key) == relative:
                    return True
            thumbnail = item.get('thumbnail')
            if isinstance(thumbnail, str) and thumbnail.startswith('/api/files/') and thumbnail[len('/api/files/'):] == relative:
                return True
            thumbnails = item.get('thumbnails', [])
            if isinstance(thumbnails, list) and relative in thumbnails:
                return True
            preview = item.get("preview")
            if isinstance(preview, dict) and relative in (preview.get("path"), preview.get("thumbnail"), preview.get("waveform")):
                return True
        return False
