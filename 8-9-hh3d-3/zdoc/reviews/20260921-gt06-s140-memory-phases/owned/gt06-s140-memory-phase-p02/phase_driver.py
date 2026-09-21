"""Owned S140 phase-memory diagnostic. Never a formal benchmark dataset.

Prepare is inert and exclusive. --run-existing consumes a prepared ID once.
Child runs the unchanged campaign under bounded observation hooks; the normal
end-of-batch GC after the last original gate ends the diagnostic.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
CLOSURE = "763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4"
NATIVE = "13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95"
PROFILE = "0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85"
RUN_RE = re.compile(r"gt06-s140-memory-phase-[a-z0-9-]{1,12}\Z")
FREEZE139 = ROOT / "zdoc/reviews/20260921-gt06-s138-coordinator/source-freeze-s139.json"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def read(path):
    return json.loads(path.read_bytes())


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_campaign(root):
    sys.path.insert(0, str(root))
    from studio.tests.replay import run_benchmark_campaign as campaign
    campaign.load_fixture()  # dynamic dependencies must load before hashing.
    return campaign


def check(root=ROOT):
    campaign = load_campaign(root)
    sources = campaign.source_files()
    if campaign.closure(sources) != CLOSURE or len(sources) != 53:
        raise RuntimeError("S140_SOURCE_DRIFT")
    if sha(root / "studio/tests/replay/benchmark_native.gd") != NATIVE:
        raise RuntimeError("S140_NATIVE_DRIFT")
    if campaign.profile.PROFILE_SHA256 != PROFILE:
        raise RuntimeError("S140_PROFILE_DRIFT")
    lock = read(root / "studio/toolchain.lock.json")["godot"]
    binary = root / "studio/.local/tooling/godot-4.7.2-stable" / lock["gui_executable"]
    if sha(binary) != lock["gui_sha256"]:
        raise RuntimeError("S140_BINARY_DRIFT")
    return campaign, sources


def error_record(error):
    value = str(error)
    return {"type": type(error).__name__,
            "code": getattr(error, "code", None) or
                    (value if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else None)}


def prepare(run_id, prefix):
    if not RUN_RE.fullmatch(run_id) or prefix not in (1, 7):
        raise ValueError("S140_RUN_ID_OR_PREFIX")
    if len(run_id + ".r00.a01") > 48:
        raise ValueError("S140_COMMAND_PRODUCER_ID_LIMIT")
    campaign, sources = check()
    run = ROOT / "studio/.local/reviews" / run_id
    helpers = BASE / "owned" / run_id
    if run.exists() or helpers.exists():
        raise RuntimeError("S140_FRESH_ID_REQUIRED")
    frozen139 = read(FREEZE139)
    execution = {"studio/" + name: value for name, value in sources.items()}
    installed = frozen139["installed_execution"]["source_files"]
    for name, value in installed.items():
        key = "studio/" + name
        if key in execution and execution[key] != value:
            raise RuntimeError("S140_SOURCE_PROJECTION_CONFLICT")
        execution[key] = value
    for name, value in execution.items():
        if sha(ROOT / name) != value:
            raise RuntimeError("S140_INSTALLED_SOURCE_DRIFT")
    # Inspect/compile before creating the exclusive output directory.
    compile((BASE / "memory_phases.py").read_bytes(), "memory_phases.py", "exec")
    compile(Path(__file__).read_bytes(), "phase_driver.py", "exec")
    run.mkdir()
    (run / "attempt").mkdir()
    helpers.mkdir(parents=True)
    for source, name in ((Path(__file__), "phase_driver.py"), (BASE / "memory_phases.py", "memory_phases.py")):
        target = helpers / name
        shutil.copyfile(source, target)
        execution[target.relative_to(ROOT).as_posix()] = sha(target)
    campaign_doc = {
        "schema_id": "hh-studio.s140-diagnostic-campaign", "campaign_id": run_id,
        "source_files": sources, "source_closure_sha256": CLOSURE,
        "profile_sha256": PROFILE, "prefix_batches": prefix,
        "formal_acceptance": False, "eligible_for_dataset": False}
    write(run / "campaign.json", campaign_doc)
    context = {
        "run_id": run_id + ".r00.a01", "index": 0, "attempt": 1,
        "source_files": sources, "source_closure_sha256": CLOSURE,
        "profile_sha256": PROFILE, "campaign_sha256": sha(run / "campaign.json"),
        "formal_acceptance": False, "eligible_for_dataset": False}
    write(run / "attempt/context.json", context)
    for path in (run / "campaign.json", run / "attempt/context.json"):
        execution[path.relative_to(ROOT).as_posix()] = sha(path)
    freeze = {
        "schema": "HH-GT06-S140-freeze-2", "run_id": run_id, "prefix_batches": prefix,
        "original_root": str(ROOT), "helper_root": str(helpers),
        "source_files": sources, "source_closure": CLOSURE, "native_sha256": NATIVE,
        "profile_sha256": PROFILE, "source_freeze_s139_sha256": sha(FREEZE139),
        "python_sha256": sha(sys.executable), "outer_seconds": 300 if prefix == 1 else 1230,
        "created_utc": utc(), "formal_acceptance": False, "eligible_for_dataset": False}
    write(run / "freeze.json", freeze)
    execution[(run / "freeze.json").relative_to(ROOT).as_posix()] = sha(run / "freeze.json")
    write(run / "execution-source-files.json", execution)
    return run


def child(run):
    freeze = read(run / "freeze.json")
    root = Path(freeze["original_root"])
    helpers = Path(freeze["helper_root"])
    if Path(__file__).resolve() != helpers / "phase_driver.py":
        raise RuntimeError("S140_COPIED_CHILD_REQUIRED")
    execution = read(run / "execution-source-files.json")
    if not all(sha(root / name) == value for name, value in execution.items()):
        raise RuntimeError("S140_EXECUTION_DRIFT")
    campaign = load_campaign(root)
    if campaign.source_files() != freeze["source_files"]:
        raise RuntimeError("S140_CHILD_SOURCE_DRIFT")
    from memory_phases import PhaseMemoryRecorder, install_phase_memory_wrappers, BoundedPhaseStop
    recorder = PhaseMemoryRecorder(freeze["run_id"] + ".r00.a01", freeze["prefix_batches"])
    status, primary, cleanup = "INCOMPLETE", None, []
    try:
        # No factory patch: wrappers bind directly to the stock class methods.
        with install_phase_memory_wrappers(campaign, recorder):
            campaign.run_child(run / "attempt")
        status = "UNEXPECTED_FULL_COMPLETION"
    except BoundedPhaseStop as error:
        status = "BOUNDARY_CAPTURED"
        cleanup = [error_record(e) for e in getattr(error, "cleanup_errors", ())]
    except BaseException as error:
        status, primary = "ORIGINAL_FAILURE", error_record(error)
        cleanup = [error_record(e) for e in getattr(error, "cleanup_errors", ())]
    finally:
        recorder.persist(run / "phase-memory.json", status=status,
                         error_code=primary["code"] if primary else None)
        write(run / "diagnostic-summary.json", {
            "schema": "HH-GT06-S140-summary-2", "run_id": freeze["run_id"],
            "pid": os.getpid(), "status": status, "primary_error": primary,
            "cleanup_errors": cleanup, "phase_rows": recorder.row_count,
            "phase_sha256": sha(run / "phase-memory.json"),
            "source_unchanged": campaign.source_files() == freeze["source_files"],
            "ended_utc": utc(), "formal_acceptance": False, "eligible_for_dataset": False,
            "scope": "Instrumented prefix. Boundary termination is not a natural full editor exit."})
    # Deliberate boundary is nonzero, never reclassified as a benchmark PASS.
    return 1


def launch(run):
    freeze = read(run / "freeze.json")
    if run != ROOT / "studio/.local/reviews" / freeze["run_id"]:
        raise RuntimeError("S140_RUN_PATH")
    write(run / "dispatch-once.json", {"dispatched_utc": utc(), "pid": os.getpid()})
    campaign = load_campaign(ROOT)
    context = read(run / "attempt/context.json")
    execution = read(run / "execution-source-files.json")
    owner = None
    errors = []
    helper_exit = None
    started = time.monotonic()

    def stopped():
        return campaign.stop_requested(run / "attempt", run_id=context["run_id"],
            source_closure_sha256=CLOSURE, campaign_sha256=context["campaign_sha256"])

    try:
        if stopped():
            raise RuntimeError("BENCHMARK_STOPPED")
        owner = campaign.BenchmarkProcess(
            [sys.executable, "-B", str(Path(freeze["helper_root"]) / "phase_driver.py"),
             "--child", str(run)], cwd=run, output=run / "owned",
            source_root=ROOT, source_files=execution,
            binary_sha256=freeze["python_sha256"], campaign_host=True)
        while True:
            helper_exit = owner.tick(stop=stopped())
            if helper_exit is not None:
                break
            if time.monotonic() - started >= freeze["outer_seconds"]:
                raise RuntimeError("S140_OUTER_LIMIT")
            time.sleep(.2)
    except BaseException as error:
        if owner is None:
            owner = getattr(error, "cleanup_owner", None)
        errors.append(error_record(error))
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(error_record(error))
        observations = {}
        for name, getter in (
            ("owner", lambda: campaign._editor_cleanup_state(owner)),
            ("target", lambda: campaign._target_exit_state(run, "owned")),
            ("source_unchanged", lambda: campaign.source_files() == freeze["source_files"]),
            ("execution_unchanged", lambda: all(sha(ROOT / p) == h for p, h in execution.items())),
            ("stop_requested", stopped),
        ):
            try:
                observations[name] = getter()
            except BaseException as error:
                observations[name] = None
                errors.append({"stage": name, **error_record(error)})
        write(run / "result.json", {
            "schema": "HH-GT06-S140-owner-result-2", "run_id": freeze["run_id"],
            "helper_exit_before_close": helper_exit, "errors": errors,
            "observations": observations, "elapsed_seconds": time.monotonic() - started,
            "ended_utc": utc(), "formal_acceptance": False, "eligible_for_dataset": False})
    print(json.dumps({"terminal": str(run), "errors": errors, "helper_exit": helper_exit}), flush=True)
    return 0 if not errors and (run / "diagnostic-summary.json").is_file() else 1


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--run-existing", type=Path)
    modes.add_argument("--child", type=Path)
    parser.add_argument("--run-id")
    parser.add_argument("--prefix", type=int, choices=(1, 7), default=1)
    args = parser.parse_args()
    if args.check:
        _, sources = check()
        print(json.dumps({"checked": True, "source_count": len(sources), "closure": CLOSURE}))
        return 0
    if args.prepare:
        print(json.dumps({"prepared": str(prepare(args.run_id, args.prefix))}))
        return 0
    if args.child:
        return child(args.child.resolve())
    return launch(args.run_existing.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
