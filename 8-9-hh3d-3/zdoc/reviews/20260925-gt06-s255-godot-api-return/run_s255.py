"""Bounded diagnostic: CDB API entry/return capture on an owned Godot editor.

The editor is created suspended, assigned to an owned KILL_ON_JOB_CLOSE Job,
then CDB is attached before ResumeThread.  This is diagnostic evidence only;
it does not alter the frozen GT06 source, profile, or acceptance gate.
"""
from __future__ import annotations

import ctypes
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDIO = ROOT / "studio"
RAW = STUDIO / ".local/reviews/gt06-s255-godot-api-return-12"
PROJECT = RAW / "project"
SOURCE_PROJECT = STUDIO / ".local/reviews/gt06-s203-cdb-handle-snapshot-01/project"
RUN_ID = "gt06-s255-godot-api-return-12"


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
        text=True, timeout=10,
    ).strip()
    return Path(install) / "amd64/cdb.exe"


def engine_path() -> Path:
    lock = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))
    return STUDIO / ".local/tooling/godot-4.7.2-stable" / lock["godot"]["gui_executable"]


def files_under(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and ".godot" not in path.parts:
            out[path.relative_to(ROOT).as_posix()] = sha(path)
    return out


def pump(stream, path: Path, rows: list[str]) -> None:
    with path.open("x", encoding="utf-8", errors="replace") as out:
        for line in iter(stream.readline, ""):
            rows.append(line.rstrip("\r\n"))
            out.write(line)
            out.flush()


def resume_thread(handle) -> None:
    # Popen retains the process handle, while CREATE_SUSPENDED leaves the
    # primary thread handle private.  NtResumeProcess resumes the owned
    # process without guessing a thread/PID pair.
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
    ntdll.NtResumeProcess.restype = ctypes.c_long
    status = ntdll.NtResumeProcess(ctypes.c_void_p(int(handle)))
    if status < 0:
        raise OSError(f"NtResumeProcess NTSTATUS=0x{status & 0xffffffff:08x}")


def main() -> None:
    if RAW.exists() and any(RAW.iterdir()):
        raise RuntimeError("S255_RAW_ALREADY_EXISTS")
    RAW.mkdir(parents=True, exist_ok=True)
    cdb = cdb_path()
    godot = engine_path()
    if not cdb.is_file(): raise RuntimeError("S255_CDB_MISSING")
    if not godot.is_file(): raise RuntimeError("S255_GODOT_MISSING")
    if not SOURCE_PROJECT.is_dir(): raise RuntimeError("S255_SOURCE_PROJECT_MISSING")
    shutil.copytree(SOURCE_PROJECT, PROJECT, ignore=shutil.ignore_patterns(".godot"))
    idle = PROJECT / "addons/hh_idle/idle.gd"
    shutil.copy2(HERE / "idle_s255.gd", idle)
    shutil.copy2(HERE / "idle_s255.gd", PROJECT / "addons/hh_idle/idle_s255.gd")
    # Keep the accepted fixture's project and adapter closure but install the
    # explicitly versioned diagnostic plugin source.
    (PROJECT / "addons/hh_idle/plugin.cfg").write_text(
        '[plugin]\nname="S255 CDB API diagnostic"\ndescription="Diagnostic only"\nauthor="HH Studio"\nversion="1.0"\nscript="idle_s255.gd"\n',
        encoding="utf-8",
    )
    project_files = files_under(PROJECT)
    source_files = {**project_files, HERE.relative_to(ROOT).as_posix(): sha(HERE / "idle_s255.gd"),
                    (HERE / "cdb-commands.txt").relative_to(ROOT).as_posix(): sha(HERE / "cdb-commands.txt"),
                    (HERE / "run_s255.py").relative_to(ROOT).as_posix(): sha(HERE / "run_s255.py"),
                    "studio/toolchain.lock.json": sha(STUDIO / "toolchain.lock.json")}
    write_once("preflight.json", {
        "run_id": RUN_ID, "authority": 0, "formal_acceptance": False,
        "engine_started": False, "godot": str(godot), "godot_sha256": sha(godot),
        "cdb": str(cdb), "cdb_sha256": sha(cdb), "source_files": source_files,
        "source_project_reuse": "S203_PROJECT_SOURCE_ONLY_EXCLUDING_.godot",
        "requested_utc": stamp(), "formal_gate_unchanged": True,
        "hypothesis": "CDB API entry/return capture can bind a native handle creator to the owned Godot editor stack",
    })
    # Validate the diagnostic script before starting the editor.
    parse_dir = RAW / "parse"
    parse_dir.mkdir()
    parse = subprocess.run([str(godot), "--headless", "--path", str(PROJECT), "--check-only", "--script", "res://addons/hh_idle/idle_s255.gd"], cwd=PROJECT, capture_output=True, text=True, timeout=30)
    (parse_dir / "stdout.txt").write_text(parse.stdout, encoding="utf-8")
    (parse_dir / "stderr.txt").write_text(parse.stderr, encoding="utf-8")
    write_once("parse.json", {"exit": parse.returncode, "stdout_sha256": sha(parse_dir / "stdout.txt"), "stderr_sha256": sha(parse_dir / "stderr.txt")})
    if parse.returncode != 0 or parse.stderr.strip(): raise RuntimeError("S255_PARSE_FAILED")
    sys.path.insert(0, str(STUDIO / "godot-addon"))
    import cli_job  # type: ignore
    output_rows: list[str] = []
    error_rows: list[str] = []
    editor = None
    owner = None
    cdb_proc = None
    cdb_rows: list[str] = []
    cdb_errors: list[str] = []
    try:
        flags = 0x00000004 | subprocess.CREATE_NO_WINDOW  # CREATE_SUSPENDED; Python exposes no named constant.
        editor = subprocess.Popen([str(godot), "--headless", "--editor", "--path", str(PROJECT), "--import", "--", "--hh-s255-cdb-api"], cwd=PROJECT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=flags, bufsize=1)
        owner = cli_job.create(editor)
        write_once("editor-suspended.json", {"pid": editor.pid, "started_utc": stamp(), "job": owner.snapshot()})
        cdb_proc = subprocess.Popen([str(cdb), "-p", str(editor.pid), "-pd", "-nosqm", "-logo", str(RAW / "cdb-logo.txt"), "-cf", str(HERE / "cdb-commands.txt")], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW, bufsize=1)
        t0 = threading.Thread(target=pump, args=(editor.stdout, RAW / "editor-stdout.txt", output_rows), daemon=True)
        t1 = threading.Thread(target=pump, args=(editor.stderr, RAW / "editor-stderr.txt", error_rows), daemon=True)
        t2 = threading.Thread(target=pump, args=(cdb_proc.stdout, RAW / "cdb-stdout.txt", cdb_rows), daemon=True)
        t3 = threading.Thread(target=pump, args=(cdb_proc.stderr, RAW / "cdb-stderr.txt", cdb_errors), daemon=True)
        for thread in (t0, t1, t2, t3): thread.start()
        write_once("cdb-start.json", {"pid": cdb_proc.pid, "target_pid": editor.pid, "started_utc": stamp()})
        deadline = time.monotonic() + 20
        while "S255_BREAKPOINTS_ARMED" not in cdb_rows:
            if cdb_proc.poll() is not None: raise RuntimeError(f"S255_CDB_EARLY_EXIT:{cdb_proc.returncode}")
            if time.monotonic() > deadline: raise RuntimeError("S255_CDB_ARM_TIMEOUT")
            time.sleep(.02)
        resume_thread(editor._handle)
        write_once("resume.json", {"utc": stamp(), "pid": editor.pid})
        run_deadline = time.monotonic() + 80
        while editor.poll() is None:
            if time.monotonic() > run_deadline: raise RuntimeError("S255_EDITOR_TIMEOUT")
            time.sleep(.05)
        editor_exit = editor.returncode
        try: cdb_exit = cdb_proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            cdb_proc.terminate(); cdb_exit = cdb_proc.wait(timeout=10)
        for thread in (t0, t1, t2, t3): thread.join(3)
        text = "\n".join(cdb_rows)
        write_once("result.json", {
            "run_id": RUN_ID, "authority": 0, "formal_acceptance": False,
            "editor_pid": editor.pid, "editor_exit": editor_exit, "cdb_pid": cdb_proc.pid, "cdb_exit": cdb_exit,
            "markers": {"attached": "S255_ATTACHED" in text, "armed": "S255_BREAKPOINTS_ARMED" in text, "complete": "S255_COMPLETE" in text},
            "entry_rows": [line for line in cdb_rows if "_ENTRY" in line],
            "return_rows": [line for line in cdb_rows if "_RETURN" in line],
            "stack_rows": sum(1 for line in cdb_rows if "Child-SP" in line or "ntdll!" in line or "godot" in line.lower() or "kernelbase!" in line),
            "editor_output_rows": len(output_rows), "editor_stderr_rows": len(error_rows), "cdb_stderr_rows": len(cdb_errors),
            "job_after_exit": owner.snapshot(), "formal_gate_unchanged": True,
        })
    finally:
        if cdb_proc is not None and cdb_proc.poll() is None:
            cdb_proc.terminate()
            try: cdb_proc.wait(timeout=10)
            except subprocess.TimeoutExpired: cdb_proc.kill()
        if editor is not None and editor.poll() is None:
            if owner is not None:
                try: owner.terminate()
                except Exception: pass
            else:
                editor.terminate()
            try: editor.wait(timeout=10)
            except subprocess.TimeoutExpired: editor.kill()
        if owner is not None and not owner.closed:
            owner.close()
        write_once("cleanup.json", {"utc": stamp(), "editor_exit": None if editor is None else editor.poll(), "cdb_exit": None if cdb_proc is None else cdb_proc.poll(), "job": None if owner is None else owner.snapshot()})


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        try: write_once("failure.json", {"type": type(exc).__name__, "message": str(exc), "formal_acceptance": False, "utc": stamp()})
        finally: raise
