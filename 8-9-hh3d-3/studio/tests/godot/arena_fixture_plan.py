"""Detached authority-zero plan for the 2D arena fixture.

This module composes the existing TileMapLayer, gameplay-edge and typed
gameplay-behavior candidate validators into one reviewable fixture document.
It is deliberately a *plan*: no Godot process, editor mutation, script
execution, save, ACK, lease admission or runtime proof is performed here.
The source rows are typed references to a future gameplay-source publication;
their bytes and native readback remain separate gates.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Mapping

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

SCHEMA = "hh-o2-arena-fixture-plan-1"
DETACHED_MODE = "DETACHED_PLAN_ONLY"
AUTHORITY = 0


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, STUDIO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_TILEMAP = _load("hh_arena_fixture_tilemap", "godot-addon/tilemap_authoring.py")
_EDGES = _load("hh_arena_fixture_edges", "godot-addon/gameplay_edges.py")
_BEHAVIOR = _load("hh_arena_fixture_behavior", "godot-addon/gameplay_behavior.py")


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def _detached(**extra: Any) -> dict[str, Any]:
    return {"authority": AUTHORITY, "runtime_authorized": False,
            "native_observed": False, "execution": DETACHED_MODE, **extra}


def _request(*, command_id: str, project_id: str, operation: str,
             lease_id: str, revision: str, project_revision: str,
             generation: int, fencing_epoch: int, target: str,
             payload: dict[str, Any], deadline_ms: int = 2000) -> Request:
    body = {**payload, "expected_generation": generation,
            "expected_project_revision": project_revision}
    return Request(command_id=command_id, project_id=project_id,
                   operation=operation, lease_id=lease_id,
                   fencing_epoch=fencing_epoch, expected_revision=revision,
                   target={"stable_id": target}, payload=body,
                   payload_hash=_sha(body), deadline_ms=deadline_ms)


def _base_observation() -> dict[str, Any]:
    return {"project_id": "project.arena.fixture", "revision": _sha({"fixture": "arena"}),
            "project_revision": _sha({"fixture": SCHEMA}), "generation": 1,
            "lease_id": "lease.arena.fixture", "fencing_epoch": 1,
            "lease_expires_ms": 30_000, "now_ms": 1_000}


def _tilemap_plan(base: dict[str, Any]) -> dict[str, Any]:
    project_id, revision = base["project_id"], base["revision"]
    project_revision, generation = base["project_revision"], base["generation"]
    lease, epoch = base["lease_id"], base["fencing_epoch"]
    node_rows = (_TILEMAP.NodeState("root", None, "Node2D", "Arena"),
                 _TILEMAP.NodeState("platforms", "root", "TileMapLayer", "Platforms"))
    source = _TILEMAP.TileSourceState(
        0, _sha({"atlas": "arena.platforms", "schema": 1}),
        ((0, 0), (1, 0)), (0,))
    cells: list[Any] = []
    commands: list[dict[str, Any]] = []
    # A deterministic ledge and floor, kept small enough for a candidate
    # fixture while still exercising multiple rows and a non-floor platform.
    coordinates = ((0, 8), (1, 8), (2, 8), (3, 8), (4, 8),
                   (2, 5), (3, 5), (4, 5), (7, 3))
    for index, cell in enumerate(coordinates):
        context = _TILEMAP.ValidationContext(
            project_id, revision, project_revision, generation, lease, epoch,
            base["lease_expires_ms"], base["now_ms"], node_rows, (source,),
            tuple(cells))
        request = _request(command_id=f"arena.tilemap.cell.{index}",
            project_id=project_id, operation="scene.tilemap.cell.set",
            lease_id=lease, revision=revision, project_revision=project_revision,
            generation=generation, fencing_epoch=epoch, target="platforms",
            payload={"cell": list(cell), "source_id": 0,
                     "atlas_coords": [0 if index < 5 else 1, 0], "alternative": 0})
        validated = _TILEMAP.validate_request(request, context)
        projection = validated.projection
        commands.append(_detached(command_id=request.command_id,
            operation=request.operation, request=request.as_dict(),
            request_digest=request.digest,
            projection_sha256=_sha(projection), projection=projection))
        cells.append(_TILEMAP.CellState("platforms", cell, 0,
                                        tuple(request.payload["atlas_coords"]), 0))
    return _detached(profile=_TILEMAP.PROFILE, node={"stable_id": "platforms",
        "node_type": "TileMapLayer", "parent_id": "root"},
        source={"source_id": source.source_id, "atlas_revision": source.atlas_revision,
                "atlas_coords": [list(row) for row in source.atlas_coords],
                "alternatives": list(source.alternatives)},
        cells=[list(row.cell) for row in cells], commands=commands,
        cell_count=len(commands), canonical_sha256=_sha({"cells": [list(row.cell) for row in cells],
            "commands": commands}))


def _edge_plan(base: dict[str, Any]) -> dict[str, Any]:
    project_id, revision = base["project_id"], base["revision"]
    project_revision, generation = base["project_revision"], base["generation"]
    lease, epoch = base["lease_id"], base["fencing_epoch"]
    nodes = tuple(_EDGES.EdgeNode(value) for value in
                  ("root", "player", "pickup", "bot"))
    context = _EDGES.EdgeContext(project_id, revision, project_revision,
        generation, lease, epoch, base["lease_expires_ms"], base["now_ms"], nodes)
    proposals = [
        ("scene.signal.connect", "pickup", {"signal_name": "body_entered",
            "target_stable_id": "root", "method": "on_pickup_collected"}),
        ("scene.signal.connect", "bot", {"signal_name": "tree_exited",
            "target_stable_id": "root", "method": "on_bot_defeated"}),
        ("scene.signal.connect", "root", {"signal_name": "child_entered_tree",
            "target_stable_id": "root", "method": "on_respawn_ready"}),
        ("scene.group.assign", "pickup", {"group_name": "arena_pickup"}),
        ("scene.group.assign", "bot", {"group_name": "arena_bot"}),
        ("input.action.define", "root", {"action_name": "arena_pause",
            "physical_key": 80, "deadzone": 0.5}),
        ("input.action.define", "root", {"action_name": "arena_restart",
            "physical_key": 82, "deadzone": 0.5}),
        ("input.action.define", "root", {"action_name": "arena_respawn",
            "physical_key": 70, "deadzone": 0.5}),
    ]
    rows: list[dict[str, Any]] = []
    for index, (operation, target, values) in enumerate(proposals):
        request = _request(command_id=f"arena.edge.{index}", project_id=project_id,
            operation=operation, lease_id=lease, revision=revision,
            project_revision=project_revision, generation=generation,
            fencing_epoch=epoch, target=target, payload=values)
        validated = _EDGES.validate_request(request, context)
        projection = validated.projection
        rows.append(_detached(command_id=request.command_id, operation=operation,
            request=request.as_dict(), request_digest=request.digest,
            projection_sha256=_sha(projection), projection=projection,
            semantic={"pickup": "collect", "bot": "defeat",
                      "arena_pause": "pause", "arena_restart": "restart",
                      "arena_respawn": "respawn"}))
    return _detached(profile=_EDGES.PROFILE, nodes=[node.stable_id for node in nodes],
                     commands=rows, command_count=len(rows),
                     canonical_sha256=_sha(rows))


def _behavior_plan(base: dict[str, Any]) -> dict[str, Any]:
    project_id, revision = base["project_id"], base["revision"]
    project_revision, generation = base["project_revision"], base["generation"]
    lease, epoch = base["lease_id"], base["fencing_epoch"]
    nodes = tuple(_BEHAVIOR.NodeState(value, "CharacterBody2D" if value == "player"
                                      else "Area2D" if value in ("pickup", "bot")
                                      else "Node2D") for value in
                  ("root", "player", "pickup", "bot"))
    context = _BEHAVIOR.ValidationContext(project_id, revision, project_revision,
        generation, lease, epoch, base["lease_expires_ms"], base["now_ms"], nodes)
    specs = [
        ("player", "player_controller", ["idle", "run", "jump", "respawn"], "idle", [
            {"from_state": "idle", "action": "move", "to_state": "run",
             "effects": [{"kind": "move", "params": {"speed": 120}}]},
            {"from_state": "run", "action": "jump", "to_state": "jump",
             "effects": [{"kind": "jump", "params": {"velocity_y": -360}}]},
            {"from_state": "jump", "action": "respawn", "to_state": "respawn",
             "effects": [{"kind": "set_velocity", "params": {"velocity_x": 0, "velocity_y": 0}}]},
        ]),
        ("pickup", "pickup_controller", ["available", "collected"], "available", [
            {"from_state": "available", "action": "collect", "to_state": "collected",
             "effects": [{"kind": "emit_signal", "params": {"signal": "pickup_collected"}}]},
        ]),
        ("bot", "bot_controller", ["active", "defeated"], "active", [
            {"from_state": "active", "action": "defeat", "to_state": "defeated",
             "effects": [{"kind": "emit_signal", "params": {"signal": "bot_defeated"}}]},
        ]),
    ]
    rows: list[dict[str, Any]] = []
    for index, (target, behavior_id, states, initial, transitions) in enumerate(specs):
        payload = {"behavior_id": behavior_id, "states": states,
                   "initial_state": initial, "transitions": transitions}
        request = _request(command_id=f"arena.behavior.{index}", project_id=project_id,
            operation="scene.behavior.create", lease_id=lease, revision=revision,
            project_revision=project_revision, generation=generation,
            fencing_epoch=epoch, target=target, payload=payload)
        validated = _BEHAVIOR.validate_request(request, context)
        projection = validated.projection
        rows.append(_detached(command_id=request.command_id, operation=request.operation,
            request=request.as_dict(), request_digest=request.digest,
            projection_sha256=_sha(projection), projection=projection))
    source_rows = []
    for target, behavior_id, _states, _initial, _transitions in specs:
        descriptor = {"schema": "hh-o2-typed-gameplay-source-reference-1",
                      "owner": target, "behavior_id": behavior_id,
                      "source_path": f"scripts/{target}_controller.gd",
                      "profile": "hh-godot-gameplay-source-1",
                      "typed": True, "source_bytes_observed": False,
                      "native_observed": False}
        source_rows.append(_detached(**descriptor, source_sha256=_sha(descriptor)))
    # Pause/restart are input edge semantics; keep their source references in
    # the same typed manifest without pretending they are behavior effects.
    source_rows.append(_detached(schema="hh-o2-typed-gameplay-source-reference-1",
        owner="root", behavior_id="arena_lifecycle", source_path="scripts/arena_controller.gd",
        profile="hh-godot-gameplay-source-1", typed=True, source_bytes_observed=False,
        native_observed=False, semantics=["pause", "restart", "respawn"],
        source_sha256=_sha({"owner": "root", "semantics": ["pause", "restart", "respawn"]})))
    return _detached(profile=_BEHAVIOR.PROFILE, commands=rows,
        source_references=source_rows, command_count=len(rows),
        canonical_sha256=_sha({"commands": rows, "source_references": source_rows}))


def build_plan() -> dict[str, Any]:
    """Build the canonical, validator-backed arena fixture plan."""
    base = _base_observation()
    tilemap = _tilemap_plan(base)
    edges = _edge_plan(base)
    behavior = _behavior_plan(base)
    body = _detached(schema=SCHEMA, state_kind="PLANNED_NOT_NATIVE",
        fixture="arena_2d", admission=_copy(base), tilemap=tilemap,
        edges=edges, gameplay=behavior,
        validation_scope="STATIC_FIXTURE_ONLY; native adapter/readback pending")
    body["canonical_sha256"] = _sha(body)
    return _copy(body)


def _reject(code: str, detail: str) -> None:
    """Raise the shared fail-closed error for a malformed detached plan."""
    raise ValidationError(code, detail)


def _expect(condition: bool, code: str, detail: str) -> None:
    if not condition:
        _reject(code, detail)


def _check_row(row: object, *, fields: set[str], label: str) -> dict[str, Any]:
    _expect(type(row) is dict and set(row) == fields, "ARENA_PLAN_ROW_SHAPE", label)
    return row  # type: ignore[return-value]


def _check_candidate_row(row: object, *, operation: str, label: str,
                         semantic: bool = False) -> dict[str, Any]:
    value = _check_row(row, fields={"authority", "runtime_authorized", "native_observed",
                                    "execution", "command_id", "operation", "request",
                                    "request_digest", "projection_sha256", "projection",
                                    "semantic"} if semantic else
                              {"authority", "runtime_authorized", "native_observed",
                               "execution", "command_id", "operation", "request",
                               "request_digest", "projection_sha256", "projection"},
                       label=label)
    _expect(value["operation"] == operation, "ARENA_PLAN_OPERATION", label)
    _expect(value["authority"] == AUTHORITY and value["runtime_authorized"] is False
            and value["native_observed"] is False and value["execution"] == DETACHED_MODE,
            "ARENA_PLAN_AUTHORITY", label)
    return value


def _check_projection(row: Mapping[str, Any], validated: Any, label: str) -> None:
    request = row["request"]
    _expect(type(request) is dict, "ARENA_PLAN_REQUEST", label)
    checked = Request.from_dict(_copy(request))
    _expect(row["command_id"] == checked.command_id and row["request_digest"] == checked.digest,
            "ARENA_PLAN_DIGEST", label)
    projection = validated.projection
    _expect(row["projection"] == projection and row["projection_sha256"] == _sha(projection),
            "ARENA_PLAN_PROJECTION", label)


def _validate_tilemap(plan: Mapping[str, Any], base: Mapping[str, Any]) -> None:
    tilemap = plan.get("tilemap")
    _expect(type(tilemap) is dict, "ARENA_PLAN_SECTION", "tilemap")
    expected = _tilemap_plan(dict(base))
    _expect(tilemap["profile"] == expected["profile"] and tilemap["node"] == expected["node"]
            and tilemap["source"] == expected["source"], "ARENA_PLAN_TILEMAP_BINDING", "tilemap")
    rows = tilemap.get("commands")
    _expect(type(rows) is list and tilemap.get("cell_count") == len(rows),
            "ARENA_PLAN_TILEMAP_ROWS", "tilemap")
    nodes = (_TILEMAP.NodeState("root", None, "Node2D", "Arena"),
             _TILEMAP.NodeState("platforms", "root", "TileMapLayer", "Platforms"))
    source = _TILEMAP.TileSourceState(0, expected["source"]["atlas_revision"],
                                      ((0, 0), (1, 0)), (0,))
    cells: list[Any] = []
    for index, raw in enumerate(rows):
        row = _check_candidate_row(raw, operation="scene.tilemap.cell.set",
                                   label=f"tilemap.commands[{index}]")
        context = _TILEMAP.ValidationContext(base["project_id"], base["revision"],
            base["project_revision"], base["generation"], base["lease_id"],
            base["fencing_epoch"], base["lease_expires_ms"], base["now_ms"], nodes,
            (source,), tuple(cells))
        validated = _TILEMAP.validate_request(row["request"], context)
        _check_projection(row, validated, f"tilemap.commands[{index}]")
        payload = dict(Request.from_dict(_copy(row["request"])).payload)
        cells.append(_TILEMAP.CellState("platforms", tuple(payload["cell"]), 0,
                                        tuple(payload["atlas_coords"]), payload["alternative"]))
    _expect(tilemap["cells"] == [list(cell.cell) for cell in cells]
            and tilemap["canonical_sha256"] == _sha({"cells": tilemap["cells"], "commands": rows}),
            "ARENA_PLAN_TILEMAP_HASH", "tilemap")


def _validate_edges(plan: Mapping[str, Any], base: Mapping[str, Any]) -> None:
    edges = plan.get("edges")
    _expect(type(edges) is dict, "ARENA_PLAN_SECTION", "edges")
    expected = _edge_plan(dict(base))
    _expect(edges["profile"] == expected["profile"] and edges["nodes"] == expected["nodes"],
            "ARENA_PLAN_EDGE_BINDING", "edges")
    rows = edges.get("commands")
    _expect(type(rows) is list and edges.get("command_count") == len(rows),
            "ARENA_PLAN_EDGE_ROWS", "edges")
    nodes = tuple(_EDGES.EdgeNode(value) for value in ("root", "player", "pickup", "bot"))
    signals: list[Any] = []
    groups: list[Any] = []
    inputs: list[Any] = []
    for index, raw in enumerate(rows):
        operation = raw.get("operation") if type(raw) is dict else ""
        fields = {"authority", "runtime_authorized", "native_observed", "execution",
                  "command_id", "operation", "request", "request_digest", "projection_sha256",
                  "projection", "semantic"}
        row = _check_row(raw, fields=fields, label=f"edges.commands[{index}]")
        _expect(operation in _EDGES._OPERATIONS, "ARENA_PLAN_EDGE_OPERATION", f"edges.commands[{index}]")
        _expect(row["authority"] == AUTHORITY and row["runtime_authorized"] is False
                and row["native_observed"] is False and row["execution"] == DETACHED_MODE,
                "ARENA_PLAN_AUTHORITY", f"edges.commands[{index}]")
        context = _EDGES.EdgeContext(base["project_id"], base["revision"], base["project_revision"],
            base["generation"], base["lease_id"], base["fencing_epoch"], base["lease_expires_ms"],
            base["now_ms"], nodes, tuple(signals), tuple(groups), tuple(inputs))
        validated = _EDGES.validate_request(row["request"], context)
        _check_projection(row, validated, f"edges.commands[{index}]")
        checked = Request.from_dict(_copy(row["request"]))
        payload = dict(checked.payload)
        target = checked.target["stable_id"]
        if operation == "scene.signal.connect":
            signals.append(_EDGES.SignalEdge(target, payload["signal_name"],
                                               payload["target_stable_id"], payload["method"]))
        elif operation == "scene.group.assign":
            groups.append(_EDGES.GroupEdge(target, payload["group_name"]))
        else:
            inputs.append(_EDGES.InputAction(payload["action_name"], payload["physical_key"],
                                             payload["deadzone"]))
    _expect(edges["canonical_sha256"] == _sha(rows), "ARENA_PLAN_EDGE_HASH", "edges")


def _validate_behavior(plan: Mapping[str, Any], base: Mapping[str, Any]) -> None:
    gameplay = plan.get("gameplay")
    _expect(type(gameplay) is dict, "ARENA_PLAN_SECTION", "gameplay")
    expected = _behavior_plan(dict(base))
    _expect(gameplay["profile"] == expected["profile"]
            and gameplay["source_references"] == expected["source_references"],
            "ARENA_PLAN_BEHAVIOR_BINDING", "gameplay")
    rows = gameplay.get("commands")
    _expect(type(rows) is list and gameplay.get("command_count") == len(rows),
            "ARENA_PLAN_BEHAVIOR_ROWS", "gameplay")
    nodes = tuple(_BEHAVIOR.NodeState(value, "CharacterBody2D" if value == "player"
                                      else "Area2D" if value in ("pickup", "bot") else "Node2D")
                  for value in ("root", "player", "pickup", "bot"))
    behaviors: list[Any] = []
    for index, raw in enumerate(rows):
        row = _check_candidate_row(raw, operation="scene.behavior.create",
                                   label=f"gameplay.commands[{index}]")
        context = _BEHAVIOR.ValidationContext(base["project_id"], base["revision"],
            base["project_revision"], base["generation"], base["lease_id"], base["fencing_epoch"],
            base["lease_expires_ms"], base["now_ms"], nodes, tuple(behaviors))
        validated = _BEHAVIOR.validate_request(row["request"], context)
        _check_projection(row, validated, f"gameplay.commands[{index}]")
        checked = Request.from_dict(_copy(row["request"]))
        payload = dict(checked.payload)
        behaviors.append(_BEHAVIOR.BehaviorState(payload["behavior_id"],
            checked.target["stable_id"], tuple(payload["states"]), payload["initial_state"]))
    _expect(gameplay["canonical_sha256"] == _sha({"commands": rows,
                                                     "source_references": gameplay["source_references"]}),
            "ARENA_PLAN_BEHAVIOR_HASH", "gameplay")


def validate_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a detached plan and every proposal it carries.

    This is an offline verifier only.  It rejects stale admission, unknown
    fields/profiles/operations, altered hashes and validator-rejected rows;
    it never contacts Godot or grants an owner capability.
    """
    _expect(type(value) is dict, "ARENA_PLAN_TYPE", "plan")
    allowed = {"authority", "runtime_authorized", "native_observed", "execution", "schema",
               "state_kind", "fixture", "admission", "tilemap", "edges", "gameplay",
               "validation_scope", "canonical_sha256"}
    _expect(set(value) == allowed, "ARENA_PLAN_UNKNOWN_FIELD", "plan")
    _expect(value["authority"] == AUTHORITY and value["runtime_authorized"] is False
            and value["native_observed"] is False and value["execution"] == DETACHED_MODE
            and value["schema"] == SCHEMA and value["state_kind"] == "PLANNED_NOT_NATIVE"
            and value["fixture"] == "arena_2d", "ARENA_PLAN_AUTHORITY", "plan")
    _expect(value["canonical_sha256"] == _sha({k: value[k] for k in value if k != "canonical_sha256"}),
            "ARENA_PLAN_HASH", "plan")
    base = _base_observation()
    _expect(value["admission"] == base, "ARENA_PLAN_STALE_ADMISSION", "admission")
    _validate_tilemap(value, base)
    _validate_edges(value, base)
    _validate_behavior(value, base)
    return _copy(value)


def source_paths() -> tuple[str, ...]:
    """Files whose code defines this plan; no generated/native output is listed."""
    return ("tests/godot/arena_fixture_plan.py", "godot-addon/tilemap_authoring.py",
            "godot-addon/gameplay_edges.py", "godot-addon/gameplay_behavior.py",
            "protocol/__init__.py", "protocol/core.py",
            "protocol/_rfc8785/__init__.py", "protocol/_rfc8785/_impl.py")


if __name__ == "__main__":
    import json
    print(json.dumps(build_plan(), sort_keys=True, separators=(",", ":")))
