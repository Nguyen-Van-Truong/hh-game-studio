"""Volatile FIFO admission over one exact registered PublicationSession.

The owner must retain this wrapper and route EVERY writer lease acquisition
through it. This module does not replace or monkeypatch the session's lease
method. Read leases, effect admission, durable commands and recovery stay with
their existing owners. Tickets/grants are intentionally not restored on restart.

enqueue/poll are nonblocking: a poll may issue one lease for the earliest live
waiter. No renewal bypass exists. A terminal ticket is immutable, including an
expired historical GRANTED receipt. Use granted_lease to obtain the actual
registered object; detached ticket dictionaries never authorize an effect.

Cancellation/Stop during GRANTING returns an immutable terminal with uncertain
grant outcome. A possibly minted unused native lease is left to expire (or be
revoked by its session); it is never returned or silently reissued. Loss of the
native lease return similarly becomes UNKNOWN. Cancel after GRANTED returns the
historical grant; it cannot pretend that an already issued lease was revoked.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib.util
from pathlib import Path
import secrets
import sys
import threading
import weakref

from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes, parse_json

HERE = Path(__file__).resolve().parent
MAX_WAITERS = 8
MAX_TICKETS = 64
MAX_WAIT_MS = 90_000
RETRY_AFTER_MS = 25
_OWNERS = weakref.WeakKeyDictionary()
_OWNERS_LOCK = threading.Lock()
_PENDING = frozenset({'QUEUED', 'GRANTING'})
_BUSY = frozenset({'GODOT_LEASE_BUSY', 'GODOT_EFFECT_DRAIN_REQUIRED'})


class PublicationFifoError(SafetyViolation):
    pass


def _need(value, code):
    if not value:
        raise PublicationFifoError(code)


def _session_module():
    # Match publication_owner._load exactly, without eagerly importing owner.
    # The class is fixed; arbitrary dynamically supplied classes are not accepted.
    path = HERE / 'publication_session.py'
    raw = path.read_bytes()
    key = '_hh_publication_owner_' + hashlib.sha256(str(path).encode() + b'\0' + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


session_model = _session_module()


class PublicationFifo:
    """One volatile queue per session owner; eight waiters, 64 lifetime tickets."""
    def __init__(self, sessions):
        _need(type(sessions) is session_model.PublicationSession, 'GODOT_FIFO_REGISTERED_SESSION_REQUIRED')
        self._model = session_model
        self._sessions = sessions
        self._lock = threading.RLock()
        self._rows = {}
        self._requests = {}
        self._queue = []
        self._granting = None
        self._stopped = False
        with _OWNERS_LOCK:
            previous = _OWNERS.get(sessions)
            _need(previous is None or previous() is None, 'GODOT_FIFO_OWNER_ALREADY_REGISTERED')
            _OWNERS[sessions] = weakref.ref(self)

    def _grant(self, grant):
        # Native authentication validates object identity, immutable grant bytes,
        # original credential registration, current expiry and revocation.
        with self._sessions._mutex:
            self._sessions._check_access(grant, self._model.WRITE_OPERATIONS)

    def _row(self, grant, ticket_id):
        _need(type(ticket_id) is str, 'GODOT_FIFO_INVALID_TICKET')
        row = self._rows.get(ticket_id)
        _need(row is not None and row['grant'] is grant, 'GODOT_FIFO_TICKET_NOT_OWNED')
        return row

    def _result(self, row):
        if row['terminal'] is not None:
            return parse_json(row['terminal'])
        return {**row['base'], 'state': row['state'], 'code': 'GODOT_FIFO_' + row['state'],
                'lease': None, 'grant_outcome': 'PENDING', 'retry_after_ms': RETRY_AFTER_MS}

    def _finish(self, row, state, code, *, lease=None, uncertain=False):
        if row['terminal'] is not None:
            return
        row['state'] = state
        row['lease'] = lease
        row['terminal'] = canonical_bytes({**row['base'], 'state': state, 'code': code,
            'lease': asdict(lease) if lease is not None else None,
            'grant_outcome': 'UNKNOWN' if uncertain else 'ISSUED' if lease is not None else 'NOT_ISSUED',
            'retry_after_ms': None})

    def _sweep(self):
        now = self._model.epoch_ms()
        stopped = self._stopped or self._sessions.status()['stopped'] or self._sessions.status()['held']
        if stopped:
            self._stopped = True
        for ticket in self._queue:
            row = self._rows[ticket]
            if row['state'] not in _PENDING:
                continue
            uncertain = row['state'] == 'GRANTING'
            if stopped:
                self._finish(row, 'STOPPED', 'GODOT_FIFO_STOPPED', uncertain=uncertain)
            elif now >= row['base']['wait_deadline_ms']:
                self._finish(row, 'EXPIRED', 'GODOT_FIFO_WAIT_EXPIRED', uncertain=uncertain)
            else:
                try:
                    self._grant(row['grant'])
                except SafetyViolation:
                    self._finish(row, 'REJECTED', 'GODOT_FIFO_GRANT_INVALID', uncertain=uncertain)
        self._queue[:] = [ticket for ticket in self._queue if self._rows[ticket]['state'] in _PENDING]

    def _pump(self):
        with self._lock:
            self._sweep()
            if self._stopped or self._granting is not None or not self._queue:
                return
            ticket = self._queue[0]
            row = self._rows[ticket]
            row['state'] = 'GRANTING'
            self._granting = ticket
        lease = None
        error = None
        try:
            # PublicationSession.lease authenticates again under its own mutex
            # immediately before minting, and refuses active writer/effect bypass.
            lease = self._sessions.lease(row['grant'], ttl_ms=row['base']['ttl_ms'])
            with self._sessions._mutex:
                _need(type(lease) is self._model.GodotLease and self._sessions._lease is lease
                      and self._sessions._lease_bytes == canonical_bytes(asdict(lease))
                      and lease.session_id == row['grant'].session_id,
                      'GODOT_FIFO_UNREGISTERED_LEASE_RETURN')
        except BaseException as exc:
            error = exc
        with self._lock:
            self._granting = None
            # Concurrent cancellation/Stop already sealed its terminal response.
            if row['terminal'] is None:
                now = self._model.epoch_ms()
                if self._stopped or self._sessions.status()['stopped'] or self._sessions.status()['held']:
                    self._finish(row, 'STOPPED', 'GODOT_FIFO_STOPPED', uncertain=lease is not None or error is not None)
                elif now >= row['base']['wait_deadline_ms']:
                    self._finish(row, 'EXPIRED', 'GODOT_FIFO_WAIT_EXPIRED', uncertain=lease is not None or error is not None)
                elif error is None:
                    # A revocation after minting must not publish an unusable grant.
                    try:
                        self._grant(row['grant'])
                        self._sessions.check(row['grant'], lease,
                            deadline_ms=lease.expires_ms, operation=self._operation(row['grant']))
                    except SafetyViolation:
                        self._finish(row, 'REJECTED', 'GODOT_FIFO_GRANT_INVALID', uncertain=True)
                    else:
                        self._finish(row, 'GRANTED', 'GODOT_FIFO_GRANTED', lease=lease)
                elif isinstance(error, self._model.PublicationSessionError) and str(error) in _BUSY:
                    row['state'] = 'QUEUED'
                elif isinstance(error, self._model.PublicationSessionError):
                    self._finish(row, 'REJECTED', 'GODOT_FIFO_GRANT_INVALID')
                else:
                    self._finish(row, 'UNKNOWN', 'GODOT_FIFO_GRANT_UNKNOWN', uncertain=True)
            self._queue[:] = [key for key in self._queue if self._rows[key]['state'] in _PENDING]
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            raise error

    def _operation(self, grant):
        return sorted(set(grant.operations) & self._model.WRITE_OPERATIONS)[0]

    def enqueue(self, grant, *, request_id, ttl_ms=90_000, wait_ms=30_000):
        self._grant(grant)
        self._sessions.validate_public_identifier(request_id)
        _need(type(ttl_ms) is int and 0 < ttl_ms <= self._model.MAX_SAVE_MS
              and type(wait_ms) is int and 0 < wait_ms <= MAX_WAIT_MS, 'GODOT_FIFO_INVALID_LIMIT')
        with self._lock:
            self._sweep()
            previous = self._requests.get(request_id)
            if previous is not None:
                row = self._row(grant, previous)
                _need(row['base']['ttl_ms'] == ttl_ms and row['wait_ms'] == wait_ms, 'GODOT_FIFO_REQUEST_CONFLICT')
                return self._result(row)
            _need(not self._stopped, 'GODOT_FIFO_STOPPED')
            _need(len(self._queue) < MAX_WAITERS, 'GODOT_FIFO_QUEUE_FULL')
            _need(len(self._rows) < MAX_TICKETS, 'GODOT_FIFO_TICKET_LIMIT')
            _need(not any(self._rows[t]['grant'] is grant for t in self._queue), 'GODOT_FIFO_WAITER_ALREADY_OWNED')
            now = self._model.epoch_ms()
            ticket = 'ticket.' + secrets.token_hex(16)
            row = {'base': {'schema': 'hh-godot-fifo-ticket-1', 'ticket_id': ticket, 'request_id': request_id,
                           'project_id': self._sessions.project_id, 'session_id': grant.session_id,
                           'enqueued_ms': now, 'wait_deadline_ms': now + wait_ms, 'ttl_ms': ttl_ms,
                           'volatile': True, 'restart_replay': False},
                   'wait_ms': wait_ms, 'grant': grant, 'state': 'QUEUED', 'lease': None, 'terminal': None}
            self._requests[request_id] = ticket
            self._rows[ticket] = row
            self._queue.append(ticket)
        self._pump()
        with self._lock:
            return self._result(row)

    def poll(self, grant, ticket_id):
        self._grant(grant)
        with self._lock:
            row = self._row(grant, ticket_id)
            if row['terminal'] is not None:
                return self._result(row)
        self._pump()
        with self._lock:
            return self._result(row)

    def cancel(self, grant, ticket_id):
        self._grant(grant)
        with self._lock:
            self._sweep()
            row = self._row(grant, ticket_id)
            self._finish(row, 'CANCELED', 'GODOT_FIFO_CANCELED', uncertain=row['state'] == 'GRANTING')
            self._queue[:] = [key for key in self._queue if self._rows[key]['state'] in _PENDING]
            return self._result(row)

    def granted_lease(self, grant, ticket_id):
        self._grant(grant)
        with self._lock:
            row = self._row(grant, ticket_id)
            _need(row['state'] == 'GRANTED' and row['lease'] is not None, 'GODOT_FIFO_NOT_GRANTED')
            lease = row['lease']
            _need(asdict(lease) == parse_json(row['terminal'])['lease'], 'GODOT_FIFO_LEASE_CHANGED')
        self._sessions.check(grant, lease, deadline_ms=lease.expires_ms, operation=self._operation(grant))
        return lease

    def stop(self, grant):
        # Control latch precedes queue work; no scene/command lock is involved.
        result = self._sessions.stop(grant)
        with self._lock:
            self._stopped = True
            self._sweep()
        return result

    def halt(self):
        """Trusted local owner shutdown; no new grants after this latch."""
        self._sessions.halt()
        with self._lock:
            self._stopped = True
            self._sweep()

    def snapshot(self):
        """Trusted local status only; wire callers must use owned ticket routes."""
        with self._lock:
            self._sweep()
            return {'stopped': self._stopped, 'queued': len(self._queue), 'retained': len(self._rows),
                    'granting': self._granting is not None, 'max_waiters': MAX_WAITERS,
                    'max_tickets': MAX_TICKETS, 'max_wait_ms': MAX_WAIT_MS,
                    'volatile': True, 'restart_replay': False}
