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
SCHEMA = "HH-GT10PC-TASK-REQUEST-1"
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
    files: list[tuple[str, str]] = []
    roots = [STUDIO / "package", STUDIO / "tests" / "conformance" / "run_gt10pc_matrix.py",
             STUDIO / "tests" / "conformance" / "run_gt10pc_native_probe.py", Path(__file__).resolve()]
    for root in roots:
        candidates = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for path in candidates:
            rel = path.relative_to(REPO_ROOT).as_posix()
            if "__pycache__" in rel or ".local" in rel:
                continue
            files.append((rel, sha(path)))
    return hashlib.sha256(json.dumps(files, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def paths(run_id: str) -> tuple[Path, Path]:
    if os.name != "nt" or RUN_RE.fullmatch(run_id) is None:
        raise ValueError("GT10PC_TASK_RUN_ID")
    root = STUDIO / ".local" / "reviews" / run_id
    task = STUDIO / ".local" / "reviews" / (run_id + "-task")
    return root, task


def prepare(run_id: str, mode: str = "rehearsal") -> Path:
    if mode not in ("rehearsal", "final"):
        raise ValueError("GT10PC_TASK_MODE")
    if not TRUST.is_file() or not PRIVATE.is_file():
        raise ValueError("GT10PC_EXTERNAL_TRUST_MISSING")
    matrix_root, task = paths(run_id)
    if matrix_root.exists() or task.exists():
        raise FileExistsError("GT10PC_TASK_OUTPUT_ALREADY_EXISTS")
    task.mkdir(parents=True)
    try:
        console = Path(sys.executable).resolve().with_name("python.exe")
        windowed = Path(sys.executable).resolve().with_name("pythonw.exe")
        write_new(task / "request.json", {
            "schema": SCHEMA, "run_id": run_id, "mode": mode,
            "matrix_sha256": sha(MATRIX), "supervisor_sha256": sha(Path(__file__).resolve()),
            "producer_sha256": sha(STUDIO / "tests" / "conformance" / "run_gt10pc_native_probe.py"),
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
    console = Path(sys.executable).resolve().with_name("python.exe")
    windowed = Path(sys.executable).resolve().with_name("pythonw.exe")
    expected = {
        "schema": SCHEMA, "run_id": run_id, "mode": request.get("mode"), "matrix_sha256": sha(MATRIX),
        "supervisor_sha256": sha(Path(__file__).resolve()), "python_sha256": sha(console),
        "pythonw_sha256": sha(windowed), "source_closure_sha256": request.get("source_closure_sha256"),
        "prepared_utc": request.get("prepared_utc"),
    }
    expected["producer_sha256"] = sha(STUDIO / "tests" / "conformance" / "run_gt10pc_native_probe.py")
    expected["trust_sha256"] = sha(TRUST); expected["private_sha256"] = sha(PRIVATE)
    if request != expected or source_closure() != request["source_closure_sha256"]:
        raise ValueError("GT10PC_TASK_SOURCE_CHANGED")
    return matrix_root, task, request


def run(run_id: str) -> int:
    matrix_root, task, request = load_request(run_id)
    started = time.monotonic(); code = 1
    stdout_path, stderr_path = task / "stdout.txt", task / "stderr.txt"
    try:
        if request["mode"] == "final":
            raise ValueError("GT10PC_FINAL_DISABLED_UNTIL_NATIVE_P1_P10")
        console = Path(sys.executable).resolve().with_name("python.exe")
        producer = STUDIO / "tests" / "conformance" / "run_gt10pc_native_probe.py"
        command = [str(console), "-B", str(producer), "--output", str(matrix_root),
                   "--trust", str(TRUST), "--trust-sha256", request["trust_sha256"],
                   "--private-key", str(PRIVATE)]
        env = os.environ.copy(); env["PYTHONPATH"] = str(STUDIO) + os.pathsep + env.get("PYTHONPATH", "")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            proc = subprocess.run(command, cwd=REPO_ROOT, stdout=stdout, stderr=stderr,
                                  env=env, check=False)
            code = int(proc.returncode)
        if code == 0:
            verify = subprocess.run([str(console), "-B", str(MATRIX), "--verify-only", str(matrix_root)],
                                    cwd=REPO_ROOT, env=env, capture_output=True, text=True, check=False)
            (task / "verify-stdout.txt").write_text(verify.stdout, encoding="utf-8")
            (task / "verify-stderr.txt").write_text(verify.stderr, encoding="utf-8")
            code = int(verify.returncode)
    except BaseException:
        with stderr_path.open("ab") as stderr: stderr.write(traceback.format_exc().encode())
    finally:
        write_new(task / "return.json", {"schema": "HH-GT10PC-TASK-RETURN-2", "run_id": run_id,
            "returned_exit_code": code, "matrix_root": str(matrix_root),
            "source_closure_sha256": request["source_closure_sha256"],
            "elapsed_seconds": time.monotonic() - started, "actual_process_exit_observed": True,
            "formal_acceptance": False, "mode": request["mode"]})
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--prepare", action="store_true"); parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("rehearsal", "final"), default="rehearsal")
    args = parser.parse_args(argv)
    if args.prepare:
        print(json.dumps({"schema": SCHEMA, "task": str(prepare(args.run_id, args.mode))}, sort_keys=True)); return 0
    if Path(sys.executable).name.lower() != "pythonw.exe": raise ValueError("GT10PC_TASK_WINDOWED_INTERPRETER_REQUIRED")
    return run(args.run_id)


if __name__ == "__main__": raise SystemExit(main())
