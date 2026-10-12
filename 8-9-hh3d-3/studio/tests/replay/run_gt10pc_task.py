"""Demand-only Scheduled Task supervisor for the GT-10-PC final matrix.

The request binds the runner, supervisor, interpreter and source closure before
the windowed Scheduled Task starts.  The task records the child process exit
and never treats a banner or a missing return receipt as success.
"""

from __future__ import annotations

import argparse
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
MATRIX = STUDIO / "tests" / "conformance" / "run_gt10pc_matrix.py"
RUN_RE = re.compile(r"gt10pc-(?:final|rehearsal)-20\d{6}-[a-z0-9-]{1,24}\Z")
ROWS = tuple("P" + str(index) for index in range(1, 13))
FINAL_ROWS = tuple("P" + str(index) for index in range(1, 12))
SCHEMA = "HH-GT10PC-TASK-REQUEST-2"
TRUST = STUDIO / ".local" / "gt10pc-publisher-v2" / "trust.json"
PRIVATE = STUDIO / ".local" / "gt10pc-publisher-v2" / "private.raw"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write((json.dumps(value, indent=2, sort_keys=True) + "\n").encode())
        stream.flush(); os.fsync(stream.fileno())


def source_closure() -> str:
    sys.path.insert(0, str(REPO_ROOT))
    from studio.package.release_contract import _source_files, _payload_digest
    return hashlib.sha256(json.dumps({
        "payload": _payload_digest(_source_files(STUDIO)),
        "publisher": sha(STUDIO / "tests/conformance/gt10pc_signing.py"),
    }, sort_keys=True).encode()).hexdigest()


def paths(run_id: str) -> tuple[Path, Path]:
    if os.name != "nt" or RUN_RE.fullmatch(run_id) is None:
        raise ValueError("GT10PC_TASK_RUN_ID")
    root = STUDIO / ".local" / "reviews" / run_id
    task = STUDIO / ".local" / "reviews" / (run_id + "-task")
    return root, task


def normalize_rows(rows: str | None, mode: str) -> list[str]:
    # P12 is an external critic gate, never a matrix producer row.  Keeping
    # it out of the default rehearsal selection prevents a green native run
    # from being downgraded to INCOMPLETE by a deliberately deferred critic.
    selected = list(FINAL_ROWS) if rows is None else rows.split(",")
    if not selected or any(row not in ROWS for row in selected) or len(selected) != len(set(selected)):
        raise ValueError("GT10PC_TASK_ROWS")
    if mode == "final" and selected != list(FINAL_ROWS):
        raise ValueError("GT10PC_FINAL_REQUIRES_ALL_ROWS")
    return selected


def prepare(run_id: str, mode: str = "rehearsal", rows: str | None = None) -> Path:
    if mode not in ("rehearsal", "final") or not run_id.startswith("gt10pc-" + mode + "-"):
        raise ValueError("GT10PC_TASK_MODE")
    if not TRUST.is_file() or not PRIVATE.is_file():
        raise ValueError("GT10PC_EXTERNAL_TRUST_MISSING")
    selected = normalize_rows(rows, mode)
    matrix_root, task = paths(run_id)
    if matrix_root.exists() or task.exists():
        raise FileExistsError("GT10PC_TASK_OUTPUT_ALREADY_EXISTS")
    task.mkdir(parents=True)
    try:
        console = Path(sys.executable).resolve().with_name("python.exe")
        windowed = Path(sys.executable).resolve().with_name("pythonw.exe")
        write_new(task / "request.json", {
            "schema": SCHEMA, "run_id": run_id, "mode": mode, "rows": selected,
            "matrix_sha256": sha(MATRIX), "supervisor_sha256": sha(Path(__file__).resolve()),
            "producer_sha256": sha(MATRIX),
            "trust_sha256": sha(TRUST), "private_sha256": sha(PRIVATE),
            "python_sha256": sha(console), "pythonw_sha256": sha(windowed),
            "source_closure_sha256": source_closure(), "prepared_utc": datetime.now(timezone.utc).isoformat(),
        })
        return task
    except BaseException:
        try: (task / "request.json").unlink(missing_ok=True); task.rmdir()
        except OSError: pass
        raise


def load_request(run_id: str) -> tuple[Path, Path, dict[str, object]]:
    matrix_root, task = paths(run_id); request_path = task / "request.json"
    if not request_path.is_file() or matrix_root.exists():
        raise ValueError("GT10PC_TASK_REQUEST_BINDING")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("mode") not in ("rehearsal", "final") or not run_id.startswith("gt10pc-" + request["mode"] + "-"):
        raise ValueError("GT10PC_TASK_MODE_BINDING")
    console = Path(sys.executable).resolve().with_name("python.exe")
    windowed = Path(sys.executable).resolve().with_name("pythonw.exe")
    mode = request.get("mode")
    rows = request.get("rows")
    if mode not in ("rehearsal", "final") or not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
        raise ValueError("GT10PC_TASK_REQUEST_ROWS")
    if normalize_rows(",".join(rows), mode) != rows:
        raise ValueError("GT10PC_TASK_REQUEST_ROWS")
    expected = {
        "schema": SCHEMA, "run_id": run_id, "mode": mode, "rows": rows, "matrix_sha256": sha(MATRIX),
        "supervisor_sha256": sha(Path(__file__).resolve()), "python_sha256": sha(console),
        "pythonw_sha256": sha(windowed), "source_closure_sha256": request.get("source_closure_sha256"),
        "prepared_utc": request.get("prepared_utc"),
    }
    expected["producer_sha256"] = sha(MATRIX)
    expected["trust_sha256"] = sha(TRUST); expected["private_sha256"] = sha(PRIVATE)
    if request != expected or source_closure() != request["source_closure_sha256"]:
        raise ValueError("GT10PC_TASK_SOURCE_CHANGED")
    return matrix_root, task, request


def run(run_id: str) -> int:
    matrix_root, task, request = load_request(run_id)
    started = time.monotonic(); code = 1; process_observed = False
    stdout_path, stderr_path = task / "stdout.txt", task / "stderr.txt"
    try:
        console = Path(sys.executable).resolve().with_name("python.exe")
        command = [str(console), "-B", str(MATRIX), "--matrix", request["mode"],
                   "--output", str(matrix_root),
                   "--trust", str(TRUST), "--trust-sha256", request["trust_sha256"],
                   "--private-key", str(PRIVATE)]
        if request["mode"] == "rehearsal":
            command[command.index("--output"):command.index("--output")] = [
                "--rows", ",".join(request["rows"])]
        env = os.environ.copy(); env["PYTHONPATH"] = str(STUDIO) + os.pathsep + env.get("PYTHONPATH", "")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            proc = subprocess.run(command, cwd=REPO_ROOT, stdout=stdout, stderr=stderr,
                                  env=env, timeout=24 * 3600, check=False)
            code = int(proc.returncode)
            process_observed = True
        # The matrix producer owns row verification. Keep a separate task
        # receipt of that process exit; never infer success from its stdout.
        if source_closure() != request["source_closure_sha256"]:
            raise ValueError("GT10PC_TASK_SOURCE_CHANGED_DURING_RUN")
    except BaseException:
        code = 2
        with stderr_path.open("ab") as stderr: stderr.write(traceback.format_exc().encode())
    finally:
        write_new(task / "return.json", {"schema": "HH-GT10PC-TASK-RETURN-2", "run_id": run_id,
            "returned_exit_code": code, "matrix_root": str(matrix_root),
            "source_closure_sha256": request["source_closure_sha256"],
            "elapsed_seconds": time.monotonic() - started, "actual_process_exit_observed": process_observed,
            "formal_acceptance": False, "mode": request["mode"]})
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true"); parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("rehearsal", "final"), default="rehearsal")
    parser.add_argument("--rows")
    args = parser.parse_args(argv)
    if args.rows and not args.prepare:
        parser.error("--rows is prepare-only; execution reads the pinned request")
    if args.prepare:
        print(json.dumps({"schema": SCHEMA, "task": str(prepare(args.run_id, args.mode, args.rows))}, sort_keys=True)); return 0
    if Path(sys.executable).name.lower() != "pythonw.exe": raise ValueError("GT10PC_TASK_WINDOWED_INTERPRETER_REQUIRED")
    return run(args.run_id)


if __name__ == "__main__": raise SystemExit(main())
