"""Freeze a disposable GT-02 test snapshot and capture real owned host exits.

This produces CANDIDATE or DIAGNOSTIC evidence, never acceptance. Source and
test closure are hashed before/after; a child must print its unittest counts
after execution as well as exit cleanly. The accepted bootstrap Job Object
runner owns the test child and all its descendants on Windows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO))
from host.core.redaction import Redactor

SPEC = importlib.util.spec_from_file_location("gt01_owned_runner", STUDIO / "build/bootstrap/run_fixture.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
SOURCE_DIRS = ("protocol", "host/core", "tests/protocol", "tests/bootstrap", "build/bootstrap", "fixtures")
EXCLUDE = {"__pycache__", ".godot", ".local", "evidence"}
LF_SOURCE_SUFFIXES = {".txt", ".md", ".json", ".jsonl", ".py", ".ps1",
                      ".gd", ".uid", ".import", ".godot", ".tscn"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_manifest(studio=STUDIO):
    paths = [studio / "toolchain.lock.json"]
    for folder in SOURCE_DIRS:
        paths.extend(path for path in (studio / folder).rglob("*")
                     if path.is_file() and not (set(path.relative_to(studio).parts) & EXCLUDE))
    result = {}
    for path in sorted(paths):
        if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
            raise ValueError("SOURCE_REPARSE_FORBIDDEN")
        if path.suffix in LF_SOURCE_SUFFIXES and b"\r\n" in path.read_bytes():
            raise ValueError("SOURCE_TEXT_NOT_LF")
        result[path.relative_to(studio).as_posix()] = sha(path)
    return result


def redact_golden_stream(raw, redactor):
    # LF is the record delimiter. str.splitlines() also splits U+0085,
    # U+2028 and U+2029 inside valid JSON strings, corrupting vector evidence.
    lines = []
    for line in raw.split("\n"):
        if line.startswith("HH_GT02_JCS "):
            # These are the fixed fixture's public conformance rows, checked
            # against the independent consumers by test_golden_vectors.
            value = json.loads(line[len("HH_GT02_JCS "):])
            if set(value) != {"rows", "rejected"}:
                raise ValueError("INVALID_GOLDEN_RECORD")
            lines.append(line)
        else:
            lines.append(redactor.text(line))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.run_id.isascii() or not all(c.isalnum() or c in "-_" for c in args.run_id):
        parser.error("invalid run ID")
    output = args.output.resolve()
    output.relative_to(STUDIO.parent / "zdoc/reviews")
    output.mkdir(parents=True, exist_ok=False)
    before = source_manifest()
    closure = RUNNER.source_closure_sha256(before)
    (output / "source-closure.json").write_text(json.dumps({
        "schema": "hh-gt02-source-closure-v1", "source_closure_sha256": closure,
        "files": before}, indent=2) + "\n", encoding="utf-8")
    started = datetime.now(timezone.utc).isoformat()
    lanes = []
    redactor = Redactor(host_paths=[str(STUDIO.parent), str(Path.home()), tempfile.gettempdir()])
    with tempfile.TemporaryDirectory(prefix="hh-gt02-frozen-") as temporary:
        snapshot = Path(temporary)
        for relative in before:
            destination = snapshot / "studio" / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(STUDIO / relative, destination)
            if sha(destination) != before[relative]:
                raise ValueError("COPY_SOURCE_CHANGED")
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(snapshot)
        environment["PYTHONIOENCODING"] = "utf-8"
        local = STUDIO / ".local/toolchain.local.json"
        if local.exists():
            console = json.loads(local.read_text(encoding="utf-8")).get("godot_console")
            if console:
                environment["HH_STUDIO_GODOT_CONSOLE"] = console
        if not environment.get("HH_STUDIO_GODOT_CONSOLE"):
            pin = json.loads((STUDIO / "toolchain.lock.json").read_text(encoding="utf-8"))["godot"]
            environment["HH_STUDIO_GODOT_CONSOLE"] = str(STUDIO / ".local/tooling" / ("godot-" + pin["version"]) / pin["console_executable"])
        environment["HH_GT02_GOLDEN_EVIDENCE_DIR"] = str(output / "golden")
        for suite in ("protocol", "bootstrap"):
            code = "\n".join([
                "import json,sys,unittest", "from pathlib import Path",
                "suite=unittest.defaultTestLoader.discover(sys.argv[1], pattern='test_*.py')",
                "def flatten(item):",
                "    return [item.id()] if isinstance(item,unittest.TestCase) else [key for child in item for key in flatten(child)]",
                "test_ids=flatten(suite)",
                "r=unittest.TextTestRunner(verbosity=2).run(suite)",
                "summary={'tests_run':r.testsRun,'test_ids':test_ids,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),'skipped':[{'id':t.id(),'reason':s} for t,s in r.skipped]}",
                "print('HH_GT02_TEST_RESULT '+json.dumps(summary),flush=True)",
                "sys.exit(0 if r.wasSuccessful() else 1)",
            ])
            run = RUNNER.run_process([sys.executable, "-c", code, str(snapshot / "studio/tests" / suite)],
                                     cwd=snapshot, output=output, timeout=120, label=suite, env=environment)
            stdout = (output / run["stdout"]).read_text(encoding="utf-8", errors="strict")
            markers = [line[len("HH_GT02_TEST_RESULT "):] for line in stdout.splitlines() if line.startswith("HH_GT02_TEST_RESULT ")]
            summary = json.loads(markers[0]) if len(markers) == 1 else None
            host = json.loads((output / run["host"]).read_text(encoding="utf-8")) if (output / run["host"]).exists() else {}
            passed = (run["exit_code"] == run["wrapper_exit_code"] == host.get("exit_code") == 0
                      and run["tree_verified"] and not run["timed_out"] and summary is not None
                      and summary["tests_run"] > summary["skips"] and summary["failures"] == summary["errors"] == 0
                      and len(set(summary["test_ids"])) == len(summary["test_ids"]) == summary["tests_run"])
            required_skips = [skip for skip in (summary or {}).get("skipped", [])
                              if "GoldenVectorTests" in skip["id"] or "JournalCasTests" in skip["id"]]
            passed = passed and not required_skips
            for stream_name in (run["stdout"], run["stderr"]):
                stream = output / stream_name
                raw = stream.read_text(encoding="utf-8", errors="strict")
                # Redact line by line: bounded policy must not reject a whole
                # long suite log merely due to its combined length.
                stream.write_text("\n".join(redactor.text(line) for line in raw.splitlines()) + "\n", encoding="utf-8")
            lanes.append({"suite": suite, "host": run, "summary": summary, "passed": passed,
                          "missing_required_evidence": required_skips})
        snapshot_unchanged = source_manifest(snapshot / "studio") == before
    after = source_manifest()
    stable = before == after and snapshot_unchanged
    evidence = {"schema": "hh-gt02-candidate-v1", "run_id": args.run_id,
                "command_id": "cmd." + args.run_id, "seed": 8785,
                "started_utc": started, "completed_utc": datetime.now(timezone.utc).isoformat(),
                "source_closure_sha256": closure, "source_unchanged": stable,
                "environment": {"os": platform.system(), "release": platform.release(),
                                "architecture": platform.machine(), "python": platform.python_version(),
                                "python_sha256": sha(Path(sys.executable))},
                "lanes": lanes, "acceptance": "NOT_REVIEWED",
                "acceptance_ready": False,
                "known_gaps": ["Public safe-write/replace disabled; protected file fixture has IPC/journal integration but reopened mutation, custody and production supervisor remain incomplete",
                               "Godot JCS proves serialization; raw wire admission remains separate",
                               "two independent frozen-source critic verdicts required"],
                "status": "CANDIDATE" if stable and all(lane["passed"] for lane in lanes) else "DIAGNOSTIC",
                "repro": "python studio/tests/protocol/run_gt02_candidate.py --run-id NEW_UNIQUE_ID --output zdoc/reviews/NEW_UNIQUE_DIRECTORY"}
    # Golden diagnostic streams are output boundaries too; preserve original
    # stream hashes, redact their text without altering numeric/exit evidence.
    for artifact in (output / "golden").glob("*.json"):
        record = json.loads(artifact.read_text(encoding="utf-8"))
        for field in ("stdout", "stderr"):
            if field in record:
                raw = record[field]
                record[field + "_raw_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                record[field] = redact_golden_stream(raw, redactor)
        artifact.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Bind every output artifact, including real Godot rows and host records.
    evidence["artifacts"] = {path.relative_to(output).as_posix(): sha(path)
                             for path in sorted(output.rglob("*")) if path.is_file()}
    (output / "candidate.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "source_closure_sha256": closure,
                      "lanes": [{"suite": lane["suite"], "summary": {key: value for key, value in lane["summary"].items()
                                  if key != "test_ids"} if lane["summary"] else None} for lane in lanes]}))
    return 0 if evidence["status"] == "CANDIDATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
