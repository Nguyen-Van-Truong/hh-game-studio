"""Internal, single-pending fixture activation transaction and recovery.

One private event stream owns leases, revisions, intent, selection and receipts.
Consumers are fixed memory/protected-file fixtures, not engine adapters. No
public capability is enabled. Clocks/revision observations come from trusted
broker code; arbitrary clients cannot call these methods or supply a consumer.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import re
import threading
import uuid

from .limits import (SafetyViolation, canonical_json, parse_json_utf8, validate_envelope,
                     request_digest, Request, ValidationError)
from .private_events import PrivateEventLog, EventHead, EventRecord, EventLogError, MAX_EVENT_BYTES
from .private_store import PrivateBlobStore, StagedBlob, MAX_BLOB_BYTES, MAX_STAGED_OBJECTS, MAX_STAGED_BYTES
from .safe_replace import ProtectedFileRoot, SafeReplaceError
from .fixture_release import (stage_fixture_release, pin_fixture_release, parse_release,
                              release_value, StagedRelease, PinnedRelease, MAX_ASSET_BYTES, _asset, _graph)

_ZERO = '0' * 64
_NAME = re.compile('[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
_HASH = re.compile('[0-9a-f]{64}')
_SAFE = 2**53 - 1
_REMAINING = {'INTENT': 6, 'STAGING': 5, 'STAGED': 4, 'SELECTED': 3, 'RESTORING': 2}
_PAYLOAD = {'assets', 'entrypoint', 'expected_generation', 'expected_selection_hash',
            'expected_source_revision', 'expected_source_sha256', 'expected_game_revision'}
_BIND_LOCK = threading.Lock()


class SelectorError(SafetyViolation):
    def __init__(self, code: str, *, outcome_unknown: bool = False) -> None:
        self.outcome_unknown = outcome_unknown
        super().__init__(code)


def _need(condition, code='SELECTOR_INVALID_HISTORY'):
    if not condition:
        raise SelectorError(code)


def _fields(value, fields):
    _need(type(value) is dict and set(value) == set(fields))


def _name(value):
    _need(type(value) is str and _NAME.fullmatch(value), 'SELECTOR_INVALID_NAME')


def _hash(value):
    _need(type(value) is str and _HASH.fullmatch(value), 'SELECTOR_INVALID_HASH')


def _clock(value):
    _need(type(value) is int and 0 <= value <= _SAFE, 'SELECTOR_INVALID_CLOCK')


def _revisions(value):
    _fields(value, ('source_revision', 'source_sha256', 'game_revision'))
    _name(value['source_revision'])
    _hash(value['source_sha256'])
    _name(value['game_revision'])


def _assets(payload):
    _fields(payload, _PAYLOAD)
    _need(type(payload['assets']) is dict and 1 <= len(payload['assets']) <= 16, 'SELECTOR_ASSET_LIMIT')
    prepared, graph = {}, {}
    for name, value in payload['assets'].items():
        _need(type(name) is str and re.fullmatch('[a-z][a-z0-9_-]{0,47}', name), 'SELECTOR_ASSET_ID')
        prepared[name], graph[name] = _asset(canonical_json(value))
    _graph(payload['entrypoint'], graph)
    _need(type(payload['expected_generation']) is int and 0 <= payload['expected_generation'] <= _SAFE,
          'SELECTOR_INVALID_GENERATION')
    _hash(payload['expected_selection_hash'])
    _revisions(_expected_revisions(payload))
    # Persist the entire admitted input in one bounded intent. Larger fixture
    # releases remain stage-only until a separate durable upload protocol exists.
    _need(len(canonical_json(payload)) <= 8192, 'SELECTOR_INTENT_LIMIT')
    return prepared


def _expected_revisions(payload):
    return {name: payload['expected_' + name] for name in ('source_revision', 'source_sha256', 'game_revision')}


def _asset_hash(assets):
    return hashlib.sha256(canonical_json({name: hashlib.sha256(data).hexdigest()
                                         for name, data in assets})).hexdigest()


def _empty_state():
    return {'config': None, 'revisions': None, 'lease': None, 'epoch': 0, 'clock': 0,
            'selected': None, 'adopted': None, 'generation': 0, 'selection_hash': _ZERO,
            'commands': {}, 'pending': None, 'request': None, 'stopped': False}


def _check_current(state, request, now, *, allow_stopped=False, check_lease=True):
    payload = request['payload']
    _need(allow_stopped or not state['stopped'], 'SELECTOR_STOPPED')
    _need(state['revisions'] == _expected_revisions(payload), 'SELECTOR_REVISION_CONFLICT')
    if check_lease:
        lease = state['lease']
        _need(lease is not None and lease['lease_id'] == request['lease_id']
              and lease['fencing_epoch'] == request['fencing_epoch'] and now < lease['expires_ms'],
              'SELECTOR_STALE_LEASE')
        _need(now < request['deadline_ms'], 'SELECTOR_DEADLINE_EXPIRED')


def _authority(state, value, *, recovery):
    _fields(value, ('lease_id', 'fencing_epoch', 'now_ms', 'recovery'))
    _clock(value['now_ms'])
    lease = state['lease']
    _need(type(value['recovery']) is bool and value['recovery'] == recovery
          and value['now_ms'] >= state['clock'], 'SELECTOR_RECOVERY_AUTHORITY')
    _need(lease is not None and value['lease_id'] == lease['lease_id']
          and type(value['fencing_epoch']) is int and value['fencing_epoch'] == lease['fencing_epoch']
          and value['now_ms'] < lease['expires_ms'], 'SELECTOR_STALE_LEASE')
    state['clock'] = value['now_ms']


def _response(state, command, status):
    identifier = state['pending']
    if status == 'COMMITTED':
        selected = state['selected']
        post = {'generation': selected['generation'], 'selection_hash': selected['selection_hash'],
                'release_id': selected['release']['release_id'],
                'manifest_sha256': selected['release']['manifest']['sha256'],
                'asset_set_sha256': _asset_hash(_assets(state['request']['payload']).items())}
        return {'status': status, 'code': 'FIXTURE_RELEASE_ACTIVE', 'command_id': identifier,
                'result_revision': 'selection-' + selected['selection_hash'],
                'result_hash': 'sha256:' + post['asset_set_sha256'], 'postconditions': post}
    if status == 'CANCELED':
        return {'status': status, 'code': 'FIXTURE_ACTIVATION_CANCELED', 'command_id': identifier,
                'result_revision': None, 'result_hash': None,
                'postconditions': {'selection_effect': False, 'staging_may_exist': command['phase'] != 'INTENT'}}
    _need(status == 'UNKNOWN' and command['phase'] == 'RESTORING')
    selected = state['selected']
    return {'status': 'UNKNOWN', 'code': 'FIXTURE_ACTIVATION_RESTORED', 'command_id': identifier,
            'result_revision': state['revisions']['game_revision'], 'result_hash': None,
            'postconditions': {'restored': True, 'generation': selected['generation'],
                               'selection_hash': selected['selection_hash']}}


def _reduce(state, record: EventRecord):
    event = parse_json_utf8(record.event)
    if record.head.sequence == 1:
        _need(event.get('kind') == 'GENESIS')
        return state  # Storage layer validates exact genesis/store identities.
    _need(type(event) is dict and type(event.get('kind')) is str)
    kind = event['kind']
    if kind == 'CONFIG':
        config_fields = ('kind', 'project_id', 'store', 'revisions')
        _fields(event, (*config_fields, 'consumer') if 'consumer' in event else config_fields)
        _need(record.head.sequence == 2 and state['config'] is None)
        _name(event['project_id'])
        _revisions(event['revisions'])
        _fields(event['store'], ('name', 'volume', 'file_id'))
        if 'consumer' in event:
            consumer = event['consumer']
            _fields(consumer, ('kind', 'name', 'volume', 'file_id'))
            _need(consumer['kind'] == 'protected-file-v1'
                  and type(consumer['name']) is str and re.fullmatch(r'hh-files-[0-9a-f]{32}', consumer['name'])
                  and type(consumer['volume']) is str and re.fullmatch(r'0|[1-9][0-9]{0,19}', consumer['volume'])
                  and int(consumer['volume']) < 2**64
                  and type(consumer['file_id']) is str and re.fullmatch(r'[0-9a-f]{32}', consumer['file_id']),
                  'SELECTOR_CONSUMER_BINDING_INVALID')
        state['config'] = event
        state['revisions'] = event['revisions']
        return state
    _need(state['config'] is not None)
    if kind == 'LEASE':
        _fields(event, ('kind', 'owner', 'lease_id', 'fencing_epoch', 'expires_ms', 'now_ms'))
        for name in ('owner', 'lease_id'):
            _name(event[name])
        _clock(event['now_ms']); _clock(event['expires_ms'])
        _need(event['now_ms'] >= state['clock'] and type(event['fencing_epoch']) is int
              and event['fencing_epoch'] == state['epoch'] + 1
              and 0 < event['expires_ms'] - event['now_ms'] <= 30_000)
        old = state['lease']
        _need(old is None or event['now_ms'] >= old['expires_ms'] or old['owner'] == event['owner'])
        state['lease'], state['epoch'], state['clock'] = event, event['fencing_epoch'], event['now_ms']
        return state
    if kind == 'REVISIONS':
        _fields(event, ('kind', 'before', 'after'))
        _revisions(event['before']); _revisions(event['after'])
        _need(event['before'] == state['revisions'])
        state['revisions'] = event['after']
        return state
    if kind == 'STOP':
        _fields(event, ('kind',))
        _need(not state['stopped'])
        state['stopped'] = True
        return state
    if kind == 'INTENT':
        _fields(event, ('kind', 'request', 'digest', 'release_id', 'now_ms'))
        request = validate_envelope(event['request'], now_ms=event['now_ms'])
        _assets(request['payload'])
        _need(request['project_id'] == state['config']['project_id']
              and request['operation'] == 'fixture.release.activate'
              and request['target'] == {'stable_id': 'active-release'}
              and request['expected_revision'] == request['payload']['expected_game_revision'], 'SELECTOR_REQUEST_SCOPE')
        _need(event['digest'] == request_digest(request['operation'], request['target'], request['payload'], request['schema_version']))
        _need(type(event['release_id']) is str and re.fullmatch('release-[0-9a-f]{32}', event['release_id']))
        _need(state['pending'] is None and request['command_id'] not in state['commands'], 'SELECTOR_PENDING_OR_DUPLICATE')
        _need(event['now_ms'] >= state['clock'], 'SELECTOR_CLOCK_REGRESSED')
        _check_current(state, request, event['now_ms'])
        _need(request['payload']['expected_generation'] == state['generation']
              and request['payload']['expected_selection_hash'] == state['selection_hash'], 'SELECTOR_PARENT_CONFLICT')
        state['commands'][request['command_id']] = {'digest': event['digest'], 'phase': 'INTENT',
                                                    'intent_sequence': record.head.sequence,
                                                    'terminal_sequence': None, 'release_id': event['release_id']}
        state['pending'], state['request'], state['clock'] = request['command_id'], request, event['now_ms']
        return state
    _need(state['pending'] is not None)
    _need(event.get('command_id') == state['pending'])
    command = state['commands'][state['pending']]
    _need(event.get('digest') == command['digest'])
    if kind in ('STAGING', 'SELECT'):
        fields = {'kind', 'command_id', 'digest', 'now_ms', 'authority'}
        if kind == 'SELECT':
            fields |= {'parent_generation', 'parent_hash'}
        _fields(event, fields)
        _clock(event['now_ms'])
        _need(event['now_ms'] >= state['clock'], 'SELECTOR_CLOCK_REGRESSED')
        _need(type(event['authority']) is dict and type(event['authority'].get('recovery')) is bool)
        recovery = event['authority']['recovery']
        _need(event['authority'].get('now_ms') == event['now_ms'])
        _authority(state, event['authority'], recovery=recovery)
        _check_current(state, state['request'], event['now_ms'], check_lease=not recovery)
        _need(command['phase'] == ('INTENT' if kind == 'STAGING' else 'STAGED'))
        if kind == 'SELECT':
            _need(event['parent_generation'] == state['generation']
                  and type(event['parent_generation']) is int and event['parent_hash'] == state['selection_hash'])
            state['generation'] += 1
            state['selection_hash'] = record.head.sha256
            state['selected'] = {'generation': state['generation'], 'selection_hash': record.head.sha256,
                                 'release': command['release']}
        command['phase'] = 'STAGING' if kind == 'STAGING' else 'SELECTED'
        state['clock'] = event['now_ms']
        return state
    if kind == 'STAGED':
        _fields(event, ('kind', 'command_id', 'digest', 'release'))
        release = parse_release(event['release'])
        _need(command['phase'] == 'STAGING' and release.release_id == command['release_id'])
        command['phase'], command['release'] = 'STAGED', event['release']
        return state
    if kind == 'RESTORE':
        _fields(event, ('kind', 'command_id', 'digest', 'parent_hash', 'authority'))
        _authority(state, event['authority'], recovery=True)
        _need(command['phase'] == 'SELECTED' and event['parent_hash'] == state['selection_hash'])
        _check_current(state, state['request'], 0, allow_stopped=True, check_lease=False)
        state['generation'] += 1
        state['selection_hash'] = record.head.sha256
        state['selected'] = {'generation': state['generation'], 'selection_hash': record.head.sha256,
                             'release': state['adopted']['release'] if state['adopted'] else None}
        command['phase'] = 'RESTORING'
        return state
    if kind == 'TERMINAL':
        _fields(event, ('kind', 'command_id', 'digest', 'response', 'authority'))
        response = event['response']
        _need(type(response) is dict)
        status = response.get('status')
        _need((status == 'COMMITTED' and command['phase'] == 'SELECTED')
              or (status == 'CANCELED' and command['phase'] in ('INTENT', 'STAGING', 'STAGED'))
              or (status == 'UNKNOWN' and command['phase'] == 'RESTORING'))
        if status == 'COMMITTED':
            _need(type(event['authority']) is dict and type(event['authority'].get('recovery')) is bool)
            recovery = event['authority']['recovery']
            _authority(state, event['authority'], recovery=recovery)
            _check_current(state, state['request'], event['authority']['now_ms'], check_lease=not recovery)
        elif status == 'UNKNOWN':
            _authority(state, event['authority'], recovery=True)
            _check_current(state, state['request'], 0, allow_stopped=True, check_lease=False)
        else:
            _need(event['authority'] is None)
        _need(response == _response(state, command, status))
        if status in ('COMMITTED', 'UNKNOWN'):
            state['adopted'] = state['selected']
        if status == 'COMMITTED':
            state['revisions'] = {**state['revisions'], 'game_revision': response['result_revision']}
        command['phase'], command['terminal_sequence'] = status, record.head.sequence
        command.pop('release', None)
        state['pending'] = state['request'] = None
        return state
    raise SelectorError('SELECTOR_UNKNOWN_EVENT')


@dataclass(frozen=True)
class ConsumerReadback:
    generation: int
    selection_hash: str
    release_id: str | None
    manifest_sha256: str | None
    asset_set_sha256: str


class FixtureReleaseConsumer:
    """Fixed synchronous mock consumer; input bytes are never evaluated."""
    def __init__(self, project_id: str):
        _name(project_id)
        self.project_id = project_id
        self._selected = None
        self._pin: PinnedRelease | None = None
        self.adoption_count = 0

    def adopt(self, selected, pin):
        if pin is not None:
            _need(type(pin) is PinnedRelease and pin.project_id == self.project_id
                  and release_value(pin.release) == selected['release'], 'CONSUMER_PIN_MISMATCH')
        else:
            _need(selected['release'] is None, 'CONSUMER_PIN_MISMATCH')
        # One immutable assignment in the trusted fixture's thread. Real engine
        # thread dispatch/UndoRedo/reload is explicitly a later implementation.
        if self._selected != selected or self._pin != pin:
            self._selected, self._pin = copy.deepcopy(selected), pin
            self.adoption_count += 1

    def readback(self):
        if self._selected is None:
            return None
        return ConsumerReadback(self._selected['generation'], self._selected['selection_hash'],
                                self._pin.release.release_id if self._pin else None,
                                self._pin.release.manifest.sha256 if self._pin else None,
                                _asset_hash(self._pin.assets if self._pin else ()))


class FileFixtureReleaseConsumer(FixtureReleaseConsumer):
    """Persist the complete inert fixture snapshot at one fixed protected name.

    The selector binds the root identity in CONFIG. Recovery may confirm the
    exact already-published value on a read-only reopen; it cannot overwrite
    mismatched bytes or enable future mutation by guessing the prior outcome.
    Caller owns the ProtectedFileRoot lifetime and closes this consumer after
    closing its selector. No root/path/version is supplied over the wire.
    """
    def __init__(self, project_id, files):
        super().__init__(project_id)
        _need(type(files) is ProtectedFileRoot, 'CONSUMER_PROTECTED_ROOT_REQUIRED')
        self.files, self._version = files, None
        self._closed = False
        self._mutex = threading.RLock()
        self.binding = {'kind':'protected-file-v1','name':files.root.name,
                        'volume':str(files.root_identity.volume),'file_id':files.root_identity.file_id}
        with _BIND_LOCK:
            _need(getattr(files, '_fixture_file_consumer', None) is None, 'CONSUMER_ROOT_ALREADY_BOUND')
            files._fixture_file_consumer = self

    def close(self):
        with self._mutex, _BIND_LOCK:
            _need(getattr(self, '_fixture_selector', None) is None, 'CONSUMER_SELECTOR_STILL_BOUND')
            self._closed = True
            if getattr(self.files, '_fixture_file_consumer', None) is self:
                self.files._fixture_file_consumer = None

    def _wire(self, selected, pin):
        return canonical_json({'schema':'hh-fixture-consumer-1','project_id':self.project_id,
                               'selected':selected,
                               'assets':{name:parse_json_utf8(data) for name,data in pin.assets} if pin else {}})

    def adopt(self, selected, pin):
        with self._mutex:
            _need(not self._closed, 'CONSUMER_CLOSED')
            checked = FixtureReleaseConsumer(self.project_id)
            checked.adopt(selected, pin)
            wire = self._wire(selected, pin)
            try:
                current, actual = self.files.read('active.json')
            except SafeReplaceError as exc:
                if exc.code != 'PATH_NOT_FOUND' or self._version is not None:
                    raise
                version = self.files.create_new('active.json', wire)
            else:
                if self._version is not None:
                    _need(current == self._version, 'CONSUMER_FILE_VERSION_CHANGED')
                elif actual != wire:
                    raise SelectorError('CONSUMER_RECONCILIATION_REQUIRED')
                if actual == wire:
                    self.files.confirm_barrier('active.json', current)
                    version = current
                else:
                    version = self.files.atomic_replace('active.json', wire, expected=current)
            self._version = version
            super().adopt(selected, pin)

    def readback(self):
        with self._mutex:
            _need(not self._closed, 'CONSUMER_CLOSED')
            if self._selected is None:
                return None
            current, actual = self.files.read('active.json')
            _need(current == self._version and actual == self._wire(self._selected, self._pin),
                  'CONSUMER_FILE_READBACK_FAILED')
            return super().readback()


class FixtureSelector:
    """Trusted fixture transaction owner; existing log/store lifetimes stay
    with the caller. Reopen reconstructs history but never resumes pending work.
    Only explicit reconcile() may progress a command inherited from a restart.
    """
    def __init__(self, log, store, consumer, *, project_id, initial_revisions=None):
        _need(type(log) is PrivateEventLog and type(store) is PrivateBlobStore
              and type(consumer) in (FixtureReleaseConsumer, FileFixtureReleaseConsumer), 'SELECTOR_TRUSTED_COMPONENT_REQUIRED')
        _name(project_id)
        _need(consumer.project_id == project_id, 'SELECTOR_PROJECT_MISMATCH')
        self.log, self.store, self.consumer = log, store, consumer
        self.project_id = project_id
        self._mutex = threading.RLock()
        self._closed = self._uncertain = False
        self._live = set()
        self._stop_requested = threading.Event()
        self._store_binding = {'name': store.root.name, 'volume': str(store.root_identity.volume),
                               'file_id': store.root_identity.file_id}
        self._consumer_binding = copy.deepcopy(consumer.binding) if type(consumer) is FileFixtureReleaseConsumer else None
        with _BIND_LOCK:
            _need(getattr(log, '_fixture_selector', None) is None
                  and getattr(store, '_fixture_selector', None) is None
                  and getattr(consumer, '_fixture_selector', None) is None, 'SELECTOR_ALREADY_BOUND')
            log._fixture_selector = store._fixture_selector = consumer._fixture_selector = self
        try:
            _need(store.root_identity.volume == log.binding().root.volume and store.root != log.root,
                  'SELECTOR_STORE_VOLUME_OR_ROOT')
            if initial_revisions is not None:
                _revisions(initial_revisions)
                head = log.binding().witnessed
                _need(head.sequence == 1, 'SELECTOR_ALREADY_CONFIGURED')
                event = {'kind': 'CONFIG', 'project_id': project_id, 'store': self._store_binding,
                         'revisions': initial_revisions}
                if self._consumer_binding is not None:
                    event['consumer'] = self._consumer_binding
                log.append(event, head, reserve_records=1, reserve_bytes=MAX_EVENT_BYTES + 36)
            self._reload()
        except BaseException:
            self.close()  # Releases logical ownership only; caller owns handles.
            raise

    def close(self):
        with self._mutex:
            self._closed = True
            with _BIND_LOCK:
                for resource in (self.log, self.store, self.consumer):
                    if getattr(resource, '_fixture_selector', None) is self:
                        resource._fixture_selector = None

    def _reload(self):
        _need(not self._closed, 'SELECTOR_CLOSED')
        self._head, self._state = self.log.fold(_empty_state(), _reduce)
        config = self._state['config']
        _need(config is not None and config['project_id'] == self.project_id
              and config['store'] == self._store_binding
              and config.get('consumer') == self._consumer_binding, 'SELECTOR_BINDING_MISMATCH')

    def _append(self, event):
        # Validate the exact transition before a native write. The predicted
        # frame hash is the actual selection token; append compares the head.
        body, frame = self.log._encode(event, self._head.sequence + 1, self._head.sha256)
        next_head = EventHead(self._head.sequence + 1, hashlib.sha256(body).hexdigest(), self._head.size + len(frame))
        next_state = _reduce(copy.deepcopy(self._state), EventRecord(next_head, canonical_json(event)))
        pending = next_state['pending']
        reserve = _REMAINING[next_state['commands'][pending]['phase']] if pending else 1
        try:
            head = self.log.append(event, self._head, reserve_records=reserve,
                                   reserve_bytes=reserve * (MAX_EVENT_BYTES + 36))
            _need(head == next_head, 'SELECTOR_HEAD_READBACK_MISMATCH')
        except BaseException as exc:
            # The storage primitive emits this exact failure only after head
            # validation and before WriteFile. Other/uncertain failures cannot
            # be classified as no effect from their code alone.
            if type(exc) is EventLogError and exc.code == 'EVENT_CAPACITY' and not exc.outcome_unknown:
                raise SelectorError('SELECTOR_CAPACITY') from exc
            self._uncertain = True
            if isinstance(exc, (SafetyViolation, OSError)):
                raise SelectorError('SELECTOR_EVENT_UNKNOWN', outcome_unknown=True) from exc
            raise
        self._head, self._state = head, next_state

    def snapshot(self):
        with self._mutex:
            self._reload()
            state = self._state
            observed = self.consumer.readback()
            selected = state['selected']
            ready = bool(selected and selected == state['adopted']
                         and observed == self._readback_expected(selected, self._pin(selected)))
            return {'generation': state['generation'], 'selection_hash': state['selection_hash'],
                    'selected': copy.deepcopy(selected), 'last_verified_adopted': copy.deepcopy(state['adopted']),
                    'revisions': dict(state['revisions']), 'stopped': state['stopped'],
                    'ready': ready, 'pending_command': state['pending']}

    def lease(self, owner, *, now_ms, ttl_ms=30_000):
        _name(owner); _clock(now_ms)
        _need(type(ttl_ms) is int and 0 < ttl_ms <= 30_000, 'SELECTOR_LEASE_LIMIT')
        with self._mutex:
            self._reload()
            # A fresh recovery lease can be issued while stopped; it cannot
            # authorize prepare/select/normal adoption while STOP is set.
            event = {'kind': 'LEASE', 'owner': owner, 'lease_id': 'lease-' + uuid.uuid4().hex,
                     'fencing_epoch': self._state['epoch'] + 1, 'expires_ms': now_ms + ttl_ms, 'now_ms': now_ms}
            self._append(event)
            return dict(event)

    def observe_revisions(self, before, after):
        """Trusted fixture source observation; does not edit or roll back files."""
        with self._mutex:
            self._reload()
            self._append({'kind': 'REVISIONS', 'before': before, 'after': after})

    def lookup(self, command_id, digest=None):
        _name(command_id)
        with self._mutex:
            self._reload()
            command = self._state['commands'].get(command_id)
            if command is None:
                return None
            _need(digest is None or command['digest'] == digest, 'SELECTOR_COMMAND_CONFLICT')
            if command['terminal_sequence'] is not None:
                return parse_json_utf8(self.log.read(command['terminal_sequence']).event)['response']
            return {'status': 'ACCEPTED_PENDING' if command['phase'] in ('INTENT', 'STAGING', 'STAGED') else 'UNKNOWN',
                    'command_id': command_id, 'phase': command['phase'], 'digest': command['digest']}

    def prepare(self, request, *, now_ms):
        # Copy before retaining anything; caller dictionaries cannot change the
        # bytes whose command digest was admitted. Lookup precedes deadline.
        request = parse_json_utf8(canonical_json(request))
        try:
            Request.from_dict(request)
        except ValidationError as exc:
            raise SelectorError(exc.code) from None
        _assets(request['payload'])
        _need(request['project_id'] == self.project_id and request['operation'] == 'fixture.release.activate'
              and request['target'] == {'stable_id': 'active-release'}
              and request['expected_revision'] == request['payload']['expected_game_revision'], 'SELECTOR_REQUEST_SCOPE')
        digest = request_digest(request['operation'], request['target'], request['payload'], request['schema_version'])
        with self._mutex:
            old = self.lookup(request['command_id'], digest)
            if old is not None:
                return old
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            _need(not self._uncertain, 'SELECTOR_RECONCILIATION_REQUIRED')
            self._stage_capacity(request['payload'])
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            self._append({'kind': 'INTENT', 'request': request, 'digest': digest,
                          'release_id': 'release-' + uuid.uuid4().hex, 'now_ms': now_ms})
            self._live.add(request['command_id'])
            return self.lookup(request['command_id'], digest)

    def _stage_capacity(self, payload):
        prepared = _assets(payload)
        with self.store._mutex:
            self.store._check()
            # Reserve one complete release (all assets + worst-case manifest).
            # Single pending intent and exclusive selector/store ownership keep
            # this reservation reconstructible without a second quota journal.
            self.store._check_quota(sum(map(len, prepared.values())) + MAX_ASSET_BYTES)
            existing = sum(path.name != '.writer' for path in self.store.root.iterdir())
            _need(existing + len(prepared) + 1 <= MAX_STAGED_OBJECTS, 'SELECTOR_STAGE_CAPACITY')

    def _pending(self, command_id, phases, recovery):
        self._reload()
        _need(self._state['pending'] == command_id, 'SELECTOR_COMMAND_NOT_PENDING')
        command = self._state['commands'][command_id]
        _need(command['phase'] in phases, 'SELECTOR_PHASE_CONFLICT')
        _need(recovery or (command_id in self._live and not self._uncertain), 'SELECTOR_EXPLICIT_RECONCILE_REQUIRED')
        return command

    def _command_event(self, kind, command_id, **fields):
        return {'kind': kind, 'command_id': command_id,
                'digest': self._state['commands'][command_id]['digest'], **fields}

    def stage(self, command_id, *, now_ms, _recovery=False):
        with self._mutex:
            command = self._pending(command_id, ('INTENT',), _recovery)
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            self._stage_capacity(self._state['request']['payload'])
            authority = self._authorization(now_ms, _recovery)
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            self._append(self._command_event('STAGING', command_id, now_ms=now_ms, authority=authority))
            payload = self._state['request']['payload']
            try:
                release = stage_fixture_release(self.store, project_id=self.project_id,
                          source_revision=payload['expected_source_revision'], source_sha256=payload['expected_source_sha256'],
                          game_revision=payload['expected_game_revision'], entrypoint=payload['entrypoint'],
                          assets=_assets(payload), release_id=command['release_id'])
                self._append(self._command_event('STAGED', command_id, release=release_value(release)))
            except BaseException as exc:
                self._uncertain = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise SelectorError('SELECTOR_STAGE_UNKNOWN', outcome_unknown=True) from exc
                raise
            return release_value(release)

    def _pin(self, selected):
        if selected['release'] is None:
            return None
        return pin_fixture_release(self.store, parse_release(selected['release']), project_id=self.project_id)

    def select(self, command_id, *, now_ms, _recovery=False):
        with self._mutex:
            command = self._pending(command_id, ('STAGED',), _recovery)
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            pin = self._pin({'release': command['release']})
            payload = self._state['request']['payload']
            _need(dict(pin.assets) == _assets(payload) and pin.entrypoint == payload['entrypoint']
                  and pin.source_revision == payload['expected_source_revision']
                  and pin.source_sha256 == payload['expected_source_sha256']
                  and pin.game_revision == payload['expected_game_revision'], 'SELECTOR_RELEASE_READBACK_MISMATCH')
            authority = self._authorization(now_ms, _recovery)
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            self._append(self._command_event('SELECT', command_id, now_ms=now_ms, authority=authority,
                         parent_generation=self._state['generation'], parent_hash=self._state['selection_hash']))
            return copy.deepcopy(self._state['selected'])

    def _discover_staged(self, command_id):
        command = self._pending(command_id, ('STAGING',), True)
        store, candidates = self.store, []
        # Enumerate only the retained, private store. Metadata/hash are read
        # through verified native handles, never inferred from a path listing.
        with store._mutex:
            store._check()
            count = total = 0
            for path in store.root.iterdir():
                if path.name == '.writer':
                    continue
                count += 1
                _need(count <= MAX_STAGED_OBJECTS and re.fullmatch('blob-[0-9a-f]{32}', path.name),
                      'SELECTOR_STAGE_NAMESPACE')
                handle = store._api.open(path)
                try:
                    before = store._api.inspect(handle, path)
                    store._api.check_security(handle)
                    _need(before.volume == store.root_identity.volume and 0 <= before.size <= MAX_BLOB_BYTES,
                          'SELECTOR_STAGE_NAMESPACE')
                    total += before.size
                    _need(total <= MAX_STAGED_BYTES, 'SELECTOR_STAGE_NAMESPACE')
                    raw = store._api.read(handle, MAX_BLOB_BYTES)
                    _need(store._api.inspect(handle, path) == before and len(raw) == before.size,
                          'SELECTOR_STAGE_IDENTITY_CHANGED')
                    store._api.check_security(handle)
                    store._check()
                    try:
                        value = parse_json_utf8(raw)
                    except SafetyViolation:
                        continue  # unrelated opaque blob; never interpreted
                    if (type(value) is dict and value.get('format') == 'hh-fixture-release-1'
                            and value.get('release_id') == command['release_id']):
                        candidates.append(StagedRelease(command['release_id'],
                                          StagedBlob(path.name, before, hashlib.sha256(raw).hexdigest())))
                finally:
                    store._api.close(handle)
        _need(len(candidates) == 1, 'SELECTOR_STAGING_INCOMPLETE_OR_AMBIGUOUS')
        release = candidates[0]
        pin = pin_fixture_release(store, release, project_id=self.project_id)
        payload = self._state['request']['payload']
        _need(dict(pin.assets) == _assets(payload) and pin.entrypoint == payload['entrypoint']
              and pin.source_revision == payload['expected_source_revision']
              and pin.source_sha256 == payload['expected_source_sha256']
              and pin.game_revision == payload['expected_game_revision'], 'SELECTOR_RELEASE_READBACK_MISMATCH')
        self._append(self._command_event('STAGED', command_id, release=release_value(release)))
        return release_value(release)

    @staticmethod
    def _readback_expected(selected, pin):
        return ConsumerReadback(selected['generation'], selected['selection_hash'],
               pin.release.release_id if pin else None, pin.release.manifest.sha256 if pin else None,
               _asset_hash(pin.assets if pin else ()))

    def _authorization(self, now_ms, recovery):
        lease = self._state['lease']
        _need(lease is not None, 'SELECTOR_STALE_LEASE')
        value = {'lease_id': lease['lease_id'], 'fencing_epoch': lease['fencing_epoch'],
                 'now_ms': now_ms, 'recovery': recovery}
        _authority(copy.deepcopy(self._state), value, recovery=recovery)
        return value

    def adopt(self, command_id, *, now_ms, _recovery=False):
        with self._mutex:
            command = self._pending(command_id, ('SELECTED', 'RESTORING'), _recovery)
            restoring = command['phase'] == 'RESTORING'
            _need(restoring or not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            authority = self._authorization(now_ms, _recovery or restoring)
            _check_current(self._state, self._state['request'], now_ms,
                           allow_stopped=restoring, check_lease=not (_recovery or restoring))
            selected = self._state['selected']
            pin = self._pin(selected)
            expected = self._readback_expected(selected, pin)
            # Stop can arrive while native pin/readback holds the main mutex.
            # Recheck at effect admission, after that potentially slow I/O.
            _need(restoring or not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            try:
                self.consumer.adopt(selected, pin)
                _need(self.consumer.readback() == expected, 'SELECTOR_CONSUMER_READBACK_FAILED')
                status = 'UNKNOWN' if restoring else 'COMMITTED'
                response = _response(self._state, command, status)
                if not restoring:
                    _need(response['postconditions']['asset_set_sha256'] == expected.asset_set_sha256,
                          'SELECTOR_CONSUMER_READBACK_FAILED')
                self._append(self._command_event('TERMINAL', command_id, response=response, authority=authority))
            except BaseException as exc:
                self._uncertain = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise SelectorError('SELECTOR_ADOPTION_UNKNOWN', outcome_unknown=True) from exc
                raise
            self._live.discard(command_id)
            self._uncertain = False
            return response

    def cancel(self, command_id, *, _recovery=False):
        with self._mutex:
            command = self._pending(command_id, ('INTENT', 'STAGING', 'STAGED'), _recovery)
            response = _response(self._state, command, 'CANCELED')
            self._append(self._command_event('TERMINAL', command_id, response=response, authority=None))
            self._live.discard(command_id)
            return response

    def load_committed(self, *, now_ms):
        """Explicit startup adoption of the last committed snapshot. Does not
        stage, append a selection, replay the command, or clear durable STOP.
        """
        with self._mutex:
            self._reload()
            state = self._state
            _need(not state['stopped'] and not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            _need(state['pending'] is None and state['selected'] is not None
                  and state['selected'] == state['adopted'], 'SELECTOR_RECONCILIATION_REQUIRED')
            self._authorization(now_ms, True)
            pin = self._pin(state['selected'])
            expected = self._readback_expected(state['selected'], pin)
            _need(not self._stop_requested.is_set(), 'SELECTOR_STOPPED')
            try:
                self.consumer.adopt(state['selected'], pin)
                _need(self.consumer.readback() == expected, 'SELECTOR_CONSUMER_READBACK_FAILED')
            except BaseException as exc:
                self._uncertain = True
                if isinstance(exc, (SafetyViolation, OSError)):
                    raise SelectorError('SELECTOR_ADOPTION_UNKNOWN', outcome_unknown=True) from exc
                raise
            self._uncertain = False
            return expected

    def stop(self):
        self._stop_requested.set()
        with self._mutex:
            self._reload()
            if not self._state['stopped']:
                self._append({'kind': 'STOP'})
            pending = self._state['pending']
            if pending and self._state['commands'][pending]['phase'] in ('INTENT', 'STAGING', 'STAGED'):
                self.cancel(pending, _recovery=True)
            return self.snapshot()

    def reconcile(self, command_id, action, *, now_ms=None):
        """Explicit trusted recovery decision. Never infer action from elapsed
        time, a caller-provided force bit, or a missing receipt. A STAGING cut
        may resolve one complete matching release or be canceled; it is never
        blindly staged again. Partial/ambiguous files stay preserved.
        """
        with self._mutex:
            if action == 'stage':
                return self.stage(command_id, now_ms=now_ms, _recovery=True)
            if action == 'discover_staged':
                return self._discover_staged(command_id)
            if action == 'select':
                return self.select(command_id, now_ms=now_ms, _recovery=True)
            if action == 'adopt':
                return self.adopt(command_id, now_ms=now_ms, _recovery=True)
            if action == 'cancel':
                return self.cancel(command_id, _recovery=True)
            if action == 'restore':
                self._pending(command_id, ('SELECTED',), True)
                authority = self._authorization(now_ms, True)
                self._append(self._command_event('RESTORE', command_id, parent_hash=self._state['selection_hash'], authority=authority))
                return self.adopt(command_id, now_ms=now_ms, _recovery=True)
            raise SelectorError('SELECTOR_RECOVERY_ACTION_UNSUPPORTED')
