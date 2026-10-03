#!/usr/bin/env python3
"""Run a command only when the shared GT-06 measurement lock is absent.

The wrapper owns the child process, records the actual exit code, and kills the
whole process tree on timeout. It intentionally does not infer PASS from a
caller-supplied field or a printed banner.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def lock_path() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is unavailable")
    return Path(local) / "HHGodotAgent" / "measure-window.lock"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    guard = lock_path()
    if guard.exists():
        print(json.dumps({"status": "MEASURE_LOCK_PRESENT", "path": str(guard)}, ensure_ascii=False))
        return 125
    started = time.time()
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(command, creationflags=creationflags)
    timed_out = False
    try:
        actual_exit = proc.wait(timeout=args.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        actual_exit = proc.wait()
    result = {
        "status": "TIMEOUT" if timed_out else "EXITED",
        "command": command,
        "pid": proc.pid,
        "exit_code": actual_exit,
        "duration_seconds": round(time.time() - started, 3),
    }
    if args.evidence:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 124 if timed_out else actual_exit


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
