"""Registered-catalog seeded repair scenario for GT-09 K9 (AUTHORITY=0).

This module orchestrates the existing registered authoring owner.  It consumes
an observed catalog/native snapshot, prepares a typed repair batch, and can
hand that batch to callbacks for native apply, replay, and checkpoint
readback.  It never starts Godot or Blender itself and never treats a static
recipe or child ``PASS`` field as evidence.

Callbacks have these signatures::

    execute(transaction, admission, blender_handoff) -> mapping
    replay(transaction, apply_receipt) -> mapping
    checkpoint(transaction, apply_receipt) -> mapping

``execute`` is passed through ``RegisteredAuthoringOwner.apply`` and must
return the receipt fields validated by that owner.  Missing callbacks leave
the scenario OPEN with a concrete gap.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable, Mapping

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import Request, canonical_bytes, parse_json

OWNER_PATH = STUDIO / "godot-addon" / "registered_authoring_owner.py"
SCHEMA = "hh-gt09-registered-repair-1"
FIXTURES = ("arena", "room")
RUN_ID_RE = re.compile(r"gt09-registered-repair-[a-z0-9-]{1,40}\Z")
REVISION_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REGISTERED_REPAIR_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_OWNER = _load("gt09_registered_repair_owner", OWNER_PATH)


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _need(value: object, code: str) -> None:
    if not value:
        raise ValueError(code)


def _fixture(fixture: str) -> tuple[str, str, str, str, list[int]]:
    _need(fixture in FIXTURES, "REGISTERED_REPAIR_FIXTURE")
    if fixture == "arena":
        return "project.registered.arena", "Node2D", "player", "arena", [32, 174]
    return "project.registered.room", "Node3D", "avatar", "room", [2, 0, 0]


def _snapshot(observed: Mapping[str, Any]) -> dict[str, Any] | None:
    value = observed.get("snapshot")
    if value is None and isinstance(observed.get("snapshots"), Mapping):
        value = observed["snapshots"].get("after_reload") or observed["snapshots"].get("after_apply")
    return _copy(value) if isinstance(value, Mapping) else None


def _find(snapshot: Mapping[str, Any], stable_id: str) -> dict[str, Any] | None:
    for row in snapshot.get("nodes", ()):
        if isinstance(row, Mapping) and row.get("stable_id") == stable_id:
            return row
    return None


def _observe_gate(observed: Mapping[str, Any], fixture: str) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    gaps: list[dict[str, str]] = []
    if not isinstance(observed, Mapping):
        return None, [{"code": "OBSERVATION_SHAPE", "detail": f"{fixture}:producer observation must be an object"}]
    if observed.get("authority") != 0 or observed.get("public_ack") is not False:
        gaps.append({"code": "OBSERVATION_AUTHORITY", "detail": f"{fixture}:authority/public_ack binding missing"})
    profile_value = observed.get("profile")
    profile_name = profile_value if isinstance(profile_value, str) else profile_value.get("profile") if isinstance(profile_value, Mapping) else None
    if profile_name != _OWNER.PROFILE:
        gaps.append({"code": "REGISTERED_PROFILE_MISSING", "detail": f"{fixture}:registered profile identity is missing"})
    digest = observed.get("profile_catalog_digest")
    if digest is None and isinstance(profile_value, Mapping):
        digest = profile_value.get("catalog_digest")
    if digest is None and isinstance(observed.get("receipt"), Mapping):
        digest = observed["receipt"].get("profile_catalog_digest")
    if not isinstance(digest, str) or not REVISION_RE.fullmatch(digest):
        gaps.append({"code": "REGISTERED_CATALOG_DIGEST_MISSING", "detail": f"{fixture}:catalog digest is not bound to observation"})
    closure = observed.get("source_closure_sha256")
    if not isinstance(closure, str) or not REVISION_RE.fullmatch(closure):
        gaps.append({"code": "SOURCE_CLOSURE_MISSING", "detail": f"{fixture}:source closure hash is not bound to observation"})
    native = observed.get("native_observed") is True or (
        observed.get("status") == "DIAGNOSTIC_PASS" and observed.get("native_process") is not None)
    if not native:
        gaps.append({"code": "NATIVE_OBSERVATION_REQUIRED", "detail": f"{fixture}:catalog native readback is not observed"})
    trace = observed.get("input_trace") or observed.get("trace")
    if not isinstance(trace, Mapping) or trace.get("fps") != 60 or type(trace.get("seed")) is not int:
        gaps.append({"code": "REPLAY_INPUT_TRACE_MISSING", "detail": f"{fixture}:fixed 60 Hz seeded input trace is not bound"})
    snapshot = _snapshot(observed)
    if snapshot is None:
        gaps.append({"code": "SNAPSHOT_READBACK_REQUIRED", "detail": f"{fixture}:after_reload snapshot missing"})
    else:
        _project, root_type, target, _name, _repair = _fixture(fixture)
        root = _find(snapshot, "root")
        if root is None or root.get("node_type") != root_type:
            gaps.append({"code": "REGISTERED_ROOT_MISMATCH", "detail": f"{fixture}:root type/readback mismatch"})
        if _find(snapshot, target) is None:
            gaps.append({"code": "REGISTERED_TARGET_MISSING", "detail": f"{fixture}:{target} not present in readback"})
    if not isinstance(observed.get("seeded_faults"), list) or not observed.get("seeded_faults"):
        gaps.append({"code": "SEEDED_FAULT_READBACK_MISSING", "detail": f"{fixture}:seeded scene/resource/script fault was not observed"})
    return snapshot, gaps


def _faults(observed: Mapping[str, Any], fixture: str, snapshot: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows = observed.get("seeded_faults")
    gaps: list[dict[str, str]] = []
    valid: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return valid, [{"code": "SEEDED_FAULT_READBACK_MISSING", "detail": f"{fixture}:fault list missing"}]
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            gaps.append({"code": "SEEDED_FAULT_SHAPE", "detail": f"{fixture}:fault {index} is not an object"})
            continue
        kind = row.get("kind")
        if kind not in {"scene", "resource", "script"}:
            gaps.append({"code": "SEEDED_FAULT_KIND", "detail": f"{fixture}:fault {index} has unsupported kind"})
            continue
        if kind == "scene":
            target = row.get("target_stable_id")
            prop, before, after = row.get("property"), row.get("before"), row.get("after")
            node = _find(snapshot, str(target)) if isinstance(target, str) else None
            if node is None or not isinstance(prop, str) or before is None or after is None:
                gaps.append({"code": "SEEDED_SCENE_FAULT_BINDING", "detail": f"{fixture}:scene fault {index} is not bound to readback"})
                continue
            actual = node.get("properties", {}).get(prop)
            if actual != before:
                gaps.append({"code": "SEEDED_SCENE_FAULT_STALE", "detail": f"{fixture}:{target}.{prop} before value differs from readback"})
                continue
            valid.append({"kind": kind, "target_stable_id": target, "property": prop,
                          "before": _copy(before), "after": _copy(after),
                          "command_id": f"repair.{fixture}.scene.{index + 1}"})
        else:
            # The catalog intentionally has no resource.update or script
            # replacement operation. Keep this measured gap explicit.
            gaps.append({"code": "REGISTERED_" + kind.upper() + "_ROUTE_DISABLED",
                         "detail": f"{fixture}:{kind} repair has no registered catalog operation"})
    return valid, gaps


def _inventory(snapshot: Mapping[str, Any], admission: Any):
    nodes = tuple(_OWNER._NODE.NodeState(row["stable_id"], row.get("parent_id"),
                                         row["node_type"], row["name"])
                  for row in snapshot.get("nodes", ()))
    resource_nodes = tuple(_OWNER._RESOURCE.NodeState(row.stable_id, row.parent_id,
                                                      row.node_type, row.name)
                           for row in nodes)
    resources = tuple(_OWNER._NODE.ResourceState(row["resource_id"], row.get("base", "Shape"))
                      for row in snapshot.get("asset_resources", ()))
    node_ctx = _OWNER._PLANNER._NODE.ValidationContext(
        admission.project_id, admission.revision, admission.project_revision,
        admission.generation, admission.lease_id, admission.fencing_epoch,
        admission.lease_expires_ms, admission.now_ms, nodes, resources)
    resource_ctx = _OWNER._PLANNER._RESOURCE.ValidationContext(
        admission.project_id, admission.revision, admission.project_revision,
        admission.generation, admission.lease_id, admission.fencing_epoch,
        admission.lease_expires_ms, admission.now_ms, resource_nodes, ())
    return _OWNER._PLANNER.TrustedInventory(node_ctx, resource_ctx)


def _request(admission: Any, *, command_id: str, target: str, changes: Mapping[str, Any]) -> Request:
    payload = {"changes": _copy(changes), "expected_generation": admission.generation,
               "expected_project_revision": admission.project_revision}
    return Request(command_id=command_id, project_id=admission.project_id,
                   operation="scene.node.update", lease_id=admission.lease_id,
                   fencing_epoch=admission.fencing_epoch,
                   expected_revision=admission.revision, target={"stable_id": target},
                   payload=payload, payload_hash=_sha(payload), deadline_ms=min(
                       admission.lease_expires_ms - 1, admission.now_ms + 1000))


def _build_batch(fixture: str, observed: Mapping[str, Any], snapshot: Mapping[str, Any], faults: list[dict[str, Any]]):
    project_id, root_type, _target, _name, _repair = _fixture(fixture)
    project_revision = observed.get("project_revision")
    if not isinstance(project_revision, str) or not REVISION_RE.fullmatch(project_revision):
        project_revision = _sha({"fixture": fixture, "snapshot": snapshot})
    admission = _OWNER.make_admission(project_id=project_id, revision=_sha(snapshot),
        project_revision=project_revision, generation=int(observed.get("generation", 1)),
        lease_id=f"lease.repair.{fixture}", fencing_epoch=int(observed.get("fencing_epoch", 1)),
        now_ms=int(time.time() * 1000), ttl_ms=120_000)
    requests = [_request(admission, command_id=fault["command_id"],
                         target=fault["target_stable_id"],
                         changes={fault["property"]: fault["after"]}) for fault in faults]
    return admission, requests, {"project_id": project_id, "root_type": root_type,
        "command_ids": [request.command_id for request in requests],
        "source_snapshot_sha256": _sha(snapshot), "repair_faults": _copy(faults)}


def _dummy_handoff(observed: Mapping[str, Any]):
    handoff = observed.get("blender_handoff") if isinstance(observed.get("blender_handoff"), Mapping) else {}
    return _OWNER.BlenderHandoff(str(handoff.get("published_root", "registered://fixture")),
        str(handoff.get("glb_sha256", "0" * 64)), str(handoff.get("manifest_sha256", "0" * 64)),
        str(handoff.get("manifest_schema", "DIAGNOSTIC")), str(handoff.get("command_id", "repair-handoff")),
        str(handoff["sprite_sha256"]) if isinstance(handoff.get("sprite_sha256"), str) else None,
        str(handoff["content_schema"]) if isinstance(handoff.get("content_schema"), str) else None,
        str(handoff["source_closure_sha256"]) if isinstance(handoff.get("source_closure_sha256"), str) else None)


def _check_receipt(receipt: Mapping[str, Any], transaction: Any, handoff: Any) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    if not isinstance(receipt, Mapping):
        return [{"code": "REGISTERED_APPLY_RECEIPT_MISSING", "detail": "execute callback did not return a receipt"}]
    if receipt.get("native_observed") is not True or receipt.get("public_ack") is not False or receipt.get("authority") != 0:
        gaps.append({"code": "REGISTERED_APPLY_NOT_OBSERVED", "detail": "batch receipt is not authority-zero native readback"})
    if receipt.get("readback_ack") is not True:
        gaps.append({"code": "REGISTERED_APPLY_READBACK_MISSING", "detail": "batch receipt lacks postcondition readback"})
    if receipt.get("transaction_digest") != transaction.digest or receipt.get("command_ids") != list(transaction.command_ids):
        gaps.append({"code": "REGISTERED_APPLY_BINDING", "detail": "batch receipt does not echo transaction identity"})
    process = receipt.get("native_process")
    if not isinstance(process, Mapping) or process.get("exit_code") != 0:
        gaps.append({"code": "REGISTERED_NATIVE_EXIT_MISSING", "detail": "batch receipt lacks a host-captured native exit 0"})
    if receipt.get("blender_handoff") != handoff.as_dict():
        gaps.append({"code": "REGISTERED_APPLY_HANDOFF", "detail": "batch receipt handoff differs from admission"})
    rows = receipt.get("catalog_commands_executed")
    if not isinstance(rows, list) or len(rows) != len(transaction.commands) or not all(
            isinstance(row, Mapping) and row.get("command_id") == command.command_id
            and row.get("projection_sha256") == command.projection_sha256
            and row.get("verified") is True and isinstance(row.get("readback"), Mapping)
            for row, command in zip(rows, transaction.commands)):
        gaps.append({"code": "REGISTERED_COMMAND_READBACK", "detail": "per-command catalog readback missing"})
    return gaps


def run_scenario(*, fixture: str, observed: Mapping[str, Any], execute: Callable[..., Mapping[str, Any]] | None = None,
                 replay: Callable[..., Mapping[str, Any]] | None = None,
                 checkpoint: Callable[..., Mapping[str, Any]] | None = None,
                 run_id: str | None = None, output: Path | None = None) -> dict[str, Any]:
    """Run one fixture's observe -> batch -> replay -> checkpoint contract."""
    _need(fixture in FIXTURES, "REGISTERED_REPAIR_FIXTURE")
    if run_id is not None:
        _need(RUN_ID_RE.fullmatch(run_id) is not None, "REGISTERED_REPAIR_RUN_ID")
    snapshot, gaps = _observe_gate(observed, fixture)
    result: dict[str, Any] = {"schema": SCHEMA, "run_id": run_id, "fixture": fixture,
        "authority": 0, "public_ack": False, "acceptance": False, "status": "OPEN",
        "diagnostic_only": True, "profile": observed.get("profile"),
        "profile_catalog_digest": observed.get("profile_catalog_digest"),
        "source_closure_sha256": observed.get("source_closure_sha256"),
        "phases": {}, "gaps": gaps}
    result["gaps"].append({"code": "REGISTERED_SCRIPT_ROUTE_DISABLED", "detail": f"{fixture}:controller script change is not in the registered catalog"})
    result["gaps"].append({"code": "CONTROLLER_REACTION_READBACK_MISSING", "detail": f"{fixture}:scene readback does not prove controller reaction changed"})
    if snapshot is None:
        return _write(result, output)
    faults, fault_gaps = _faults(observed, fixture, snapshot)
    result["gaps"].extend(fault_gaps)
    result["phases"]["observe"] = {"native_observed": not any(g["code"] == "NATIVE_OBSERVATION_REQUIRED" for g in gaps),
        "snapshot_sha256": _sha(snapshot), "seeded_fault_count": len(faults)}
    if not faults:
        return _write(result, output)
    admission, requests, batch_meta = _build_batch(fixture, observed, snapshot, faults)
    handoff = _dummy_handoff(observed)
    result["phases"]["batch"] = {**batch_meta, "prepared": False}
    owner = None
    try:
        owner = _OWNER.RegisteredAuthoringOwner(admission=admission, blender=handoff,
            native_apply=lambda transaction, live_admission, live_handoff: execute(
                transaction, live_admission, live_handoff) if execute is not None else {})
        transaction = owner.prepare(requests, inventory=_inventory(snapshot, admission))
        result["phases"]["batch"].update({"prepared": True, "transaction_digest": transaction.digest,
                                           "command_ids": list(transaction.command_ids)})
        if execute is None:
            result["gaps"].append({"code": "REGISTERED_EXECUTOR_CALLBACK_MISSING", "detail": "catalog batch was prepared but no native producer was supplied"})
            return _write(result, output)
        receipt = owner.apply(transaction)
        apply_gaps = _check_receipt(receipt, transaction, handoff)
        result["gaps"].extend(apply_gaps)
        result["phases"]["batch"].update({"applied": not apply_gaps, "receipt": _copy(receipt) if not apply_gaps else None})
        if apply_gaps:
            return _write(result, output)
        if replay is None:
            result["gaps"].append({"code": "REGISTERED_REPLAY_CALLBACK_MISSING", "detail": "catalog batch replay producer was not supplied"})
        else:
            replay_result = replay(transaction, receipt)
            result["phases"]["replay"] = _copy(replay_result) if isinstance(replay_result, Mapping) else {}
            if not isinstance(replay_result, Mapping) or replay_result.get("native_observed") is not True or replay_result.get("replay_equal") is not True:
                result["gaps"].append({"code": "REGISTERED_REPLAY_NOT_EQUAL", "detail": "replay lacks native observed equal postcondition"})
        if checkpoint is None:
            result["gaps"].append({"code": "REGISTERED_CHECKPOINT_CALLBACK_MISSING", "detail": "checkpoint producer was not supplied"})
        else:
            checkpoint_result = checkpoint(transaction, receipt)
            result["phases"]["checkpoint"] = _copy(checkpoint_result) if isinstance(checkpoint_result, Mapping) else {}
            if not isinstance(checkpoint_result, Mapping) or checkpoint_result.get("native_observed") is not True or checkpoint_result.get("checkpoint_verified") is not True or checkpoint_result.get("postcondition_readback") is not True:
                result["gaps"].append({"code": "REGISTERED_CHECKPOINT_NOT_VERIFIED", "detail": "checkpoint lacks native postcondition readback"})
    except Exception as error:
        result["gaps"].append({"code": "REGISTERED_REPAIR_EXCEPTION", "detail": type(error).__name__})
    finally:
        if owner is not None:
            owner.close()
    result["status"] = "DIAGNOSTIC_PASS" if not result["gaps"] else "OPEN"
    return _write(result, output)


def build_repair_batch(*, fixture: str, observed: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare only a typed registered batch; never starts a native process."""
    snapshot, gaps = _observe_gate(observed, fixture)
    if snapshot is None:
        return {"status": "OPEN", "fixture": fixture, "gaps": gaps, "commands": []}
    faults, fault_gaps = _faults(observed, fixture, snapshot)
    gaps.extend(fault_gaps)
    if not faults:
        return {"status": "OPEN", "fixture": fixture, "gaps": gaps, "commands": []}
    admission, requests, meta = _build_batch(fixture, observed, snapshot, faults)
    return {"status": "OPEN" if gaps else "READY", "fixture": fixture, "gaps": gaps,
            "admission": admission.as_dict(), "commands": [request.as_dict() for request in requests],
            "batch": meta}


def load_observation(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _need(type(value) is dict, "REGISTERED_REPAIR_OBSERVATION_JSON")
    return value


def _write(result: dict[str, Any], output: Path | None) -> dict[str, Any]:
    if output is not None:
        target = output.resolve()
        _need(target.is_relative_to((STUDIO / ".local" / "reviews").resolve()), "REGISTERED_REPAIR_OUTPUT_ROOT")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", choices=FIXTURES, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--observe", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    _need(RUN_ID_RE.fullmatch(args.run_id) is not None, "REGISTERED_REPAIR_RUN_ID")
    if args.dry_run:
        result = {"schema": SCHEMA, "run_id": args.run_id, "fixture": args.fixture,
                  "authority": 0, "public_ack": False, "status": "OPEN", "acceptance": False,
                  "diagnostic_only": True, "phases": {"observe": {"planned": True},
                  "batch": {"planned": True, "registered_operations": list(_OWNER.OPERATIONS), "script_route": False},
                  "replay": {"planned": True}, "checkpoint": {"planned": True}},
                  "gaps": [{"code": "DRY_RUN_NO_NATIVE_OBSERVATION", "detail": "dry-run does not provide seeded readback"},
                           {"code": "REGISTERED_SCRIPT_ROUTE_DISABLED", "detail": "catalog script operation is disabled"}]}
        if args.output is None:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            _write(result, args.output)
        return 2
    if args.observe is None:
        result = {"schema": SCHEMA, "run_id": args.run_id, "fixture": args.fixture,
                  "authority": 0, "public_ack": False, "status": "OPEN", "acceptance": False,
                  "diagnostic_only": True, "phases": {},
                  "gaps": [{"code": "NATIVE_OBSERVATION_REQUIRED", "detail": "--observe is required; no catalog readback is invented"}]}
        if args.output is None:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            _write(result, args.output)
        return 2
    result = run_scenario(fixture=args.fixture, observed=load_observation(args.observe),
                          run_id=args.run_id, output=args.output)
    if args.output is None:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "DIAGNOSTIC_PASS" else 2


__all__ = ["SCHEMA", "FIXTURES", "build_repair_batch", "load_observation", "run_scenario", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
