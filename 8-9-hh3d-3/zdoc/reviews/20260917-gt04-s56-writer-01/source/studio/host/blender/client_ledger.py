"""Unadvertised public/private command binding on the unchanged GT02 Journal.

This records admission and exact response bytes, not native effect authority,
protected publication custody, GUI recovery, or a public durable ACK.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import re
import threading

from studio.host.core.journal import Journal, JournalError, JournalLimits
from studio.host.core.limits import DEFAULT_LIMITS
from studio.host.core.transport import epoch_ms
from studio.protocol.core import Request, Response, Status, canonical_bytes, parse_json
from .durable_session import queue
from . import publication_state

SCHEMA = 'HH-BLENDER-CLIENT-LEDGER-1'
PROJECT = 'blender.client-ledger'
FILENAME = 'client-commands.jsonl'
MAX_COMMANDS = 32
MAX_PENDING = 1
MAX_REQUEST_BYTES = 8192
MAX_RESPONSE_BYTES = 32768
MAX_RECORDS = 1 + 2 * MAX_COMMANDS
LIMITS = JournalLimits(max_bytes=17 * 1024**2, max_records=MAX_RECORDS,
    max_pending_commands=MAX_PENDING, retry_horizon_ms=86400000)
_HASH = re.compile(r'sha256:[0-9a-f]{64}\Z')
_PUBLIC_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z')
_SESSION = re.compile(r'session\.[0-9a-f]{32}\Z')
_EDITS = frozenset({'mesh.create_box', 'object.transform.set', 'material.set_principled',
                   'history.undo', 'history.redo'})


class LedgerError(JournalError):
    def __init__(self, code, *, outcome_unknown=False):
        super().__init__(code)
        self.outcome_unknown = outcome_unknown


def need(value, code='BLENDER_LEDGER_INVALID'):
    if not value:
        raise LedgerError(code)


def exact(value, keys):
    need(type(value) is dict and set(value) == set(keys))


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


class EntryState(str, Enum):
    INTENT = 'INTENT'
    TERMINAL = 'TERMINAL'


@dataclass(frozen=True)
class LedgerBinding:
    project_id: str
    generation: str
    source_sha256: str
    catalog_digest: str
    owner_pin_sha256: str

    def __post_init__(self):
        need(type(self.project_id) is str and re.fullmatch(r'[a-z][a-z0-9._-]{0,63}', self.project_id))
        need(type(self.generation) is str and re.fullmatch(r'[0-9a-f]{32}', self.generation))
        for value in (self.source_sha256, self.catalog_digest, self.owner_pin_sha256):
            need(type(value) is str and _HASH.fullmatch(value))


def binding_value(binding):
    need(type(binding) is LedgerBinding)
    # Reconstruct to reject object.__setattr__ changes to the frozen value.
    return asdict(LedgerBinding(**asdict(binding)))


def private_alias(binding, session_id, command_id):
    need(type(session_id) is str and _SESSION.fullmatch(session_id), 'BLENDER_LEDGER_SESSION')
    need(type(command_id) is str and _PUBLIC_ID.fullmatch(command_id), 'BLENDER_LEDGER_COMMAND_ID')
    identity = {'binding': binding_value(binding), 'session_id': session_id, 'command_id': command_id}
    # Hash the complete public identity, never truncate or normalize its text.
    # History validation also rejects any alias collision within this owner.
    return 'client-' + hashlib.sha256(canonical_bytes(identity)).hexdigest()[:40]


def chunks(raw, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap, 'BLENDER_LEDGER_WIRE_LIMIT')
    text = raw.decode('utf-8', 'strict')
    return [text[i:i + 8192] for i in range(0, len(text), 8192)]


def unchunk(value, cap):
    need(type(value) is list and 1 <= len(value) <= (cap + 8191) // 8192)
    need(all(type(part) is str and 0 < len(part) <= 8192 for part in value))
    raw = ''.join(value).encode('utf-8', 'strict')
    need(len(raw) <= cap and chunks(raw, cap) == value)
    return raw


def make_intent(binding, session_id, request, native_command):
    need(type(request) is Request, 'BLENDER_LEDGER_REQUEST')
    request = Request.from_dict(parse_json(canonical_bytes(request.as_dict())))
    need(request.project_id == binding.project_id, 'BLENDER_LEDGER_PROJECT')
    need(dict(request.target) == {'stable_id': 'blender.owned-scene'}, 'BLENDER_LEDGER_TARGET')
    alias = private_alias(binding, session_id, request.command_id)
    native_raw = queue.c.canonical(native_command)
    need(len(native_raw) <= queue.c.MAX_BYTES, 'BLENDER_LEDGER_WIRE_LIMIT')
    if request.operation == 'export.publish':
        native = publication_state.validate_request(parse_json(native_raw))
    else:
        native = queue.parse(native_raw)
    need(native['command_id'] == alias, 'BLENDER_LEDGER_PRIVATE_ALIAS')
    need(native_raw == queue.c.canonical(native), 'BLENDER_LEDGER_NATIVE_CANONICAL')
    if request.operation == 'scene.inspect':
        need(request.payload == {} and native['operation'] == 'scene.inspect', 'BLENDER_LEDGER_TRANSLATION')
    else:
        exact(dict(request.payload), ('expected_context', 'arguments'))
        need(native['expected_revision'] == request.expected_revision
            and canonical_bytes(native['expected_context']) == canonical_bytes(request.payload['expected_context']),
            'BLENDER_LEDGER_REVISION_BINDING')
        if request.operation in _EDITS:
            need(native['operation'] == request.operation and canonical_bytes(native['payload']) ==
                canonical_bytes(request.payload['arguments']), 'BLENDER_LEDGER_TRANSLATION')
        elif request.operation in ('scene.save', 'checkpoint.save'):
            slot = 'fixture' if request.operation == 'scene.save' else 'checkpoint'
            need(request.payload['arguments'] == {} and native['operation'] == 'checkpoint.save'
                and native['payload'] == {'slot': slot}, 'BLENDER_LEDGER_TRANSLATION')
        elif request.operation == 'export.publish':
            need(request.payload['arguments'] == {}, 'BLENDER_LEDGER_TRANSLATION')
        else:
            raise LedgerError('BLENDER_LEDGER_UNSUPPORTED_OPERATION')
    request_raw = canonical_bytes(request.as_dict())
    return {'schema': SCHEMA, 'state': EntryState.INTENT.value, 'binding': binding_value(binding),
        'session_id': session_id, 'command_id': request.command_id, 'request_digest': request.digest,
        'request_sha256': sha(request_raw), 'request_chunks': chunks(request_raw, MAX_REQUEST_BYTES),
        'private_id': alias, 'native_digest': queue.c.digest(native), 'native_sha256': sha(native_raw),
        'native_chunks': chunks(native_raw, queue.c.MAX_BYTES)}


def validate_intent(value, binding):
    exact(value, ('schema', 'state', 'binding', 'session_id', 'command_id', 'request_digest',
        'request_sha256', 'request_chunks', 'private_id', 'native_digest', 'native_sha256', 'native_chunks'))
    request_raw = unchunk(value['request_chunks'], MAX_REQUEST_BYTES)
    native_raw = unchunk(value['native_chunks'], queue.c.MAX_BYTES)
    request = Request.from_json(request_raw)
    expected = make_intent(binding, value['session_id'], request, parse_json(native_raw))
    need(value == expected, 'BLENDER_LEDGER_INTENT_BINDING')
    return request


def validate_response(raw, intent):
    raw = unchunk(chunks(raw, MAX_RESPONSE_BYTES), MAX_RESPONSE_BYTES)
    response = Response.from_dict(parse_json(raw))
    need(canonical_bytes(response.as_dict()) == raw, 'BLENDER_LEDGER_RESPONSE_CANONICAL')
    need(response.command_id == intent['command_id'] and response.status in
        (Status.COMMITTED, Status.REJECTED, Status.CANCELED, Status.UNKNOWN), 'BLENDER_LEDGER_RESPONSE_BINDING')
    need(response.postconditions.get('public_ack') is False
        and response.postconditions.get('ledger_receipt_only') is True, 'BLENDER_LEDGER_NO_PUBLIC_ACK')
    return response


def make_terminal(intent, raw):
    response = validate_response(raw, intent)
    return {'schema': SCHEMA, 'state': EntryState.TERMINAL.value, 'intent': intent,
        'intent_sha256': sha(canonical_bytes(intent)), 'response_sha256': sha(raw),
        'response_chunks': chunks(raw, MAX_RESPONSE_BYTES)}, response.status.value


def unknown_response(intent):
    return canonical_bytes(Response(Status.UNKNOWN, 'BLENDER_LEDGER_UNRESOLVED_INTENT', intent['command_id'],
        postconditions={'public_ack': False, 'ledger_receipt_only': True, 'dispatch_permitted': False,
            'request_digest': intent['request_digest'], 'intent_sha256': sha(canonical_bytes(intent))}).as_dict())


def validate_history(records, binding):
    """Pure complete-chain validation; no backend or native authority created."""
    config = {'schema': SCHEMA, 'binding': binding_value(binding)}
    entries = {}
    public_ids = set()
    need(len(records) <= MAX_RECORDS, 'BLENDER_LEDGER_CAPACITY')
    for index, row in enumerate(records):
        exact(row, ('kind', 'project_id', 'command_id', 'digest', 'status', 'receipt', 'created_ms', 'expires_ms'))
        need(row['kind'] == 'command' and row['project_id'] == PROJECT, 'BLENDER_LEDGER_FOREIGN_RECORD')
        need(type(row['created_ms']) is int and type(row['expires_ms']) is int
             and 0 <= row['created_ms'] <= row['expires_ms'] < 2**53)
        if index == 0:
            need(row['command_id'] == 'ledger-config' and row['status'] == 'COMMITTED'
                and row['receipt'] == config and row['digest'] == sha(canonical_bytes(config)),
                'BLENDER_LEDGER_CONFIG_BINDING')
            continue
        value = row['receipt']
        need(type(value) is dict)
        state = value.get('state')
        if state == EntryState.INTENT.value:
            request = validate_intent(value, binding)
            key = value['private_id']
            public_key = (request.project_id, request.command_id)
            need(public_key not in public_ids, 'BLENDER_LEDGER_PUBLIC_ID_DUPLICATE')
            need(key not in entries and len(entries) < MAX_COMMANDS, 'BLENDER_LEDGER_ALIAS_OR_CAPACITY')
            need(row['command_id'] == key and row['status'] == 'ACCEPTED_PENDING'
                and row['digest'] == sha(canonical_bytes(value)), 'BLENDER_LEDGER_INTENT_ROW')
            entries[key] = {'intent': value, 'request': request, 'row': row, 'response': None}
            public_ids.add(public_key)
        elif state == EntryState.TERMINAL.value:
            exact(value, ('schema', 'state', 'intent', 'intent_sha256', 'response_sha256', 'response_chunks'))
            old = entries.get(row['command_id'])
            need(old is not None and old['response'] is None, 'BLENDER_LEDGER_TERMINAL_ORDER')
            raw = unchunk(value['response_chunks'], MAX_RESPONSE_BYTES)
            expected, status = make_terminal(old['intent'], raw)
            need(value == expected and row['status'] == status
                and all(row[name] == old['row'][name] for name in ('digest', 'created_ms', 'expires_ms')),
                'BLENDER_LEDGER_TERMINAL_BINDING')
            old['response'] = raw
        else:
            raise LedgerError('BLENDER_LEDGER_STATE')
        need(sum(entry['response'] is None for entry in entries.values()) <= MAX_PENDING,
             'BLENDER_LEDGER_PENDING_LIMIT')
    return entries


class _ClientJournal(Journal):
    """All compound decisions run within the existing native Journal guard."""
    def __init__(self, path, binding):
        self.binding = binding
        super().__init__(path, limits=LIMITS, profile=DEFAULT_LIMITS)

    def _state(self):
        try:
            return validate_history(self._records, self.binding)
        except Exception as error:
            raise LedgerError('BLENDER_LEDGER_HISTORY_UNKNOWN', outcome_unknown=True) from error

    def _retry(self, intent, state):
        incoming = validate_intent(intent, self.binding)
        # Native aliases remain session-scoped for response confidentiality,
        # but the public dedupe identity is (project_id, command_id). A second
        # authenticated session cannot turn a reserved ID into a fresh effect.
        for entry in state.values():
            first = entry['request']
            if (first.project_id, first.command_id) == (incoming.project_id, incoming.command_id):
                need(entry['intent']['session_id'] == intent['session_id'], 'BLENDER_LEDGER_COMMAND_OWNER')
        old = state.get(intent['private_id'])
        if old is None:
            return None
        first = old['request']
        need(old['intent']['session_id'] == intent['session_id']
            and old['intent']['command_id'] == intent['command_id']
            and first.digest == incoming.digest and first.expected_revision == incoming.expected_revision
            and old['intent']['native_chunks'] == intent['native_chunks'], 'BLENDER_LEDGER_COMMAND_CONFLICT')
        return False, old['intent'], old['response'] or unknown_response(old['intent'])

    @Journal._mutating
    def retry(self, intent):
        return self._retry(intent, self._state())

    @Journal._mutating
    def configure(self, now_ms):
        if not self._records:
            config = {'schema': SCHEMA, 'binding': binding_value(self.binding)}
            Journal.append_command.__wrapped__(self, project_id=PROJECT, command_id='ledger-config',
                digest=sha(canonical_bytes(config)), receipt=config, now_ms=now_ms)
            self._reload()
        self._state()

    @Journal._mutating
    def admit(self, intent, now_ms):
        need(bool(self._records), 'BLENDER_LEDGER_CONFIG_REQUIRED')
        state = self._state(); key = intent['private_id']; previous = self._retry(intent, state)
        if previous is not None:
            return previous  # Authority/deadline changes never renew admission.
        need(len(state) < MAX_COMMANDS, 'BLENDER_LEDGER_CAPACITY')
        need(sum(row['response'] is None for row in state.values()) < MAX_PENDING, 'BLENDER_LEDGER_PENDING_LIMIT')
        try:
            Journal.append_command.__wrapped__(self, project_id=PROJECT, command_id=key,
                digest=sha(canonical_bytes(intent)), receipt=intent, now_ms=now_ms, pending=True)
        except JournalError as error:
            if error.code not in ('JOURNAL_RECORD_LIMIT', 'JOURNAL_FULL', 'PENDING_LIMIT'):
                error.outcome_unknown = True
            raise
        except Exception as error:
            raise LedgerError('BLENDER_LEDGER_ADMISSION_UNKNOWN', outcome_unknown=True) from error
        try:
            self._reload(); observed = self._state()[key]
            need(observed['intent'] == intent and observed['response'] is None, 'BLENDER_LEDGER_ADMISSION_READBACK')
            return True, observed['intent'], None
        except Exception as error:
            raise LedgerError('BLENDER_LEDGER_ADMISSION_UNKNOWN', outcome_unknown=True) from error

    @Journal._mutating
    def finish(self, intent, raw, now_ms):
        terminal, status = make_terminal(intent, raw)
        state = self._state(); key = intent['private_id']; old = state.get(key)
        need(old is not None and old['intent'] == intent, 'BLENDER_LEDGER_FINISH_BINDING')
        if old['response'] is not None:
            need(old['response'] == raw, 'BLENDER_LEDGER_TERMINAL_CONFLICT')
            return old['response']
        try:
            Journal.finish_command.__wrapped__(self, project_id=PROJECT, command_id=key,
                status=status, receipt=terminal, now_ms=now_ms)
            self._reload(); observed = self._state()[key]['response']
            need(observed == raw, 'BLENDER_LEDGER_TERMINAL_READBACK')
            return observed
        except Exception as error:
            raise LedgerError('BLENDER_LEDGER_TERMINAL_UNKNOWN', outcome_unknown=True) from error

    @Journal._mutating
    def historical(self, session_id, command_id):
        alias = private_alias(self.binding, session_id, command_id)
        old = self._state().get(alias)
        need(old is not None and old['intent']['session_id'] == session_id
            and old['intent']['command_id'] == command_id, 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        return old['response'] or unknown_response(old['intent'])


class _AdmissionPermit:
    __slots__ = ()


@dataclass(frozen=True)
class Admission:
    private_id: str
    native_command: bytes
    permit: _AdmissionPermit | None
    response: bytes | None
    replayed: bool


class BlenderClientLedger:
    def __init__(self):
        raise TypeError('use BlenderClientLedger.from_owner')

    @classmethod
    def from_owner(cls, owner):
        from .client_owner import BlenderClientOwner
        need(type(owner) is BlenderClientOwner, 'BLENDER_LEDGER_EXACT_OWNER')
        owner._check_native()
        ledger = object.__new__(cls)
        ledger._owner = owner
        ledger.binding = LedgerBinding(owner.project_id, owner._host._session, owner._source_sha256,
            owner.catalog_digest, sha(owner._pin))
        ledger._binding_raw = canonical_bytes(binding_value(ledger.binding))
        ledger._mutex = threading.RLock(); ledger._permits = {}; ledger._held = False
        root = owner._host.directory / 'client-ledger'
        if not root.exists():
            owner._host._api.mkdir(root)
        ledger._journal = _ClientJournal(root / FILENAME, ledger.binding)
        ledger._journal.configure(epoch_ms())
        owner._check_native()
        return ledger

    def _binding(self):
        need(canonical_bytes(binding_value(self.binding)) == self._binding_raw, 'BLENDER_LEDGER_BINDING_CHANGED')

    def _safe_wire(self, value):
        raw = canonical_bytes(value)
        need(self._owner.sessions.encode_output(value) == raw, 'BLENDER_LEDGER_SENSITIVE_DATA')
        return raw

    def replay(self, grant, request, native_command) -> Admission | None:
        """Read authenticated history without admitting work or issuing a permit.

        Current session/operation authority and the original command binding
        remain required. A changed lease or elapsed request deadline cannot
        erase history, and an unresolved intent cannot authorize redispatch.
        """
        with self._mutex:
            self._binding()
            need(type(request) is Request, 'BLENDER_LEDGER_REQUEST')
            request = Request.from_dict(parse_json(canonical_bytes(request.as_dict())))
            self._owner.sessions._check_grant(grant, request.operation)
            self._owner.sessions.validate_public_identifier(request.command_id)
            intent = make_intent(self.binding, grant.session_id, request, native_command)
            self._safe_wire(intent)
            try:
                previous = self._journal.retry(intent)
                if previous is None:
                    return None
                fresh, saved, raw = previous
                need(not fresh and raw is not None, 'BLENDER_LEDGER_REPLAY_BINDING')
            except JournalError as error:
                if error.code not in ('BLENDER_LEDGER_COMMAND_CONFLICT', 'BLENDER_LEDGER_COMMAND_OWNER') or error.outcome_unknown:
                    self._held = True
                    error.outcome_unknown = True
                raise
            except Exception as error:
                # A guard-release failure must not expose a result whose
                # protected history read did not complete successfully.
                self._held = True
                raise LedgerError('BLENDER_LEDGER_REPLAY_UNKNOWN', outcome_unknown=True) from error
            need(self._safe_wire(parse_json(raw)) == raw, 'BLENDER_LEDGER_SENSITIVE_DATA')
            return Admission(saved['private_id'], unchunk(saved['native_chunks'], queue.c.MAX_BYTES),
                None, raw, True)

    def begin(self, grant, request, native_command):
        with self._mutex:
            self._binding()
            need(type(request) is Request, 'BLENDER_LEDGER_REQUEST')
            request = Request.from_dict(parse_json(canonical_bytes(request.as_dict())))
            self._owner.sessions._check_grant(grant, request.operation)
            self._owner.sessions.validate_public_identifier(request.command_id)
            intent = make_intent(self.binding, grant.session_id, request, native_command)
            self._safe_wire(intent)
            try:
                previous = self._journal.retry(intent)
                if previous is not None:
                    fresh, saved, raw = previous
                else:
                    need(not self._held, 'BLENDER_LEDGER_HELD')
                    self._owner._check_native()
                    fresh, saved, raw = self._journal.admit(intent, epoch_ms())
            except JournalError as error:
                if error.code not in ('BLENDER_LEDGER_COMMAND_CONFLICT', 'BLENDER_LEDGER_COMMAND_OWNER', 'BLENDER_LEDGER_CAPACITY',
                    'BLENDER_LEDGER_PENDING_LIMIT', 'BLENDER_LEDGER_HELD', 'JOURNAL_RECORD_LIMIT',
                    'JOURNAL_FULL', 'PENDING_LIMIT') or error.outcome_unknown:
                    self._held = True
                    error.outcome_unknown = True
                raise
            except Exception as error:
                # The native guard may fail while releasing its handle after
                # the intent was persisted and read back. No admission marker
                # escaped, but this is not proof that no record was written.
                self._held = True
                raise LedgerError('BLENDER_LEDGER_ADMISSION_UNKNOWN', outcome_unknown=True) from error
            permit = None
            if fresh:
                permit = _AdmissionPermit()
                self._permits[permit] = {'intent': canonical_bytes(saved), 'response': None}
            elif raw is not None:
                need(self._safe_wire(parse_json(raw)) == raw, 'BLENDER_LEDGER_SENSITIVE_DATA')
            return Admission(saved['private_id'], unchunk(saved['native_chunks'], queue.c.MAX_BYTES), permit, raw, not fresh)

    def finish(self, permit, response):
        with self._mutex:
            self._binding()
            need(type(permit) is _AdmissionPermit and permit in self._permits, 'BLENDER_LEDGER_PERMIT_REQUIRED')
            record = self._permits[permit]; intent = parse_json(record['intent'])
            need(type(response) is Response, 'BLENDER_LEDGER_RESPONSE')
            raw = self._safe_wire(response.as_dict()); validate_response(raw, intent)
            need(record['response'] is None or record['response'] == raw, 'BLENDER_LEDGER_TERMINAL_CONFLICT')
            record['response'] = raw
            try:
                observed = self._journal.finish(intent, raw, epoch_ms())
            except JournalError as error:
                self._held = True
                error.outcome_unknown = True
                raise
            except Exception as error:
                self._held = True
                raise LedgerError('BLENDER_LEDGER_TERMINAL_UNKNOWN', outcome_unknown=True) from error
            del self._permits[permit]
            return observed

    def lookup(self, grant, command_id):
        with self._mutex:
            self._binding()
            self._owner.sessions._check_grant(grant, 'control.lookup')
            self._owner.sessions.validate_public_identifier(command_id)
            raw = self._journal.historical(grant.session_id, command_id)
            # Expanded redaction history can deny delivery, never rewrite a
            # stored receipt under its original response hash.
            need(self._safe_wire(parse_json(raw)) == raw, 'BLENDER_LEDGER_SENSITIVE_DATA')
            return raw
