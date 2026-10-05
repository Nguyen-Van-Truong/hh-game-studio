"""Trusted phase scheduling for registered inert fixture-release owners.

This is an internal coordinator, not a new IPC capability. Clients first pass
the existing authenticated owner admission. Only that owner advances effects;
scheduler reservations never grant an asset lease or manufacture its ACK.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import threading

from ...protocol.core import Response, Status, canonical_bytes
from ..core.limits import SafetyViolation
from ..core.selector_pipe import SelectorFixtureBroker
from ..core.transport import epoch_ms
from .durable_broker import JobRequest, OwnerResult, Reservation
from .queue_owner import QueueOwner

_BIND = threading.RLock()


class DispatchError(SafetyViolation):
    pass


def _need(value, code):
    if not value:
        raise DispatchError(code)


@dataclass(frozen=True)
class _Binding:
    broker: SelectorFixtureBroker
    activation: object
    command_id: str
    digest: str


class SelectorDispatcher:
    """One trusted local phase pump; control never waits for the pump lock.

    Recovered queued work and reservations have no local authorization binding.
    Neither reserve nor advance reconstructs an expired session or retries them.
    The supervisor must explicitly reconcile them with their original owner.
    """
    def __init__(self, queue: QueueOwner):
        _need(type(queue) is QueueOwner and queue.broker is not None, 'DISPATCH_QUEUE_OWNER_REQUIRED')
        self.queue = queue
        self._owners = {}
        self._bindings = {}
        self._issued = {}
        self._phase = threading.Lock()
        self._stop = threading.Event()
        self._closed = False
        with queue._lifecycle:
            _need(queue._dispatcher is None, 'DISPATCH_QUEUE_ALREADY_BOUND')
            queue._dispatcher = self

    def register(self, broker: SelectorFixtureBroker):
        _need(type(broker) is SelectorFixtureBroker and broker._managed_owner is not None,
              'DISPATCH_REGISTERED_OWNER_REQUIRED')
        owner = broker._managed_owner
        with _BIND, owner._lifecycle_lock:
            _need(not self._closed and not self._stop.is_set(), 'DISPATCH_STOPPED')
            broker._check_open()
            broker._check_registration()
            _need(broker.project_id not in self._owners and owner._service is None
                  and broker._service_owner is None, 'DISPATCH_OWNER_ALREADY_BOUND')
            # Same markers exclude an independent ManagedPipeService pump and
            # prevent owner.close() while this coordinator can still use it.
            owner._service = broker._service_owner = self
            self._owners[broker.project_id] = broker

    def enqueue(self, broker: SelectorFixtureBroker, command_id: str, *, dependencies=()):
        with _BIND:
            _need(not self._closed and not self._stop.is_set(), 'DISPATCH_STOPPED')
            _need(type(broker) is SelectorFixtureBroker
                  and self._owners.get(broker.project_id) is broker
                  and broker._service_owner is self, 'DISPATCH_REGISTERED_OWNER_REQUIRED')
            # Serialize against the existing authenticated admission. Resources
            # are host-resolved native file identities, never client paths.
            with broker._admission, broker.selector._mutex:
                broker._check_registration()
                current = broker.selector.lookup(command_id)
                with broker._state_lock:
                    activation = broker._job
                _need(activation is not None and activation.command_id == command_id
                      and current is not None and 'code' not in current
                      and current['phase'] == 'INTENT', 'DISPATCH_ADMITTED_INTENT_REQUIRED')
                broker._scope(activation.session, 'fixture.write')
                _need(not broker._hold.is_set(), 'DISPATCH_OWNER_HELD')
                request = broker.selector._state['request']
                identity = broker._managed_owner.files.root_identity
                job_id = 'owner-' + hashlib.sha256(canonical_bytes([broker.project_id, command_id])).hexdigest()
                digest = current['digest']
                _need(type(digest) is str and digest.startswith('sha256:') and len(digest) == 71,
                      'DISPATCH_COMMAND_DIGEST_INVALID')
                body = JobRequest(job_id, broker.project_id, activation.session.credential.session_id,
                                  request['deadline_ms'], (f'files:{identity.volume}:{identity.file_id}',),
                                  dependencies, digest[7:])
                binding = _Binding(broker, activation, command_id, digest)
                existing = self.queue.broker.lookup(job_id)
                if existing is not None:
                    _need(self._bindings.get(job_id) == binding
                          and existing.command_sha256 == body.command_sha256
                          and existing.job.dependencies == dependencies,
                          'DISPATCH_EXISTING_RECONCILE_REQUIRED')
                    return existing
                row = self.queue.broker.enqueue(body, now_ms=epoch_ms())
                self._bindings[job_id] = binding
                return row

    def reserve(self):
        with _BIND:
            _need(not self._closed, 'DISPATCH_CLOSED')
            if self._stop.is_set():
                return None
            snapshot = self.queue.broker.snapshot()
            _need(all(job.job_id in self._bindings for job in snapshot.pending),
                  'DISPATCH_RECOVERY_REQUIRED')
            reservation = self.queue.broker.reserve_next(now_ms=epoch_ms())
            if reservation is not None:
                self._issued[reservation.job.job_id] = reservation
            return reservation

    def advance(self, reservation: Reservation):
        _need(type(reservation) is Reservation, 'DISPATCH_RESERVATION_REQUIRED')
        if not self._phase.acquire(blocking=False):
            raise DispatchError('DISPATCH_PHASE_BUSY')
        try:
            with _BIND:
                _need(not self._closed and not self._stop.is_set(), 'DISPATCH_STOPPED')
                _need(not reservation.recovered
                      and self._issued.get(reservation.job.job_id) == reservation,
                      'DISPATCH_RECOVERY_REQUIRED')
                binding = self._bindings[reservation.job.job_id]
                broker = binding.broker
            # Serialize the phase AND its queue receipt with owner admission.
            # Otherwise a fresh command can replace _job after COMMITTED but
            # before collection. Control Stop/cancel uses neither this lock nor
            # our pump lock, so it remains able to fence the next effect.
            with broker._admission:
                try:
                    _need(not self._stop.is_set(), 'DISPATCH_STOPPED')
                    with broker._state_lock:
                        _need(broker._job is binding.activation, 'DISPATCH_OWNER_JOB_CHANGED')
                    _need(broker._service_owner is self, 'DISPATCH_OWNER_BINDING_CHANGED')
                    broker.selector.lookup(binding.command_id, binding.digest)
                    response = broker.advance()
                    self._collect(reservation, binding, response)
                    return response
                except BaseException:
                    # Hold before releasing admission; never poison a new
                    # activation that won an unrelated race after this failure.
                    broker._hold.set()
                    raise
        finally:
            self._phase.release()

    def _collect(self, reservation, binding, response):
        if type(response) is not Response or response.status not in {Status.COMMITTED, Status.CANCELED, Status.REJECTED}:
            return  # SELECTED/UNKNOWN is not completion; keep ownership.
        broker = binding.broker
        # Caller holds owner admission through phase + durable collection.
        with broker.selector._mutex:
            broker._check_registration()
            actual = broker.selector.lookup(binding.command_id, binding.digest)
            _need(actual == response.as_dict() and response.command_id == binding.command_id,
                  'DISPATCH_OWNER_RECEIPT_MISMATCH')
            if response.status is Status.COMMITTED:
                state = broker.selector.snapshot()  # Includes actual native readback.
                _need(state['ready'] and state['pending_command'] is None
                      and state['selection_hash'] == response.postconditions['selection_hash'],
                      'DISPATCH_OWNER_READBACK_REQUIRED')
            # Registered selector phases are synchronous in this exclusive
            # pump. The returned phase owns no external worker/process tree.
            _need(not broker._pump.locked(), 'DISPATCH_OWNER_PHASE_ACTIVE')
            with broker._state_lock:
                # advance() may already clear the old activation after a
                # control-channel cancellation produced this terminal receipt.
                # A different activation is never ours to retire.
                _need(broker._job is None or broker._job is binding.activation,
                      'DISPATCH_OWNER_JOB_CHANGED')
                result = OwnerResult(response.status.value, reservation.command_sha256,
                                     hashlib.sha256(canonical_bytes(actual)).hexdigest())
                self.queue.broker.record_owner_result(reservation, result)
                broker._job = None
            self._issued.pop(reservation.job.job_id, None)

    def stop(self):
        self._stop.set()  # Immediate control fence before any storage wait.
        with _BIND:
            _need(not self._closed, 'DISPATCH_CLOSED')
            owners = tuple(self._owners.values())
            for broker in owners:
                broker._hold.set()
                broker.selector._stop_requested.set()
        snapshot = self.queue.broker.stop()
        for broker in owners:
            broker.selector.stop()
        return snapshot

    def reconcile_terminal(self, reservation, broker, command_id):
        """Explicit trusted lookup after restart; never executes an owner phase.

        A pending/missing owner receipt stays held. A committed historical
        selection superseded by a newer edit also needs separate reconciliation;
        this method must not roll back it or infer readback from the old receipt.
        """
        _need(type(reservation) is Reservation and type(command_id) is str,
              'DISPATCH_RESERVATION_REQUIRED')
        if not self._phase.acquire(blocking=False):
            raise DispatchError('DISPATCH_PHASE_BUSY')
        try:
            with _BIND:
                _need(not self._closed and type(broker) is SelectorFixtureBroker
                      and self._owners.get(broker.project_id) is broker
                      and broker._service_owner is self, 'DISPATCH_REGISTERED_OWNER_REQUIRED')
            expected_id = 'owner-' + hashlib.sha256(canonical_bytes([broker.project_id, command_id])).hexdigest()
            identity = broker._managed_owner.files.root_identity
            _need(reservation.job.job_id == expected_id and reservation.job.project_id == broker.project_id
                  and reservation.job.resources == (f'files:{identity.volume}:{identity.file_id}',),
                  'DISPATCH_RECOVERY_BINDING_MISMATCH')
            with broker._admission:
                broker._check_registration()
                _need(not broker._pump.locked(), 'DISPATCH_OWNER_PHASE_ACTIVE')
                with broker._state_lock:
                    _need(broker._job is None, 'DISPATCH_OWNER_PHASE_ACTIVE')
                with broker.selector._mutex:
                    actual = broker.selector.lookup(command_id, 'sha256:' + reservation.command_sha256)
                    _need(actual is not None and 'code' in actual
                          and actual['status'] in {'COMMITTED', 'REJECTED', 'CANCELED'},
                          'DISPATCH_TERMINAL_OWNER_PROOF_REQUIRED')
                    response = Response.from_dict(actual)
                    _need(response.command_id == command_id, 'DISPATCH_OWNER_RECEIPT_MISMATCH')
                    state = broker.selector.snapshot()
                    _need(state['pending_command'] is None, 'DISPATCH_OWNER_PHASE_ACTIVE')
                    if response.status is Status.COMMITTED:
                        _need(state['ready'] and state['selection_hash'] == response.postconditions['selection_hash'],
                              'DISPATCH_OWNER_READBACK_REQUIRED')
                    return self.queue.broker.record_owner_result(reservation, OwnerResult(
                        response.status.value, reservation.command_sha256,
                        hashlib.sha256(canonical_bytes(actual)).hexdigest()))
        finally:
            self._phase.release()

    def close(self):
        self._stop.set()
        if not self._phase.acquire(blocking=False):
            raise DispatchError('DISPATCH_PHASE_BUSY')
        try:
            with _BIND, self.queue._lifecycle:
                for broker in self._owners.values():
                    with broker._managed_owner._lifecycle_lock:
                        broker._hold.set()
                        if broker._service_owner is self:
                            broker._service_owner = None
                        if broker._managed_owner._service is self:
                            broker._managed_owner._service = None
                self._closed = True
                if self.queue._dispatcher is self:
                    self.queue._dispatcher = None
        finally:
            self._phase.release()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
