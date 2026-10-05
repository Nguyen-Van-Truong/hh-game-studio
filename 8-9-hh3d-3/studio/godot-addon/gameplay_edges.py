"""Authority-0 candidate contract for gameplay scene edges.

This module validates proposals for signal connections, group membership, and
input actions before a future registered Godot owner exists. It never contacts
Godot, edits a scene, executes script, grants a capability, or emits an ACK.
Native readback, UndoRedo, lease ownership, project-revision fencing, and
AUTH-01..05 remain required at integration time.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping

from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

PROFILE = "hh-godot-gameplay-edges-1"
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,47}\Z")
_ACTION = re.compile(r"[a-z][a-z0-9._-]{0,47}\Z")
_REVISION = re.compile(r"sha256:[0-9a-f]{64}\Z")
_OPERATIONS = ("scene.signal.connect", "scene.group.assign", "input.action.define")


class EdgeContractError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, code)


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise EdgeContractError(code)


def _id(value: object) -> bool:
    return type(value) is str and _ID.fullmatch(value) is not None


def _name(value: object) -> bool:
    return type(value) is str and _NAME.fullmatch(value) is not None


def _action(value: object) -> bool:
    return type(value) is str and _ACTION.fullmatch(value) is not None


@dataclass(frozen=True, slots=True)
class EdgeNode:
    stable_id: str


@dataclass(frozen=True, slots=True)
class SignalEdge:
    source_id: str
    signal_name: str
    target_id: str
    method: str


@dataclass(frozen=True, slots=True)
class GroupEdge:
    node_id: str
    group_name: str


@dataclass(frozen=True, slots=True)
class InputAction:
    action_name: str
    physical_key: int
    deadzone: float = 0.5


@dataclass(frozen=True, slots=True)
class EdgeContext:
    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int
    nodes: tuple[EdgeNode, ...]
    signals: tuple[SignalEdge, ...] = ()
    groups: tuple[GroupEdge, ...] = ()
    inputs: tuple[InputAction, ...] = ()
    stopped: bool = False


@dataclass(frozen=True, slots=True)
class ValidatedEdge:
    request_digest: str
    operation: str
    _projection: bytes

    @property
    def projection(self) -> dict[str, Any]:
        return parse_json(self._projection)


def _context(context: EdgeContext) -> tuple[set[str], set[tuple[str, str, str, str]], set[tuple[str, str]], set[str]]:
    _need(type(context) is EdgeContext and _id(context.project_id) and _id(context.lease_id), "EDGE_CONTEXT")
    _need(type(context.revision) is str and _REVISION.fullmatch(context.revision)
          and type(context.project_revision) is str and _REVISION.fullmatch(context.project_revision),
          "EDGE_CONTEXT")
    _need(type(context.generation) is int and context.generation >= 1, "EDGE_CONTEXT")
    _need(type(context.fencing_epoch) is int and context.fencing_epoch >= 0, "EDGE_CONTEXT")
    _need(all(type(value) is int and value >= 0 for value in
              (context.lease_expires_ms, context.now_ms)), "EDGE_CONTEXT")
    _need(type(context.stopped) is bool and not context.stopped, "EDGE_STOPPED")
    _need(type(context.nodes) is tuple and 1 <= len(context.nodes) <= 256, "EDGE_NODE_STATE")
    nodes = {node.stable_id for node in context.nodes
             if type(node) is EdgeNode and _id(node.stable_id)}
    _need(len(nodes) == len(context.nodes), "EDGE_NODE_STATE")
    _need(type(context.signals) is tuple, "EDGE_SIGNAL_STATE")
    signal_rows = {(row.source_id, row.signal_name, row.target_id, row.method)
                   for row in context.signals
                   if type(row) is SignalEdge and _id(row.source_id) and _name(row.signal_name)
                   and _id(row.target_id) and _name(row.method)
                   and row.source_id in nodes and row.target_id in nodes}
    _need(len(signal_rows) == len(context.signals), "EDGE_SIGNAL_STATE")
    _need(type(context.groups) is tuple, "EDGE_GROUP_STATE")
    group_rows = {(row.node_id, row.group_name) for row in context.groups
                  if type(row) is GroupEdge and _id(row.node_id)
                  and row.node_id in nodes and _id(row.group_name)}
    _need(len(group_rows) == len(context.groups), "EDGE_GROUP_STATE")
    _need(type(context.inputs) is tuple, "EDGE_INPUT_STATE")
    input_rows = {row.action_name for row in context.inputs
                  if type(row) is InputAction and _action(row.action_name)
                  and type(row.physical_key) is int and 0 <= row.physical_key <= 65535
                  and type(row.deadzone) is float and math.isfinite(row.deadzone)
                  and 0.0 <= row.deadzone <= 1.0}
    _need(len(input_rows) == len(context.inputs), "EDGE_INPUT_STATE")
    return nodes, signal_rows, group_rows, input_rows


def validate_request(request: Request | Mapping[str, Any], context: EdgeContext) -> ValidatedEdge:
    """Validate an immutable edge proposal; never applies it."""
    nodes, signals, groups, inputs = _context(context)
    checked = Request.from_dict(parse_json(canonical_bytes(
        request.as_dict() if type(request) is Request else request)))
    _need(checked.operation in _OPERATIONS, "EDGE_OPERATION_DISABLED")
    _need(_id(checked.command_id) and checked.project_id == context.project_id, "EDGE_REQUEST_BINDING")
    _need(checked.expected_revision == context.revision, "EDGE_STALE_REVISION")
    _need(checked.lease_id == context.lease_id and checked.fencing_epoch == context.fencing_epoch,
          "EDGE_STALE_LEASE")
    _need(context.now_ms < checked.deadline_ms <= min(context.lease_expires_ms, context.now_ms + 30000),
          "EDGE_DEADLINE")
    payload = dict(checked.payload)
    _need(type(payload.get("expected_generation")) is int
          and payload["expected_generation"] == context.generation, "EDGE_STALE_GENERATION")
    _need(type(payload.get("expected_project_revision")) is str
          and _REVISION.fullmatch(payload["expected_project_revision"]) is not None,
          "EDGE_PROJECT_REVISION")
    _need(payload["expected_project_revision"] == context.project_revision,
          "EDGE_STALE_PROJECT_REVISION")
    target = dict(checked.target)
    _need(set(target) == {"stable_id"} and _id(target["stable_id"]), "EDGE_TARGET")
    if checked.operation == "scene.signal.connect":
        _need(target["stable_id"] in nodes, "EDGE_TARGET")
        _need(set(payload) == {"expected_generation", "expected_project_revision", "signal_name", "target_stable_id", "method"},
              "EDGE_SIGNAL_SHAPE")
        row = (target["stable_id"], payload["signal_name"], payload["target_stable_id"], payload["method"])
        _need(_name(payload["signal_name"]) and _id(payload["target_stable_id"])
              and payload["target_stable_id"] in nodes and _name(payload["method"]), "EDGE_SIGNAL")
        _need(row not in signals, "EDGE_DUPLICATE_SIGNAL")
        after = {"source_id": row[0], "signal_name": row[1], "target_id": row[2], "method": row[3]}
    elif checked.operation == "scene.group.assign":
        _need(set(payload) == {"expected_generation", "expected_project_revision", "group_name"}
              and target["stable_id"] in nodes and _id(payload["group_name"]), "EDGE_GROUP")
        row = (target["stable_id"], payload["group_name"])
        _need(row not in groups, "EDGE_DUPLICATE_GROUP")
        after = {"node_id": row[0], "group_name": row[1]}
    else:
        _need(target["stable_id"] == "root" and "root" in nodes
              and set(payload) == {"expected_generation", "expected_project_revision", "action_name", "physical_key", "deadzone"},
              "EDGE_INPUT")
        _need(_action(payload["action_name"])
              and type(payload["physical_key"]) is int and 0 <= payload["physical_key"] <= 65535
              and type(payload["deadzone"]) is float and math.isfinite(payload["deadzone"])
              and 0.0 <= payload["deadzone"] <= 1.0, "EDGE_INPUT")
        _need(payload["action_name"] not in inputs, "EDGE_DUPLICATE_INPUT")
        after = {"action_name": payload["action_name"], "physical_key": payload["physical_key"],
                 "deadzone": payload["deadzone"]}
    projection = {"profile": PROFILE, "operation": checked.operation,
                  "command_id": checked.command_id, "request_digest": checked.digest,
                  "expected_revision": context.revision, "project_revision": context.project_revision,
                  "expected_project_revision": context.project_revision,
                  "expected_generation": context.generation,
                  "target": target, "after": after, "changes_applied": False,
                  "runtime_authorized": False, "native_verified": False,
                  "undo_policy": "remove_created_edge_if_revision_matches"}
    return ValidatedEdge(checked.digest, checked.operation, canonical_bytes(projection))
