"""PC-only conformance adapter for the closed gameplay-source owner.

The adapter is deliberately a thin, typed client seam around
``GameplaySourcePublicationOwner``.  It never enables a public capability on
its own: discovery advertises no public operation before GT09 acceptance.
Caller-supplied capability flags are not measurements. Reconnect and context reset clear
client state and perform lookup/readback only; they never invent a new command
or replay an uncertain effect.

This module is a pure adapter contract.  The owner remains responsible for
the native executor, lease/fencing, durable journal and readback ACK.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import re
from typing import Any, Mapping

from studio.protocol.core import (
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


class GameplaySourceAdapter:
    """Typed PC client for one already-admitted publication owner.

    ``owner`` is intentionally injected by the trusted launcher.  The adapter
    accepts no path, process, engine or network endpoint from a request.
    """

    def __init__(self, owner: Any, *, client_version: str = SUPPORTED_CLIENT_VERSION):
        _need(owner is not None and hasattr(owner, "project_id")
              and hasattr(owner, "source_closure_sha256"), "ADAPTER_OWNER_REQUIRED")
        self.check_client_version(client_version)
        self._owner = owner
        self.project_id = owner.project_id
        self.client_version = client_version
        self._connected = True
        self._requests: dict[str, str] = {}

    @classmethod
    def check_client_version(cls, client_version: str) -> None:
        _need(type(client_version) is str and client_version in SUPPORTED_CLIENT_VERSIONS,
              "UNSUPPORTED_CLIENT_VERSION")

    def discovery(self) -> Discovery:
        """No public capabilities: private probes use actual owner grants."""
        self._require_connected()
        return Discovery(PROTOCOL_VERSION, SCHEMA_VERSION, SCHEMA_DIGEST,
                         "hh-gameplay-source", ADAPTER_BUILD, self.project_id,
                         (), {"native_timeout_seconds": 30,
                              "native_timeout_scope": "authenticated-gameplay-source"})

    def _require_connected(self) -> None:
        _need(self._connected, "ADAPTER_DISCONNECTED")

    def inspect(self) -> dict[str, Any]:
        self._require_connected()
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
        replacement = GameplaySourceAdapter(self._owner, client_version=self.client_version)
        self._connected = False
        return replacement

    def close(self) -> None:
        self._connected = False


__all__ = [
    "ADAPTER_SCHEMA", "ADAPTER_BUILD", "PROFILE", "PUBLISH_OPERATION",
    "READ_OPERATION", "SUPPORTED_CLIENT_VERSION", "SCHEMA_DIGEST",
    "GameplaySourceAdapter",
    "GameplaySourceAdapterError",
]
