"""Registered O2 owner around the disposable Godot authoring diagnostic.

This module is intentionally a private, authority-zero owner.  It is the
missing integration between the typed ``authoring_owner`` planner and the
already measured Godot editor probe: the launcher supplies a trusted native
apply callback, while requests cannot choose a path, catalog, lease, or
Blender asset.  A native receipt is accepted only after its transaction,
command IDs, lease/fence and Blender handoff all match the owner admission.

The receipt is diagnostic evidence, not a public capability or a GT-09 tick.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import threading
import time
from typing import Any, Callable, Mapping, Sequence

from studio.protocol.core import PROTOCOL_VERSION, Request, ValidationError, canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
PROFILE = "hh-godot-gameplay-source-1"
SCHEMA = "hh-godot-registered-authoring-owner-1"
AUTHORITY = 0
STATE_KIND = "NATIVE_OBSERVED_AUTHORITY0"
PROFILE_VERSION = 1
# Trusted host policy, never selected by a request. This module is captured in
# the native source closure. Other projects cannot acquire this fixture route.
FIXTURE_PROJECTS = {"project.registered.room": "Node3D",
                    "project.registered.arena": "Node2D"}
OPERATIONS = ("scene.node.create", "scene.node.update", "scene.resource.create")
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_REV = re.compile(r"sha256:[0-9a-f]{64}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")


def _load_authoring_owner():
    path = HERE / "authoring_owner.py"
    key = "_hh_registered_authoring_owner_" + hashlib.sha256(path.read_bytes()).hexdigest()
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("REGISTERED_OWNER_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[key]
            raise
    return module


_PLANNER = _load_authoring_owner()
_NODE = _PLANNER.NODE_CONTRACT
_RESOURCE = _PLANNER.RESOURCE_CONTRACT


class RegisteredAuthoringOwnerError(ValidationError):
    def __init__(self, code: str):
        super().__init__(code, "registered O2 authoring owner")


def _need(condition: object, code: str) -> None:
    if not condition:
        raise RegisteredAuthoringOwnerError(code)


def _copy(value: Any) -> Any:
    return parse_json(canonical_bytes(value))


def _sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha(value: Any) -> str:
    return "sha256:" + _sha_bytes(canonical_bytes(value))


def _safe_file(path: Path, *, maximum: int = 16 * 1024 * 1024) -> bytes:
    _need(path.is_absolute() and path.is_file(), "REGISTERED_HANDOFF_FILE")
    for part in (path, *path.parents):
        info = part.stat(follow_symlinks=False)
        _need(not part.is_symlink() and not getattr(info, "st_file_attributes", 0) & 0x400,
              "REGISTERED_HANDOFF_REPARSE")
    _need(path.stat().st_size <= maximum, "REGISTERED_HANDOFF_SIZE")
    return path.read_bytes()


@dataclass(frozen=True, slots=True)
class RegisteredProfile:
    profile: str
    catalog_digest: str
    operations: tuple[str, ...]
    status: str = "CANDIDATE_ONLY"
    authority: int = AUTHORITY
    runtime_enabled: bool = False
    script_enabled: bool = False
    version: int = PROFILE_VERSION

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "profile": self.profile,
                "catalog_digest": self.catalog_digest,
                "operations": list(self.operations), "status": self.status,
                "authority": self.authority, "runtime_enabled": self.runtime_enabled,
                "script_enabled": self.script_enabled, "version": self.version}


def register_profile() -> RegisteredProfile:
    """Register only the pinned candidate catalog; no public discovery occurs."""
    catalog = _NODE.load_catalog()
    _need(catalog.digest.startswith("sha256:") and _HEX.fullmatch(catalog.digest[7:]),
          "REGISTERED_CATALOG_DIGEST")
    digest = _sha({"schema": SCHEMA, "profile": PROFILE, "version": PROFILE_VERSION,
                   "node_catalog_digest": catalog.digest, "operations": list(OPERATIONS),
                   "fixture_projects": FIXTURE_PROJECTS,
                   "resource_contract_sha256": _sha_bytes(
                       (HERE / "resource_authoring.py").read_bytes())})
    return RegisteredProfile(PROFILE, digest, OPERATIONS)


@dataclass(frozen=True, slots=True)
class OwnerAdmission:
    project_id: str
    revision: str
    project_revision: str
    generation: int
    lease_id: str
    fencing_epoch: int
    lease_expires_ms: int
    now_ms: int

    def as_dict(self) -> dict[str, Any]:
        return {"project_id": self.project_id, "revision": self.revision,
                "project_revision": self.project_revision, "generation": self.generation,
                "lease_id": self.lease_id, "fencing_epoch": self.fencing_epoch,
                "lease_expires_ms": self.lease_expires_ms, "now_ms": self.now_ms}


def make_admission(*, project_id: str, revision: str, project_revision: str,
                   generation: int = 1, lease_id: str = "lease.registered.o2",
                   fencing_epoch: int = 1, ttl_ms: int = 120_000,
                   now_ms: int | None = None) -> OwnerAdmission:
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    _need(_ID.fullmatch(project_id) is not None and _ID.fullmatch(lease_id) is not None,
          "REGISTERED_ADMISSION_ID")
    _need(_REV.fullmatch(revision) is not None and _REV.fullmatch(project_revision) is not None,
          "REGISTERED_ADMISSION_REVISION")
    _need(type(generation) is int and generation >= 1 and type(fencing_epoch) is int
          and fencing_epoch >= 1 and type(now_ms) is int and type(ttl_ms) is int
          and 1_000 <= ttl_ms <= 300_000, "REGISTERED_ADMISSION_INTEGER")
    return OwnerAdmission(project_id, revision, project_revision, generation, lease_id,
                          fencing_epoch, now_ms + ttl_ms, now_ms)


@dataclass(frozen=True, slots=True)
class BlenderHandoff:
    published_root: str
    glb_sha256: str
    manifest_sha256: str
    manifest_schema: str
    command_id: str

    def as_dict(self) -> dict[str, Any]:
        return {"published_root": self.published_root, "glb_sha256": self.glb_sha256,
                "manifest_sha256": self.manifest_sha256, "manifest_schema": self.manifest_schema,
                "command_id": self.command_id}


def inspect_blender_handoff(published_root: Path) -> BlenderHandoff:
    """Bind exactly one trusted Blender GLB publication and its manifest."""
    root = published_root.resolve(strict=True)
    _need(root.is_dir(), "REGISTERED_HANDOFF_ROOT")
    glb = root / "scene.glb"
    manifest_path = root / "manifest.json"
    glb_raw = _safe_file(glb)
    manifest_raw = _safe_file(manifest_path, maximum=2 * 1024 * 1024)
    try:
        manifest = parse_json(manifest_raw)
    except Exception as exc:
        raise RegisteredAuthoringOwnerError("REGISTERED_HANDOFF_MANIFEST_JSON") from exc
    _need(type(manifest) is dict and manifest.get("schema") == "HH-BLENDER-PUBLICATION-1",
          "REGISTERED_HANDOFF_MANIFEST_SCHEMA")
    expected = manifest.get("native", {}).get("glb_sha256")
    _need(type(expected) is str and _HEX.fullmatch(expected) and expected == _sha_bytes(glb_raw),
          "REGISTERED_HANDOFF_GLB_HASH")
    _need(type(manifest.get("command_id")) is str and _ID.fullmatch(manifest["command_id"].replace("-", ".")),
          "REGISTERED_HANDOFF_COMMAND")
    return BlenderHandoff(str(root), expected, _sha_bytes(manifest_raw), manifest["schema"],
                          manifest["command_id"])


class RegisteredAuthoringOwner:
    """Private owner that joins planner admission to one trusted native apply."""

    def __init__(self, *, admission: OwnerAdmission, blender: BlenderHandoff,
                 native_apply: Callable[[Any, OwnerAdmission, BlenderHandoff], Mapping[str, Any]]):
        _need(type(admission) is OwnerAdmission and type(blender) is BlenderHandoff,
              "REGISTERED_OWNER_CONTEXT")
        _need(callable(native_apply), "REGISTERED_NATIVE_CALLBACK")
        _need(admission.project_id in FIXTURE_PROJECTS, "REGISTERED_FIXTURE_PROJECT")
        self.profile = register_profile()
        self.admission = admission
        self.blender = blender
        self._closed = False
        self._transactions: dict[str, Any] = {}
        self._receipts: dict[str, dict[str, Any]] = {}
        self._planner = _PLANNER.AuthoringOwner(self._inventory, self._planned_compiler)
        self._native_apply = native_apply
        self._work = threading.Lock()
        self._uncertain: set[str] = set()
        self._batches: dict[tuple[str, ...], str] = {}

    def discovery(self, *, project_id: str, protocol_version: str = PROTOCOL_VERSION,
                  profile: str = PROFILE) -> dict[str, Any]:
        """Fixture-scoped API discovery; it never enables global runtime code."""
        _need(not self._closed, "REGISTERED_OWNER_CLOSED")
        _need(protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_CLIENT_VERSION")
        _need(profile == PROFILE, "REGISTERED_PROFILE_UNKNOWN")
        enabled = project_id == self.admission.project_id and project_id in FIXTURE_PROJECTS
        return {"schema": SCHEMA, "protocol_version": PROTOCOL_VERSION,
                "project_id": project_id, "profiles": [self.profile.as_dict()] if enabled else [],
                "fixture_enabled": enabled, "public_runtime_enabled": False,
                "authority": AUTHORITY, "public_ack": False}

    def _inventory(self):
        raise RegisteredAuthoringOwnerError("REGISTERED_INVENTORY_NOT_BOUND")

    def _planned_compiler(self, _transaction):
        raise RegisteredAuthoringOwnerError("REGISTERED_NATIVE_ROUTE_REQUIRED")

    def close(self) -> None:
        self._closed = True
        self._planner.close()

    def _check_live(self, transaction=None) -> None:
        _need(not self._closed, "REGISTERED_OWNER_CLOSED")
        now = int(time.time() * 1000)
        _need(self.admission.now_ms <= now < self.admission.lease_expires_ms,
              "REGISTERED_LEASE_EXPIRED")
        if transaction is not None:
            _need(type(transaction) is _PLANNER.AuthoringTransaction,
                  "REGISTERED_TRANSACTION_TYPE")
            _need(transaction.digest == _PLANNER._sha(transaction._body()),
                  "REGISTERED_TRANSACTION_CHANGED")
            _need(transaction.profile == PROFILE and transaction.authority == AUTHORITY
                  and transaction.public_ack is False, "REGISTERED_TRANSACTION_AUTHORITY")
            _need(transaction.project_id == self.admission.project_id
                  and transaction.lease_id == self.admission.lease_id
                  and transaction.fencing_epoch == self.admission.fencing_epoch,
                  "REGISTERED_TRANSACTION_FENCE")

    def prepare(self, requests: Sequence[Request | Mapping[str, Any]], *, inventory) -> Any:
        """Bind requests to the supplied trusted live inventory exactly once."""
        self._check_live()
        _need(type(inventory) is _PLANNER.TrustedInventory, "REGISTERED_INVENTORY_REQUIRED")
        try:
            node, resource = _PLANNER._coherent(inventory)
        except _PLANNER.AuthoringOwnerError as exc:
            raise RegisteredAuthoringOwnerError(exc.code) from exc
        fields = ("project_id", "revision", "project_revision", "generation", "lease_id",
                  "fencing_epoch", "lease_expires_ms", "now_ms")
        _need(all(getattr(node, name) == getattr(self.admission, name)
                  for name in fields), "REGISTERED_INVENTORY_ADMISSION")
        roots = [row for row in node.nodes if row.parent_id is None]
        _need(len(roots) == 1 and roots[0].stable_id == "root"
              and roots[0].node_type == FIXTURE_PROJECTS[self.admission.project_id],
              "REGISTERED_FIXTURE_ROOT")
        _need(isinstance(requests, Sequence) and not isinstance(requests, (str, bytes))
              and 0 < len(requests) <= 128, "REGISTERED_REQUESTS")
        try:
            checked = tuple(_PLANNER._request(value) for value in requests)
        except _PLANNER.AuthoringOwnerError as exc:
            raise RegisteredAuthoringOwnerError(exc.code) from exc
        _need(all(value.operation in self.profile.operations for value in checked),
              "REGISTERED_OPERATION_DISABLED")
        ids = tuple(value.command_id for value in checked)
        _need(len(set(ids)) == len(ids), "AUTHORING_COMMAND_DUPLICATE")
        batch_digest = _sha([_PLANNER._identity(value) for value in checked])
        known = [value for value in ids if value in self._transactions]
        if known:
            _need(self._batches.get(ids) == batch_digest,
                  "AUTHORING_COMMAND_CONFLICT")
        # The inventory callback is set only for this synchronous admission.
        self._planner._read_inventory = lambda: inventory
        try:
            transaction = self._planner.prepare(checked)
        except _PLANNER.AuthoringOwnerError as exc:
            raise RegisteredAuthoringOwnerError(exc.code) from exc
        self._check_live(transaction)
        for command_id in transaction.command_ids:
            self._transactions[command_id] = transaction
        self._batches[ids] = batch_digest
        return transaction

    def apply(self, transaction: Any) -> dict[str, Any]:
        """Apply once through the trusted native callback and validate readback."""
        _need(self._work.acquire(blocking=False), "REGISTERED_OWNER_BUSY")
        try:
            return self._apply(transaction)
        finally:
            self._work.release()

    def _apply(self, transaction: Any) -> dict[str, Any]:
        self._check_live(transaction)
        _need(transaction.digest in {row.digest for row in self._transactions.values()},
              "REGISTERED_TRANSACTION_UNKNOWN")
        cached = self._receipts.get(transaction.digest)
        if cached is not None:
            return _copy(cached)
        # Once native dispatch starts, any failed/malformed reply is uncertain.
        # A retry must not invoke the callback a second time.
        _need(transaction.digest not in self._uncertain, "REGISTERED_RECONCILE_REQUIRED")
        self._uncertain.add(transaction.digest)
        try:
            result = self._native_apply(transaction, self.admission, self.blender)
        except RegisteredAuthoringOwnerError:
            raise
        except Exception as exc:
            raise RegisteredAuthoringOwnerError("REGISTERED_NATIVE_CALLBACK_FAILED") from exc
        _need(isinstance(result, Mapping), "REGISTERED_NATIVE_RESULT_SHAPE")
        result = _copy(result)
        _need(result.get("transaction_digest") == transaction.digest,
              "REGISTERED_NATIVE_TRANSACTION_MISMATCH")
        _need(result.get("command_ids") == list(transaction.command_ids),
              "REGISTERED_NATIVE_COMMAND_MISMATCH")
        _need(result.get("authority") == AUTHORITY and result.get("public_ack") is False
              and result.get("native_observed") is True
              and result.get("state_kind") == STATE_KIND,
              "REGISTERED_NATIVE_AUTHORITY")
        _need(result.get("lease_id") == self.admission.lease_id
              and result.get("fencing_epoch") == self.admission.fencing_epoch,
              "REGISTERED_NATIVE_FENCE")
        handoff = result.get("blender_handoff")
        _need(handoff == self.blender.as_dict(), "REGISTERED_NATIVE_HANDOFF")
        self._receipts[transaction.digest] = result
        self._uncertain.remove(transaction.digest)
        return _copy(result)


__all__ = ["PROFILE", "SCHEMA", "AUTHORITY", "STATE_KIND", "RegisteredProfile",
           "OwnerAdmission", "BlenderHandoff", "RegisteredAuthoringOwner",
           "RegisteredAuthoringOwnerError", "register_profile", "make_admission",
           "inspect_blender_handoff"]
