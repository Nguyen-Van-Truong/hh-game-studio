"""Bounded B4 verifier for the registered GT-09 failure path.

This is intentionally a diagnostic verifier.  It does not enable the public
profile, dispatch Godot, or promote an unregistered gameplay probe to AUTH.
It freezes the relevant source hashes, checks hostile markers are adjacent to
the behaviour they guard, and reports the measured gaps in K3--K7.  Existing
raw native receipts are summarized with their host exit codes, but their
diagnostic status is preserved verbatim.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
FIXTURES = STUDIO / "tests/godot/linux_probe_fixtures.py"
REGISTERED_OWNER = STUDIO / "godot-addon/registered_authoring_owner.py"
FAILURE_RUNNER = STUDIO / "tests/godot/run_gameplay_failure_probe.py"
PUBLICATION_RUNNER = STUDIO / "tests/godot/run_gameplay_publication_probe.py"
PROBE = STUDIO / "tests/godot/run_linux_probe.py"

SOURCE_FILES = (FIXTURES, REGISTERED_OWNER, FAILURE_RUNNER, PUBLICATION_RUNNER, PROBE)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_fixtures():
    spec = importlib.util.spec_from_file_location("gt09_b4_fixtures", FIXTURES)
    if spec is None or spec.loader is None:
        raise RuntimeError("FIXTURE_IMPORT")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registered_profile() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("gt09_b4_registered_owner", REGISTERED_OWNER)
    if spec is None or spec.loader is None:
        raise RuntimeError("REGISTERED_OWNER_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.register_profile().as_dict()


def _line_number(lines: list[str], text: str) -> int:
    matches = [index for index, line in enumerate(lines) if text in line]
    if len(matches) != 1:
        raise ValueError(f"MARKER_OR_BEHAVIOUR_COUNT:{text}")
    return matches[0]


def verify_hostile_markers() -> dict[str, Any]:
    """Require each hostile marker to be immediately before its operation."""
    fixtures = _load_fixtures().FIXTURES
    contracts = {
        "gameplay_source_spawn": [("spawn", "OS.execute")],
        "gameplay_source_boundary": [
            ("source_write", "FileAccess.open(\"res://scripts/fixture_actor.gd\", FileAccess.WRITE)"),
            ("root_write", "FileAccess.open(\"/escape-at-root\", FileAccess.WRITE)"),
            ("docker_socket", "FileAccess.file_exists(\"/var/run/docker.sock\")"),
            ("network_connect", "network.connect_to_host"),
        ],
        "gameplay_source_busy": [("watchdog_loop", "while true:")],
        "gameplay_source_wall_wait": [("watchdog_loop", "while true:")],
    }
    rows = []
    for fixture, checks in contracts.items():
        lines = fixtures[fixture]["script"].splitlines()
        for marker_name, behaviour in checks:
            marker = f'HH_HOSTILE_BEHAVIOR_BEGIN {marker_name}'
            marker_line = _line_number(lines, marker)
            behaviour_line = _line_number(lines, behaviour)
            if behaviour_line != marker_line + 1:
                raise ValueError(f"HOSTILE_MARKER_NOT_ADJACENT:{fixture}:{marker_name}")
            rows.append({"fixture": fixture, "marker": marker,
                         "marker_line": marker_line + 1,
                         "behaviour": behaviour, "behaviour_line": behaviour_line + 1})
    return {"verified": True, "rows": rows}


def _raw_receipts(root: Path) -> list[dict[str, Any]]:
    """Read only existing native result receipts; never infer a pass."""
    rows = []
    if not root.is_dir():
        return rows
    for path in sorted(root.glob("o2-publication-gt09-auth05-*/**/result.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(value, dict) or value.get("schema") != "hh-gt03-linux-diagnostic-1":
            continue
        host = value.get("command_host")
        state = value.get("container_state")
        if not isinstance(host, dict) or not isinstance(state, dict):
            continue
        rows.append({"run_id": value.get("run_id"),
                     "source_run": path.parent.parent.parent.name,
                     "status": value.get("diagnostic_process_clean"),
                     "actual_exit": host.get("exit_code"),
                     "container_exit": state.get("ExitCode"),
                     "timed_out": host.get("timed_out"),
                     "source_closure_sha256": value.get("source_closure_sha256"),
                     "raw_result": path.relative_to(root).as_posix()})
    return rows


def build_report(*, evidence_root: Path | None = None) -> dict[str, Any]:
    profile = _registered_profile()
    marker_report = verify_hostile_markers()
    files = {path.relative_to(STUDIO).as_posix(): _sha(path) for path in SOURCE_FILES}
    closure = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    existing = _raw_receipts(evidence_root or STUDIO / ".local/reviews")
    has_script_route = "script.create" in profile.get("operations", ()) or profile.get("script_enabled") is True
    rows = [
        {"id": "K3", "status": "OPEN", "reason": "REGISTERED_SCRIPT_ROUTE_DISABLED",
         "profile_script_enabled": profile.get("script_enabled"), "registered_replay": False},
        {"id": "K4", "status": "OPEN", "reason": "REGISTERED_STATIC_GRAPH_NOT_BOUND",
         "registered_reopen_graph": False},
        {"id": "K5", "status": "OPEN", "reason": "REGISTERED_FAILURE_ACK_NOT_BOUND",
         "registered_failure_exit_preserved": False},
        {"id": "K6", "status": "OPEN", "reason": "REGISTERED_DURABLE_PUBLISH_NOT_IMPLEMENTED",
         "registered_reopen_owner_edit": False},
        {"id": "K7", "status": "OPEN", "reason": "REGISTERED_HOSTILE_EXECUTOR_NOT_BOUND",
         "hostile_marker_contract": marker_report["verified"],
         "registered_sandbox_observation": False},
    ]
    return {"schema": "hh-gt09-b4-registered-failure-1", "authority": 0,
            "public_ack": False, "profile": profile, "source_closure_sha256": closure,
            "source_files": files, "rows": rows, "registered_script_route": has_script_route,
            "hostile_markers": marker_report, "existing_raw_receipts": existing,
            "diagnostic_only": True, "package_ready": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate without writing evidence")
    parser.add_argument("--evidence-root", type=Path, default=STUDIO / ".local/reviews")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = build_report(evidence_root=args.evidence_root.resolve())
    if args.output is not None:
        output = args.output.resolve()
        if not output.is_relative_to(STUDIO / ".local/reviews"):
            parser.error("output must be below studio/.local/reviews")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"schema": report["schema"], "status": "OPEN",
                      "rows": [row["id"] + ":" + row["status"] for row in report["rows"]],
                      "source_closure_sha256": report["source_closure_sha256"],
                      "raw_receipts": len(report["existing_raw_receipts"]),
                      "authority": report["authority"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
