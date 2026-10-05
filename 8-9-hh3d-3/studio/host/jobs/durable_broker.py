"""GT07 durable admission/reservation, for one trusted local coordinator.

The caller supplies a dedicated, custody-bound PrivateEventLog and continues to
own its lifetime. No path, callable, process, payload or wire receipt is accepted
here. Admission and reservation acknowledge storage only. COMMITTED is copied
only from an OwnerResult whose registered command owner the integration has
already checked, including postcondition and release of its active phase.

One event atomically records selection, resource ownership and fairness cursor.
A restarted reservation is uncertain and stays occupied; it is never reissued.
There is deliberately no automatic retry, resume, lease-expiry release, journal
compaction or gameplay/publish authority in this slice.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
import hashlib
import re
import threading
import time
from typing import Iterator

from ..core.custody import WitnessCustody
from ..core.limits import SafetyViolation, canonical_json, parse_json_utf8
from ..core.private_events import (EventHead, EventLogError, MAX_EVENT_BYTES,
                                   MAX_LOG_BYTES, MAX_RECORDS, PrivateEventLog)
from .dispatch_policy import (ActiveJob, Cursor, DispatchPolicyError, PendingJob,
                              QueueLimits, _identifier, _integer, select_next)
from .segmented_journal import SEGMENT_SCHEMA, QueueJournalManager

_SCHEMA = 'hh-durable-dispatch-1'
_TERMINAL = frozenset({'COMMITTED', 'REJECTED', 'CANCELED'})
_OWNERS: dict[int, DurableBroker] = {}
_OWNERS_LOCK = threading.Lock()


class BrokerError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        self.next_action = ('Stop admission; preserve the journal and reconcile with its registered owner.'
                            if outcome_unknown else 'Inspect the queue or supply a corrected trusted request.')
        if code == 'BROKER_JOURNAL_FULL':
            self.next_action = 'Stop new admission; drain/reconcile existing jobs. Journal rotation is not implemented.'
        super().__init__(code)


@dataclass(frozen=True)
class JobRequest:
    job_id: str
    project_id: str
    session_id: str
    deadline_ms: int
    resources: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    command_sha256: str = ''


@dataclass(frozen=True)
class Fence:
    stream_id: str
    generation: int


@dataclass(frozen=True)
class Reservation:
    job: PendingJob
    command_sha256: str
    fence: Fence
    recovered: bool = False


@dataclass(frozen=True)
class OwnerResult:
    """Trusted integration only: verified owner lookup, never caller assertions.

    A terminal result additionally asserts the owner has no active phase and has
    released this reservation's resources. UNKNOWN asserts neither and retains
    ownership. The digest identifies the verified receipt, not an inferred ACK.
    """
    outcome: str
    command_sha256: str
    receipt_sha256: str
    completed_at_ms: int | None = None


@dataclass(frozen=True)
class JobRecord:
    job: PendingJob
    command_sha256: str
    state: str
    fence: Fence | None = None
    receipt_sha256: str | None = None


@dataclass(frozen=True)
class BrokerSnapshot:
    pending: tuple[PendingJob, ...]
    reservations: tuple[Reservation, ...]
    receipts: tuple[JobRecord, ...]
    cursor: Cursor
    stopped: bool
    head: EventHead


@dataclass
class _Projection:
    records: dict[str, JobRecord] = field(default_factory=dict)
    cursor: Cursor = Cursor()
    stopped: bool = False
    sequence: int = 0
    generation: int = 0
    now_ms: int = 0
    configured: bool = False
    terminal_ms: dict[str, int] = field(default_factory=dict)
    checkpoint_meta: dict | None = None
    checkpoint_rows: dict[int, dict] = field(default_factory=dict)


def _need(condition: bool, code: str = 'BROKER_HISTORY_INVALID') -> None:
    if not condition:
        raise BrokerError(code)


def _digest(value: object) -> bool:
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _shape(value: object, keys: tuple[str, ...]) -> None:
    _need(type(value) is dict and set(value) == set(keys))


class DurableBroker:
    """One broker writer, one native writer guard, one bounded coherent state.

    Only the exact custody-bound storage primitive is accepted. The supervisor
    must provision/reopen that dedicated log through its existing protected
    custody route; this class never provisions a filesystem or recovery anchor.
    """
    def __init__(self, events: PrivateEventLog, *, limits: QueueLimits = QueueLimits()) -> None:
        _need(type(events) is PrivateEventLog, 'BROKER_TRUSTED_LOG_REQUIRED')
        self._validate_policy(_Projection(), limits, 0)
        self._events, self.limits = events, limits
        self._journal = None
        self._mutex = threading.Lock()
        self._closed = self._poisoned = self._stop_requested = False
        self._recovered: set[str] = set()
        with _OWNERS_LOCK:
            _need(id(events) not in _OWNERS, 'BROKER_ALREADY_OWNED')
            _OWNERS[id(events)] = self
        try:
            self._custody = getattr(events, '_custody', None)
            _need(type(self._custody) is WitnessCustody, 'BROKER_CUSTODY_REQUIRED')
            self._custody.confirm_current()
            binding = events.binding()
            _need(self._custody.binding.witnessed == binding.witnessed,
                  'BROKER_CUSTODY_MISMATCH')
            # Physical segment identities rotate. Fences use the immutable
            # custody storage ID so an old reservation remains comparable.
            self._stream_id = f'queue:{self._custody._registry.local_id}'
            self._head, self._state = events.fold(_Projection(), self._fold)
            self._recovered = {key for key, row in self._state.records.items()
                               if row.state in {'RESERVED', 'UNKNOWN'}}
            if not self._state.configured:
                self._append({'kind': 'CONFIG', 'limits': asdict(limits)})
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _validate_policy(state: _Projection, limits: QueueLimits, now_ms: int):
        pending = tuple(row.job for row in state.records.values() if row.state == 'QUEUED')
        active = tuple(ActiveJob(row.job.job_id, row.job.project_id, row.job.session_id,
                                 row.job.resources) for row in state.records.values()
                       if row.state in {'RESERVED', 'UNKNOWN'})
        receipts = {key: row.state for key, row in state.records.items() if row.state in _TERMINAL}
        try:
            return select_next(pending=pending, active=active, receipts=receipts,
                               cursor=state.cursor, now_ms=now_ms,
                               stopped=state.stopped, limits=limits)
        except DispatchPolicyError as exc:
            raise BrokerError(str(exc)) from None

    @contextmanager
    def _locked(self) -> Iterator[None]:
        if not self._mutex.acquire(timeout=2):
            raise BrokerError('BROKER_BUSY')
        try:
            _need(not self._closed, 'BROKER_CLOSED')
            if self._poisoned:
                raise BrokerError('BROKER_RECOVERY_REQUIRED', outcome_unknown=True)
            self._check_head()
            yield
        finally:
            self._mutex.release()

    def _check_head(self) -> None:
        try:
            self._custody.confirm_current()
            binding = self._events.binding()
            _need(binding.witnessed == self._head
                  and self._custody.binding.witnessed == self._head,
                  'BROKER_HEAD_CHANGED')
        except BaseException as exc:
            self._poisoned = True
            raise BrokerError('BROKER_RECOVERY_REQUIRED', outcome_unknown=True) from exc

    def _fold(self, state: _Projection, record) -> _Projection:
        event = parse_json_utf8(record.event)
        if record.head.sequence == 1:
            _need(event.get('kind') == 'GENESIS')
            return state
        return self._apply(state, event)

    def _apply(self, previous: _Projection, event: dict) -> _Projection:
        _need(type(event) is dict)
        if event.get('schema') == SEGMENT_SCHEMA:
            return self._apply_checkpoint(previous, event)
        _need(event.get('schema') == _SCHEMA)
        kind = event.get('kind')
        state = replace(previous, records=dict(previous.records),
                        terminal_ms=dict(previous.terminal_ms))
        if kind == 'CONFIG':
            _shape(event, ('schema', 'kind', 'limits'))
            _need(not state.configured and type(event['limits']) is dict
                  and all(type(v) is int for v in event['limits'].values())
                  and event['limits'] == asdict(self.limits), 'BROKER_PROFILE_MISMATCH')
            state.configured = True
            return state
        _need(state.configured, 'BROKER_CONFIG_REQUIRED')
        if kind == 'ENQUEUE':
            _shape(event, ('schema', 'kind', 'job', 'command_sha256', 'now_ms'))
            _shape(event['job'], tuple(PendingJob.__dataclass_fields__))
            data = dict(event['job'])
            _need(type(data['resources']) is list and type(data['dependencies']) is list)
            data['resources'], data['dependencies'] = tuple(data['resources']), tuple(data['dependencies'])
            job = PendingJob(**data)
            _need(all(_identifier(value) for value in (job.job_id, job.project_id, job.session_id)),
                  'BROKER_JOB_INVALID')
            _need(_integer(event['now_ms']) and event['now_ms'] >= state.now_ms,
                  'BROKER_CLOCK_INVALID')
            _need(not state.stopped, 'BROKER_STOPPED')
            _need(job.job_id not in state.records, 'BROKER_ID_CONFLICT')
            _need(_digest(event['command_sha256']), 'BROKER_COMMAND_INVALID')
            _need(type(job.sequence) is int and job.sequence == state.sequence + 1,
                  'BROKER_SEQUENCE_INVALID')
            _need(_integer(job.deadline_ms) and job.deadline_ms > event['now_ms'],
                  'BROKER_DEADLINE_INVALID')
            # Only prior admitted IDs may be prerequisites. With no graph edits
            # or forward references, a dependency cycle cannot be introduced.
            _need(all(type(dep) is str and dep in state.records for dep in job.dependencies),
                  'BROKER_DEPENDENCY_INVALID')
            _need(len(state.records) < self.limits.receipts, 'BROKER_TOMBSTONE_CAPACITY')
            state.records[job.job_id] = JobRecord(job, event['command_sha256'], 'QUEUED')
            state.sequence, state.now_ms = job.sequence, event['now_ms']
        elif kind == 'RESERVE':
            _shape(event, ('schema', 'kind', 'now_ms', 'job_id', 'generation', 'cursor'))
            _need(not state.stopped, 'BROKER_STOPPED')
            _need(_integer(event['now_ms']) and event['now_ms'] >= state.now_ms,
                  'BROKER_CLOCK_INVALID')
            state = self._expire_pending(state, event['now_ms'])
            chosen = self._validate_policy(state, self.limits, state.now_ms)
            _need(event['job_id'] == (chosen.job_id if chosen else None), 'BROKER_SELECTION_INVALID')
            cursor = chosen.next_cursor if chosen else state.cursor
            _need(event['cursor'] == self._cursor_value(cursor), 'BROKER_CURSOR_INVALID')
            if chosen:
                _need(type(event['generation']) is int and event['generation'] == state.generation + 1,
                      'BROKER_FENCE_INVALID')
                row = state.records[chosen.job_id]
                state.generation += 1
                state.records[chosen.job_id] = replace(row, state='RESERVED',
                                                       fence=Fence(self._stream_id, state.generation))
                state.cursor = cursor
            else:
                _need(event['generation'] is None)
        elif kind == 'OWNER_RESULT':
            old_keys = ('schema', 'kind', 'job_id', 'fence', 'outcome',
                        'command_sha256', 'receipt_sha256')
            new_keys = old_keys + ('terminal_ms', 'expires_ms')
            _need(set(event) in (set(old_keys), set(new_keys)), 'BROKER_RESULT_INVALID')
            _need(type(event['job_id']) is str and event['job_id'] in state.records,
                  'BROKER_JOB_UNKNOWN')
            row = state.records[event['job_id']]
            _need(row.state in {'RESERVED', 'UNKNOWN'} and row.fence is not None,
                  'BROKER_NOT_RESERVED')
            _need(event['fence'] == asdict(row.fence)
                  and type(event['fence']) is dict
                  and type(event['fence'].get('generation')) is int, 'BROKER_FENCE_INVALID')
            _need(type(event['outcome']) is str and event['outcome'] in _TERMINAL | {'UNKNOWN'},
                  'BROKER_RESULT_INVALID')
            _need(event['command_sha256'] == row.command_sha256
                  and _digest(event['receipt_sha256']), 'BROKER_RESULT_INVALID')
            state.records[row.job.job_id] = replace(row, state=event['outcome'],
                                                    receipt_sha256=event['receipt_sha256'])
            if event['outcome'] in _TERMINAL:
                if 'terminal_ms' in event:
                    _need(_integer(event['terminal_ms']) and _integer(event['expires_ms'])
                          and event['expires_ms'] >= event['terminal_ms'], 'BROKER_RESULT_INVALID')
                    state.terminal_ms[row.job.job_id] = event['terminal_ms']
        elif kind == 'STOP':
            _shape(event, ('schema', 'kind'))
            _need(not state.stopped, 'BROKER_STOPPED')
            state.stopped = True
            state.records = {key: replace(row, state='CANCELED') if row.state == 'QUEUED' else row
                             for key, row in state.records.items()}
        else:
            raise BrokerError('BROKER_EVENT_INVALID')
        self._validate_policy(state, self.limits, state.now_ms)
        return state

    @staticmethod
    def _record_value(row: JobRecord, terminal_ms: int | None) -> dict:
        fence = None if row.fence is None else asdict(row.fence)
        job = asdict(row.job)
        # Checkpoint rows cross the canonical JSON boundary; dataclass tuples
        # must be represented as JSON arrays just like the live event schema.
        job['resources'] = list(row.job.resources)
        job['dependencies'] = list(row.job.dependencies)
        return {'job': job, 'command_sha256': row.command_sha256,
                'state': row.state, 'fence': fence, 'receipt_sha256': row.receipt_sha256,
                'terminal_ms': terminal_ms}

    def _record_from(self, value: dict) -> tuple[str, JobRecord, int | None]:
        _need(type(value) is dict and set(value) == {'job', 'command_sha256', 'state',
                                                      'fence', 'receipt_sha256', 'terminal_ms'},
              'BROKER_CHECKPOINT_ROW_INVALID')
        _shape(value['job'], tuple(PendingJob.__dataclass_fields__))
        data = dict(value['job'])
        _need(type(data.get('resources')) is list and type(data.get('dependencies')) is list,
              'BROKER_CHECKPOINT_ROW_INVALID')
        _need(len(data['resources']) <= self.limits.resources
              and len(data['dependencies']) <= self.limits.dependencies,
              'BROKER_CHECKPOINT_ROW_INVALID')
        _need(all(_identifier(v) for v in (data['job_id'], data['project_id'], data['session_id'])),
              'BROKER_CHECKPOINT_ROW_INVALID')
        _need(all(_identifier(v) for v in data['resources'])
              and len(set(data['resources'])) == len(data['resources'])
              and data['resources'], 'BROKER_CHECKPOINT_ROW_INVALID')
        _need(all(_identifier(v) for v in data['dependencies'])
              and len(set(data['dependencies'])) == len(data['dependencies']),
              'BROKER_CHECKPOINT_ROW_INVALID')
        data['resources'], data['dependencies'] = tuple(data['resources']), tuple(data['dependencies'])
        try:
            job = PendingJob(**data)
        except (TypeError, ValueError, KeyError):
            raise BrokerError('BROKER_CHECKPOINT_ROW_INVALID') from None
        _need(_integer(job.sequence, 1) and _integer(job.deadline_ms),
              'BROKER_CHECKPOINT_ROW_INVALID')
        fence_value = value['fence']
        if fence_value is None:
            fence = None
        else:
            _shape(fence_value, ('stream_id', 'generation'))
            _need(_identifier(fence_value['stream_id']) and _integer(fence_value['generation']))
            fence = Fence(**fence_value)
        _need(_digest(value['command_sha256']) and value['state'] in {'QUEUED', 'RESERVED',
              'UNKNOWN', 'COMMITTED', 'REJECTED', 'CANCELED'}, 'BROKER_CHECKPOINT_ROW_INVALID')
        _need(value['receipt_sha256'] is None or _digest(value['receipt_sha256']),
              'BROKER_CHECKPOINT_ROW_INVALID')
        terminal = value['terminal_ms']
        _need(terminal is None or _integer(terminal), 'BROKER_CHECKPOINT_ROW_INVALID')
        state = value['state']
        if state in {'RESERVED', 'UNKNOWN'}:
            _need(fence is not None and value['receipt_sha256'] is None and terminal is None,
                  'BROKER_CHECKPOINT_ROW_INVALID')
        elif state == 'QUEUED':
            _need(fence is None and value['receipt_sha256'] is None and terminal is None,
                  'BROKER_CHECKPOINT_ROW_INVALID')
        elif state == 'COMMITTED':
            _need(value['receipt_sha256'] is not None and fence is not None,
                  'BROKER_CHECKPOINT_ROW_INVALID')
        elif state == 'REJECTED':
            _need(value['receipt_sha256'] is None or _digest(value['receipt_sha256']),
                  'BROKER_CHECKPOINT_ROW_INVALID')
        else:
            _need(state == 'CANCELED' and value['receipt_sha256'] is None,
                  'BROKER_CHECKPOINT_ROW_INVALID')
        return job.job_id, JobRecord(job, value['command_sha256'], value['state'], fence,
                                     value['receipt_sha256']), terminal

    def _apply_checkpoint(self, previous: _Projection, event: dict) -> _Projection:
        kind = event.get('kind')
        state = replace(previous, records=dict(previous.records),
                        terminal_ms=dict(previous.terminal_ms),
                        checkpoint_rows=dict(previous.checkpoint_rows))
        if kind == 'CHECKPOINT_BEGIN':
            _shape(event, ('schema', 'kind', 'generation', 'logical_stream_id',
                           'previous', 'row_count', 'now_ms', 'cursor', 'stopped',
                           'logical_generation'))
            _need(not previous.configured and state.checkpoint_meta is None
                  and _integer(event['generation'], 1) and event['logical_stream_id'] == self._stream_id
                  and type(event['row_count']) is int and 0 <= event['row_count'] <= self.limits.receipts
                  and _integer(event['now_ms']) and type(event['cursor']) is dict
                  and type(event['stopped']) is bool and _integer(event['logical_generation']))
            state.checkpoint_meta = event
            state.checkpoint_rows = {}
            return state
        _need(state.checkpoint_meta is not None and not state.configured,
              'BROKER_CHECKPOINT_ORDER')
        if kind == 'CHECKPOINT_ROW':
            _shape(event, ('schema', 'kind', 'index', 'row'))
            _need(type(event['index']) is int and 0 <= event['index'] < state.checkpoint_meta['row_count']
                  and event['index'] not in state.checkpoint_rows, 'BROKER_CHECKPOINT_ROW_INVALID')
            state.checkpoint_rows[event['index']] = event['row']
            return state
        if kind != 'CHECKPOINT_END':
            raise BrokerError('BROKER_CHECKPOINT_ORDER')
        _shape(event, ('schema', 'kind', 'row_count', 'checkpoint_sha256'))
        meta = state.checkpoint_meta
        _need(event['row_count'] == meta['row_count'] == len(state.checkpoint_rows),
              'BROKER_CHECKPOINT_COUNT')
        digest = hashlib.sha256()
        digest.update(canonical_json(meta))
        records, terminal_ms = {}, {}
        for index in range(event['row_count']):
            row = state.checkpoint_rows[index]
            digest.update(canonical_json(row))
            key, record, terminal = self._record_from(row)
            _need(key not in records, 'BROKER_CHECKPOINT_DUPLICATE')
            records[key] = record
            if terminal is not None:
                terminal_ms[key] = terminal
        _need(_digest(event['checkpoint_sha256'])
              and digest.hexdigest() == event['checkpoint_sha256'], 'BROKER_CHECKPOINT_HASH')
        cursor_value = meta['cursor']
        _shape(cursor_value, ('last_project', 'sessions'))
        _need(cursor_value['last_project'] is None or _identifier(cursor_value['last_project']),
              'BROKER_CHECKPOINT_CURSOR_INVALID')
        _need(type(cursor_value['sessions']) is list and
              all(type(item) is list and len(item) == 2 and
                  _identifier(item[0]) and _identifier(item[1])
                  for item in cursor_value['sessions']),
              'BROKER_CHECKPOINT_CURSOR_INVALID')
        sessions = tuple(tuple(item) for item in cursor_value['sessions'])
        _need(tuple(sorted(sessions)) == sessions and len(set(sessions)) == len(sessions),
              'BROKER_CHECKPOINT_CURSOR_INVALID')
        state = replace(state, records=records, terminal_ms=terminal_ms,
                        cursor=Cursor(cursor_value.get('last_project'), sessions),
                        stopped=meta['stopped'], sequence=max((row.job.sequence for row in records.values()), default=0),
                        generation=meta['logical_generation'], now_ms=meta['now_ms'], configured=True,
                        checkpoint_meta=None, checkpoint_rows={})
        self._validate_policy(state, self.limits, state.now_ms)
        return state

    @staticmethod
    def _cursor_value(cursor: Cursor) -> dict:
        return {'last_project': cursor.last_project, 'sessions': [list(row) for row in cursor.sessions]}

    @staticmethod
    def _expire_pending(state: _Projection, now_ms: int) -> _Projection:
        return replace(state, now_ms=now_ms, records={
            key: replace(row, state='REJECTED')
            if row.state == 'QUEUED' and row.job.deadline_ms <= now_ms else row
            for key, row in state.records.items()})

    def _append(self, event: dict) -> None:
        event = {'schema': _SCHEMA, **event}
        prospective = self._apply(self._state, event)
        pending = sum(row.state == 'QUEUED' for row in prospective.records.values())
        active = sum(row.state in {'RESERVED', 'UNKNOWN'} for row in prospective.records.values())
        # Each queued job can still reserve+finish, each active job can finish,
        # and Stop has its own slot outside all admission/active quotas.
        reserve = 2 * pending + active + int(not prospective.stopped)
        reserved_bytes = reserve * (MAX_EVENT_BYTES + 36)
        if (reserve >= MAX_RECORDS or reserved_bytes > MAX_LOG_BYTES
                or self._head.sequence + 1 + reserve > MAX_RECORDS):
            raise BrokerError('BROKER_JOURNAL_FULL')
        try:
            head = self._events.append(event, self._head,
                                       reserve_records=reserve, reserve_bytes=reserved_bytes)
        except EventLogError as exc:
            if exc.code == 'EVENT_CAPACITY' and not exc.outcome_unknown:
                raise BrokerError('BROKER_JOURNAL_FULL') from exc
            self._poisoned = True
            raise BrokerError('BROKER_PERSIST_UNCERTAIN', outcome_unknown=True) from exc
        except BaseException as exc:
            self._poisoned = True
            raise BrokerError('BROKER_PERSIST_UNCERTAIN', outcome_unknown=True) from exc
        self._state, self._head = prospective, head

    def enqueue(self, request: JobRequest, *, now_ms: int) -> JobRecord:
        _need(type(request) is JobRequest, 'BROKER_REQUEST_INVALID')
        _need(type(request.resources) is tuple and type(request.dependencies) is tuple,
              'BROKER_REQUEST_INVALID')
        with self._locked():
            _need(not self._stop_requested, 'BROKER_STOPPED')
            _need(_digest(request.command_sha256), 'BROKER_COMMAND_INVALID')
            # A compacted terminal row remains an immutable archive tombstone.
            # A duplicate same-id/same-command is a read-only replay of the
            # old result; a changed payload is a durable conflict.
            if self._journal is not None and request.job_id not in self._state.records:
                archived = self._journal.lookup_archived(request.job_id)
                if archived is not None:
                    archived_row, _ = archived
                    _need(archived_row['command_sha256'] == request.command_sha256,
                          'BROKER_ID_CONFLICT')
                    return self._record_from(archived_row)[1]
            job = PendingJob(request.job_id, request.project_id, request.session_id,
                             self._state.sequence + 1, request.deadline_ms,
                             request.resources, request.dependencies)
            data = asdict(job)
            data['resources'], data['dependencies'] = list(job.resources), list(job.dependencies)
            self._append({'kind': 'ENQUEUE', 'job': data,
                          'command_sha256': request.command_sha256, 'now_ms': now_ms})
            return self._state.records[request.job_id]

    def reserve_next(self, *, now_ms: int) -> Reservation | None:
        with self._locked():
            _need(_integer(now_ms) and now_ms >= self._state.now_ms, 'BROKER_CLOCK_INVALID')
            if self._state.stopped or self._stop_requested:
                return None
            # Choose from exactly the state RESERVE will durably project.
            # Expired projects must not leave stale session cursor entries.
            selection_state = self._expire_pending(self._state, now_ms)
            chosen = self._validate_policy(selection_state, self.limits, now_ms)
            expired = any(row.state == 'QUEUED' and row.job.deadline_ms <= now_ms
                          for row in self._state.records.values())
            if not chosen and not expired:
                return None
            self._append({'kind': 'RESERVE', 'now_ms': now_ms,
                          'job_id': chosen.job_id if chosen else None,
                          'generation': self._state.generation + 1 if chosen else None,
                          'cursor': self._cursor_value(chosen.next_cursor if chosen else self._state.cursor)})
            if self._stop_requested:
                return None
            return self._reservation(self._state.records[chosen.job_id]) if chosen else None

    def _reservation(self, row: JobRecord) -> Reservation:
        return Reservation(row.job, row.command_sha256, row.fence,
                           row.job.job_id in self._recovered)

    def record_owner_result(self, reservation: Reservation, result: OwnerResult) -> JobRecord:
        _need(type(reservation) is Reservation and type(result) is OwnerResult,
              'BROKER_TRUSTED_RESULT_REQUIRED')
        _need(type(reservation.fence) is Fence and type(reservation.job) is PendingJob,
              'BROKER_FENCE_INVALID')
        with self._locked():
            row = self._state.records.get(reservation.job.job_id)
            _need(row is not None and row.job == reservation.job
                  and row.command_sha256 == reservation.command_sha256, 'BROKER_RESERVATION_INVALID')
            terminal_ms = result.completed_at_ms
            if terminal_ms is None:
                terminal_ms = time.time_ns() // 1_000_000
            self._append({'kind': 'OWNER_RESULT', 'job_id': row.job.job_id,
                          'fence': asdict(reservation.fence), 'outcome': result.outcome,
                          'command_sha256': result.command_sha256,
                          'receipt_sha256': result.receipt_sha256,
                          'terminal_ms': terminal_ms,
                          'expires_ms': terminal_ms + 24 * 60 * 60 * 1000})
            return self._state.records[row.job.job_id]

    def _checkpoint_rows(self, *, now_ms: int, retry_horizon_ms: int) -> list[dict]:
        _need(_integer(now_ms) and type(retry_horizon_ms) is int and retry_horizon_ms >= 60_000,
              'BROKER_RETENTION_INVALID')
        dependencies = {dep for row in self._state.records.values()
                        if row.state in {'QUEUED', 'RESERVED', 'UNKNOWN'} for dep in row.job.dependencies}
        rows = []
        for key, row in sorted(self._state.records.items(), key=lambda item: item[1].job.sequence):
            terminal = self._state.terminal_ms.get(key)
            keep = row.state not in _TERMINAL or terminal is None \
                or terminal + retry_horizon_ms > now_ms or key in dependencies
            if keep:
                rows.append(self._record_value(row, terminal))
        return rows

    def rotate(self, journal: QueueJournalManager, *, now_ms: int,
               retry_horizon_ms: int | None = None):
        """Quiesced QueueOwner path: checkpoint, rotate, then switch broker log."""
        _need(type(journal) is QueueJournalManager and journal.current is self._events,
              'BROKER_SEGMENT_OWNER_MISMATCH')
        horizon = journal.retry_horizon_ms if retry_horizon_ms is None else retry_horizon_ms
        with self._locked():
            rows = self._checkpoint_rows(now_ms=now_ms, retry_horizon_ms=horizon)
            state = {'now_ms': now_ms, 'cursor': self._cursor_value(self._state.cursor),
                     'stopped': self._state.stopped,
                     'logical_generation': self._state.generation}
            checkpoint = journal.prepare(rows, state, reserve_records=0)
            try:
                # Project the exact checkpoint before any custody barrier. If
                # validation fails, the old stream remains authoritative.
                projected = self._apply_checkpoint(_Projection(), checkpoint.begin)
                for index, row in enumerate(rows):
                    projected = self._apply_checkpoint(projected, {
                        'schema': SEGMENT_SCHEMA, 'kind': 'CHECKPOINT_ROW',
                        'index': index, 'row': row})
                projected = self._apply_checkpoint(projected, {
                    'schema': SEGMENT_SCHEMA, 'kind': 'CHECKPOINT_END',
                    'row_count': len(rows), 'checkpoint_sha256': checkpoint.sha256})
            except BaseException:
                journal.abort_prepared()
                raise
            journal.commit(checkpoint)
            self._state = projected
            self._events = journal.current
            self._head = self._events.binding().witnessed
            self._custody = self._events._custody
            self._recovered = {key for key, row in self._state.records.items()
                               if row.state in {'RESERVED', 'UNKNOWN'}}
            return checkpoint

    def stop(self) -> BrokerSnapshot:
        # Set before waiting for the current synchronous storage operation.
        # A failed barrier is UNKNOWN, never a claim of persisted Stop.
        self._stop_requested = True
        with self._locked():
            if not self._state.stopped:
                self._append({'kind': 'STOP'})
            return self._snapshot()

    def lookup(self, job_id: str) -> JobRecord | None:
        _need(_identifier(job_id), 'BROKER_JOB_INVALID')
        with self._locked():
            row = self._state.records.get(job_id)
            if row is not None or self._journal is None:
                return row
            archived = self._journal.lookup_archived(job_id)
            return None if archived is None else self._record_from(archived[0])[1]

    def _snapshot(self) -> BrokerSnapshot:
        rows = tuple(sorted(self._state.records.values(), key=lambda row: row.job.sequence))
        return BrokerSnapshot(tuple(row.job for row in rows if row.state == 'QUEUED'),
                              tuple(self._reservation(row) for row in rows
                                    if row.state in {'RESERVED', 'UNKNOWN'}),
                              tuple(row for row in rows if row.state in _TERMINAL),
                              self._state.cursor, self._state.stopped, self._head)

    def snapshot(self) -> BrokerSnapshot:
        with self._locked():
            return self._snapshot()

    def close(self) -> None:
        with self._mutex:
            self._closed = True
            with _OWNERS_LOCK:
                if _OWNERS.get(id(self._events)) is self:
                    _OWNERS.pop(id(self._events))

    def __enter__(self) -> DurableBroker:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
