"""Bounded registered O2 owner probe using the pinned Godot editor.

The owner admits fixture recipe requests and sends their actual validated
transactions to the reusable catalog addon. Builders remain detached oracles;
they are never dispatched to construct the native project.
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
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import canonical_bytes


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
_ARENA = _load("hh_registered_arena_recipe", "tests/godot/saved_arena_recipe.py")
_NATIVE = _load("hh_registered_catalog_native", "godot-addon/catalog_native_host.py")


def _need(value: object, code: str) -> None:
    if not value:
        raise ValueError(code)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _source_manifest(*_args) -> tuple[dict[str, str], str]:
    """One shared room/arena closure, including the actual native executor."""
    names = {
        "godot-addon/registered_authoring_owner.py",
        "godot-addon/authoring_owner.py",
        "godot-addon/authoring_contract.py",
        "godot-addon/resource_authoring.py",
        "contracts/godot-authoring-schema-v1.json",
        "tests/godot/run_registered_authoring_probe.py",
        "tests/godot/saved_room_recipe.py",
        "tests/godot/saved_arena_recipe.py",
        "godot-addon/gameplay_fixture_profile.py",
        "godot-addon/fixture_profile.json",
        "host/blender/fixture_content.py",
        "host/blender/fixture_content_job.py",
        "host/blender/fixture_content_native.py",
        "tests/blender/sprite_sheet_pixels.py",
        "toolchain.lock.json",
    }
    return _NATIVE.source_manifest(names)


def _recipe_modules(fixture: str):
    _need(fixture in {"room", "arena"}, "REGISTERED_FIXTURE")
    if fixture == "arena":
        return _ARENA, _NATIVE, "arena"
    return _ROOM, _NATIVE, "room"


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


def _bound_requests(recipe: dict[str, Any], admission: _OWNER.OwnerAdmission,
                    recipe_module=_ROOM) -> list[dict]:
    bound = recipe_module.bind_recipe_to_owner_admission(recipe, admission.as_dict())
    return [row["request"] for row in bound["commands"]]


def _verify_native(native_root: Path, transaction, handoff: _OWNER.BlenderHandoff,
                   recipe: dict[str, Any], fixture: str, builder,
                   source_closure_sha256: str) -> dict[str, Any]:
    _NATIVE.verify_native(native_root)
    scene_raw = _NATIVE.read(native_root / "project/scenes/authored.tscn")
    result_path = native_root / "result.json"
    _need(result_path.is_file(), "REGISTERED_NATIVE_RESULT_MISSING")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _need(result.get("status") == "DIAGNOSTIC_PASS" and result.get("authority") == 0
          and result.get("public_ack") is False, "REGISTERED_NATIVE_RESULT")
    observation = json.loads((native_root / "native-observation.json").read_text(encoding="utf-8"))
    _need(observation.get("failures") == [] and observation.get("authority") == 0
          and observation.get("public_ack") is False, "REGISTERED_NATIVE_OBSERVATION")
    data = json.loads((native_root / "project/catalog-input.json").read_bytes())
    _need(data["transaction"] == transaction.as_dict(), "REGISTERED_NATIVE_TRANSACTION_BINDING")
    _need(_NATIVE.semantic_equal(observation["snapshots"]["after_reload"], recipe["expected_snapshot"]),
          "REGISTERED_RECIPE_ORACLE")
    return {"native_run_id": native_root.name,
            "native_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "native_observation_sha256": hashlib.sha256(
                (native_root / "native-observation.json").read_bytes()).hexdigest(),
            "native_scene_sha256": hashlib.sha256(scene_raw).hexdigest(),
            "native_process": json.loads((native_root / "editor-host/process-exit.json").read_bytes()),
            "source_closure_sha256": source_closure_sha256,
            "blender_handoff": handoff.as_dict(),
            "catalog_commands_executed": observation["commands"],
            "readback_ack": True,
            "editor_diagnostic_pass": True}


def _bind_handoff(recipe: dict, handoff: _OWNER.BlenderHandoff) -> None:
    for asset in recipe.get("asset_bindings", ()):
        asset.update(sha256=handoff.glb_sha256, manifest_sha256=handoff.manifest_sha256)


def _native_input(transaction, admission, recipe, handoff, fixture):
    _need(handoff.sprite_sha256 is not None, "REGISTERED_SPRITE_HANDOFF_REQUIRED")
    assets = {"mesh.avatar": {"path": "assets/avatar.glb", "sha256": handoff.glb_sha256,
                               "sprite_path": "assets/sprite_sheet.png",
                               "sprite_sha256": handoff.sprite_sha256}}
    return _NATIVE.make_input(transaction, admission, recipe["root"], _OWNER._NODE.load_catalog(), assets)


def run(*, run_id: str, godot: Path, blender_published: Path,
        fixture: str = "room") -> dict[str, Any]:
    _need(re.fullmatch(r"o2-registered-authoring-[a-z0-9-]{1,29}", run_id),
          "REGISTERED_RUN_ID")
    recipe_module, builder, fixture = _recipe_modules(fixture)
    output = (STUDIO / ".local/reviews" / run_id).resolve()
    _need(not output.exists(), "REGISTERED_OUTPUT_EXISTS")
    output.mkdir(parents=True)
    recipe = recipe_module.build_recipe()
    revision = _sha(recipe["initial_snapshot"])
    project_suffix = "arena" if fixture == "arena" else "room"
    project_revision = recipe["planned_project_revision"]
    now = int(time.time() * 1000)
    admission = _OWNER.make_admission(project_id="project.registered." + project_suffix,
                                       revision=revision,
                                       project_revision=project_revision,
                                       lease_id="lease.registered." + project_suffix,
                                       fencing_epoch=1, now_ms=now, ttl_ms=120_000)
    handoff = _OWNER.inspect_blender_handoff(blender_published)
    _bind_handoff(recipe, handoff)
    source_files, source_closure_sha256 = _source_manifest(recipe_module, builder)
    profile_catalog_digest = _OWNER.register_profile().catalog_digest
    native_prefix = "o2-catalog-" + fixture + "-"
    native_run_id = native_prefix + run_id.removeprefix("o2-registered-authoring-")
    _need(len(native_run_id) < 80, "REGISTERED_NATIVE_RUN_ID")

    def native_apply(transaction, live_admission, live_handoff):
        _need(transaction.fencing_epoch == live_admission.fencing_epoch,
              "REGISTERED_APPLY_FENCE")
        _need(transaction.lease_id == live_admission.lease_id, "REGISTERED_APPLY_LEASE")
        native_root = STUDIO / ".local/reviews" / native_run_id
        _NATIVE.execute(output=native_root, godot=godot,
            data=_native_input(transaction, live_admission, recipe, live_handoff, fixture),
            source_files=source_files, blender=live_handoff)
        live_files, live_closure = _source_manifest(recipe_module, builder)
        _need(live_files == source_files and live_closure == source_closure_sha256,
              "REGISTERED_SOURCE_CHANGED")
        native = _verify_native(native_root, transaction, live_handoff, recipe, fixture,
                                builder, source_closure_sha256)
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
        requests = _bound_requests(recipe, admission, recipe_module)
        adapter = _OWNER.RegisteredAuthoringAdapter(owner, inventory=_inventory(recipe, admission),
            source_files=source_files, host_profile=_OWNER.load_fixture_host_profile(admission.project_id))
        discovery = adapter.discovery(project_id=admission.project_id)
        _need(discovery["fixture_enabled"] and len(discovery["profiles"]) == 1,
              "REGISTERED_FIXTURE_DISCOVERY")
        _need(adapter.discovery(project_id="project.ungranted")["profiles"] == [],
              "REGISTERED_DISCOVERY_LEAK")
        identity = {"profile_digest": discovery["profiles"][0]["catalog_digest"]}
        transaction = adapter.prepare(requests, **identity)
        receipt = adapter.execute(requests, **identity)
        _need(adapter.execute(requests, **identity) == receipt, "REGISTERED_RETRY_CHANGED")
        envelope = {"schema": _OWNER.SCHEMA, "run_id": run_id,
                    "authority": _OWNER.AUTHORITY, "public_ack": False,
                    "status": "DIAGNOSTIC_PASS", "fixture": fixture,
                    "profile": discovery["profiles"][0],
                    "discovery": discovery, "same_request_same_receipt": True,
                    "source_files": source_files,
                    "source_closure_sha256": source_closure_sha256,
                    "admission": admission.as_dict(), "transaction": transaction.as_dict(),
                    "receipt": receipt, "native_run_id": native_run_id}
        envelope["envelope_sha256"] = hashlib.sha256(
            json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        (output / "registered-owner-result.json").write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        (output / "verification.json").write_text(
            json.dumps({"verified": True, "authority": 0,
                        "native_process": receipt["native_process"]},
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


def dry_run(*, run_id: str, godot: Path, blender_published: Path, fixture: str = "room") -> dict:
    """Validate exact fixture commands and pinned inputs without native work."""
    _need(re.fullmatch(r"o2-registered-authoring-[a-z0-9-]{1,29}", run_id), "REGISTERED_RUN_ID")
    recipe_module, builder, fixture = _recipe_modules(fixture)
    _need(not (STUDIO / ".local/reviews" / run_id).exists(), "REGISTERED_OUTPUT_EXISTS")
    recipe = recipe_module.build_recipe()
    admission = _OWNER.make_admission(project_id="project.registered." + fixture,
        revision=_sha(recipe["initial_snapshot"]), project_revision=recipe["planned_project_revision"],
        lease_id="lease.registered." + fixture)
    handoff = _OWNER.inspect_blender_handoff(blender_published)
    _bind_handoff(recipe, handoff)
    source_files, source_closure_sha256 = _source_manifest(recipe_module, builder)
    pin = json.loads((STUDIO / "toolchain.lock.json").read_bytes())["godot"]["gui_sha256"]
    _need(hashlib.sha256(_OWNER._safe_file(godot.resolve(strict=True), maximum=200 * 1024**2)).hexdigest() == pin,
          "REGISTERED_BINARY_PIN")
    actor = _OWNER.RegisteredAuthoringOwner(admission=admission, blender=handoff,
        native_apply=lambda *_args: (_ for _ in ()).throw(AssertionError("dry run native dispatch")))
    try:
        adapter = _OWNER.RegisteredAuthoringAdapter(actor, inventory=_inventory(recipe, admission),
            source_files=source_files, host_profile=_OWNER.load_fixture_host_profile(admission.project_id))
        discovered = adapter.discovery(project_id=admission.project_id)
        transaction = adapter.prepare(_bound_requests(recipe, admission, recipe_module),
            profile_digest=discovered["profiles"][0]["catalog_digest"])
        data = _native_input(transaction, admission, recipe, handoff, fixture)
        _need(_NATIVE.semantic_equal(_NATIVE.expected_readbacks(data)[1], recipe["expected_snapshot"]),
              "REGISTERED_RECIPE_ORACLE")
        return {"schema": _OWNER.SCHEMA, "run_id": run_id, "fixture": fixture,
                "dry_run": True, "authority": 0, "public_ack": False,
                "commands": len(transaction.commands), "binary_sha256": pin,
                "source_files": source_files, "source_closure_sha256": source_closure_sha256,
                "discovery": discovered}
    finally:
        actor.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--blender-published", required=True, type=Path)
    parser.add_argument("--fixture", choices=("room", "arena"), default="room")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    call = dry_run if args.dry_run else run
    report = call(run_id=args.run_id, godot=args.godot,
                 blender_published=args.blender_published, fixture=args.fixture)
    print(json.dumps(report if args.dry_run else {"run_id": report["run_id"],
          "status": report["status"], "authority": report["authority"],
          "native_run_id": report["native_run_id"]}), flush=True)
