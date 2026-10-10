"""Demand-only Scheduled Task supervisor for a GT-09 final or rehearsal.

The supervisor deliberately exposes one operation: run one pre-bound matrix
ID and row selection from a request prepared by the coordinator. It does not accept an
arbitrary command or resume a partial matrix.  The Task Scheduler process is
the durable parent of the matrix, while the matrix continues to own every
Godot/Blender/ffmpeg child with its existing checked job wrappers.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

STUDIO = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO.parent
MATRIX = STUDIO / "tests" / "conformance" / "run_gt09_matrix.py"
RUN_RE = re.compile(r"gt09-matrix-(final|rehearsal)-20\d{6}-[a-z0-9-]{1,24}\Z")
SCHEMA = "HH-GT09-TASK-REQUEST-1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def _matrix_module():
    sys.path.insert(0, str(REPO_ROOT))
    from studio.tests.conformance import run_gt09_matrix
    return run_gt09_matrix


def _closure() -> str:
    return _matrix_module()._source_tree_closure()[0]


def _paths(run_id: str) -> tuple[Path, Path]:
    if os.name != "nt" or RUN_RE.fullmatch(run_id) is None:
        raise ValueError("GT09_TASK_RUN_ID")
    matrix_root = STUDIO / ".local" / "reviews" / run_id
    supervisor = STUDIO / ".local" / "reviews" / (run_id + "-task")
    return matrix_root, supervisor


def process_observation() -> dict[str, object]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.GetPriorityClass.argtypes = [w.HANDLE]
    kernel.GetPriorityClass.restype = w.DWORD
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    handle = kernel.GetCurrentProcess()
    created, exited, system, user = (w.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in (created, exited, system, user))):
        raise OSError(ctypes.get_last_error(), "GT09_TASK_PROCESS_TIMES")
    priority = int(kernel.GetPriorityClass(handle))
    if priority != 0x20:
        raise ValueError("GT09_TASK_PRIORITY_NOT_NORMAL")
    return {
        "pid": os.getpid(),
        "parent_pid": os.getppid(),
        "priority_class": priority,
        "process_start": "windows:" + str(created.dwLowDateTime | created.dwHighDateTime << 32),
    }


def _selection(run_id: str, rows: list[str]) -> list[str]:
    """Only the implemented rehearsal dependency graph may be scheduled."""
    match = RUN_RE.fullmatch(run_id)
    if match is None or (rows not in (["K3"], ["K9"]) if match[1] == "rehearsal" else rows != []):
        raise ValueError("GT09_TASK_ROW_SELECTION")
    return rows


def _command(console: Path, run_id: str, matrix_root: Path, rows: list[str]) -> list[str]:
    _selection(run_id, rows)
    mode = ["--rows", ",".join(rows)] if rows else ["--matrix", "final"]
    return [str(console), "-B", str(MATRIX), *mode,
            "--run-id", run_id, "--output", str(matrix_root)]


def prepare(run_id: str, rows: list[str] | None = None) -> Path:
    matrix_root, supervisor = _paths(run_id)
    rows = _selection(run_id, rows or [])
    if matrix_root.exists() or supervisor.exists():
        raise FileExistsError("GT09_TASK_OUTPUT_ALREADY_EXISTS")
    console = Path(sys.executable).resolve().with_name("python.exe")
    windowed = Path(sys.executable).resolve().with_name("pythonw.exe")
    request = {
        "schema": SCHEMA,
        "run_id": run_id,
        "rows": rows,
        "matrix_script_sha256": sha(MATRIX),
        "supervisor_script_sha256": sha(Path(__file__).resolve()),
        "python_sha256": sha(console),
        "pythonw_sha256": sha(windowed),
        "source_closure_sha256": _closure(),
        "prepared_utc": datetime.now(timezone.utc).isoformat(),
    }
    supervisor.mkdir(parents=True)
    try:
        write_new(supervisor / "request.json", request)
        return supervisor
    except BaseException:
        # Only remove the directory we just created; no recursive cleanup of
        # an existing review is ever attempted.
        try:
            (supervisor / "request.json").unlink(missing_ok=True)
            supervisor.rmdir()
        except OSError:
            pass
        raise


def _load_request(run_id: str) -> tuple[Path, Path, dict[str, object]]:
    matrix_root, supervisor = _paths(run_id)
    request_path = supervisor / "request.json"
    if not request_path.is_file() or matrix_root.exists():
        raise ValueError("GT09_TASK_REQUEST_BINDING")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    expected = {
        "schema": SCHEMA,
        "run_id": run_id,
        "rows": _selection(run_id, request.get("rows")),
        "matrix_script_sha256": sha(MATRIX),
        "supervisor_script_sha256": sha(Path(__file__).resolve()),
        "python_sha256": sha(Path(sys.executable).resolve().with_name("python.exe")),
        "pythonw_sha256": sha(Path(sys.executable).resolve().with_name("pythonw.exe")),
        "source_closure_sha256": request.get("source_closure_sha256"),
        "prepared_utc": request.get("prepared_utc"),
    }
    if request != expected or not isinstance(request["source_closure_sha256"], str):
        raise ValueError("GT09_TASK_REQUEST_CHANGED")
    if _closure() != request["source_closure_sha256"]:
        raise ValueError("GT09_TASK_SOURCE_CHANGED")
    return matrix_root, supervisor, request


def run(run_id: str) -> int:
    matrix_root, supervisor, request = _load_request(run_id)
    start = time.monotonic()
    write_new(supervisor / "start.json", {
        **process_observation(), "schema": "HH-GT09-TASK-START-1", "run_id": run_id,
        "source_closure_sha256": request["source_closure_sha256"],
        "started_utc": datetime.now(timezone.utc).isoformat(), "formal_acceptance": False,
    })
    stdout_path, stderr_path = supervisor / "stdout.txt", supervisor / "stderr.txt"
    code = 1
    try:
        console = Path(sys.executable).resolve().with_name("python.exe")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            command = _command(console, run_id, matrix_root, request["rows"])
            proc = subprocess.run(command, cwd=REPO_ROOT, stdout=stdout, stderr=stderr,
                                  check=False)
            code = int(proc.returncode)
    except BaseException:
        with stderr_path.open("ab") as stderr:
            stderr.write(traceback.format_exc().encode())
    finally:
        write_new(supervisor / "return.json", {
            "schema": "HH-GT09-TASK-RETURN-1", "run_id": run_id,
            "returned_exit_code": code, "matrix_root": str(matrix_root),
            "source_closure_sha256": request["source_closure_sha256"],
            "elapsed_seconds": time.monotonic() - start,
            "actual_process_exit_observed": True, "formal_acceptance": False,
        })
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--rows", help="prepare-only rehearsal selection: K3 or K9 with its producers")
    args = parser.parse_args(argv)
    if args.rows and not args.prepare:
        parser.error("--rows is prepare-only; execution uses the pinned request")
    # --prepare is coordinator-side console work; the scheduled action is the
    # only path allowed to execute without it.
    if not args.prepare and Path(sys.executable).name.lower() != "pythonw.exe":
        raise ValueError("GT09_TASK_WINDOWED_INTERPRETER_REQUIRED")
    if args.prepare:
        rows = args.rows.split(",") if args.rows else []
        print(json.dumps({"schema": SCHEMA, "supervisor": str(prepare(args.run_id, rows))}, sort_keys=True))
        return 0
    return run(args.run_id)


if __name__ == "__main__":
    raise SystemExit(main())
