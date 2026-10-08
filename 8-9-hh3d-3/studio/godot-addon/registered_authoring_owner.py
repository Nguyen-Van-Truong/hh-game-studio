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
# The fixture host profile also admits the durable gameplay-source operations.
# They intentionally live behind a separate route: the scene/resource owner
# above emits catalog projections, while this route delegates source changes to
# the already authenticated GameplaySourcePublicationOwner.  Keeping the two
# transaction shapes separate prevents a source publish from being mistaken
# for a scene projection or from bypassing the source owner's journal.
SCRIPT_OPERATIONS = ("gameplay-source.inspect", "gameplay-source.publish")
SCRIPT_ROUTE_SCHEMA = "hh-godot-registered-script-route-1"
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
    sprite_sha256: str | None = None
    content_schema: str | None = None
    source_closure_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result = {"published_root": self.published_root, "glb_sha256": self.glb_sha256,
                  "manifest_sha256": self.manifest_sha256, "manifest_schema": self.manifest_schema,
                  "command_id": self.command_id}
        if self.sprite_sha256 is not None:
            result["sprite_sha256"] = self.sprite_sha256
        if self.content_schema is not None:
            result["content_schema"] = self.content_schema
        if self.source_closure_sha256 is not None:
            result["source_closure_sha256"] = self.source_closure_sha256
        return result


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
    schema = manifest.get("schema") if type(manifest) is dict else None
    if schema == "HH-BLENDER-PUBLICATION-1":
        expected = manifest.get("native", {}).get("glb_sha256")
        command_id = manifest.get("command_id")
        sprite_sha256 = None
        content_schema = None
        source_closure_sha256 = None
    elif schema == "HH-BLENDER-FIXTURE-CONTENT-1":
        _need(manifest.get("authority") == 0 and manifest.get("public_ack") is False
              and manifest.get("external_inputs") == [], "REGISTERED_HANDOFF_CONTENT_AUTHORITY")
        artifacts = manifest.get("artifacts", {})
        expected = artifacts.get("scene.glb")
        sprite_sha256 = artifacts.get("sprite_sheet.png")
        command_id = manifest.get("run_id")
        content_schema = schema
        source_closure_sha256 = manifest.get("source_closure_sha256")
        _need(type(source_closure_sha256) is str and _REV.fullmatch(source_closure_sha256),
              "REGISTERED_HANDOFF_SOURCE_CLOSURE")
        body = dict(manifest)
        body_hash = body.pop("manifest_body_sha256", None)
        _need(type(body_hash) is str and body_hash == _sha_bytes(canonical_bytes(body)),
              "REGISTERED_HANDOFF_MANIFEST_HASH")
        _need(type(sprite_sha256) is str and _HEX.fullmatch(sprite_sha256),
              "REGISTERED_HANDOFF_SPRITE_HASH")
    else:
        raise RegisteredAuthoringOwnerError("REGISTERED_HANDOFF_MANIFEST_SCHEMA")
    _need(type(expected) is str and _HEX.fullmatch(expected) and expected == _sha_bytes(glb_raw),
          "REGISTERED_HANDOFF_GLB_HASH")
    _need(type(command_id) is str and _ID.fullmatch(command_id.replace("-", ".")),
          "REGISTERED_HANDOFF_COMMAND")
    return BlenderHandoff(str(root), expected, _sha_bytes(manifest_raw), schema,
                          command_id, sprite_sha256, content_schema, source_closure_sha256)


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


def _fixture_module():
    path = HERE / "gameplay_fixture_profile.py"
    raw = _safe_file(path, maximum=65536)
    key = "_hh_gameplay_fixture_profile_" + hashlib.sha256(str(path).encode() + b"\0" + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        _need(spec is not None, "REGISTERED_PROFILE_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


def load_fixture_host_profile(project_id: str):
    return _fixture_module().load_fixture_profile(project_id)


class RegisteredAuthoringAdapter:
    """Fixture-only request route backed by the existing trusted owner.

    The host injects the observed inventory and frozen policy. Requests can
    choose neither; they carry only the protocol/catalog identity and commands.
    Default discovery remains empty until an explicit host registration exists.
    """

    def __init__(self, owner: RegisteredAuthoringOwner, *, inventory, source_files,
                 host_profile=None):
        _need(type(owner) is RegisteredAuthoringOwner, "REGISTERED_OWNER_REQUIRED")
        self.owner = owner
        self._inventory = inventory
        self._source_files = dict(source_files)
        self._profile = host_profile
        if host_profile is not None:
            self._descriptor()

    def _descriptor(self):
        _need(self._profile is not None, "FIXTURE_PROFILE_DISABLED")
        try:
            result = _fixture_module().validate_fixture_profile(self._profile,
                project_id=self.owner.admission.project_id, source_files=self._source_files)
        except ValueError as exc:
            raise RegisteredAuthoringOwnerError(getattr(exc, "code", "REGISTERED_PROFILE_INVALID")) from exc
        # Registration identity and the node/resource allowlist are distinct.
        result["node_catalog_digest"] = self.owner.profile.catalog_digest
        result["operations"] = list(self.owner.profile.operations)
        return result

    def discovery(self, *, project_id=None, protocol_version=PROTOCOL_VERSION, profile=PROFILE):
        _need(protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_CLIENT_VERSION")
        _need(profile == PROFILE, "REGISTERED_PROFILE_UNKNOWN")
        project_id = project_id or self.owner.admission.project_id
        descriptor = self._descriptor() if self._profile is not None else None
        enabled = descriptor is not None and project_id == self.owner.admission.project_id
        return {"schema": SCHEMA, "protocol_version": PROTOCOL_VERSION, "project_id": project_id,
                "profiles": [descriptor] if enabled else [], "fixture_enabled": enabled,
                "public_runtime_enabled": False, "authority": 0, "public_ack": False}

    def prepare(self, requests, *, protocol_version=PROTOCOL_VERSION, profile=PROFILE,
                profile_version=PROFILE_VERSION, profile_digest):
        _need(protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_CLIENT_VERSION")
        _need(profile == PROFILE, "REGISTERED_PROFILE_UNKNOWN")
        descriptor = self._descriptor()
        _need(type(profile_version) is int and profile_version == descriptor["version"],
              "FIXTURE_PROFILE_VERSION")
        _need(profile_digest == descriptor["catalog_digest"], "FIXTURE_PROFILE_DIGEST")
        return self.owner.prepare(requests, inventory=self._inventory)

    def execute(self, requests, **identity):
        transaction = self.prepare(requests, **identity)
        receipt = self.owner.apply(transaction)
        _need(receipt.get("readback_ack") is True, "REGISTERED_READBACK_REQUIRED")
        rows = receipt.get("catalog_commands_executed")
        _need(type(rows) is list and len(rows) == len(transaction.commands), "REGISTERED_COMMAND_READBACK")
        for row, command in zip(rows, transaction.commands):
            _need(row.get("command_id") == command.command_id
                  and row.get("projection_sha256") == command.projection_sha256
                  and row.get("verified") is True and isinstance(row.get("readback"), dict),
                  "REGISTERED_COMMAND_READBACK")
        return receipt


class RegisteredScriptRoute:
    """Fixture-scoped registered route for real controller source changes.

    ``GameplaySourceAdapter`` already owns the durable journal, grant/lease
    checks, native executor and postcondition readback.  This class is the
    catalog registration seam around that owner.  It accepts only typed
    protocol requests and a trusted adapter/grant/lease supplied by the host;
    paths, projects and capability flags remain host-owned.  Exact retries
    return the cached owner receipt, while a changed request with the same
    command id is rejected before a second native dispatch.
    """

    def __init__(self, owner: RegisteredAuthoringOwner, *, adapter: Any,
                 grant: Any, lease: Any, host_profile: Any):
        _need(type(owner) is RegisteredAuthoringOwner, "REGISTERED_OWNER_REQUIRED")
        _need(adapter is not None and callable(getattr(adapter, "execute", None)),
              "REGISTERED_SCRIPT_ADAPTER_REQUIRED")
        _need(grant is not None and lease is not None, "REGISTERED_SCRIPT_CREDENTIALS_REQUIRED")
        _need(host_profile is not None and getattr(host_profile, "script_enabled", False) is True,
              "REGISTERED_SCRIPT_PROFILE_DISABLED")
        _need(tuple(getattr(host_profile, "operations", ())) ==
              tuple(_fixture_module().OPERATIONS), "REGISTERED_SCRIPT_PROFILE_OPERATIONS")
        _need(owner.admission.project_id == getattr(host_profile, "project_id", None),
              "REGISTERED_SCRIPT_PROJECT")
        self.owner = owner
        self.adapter = adapter
        self.grant = grant
        self.lease = lease
        self.host_profile = host_profile
        self._requests: dict[str, str] = {}
        self._receipts: dict[str, dict[str, Any]] = {}

    def _check_request(self, request: Request | Mapping[str, Any]) -> Request:
        try:
            wire = request.as_dict() if isinstance(request, Request) else request
            checked = Request.from_dict(parse_json(canonical_bytes(wire)))
        except (ValidationError, TypeError, ValueError) as exc:
            code = getattr(exc, "code", "REGISTERED_SCRIPT_REQUEST_INVALID")
            raise RegisteredAuthoringOwnerError(code) from exc
        _need(checked.project_id == self.owner.admission.project_id,
              "REGISTERED_SCRIPT_PROJECT")
        _need(checked.operation in SCRIPT_OPERATIONS, "REGISTERED_SCRIPT_OPERATION_DISABLED")
        _need(checked.lease_id == self.owner.admission.lease_id and
              checked.fencing_epoch == self.owner.admission.fencing_epoch,
              "REGISTERED_SCRIPT_FENCE")
        # The source owner, rather than this registration seam, decides
        # whether the expected revision is current.  Keeping that check in
        # one place is required for an exact retry: after a successful publish
        # the selected revision advances, yet the original command must still
        # reconcile to its durable receipt without a second native run.
        return checked

    def discovery(self) -> dict[str, Any]:
        """Return the host profile only after revalidating its policy bytes."""
        try:
            descriptor = self.adapter.profile_discovery(
                project_id=self.owner.admission.project_id)
        except Exception as exc:
            raise RegisteredAuthoringOwnerError(
                getattr(exc, "code", "REGISTERED_SCRIPT_DISCOVERY")) from exc
        _need(descriptor.get("fixture_enabled") is True and
              descriptor.get("public_runtime_enabled") is False and
              descriptor.get("authority") == 0 and descriptor.get("public_ack") is False,
              "REGISTERED_SCRIPT_DISCOVERY")
        return {"schema": SCRIPT_ROUTE_SCHEMA, "profile": descriptor,
                "operations": list(SCRIPT_OPERATIONS), "authority": 0,
                "public_ack": False}

    def execute(self, request: Request | Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch one registered source request and bind its readback."""
        checked = self._check_request(request)
        command_id = checked.command_id
        digest = checked.digest
        prior = self._requests.get(command_id)
        _need(prior is None or prior == digest, "REGISTERED_SCRIPT_COMMAND_CONFLICT")
        cached = self._receipts.get(digest)
        if cached is not None:
            return _copy(cached)
        try:
            receipt = self.adapter.execute(checked, grant=self.grant, lease=self.lease)
        except Exception as exc:
            code = getattr(exc, "code", "REGISTERED_SCRIPT_NATIVE_FAILED")
            raise RegisteredAuthoringOwnerError(code) from exc
        _need(isinstance(receipt, Mapping), "REGISTERED_SCRIPT_RECEIPT_SHAPE")
        receipt = _copy(receipt)
        if checked.operation == "gameplay-source.inspect":
            # Inspection is a read-only command: the source owner has already
            # authenticated the lease and revalidated its selected revision,
            # but there is no new native process/run id to acknowledge.  Wrap
            # that durable readback in the same typed route envelope so the
            # advertised inspect operation cannot accidentally be treated as
            # a publish or force a fabricated native receipt.
            _need(receipt.get("public_ack") is False
                  and receipt.get("project_id") == checked.project_id
                  and isinstance(receipt.get("project_revision"), str)
                  and receipt.get("selected_revision") == receipt.get("project_revision")
                  and isinstance(receipt.get("source_sha256"), str),
                  "REGISTERED_SCRIPT_INSPECT_READBACK_REQUIRED")
            receipt = {"status": "READBACK_ACK", "command_id": command_id,
                       "request_digest": digest, "readback_ack": True,
                       "public_ack": False, "readback": receipt}
            native_observed = False
        else:
            _need(receipt.get("status") == "READBACK_ACK" and
                  receipt.get("readback_ack") is True and receipt.get("public_ack") is False,
                  "REGISTERED_SCRIPT_READBACK_REQUIRED")
            _need(receipt.get("command_id") == command_id,
                  "REGISTERED_SCRIPT_COMMAND_MISMATCH")
            _need(type(receipt.get("native_run_id")) is str and receipt["native_run_id"],
                  "REGISTERED_SCRIPT_NATIVE_RUN_MISSING")
            native_observed = True
        envelope = {"schema": SCRIPT_ROUTE_SCHEMA, "authority": 0,
                    "public_ack": False, "native_observed": native_observed,
                    "readback_observed": True,
                    "registered_route": True, "command_id": command_id,
                    "request_digest": digest, "project_id": checked.project_id,
                    "lease_id": checked.lease_id,
                    "fencing_epoch": checked.fencing_epoch,
                    "status": receipt.get("status"),
                    "receipt": receipt}
        self._requests[command_id] = digest
        self._receipts[digest] = envelope
        return _copy(envelope)


__all__ = ["PROFILE", "SCHEMA", "AUTHORITY", "STATE_KIND", "SCRIPT_OPERATIONS",
           "SCRIPT_ROUTE_SCHEMA", "RegisteredProfile",
           "OwnerAdmission", "BlenderHandoff", "RegisteredAuthoringOwner",
           "RegisteredAuthoringOwnerError", "register_profile", "make_admission",
           "inspect_blender_handoff", "RegisteredAuthoringAdapter", "RegisteredScriptRoute",
           "load_fixture_host_profile"]
