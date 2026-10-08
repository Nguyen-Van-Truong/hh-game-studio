"""Single fail-closed GT-09 K1-K15 matrix coordinator.

The dry-run freezes the row table and validates that every referenced runner is
present without starting Godot, Blender, Docker, MCP, or a long playtest.
``--matrix final`` only assembles rows that already have explicit PASS evidence
on one source closure; it never turns a diagnostic banner into a PASS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
REPO_ROOT = STUDIO.parent
PLAN = STUDIO.parent / "zdoc" / "8-9-godot-blender-agent-studio-plan.txt"
SCHEMA = "hh-gt09-matrix-1"
ROW_IDS = tuple(f"K{i}" for i in range(1, 16))

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
    "K9": {"gate": "seeded defect repair through catalog batch and replay", "runner": "tests/godot/run_registered_authoring_probe.py", "status": "OPEN"},
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


def _safe_review_path(path: Path, *, root: Path) -> Path:
    """Resolve a receipt only inside this matrix's review directory."""
    value = path if path.is_absolute() else root / path
    value = value.resolve()
    _need(value.is_relative_to(root.resolve()), "evidence_path_outside_review")
    _need(value.is_file(), f"evidence_missing:{value.name}")
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


def _native_result(prefix: str, *, closure: str | None = None,
                   required: tuple[str, ...] = ()) -> tuple[Path, dict[str, Any]] | None:
    """Select the newest clean native diagnostic for ``prefix``.

    Selection is deterministic (mtime then name) and rejects stale/failed
    diagnostics.  ``source_closure_sha256`` is compared when the producer
    supplied one, so a later source change cannot silently reuse an old run.
    """
    root = STUDIO / ".local" / "reviews"
    candidates: list[tuple[float, str, Path, dict[str, Any]]] = []
    for directory in root.glob(prefix + "*"):
        result_path = directory / "result.json"
        if not result_path.is_file():
            continue
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if type(result) is not dict or result.get("status") != "DIAGNOSTIC_PASS":
            continue
        if closure is not None and result.get("source_closure_sha256") not in (None, closure):
            continue
        if any(result.get(field) is not True for field in required):
            continue
        candidates.append((result_path.stat().st_mtime, directory.name, result_path, result))
    if not candidates:
        return None
    _, _, path, result = max(candidates, key=lambda item: (item[0], item[1]))
    return path, result


def _auth_failure_semantics(closure: str | None) -> bool:
    """Require both independent AUTH-03 native reject fixtures and durable state."""
    found: list[dict[str, Any]] = []
    for fixture in ("syntax", "type"):
        candidates: list[tuple[float, dict[str, Any]]] = []
        for path in (STUDIO / ".local" / "reviews").glob("o2-auth03-native-*/result.json"):
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if result.get("failure_fixture") == fixture and result.get("source_closure_sha256") in (None, closure):
                candidates.append((path.stat().st_mtime, result))
        if not candidates:
            return False
        _, result = max(candidates, key=lambda item: item[0])
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
    return len(found) == 2


def _auth05_semantics(closure: str | None) -> bool:
    """Require all four AUTH-05 hostile native cases and supervisor proof."""
    for fixture in ("boundary", "spawn", "busy", "wall"):
        candidates = []
        for path in (STUDIO / ".local" / "reviews").glob("o2-auth05-native-*/result.json"):
            try:
                result = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                continue
            if (result.get("status") == "DIAGNOSTIC_PASS"
                    and result.get("failure_fixture") == fixture
                    and result.get("source_closure_sha256") in (None, closure)):
                candidates.append((path.stat().st_mtime, result))
        if not candidates:
            return False
        _, result = max(candidates, key=lambda item: item[0])
        observation = result.get("bad_observation")
        if (result.get("bad_rejected") is not True
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
    return True


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


def _host_playtest_semantics(run_id: str, *, fixture: str, minimum_seconds: float = 900.0) -> bool:
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


def _adapter_semantics(*, closure: str | None = None) -> bool:
    hit = _native_result("o2-adapter-", closure=closure)
    if hit is None:
        return False
    _, result = hit
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


def _attribution_semantics() -> bool:
    root = STUDIO / ".local" / "reviews" / "gt09-attribution-hostile-20261007-01"
    result_path = root / "gameplay_source" / "result.json"
    forged_path = root / "gameplay_source_forged_phase" / "result.json"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        forged = json.loads(forged_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    host = result.get("command_host")
    state = result.get("container_state")
    return (result.get("diagnostic_execution_complete") is True
            and result.get("attribution_verified") is True
            and result.get("attribution_harness_unchanged") is True
            and result.get("gameplay_source_envelope_checked") is True
            and result.get("input_unchanged") is True
            and result.get("snapshot_unchanged") is True
            and result.get("owner_record_retained") is False
            and type(host) is dict and host.get("exit_code") == 0
            and type(state) is dict and state.get("ExitCode") == 0
            and forged.get("diagnostic_execution_complete") is False
            and forged.get("log_policy", {}).get("accepted") is False)


def _k13_semantics(doc: dict[str, Any]) -> bool:
    if (doc.get("schema") != "hh-gt09-mcp-capability-matrix-1"
            or doc.get("status") != "EXTERNAL_NATIVE_LIMITS_MEASURED_CLIENT_OPEN"
            or doc.get("authority") != 0 or doc.get("acceptance") is not False):
        return False
    private = doc.get("private_receipt")
    if type(private) is not dict or not isinstance(private.get("path"), str):
        return False
    receipt_path = (REPO_ROOT / private["path"]).resolve()
    if not receipt_path.is_file() or private.get("sha256") != _sha(receipt_path):
        return False
    rows = doc.get("rows")
    if type(rows) is not list or len(rows) < 3:
        return False
    for row in rows:
        if type(row) is not dict or row.get("authority") != 0 or not row.get("id"):
            return False
        receipt = row.get("receipt") or row.get("native_receipt")
        if type(receipt) is dict and receipt.get("path"):
            path = (REPO_ROOT / str(receipt["path"])).resolve()
            if not path.is_file() or receipt.get("sha256") != _sha(path):
                return False
    return True


def _gt08a_semantics(root: Path) -> bool:
    path = root / "manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    rows = value.get("rows")
    return (value.get("status") == "PASS" and value.get("authority") == 0
            and value.get("acceptance") is False and type(rows) is list
            and len(rows) == 18
            and all(type(row) is dict and row.get("status") == "PASS"
                    and row.get("actual_exit") == 0 for row in rows))


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
        if (result.get("native_fixture_observed") is not True
                or result.get("catalog_scene_instantiation_observed") is not True
                or type(files) is not dict
                or "scripts/fixture_lifecycle.gd" not in files):
            return False
    return True


def _registered_script_semantics(path: Path, *, closure: str | None = None,
                                 require_repair: bool = False) -> bool:
    """Validate the native registered controller route and replay checkpoint.

    K3 proves the ordinary registered source publication.  K9 additionally
    requires a deliberately broken source to be rejected by the native host,
    followed by a durable reopen, typed repair and a fresh native replay.
    Those fields are checked from the child receipt rather than inferred from
    the final status banner.
    """
    result_path = path / "result.json"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    checkpoint = result.get("checkpoint")
    route = result.get("registered_route")
    valid = (result.get("schema") == "hh-gt09-registered-script-result-1"
            and result.get("status") == "DIAGNOSTIC_PASS"
            and result.get("authority") == 0 and result.get("acceptance") is False
            and (closure is None or result.get("source_closure_sha256") == closure)
            and result.get("behavior_changed") is True
            and result.get("controller_reaction_readback") is True
            and result.get("same_command_retry") is True
            and result.get("native_run_count") >= 3
            and type(result.get("baseline")) is dict
            and result["baseline"].get("fixture_observed") is True
            and type(result.get("replay")) is dict
            and result["replay"].get("fixture_observed") is True
            and type(route) is dict and route.get("status") in ("READBACK_ACK", "APPLIED")
            and type(checkpoint) is dict
            and checkpoint.get("native_observed") is True
            and checkpoint.get("postcondition_readback") is True
            and checkpoint.get("checkpoint_reload_observed") is True
            and checkpoint.get("replay_hash_equal") is True)
    if not valid or not require_repair:
        return valid
    seed_native = result.get("seed_native")
    repair_route = result.get("repair_route")
    repair_replay = result.get("repair_replay")
    return (result.get("seeded_fault_observed") is True
            and isinstance(result.get("seed_error"), str)
            and isinstance(seed_native, dict)
            and seed_native.get("diagnostic_process_clean") is False
            and isinstance(seed_native.get("command_host"), dict)
            and seed_native["command_host"].get("exit_code") not in (None, 0)
            and result.get("repair_batch_applied") is True
            and result.get("repair_replay_observed") is True
            and result.get("checkpoint_verified") is True
            and isinstance(repair_route, dict)
            and repair_route.get("status") in ("READBACK_ACK", "APPLIED")
            and isinstance(repair_replay, dict)
            and repair_replay.get("fixture_observed") is True
            and result.get("native_run_count") >= 6)


def _verify_row(row: dict[str, Any], *, matrix_root: Path, closure: str | None) -> str:
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
    return child_closure


def final_matrix(row_evidence: Path | None, output: Path | None, run_id: str) -> int:
    _need(row_evidence is not None, "final_requires_row_evidence")
    manifest = load_rows(row_evidence)
    rows = manifest.get("rows")
    _need(type(rows) is list and {r.get("id") for r in rows if isinstance(r, dict)} == set(ROW_IDS),
          "final_requires_all_rows")
    errors: list[str] = []
    closures: set[str] = set()
    matrix_root = row_evidence.parent.resolve()
    for row in rows:
        try:
            closures.add(_verify_row(row, matrix_root=matrix_root,
                                     closure=next(iter(closures), None)))
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


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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
    """Run one child, retaining raw stdout/stderr and the real host exit."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    env = os.environ.copy()
    pythonpath = os.pathsep.join((str(REPO_ROOT), str(STUDIO),
                                  str(STUDIO / "tests" / "conformance"),
                                  str(STUDIO / "tests" / "godot")))
    env["PYTHONPATH"] = pythonpath + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8",
                            errors="replace", creationflags=getattr(subprocess,
                            "CREATE_NO_WINDOW", 0))
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, stderr = proc.communicate(timeout=20)
    (raw_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (raw_dir / "stderr.txt").write_text(stderr, encoding="utf-8")
    return {
        "command": command,
        "cwd": str(cwd),
        "actual_exit": proc.returncode,
        "timed_out": timed_out,
        "owned_tree_zero": proc.poll() is not None,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_sha256": _sha_bytes(stdout.encode("utf-8")),
        "stderr_sha256": _sha_bytes(stderr.encode("utf-8")),
    }


def _write_row(root: Path, row_id: str, *, closure: str,
               producer_closures: dict[str, Any], steps: list[dict[str, Any]],
               semantic_pass: bool, requirement: str,
               references: list[str] | None = None) -> dict[str, Any]:
    row_root = root / "rows" / row_id
    row_root.mkdir(parents=True, exist_ok=False)
    actual_ok = all(step["actual_exit"] == 0 and not step["timed_out"]
                    and step["owned_tree_zero"] for step in steps)
    result = {
        "schema": "hh-gt09-row-result-1", "row_id": row_id,
        "status": "PASS" if actual_ok and semantic_pass else "FAIL",
        "source_closure_sha256": closure,
        "producer_closures": producer_closures,
        "requirement": requirement, "steps": steps,
        "references": references or [],
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


def final_matrix_orchestrated(*, output: Path, run_id: str,
                              arena: Path, room: Path,
                              blender: Path, k13: Path | None,
                              playtest_deadline: float = 960.0,
                              playtest_start: int = 16) -> int:
    """Run K1-K15 sequentially against one coordinator-frozen package."""
    output = output.resolve()
    arena, room, blender = arena.resolve(), room.resolve(), blender.resolve()
    if k13 is not None:
        k13 = k13.resolve()
    _need(not output.exists(), f"matrix_output_exists:{output}")
    _need(arena.is_dir() and room.is_dir() and blender.is_dir(),
          "final_requires_publications")
    output.mkdir(parents=True)
    # The dry-run is a required barrier and is retained in the package.
    dry = dry_run()
    (output / "dry-run.json").write_bytes(_canonical(dry))
    closure, closure_payload = _matrix_closure(arena=arena, room=room,
                                                blender=blender, k13=k13)
    conformance = STUDIO / "tests" / "conformance" / "gt09_fixture_conformance.py"
    blender_root = blender
    godot_gui = STUDIO / ".local" / "tooling" / "godot-4.7.2-stable" / \
        "Godot_v4.7.2-stable_win64.exe"
    blender_arg = str(blender_root)
    arena_arg, room_arg = str(arena), str(room)
    common = {"arena": arena_arg, "room": room_arg}
    rows: list[dict[str, Any]] = []
    producer = {"arena": json.loads((arena / "result.json").read_text(encoding="utf-8")).get("source_closure_sha256"),
                "room": json.loads((room / "result.json").read_text(encoding="utf-8")).get("source_closure_sha256"),
                "blender_manifest": json.loads((arena / "result.json").read_text(encoding="utf-8")).get("blender_content", {}).get("manifest_sha256")}

    def publication_project(publication: Path) -> Path:
        result = json.loads((publication / "result.json").read_text(encoding="utf-8"))
        selected = result.get("selected") or {}
        revision = selected.get("selected_revision") or selected.get("project_revision")
        _need(isinstance(revision, str) and revision.startswith("sha256:"),
              f"publication_revision_missing:{publication}")
        revision_id = revision.split(":", 1)[1]
        matches = list(publication.glob(f"gameplay-owner-*/revisions/{revision_id}/project"))
        _need(len(matches) == 1 and matches[0].is_dir(),
              f"publication_project_missing:{publication}")
        return matches[0]

    arena_project = publication_project(arena)
    room_project = publication_project(room)

    def run_steps(row_id: str, commands: list[tuple[list[str], float]],
                  requirement: str, semantic_pass: bool = True,
                  references: list[str] | None = None,
                  validator=None) -> None:
        steps = []
        for index, (command, timeout) in enumerate(commands, 1):
            steps.append(_run_owned(command, cwd=REPO_ROOT,
                                    raw_dir=output / "raw" / row_id / str(index),
                                    timeout=timeout))
        try:
            semantic_ok = bool(validator()) if validator is not None else bool(semantic_pass)
        except Exception:
            semantic_ok = False
        rows.append(_write_row(output, row_id, closure=closure,
                               producer_closures=producer, steps=steps,
                               semantic_pass=bool(semantic_pass) and semantic_ok,
                               requirement=requirement, references=references))

    # Native failure probes write their own immutable review roots.  Derive a
    # fresh, bounded identifier from this matrix run so retries cannot reuse a
    # prior receipt while keeping the runner's strict ID grammar.
    probe_nonce = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:10]
    def failure_probe_id(kind: str, fixture: str) -> str:
        value = f"o2-auth{kind}-native-gt09m-{probe_nonce}-{fixture}"
        _need(re.fullmatch(r"o2-auth0[35]-native-[a-z0-9-]{1,40}", value) is not None,
              "failure_probe_id_invalid")
        return value

    # K1/K2 are exercised through the registered public route and its focused
    # contract suites.  Dry-run output is a real runner result, not a forged
    # caller field.
    registered = [sys.executable, "-B", "studio/tests/godot/run_registered_authoring_probe.py",
                  "--run-id", f"o2-registered-authoring-gt09m-{probe_nonce}",
                  "--godot", str(godot_gui), "--blender-published", blender_arg,
                  "--fixture", "room", "--dry-run"]
    registered_script_root = output / "registered-script"
    registered_script_id = f"gt09-registered-script-{probe_nonce}"
    registered_script = [sys.executable, "-B", "studio/tests/conformance/run_gt09_registered_script.py",
                         "--run-id", registered_script_id,
                         "--output", str(registered_script_root)]
    run_steps("K1", [(_test_command(("studio.tests.godot.test_registered_authoring_owner",)), 120),
                     (registered, 120)], "registered discovery/profile isolation",
               validator=lambda: _registered_semantics(room, fixture="room"))
    run_steps("K2", [(_test_command(("studio.tests.godot.test_registered_authoring_owner",
                                      "studio.tests.godot.test_authoring_contract")), 120)],
               "allowlist/identity/idempotency/conflict",
               validator=lambda: _registered_semantics(arena, fixture="arena"))
    run_steps("K3", [(_test_command(("studio.tests.godot.test_gameplay_behavior",
                                      "studio.tests.godot.test_gameplay_source_adapter")), 180),
                     ([sys.executable, "-B", str(conformance), "--arena", arena_arg,
                       "--room", room_arg], 120),
                     (registered_script, 420)], "registered behavior/replay",
               references=[str(registered_script_root / "result.json")],
               validator=lambda: _registered_script_semantics(
                   registered_script_root, closure=producer.get("arena")))
    run_steps("K4", [(_test_command(("studio.tests.godot.test_gameplay_dependency_evidence",
                                      "studio.tests.godot.test_gameplay_dependency_observation",
                                      "studio.tests.godot.test_gameplay_native_dependencies")), 180)],
               "static dependency/import/UID admission",
               references=[str(arena / "result.json"), str(room / "result.json")],
               validator=lambda: all(
                   isinstance(json.loads((pub / "result.json").read_text(encoding="utf-8")).get("selected", {}).get("files"), dict)
                   and {"scripts/fixture_actor.gd", "scripts/fixture_dependencies.gd", "scripts/fixture_lifecycle.gd"}
                   .issubset(json.loads((pub / "result.json").read_text(encoding="utf-8")).get("selected", {}).get("files", {}))
                   for pub in (arena, room)))
    k5_commands = [(_test_command(("studio.tests.godot.test_gameplay_failure_probe",
                                   "studio.tests.godot.test_gameplay_source_eligibility",
                                   "studio.tests.godot.test_gameplay_sandbox")), 180)]
    for failure in ("syntax", "type"):
        k5_commands.append(([sys.executable, "-B", "studio/tests/godot/run_gameplay_failure_probe.py",
                             "--run-id", failure_probe_id("03", failure),
                             "--failure-fixture", failure], 180))
    run_steps("K5", k5_commands,
               "failure preservation and hostile rejection",
               references=[failure_probe_id("03", fixture) for fixture in ("syntax", "type")],
               validator=lambda: _auth_failure_semantics(producer.get("arena")))
    run_steps("K6", [(_test_command(("studio.tests.godot.test_gameplay_publication_probe",
                                      "studio.tests.godot.test_publication_recovery",
                                      "studio.tests.godot.test_publication_stop_latency")), 240)],
               "durable publish/retry/reopen",
               references=[str(arena / "result.json"), str(room / "result.json")],
               validator=lambda: _publication_semantics(arena, fixture="arena")
               and _publication_semantics(room, fixture="room"))
    linux_out = output / "k7-linux-dry-run.json"
    k7_commands = [(_test_command(("studio.tests.godot.test_linux_guarded",
                                   "studio.tests.godot.test_linux_executor",
                                   "studio.tests.godot.test_linux_probe_evidence")), 240),
                     ([sys.executable, "-B", "studio/tests/godot/run_linux_probe.py",
                       "--output", str(linux_out), "--run-id", "gt09-matrix-k7",
                       "--dry-run"], 180)]
    for failure in ("boundary", "spawn", "busy", "wall"):
        k7_commands.append(([sys.executable, "-B", "studio/tests/godot/run_gameplay_failure_probe.py",
                             "--run-id", failure_probe_id("05", failure),
                             "--failure-fixture", failure], 180))
    run_steps("K7", k7_commands, "executor isolation/hostile cases",
               references=[failure_probe_id("05", fixture)
                           for fixture in ("boundary", "spawn", "busy", "wall")],
               validator=lambda: _auth05_semantics(producer.get("arena")))
    conf_out = output / "fixture-conformance.json"
    run_steps("K8", [([sys.executable, "-B", str(conformance), "--arena", arena_arg,
                       "--room", room_arg, "--output", str(conf_out)], 120),
                      (_test_command(("studio.tests.godot.test_catalog_gameplay_handoff",
                                      "studio.tests.conformance.test_gt09_fixture_conformance")), 180)],
               "catalog authored room/arena and Blender handoff",
               references=[str(conf_out), str(arena / "result.json"), str(room / "result.json")],
               validator=lambda: _conformance_semantics(conf_out)
               and _publication_semantics(arena, fixture="arena")
               and _publication_semantics(room, fixture="room"))
    run_steps("K9", [(_test_command(("studio.tests.godot.test_gameplay_adapter_probe",
                                      "studio.tests.godot.test_gameplay_failure_probe",
                                      "studio.tests.godot.test_gameplay_probe_evidence")), 240),
                     ([sys.executable, "-B", str(conformance), "--arena", arena_arg,
                       "--room", room_arg], 120)], "seeded repair/batch/replay/checkpoint",
               references=[str(registered_script_root / "result.json")],
               validator=lambda: _registered_script_semantics(
                   registered_script_root, closure=producer.get("arena"),
                   require_repair=True))
    k10_conf_out = output / "k10-fixture-conformance.json"
    run_steps("K10", [(_test_command(("studio.tests.godot.test_gameplay_log_policy",
                                       "studio.tests.godot.test_gameplay_probe_evidence",
                                       "studio.tests.godot.test_gameplay_runtime_binding")), 180),
                      ([sys.executable, "-B", str(conformance), "--arena", arena_arg,
                        "--room", room_arg, "--output", str(k10_conf_out)], 120)],
               "input/pause/save/reload/perf final fixtures",
               references=[str(k10_conf_out), str(arena / "result.json"), str(room / "result.json")],
               validator=lambda: _k10_semantics(arena=arena, room=room,
                                                conformance=k10_conf_out))
    run_steps("K11", [(_test_command(("studio.tests.godot.test_gameplay_adapter_probe",
                                       "studio.tests.godot.test_publication_session",
                                       "studio.tests.godot.test_publication_transport")), 240)],
               "reconnect/retry/context reset/lease",
               validator=lambda: _adapter_semantics())
    run_steps("K12", [(_test_command(("studio.tests.godot.test_gameplay_attribution",
                                       "studio.tests.godot.test_gameplay_source_eligibility")), 180)],
               "prompt injection and out-of-scope rejection",
               validator=_attribution_semantics)
    k13_path = k13 or (STUDIO / ".local" / "reviews" /
                       "gt09-mcp-capability-matrix-20261009-k13.json")
    _need(k13_path.is_file(), f"k13_evidence_missing:{k13_path}")
    k13_doc = _load_json(k13_path)
    _need(_k13_semantics(k13_doc), "k13_evidence_not_measured")
    run_steps("K13", [(_test_command(("studio.tests.conformance.test_gt09_mcp_compatibility",
                                       "studio.tests.conformance.test_gt09_mcp_native")), 240)],
               "MCP/client/model/host capability matrix", references=[str(k13_path)])
    gt08a_root = output / "gt08a-matrix"
    run_steps("K14", [([sys.executable, "-B", "studio/build/ci/gt08a_matrix.py",
                        "--matrix", "--run-id", "gt09-k14-gt08a",
                        "--output-root", str(gt08a_root)], 900),
                      (_test_command(("studio.tests.conformance.test_gt09_mcp_native",
                                      "studio.tests.godot.test_contract",
                                      "studio.tests.godot.test_validation_owner")), 240)],
               "GT-08A/TX15/focused regression",
               references=[str(gt08a_root / "manifest.json")],
               validator=lambda: _gt08a_semantics(gt08a_root))

    # K15 is deliberately last.  It is the only long-running row; host runs
    # are owned by the delegated runner and each gets its own fresh run ID.
    _need(0 <= playtest_start <= 98, "playtest_start_range")
    # The matrix run id is the freshness boundary; never reuse a consumed
    # playtest root merely because a caller picked an old numeric suffix.
    play_nonce = int(hashlib.sha256((run_id + ":playtest").encode("utf-8")).hexdigest()[:8], 16) % 99
    play_date_match = re.search(r"20\d{6}", run_id)
    play_date = play_date_match.group(0) if play_date_match else "20261009"
    # Reserve two adjacent numeric suffixes that have not already been
    # consumed.  The delegated runner intentionally accepts only this compact
    # date/suffix grammar; matrix freshness comes from the hash plus the
    # collision scan inside the review root.
    chosen: tuple[str, str] | None = None
    for offset in range(99):
        first = (play_nonce + offset) % 99
        second = (first + 1) % 99
        candidates = (f"gt09-playtest-{play_date}-{first:02d}",
                      f"gt09-playtest-{play_date}-{second:02d}")
        if all(not (STUDIO / ".local" / "reviews" / candidate).exists()
               for candidate in candidates):
            chosen = candidates
            break
    _need(chosen is not None, "playtest_id_space_exhausted")
    for fixture, play_id in zip(("arena", "room"), chosen):
        run_steps("K15B" if fixture == "room" else "K15A", [
            ([sys.executable, "-B", "studio/tests/godot/run_delegated_playtest.py",
              "--run-id", play_id, "--fixture", fixture, "--prepare",
              "--publication-root", str(arena if fixture == "arena" else room)], 180),
            ([sys.executable, "-B", "studio/tests/godot/run_delegated_playtest.py",
              "--run-id", play_id, "--fixture", fixture, "--dry-run",
              "--deadline-seconds", str(playtest_deadline)], 180),
            ([sys.executable, "-B", "studio/tests/godot/run_delegated_playtest.py",
              "--run-id", play_id, "--fixture", fixture, "--host",
              "--deadline-seconds", str(playtest_deadline), "--mode", "scripted"],
             playtest_deadline + 120),
            ([sys.executable, "-B", "studio/tests/conformance/run_gt09_playtest_evidence.py",
              "--run-id", play_id, "--fixture", fixture,
              "--minimum-duration-seconds", "900"], 180)],
            f"delegated 15-minute {fixture} playtest", references=[play_id],
            validator=lambda play_id=play_id, fixture=fixture: _host_playtest_semantics(
                play_id, fixture=fixture))
    # Collapse K15A/K15 into the required single K15 row only after both host
    # sessions have real exits.  Preserve both raw child rows in the package.
    k15a = rows.pop(-2); k15b = rows.pop(-1)
    k15_steps = k15a["steps"] + k15b["steps"]
    rows.append(_write_row(output, "K15", closure=closure,
                           producer_closures=producer, steps=k15_steps,
                           semantic_pass=(k15a["status"] == "PASS" and k15b["status"] == "PASS"),
                           requirement="delegated 2 x 15-minute final-closure playtest",
                           references=["K15A", "K15B"]))

    manifest = {
        "schema": SCHEMA, "run_id": run_id, "authority": 0,
        "acceptance": False,
        "status": "PASS" if all(row["status"] == "PASS" for row in rows)
        and {row["id"] for row in rows} == set(ROW_IDS) else "INCOMPLETE",
        "source_closure_sha256": closure, "closure_payload": closure_payload,
        "rows": rows, "requirements": {row["id"]: row["requirement"] for row in rows},
        "engine_launched": True, "network_used": False,
    }
    (output / "manifest.json").write_bytes(_canonical(manifest))
    (output / "manifest.sha256").write_text(_sha(output / "manifest.json") + "\n", encoding="ascii")
    print(json.dumps({"schema": SCHEMA, "run_id": run_id,
                      "status": manifest["status"], "manifest": str(output / "manifest.json"),
                      "source_closure_sha256": closure}, sort_keys=True))
    return 0 if manifest["status"] == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--row", choices=ROW_IDS)
    parser.add_argument("--matrix", choices=("final",))
    parser.add_argument("--row-evidence", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id", default="gt09-matrix-local")
    parser.add_argument("--arena-publication", type=Path)
    parser.add_argument("--room-publication", type=Path)
    parser.add_argument("--blender-publication", type=Path)
    parser.add_argument("--k13-evidence", type=Path)
    parser.add_argument("--playtest-deadline", type=float, default=960.0)
    parser.add_argument("--playtest-start", type=int, default=16)
    args = parser.parse_args(argv)
    if args.dry_run and args.matrix:
        parser.error("choose --dry-run or --matrix final")
    try:
        if args.dry_run:
            print(json.dumps(dry_run(args.row), sort_keys=True, separators=(",", ":")))
            return 0
        if args.matrix == "final":
            if args.arena_publication or args.room_publication or args.blender_publication:
                _need(args.arena_publication is not None and args.room_publication is not None
                      and args.blender_publication is not None and args.output is not None,
                      "orchestrated_final_requires_publications_and_output")
                return final_matrix_orchestrated(
                    output=args.output, run_id=args.run_id,
                    arena=args.arena_publication, room=args.room_publication,
                    blender=args.blender_publication, k13=args.k13_evidence,
                    playtest_deadline=args.playtest_deadline,
                    playtest_start=args.playtest_start)
            return final_matrix(args.row_evidence, args.output, args.run_id)
        parser.error("choose --dry-run or --matrix final")
    except MatrixError as exc:
        print(f"GT09_MATRIX_FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
