"""Typed, bounded client over two already connected trusted local pipes.

Connection, peer identity and confinement belong to the launcher. This module
does not open names, launch workers, reconnect, retry or execute returned data.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
import threading
import time

from ...protocol.core import (Discovery, Request, Response, Status, ValidationError,
                              PROTOCOL_VERSION, SCHEMA_VERSION, canonical_bytes)
from .fixture_release import _asset, _asset_id, _graph
from .limits import SafetyViolation, parse_json_utf8
from .pipe_io import MAX_FRAME_BYTES, OwnedPipe
from .selector_contract import (SELECTOR_SCHEMA_DIGEST, SELECTOR_SCOPE, SELECTOR_INSPECT_MAX_BYTES,
                                SELECTOR_PAYLOAD_MAX_BYTES)
from .transport import SessionCredential, epoch_ms

MAX_REPLY_BYTES = 64 * 1024
MAX_CLIENTS = 16
_SAFE = 2**53 - 1
_OWNERS_LOCK = threading.Lock()
_OWNERS: dict[int, ManagedFixtureClient] = {}
_CHANNELS: dict[OwnedPipe, ManagedFixtureClient] = {}


class SelectorClientError(SafetyViolation):
    def __init__(self, code, *, response=None, cleanup_owner=None):
        self.response = response
        self.outcome_unknown = response is not None and response.status is Status.UNKNOWN
        self.cleanup_owner = cleanup_owner
        super().__init__(code)


def _need(value, code='CLIENT_INVALID_REPLY'):
    if not value:
        raise SelectorClientError(code)


def _name(value):
    _need(type(value) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', value))


def _hash(value):
    _need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value))


def _integer(value, minimum=0):
    _need(type(value) is int and minimum <= value <= _SAFE)


def _shape(value, keys):
    _need(type(value) is dict and set(value) == set(keys))


def parse_bootstrap(raw: bytes, *, expected_project_id: str) -> SessionCredential:
    """Decode one launcher-consumed frame; does not read or own a connection."""
    _name(expected_project_id)
    _need(type(raw) is bytes and 0 < len(raw) <= 4096, 'CLIENT_BOOTSTRAP_LIMIT')
    value = parse_json_utf8(raw)
    _shape(value, ('schema', 'project_id', 'session_id', 'expires_ms', 'scopes', 'bearer'))
    _need(value['schema'] == 'hh-selector-session-1' and value['project_id'] == expected_project_id,
          'CLIENT_BOOTSTRAP_BINDING')
    _name(value['session_id']); _integer(value['expires_ms'], 1)
    _need(epoch_ms() < value['expires_ms'] <= epoch_ms() + 900_000, 'CLIENT_BOOTSTRAP_EXPIRED')
    scopes = value['scopes']
    _need(type(scopes) is list and all(type(scope) is str for scope in scopes)
          and scopes == sorted(set(scopes))
          and set(scopes) <= {'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'},
          'CLIENT_BOOTSTRAP_SCOPES')
    _need(type(value['bearer']) is str and re.fullmatch(r'[A-Za-z0-9_-]{43}', value['bearer']),
          'CLIENT_CREDENTIAL_INVALID')
    return SessionCredential(value['session_id'], value['project_id'], value['expires_ms'],
                             frozenset(scopes), value['bearer'])


@dataclass(frozen=True)
class SelectorLease:
    lease_id: str
    fencing_epoch: int
    expires_ms: int

    def __post_init__(self):
        _name(self.lease_id)
        _integer(self.fencing_epoch, 1)
        _integer(self.expires_ms, 1)


@dataclass(frozen=True)
class SelectorRevisions:
    source_revision: str
    source_sha256: str
    game_revision: str

    def __post_init__(self):
        _name(self.source_revision); _hash(self.source_sha256); _name(self.game_revision)


@dataclass(frozen=True)
class SelectorSelection:
    generation: int
    selection_hash: str
    release_id: str | None
    manifest_sha256: str | None

    def __post_init__(self):
        _integer(self.generation, 1); _hash(self.selection_hash)
        _need((self.release_id is None) == (self.manifest_sha256 is None))
        if self.release_id is not None:
            _need(type(self.release_id) is str and re.fullmatch(r'release-[0-9a-f]{32}', self.release_id))
            _hash(self.manifest_sha256)


@dataclass(frozen=True)
class SelectorSnapshot:
    project_id: str
    generation: int
    selection_hash: str
    revisions: SelectorRevisions
    stopped: bool
    ready: bool
    pending_command: str | None
    selected: SelectorSelection | None
    last_verified_adopted: SelectorSelection | None

    def __post_init__(self):
        _name(self.project_id); _integer(self.generation); _hash(self.selection_hash)
        _need(type(self.revisions) is SelectorRevisions)
        _need(type(self.stopped) is bool and type(self.ready) is bool)
        if self.pending_command is not None:
            _name(self.pending_command)
        for selected in (self.selected, self.last_verified_adopted):
            _need(selected is None or type(selected) is SelectorSelection)
        if self.selected is not None:
            _need((self.selected.generation, self.selected.selection_hash) == (self.generation, self.selection_hash))
        else:
            _need(self.generation == 0 and self.selection_hash == '0' * 64)
        if self.last_verified_adopted is not None:
            _need(self.last_verified_adopted.generation <= self.generation)
        if self.ready:
            _need(self.selected is not None and self.selected == self.last_verified_adopted)


@dataclass(frozen=True)
class SelectorStopResult:
    stopped: bool
    pending_command: str | None
    command: Response


def pending_selector_client_cleanup() -> tuple[ManagedFixtureClient, ...]:
    with _OWNERS_LOCK:
        return tuple(client for client in _OWNERS.values() if client._closing.is_set())


class ManagedFixtureClient:
    """Successful construction transfers both OwnedPipe lifetimes to client.

    The trusted caller stops using/closing the channels after transfer. A
    failed constructor transfers nothing. Separate channel locks permit Stop
    and lookup while a work response is stalled; no background pump is started.
    """
    def __init__(self, work: OwnedPipe, control: OwnedPipe, credential: SessionCredential,
                 *, timeout_ms: int = 1000):
        _need(type(work) is OwnedPipe and type(control) is OwnedPipe and work is not control,
              'CLIENT_DISTINCT_OWNED_PIPES_REQUIRED')
        _need(not work.closed and not control.closed, 'CLIENT_CLOSED_PIPE')
        _need(type(credential) is SessionCredential, 'CLIENT_CREDENTIAL_REQUIRED')
        _name(credential.project_id); _name(credential.session_id)
        _integer(credential.expires_ms, 1)
        _need(epoch_ms() < credential.expires_ms <= epoch_ms() + 900_000, 'CLIENT_CREDENTIAL_EXPIRED')
        _need(type(credential.bearer) is str and re.fullmatch(r'[A-Za-z0-9_-]{43}', credential.bearer),
              'CLIENT_CREDENTIAL_INVALID')
        _need(type(credential.scopes) is frozenset and all(type(s) is str for s in credential.scopes)
              and credential.scopes <= {'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'},
              'CLIENT_CREDENTIAL_INVALID')
        _need(type(timeout_ms) is int and 1 <= timeout_ms <= 30_000, 'CLIENT_TIMEOUT_INVALID')
        self.project_id, self._credential, self.timeout_ms = credential.project_id, credential, timeout_ms
        self._pipes = (work, control)
        self._locks = (threading.Lock(), threading.Lock())
        self._bad = [False, False]
        self._closing = threading.Event()
        self._state_lock = threading.Lock()
        self._can_activate = False
        with _OWNERS_LOCK:
            _need(len(_OWNERS) < MAX_CLIENTS, 'CLIENT_OWNER_LIMIT')
            _need(work not in _CHANNELS and control not in _CHANNELS, 'CLIENT_PIPE_ALREADY_BOUND')
            _OWNERS[id(self)] = self
            _CHANNELS[work] = _CHANNELS[control] = self

    @staticmethod
    def _remaining(deadline):
        remaining = deadline - time.monotonic()
        _need(remaining > 0, 'CLIENT_TIMEOUT')
        return min(30_000, max(1, math.ceil(remaining * 1000)))

    @staticmethod
    def _unknown(identifier, code='CLIENT_EXCHANGE_UNKNOWN'):
        return Response(Status.UNKNOWN, code, identifier, postconditions={'next_action': 'lookup'})

    def _decode(self, route, value, identifier):
        if type(value) is dict and 'status' in value:
            response = Response.from_dict(value)
            _need(response.command_id == identifier, 'CLIENT_COMMAND_MISMATCH')
            return response
        if route == '/v1/discovery':
            discovery = Discovery.from_dict(value)
            _need(discovery.project_id == self.project_id, 'CLIENT_PROJECT_MISMATCH')
            _need(discovery.schema_digest == SELECTOR_SCHEMA_DIGEST, 'CLIENT_SCHEMA_MISMATCH')
            names = [cap.operation for cap in discovery.capabilities]
            _need(len(names) == len(set(names)) and set(names) <= {'fixture.release.activate', 'fixture.release.inspect'})
            for capability in discovery.capabilities:
                expected = ((), (SELECTOR_SCOPE,)) if capability.operation == 'fixture.release.activate' else ((SELECTOR_SCOPE,), ())
                _need((capability.read_scopes, capability.write_scopes) == expected, 'CLIENT_CAPABILITY_SCOPE')
            with self._state_lock:
                self._can_activate = discovery.supports('fixture.release.activate') and 'fixture.write' in self._credential.scopes
            return discovery
        if route == '/v1/inspect':
            _shape(value, ('project_id', 'protocol_version', 'schema_digest', 'generation', 'selection_hash',
                           'revisions', 'stopped', 'ready', 'pending_command', 'selected', 'last_verified_adopted'))
            _need(value['project_id'] == self.project_id, 'CLIENT_PROJECT_MISMATCH')
            _need(value['protocol_version'] == PROTOCOL_VERSION and value['schema_digest'] == SELECTOR_SCHEMA_DIGEST,
                  'CLIENT_SCHEMA_MISMATCH')
            _shape(value['revisions'], ('source_revision', 'source_sha256', 'game_revision'))
            selections = []
            for key in ('selected', 'last_verified_adopted'):
                item = value[key]
                if item is not None:
                    _shape(item, ('generation', 'selection_hash', 'release_id', 'manifest_sha256'))
                    item = SelectorSelection(**item)
                selections.append(item)
            return SelectorSnapshot(value['project_id'], value['generation'], value['selection_hash'],
                SelectorRevisions(**value['revisions']), value['stopped'], value['ready'],
                value['pending_command'], *selections)
        if route == '/v1/lease':
            _shape(value, ('lease_id', 'fencing_epoch', 'expires_ms'))
            lease = SelectorLease(**value)
            _need(lease.expires_ms <= epoch_ms() + 30_000, 'CLIENT_LEASE_HORIZON')
            return lease
        if route == '/v1/stop':
            _shape(value, ('stopped', 'pending_command', 'command'))
            _need(value['stopped'] is True)
            if value['pending_command'] is not None:
                _name(value['pending_command'])
            response = Response.from_dict(value['command'])
            _need(response.command_id == identifier, 'CLIENT_COMMAND_MISMATCH')
            return SelectorStopResult(True, value['pending_command'], response)
        raise SelectorClientError('CLIENT_INVALID_REPLY')

    def _exchange(self, route, body, *, control=False):
        index = 1 if control else 0
        identifier = body.get('command_id', 'transport.request')
        frame = ('Bearer ' + self._credential.bearer + '\n' + route + '\n').encode('ascii') + canonical_bytes(body)
        _need(len(frame) <= MAX_FRAME_BYTES, 'CLIENT_FRAME_LIMIT')
        deadline = time.monotonic() + self.timeout_ms / 1000
        lock, pipe = self._locks[index], self._pipes[index]
        _need(lock.acquire(timeout=self._remaining(deadline) / 1000), 'CLIENT_CHANNEL_BUSY')
        sent = False
        try:
            _need(not self._closing.is_set(), 'CLIENT_CLOSING')
            if self._bad[index]:
                return self._unknown(identifier, 'CLIENT_CHANNEL_RECOVERY_REQUIRED')
            remaining = self._remaining(deadline)
            sent = True  # A failing native write can still have delivered data.
            pipe.write_frame(frame, timeout_ms=remaining)
            raw = pipe.read_frame(timeout_ms=self._remaining(deadline))
            cap = SELECTOR_INSPECT_MAX_BYTES if route == '/v1/inspect' else MAX_REPLY_BYTES
            _need(type(raw) is bytes and len(raw) <= cap, 'CLIENT_REPLY_LIMIT')
            return self._decode(route, parse_json_utf8(raw), identifier)
        except (SafetyViolation, ValidationError, OSError):
            if not sent:
                raise
            self._bad[index] = True
            with self._state_lock:
                self._can_activate = False
            return self._unknown(identifier)
        finally:
            lock.release()

    @staticmethod
    def _metadata(value):
        if type(value) is Response:
            raise SelectorClientError(value.code, response=value)
        return value

    def discover(self) -> Discovery:
        with self._state_lock:
            self._can_activate = False
        return self._metadata(self._exchange('/v1/discovery',
            {'project_id': self.project_id, 'protocol_version': PROTOCOL_VERSION}))

    def inspect(self) -> SelectorSnapshot:
        return self._metadata(self._exchange('/v1/inspect',
            {'project_id': self.project_id, 'protocol_version': PROTOCOL_VERSION}, control=True))

    def lease(self, *, ttl_ms=30_000) -> SelectorLease:
        _need(type(ttl_ms) is int and 1 <= ttl_ms <= 30_000, 'CLIENT_LEASE_TTL_INVALID')
        return self._metadata(self._exchange('/v1/lease', {'project_id': self.project_id, 'ttl_ms': ttl_ms}))

    def build_activation(self, command_id, *, assets, entrypoint, inspection: SelectorSnapshot,
                         lease: SelectorLease, deadline_after_ms=10_000) -> Request:
        _name(command_id)
        with self._state_lock:
            _need(self._can_activate and not self._closing.is_set(), 'CLIENT_ACTIVATION_UNAVAILABLE')
        _need(type(inspection) is SelectorSnapshot and inspection.project_id == self.project_id,
              'CLIENT_INSPECTION_REQUIRED')
        _need(not inspection.stopped and inspection.pending_command is None, 'CLIENT_ACTIVATION_UNAVAILABLE')
        _need(type(lease) is SelectorLease, 'CLIENT_LEASE_REQUIRED')
        _need(type(deadline_after_ms) is int and 1 <= deadline_after_ms <= 30_000, 'CLIENT_DEADLINE_INVALID')
        _need(type(assets) is dict and 1 <= len(assets) <= 16, 'CLIENT_ASSET_LIMIT')
        copied, graph = {}, {}
        for name, asset in assets.items():
            _asset_id(name)
            raw, graph[name] = _asset(canonical_bytes(asset))
            copied[name] = parse_json_utf8(raw)
        _graph(entrypoint, graph)
        payload = {'assets': copied, 'entrypoint': entrypoint, 'expected_generation': inspection.generation,
                   'expected_selection_hash': inspection.selection_hash,
                   'expected_source_revision': inspection.revisions.source_revision,
                   'expected_source_sha256': inspection.revisions.source_sha256,
                   'expected_game_revision': inspection.revisions.game_revision}
        raw = canonical_bytes(payload)
        _need(len(raw) <= SELECTOR_PAYLOAD_MAX_BYTES, 'CLIENT_PAYLOAD_LIMIT')
        now = epoch_ms()
        deadline = min(now + deadline_after_ms, lease.expires_ms, self._credential.expires_ms)
        _need(deadline > now, 'CLIENT_AUTHORITY_EXPIRED')
        return Request(command_id, self.project_id, 'fixture.release.activate', lease.lease_id, lease.fencing_epoch,
                       inspection.revisions.game_revision, {'stable_id': 'active-release'}, payload,
                       'sha256:' + hashlib.sha256(raw).hexdigest(), deadline, SCHEMA_VERSION)

    def activate(self, request: Request) -> Response:
        _need(type(request) is Request, 'CLIENT_REQUEST_REQUIRED')
        checked = Request.from_dict(parse_json_utf8(canonical_bytes(request.as_dict())))
        _need(checked.project_id == self.project_id and checked.operation == 'fixture.release.activate'
              and checked.target == {'stable_id': 'active-release'}, 'CLIENT_REQUEST_SCOPE')
        _need(len(canonical_bytes(checked.payload)) <= SELECTOR_PAYLOAD_MAX_BYTES, 'CLIENT_PAYLOAD_LIMIT')
        _need(0 < checked.deadline_ms - epoch_ms() <= 30_000, 'CLIENT_DEADLINE_INVALID')
        return self._exchange('/v1/commands', checked.as_dict())

    def lookup(self, command_id) -> Response:
        _name(command_id)
        return self._exchange('/v1/lookup', {'project_id': self.project_id, 'command_id': command_id}, control=True)

    def cancel(self, command_id) -> Response:
        _name(command_id)
        return self._exchange('/v1/cancel', {'project_id': self.project_id, 'command_id': command_id}, control=True)

    def stop(self, command_id='control.stop') -> SelectorStopResult | Response:
        _name(command_id)
        with self._state_lock:
            self._can_activate = False
        return self._exchange('/v1/stop', {'project_id': self.project_id, 'command_id': command_id}, control=True)

    def close(self):
        self._closing.set()
        for pipe in self._pipes:
            pipe.request_stop()
        incomplete = False
        for lock, pipe in zip(self._locks, self._pipes):
            if not lock.acquire(blocking=False):
                incomplete = True
                continue
            try:
                try:
                    pipe.close()
                except SafetyViolation:
                    incomplete = True
            finally:
                lock.release()
        if incomplete:
            raise SelectorClientError('CLIENT_CLOSE_PENDING', cleanup_owner=self)
        with _OWNERS_LOCK:
            _OWNERS.pop(id(self), None)
            for pipe in self._pipes:
                if _CHANNELS.get(pipe) is self:
                    _CHANNELS.pop(pipe)
