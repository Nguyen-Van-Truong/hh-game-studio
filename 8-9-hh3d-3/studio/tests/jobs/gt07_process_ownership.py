"""GT-07 M8 host/process diagnostics.

This module deliberately stays below the Godot/Blender layer.  It starts a
small gated Python worker, assigns that worker to the existing Windows Job
owner, and records native PID/start-time/Job/handle observations.  A report
from this module is diagnostic (authority 0); it is not product acceptance.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable

STUDIO = Path(__file__).resolve().parents[2]
REVIEWS = STUDIO / ".local" / "reviews"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,96}$")
SCHEMA = "gt07-m8-process-ownership-1"
MEMORY_CAP = 64 * 1024 * 1024
WAIT_SECONDS = 8.0

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
STILL_ACTIVE = 259
ERROR_MORE_DATA = 234
JOB_OBJECT_BASIC_PROCESS_ID_LIST = 3
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender.ui_host import cli_job


class NativeDiagnosticError(RuntimeError):
    """A native query or identity operation could not be proven."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _fresh_output(output_root: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("RUN_ID_INVALID")
    root = output_root.expanduser().resolve()
    allowed = REVIEWS.expanduser().resolve()
    try:
        root.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_ROOT_FORBIDDEN") from error
    output = (root / run_id).resolve()
    try:
        output.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_PATH_TRAVERSAL") from error
    if output.exists():
        raise ValueError("RUN_ID_USED")
    output.mkdir(parents=True)
    return output


def _reuse_dry_run(output_root: Path, run_id: str) -> Path:
    """Admit native work only through the matching engine-free receipt."""
    root = output_root.expanduser().resolve()
    allowed = REVIEWS.expanduser().resolve()
    try:
        root.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_ROOT_FORBIDDEN") from error
    output = (root / run_id).resolve()
    try:
        output.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_PATH_TRAVERSAL") from error
    receipt = output / "report.json"
    if not receipt.is_file():
        raise ValueError("DRY_RUN_REQUIRED")
    try:
        report = json.loads(receipt.read_bytes())
    except (OSError, ValueError) as error:
        raise ValueError("DRY_RUN_RECEIPT_INVALID") from error
    if (report.get("schema") != SCHEMA or report.get("run_id") != run_id
            or report.get("dry_run") is not True or report.get("authority") != 0
            or report.get("diagnostic_only") is not True
            or report.get("source_hashes") != _source_hashes()):
        raise ValueError("DRY_RUN_RECEIPT_INVALID")
    if report.get("verified") is not None or report.get("scenarios") != []:
        raise ValueError("DRY_RUN_RECEIPT_CONSUMED")
    return output


def _kernel() -> Any:
    if os.name != "nt":
        raise NativeDiagnosticError("WINDOWS_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD)]
    kernel.QueryInformationJobObject.restype = wintypes.BOOL
    kernel.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, wintypes.INT, wintypes.LPVOID, wintypes.DWORD]
    kernel.SetInformationJobObject.restype = wintypes.BOOL
    kernel.VirtualAlloc.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel.VirtualAlloc.restype = wintypes.LPVOID
    kernel.VirtualFree.argtypes = [wintypes.LPVOID, ctypes.c_size_t, wintypes.DWORD]
    kernel.VirtualFree.restype = wintypes.BOOL
    return kernel


def _handle_number(handle: Any) -> int:
    value = getattr(handle, "value", handle)
    return int(value)


def _filetime(value: wintypes.FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _process_start(handle: Any) -> int:
    kernel = _kernel()
    values = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
        raise NativeDiagnosticError(f"GET_PROCESS_TIMES:{ctypes.get_last_error()}")
    return _filetime(values[0])


def _open_process(pid: int) -> Any:
    kernel = _kernel()
    handle = kernel.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not handle:
        raise NativeDiagnosticError(f"OPEN_PROCESS:{ctypes.get_last_error()}")
    return handle


def _close_handle(handle: Any) -> None:
    if handle:
        kernel = _kernel()
        if not kernel.CloseHandle(handle):
            raise NativeDiagnosticError(f"CLOSE_HANDLE:{ctypes.get_last_error()}")


def _alive(handle: Any) -> bool:
    result = _kernel().WaitForSingleObject(handle, 0)
    if result == WAIT_TIMEOUT:
        return True
    if result == WAIT_OBJECT_0:
        return False
    raise NativeDiagnosticError(f"WAIT_PROCESS:{result}")


def _wait_exit(handle: Any, timeout: float) -> int:
    result = _kernel().WaitForSingleObject(handle, max(0, int(timeout * 1000)))
    if result == WAIT_TIMEOUT:
        raise NativeDiagnosticError("PROCESS_EXIT_TIMEOUT")
    if result != WAIT_OBJECT_0:
        raise NativeDiagnosticError(f"WAIT_PROCESS:{result}")
    code = wintypes.DWORD()
    if not _kernel().GetExitCodeProcess(handle, ctypes.byref(code)):
        raise NativeDiagnosticError(f"GET_EXIT_CODE:{ctypes.get_last_error()}")
    return int(code.value)


def _identity(pid: int, handle: Any) -> dict[str, int]:
    return {"pid": int(pid), "creation_filetime": _process_start(handle)}


def _identity_matches(expected: dict[str, int], observed: dict[str, int]) -> bool:
    return (type(expected.get("pid")) is int and type(expected.get("creation_filetime")) is int
            and expected == observed)


def _terminate_exact(handle: Any, expected: dict[str, int]) -> None:
    """Terminate only a retained handle whose PID/start identity still matches."""
    observed = _identity(expected["pid"], handle)
    if not _identity_matches(expected, observed):
        raise NativeDiagnosticError("PROCESS_START_MISMATCH")
    if not _kernel().TerminateProcess(handle, 137):
        raise NativeDiagnosticError(f"TERMINATE_PROCESS:{ctypes.get_last_error()}")


class _BasicLimit(ctypes.Structure):
    _fields_ = [
        ("per_process_user_time", ctypes.c_longlong),
        ("per_job_user_time", ctypes.c_longlong),
        ("limit_flags", wintypes.DWORD),
        ("minimum_working_set", ctypes.c_size_t),
        ("maximum_working_set", ctypes.c_size_t),
        ("active_process_limit", wintypes.DWORD),
        ("affinity", ctypes.c_size_t),
        ("priority_class", wintypes.DWORD),
        ("scheduling_class", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [("values", ctypes.c_ulonglong * 6)]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [
        ("basic", _BasicLimit),
        ("io", _IoCounters),
        ("process_memory_limit", ctypes.c_size_t),
        ("job_memory_limit", ctypes.c_size_t),
        ("peak_process_memory", ctypes.c_size_t),
        ("peak_job_memory", ctypes.c_size_t),
    ]


def _query_job_process_ids(handle: Any) -> list[int]:
    kernel = _kernel()
    size = 64
    for _ in range(6):
        buffer = ctypes.create_string_buffer(size)
        returned = wintypes.DWORD()
        if kernel.QueryInformationJobObject(handle, JOB_OBJECT_BASIC_PROCESS_ID_LIST,
                                            buffer, size, ctypes.byref(returned)):
            assigned = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD))[0]
            count = ctypes.cast(ctypes.byref(buffer, 4), ctypes.POINTER(wintypes.DWORD))[0]
            offset = ctypes.sizeof(wintypes.DWORD) * 2
            item_size = ctypes.sizeof(ctypes.c_size_t)
            if count > assigned or offset + count * item_size > size:
                raise NativeDiagnosticError("JOB_PROCESS_LIST_INVALID")
            return [int(ctypes.c_size_t.from_buffer_copy(buffer, offset + item_size * index).value)
                    for index in range(count)]
        error = ctypes.get_last_error()
        if error != ERROR_MORE_DATA:
            raise NativeDiagnosticError(f"QUERY_JOB_PROCESS_IDS:{error}")
        size *= 4
    raise NativeDiagnosticError("QUERY_JOB_PROCESS_IDS_TOO_LARGE")


def _configure_job_memory(handle: Any, cap: int) -> None:
    if not 64 * 1024 * 1024 <= cap <= 128 * 1024 * 1024:
        raise ValueError("JOB_MEMORY_CAP_OUT_OF_RANGE")
    limits = _ExtendedLimit()
    limits.basic.limit_flags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | JOB_OBJECT_LIMIT_JOB_MEMORY
    limits.job_memory_limit = cap
    if not _kernel().SetInformationJobObject(handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                              ctypes.byref(limits), ctypes.sizeof(limits)):
        raise NativeDiagnosticError(f"SET_JOB_MEMORY_LIMIT:{ctypes.get_last_error()}")


def _query_job_limits(handle: Any) -> dict[str, int]:
    limits = _ExtendedLimit()
    returned = wintypes.DWORD()
    if not _kernel().QueryInformationJobObject(handle, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
                                               ctypes.byref(limits), ctypes.sizeof(limits),
                                               ctypes.byref(returned)):
        raise NativeDiagnosticError(f"QUERY_JOB_LIMITS:{ctypes.get_last_error()}")
    if returned.value != ctypes.sizeof(limits):
        raise NativeDiagnosticError("QUERY_JOB_LIMITS_SIZE")
    return {"limit_flags": int(limits.basic.limit_flags),
            "job_memory_limit": int(limits.job_memory_limit)}


def _job_identity(owner: Any, root: dict[str, int], *, query: Callable[[Any], list[int]] = _query_job_process_ids) -> dict[str, Any]:
    """Build an identity only after both the retained Job handle and query agree."""
    try:
        process_ids = query(owner._handle)
        if root["pid"] not in process_ids:
            raise NativeDiagnosticError("JOB_ROOT_NOT_ASSIGNED")
        return {"handle_value": _handle_number(owner._handle), "root": root,
                "process_ids": sorted(int(pid) for pid in process_ids), "verified": True}
    except Exception as error:
        return {"handle_value": _handle_number(owner._handle) if owner._handle else None,
                "root": root, "process_ids": [], "verified": False,
                "error": str(error)}


WORKER = r'''import ctypes, json, os, pathlib, subprocess, sys, time
def save(path, value):
    p = pathlib.Path(path); t = p.with_name(p.name + ".pending")
    t.write_text(json.dumps(value, sort_keys=True), encoding="utf-8"); t.replace(p)
def gate():
    if sys.stdin.buffer.readline(4097) != b"GO\n": sys.exit(74)
def wait_forever():
    while True: time.sleep(1)
mode, marker = sys.argv[1], sys.argv[2]
if mode == "descendant":
    save(marker, {"pid": os.getpid()}); wait_forever()
gate()
if mode == "tree":
    child_marker = sys.argv[3]
    child = subprocess.Popen([sys.executable, "-B", __file__, "descendant", child_marker],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    save(marker, {"pid": os.getpid(), "child_pid": child.pid}); wait_forever()
if mode == "single":
    save(marker, {"pid": os.getpid()}); wait_forever()
if mode == "sentinel":
    save(marker, {"pid": os.getpid()}); wait_forever()
if mode == "memory":
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
    kernel.VirtualAlloc.restype = ctypes.c_void_p
    kernel.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong]
    kernel.VirtualFree.restype = ctypes.c_bool
    allocations, denied, last_error = [], False, 0
    for _ in range(128):
        pointer = kernel.VirtualAlloc(None, 4 * 1024 * 1024, 0x3000, 0x04)
        if not pointer:
            denied, last_error = True, ctypes.get_last_error(); break
        allocations.append(pointer)
    for pointer in allocations: kernel.VirtualFree(pointer, 0, 0x8000)
    save(marker, {"native_virtualalloc_denied": denied, "last_error": int(last_error),
                  "allocations": len(allocations), "python_memory_error": False})
    wait_forever()
sys.exit(75)
'''


def _write_worker(output: Path) -> Path:
    path = output / "m8_worker.py"
    path.write_text(WORKER, encoding="utf-8", newline="\n")
    return path


def _read_json(path: Path, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if type(value) is dict:
                return value
            raise NativeDiagnosticError("WORKER_MARKER_INVALID")
        time.sleep(.02)
    raise NativeDiagnosticError("WORKER_MARKER_TIMEOUT")


def _spawn(worker: Path, mode: str, output: Path, *extra: Path) -> tuple[subprocess.Popen, Any, dict[str, int]]:
    stdout = (output / f"{mode}.stdout.log").open("xb")
    stderr = (output / f"{mode}.stderr.log").open("xb")
    process = subprocess.Popen([sys.executable, "-B", str(worker), mode,
                                str(output / f"{mode}.json"), *(str(item) for item in extra)],
                               stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    stdout.close(); stderr.close()
    retained = _open_process(process.pid)
    identity = _identity(process.pid, retained)
    return process, retained, identity


def _send_go(process: subprocess.Popen) -> None:
    if process.stdin is None:
        raise NativeDiagnosticError("WORKER_STDIN_MISSING")
    process.stdin.write(b"GO\n"); process.stdin.flush(); process.stdin.close()


def _close_process_handle(process: subprocess.Popen) -> None:
    handle = getattr(process, "_handle", None)
    if handle is None:
        return
    close = getattr(handle, "Close", None)
    if close is not None:
        close()
    else:
        _close_handle(handle)
    process._handle = None


def _finish(process: subprocess.Popen, handle: Any, owner: Any | None) -> dict[str, Any]:
    error = None
    exit_code = None
    owner_snapshot = None
    try:
        if _alive(handle):
            if owner is not None:
                owner.terminate()
            else:
                _terminate_exact(handle, _identity(process.pid, handle))
        exit_code = _wait_exit(handle, WAIT_SECONDS)
        process.wait(timeout=WAIT_SECONDS)
    except Exception as failure:
        error = str(failure)
    finally:
        try:
            if owner is not None:
                owner.close()
                owner_snapshot = owner.snapshot()
        except Exception as failure:
            error = error or str(failure)
        try:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
        except Exception as failure:
            error = error or str(failure)
        try:
            if process.poll() is not None:
                _close_process_handle(process)
        except Exception as failure:
            error = error or str(failure)
        try:
            _close_handle(handle)
        except Exception as failure:
            error = error or str(failure)
    return {"exit_code": exit_code, "error": error, "owner": owner_snapshot}


def run_held_identity(output: Path, worker: Path) -> dict[str, Any]:
    process = retained = owner = None
    report: dict[str, Any] = {"scenario": "held-identity", "verified": False, "errors": []}
    try:
        process, retained, root = _spawn(worker, "single", output)
        owner = cli_job.create(process)
        _send_go(process)
        _read_json(output / "single.json", time.monotonic() + 3)
        report["job"] = _job_identity(owner, root)
        forged = {**root, "creation_filetime": root["creation_filetime"] + 1}
        try:
            _terminate_exact(retained, forged)
            report["errors"].append("FORGED_TERMINATION_ACCEPTED")
        except NativeDiagnosticError as error:
            report["forged_kill_refused"] = str(error) == "PROCESS_START_MISMATCH"
        report["alive_before_cleanup"] = _alive(retained)
        cleanup = _finish(process, retained, owner)
        report["cleanup"] = cleanup
        report["verified"] = bool(report["job"].get("verified") and report.get("forged_kill_refused")
                                   and report.get("alive_before_cleanup") and cleanup["error"] is None
                                   and cleanup["exit_code"] is not None)
    except Exception as error:
        report["errors"].append(str(error))
        if process is not None and retained is not None:
            _finish(process, retained, owner)
    return report


def run_owned_timeout(output: Path, worker: Path) -> dict[str, Any]:
    process = retained = child_handle = sentinel = sentinel_handle = owner = None
    report: dict[str, Any] = {"scenario": "owned-timeout", "verified": False, "errors": []}
    try:
        sentinel, sentinel_handle, sentinel_identity = _spawn(worker, "sentinel", output)
        process, retained, root = _spawn(worker, "tree", output, output / "descendant.json")
        owner = cli_job.create(process)
        _send_go(process)
        meta = _read_json(output / "tree.json", time.monotonic() + 3)
        child_meta = _read_json(output / "descendant.json", time.monotonic() + 3)
        child_handle = _open_process(int(child_meta["pid"]))
        job = _job_identity(owner, root)
        job["descendant"] = _identity(int(child_meta["pid"]), child_handle)
        job["process_ids_after_spawn"] = _query_job_process_ids(owner._handle)
        report["job"] = job
        timeout_result = _kernel().WaitForSingleObject(retained, 250)
        if timeout_result != WAIT_TIMEOUT:
            raise NativeDiagnosticError(f"TIMEOUT_NOT_BOUNDED:{timeout_result}")
        report["timeout_bound_ms"] = 250
        report["timed_out"] = True
        owner.terminate()
        root_exit = _wait_exit(retained, WAIT_SECONDS)
        child_exit = _wait_exit(child_handle, WAIT_SECONDS)
        report["actual_exits"] = {"root": root_exit, "descendant": child_exit}
        report["sentinel_alive_before_cleanup"] = _alive(sentinel_handle)
        owner.close()
        report["sentinel_alive_after_cleanup"] = _alive(sentinel_handle)
        report["sentinel_cleanup"] = _finish(sentinel, sentinel_handle, None)
        _close_handle(child_handle); child_handle = None
        _close_handle(retained); retained = None
        report["verified"] = bool(job["verified"] and root["pid"] in job["process_ids_after_spawn"]
                                   and int(meta["child_pid"]) == int(child_meta["pid"])
                                   and root_exit != STILL_ACTIVE and child_exit != STILL_ACTIVE
                                   and report["sentinel_alive_before_cleanup"]
                                   and report["sentinel_alive_after_cleanup"]
                                   and report["sentinel_cleanup"]["error"] is None)
    except Exception as error:
        report["errors"].append(str(error))
    finally:
        if owner is not None:
            try: owner.close()
            except Exception: pass
        for process_handle in (child_handle, retained, sentinel_handle):
            if process_handle:
                try: _close_handle(process_handle)
                except Exception: pass
        for process in (process, sentinel):
            if process is not None:
                try: process.kill(); process.wait(timeout=2)
                except Exception: pass
    return report


def run_memory_limit(output: Path, worker: Path) -> dict[str, Any]:
    process = retained = owner = None
    report: dict[str, Any] = {"scenario": "job-memory-limit", "verified": False, "errors": []}
    try:
        process, retained, root = _spawn(worker, "memory", output)
        def before_assign(current_owner: Any) -> None:
            _configure_job_memory(current_owner._handle, MEMORY_CAP)
        owner = cli_job.create(process, before_assign=before_assign)
        _send_go(process)
        allocation = _read_json(output / "memory.json", time.monotonic() + WAIT_SECONDS)
        limits = _query_job_limits(owner._handle)
        job = _job_identity(owner, root)
        cleanup = _finish(process, retained, owner)
        report.update({"job": job, "limits": limits,
                       "allocation": allocation, "cleanup": cleanup})
        report["verified"] = bool(report["job"]["verified"]
                                   and limits["job_memory_limit"] == MEMORY_CAP
                                   and limits["limit_flags"] & JOB_OBJECT_LIMIT_JOB_MEMORY
                                   and allocation.get("native_virtualalloc_denied") is True
                                   and type(allocation.get("last_error")) is int
                                   and allocation.get("last_error", 0) > 0
                                   and allocation.get("python_memory_error") is False
                                   and cleanup["error"] is None)
    except Exception as error:
        report["errors"].append(str(error))
        if process is not None and retained is not None:
            _finish(process, retained, owner)
    return report


def _source_hashes() -> dict[str, str]:
    paths = [Path(__file__), STUDIO / "godot-addon" / "cli_job.py",
             STUDIO / "host" / "blender" / "ui_host.py"]
    values = {path.relative_to(STUDIO).as_posix(): _sha256(path) for path in paths}
    values["source_closure_sha256"] = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return values


def run_diagnostic(output_root: Path, run_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    output = (_fresh_output(output_root, run_id) if dry_run
              else _reuse_dry_run(output_root, run_id))
    report: dict[str, Any] = {"schema": SCHEMA, "authority": 0,
                              "diagnostic_only": True, "run_id": run_id,
                              "source_hashes": _source_hashes(),
                              "platform": os.name, "engine_started": False,
                              "scenarios": []}
    if dry_run:
        report["dry_run"] = True
        _json_write(output / "report.json", report)
        return report
    worker = None
    try:
        if os.name != "nt":
            raise ValueError("WINDOWS_REQUIRED")
        worker = _write_worker(output)
        from studio.tests.jobs.run_gt07_scenarios import _native_measure_guard
        with _native_measure_guard():
            for function in (run_held_identity, run_owned_timeout, run_memory_limit):
                report["scenarios"].append(function(output, worker))
    except Exception as error:
        report["status"] = "ERROR"
        report["errors"] = [str(error)]
    report["verified"] = bool(report["scenarios"] and
                               all(row.get("verified") is True for row in report["scenarios"]))
    if worker is not None and worker.is_file():
        report["worker_sha256"] = _sha256(worker)
    _json_write(output / "report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, default=REVIEWS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run_diagnostic(args.output, args.run_id, dry_run=args.dry_run)
    except Exception as error:
        print(json.dumps({"schema": SCHEMA, "authority": 0,
                          "diagnostic_only": True, "run_id": args.run_id,
                          "status": "ERROR", "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("dry_run") or result.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
