"""Authority-0 candidate contract for typed PackedScene instances.

The validator only checks a trusted scene-source manifest and a trusted node
snapshot. It never loads a path, calls PackedScene, edits a scene, or emits an
ACK. A future native owner must re-read the source hash and parent identity on
the Godot main thread before applying the projection.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from studio.protocol.core import Request, SAFE_INTEGER, ValidationError, canonical_bytes, parse_json

PROFILE = "hh-godot-scene-instance-1"
OPERATIONS = ("scene.instance.create", "scene.instance.remove")
AUTHORITY = 0
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,47}\Z")
_CLASS = re.compile(r"[A-Z][A-Za-z0-9_]*\Z")
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SCENE_PATH = re.compile(r"scenes/[A-Za-z][A-Za-z0-9_.-]{0,63}\.tscn\Z")
_ROOT_TYPES = frozenset(("Node2D", "Node3D"))


class InstanceContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, "O2 scene-instance candidate validation; no effect authorized")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise InstanceContractError(code)


def _matches(value: object, pattern: re.Pattern[str]) -> bool:
    return type(value) is str and pattern.fullmatch(value) is not None


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def _vector(value: object, arity: int, *, positive: bool = False) -> bool:
    return (type(value) is list and len(value) == arity
            and all(type(item) in (int, float) and abs(item) <= SAFE_INTEGER
                    and math.isfinite(item) and (not positive or item > 0) for item in value))


@dataclass(frozen=True, slots=True)
class NodeState:
    stable_id: str
    parent_id: str | None
    node_type: str
    name: str


@dataclass(frozen=True, slots=True)
class SceneSourceState:
    scene_id: str
    path: str
    revision: str
    root_type: str


@dataclass(frozen=True, slots=True)
class InstanceState:
    instance_id: str
    scene_id: str
    parent_id: str
    name: str
    source_revision: str


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
    scenes: tuple[SceneSourceState, ...]
    instances: tuple[InstanceState, ...] = ()
    stopped: bool = False
    profile: str = PROFILE


@dataclass(frozen=True, slots=True)
class ValidatedInstance:
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


def _context(context: ValidationContext) -> tuple[dict[str, NodeState], dict[str, SceneSourceState], dict[str, InstanceState]]:
    _need(type(context) is ValidationContext and context.profile == PROFILE, "INSTANCE_TRUSTED_CONTEXT_REQUIRED")
    _need(_matches(context.project_id, _ID) and _matches(context.lease_id, _ID), "INSTANCE_CONTEXT_ID")
    _need(_matches(context.revision, _REV) and _matches(context.project_revision, _REV), "INSTANCE_REVISION")
    _need(type(context.generation) is int and 1 <= context.generation <= 2147483647
          and type(context.stopped) is bool, "INSTANCE_CONTEXT")
    _need(all(type(value) is int and 0 <= value <= SAFE_INTEGER
              for value in (context.fencing_epoch, context.lease_expires_ms, context.now_ms)), "INSTANCE_CONTEXT")
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 256, "INSTANCE_NODE_STATE")
    nodes: dict[str, NodeState] = {}
    for node in context.nodes:
        _need(type(node) is NodeState and _matches(node.stable_id, _ID)
              and node.stable_id not in nodes and _matches(node.node_type, _CLASS)
              and _matches(node.name, _NAME), "INSTANCE_NODE_STATE")
        _need(node.parent_id is None or _matches(node.parent_id, _ID), "INSTANCE_NODE_STATE")
        nodes[node.stable_id] = node
    _need("root" in nodes and nodes["root"].parent_id is None
          and sum(node.parent_id is None for node in nodes.values()) == 1, "INSTANCE_HIERARCHY")
    for node in nodes.values():
        seen: set[str] = set()
        current: str | None = node.stable_id
        while current is not None:
            _need(current in nodes and current not in seen, "INSTANCE_HIERARCHY")
            seen.add(current)
            _need(len(seen) <= 32, "INSTANCE_DEPTH_LIMIT")
            current = nodes[current].parent_id
    _need(type(context.scenes) is tuple and 1 <= len(context.scenes) <= 128, "INSTANCE_SCENE_LIMIT")
    scenes: dict[str, SceneSourceState] = {}
    paths: set[str] = set()
    for scene in context.scenes:
        _need(type(scene) is SceneSourceState and _matches(scene.scene_id, _ID)
              and scene.scene_id not in scenes and _matches(scene.path, _SCENE_PATH)
              and scene.path not in paths and _matches(scene.revision, _REV)
              and scene.root_type in _ROOT_TYPES, "INSTANCE_SCENE_STATE")
        scenes[scene.scene_id] = scene
        paths.add(scene.path)
    _need(type(context.instances) is tuple and len(context.instances) <= 256, "INSTANCE_STATE_LIMIT")
    instances: dict[str, InstanceState] = {}
    for instance in context.instances:
        _need(type(instance) is InstanceState and _matches(instance.instance_id, _ID)
              and instance.instance_id not in instances and instance.scene_id in scenes
              and instance.parent_id in nodes and _matches(instance.name, _NAME)
              and _matches(instance.source_revision, _REV)
              and instance.source_revision == scenes[instance.scene_id].revision,
              "INSTANCE_STATE")
        instances[instance.instance_id] = instance
    return nodes, scenes, instances


def validate_request(request: Request | Mapping[str, Any], context: ValidationContext) -> ValidatedInstance:
    """Validate a detached scene-instance proposal against trusted state."""
    nodes, scenes, instances = _context(context)
    checked = Request.from_dict(_copy(request.as_dict() if type(request) is Request else request))
    _need(checked.operation in OPERATIONS and _matches(checked.command_id, _ID), "INSTANCE_OPERATION")
    _need(checked.project_id == context.project_id, "INSTANCE_PROJECT_MISMATCH")
    _need(checked.expected_revision == context.revision, "INSTANCE_STALE_REVISION")
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch, "INSTANCE_STALE_LEASE")
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000), "INSTANCE_DEADLINE")
    _need(not context.stopped, "INSTANCE_STOPPED")
    target = dict(checked.target)
    payload = dict(checked.payload)
    _need(set(target) == {"stable_id"} and _matches(target["stable_id"], _ID), "INSTANCE_TARGET")
    common = {"expected_generation", "expected_project_revision"}
    _need(type(payload.get("expected_generation")) is int and payload["expected_generation"] == context.generation,
          "INSTANCE_STALE_GENERATION")
    _need(payload.get("expected_project_revision") == context.project_revision, "INSTANCE_STALE_PROJECT_REVISION")
    if checked.operation == "scene.instance.create":
        _need(set(payload) == common | {"scene_id", "instance_stable_id", "instance_name", "position", "rotation_degrees", "scale"},
              "INSTANCE_CREATE_SHAPE")
        scene_id = payload["scene_id"]
        instance_id = payload["instance_stable_id"]
        _need(_matches(scene_id, _ID) and scene_id in scenes, "INSTANCE_SCENE_UNKNOWN")
        _need(_matches(instance_id, _ID) and instance_id not in instances and instance_id not in nodes,
              "INSTANCE_DUPLICATE_ID")
        _need(_matches(payload["instance_name"], _NAME), "INSTANCE_NAME")
        _need(_vector(payload["position"], 2 if scenes[scene_id].root_type == "Node2D" else 3)
              and _vector(payload["rotation_degrees"], 1 if scenes[scene_id].root_type == "Node2D" else 3)
              and _vector(payload["scale"], 2 if scenes[scene_id].root_type == "Node2D" else 3, positive=True),
              "INSTANCE_TRANSFORM")
        parent = nodes.get(target["stable_id"])
        _need(parent is not None and (scenes[scene_id].root_type == "Node2D"
              and parent.node_type in ("Node", "Node2D")
              or scenes[scene_id].root_type == "Node3D"
              and parent.node_type in ("Node", "Node3D")), "INSTANCE_PARENT_TYPE")
        projection_payload = {key: value for key, value in payload.items() if key != "expected_project_revision"}
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "parent_stable_id": target["stable_id"], "scene_id": scene_id,
                      "source_revision": scenes[scene_id].revision, "payload": projection_payload}
        preview = {"profile": PROFILE, "authority": AUTHORITY, "command_id": checked.command_id,
                   "request_digest": checked.digest, "scene_revision": context.revision,
                   "project_revision": context.project_revision, "scene_id": scene_id,
                   "source_path": scenes[scene_id].path, "source_revision": scenes[scene_id].revision,
                   "changes_applied": False, "runtime_authorized": False, "native_verified": False}
    else:
        _need(set(payload) == common | {"instance_stable_id"}, "INSTANCE_REMOVE_SHAPE")
        instance_id = payload["instance_stable_id"]
        _need(_matches(instance_id, _ID) and target["stable_id"] == instance_id, "INSTANCE_TARGET")
        state = instances.get(instance_id)
        _need(state is not None and state.source_revision == scenes[state.scene_id].revision, "INSTANCE_STALE_STATE")
        projection = {"operation": checked.operation, "command_id": checked.command_id,
                      "expected_revision": context.revision, "expected_generation": context.generation,
                      "instance_stable_id": instance_id, "parent_stable_id": state.parent_id,
                      "scene_id": state.scene_id}
        preview = {"profile": PROFILE, "authority": AUTHORITY, "command_id": checked.command_id,
                   "request_digest": checked.digest, "scene_revision": context.revision,
                   "project_revision": context.project_revision, "scene_id": state.scene_id,
                   "source_revision": state.source_revision, "changes_applied": False,
                   "runtime_authorized": False, "native_verified": False}
    return ValidatedInstance(checked.digest, checked.operation, canonical_bytes(projection), canonical_bytes(preview))
