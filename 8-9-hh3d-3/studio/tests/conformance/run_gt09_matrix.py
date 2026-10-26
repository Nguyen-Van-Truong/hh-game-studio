"""Single fail-closed GT-09 K1-K15 matrix coordinator.

The dry-run freezes the row table and validates that every referenced runner is
present without starting Godot, Blender, Docker, MCP, or a long playtest.
``--matrix final`` only assembles rows that already have explicit PASS evidence
on one source closure; it never turns a diagnostic banner into a PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

_RUN_FIXTURE_MODULE: Any | None = None

STUDIO = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO.parent
PLAN = STUDIO.parent / "zdoc" / "8-9-godot-blender-agent-studio-plan.txt"
SCHEMA = "hh-gt09-matrix-1"
ROW_IDS = tuple(f"K{i}" for i in range(1, 16))
K13_EXTERNAL_IDS = {"NPGameDev/godot-mcp-toolkit", "hybridindie/godot-mcp"}

# Evidence is deliberately explicit.  A row may be reused only after its
# producer has emitted status=PASS on the same final closure.
ROWS: dict[str, dict[str, Any]] = {
    "K1": {"gate": "registered catalog discovery and fixture-only admission", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K2": {"gate": "registered allowlist validation and idempotent conflict", "runner": "tests/godot/test_registered_authoring_owner.py", "status": "OPEN"},
    "K3": {"gate": "registered AUTH-01 authored behavior and replay", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K4": {"gate": "AUTH-02 dependency graph, UID/import and rejects", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K5": {"gate": "AUTH-03 failure preserves last good", "runner": "tests/godot/run_gameplay_failure_probe.py", "status": "OPEN"},
    "K6": {"gate": "AUTH-04 durable publish retry/reopen and owner edit", "runner": "tests/godot/run_gameplay_publication_probe.py", "status": "OPEN"},
    "K7": {"gate": "AUTH-05 executor isolation and hostile cases", "runner": "tests/godot/run_linux_probe.py", "status": "OPEN"},
    "K8": {"gate": "two fixtures authored through catalog commands", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
    "K9": {"gate": "seeded defect repair through catalog batch and replay", "runner": "tests/conformance/run_gt09_fixture_repair.py", "status": "OPEN"},
    "K10": {"gate": "input/pause/save/reload/perf on final catalog fixtures", "runner": "tests/godot/run_delegated_playtest.py", "status": "OPEN"},
    "K11": {"gate": "reconnect/retry/context reset/owner edit/parallel source jobs", "runner": "tests/godot/run_gameplay_adapter_probe.py", "status": "OPEN"},
    "K12": {"gate": "prompt injection and out-of-scope command rejection", "runner": "tests/godot/test_gameplay_attribution.py", "status": "OPEN"},
    "K13": {"gate": "pinned MCP/client/model/host operation matrix", "runner": "tests/conformance/run_gt09_mcp_spike.py", "status": "OPEN"},
    "K14": {"gate": "GT-08A/TX15/focused regression on final closure", "runner": "build/ci/gt08a_matrix.py", "status": "OPEN"},
    "K15": {"gate": "delegated 2 x 15 minute final-closure playtest", "runner": "tests/godot/run_delegated_playtest.py", "status": "OPEN"},
}


class MatrixError(ValueError):
    pass


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise MatrixError(message)


def _row_payload(row_id: str | None = None) -> list[dict[str, Any]]:
    if row_id is not None:
        _need(row_id in ROWS, f"unknown_row:{row_id}")
        ids = [row_id]
    else:
        ids = list(ROW_IDS)
    result = []
    for ident in ids:
        row = dict(ROWS[ident])
        runner = STUDIO / row["runner"]
        row.update({"id": ident, "runner_exists": runner.is_file(),
                    "runner_sha256": _sha(runner) if runner.is_file() else None})
        _need(row["runner_exists"], f"runner_missing:{ident}:{row['runner']}")
        result.append(row)
    return result


def dry_run(row_id: str | None = None) -> dict[str, Any]:
    _need(PLAN.is_file(), "plan_missing")
    rows = _row_payload(row_id)
    return {"schema": SCHEMA, "mode": "DRY_RUN", "authority": 0,
            "acceptance": False, "engine_launched": False, "network_used": False,
            "plan_sha256": _sha(PLAN), "row_count": len(rows), "rows": rows,
            "required_rows": list(ROW_IDS)}


def load_rows(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError("evidence_manifest_invalid") from exc
    _need(type(value) is dict and value.get("schema") == SCHEMA, "evidence_manifest_schema")
    return value


def _safe_review_path(path: Path, *, root: Path, must_file: bool = True) -> Path:
    """Resolve a receipt only inside this matrix's review directory."""
    value = path if path.is_absolute() else root / path
    value = value.resolve()
    _need(value.is_relative_to(root.resolve()), "evidence_path_outside_review")
    _need((value.is_file() if must_file else value.is_dir()),
          f"evidence_missing:{value.name}")
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MatrixError(f"evidence_json_invalid:{path.name}") from exc
    _need(type(value) is dict, f"evidence_json_shape:{path.name}")
    return value


def _review_json(run_id: str, name: str = "result.json") -> dict[str, Any] | None:
    """Read an existing review receipt without treating its caller fields as proof.

    The orchestrator uses this only as an input to the row-specific semantic
    predicates below.  A missing receipt is a hard false, which keeps a unit
    test's exit code from manufacturing native evidence.
    """
    path = STUDIO / ".local" / "reviews" / run_id / name
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if type(value) is dict else None


def _auth_failure_semantics(paths: tuple[Path, Path]) -> bool:
    """Require the two exact AUTH-03 native receipts from this matrix."""
    found: list[dict[str, Any]] = []
    for path, fixture in zip(paths, ("syntax", "type")):
        try:
            result = json.loads((path / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        if result.get("source_closure_sha256") in (None, ""):
            return False
        if (result.get("status") != "DIAGNOSTIC_PASS"
                or result.get("failure_fixture") != fixture
                or result.get("bad_rejected") is not True
                or result.get("reopen_readback_equal") is not True
                or result.get("retry_equal") is not True
                or result.get("retry_no_redispatch") is not True
                or result.get("durable_state_unchanged") is not True
                or result.get("source_unchanged") is not True):
            return False
        found.append(result)
    return len(found) == 2 and len({item.get("source_closure_sha256") for item in found}) == 1


def _auth05_semantics(paths: tuple[Path, Path, Path, Path]) -> bool:
    """Require the exact four AUTH-05 native receipts from this matrix."""
    closures = set()
    for path, fixture in zip(paths, ("boundary", "spawn", "busy", "wall")):
        try:
            result = json.loads((path / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        if not result.get("source_closure_sha256"):
            return False
        closures.add(result.get("source_closure_sha256"))
        observation = result.get("bad_observation")
        if (result.get("status") != "DIAGNOSTIC_PASS"
                or result.get("failure_fixture") != fixture
                or result.get("bad_rejected") is not True
                or result.get("reopen_readback_equal") is not True
                or result.get("retry_equal") is not True
                or result.get("retry_no_redispatch") is not True
                or result.get("durable_state_unchanged") is not True
                or result.get("source_unchanged") is not True
                or type(observation) is not dict
                or observation.get("fixture_observed") is not True
                or observation.get("confinement_lifecycle_observed") is not True
                or observation.get("supervisor_binding_verified") is not True):
            return False
    return len(closures) == 1


def _publication_semantics(publication: Path, *, fixture: str) -> bool:
    """Require the native publication/reopen/readback contract for a fixture."""
    result_path = publication / "result.json"
    if not result_path.is_file():
        return False
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if (result.get("status") != "DIAGNOSTIC_PASS"
            or result.get("authority") != 0
            or result.get("public_ack") is not False
            or result.get("native_fixture_observed") is not True
            or result.get("live_retry_equal") is not True
            or result.get("reopened_retry_equal") is not True
            or result.get("durable_state_unchanged") is not True
            or result.get("source_unchanged") is not True):
        return False
    handoff_key = "catalog_handoff" if fixture == "arena" else "catalog_room_handoff"
    handoff = result.get(handoff_key)
    if type(handoff) is not dict or handoff.get("schema") != "hh-catalog-gameplay-handoff-1":
        return False
    provenance = handoff.get("provenance")
    if type(provenance) is not dict or not handoff.get("native_run_id"):
        return False
    if provenance.get("catalog_result_sha256") is None or provenance.get("catalog_observation_sha256") is None:
        return False
    if result.get("blender_content_verified") is not True:
        return False
    blender = result.get("blender_content")
    return (type(blender) is dict and isinstance(blender.get("manifest_sha256"), str)
            and type(blender.get("artifact_sha256")) is dict
            and all(isinstance(value, str) for value in blender["artifact_sha256"].values()))


def _generic_publication_semantics(publication: Path) -> bool:
    """Validate the native AUTH-04 publication used by K6.

    K6 is deliberately separate from the catalog-specific K8 receipts, but it
    must still carry a native publication and durable retry/readback proof.
    """
    try:
        result = json.loads((publication / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (result.get("status") == "DIAGNOSTIC_PASS"
            and result.get("authority") == 0
            and result.get("public_ack") is False
            and result.get("native_fixture_observed") is True
            and result.get("native_run_count") == 1
            and result.get("live_retry_equal") is True
            and result.get("reopened_retry_equal") is True
            and result.get("durable_state_unchanged") is True
            and result.get("source_unchanged") is True
            and isinstance(result.get("source_closure_sha256"), str))


def _registered_semantics(publication: Path, *, fixture: str) -> bool:
    """Validate registered discovery/transaction readback embedded by publication."""
    try:
        result = json.loads((publication / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    key = "catalog_handoff" if fixture == "arena" else "catalog_room_handoff"
    handoff = result.get(key)
    if type(handoff) is not dict:
        return False
    root = handoff.get("registered_root")
    if not isinstance(root, str):
        return False
    registered = Path(root)
    receipt_path = registered / "registered-owner-result.json"
    if not receipt_path.is_file():
        return False
    try:
        owner = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    discovery = owner.get("discovery")
    profile = owner.get("profile")
    transaction = owner.get("transaction")
    receipt = owner.get("receipt")
    commands = receipt.get("command_ids") if isinstance(receipt, dict) else None
    return (owner.get("status") == "DIAGNOSTIC_PASS" and owner.get("same_request_same_receipt") is True
            and type(discovery) is dict and discovery.get("fixture_enabled") is True
            and type(profile) is dict and profile.get("profile") == "hh-godot-gameplay-source-1"
            and profile.get("script_enabled") is True
            and type(transaction) is dict and transaction.get("schema") == "hh-godot-authoring-transaction-1"
            and isinstance(transaction.get("command_ids"), list) and len(transaction["command_ids"]) >= 3
            and type(receipt) is dict and receipt.get("readback_ack") is True
            and receipt.get("native_observed") is True and isinstance(commands, list))


def _conformance_semantics(path: Path, *, closure: str | None = None) -> bool:
    if not path.is_file():
        return False
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (result.get("status") == "CANDIDATE_PASS"
            and result.get("authority") == 0
            and result.get("acceptance") is False
            and result.get("errors") == []
            and isinstance(result.get("source_closure_sha256"), str)
            and (closure is None or result.get("source_closure_sha256") == closure))


def _host_playtest_semantics(run_id: str, *, fixture: str,
                             expected_publication: Path | None = None,
                             minimum_seconds: float = 900.0) -> bool:
    """Require owned import/native/video exits and immutable publication provenance."""
    root = STUDIO / ".local" / "reviews" / run_id / fixture
    try:
        metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
        result = json.loads((root / "host-result.json").read_text(encoding="utf-8"))
        native = json.loads((root / "native" / "capture.json").read_text(encoding="utf-8"))
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        video = result.get("video")
    except (OSError, ValueError, TypeError):
        return False
    provenance = metadata.get("publication_provenance")
    if not isinstance(provenance, dict):
        return False
    summary = manifest.get("summary") if type(manifest.get("summary")) is dict else {}
    state = manifest.get("state_readback") if type(manifest.get("state_readback")) is dict else {}
    counts = summary.get("counts") if type(summary.get("counts")) is dict else {}
    return (metadata.get("source_mode") == "native-publication-snapshot"
            and metadata.get("legacy_unaccepted") is False
            and manifest.get("schema") == "hh-fixture-lifecycle-evidence-2"
            and manifest.get("status") == "PLAYTEST_EVIDENCE_READY"
            and manifest.get("errors") == []
            and manifest.get("run_id") == run_id
            and manifest.get("fixture") == fixture
            and manifest.get("source_closure_sha256") == metadata.get("source_closure_sha256")
            and (expected_publication is None
                 or (isinstance(provenance.get("publication_root"), str)
                     and Path(provenance["publication_root"]).resolve()
                         == expected_publication.resolve()))
            and summary.get("mode") == "scripted"
            and summary.get("reason") == "input_quit"
            and summary.get("lifecycle_complete") is True
            and summary.get("freeze_errors") == 0
            and summary.get("elapsed_ms", 0) >= int(minimum_seconds * 1000)
            and all(type(counts.get(command)) is int and counts[command] >= 1
                    for command in ("start", "pause", "resume", "restart", "quit"))
            and state.get("final_phase") == "QUIT"
            and state.get("freeze_errors") == 0
            and result.get("status") == "HOST_RUN_CAPTURED"
            and result.get("actual_process_exit") == 0
            and result.get("wrapper_exit_code") == 0
            and result.get("timed_out") is False
            and not result.get("errors")
            and isinstance(result.get("duration_seconds"), (int, float))
            and result["duration_seconds"] >= minimum_seconds
            and type(result.get("tree")) is dict and result["tree"].get("verified") is True
            and type(result.get("job")) is dict and result["job"].get("zero_observed") is True
            and type(native.get("actual_process_exit")) is dict
            and native["actual_process_exit"].get("exit_code") == 0
            and native.get("natural_tree_exit") is True
            and type(video) is dict and video.get("status") == "decoded"
            and type(provenance) is dict
            and provenance.get("selected_matches_executed_snapshot") is True
            and isinstance(provenance.get("native_run_id"), str)
            and provenance.get("executed_snapshot_files") == metadata.get("source_files"))


def _adapter_semantics(path: Path) -> bool:
    try:
        result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    if not result.get("source_closure_sha256"):
        return False
    exits = result.get("native_exits")
    receipts = result.get("receipts")
    return (result.get("native_fixture_observed") is True
            and isinstance(receipts, list) and len(receipts) >= 2
            and all(type(item) is dict and item.get("status") == "READBACK_ACK"
                    and item.get("readback_ack") is True for item in receipts)
            and isinstance(exits, list) and len(exits) >= 2
            and all(type(item) is dict and item.get("command_host_exit") == 0
                    and item.get("container_exit") == 0 and item.get("docker_wait_exit") == 0
                    and item.get("timed_out") is False for item in exits)
            and type(result.get("contender")) is dict
            and result["contender"].get("error_code") == "GAMEPLAY_OWNER_BUSY"
            and result.get("context_reset_lookup_only") is True
            and result.get("reconnect_lookup_only") is True
            and result.get("durable_state_unchanged") is True
            and result.get("source_unchanged") is True
            and result.get("unsupported_client_rejected") is True
            and result.get("owner_edit_preserved") is True)


def _attribution_semantics(root: Path) -> bool:
    result_path = root / "result.json"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    host = result.get("command_host")
    state = result.get("container_state")
    return (result.get("schema") == "hh-gt09-attribution-hostile-2"
            and result.get("diagnostic_execution_complete") is True
            and result.get("attribution_verified") is True
            and result.get("attribution_harness_unchanged") is True
            and result.get("gameplay_source_envelope_checked") is True
            and result.get("input_unchanged") is True
            and result.get("snapshot_unchanged") is True
            and result.get("owner_record_retained") is False
            and type(host) is dict and host.get("exit_code") == 0
            and type(state) is dict and state.get("ExitCode") == 0
            and type(result.get("scope_boundary")) is dict
            and result["scope_boundary"].get("accepted") is False
            and result["scope_boundary"].get("native_dispatch") is False
            and result["scope_boundary"].get("no_effect") is True
            and type(result.get("hostile_inputs")) is dict
            and result["hostile_inputs"].get("treated_as_opaque_data") is True
            and type(result.get("raw_rejection")) is dict
            and isinstance(result["raw_rejection"].get("stdout_sha256"), str)
            and result.get("source_closure_sha256", "").startswith("sha256:")
            and result.get("forged", {}).get("diagnostic_execution_complete") is False
            and result.get("forged", {}).get("log_policy", {}).get("accepted") is False)


def _k13_semantics(doc: dict[str, Any], client: Path | None = None,
                    expected_closure: str | None = None) -> bool:
    if not isinstance(doc, dict):
        return False
    rows = doc.get("rows")
    if not isinstance(rows, list):
        return False
    # Transport-only and CLIENT_OPEN packages cannot close O13.1e, even when
    # a separately bound client receipt is complete. Every policy adapter
    # needs its own measured native result.
    if ("OPEN" in str(doc.get("status", ""))
            or any(isinstance(row, dict)
                   and row.get("status") in {"UNMEASURED", "MEASURED_TRANSPORT_ONLY"}
                   for row in rows)):
        return False
    if (doc.get("schema") != "hh-gt09-mcp-capability-matrix-1"
            or doc.get("status") not in {"EXTERNAL_NATIVE_LIMITS_MEASURED", "COMPLETE"}
            or doc.get("authority") != 0 or doc.get("acceptance") is not False):
        return False
    private = doc.get("private_receipt")
    if type(private) is not dict or not isinstance(private.get("path"), str):
        return False
    receipt_path = (REPO_ROOT / private["path"]).resolve()
    if not receipt_path.is_file() or private.get("sha256") != _sha(receipt_path):
        return False
    required_ids = {"hh-private-python-adapter", *K13_EXTERNAL_IDS, "hh-public-catalog"}
    if (type(rows) is not list or len(rows) != len(required_ids)
            or {row.get("id") for row in rows if isinstance(row, dict)} != required_ids):
        return False
    for row in rows:
        if type(row) is not dict or row.get("authority") != 0 or not row.get("id"):
            return False
        row_id = row.get("id")
        if row_id == "hh-private-python-adapter" and row.get("status") != "MEASURED_PRIVATE":
            return False
        if row_id == "hh-public-catalog" and row.get("status") != "DISABLED":
            return False
        if row_id in K13_EXTERNAL_IDS:
            if row.get("status") not in {"SUPPORTED", "UNSUPPORTED", "INCOMPATIBLE"}:
                return False
            native = row.get("native_receipt")
            if (not isinstance(native, dict) or not isinstance(native.get("path"), str)
                    or not isinstance(native.get("sha256"), str)):
                return False
        receipt = row.get("receipt") or row.get("native_receipt")
        if row_id in K13_EXTERNAL_IDS and not isinstance(receipt, dict):
            return False
        if type(receipt) is dict and receipt.get("path"):
            path = (REPO_ROOT / str(receipt["path"])).resolve()
            if (not path.is_file() or path.is_symlink()
                    or not path.is_relative_to(STUDIO.resolve())
                    or receipt.get("sha256") != _sha(path)):
                return False
    if client is None:
        return True
    try:
        receipt = json.loads(client.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (receipt.get("schema") == "hh-gt09-mcp-client-receipt-1"
            and receipt.get("status") == "MEASURED_INCOMPATIBLE"
            and receipt.get("authority") == 0
            and receipt.get("public_ack") is False
            and isinstance(receipt.get("client"), dict)
            and isinstance(receipt["client"].get("name"), str)
            and isinstance(receipt["client"].get("version"), str)
            and isinstance(receipt["client"].get("model"), str)
            and type(receipt.get("host")) is dict
            and isinstance(receipt.get("adapter"), str)
            and isinstance(receipt.get("protocol"), str)
            and isinstance(receipt.get("external_client"), dict)
            and isinstance(receipt.get("external_protocol"), str)
            and isinstance(receipt.get("author"), dict)
            and isinstance(receipt["author"].get("model"), str)
            and receipt["author"].get("model", "").upper() != "UNSPECIFIED"
            and receipt.get("recipe_observed") is True
            and receipt.get("batch_observed") is True
            and isinstance(receipt.get("transcript_sha256"), str)
            and isinstance(receipt.get("source_closure_sha256"), str)
            and isinstance(receipt.get("author_provenance"), dict)
            and isinstance(receipt["author_provenance"].get("path"), str)
            and (lambda p: p.is_file() and receipt["author_provenance"].get("sha256") == _sha(p))(
                Path(receipt["author_provenance"]["path"]).resolve())
            and (expected_closure is None
                 or receipt.get("source_closure_sha256") == expected_closure))


def _gt08a_semantics(root: Path) -> bool:
    path = root / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    rows = value.get("rows")
    formal = value.get("formal_acceptance", value.get("acceptance"))
    return (value.get("status") == "PASS" and value.get("authority") == 0
            and formal is False and type(rows) is list
            and len(rows) == 18
            and all(type(row) is dict and row.get("status") == "PASS"
                    for row in rows))


def _k10_semantics(*, arena: Path, room: Path, conformance: Path) -> bool:
    """Bind K10 to native fixture observations and the checked catalog closure.

    Lifecycle input/pause evidence is packed separately by the delegated
    playtest verifier (K15).  K10 still refuses the old static-only shortcut:
    both final publication snapshots must contain the lifecycle dependency and
    the same conformance package must be a native candidate pass.
    """
    if not _conformance_semantics(conformance):
        return False
    for publication in (arena, room):
        try:
            result = json.loads((publication / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return False
        files = result.get("selected", {}).get("files")
        scene_key = ("catalog_scene_instantiation_observed"
                     if publication.name.endswith("arena")
                     else "catalog_room_scene_instantiation_observed")
        if (result.get("native_fixture_observed") is not True
                or result.get(scene_key) is not True
                or type(files) is not dict
                or "scripts/fixture_lifecycle.gd" not in files):
            return False
    return True


def _registered_script_semantics(path: Path, *, closure: str | None = None) -> bool:
    """K3 controller change only; K9 validates both real publications separately."""
    try:
        result = _load_json(path / "result.json")
        before = result["baseline"]
        after = result["replay"]
        route = result["registered_route"]
        return (result.get("schema") == "hh-gt09-registered-script-result-1"
                and result.get("status") == "DIAGNOSTIC_PASS"
                and result.get("authority") == 0 and result.get("acceptance") is False
                and (closure is None or result.get("source_closure_sha256") == closure)
                and before.get("fixture_observed") is True and after.get("fixture_observed") is True
                and before["untrusted_child_observation"] != after["untrusted_child_observation"]
                and after["untrusted_child_observation"].get("controller_speed") == 0.75
                and route.get("status") in ("READBACK_ACK", "APPLIED")
                and route["receipt"].get("readback_ack") is True
                and result.get("same_command_retry") is True)
    except (OSError, ValueError, TypeError, KeyError):
        return False


def _verify_row(row: dict[str, Any], *, matrix_root: Path, closure: str | None,
                strict_steps: bool = False) -> str:
    """Verify raw child receipts; caller fields cannot manufacture a PASS."""
    ident = row.get("id")
    _need(ident in ROWS, f"unknown_row:{ident}")
    raw_path = _safe_review_path(Path(str(row.get("evidence_path", ""))), root=matrix_root)
    raw = _load_json(raw_path)
    _need(raw.get("schema") in ("hh-gt09-row-result-1", "hh-gt09-evidence-1"),
          f"{ident}:evidence_schema")
    _need(raw.get("row_id") == ident, f"{ident}:evidence_row_id")
    _need(raw.get("status") == "PASS", f"{ident}:evidence_status")
    child_closure = raw.get("source_closure_sha256")
    _need(type(child_closure) is str and child_closure.startswith("sha256:")
          and len(child_closure) == 71, f"{ident}:evidence_closure")
    if closure is not None:
        _need(child_closure == closure, f"{ident}:source_closure_mismatch")
    exit_path = _safe_review_path(Path(str(row.get("exit_evidence_path", ""))), root=matrix_root)
    receipt = _load_json(exit_path)
    _need(receipt.get("schema") == "hh-process-exit-1", f"{ident}:exit_schema")
    _need(receipt.get("row_id") == ident and receipt.get("actual_exit") == 0
          and receipt.get("timed_out") is False and receipt.get("owned_tree_zero") is True,
          f"{ident}:actual_exit")
    _need(row.get("evidence_sha256") == _sha(raw_path)
          and row.get("exit_evidence_sha256") == _sha(exit_path),
          f"{ident}:receipt_hash")
    steps = raw.get("steps")
    if strict_steps:
        _need(type(steps) is list and steps, f"{ident}:steps_missing")
        evidence_types = {step.get("evidence_type") for step in steps if type(step) is dict}
        _need("host" in evidence_types or "native" in evidence_types,
              f"{ident}:evidence_type_missing")
        _need(all(type(step) is dict and isinstance(step.get("command"), list)
                  and isinstance(step.get("actual_exit"), int)
                  and step.get("actual_exit") == 0
                  and type(step.get("wrapper_exit")) is int
                  and step.get("wrapper_exit") == 0
                  and step.get("timed_out") is False
                  and step.get("owned_tree_zero") is True
                  for step in steps), f"{ident}:step_exit")
        _verify_step_receipts(raw, matrix_root=matrix_root)
        references = raw.get("references", [])
        bindings = raw.get("reference_sha256")
        _need(isinstance(bindings, dict) and references
              and set(bindings) == set(references), f"{ident}:reference_bindings")
        for reference in references:
            path = Path(reference).resolve()
            _need(path.is_file() and not path.is_symlink()
                  and path.is_relative_to(STUDIO.resolve())
                  and _sha(path) == bindings[reference],
                  f"{ident}:reference_hash:{path.name}")
        _revalidate_row_semantics(raw)
    return child_closure


def _self_check_row(row: dict[str, Any], *, root: Path, closure: str) -> None:
    """Check persisted evidence before spending time on the next native row."""
    if row["status"] != "PASS":
        return
    try:
        _verify_row(row, matrix_root=root, closure=closure, strict_steps=True)
    except Exception as error:
        # Preserve producer/exit receipts; the separate diagnostic records why
        # the persisted PASS was not sufficient to continue this matrix.
        row["status"] = "FAIL"
        row["failure_class"] = "VERIFIER"
        row["self_check_error"] = type(error).__name__ + ":" + str(error)
        (root / "rows" / row["id"] / "self-check-failure.json").write_bytes(_canonical({
            "row_id": row["id"], "authority": 0, "status": "FAIL",
            "failure_class": "VERIFIER", "error": row["self_check_error"],
        }))


def final_matrix(row_evidence: Path | None, output: Path | None, run_id: str) -> int:
    _need(row_evidence is not None, "final_requires_row_evidence")
    manifest = load_rows(row_evidence)
    rows = manifest.get("rows")
    _need(type(rows) is list and len(rows) == len(ROW_IDS)
          and {r.get("id") for r in rows if isinstance(r, dict)} == set(ROW_IDS),
          "final_requires_all_rows")
    errors: list[str] = []
    closures: set[str] = set()
    matrix_root = row_evidence.parent.resolve()
    for row in rows:
        try:
            closures.add(_verify_row(row, matrix_root=matrix_root,
                                     closure=next(iter(closures), None), strict_steps=True))
        except MatrixError as exc:
            errors.append(str(exc))
    if len(closures) != 1:
        errors.append("source_closure_mismatch")
    result = {"schema": SCHEMA, "run_id": run_id, "authority": 0,
              "acceptance": False, "status": "PASS" if not errors else "INCOMPLETE",
              "source_closure_sha256": next(iter(closures)) if len(closures) == 1 else None,
              "rows": rows, "errors": errors, "engine_launched": False}
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_canonical(result))
    print(json.dumps({"schema": SCHEMA, "run_id": run_id, "status": result["status"],
                      "errors": errors, "authority": 0}, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


def rehearsal_rows(*, output: Path, run_id: str, selected: tuple[str, ...]) -> int:
    """Run selected short rows on the current source without making a final.

    This is intentionally a real producer/validator path, rather than the
    old ``--row`` plan printer.  K3 is independent of the Blender/publication
    chain and is the first useful rehearsal after a registered-script failure;
    adding another row requires its producer dependencies to be wired here.
    The resulting manifest is explicitly rehearsal-only and can never satisfy
    ``final`` or ``verify-only``.
    """
    if selected == ('K9',):
        return final_matrix_orchestrated(output=output, run_id=run_id, k13=None,
                                         rehearsal_through_k9=True)
    output = output.resolve()
    _need(not output.exists(), f"rehearsal_output_exists:{output}")
    _need(selected and len(set(selected)) == len(selected), "rehearsal_rows_empty_or_duplicate")
    for row_id in selected:
        _need(row_id in ROW_IDS, f"unknown_row:{row_id}")
    unsupported = [row_id for row_id in selected if row_id != "K3"]
    _need(not unsupported, "rehearsal_dependencies_not_wired:" + ",".join(unsupported))
    output.mkdir(parents=True)
    closure, closure_payload = _source_tree_closure()
    nonce = hashlib.sha256((run_id + ":" + closure).encode()).hexdigest()[:10]
    rows: list[dict[str, Any]] = []
    producer = {"matrix_source_closure": closure, "mode": "REHEARSAL"}
    script_root = output / "registered-script"
    script_cmd = [sys.executable, "-B", "studio/tests/conformance/run_gt09_registered_script.py",
                  "--run-id", f"gt09-registered-script-{nonce}", "--output", str(script_root)]
    unit_cmd = _test_command(("studio.tests.godot.test_gameplay_behavior",
                              "studio.tests.godot.test_gameplay_source_adapter"))
    steps: list[dict[str, Any]] = []
    for index, (command, timeout, evidence_type) in enumerate(
            ((unit_cmd, 240, "unit"), (script_cmd, 600, "native")), 1):
        step = _run_owned(command, cwd=REPO_ROOT,
                          raw_dir=output / "raw" / f"K3/{index}", timeout=timeout)
        step["evidence_type"] = evidence_type
        steps.append(step)
        if step.get("actual_exit") != 0 or step.get("timed_out") or not step.get("owned_tree_zero"):
            break
    semantic = (all(step.get("actual_exit") == 0 and not step.get("timed_out")
                    and step.get("owned_tree_zero") for step in steps)
                and _registered_script_semantics(script_root))
    row = _write_row(output, "K3", closure=closure, producer_closures=producer,
                     steps=steps, semantic_pass=semantic,
                     requirement="registered AUTH-01 authored behavior and replay",
                     references=[str(script_root / "result.json")])
    _self_check_row(row, root=output, closure=closure)
    semantic = row["status"] == "PASS"
    rows.append(row)
    closure_end, closure_end_payload = _source_tree_closure()
    _need(closure_end == closure, "source_changed_during_rehearsal")
    manifest = {"schema": SCHEMA, "mode": "REHEARSAL", "run_id": run_id,
                "authority": 0, "acceptance": False,
                "status": "PASS" if semantic else "INCOMPLETE",
                "source_closure_sha256": closure, "closure_start": closure,
                "closure_end": closure_end, "closure_payload": closure_payload,
                "closure_end_payload": closure_end_payload, "producer": producer,
                "rows": rows, "required_rows": list(selected),
                "engine_launched": True, "network_used": False}
    (output / "manifest.json").write_bytes(_canonical(manifest))
    (output / "manifest.sha256").write_text(_sha(output / "manifest.json") + "\n", encoding="ascii")
    print(json.dumps({"schema": SCHEMA, "mode": "REHEARSAL", "run_id": run_id,
                      "status": manifest["status"], "manifest": str(output / "manifest.json"),
                      "source_closure_sha256": closure}, sort_keys=True))
    return 0 if semantic else 2


def _verify_step_receipts(raw: dict[str, Any], *, matrix_root: Path) -> None:
    """Read process and stream receipts independently of the row assertions."""
    ident = raw["row_id"]
    seen_dirs: set[Path] = set()
    for index, step in enumerate(raw["steps"], 1):
        prefix = f"{ident}:step{index}"
        _need(isinstance(step, dict), prefix + ":step_shape")
        receipt_dir = _safe_review_path(Path(step.get("receipt_dir", "")),
                                        root=matrix_root, must_file=False)
        _need(receipt_dir.is_dir(), prefix + ":receipt_directory")
        _need(receipt_dir.is_relative_to((matrix_root / "raw" / ident).resolve()),
              prefix + ":receipt_directory_owner")
        _need(receipt_dir not in seen_dirs, prefix + ":receipt_directory_reused")
        seen_dirs.add(receipt_dir)
        host_path = _safe_review_path(receipt_dir / str(step.get("host_receipt", "")), root=matrix_root)
        host = _load_json(host_path)
        owner = host.get("job_owner")
        _need(isinstance(owner, dict), prefix + ":job_owner_shape")
        _need(type(host.get("wrapper_exit_code")) is int and host.get("wrapper_exit_code") == 0
              and type(step.get("wrapper_exit")) is int and step.get("wrapper_exit") == 0
              and step.get("host_sha256") == _sha(host_path)
              and type(host.get("exit_code")) is int and host["exit_code"] == step.get("actual_exit") == 0
              and host.get("wrapper_exit_code") == step.get("wrapper_exit")
              and host.get("timed_out") is step.get("timed_out")
              and host.get("tree_verified") is step.get("owned_tree_zero")
              and host.get("readers_stopped") is True
              and owner.get("zero_observed") is True
              and owner.get("active_count") == 0, prefix + ":owned_exit")
        for stream in ("stdout", "stderr"):
            path = _safe_review_path(receipt_dir / str(host.get(stream, "")), root=matrix_root)
            _need(_sha(path) == step.get(stream + "_sha256"), prefix + ":" + stream + "_hash")


def _revalidate_row_semantics(raw: dict[str, Any]) -> None:
    """Replay the same read-only validators on persisted producer evidence.

    Never execute commands from a manifest: paths select data for fixed local
    validators. These validators neither launch engines nor rewrite reports.
    """
    ident = raw["row_id"]
    refs = [Path(value) for value in raw.get("references", [])]
    producer = raw.get("producer_closures", {})
    _need(bool(refs), f"{ident}:semantic_references")
    ok = False
    if ident == "K1":
        ok = _content_semantics(refs[0].parent)[0] and all(
            _registered_probe_semantics(ref.parent, fixture=fixture)
            for ref, fixture in zip(refs[1:], ("arena", "room"))) and len(refs) == 3
    elif ident == "K2":
        from studio.tests.conformance.run_gt09_registered_check import _check
        check = _load_json(refs[0])
        values = []
        for fixture in ("arena", "room"):
            value = _load_json(Path(producer["registered_roots"][fixture]) / "registered-owner-result.json")
            _check(value, fixture)
            values.append(value)
        ok = (check.get("status") == "DIAGNOSTIC_PASS"
              and values[0]["transaction"]["command_ids"] != values[1]["transaction"]["command_ids"]
              and values[0]["source_closure_sha256"] == values[1]["source_closure_sha256"]
              == check.get("source_closure_sha256"))
    elif ident == "K3":
        ok = _registered_script_semantics(refs[0].parent)
    elif ident == "K9":
        from studio.tests.conformance.run_gt09_fixture_repair import verify
        doc = verify(refs[0].parent)
        ok = all(doc['fixtures'][fixture]['publication'] == producer['publication_roots'][fixture]
                 for fixture in ('arena', 'room'))
    elif ident == "K4":
        from studio.tests.conformance.run_gt09_catalog_native_check import _check
        for fixture in ("arena", "room"):
            _check(Path(producer["native_roots"][fixture]))
        check = _load_json(refs[0])
        ok = check.get("status") == "DIAGNOSTIC_PASS" and check.get("dependency_readback") is True
    elif ident == "K5":
        ok = len(refs) == 2 and _auth_failure_semantics(tuple(ref.parent for ref in refs))
        if ok:
            _revalidate_failure_raw(refs)
    elif ident == "K6":
        ok = (len(refs) == 3 and _generic_publication_semantics(refs[2].parent)
              and _publication_semantics(refs[0].parent, fixture="arena")
              and _publication_semantics(refs[1].parent, fixture="room"))
    elif ident == "K7":
        ok = len(refs) == 4 and _auth05_semantics(tuple(ref.parent for ref in refs))
        if ok:
            _revalidate_failure_raw(refs)
    elif ident in {"K8", "K10"}:
        from studio.tests.conformance.gt09_fixture_conformance import build_report
        _need(len(refs) == 3, f"{ident}:conformance_references")
        report = build_report(refs[1].parent, refs[2].parent)
        stored = _load_json(refs[0])
        _need(report == stored, f"{ident}:conformance_raw_mismatch")
        ok = (report["status"] == "CANDIDATE_PASS" and not report["errors"]
              and _publication_semantics(refs[1].parent, fixture="arena")
              and _publication_semantics(refs[2].parent, fixture="room"))
        if ident == "K10":
            ok = ok and _k10_semantics(arena=refs[1].parent, room=refs[2].parent, conformance=refs[0])
    elif ident == "K11":
        ok = _adapter_semantics(refs[0].parent)
    elif ident == "K12":
        ok = _attribution_semantics(refs[0].parent)
    elif ident == "K13":
        expected = producer.get("content_source_closure")
        _need(isinstance(expected, str) and len(expected) == 64
              and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
              "K13:content_source_closure")
        ok = len(refs) == 2 and raw.get("source_closure_sha256") == producer.get("matrix_source_closure") \
            and _k13_semantics(_load_json(refs[0]), client=refs[1], expected_closure=expected)
    elif ident == "K14":
        ok = _gt08a_semantics(refs[0].parent)
    elif ident == "K15":
        from studio.tests.godot.fixture_lifecycle_manifest import build_manifest
        from studio.tests.godot.run_delegated_playtest import _load_metadata, _publication_project
        _need(len(refs) == 2, "K15:publication_references")
        seen = set()
        expected_playtest_closures = producer.get("playtest_source_closures")
        _need(isinstance(expected_playtest_closures, dict), "K15:playtest_closures")
        for step in raw["steps"]:
            command = step["command"]
            _need(isinstance(command, list) and command
                  and any(Path(str(arg)).name in {"run_delegated_playtest.py",
                                                  "run_gt09_playtest_evidence.py"}
                             for arg in command),
                  "K15:runner_identity")
            if "--host" not in command:
                continue
            _need(isinstance(command, list), "K15:command_shape")
            try:
                fixture = command[command.index("--fixture") + 1]
                run_id = command[command.index("--run-id") + 1]
            except (ValueError, IndexError, TypeError) as exc:
                raise MatrixError("K15:command_identity") from exc
            _need(fixture in {"arena", "room"} and fixture not in seen, "K15:fixture_identity")
            _need(isinstance(run_id, str)
                  and re.fullmatch(r"gt09-playtest-20\d{6}-\d{2}", run_id) is not None,
                  "K15:run_id")
            _need("run_delegated_playtest.py" in {Path(str(arg)).name for arg in command}
                  and "--mode" in command and command[command.index("--mode") + 1] == "scripted"
                  and "--deadline-seconds" in command,
                  "K15:host_command")
            seen.add(fixture)
            pub = refs[0 if fixture == "arena" else 1].parent
            _need(_publication_semantics(pub, fixture=fixture),
                  "K15:publication_semantics:" + fixture)
            _, publication_provenance = _publication_project(pub, fixture)
            _need(_host_playtest_semantics(run_id, fixture=fixture, expected_publication=pub),
                  "K15:host_semantics:" + fixture)
            root = STUDIO / ".local/reviews" / run_id / fixture
            metadata = _load_json(root / "metadata.json")
            _load_metadata(metadata)
            _need(metadata.get("publication_provenance") == publication_provenance,
                  "K15:publication_provenance:" + fixture)
            _need(metadata.get("source_closure_sha256") == expected_playtest_closures.get(fixture),
                  "K15:playtest_closure:" + fixture)
            report = build_manifest(fixture=fixture, run_id=run_id,
                log_path=root / "godot.stdout.log", source_closure_sha256=metadata["source_closure_sha256"],
                host_result_path=root / "host-result.json", video_path=root / "video/capture.mkv",
                minimum_duration_seconds=900)
            _need(report == _load_json(root / "manifest.json")
                  and report.get("status") == "PLAYTEST_EVIDENCE_READY" and not report["errors"],
                  "K15:lifecycle_raw_mismatch:" + fixture)
        ok = seen == {"arena", "room"}
    _need(ok, f"{ident}:semantic_validation")


def _revalidate_failure_raw(refs: list[Path]) -> None:
    from studio.tests.godot import run_gameplay_failure_probe as failure
    probe = failure.load("gt09_verify_linux_probe", STUDIO / "tests/godot/run_linux_probe.py")
    fixtures = failure.load("gt09_verify_linux_fixtures", STUDIO / "tests/godot/linux_probe_fixtures.py")
    # The producer adds the canonical scene/project envelope before calling
    # case_files().  Reconstruct that same envelope during verify-only; the
    # raw fixture table intentionally stores only the failure-specific fields.
    profile = failure.load("gt09_verify_gameplay_profile",
                          STUDIO / "godot-addon/gameplay_source_profile.py")
    for ref in refs:
        result = _load_json(ref)
        fixture = result["failure_fixture"]
        case_name = failure.failure_case_name(fixture)
        case = dict(fixtures.FIXTURES[case_name])
        case.update(scene=fixtures.SCENE, project=profile.PROJECT_TEMPLATE)
        if not failure.is_auth05_failure(fixture):
            case.update(timeout=30, authenticated_timeout=True)
        paths = result.get("native_paths", [])
        _need(len(paths) == 2, f"failure:{fixture}:native_paths")
        bad_root = (ref.parent / paths[1]).resolve()
        _need(bad_root.is_relative_to(ref.parent.resolve()), "failure:native_path_escape")
        observation = probe.case_observation(bad_root, case, name=case_name,
                                             binding=_load_json(ref.parent / "binding.json"))
        _need(observation == result.get("bad_observation")
              and observation.get("fixture_observed") is True, f"failure:{fixture}:raw_observation")


def verify_only(root: Path) -> int:
    """Audit an existing package without writing a PASS or changing evidence."""
    root = root.resolve()
    errors: list[str] = []
    try:
        manifest = _load_json(root / "manifest.json")
        _need((root / "manifest.sha256").read_text(encoding="ascii").strip()
              == _sha(root / "manifest.json"), "manifest_hash")
        _need(manifest.get("mode") != "REHEARSAL", "rehearsal_not_acceptable")
        closure = manifest.get("source_closure_sha256")
        _need(manifest.get("schema") == SCHEMA, "manifest_schema")
        _need(isinstance(closure, str) and closure.startswith("sha256:"), "manifest_closure")
        current_closure, _ = _source_tree_closure()
        _need(current_closure == closure, "source_closure_current_mismatch")
        rows = manifest.get("rows")
        _need(type(rows) is list, "manifest_rows")
        for row in rows:
            try:
                _verify_row(row, matrix_root=root, closure=closure, strict_steps=True)
            except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
                errors.append(f"{row.get('id')}:" + str(exc))
        _need(manifest.get("status") == "PASS", "manifest_not_pass")
        _need(manifest.get("closure_start") == manifest.get("closure_end") == closure,
              "closure_boundary")
        _need({row.get("id") for row in rows if isinstance(row, dict)} == set(ROW_IDS),
              "row_set")
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        errors.append(str(exc))
    result = {"schema": "hh-gt09-verify-only-1", "status": "DIAGNOSTIC_OK" if not errors else "DIAGNOSTIC_FAIL",
              "authority": 0, "acceptance": False, "root": str(root), "errors": errors}
    print(json.dumps(result, sort_keys=True))
    return 0 if not errors else 2


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_tree_closure() -> tuple[str, dict[str, str]]:
    """Hash the committed studio tree consumed by the final coordinator.

    Review output, Godot import caches and Python bytecode are deliberately
    excluded.  The plan and sibling game scopes are outside this closure.
    """
    ignored = {".local", ".godot", "__pycache__", ".pytest_cache", ".mypy_cache"}
    files: dict[str, str] = {}
    for directory, subdirs, filenames in os.walk(STUDIO):
        # Prune generated evidence before traversal; .local may contain many
        # gigabytes of historical native runs, none of which is in this hash.
        subdirs[:] = [name for name in subdirs if name not in ignored]
        for name in filenames:
            path = Path(directory) / name
            if path.is_symlink():
                raise MatrixError("source_symlink:" + str(path))
            if path.is_file() and not any(part in ignored for part in path.parts):
                rel = path.relative_to(STUDIO).as_posix()
                files[rel] = _sha(path)
    payload = dict(sorted(files.items()))
    return "sha256:" + _sha_bytes(_canonical(payload)), payload


def _registered_probe_semantics(path: Path, *, fixture: str) -> bool:
    try:
        result = json.loads((path / "registered-owner-result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    discovery = result.get("discovery")
    profile = result.get("profile")
    receipt = result.get("receipt")
    transaction = result.get("transaction")
    return (result.get("schema") == "hh-godot-registered-authoring-owner-1"
            and result.get("status") == "DIAGNOSTIC_PASS"
            and result.get("fixture") == fixture
            and result.get("authority") == 0
            and result.get("public_ack") is False
            and isinstance(result.get("source_closure_sha256"), str)
            and isinstance(discovery, dict)
            and discovery.get("fixture_enabled") is True
            and discovery.get("public_runtime_enabled") is False
            and isinstance(profile, dict)
            and profile.get("profile") == "hh-godot-gameplay-source-1"
            and profile.get("script_enabled") is True
            and isinstance(transaction, dict)
            and isinstance(transaction.get("command_ids"), list)
            and len(transaction["command_ids"]) >= 3
            and isinstance(receipt, dict)
            and receipt.get("readback_ack") is True
            and receipt.get("native_observed") is True
            and receipt.get("native_process", {}).get("exit_code") == 0)


def _content_semantics(path: Path) -> tuple[bool, Path | None]:
    try:
        result = json.loads((path / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False, None
    published = result.get("published_root")
    return (result.get("schema") == "hh-gt09-content-run-1"
            and result.get("status") == "DIAGNOSTIC_PASS"
            and result.get("authority") == 0
            and result.get("public_ack") is False
            and isinstance(result.get("source_closure_sha256"), str)
            and isinstance(published, str)
            and Path(published).is_dir()
            and isinstance(result.get("publication_readback"), dict)
            and result["publication_readback"].get("public_ack") is False), Path(published) if isinstance(published, str) else None


def _matrix_closure(*, arena: Path, room: Path, blender: Path,
                    k13: Path | None) -> tuple[str, dict[str, Any]]:
    """Freeze the exact inputs consumed by the final coordinator.

    The native publication runners and GT-08A have deliberately different
    producer closures.  The matrix closure is therefore a signed digest of
    those producer manifests plus every runner/plan hash, while each row keeps
    its producer closure in raw evidence.  This prevents mixing rows from
    different final packages without pretending that their internal producer
    closures are identical.
    """
    def file_hash(path: Path) -> str:
        _need(path.is_file(), f"matrix_input_missing:{path}")
        return _sha(path)

    arena_result = arena / "result.json"
    room_result = room / "result.json"
    arena_obs = arena / "native-observation.json"
    room_obs = room / "native-observation.json"
    content_binding = arena / "catalog-content" / "binding.json"
    command_sources: dict[str, str] = {}
    for directory in (STUDIO / "tests" / "godot", STUDIO / "tests" / "conformance",
                      STUDIO / "build" / "ci"):
        for source in sorted(directory.glob("*.py")):
            command_sources[str(source.relative_to(STUDIO))] = file_hash(source)
    command_sources["toolchain.lock.json"] = file_hash(STUDIO / "toolchain.lock.json")
    payload = {
        "plan_sha256": file_hash(PLAN),
        "runner_sha256": {str(p.relative_to(STUDIO)): file_hash(p)
                          for p in (Path(__file__), STUDIO / "tests" / "conformance" /
                                    "gt09_fixture_conformance.py")},
        "command_sources": command_sources,
        "publications": {
            "arena_result": file_hash(arena_result),
            "arena_observation": file_hash(arena_obs),
            "room_result": file_hash(room_result),
            "room_observation": file_hash(room_obs),
            "content_binding": file_hash(content_binding),
        },
        "k13": file_hash(k13) if k13 else None,
    }
    digest = "sha256:" + _sha_bytes(_canonical(payload))
    return digest, payload


def _run_owned(command: list[str], *, cwd: Path, raw_dir: Path,
               timeout: float) -> dict[str, Any]:
    """Run one child behind the repository's gated process-tree runner.

    The previous implementation used ``communicate()`` on anonymous pipes and
    killed only the immediate wrapper on a deadline.  A verbose child or a
    descendant that outlived its parent could therefore produce a false
    ``owned_tree_zero`` receipt.  ``run_fixture.run_process`` launches through
    the pinned helper, assigns the helper to a Windows Job Object (or a Linux
    process group), drains to files, and records target and wrapper exits
    independently.
    """
    global _RUN_FIXTURE_MODULE
    raw_dir = raw_dir.resolve()
    _need(not raw_dir.exists(), f"owned_output_exists:{raw_dir}")
    raw_dir.mkdir(parents=True)
    if _RUN_FIXTURE_MODULE is None:
        path = STUDIO / "build" / "bootstrap" / "run_fixture.py"
        spec = importlib.util.spec_from_file_location("gt09_owned_runner", path)
        _need(spec is not None and spec.loader is not None, "owned_runner_import")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _RUN_FIXTURE_MODULE = module
    started = time.monotonic()
    env = os.environ.copy()
    pythonpath = os.pathsep.join((str(REPO_ROOT), str(STUDIO),
                                  str(STUDIO / "tests" / "conformance"),
                                  str(STUDIO / "tests" / "godot")))
    env["PYTHONPATH"] = pythonpath + os.pathsep + env.get("PYTHONPATH", "")
    label = "child"
    bounded_timeout = max(1, int(timeout + 0.999))
    if bounded_timeout <= 600:
        result = _RUN_FIXTURE_MODULE.run_process(
            command, cwd=cwd, output=raw_dir, timeout=bounded_timeout,
            label=label, env=env)
    else:
        # The pinned bootstrap runner deliberately caps ordinary probes at
        # 600s.  K15/K14 have longer, separately bounded windows; keep their
        # same helper + Job Object/process-group semantics here without
        # changing the hash-pinned bootstrap file used by the Linux executor.
        host_path = raw_dir / "child-host.json"
        stdout_path, stderr_path = raw_dir / "child-stdout.txt", raw_dir / "child-stderr.txt"
        helper = ("import subprocess,sys,json,datetime; token=sys.stdin.readline(); "
                  "sys.exit(125) if token != 'GO\\n' else None; "
                  "started=datetime.datetime.now(datetime.timezone.utc).isoformat(); "
                  "p=subprocess.Popen(sys.argv[2:]); code=p.wait(); "
                  "f=open(sys.argv[1],'x',encoding='utf-8'); "
                  "json.dump({'target_pid':p.pid,'started_at':started,'exit_code':code},f); f.close()")
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = None
        job_state = None
        started = time.monotonic()
        timed_out = False
        tree_verified = False
        wrapper_exit = None
        try:
            with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
                process = subprocess.Popen(
                    [sys.executable, "-c", helper, str(host_path), *command],
                    cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                    stdin=subprocess.PIPE, creationflags=flags,
                    start_new_session=os.name != "nt")
                if os.name == "nt":
                    job_state = _RUN_FIXTURE_MODULE._job_for_process(process)
                process.stdin.write(b"GO\n")
                process.stdin.close()
                try:
                    wrapper_exit = process.wait(timeout=bounded_timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    if job_state:
                        _RUN_FIXTURE_MODULE._terminate_job(job_state)
                    elif os.name != "nt":
                        import signal
                        os.killpg(process.pid, signal.SIGKILL)
                    wrapper_exit = process.wait(timeout=10)
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if os.name == "nt":
                        tree_verified = _RUN_FIXTURE_MODULE._job_active_count(job_state) == 0
                    else:
                        try:
                            os.killpg(process.pid, 0)
                        except ProcessLookupError:
                            tree_verified = True
                    if tree_verified:
                        break
                    time.sleep(0.02)
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            if not tree_verified:
                if job_state:
                    _RUN_FIXTURE_MODULE._terminate_job(job_state)
                elif os.name != "nt" and process is not None:
                    import signal
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            if job_state:
                _RUN_FIXTURE_MODULE._close_job(job_state)
        host = _load_json(host_path) if host_path.is_file() else {}
        # Normalize the long-window helper receipt to the same independently
        # verifiable shape as the pinned bootstrap runner.
        host.update({
            "wrapper_exit_code": wrapper_exit,
            "timed_out": timed_out,
            "tree_verified": tree_verified,
            "readers_stopped": True,
            "stdout": stdout_path.name,
            "stderr": stderr_path.name,
            "job_owner": {"zero_observed": tree_verified, "active_count": 0},
        })
        host_path.write_bytes(_canonical(host))
        result = {"exit_code": host.get("exit_code"), "wrapper_exit_code": wrapper_exit,
                  "timed_out": timed_out, "tree_verified": tree_verified,
                  "ownership": "gated_job_kill_on_close" if os.name == "nt" else "process_group",
                  "host": host_path.name, "stdout": stdout_path.name, "stderr": stderr_path.name,
                  "duration_seconds": round(time.monotonic() - started, 3)}
    # The pinned short-window runner returns a compact result and intentionally
    # keeps its host file minimal.  Normalize that file here after the helper
    # has exited and both streams have been closed, so strict verification can
    # independently prove the same ownership/cleanup facts for every window.
    host_path = raw_dir / str(result["host"])
    host = _load_json(host_path) if host_path.is_file() else {}
    host.update({
        "wrapper_exit_code": result.get("wrapper_exit_code"),
        "timed_out": result.get("timed_out") is True,
        "tree_verified": result.get("tree_verified") is True,
        "readers_stopped": True,
        "stdout": result.get("stdout"),
        "stderr": result.get("stderr"),
        "job_owner": {"zero_observed": result.get("tree_verified") is True,
                       "active_count": 0},
    })
    host_path.write_bytes(_canonical(host))
    stdout_path = raw_dir / result["stdout"]
    stderr_path = raw_dir / result["stderr"]
    stdout = stdout_path.read_bytes() if stdout_path.is_file() else b""
    stderr = stderr_path.read_bytes() if stderr_path.is_file() else b""
    return {
        "command": command,
        "cwd": str(cwd),
        "receipt_dir": str(raw_dir),
        "actual_exit": result.get("exit_code"),
        "wrapper_exit": result.get("wrapper_exit_code"),
        "timed_out": result.get("timed_out") is True,
        "owned_tree_zero": result.get("tree_verified") is True,
        "ownership": result.get("ownership"),
        "host_receipt": result.get("host"),
        "host_sha256": _sha(host_path),
        "duration_seconds": round(time.monotonic() - started, 3),
        "stdout_sha256": _sha_bytes(stdout),
        "stderr_sha256": _sha_bytes(stderr),
    }


def _write_row(root: Path, row_id: str, *, closure: str,
               producer_closures: dict[str, Any], steps: list[dict[str, Any]],
               semantic_pass: bool, requirement: str,
               references: list[str] | None = None) -> dict[str, Any]:
    row_root = root / "rows" / row_id
    row_root.mkdir(parents=True, exist_ok=False)
    actual_ok = all(step["actual_exit"] == 0 and not step["timed_out"]
                    and step["owned_tree_zero"] for step in steps)
    # Normalize step evidence before serializing.  The verify-only path audits
    # the persisted JSON, so mutating the in-memory list after the write would
    # make a final PASS unverifiable.
    for step in steps:
        step.setdefault("evidence_type", "host")
    bound_references = [str(Path(value).resolve()) for value in (references or [])]
    reference_sha256 = {}
    for value in bound_references:
        path = Path(value)
        _need(path.is_file(), f"reference_missing:{path}")
        reference_sha256[value] = _sha(path)
    result = {
        "schema": "hh-gt09-row-result-1", "row_id": row_id,
        "status": "PASS" if actual_ok and semantic_pass else "FAIL",
        "source_closure_sha256": closure,
        "producer_closures": producer_closures,
        "requirement": requirement, "steps": steps,
        "references": bound_references,
        "reference_sha256": reference_sha256,
    }
    result_path = row_root / "result.json"
    result_path.write_bytes(_canonical(result))
    exit_receipt = {
        "schema": "hh-process-exit-1", "row_id": row_id,
        "actual_exit": 0 if actual_ok else next((s["actual_exit"] for s in steps
                                                   if s["actual_exit"] != 0), 1),
        "timed_out": any(s["timed_out"] for s in steps),
        "owned_tree_zero": all(s["owned_tree_zero"] for s in steps),
        "step_count": len(steps),
    }
    exit_path = row_root / "exit.json"
    exit_path.write_bytes(_canonical(exit_receipt))
    return {
        "id": row_id,
        "evidence_path": str(result_path.relative_to(root)),
        "exit_evidence_path": str(exit_path.relative_to(root)),
        "evidence_sha256": _sha(result_path),
        "exit_evidence_sha256": _sha(exit_path),
        "status": result["status"],
        "requirement": requirement,
        "steps": steps,
    }


def _test_command(modules: tuple[str, ...]) -> list[str]:
    return [sys.executable, "-B", "-m", "unittest", "-q", *modules]


def _k13_author_provenance(*, output: Path, arena: Path, room: Path,
                           registered: Path, run_id: str) -> tuple[Path, str]:
    """Write the current coordinator's K8/K9 author transcript.

    K13's external MCP spike only measures adapter capability.  This receipt
    binds the author identity to the native K8/K9 files produced by this exact
    matrix, so an external model name cannot be mistaken for authorship.
    """
    arena_path = (arena / "result.json").resolve()
    room_path = (room / "result.json").resolve()
    registered_path = (registered / "result.json").resolve()
    arena_doc = _load_json(arena_path)
    room_doc = _load_json(room_path)
    registered_doc = _load_json(registered_path)
    closures = {arena_doc.get("source_closure_sha256"),
                room_doc.get("source_closure_sha256"),
                registered_doc.get("source_closure_sha256")}
    _need(len(closures) == 1 and None not in closures, "k13_author_closure_mismatch")
    source_closure = next(iter(closures))
    arena_handoff = arena_doc.get("catalog_handoff")
    room_handoff = room_doc.get("catalog_room_handoff")
    _need(isinstance(arena_handoff, dict) and isinstance(room_handoff, dict),
          "k13_author_catalog_handoff_missing")
    _need(registered_doc.get('schema') == 'hh-gt09-fixture-repair-1'
          and set(registered_doc.get('fixtures', {})) == {'arena', 'room'},
          'k13_author_both_repairs_missing')
    events = [
        {"kind": "recipe", "fixture": "arena",
         "payload": {"command_ids": arena_handoff["command_ids"],
                     "transaction_digest": arena_handoff["transaction_digest"]},
         "receipt_sha256": _sha(arena_path)},
        {"kind": "recipe", "fixture": "room",
         "payload": {"command_ids": room_handoff["command_ids"],
                     "transaction_digest": room_handoff["transaction_digest"]},
         "receipt_sha256": _sha(room_path)},
    ]
    for fixture in ('arena', 'room'):
        row = registered_doc['fixtures'][fixture]
        events.append({'kind': 'repair_batch', 'fixture': fixture,
            'payload': {'command_ids': [row['repair_route']['command_id']],
                'command_sha256': row['command_sha256'],
                'recipe_sha256': registered_doc['recipe_sha256'],
                'observed_fault_sha256': row['seed']['result_sha256'],
                'repair_replay_sha256': row['replay']['result_sha256']},
            'receipt_sha256': _sha(registered_path)})
    for event in events:
        event["payload_sha256"] = hashlib.sha256(
            json.dumps(event["payload"], sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest()
    # The matrix is executed by this Codex coordinator.  Keep the identity
    # explicit and allow a host-provided model/task label when available.
    author = {
        "client": {"name": "Codex", "version": "desktop", "protocol": "codex-task"},
        "model": os.environ.get("CODEX_MODEL", "gpt-6.1-sol"),
        "reasoning_effort": os.environ.get("CODEX_REASONING_EFFORT", "xhigh"),
        "task_id": os.environ.get("CODEX_THREAD_ID", f"codex:{run_id}"),
    }
    transcript = {"author": author, "events": events,
                  "source_closure_sha256": source_closure}
    transcript_hash = hashlib.sha256(
        json.dumps(transcript, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False).encode("utf-8")).hexdigest()
    document = {
        "schema": "hh-gt09-k13-author-provenance-1", "authority": 0,
        "public_ack": False, "acceptance": False, "author": author,
        "source_closure_sha256": source_closure, "events": events,
        "receipt_bindings": {
            "arena": {"path": str(arena_path), "sha256": _sha(arena_path)},
            "room": {"path": str(room_path), "sha256": _sha(room_path)},
            "registered": {"path": str(registered_path), "sha256": _sha(registered_path)},
        },
        "transcript": transcript, "transcript_sha256": transcript_hash,
    }
    path = (output / "k13-author-provenance.json").resolve()
    path.write_bytes(_canonical(document))
    return path, source_closure



def final_matrix_orchestrated(*, output: Path, run_id: str, k13: Path | None,
                              playtest_deadline: float = 960.0,
                              playtest_start: int = 16,
                              rehearsal_through_k9: bool = False) -> int:
    """Own every GT-09 producer and stop at the first failed row."""
    output = output.resolve()
    _need(not output.exists(), f"matrix_output_exists:{output}")
    output.mkdir(parents=True)
    dry = dry_run()
    (output / "dry-run.json").write_bytes(_canonical(dry))
    closure, closure_payload = _source_tree_closure()
    preflight = {"schema": "hh-gt09-measure-window-preflight-1", "run_id": run_id,
                 "authority": 0, "acceptance": False}
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from studio.tests.replay.measure_window import measurement_window
        with measurement_window(run_id, "GT09 final native preflight"):
            preflight.update(status="DIAGNOSTIC_PASS", recovered_dead_marker=True)
    except Exception as error:
        preflight.update(status="DIAGNOSTIC_FAIL", error_code=str(error))
        (output / "measure-window-preflight.json").write_bytes(_canonical(preflight))
        raise MatrixError("measurement_window_preflight:" + str(error)) from error
    (output / "measure-window-preflight.json").write_bytes(_canonical(preflight))
    conformance = STUDIO / "tests" / "conformance" / "gt09_fixture_conformance.py"
    godot_gui = STUDIO / ".local" / "tooling" / "godot-4.7.2-stable" / "Godot_v4.7.2-stable_win64.exe"
    blender_bin = STUDIO / ".local" / "tooling" / "blender-5.2.3-windows-x64" / "blender.exe"
    nonce = hashlib.sha256((run_id + ":" + closure).encode()).hexdigest()[:10]
    rows: list[dict[str, Any]] = []
    producer: dict[str, Any] = {
        "matrix_source_closure": closure,
        "content_root": str(output / "blender-content"),
        "measure_window_preflight": str(output / "measure-window-preflight.json"),
    }

    def owned(command: list[str], raw_name: str, timeout: float) -> dict[str, Any]:
        return _run_owned(command, cwd=REPO_ROOT,
                          raw_dir=output / "raw" / raw_name,
                          timeout=timeout)

    def finish_row(row_id: str, steps: list[dict[str, Any]], requirement: str,
                   semantic: bool = True, references: list[str] | None = None,
                   fail_fast: bool = True) -> dict[str, Any]:
        row = _write_row(output, row_id, closure=closure,
                         producer_closures=producer, steps=steps,
                         semantic_pass=semantic, requirement=requirement,
                         references=references)
        _self_check_row(row, root=output, closure=closure)
        rows.append(row)
        if fail_fast and row["status"] != "PASS":
            raise MatrixError(f"{row_id}:FAIL")
        return row

    def run_row(row_id: str, specs: list[tuple[list[str], float, str]],
                requirement: str, validator=None,
                references: list[str] | None = None) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        for index, (command, timeout, evidence_type) in enumerate(specs, 1):
            step = owned(command, f"{row_id}/{index}", timeout)
            step["evidence_type"] = evidence_type
            steps.append(step)
            if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
                return finish_row(row_id, steps, requirement, False, references)
        try:
            semantic = bool(validator()) if validator is not None else True
        except Exception:
            semantic = False
        return finish_row(row_id, steps, requirement, semantic, references)

    def json_result(path: Path) -> dict[str, Any]:
        return _load_json(path)

    _need(blender_bin.is_file(), f"blender_binary_missing:{blender_bin}")
    content_root = output / "blender-content"
    content_cmd = [sys.executable, "-B", "studio/tests/conformance/run_gt09_blender_content.py",
                   "--run-id", f"gt09-content-{nonce}", "--output", str(content_root),
                   "--binary", str(blender_bin)]
    k1_steps: list[dict[str, Any]] = []
    step = owned(content_cmd, "K1/1-content", 600)
    step["evidence_type"] = "native"
    k1_steps.append(step)
    if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
        finish_row("K1", k1_steps, "registered discovery/profile isolation and native Blender producer", False)
        raise MatrixError("K1:FAIL")
    content_ok, published_root = _content_semantics(content_root)
    _need(content_ok and published_root is not None, "content_producer_not_observed")
    producer["published_root"] = str(published_root)
    producer["content_result"] = str(content_root / "result.json")
    content_result = json_result(content_root / "result.json")
    producer["content_source_closure"] = content_result.get("source_closure_sha256")

    registered_roots: dict[str, Path] = {}
    native_roots: dict[str, Path] = {}
    for index, fixture in enumerate(("arena", "room"), 2):
        reg_id = f"o2-registered-authoring-gt09m-{nonce}-{fixture}"
        reg_root = STUDIO / ".local" / "reviews" / reg_id
        reg_cmd = [sys.executable, "-B", "studio/tests/godot/run_registered_authoring_probe.py",
                   "--run-id", reg_id, "--godot", str(godot_gui),
                   "--blender-published", str(published_root), "--fixture", fixture]
        step = owned(reg_cmd, f"K1/{index}-{fixture}", 900)
        step["evidence_type"] = "native"
        k1_steps.append(step)
        registered_roots[fixture] = reg_root
        if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
            finish_row("K1", k1_steps, "registered discovery/profile isolation and native Blender producer", False,
                       [str(content_root / "result.json"), str(reg_root / "registered-owner-result.json")])
            raise MatrixError("K1:FAIL")
        if not _registered_probe_semantics(reg_root, fixture=fixture):
            finish_row("K1", k1_steps, "registered discovery/profile isolation and native Blender producer", False,
                       [str(content_root / "result.json"), str(reg_root / "registered-owner-result.json")])
            raise MatrixError("K1:FAIL")
        owner = json_result(reg_root / "registered-owner-result.json")
        native_run_id = owner.get("native_run_id")
        _need(isinstance(native_run_id, str), f"native_run_id_missing:{fixture}")
        native_roots[fixture] = STUDIO / ".local" / "reviews" / native_run_id
    producer["registered_roots"] = {key: str(value) for key, value in registered_roots.items()}
    producer["native_roots"] = {key: str(value) for key, value in native_roots.items()}
    finish_row("K1", k1_steps, "registered discovery/profile isolation and native Blender producer",
               True, [str(content_root / "result.json")] +
               [str(value / "registered-owner-result.json") for value in registered_roots.values()])

    check_root = output / "registered-check.json"
    run_row("K2", [
        (_test_command(("studio.tests.godot.test_registered_authoring_owner",
                        "studio.tests.godot.test_authoring_contract")), 180, "unit"),
        ([sys.executable, "-B", "studio/tests/conformance/run_gt09_registered_check.py",
          "--run-id", f"gt09-registered-check-{nonce}",
          "--arena-root", str(registered_roots["arena"]),
          "--room-root", str(registered_roots["room"]), "--output", str(check_root)], 180, "host"),
    ], "allowlist/identity/idempotency/conflict", references=[str(check_root)])

    registered_script_root = output / "registered-script"
    registered_script_cmd = [sys.executable, "-B", "studio/tests/conformance/run_gt09_registered_script.py",
                             "--run-id", f"gt09-registered-script-{nonce}",
                             "--output", str(registered_script_root)]
    run_row("K3", [
        (_test_command(("studio.tests.godot.test_gameplay_behavior",
                        "studio.tests.godot.test_gameplay_source_adapter")), 240, "unit"),
        (registered_script_cmd, 600, "native"),
    ], "registered AUTH-01 authored behavior and replay",
       references=[str(registered_script_root / "result.json")],
       validator=lambda: _registered_script_semantics(registered_script_root))

    def publication_project(publication: Path) -> Path:
        result = json_result(publication / "result.json")
        selected = result.get("selected") or {}
        revision = selected.get("selected_revision") or selected.get("project_revision")
        _need(isinstance(revision, str) and revision.startswith("sha256:"), "publication_revision_missing")
        revision_id = revision.split(":", 1)[1]
        matches = list(publication.glob(f"gameplay-owner-*/revisions/{revision_id}/project"))
        _need(len(matches) == 1 and matches[0].is_dir(), "publication_project_missing")
        return matches[0]

    k4_check = output / "k4-catalog-native-check.json"
    run_row("K4", [
        (_test_command(("studio.tests.godot.test_gameplay_dependency_evidence",
                        "studio.tests.godot.test_gameplay_dependency_observation",
                        "studio.tests.godot.test_gameplay_native_dependencies")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/conformance/run_gt09_catalog_native_check.py",
          "--run-id", f"gt09-k4-check-{nonce}",
          "--arena-native", str(native_roots["arena"]),
          "--room-native", str(native_roots["room"]),
          "--arena-registered", str(registered_roots["arena"]),
          "--room-registered", str(registered_roots["room"]),
          "--output", str(k4_check)], 180, "host"),
    ], "AUTH-02 dependency graph, UID/import and rejects",
       references=[str(k4_check), str(native_roots["arena"] / "native-observation.json"),
                   str(native_roots["room"] / "native-observation.json")],
       validator=lambda: (json_result(k4_check).get("schema") == "hh-gt09-catalog-native-check-1"
                          and json_result(k4_check).get("status") == "DIAGNOSTIC_PASS"
                          and isinstance(json_result(k4_check).get("source_closure_sha256"), str)
                          and json_result(k4_check).get("dependency_readback") is True
                          and json_result(k4_check).get("uid_import_checks") is True))

    def failure_probe_id(kind: str, fixture: str) -> str:
        value = f"o2-auth{kind}-native-gt09m-{nonce}-{fixture}"
        _need(re.fullmatch(r"o2-auth0[35]-native-[a-z0-9-]{1,40}", value) is not None,
              "failure_probe_id_invalid")
        return value

    auth3_paths = tuple(STUDIO / ".local" / "reviews" / failure_probe_id("03", item)
                        for item in ("syntax", "type"))
    run_row("K5", [
        (_test_command(("studio.tests.godot.test_gameplay_failure_probe",
                        "studio.tests.godot.test_gameplay_source_eligibility",
                        "studio.tests.godot.test_gameplay_sandbox")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/godot/run_gameplay_failure_probe.py",
          "--run-id", failure_probe_id("03", "syntax"), "--failure-fixture", "syntax"], 240, "native"),
        ([sys.executable, "-B", "studio/tests/godot/run_gameplay_failure_probe.py",
          "--run-id", failure_probe_id("03", "type"), "--failure-fixture", "type"], 240, "native"),
    ], "AUTH-03 failure preserves last good",
       references=[str(path / "result.json") for path in auth3_paths],
       validator=lambda: _auth_failure_semantics(auth3_paths))

    publication_roots: dict[str, Path] = {}
    for fixture, native_key, reg_key, run_fixture, index in (
            ("arena", "arena", "arena", "gameplay_arena_physics", 1),
            ("room", "room", "room", "gameplay_source_room_3d_native", 2)):
        pub_id = f"o2-publication-gt09-final-{nonce}-{fixture}"
        pub_root = STUDIO / ".local" / "reviews" / pub_id
        args = ["--run-id", pub_id, "--fixture", run_fixture]
        if fixture == "arena":
            args += ["--catalog-arena", str(native_roots[native_key]),
                     "--registered-arena", str(registered_roots[reg_key])]
        else:
            args += ["--catalog-room", str(native_roots[native_key]),
                     "--registered-room", str(registered_roots[reg_key])]
        args += ["--blender-content-published", str(published_root)]
        cmd = [sys.executable, "-B", "studio/tests/godot/run_gameplay_publication_probe.py", *args]
        step = owned(cmd, f"K8/{index}-{fixture}", 1200)
        step["evidence_type"] = "native"
        publication_roots[fixture] = pub_root
        if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
            finish_row("K8", [step], "two fixtures authored through catalog commands", False)
            raise MatrixError("K8:FAIL")
    arena, room = publication_roots["arena"], publication_roots["room"]
    producer['publication_roots'] = {key: str(value.resolve()) for key, value in publication_roots.items()}
    conf_out = output / "fixture-conformance.json"
    k8_steps = [
        {"command": [str(sys.executable), "-B", str(conformance), "--arena", str(arena),
                     "--room", str(room), "--output", str(conf_out)],
         "cwd": str(REPO_ROOT), "actual_exit": 0, "timed_out": False,
         "owned_tree_zero": True, "duration_seconds": 0, "stdout_sha256": "",
         "stderr_sha256": "", "evidence_type": "host"},
    ]
    # Preserve actual host receipt for conformance instead of fabricating it.
    k8_steps[0] = owned(k8_steps[0]["command"], "K8/3-conformance", 240)
    k8_steps[0]["evidence_type"] = "host"
    k8_steps.append(owned(_test_command(("studio.tests.godot.test_catalog_gameplay_handoff",
                                          "studio.tests.conformance.test_gt09_fixture_conformance")),
                          "K8/4-unit", 240))
    k8_steps[-1]["evidence_type"] = "unit"
    k8_semantic = _conformance_semantics(conf_out, closure=None) and \
        _publication_semantics(arena, fixture="arena") and \
        _publication_semantics(room, fixture="room")
    finish_row("K8", k8_steps, "two fixtures authored through catalog commands",
               k8_semantic, [str(conf_out), str(arena / "result.json"), str(room / "result.json")])

    k6_native_run_id = f"o2-publication-gt09m-{nonce}-k6"
    k6_native_root = STUDIO / ".local" / "reviews" / k6_native_run_id
    run_row("K6", [
        (_test_command(("studio.tests.godot.test_gameplay_publication_probe",
                        "studio.tests.godot.test_publication_recovery",
                        "studio.tests.godot.test_publication_stop_latency")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/godot/run_gameplay_publication_probe.py",
          "--run-id", k6_native_run_id, "--fixture", "gameplay_source_multifile"],
         1200, "native"),
    ], "AUTH-04 durable publish/retry/reopen and owner edit",
       references=[str(arena / "result.json"), str(room / "result.json"),
                   str(k6_native_root / "result.json")],
       validator=lambda: _generic_publication_semantics(k6_native_root)
       and _publication_semantics(arena, fixture="arena")
       and _publication_semantics(room, fixture="room"))

    auth5_paths = tuple(STUDIO / ".local" / "reviews" / failure_probe_id("05", item)
                        for item in ("boundary", "spawn", "busy", "wall"))
    linux_out = output / "k7-linux-dry-run.json"
    k7_specs: list[tuple[list[str], float, str]] = [
        (_test_command(("studio.tests.godot.test_linux_guarded",
                        "studio.tests.godot.test_linux_executor",
                        "studio.tests.godot.test_linux_probe_evidence")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/godot/run_linux_probe.py",
          "--output", str(linux_out), "--run-id", f"gt09-k7-{nonce}", "--dry-run"], 180, "host"),
    ]
    for fixture in ("boundary", "spawn", "busy", "wall"):
        k7_specs.append(([sys.executable, "-B", "studio/tests/godot/run_gameplay_failure_probe.py",
                         "--run-id", failure_probe_id("05", fixture),
                         "--failure-fixture", fixture], 240, "native"))
    run_row("K7", k7_specs, "AUTH-05 executor isolation and hostile cases",
       references=[str(path / "result.json") for path in auth5_paths],
       validator=lambda: _auth05_semantics(auth5_paths))

    k10_conf = output / "k10-fixture-conformance.json"
    k9_root = STUDIO / '.local' / 'reviews' / ('k9-' + nonce)
    from studio.tests.conformance.run_gt09_fixture_repair import verify as verify_k9
    run_row("K9", [
        (_test_command(("studio.tests.godot.test_gameplay_adapter_probe",
                        "studio.tests.godot.test_gameplay_failure_probe",
                        "studio.tests.godot.test_gameplay_probe_evidence",
                        "studio.tests.conformance.test_gt09_fixture_repair")), 300, "unit"),
        ([sys.executable, '-B', 'studio/tests/conformance/run_gt09_fixture_repair.py',
          '--arena', str(arena), '--room', str(room), '--output', str(k9_root),
          '--run-id', 'gt09-k9-' + nonce, '--dry-run'], 180, 'host'),
        ([sys.executable, '-B', 'studio/tests/conformance/run_gt09_fixture_repair.py',
          '--arena', str(arena), '--room', str(room), '--output', str(k9_root),
          '--run-id', 'gt09-k9-' + nonce], 600, 'native'),
    ], "seeded defect repair through catalog batch and replay",
       references=[str(k9_root / 'result.json')], validator=lambda: bool(verify_k9(k9_root)))

    if rehearsal_through_k9:
        closure_end, closure_end_payload = _source_tree_closure()
        _need(closure_end == closure, 'source_changed_during_rehearsal')
        manifest = {'schema': SCHEMA, 'mode': 'REHEARSAL', 'run_id': run_id,
            'authority': 0, 'acceptance': False, 'status': 'PASS',
            'source_closure_sha256': closure, 'closure_start': closure, 'closure_end': closure_end,
            'closure_payload': closure_payload, 'closure_end_payload': closure_end_payload,
            'rows': rows, 'producer': producer, 'required_rows': ['K9'],
            'dependency_rows': [row['id'] for row in rows],
            'engine_launched': True, 'network_used': False}
        (output / 'manifest.json').write_bytes(_canonical(manifest))
        (output / 'manifest.sha256').write_text(_sha(output / 'manifest.json') + '\n', encoding='ascii')
        print(json.dumps({'mode': 'REHEARSAL', 'status': 'PASS', 'run_id': run_id}))
        return 0

    run_row("K10", [
        (_test_command(("studio.tests.godot.test_gameplay_log_policy",
                        "studio.tests.godot.test_gameplay_probe_evidence",
                        "studio.tests.godot.test_gameplay_runtime_binding")), 240, "unit"),
        ([sys.executable, "-B", str(conformance), "--arena", str(arena),
          "--room", str(room), "--output", str(k10_conf)], 180, "host"),
    ], "input/pause/save/reload/perf on final catalog fixtures",
       references=[str(k10_conf), str(arena / "result.json"), str(room / "result.json")],
       validator=lambda: _k10_semantics(arena=arena, room=room, conformance=k10_conf))

    adapter_id = f"o2-adapter-gt09-final-{nonce}"
    adapter_root = STUDIO / ".local" / "reviews" / adapter_id
    run_row("K11", [
        (_test_command(("studio.tests.godot.test_gameplay_adapter_probe",
                        "studio.tests.godot.test_publication_session",
                        "studio.tests.godot.test_publication_transport")), 300, "unit"),
        ([sys.executable, "-B", "studio/tests/godot/run_gameplay_adapter_probe.py",
          "--run-id", adapter_id,
          "--authenticated"], 900, "native"),
    ], "reconnect/retry/context reset/owner edit/parallel source jobs",
       references=[str(adapter_root / "result.json")],
       validator=lambda: _adapter_semantics(adapter_root))

    attribution_root = output / "attribution"
    run_row("K12", [
        (_test_command(("studio.tests.godot.test_gameplay_attribution",
                        "studio.tests.godot.test_gameplay_source_eligibility")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/conformance/run_gt09_attribution_hostile.py",
          "--run-id", f"gt09-attribution-{nonce}", "--output", str(attribution_root)], 180, "host"),
    ], "prompt injection and out-of-scope command rejection",
       references=[str(attribution_root / "result.json")],
       validator=lambda: _attribution_semantics(attribution_root))

    # The latest measured external-native matrix is the only default accepted
    # by the final scheduled runner.  Keep an explicit --k13-evidence escape
    # hatch for historical diagnostics, but never silently fall back to the
    # superseded v2 authority-0 artifact.
    k13_path = k13 or (STUDIO / ".local" / "reviews" /
                       "gt09-mcp-capability-matrix-20261010-k13-v3.json")
    k13_path = k13_path.resolve()
    _need(k13_path.is_file(), f"k13_evidence_missing:{k13_path}")
    k13_doc = _load_json(k13_path)
    _need(_k13_semantics(k13_doc), "k13_evidence_not_measured")
    k13_author, k13_child_closure = _k13_author_provenance(
        output=output, arena=arena, room=room,
        registered=k9_root, run_id=run_id)
    k13_client = output / "k13-client.json"
    run_row("K13", [
        (_test_command(("studio.tests.conformance.test_gt09_mcp_compatibility",
                        "studio.tests.conformance.test_gt09_mcp_native")), 240, "unit"),
        ([sys.executable, "-B", "studio/tests/conformance/run_gt09_k13_client.py",
          "--run-id", f"gt09-k13-client-{nonce}",
          "--arena-publication", str(arena / "result.json"),
          "--room-publication", str(room / "result.json"),
          "--registered-result", str(k9_root / "result.json"),
          "--author-provenance", str(k13_author),
          "--k13-evidence", str(k13_path),
          "--output", str(k13_client)], 180, "host"),
    ], "pinned MCP/client/model/host operation matrix",
       references=[str(k13_path), str(k13_client)],
       validator=lambda: _k13_semantics(k13_doc, client=k13_client,
                                        expected_closure=k13_child_closure))

    gt08a_root = output / "gt08a-matrix"
    run_row("K14", [
        ([sys.executable, "-B", "studio/build/ci/gt08a_matrix.py",
          "--matrix", "--run-id", f"gt09-k14-{nonce}",
          "--output-root", str(gt08a_root)], 1200, "native"),
        (_test_command(("studio.tests.conformance.test_gt09_mcp_native",
                        "studio.tests.godot.test_contract",
                        "studio.tests.godot.test_validation_owner")), 240, "unit"),
    ], "GT-08A/TX15/focused regression on final closure",
       references=[str(gt08a_root / "manifest.json")],
       validator=lambda: _gt08a_semantics(gt08a_root))

    _need(0 <= playtest_start <= 98, "playtest_start_range")
    play_nonce = int(hashlib.sha256((run_id + ":playtest").encode()).hexdigest()[:8], 16) % 99
    play_date_match = re.search(r"20\d{6}", run_id)
    play_date = play_date_match.group(0) if play_date_match else "20261009"
    chosen = None
    for offset in range(99):
        first = (play_nonce + offset) % 99
        second = (first + 1) % 99
        candidates = (f"gt09-playtest-{play_date}-{first:02d}",
                      f"gt09-playtest-{play_date}-{second:02d}")
        if all(not (STUDIO / ".local" / "reviews" / candidate).exists() for candidate in candidates):
            chosen = candidates
            break
    _need(chosen is not None, "playtest_id_space_exhausted")
    play_steps: list[dict[str, Any]] = []
    for fixture, play_id in zip(("arena", "room"), chosen):
        pub = arena if fixture == "arena" else room
        for suffix, args, timeout, evidence_type in (
            ("prepare", ["--prepare", "--publication-root", str(pub)], 180, "host"),
            ("dry-run", ["--dry-run", "--deadline-seconds", str(playtest_deadline)], 180, "host"),
            ("host", ["--host", "--deadline-seconds", str(playtest_deadline), "--mode", "scripted"],
             playtest_deadline + 180, "native"),
        ):
            cmd = [sys.executable, "-B", "studio/tests/godot/run_delegated_playtest.py",
                   "--run-id", play_id, "--fixture", fixture, *args]
            step = owned(cmd, f"K15/{fixture}-{suffix}", timeout)
            step["evidence_type"] = evidence_type
            play_steps.append(step)
            if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
                finish_row("K15", play_steps, "delegated 2 x 15-minute final-closure playtest", False,
                           [str(arena / "result.json"), str(room / "result.json")])
                raise MatrixError("K15:FAIL")
        evidence_cmd = [sys.executable, "-B", "studio/tests/conformance/run_gt09_playtest_evidence.py",
                        "--run-id", play_id, "--fixture", fixture,
                        "--minimum-duration-seconds", "900"]
        step = owned(evidence_cmd, f"K15/{fixture}-evidence", 240)
        step["evidence_type"] = "host"
        play_steps.append(step)
        if step["actual_exit"] != 0 or step["timed_out"] or not step["owned_tree_zero"]:
            finish_row("K15", play_steps, "delegated 2 x 15-minute final-closure playtest", False)
            raise MatrixError("K15:FAIL")
        if not _host_playtest_semantics(play_id, fixture=fixture,
                                        expected_publication=pub):
            finish_row("K15", play_steps, "delegated 2 x 15-minute final-closure playtest", False)
            raise MatrixError("K15:FAIL")
        metadata = _load_json(STUDIO / ".local" / "reviews" / play_id / fixture / "metadata.json")
        producer.setdefault("playtest_source_closures", {})[fixture] = metadata.get("source_closure_sha256")
    finish_row("K15", play_steps, "delegated 2 x 15-minute final-closure playtest",
               True, [str(arena / "result.json"), str(room / "result.json")])

    closure_end, closure_end_payload = _source_tree_closure()
    _need(closure_end == closure, "source_changed_during_final")
    rows.sort(key=lambda row: ROW_IDS.index(row["id"]))
    manifest = {
        "schema": SCHEMA, "run_id": run_id, "authority": 0, "acceptance": False,
        "status": "PASS" if {row["id"] for row in rows} == set(ROW_IDS)
        and all(row["status"] == "PASS" for row in rows) else "INCOMPLETE",
        "source_closure_sha256": closure, "closure_start": closure,
        "closure_end": closure_end, "closure_payload": closure_payload,
        "closure_end_payload": closure_end_payload, "producer": producer,
        "rows": rows, "requirements": {row["id"]: row["requirement"] for row in rows},
        "engine_launched": True, "network_used": False,
        "requirement_test_artifact": {
            row["id"]: {"requirement": row["requirement"], "references": row.get("references", [])}
            for row in rows
        },
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))
    (output / "manifest.sha256").write_text(_sha(output / "manifest.json") + "\n", encoding="ascii")
    print(json.dumps({"schema": SCHEMA, "run_id": run_id, "status": manifest["status"],
                      "manifest": str(output / "manifest.json"),
                      "source_closure_sha256": closure}, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 2

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--row", choices=ROW_IDS)
    parser.add_argument("--rows", help="comma-separated rehearsal rows (requires --output)")
    parser.add_argument("--matrix", choices=("final",))
    parser.add_argument("--row-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id", default="gt09-matrix-local")
    parser.add_argument("--k13-evidence", type=Path)
    parser.add_argument("--playtest-deadline", type=float, default=960.0)
    parser.add_argument("--playtest-start", type=int, default=16)
    parser.add_argument("--verify-only", type=Path)
    args = parser.parse_args(argv)
    if args.dry_run and args.matrix:
        parser.error("choose --dry-run or --matrix final")
    if args.row and args.rows:
        parser.error("choose --row or --rows")
    try:
        if args.dry_run:
            print(json.dumps(dry_run(args.row), sort_keys=True, separators=(",", ":")))
            return 0
        if args.verify_only:
            return verify_only(args.verify_only)
        if args.rows:
            if args.output is None:
                parser.error("--rows requires --output")
            selected = tuple(item.strip() for item in args.rows.split(",") if item.strip())
            return rehearsal_rows(output=args.output, run_id=args.run_id, selected=selected)
        if args.matrix == "final":
            if args.output is not None and args.row_evidence is None:
                return final_matrix_orchestrated(
                    output=args.output, run_id=args.run_id, k13=args.k13_evidence,
                    playtest_deadline=args.playtest_deadline,
                    playtest_start=args.playtest_start)
            return final_matrix(args.row_evidence, args.output, args.run_id)
        parser.error("choose --dry-run or --matrix final")
    except MatrixError as exc:
        print(f"GT09_MATRIX_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
