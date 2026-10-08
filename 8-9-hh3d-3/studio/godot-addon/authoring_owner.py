"""Trusted-owner seam for the O2 typed scene/resource authoring candidate.

The scene and resource modules in this directory intentionally stop at pure
validation.  This module is the smallest bridge toward a real owner: a
trusted launcher supplies an inventory reader and a native compiler callback.
Requests never supply either callback, an authority value, or a path.  A
prepared transaction is detached planning data (authority ``0``); the
callback is the only place where a future Godot owner may compile it.

The bridge does not pretend to be native evidence.  It gives the real owner a
stable, retry-safe recipe whose commands are bound to one observed revision,
generation, lease and fencing epoch.  The callback must independently perform
fresh admission, UndoRedo, save/reload and readback before returning a receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping, Sequence

from studio.protocol.core import Request, ValidationError, canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
SCHEMA = "hh-godot-authoring-transaction-1"
PROFILE = "hh-godot-gameplay-source-1"
AUTHORITY = 0
STATE_KIND = "PLANNED_NOT_NATIVE"
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
_MAX_COMMANDS = 128


def _load(name: str, filename: str):
    path = HERE / filename
    key = f"_hh_o2_authoring_owner_{name}_{hashlib.sha256(path.read_bytes()).hexdigest()}"
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("AUTHORING_CONTRACT_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[key]
            raise
    return module


_NODE = _load("node", "authoring_contract.py")
_RESOURCE = _load("resource", "resource_authoring.py")


class AuthoringOwnerError(ValidationError):
    """Stable admission/transaction failure; no native effect is implied."""

    def __init__(self, code: str):
        super().__init__(code, "trusted O2 authoring owner")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise AuthoringOwnerError(code)


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def _sha(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


@dataclass(frozen=True, slots=True)
class TrustedInventory:
    """Two validator contexts returned by the trusted owner observation hook.

    The constructor is public for test fixtures, but production code must only
    return it from the owner callback.  Coherence is checked again before any
    request is validated, so a client cannot splice a lease from one scene
    with resources from another scene.
    """

    node_context: Any
    resource_context: Any


@dataclass(frozen=True, slots=True)
class BoundCommand:
    command_id: str
    operation: str
    target_stable_id: str
    request_digest: str
    projection_sha256: str
    projection: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"command_id": self.command_id, "operation": self.operation,
                "target_stable_id": self.target_stable_id,
                "request_digest": self.request_digest,
                "projection_sha256": self.projection_sha256,
                "projection": _copy(self.projection)}


@dataclass(frozen=True, slots=True)
class AuthoringTransaction:
    """Immutable recipe bound to one owner observation.

    ``transaction_digest`` covers every field except itself.  The digest is
    what the native callback must echo in a later receipt.
    """

    schema: str
    profile: str
    authority: int
    state_kind: str
    public_ack: bool
    project_id: str
    expected_revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    command_ids: tuple[str, ...]
    commands: tuple[BoundCommand, ...]
    transaction_digest: str

    def _body(self) -> dict[str, Any]:
        return {"schema": self.schema, "profile": self.profile,
                "authority": self.authority, "state_kind": self.state_kind,
                "public_ack": self.public_ack, "project_id": self.project_id,
                "expected_revision": self.expected_revision,
                "project_revision": self.project_revision,
                "generation": self.generation, "lease_id": self.lease_id,
                "fencing_epoch": self.fencing_epoch,
                "command_ids": list(self.command_ids),
                "commands": [command.as_dict() for command in self.commands]}

    def as_dict(self) -> dict[str, Any]:
        body = self._body()
        body["transaction_digest"] = self.transaction_digest
        return _copy(body)

    @property
    def digest(self) -> str:
        return self.transaction_digest


def _transaction(*, context: Any, commands: Sequence[BoundCommand]) -> AuthoringTransaction:
    command_ids = tuple(command.command_id for command in commands)
    body = {"schema": SCHEMA, "profile": PROFILE, "authority": AUTHORITY,
            "state_kind": STATE_KIND, "public_ack": False,
            "project_id": context.project_id, "expected_revision": context.revision,
            "project_revision": context.project_revision,
            "generation": context.generation, "lease_id": context.lease_id,
            "fencing_epoch": context.fencing_epoch, "command_ids": list(command_ids),
            "commands": [command.as_dict() for command in commands]}
    return AuthoringTransaction(SCHEMA, PROFILE, AUTHORITY, STATE_KIND, False,
                               context.project_id, context.revision,
                               context.project_revision, context.generation,
                               context.lease_id, context.fencing_epoch,
                               command_ids, tuple(commands), _sha(body))


def _identity(request: Request) -> str:
    # Request.digest intentionally omits lease/deadline fields.  Retry identity
    # includes the owner admission tuple so a command cannot cross a lease or
    # revision boundary while retaining the same payload digest.
    return _sha({"digest": request.digest, "project_id": request.project_id,
                 "expected_revision": request.expected_revision,
                 "lease_id": request.lease_id,
                 "fencing_epoch": request.fencing_epoch})


def _same_scalar(left: Any, right: Any) -> bool:
    return left == right and type(left) is type(right)


def _coherent(inventory: TrustedInventory) -> tuple[Any, Any]:
    _need(type(inventory) is TrustedInventory, "AUTHORING_INVENTORY_REQUIRED")
    node = inventory.node_context
    resource = inventory.resource_context
    _need(type(node) is _NODE.ValidationContext and type(resource) is _RESOURCE.ValidationContext,
          "AUTHORING_INVENTORY_CONTEXT")
    fields = ("project_id", "revision", "project_revision", "generation", "lease_id",
              "fencing_epoch", "lease_expires_ms", "now_ms", "stopped")
    _need(all(_same_scalar(getattr(node, field), getattr(resource, field)) for field in fields),
          "AUTHORING_INVENTORY_MISMATCH")
    _need(node.profile == _NODE.PROFILE and resource.profile == _RESOURCE.PROFILE,
          "AUTHORING_INVENTORY_PROFILE")
    _need(_ID.fullmatch(node.project_id) and _ID.fullmatch(node.lease_id)
          and _REV.fullmatch(node.revision) and _REV.fullmatch(node.project_revision),
          "AUTHORING_INVENTORY_ID")
    node_rows = tuple((row.stable_id, row.parent_id, row.node_type, row.name)
                      for row in node.nodes)
    resource_rows = tuple((row.stable_id, row.parent_id, row.node_type, row.name)
                          for row in resource.nodes)
    _need(node_rows == resource_rows, "AUTHORING_INVENTORY_NODES")
    return node, resource


def _request(value: Request | Mapping[str, Any]) -> Request:
    try:
        return Request.from_dict(_copy(value.as_dict() if type(value) is Request else value))
    except (ValidationError, TypeError, AttributeError) as exc:
        code = getattr(exc, "code", "AUTHORING_REQUEST_INVALID")
        raise AuthoringOwnerError(code) from exc


def _append_node_context(context: Any, row: Any, *, resources: tuple[Any, ...] | None = None) -> Any:
    return replace(context, nodes=context.nodes + (row,),
                   resources=context.resources if resources is None else resources)


def _append_resource_context(context: Any, row: Any) -> Any:
    return replace(context, resources=context.resources + (row,))


def _update_resource_context(context: Any, resource_id: str, properties: Mapping[str, Any]) -> Any:
    rows = []
    for row in context.resources:
        if row.resource_id == resource_id:
            rows.append(_RESOURCE.ResourceState(row.resource_id, row.owner_stable_id,
                                                row.resource_type, row.shared, properties))
        else:
            rows.append(row)
    return replace(context, resources=tuple(rows))


class AuthoringOwner:
    """Retry-safe planner backed by injected trusted owner callbacks.

    ``inventory_reader`` and ``native_compiler`` are dependencies of the
    trusted launcher, never request fields.  ``native_compiler`` receives only
    an immutable transaction and must perform all actual native checks itself.
    """

    def __init__(self, inventory_reader: Callable[[], TrustedInventory],
                 native_compiler: Callable[[AuthoringTransaction], Mapping[str, Any]]):
        _need(callable(inventory_reader), "AUTHORING_INVENTORY_READER_REQUIRED")
        _need(callable(native_compiler), "AUTHORING_NATIVE_CALLBACK_REQUIRED")
        self._read_inventory = inventory_reader
        self._compile = native_compiler
        self._closed = False
        self._transactions: dict[str, tuple[str, AuthoringTransaction]] = {}
        self._native: dict[str, dict[str, Any]] = {}

    def _require_open(self) -> None:
        _need(not self._closed, "AUTHORING_OWNER_CLOSED")

    def _cached(self, requests: tuple[Request, ...]) -> AuthoringTransaction | None:
        known: list[AuthoringTransaction] = []
        for request in requests:
            row = self._transactions.get(request.command_id)
            if row is None:
                continue
            _need(row[0] == _identity(request), "AUTHORING_COMMAND_CONFLICT")
            known.append(row[1])
        if not known:
            return None
        _need(len(known) == len(requests) and len({row.digest for row in known}) == 1,
              "AUTHORING_COMMAND_CONFLICT")
        return known[0]

    def prepare(self, requests: Sequence[Request | Mapping[str, Any]]) -> AuthoringTransaction:
        """Validate and bind typed requests to one trusted inventory snapshot."""
        self._require_open()
        _need(isinstance(requests, Sequence) and not isinstance(requests, (str, bytes)),
              "AUTHORING_REQUESTS_REQUIRED")
        _need(0 < len(requests) <= _MAX_COMMANDS, "AUTHORING_COMMAND_LIMIT")
        checked = tuple(_request(item) for item in requests)
        ids = tuple(item.command_id for item in checked)
        _need(len(ids) == len(set(ids)), "AUTHORING_COMMAND_DUPLICATE")
        cached = self._cached(checked)
        if cached is not None:
            return cached
        try:
            inventory = self._read_inventory()
        except Exception as exc:
            raise AuthoringOwnerError("AUTHORING_INVENTORY_READ_FAILED") from exc
        node_context, resource_context = _coherent(inventory)
        catalog = _NODE.load_catalog()
        commands: list[BoundCommand] = []
        for request in checked:
            if request.operation.startswith("scene.node."):
                try:
                    validated = _NODE.validate_request(request, node_context, catalog)
                except ValidationError as exc:
                    raise AuthoringOwnerError(exc.code) from exc
            elif request.operation.startswith("scene.resource."):
                try:
                    validated = _RESOURCE.validate_request(request, resource_context)
                except ValidationError as exc:
                    raise AuthoringOwnerError(exc.code) from exc
            else:
                raise AuthoringOwnerError("AUTHORING_OPERATION_DISABLED")
            projection = validated.projection
            commands.append(BoundCommand(
                request.command_id, request.operation, request.target["stable_id"],
                request.digest, _sha(projection), projection))
            payload = request.payload
            if request.operation == "scene.node.create":
                row = _NODE.NodeState(payload["stable_id"], request.target["stable_id"],
                                      payload["node_type"], payload["name"])
                node_context = _append_node_context(node_context, row)
                resource_context = _append_node_context(resource_context,
                    _RESOURCE.NodeState(row.stable_id, row.parent_id, row.node_type, row.name))
            elif request.operation == "scene.resource.create":
                row = _RESOURCE.ResourceState(payload["resource_id"],
                    request.target["stable_id"], payload["resource_type"],
                    properties=payload["properties"])
                resource_context = _append_resource_context(resource_context, row)
                # The node validator only needs resource identity/base for a
                # later property reference; shape resources are catalog bases.
                node_context = replace(
                    node_context, resources=node_context.resources +
                    (_NODE.ResourceState(payload["resource_id"], payload["resource_type"]),))
            elif request.operation == "scene.resource.update":
                state = next(row for row in resource_context.resources
                             if row.resource_id == payload["resource_id"])
                effective = dict(state.properties)
                effective.update(payload["changes"])
                resource_context = _update_resource_context(
                    resource_context, payload["resource_id"], effective)
        transaction = _transaction(context=node_context, commands=commands)
        for request in checked:
            self._transactions[request.command_id] = (_identity(request), transaction)
        return transaction

    def compile_native(self, transaction: AuthoringTransaction) -> dict[str, Any]:
        """Route one prepared transaction to the trusted native-owner callback."""
        self._require_open()
        _need(type(transaction) is AuthoringTransaction
              and transaction.schema == SCHEMA and transaction.authority == AUTHORITY
              and transaction.public_ack is False, "AUTHORING_TRANSACTION_INVALID")
        cached = self._native.get(transaction.digest)
        if cached is not None:
            return _copy(cached)
        known = [self._transactions.get(command_id) for command_id in transaction.command_ids]
        _need(all(row is not None and row[1].digest == transaction.digest for row in known),
              "AUTHORING_TRANSACTION_UNKNOWN")
        try:
            result = self._compile(transaction)
        except AuthoringOwnerError:
            raise
        except Exception as exc:
            raise AuthoringOwnerError("AUTHORING_NATIVE_CALLBACK_FAILED") from exc
        _need(isinstance(result, Mapping), "AUTHORING_NATIVE_RESULT_SHAPE")
        result = _copy(result)
        _need(result.get("transaction_digest") == transaction.digest,
              "AUTHORING_NATIVE_TRANSACTION_MISMATCH")
        _need(result.get("command_ids") == list(transaction.command_ids),
              "AUTHORING_NATIVE_COMMAND_MISMATCH")
        _need(result.get("state_kind") == STATE_KIND
              and result.get("native_observed") is False,
              "AUTHORING_NATIVE_STATE")
        _need(result.get("authority") == AUTHORITY and result.get("public_ack") is False,
              "AUTHORING_NATIVE_AUTHORITY")
        self._native[transaction.digest] = result
        return _copy(result)

    def close(self) -> None:
        self._closed = True


NODE_CONTRACT = _NODE
RESOURCE_CONTRACT = _RESOURCE

__all__ = ["SCHEMA", "PROFILE", "AUTHORITY", "STATE_KIND", "NODE_CONTRACT",
           "RESOURCE_CONTRACT", "TrustedInventory",
           "BoundCommand", "AuthoringTransaction", "AuthoringOwnerError", "AuthoringOwner"]
