"""Bounded diagnostic cut of a gated, directly owned Windows process.

Uses the accepted CLI Job owner. A matched receipt permits killing only the
held child process handle; Job termination is separately reported as cleanup.
It proves a process cut, never publication/recovery acceptance by itself.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time

from studio.host.blender.ui_host import cli_job


def _created(process) -> int:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    call = kernel.GetProcessTimes
    call.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    call.restype = wintypes.BOOL
    values = [wintypes.FILETIME() for _ in range(4)]
    if not call(int(process._handle), *(ctypes.byref(value) for value in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime


def _receipt(path: Path, *, process, run_id: str, phase: str, started_ns: int) -> dict:
    value = json.loads(path.read_bytes())
    if (type(value) is not dict or value.get("schema") != "HH-GT07-FAILPOINT-REACHED-1"
            or value.get("run_id") != run_id or value.get("phase") != phase
            or type(value.get("pid")) is not int or value["pid"] != process.pid
            or type(value.get("monotonic_ns")) is not int
            or not started_ns <= value["monotonic_ns"] <= time.monotonic_ns()):
        raise ValueError("CRASH_RECEIPT_BINDING_MISMATCH")
    return value


def run_cut(command: list[str], *, cwd: Path, output: Path, env: dict,
            receipt_path: Path, run_id: str, phase: str, timeout: float = 240) -> dict:
    if os.name != "nt":
        raise ValueError("CRASH_WINDOWS_REQUIRED")
    if receipt_path.exists():
        raise ValueError("CRASH_RECEIPT_NOT_FRESH")
    process = job = None
    report = {"schema": "gt07-owned-crash-process-1", "run_id": run_id,
              "phase": phase, "cwd": str(cwd), "target_pid": None,
              "target_creation_filetime": None, "receipt": None,
              "target_terminated": False, "timed_out": False,
              "exit_code": None, "natural_exit": None,
              "tree_cleanup_terminated": False, "process_handle_closed": False,
              "job": None, "errors": [], "cut_verified": False}
    started_ns = time.monotonic_ns()
    environment = {**env, "HH_GT07_CRASH_GATE": "1"}
    cli_job.require_no_holds()
    with (output / "crash.stdout.log").open("xb") as stdout, \
            (output / "crash.stderr.log").open("xb") as stderr:
        try:
            process = subprocess.Popen(command, cwd=cwd, env=environment,
                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            report["target_pid"] = process.pid
            report["target_creation_filetime"] = _created(process)
            job = cli_job.create(process)
            process.stdin.write(b"GO\n")
            process.stdin.flush()
            process.stdin.close()
            deadline = time.monotonic() + timeout
            while process.poll() is None:
                if receipt_path.is_file():
                    report["receipt"] = _receipt(receipt_path, process=process,
                        run_id=run_id, phase=phase, started_ns=started_ns)
                    if _created(process) != report["target_creation_filetime"]:
                        raise ValueError("CRASH_PROCESS_IDENTITY_CHANGED")
                    process.kill()  # Exact held process handle, never a PID lookup.
                    report["target_terminated"] = True
                    break
                if time.monotonic() >= deadline:
                    report["timed_out"] = True
                    raise TimeoutError("CRASH_PHASE_NOT_REACHED")
                time.sleep(.05)
            report["exit_code"] = process.wait(timeout=5)
            report["natural_exit"] = not report["target_terminated"]
        except Exception as error:
            report["errors"].append({"type": type(error).__name__, "code": str(error)})
        finally:
            if job is None and process is not None:
                job = cli_job.owner_for_process(process)
            if job is not None:
                try:
                    # Allow KILL_ON_CLOSE on the crashed owner's inner jobs to
                    # drain children before resorting to outer-tree cleanup.
                    deadline = time.monotonic() + 2
                    active = job.active_count()
                    while active and time.monotonic() < deadline:
                        time.sleep(.05)
                        active = job.active_count()
                    report["tree_cleanup_terminated"] = active != 0
                    job.close()
                except Exception as error:
                    report["errors"].append({"type": type(error).__name__, "code": str(error)})
                report["job"] = job.snapshot()
            if process is not None:
                try:
                    if process.poll() is None:
                        process.kill()  # Still this handle, including setup failures.
                    report["exit_code"] = process.wait(timeout=5)
                    if process.stdin and not process.stdin.closed:
                        process.stdin.close()
                    process._handle.Close()
                    report["process_handle_closed"] = True
                except Exception as error:
                    report["errors"].append({"type": type(error).__name__, "code": str(error)})
    state = report["job"] or {}
    report["tree_verified"] = bool(
        all(state.get(key) is True for key in ("configured", "assigned", "zero_observed", "closed"))
        and all(state.get(key) is False for key in ("tainted", "handle_retained", "create_uncertain", "close_uncertain"))
        and state.get("active_count") == 0 and state.get("failed_operations") == [])
    report["cut_verified"] = bool(report["target_terminated"] and report["receipt"]
        and report["exit_code"] != 0 and not report["timed_out"] and not report["errors"]
        and report["tree_verified"] and report["process_handle_closed"])
    return report
