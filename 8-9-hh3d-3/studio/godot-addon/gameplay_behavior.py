"""Authority-0 declarative gameplay behavior candidate.

This is a bounded data contract for deterministic state transitions and typed
effects. It deliberately accepts no GDScript text, expressions, resource
paths, method names or executable hooks. Native execution, sandboxing and
publication remain separate gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

PROFILE = "hh-godot-declarative-gameplay-1"
OPERATIONS = ("scene.behavior.create", "scene.behavior.remove")
AUTHORITY = 0
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_STATE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
_ACTION = re.compile(r"[a-z][a-z0-9._-]{0,47}\Z")
_EFFECTS = frozenset(("move", "jump", "set_velocity", "face", "emit_signal", "play_animation"))
_PARAMS = frozenset(("speed", "velocity_x", "velocity_y", "angle", "animation"))
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")


class BehaviorContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, "O2 declarative gameplay candidate validation; no effect authorized")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise BehaviorContractError(code)


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _state(value: object) -> bool:
    return type(value) is str and _STATE.fullmatch(value) is not None


def _action(value: object) -> bool:
    return type(value) is str and _ACTION.fullmatch(value) is not None


def _number(value: object) -> bool:
    return type(value) in (int, float) and abs(value) <= SAFE_INTEGER and math.isfinite(value)


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    node_type: str


@dataclass(frozen=True, slots=True)
class BehaviorState:
    behavior_id: str
    owner_stable_id: str
    states: tuple[str, ...]
    initial_state: str


@dataclass(frozen=True, slots=True)
class ValidationContext:
    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    nodes: tuple[NodeState, ...]
    behaviors: tuple[BehaviorState, ...] = ()
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedBehavior:
    request_digest: str
    requested_operation: str
    _projection: bytes
    _preview: bytes

    @property
    def projection(self) -> dict[str, Any]:
        return parse_json(self._projection)

    @property
    def preview(self) -> dict[str, Any]:
        return parse_json(self._preview)


def _context(context: ValidationContext) -> tuple[dict[str, NodeState], dict[str, BehaviorState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, "BEHAVIOR_TRUSTED_CONTEXT_REQUIRED")
    _need(_id(context.project_id) and _id(context.lease_id), "BEHAVIOR_CONTEXT_ID")
    _need(type(context.revision) is str and _REV.fullmatch(context.revision)
          and type(context.project_revision) is str and _REV.fullmatch(context.project_revision), "BEHAVIOR_REVISION")
    _need(type(context.generation) is int and 1 <= context.generation <= 2147483647
          and type(context.stopped) is bool, "BEHAVIOR_CONTEXT")
    _need(all(type(value) is int and 0 <= value <= SAFE_INTEGER
              for value in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)), "BEHAVIOR_CONTEXT")
    nodes: dict[str, NodeState] = {}
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 256, "BEHAVIOR_NODE_STATE")
    for node in context.nodes:
        _need(type(node) is NodeState and _id(node.stable_id) and node.stable_id not in nodes
              and node.node_type in ("Node2D", "CharacterBody2D", "Area2D", "Node3D", "CharacterBody3D", "Area3D"),
              "BEHAVIOR_NODE_STATE")
        nodes[node.stable_id] = node
    behaviors: dict[str, BehaviorState] = {}
    _need(type(context.behaviors) is tuple and len(context.behaviors) <= 128, "BEHAVIOR_STATE_LIMIT")
    for behavior in context.behaviors:
        _need(type(behavior) is BehaviorState and _id(behavior.behavior_id)
              and behavior.behavior_id not in behaviors and behavior.owner_stable_id in nodes
              and type(behavior.states) is tuple and 1 <= len(behavior.states) <= 32
              and len(set(behavior.states)) == len(behavior.states) and all(_state(value) for value in behavior.states)
              and behavior.initial_state in behavior.states, "BEHAVIOR_STATE")
        behaviors[behavior.behavior_id] = behavior
    return nodes, behaviors


def _validate_transitions(raw: object, states: set[str], nodes: Mapping[str, NodeState]) -> list[dict[str, Any]]:
    _need(type(raw) is list and 1 <= len(raw) <= 128, "BEHAVIOR_TRANSITION_SHAPE")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw:
        _need(type(row) is dict and set(row) == {"from_state", "action", "to_state", "effects"}, "BEHAVIOR_TRANSITION_SHAPE")
        source, action, target = row["from_state"], row["action"], row["to_state"]
        _need(_state(source) and source in states and _action(action)
              and _state(target) and target in states, "BEHAVIOR_TRANSITION_TARGET")
        _need((source, action) not in seen, "BEHAVIOR_DUPLICATE_TRANSITION")
        seen.add((source, action))
        effects = row["effects"]
        _need(type(effects) is list and 0 <= len(effects) <= 8, "BEHAVIOR_EFFECT_SHAPE")
        checked_effects: list[dict[str, Any]] = []
        for effect in effects:
            _need(type(effect) is dict and set(effect) == {"kind", "params"}
                  and effect["kind"] in _EFFECTS and type(effect["params"]) is dict
                  and set(effect["params"]) <= _PARAMS, "BEHAVIOR_EFFECT_SHAPE")
            params = _copy(effect["params"])
            for key, value in params.items():
                if key == "animation":
                    _need(_state(value), "BEHAVIOR_EFFECT_VALUE")
                else:
                    _need(_number(value) and abs(value) <= 10000, "BEHAVIOR_EFFECT_VALUE")
            checked_effects.append({"kind": effect["kind"], "params": params})
        result.append({"from_state": source, "action": action, "to_state": target, "effects": checked_effects})
    return result


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedBehavior:
    nodes, behaviors = _context(context)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation in OPERATIONS and _id(checked.command_id), "BEHAVIOR_OPERATION")
    _need(checked.project_id == context.project_id, "BEHAVIOR_PROJECT_MISMATCH")
    _need(checked.expected_revision == context.revision, "BEHAVIOR_STALE_REVISION")
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, "BEHAVIOR_STALE_LEASE")
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000), "BEHAVIOR_DEADLINE")
    _need(not context.stopped, "BEHAVIOR_STOPPED")
    target = dict(checked.target)
    payload = dict(checked.payload)
    _need(set(target) == {"stable_id"} and _id(target["stable_id"]), "BEHAVIOR_TARGET")
    owner = target["stable_id"]
    _need(owner in nodes, "BEHAVIOR_TARGET")
    common = {"expected_generation", "expected_project_revision", "behavior_id"}
    _need(type(payload.get("expected_generation")) is int and payload["expected_generation"] == context.generation,
          "BEHAVIOR_STALE_GENERATION")
    _need(payload.get("expected_project_revision") == context.project_revision, "BEHAVIOR_STALE_PROJECT_REVISION")
    behavior_id = payload.get("behavior_id")
    _need(_id(behavior_id), "BEHAVIOR_ID")
    if checked.operation == "scene.behavior.create":
        _need(set(payload) == common | {"states", "initial_state", "transitions"}, "BEHAVIOR_CREATE_SHAPE")
        states = payload["states"]
        _need(type(states) is list and 1 <= len(states) <= 32 and len(set(states)) == len(states)
              and all(_state(value) for value in states) and _state(payload["initial_state"])
              and payload["initial_state"] in states and behavior_id not in behaviors, "BEHAVIOR_STATES")
        transitions = _validate_transitions(payload["transitions"], set(states), nodes)
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "target_stable_id": owner, "behavior_id": behavior_id, "states": list(states),
                      "initial_state": payload["initial_state"], "transitions": transitions}
        pending = ["deterministic_dispatch", "native_script_boundary", "sandbox", "readback", "undo"]
    else:
        _need(set(payload) == common and behavior_id in behaviors
              and behaviors[behavior_id].owner_stable_id == owner, "BEHAVIOR_REMOVE_SHAPE")
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "target_stable_id": owner, "behavior_id": behavior_id}
        pending = ["native_script_boundary", "sandbox", "readback", "undo"]
    binding = {"profile": PROFILE, "authority": AUTHORITY, "project_id": context.project_id,
               "project_revision": context.project_revision, "scene_revision": context.revision,
               "request_digest": checked.digest, "changes_applied": False,
               "runtime_authorized": False, "native_verified": False}
    projection.update(binding)
    preview = {**binding, "behavior_id": behavior_id, "native_tests_pending": pending}
    return ValidatedBehavior(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))
