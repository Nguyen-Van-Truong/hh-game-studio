"""Authority-0 candidate contract for typed Godot AnimationPlayer libraries."""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

PROFILE = "hh-godot-animation-library-1"
OPERATIONS = ("scene.animation.create", "scene.animation.remove")
AUTHORITY = 0
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,47}\Z")
_PROPERTY = frozenset(("position", "rotation_degrees", "scale"))
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_TIME = 3600.0


class AnimationContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, "O2 animation candidate validation; no effect authorized")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise AnimationContractError(code)


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _revision(value: object) -> bool:
    return type(value) is str and _REV.fullmatch(value) is not None


def _number(value: object) -> bool:
    return type(value) in (int, float) and abs(value) <= SAFE_INTEGER and math.isfinite(value)


def _vector(value: object, arity: int, *, positive: bool = False) -> bool:
    return (type(value) is list and len(value) == arity and all(
        _number(item) and (not positive or item > 0) for item in value))


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str


@dataclass(frozen=True, slots=True)
class AnimationTrackState:
    node_stable_id: str
    property: str
    keys: tuple[tuple[float, float | tuple[float, ...]], ...]


@dataclass(frozen=True, slots=True)
class AnimationState:
    animation_id: str
    owner_stable_id: str
    length: float
    loop_mode: int
    tracks: tuple[AnimationTrackState, ...]


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
    animations: tuple[AnimationState, ...] = ()
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedAnimation:
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


def _context(context: ValidationContext) -> tuple[dict[str, NodeState], dict[str, AnimationState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, "ANIMATION_TRUSTED_CONTEXT_REQUIRED")
    _need(_id(context.project_id) and _id(context.lease_id), "ANIMATION_CONTEXT_ID")
    _need(_revision(context.revision) and _revision(context.project_revision), "ANIMATION_REVISION")
    _need(type(context.generation) is int and 1 <= context.generation <= 2147483647
          and type(context.stopped) is bool, "ANIMATION_CONTEXT")
    _need(all(type(value) is int and 0 <= value <= SAFE_INTEGER
              for value in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)), "ANIMATION_CONTEXT")
    nodes: dict[str, NodeState] = {}
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 256, "ANIMATION_NODE_STATE")
    for node in context.nodes:
        _need(type(node) is NodeState and _id(node.stable_id) and node.stable_id not in nodes
              and type(node.node_type) is str and node.node_type in ("Node2D", "Node3D", "AnimationPlayer")
              and type(node.name) is str and _NAME.fullmatch(node.name) is not None,
              "ANIMATION_NODE_STATE")
        _need(node.parent_id is None or _id(node.parent_id), "ANIMATION_HIERARCHY")
        nodes[node.stable_id] = node
    _need("root" in nodes and nodes["root"].parent_id is None
          and sum(node.parent_id is None for node in nodes.values()) == 1, "ANIMATION_HIERARCHY")
    siblings: set[tuple[str | None, str]] = set()
    for node in nodes.values():
        sibling = (node.parent_id, node.name.lower())
        _need(sibling not in siblings, "ANIMATION_DUPLICATE_NAME")
        siblings.add(sibling)
        current, seen = node.stable_id, set()
        while current is not None:
            _need(current in nodes and current not in seen and len(seen) < 32, "ANIMATION_HIERARCHY")
            seen.add(current)
            current = nodes[current].parent_id
    animations: dict[str, AnimationState] = {}
    _need(type(context.animations) is tuple and len(context.animations) <= 128, "ANIMATION_STATE_LIMIT")
    for animation in context.animations:
        _need(type(animation) is AnimationState and _id(animation.animation_id)
              and animation.animation_id not in animations and _id(animation.owner_stable_id)
              and animation.owner_stable_id in nodes
              and nodes[animation.owner_stable_id].node_type == "AnimationPlayer"
              and _number(animation.length) and 0 < animation.length <= _MAX_TIME
              and type(animation.loop_mode) is int and animation.loop_mode in (0, 1),
              "ANIMATION_STATE")
        _need(type(animation.tracks) is tuple and len(animation.tracks) <= 32, "ANIMATION_STATE")
        tracks = []
        for track in animation.tracks:
            _need(type(track) is AnimationTrackState and type(track.keys) is tuple, "ANIMATION_STATE")
            keys = []
            for key in track.keys:
                _need(type(key) is tuple and len(key) == 2
                      and (_number(key[1]) or type(key[1]) is tuple), "ANIMATION_STATE")
                keys.append([key[0], list(key[1]) if type(key[1]) is tuple else key[1]])
            tracks.append({"node_stable_id": track.node_stable_id, "property": track.property, "keys": keys})
        if tracks:
            _validate_tracks(tracks, nodes, float(animation.length))
        animations[animation.animation_id] = animation
    return nodes, animations


def _validate_tracks(raw: object, nodes: Mapping[str, NodeState], length: float) -> list[dict[str, Any]]:
    _need(type(raw) is list and 1 <= len(raw) <= 32, "ANIMATION_TRACK_SHAPE")
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for track in raw:
        _need(type(track) is dict and set(track) == {"node_stable_id", "property", "keys"}, "ANIMATION_TRACK_SHAPE")
        node_id, property_name, keys = track["node_stable_id"], track["property"], track["keys"]
        _need(_id(node_id) and node_id in nodes and nodes[node_id].node_type in ("Node2D", "Node3D")
              and type(property_name) is str and property_name in _PROPERTY, "ANIMATION_TRACK_TARGET")
        _need((node_id, property_name) not in seen, "ANIMATION_DUPLICATE_TRACK")
        seen.add((node_id, property_name))
        arity = 2 if nodes[node_id].node_type == "Node2D" else 3
        scalar = arity == 2 and property_name == "rotation_degrees"
        _need(type(keys) is list and 1 <= len(keys) <= 128, "ANIMATION_KEY_SHAPE")
        checked_keys: list[list[Any]] = []
        previous = -1.0
        for key in keys:
            _need(type(key) is list and len(key) == 2 and _number(key[0])
                  and 0 <= key[0] <= length and key[0] > previous
                  and (_number(key[1]) if scalar else
                       _vector(key[1], arity, positive=property_name == "scale")), "ANIMATION_KEY_SHAPE")
            previous = float(key[0])
            checked_keys.append([key[0], key[1] if scalar else list(key[1])])
        parts, current = [], node_id
        while current != "root":
            parts.insert(0, nodes[current].name)
            current = nodes[current].parent_id
        result.append({"node_stable_id": node_id, "node_type": nodes[node_id].node_type,
                       "node_path": "/".join(parts) or ".", "property": property_name, "keys": checked_keys})
    return result


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedAnimation:
    nodes, animations = _context(context)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation in OPERATIONS and _id(checked.command_id), "ANIMATION_OPERATION")
    _need(checked.project_id == context.project_id, "ANIMATION_PROJECT_MISMATCH")
    _need(checked.expected_revision == context.revision, "ANIMATION_STALE_REVISION")
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, "ANIMATION_STALE_LEASE")
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000), "ANIMATION_DEADLINE")
    _need(not context.stopped, "ANIMATION_STOPPED")
    target = dict(checked.target)
    payload = dict(checked.payload)
    _need(set(target) == {"stable_id"} and _id(target["stable_id"]), "ANIMATION_TARGET")
    owner = target["stable_id"]
    _need(owner in nodes and nodes[owner].node_type == "AnimationPlayer", "ANIMATION_TARGET_TYPE")
    common = {"expected_generation", "expected_project_revision", "animation_id"}
    _need(type(payload.get("expected_generation")) is int
          and payload["expected_generation"] == context.generation, "ANIMATION_STALE_GENERATION")
    _need(payload.get("expected_project_revision") == context.project_revision, "ANIMATION_STALE_PROJECT_REVISION")
    animation_id = payload.get("animation_id")
    _need(_id(animation_id), "ANIMATION_ID")
    if checked.operation == "scene.animation.create":
        _need(set(payload) == common | {"length", "loop_mode", "tracks"}, "ANIMATION_CREATE_SHAPE")
        _need(animation_id not in animations and _number(payload["length"])
              and 0 < payload["length"] <= _MAX_TIME and type(payload["loop_mode"]) is int
              and payload["loop_mode"] in (0, 1), "ANIMATION_PROPERTIES")
        tracks = _validate_tracks(payload["tracks"], nodes, float(payload["length"]))
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "target_stable_id": owner, "animation_id": animation_id,
                      "length": payload["length"], "loop_mode": payload["loop_mode"], "tracks": tracks}
        preview = {"profile": PROFILE, "authority": AUTHORITY, "command_id": checked.command_id,
                   "request_digest": checked.digest, "animation_id": animation_id,
                   "changes_applied": False, "runtime_authorized": False,
                   "native_tests_pending": ["library", "tracks", "readback", "undo"]}
    else:
        _need(set(payload) == common and animation_id in animations, "ANIMATION_REMOVE_SHAPE")
        _need(animations[animation_id].owner_stable_id == owner, "ANIMATION_OWNER_MISMATCH")
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "target_stable_id": owner, "animation_id": animation_id}
        preview = {"profile": PROFILE, "authority": AUTHORITY, "command_id": checked.command_id,
                   "request_digest": checked.digest, "animation_id": animation_id,
                   "changes_applied": False, "runtime_authorized": False,
                   "native_tests_pending": ["library", "readback", "undo"]}
    binding = {"profile": PROFILE, "authority": AUTHORITY, "project_id": context.project_id,
               "project_revision": context.project_revision, "scene_revision": context.revision,
               "request_digest": checked.digest, "changes_applied": False, "runtime_authorized": False,
               "animation_root_stable_id": "root", "native_verified": False}
    projection.update(binding)
    preview.update(binding)
    return ValidatedAnimation(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))
