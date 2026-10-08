"""Fail-closed verifier for registered GT-09 K5/K7 failure evidence.

The existing K5 and K7 probes exercise the private gameplay-source owner, while
the registered authoring owner currently admits only scene/node/resource
operations.  This module is the boundary between those two routes.  It binds a
future registered receipt to the current profile and source closure, validates
the independently captured host/container exit fields, and leaves the rows
OPEN until a native registered route is actually observed.

It intentionally never starts Godot, Docker, Blender, MCP, or a subprocess.
The JSON validators are useful to a native worker or a coordinator, but a
synthetic unit-test dictionary cannot become native evidence merely by setting
``status`` or ``native_observed``.  A receipt must contain the complete
postconditions and be read from an evidence file under the supplied review
root; reports remain authority-zero diagnostic summaries.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping


STUDIO = Path(__file__).resolve().parents[2]
REGISTERED_OWNER = STUDIO / "godot-addon" / "registered_authoring_owner.py"
FIXTURES = STUDIO / "tests" / "godot" / "linux_probe_fixtures.py"
FAILURE_RUNNER = STUDIO / "tests" / "godot" / "run_gameplay_failure_probe.py"
PROBE = STUDIO / "tests" / "godot" / "run_linux_probe.py"
THIS_FILE = Path(__file__).resolve()

SCHEMA = "hh-gt09-registered-failures-1"
RECEIPT_SCHEMA = "hh-gt09-registered-failure-evidence-1"
AUTHORITY = 0
K5_CASES = ("syntax", "type", "timeout", "stop")
K7_CASES = ("spawn", "boundary", "busy", "wall")
K7_MARKERS = {
    "spawn": "spawn",
    "boundary": "source_write",
    "busy": "watchdog_loop",
    "wall": "watchdog_loop",
}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_PROFILE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RUN_ID = re.compile(r"[A-Za-z0-9._-]{1,96}\Z")

# Keep the closure explicit.  This is the source consumed by this verifier and
# the registered/gameplay paths it binds; callers cannot supply this list.
SOURCE_FILES = (FIXTURES, REGISTERED_OWNER, FAILURE_RUNNER, PROBE, THIS_FILE)


class RegisteredFailureError(ValueError):
    """A malformed or unbound registered failure receipt."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _need(condition: object, code: str) -> None:
    if not condition:
        raise RegisteredFailureError(code)


def _dict(value: Any) -> dict[str, Any]:
    return value if type(value) is dict else {}


def _profile_module():
    # Importing the owner is a read-only registration operation.  It does not
    # acquire a lease, open a process, or enable the public profile.
    name = "hh_gt09_registered_failure_owner_" + _sha(REGISTERED_OWNER)
    module = sys.modules.get(name)
    if module is None:
        spec = importlib.util.spec_from_file_location(name, REGISTERED_OWNER)
        if spec is None or spec.loader is None:
            raise RegisteredFailureError("REGISTERED_OWNER_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return module


def registered_profile() -> dict[str, Any]:
    """Return the pinned private registered profile descriptor."""
    try:
        value = _profile_module().register_profile().as_dict()
    except RegisteredFailureError:
        raise
    except Exception as exc:  # preserve a stable verifier error for callers
        raise RegisteredFailureError("REGISTERED_PROFILE_IMPORT") from exc
    _need(type(value) is dict, "REGISTERED_PROFILE_SHAPE")
    _need(value.get("authority") == AUTHORITY, "REGISTERED_PROFILE_AUTHORITY")
    _need(type(value.get("profile")) is str and value["profile"], "REGISTERED_PROFILE_ID")
    _need(_PROFILE_DIGEST.fullmatch(str(value.get("catalog_digest", ""))) is not None,
          "REGISTERED_PROFILE_DIGEST")
    _need(type(value.get("operations")) is list and all(type(item) is str for item in value["operations"]),
          "REGISTERED_PROFILE_OPERATIONS")
    return value


def source_binding() -> dict[str, Any]:
    """Hash the complete local closure used by this diagnostic verifier."""
    files: dict[str, str] = {}
    for path in SOURCE_FILES:
        _need(path.is_file(), "REGISTERED_FAILURE_SOURCE_MISSING:" + path.name)
        files[path.relative_to(STUDIO).as_posix()] = _sha(path)
    raw = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"source_files": files,
            "source_closure_sha256": hashlib.sha256(raw).hexdigest()}


def verify_hostile_markers() -> dict[str, Any]:
    """Check that each hostile marker is adjacent to the operation it guards.

    This is a source contract only.  ``native_observed`` is deliberately absent
    from the returned rows; callers must supply a separate native receipt.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "hh_gt09_registered_failure_fixtures", FIXTURES)
        if spec is None or spec.loader is None:
            raise RegisteredFailureError("FIXTURE_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        fixtures = module.FIXTURES
    except RegisteredFailureError:
        raise
    except Exception as exc:
        raise RegisteredFailureError("FIXTURE_IMPORT") from exc

    contracts = {
        "gameplay_source_spawn": (("spawn", "OS.execute"),),
        "gameplay_source_boundary": (
            ("source_write", 'FileAccess.open("res://scripts/fixture_actor.gd", FileAccess.WRITE)'),
            ("root_write", 'FileAccess.open("/escape-at-root", FileAccess.WRITE)'),
            ("docker_socket", 'FileAccess.file_exists("/var/run/docker.sock")'),
            ("network_connect", "network.connect_to_host"),
        ),
        "gameplay_source_busy": (("watchdog_loop", "while true:"),),
        "gameplay_source_wall_wait": (("watchdog_loop", "while true:"),),
    }
    rows: list[dict[str, Any]] = []
    for fixture, checks in contracts.items():
        case = fixtures.get(fixture)
        _need(type(case) is dict and type(case.get("script")) is str,
              "HOSTILE_FIXTURE_MISSING:" + fixture)
        lines = case["script"].splitlines()
        for marker_name, behaviour in checks:
            marker = "HH_HOSTILE_BEHAVIOR_BEGIN " + marker_name
            marker_lines = [index for index, line in enumerate(lines) if marker in line]
            behaviour_lines = [index for index, line in enumerate(lines) if behaviour in line]
            _need(len(marker_lines) == 1, "HOSTILE_MARKER_COUNT:" + fixture + ":" + marker_name)
            _need(len(behaviour_lines) == 1, "HOSTILE_BEHAVIOUR_COUNT:" + fixture + ":" + marker_name)
            _need(behaviour_lines[0] == marker_lines[0] + 1,
                  "HOSTILE_MARKER_NOT_ADJACENT:" + fixture + ":" + marker_name)
            rows.append({"fixture": fixture, "marker": marker,
                         "marker_line": marker_lines[0] + 1,
                         "behaviour": behaviour, "behaviour_line": behaviour_lines[0] + 1})
    return {"verified": True, "rows": rows, "native_observed": False}


def _expected_profile(profile: Mapping[str, Any] | None) -> dict[str, Any]:
    value = dict(profile) if profile is not None else registered_profile()
    _need(value.get("authority") == AUTHORITY, "RECEIPT_PROFILE_AUTHORITY")
    _need(type(value.get("profile")) is str and value["profile"], "RECEIPT_PROFILE_ID")
    _need(_PROFILE_DIGEST.fullmatch(str(value.get("catalog_digest", ""))) is not None,
          "RECEIPT_PROFILE_DIGEST")
    return value


def _verify_common(receipt: Mapping[str, Any], *, profile: Mapping[str, Any] | None,
                   source_closure: str | None, kind: str) -> list[str]:
    errors: list[str] = []
    value = dict(receipt)
    expected = _expected_profile(profile)

    def check(condition: object, code: str) -> None:
        if not condition:
            errors.append(code)

    check(value.get("schema") == RECEIPT_SCHEMA, "RECEIPT_SCHEMA")
    check(value.get("kind") == kind, "RECEIPT_KIND")
    check(type(value.get("run_id")) is str and _RUN_ID.fullmatch(value["run_id"]) is not None,
          "RECEIPT_RUN_ID")
    closure = value.get("source_closure_sha256")
    check(type(closure) is str and _HEX64.fullmatch(closure) is not None,
          "RECEIPT_SOURCE_CLOSURE")
    if source_closure is not None:
        check(closure == source_closure, "RECEIPT_SOURCE_CLOSURE_MISMATCH")
    check(value.get("authority") == AUTHORITY and value.get("public_ack") is False,
          "RECEIPT_AUTHORITY")
    check(value.get("registered_profile") == expected.get("profile"), "RECEIPT_PROFILE")
    check(value.get("profile_catalog_digest") == expected.get("catalog_digest"),
          "RECEIPT_PROFILE_DIGEST_MISMATCH")
    discovery = _dict(value.get("registered_discovery"))
    discovered = _dict(discovery.get("profile"))
    check(discovery.get("fixture_enabled") is True
          and discovery.get("public_runtime_enabled") is False
          and discovery.get("authority") == AUTHORITY
          and discovery.get("public_ack") is False, "RECEIPT_DISCOVERY")
    check(discovered.get("profile") == expected.get("profile")
          and discovered.get("catalog_digest") == expected.get("catalog_digest"),
          "RECEIPT_DISCOVERY_PROFILE")
    # A profile descriptor with no script route cannot claim a registered
    # gameplay failure.  This is the current upstream state and keeps reports
    # OPEN until a separately reviewed route is enabled.
    operations = expected.get("operations", [])
    check(expected.get("script_enabled") is True or "script.create" in operations,
          "REGISTERED_SCRIPT_ROUTE_DISABLED")
    check(value.get("native_observed") is True, "RECEIPT_NATIVE_OBSERVATION")
    check(value.get("evidence_origin") == "registered-native", "RECEIPT_EVIDENCE_ORIGIN")
    return errors


def _verify_exit(value: Mapping[str, Any], errors: list[str], *, timeout_allowed: bool = False) -> None:
    process = _dict(value.get("process"))
    host_exit = process.get("host_exit")
    container_exit = process.get("container_exit")
    timed_out = process.get("timed_out")
    # A result's convenience fields are not the process receipt.  The native
    # host must write this independently captured envelope and bind its
    # canonical hash into the result before a registered row can be measured.
    exit_receipt = _dict(process.get("exit_receipt"))
    if exit_receipt.get("schema") != "hh-process-exit-1":
        errors.append("PROCESS_EXIT_RECEIPT_SCHEMA")
    if type(exit_receipt.get("actual_exit")) is not int:
        errors.append("PROCESS_EXIT_RECEIPT_EXIT")
    if type(exit_receipt.get("timed_out")) is not bool:
        errors.append("PROCESS_EXIT_RECEIPT_TIMEOUT")
    if exit_receipt.get("owned_tree_zero") is not True:
        errors.append("PROCESS_EXIT_RECEIPT_TREE")
    encoded = json.dumps(exit_receipt, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    expected_hash = hashlib.sha256(encoded).hexdigest()
    if process.get("exit_receipt_sha256") != expected_hash:
        errors.append("PROCESS_EXIT_RECEIPT_HASH")
    if type(host_exit) is not int:
        errors.append("PROCESS_HOST_EXIT")
    if type(container_exit) is not int:
        errors.append("PROCESS_CONTAINER_EXIT")
    if type(host_exit) is int and type(container_exit) is int and host_exit != container_exit:
        errors.append("PROCESS_EXIT_MISMATCH")
    if (type(host_exit) is int and type(exit_receipt.get("actual_exit")) is int
            and host_exit != exit_receipt["actual_exit"]):
        errors.append("PROCESS_EXIT_RECEIPT_MISMATCH")
    if type(timed_out) is not bool:
        errors.append("PROCESS_TIMEOUT")
    elif timed_out and not timeout_allowed:
        errors.append("PROCESS_UNEXPECTED_TIMEOUT")
    if (type(timed_out) is bool and type(exit_receipt.get("timed_out")) is bool
            and timed_out != exit_receipt["timed_out"]):
        errors.append("PROCESS_TIMEOUT_RECEIPT_MISMATCH")
    if process.get("stream_cap_exceeded") is not False:
        errors.append("PROCESS_STREAM_CAP")
    if process.get("owned_tree_zero") is not True:
        errors.append("PROCESS_TREE_NOT_EMPTY")


def verify_k5_receipt(receipt: Mapping[str, Any], *, expected_case: str | None = None,
                      profile: Mapping[str, Any] | None = None,
                      source_closure: str | None = None) -> dict[str, Any]:
    """Validate one registered K5 failure receipt without launching a worker."""
    errors = _verify_common(receipt, profile=profile, source_closure=source_closure,
                            kind="k5-failure")
    fixture = receipt.get("failure_case")
    if fixture not in K5_CASES:
        errors.append("K5_FAILURE_CASE")
    if expected_case is not None and fixture != expected_case:
        errors.append("K5_FAILURE_CASE_MISMATCH")
    failure = _dict(receipt.get("failure"))
    if failure.get("observed") is not True:
        errors.append("K5_FAILURE_NOT_OBSERVED")
    if failure.get("last_good_preserved") is not True:
        errors.append("K5_LAST_GOOD_CHANGED")
    if failure.get("reopen_readback_equal") is not True:
        errors.append("K5_REOPEN_READBACK")
    if failure.get("retry_equal") is not True:
        errors.append("K5_RETRY_EQUAL")
    if failure.get("retry_no_redispatch") is not True:
        errors.append("K5_RETRY_REDISPATCH")
    if failure.get("exit_preserved") is not True:
        errors.append("K5_EXIT_NOT_PRESERVED")
    _verify_exit(receipt, errors, timeout_allowed=fixture == "timeout")
    process = _dict(receipt.get("process"))
    if fixture in ("syntax", "type") and type(process.get("host_exit")) is int:
        if process["host_exit"] == 0:
            errors.append("K5_REJECTION_EXIT_ZERO")
        if process.get("timed_out") is True:
            errors.append("K5_PARSE_TIMEOUT")
    if fixture == "timeout" and process.get("timed_out") is not True:
        errors.append("K5_TIMEOUT_NOT_OBSERVED")
    if fixture == "stop" and failure.get("stop_observed") is not True:
        errors.append("K5_STOP_NOT_OBSERVED")
    return {
        "kind": "K5",
        "failure_case": fixture,
        "valid": not errors,
        "status": "MEASURED_DIAGNOSTIC" if not errors else "OPEN",
        "native_observed": receipt.get("native_observed") is True and not errors,
        "errors": errors,
    }


def verify_k7_receipt(receipt: Mapping[str, Any], *, expected_case: str | None = None,
                      profile: Mapping[str, Any] | None = None,
                      source_closure: str | None = None) -> dict[str, Any]:
    """Validate one registered K7 hostile-executor receipt.

    Marker source checks and runtime marker observations are separate.  A static
    marker list, child banner, or claimed exit code is insufficient by itself.
    """
    errors = _verify_common(receipt, profile=profile, source_closure=source_closure,
                            kind="k7-hostile")
    fixture = receipt.get("hostile_case")
    if fixture not in K7_CASES:
        errors.append("K7_HOSTILE_CASE")
    if expected_case is not None and fixture != expected_case:
        errors.append("K7_HOSTILE_CASE_MISMATCH")
    marker = _dict(receipt.get("marker_observation"))
    expected_marker = K7_MARKERS.get(fixture)
    if marker.get("name") != expected_marker or marker.get("count") != 1:
        errors.append("K7_MARKER_NOT_OBSERVED")
    if marker.get("source_bound") is not True:
        errors.append("K7_MARKER_SOURCE_UNBOUND")
    sandbox = _dict(receipt.get("sandbox"))
    if fixture == "spawn":
        if sandbox.get("child_spawn_denied") is not True:
            errors.append("K7_SPAWN_NOT_DENIED")
        if sandbox.get("unexpected_child_output") is not False:
            errors.append("K7_UNEXPECTED_CHILD")
    elif fixture == "boundary":
        for key in ("source_write_denied", "root_write_denied", "docker_socket_absent", "network_denied"):
            if sandbox.get(key) is not True:
                errors.append("K7_BOUNDARY_" + key.upper())
    elif fixture in ("busy", "wall"):
        if sandbox.get("watchdog_entered") is not True:
            errors.append("K7_WATCHDOG_NOT_ENTERED")
        if sandbox.get("watchdog_terminated") is not True:
            errors.append("K7_WATCHDOG_NOT_TERMINATED")
    if sandbox.get("acceptance") is not False:
        errors.append("K7_SANDBOX_ACCEPTANCE")
    _verify_exit(receipt, errors, timeout_allowed=fixture in ("busy", "wall"))
    return {
        "kind": "K7",
        "hostile_case": fixture,
        "valid": not errors,
        "status": "MEASURED_DIAGNOSTIC" if not errors else "OPEN",
        "native_observed": receipt.get("native_observed") is True and not errors,
        "errors": errors,
    }


def verify_registered_receipt(receipt: Mapping[str, Any], *, profile: Mapping[str, Any] | None = None,
                              source_closure: str | None = None) -> dict[str, Any]:
    """Dispatch a receipt to the K5/K7 validator and never raise on bad input."""
    try:
        if type(receipt) is not dict:
            raise RegisteredFailureError("RECEIPT_SHAPE")
        kind = receipt.get("kind")
        if kind == "k5-failure":
            return verify_k5_receipt(receipt, profile=profile, source_closure=source_closure)
        if kind == "k7-hostile":
            return verify_k7_receipt(receipt, profile=profile, source_closure=source_closure)
        raise RegisteredFailureError("RECEIPT_KIND")
    except (RegisteredFailureError, TypeError, AttributeError) as exc:
        return {"kind": "UNKNOWN", "valid": False, "status": "OPEN",
                "native_observed": False, "errors": [str(exc)]}


def _safe_evidence_file(path: Path, *, root: Path) -> Path:
    resolved = path.resolve()
    root = root.resolve()
    _need(resolved.is_relative_to(root), "EVIDENCE_OUTSIDE_ROOT")
    _need(resolved.is_file(), "EVIDENCE_MISSING")
    return resolved


def _iter_receipts(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return ()
    # Only these explicit names are accepted.  Existing gameplay-source result
    # files are never silently reinterpreted as registered evidence.
    names = ("registered-k5-result.json", "registered-k7-result.json", "result.json")
    paths: list[Path] = []
    for path in root.rglob("*.json"):
        if path.name not in names:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and value.get("kind") in {"k5-failure", "k7-hostile"}:
            paths.append(path)
    return tuple(sorted(paths))


def _collect(root: Path, *, profile: Mapping[str, Any], closure: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _iter_receipts(root):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            result = verify_registered_receipt(value, profile=profile, source_closure=closure)
            result.update({"path": path.relative_to(root).as_posix(),
                           "sha256": _sha(path), "run_id": value.get("run_id")})
            rows.append(result)
        except (OSError, ValueError, TypeError) as exc:
            rows.append({"kind": "UNKNOWN", "path": path.relative_to(root).as_posix(),
                         "valid": False, "status": "OPEN", "native_observed": False,
                         "errors": ["RECEIPT_READ:" + type(exc).__name__]})
    return rows


def _matrix(rows: list[dict[str, Any]], kind: str, cases: tuple[str, ...]) -> dict[str, Any]:
    selected: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    field = "failure_case" if kind == "K5" else "hostile_case"
    for row in rows:
        if row.get("kind") != kind:
            continue
        case = row.get(field)
        if type(case) is not str:
            continue
        if case in selected:
            duplicates.add(str(case))
        else:
            selected[case] = row
    complete = all(case in selected and selected[case].get("valid") is True for case in cases)
    if duplicates:
        complete = False
    result = {"status": "MEASURED_DIAGNOSTIC" if complete else "OPEN",
            "cases": {case: selected.get(case, {"status": "OPEN", "errors": ["EVIDENCE_MISSING"]})
                      for case in cases},
            "complete": complete}
    if duplicates:
        result["duplicate_cases"] = sorted(duplicates)
    return result


def build_report(*, evidence_root: Path | None = None) -> dict[str, Any]:
    """Build the parent-callable K5/K7 scenario report without native launch."""
    errors: list[str] = []
    try:
        profile = registered_profile()
    except RegisteredFailureError as exc:
        # A broken registration import is itself an OPEN gap.  Preserve a
        # shape-stable report so a coordinator can record the failure without
        # turning a verifier exception into an accidental PASS.
        errors.append(str(exc))
        profile = {"schema": "unavailable", "profile": None, "catalog_digest": None,
                   "operations": [], "status": "UNAVAILABLE", "authority": AUTHORITY,
                   "runtime_enabled": False, "script_enabled": False, "version": None}
    try:
        binding = source_binding()
    except RegisteredFailureError as exc:
        errors.append(str(exc))
        binding = {"source_files": {}, "source_closure_sha256": None}
    try:
        markers = verify_hostile_markers()
    except RegisteredFailureError as exc:
        errors.append(str(exc))
        markers = {"verified": False, "rows": [], "native_observed": False}
    root = (evidence_root or STUDIO / ".local" / "reviews").resolve()
    evidence = _collect(root, profile=profile, closure=binding["source_closure_sha256"])
    k5 = _matrix(evidence, "K5", K5_CASES)
    k7 = _matrix(evidence, "K7", K7_CASES)
    # The current profile is intentionally private and scriptless; even a
    # complete candidate receipt remains a measured diagnostic until that
    # registered route is enabled and reviewed upstream.
    route_enabled = profile.get("script_enabled") is True or "script.create" in profile.get("operations", [])
    if not route_enabled:
        k5["status"] = k7["status"] = "OPEN"
        k5["route_reason"] = k7["route_reason"] = "REGISTERED_SCRIPT_ROUTE_DISABLED"
    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "public_ack": False,
        "acceptance": False,
        "diagnostic_only": True,
        "package_ready": False,
        "registered_profile": profile,
        "registered_route_enabled": route_enabled,
        "source_files": binding["source_files"],
        "source_closure_sha256": binding["source_closure_sha256"],
        "hostile_markers": markers,
        "errors": errors,
        "k5": k5,
        "k7": k7,
        "evidence": evidence,
        "native_launch_performed": False,
        "requirements": {
            "k5": "registered syntax/type/timeout/stop receipt with independent host exit and last-good readback",
            "k7": "registered spawn/boundary/watchdog receipts with source-bound hostile markers and sandbox readback",
            "native": "OPEN until a registered script route emits native evidence",
        },
    }


def scenario_interface(*, evidence_root: Path | None = None) -> dict[str, Any]:
    """Small stable interface for a coordinator to consume this scenario."""
    return build_report(evidence_root=evidence_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, default=STUDIO / ".local" / "reviews")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="build the report without native work")
    args = parser.parse_args(argv)
    report = build_report(evidence_root=args.evidence_root.resolve())
    if args.output is not None:
        output = args.output.resolve()
        review_root = (STUDIO / ".local" / "reviews").resolve()
        if not output.is_relative_to(review_root):
            parser.error("output must be below studio/.local/reviews")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
    print(json.dumps({"schema": SCHEMA, "status": "OPEN",
                      "k5": report["k5"]["status"], "k7": report["k7"]["status"],
                      "source_closure_sha256": report["source_closure_sha256"],
                      "native_launch_performed": False, "authority": AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
