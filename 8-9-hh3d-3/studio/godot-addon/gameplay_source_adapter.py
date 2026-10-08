"""PC adapter for the durable gameplay-source owner and GT-09 fixtures.

The adapter is deliberately a thin, typed client seam around
``GameplaySourcePublicationOwner``.  It never enables a public capability on
its own: default discovery advertises no operation before GT09 acceptance.
Only a source-bound trusted host profile enables the registered request route
for its fixture project. Legacy private diagnostic methods remain available
to their trusted owner launcher; they never grant registration by themselves.
Caller-supplied capability flags are not measurements. Reconnect and context reset clear
client state and perform lookup/readback only; they never invent a new command
or replay an uncertain effect.

This module is a pure adapter contract.  The owner remains responsible for
the native executor, lease/fencing, durable journal and readback ACK.
"""
from __future__ import annotations

import hashlib
import base64
import binascii
import importlib.util
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from studio.protocol.core import (
    Capability,
    Discovery,
    PROTOCOL_VERSION,
    Request,
    SCHEMA_VERSION,
    ValidationError,
    canonical_bytes,
    parse_json,
)


ADAPTER_SCHEMA = "hh-gameplay-source-adapter-1"
ADAPTER_BUILD = "pc-0.1"
PROFILE = "hh-godot-gameplay-source-1"
PUBLISH_OPERATION = "gameplay-source.publish"
READ_OPERATION = "gameplay-source.inspect"
SUPPORTED_CLIENT_VERSION = "pc-godot-4.7.2"
SUPPORTED_CLIENT_VERSIONS = frozenset({SUPPORTED_CLIENT_VERSION})
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_PROFILE_FIELDS = frozenset({"profile", "profile_version", "profile_digest"})
_ADAPTER_PATH = Path(__file__)
_ADAPTER_BYTES = _ADAPTER_PATH.read_bytes()
_ADAPTER_SHA256 = hashlib.sha256(_ADAPTER_BYTES).hexdigest()
if sys._getframe().f_code != compile(_ADAPTER_BYTES, str(_ADAPTER_PATH), "exec", dont_inherit=True):
    raise ValueError("ADAPTER_IMPORT_CHANGED")

_DECLARATION = {
    "schema": ADAPTER_SCHEMA,
    "protocol_version": PROTOCOL_VERSION,
    "schema_version": SCHEMA_VERSION,
    "profile": PROFILE,
    "operations": [READ_OPERATION, PUBLISH_OPERATION],
    "client_versions": sorted(SUPPORTED_CLIENT_VERSIONS),
}
SCHEMA_DIGEST = "sha256:" + hashlib.sha256(canonical_bytes(_DECLARATION)).hexdigest()


class GameplaySourceAdapterError(ValueError):
    """A typed client/admission failure; no native effect is implied."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(condition: object, code: str) -> None:
    if not condition:
        raise GameplaySourceAdapterError(code)


def _error_code(error: Exception, fallback: str) -> str:
    value = getattr(error, "code", str(error))
    return value if type(value) is str and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", value) else fallback


def _owner_module():
    """Load the hyphenated addon module without importing engine state."""
    path = Path(__file__).with_name("gameplay_source_owner.py")
    key = "_hh_gameplay_source_owner_adapter_" + hashlib.sha256(path.read_bytes()).hexdigest()
    import sys
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        if spec is None or spec.loader is None:
            raise GameplaySourceAdapterError("ADAPTER_OWNER_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[key]
            raise
    return module


def _fixture_module():
    """One exact-byte host module; a request cannot provide its import path."""
    path = Path(__file__).with_name("gameplay_fixture_profile.py")
    raw = path.read_bytes()
    key = "_hh_gameplay_fixture_profile_" + hashlib.sha256(
        str(path).encode() + b"\0" + raw).hexdigest()
    import sys
    module = sys.modules.get(key)
    if module is None:
        spec = importlib.util.spec_from_file_location(key, path)
        _need(spec is not None, "ADAPTER_PROFILE_IMPORT")
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return module


def load_fixture_host_profile(project_id: str):
    """Trusted launcher API; returns no registration for another project."""
    try:
        return _fixture_module().load_fixture_profile(project_id)
    except Exception as exc:
        raise GameplaySourceAdapterError(_error_code(exc, "ADAPTER_PROFILE_LOAD")) from exc


class GameplaySourceAdapter:
    """Typed PC client for one already-admitted publication owner.

    ``owner`` is intentionally injected by the trusted launcher.  The adapter
    accepts no path, process, engine or network endpoint from a request.
    """

    def __init__(self, owner: Any, *, client_version: str = SUPPORTED_CLIENT_VERSION,
                 host_profile: Any = None):
        _need(owner is not None and hasattr(owner, "project_id")
              and hasattr(owner, "source_closure_sha256"), "ADAPTER_OWNER_REQUIRED")
        self.check_client_version(client_version)
        self._owner = owner
        self._host_profile = host_profile
        self.project_id = owner.project_id
        self.client_version = client_version
        self._connected = True
        self._requests: dict[str, str] = {}
        if host_profile is not None:
            self._registered_profile()

    @classmethod
    def check_client_version(cls, client_version: str) -> None:
        _need(type(client_version) is str and client_version in SUPPORTED_CLIENT_VERSIONS,
              "UNSUPPORTED_CLIENT_VERSION")

    def discovery(self) -> Discovery:
        """Advertise only operations registered for this host-owned fixture."""
        self._require_connected()
        if self._host_profile is not None:
            profile = self._registered_profile()
            capabilities = (
                Capability(READ_OPERATION, (self.project_id,)),
                Capability(PUBLISH_OPERATION, (self.project_id,), (self.project_id,)),
            )
            return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, profile["catalog_digest"],
                             "hh-gameplay-source", ADAPTER_BUILD, self.project_id,
                             capabilities, {"native_timeout_seconds": 30,
                                            "profile_version": profile["version"]})
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, SCHEMA_DIGEST,
                         "hh-gameplay-source", ADAPTER_BUILD, self.project_id,
                         (), {"native_timeout_seconds": 30})

    def profile_discovery(self, *, project_id: str | None = None,
                          profile: str = PROFILE,
                          protocol_version: str = PROTOCOL_VERSION) -> dict[str, Any]:
        """Fixture profile/version/digest discovery; default/global is hidden."""
        self._require_connected()
        _need(protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_CLIENT_VERSION")
        _need(profile == PROFILE, "FIXTURE_PROFILE_UNKNOWN")
        project_id = self.project_id if project_id is None else project_id
        _need(type(project_id) is str and _ID.fullmatch(project_id), "FIXTURE_PROJECT_ID")
        registered = (self._registered_profile() if self._host_profile is not None else None)
        enabled = registered is not None and project_id == self.project_id
        return {"schema": ADAPTER_SCHEMA, "protocol_version": PROTOCOL_VERSION,
                "project_id": project_id, "profiles": [registered] if enabled else [],
                "fixture_enabled": enabled, "authority": 0, "public_ack": False,
                "public_runtime_enabled": False}

    def _registered_profile(self) -> dict[str, Any]:
        """Bind trusted policy to the actual publication owner's source closure."""
        self._require_connected()
        _need(self._host_profile is not None, "FIXTURE_PROFILE_DISABLED")
        import sys
        owner_module = sys.modules.get(type(self._owner).__module__)
        _need(owner_module is not None
              and type(self._owner) is getattr(owner_module, "GameplaySourcePublicationOwner", None),
              "ADAPTER_REGISTERED_OWNER_REQUIRED")
        try:
            files, digest = owner_module.runtime_source_closure()
            _need(digest == self._owner.source_closure_sha256, "FIXTURE_PROFILE_CLOSURE")
            _need(files.get("godot-addon/gameplay_source_adapter.py")
                  == _ADAPTER_SHA256 and _ADAPTER_PATH.read_bytes() == _ADAPTER_BYTES,
                  "FIXTURE_PROFILE_CLOSURE")
            registered = _fixture_module().validate_fixture_profile(
                self._host_profile, project_id=self._owner.project_id, source_files=files)
        except GameplaySourceAdapterError:
            raise
        except Exception as exc:
            raise GameplaySourceAdapterError(_error_code(exc, "ADAPTER_PROFILE_INVALID")) from exc
        _need(self.project_id == self._owner.project_id == registered["project_id"],
              "FIXTURE_PROFILE_PROJECT")
        _need(self.client_version in registered["client_versions"], "UNSUPPORTED_CLIENT_VERSION")
        return registered

    def execute(self, request: Request | Mapping[str, Any], *, grant: Any, lease: Any,
                protocol_version: str = PROTOCOL_VERSION) -> dict[str, Any]:
        """Registered catalog route, reusing the owner journal/sandbox/readback.

        ``source_files`` maps relative paths to canonical base64 strings or
        lists of base64 chunks. The existing protocol payload ceiling still
        applies. No config, capability, source root, or executor flag is an
        accepted request field.
        """
        self._require_connected()
        _need(protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_CLIENT_VERSION")
        try:
            wire = request.as_dict() if isinstance(request, Request) else request
            checked = Request.from_dict(parse_json(canonical_bytes(wire)))
        except (ValidationError, TypeError, ValueError) as exc:
            raise GameplaySourceAdapterError(_error_code(exc, "INVALID_SOURCE_REQUEST")) from exc
        payload = checked.payload
        _need(payload.get("profile") == PROFILE, "FIXTURE_PROFILE_UNKNOWN")
        registered = self._registered_profile()
        _need(checked.project_id == self.project_id, "FIXTURE_PROFILE_PROJECT")
        _need(checked.operation in (READ_OPERATION, PUBLISH_OPERATION),
              "FIXTURE_OPERATION_DISABLED")
        _need(type(payload.get("profile_version")) is int
              and payload["profile_version"] == registered["version"],
              "FIXTURE_PROFILE_VERSION")
        _need(payload.get("profile_digest") == registered["catalog_digest"],
              "FIXTURE_PROFILE_DIGEST")
        _need(checked.target == {"path": self._owner.entrypoint}, "FIXTURE_PROFILE_TARGET")
        _need(checked.lease_id == getattr(lease, "lease_id", None)
              and checked.fencing_epoch == getattr(lease, "fencing_epoch", None),
              "FIXTURE_PROFILE_FENCE")
        if checked.operation == READ_OPERATION:
            _need(set(payload) == _PROFILE_FIELDS, "FIXTURE_REQUEST_FIELDS")
            # The current owner deliberately uses a writer-authorized lookup
            # contract for private source readback. This validates lease and
            # grant even for a missing command, without dispatching an effect.
            self.lookup(checked.command_id, grant=grant, lease=lease,
                        deadline_ms=checked.deadline_ms)
            observed = self.inspect()
            _need(checked.expected_revision == observed["project_revision"],
                  "GAMEPLAY_OWNER_STALE_PROJECT")
            return observed
        _need(set(payload) == _PROFILE_FIELDS | {"entrypoint", "source_files",
                                                "expected_project_revision"},
              "FIXTURE_REQUEST_FIELDS")
        _need(payload["entrypoint"] == self._owner.entrypoint, "FIXTURE_PROFILE_TARGET")
        _need(checked.expected_revision == payload["expected_project_revision"],
              "FIXTURE_REQUEST_REVISION")
        encoded = payload["source_files"]
        _need(type(encoded) is dict and 0 < len(encoded) <= 64, "INVALID_SOURCE_FILES")
        files: dict[str, bytes] = {}
        for name, item in encoded.items():
            chunks = item if type(item) is list else [item]
            _need(type(name) is str and chunks
                  and all(type(chunk) is str and 0 < len(chunk) <= 16384 for chunk in chunks),
                  "INVALID_SOURCE_ENCODING")
            try:
                raw_chunks = [base64.b64decode(chunk, validate=True) for chunk in chunks]
            except (binascii.Error, ValueError) as exc:
                raise GameplaySourceAdapterError("INVALID_SOURCE_ENCODING") from exc
            _need(all(base64.b64encode(raw).decode("ascii") == chunk
                      for raw, chunk in zip(raw_chunks, chunks)), "INVALID_SOURCE_ENCODING")
            files[name] = b"".join(raw_chunks)
        return self.publish_source(command_id=checked.command_id, source_files=files,
            expected_project_revision=payload["expected_project_revision"], grant=grant,
            lease=lease, deadline_ms=checked.deadline_ms)

    def _require_connected(self) -> None:
        _need(self._connected, "ADAPTER_DISCONNECTED")

    def inspect(self) -> dict[str, Any]:
        self._require_connected()
        if self._host_profile is not None:
            self._registered_profile()
        try:
            value = self._owner.inspect()
        except Exception as exc:
            raise GameplaySourceAdapterError(_error_code(exc, "OWNER_READBACK_FAILED")) from exc
        _need(type(value) is dict and value.get("public_ack") is False,
              "OWNER_READBACK_INVALID")
        return value

    def build_request(self, *, command_id: str, source_files: Mapping[str, bytes],
                      expected_project_revision: str) -> dict[str, Any]:
        self._require_connected()
        if self._host_profile is not None:
            self._registered_profile()
        _need(type(command_id) is str and _ID.fullmatch(command_id),
              "INVALID_COMMAND_ID")
        _need(isinstance(source_files, Mapping), "INVALID_SOURCE_FILES")
        owner = _owner_module()
        try:
            digest = owner.request_digest(project_id=self.project_id,
                                          command_id=command_id,
                                          entrypoint=owner.ENTRYPOINT,
                                          expected_project_revision=expected_project_revision,
                                          source_files=dict(source_files))
        except Exception as exc:
            raise GameplaySourceAdapterError("INVALID_SOURCE_REQUEST") from exc
        return {"command_id": command_id, "digest": digest,
                "expected_project_revision": expected_project_revision,
                "source_files": dict(source_files), "entrypoint": owner.ENTRYPOINT}

    def publish_source(self, *, command_id: str, source_files: Mapping[str, bytes],
                       expected_project_revision: str, grant: Any, lease: Any,
                       deadline_ms: int) -> dict[str, Any]:
        """Publish once and verify owner readback; exact retries are idempotent."""
        self._require_connected()
        if self._host_profile is not None:
            self._registered_profile()
        request = self.build_request(command_id=command_id, source_files=source_files,
                                     expected_project_revision=expected_project_revision)
        digest = request["digest"]
        prior = self._requests.get(command_id)
        _need(prior is None or prior == digest, "COMMAND_CONFLICT")
        # An artist/owner edit must be observed before retry or a new effect.
        before = self.inspect()
        try:
            receipt = self._owner.publish(request, grant=grant, lease=lease,
                                          deadline_ms=deadline_ms)
        except GameplaySourceAdapterError:
            raise
        except Exception as exc:
            # Preserve the owner's typed code when available, while keeping
            # adapter errors stable for callers that do not import the owner.
            code = getattr(exc, "code", None)
            if isinstance(code, str):
                raise GameplaySourceAdapterError(code) from exc
            raise
        _need(type(receipt) is dict and receipt.get("readback_ack") is True
              and receipt.get("public_ack") is False, "OWNER_ACK_INVALID")
        after = self.inspect()
        same_revision = (after.get("project_revision") == receipt.get("project_revision")
                         and after.get("generation") == receipt.get("generation"))
        historical_retry = (type(receipt.get("generation")) is int
                            and receipt["generation"] < before["generation"]
                            and before == after)
        _need(same_revision or historical_retry, "OWNER_READBACK_MISMATCH")
        self._requests[command_id] = digest
        return dict(receipt)

    def lookup(self, command_id: str, *, grant: Any, lease: Any,
               deadline_ms: int) -> dict[str, Any] | None:
        """Authenticated durable readback; never dispatches or resumes work."""
        self._require_connected()
        if self._host_profile is not None:
            self._registered_profile()
        _need(type(command_id) is str and _ID.fullmatch(command_id),
              "INVALID_COMMAND_ID")
        try:
            return self._owner.lookup(command_id, grant=grant, lease=lease,
                                      deadline_ms=deadline_ms)
        except Exception as exc:
            raise GameplaySourceAdapterError(_error_code(exc, "OWNER_LOOKUP_FAILED")) from exc

    def context_reset(self) -> "GameplaySourceAdapter":
        """Drop client caches; durable owner state remains the source of truth."""
        self._require_connected()
        self._requests.clear()
        return self

    def reconnect(self) -> "GameplaySourceAdapter":
        """Create a fresh client context without replaying any command."""
        self._require_connected()
        replacement = GameplaySourceAdapter(self._owner, client_version=self.client_version,
                                            host_profile=self._host_profile)
        self._connected = False
        return replacement

    def close(self) -> None:
        self._connected = False


__all__ = [
    "ADAPTER_SCHEMA", "ADAPTER_BUILD", "PROFILE", "PUBLISH_OPERATION",
    "READ_OPERATION", "SUPPORTED_CLIENT_VERSION", "SCHEMA_DIGEST",
    "GameplaySourceAdapter", "load_fixture_host_profile",
    "GameplaySourceAdapterError",
]
