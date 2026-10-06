"""GT07 scenario admission and matrix runner.

The dry-run path is deliberately engine-free.  It validates the frozen source
closure, pinned executable bytes, public scenario/deadline contract and the
owner's measure-window lock before an existing native probe is invoked.  The
native path only delegates to the already-tested Blender/Godot probes; it does
not implement a second queue or retry policy.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import stat
import subprocess

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.measure_window import default_path, plain
from studio.host.core.gt07_failpoints import assert_disabled, runtime_root
from studio.tests.jobs.gt07_failure import failure_boundary

SCENARIOS = {
    "godot-authority": {"kind": "godot", "operation": "scene.node.update",
                       "probe": "run_native_godot_queue_probe.py", "suffix": "authority",
                       "max_horizon_ms": 30_000, "authority_cases": True, "failpoint_phases": ()},
    "godot-edit": {"kind": "godot", "operation": "scene.node.update",
                   "probe": "run_native_godot_queue_probe.py", "suffix": "edit",
                   "max_horizon_ms": 30_000, "failpoint_phases": ()},
    "godot-save": {"kind": "godot", "operation": "scene.save",
                   "probe": "run_native_godot_queue_probe.py", "suffix": "save",
                   "max_horizon_ms": 90_000,
                   "failpoint_phases": ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "RELOAD", "ACK")},
    "godot-save-locked": {"kind": "godot", "operation": "scene.save",
                          "probe": "run_native_godot_queue_probe.py", "suffix": "save-locked",
                          "max_horizon_ms": 90_000, "file_lock": True, "failpoint_phases": ()},
    "godot-script": {"kind": "godot", "operation": "script_text.replace",
                     "probe": "run_native_godot_queue_probe.py", "suffix": "script",
                     "max_horizon_ms": 90_000,
                     "failpoint_phases": ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "RELOAD", "ACK")},
    "godot-recovery": {"kind": "godot", "operation": "script_text.replace",
                       "probe": "run_native_godot_queue_probe.py", "suffix": "recovery",
                   "max_horizon_ms": 90_000, "recover_after_loss": True, "failpoint_phases": ()},
    "godot-conflict": {"kind": "godot", "operation": "scene.node.update",
                       "probe": "run_native_godot_queue_probe.py", "suffix": "conflict",
                       "max_horizon_ms": 30_000, "manual_conflict": True, "failpoint_phases": ()},
    "blender-box": {"kind": "blender", "operation": "mesh.create_box",
                    "probe": "run_native_blender_queue_probe.py", "suffix": "blender",
                    "max_horizon_ms": 5_000, "failpoint_phases": ()},
    "blender-authority": {"kind": "blender", "operation": "mesh.create_box",
                          "probe": "run_native_blender_queue_probe.py", "suffix": "authority",
                          "max_horizon_ms": 30_000, "authority_cases": True,
                          "failpoint_phases": ()},
    "blender-conflict": {"kind": "blender", "operation": "object.transform.set",
                         "probe": "run_native_blender_queue_probe.py", "suffix": "conflict",
                         "max_horizon_ms": 30_000, "manual_conflict": True,
                         "failpoint_phases": ()},
    "blender-export": {"kind": "blender", "operation": "export.publish",
                       "probe": "run_native_blender_queue_probe.py", "suffix": "export",
                       "max_horizon_ms": 30_000,
                       "failpoint_phases": ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED", "ACK")},
}

# A phase is part of the row definition, never a matrix-wide CLI override.
for _base, _phases in (("godot-save", ("RELOAD", "ACK")),
                       ("godot-script", ("RELOAD", "ACK")),
                       ("blender-export", ("PREPARED", "VALIDATED", "ACTIVATING", "COMMITTED"))):
    for _phase in _phases:
        SCENARIOS[_base + "-cut-" + _phase.lower()] = {
            **SCENARIOS[_base], "phase": _phase}

ADAPTER_SCENARIOS = {
    "godot-fifo": {"kind": "fifo", "app": "godot", "matrix": "M2",
                   "probe": "../godot/run_fifo_publication_probe.py", "timeout": 210,
                   "run_prefix": "gt07-godot-fifo"},
    "blender-fifo": {"kind": "fifo", "app": "blender", "matrix": "M2",
                     "probe": "../blender/run_writer_fifo_probe.py", "timeout": 60,
                     "run_prefix": "gt07-blender-fifo"},
    "cross-app-reload": {"kind": "cross-app", "phase": "RELOAD", "matrix": "M3",
                         "producer": "blender-export", "run_prefix": "gt07-cross-app"},
    "cross-app-ack": {"kind": "cross-app", "phase": "ACK", "matrix": "M3",
                      "producer": "blender-export", "run_prefix": "gt07-cross-app"},
    "play-mutation": {"kind": "adversary", "matrix": "M9",
                      "run_prefix": "gt06-gt07-m9-playmutation"},
}

HOST_SCENARIOS = {
    "host-storage": {"kind": "host", "probe": "gt07_storage_faults.py",
                      "run_prefix": "gt07-m5-final", "matrix": "M5"},
    "host-process": {"kind": "host", "probe": "gt07_process_ownership.py",
                      "run_prefix": "gt07-m8-final", "matrix": "M8",
                      # M8's probe owns the fixed guard around its three
                      # process/Job sub-scenarios.  The matrix runner must
                      # not acquire the same non-reentrant guard outside it.
                      "owns_measure_guard": True},
    "host-m1-tests": {"kind": "host-test", "run_prefix": "gt07-m1-final",
                      "matrix": "M1", "tests": (
                          "studio.tests.jobs.test_dispatch_policy",
                          "studio.tests.jobs.test_durable_broker",
                          "studio.tests.jobs.test_selector_dispatch",
                          "studio.tests.jobs.test_native_dispatch",
                      )},
    "host-m6-tests": {"kind": "host-test", "run_prefix": "gt07-m6-final",
                      "matrix": "M6", "tests": (
                          "studio.tests.jobs.test_gt07_stop_lifecycle",
                          "studio.tests.jobs.test_native_godot_stop",
                      )},
    "host-m7-tests": {"kind": "host-test", "run_prefix": "gt07-m7-final",
                      "matrix": "M7", "environment": {
                          "GT07_REAL_CLOCK_SOAK": "1", "GT07_REAL_CLOCK_ROTATION_CUTS": "1"}, "tests": (
                          "studio.tests.jobs.test_queue_rotation_custody",
                          "studio.tests.jobs.test_segmented_broker_regression",
                          "studio.tests.jobs.test_segmented_journal",
                      )},
    "host-gt02-06-regression-tests": {"kind": "host-test", "run_prefix": "gt07-gt02-06-regression",
                                       "matrix": "REGRESSION", "tests": (
                                           "studio.tests.godot.test_contract",
                                           "studio.tests.godot.test_publication_fifo",
                                           "studio.tests.godot.test_publication_fifo_host",
                                           "studio.tests.godot.test_publication_recovery",
                                           "studio.tests.godot.test_recovery_host",
                                           "studio.tests.godot.test_recovery_journal_native",
                                           "studio.tests.godot.test_publication_owner",
                                           "studio.tests.godot.test_publication_journal_v5",
                                           "studio.tests.blender.test_client_writer_publication",
                                           "studio.tests.blender.test_publication",
                                           "studio.tests.replay.test_contract",
                                           "studio.tests.replay.test_service_adversary",
                                           "studio.tests.jobs.test_cross_app_publication",
                                           "studio.tests.jobs.test_gt07_scenarios",
                                           "studio.tests.jobs.test_native_dispatch",
                                           "studio.tests.jobs.test_segmented_broker_regression",
                                           "studio.tests.jobs.test_segmented_journal",
                                       )},
}
ALL_SCENARIOS = {**SCENARIOS, **HOST_SCENARIOS, **ADAPTER_SCENARIOS}

# Host tests supplement the native rows. Cross-app consumer rows depend only
# on the fresh export in this same invocation, never a historical handoff.
FINAL_MATRIX = (
    "host-m1-tests", "godot-fifo", "blender-fifo",
    "godot-authority", "godot-edit", "godot-save", "godot-save-locked",
    "godot-script", "godot-recovery", "godot-conflict", "blender-box",
    "blender-authority", "blender-conflict", "blender-export",
    "blender-export-cut-prepared", "blender-export-cut-validated",
    "blender-export-cut-activating", "blender-export-cut-committed",
    "cross-app-reload", "cross-app-ack",
    "godot-save-cut-reload", "godot-save-cut-ack",
    "godot-script-cut-reload", "godot-script-cut-ack",
    "host-storage", "host-process", "host-m6-tests", "host-m7-tests", "play-mutation",
    "host-gt02-06-regression-tests",
)
MATRIX_ALIASES = {"final": FINAL_MATRIX}

REQUIREMENTS = {
    "host-m1-tests": ["M1/Q01/TX18"],
    "godot-fifo": ["M2/Q03/TX06", "M6/Q04/TX14"],
    "blender-fifo": ["M2/Q03/TX06", "M6/Q04/TX14"],
    "godot-authority": ["M2/Q03/TX06"], "godot-edit": ["M2/Q03/TX06"],
    "blender-authority": ["M2/Q03/TX06"], "blender-box": ["M2/Q03/TX06"],
    "godot-save-locked": ["M5/Q06/TX05/TX09"],
    "godot-conflict": ["M4/Q06/TX06"], "blender-conflict": ["M4/Q06/TX06"],
    "host-storage": ["M5/Q06/TX05/TX09"], "host-process": ["M8/TX05"],
    "host-m6-tests": ["M6/Q04/TX14"], "host-m7-tests": ["M7/Q07/TX11"],
    "play-mutation": ["M9/TX13"],
    "host-gt02-06-regression-tests": ["GT02-GT06/FOCUSED_REGRESSION"],
}
for _name in FINAL_MATRIX:
    REQUIREMENTS.setdefault(_name, ["M3/Q05/TQ07/TX09/TX11"])


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_probe(name: str):
    path = STUDIO / "tests/jobs" / name
    spec = importlib.util.spec_from_file_location("gt07_scenario_probe", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("SCENARIO_PROBE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scenario(name: str) -> dict:
    return ALL_SCENARIOS[name]


def _host_test_sources(scenario: dict) -> dict[str, str]:
    # Test-module hashes alone miss changes in the implementation they import.
    values = _matrix_sources()
    for module_name in scenario["tests"]:
        relative = Path(*module_name.split(".")).with_suffix(".py")
        path = STUDIO.parent / relative
        if not path.is_file():
            raise ValueError("HOST_TEST_SOURCE_MISSING")
        values[relative.as_posix()] = _sha(path)
    values["source_closure_sha256"] = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return values


def _matrix_sources() -> dict[str, str]:
    """One source universe for the whole run, including drivers and fixtures.

    Tracked files plus the explicit runtime trees include local new source;
    generated evidence, caches, credentials and installed binaries are excluded.
    Pins are bound separately. Per-probe maps remain useful as subsets, not as
    independent freezes taken after earlier matrix rows have already executed.
    """
    raw = subprocess.check_output(["git", "ls-files", "-z", "--", "studio"],
                                  cwd=STUDIO.parent)
    paths = {STUDIO.parent / name for name in raw.decode().split("\0") if name}
    for folder in ("godot-addon", "blender-addon", "host", "protocol", "pipeline",
                   "contracts", "tests", "build/bootstrap"):
        paths.update(path for path in (STUDIO / folder).rglob("*")
                     if path.is_file() and "__pycache__" not in path.parts
                     and ".godot" not in path.parts
                     and path.suffix in (".py", ".gd", ".json", ".godot", ".cfg",
                                         ".tscn", ".tres", ".uid", ".glb", ".png", ".md"))
    result = {}
    for path in sorted(paths):
        plain(path)
        result[path.relative_to(STUDIO).as_posix()] = _sha(path)
    return result


def _source_digest(files: dict) -> str:
    return hashlib.sha256(json.dumps(files, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _adapter_admission(name, scenario, args, index, output):
    _check_lock(args.measure_lock, native=True)
    assert_disabled(STUDIO)
    assert_disabled(runtime_root(STUDIO))
    report = {"scenario": name, "kind": scenario["kind"], "run_id": output.name,
              "output": str(output), "matrix": scenario["matrix"],
              "dry_run": True, "engine_started": False, "authority": 0}
    if scenario["kind"] == "fifo":
        binary = _binary_for(scenario, args)
        base = SCENARIOS["godot-authority" if scenario["app"] == "godot" else "blender-authority"]
        contract = _contract_dry_run(name, base)
        files = _matrix_sources()
        runner = _load_probe("../../build/bootstrap/run_fixture.py")
        fifo_closure = runner.source_closure_sha256(files)
        report.update(binary=str(binary), binary_sha256=_sha(binary), contract=contract,
                      source_closure_sha256=fifo_closure,
                      matrix_source_closure_sha256=_source_digest(files))
    elif scenario["kind"] == "adversary":
        probe = _load_probe("../replay/run_service_adversary.py")
        value = probe.dry_run(output.name, "play-mutation")
        report.update(adversary=value, source_closure_sha256=value["source_closure_sha256"],
                      driver_sha256=value["driver_sha256"])
    else:
        # Output bytes do not exist until the preceding producer completes.
        # Bind the edge now; validate the actual receipt/GLB before consumption.
        names = getattr(args, "matrix_names", ())
        if scenario["producer"] not in names[:index]:
            raise ValueError("CROSS_APP_SAME_MATRIX_PRODUCER_REQUIRED")
        producer_index = names.index(scenario["producer"])
        producer_id = args.run_ids[producer_index]
        probe = _load_probe("run_gt07_cross_app_probe.py")
        owner = probe.base.load("gt07_matrix_gameplay_owner", STUDIO / "godot-addon/gameplay_source_owner.py")
        fixture = argparse.Namespace(fixture="gameplay_source_assets", saved_arena=None,
                                     blender_published=Path(args.output_root) / producer_id / "published")
        files, closure = probe._probe_sources(owner, fixture)
        executor = owner._load("linux_executor")
        executor._lock()
        binary = executor._binary()
        adapter_closure = _source_digest(files)
        handoff = str(fixture.blender_published)
        report.update(source_closure_sha256=closure, source_hashes=files,
                      binary=str(binary), binary_sha256=_sha(binary),
                      adapter_source_closure_sha256=adapter_closure,
                      failpoint_phase=scenario["phase"], producer_run_id=producer_id,
                      handoff=handoff,
                      dependency_receipt_pending=True,
                      dependency_status="PENDING_PRODUCER_TERMINAL", matrix_admission=True)
    return report


def _run_fifo(scenario, check):
    """Reuse the existing frozen FIFO entrypoint and owned Job wrapper."""
    output = Path(check["output"])
    output.mkdir(parents=True, exist_ok=False)
    files = _matrix_sources()
    runner = _load_probe("../../build/bootstrap/run_fixture.py")
    closure = runner.source_closure_sha256(files)
    if closure != check.get("source_closure_sha256"):
        raise ValueError("FIFO_SOURCE_CLOSURE_CHANGED")
    snapshot = output / "source/studio"
    for name, expected in files.items():
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
        if _sha(target) != expected:
            raise ValueError("FIFO_SNAPSHOT_CHANGED")
    _write_json(output / "source-closure.json", {"files": files, "source_closure_sha256": closure})
    relative = (Path("tests/jobs") / scenario["probe"]).as_posix()
    command = [sys.executable, "-B", str(snapshot / relative), "--frozen",
               "--output", str(output), "--binary", check["binary"]]
    if scenario["app"] == "godot":
        command += ["--run-id", output.name, "--closure", closure]
    env = dict(os.environ)
    env["HH_STUDIO_LINUX_GODOT"] = str(STUDIO / ".local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64")
    host = runner.run_process(command, cwd=snapshot, output=output,
                              timeout=scenario["timeout"], label="fifo", env=env)
    receipt = output / ("fifo-publication.json" if scenario["app"] == "godot" else "native.json")
    child = json.loads(receipt.read_bytes()) if receipt.is_file() else {}
    passed = (host.get("exit_code") == host.get("wrapper_exit_code") == 0
              and host.get("tree_verified") is True and not host.get("timed_out")
              and child.get("passed") is True and files == _matrix_sources()
              and all(_sha(snapshot / n) == d for n, d in files.items()))
    report = {"command": command, "host": host, "child": child, "passed": passed,
              "authority": 0, "source_closure_sha256": closure}
    _write_json(output / "capture.json", report)
    return {"exit_code": 0 if passed else 1, "host": host, "command": command}


def _run_adapter(scenario, check):
    with _native_measure_guard():
        if scenario["kind"] == "fifo":
            return _run_fifo(scenario, check)
        if scenario["kind"] == "adversary":
            probe = _load_probe("../replay/run_service_adversary.py")
            fresh = probe.dry_run(check["run_id"], "play-mutation",
                expected_source_closure_sha256=check["source_closure_sha256"],
                expected_driver_sha256=check["driver_sha256"])
            if fresh != check["adversary"]:
                raise ValueError("ADVERSARY_ADMISSION_CHANGED")
            code = probe.bounded_run(check["run_id"], "play-mutation")
            return {"exit_code": code, "extra_raw_roots": [check["output"] + "-outer"]}
        probe = _load_probe("run_gt07_cross_app_probe.py")
        options = argparse.Namespace(run_id=check["run_id"],
            blender_published=Path(check["handoff"]), dry_run=True,
            failpoint_phase=check["failpoint_phase"])
        # Producer bytes can only be bound after that row completes.  This
        # declared dependency is resolved by one engine-free admission after
        # the producer terminal handoff, then consumed exactly once.
        if Path(check["output"]).exists():
            raise ValueError("CROSS_APP_OUTPUT_ALREADY_EXISTS")
        if probe._execute(options) != 0:
            raise ValueError("CROSS_APP_DEPENDENCY_ADMISSION_FAILED")
        binding = json.loads((Path(check["output"]) / "dry-run.json").read_bytes())
        for key in ("source_closure_sha256", "adapter_source_closure_sha256",
                    "binary_sha256", "failpoint_phase"):
            if binding.get(key) != check.get(key):
                raise ValueError("CROSS_APP_ADMISSION_CHANGED")
        options.dry_run = False
        return {"exit_code": probe._execute(options)}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _tree_digest(root: Path) -> str:
    """Hash a completed evidence tree without hashing the enclosing manifest."""
    if not root.exists():
        return ""
    digest = hashlib.sha256()
    for path in sorted((item for item in root.rglob("*") if item.is_file()),
                       key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(_sha(path)))
    return digest.hexdigest()


def _matrix_root(args: argparse.Namespace) -> Path:
    """Return the one-use durable coordinator directory for a matrix run."""
    if not args.run_ids:
        raise ValueError("MATRIX_RUN_IDS_REQUIRED")
    root = (Path(args.output_root).expanduser().resolve() /
            ("gt07-final-matrix-" + args.run_ids[0]))
    fixed_root = (STUDIO / ".local" / "reviews").resolve()
    if root.parent != fixed_root:
        raise ValueError("SCENARIO_OUTPUT_ROOT_FORBIDDEN")
    if root.exists():
        raise ValueError("MATRIX_MANIFEST_ALREADY_EXISTS")
    return root


def _atomic_json(path: Path, value: object) -> None:
    """Make the coordinator state durable without exposing a half-written JSON."""
    temporary = path.with_name(path.name + ".tmp")
    _write_json(temporary, value)
    os.replace(temporary, path)


def _append_event(root: Path, event: dict[str, object]) -> None:
    with (root / "events.ndjson").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"recorded_utc": datetime.now(timezone.utc).isoformat(),
                                 **event}, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _terminal_summary(result: dict[str, object], admission: dict[str, object],
                      index: int) -> dict[str, object]:
    """Keep manifest receipts compact while retaining actual cleanup evidence."""
    output = Path(str(result.get("output") or admission["output"]))
    summary: dict[str, object] = {
        "index": index,
        "scenario": admission["scenario"],
        "run_id": admission["run_id"],
        "requirement": REQUIREMENTS.get(admission["scenario"],
                                         [_scenario(admission["scenario"]).get("matrix", "REGRESSION")]),
        "output": str(output),
        "exit_code": result.get("exit_code"),
        "raw_tree_sha256": _tree_digest(output),
        "source_closure_sha256": admission.get("source_closure_sha256") or
                                 admission.get("matrix_source_closure_sha256"),
        "binary_sha256": admission.get("binary_sha256"),
    }
    for key in ("host", "host_report", "host_test_report", "child", "verified",
                "passed", "extra_raw_roots", "failure_boundary"):
        if key in result:
            value = result[key]
            if key == "host" and isinstance(value, dict):
                summary["host"] = {field: value.get(field) for field in
                                    ("exit_code", "wrapper_exit_code", "tree_verified",
                                     "timed_out", "job_closed", "active_processes",
                                     "retained_handle") if field in value}
            elif key in ("host_report", "host_test_report") and isinstance(value, dict):
                summary[key] = {field: value.get(field) for field in
                                 ("verified", "actual_exit", "exit_code", "wrapper_exit_code",
                                  "tree_verified", "timed_out", "source_unchanged")
                                 if field in value}
            elif key == "child" and isinstance(value, dict):
                summary["child"] = {field: value.get(field) for field in
                                     ("passed", "exit_code", "editor_exit", "wrapper_exit_code")
                                     if field in value}
            else:
                summary[key] = value
    return summary


def _persist_admission(matrix_root: Path, output: Path,
                       admission: dict[str, object], index: int) -> None:
    """Bind an engine-free row receipt before any native row is launched.

    Ordinary probes require a genuinely fresh output directory.  Their
    admission is therefore kept in the coordinator directory; host probes
    which already materialize a dry-run report and cross-app's dependency
    handoff are the only rows that receive the marker in their own directory.
    """
    admission_path = matrix_root / "admissions" / f"row-{index:02d}-{admission['run_id']}.json"
    admission["admission_path"] = str(admission_path)
    _write_json(admission_path, admission)
    scenario = _scenario(str(admission["scenario"]))
    if scenario["kind"] in ("host", "host-test"):
        output.mkdir(parents=True, exist_ok=True)
        _write_json(output / "matrix-admission.json", admission)


def _validate_admitted_row(name: str, args: argparse.Namespace, index: int,
                           admission: dict[str, object]) -> Path:
    output = Path(str(admission.get("output", ""))).resolve()
    fixed_root = (STUDIO / ".local" / "reviews").resolve()
    try:
        output.relative_to(fixed_root)
        admission_path = Path(str(admission.get("admission_path", ""))).resolve()
        admission_path.relative_to(fixed_root)
    except ValueError as error:
        raise ValueError("MATRIX_ADMISSION_PATH_FORBIDDEN") from error
    if admission.get("scenario") != name or admission.get("run_id") != output.name:
        raise ValueError("MATRIX_ADMISSION_ROW_MISMATCH")
    if not admission_path.is_file():
        raise ValueError("MATRIX_ADMISSION_RECEIPT_MISSING")
    # No second _output_for call here: its old existence check is precisely what
    # made same-invocation admission impossible.  The one-use receipt is bound
    # to the exact row and source closure instead.
    stored = json.loads(admission_path.read_bytes())
    if stored != admission:
        raise ValueError("MATRIX_ADMISSION_RECEIPT_CHANGED")
    return output


def _admit_matrix(args: argparse.Namespace, names: list[str],
                  matrix_source_digest: str) -> tuple[Path, list[dict[str, object]], str]:
    """Admit every row before row zero can start an engine."""
    run_ids = [str(value) for value in args.run_ids]
    if len(run_ids) != len(names) or len(set(run_ids)) != len(run_ids):
        raise ValueError("MATRIX_RUN_IDS_NOT_DISTINCT")
    root = _matrix_root(args)
    root.mkdir(parents=True)
    payload: dict[str, object] = {
        "schema": "gt07-final-matrix-manifest-2", "authority": 0,
        "state": "ADMITTING", "matrix_id": root.name,
        "coordinator_pid": os.getpid(),
        "coordinator_started_utc": datetime.now(timezone.utc).isoformat(),
        "matrix_source_closure_sha256": matrix_source_digest,
        "rows": [], "events": str(root / "events.ndjson"),
    }
    _atomic_json(root / "manifest.json", payload)
    _append_event(root, {"event": "MATRIX_ADMISSION_STARTED", "matrix_id": root.name})
    admissions: list[dict[str, object]] = []
    try:
        for index, name in enumerate(names):
            if matrix_source_digest != _source_digest(_matrix_sources()):
                raise ValueError("MATRIX_SOURCE_CHANGED_DURING_ADMISSION")
            admission = dry_run(name, args, index)
            admission["matrix_source_closure_sha256"] = matrix_source_digest
            _persist_admission(root, Path(str(admission["output"])), admission, index)
            admissions.append(admission)
            payload["rows"] = [{"index": row_index, "scenario": row["scenario"],
                                "run_id": row["run_id"],
                                "status": ("DEFERRED_DEPENDENCY" if row.get("dependency_receipt_pending")
                                           else "ADMITTED"),
                                "output": row["output"]}
                               for row_index, row in enumerate(admissions)]
            _atomic_json(root / "manifest.json", payload)
            _append_event(root, {"event": "ROW_ADMITTED", "index": index,
                                 "scenario": name, "run_id": admission["run_id"]})
        if matrix_source_digest != _source_digest(_matrix_sources()):
            raise ValueError("MATRIX_SOURCE_CHANGED_AFTER_ADMISSION")
        closure = matrix_closure(admissions)
        payload.update({"state": "ADMITTED", "matrix_closure_sha256": closure,
                        "rows": [{"index": index, "scenario": row["scenario"],
                                   "run_id": row["run_id"],
                                   "status": ("DEFERRED_DEPENDENCY" if row.get("dependency_receipt_pending")
                                              else "ADMITTED"),
                                   "output": row["output"]}
                                  for index, row in enumerate(admissions)]})
        _atomic_json(root / "manifest.json", payload)
        _append_event(root, {"event": "MATRIX_ADMITTED", "matrix_closure_sha256": closure,
                             "rows": len(admissions)})
        return root, admissions, closure
    except BaseException as error:
        payload.update({"state": "ADMISSION_FAILED", "error": str(error),
                        "rows": [{"index": index, "scenario": row["scenario"],
                                   "run_id": row["run_id"],
                                   "status": ("DEFERRED_DEPENDENCY" if row.get("dependency_receipt_pending")
                                              else "ADMITTED"),
                                   "output": row["output"]}
                                  for index, row in enumerate(admissions)]})
        _atomic_json(root / "manifest.json", payload)
        _append_event(root, {"event": "MATRIX_ADMISSION_FAILED", "error": str(error)})
        raise


def _binary_for(scenario: dict, args: argparse.Namespace) -> Path | None:
    if scenario["kind"] in ("host", "host-test"):
        return None
    app = scenario.get("app", scenario["kind"])
    value = args.godot_binary if app == "godot" else args.blender_binary
    if not value:
        raise ValueError("PINNED_BINARY_REQUIRED")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError("PINNED_BINARY_MISSING")
    lock = json.loads((STUDIO / "toolchain.lock.json").read_bytes())
    expected = (lock["godot"]["gui_sha256"] if app == "godot"
                else lock["blender"]["executable_sha256"])
    observed = _sha(path)
    if observed.lower() != expected.lower():
        raise ValueError("PINNED_BINARY_HASH_MISMATCH")
    return path


def _closure(scenario: dict) -> str:
    if scenario["kind"] == "host":
        raise ValueError("HOST_CLOSURE_IS_REPORTED_BY_PROBE")
    probe = _load_probe(scenario["probe"])
    source = probe._sources(STUDIO)
    closure = probe._closure(STUDIO, source)
    if not source or len(closure) != 64:
        raise ValueError("SOURCE_CLOSURE_INVALID")
    return closure


def _check_lock(path: str | None, *, native: bool) -> str | None:
    if not native:
        return None
    expected = default_path().expanduser().resolve()
    if path is not None and Path(path).expanduser().resolve() != expected:
        raise ValueError("MEASURE_WINDOW_LOCK_PATH_FORBIDDEN")
    # A formal marker is owned by the benchmark process.  Scenario probes may
    # run only while it is absent; accepting a caller-created marker would
    # turn this check into a bypass of the shared measurement lease.
    plain(expected)
    if expected.exists():
        raise ValueError("MEASURE_WINDOW_BUSY")
    return str(expected)


@contextmanager
def _native_measure_guard():
    """Hold the repository's fixed guard without creating a marker."""
    marker = default_path().expanduser().resolve()
    plain(marker)
    marker.parent.mkdir(parents=True, exist_ok=True)
    guard = marker.with_suffix('.guard')
    plain(guard)
    flags = os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0)
    fd = os.open(guard, flags, 0o600)
    locked = False
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("MEASURE_WINDOW_UNSAFE_GUARD")
        if marker.exists():
            raise ValueError("MEASURE_WINDOW_BUSY")
        if os.name == 'nt':
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise ValueError("MEASURE_WINDOW_BUSY") from error
        else:
            import fcntl
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise ValueError("MEASURE_WINDOW_BUSY") from error
        locked = True
        if marker.exists():
            raise ValueError("MEASURE_WINDOW_BUSY")
        yield str(marker)
    finally:
        if locked:
            if os.name == 'nt':
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        if marker.exists():
            raise ValueError("MEASURE_WINDOW_MARKER_CREATED")


def _contract_dry_run(name: str, scenario: dict) -> dict[str, object]:
    """Ask the existing probe to validate its real request contract.

    There is intentionally no fallback based on deadline constants.  Until a
    probe exposes this engine-free contract check, its native scenario remains
    gated and cannot be mistaken for a dry-run pass.
    """
    probe = _load_probe(scenario["probe"])
    checker = getattr(probe, "dry_run_contract", None)
    if not callable(checker):
        raise ValueError("SCENARIO_CONTRACT_DRY_RUN_UNAVAILABLE")
    result = checker(operation=scenario["operation"],
                     recover_after_loss=bool(scenario.get("recover_after_loss")),
                     **({'authority_cases': True} if scenario["kind"] == "godot"
                        and scenario.get("authority_cases") else {}))
    if scenario["kind"] == "blender" and scenario.get("authority_cases"):
        from studio.tests.jobs.gt07_writer_authority import validate_native_recipes
        validate_native_recipes()
    if not isinstance(result, dict):
        raise ValueError("SCENARIO_CONTRACT_DRY_RUN_INVALID")
    required = ("admission_validated",
                "deadline_lower_bound_rejected", "deadline_upper_bound_rejected",
                "public_lease_route_validated")
    if any(result.get(key) is not True for key in required):
        raise ValueError("SCENARIO_CONTRACT_DRY_RUN_INCOMPLETE")
    if ((scenario["operation"] is not None and result.get("operation") != scenario["operation"])
            or not isinstance(result.get("request_digest"), str)
            or re.fullmatch(r"sha256:[0-9a-f]{64}", result["request_digest"]) is None):
        raise ValueError("SCENARIO_CONTRACT_DRY_RUN_INVALID")
    return result


def _output_for(name: str, args: argparse.Namespace, index: int = 0) -> Path:
    scenario = _scenario(name)
    run_ids = getattr(args, "run_ids", None) or []
    run_id = args.run_id if index == 0 and args.run_id else (
        run_ids[index] if index < len(run_ids) else None)
    if not run_id:
        raise ValueError("SCENARIO_RUN_ID_REQUIRED")
    if scenario["kind"] == "cross-app":
        pattern = r"gt07-cross-app-[a-z0-9-]{1,64}"
    elif "run_prefix" in scenario:
        pattern = re.escape(scenario["run_prefix"]) + r"-[0-9]{8}-[0-9]{2}"
    elif scenario["kind"] == "adversary":
        pattern = r"gt06-gt07-m9-playmutation-[0-9]{8}-[0-9]{2}"
    else:
        pattern = (r"gt07-native-godot-[0-9]{8}-[0-9]{2}" if scenario["kind"] == "godot"
                   else r"gt07-native-queue-[0-9]{8}-[0-9]{2}")
    if not re.fullmatch(pattern, run_id):
        raise ValueError("SCENARIO_RUN_ID_INVALID")
    output_root = Path(args.output_root).expanduser().absolute()
    fixed_root = (STUDIO / ".local" / "reviews").resolve()
    if output_root != fixed_root:
        raise ValueError("SCENARIO_OUTPUT_ROOT_FORBIDDEN")
    # Validate parents before resolve so a symlink cannot disappear from view.
    output = output_root / run_id
    plain(output)
    if output.exists():
        raise ValueError("SCENARIO_OUTPUT_ALREADY_EXISTS")
    # Old diagnostics are immutable and their identifiers cannot be reused
    # merely because the new output root is different.
    if (STUDIO.parent / "zdoc/reviews" / run_id).exists():
        raise ValueError("SCENARIO_RUN_ID_ALREADY_USED")
    return output


def dry_run(name: str, args: argparse.Namespace, index: int = 0) -> dict[str, object]:
    scenario = _scenario(name)
    output = _output_for(name, args, index)
    if scenario["kind"] in ("fifo", "cross-app", "adversary"):
        return _adapter_admission(name, scenario, args, index, output)
    if scenario["kind"] == "host-test":
        source_hashes = _host_test_sources(scenario)
        report = {"schema": "gt07-host-test-admission-1", "authority": 0,
                  "diagnostic_only": True, "run_id": output.name,
                  "matrix": scenario["matrix"], "tests": list(scenario["tests"]),
                  "source_hashes": source_hashes, "dry_run": True,
                  "engine_started": False}
        output.mkdir(parents=True)
        _write_json(output / "dry-run.json", report)
        return {"scenario": name, "kind": "host-test", "run_id": output.name,
                "output": str(output), "tests": list(scenario["tests"]),
                "source_hashes": source_hashes, "engine_started": False,
                "dry_run": True}
    if scenario["kind"] == "host":
        probe = _load_probe(scenario["probe"])
        report = probe.run_diagnostic(Path(args.output_root), output.name, dry_run=True)
        if report.get("dry_run") is not True or report.get("engine_started") is not False:
            raise ValueError("HOST_DRY_RUN_INVALID")
        return {"scenario": name, "kind": "host", "run_id": output.name,
                "output": str(output), "probe": scenario["probe"],
                "host_report": report, "source_hashes": report.get("source_hashes"),
                "engine_started": False, "dry_run": True}
    phase = scenario.get("phase", getattr(args, "failpoint_phase", None))
    if phase is not None and phase not in scenario.get("failpoint_phases", ()):
        raise ValueError("FAILPOINT_UNSUPPORTED_SCENARIO")
    assert_disabled(STUDIO)
    assert_disabled(runtime_root(STUDIO))
    contract = _contract_dry_run(name, scenario)
    binary = _binary_for(scenario, args)
    # Dry-run must inspect the same lock that native execution will require;
    # otherwise a later caller could silently bypass the admission boundary.
    lock = _check_lock(args.measure_lock, native=True)
    closure = _closure(scenario)
    # The probe has a 90s public lease; operation horizons must stay within the
    # catalog's two explicit bounds.  No engine is imported or launched here.
    horizon = scenario["max_horizon_ms"]
    if horizon not in (5_000, 30_000, 90_000):
        raise ValueError("SCENARIO_DEADLINE_PROFILE_INVALID")
    return {"scenario": name, "kind": scenario["kind"], "run_id": output.name,
            "output": str(output), "failpoint_phase": phase,
            "operation": scenario["operation"], "probe": scenario["probe"],
            "binary": str(binary), "binary_sha256": _sha(binary),
            "source_closure_sha256": closure, "deadline_ms": horizon,
            "measure_lock": lock, "contract": contract,
            "engine_started": False, "dry_run": True}


def _run_one(name: str, args: argparse.Namespace, index: int = 0,
             admission: dict | None = None) -> dict[str, object]:
    scenario = _scenario(name)
    check = admission if admission is not None else dry_run(name, args, index)
    if scenario["kind"] in ("fifo", "cross-app", "adversary"):
        result = _run_adapter(scenario, check)
        return {**result, "scenario": name, "run_id": check["run_id"],
                "dry_run": check, "output": check["output"]}
    if scenario["kind"] == "host-test":
        if check["source_hashes"] != _host_test_sources(scenario):
            raise ValueError("HOST_TEST_SOURCE_CHANGED")
        command = [sys.executable, "-B", "-m", "unittest", "-q", *scenario["tests"]]
        runner = _load_probe("../../build/bootstrap/run_fixture.py")
        with _native_measure_guard():
            environment = dict(os.environ)
            environment.update(scenario.get("environment", {}))
            host = runner.run_process(command, cwd=STUDIO.parent, output=Path(check["output"]),
                                      timeout=600, label="host-tests", env=environment)
        unchanged = check["source_hashes"] == _host_test_sources(scenario)
        verified = (host.get("exit_code") == host.get("wrapper_exit_code") == 0
                    and host.get("tree_verified") is True and not host.get("timed_out")
                    and unchanged)
        report = {"schema": "gt07-host-test-result-1", "authority": 0,
                  "diagnostic_only": True, "run_id": check["run_id"],
                  "matrix": scenario["matrix"], "tests": list(scenario["tests"]),
                  "source_hashes": check["source_hashes"], "source_unchanged": unchanged,
                  "actual_exit": host.get("exit_code"), "host": host,
                  "command": command, "verified": verified}
        _write_json(Path(check["output"]) / "result.json", report)
        return {"scenario": name, "run_id": check["run_id"],
                "exit_code": 0 if verified else 1, "dry_run": check,
                "host_test_report": report, "output": str(check["output"])}
    if scenario["kind"] == "host":
        probe = _load_probe(scenario["probe"])
        if scenario.get("owns_measure_guard"):
            report = probe.run_diagnostic(Path(args.output_root), check["run_id"], dry_run=False)
        else:
            with _native_measure_guard():
                report = probe.run_diagnostic(Path(args.output_root), check["run_id"], dry_run=False)
        return {"scenario": name, "run_id": check["run_id"],
                "exit_code": 0 if report.get("verified") is True else 1,
                "dry_run": check, "host_report": report,
                "output": str(check["output"])}
    # The whole matrix was admitted before row 0. Recheck frozen facts without
    # creating a second admission or taking a fresh source generation per row.
    output = Path(check["output"])
    probe = _load_probe(scenario["probe"])
    binary = Path(check["binary"])
    with _native_measure_guard():
        assert_disabled(STUDIO)
        assert_disabled(runtime_root(STUDIO))
        _validate_admitted_row(name, args, index, check)
        if _closure(scenario) != check["source_closure_sha256"]:
            raise ValueError("SCENARIO_SOURCE_CHANGED_AFTER_DRY_RUN")
        if _sha(binary) != check["binary_sha256"]:
            raise ValueError("SCENARIO_BINARY_CHANGED_AFTER_DRY_RUN")
        if scenario["kind"] == "blender":
            exit_code = probe.run(output, binary, output.name, scenario["operation"],
                                  check.get("failpoint_phase"),
                                  bool(scenario.get("authority_cases")))
        else:
            exit_code = probe.run(output, binary, output.name, scenario["operation"],
                                  bool(scenario.get("recover_after_loss")),
                                  check.get("failpoint_phase"),
                                  bool(scenario.get("manual_conflict")),
                                  file_lock=bool(scenario.get("file_lock")),
                                  authority_cases=bool(scenario.get("authority_cases")))
    return {"scenario": name, "run_id": output.name, "exit_code": exit_code,
            "dry_run": check, "output": str(output)}


def matrix_closure(results: list[dict[str, object]]) -> str:
    """Bind every admitted row into one immutable matrix-level closure.

    Godot and Blender intentionally have different per-probe dependency
    closures.  Hashing their ordered admissions together prevents the old
    mistake of presenting receipts from unrelated runs as one frozen package,
    while retaining each row's own closure for native readback.
    """
    rows = []
    for result in results:
        candidate = result.get("dry_run")
        dry = candidate if isinstance(candidate, dict) else result
        rows.append({key: dry.get(key) for key in (
            "scenario", "run_id", "source_closure_sha256", "binary_sha256",
            "operation", "deadline_ms", "source_hashes", "failpoint_phase",
            "producer_run_id", "driver_sha256", "tests", "kind", "contract",
            "matrix_source_closure_sha256")})
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--scenario", choices=tuple(SCENARIOS))
    selection.add_argument("--matrix", help="comma-separated scenario names")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--godot-binary", type=Path)
    parser.add_argument("--blender-binary", type=Path)
    parser.add_argument("--measure-lock", type=Path)
    parser.add_argument("--output-root", type=Path,
                        default=STUDIO / ".local" / "reviews")
    parser.add_argument("--run-id")
    parser.add_argument("--run-ids", help="comma-separated fresh IDs for --matrix")
    parser.add_argument("--failpoint-phase", choices=("PREPARED", "VALIDATED", "ACTIVATING",
                                                        "COMMITTED", "RELOAD", "ACK"))
    args = parser.parse_args(argv)
    matrix_text = args.matrix.strip() if args.matrix else None
    names = (MATRIX_ALIASES[matrix_text] if matrix_text in MATRIX_ALIASES else
             [value.strip() for value in matrix_text.split(",") if value.strip()]
             if matrix_text else ([args.scenario] if args.scenario else []))
    args.matrix_names = tuple(names)
    if not names or any(value not in ALL_SCENARIOS for value in names):
        parser.error("one --scenario or a valid --matrix is required")
    args.run_ids = ([value.strip() for value in args.run_ids.split(",") if value.strip()]
                    if args.run_ids else [])
    if args.matrix and (args.run_id or len(args.run_ids) != len(names)
                        or len(set(args.run_ids)) != len(args.run_ids)):
        parser.error("--matrix requires one distinct --run-ids entry per scenario")
    if args.matrix and args.failpoint_phase:
        parser.error("--failpoint-phase requires one scenario")
    if not args.matrix and (args.run_id is None or args.run_ids):
        parser.error("one --run-id is required, also for --dry-run")
    if not args.matrix:
        # A single scenario still uses the same durable admission and source
        # checks as a matrix, including its one-use coordinator directory.
        args.run_ids = [args.run_id]
    matrix_source_digest = _source_digest(_matrix_sources())
    # Check every intended output before starting the first engine in a matrix.
    matrix_root = None
    try:
        for index, name in enumerate(names):
            _output_for(name, args, index)
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"native": False, "error": str(error)}, sort_keys=True))
        return 2
    if args.dry_run:
        results = []
        try:
            for index, name in enumerate(names):
                if args.matrix and matrix_source_digest != _source_digest(_matrix_sources()):
                    raise ValueError("MATRIX_SOURCE_CHANGED_DURING_DRY_RUN")
                row = dry_run(name, args, index)
                row["matrix_source_closure_sha256"] = matrix_source_digest
                results.append(row)
        except (OSError, ValueError, RuntimeError) as error:
            print(json.dumps({"dry_run": False, "error": str(error)}, sort_keys=True))
            return 2
        print(json.dumps({"dry_run": True, "matrix_source_closure_sha256": matrix_source_digest,
                          "matrix_closure_sha256": matrix_closure(results),
                          "results": results}, sort_keys=True))
        return 0
    try:
        # F3 admission is one atomic preflight.  Passing each saved receipt to
        # _run_one prevents a later row from silently taking a new source
        # generation or turning a lost native handle into a fresh retry.
        matrix_root, admissions, admitted_closure = _admit_matrix(
            args, names, matrix_source_digest)
        manifest_path = matrix_root / "manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["state"] = "RUNNING"
        _atomic_json(manifest_path, manifest)
        _append_event(matrix_root, {"event": "MATRIX_NATIVE_STARTED",
                                    "matrix_closure_sha256": admitted_closure})
        results = []
        for index, (name, admission) in enumerate(zip(names, admissions)):
            if matrix_source_digest != _source_digest(_matrix_sources()):
                raise ValueError("MATRIX_SOURCE_CHANGED_BEFORE_NATIVE_ROW")
            _append_event(matrix_root, {"event": "ROW_STARTED", "index": index,
                                        "scenario": name, "run_id": admission["run_id"]})
            try:
                result = _run_one(name, args, index, admission=admission)
            except (OSError, ValueError, RuntimeError) as error:
                # The row may have launched a child before the Python wrapper
                # lost its receipt.  Preserve UNKNOWN rather than retrying it.
                result = {"scenario": name, "run_id": admission["run_id"],
                          "output": admission["output"], "exit_code": None,
                          "error": str(error), "status": "UNKNOWN",
                          "failure_boundary": failure_boundary(error),
                          "dry_run": admission}
            result["matrix_source_closure_sha256"] = matrix_source_digest
            results.append(result)
            terminal = _terminal_summary(result, admission, index)
            _write_json(matrix_root / f"row-{index:02d}-terminal.json", terminal)
            _append_event(matrix_root, {"event": "ROW_TERMINAL", **terminal})
            manifest = json.loads(manifest_path.read_bytes())
            manifest["rows"][index] = {"index": index, "scenario": name,
                                       "run_id": admission["run_id"],
                                       "status": "PASS" if result.get("exit_code") == 0 else
                                                 ("UNKNOWN" if result.get("exit_code") is None else "FAIL"),
                                       "terminal": terminal}
            _atomic_json(manifest_path, manifest)
            if result.get("exit_code") != 0:
                manifest["state"] = "INCOMPLETE" if result.get("exit_code") is None else "FAILED"
                _atomic_json(manifest_path, manifest)
                _append_event(matrix_root, {"event": "MATRIX_STOPPED_AFTER_ROW",
                                            "index": index, "status": manifest["state"]})
                print(json.dumps({"native": False, "matrix_manifest": str(manifest_path),
                                  "results": [_terminal_summary(item, admissions[i], i)
                                               for i, item in enumerate(results)],
                                  "error": "SCENARIO_MATRIX_STOP_AFTER_FAILURE"},
                                 sort_keys=True))
                return 1
        if matrix_source_digest != _source_digest(_matrix_sources()):
            raise ValueError("MATRIX_SOURCE_CHANGED_AFTER_NATIVE")
        manifest = json.loads(manifest_path.read_bytes())
        manifest["state"] = "COMPLETE"
        manifest["final_matrix_closure_sha256"] = matrix_closure(results)
        _atomic_json(manifest_path, manifest)
        _append_event(matrix_root, {"event": "MATRIX_COMPLETE",
                                    "matrix_closure_sha256": manifest["final_matrix_closure_sha256"]})
    except BaseException as error:
        if matrix_root is not None:
            manifest_path = matrix_root / "manifest.json"
            if manifest_path.is_file():
                manifest = json.loads(manifest_path.read_bytes())
                manifest["state"] = "INTERRUPTED"
                manifest["error"] = str(error)
                _atomic_json(manifest_path, manifest)
                _append_event(matrix_root, {"event": "MATRIX_INTERRUPTED",
                                            "error": str(error)})
        print(json.dumps({"native": False, "error": str(error)}, sort_keys=True))
        return 2
    if args.matrix and matrix_source_digest != _source_digest(_matrix_sources()):
        print(json.dumps({"native": False, "error": "MATRIX_SOURCE_CHANGED_AFTER_NATIVE"}, sort_keys=True))
        return 2
    print(json.dumps({"native": True, "matrix_source_closure_sha256": matrix_source_digest,
                      "matrix_manifest": str(manifest_path),
                      "matrix_closure_sha256": matrix_closure(results),
                      "results": results}, sort_keys=True))
    return 0 if all(item["exit_code"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
