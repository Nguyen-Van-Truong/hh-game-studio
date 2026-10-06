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
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import stat

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.measure_window import default_path, plain
from studio.host.core.gt07_failpoints import assert_disabled, runtime_root

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


def _binary_for(scenario: dict, args: argparse.Namespace) -> Path:
    value = args.godot_binary if scenario["kind"] == "godot" else args.blender_binary
    if not value:
        raise ValueError("PINNED_BINARY_REQUIRED")
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError("PINNED_BINARY_MISSING")
    lock = json.loads((STUDIO / "toolchain.lock.json").read_bytes())
    expected = (lock["godot"]["gui_sha256"] if scenario["kind"] == "godot"
                else lock["blender"]["executable_sha256"])
    observed = _sha(path)
    if observed.lower() != expected.lower():
        raise ValueError("PINNED_BINARY_HASH_MISMATCH")
    return path


def _closure(scenario: dict) -> str:
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
    scenario = SCENARIOS[name]
    run_ids = getattr(args, "run_ids", None) or []
    run_id = args.run_id if index == 0 and args.run_id else (
        run_ids[index] if index < len(run_ids) else None)
    if not run_id:
        raise ValueError("SCENARIO_RUN_ID_REQUIRED")
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
    scenario = SCENARIOS[name]
    output = _output_for(name, args, index)
    phase = getattr(args, "failpoint_phase", None)
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


def _run_one(name: str, args: argparse.Namespace, index: int = 0) -> dict[str, object]:
    scenario = SCENARIOS[name]
    # Dry-run is mandatory and intentionally repeated with the exact native
    # arguments immediately before delegation.
    check = dry_run(name, args, index)
    output = Path(check["output"])
    probe = _load_probe(scenario["probe"])
    binary = Path(check["binary"])
    with _native_measure_guard():
        assert_disabled(STUDIO)
        assert_disabled(runtime_root(STUDIO))
        _output_for(name, args, index)
        if _closure(scenario) != check["source_closure_sha256"]:
            raise ValueError("SCENARIO_SOURCE_CHANGED_AFTER_DRY_RUN")
        if _sha(binary) != check["binary_sha256"]:
            raise ValueError("SCENARIO_BINARY_CHANGED_AFTER_DRY_RUN")
        if scenario["kind"] == "blender":
            exit_code = probe.run(output, binary, output.name, scenario["operation"],
                                  getattr(args, "failpoint_phase", None),
                                  bool(scenario.get("authority_cases")))
        else:
            exit_code = probe.run(output, binary, output.name, scenario["operation"],
                                  bool(scenario.get("recover_after_loss")),
                                  getattr(args, "failpoint_phase", None),
                                  bool(scenario.get("manual_conflict")),
                                  file_lock=bool(scenario.get("file_lock")),
                                  authority_cases=bool(scenario.get("authority_cases")))
    return {"scenario": name, "run_id": output.name, "exit_code": exit_code,
            "dry_run": check, "output": str(output)}


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
    names = ([value.strip() for value in args.matrix.split(",") if value.strip()]
             if args.matrix else ([args.scenario] if args.scenario else []))
    if not names or any(value not in SCENARIOS for value in names):
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
    # Check every intended output before starting the first engine in a matrix.
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
                results.append(dry_run(name, args, index))
        except (OSError, ValueError, RuntimeError) as error:
            print(json.dumps({"dry_run": False, "error": str(error)}, sort_keys=True))
            return 2
        print(json.dumps({"dry_run": True, "results": results}, sort_keys=True))
        return 0
    try:
        results = []
        for index, name in enumerate(names):
            result = _run_one(name, args, index)
            results.append(result)
            if result["exit_code"] != 0:
                print(json.dumps({"native": False, "results": results,
                                  "error": "SCENARIO_MATRIX_STOP_AFTER_FAILURE"},
                                 sort_keys=True))
                return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"native": False, "error": str(error)}, sort_keys=True))
        return 2
    print(json.dumps({"native": True, "results": results}, sort_keys=True))
    return 0 if all(item["exit_code"] == 0 for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
