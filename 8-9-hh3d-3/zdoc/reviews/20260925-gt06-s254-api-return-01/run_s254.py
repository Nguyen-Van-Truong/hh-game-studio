"""Bounded S254 diagnostic: bind native API entry/return to known handles.

This never starts Godot and never changes the GT06 gate.  CDB is attached only
to an owned Python child and is terminated/closed on every path.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RAW = ROOT / "studio/.local/reviews/gt06-s254-api-return-01"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_once(rel: str, value: object) -> None:
    path = RAW / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def cdb_path() -> Path:
    install = subprocess.check_output(
        ["powershell.exe", "-NoProfile", "-Command", "(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation"],
        text=True,
        timeout=10,
    ).strip()
    return Path(install) / "amd64/cdb.exe"


def pump(stream, path: Path, rows: list[str]) -> None:
    with path.open("x", encoding="utf-8", errors="replace") as out:
        for line in iter(stream.readline, ""):
            rows.append(line.rstrip("\r\n"))
            out.write(line)
            out.flush()


def run() -> None:
    if RAW.exists() and any(RAW.iterdir()):
        raise RuntimeError("S254_RAW_ALREADY_EXISTS")
    RAW.mkdir(parents=True, exist_ok=True)
    cdb = cdb_path()
    fixture = HERE / "api_fixture.py"
    commands = HERE / "cdb-commands.txt"
    if not cdb.is_file():
        raise RuntimeError("S254_CDB_MISSING")
    if not fixture.is_file() or not commands.is_file():
        raise RuntimeError("S254_DRIVER_INPUT_MISSING")
    write_once("preflight.json", {
        "run_id": "gt06-s254-api-return-01",
        "authority": 0,
        "formal_acceptance": False,
        "engine_started": False,
        "hypothesis": "CDB can bind NtCreateEvent/NtCreateIoCompletion entry and return values to known handles on an owned target",
        "cdb": str(cdb),
        "cdb_sha256": sha(cdb),
        "python": sys.executable,
        "python_sha256": sha(Path(sys.executable)),
        "fixture_sha256": sha(fixture),
        "commands_sha256": sha(commands),
        "requested_utc": stamp(),
        "limits": {"target_seconds": 35, "cdb_seconds": 25, "outer_seconds": 60},
        "formal_gate_unchanged": True,
    })
    trigger_dir = RAW / "target"
    trigger_dir.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-B", str(fixture), str(trigger_dir)],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
        bufsize=1,
    )
    child_rows: list[str] = []
    child_err: list[str] = []
    t1 = threading.Thread(target=pump, args=(child.stdout, RAW / "target-stdout.txt", child_rows), daemon=True)
    t2 = threading.Thread(target=pump, args=(child.stderr, RAW / "target-stderr.txt", child_err), daemon=True)
    t1.start(); t2.start()
    write_once("target-start.json", {"pid": child.pid, "started_utc": stamp(), "args": [sys.executable, "-B", str(fixture), str(trigger_dir)]})
    cdb_proc = None
    cdb_rows: list[str] = []
    cdb_err: list[str] = []
    cdb_code = None
    try:
        ready_deadline = time.monotonic() + 10
        while not (trigger_dir / "READY").exists():
            if child.poll() is not None:
                raise RuntimeError(f"S254_TARGET_EARLY_EXIT:{child.returncode}")
            if time.monotonic() > ready_deadline:
                raise RuntimeError("S254_TARGET_READY_TIMEOUT")
            time.sleep(0.02)
        target_start = json.loads((trigger_dir / "READY").read_text(encoding="utf-8"))
        target_start["observed_utc"] = stamp()
        write_once("target-ready.json", target_start)
        cdb_proc = subprocess.Popen(
            [str(cdb), "-p", str(child.pid), "-pd", "-nosqm", "-logo", str(RAW / "cdb-logo.txt"), "-cf", str(commands)],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            bufsize=1,
        )
        u1 = threading.Thread(target=pump, args=(cdb_proc.stdout, RAW / "cdb-stdout.txt", cdb_rows), daemon=True)
        u2 = threading.Thread(target=pump, args=(cdb_proc.stderr, RAW / "cdb-stderr.txt", cdb_err), daemon=True)
        u1.start(); u2.start()
        write_once("cdb-start.json", {"pid": cdb_proc.pid, "target_pid": child.pid, "started_utc": stamp()})
        arm_deadline = time.monotonic() + 15
        while "S254_BREAKPOINTS_ARMED" not in cdb_rows:
            if cdb_proc.poll() is not None:
                raise RuntimeError(f"S254_CDB_EARLY_EXIT:{cdb_proc.returncode}")
            if time.monotonic() > arm_deadline:
                raise RuntimeError("S254_CDB_ARM_TIMEOUT")
            time.sleep(0.02)
        (trigger_dir / "trigger").write_text("go\n", encoding="ascii")
        write_once("trigger.json", {"utc": stamp(), "target_pid": child.pid})
        target_deadline = time.monotonic() + 35
        while child.poll() is None:
            if time.monotonic() > target_deadline:
                raise RuntimeError("S254_TARGET_TIMEOUT")
            time.sleep(0.02)
        target_code = child.returncode
        try:
            cdb_code = cdb_proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            cdb_proc.terminate()
            cdb_code = cdb_proc.wait(timeout=10)
        u1.join(3); u2.join(3)
        if not (trigger_dir / "ground-truth.json").exists():
            raise RuntimeError("S254_GROUND_TRUTH_MISSING")
        ground = json.loads((trigger_dir / "ground-truth.json").read_text(encoding="utf-8"))
        text = "\n".join(cdb_rows)
        write_once("result.json", {
            "run_id": "gt06-s254-api-return-01",
            "authority": 0,
            "formal_acceptance": False,
            "target_pid": child.pid,
            "target_exit": target_code,
            "cdb_pid": cdb_proc.pid,
            "cdb_exit": cdb_code,
            "ground_truth": ground,
            "markers": {"attached": "S254_ATTACHED" in text, "armed": "S254_BREAKPOINTS_ARMED" in text, "complete": "S254_COMPLETE" in text},
            "entry_rows": [line for line in cdb_rows if "_ENTRY" in line],
            "return_rows": [line for line in cdb_rows if "_RETURN" in line],
            "stack_rows": sum(1 for line in cdb_rows if "Child-SP" in line or "ntdll!" in line or "kernelbase!" in line),
            "stderr_empty": not child_err and not cdb_err,
            "formal_gate_unchanged": True,
        })
    finally:
        if cdb_proc is not None and cdb_proc.poll() is None:
            cdb_proc.terminate()
            try:
                cdb_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                cdb_proc.kill()
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        t1.join(3); t2.join(3)
        write_once("cleanup.json", {"utc": stamp(), "target_exit": child.poll(), "cdb_exit": None if cdb_proc is None else cdb_proc.poll(), "owned_children": []})


if __name__ == "__main__":
    try:
        run()
    except BaseException as exc:
        try:
            write_once("failure.json", {"type": type(exc).__name__, "message": str(exc), "formal_acceptance": False, "utc": stamp()})
        finally:
            raise
