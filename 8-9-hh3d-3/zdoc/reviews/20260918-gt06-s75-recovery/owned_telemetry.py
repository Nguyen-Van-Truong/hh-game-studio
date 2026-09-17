"""Bounded, read-only Windows telemetry for an explicit owned PID allowlist.

Supplemental diagnosis only: this does not implement or replace an RSS gate.
Writes JSONL to stdout only. See owned-telemetry-design.md for the contract.
"""

from __future__ import annotations

import argparse
import ctypes as C
from datetime import datetime, timezone
import hashlib
import json
import math
import ntpath
import os
from pathlib import Path
import re
import sys
import time

DWORD = C.c_uint32
SIZE_T = C.c_size_t
HANDLE = C.c_void_p
BOOL = C.c_int32
ACCESS = 0x1000 | 0x0010  # QUERY_LIMITED_INFORMATION | VM_READ, no escalation.


class FILETIME(C.Structure):
    _fields_ = [("low", DWORD), ("high", DWORD)]

    def integer(self) -> int:
        return (self.high << 32) | self.low


class PROCESS_MEMORY_COUNTERS_EX(C.Structure):
    _fields_ = [("cb", DWORD), ("PageFaultCount", DWORD)] + [
        (name, SIZE_T) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
            "PrivateUsage",
        )
    ]


class PERFORMANCE_INFORMATION(C.Structure):
    _fields_ = [("cb", DWORD)] + [
        (name, SIZE_T) for name in (
            "CommitTotal", "CommitLimit", "CommitPeak", "PhysicalTotal",
            "PhysicalAvailable", "SystemCache", "KernelTotal", "KernelPaged",
            "KernelNonpaged", "PageSize",
        )
    ] + [(name, DWORD) for name in ("HandleCount", "ProcessCount", "ThreadCount")]


class MEMORY_PRIORITY_INFORMATION(C.Structure):
    _fields_ = [("MemoryPriority", DWORD)]


class PROCESS_POWER_THROTTLING_STATE(C.Structure):
    _fields_ = [(name, DWORD) for name in ("Version", "ControlMask", "StateMask")]


class ProbeFailure(Exception):
    def __init__(self, detail: dict):
        self.detail = detail
        super().__init__(detail.get("reason", detail.get("api", "probe_failure")))


def stamp() -> dict:
    return {"utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "monotonic_ns": time.perf_counter_ns()}


def emit(event: str, run_id: str, **fields) -> None:
    print(json.dumps({"schema": "hh.gt06.owned-telemetry.v1", "event": event,
                      "run_id": run_id, **stamp(), **fields},
                     ensure_ascii=True, allow_nan=False, separators=(",", ":")),
          flush=True)


class WinAPI:
    def __init__(self):
        if os.name != "nt":
            raise ProbeFailure({"status": "unavailable", "reason": "windows_only"})
        pointer_size = C.sizeof(HANDLE)
        expected = {4: (44, 56), 8: (80, 104)}.get(pointer_size)
        actual = (C.sizeof(PROCESS_MEMORY_COUNTERS_EX), C.sizeof(PERFORMANCE_INFORMATION))
        if expected != actual:
            raise ProbeFailure({"status": "error", "reason": "native_layout_mismatch",
                                "expected": expected, "actual": actual})
        self.dll = C.WinDLL("kernel32.dll", use_last_error=True)
        self.functions = {}
        signatures = {
            "OpenProcess": ([DWORD, BOOL, DWORD], HANDLE),
            "CloseHandle": ([HANDLE], BOOL),
            "GetProcessTimes": ([HANDLE] + [C.POINTER(FILETIME)] * 4, BOOL),
            "QueryFullProcessImageNameW":
                ([HANDLE, DWORD, C.c_wchar_p, C.POINTER(DWORD)], BOOL),
            "GetExitCodeProcess": ([HANDLE, C.POINTER(DWORD)], BOOL),
            "GetPriorityClass": ([HANDLE], DWORD),
            "GetProcessInformation": ([HANDLE, C.c_int, C.c_void_p, DWORD], BOOL),
            "GetProcessHandleCount": ([HANDLE, C.POINTER(DWORD)], BOOL),
            "K32GetProcessMemoryInfo":
                ([HANDLE, C.POINTER(PROCESS_MEMORY_COUNTERS_EX), DWORD], BOOL),
            "K32GetPerformanceInfo": ([C.POINTER(PERFORMANCE_INFORMATION), DWORD], BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.dll, name, None)
            if function is not None:
                function.argtypes, function.restype = args, result
            self.functions[name] = function
        if self.functions["CloseHandle"] is None:
            raise ProbeFailure({"status": "unavailable", "api": "CloseHandle",
                                "reason": "export_missing_no_handles_opened"})

    def call(self, name: str, *args):
        function = self.functions[name]
        if function is None:
            raise ProbeFailure({"status": "unavailable", "api": name,
                                "reason": "export_missing"})
        C.set_last_error(0)
        value = function(*args)
        if not value:
            code = C.get_last_error()
            raise ProbeFailure({"status": "error", "api": name, "winerror": code,
                                "message": C.FormatError(code).strip() if code else
                                "API returned failure without extended error"})
        return value

    def identity(self, handle) -> dict:
        created, exited, kernel, user = (FILETIME() for _ in range(4))
        self.call("GetProcessTimes", handle, C.byref(created), C.byref(exited),
                  C.byref(kernel), C.byref(user))
        name, capacity = C.create_unicode_buffer(32768), DWORD(32768)
        self.call("QueryFullProcessImageNameW", handle, 0, name, C.byref(capacity))
        # Exit FILETIME is undefined while alive; never infer liveness from it.
        return {"creation_time_100ns": str(created.integer()), "exe_path": name.value}

    def sample(self, name: str, handle=None) -> dict:
        try:
            values = {}
            if name == "cpu_priority":
                value = self.call("GetPriorityClass", handle)
                values = {"class": value, "name": {
                    0x20: "NORMAL", 0x40: "IDLE", 0x80: "HIGH", 0x100: "REALTIME",
                    0x4000: "BELOW_NORMAL", 0x8000: "ABOVE_NORMAL",
                }.get(value, "UNKNOWN")}
            elif name == "memory_priority":
                value = MEMORY_PRIORITY_INFORMATION()
                self.call("GetProcessInformation", handle, 0, C.byref(value), C.sizeof(value))
                values = {"priority": value.MemoryPriority}
            elif name == "power_throttling":
                value = PROCESS_POWER_THROTTLING_STATE(1, 0, 0)
                self.call("GetProcessInformation", handle, 4, C.byref(value), C.sizeof(value))
                values = {"version": value.Version, "control_mask": value.ControlMask,
                          "state_mask": value.StateMask}
            elif name == "memory":
                value = PROCESS_MEMORY_COUNTERS_EX()
                value.cb = C.sizeof(value)
                self.call("K32GetProcessMemoryInfo", handle, C.byref(value), C.sizeof(value))
                values = {"current_rss_bytes": value.WorkingSetSize,
                          "private_commit_bytes": value.PrivateUsage,
                          "page_fault_count_u32": value.PageFaultCount}
            elif name in ("handle_count", "exit_status"):
                value = DWORD()
                api = "GetProcessHandleCount" if name == "handle_count" else "GetExitCodeProcess"
                self.call(api, handle, C.byref(value))
                values = {"count": value.value} if name == "handle_count" else {
                    "code": value.value, "interpretation":
                    "still_active_or_application_exit_259" if value.value == 259 else "exited"}
            elif name == "system_memory":
                value = PERFORMANCE_INFORMATION()
                value.cb = C.sizeof(value)
                self.call("K32GetPerformanceInfo", C.byref(value), C.sizeof(value))
                if value.PageSize == 0:
                    raise ProbeFailure({"status": "error", "api": "K32GetPerformanceInfo",
                                        "reason": "invalid_zero_page_size"})
                values = {"page_size_bytes": value.PageSize}
                for output, native in (("commit_total", "CommitTotal"),
                                       ("commit_limit", "CommitLimit"),
                                       ("physical_total", "PhysicalTotal"),
                                       ("physical_available", "PhysicalAvailable")):
                    values[output + "_pages"] = getattr(value, native)
                    values[output + "_bytes"] = getattr(value, native) * value.PageSize
            else:
                raise ValueError("unknown sample name")
            return {"status": "ok", **values}
        except ProbeFailure as error:
            return error.detail


def target_spec(raw) -> dict:
    pid, created, exe = raw
    if not pid.isdecimal() or not 0 < int(pid) < 2**32:
        raise ValueError("PID must be a positive DWORD")
    if not created.isdecimal() or not 0 < int(created) < 2**64:
        raise ValueError("creation time must be exact positive FILETIME ticks, not rounded UTC")
    drive, tail = ntpath.splitdrive(exe)
    if not drive or not tail.startswith(("\\", "/")) or "\x00" in exe:
        raise ValueError("expected executable must be a fully qualified Windows path")
    return {"pid": int(pid), "expected_creation_time_100ns": str(int(created)),
            "expected_exe_path": exe}


def normalized_path(path: str) -> str:
    # Lexical Win32 comparison only. No filesystem resolve/symlink traversal.
    return ntpath.normcase(ntpath.normpath(path))


def run(args) -> int:
    api, handles, previous_faults = None, [], {}
    code, samples, api_errors = 0, 0, 0
    started = time.perf_counter()
    try:
        api = WinAPI()
        targets = list(args.target)
        if args.self_test:
            # Only this helper's pseudo-handle is used to bootstrap a self-test identity.
            identity = api.identity(HANDLE(-1))
            targets = [target_spec((str(os.getpid()), identity["creation_time_100ns"],
                                    identity["exe_path"]))]
        emit("start", args.run_id, diagnostic_only=True, self_test=args.self_test,
             observer_pid=os.getpid(), helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             windows_version=list(sys.getwindowsversion()[:3]), pointer_bits=C.sizeof(HANDLE) * 8,
             process_access_hex=hex(ACCESS), targets=targets,
             duration_seconds=args.duration, interval_seconds=args.interval,
             monotonic_clock="time.perf_counter_ns",
             monotonic_clock_resolution_seconds=time.get_clock_info("perf_counter").resolution,
             api_exports={name: function is not None for name, function in api.functions.items()})
        for target in targets:
            handle = api.call("OpenProcess", ACCESS, False, target["pid"])
            handles.append((target, handle))  # Own before querying; close on any later failure.
            observed = api.identity(handle)
            matches = (observed["creation_time_100ns"] == target["expected_creation_time_100ns"]
                       and normalized_path(observed["exe_path"]) ==
                       normalized_path(target["expected_exe_path"]))
            emit("identity", args.run_id, pid=target["pid"], status="ok" if matches else "mismatch",
                 observed=observed, expected=target)
            if not matches:
                raise ProbeFailure({"status": "error", "reason": "identity_mismatch",
                                    "pid": target["pid"]})
        deadline, next_at = started + args.duration, time.perf_counter()
        # One initial sample even at duration=0; after that no catch-up bursts.
        while samples == 0 or time.perf_counter() < deadline:
            delay = next_at - time.perf_counter()
            if samples and delay > 0:
                time.sleep(min(delay, max(0.0, deadline - time.perf_counter())))
                if time.perf_counter() >= deadline:
                    break
            beginning = stamp()
            system = api.sample("system_memory")
            rows = []
            exited = False
            for target, handle in handles:
                row = {"pid": target["pid"], "collection_started": stamp()}
                for name in ("exit_status", "cpu_priority", "memory_priority", "power_throttling",
                             "memory", "handle_count"):
                    row[name] = api.sample(name, handle)
                    api_errors += row[name]["status"] != "ok"
                memory, pid = row["memory"], target["pid"]
                fault_time = time.perf_counter_ns()
                if memory["status"] == "ok":
                    count = memory["page_fault_count_u32"]
                    prior = previous_faults.get(pid)
                    memory["page_fault_delta"] = (count - prior[0] if prior and count >= prior[0] else None)
                    memory["page_fault_delta_status"] = ("ok" if prior and count >= prior[0] else
                                                         "counter_decreased_or_wrapped" if prior else "no_previous_sample")
                    memory["delta_interval_ns"] = fault_time - prior[1] if prior else None
                    previous_faults[pid] = (count, fault_time)
                exited |= row["exit_status"].get("interpretation") == "exited"
                row["collection_finished"] = stamp()
                rows.append(row)
            api_errors += system["status"] != "ok"
            emit("sample", args.run_id, sample_index=samples, collection_started=beginning,
                 elapsed_seconds=time.perf_counter() - started, processes=rows, system_memory=system)
            samples += 1
            if exited:
                raise ProbeFailure({"status": "error", "reason": "owned_target_exited"})
            next_at = time.perf_counter() + args.interval
        code = 1 if api_errors else 0
    except ProbeFailure as error:
        code = 2
        emit("fatal", args.run_id, detail=error.detail)
    except KeyboardInterrupt:
        code = 130
        emit("interrupted", args.run_id)
    except Exception as error:
        code = 2
        emit("fatal", args.run_id, detail={"status": "error", "reason": type(error).__name__,
                                           "message": str(error)})
    finally:
        # Close every original handle before any cleanup output; a broken stdout
        # cannot prevent later handles from receiving their close attempt.
        cleanup = []
        for target, handle in reversed(handles):
            try:
                api.call("CloseHandle", handle)
                cleanup.append({"pid": target["pid"], "status": "closed"})
            except ProbeFailure as error:
                code = 3
                cleanup.append({"pid": target["pid"], "status": "close_failed", "detail": error.detail})
        emit("end", args.run_id, diagnostic_only=True, result_code=code,
             samples=samples, api_error_count=api_errors, cleanup=cleanup,
             all_opened_handles_closed=all(row["status"] == "closed" for row in cleanup),
             elapsed_seconds=time.perf_counter() - started)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target", nargs=3, action="append", default=[],
                        metavar=("PID", "CREATION_FILETIME_100NS", "EXE_PATH"))
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--self-test", action="store_true", help="one sample of this helper only")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", args.run_id):
        parser.error("run-id must contain 1-80 ASCII letters, digits, dots, underscores or hyphens")
    if not math.isfinite(args.duration) or not 0 <= args.duration <= 120:
        parser.error("duration must be finite and between 0 and 120 seconds")
    if not math.isfinite(args.interval) or not 0.5 <= args.interval <= 10:
        parser.error("interval must be finite and between 0.5 and 10 seconds")
    if args.self_test:
        if args.target:
            parser.error("self-test cannot be combined with targets")
        args.duration = 0.0
    elif not 1 <= len(args.target) <= 8:
        parser.error("supply 1-8 explicit owned targets")
    try:
        args.target = tuple(target_spec(item) for item in args.target)
    except ValueError as error:
        parser.error(str(error))
    if len({item["pid"] for item in args.target}) != len(args.target):
        parser.error("duplicate PIDs are rejected")
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
