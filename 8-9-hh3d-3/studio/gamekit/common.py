"""Shared host helpers for the gamekit CLI.

Every mutating gamekit command follows the same contract: validate the request before touching
files, dedupe by ``command_id`` through the project journal, checkpoint the files it will write,
write through a temp file plus ``os.replace``, and acknowledge only after a fresh Godot process
reads the result back.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Sequence

GAMEKIT_DIR = Path(__file__).resolve().parent
STUDIO_DIR = GAMEKIT_DIR.parent
BASE_DIR = STUDIO_DIR.parent
TOOLING_DIR = STUDIO_DIR / ".local" / "tooling"
GODOT_SCRIPTS_DIR = GAMEKIT_DIR / "godot"
GODOT_VERSION = "4.7.2.stable"
BLENDER_VERSION = "5.2.1"
RESULT_MARKER = "HHGK_RESULT "
TZ = _dt.timezone(_dt.timedelta(hours=7), "Asia/Saigon")

_DEFAULT_GODOT = TOOLING_DIR / "godot-4.7.2-stable" / "Godot_v4.7.2-stable_win64_console.exe"
_DEFAULT_BLENDER = TOOLING_DIR / "blender-5.2.1-windows-x64" / "blender.exe"

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
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@contextlib.contextmanager
def _lock_file(path: Path, purpose: str, wait_seconds: float) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + wait_seconds
    body = json.dumps({"pid": os.getpid(), "purpose": purpose, "at": now_iso()}).encode("utf-8")
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            holder: dict[str, Any] = {}
            with contextlib.suppress(OSError, ValueError):
                holder = json.loads(path.read_text(encoding="utf-8") or "{}")
            if holder and not _pid_alive(int(holder.get("pid", 0))):
                with contextlib.suppress(OSError):
                    path.unlink()
                continue
            if time.monotonic() >= deadline:
                raise GamekitError("LOCKED", f"{path.name} is held", holder=holder)
            time.sleep(0.2)
            continue
        try:
            os.write(fd, body)
        finally:
            os.close(fd)
        break
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


def state_lock(name: str, wait_seconds: float = 10.0) -> contextlib.AbstractContextManager[None]:
    return _lock_file(state_dir() / "locks" / f"{name}.lock", name, wait_seconds)


def project_lock(project: Project, purpose: str, wait_seconds: float = 0.0) -> contextlib.AbstractContextManager[None]:
    """One writer and one gamekit-launched Godot per project at a time."""
    return _lock_file(project.state / "project.lock", purpose, wait_seconds)


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
    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW for the console wrapper only
    started = time.monotonic()
    proc = subprocess.Popen(
        list(argv),
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
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


def refuse_if_editor_open(project: Project, allow: bool = False) -> None:
    if allow:
        return
    try:
        hits = godot_processes_for(project.root)
    except GamekitError:
        raise
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _editor_check_failed(exc) from exc
    if hits:
        raise GamekitError(
            "EDITOR_OPEN",
            "a Godot process has this project open; close it (or pass --allow-open-editor and reload "
            "the scene in the editor afterwards) so two writers do not race",
            processes=hits,
        )


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)
