"""Accounts, workspace ownership and revocable credentials. No parent credentials."""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from .core import StudioError

CODE_ROOT = Path(__file__).resolve().parents[1]
PASSWORD_WORKERS = threading.BoundedSemaphore(2)
WORKSPACE_ID = re.compile(r"w_[0-9a-f]{32}")
SESSION_SECONDS = 12 * 3600


def token_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def password_hash(password, salt=None):
    if not isinstance(password, str) or not 12 <= len(password) <= 256 or len(password.encode()) > 1024:
        raise StudioError("Usa una contraseña de entre 12 y 256 caracteres.")
    salt = secrets.token_bytes(16) if salt is None else salt
    with PASSWORD_WORKERS:
        result = hashlib.scrypt(password.encode(), salt=salt, n=32768, r=8, p=3, maxmem=64*1024*1024, dklen=32)
    return "scrypt$32768$8$3$" + salt.hex() + "$" + result.hex()


def password_matches(password, encoded):
    try:
        kind, n, r, p, salt, expected = encoded.split("$")
        if (kind, n, r, p) != ("scrypt", "32768", "8", "3"):
            return False
        return hmac.compare_digest(password_hash(password, bytes.fromhex(salt)).split("$")[-1], expected)
    except (ValueError, TypeError, StudioError):
        return False


def email_address(value):
    if not isinstance(value, str):
        raise StudioError("El correo no es válido.")
    value = value.strip().casefold()
    if not 3 <= len(value) <= 254 or not re.fullmatch(r"[^\s@\x00-\x1f]+@[^\s@\x00-\x1f]+\.[^\s@\x00-\x1f]+", value):
        raise StudioError("El correo no es válido.")
    return value


class Accounts:
    def __init__(self, root=None):
        self.root = CODE_ROOT if root is None else Path(root).resolve()
        if not self.root.is_relative_to(CODE_ROOT.resolve()):
            raise StudioError("La configuración debe permanecer dentro de SOFTWARE.", 403)
        private = self.root / ".estado/multiservice"
        if (self.root / ".estado").is_symlink() or private.is_symlink() or not private.resolve().is_relative_to(self.root):
            raise StudioError("Configuración privada fuera de SOFTWARE.", 403)
        private.mkdir(parents=True, exist_ok=True, mode=0o700)
        private.chmod(0o700)
        self.path = private / "accounts.sqlite"
        if self.path.is_symlink():
            raise StudioError("Base de cuentas inválida.", 403)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS workspaces(id TEXT PRIMARY KEY,user_id TEXT UNIQUE NOT NULL REFERENCES users(id),name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_tokens(id TEXT PRIMARY KEY,hash TEXT UNIQUE NOT NULL,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS attempts(bucket TEXT NOT NULL,created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS attempts_bucket ON attempts(bucket,created);
            """)
        self.path.chmod(0o600)
        self._dummy_password = password_hash(secrets.token_urlsafe(32))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def limited(self, action, peer, email="", maximum=10):
        """Persistent limits by source AND account; parallel requests consume slots."""
        stamp = int(time.time())
        buckets = [token_hash(action+":ip:"+peer)]
        if email:
            buckets.append(token_hash(action+":email:"+email))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE created < ?", (stamp-900,))
            for bucket in buckets:
                if db.execute("SELECT COUNT(*) FROM attempts WHERE bucket=? AND created>=?", (bucket,stamp-900)).fetchone()[0] >= maximum:
                    raise StudioError("Demasiados intentos. Vuelve a intentarlo en unos minutos.", 429)
            db.executemany("INSERT INTO attempts VALUES (?,?)", [(bucket,stamp) for bucket in buckets])

    def register(self, data, peer="local"):
        if not isinstance(data, dict) or set(data) != {"email", "name", "password"}:
            raise StudioError("El registro requiere nombre, correo y contraseña.")
        email = email_address(data["email"])
        name = data["name"]
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 120 or any(ord(c)<32 for c in name):
            raise StudioError("Introduce un nombre válido.")
        self.limited("register",peer,email,20)
        encoded = password_hash(data["password"])
        user_id, workspace_id = "u_"+secrets.token_hex(16), "w_"+secrets.token_hex(16)
        with self.connect() as db:
            try:
                db.execute("INSERT INTO users VALUES (?,?,?,?,?)",(user_id,email,name.strip(),encoded,int(time.time())))
                db.execute("INSERT INTO workspaces VALUES (?,?,?)",(workspace_id,user_id,name.strip()))
            except sqlite3.IntegrityError:
                raise StudioError("Ese correo ya tiene una cuenta.",409) from None
        return self.new_session(user_id)

    def login(self, data, peer="local"):
        if not isinstance(data,dict) or set(data) != {"email","password"}:
            raise StudioError("El acceso requiere correo y contraseña.")
        email = email_address(data["email"])
        self.limited("login",peer,email)
        with self.connect() as db:
            user = db.execute("SELECT * FROM users WHERE email=?",(email,)).fetchone()
        matched = password_matches(data["password"], user["password"] if user else self._dummy_password)
        if not matched or not user:
            raise StudioError("Correo o contraseña incorrectos.",401)
        return self.new_session(user["id"])

    def new_session(self, user_id):
        secret, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<=?",(int(time.time()),))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?)",(token_hash(secret),user_id,csrf,int(time.time())+SESSION_SECONDS))
        return {"session":secret,"principal":self.authenticate(secret)}

    def authenticate(self, secret, agent=False):
        if not isinstance(secret,str) or len(secret)>512 or not secret:
            return None
        table = "agent_tokens" if agent else "sessions"
        with self.connect() as db:
            row = db.execute(f"SELECT c.*,u.email,u.name,w.id workspace_id,w.name workspace_name FROM {table} c JOIN users u ON u.id=c.user_id JOIN workspaces w ON w.user_id=u.id WHERE c.hash=? AND c.expires>?",(token_hash(secret),int(time.time()))).fetchone()
        if not row:
            return None
        return {"user":{"id":row["user_id"],"email":row["email"],"name":row["name"]},
                "workspace":{"id":row["workspace_id"],"name":row["workspace_name"]},
                "csrf_token":None if agent else row["csrf"],"credential_hash":row["hash"],"kind":"agent" if agent else "session"}

    def logout(self, principal):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE hash=?",(principal["credential_hash"],))

    def workspace_path(self, principal):
        wid = principal["workspace"]["id"]
        if not WORKSPACE_ID.fullmatch(wid):
            raise StudioError("Espacio no válido.",403)
        base = self.root / "workspaces"
        path = base / wid
        if base.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(self.root.resolve()):
            raise StudioError("Espacio no válido.",403)
        path.mkdir(parents=True,exist_ok=True,mode=0o700)
        path.chmod(0o700)
        return path

    def tokens(self, principal):
        with self.connect() as db:
            rows = db.execute("SELECT id,name,created,expires FROM agent_tokens WHERE user_id=? ORDER BY created",(principal["user"]["id"],)).fetchall()
        return [dict(row) for row in rows]

    def create_token(self,principal,data):
        name = data.get("name") if isinstance(data,dict) and set(data)=={"name"} else None
        if not isinstance(name,str) or not 1<=len(name.strip())<=120:
            raise StudioError("Asigna un nombre al agente.")
        stamp = int(time.time())
        tid, secret = "at_"+secrets.token_hex(16), "asc_"+secrets.token_urlsafe(48)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT COUNT(*) FROM agent_tokens WHERE user_id=?",(principal["user"]["id"],)).fetchone()[0]>=20:
                raise StudioError("El espacio permite hasta veinte conexiones de agentes.",409)
            db.execute("INSERT INTO agent_tokens VALUES (?,?,?,?,?,?)",(tid,token_hash(secret),principal["user"]["id"],name.strip(),stamp,stamp+90*86400))
        return {"id":tid,"name":name.strip(),"token":secret,"expires":stamp+90*86400,"workspace_id":principal["workspace"]["id"]}

    def revoke_token(self,principal,tid):
        with self.connect() as db:
            changed=db.execute("DELETE FROM agent_tokens WHERE id=? AND user_id=?",(tid,principal["user"]["id"])).rowcount
        if not changed:
            raise StudioError("Conexión no encontrada.",404)
        return {"revoked":True,"id":tid}
