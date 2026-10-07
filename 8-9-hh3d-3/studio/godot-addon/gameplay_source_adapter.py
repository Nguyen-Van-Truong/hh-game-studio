"""PC-only conformance adapter for the closed gameplay-source owner.

The adapter is deliberately a thin, typed client seam around
``GameplaySourcePublicationOwner``.  It never enables a public capability on
its own: discovery advertises the publish operation only after a caller has
supplied measured, source-bound evidence.  Reconnect and context reset clear
client state and perform lookup/readback only; they never invent a new command
or replay an uncertain effect.

This module is a pure adapter contract.  The owner remains responsible for
the native executor, lease/fencing, durable journal and readback ACK.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
from pathlib import Path
import re
from typing import Any, Mapping

from studio.protocol.core import (
    Capability,
    Discovery,
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    canonical_bytes,
)


ADAPTER_SCHEMA = "hh-gameplay-source-adapter-1"
ADAPTER_BUILD = "pc-0.1"
PROFILE = "hh-godot-gameplay-source-1"
PUBLISH_OPERATION = "gameplay-source.publish"
READ_OPERATION = "gameplay-source.inspect"
SUPPORTED_CLIENT_VERSION = "pc-godot-4.7.2"
SUPPORTED_CLIENT_VERSIONS = frozenset({SUPPORTED_CLIENT_VERSION})
_ID = re.compile(r"[a-z][a-z0-9._-]{0,63}\Z")
_HEX = re.compile(r"[0-9a-f]{64}\Z")

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


@dataclass(frozen=True, slots=True)
class CapabilityEvidence:
    """Measured observations required before advertising the PC capability."""

    client_version: str
    protocol_version: str
    schema_version: str
    profile: str
    source_closure_sha256: str
    source_job_ids: tuple[str, ...]
    readback_ack: bool
    reconnect_lookup_only: bool
    context_reset_lookup_only: bool
    owner_edit_preserved: bool
    no_duplicate_mutation: bool
    public_ack: bool = False
    authority: int = 0

    def validate(self, *, expected_source_closure: str) -> None:
        _need(self.client_version in SUPPORTED_CLIENT_VERSIONS,
              "UNSUPPORTED_CLIENT_VERSION")
        _need(self.protocol_version == PROTOCOL_VERSION, "UNSUPPORTED_PROTOCOL_VERSION")
        _need(self.schema_version == SCHEMA_VERSION, "UNSUPPORTED_SCHEMA_VERSION")
        _need(self.profile == PROFILE, "UNSUPPORTED_GAMEPLAY_PROFILE")
        _need(type(self.source_closure_sha256) is str and _HEX.fullmatch(self.source_closure_sha256),
              "INVALID_SOURCE_CLOSURE")
        _need(self.source_closure_sha256 == expected_source_closure,
              "SOURCE_CLOSURE_MISMATCH")
        _need(type(self.source_job_ids) is tuple and len(self.source_job_ids) >= 2,
              "SOURCE_JOBS_INCOMPLETE")
        _need(all(type(job_id) is str and _ID.fullmatch(job_id) for job_id in self.source_job_ids),
              "SOURCE_JOB_ID_INVALID")
        _need(len(set(self.source_job_ids)) == len(self.source_job_ids),
              "SOURCE_JOB_DUPLICATE")
        for value in (self.readback_ack, self.reconnect_lookup_only,
                      self.context_reset_lookup_only, self.owner_edit_preserved,
                      self.no_duplicate_mutation, self.public_ack):
            _need(type(value) is bool, "INVALID_CAPABILITY_EVIDENCE")
        _need(type(self.authority) is int and not isinstance(self.authority, bool)
              and self.authority == 0, "AUTHORITY_CLAIM_FORBIDDEN")
        _need(self.readback_ack and self.reconnect_lookup_only
              and self.context_reset_lookup_only and self.owner_edit_preserved
              and self.no_duplicate_mutation, "CAPABILITY_NOT_MEASURED")
        _need(self.public_ack is False, "PUBLIC_ACK_FORBIDDEN")


@dataclass(frozen=True, slots=True)
class Measurement:
    evidence: CapabilityEvidence
    discovery: Discovery


class GameplaySourceAdapter:
    """Typed PC client for one already-admitted publication owner.

    ``owner`` is intentionally injected by the trusted launcher.  The adapter
    accepts no path, process, engine or network endpoint from a request.
    """

    def __init__(self, owner: Any, *, client_version: str = SUPPORTED_CLIENT_VERSION,
                 measurement: Measurement | None = None):
        _need(owner is not None and hasattr(owner, "project_id")
              and hasattr(owner, "source_closure_sha256"), "ADAPTER_OWNER_REQUIRED")
        _need(client_version in SUPPORTED_CLIENT_VERSIONS,
              "UNSUPPORTED_CLIENT_VERSION")
        self._owner = owner
        self.project_id = owner.project_id
        self.client_version = client_version
        self._measurement = measurement
        self._connected = True
        self._requests: dict[str, str] = {}
        self._receipts: dict[str, dict[str, Any]] = {}

    @classmethod
    def check_client_version(cls, client_version: str) -> None:
        _need(client_version in SUPPORTED_CLIENT_VERSIONS,
              "UNSUPPORTED_CLIENT_VERSION")

    @property
    def measured(self) -> bool:
        return self._measurement is not None

    def discovery(self) -> Discovery:
        capabilities: tuple[Capability, ...] = ()
        if self._measurement is not None:
            capabilities = (
                Capability(READ_OPERATION, ("gameplay.read",), (),
                           {"max_source_jobs": 2}),
                Capability(PUBLISH_OPERATION, ("gameplay.read",), ("gameplay.write",),
                           {"max_source_jobs": 2, "native_timeout_seconds": 20}),
            )
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, SCHEMA_DIGEST,
                         "hh-gameplay-source", ADAPTER_BUILD, self.project_id,
                         capabilities, {"max_source_jobs": 2, "native_timeout_seconds": 20})

    def measure_capability(self, evidence: CapabilityEvidence) -> Measurement:
        _need(self._connected, "ADAPTER_DISCONNECTED")
        evidence.validate(expected_source_closure=self._owner.source_closure_sha256)
        measurement = Measurement(evidence, self.discovery_for_measurement())
        self._measurement = measurement
        return measurement

    def discovery_for_measurement(self) -> Discovery:
        """Build the measured discovery without mutating adapter state."""
        capabilities = (
            Capability(READ_OPERATION, ("gameplay.read",), (),
                       {"max_source_jobs": 2}),
            Capability(PUBLISH_OPERATION, ("gameplay.read",), ("gameplay.write",),
                       {"max_source_jobs": 2, "native_timeout_seconds": 20}),
        )
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, SCHEMA_DIGEST,
                         "hh-gameplay-source", ADAPTER_BUILD, self.project_id,
                         capabilities, {"max_source_jobs": 2, "native_timeout_seconds": 20})

    def _require_connected(self) -> None:
        _need(self._connected, "ADAPTER_DISCONNECTED")

    def _require_measured(self) -> None:
        _need(self._measurement is not None, "CAPABILITY_UNMEASURED")

    def inspect(self) -> dict[str, Any]:
        self._require_connected()
        try:
            value = self._owner.inspect()
        except BaseException as exc:
            raise GameplaySourceAdapterError("OWNER_EDIT_CONFLICT") from exc
        _need(type(value) is dict and value.get("public_ack") is False,
              "OWNER_READBACK_INVALID")
        return value

    def build_request(self, *, command_id: str, source_files: Mapping[str, bytes],
                      expected_project_revision: str) -> dict[str, Any]:
        self._require_connected()
        self._require_measured()
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
        except BaseException as exc:
            raise GameplaySourceAdapterError("INVALID_SOURCE_REQUEST") from exc
        return {"command_id": command_id, "digest": digest,
                "expected_project_revision": expected_project_revision,
                "source_files": dict(source_files), "entrypoint": owner.ENTRYPOINT}

    def publish_source(self, *, command_id: str, source_files: Mapping[str, bytes],
                       expected_project_revision: str, grant: Any, lease: Any,
                       deadline_ms: int) -> dict[str, Any]:
        """Publish once and verify owner readback; exact retries are idempotent."""
        self._require_connected()
        self._require_measured()
        request = self.build_request(command_id=command_id, source_files=source_files,
                                     expected_project_revision=expected_project_revision)
        digest = request["digest"]
        prior = self._requests.get(command_id)
        _need(prior is None or prior == digest, "COMMAND_CONFLICT")
        # An artist/owner edit must be observed before retry or a new effect.
        self.inspect()
        try:
            receipt = self._owner.publish(request, grant=grant, lease=lease,
                                          deadline_ms=deadline_ms)
        except GameplaySourceAdapterError:
            raise
        except BaseException as exc:
            # Preserve the owner's typed code when available, while keeping
            # adapter errors stable for callers that do not import the owner.
            code = getattr(exc, "code", None)
            if isinstance(code, str):
                raise GameplaySourceAdapterError(code) from exc
            raise
        _need(type(receipt) is dict and receipt.get("readback_ack") is True
              and receipt.get("public_ack") is False, "OWNER_ACK_INVALID")
        after = self.inspect()
        _need(after.get("project_revision") == receipt.get("project_revision")
              and after.get("generation") == receipt.get("generation"),
              "OWNER_READBACK_MISMATCH")
        self._requests[command_id] = digest
        self._receipts[command_id] = dict(receipt)
        return dict(receipt)

    def lookup(self, command_id: str) -> dict[str, Any] | None:
        """Read the owner's cached receipt; never dispatches or resumes work."""
        self._require_connected()
        _need(type(command_id) is str and _ID.fullmatch(command_id),
              "INVALID_COMMAND_ID")
        cached = self._receipts.get(command_id)
        if cached is not None:
            return dict(cached)
        jobs = getattr(self._owner, "_jobs", None)
        if isinstance(jobs, dict) and isinstance(jobs.get(command_id), dict):
            return dict(jobs[command_id])
        return None

    def context_reset(self) -> "GameplaySourceAdapter":
        """Drop client caches; durable owner state remains the source of truth."""
        self._require_connected()
        self._requests.clear()
        self._receipts.clear()
        return self

    def reconnect(self) -> "GameplaySourceAdapter":
        """Create a fresh client context without replaying any command."""
        self._require_connected()
        replacement = GameplaySourceAdapter(self._owner, client_version=self.client_version,
                                             measurement=self._measurement)
        self._connected = False
        return replacement

    def close(self) -> None:
        self._connected = False


__all__ = [
    "ADAPTER_SCHEMA", "ADAPTER_BUILD", "PROFILE", "PUBLISH_OPERATION",
    "READ_OPERATION", "SUPPORTED_CLIENT_VERSION", "SCHEMA_DIGEST",
    "CapabilityEvidence", "Measurement", "GameplaySourceAdapter",
    "GameplaySourceAdapterError",
]
