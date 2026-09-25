"""Tiny owned Windows target for the S254 API entry/return diagnostic.

This is deliberately independent of Godot.  It creates one Event and one
I/O completion port only after the debugger is attached, writes the native
returned values to a ground-truth file, then closes both handles and exits.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    trigger = root / "trigger"
    result = root / "ground-truth.json"
    ready = root / "READY"
    root.mkdir(parents=True, exist_ok=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateEventW.restype = ctypes.c_void_p
    kernel32.CreateIoCompletionPort.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint]
    kernel32.CreateIoCompletionPort.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.restype = ctypes.c_int
    ready.write_text(json.dumps({"pid": os.getpid(), "pid_start_unknown": True}) + "\n", encoding="utf-8")
    sys.stdout.write("S254_READY %d\n" % os.getpid())
    sys.stdout.flush()
    deadline = time.monotonic() + 30.0
    while not trigger.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    if not trigger.exists():
        print("S254_TRIGGER_TIMEOUT", flush=True)
        return 3
    event_handle = kernel32.CreateEventW(None, 0, 0, None)
    event_error = ctypes.get_last_error()
    completion_handle = kernel32.CreateIoCompletionPort(ctypes.c_void_p(-1), None, 0, 1)
    completion_error = ctypes.get_last_error()
    payload = {
        "pid": os.getpid(),
        "event_handle": int(event_handle or 0),
        "event_last_error": event_error,
        "completion_handle": int(completion_handle or 0),
        "completion_last_error": completion_error,
    }
    result.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    print("S254_CREATED " + json.dumps(payload, sort_keys=True), flush=True)
    if event_handle:
        kernel32.CloseHandle(event_handle)
    if completion_handle:
        kernel32.CloseHandle(completion_handle)
    print("S254_CLOSED", flush=True)
    return 0 if event_handle and completion_handle else 4


if __name__ == "__main__":
    raise SystemExit(main())
