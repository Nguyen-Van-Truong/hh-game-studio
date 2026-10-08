"""Bounded registered O2 owner probe using the pinned Godot editor.

The owner admits the real saved-room recipe, checks a published Blender GLB
and then invokes the existing editor/UndoRedo/save/reload diagnostic.  The
outer receipt binds that native evidence to the exact transaction, lease,
fencing epoch and Blender manifest.  Everything remains authority zero.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _load(name: str, relative: str):
    path = STUDIO / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("REGISTERED_PROBE_IMPORT")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_OWNER = _load("hh_registered_authoring_owner_probe", "godot-addon/registered_authoring_owner.py")
_ROOM = _load("hh_registered_room_recipe", "tests/godot/saved_room_recipe.py")
_BUILDER = _load("hh_registered_room_builder", "tests/godot/run_saved_room_builder.py")


def _need(value: object, code: str) -> None:
    if not value:
        raise ValueError(code)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _inventory(recipe: dict[str, Any], admission: _OWNER.OwnerAdmission):
    initial = recipe["initial_snapshot"]
    nodes = tuple(_OWNER._NODE.NodeState(row["stable_id"], row["parent_id"],
                                        row["node_type"], row["name"])
                  for row in initial["nodes"])
    resource_nodes = tuple(_OWNER._RESOURCE.NodeState(row.stable_id, row.parent_id,
                                                      row.node_type, row.name)
                           for row in nodes)
    asset_resources = tuple(_OWNER._NODE.ResourceState(row["resource_id"], row["base"])
                            for row in initial.get("asset_resources", ()))
    node_context = _OWNER._NODE.ValidationContext(
        admission.project_id, admission.revision, admission.project_revision,
        admission.generation, admission.lease_id, admission.fencing_epoch,
        admission.lease_expires_ms, admission.now_ms, nodes, asset_resources)
    resource_context = _OWNER._RESOURCE.ValidationContext(
        admission.project_id, admission.revision, admission.project_revision,
        admission.generation, admission.lease_id, admission.fencing_epoch,
        admission.lease_expires_ms, admission.now_ms, resource_nodes, ())
    return _OWNER._PLANNER.TrustedInventory(node_context, resource_context)


def _bound_requests(recipe: dict[str, Any], admission: _OWNER.OwnerAdmission) -> list[dict]:
    bound = _ROOM.bind_recipe_to_owner_admission(recipe, admission.as_dict())
    return [row["request"] for row in bound["commands"]]


def _verify_native(native_root: Path, transaction, handoff: _OWNER.BlenderHandoff) -> dict[str, Any]:
    result_path = native_root / "result.json"
    _need(result_path.is_file(), "REGISTERED_NATIVE_RESULT_MISSING")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _need(result.get("status") == "DIAGNOSTIC_PASS" and result.get("authority") == 0
          and result.get("public_ack") is False, "REGISTERED_NATIVE_RESULT")
    observation = json.loads((native_root / "native-observation.json").read_text(encoding="utf-8"))
    _need(observation.get("failures") == [] and observation.get("authority") == 0
          and observation.get("public_ack") is False, "REGISTERED_NATIVE_OBSERVATION")
    recipe = _ROOM.build_recipe()
    expected_ids = [row["command_id"] for row in recipe["node_commands"]
                    if row["operation"] == "scene.node.create"]
    expected_ids += [row["command_id"] for row in recipe["resource_commands"]]
    expected_ids += [row["command_id"] for row in recipe["node_commands"]
                     if row["operation"] == "scene.node.update"]
    _need(list(transaction.command_ids) == expected_ids, "REGISTERED_NATIVE_COMMAND_BINDING")
    _need((native_root / "project/scenes/room.tscn").is_file(), "REGISTERED_NATIVE_SCENE")
    return {"native_run_id": result["run_id"],
            "native_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "native_observation_sha256": hashlib.sha256(
                (native_root / "native-observation.json").read_bytes()).hexdigest(),
            "native_scene_sha256": hashlib.sha256(
                (native_root / "project/scenes/room.tscn").read_bytes()).hexdigest(),
            "blender_handoff": handoff.as_dict(),
            "editor_diagnostic_pass": True}


def run(*, run_id: str, godot: Path, blender_published: Path) -> dict[str, Any]:
    _need(run_id.startswith("o2-registered-authoring-") and len(run_id) < 80,
          "REGISTERED_RUN_ID")
    output = (STUDIO / ".local/reviews" / run_id).resolve()
    _need(not output.exists(), "REGISTERED_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    recipe = _ROOM.build_recipe()
    revision = _sha(recipe["initial_snapshot"])
    project_revision = recipe["planned_project_revision"]
    now = int(time.time() * 1000)
    admission = _OWNER.make_admission(project_id="project.registered.room",
                                       revision=revision,
                                       project_revision=project_revision,
                                       lease_id="lease.registered.room",
                                       fencing_epoch=1, now_ms=now, ttl_ms=120_000)
    handoff = _OWNER.inspect_blender_handoff(blender_published)
    profile_catalog_digest = _OWNER.register_profile().catalog_digest
    native_run_id = "o2-saved-room-registered-" + run_id.removeprefix("o2-registered-authoring-")
    _need(len(native_run_id) < 80, "REGISTERED_NATIVE_RUN_ID")

    def native_apply(transaction, live_admission, live_handoff):
        _need(transaction.fencing_epoch == live_admission.fencing_epoch,
              "REGISTERED_APPLY_FENCE")
        _need(transaction.lease_id == live_admission.lease_id, "REGISTERED_APPLY_LEASE")
        code = _BUILDER.run(native_run_id, godot)
        _need(code == 0, "REGISTERED_GODOT_EXIT")
        native_root = STUDIO / ".local/reviews" / native_run_id
        native = _verify_native(native_root, transaction, live_handoff)
        envelope = {"schema": _OWNER.SCHEMA, "authority": _OWNER.AUTHORITY,
                    "state_kind": _OWNER.STATE_KIND, "public_ack": False,
                    "native_observed": True, "transaction_digest": transaction.digest,
                    "command_ids": list(transaction.command_ids),
                    "lease_id": live_admission.lease_id,
                    "fencing_epoch": live_admission.fencing_epoch,
                    "admission": live_admission.as_dict(),
                    "profile": _OWNER.PROFILE, "profile_catalog_digest": profile_catalog_digest,
                    **native}
        (native_root / "registered-owner-receipt.json").write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return envelope

    owner = _OWNER.RegisteredAuthoringOwner(admission=admission, blender=handoff,
                                            native_apply=native_apply)
    try:
        requests = _bound_requests(recipe, admission)
        transaction = owner.prepare(requests, inventory=_inventory(recipe, admission))
        receipt = owner.apply(transaction)
        envelope = {"schema": _OWNER.SCHEMA, "run_id": run_id,
                    "authority": _OWNER.AUTHORITY, "public_ack": False,
                    "status": "DIAGNOSTIC_PASS", "profile": owner.profile.as_dict(),
                    "admission": admission.as_dict(), "transaction": transaction.as_dict(),
                    "receipt": receipt, "native_run_id": native_run_id}
        envelope["envelope_sha256"] = hashlib.sha256(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        (output / "registered-owner-result.json").write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (output / "verification.json").write_text(
            json.dumps({"verified": True, "authority": 0, "native_exit": 0},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        return envelope
    except Exception as error:
        failure = {"schema": _OWNER.SCHEMA, "run_id": run_id,
                   "authority": 0, "public_ack": False, "status": "DIAGNOSTIC_FAIL",
                   "error_code": str(error) if str(error).isupper() else type(error).__name__}
        (output / "registered-owner-result.json").write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        raise
    finally:
        owner.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--blender-published", required=True, type=Path)
    args = parser.parse_args()
    report = run(run_id=args.run_id, godot=args.godot, blender_published=args.blender_published)
    print(json.dumps({"run_id": report["run_id"], "status": report["status"],
                      "authority": report["authority"], "native_run_id": report["native_run_id"]}),
          flush=True)
