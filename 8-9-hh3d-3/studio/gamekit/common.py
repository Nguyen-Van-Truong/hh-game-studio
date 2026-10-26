"""Shared host helpers for the gamekit CLI.

Every mutating gamekit command follows the same contract: validate the request before touching
files, dedupe by ``command_id`` through the project journal, checkpoint the files it will write,
write through a temp file plus ``os.replace``, and acknowledge only after a fresh Godot process
reads the result back.
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import errno
import functools
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

GAMEKIT_DIR = Path(__file__).resolve().parent
STUDIO_DIR = GAMEKIT_DIR.parent
BASE_DIR = STUDIO_DIR.parent
TOOLING_DIR = STUDIO_DIR / ".local" / "tooling"
GODOT_SCRIPTS_DIR = GAMEKIT_DIR / "godot"
TOOLCHAIN_LOCK_PATH = STUDIO_DIR / "toolchain.lock.json"


@functools.lru_cache(maxsize=1)
def toolchain_lock() -> dict[str, Any]:
    """Read the studio toolchain lock as the single source of truth for versions and hashes."""
    raw = json.loads(TOOLCHAIN_LOCK_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema") != "HH-STUDIO-TOOLCHAIN-LOCK-2":
        raise RuntimeError(f"invalid toolchain lock schema in {TOOLCHAIN_LOCK_PATH}")
    return raw


def _load_default_pins() -> tuple[str, str, Path, Path, str, str, str]:
    lock = toolchain_lock()
    godot = lock["godot"]
    blender = lock["blender"]
    godot_tag = str(godot["version"])
    godot_ver = godot_tag.replace("-stable", ".stable")
    blender_ver = str(blender["version"])
    default_godot = TOOLING_DIR / f"godot-{godot_tag}" / str(godot["console_executable"])
    default_blender = TOOLING_DIR / str(blender["binary_source_member"])
    return (
        godot_ver,
        blender_ver,
        default_godot,
        default_blender,
        str(godot["console_sha256"]),
        str(godot["gui_sha256"]),
        str(blender["executable_sha256"]),
    )


(
    GODOT_VERSION,
    BLENDER_VERSION,
    _DEFAULT_GODOT,
    _DEFAULT_BLENDER,
    GODOT_CONSOLE_SHA256,
    GODOT_GUI_SHA256,
    BLENDER_EXE_SHA256,
) = _load_default_pins()
RESULT_MARKER = "HHGK_RESULT "
TZ = _dt.timezone(_dt.timedelta(hours=7), "Asia/Saigon")

# Out of HH Studio scope per the repository AGENTS.md files; gamekit refuses to register them.
FORBIDDEN_PATH_PARTS = (
    ("godot", "dogfood", "kho-bi-an"),
    ("godot", "plugin-project", "snake"),
    ("godot", "dogfood", "superfighters"),
)

PROJECT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
COMMAND_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,95}$")
RES_PATH_RE = re.compile(r"^res://[A-Za-z0-9_\-./ ()\[\]+@]{1,240}$")
MAX_JSON_BYTES = 16 * 1024 * 1024


def godot_exe() -> Path:
    return Path(os.environ.get("HH_GODOT") or _DEFAULT_GODOT)


def blender_exe() -> Path:
    return Path(os.environ.get("HH_BLENDER") or _DEFAULT_BLENDER)


def state_dir() -> Path:
    """Host state (registry, journals, checkpoints). Selftests point HH_GAMEKIT_STATE at %TEMP%."""
    return Path(os.environ.get("HH_GAMEKIT_STATE") or (STUDIO_DIR / ".local" / "gamekit"))


class GamekitError(Exception):
    """Fail-closed error with a stable machine code."""

    def __init__(self, code: str, detail: str = "", **extra: Any) -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ok": False, "error": self.code, "detail": self.detail}
        out.update(self.extra)
        return out


# ---------------------------------------------------------------- JSON, hashing, atomic writes


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, limit: int = MAX_JSON_BYTES) -> Any:
    path = Path(path)
    if not path.is_file():
        raise GamekitError("NOT_FOUND", f"json file missing: {path}")
    size = path.stat().st_size
    if size > limit:
        raise GamekitError("BAD_REQUEST", f"json file too large ({size} bytes): {path}")
    try:
        return json.loads(path.read_bytes().decode("utf-8-sig"), parse_constant=_reject_constant)
    except (ValueError, UnicodeDecodeError) as exc:
        raise GamekitError("BAD_REQUEST", f"invalid json in {path}: {exc}") from exc


def parse_json_text(text: str) -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise GamekitError("BAD_REQUEST", f"invalid json: {exc}") from exc


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.hhtmp-{os.getpid()}-{secrets.token_hex(3)}")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any, *, sort_keys: bool = True) -> None:
    text = json.dumps(value, indent=2, sort_keys=sort_keys, ensure_ascii=False, allow_nan=False) + "\n"
    atomic_write_text(path, text)


def now_iso() -> str:
    return _dt.datetime.now(TZ).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    stamp = _dt.datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{stamp}-{secrets.token_hex(3)}"


def emit(value: dict[str, Any]) -> None:
    """Print a CLI result as UTF-8 JSON."""
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False, allow_nan=False)
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    stream.write(text + "\n")
    stream.flush()


# ---------------------------------------------------------------- projects and paths


def _norm(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def is_within(child: Path, parent: Path) -> bool:
    c, p = _norm(child), _norm(parent)
    try:
        return os.path.commonpath([c, p]) == p
    except ValueError:
        return False


_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _is_junction(path: Path) -> bool:
    """True when ``path`` is a symlink or junction, even if the target is missing.

    ``os.lstat`` does not follow the last component. A missing entry is not a link.
    """
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE_POINT)


def _has_reparse_point(path: Path, stop: Path | None = None) -> bool:
    """True if ``path`` or one of its parents (down to ``stop``) is a symlink or junction.

    Every component is tested with ``lstat``, so a dangling junction still counts.
    """
    current = Path(os.path.abspath(str(path)))
    stop_norm = _norm(stop) if stop else None
    while True:
        if _is_junction(current):
            return True
        if stop_norm and _norm(current) == stop_norm:
            return False
        parent = current.parent
        if parent == current:
            return False
        current = parent


def forbidden_reason(path: Path) -> str | None:
    parts = [p.lower() for p in Path(os.path.abspath(str(path))).parts]
    for pattern in FORBIDDEN_PATH_PARTS:
        n = len(pattern)
        for i in range(len(parts) - n + 1):
            if tuple(parts[i : i + n]) == pattern:
                return "/".join(pattern) + " is outside HH Studio scope (AGENTS.md)"
    return None


def refuse_unsafe_host_path(
    path: Path,
    *,
    what: str,
    project: Project | None = None,
    must_be_outside_project: bool = False,
) -> Path:
    """Return a resolved host path, or raise ``FORBIDDEN_PATH``.

    The path and every ancestor are tested with ``lstat`` (no follow). A symlink or
    junction is refused even when its target is missing, before ``resolve`` can follow
    it. The resolved path must not be named ``private.raw`` and must not lie under
    ``studio/.local``. When ``must_be_outside_project`` is set, it also must not lie
    inside ``project.root`` (resolved paths, case-insensitive on Windows).
    """
    if must_be_outside_project and project is None:
        raise GamekitError("BAD_REQUEST", f"{what} requires a project")
    raw = Path(os.path.abspath(str(path)))
    if raw.name.lower() == "private.raw":
        raise GamekitError("FORBIDDEN_PATH", "refusing to use private.raw")
    local = STUDIO_DIR / ".local"
    if is_within(raw, local):
        raise GamekitError("FORBIDDEN_PATH", "refusing a path under studio/.local")
    if _has_reparse_point(raw):
        raise GamekitError("FORBIDDEN_PATH", f"{what} passes through a symlink or junction: {raw}")
    try:
        resolved = raw.resolve()
    except OSError as exc:
        raise GamekitError("FORBIDDEN_PATH", f"{what} cannot be resolved: {exc}") from exc
    if resolved.name.lower() == "private.raw":
        raise GamekitError("FORBIDDEN_PATH", "refusing to use private.raw")
    if _has_reparse_point(resolved) or is_within(resolved, local):
        raise GamekitError("FORBIDDEN_PATH", f"{what} resolves to a forbidden path: {resolved}")
    if must_be_outside_project:
        assert project is not None
        try:
            root = Path(project.root).resolve()
        except OSError as exc:
            raise GamekitError("FORBIDDEN_PATH", f"project root cannot be resolved: {exc}") from exc
        if is_within(resolved, root):
            raise GamekitError("FORBIDDEN_PATH", f"{what} must be outside the project")
    return resolved


@dataclass(frozen=True)
class Project:
    project_id: str
    root: Path
    registered_at: str = ""

    @property
    def state(self) -> Path:
        return state_dir() / "projects" / self.project_id

    def res_to_path(self, res: str, *, must_exist: bool = False) -> Path:
        return res_to_path(self.root, res, must_exist=must_exist)

    def path_to_res(self, path: Path) -> str:
        if not is_within(path, self.root):
            raise GamekitError("FORBIDDEN_PATH", f"{path} is outside project {self.project_id}")
        rel = os.path.relpath(os.path.abspath(str(path)), os.path.abspath(str(self.root)))
        return "res://" + rel.replace("\\", "/")

    def to_json(self) -> dict[str, Any]:
        return {"project_id": self.project_id, "root": str(self.root), "registered_at": self.registered_at}


def res_to_path(root: Path, res: str, *, must_exist: bool = False) -> Path:
    """Map a ``res://`` path to a file inside ``root``; rejects traversal, junctions and .godot."""
    if not isinstance(res, str) or not RES_PATH_RE.match(res):
        raise GamekitError("BAD_PATH", f"not a safe res:// path: {res!r}")
    rel = res[len("res://") :]
    segments = rel.split("/")
    if any(seg in ("", ".", "..") for seg in segments) or rel.startswith("/"):
        raise GamekitError("BAD_PATH", f"res path has empty or dot segments: {res!r}")
    if segments[0].lower() == ".godot":
        raise GamekitError("BAD_PATH", f"res path points into .godot: {res!r}")
    path = Path(root, *segments)
    if not is_within(path, root):
        raise GamekitError("FORBIDDEN_PATH", f"{res!r} escapes the project root")
    if _has_reparse_point(path, stop=root):
        raise GamekitError("FORBIDDEN_PATH", f"{res!r} passes through a symlink or junction")
    if must_exist and not path.is_file():
        raise GamekitError("NOT_FOUND", f"{res!r} does not exist")
    return path


def _registry_path() -> Path:
    return state_dir() / "projects.json"


def load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"schema": "hh-gamekit-registry-1", "projects": {}}
    data = read_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("projects"), dict):
        raise GamekitError("STATE_CORRUPT", f"registry is malformed: {path}")
    return data


def register_project(root: str | Path, project_id: str | None = None) -> Project:
    raw = Path(root)
    if not raw.is_absolute():
        raw = Path(os.path.abspath(str(raw)))
    if not (raw / "project.godot").is_file():
        raise GamekitError("NOT_FOUND", f"no project.godot in {raw}")
    if _has_reparse_point(raw):
        raise GamekitError("FORBIDDEN_PATH", f"project path uses a symlink or junction: {raw}")
    reason = forbidden_reason(raw)
    if reason:
        raise GamekitError("FORBIDDEN_PATH", reason)
    resolved = Path(os.path.abspath(str(raw)))
    pid = project_id or re.sub(r"[^a-z0-9_-]+", "-", resolved.name.lower()).strip("-")[:48] or "game"
    if not PROJECT_ID_RE.match(pid):
        raise GamekitError("BAD_REQUEST", f"project id must match {PROJECT_ID_RE.pattern}: {pid!r}")
    with state_lock("registry"):
        reg = load_registry()
        for other_id, entry in reg["projects"].items():
            same_root = _norm(Path(entry["root"])) == _norm(resolved)
            if other_id == pid and not same_root:
                raise GamekitError("CONFLICT", f"project id {pid!r} is registered to {entry['root']}")
            if same_root and other_id != pid:
                raise GamekitError("CONFLICT", f"{resolved} is already registered as {other_id!r}")
        if pid in reg["projects"]:
            entry = reg["projects"][pid]
            return Project(pid, Path(entry["root"]), entry.get("registered_at", ""))
        entry = {"root": str(resolved), "registered_at": now_iso()}
        reg["projects"][pid] = entry
        atomic_write_json(_registry_path(), reg)
    return Project(pid, resolved, entry["registered_at"])


def _project_from_entry(project_id: str, entry: dict[str, Any]) -> Project:
    """Load one registry row. A root replaced by a symlink or junction is refused."""
    project = Project(project_id, Path(entry["root"]), entry.get("registered_at", ""))
    if _has_reparse_point(project.root):
        raise GamekitError("FORBIDDEN_PATH", f"project path uses a symlink or junction: {project.root}")
    return project


def get_project(ref: str) -> Project:
    reg = load_registry()
    entry = reg["projects"].get(ref)
    if entry:
        return _project_from_entry(ref, entry)
    if any(sep in ref for sep in ("/", "\\", ":")):
        target = _norm(Path(ref))
        for pid, entry in reg["projects"].items():
            if _norm(Path(entry["root"])) == target:
                return _project_from_entry(pid, entry)
    raise GamekitError("NOT_FOUND", f"unknown project {ref!r}; run: hh project add <path> --id <id>")


def list_projects() -> list[Project]:
    reg = load_registry()
    return [Project(pid, Path(e["root"]), e.get("registered_at", "")) for pid, e in sorted(reg["projects"].items())]


# ---------------------------------------------------------------- locks, journal, checkpoints


def _pid_alive(pid: int) -> bool:
    """True unless this pid is proven dead. Access denied stays occupied.

    ``os.kill(pid, 0)`` terminates a process on Windows, so liveness uses a
    synchronize handle. Unknown failures are treated as alive so a lock is not
    stolen from a process we cannot observe.
    """
    if type(pid) is not int or pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
        if not handle:
            return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0  # signaled = exited
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


_GUARD_HELD: set[str] = set()
_GUARD_META = threading.Lock()
_measure_hold: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "hh_gamekit_measure_hold", default=None
)
_LOCK_SCHEMA = "hh-gamekit-lock-1"
_MEASURE_SCHEMA = "HH-MEASURE-WINDOW-1"


def _guard_key(path: Path) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(str(path))))


def _lexists(path: Path) -> bool:
    try:
        os.lstat(path)
    except OSError:
        return False
    return True


def _lock_busy(exc: OSError) -> bool:
    winerror = getattr(exc, "winerror", None)
    if winerror in (33, 36):  # ERROR_LOCK_VIOLATION / lock conflict
        return True
    return exc.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK)


def _kernel_lock_region(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _kernel_unlock_region(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(fd, fcntl.LOCK_UN)


@contextlib.contextmanager
def _kernel_file_lock(guard: Path) -> Iterator[None]:
    """Exclusive kernel lock on a permanent guard file.

    The guard is never unlinked: replacing that inode would let two owners
    lock two different files at the same path. Same-process reentry fails
    without locking again, because a Windows byte-range unlock is process-wide
    and a nested unlock would drop the outer owner's lock.
    """
    key = _guard_key(guard)
    with _GUARD_META:
        if key in _GUARD_HELD:
            raise GamekitError("LOCKED", f"{guard.name} is held by this process", same_process=True)
        _GUARD_HELD.add(key)
    fd: int | None = None
    held = False
    try:
        if _has_reparse_point(guard.parent) or _is_junction(guard):
            raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {guard}")
        guard.parent.mkdir(parents=True, exist_ok=True)
        if _is_junction(guard) or _is_junction(guard.parent):
            raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {guard}")
        flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = _open_private(guard, flags, 0o600)
        except OSError as exc:
            if _is_junction(guard):
                raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {guard}") from exc
            raise GamekitError("LOCK_UNSAFE", f"cannot open lock guard {guard}: {exc}") from exc
        info = os.fstat(fd)
        attrs = getattr(info, "st_file_attributes", 0)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or attrs & _REPARSE_POINT:
            raise GamekitError("LOCK_UNSAFE", f"lock guard is not a regular file: {guard}")
        if info.st_size < 1:
            try:
                os.write(fd, b"\0")
                os.fsync(fd)
            except OSError as exc:
                # A holder that locked the empty guard (the legacy measurement
                # window does this) denies the padding write. That is contention.
                if _lock_busy(exc):
                    raise GamekitError("LOCKED", f"{guard.name} is held") from exc
                raise GamekitError("LOCK_UNSAFE", f"cannot prepare lock guard {guard}: {exc}") from exc
        try:
            _kernel_lock_region(fd)
            held = True
        except OSError as exc:
            if _lock_busy(exc):
                raise GamekitError("LOCKED", f"{guard.name} is held") from exc
            raise GamekitError("LOCK_UNSAFE", f"cannot lock {guard}: {exc}") from exc
        yield
    finally:
        if held and fd is not None:
            with contextlib.suppress(OSError):
                _kernel_unlock_region(fd)
        if fd is not None:
            os.close(fd)
        with _GUARD_META:
            _GUARD_HELD.discard(key)


def _retryable_lock(exc: GamekitError, deadline: float) -> bool:
    if exc.code != "LOCKED" or exc.extra.get("same_process"):
        return False
    return time.monotonic() < deadline


def _holder_public(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"pid": data["pid"]}
    for key in ("purpose", "run_id"):
        value = data.get(key)
        if isinstance(value, str) and value:
            out[key] = value[:200]
    return out


def _mark_non_inheritable(fd: int) -> None:
    """Best-effort. Engine spawns also pass ``close_fds=True``."""
    try:
        target: int = fd
        if os.name == "nt":
            import msvcrt

            target = msvcrt.get_osfhandle(fd)
        os.set_handle_inheritable(target, False)
    except OSError:
        return


def _open_nofollow_windows(path: Path, flags: int) -> int:
    """Open ``path`` without following a symlink or junction.

    This interpreter has no ``os.O_NOFOLLOW``. ``CreateFileW`` with
    ``FILE_FLAG_OPEN_REPARSE_POINT`` returns the reparse point itself; a
    reparse point is refused instead of being followed.
    """
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    class _FileTime(ctypes.Structure):
        _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

    class _FileInfo(ctypes.Structure):
        _fields_ = [
            ("attr", wintypes.DWORD),
            ("created", _FileTime),
            ("accessed", _FileTime),
            ("written", _FileTime),
            ("volume", wintypes.DWORD),
            ("size_high", wintypes.DWORD),
            ("size_low", wintypes.DWORD),
            ("links", wintypes.DWORD),
            ("index_high", wintypes.DWORD),
            ("index_low", wintypes.DWORD),
        ]

    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_FileInfo)]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    if flags & os.O_RDWR:
        access = 0x80000000 | 0x40000000
        crt = os.O_RDWR
    elif flags & os.O_WRONLY:
        access = 0x40000000
        crt = os.O_WRONLY
    else:
        access = 0x80000000
        crt = os.O_RDONLY
    if (flags & os.O_CREAT) and (flags & os.O_EXCL):
        disposition = 1  # CREATE_NEW
    elif flags & os.O_CREAT:
        disposition = 4  # OPEN_ALWAYS
    else:
        disposition = 3  # OPEN_EXISTING
    handle = kernel.CreateFileW(
        str(path), access, 0x1 | 0x2 | 0x4, None, disposition, 0x80 | 0x00200000, None,
    )
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        err = ctypes.get_last_error()
        if err == 80:  # ERROR_FILE_EXISTS
            raise FileExistsError(err, os.strerror(err) if hasattr(os, "strerror") else "file exists", str(path))
        raise OSError(0, f"winerror {err}", str(path))
    info = _FileInfo()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        kernel.CloseHandle(handle)
        raise OSError(0, f"winerror {ctypes.get_last_error()}", str(path))
    if info.attr & (_REPARSE_POINT | 0x10) or info.links != 1:
        kernel.CloseHandle(handle)
        raise OSError(0, "reparse point or extra link", str(path))
    try:
        os.set_handle_inheritable(handle, False)
    except OSError:
        pass
    try:
        return msvcrt.open_osfhandle(handle, os.O_BINARY | crt)
    except OSError:
        kernel.CloseHandle(handle)
        raise


def _open_private(path: Path, flags: int, mode: int | None = None) -> int:
    """Open a lock file without following a reparse point."""
    nofollow = getattr(os, "O_NOFOLLOW", 0) or 0
    if os.name == "nt" and not nofollow:
        fd = _open_nofollow_windows(path, flags)
    elif mode is None:
        fd = os.open(str(path), flags | int(nofollow))
    else:
        fd = os.open(str(path), flags | int(nofollow), mode)
    _mark_non_inheritable(fd)
    return fd


def _read_lock_bytes(path: Path, *, unsafe_code: str, malformed_code: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = _open_private(path, flags)
    except OSError as exc:
        if _is_junction(path):
            raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {path}") from exc
        raise GamekitError(unsafe_code, f"cannot read lock {path}: {exc}") from exc
    try:
        info = os.fstat(fd)
        attrs = getattr(info, "st_file_attributes", 0)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or attrs & _REPARSE_POINT:
            raise GamekitError(unsafe_code, f"lock path is not a single regular file: {path}")
        if info.st_size > 4096:
            raise GamekitError(malformed_code, f"lock marker is too large: {path.name}")
        return os.read(fd, 4097)
    finally:
        os.close(fd)


def _create_marker(path: Path, body: bytes) -> None:
    if len(body) > 4096:
        raise GamekitError("LOCK_UNSAFE", "lock marker exceeds 4096 bytes")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = _open_private(path, flags, 0o600)
    except FileExistsError as exc:
        raise GamekitError("LOCKED", f"{path.name} is held") from exc
    except OSError as exc:
        if _is_junction(path):
            raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {path}") from exc
        raise GamekitError("LOCK_UNSAFE", f"cannot create lock {path}: {exc}") from exc
    try:
        os.write(fd, body)
        os.fsync(fd)
    finally:
        os.close(fd)
    readback = _read_lock_bytes(path, unsafe_code="LOCK_UNSAFE", malformed_code="LOCK_MALFORMED")
    if readback != body:
        raise GamekitError("LOCK_UNSAFE", f"lock readback mismatch for {path.name}")


def _release_marker_if_ours(path: Path, body: bytes, *, quiet: bool) -> None:
    """Unlink ``path`` only when its bytes are still the marker this owner wrote."""
    try:
        if _is_junction(path) or not _lexists(path):
            return
        raw = _read_lock_bytes(path, unsafe_code="LOCK_UNSAFE", malformed_code="LOCK_MALFORMED")
    except (GamekitError, OSError):
        return
    if raw != body:
        return
    try:
        os.unlink(path)
    except OSError as exc:
        if not quiet:
            raise GamekitError("LOCK_UNSAFE", f"could not release lock {path}: {exc}") from exc


def _parse_lock_marker(raw: bytes) -> dict[str, Any] | None:
    """Accept the current marker and the older ``pid``/``purpose``/``at`` marker."""
    if not raw or len(raw) > 4096:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if type(data) is not dict:
        return None
    schema = data.get("schema")
    if schema is not None and schema != _LOCK_SCHEMA:
        return None
    pid = data.get("pid")
    if type(pid) is not int or pid <= 0:
        return None
    return data


def _parse_measure_marker(raw: bytes) -> dict[str, Any] | None:
    if not raw or len(raw) > 4096:
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if type(data) is not dict:
        return None
    schema = data.get("schema")
    if schema is not None and schema != _MEASURE_SCHEMA:
        return None
    pid = data.get("pid")
    if type(pid) is not int or pid <= 0:
        return None
    return data


def _claim_marker(path: Path, body: bytes, *, malformed_code: str, parse: Any) -> None:
    """Create ``path`` or replace a proven-dead marker. Caller holds the guard."""
    if _is_junction(path):
        raise GamekitError("FORBIDDEN_PATH", f"lock path is a symlink or junction: {path}")
    if not _lexists(path):
        _create_marker(path, body)
        return
    unsafe = "MEASURE_WINDOW" if malformed_code == "MEASURE_WINDOW" else "LOCK_UNSAFE"
    raw = _read_lock_bytes(path, unsafe_code=unsafe, malformed_code=malformed_code)
    holder = parse(raw)
    if holder is None:
        raise GamekitError(malformed_code, f"lock marker is malformed: {path.name}")
    if _pid_alive(holder["pid"]):
        raise GamekitError("LOCKED", f"{path.name} is held", holder=_holder_public(holder))
    raw2 = _read_lock_bytes(path, unsafe_code=unsafe, malformed_code=malformed_code)
    if raw2 != raw:
        raise GamekitError("LOCKED", f"{path.name} changed while recovering a stale lock")
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise GamekitError("LOCK_UNSAFE", f"cannot recover stale lock {path}: {exc}") from exc
    _create_marker(path, body)


def _lock_body(purpose: str, root: str | None) -> bytes:
    payload: dict[str, Any] = {
        "schema": _LOCK_SCHEMA,
        "pid": os.getpid(),
        "purpose": purpose,
        "at": now_iso(),
        "nonce": secrets.token_hex(16),
    }
    if root is not None:
        payload["root"] = root
    body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    if len(body) > 4096:
        raise GamekitError("LOCK_UNSAFE", "lock marker exceeds 4096 bytes")
    return body


def _enter_kernel_when_ready(guard: Path, claim: Any, deadline: float) -> contextlib.AbstractContextManager[None]:
    while True:
        lock = _kernel_file_lock(guard)
        entered = False
        try:
            lock.__enter__()
            entered = True
            claim()
            return lock
        except GamekitError as exc:
            if entered:
                lock.__exit__(None, None, None)
            if not _retryable_lock(exc, deadline):
                raise
        time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))


class _HeldLock:
    """Kernel guard plus a marker file. Release deletes the marker only if it is still ours."""

    def __init__(self, path: Path, purpose: str, wait_seconds: float, root: str | None) -> None:
        self.path = Path(path)
        self.guard = self.path.with_name(self.path.name + ".guard")
        self.body = _lock_body(purpose, root)
        self.wait_seconds = max(0.0, float(wait_seconds))
        self._lock: contextlib.AbstractContextManager[None] | None = None

    def __enter__(self) -> "_HeldLock":
        if _has_reparse_point(self.path.parent):
            raise GamekitError(
                "FORBIDDEN_PATH",
                f"lock directory passes through a symlink or junction: {self.path.parent}",
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.wait_seconds

        def claim() -> None:
            _claim_marker(self.path, self.body, malformed_code="LOCK_MALFORMED", parse=_parse_lock_marker)

        self._lock = _enter_kernel_when_ready(self.guard, claim, deadline)
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        try:
            _release_marker_if_ours(self.path, self.body, quiet=exc_type is not None)
        finally:
            lock = self._lock
            self._lock = None
            if lock is not None:
                lock.__exit__(None, None, None)
        return False


def _lock_file(path: Path, purpose: str, wait_seconds: float) -> contextlib.AbstractContextManager[None]:
    return _HeldLock(Path(path), purpose, wait_seconds, None)


def state_lock(name: str, wait_seconds: float = 10.0) -> contextlib.AbstractContextManager[None]:
    return _lock_file(state_dir() / "locks" / f"{name}.lock", name, wait_seconds)


def canonical_project_root(root: Path) -> str:
    """Absolute, case-folded project root. Symlinks and junctions are refused."""
    raw = Path(os.path.abspath(str(root)))
    if _has_reparse_point(raw):
        raise GamekitError("FORBIDDEN_PATH", f"project path uses a symlink or junction: {raw}")
    return os.path.normcase(os.path.normpath(str(raw)))


def shared_lock_dir() -> Path:
    """Machine-local lock directory, outside the project and outside git.

    ``HH_GAMEKIT_SHARED_LOCK_DIR`` overrides the default
    ``%LOCALAPPDATA%/HHGodotAgent/gamekit-project-locks`` so tests do not use
    the real directory. The override is still refused when it is a reparse path.
    """
    override = os.environ.get("HH_GAMEKIT_SHARED_LOCK_DIR")
    if override:
        directory = Path(os.path.abspath(override))
    else:
        base = os.environ.get("LOCALAPPDATA")
        if not isinstance(base, str) or not base.strip():
            raise GamekitError("LOCK_UNAVAILABLE", "LOCALAPPDATA is required for the shared project lock")
        directory = Path(base) / "HHGodotAgent" / "gamekit-project-locks"
    if _has_reparse_point(directory):
        raise GamekitError(
            "FORBIDDEN_PATH",
            f"shared lock directory passes through a symlink or junction: {directory}",
        )
    return directory


def shared_project_lock_path(root: Path) -> Path:
    """Lock file for one physical project root, independent of state dir and project id."""
    key = hashlib.sha256(canonical_project_root(root).encode("utf-8")).hexdigest()
    return shared_lock_dir() / f"{key}.lock"


def project_lock(project: Project, purpose: str, wait_seconds: float = 0.0) -> contextlib.AbstractContextManager[None]:
    """One writer for a physical project root, then the per-state project lock.

    Agents that use different ``HH_GAMEKIT_STATE`` directories or project ids
    still share the physical lock. The per-state ``project.lock`` remains next
    to that state's journal. Nested acquisition in this process raises ``LOCKED``.
    Distinct roots take distinct shared locks. Wait is bounded by ``wait_seconds``.
    """
    shared = shared_project_lock_path(project.root)
    state = project.state / "project.lock"
    root_key = canonical_project_root(project.root)

    @contextlib.contextmanager
    def _held() -> Iterator[None]:
        with _HeldLock(shared, purpose, wait_seconds, root_key):
            with _HeldLock(state, purpose, wait_seconds, None):
                yield

    return _held()


def measure_window_lock_path() -> Path:
    """Legacy measurement marker. ``HH_GAMEKIT_MEASURE_LOCK`` overrides it for tests."""
    override = os.environ.get("HH_GAMEKIT_MEASURE_LOCK")
    if override:
        return Path(os.path.abspath(override))
    base = os.environ.get("LOCALAPPDATA")
    if not isinstance(base, str) or not base.strip():
        raise GamekitError("MEASURE_WINDOW", "LOCALAPPDATA is required")
    return Path(base) / "HHGodotAgent" / "measure-window.lock"


def _new_measure_payload(purpose: str, run_id: str | None) -> dict[str, Any]:
    if not isinstance(purpose, str) or not purpose.strip() or len(purpose) > 200:
        raise GamekitError("BAD_REQUEST", "measurement purpose must be a short non-empty string")
    if run_id is not None and (not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 200):
        raise GamekitError("BAD_REQUEST", "measurement run_id must be a short string")
    now = _dt.datetime.now(_dt.timezone.utc)
    return {
        "schema": _MEASURE_SCHEMA,
        "owner": "hh-gamekit",
        "pid": os.getpid(),
        "run_id": run_id or new_id("measure"),
        "purpose": purpose,
        "claimed_utc": now.isoformat(),
        "expires_utc": (now + _dt.timedelta(hours=24)).isoformat(),
        "nonce": secrets.token_hex(16),
    }


def _require_our_measure_marker(path: Path, nonce: str) -> None:
    if _is_junction(path) or not _lexists(path):
        raise GamekitError("MEASURE_WINDOW", "measurement marker disappeared while this process held it")
    raw = _read_lock_bytes(path, unsafe_code="MEASURE_WINDOW", malformed_code="MEASURE_WINDOW")
    holder = _parse_measure_marker(raw)
    if holder is None or holder.get("nonce") != nonce or holder.get("pid") != os.getpid():
        raise GamekitError("MEASURE_WINDOW", "measurement marker is no longer owned by this process")


def _raise_if_measure_blocks(path: Path) -> None:
    """Refuse a live or malformed marker. A proven-dead marker is left untouched."""
    if _is_junction(path):
        raise GamekitError("FORBIDDEN_PATH", f"measurement lock is a symlink or junction: {path}")
    if not _lexists(path):
        return
    raw = _read_lock_bytes(path, unsafe_code="MEASURE_WINDOW", malformed_code="MEASURE_WINDOW")
    holder = _parse_measure_marker(raw)
    if holder is None:
        raise GamekitError("MEASURE_WINDOW", "measurement lock is malformed")
    if _pid_alive(holder["pid"]):
        raise GamekitError(
            "MEASURE_WINDOW",
            "a measurement reservation is held",
            holder=_holder_public(holder),
        )


def assert_measure_window_clear() -> None:
    """Refuse an engine launch when a measurement reservation is held.

    The check takes the legacy ``measure-window.guard`` only when this process
    does not already hold ``measure_window``, so ``hh perf`` does not deadlock
    on its own guard. A matching nonce is the proof of our hold; a live pid
    alone is not, because pids are reused. Proven-dead markers do not block and
    are not deleted here.
    """
    path = measure_window_lock_path()
    nonce = _measure_hold.get()
    if nonce is not None:
        _require_our_measure_marker(path, nonce)
        return
    if _has_reparse_point(path.parent):
        raise GamekitError(
            "FORBIDDEN_PATH",
            f"measurement lock directory passes through a symlink or junction: {path.parent}",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    guard = path.with_suffix(".guard")
    try:
        with _kernel_file_lock(guard):
            _raise_if_measure_blocks(path)
    except GamekitError as exc:
        if exc.code == "LOCKED":
            raise GamekitError("MEASURE_WINDOW", "measurement guard is held") from exc
        raise


@contextlib.contextmanager
def measure_window(
    purpose: str,
    *,
    run_id: str | None = None,
    wait_seconds: float = 0.0,
) -> Iterator[dict[str, Any]]:
    """Acquire the legacy measurement marker and always release it from ``finally``.

    The guard file and schema match ``studio/tests/replay/measure_window.py``.
    A live owner is not stolen when ``expires_utc`` has passed. A proven-dead
    marker is replaced only while this process holds the guard, and only after
    a second read shows the same bytes. Wait is bounded by ``wait_seconds``.
    """
    if _measure_hold.get() is not None:
        raise GamekitError("MEASURE_WINDOW", "this process already holds the measurement reservation")
    path = measure_window_lock_path()
    if _has_reparse_point(path.parent):
        raise GamekitError(
            "FORBIDDEN_PATH",
            f"measurement lock directory passes through a symlink or junction: {path.parent}",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    value = _new_measure_payload(purpose, run_id)
    body = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    guard = path.with_suffix(".guard")
    deadline = time.monotonic() + max(0.0, float(wait_seconds))

    def claim() -> None:
        _claim_marker(path, body, malformed_code="MEASURE_WINDOW", parse=_parse_measure_marker)

    try:
        lock = _enter_kernel_when_ready(guard, claim, deadline)
    except GamekitError as exc:
        if exc.code == "LOCKED":
            extra = {key: item for key, item in exc.extra.items() if key != "same_process"}
            raise GamekitError("MEASURE_WINDOW", exc.detail, **extra) from exc
        raise
    token = _measure_hold.set(str(value["nonce"]))
    try:
        yield value
    finally:
        _measure_hold.reset(token)
        try:
            _release_marker_if_ours(path, body, quiet=sys.exc_info()[0] is not None)
        finally:
            lock.__exit__(None, None, None)


def validate_command_id(command_id: str) -> str:
    if not isinstance(command_id, str) or not COMMAND_ID_RE.match(command_id):
        raise GamekitError("BAD_REQUEST", f"command_id must match {COMMAND_ID_RE.pattern}")
    return command_id


class Journal:
    """Append-only per-project journal: one JSON line per committed command."""

    def __init__(self, project: Project) -> None:
        self.path = project.state / "journal.jsonl"

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def find(self, command_id: str) -> dict[str, Any] | None:
        found = None
        for rec in self.records():
            if rec.get("command_id") == command_id:
                found = rec
        return found

    def replay_or_conflict(self, command_id: str, request_digest: str) -> dict[str, Any] | None:
        rec = self.find(command_id)
        if rec is None:
            return None
        if rec.get("request_digest") != request_digest:
            raise GamekitError(
                "CONFLICT",
                f"command_id {command_id!r} was already used with a different request",
                previous_digest=rec.get("request_digest"),
            )
        receipt = dict(rec["receipt"])
        receipt["replayed"] = True
        return receipt

    def append(self, command_id: str, request_digest: str, receipt: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = canonical_json({"command_id": command_id, "request_digest": request_digest, "receipt": receipt})
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())


def _checkpoint_dir(project: Project, command_id: str) -> Path:
    return project.state / "checkpoints" / re.sub(r"[^A-Za-z0-9._-]", "_", command_id)


def checkpoint(project: Project, command_id: str, paths: Sequence[Path]) -> dict[str, Any]:
    """Copy the current bytes of ``paths`` before a mutation; missing files are recorded as absent."""
    cdir = _checkpoint_dir(project, command_id)
    cdir.mkdir(parents=True, exist_ok=True)
    entries = []
    for i, path in enumerate(paths):
        res = project.path_to_res(path)
        if path.is_file():
            data = path.read_bytes()
            (cdir / f"{i}.bin").write_bytes(data)
            entries.append({"res": res, "existed": True, "sha256": sha256_bytes(data), "blob": f"{i}.bin"})
        else:
            entries.append({"res": res, "existed": False})
    manifest = {"command_id": command_id, "at": now_iso(), "files": entries}
    atomic_write_json(cdir / "manifest.json", manifest)
    return manifest


def restore_checkpoint(project: Project, command_id: str) -> list[str]:
    cdir = _checkpoint_dir(project, command_id)
    manifest = read_json(cdir / "manifest.json")
    restored = []
    for entry in manifest["files"]:
        path = project.res_to_path(entry["res"])
        if entry["existed"]:
            data = (cdir / entry["blob"]).read_bytes()
            if sha256_bytes(data) != entry["sha256"]:
                raise GamekitError("STATE_CORRUPT", f"checkpoint blob hash mismatch for {entry['res']}")
            atomic_write_bytes(path, data)
        elif path.exists():
            path.unlink()
        restored.append(entry["res"])
    return restored


def checkpoint_manifest(project: Project, command_id: str) -> dict[str, Any]:
    return read_json(_checkpoint_dir(project, command_id) / "manifest.json")


# ---------------------------------------------------------------- running Godot and Blender

_ERROR_RE = re.compile(r"(SCRIPT ERROR|Parse Error|USER ERROR|^ERROR:|^\s*ERROR:|Failed to load|Cannot open file)")
_WARNING_RE = re.compile(r"^(WARNING:|\s*WARNING:|USER WARNING)")


@dataclass
class ProcessRun:
    argv: list[str]
    exit_code: int | None
    seconds: float
    stdout: str
    stderr: str
    timed_out: bool = False
    result: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "exit_code": self.exit_code,
            "seconds": round(self.seconds, 2),
            "timed_out": self.timed_out,
            "errors": self.errors[:40],
            "warnings": self.warnings[:40],
        }


def _kill_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
    else:  # pragma: no cover - Windows host is the supported platform
        with contextlib.suppress(OSError):
            os.kill(pid, 9)


def run_process(argv: Sequence[str], *, timeout: float, cwd: Path | None = None, env: dict[str, str] | None = None) -> ProcessRun:
    # Engine entry points also check before building argv. Checking again here
    # keeps the reservation test next to the spawn. hh perf already holds the
    # marker, so this call observes that nonce and does not lock the guard twice.
    assert_measure_window_clear()
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW for the console wrapper only
    started = time.monotonic()
    proc = subprocess.Popen(
        list(argv),
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=flags,
    )
    timed_out = False
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc.pid)
        out, err = proc.communicate()
    run = ProcessRun(
        argv=[str(a) for a in argv],
        exit_code=None if timed_out else proc.returncode,
        seconds=time.monotonic() - started,
        stdout=out.decode("utf-8", errors="replace"),
        stderr=err.decode("utf-8", errors="replace"),
        timed_out=timed_out,
    )
    for line in (run.stdout + "\n" + run.stderr).splitlines():
        if line.startswith(RESULT_MARKER):
            try:
                parsed = json.loads(line[len(RESULT_MARKER) :])
            except ValueError:
                run.errors.append("unparseable result line")
                continue
            if isinstance(parsed, dict):
                run.result = parsed
        elif _ERROR_RE.search(line):
            run.errors.append(line.strip()[:400])
        elif _WARNING_RE.search(line):
            run.warnings.append(line.strip()[:400])
    return run


def run_godot(
    project_root: Path,
    script: Path | None = None,
    args: Sequence[str] = (),
    *,
    headless: bool = True,
    editor: bool = False,
    windowed: bool = False,
    resolution: tuple[int, int] | None = None,
    fixed_fps: int | None = None,
    timeout: float = 180.0,
    extra: Sequence[str] = (),
    env: dict[str, str] | None = None,
) -> ProcessRun:
    assert_measure_window_clear()
    exe = godot_exe()
    if not exe.is_file():
        raise GamekitError("TOOL_MISSING", f"pinned Godot not found: {exe}")
    argv: list[str] = [str(exe)]
    if headless:
        argv.append("--headless")
    if editor:
        argv.append("--editor")
    argv += ["--path", str(project_root)]
    if windowed:
        argv.append("--windowed")
        if resolution:
            argv += ["--resolution", f"{int(resolution[0])}x{int(resolution[1])}", "--position", "40,40"]
    if fixed_fps:
        argv += ["--fixed-fps", str(int(fixed_fps))]
    argv += list(extra)
    if script is not None:
        argv += ["--script", str(script)]
    if args:
        argv.append("--")
        argv += [str(a) for a in args]
    return run_process(argv, timeout=timeout, cwd=project_root, env=env)


def run_godot_tool(project_root: Path, tool: str, request: dict[str, Any], **kwargs: Any) -> ProcessRun:
    """Run ``studio/gamekit/godot/<tool>`` with a JSON request file; the tool emits HHGK_RESULT."""
    script = GODOT_SCRIPTS_DIR / tool
    if not script.is_file():
        raise GamekitError("TOOL_MISSING", f"gamekit Godot script missing: {script}")
    req_dir = state_dir() / "requests"
    req_dir.mkdir(parents=True, exist_ok=True)
    req_path = req_dir / f"{new_id('req')}.json"
    # Keep the caller's key order: Godot applies props in order (Curve2D point_count before point_N/*).
    atomic_write_json(req_path, request, sort_keys=False)
    try:
        return run_godot(project_root, script, ["--request", str(req_path)], **kwargs)
    finally:
        with contextlib.suppress(OSError):
            req_path.unlink()


def require_result(run: ProcessRun, what: str) -> dict[str, Any]:
    """Fail closed unless Godot exited 0, emitted a result and reported ok."""
    if run.timed_out:
        raise GamekitError("TIMEOUT", f"{what} timed out after {run.seconds:.0f}s", process=run.summary())
    if run.result is None:
        raise GamekitError("GODOT_FAILED", f"{what} produced no result", process=run.summary(),
                           tail=(run.stdout + run.stderr)[-1500:])
    if not run.result.get("ok", False):
        raise GamekitError(run.result.get("error", "GODOT_FAILED"), str(run.result.get("detail", what)),
                           result=run.result, process=run.summary())
    if run.exit_code != 0:
        raise GamekitError("GODOT_FAILED", f"{what} exited {run.exit_code}", process=run.summary())
    return run.result


def import_project(project_root: Path, timeout: float = 600.0) -> ProcessRun:
    """Run the pinned editor's --import pass so textures, models and audio load in tools."""
    return run_godot(project_root, None, (), headless=True, editor=True, timeout=timeout, extra=("--import",))


def ensure_imported(project_root: Path) -> ProcessRun | None:
    if (project_root / ".godot" / "imported").is_dir() or (project_root / ".godot" / "uid_cache.bin").exists():
        return None
    return import_project(project_root)


def run_blender(script: Path, args: Sequence[str] = (), *, timeout: float = 600.0, blend: Path | None = None) -> ProcessRun:
    assert_measure_window_clear()
    exe = blender_exe()
    if not exe.is_file():
        raise GamekitError("TOOL_MISSING", f"pinned Blender not found: {exe}")
    argv = [str(exe), "--background", "--factory-startup", "--disable-autoexec", "--python-exit-code", "17"]
    if blend is not None:
        argv.append(str(blend))
    argv += ["--python", str(script)]
    if args:
        argv.append("--")
        argv += [str(a) for a in args]
    return run_process(argv, timeout=timeout)


_EDITOR_CHECK_DETAIL = (
    "could not check for an open Godot editor; close it and retry, or pass --allow-open-editor"
)


def _editor_check_failed(exc: BaseException | None = None) -> GamekitError:
    err = GamekitError("EDITOR_CHECK_FAILED", _EDITOR_CHECK_DETAIL)
    if exc is not None:
        err.__cause__ = exc
    return err


def _decode_process_query(data: bytes) -> str:
    """Decode a PowerShell process listing. Empty bytes are a failed query, not 'no editor'."""
    if not data or not data.strip():
        return ""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace").strip()
    if data.count(b"\x00") > len(data) // 4:
        return data.decode("utf-16-le", errors="replace").strip()
    return data.decode("utf-8-sig", errors="replace").strip()


def godot_processes_for(project_root: Path) -> list[dict[str, Any]]:
    """Godot processes whose command line mentions the project (e.g. an open editor).

    A timeout, ``OSError``, empty stdout, or unreadable JSON raises ``EDITOR_CHECK_FAILED``.
    A successful query that lists no matching process returns an empty list.
    """
    if os.name != "nt":
        return []
    # Always emit JSON, including ``[]`` when no Godot process exists. PowerShell's default
    # pipe encoding is UTF-16; force UTF-8 so an empty editor list stays parseable.
    ps = (
        "$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$ProgressPreference = 'SilentlyContinue'; "
        "$ErrorActionPreference = 'Stop'; "
        "$items = @(Get-CimInstance Win32_Process -Filter \"Name like 'Godot%'\" | "
        "Select-Object -Property ProcessId,CommandLine); "
        "if ($items.Count -eq 0) { '[]' } else { ConvertTo-Json -InputObject @($items) -Compress }"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, timeout=20, check=False, creationflags=0x08000000,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _editor_check_failed(exc) from exc
    text = _decode_process_query(completed.stdout)
    if not text:
        raise _editor_check_failed()
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise _editor_check_failed(exc) from exc
    if data is None or not isinstance(data, (list, dict)):
        raise _editor_check_failed()
    rows = data if isinstance(data, list) else [data]
    root_variants = {_norm(project_root), _norm(project_root).replace("\\", "/")}
    hits = []
    for row in rows:
        if not isinstance(row, dict):
            raise _editor_check_failed()
        cmd = os.path.normcase(str(row.get("CommandLine") or ""))
        if any(v in cmd or v in cmd.replace("\\", "/") for v in root_variants):
            hits.append({"pid": row.get("ProcessId"), "command_line": str(row.get("CommandLine"))[:300]})
    return hits


def refuse_if_editor_open(project: Project, allow: bool = False, *, hint_allow: bool = True) -> None:
    if allow:
        return
    try:
        hits = godot_processes_for(project.root)
    except GamekitError:
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _editor_check_failed(exc) from exc
    if hits:
        if hint_allow:
            detail = (
                "a Godot process has this project open; close it (or pass --allow-open-editor and reload "
                "the scene in the editor afterwards) so two writers do not race"
            )
        else:
            detail = "a Godot process has this project open; close it before hh play so the play run does not race the editor"
        raise GamekitError("EDITOR_OPEN", detail, processes=hits)


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)
