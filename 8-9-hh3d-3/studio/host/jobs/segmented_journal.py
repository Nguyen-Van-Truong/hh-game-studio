"""Private queue segments linked by witnessed descriptors, not file discovery.

Only one bounded segment is projected during archive lookup. Old bytes are
never rewritten or deleted. Pending custody phases require reconciliation.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path

from ..core.custody import WitnessCustody, binding_from, binding_value, _path, _same_binding
from ..core.limits import SafetyViolation, canonical_json, parse_json_utf8
from ..core.private_events import EventHead, PrivateEventLog, MAX_RECORDS, MAX_LOG_BYTES, MAX_EVENT_BYTES
from .dispatch_policy import QueueLimits, _identifier

SEGMENT_SCHEMA = 'hh-queue-segment-1'
DEFAULT_RETRY_HORIZON_MS = 86_400_000

class SegmentError(SafetyViolation):
    def __init__(self, code, *, outcome_unknown=False, cleanup_owner=None):
        self.outcome_unknown, self.cleanup_owner = outcome_unknown, cleanup_owner
        super().__init__(code)

def _need(ok, code='SEGMENT_INVALID'):
    if not ok:
        raise SegmentError(code)

def descriptor_from(value):
    _need(type(value) is dict and set(value) == {'generation', 'path', 'binding'}, 'SEGMENT_DESCRIPTOR_INVALID')
    _need(type(value['generation']) is int and 0 <= value['generation'] <= 1_000_000, 'SEGMENT_GENERATION_INVALID')
    _path(value['path'], 'hh-private-')
    binding_from(value['binding'])
    return value

def checkpoint_digest(begin, rows):
    digest = hashlib.sha256()
    digest.update(canonical_json(begin))
    for value in rows:
        raw = canonical_json(value)
        digest.update(raw)
    return digest.hexdigest()

@dataclass(frozen=True)
class Checkpoint:
    begin: dict
    sha256: str
    head: EventHead

    @property
    def generation(self):
        return self.begin['generation']

    @property
    def logical_stream_id(self):
        return self.begin['logical_stream_id']

def inspect_checkpoint(log):
    """Validate checkpoint prefix without retaining all rows."""
    begin, digest, count, complete = None, hashlib.sha256(), 0, None
    def fold(_, record):
        nonlocal begin, count, complete
        event = parse_json_utf8(record.event)
        if record.head.sequence == 1:
            return None
        if record.head.sequence == 2:
            if event.get('schema') != SEGMENT_SCHEMA:
                return None
            header_keys = {'schema', 'kind', 'generation', 'logical_stream_id', 'previous', 'row_count', 'now_ms', 'cursor', 'stopped', 'logical_generation'}
            optional_keys = {'retry_horizon_ms', 'sequence'}
            _need(set(event) in (header_keys, header_keys | {'retry_horizon_ms'},
                                  header_keys | {'sequence'}, header_keys | optional_keys)
                  and event['kind'] == 'CHECKPOINT_BEGIN', 'SEGMENT_HEADER_INVALID')
            _need(type(event['generation']) is int and event['generation'] > 0
                  and type(event['row_count']) is int and 0 <= event['row_count'] <= MAX_RECORDS - 3
                  and _identifier(event['logical_stream_id']) and type(event['now_ms']) is int
                  and type(event['cursor']) is dict and type(event['stopped']) is bool
                  and type(event['logical_generation']) is int, 'SEGMENT_HEADER_INVALID')
            if 'retry_horizon_ms' in event:
                _need(type(event['retry_horizon_ms']) is int
                      and 60_000 <= event['retry_horizon_ms'] <= DEFAULT_RETRY_HORIZON_MS,
                      'SEGMENT_HORIZON_INVALID')
            if 'sequence' in event:
                _need(type(event['sequence']) is int and 0 <= event['sequence'] <= (1 << 53) - 1,
                      'SEGMENT_SEQUENCE_INVALID')
            previous = descriptor_from(event['previous'])
            _need(previous['generation'] + 1 == event['generation'], 'SEGMENT_CHAIN_INVALID')
            begin = event
            digest.update(canonical_json(begin))
            return None
        if begin is None or complete is not None:
            _need(event.get('schema') != SEGMENT_SCHEMA, 'SEGMENT_CHECKPOINT_ORDER')
            return None
        if count < begin['row_count']:
            _need(set(event) == {'schema', 'kind', 'index', 'row'}
                  and event['schema'] == SEGMENT_SCHEMA and event['kind'] == 'CHECKPOINT_ROW'
                  and type(event['index']) is int and event['index'] == count
                  and type(event['row']) is dict, 'SEGMENT_CHECKPOINT_ORDER')
            raw = canonical_json(event['row'])
            digest.update(raw)
            count += 1
        else:
            _need(set(event) == {'schema', 'kind', 'row_count', 'checkpoint_sha256'}
                  and event['schema'] == SEGMENT_SCHEMA and event['kind'] == 'CHECKPOINT_END'
                  and type(event['row_count']) is int and event['row_count'] == count
                  and event['checkpoint_sha256'] == digest.hexdigest(), 'SEGMENT_CHECKPOINT_HASH')
            complete = Checkpoint(begin, digest.hexdigest(), record.head)
        return None
    log.fold(None, fold)
    _need(begin is None or complete is not None, 'SEGMENT_CHECKPOINT_INCOMPLETE')
    return complete

class QueueJournalManager:
    """QueueOwner owns lifecycle; broker mutex serializes transactions/lookup."""
    def __init__(self, current, custody, *, logical_stream_id=None, parent=None,
                 retry_horizon_ms=DEFAULT_RETRY_HORIZON_MS):
        _need(type(current) is PrivateEventLog and type(custody) is WitnessCustody, 'SEGMENT_TRUSTED_OWNER_REQUIRED')
        _need(custody.record['project_id'] == 'studio.scheduler', 'SEGMENT_QUEUE_ONLY')
        self.current, self.custody = current, custody
        self.logical_stream_id = logical_stream_id or ('queue:' + custody._registry.local_id)
        self.parent = Path(parent) if parent is not None else current.root.parent
        _need(self.parent.resolve().is_dir() and
              str(current.root.resolve().parent).casefold() == str(self.parent.resolve()).casefold(),
              'SEGMENT_PARENT_INVALID')
        _need(_identifier(self.logical_stream_id), 'SEGMENT_STREAM_INVALID')
        _need(type(retry_horizon_ms) is int and 60_000 <= retry_horizon_ms <= DEFAULT_RETRY_HORIZON_MS, 'SEGMENT_HORIZON_INVALID')
        self.retry_horizon_ms = retry_horizon_ms
        self.pending = None
        self._cleanup = []
        self._poisoned = self._closed = False
        self.checkpoint = inspect_checkpoint(current)
        rotation = custody.record.get('rotation')
        if rotation is None:
            _need(self.checkpoint is None, 'SEGMENT_CUSTODY_MISMATCH')
        else:
            _need(rotation['phase'] == 'COMMITTED' and self.checkpoint is not None
                  and rotation['generation'] == self.checkpoint.begin['generation']
                  and rotation['checkpoint_sha256'] == self.checkpoint.sha256
                  and binding_from(rotation['candidate']['binding']).witnessed == self.checkpoint.head,
                  'SEGMENT_CUSTODY_MISMATCH')

    def _check(self):
        _need(not self._poisoned and not self._closed, 'SEGMENT_RECONCILIATION_REQUIRED')

    def prepare(self, rows, state, *, reserve_records):
        """Pre-encode bounded frames; no custody change until verified."""
        self._check()
        _need(self.pending is None and type(rows) is list, 'SEGMENT_CANDIDATE_EXISTS')
        old = self.current.binding()
        _need(_same_binding(old, self.custody.binding), 'SEGMENT_HEAD_CHANGED')
        generation = 0 if self.checkpoint is None else self.checkpoint.begin['generation']
        previous = {'generation': generation, 'path': str(self.current.root), 'binding': binding_value(old)}
        begin = {'schema': SEGMENT_SCHEMA, 'kind': 'CHECKPOINT_BEGIN',
                 'generation': generation + 1, 'logical_stream_id': self.logical_stream_id, 'previous': previous, 'row_count': len(rows), 'now_ms': state['now_ms'], 'cursor': state['cursor'], 'stopped': state['stopped'], 'logical_generation': state['logical_generation'], 'retry_horizon_ms': self.retry_horizon_ms}
        begin['sequence'] = state.get('sequence', 0)
        digest = checkpoint_digest(begin, rows)
        events = [begin] + [{'schema': SEGMENT_SCHEMA, 'kind': 'CHECKPOINT_ROW', 'index': i, 'row': row}
                            for i, row in enumerate(rows)]
        events.append({'schema': SEGMENT_SCHEMA, 'kind': 'CHECKPOINT_END',
                       'row_count': len(rows), 'checkpoint_sha256': digest})
        _need(type(reserve_records) is int and reserve_records >= 0
              and len(events) + 1 + reserve_records <= MAX_RECORDS, 'SEGMENT_CAPACITY')
        size = 1024
        for index, event in enumerate(events, 2):
            _, frame = PrivateEventLog._encode(event, index, '0' * 64)
            size += len(frame)
        _need(size + reserve_records * (MAX_EVENT_BYTES + 36) <= MAX_LOG_BYTES, 'SEGMENT_CAPACITY')
        try:
            self.pending = PrivateEventLog.create(self.parent)
            head = self.pending.binding().witnessed
            for event in events:
                head = self.pending.append(event, head)
            checked = inspect_checkpoint(self.pending)
            _need(checked is not None and checked.sha256 == digest and checked.begin == begin, 'SEGMENT_CANDIDATE_CHANGED')
            return checked
        except BaseException as exc:
            cleanup = getattr(exc, 'cleanup_owner', None)
            if cleanup is not None and cleanup is not self.pending:
                self._cleanup.append(cleanup)
            self._poisoned = True
            raise SegmentError('SEGMENT_PREPARE_UNCERTAIN', outcome_unknown=True, cleanup_owner=self) from exc

    def commit(self, checkpoint):
        """Caller already verified full broker projection of the candidate."""
        self._check()
        _need(self.pending is not None and type(checkpoint) is Checkpoint, 'SEGMENT_NOT_PREPARED')
        try:
            _need(inspect_checkpoint(self.pending) == checkpoint, 'SEGMENT_CANDIDATE_CHANGED')
            old = self.current.binding()
            previous = checkpoint.begin['previous']
            _need(previous['path'] == str(self.current.root)
                  and _same_binding(old, binding_from(previous['binding'])), 'SEGMENT_HEAD_CHANGED')
            candidate = self.pending.binding()
            _need(candidate.witnessed == checkpoint.head, 'SEGMENT_CANDIDATE_SUFFIX')
            self.custody.prepare_queue_rotation(expected=old, candidate_root=self.pending.root,
                candidate_root_identity=candidate.root, candidate_binding=candidate,
                checkpoint_sha256=checkpoint.sha256)
            for phase in ('PREPARED', 'ACTIVE_POINTER'):
                _need(_same_binding(self.current.binding(), old)
                      and _same_binding(self.pending.binding(), candidate), 'SEGMENT_HEAD_CHANGED')
                self.custody.advance_queue_rotation(expected_phase=phase, previous=old, candidate=candidate,
                                                    checkpoint_sha256=checkpoint.sha256)
            self.current.close()
            self.pending.bind_custody(self.custody)
            self.current, self.pending = self.pending, None
            self.checkpoint = checkpoint
        except BaseException as exc:
            self._poisoned = True
            raise SegmentError('SEGMENT_SWITCH_UNCERTAIN', outcome_unknown=True, cleanup_owner=self) from exc

    def abort_prepared(self):
        """Close an uncommitted candidate without changing custody.

        A candidate is never selected by recovery until the registry barriers
        are advanced.  This path is for a pre-commit projection/validation
        failure; it deliberately leaves the candidate bytes for forensic
        inspection and clears only the live owned handle.
        """
        if self.pending is None:
            return
        pending = self.pending
        self.pending = None
        try:
            pending.close()
        except BaseException as exc:
            self._poisoned = True
            self._cleanup.append(pending)
            raise SegmentError('SEGMENT_CLOSE_UNCERTAIN', outcome_unknown=True,
                               cleanup_owner=self) from exc

    def rotate(self, rows, *, row_count, now_ms, cursor, stopped, logical_generation):
        _need(type(rows) is list and len(rows) == row_count, 'SEGMENT_ROW_COUNT_INVALID')
        state = {'now_ms': now_ms, 'cursor': cursor, 'stopped': stopped,
                 'logical_generation': logical_generation}
        checkpoint = self.prepare(rows, state, reserve_records=0)
        self.commit(checkpoint)
        return checkpoint

    def lookup_archived(self, job_id, *, limits=None):
        """Exact decreasing generations; one bounded disk segment at a time."""
        self._check()
        _need(_identifier(job_id), 'SEGMENT_JOB_INVALID')
        previous = None if self.checkpoint is None else self.checkpoint.begin['previous']
        visited = set()
        while previous is not None:
            descriptor_from(previous)
            _need(str(Path(previous['path']).resolve().parent).casefold() ==
                  str(self.parent.resolve()).casefold(), 'SEGMENT_PARENT_ESCAPE')
            identity_key = (previous['path'], previous['binding']['stream']['file_id'],
                            previous['binding']['witnessed']['sha256'])
            _need(identity_key not in visited, 'SEGMENT_CHAIN_CYCLE')
            visited.add(identity_key)
            binding = binding_from(previous['binding'])
            log = None
            try:
                log = PrivateEventLog.reopen(previous['path'], binding)
                _need(_same_binding(log.binding(), binding), 'SEGMENT_ARCHIVE_SUFFIX')
                checkpoint = inspect_checkpoint(log)
                _need(checkpoint is None or checkpoint.begin['generation'] == previous['generation'], 'SEGMENT_CHAIN_INVALID')
                # Reuse the live state machine: UNKNOWN may be followed by a
                # terminal result, while Stop/expiry only affect queued jobs.
                # This avoids a second, weaker interpretation of the journal.
                from .durable_broker import DurableBroker
                reader, state = DurableBroker.project_archive(
                    log, limits=QueueLimits() if limits is None else limits,
                    logical_stream_id=self.logical_stream_id)
                record = state.records.get(job_id)
                row = None if record is None else reader._record_value(
                    record, state.terminal_ms.get(job_id))
                del reader, state
                next_previous = None if checkpoint is None else checkpoint.begin['previous']
            except BaseException as exc:
                cleanup = getattr(exc, 'cleanup_owner', None)
                if cleanup is not None and cleanup is not log:
                    self._cleanup.append(cleanup)
                self._poisoned = True
                raise SegmentError('SEGMENT_ARCHIVE_UNCERTAIN', outcome_unknown=True, cleanup_owner=self) from exc
            finally:
                if log is not None:
                    try:
                        log.close()
                    except BaseException:
                        self._cleanup.append(log)
                        self._poisoned = True
                        raise SegmentError('SEGMENT_CLOSE_UNCERTAIN', outcome_unknown=True, cleanup_owner=self)
            if row is not None:
                return row, (row.get('terminal_ms') if type(row) is dict else None)
            previous = next_previous
        return None

    def close(self):
        self._closed = True
        if self.pending is not None:
            self.pending.close()
            self.pending = None
        while self._cleanup:
            self._cleanup[0].close()
            self._cleanup.pop(0)


