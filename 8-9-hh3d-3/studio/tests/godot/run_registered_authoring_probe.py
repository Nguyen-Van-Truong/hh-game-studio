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
import re
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
_ARENA = _load("hh_registered_arena_recipe", "tests/godot/saved_arena_recipe.py")
_ROOM_BUILDER = _load("hh_registered_room_builder", "tests/godot/run_saved_room_builder.py")
_ARENA_BUILDER = _load("hh_registered_arena_builder", "tests/godot/run_saved_arena_builder.py")


def _need(value: object, code: str) -> None:
    if not value:
        raise ValueError(code)


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":")))


def _sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _source_manifest(recipe_module, builder) -> tuple[dict[str, str], str]:
    """Freeze the owner/recipe/runner bytes around the native child.

    The saved-scene builder records its own closure, but the registered owner
    and this dispatcher sit one layer above it. Bind those bytes too so a
    receipt cannot be reused after the admission boundary changes.
    """
    names = {
        "godot-addon/registered_authoring_owner.py",
        "godot-addon/authoring_owner.py",
        "godot-addon/authoring_contract.py",
        "godot-addon/resource_authoring.py",
        "contracts/godot-authoring-schema-v1.json",
        "tests/godot/run_registered_authoring_probe.py",
        "tests/godot/run_saved_room_builder.py" if builder is _ROOM_BUILDER
        else "tests/godot/run_saved_arena_builder.py",
        "tests/godot/saved_room_builder.gd" if builder is _ROOM_BUILDER
        else "tests/godot/saved_arena_builder.gd",
        "tests/godot/saved_room_recipe.py" if recipe_module is _ROOM
        else "tests/godot/saved_arena_recipe.py",
        "toolchain.lock.json",
    }
    files = {}
    for name in sorted(names):
        path = STUDIO / name
        files[name] = _OWNER._sha_bytes(_OWNER._safe_file(path, maximum=2 * 1024 * 1024))
    return files, _sha(files)


def _recipe_modules(fixture: str):
    _need(fixture in {"room", "arena"}, "REGISTERED_FIXTURE")
    if fixture == "arena":
        return _ARENA, _ARENA_BUILDER, "arena"
    return _ROOM, _ROOM_BUILDER, "room"


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
    # These existing verifiers parse the actual host capture, source/project
    # bindings, saved bytes and semantic readback. Never infer exit 0 from a
    # callback return or a child PASS flag.
    verify = builder.verify_saved_arena if fixture == "arena" else builder.verify_saved_room
    scene_raw = verify(native_root)
    result_path = native_root / "result.json"
    _need(result_path.is_file(), "REGISTERED_NATIVE_RESULT_MISSING")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _need(result.get("status") == "DIAGNOSTIC_PASS" and result.get("authority") == 0
          and result.get("public_ack") is False, "REGISTERED_NATIVE_RESULT")
    observation = json.loads((native_root / "native-observation.json").read_text(encoding="utf-8"))
    _need(observation.get("failures") == [] and observation.get("authority") == 0
          and observation.get("public_ack") is False, "REGISTERED_NATIVE_OBSERVATION")
    expected_ids = [row["command_id"] for row in recipe["node_commands"]
                    if row["operation"] == "scene.node.create"]
    expected_ids += [row["command_id"] for row in recipe["resource_commands"]]
    expected_ids += [row["command_id"] for row in recipe["node_commands"]
                     if row["operation"] == "scene.node.update"]
    _need(list(transaction.command_ids) == expected_ids, "REGISTERED_NATIVE_COMMAND_BINDING")
    ordered = [row for row in recipe["node_commands"] if row["operation"] == "scene.node.create"]
    ordered += recipe["resource_commands"]
    ordered += [row for row in recipe["node_commands"] if row["operation"] == "scene.node.update"]
    for command, expected in zip(transaction.commands, ordered):
        proposed = _copy(command.projection)
        baseline = _copy(expected)
        for value in (proposed, baseline):
            value.pop("expected_revision", None)
            value.pop("expected_generation", None)
            value["payload"].pop("expected_generation", None)
        _need(proposed == baseline, "REGISTERED_NATIVE_PROJECTION_BINDING")
    _need(json.loads((native_root / "recipe.json").read_bytes()) == recipe,
          "REGISTERED_NATIVE_RECIPE_BINDING")
    scene_name = "arena.tscn" if fixture == "arena" else "room.tscn"
    _need((native_root / "project/scenes" / scene_name).is_file(), "REGISTERED_NATIVE_SCENE")
    return {"native_run_id": result["run_id"],
            "native_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "native_observation_sha256": hashlib.sha256(
                (native_root / "native-observation.json").read_bytes()).hexdigest(),
            "native_scene_sha256": hashlib.sha256(scene_raw).hexdigest(),
            "native_process": json.loads((native_root / "editor-host/process-exit.json").read_bytes()),
            "source_closure_sha256": source_closure_sha256,
            "blender_handoff": handoff.as_dict(),
            "editor_diagnostic_pass": True}


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
    source_files, source_closure_sha256 = _source_manifest(recipe_module, builder)
    profile_catalog_digest = _OWNER.register_profile().catalog_digest
    native_prefix = "o2-saved-arena-registered-" if fixture == "arena" \
        else "o2-saved-room-registered-"
    native_run_id = native_prefix + run_id.removeprefix("o2-registered-authoring-")
    _need(len(native_run_id) < 80, "REGISTERED_NATIVE_RUN_ID")

    def native_apply(transaction, live_admission, live_handoff):
        _need(transaction.fencing_epoch == live_admission.fencing_epoch,
              "REGISTERED_APPLY_FENCE")
        _need(transaction.lease_id == live_admission.lease_id, "REGISTERED_APPLY_LEASE")
        code = builder.run(native_run_id, godot)
        _need(code == 0, "REGISTERED_GODOT_EXIT")
        native_root = STUDIO / ".local/reviews" / native_run_id
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
        discovery = owner.discovery(project_id=admission.project_id)
        _need(discovery["fixture_enabled"] and len(discovery["profiles"]) == 1,
              "REGISTERED_FIXTURE_DISCOVERY")
        _need(owner.discovery(project_id="project.ungranted")["profiles"] == [],
              "REGISTERED_DISCOVERY_LEAK")
        transaction = owner.prepare(requests, inventory=_inventory(recipe, admission))
        receipt = owner.apply(transaction)
        _need(owner.prepare(requests, inventory=_inventory(recipe, admission)).digest == transaction.digest
              and owner.apply(transaction) == receipt, "REGISTERED_RETRY_CHANGED")
        envelope = {"schema": _OWNER.SCHEMA, "run_id": run_id,
                    "authority": _OWNER.AUTHORITY, "public_ack": False,
                    "status": "DIAGNOSTIC_PASS", "fixture": fixture,
                    "profile": owner.profile.as_dict(),
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
    source_files, source_closure_sha256 = _source_manifest(recipe_module, builder)
    pin = json.loads((STUDIO / "toolchain.lock.json").read_bytes())["godot"]["gui_sha256"]
    _need(hashlib.sha256(_OWNER._safe_file(godot.resolve(strict=True), maximum=200 * 1024**2)).hexdigest() == pin,
          "REGISTERED_BINARY_PIN")
    actor = _OWNER.RegisteredAuthoringOwner(admission=admission, blender=handoff,
        native_apply=lambda *_args: (_ for _ in ()).throw(AssertionError("dry run native dispatch")))
    try:
        transaction = actor.prepare(_bound_requests(recipe, admission, recipe_module),
                                    inventory=_inventory(recipe, admission))
        return {"schema": _OWNER.SCHEMA, "run_id": run_id, "fixture": fixture,
                "dry_run": True, "authority": 0, "public_ack": False,
                "commands": len(transaction.commands), "binary_sha256": pin,
                "source_files": source_files, "source_closure_sha256": source_closure_sha256,
                "discovery": actor.discovery(project_id=admission.project_id)}
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
