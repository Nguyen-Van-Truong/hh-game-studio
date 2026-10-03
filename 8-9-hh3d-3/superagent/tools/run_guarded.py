#!/usr/bin/env python3
"""Bounded runner for project commands behind the shared GT-06 guard.

Windows children are created suspended and assigned to a Job Object with
KILL_ON_JOB_CLOSE before resume.  The machine measurement lock is observed but
never changed.  Evidence is written under ``.local/runs``.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Sequence

EXIT_GUARD = 125
EXIT_TIMEOUT = 124
EXIT_CONTAINMENT = 126
EXIT_DIAGNOSTIC = 1
_WIN_CREATE_NEW_PROCESS_GROUP = 0x00000200
_WIN_CREATE_SUSPENDED = 0x00000004
MAX_TIMEOUT_SECONDS = 24 * 60 * 60
LOCK_POLL_SECONDS = 0.20
DEFAULT_TASK_POLL_SECONDS = 3.0
_SENSITIVE = re.compile(r"(?i)(?:password|passwd|token|secret|api[_-]?key|authorization|bearer)")
_DIAGNOSTIC = re.compile(r"(?i)(?:\bwarn(?:ing)?\b|\berror\b|\bleaks?\b|\bleaked\b|\borphan(?:ed)?\b|\bleftover\b|objectdb|audiostream)")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def lock_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is unavailable")
    return Path(local) / "HHGodotAgent" / "measure-window.lock"


def _startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt":
        return None
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return startup


def scheduled_gt06_running(*, timeout: float = 5.0) -> tuple[bool, str | None]:
    """Return (running, detail), with a bounded one-shot Task Scheduler query."""
    if os.name != "nt":
        return False, None
    script = (
        "$ErrorActionPreference='Stop'; "
        "$x=Get-ScheduledTask | Where-Object { $_.TaskName -like 'HHStudio.GT06.*' -and $_.State -eq 'Running' }; "
        "if ($null -ne $x) { $x | ForEach-Object { $_.TaskName } }"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=timeout,
            startupinfo=_startupinfo(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"scheduled-task-query-unavailable:{type(exc).__name__}"
    if result.returncode != 0:
        return False, f"scheduled-task-query-exit:{result.returncode}"
    names = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return bool(names), ";".join(names) if names else None


def measurement_guard_status() -> tuple[bool, str | None, bool]:
    """Return (blocked, reason, query_unknown), without touching global state."""
    path = lock_path()
    if path.exists():
        return True, f"measure-lock:{path}", False
    running, detail = scheduled_gt06_running()
    if detail and detail.startswith("scheduled-task-query-"):
        return True, detail, True
    if running:
        return True, f"scheduled-task:{detail}", False
    return False, None, False


def _redact_text(text: str) -> str:
    lines = []
    for line in text.splitlines(keepends=True):
        if _SENSITIVE.search(line):
            lines.append("[REDACTED_SENSITIVE_LINE]" + ("\n" if line.endswith("\n") else ""))
        else:
            lines.append(line)
    return "".join(lines)


def _reader(source, destination: Path) -> None:
    with destination.open("w", encoding="utf-8", newline="") as handle:
        while True:
            chunk = source.readline()
            if not chunk:
                return
            if isinstance(chunk, bytes):
                chunk = chunk.decode("utf-8", errors="replace")
            handle.write(_redact_text(chunk))
            handle.flush()


def redact_command(command: Sequence[str]) -> list[str]:
    output: list[str] = []
    redact_next = False
    for token in command:
        token = os.fspath(token)
        if redact_next:
            output.append("[REDACTED]")
            redact_next = False
        elif _SENSITIVE.search(token):
            if "=" in token:
                output.append(token.split("=", 1)[0] + "=[REDACTED]")
            else:
                output.append(token)
                redact_next = token.startswith("-") or token.lower() in {"password", "token", "secret"}
        else:
            output.append(token)
    return output


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _hash_sources(paths: Sequence[Path], root: Path, command: Sequence[str]) -> str:
    digest = hashlib.sha256()
    if not paths:
        digest.update(b"command-spec\0")
        digest.update(json.dumps(list(command), ensure_ascii=False, separators=(",", ":")).encode())
        return digest.hexdigest()
    for original in sorted(paths, key=lambda p: os.fspath(p).lower()):
        resolved = original.resolve()
        if not _inside(resolved, root):
            raise ValueError(f"source path escapes project root: {original}")
        if not resolved.exists():
            raise ValueError(f"source path does not exist: {original}")
        files = [resolved] if resolved.is_file() else sorted((p for p in resolved.rglob("*") if p.is_file()), key=lambda p: os.fspath(p).lower())
        for path in files:
            path = path.resolve()
            if not _inside(path, root):
                raise ValueError(f"source path escapes project root: {path}")
            if ".godot" in path.parts or (".local" in path.parts and "runs" in path.parts):
                continue
            rel = path.relative_to(root).as_posix().encode()
            digest.update(len(rel).to_bytes(4, "big")); digest.update(rel)
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
    return digest.hexdigest()


def _safe_command(command: Sequence[str], root: Path) -> None:
    if not command or any("\x00" in str(token) for token in command):
        raise ValueError("empty command or NUL byte")
    executable = Path(os.path.expandvars(os.fspath(command[0])))
    name = executable.name.lower()
    if name in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe", "sh", "bash", "zsh"}:
        raise ValueError("shell executables are not allowed")
    resolved = Path(shutil.which(os.fspath(executable)) or executable).resolve()
    python_executable = name.startswith("python") or name in {"py", "py.exe"} or resolved == Path(sys.executable).resolve()
    pin_root = (root / ".local" / "tooling").resolve()
    in_pin = _inside(resolved, pin_root)
    if name.startswith("godot") and not in_pin:
        raise ValueError("Godot executable must be under project .local/tooling")
    if not python_executable and not in_pin:
        raise ValueError("only Python tests or a pinned .local/tooling executable are allowed")
    if name.startswith("godot") and not resolved.exists():
        raise ValueError(f"pinned Godot executable does not exist: {resolved}")


class _ProcessContainer:
    """Windows Job Object; POSIX process group fallback is for source tests."""
    def __init__(self) -> None:
        self.handle = None
        self._windows = os.name == "nt"
        if self._windows:
            self._open_job()

    def _open_job(self) -> None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32 = kernel32
        for function, args, result in (
            ("CreateJobObjectW", [wintypes.LPVOID, wintypes.LPCWSTR], wintypes.HANDLE),
            ("SetInformationJobObject", [wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD], wintypes.BOOL),
            ("AssignProcessToJobObject", [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            ("CloseHandle", [wintypes.HANDLE], wintypes.BOOL),
        ):
            proc = getattr(kernel32, function); proc.argtypes = args; proc.restype = result

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong), ("PerJobUserTimeLimit", ctypes.c_longlong), ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t), ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD), ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]
        class Io(ctypes.Structure):
            _fields_ = [(name, ctypes.c_ulonglong) for name in ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount", "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]
        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", Io), ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
        info = Extended(); info.BasicLimitInformation.LimitFlags = 0x2000
        if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
            kernel32.CloseHandle(job); raise OSError(ctypes.get_last_error(), "SetInformationJobObject failed")
        self.handle = job

    def popen_kwargs(self) -> dict:
        if self._windows:
            # Popen closes its primary-thread handle, so CREATE_SUSPENDED cannot be resumed safely
            # through its public/private API. Attach immediately after creation; the Job Object
            # still owns the process tree and is closed on timeout/guard failure.
            return {"creationflags": _WIN_CREATE_NEW_PROCESS_GROUP, "startupinfo": _startupinfo()}
        return {"start_new_session": True}

    def attach_and_resume(self, proc: subprocess.Popen) -> None:
        if self._windows:
            if not self._kernel32.AssignProcessToJobObject(self.handle, proc._handle):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

    def terminate(self, proc: subprocess.Popen) -> None:
        if self._windows:
            self.close(); return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            try: proc.kill()
            except OSError: pass

    def close(self) -> None:
        if self._windows and self.handle:
            self._kernel32.CloseHandle(self.handle); self.handle = None


class ProjectLock:
    def __init__(self, path: Path, payload: dict):
        self.path, self.payload, self.owned = path, payload, False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open("x", encoding="utf-8") as handle:
                json.dump(self.payload, handle, separators=(",", ":")); handle.write("\n")
            self.owned = True
        except FileExistsError as exc:
            raise RuntimeError(f"project writer lock exists: {self.path}") from exc

    def release(self) -> None:
        if not self.owned: return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
            if current.get("run_id") == self.payload.get("run_id"):
                self.path.unlink(missing_ok=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        self.owned = False


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def run(argv: Sequence[str]) -> tuple[int, dict]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, action="append", default=[])
    parser.add_argument("--command-id")
    parser.add_argument("--seed"); parser.add_argument("--map"); parser.add_argument("--mode")
    parser.add_argument("--task-poll-seconds", type=float, default=DEFAULT_TASK_POLL_SECONDS)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(list(argv))
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command: parser.error("a command is required after --")
    if not 0 < args.timeout <= MAX_TIMEOUT_SECONDS: parser.error("--timeout is outside bounded range")
    if not 0.25 <= args.task_poll_seconds <= 60: parser.error("--task-poll-seconds is outside bounded range")

    root = args.project_root.resolve(); _safe_command(command, root)
    source_paths = [path if path.is_absolute() else root / path for path in args.source]
    source_hash = _hash_sources(source_paths, root, command)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:10]
    command_id = args.command_id or f"cmd.guard.{uuid.uuid4().hex}"
    lock = ProjectLock(root / ".local" / "run_guarded.lock", {"run_id": run_id, "pid": os.getpid(), "started_utc": utc_now()})
    # Take the project lease before creating even the per-run evidence folder.
    # This keeps two wrappers from mutating the same product tree concurrently.
    lock.acquire()
    run_dir = root / ".local" / "runs" / run_id
    try:
        run_dir.mkdir(parents=True, exist_ok=False)
    except Exception:
        lock.release()
        raise
    result = {"schema": 1, "run_id": run_id, "command_id": command_id, "source_hash": source_hash, "seed": args.seed, "map": args.map, "mode": args.mode, "command": redact_command(command), "cwd": str(root), "started_utc": utc_now(), "status": "STARTING", "stdout": str(run_dir / "stdout.log"), "stderr": str(run_dir / "stderr.log")}
    try:
        _write_json(run_dir / "manifest.json", result)
    except Exception:
        lock.release()
        raise
    try:
        blocked, reason, _ = measurement_guard_status()
        if blocked: result.update(status="MEASURE_GUARD_BLOCKED", guard_reason=reason); return EXIT_GUARD, result
        blocked, reason, _ = measurement_guard_status()
        if blocked: result.update(status="MEASURE_GUARD_BLOCKED", guard_reason=reason); return EXIT_GUARD, result
        container = _ProcessContainer(); proc = None; threads: list[threading.Thread] = []
        started = time.monotonic(); guard_reason = None; timed_out = False
        try:
            proc = subprocess.Popen(list(command), cwd=str(root), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **container.popen_kwargs())
            try: container.attach_and_resume(proc)
            except Exception:
                container.terminate(proc); proc.wait(timeout=2); raise
            assert proc.stdout is not None and proc.stderr is not None
            threads = [threading.Thread(target=_reader, args=(proc.stdout, run_dir / "stdout.log"), daemon=True), threading.Thread(target=_reader, args=(proc.stderr, run_dir / "stderr.log"), daemon=True)]
            for thread in threads: thread.start()
            last_task_check = 0.0
            while proc.poll() is None:
                now = time.monotonic()
                if now - started >= args.timeout: timed_out = True; break
                if lock_path().exists(): guard_reason = "measure-lock-started"; break
                if now - last_task_check >= args.task_poll_seconds:
                    last_task_check = now; blocked, reason, _ = measurement_guard_status()
                    if blocked: guard_reason = reason; break
                time.sleep(LOCK_POLL_SECONDS)
            if timed_out or guard_reason: container.terminate(proc)
            else: container.close()
            try: actual_exit = proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                container.terminate(proc); actual_exit = proc.wait(timeout=3)
            for thread in threads: thread.join(timeout=2)
            result.update(exit_code=actual_exit, host_exit_code=actual_exit, actual_exit_code=actual_exit, duration_seconds=round(time.monotonic() - started, 3), timed_out=timed_out)
            if guard_reason: result.update(status="MEASURE_WINDOW_STARTED", guard_reason=guard_reason); return EXIT_GUARD, result
            if timed_out: result["status"] = "TIMEOUT"; return EXIT_TIMEOUT, result
            combined = "".join(path.read_text(encoding="utf-8", errors="replace") for path in (run_dir / "stdout.log", run_dir / "stderr.log"))
            diagnostics = [line.strip() for line in combined.splitlines() if _DIAGNOSTIC.search(line)]; result["diagnostics"] = diagnostics[:50]
            if diagnostics: result["status"] = "FAILED_DIAGNOSTICS"; return EXIT_DIAGNOSTIC, result
            result["status"] = "EXITED"; return int(actual_exit), result
        finally: container.close()
    finally:
        result.setdefault("finished_utc", utc_now()); result.setdefault("duration_seconds", 0.0)
        _write_json(run_dir / "manifest.json", result)
        if args.evidence: args.evidence.parent.mkdir(parents=True, exist_ok=True); _write_json(args.evidence, result)
        print(json.dumps(result, ensure_ascii=False)); lock.release()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        code, _ = run(sys.argv[1:] if argv is None else argv); return code
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "GUARD_ERROR", "error": str(exc)}, ensure_ascii=False)); return EXIT_CONTAINMENT


if __name__ == "__main__":
    raise SystemExit(main())
