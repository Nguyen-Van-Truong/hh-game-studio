"""Trusted queue pump for native Blender and Godot writers.

Reservations carry the hash of the full canonical Request (including absolute
deadline/fence), never credentials or payload. Effects remain subject to the
existing native owner. Unknown completion consumes the local ticket and holds
the durable slot until explicit authenticated lookup plus current readback.
Godot read-only inspection stays on the owner route: it has no durable command
receipt and cannot be reconciled as a queued write after coordinator failure.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
import hashlib
import math
import sys
import secrets
import threading
import time
import weakref
from pathlib import Path

from ...protocol.core import Request, Response, Status, canonical_bytes, parse_json
from ..blender import client_write_catalog as catalog
from ..blender.client_writer_owner import BlenderWriterClientOwner
from ..blender.client_owner import _OWNERS, _REGISTER
from ..blender.client_ledger import binding_value, MAX_COMMANDS
from ..core.limits import SafetyViolation
from ..core.transport import epoch_ms
from .durable_broker import JobRequest, OwnerResult, Reservation
from .queue_owner import QueueOwner

_BIND = threading.RLock()
_BINDINGS = weakref.WeakKeyDictionary()


class NativeDispatchError(SafetyViolation):
    pass


def _need(value, code):
    if not value:
        raise NativeDispatchError(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _registered(owner, *, control=False):
    _need(type(owner) is BlenderWriterClientOwner, 'NATIVE_BLENDER_OWNER_REQUIRED')
    with _REGISTER:
        registered = _OWNERS.get(owner._host)
        _need(registered is not None and registered() is owner._read_owner,
              'NATIVE_REGISTERED_OWNER_REQUIRED')
    owner._check_native(control=control)


@dataclass(frozen=True, eq=False, init=False)
class BlenderOwnerBinding:
    owner: object = field(repr=False)
    body: bytes = field(repr=False)
    authorization: str = field(repr=False)
    grant: object = field(repr=False)
    ledger_binding: bytes = field(repr=False)
    resource: str
    session_id: str
    project_id: str
    command_id: str
    command_sha256: str
    catalog_digest: str

    def __init__(self, *args, **kwargs):
        raise TypeError('use BlenderOwnerBinding.create')

    @classmethod
    def create(cls, owner, *, body, authorization, catalog_digest):
        _need(cls is BlenderOwnerBinding, 'NATIVE_BINDING_REQUIRED')
        _registered(owner)
        grant = owner._auth(body, authorization, catalog_digest)
        request = catalog.validate_request(body, project_id=owner.project_id,
                                           source_sha256=owner._source_sha256)
        for operation in (request.operation, catalog.READ, 'control.lookup', 'control.stop'):
            owner.sessions._check_grant(grant, operation)
        _need(request.operation in owner._supported, 'NATIVE_OPERATION_NOT_CONNECTED')
        catalog.translate(request, binding=owner._ledger.binding, session_id=grant.session_id)
        raw = canonical_bytes(request.as_dict())
        ledger = canonical_bytes(binding_value(owner._ledger.binding))
        values = dict(owner=owner, body=raw, authorization=authorization, grant=grant,
                      ledger_binding=ledger, resource='blender-' + _sha(ledger),
                      session_id=grant.session_id, project_id=request.project_id,
                      command_id=request.command_id, command_sha256=_sha(raw),
                      catalog_digest=catalog_digest)
        binding = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(binding, name, value)
        with _BIND:
            _BINDINGS[binding] = tuple(values.values())
        return binding

    def check(self, *, control=False):
        with _BIND:
            _need(type(self) is BlenderOwnerBinding and _BINDINGS.get(self) == tuple(
                getattr(self, name) for name in self.__dataclass_fields__),
                'NATIVE_BINDING_CHANGED')
        _registered(self.owner, control=control)
        _need(self.ledger_binding == canonical_bytes(binding_value(self.owner._ledger.binding)),
              'NATIVE_OWNER_BINDING_CHANGED')
        grant = self.owner._auth(parse_json(self.body), self.authorization, self.catalog_digest)
        _need(grant is self.grant and grant.session_id == self.session_id,
              'NATIVE_SESSION_CHANGED')
        self.owner.sessions._check_grant(grant, 'control.lookup')
        return Request.from_json(self.body)

    def lookup(self):
        return self.owner.lookup({'project_id': self.project_id, 'command_id': self.command_id},
                                 authorization=self.authorization, catalog_digest=self.catalog_digest)


def _godot_owner_required(owner):
    """Accept only the exact dynamically loaded publication owner class."""
    module = sys.modules.get(type(owner).__module__)
    expected = Path(__file__).resolve().parents[2] / 'godot-addon' / 'publication_owner.py'
    _need(module is not None and Path(getattr(module, '__file__', '')).resolve() == expected
          and type(owner) is getattr(module, 'GodotPublicationOwner', None),
          'NATIVE_GODOT_OWNER_REQUIRED')
    return module


def _godot_lease(owner, request, grant):
    with owner._lock:
        lease = owner._leases.get(grant.session_id)
        _need(lease is not None and lease.lease_id == request.lease_id
              and lease.fencing_epoch == request.fencing_epoch,
              'NATIVE_GODOT_LEASE_REQUIRED')
    owner.sessions.check(grant, lease, deadline_ms=request.deadline_ms,
                         operation=request.operation)
    owner.contract.validate_deadline(request, now_ms=epoch_ms(), lease_expires_ms=lease.expires_ms)
    return lease


@dataclass(frozen=True, eq=False, init=False)
class GodotOwnerBinding:
    owner: object = field(repr=False)
    body: bytes = field(repr=False)
    authorization: str = field(repr=False)
    grant: object = field(repr=False)
    resource: str
    session_id: str
    project_id: str
    command_id: str
    command_sha256: str
    catalog_digest: str
    source_closure_sha256: str
    source_release: object = field(repr=False)
    editor_identity: object = field(repr=False)
    storage_id: str
    journal: object = field(repr=False)
    sessions: object = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError('use GodotOwnerBinding.create')

    @classmethod
    def create(cls, owner, *, body, authorization, catalog_digest):
        _need(cls is GodotOwnerBinding, 'NATIVE_BINDING_REQUIRED')
        _godot_owner_required(owner)
        _need(type(body) is dict, 'NATIVE_GODOT_REQUEST_REQUIRED')
        request = Request.from_dict(body)
        grant = owner._auth(body, request.operation, authorization, catalog_digest)
        _need(request.project_id == owner.project_id, 'NATIVE_GODOT_PROJECT_CHANGED')
        _need(request.operation in (owner.auth_model.EDIT_OPERATIONS
                                    | {'scene.save', 'script_text.replace'}),
              'NATIVE_GODOT_OPERATION_NOT_CONNECTED')
        for operation in ('scene.inspect', 'control.lookup'):
            owner.sessions._check_grant(grant, operation)
        owner._same_release()
        lease = _godot_lease(owner, request, grant)
        # Validate the real catalog (including the shorter edit horizon)
        # before consuming a durable queue identity. Submit checks again.
        owner.contract.validate_request(request, owner._context(owner.inspect(), lease))
        identity = canonical_bytes(owner._editor.identity)
        values = dict(owner=owner, body=canonical_bytes(request.as_dict()),
                      authorization=authorization, grant=grant,
                      resource='godot-' + owner.storage_id,
                      session_id=grant.session_id, project_id=request.project_id,
                      command_id=request.command_id, command_sha256=_sha(canonical_bytes(request.as_dict())),
                      catalog_digest=catalog_digest,
                      source_closure_sha256=owner._source_closure_sha256,
                      source_release=owner._source_release, editor_identity=identity,
                      storage_id=owner.storage_id, journal=owner._journal, sessions=owner.sessions)
        binding = object.__new__(cls)
        for name, value in values.items():
            object.__setattr__(binding, name, value)
        with _BIND:
            _BINDINGS[binding] = tuple(values.values())
        return binding

    def check(self, *, control=False):
        with _BIND:
            _need(type(self) is GodotOwnerBinding and _BINDINGS.get(self) == tuple(
                getattr(self, name) for name in self.__dataclass_fields__),
                  'NATIVE_BINDING_CHANGED')
        _godot_owner_required(self.owner)
        request = Request.from_json(self.body)
        _need(self.owner._source_closure_sha256 == self.source_closure_sha256
              and self.owner._source_release == self.source_release
              and self.owner.storage_id == self.storage_id
              and self.owner._journal is self.journal and self.owner.sessions is self.sessions
              and (control and request.operation == 'script_text.replace'
                   or canonical_bytes(self.owner._editor.lookup_identity if control
                                      else self.owner._editor.identity) == self.editor_identity),
              'NATIVE_GODOT_OWNER_BINDING_CHANGED')
        self.owner._same_release()
        grant = self.owner._auth(parse_json(self.body), request.operation,
                                 self.authorization, self.catalog_digest)
        _need(grant is self.grant and grant.session_id == self.session_id,
              'NATIVE_GODOT_SESSION_CHANGED')
        self.owner.sessions._check_grant(grant, 'control.lookup')
        if not control:
            _godot_lease(self.owner, request, grant)
        return request

    def lookup(self):
        return self.owner.lookup({'project_id': self.project_id, 'command_id': self.command_id},
                                 authorization=self.authorization, catalog_digest=self.catalog_digest)


class NativeOwnerDispatcher:
    def __init__(self, queue):
        _need(type(queue) is QueueOwner and queue.broker is not None, 'NATIVE_QUEUE_OWNER_REQUIRED')
        self.queue = queue
        self._bindings, self._owners, self._issued = {}, {}, {}
        self._recovery_only = set()
        self._phase = threading.Lock()
        self._stop = threading.Event()
        self._closed = False
        with _BIND, queue._lifecycle:
            _need(queue._dispatcher is None, 'NATIVE_QUEUE_ALREADY_BOUND')
            queue._dispatcher = self

    @staticmethod
    def _job_id(binding):
        # Changed envelope/session must conflict, never acquire a second effect
        # identity for the same owner's public command ID.
        return 'native-' + _sha(canonical_bytes([
            binding.resource, binding.project_id, binding.command_id]))

    def _open(self):
        _need(not self._closed and not self._stop.is_set(), 'NATIVE_DISPATCH_STOPPED')

    def register(self, binding):
        self._register_binding(binding, recovery=False)

    def register_recovery(self, binding):
        """Reattach an exact surviving owner for lookup only, never execution.

        A script publication may replace the editor before queue collection.
        Its old binding is valid history but cannot authorize another effect.
        Reopening a queue does not reconstruct an owner, grant or binding.
        """
        self._register_binding(binding, recovery=True)

    def _register_binding(self, binding, *, recovery):
        _need(type(binding) in (BlenderOwnerBinding, GodotOwnerBinding), 'NATIVE_BINDING_REQUIRED')
        binding.check(control=recovery)
        owner = binding.owner
        key = self._job_id(binding)
        with _BIND:
            self._open()
            if recovery:
                row = self.queue.broker.lookup(key)
                _need(row is not None and row.state in ('RESERVED', 'UNKNOWN')
                      and row.fence is not None
                      and row.job.resources == (binding.resource,)
                      and row.job.project_id == binding.project_id
                      and row.job.session_id == binding.session_id
                      and row.command_sha256 == binding.command_sha256,
                      'NATIVE_RECOVERY_RESERVATION_REQUIRED')
            else:
                _need(key not in self._recovery_only, 'NATIVE_RECOVERY_LOOKUP_ONLY')
        if type(binding) is BlenderOwnerBinding:
            with _BIND, owner._attachment_lock, ExitStack() as stack:
                self._open()
                stack.enter_context(owner._host._close_lock)
                for publisher in owner._publications.values():
                    stack.enter_context(publisher._mutex)
                _registered(owner)
                _need(owner._transport is None and owner._queue_dispatcher in (None, self)
                      and getattr(owner._host, '_queue_dispatcher', None) in (None, self),
                      'NATIVE_OWNER_ALREADY_BOUND')
                _need(self._owners.get(binding.resource, owner) is owner, 'NATIVE_OWNER_BINDING_CHANGED')
                key = self._job_id(binding)
                _need(key not in self._bindings or self._bindings[key] is binding,
                      'NATIVE_BINDING_ALREADY_REGISTERED')
                _need(len(self._bindings) < self.queue.broker.limits.receipts
                      and sum(b.owner is owner for b in self._bindings.values()) < MAX_COMMANDS,
                      'NATIVE_BINDING_CAPACITY')
                for publisher in owner._publications.values():
                    _need(getattr(publisher, '_queue_dispatcher', None) in (None, self),
                          'NATIVE_OWNER_ALREADY_BOUND')
                owner._queue_dispatcher = owner._host._queue_dispatcher = self
                for publisher in owner._publications.values():
                    publisher._queue_dispatcher = self
                self._owners[binding.resource] = owner
                self._bindings[key] = binding
                if recovery:
                    self._recovery_only.add(key)
            return
        # Godot's publication owner is dynamically loaded and has a single
        # owner lock, not Blender's transport/publication attachment graph.
        # Attach an explicit queue marker and admission lock so its direct
        # PublicationTransport cannot race a queued effect.
        with _BIND, owner._attachment_lock, owner._lock:
            self._open()
            _need(not owner._closed and not owner._work.locked()
                  and owner._transport is None
                  and owner._queue_dispatcher in (None, self),
                  'NATIVE_OWNER_ALREADY_BOUND')
            _need(self._owners.get(binding.resource, owner) is owner, 'NATIVE_OWNER_BINDING_CHANGED')
            key = self._job_id(binding)
            _need(key not in self._bindings or self._bindings[key] is binding,
                  'NATIVE_BINDING_ALREADY_REGISTERED')
            _need(len(self._bindings) < self.queue.broker.limits.receipts
                  and sum(b.owner is owner for b in self._bindings.values()) < MAX_COMMANDS,
                  'NATIVE_BINDING_CAPACITY')
            owner._queue_dispatcher = self
            self._owners[binding.resource] = owner
            self._bindings[key] = binding
            if recovery:
                self._recovery_only.add(key)

    def enqueue(self, binding, *, dependencies=()):
        with _BIND:
            self._open()
            _need(type(binding) in (BlenderOwnerBinding, GodotOwnerBinding)
                  and self._bindings.get(self._job_id(binding)) is binding,
                  'NATIVE_BINDING_NOT_REGISTERED')
            _need(self._job_id(binding) not in self._recovery_only, 'NATIVE_RECOVERY_LOOKUP_ONLY')
            request = binding.check()
            owner, grant = binding.owner, binding.grant
            # Fail the harness/admission before consuming native IDs if it
            # confuses the lease horizon with the shorter operation horizon.
            if type(binding) is BlenderOwnerBinding and request.operation == catalog.READ:
                lease = owner.sessions.resolve_lease(grant, request.lease_id, request.fencing_epoch)
                owner.sessions.check_read(grant, lease, deadline_ms=request.deadline_ms)
            elif type(binding) is BlenderOwnerBinding:
                lease = owner.sessions.resolve_writer_lease(grant, request.lease_id, request.fencing_epoch)
                owner.sessions.check_write(grant, lease, operation=request.operation,
                                           deadline_ms=request.deadline_ms)
            self._open()
            job = JobRequest(self._job_id(binding), binding.project_id, binding.session_id,
                             request.deadline_ms, (binding.resource,), tuple(dependencies),
                             binding.command_sha256)
            return self.queue.broker.enqueue(job, now_ms=epoch_ms())

    def reserve(self):
        with _BIND:
            self._open()
            snapshot = self.queue.broker.snapshot()
            _need(all(job.job_id in self._bindings for job in snapshot.pending),
                  'NATIVE_RECOVERY_REQUIRED')
            reservation = self.queue.broker.reserve_next(now_ms=epoch_ms())
            if reservation is not None:
                self._issued[reservation.job.job_id] = reservation
            return reservation

    def _binding_for(self, reservation):
        binding = self._bindings.get(reservation.job.job_id)
        _need(binding is not None and reservation.job.resources == (binding.resource,)
              and reservation.job.session_id == binding.session_id
              and reservation.job.project_id == binding.project_id
              and reservation.command_sha256 == binding.command_sha256,
              'NATIVE_RECOVERY_BINDING_MISMATCH')
        current = self.queue.broker.lookup(reservation.job.job_id)
        _need(current is not None and current.state in ('RESERVED', 'UNKNOWN')
              and current.job == reservation.job and current.fence == reservation.fence,
              'NATIVE_RESERVATION_REQUIRED')
        _need(binding.owner._queue_dispatcher is self, 'NATIVE_OWNER_BINDING_CHANGED')
        return binding

    def _collect(self, reservation, binding, response=None):
        if type(binding) is GodotOwnerBinding:
            return self._collect_godot(reservation, binding, response)
        return self._collect_blender(reservation, binding, response)

    def _collect_godot(self, reservation, binding, response=None):
        request = binding.check(control=True)
        owner = binding.owner
        _need(not owner._work.locked(), 'NATIVE_OWNER_PHASE_ACTIVE')
        with owner.sessions._mutex:
            _need(owner.sessions._active is None, 'NATIVE_OWNER_PHASE_ACTIVE')
        actual = binding.lookup()
        raw = canonical_bytes(actual.as_dict())
        if response is not None:
            _need(raw == canonical_bytes(response.as_dict()), 'NATIVE_GODOT_LOOKUP_MISMATCH')
        _need(actual.command_id == request.command_id and actual.status in {
            Status.COMMITTED, Status.REJECTED, Status.UNKNOWN},
              'NATIVE_GODOT_NOT_TERMINAL')
        if actual.status is Status.REJECTED and response is not None:
            _need(actual.postconditions.get('public_ack') is False
                  and actual.postconditions.get('request_digest') == request.digest
                  and 'durable_receipt_sha256' not in actual.postconditions,
                  'NATIVE_GODOT_REJECTION_MISMATCH')
        else:
            durable = owner._journal.lookup_response(request.command_id, request.digest)
            _need(type(durable) is bytes and durable == raw,
                  'NATIVE_GODOT_DURABLE_RESPONSE_MISMATCH')
            if actual.status is Status.UNKNOWN:
                _need(actual.postconditions.get('public_ack') is False
                      and actual.postconditions.get('next_action') == 'lookup.reconcile',
                      'NATIVE_GODOT_UNKNOWN_MISMATCH')
        if actual.status is Status.COMMITTED:
            post = actual.postconditions
            durable = owner._journal.lookup(request.command_id, request.digest)
            _need(post.get('public_ack') is True
                  and post.get('request_digest') == request.digest
                  and type(durable) is dict and durable.get('phase') == 'COMMITTED'
                  and durable.get('receipt_sha256') == post.get('durable_receipt_sha256')
                  and type(durable.get('receipt')) is dict
                  and _sha(canonical_bytes(durable['receipt'])) == post.get('durable_receipt_sha256'),
                  'NATIVE_GODOT_RECEIPT_MISMATCH')
            self._godot_readback(binding, request, actual, durable['receipt'])
        result = self.queue.broker.record_owner_result(
            reservation, OwnerResult(actual.status.value, binding.command_sha256, _sha(raw)))
        return result, actual

    @staticmethod
    def _godot_readback(binding, request, actual, receipt):
        owner, post = binding.owner, actual.postconditions
        identity = owner._editor.identity
        observed = owner.inspect()
        selected = owner._journal.selection_facts()
        manifest = parse_json(owner._journal.read_selected_bundle().manifest_bytes)
        _need(receipt.get('command_id') == request.command_id
              and receipt.get('digest') == request.digest
              and receipt.get('operation') == request.operation
              and receipt.get('status') == 'COMMITTED'
              and owner._source_closure_sha256 == binding.source_closure_sha256
              and type(observed) is dict
              and observed.get('revision') == post.get('scene_revision')
              and observed.get('project_revision') == post.get('project_revision')
              and observed.get('generation') == post.get('generation')
              and observed.get('editor_session_id') == identity['session_id']
              and observed.get('selected_files') == manifest['files']
              and observed.get('project_revision') == manifest['project_revision']
              and selected['selector']['selection'] == post.get('selection')
              and receipt.get('selection') == post.get('selection')
              and receipt.get('selector_version') == selected['selector_version'],
              'NATIVE_GODOT_READBACK_CHANGED')
        if request.operation in owner.auth_model.EDIT_OPERATIONS:
            _need(receipt.get('schema') == 'hh-godot-editor-terminal-5'
                  and canonical_bytes(identity) == binding.editor_identity
                  and receipt.get('editor') == identity
                  and str(receipt.get('root_instance_id')) == observed.get('root_instance_id')
                  and actual.code == 'GODOT_EDITOR_EDITED'
                  and post.get('effect_scope') == 'editor_session'
                  and post.get('files_saved') is False and post.get('live_state_durable') is False
                  and post.get('journal_receipt_durable') is True
                  and post.get('history_boundary') is False
                  and post.get('editor_session_id') == identity['session_id']
                  and all(post.get(key) == observed.get(key) for key in
                          ('history_id', 'can_undo', 'can_redo'))
                  and receipt['observation']['semantic_revision'] == observed.get('revision')
                  and receipt['observation']['history_id_after'] == observed.get('history_id'),
                  'NATIVE_GODOT_EDIT_READBACK_CHANGED')
            return
        adoption = owner._journal.lookup_adoption(request.command_id, request.digest)
        _need(receipt.get('schema') == 'hh-godot-publication-terminal-4'
              and receipt.get('adoption_sha256') == _sha(canonical_bytes(adoption))
              and adoption['generation_after'] == observed['generation']
              and adoption['semantic_revision'] == observed['revision']
              and adoption['project_revision'] == observed['project_revision']
              and adoption['files'] == observed['selected_files']
              and post.get('history_boundary') is True
              and observed.get('can_undo') is False and observed.get('can_redo') is False,
              'NATIVE_GODOT_PUBLICATION_READBACK_CHANGED')
        if request.operation == 'script_text.replace':
            _need(actual.code == 'GODOT_MANAGED_SCRIPT_REPLACED'
                  and canonical_bytes(adoption['old_editor']) == binding.editor_identity
                  and adoption['new_editor'] == identity
                  and canonical_bytes(identity) != binding.editor_identity
                  and str(adoption['root_after']) == observed['root_instance_id'],
                  'NATIVE_GODOT_SUCCESSOR_CHANGED')
        else:
            _need(request.operation == 'scene.save' and actual.code == 'GODOT_MANAGED_SCENE_SAVED'
                  and canonical_bytes(identity) == binding.editor_identity
                  and adoption['editor'] == identity
                  and str(adoption['root_instance_id_after']) == observed['root_instance_id'],
                  'NATIVE_GODOT_SAVED_EDITOR_CHANGED')

    def _collect_blender(self, reservation, binding, response=None):
        request = binding.check(control=True)
        owner = binding.owner
        _need(not owner._work.locked(), 'NATIVE_OWNER_PHASE_ACTIVE')
        with owner.sessions._mutex:
            _need(owner.sessions._active is None and owner.sessions._write_active is None,
                  'NATIVE_OWNER_PHASE_ACTIVE')
        # replay() is a history read, not submit(): it checks the complete
        # original Request/native translation/session against the saved INTENT.
        command = parse_json(catalog.translate(request, binding=owner._ledger.binding,
                                               session_id=binding.session_id))
        saved = owner._ledger.replay(binding.grant, request, command)
        # A synchronous pre-admission refusal can have no ledger INTENT. Only
        # the fresh exact owner return proves that case; historical lookup
        # cannot reconstruct a missing refusal after coordinator death.
        if saved is None and type(response) is Response and response.status is Status.REJECTED:
            _need(response.command_id == request.command_id
                  and response.postconditions.get('public_ack') is False
                  and response.postconditions.get('ledger_receipt_only') is True,
                  'NATIVE_OWNER_RECEIPT_MISMATCH')
            owner.sessions._check_grant(binding.grant, 'control.lookup')
            raw = canonical_bytes(response.as_dict())
            return self.queue.broker.record_owner_result(
                reservation, OwnerResult('REJECTED', binding.command_sha256, _sha(raw))), response
        _need(saved is not None and saved.response is not None, 'NATIVE_TERMINAL_PROOF_REQUIRED')
        actual = binding.lookup()
        raw = canonical_bytes(actual.as_dict())
        _need(raw == saved.response and (response is None or raw == canonical_bytes(response.as_dict())),
              'NATIVE_OWNER_LOOKUP_MISMATCH')
        _need(actual.command_id == request.command_id and actual.status in {
            Status.COMMITTED, Status.REJECTED, Status.CANCELED, Status.UNKNOWN},
              'NATIVE_OWNER_NOT_TERMINAL')
        if actual.status is Status.UNKNOWN:
            post = actual.postconditions
            _need(post.get('public_ack') is False
                  and post.get('ledger_receipt_only') is True
                  and post.get('next_action') == 'lookup.reconcile'
                  and post.get('manual_state_preserved') is True
                  and isinstance(post.get('manual_revision'), str),
                  'NATIVE_BLENDER_UNKNOWN_MISMATCH')
        if actual.status is Status.COMMITTED:
            post = actual.postconditions
            _need(post.get('public_ack') is False and post.get('ledger_receipt_only') is True,
                  'NATIVE_OWNER_RECEIPT_MISMATCH')
            if request.operation in catalog.EDIT_OPERATIONS | {catalog.READ}:
                observation = post.get('observation', {})
                _need(actual.code == 'BLENDER_CLIENT_READBACK'
                      and observation.get('pid') == owner._host.pid
                      and observation.get('generation') == owner._host._session
                      and observation.get('source_sha256') == owner._source_sha256,
                      'NATIVE_OWNER_READBACK_REQUIRED')
                owner.sessions._check_grant(binding.grant, catalog.READ)
                # A new read ID on EACH collection attempt is essential:
                # native idempotency must not substitute an old observation.
                live = owner._read_owner._read_native(
                    'qr' + secrets.token_hex(20), epoch_ms() + catalog.MAX_READ_MS)
                _need(canonical_bytes(live) == canonical_bytes(observation.get('scene'))
                      and actual.result_revision == live['revision'],
                      'NATIVE_OWNER_READBACK_CHANGED')
            else:
                publication = post.get('publication', {})
                publisher = owner._publications[request.operation]
                with publisher._mutex:
                    manifest, artifacts = publisher.read_selected()
                    private = publisher.lookup_bytes(publication['receipt']['command_id'])
                    _need(actual.code == 'BLENDER_CLIENT_PUBLICATION'
                          and publication['storage_id'] == publisher.storage_id
                          and publication['receipt_sha256'] == 'sha256:' + _sha(private)
                          and publication['receipt'] == parse_json(private)
                          and publication['selector_version'] == publisher._state['terminal']['selector_version']
                          and manifest['scene_revision'] == request.expected_revision
                          and publication['generation'] == owner._host._session
                          and publication['source_sha256'] == owner._source_sha256
                          and all(publication['receipt']['artifacts'][name] ==
                                  {'sha256': _sha(data), 'size_bytes': len(data)}
                                  for name, data in artifacts.items()),
                          'NATIVE_OWNER_READBACK_CHANGED')
        owner.sessions._check_grant(binding.grant, 'control.lookup')
        return self.queue.broker.record_owner_result(
            reservation, OwnerResult(actual.status.value, binding.command_sha256, _sha(raw))), actual

    def advance(self, reservation):
        _need(type(reservation) is Reservation, 'NATIVE_RESERVATION_REQUIRED')
        _need(self._phase.acquire(blocking=False), 'NATIVE_PHASE_BUSY')
        try:
            with _BIND:
                self._open()
                _need(reservation.job.job_id not in self._recovery_only, 'NATIVE_RECOVERY_LOOKUP_ONLY')
                _need(not reservation.recovered
                      and self._issued.get(reservation.job.job_id) is reservation,
                      'NATIVE_RESERVATION_REQUIRED')
                binding = self._binding_for(reservation)
                self._issued.pop(reservation.job.job_id)
            owner = binding.owner
            _need(owner._admission.acquire(blocking=False), 'NATIVE_OWNER_PHASE_ACTIVE')
            try:
                self._open()
                binding.check()
                result = owner.submit(parse_json(binding.body), authorization=binding.authorization,
                                      catalog_digest=binding.catalog_digest)
                return self._collect(reservation, binding, result)[1]
            finally:
                owner._admission.release()
        finally:
            self._phase.release()

    def reconcile(self, reservation, binding):
        """Explicit lookup only after lost collection; never replays an effect."""
        _need(type(reservation) is Reservation
              and type(binding) in (BlenderOwnerBinding, GodotOwnerBinding),
              'NATIVE_RECONCILE_REQUIRED')
        _need(self._phase.acquire(blocking=False), 'NATIVE_PHASE_BUSY')
        try:
            with _BIND:
                _need(not self._closed and self._binding_for(reservation) is binding,
                      'NATIVE_BINDING_NOT_REGISTERED')
                self._issued.pop(reservation.job.job_id, None)
            _need(binding.owner._admission.acquire(blocking=False), 'NATIVE_OWNER_PHASE_ACTIVE')
            try:
                return self._collect(reservation, binding)[0]
            finally:
                binding.owner._admission.release()
        finally:
            self._phase.release()

    def stop(self):
        # Local latch precedes every storage/native wait. Supervisor owns this
        # internal control; expired client credentials cannot prevent shutdown.
        self._stop.set()
        with _BIND:
            _need(not self._closed, 'NATIVE_DISPATCH_STOPPED')
            owners = tuple(self._owners.values())
        for owner in owners:
            owner.sessions._stopped.set()
            if type(owner) is BlenderWriterClientOwner:
                for publisher in owner._publications.values():
                    publisher.request_stop()
        failure = None
        for owner in owners:
            try:
                if type(owner) is BlenderWriterClientOwner:
                    owner._durable.stop()
                    for publisher in owner._publications.values():
                        publisher.stop()
                else:
                    _godot_owner_required(owner)
                    owner.request_stop()
            except BaseException as error:
                if type(owner) is BlenderWriterClientOwner:
                    owner._hold()
                else:
                    owner.sessions.halt()
                    owner._held = True
                failure = error
        snapshot = self.queue.broker.stop()
        if failure is not None:
            raise NativeDispatchError('NATIVE_STOP_UNKNOWN') from failure
        return snapshot

    def close(self):
        self._stop.set()
        _need(self._phase.acquire(blocking=False), 'NATIVE_PHASE_BUSY')
        try:
            with _BIND, self.queue._lifecycle:
                # Validate all drains before detaching any owner. A later
                # pending Godot must not leave earlier owners half detached.
                for owner in self._owners.values():
                    if type(owner) is not BlenderWriterClientOwner:
                        stop_thread = getattr(owner, '_stop_thread', None)
                        _need(stop_thread is None or not stop_thread.is_alive(),
                              'NATIVE_STOP_DRAIN_REQUIRED')
                for owner in self._owners.values():
                    if type(owner) is not BlenderWriterClientOwner:
                        with owner._attachment_lock:
                            if owner._queue_dispatcher is self:
                                owner._queue_dispatcher = None
                        continue
                    with owner._attachment_lock, owner._host._close_lock, ExitStack() as stack:
                        for publisher in owner._publications.values():
                            stack.enter_context(publisher._mutex)
                        if owner._queue_dispatcher is self:
                            owner._queue_dispatcher = None
                        if getattr(owner._host, '_queue_dispatcher', None) is self:
                            owner._host._queue_dispatcher = None
                        for publisher in owner._publications.values():
                            if getattr(publisher, '_queue_dispatcher', None) is self:
                                publisher._queue_dispatcher = None
                self._closed = True
                self._bindings.clear()
                self._issued.clear()
                self._recovery_only.clear()
                if self.queue._dispatcher is self:
                    self.queue._dispatcher = None
        finally:
            self._phase.release()

    def drain_stop(self, *, timeout=95):
        """Supervisor wait after the priority Stop latch, never a wire call."""
        _need(type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 95,
              'NATIVE_STOP_INVALID_TIMEOUT')
        _need(self._stop.is_set() and not self._closed, 'NATIVE_STOP_REQUIRED')
        deadline = time.monotonic() + timeout
        # Both apps may still be executing/collecting a result after Stop.
        # A timeout preserves the attached owner and its uncertain reservation;
        # it cannot claim a successful drain or silently detach that work.
        _need(self._phase.acquire(timeout=timeout), 'NATIVE_STOP_DRAIN_REQUIRED')
        try:
            with _BIND:
                _need(not self._closed, 'NATIVE_DISPATCH_STOPPED')
                owners = tuple(self._owners.values())
            for owner in owners:
                if type(owner) is BlenderWriterClientOwner:
                    continue  # Synchronous Blender Stop persistence finished in stop().
                _godot_owner_required(owner)
                thread = getattr(owner, '_stop_thread', None)
                _need(thread is not None, 'NATIVE_STOP_REQUIRED')
                thread.join(timeout=max(0, deadline - time.monotonic()))
                _need(not thread.is_alive(), 'NATIVE_STOP_DRAIN_REQUIRED')
                _need(owner._stop_persistence == 'DURABLE'
                      and owner._journal.snapshot()['stopped'] is True, 'NATIVE_STOP_UNKNOWN')
        finally:
            self._phase.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
