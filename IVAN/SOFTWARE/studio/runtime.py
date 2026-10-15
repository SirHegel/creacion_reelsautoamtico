"""Immutable process scope: executable code and private workspace data.

The gateway selects a workspace before starting a backend. Requests never
change these roots, global environments or shared model configuration.
"""
from pathlib import Path
import os


CODE_ROOT = Path(__file__).resolve().parents[1]
MANUAL_ROOT = CODE_ROOT.parent
WORKSPACES_ROOT = CODE_ROOT / "workspaces"
SHARED_CPU_LOCK = CODE_ROOT / ".estado/cpu_worker.lock"


class WorkspaceConfigurationError(ValueError):
    """An invalid backend scope fails before any data is opened or written."""


def validate_workspace(value):
    if not isinstance(value, (str, Path)) or not str(value).strip() or "\x00" in str(value):
        raise WorkspaceConfigurationError("ASCENDIA_WORKSPACE requiere una ruta local válida.")
    path = Path(value)
    if ".." in path.parts:
        raise WorkspaceConfigurationError("ASCENDIA_WORKSPACE no admite rutas ascendentes.")
    path = path if path.is_absolute() else CODE_ROOT / path
    # Resolve even missing descendants: a symlink in any existing ancestor
    # is an alias, including links to another otherwise valid workspace.
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise WorkspaceConfigurationError("ASCENDIA_WORKSPACE no puede resolverse.") from error
    if path.absolute() != resolved or resolved == WORKSPACES_ROOT or not resolved.is_relative_to(WORKSPACES_ROOT):
        raise WorkspaceConfigurationError("ASCENDIA_WORKSPACE debe ser un directorio real bajo SOFTWARE/workspaces, sin enlaces.")
    if resolved.exists() and not resolved.is_dir():
        raise WorkspaceConfigurationError("ASCENDIA_WORKSPACE debe ser un directorio.")
    return resolved


_selected = os.environ.get("ASCENDIA_WORKSPACE")
DATA_ROOT = CODE_ROOT if _selected is None else validate_workspace(_selected)


def shared_cpu_lock_path(value=None):
    """Validate the fixed global lease before mkdir/open; no alias traversal.

    An explicit value is trusted process/test configuration, never request
    data. Production jobs pass their immutable SHARED_CPU_LOCK constant.
    """
    path = SHARED_CPU_LOCK if value is None else Path(value)
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError, ValueError) as error:
        raise WorkspaceConfigurationError("No se puede resolver el bloqueo CPU compartido.") from error
    if path.absolute() != resolved or not resolved.is_relative_to(CODE_ROOT):
        raise WorkspaceConfigurationError("El bloqueo CPU debe permanecer en SOFTWARE sin enlaces ni alias.")
    if resolved.exists() and not resolved.is_file():
        raise WorkspaceConfigurationError("El bloqueo CPU requiere un archivo regular.")
    return resolved

