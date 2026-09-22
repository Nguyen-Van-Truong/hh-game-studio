"""Bounded CDB !htrace attribution fixture; diagnostic evidence only."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent
TEMP = Path(tempfile.gettempdir())
STAMP = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
EXE = TEMP / f"hh3d-s169-{STAMP}.exe"
CSC = Path(os.environ["WINDIR"]) / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe"
PKG = Path(subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", "(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation"], text=True).strip())
CDB = PKG / "amd64" / "cdb.exe"
COMMANDS = RUN_DIR / "cdb-commands.txt"
SOURCE = RUN_DIR / "native_fixture_s169.cs"
OUT = RUN_DIR / "target.stdout.jsonl"
ERR = RUN_DIR / "target.stderr.txt"
CDB_OUT = RUN_DIR / "cdb.stdout.txt"
CDB_ERR = RUN_DIR / "cdb.stderr.txt"
CDB_LOG = RUN_DIR / "cdb.logo.txt"
RECEIPT = RUN_DIR / "s169-attribution-result.json"


def pump(stream, sink: queue.Queue[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            sink.put(line.rstrip("\r\n"))
    finally:
        stream.close()


def start(argv: list[str]) -> tuple[subprocess.Popen[str], queue.Queue[str], queue.Queue[str]]:
    proc = subprocess.Popen(
        argv,
        cwd=RUN_DIR,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    out_q: queue.Queue[str] = queue.Queue()
    err_q: queue.Queue[str] = queue.Queue()
    threading.Thread(target=pump, args=(proc.stdout, out_q), daemon=True).start()
    threading.Thread(target=pump, args=(proc.stderr, err_q), daemon=True).start()
    return proc, out_q, err_q


def drain(q: queue.Queue[str], lines: list[str]) -> None:
    while True:
        try:
            lines.append(q.get_nowait())
        except queue.Empty:
            return


def wait_marker(q: queue.Queue[str], lines: list[str], marker: str, seconds: float) -> bool:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            line = q.get(timeout=0.1)
        except queue.Empty:
            continue
        lines.append(line)
        if marker in line:
            return True
    drain(q, lines)
    return False


def main() -> int:
    compile_cp = subprocess.run(
        [str(CSC), "/nologo", "/target:exe", f"/out:{EXE}", str(SOURCE)],
        cwd=RUN_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    (RUN_DIR / "compile.stdout.txt").write_text(compile_cp.stdout, encoding="utf-8")
    (RUN_DIR / "compile.stderr.txt").write_text(compile_cp.stderr, encoding="utf-8")
    if compile_cp.returncode != 0:
        raise RuntimeError(f"C# compile exit {compile_cp.returncode}")

    target, target_q, target_err_q = start([str(EXE)])
    target_lines: list[str] = []
    target_err_lines: list[str] = []
    debugger = None
    debugger_q = debugger_err_q = None
    debugger_lines: list[str] = []
    debugger_err_lines: list[str] = []
    forced_target = forced_debugger = False
    attached = False
    try:
        if not wait_marker(target_q, target_lines, '"kind":"ready"', 10):
            raise RuntimeError("target did not emit ready")
        # The installed CDB treats -netsyms as a legacy command-line boundary;
        # passing the literal value "no" makes it interpret that value as the
        # debuggee path.  Omit the optional switch and keep symbols offline by
        # using only the owned PID and -nosqm.
        cdb_args = [str(CDB), "-p", str(target.pid), "-pd", "-nosqm", "-logo", str(CDB_LOG), "-cf", str(COMMANDS)]
        debugger, debugger_q, debugger_err_q = start(cdb_args)
        attached = wait_marker(debugger_q, debugger_lines, "CDB_ATTACHED", 20)
        if not attached:
            raise RuntimeError("CDB did not emit CDB_ATTACHED")
        assert target.stdin is not None
        target.stdin.write("break_ready\nopen\n")
        target.stdin.flush()
        deadline = time.monotonic() + 60
        while debugger.poll() is None and time.monotonic() < deadline:
            time.sleep(0.1)
        if debugger.poll() is None:
            forced_debugger = True
            debugger.kill()
        target_deadline = time.monotonic() + 15
        while target.poll() is None and time.monotonic() < target_deadline:
            time.sleep(0.1)
        if target.poll() is None:
            forced_target = True
            target.kill()
    finally:
        if debugger is not None and debugger.poll() is None:
            forced_debugger = True
            debugger.kill()
        if target.poll() is None:
            forced_target = True
            target.kill()
        if debugger is not None:
            debugger.wait(timeout=5)
        target.wait(timeout=5)
        drain(target_q, target_lines)
        drain(target_err_q, target_err_lines)
        if debugger_q is not None:
            drain(debugger_q, debugger_lines)
        if debugger_err_q is not None:
            drain(debugger_err_q, debugger_err_lines)
        # Preserve the raw streams even when the harness fails before receipt creation.
        OUT.write_text("\n".join(target_lines) + ("\n" if target_lines else ""), encoding="utf-8")
        ERR.write_text("\n".join(target_err_lines) + ("\n" if target_err_lines else ""), encoding="utf-8")
        CDB_OUT.write_text("\n".join(debugger_lines) + ("\n" if debugger_lines else ""), encoding="utf-8")
        CDB_ERR.write_text("\n".join(debugger_err_lines) + ("\n" if debugger_err_lines else ""), encoding="utf-8")

    cdb_text = "\n".join(debugger_lines)
    if CDB_LOG.exists():
        cdb_text += "\n" + CDB_LOG.read_text(encoding="utf-8", errors="replace")
    OUT.write_text("\n".join(target_lines) + ("\n" if target_lines else ""), encoding="utf-8")
    ERR.write_text("\n".join(target_err_lines) + ("\n" if target_err_lines else ""), encoding="utf-8")
    CDB_OUT.write_text("\n".join(debugger_lines) + ("\n" if debugger_lines else ""), encoding="utf-8")
    CDB_ERR.write_text("\n".join(debugger_err_lines) + ("\n" if debugger_err_lines else ""), encoding="utf-8")

    debugger_version = subprocess.check_output([str(CDB), "-version"], text=True, stderr=subprocess.STDOUT, timeout=15).strip()
    receipt = {
        "schema": "gt06-s169-windbg-attribution-v1",
        "run_id": "gt06-s169-windbg-attribution-01",
        "command_id": "cmd.gt06.s169.windbg-htrace.1",
        "authority": 0,
        "diagnostic_only": True,
        "source_closure": "fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde",
        "profile_sha256": "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fc" + "d6dbf4d85",
        "debugger": {
            "path": str(CDB),
            "version": debugger_version,
            "sha256": hashlib.sha256(CDB.read_bytes()).hexdigest(),
            "attached_marker": attached,
            "cdb_exit": debugger.returncode if debugger is not None else None,
        },
        "target": {"pid": target.pid, "target_exit": target.returncode, "executable": str(EXE)},
        "markers": {
            "htrace_enable": "htrace" in cdb_text.lower() and "enable" in cdb_text.lower(),
            "ready_break": "READY_BREAK" in cdb_text,
            "open_break": "OPEN_BREAK" in cdb_text,
            "close_break": "CLOSE_BREAK" in cdb_text,
            "diff_present": any(x in cdb_text.lower() for x in ("htrace", "handle", "stack")),
        },
        "target_markers": {
            "start": any('"kind":"start"' in x for x in target_lines),
            "ready": any('"kind":"ready"' in x for x in target_lines),
            "open": any('"kind":"open"' in x for x in target_lines),
            "close": any('"kind":"close"' in x for x in target_lines),
            "exit": any('"kind":"exit"' in x for x in target_lines),
        },
        "forced_cleanup": {"debugger": forced_debugger, "target": forced_target},
        "status": "DIAGNOSTIC_RETAINED_AUTHORITY_0",
        "exclusions": ["F13", "F14", "GT06_DATASET", "LEAK_PROOF", "ROOT_CAUSE", "REPAIR_AUTHORIZATION", "GT06_ACCEPTANCE"],
        "stderr": {"debugger": "\n".join(debugger_err_lines), "target": "\n".join(target_err_lines)},
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(RECEIPT), "target_exit": target.returncode, "cdb_exit": debugger.returncode if debugger else None, "forced_cleanup": receipt["forced_cleanup"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"S169_RUNNER_ERROR: {type(exc).__name__}: {exc}", flush=True)
        raise
