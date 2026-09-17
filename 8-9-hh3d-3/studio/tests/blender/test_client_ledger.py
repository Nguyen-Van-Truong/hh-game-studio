"""Pure ledger/model tests. No filesystem, native lock, engine or Registry I/O.

MemoryJournal is explicitly inert. It exercises production compound methods
and core record encoding/validation, not native durability or process recovery.
"""
import copy
from contextlib import contextmanager
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.blender import client_ledger as m
from studio.host.core.journal import Journal, JournalError
from studio.protocol.core import Request, Response, Status, canonical_bytes, parse_json

BINDING = m.LedgerBinding('blender.test', 'a' * 32, 'sha256:' + 'b' * 64,
    'sha256:' + 'c' * 64, 'sha256:' + 'd' * 64)
SESSION = 'session.' + 'e' * 32


def request(key='Public/Command:One', **changes):
    payload = {'expected_context': {'mode': 'OBJECT', 'active_id': None, 'selected_ids': []},
        'arguments': {'object_id': 'box', 'size': [1, 2, 3]}}
    values = dict(command_id=key, project_id=BINDING.project_id, operation='mesh.create_box',
        lease_id='writer.1', fencing_epoch=1, expected_revision='sha256:' + 'f' * 64,
        target={'stable_id': 'blender.owned-scene'}, payload=payload,
        payload_hash=m.sha(canonical_bytes(payload)), deadline_ms=10000)
    values.update(changes)
    values['payload_hash'] = m.sha(canonical_bytes(values['payload']))
    return Request(**values)


def native(value, session_id=SESSION, binding=BINDING):
    return {'schema': m.queue.SCHEMA, 'command_id': m.private_alias(binding, session_id, value.command_id),
        'operation': value.operation, 'expected_revision': value.expected_revision,
        'expected_context': value.payload['expected_context'], 'payload': value.payload['arguments']}


def response(value, status=Status.COMMITTED, **postconditions):
    return Response(status, 'TEST_OBSERVED', value.command_id, value.expected_revision,
        postconditions={'public_ack': False, 'ledger_receipt_only': True,
            'live_state_durable': False, **postconditions})


class MemoryJournal(m._ClientJournal):
    def __init__(self, binding=BINDING, records=()):
        self.binding = binding; self.limits = m.LIMITS; self.profile = m.DEFAULT_LIMITS
        self._records = copy.deepcopy(list(records)); self._commands = {}; self._pending = set(); self._leases = {}
        self._guard = threading.RLock(); self.failure = None; self.fail_reload = False
        self._reload()

    @contextmanager
    def _writer_lock(self):
        with self._guard:
            yield

    def _reload(self):
        if self.fail_reload:
            raise JournalError('JOURNAL_DURABILITY_UNCONFIRMED')
        self._commands = {}; self._pending = set(); self._leases = {}
        for index, row in enumerate(self._records):
            self._apply_loaded(row, index)

    def _append(self, row):
        # Pure primitive calls only. The host's actual Journal handles all
        # native capacity reservations/barriers in the later integration run.
        self._validate_record(row)
        self._encoded_record(row)
        if self.failure == 'before':
            raise OSError('inert write failure')
        self._records.append(copy.deepcopy(row))
        self._reload()
        if self.failure == 'after':
            raise OSError('inert failure after visible append')


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.journal = MemoryJournal(); self.journal.configure(1000)
        self.value = request(); self.native = native(self.value)
        self.intent = m.make_intent(BINDING, SESSION, self.value, self.native)

    def admit(self, value=None, session_id=SESSION):
        value = value or self.value
        intent = m.make_intent(BINDING, session_id, value, native(value, session_id))
        return self.journal.admit(intent, 1001)

    def test_alias_covers_complete_identity_and_private_grammar(self):
        alias = self.intent['private_id']
        self.assertRegex(alias, r'^[a-z][a-z0-9_-]{0,47}$')
        self.assertNotIn(self.value.command_id, alias)
        self.assertNotEqual(alias, m.private_alias(BINDING, 'session.' + '1' * 32, self.value.command_id))
        self.assertNotEqual(alias, m.private_alias(BINDING, SESSION, self.value.command_id.lower()))
        other = m.LedgerBinding(BINDING.project_id, '1' * 32, BINDING.source_sha256,
            BINDING.catalog_digest, BINDING.owner_pin_sha256)
        self.assertNotEqual(alias, m.private_alias(other, SESSION, self.value.command_id))

    def test_first_intent_exact_request_and_native_bytes(self):
        fresh, saved, raw = self.admit()
        self.assertTrue(fresh); self.assertIsNone(raw)
        self.assertEqual(m.unchunk(saved['request_chunks'], m.MAX_REQUEST_BYTES), canonical_bytes(self.value.as_dict()))
        self.assertEqual(m.unchunk(saved['native_chunks'], m.queue.c.MAX_BYTES), m.queue.c.canonical(self.native))
        self.assertEqual(len(self.journal._records), 2)
        self.assertEqual(self.journal._records[-1]['status'], 'ACCEPTED_PENDING')

    def test_pending_retry_and_reopen_are_unknown_never_fresh(self):
        self.admit()
        reopened = MemoryJournal(records=self.journal._records)
        fresh, _, raw = reopened.admit(self.intent, 999999999)
        self.assertFalse(fresh)
        value = Response.from_dict(parse_json(raw))
        self.assertEqual(value.status, Status.UNKNOWN)
        self.assertFalse(value.postconditions['dispatch_permitted'])
        self.assertEqual(reopened.historical(SESSION, self.value.command_id), raw)
        self.assertEqual(len(reopened._records), 2)

    def test_terminal_exact_retry_after_horizon_and_authority_change(self):
        self.admit(); raw = canonical_bytes(response(self.value).as_dict())
        self.assertEqual(self.journal.finish(self.intent, raw, 1002), raw)
        changed = request(lease_id='new.lease', fencing_epoch=999, deadline_ms=1)
        self.assertEqual(self.admit(changed), (False, self.intent, raw))
        reopened = MemoryJournal(records=self.journal._records)
        self.assertEqual(reopened.admit(self.intent, 10**12), (False, self.intent, raw))
        self.assertEqual(reopened.historical(SESSION, self.value.command_id), raw)
        self.assertEqual(len(reopened._records), 3)

    def test_changed_payload_revision_or_native_translation_conflicts(self):
        self.admit()
        payload = copy.deepcopy(self.value.payload); payload['arguments']['size'] = [3, 2, 1]
        for value in (request(payload=payload),
                      request(expected_revision='sha256:' + '0' * 64)):
            with self.assertRaisesRegex(m.LedgerError, 'COMMAND_CONFLICT'):
                self.admit(value)
        changed = dict(self.native, payload={'object_id': 'box', 'size': [1.0, 2.0, 3.0]})
        intent = m.make_intent(BINDING, SESSION, self.value, changed)
        with self.assertRaisesRegex(m.LedgerError, 'COMMAND_CONFLICT'):
            self.journal.admit(intent, 1002)

    def test_lookup_is_session_scoped(self):
        self.admit()
        with self.assertRaisesRegex(m.LedgerError, 'COMMAND_NOT_FOUND'):
            self.journal.historical('session.' + '1' * 32, self.value.command_id)

    def test_native_alias_precondition_and_canonical_tamper_rejected(self):
        for field, value in (('command_id', 'caller-chosen'), ('expected_revision', 'sha256:' + '0' * 64)):
            with self.subTest(field=field), self.assertRaises(m.LedgerError):
                m.make_intent(BINDING, SESSION, self.value, dict(self.native, **{field: value}))
        for field in ('request_sha256', 'native_sha256', 'native_digest', 'request_digest'):
            changed = copy.deepcopy(self.intent); changed[field] = 'sha256:' + '0' * 64
            with self.subTest(field=field), self.assertRaises(m.LedgerError):
                m.validate_intent(changed, BINDING)

    def test_read_request_cannot_bind_a_private_write(self):
        value = request(operation='scene.inspect', payload={})
        with self.assertRaisesRegex(m.LedgerError, 'TRANSLATION'):
            m.make_intent(BINDING, SESSION, value, self.native)
        inspect = dict(self.native, operation='scene.inspect', expected_revision=None, expected_context=None, payload={})
        self.assertEqual(m.make_intent(BINDING, SESSION, value, inspect)['private_id'], self.intent['private_id'])

    def test_payload_and_context_translation_are_bound_before_admission(self):
        for changes in ({'payload': {'object_id': 'other', 'size': [1, 2, 3]}},
                        {'expected_context': {'mode': 'OBJECT', 'active_id': 'box', 'selected_ids': ['box']}}):
            with self.subTest(changes=changes), self.assertRaises(m.LedgerError):
                m.make_intent(BINDING, SESSION, self.value, dict(self.native, **changes))
        with self.assertRaisesRegex(m.LedgerError, 'TARGET'):
            m.make_intent(BINDING, SESSION, request(target={'path': 'artist.blend'}), self.native)

    def test_fixed_save_checkpoint_and_publication_requests_bind_distinct_private_protocols(self):
        context = self.value.payload['expected_context']
        for operation, slot in (('scene.save', 'fixture'), ('checkpoint.save', 'checkpoint')):
            value = request(operation=operation, payload={'expected_context': context, 'arguments': {}})
            command = dict(self.native, operation='checkpoint.save', payload={'slot': slot})
            intent = m.make_intent(BINDING, SESSION, value, command)
            self.assertEqual(m.validate_intent(intent, BINDING), value)
            with self.assertRaisesRegex(m.LedgerError, 'TRANSLATION'):
                m.make_intent(BINDING, SESSION, value, dict(command, payload={'slot': 'checkpoint' if slot == 'fixture' else 'fixture'}))
        value = request(operation='export.publish', payload={'expected_context': context, 'arguments': {}})
        publication = {'schema': m.publication_state.SCHEMA, 'command_id': self.intent['private_id'],
            'expected_revision': value.expected_revision, 'expected_context': context}
        intent = m.make_intent(BINDING, SESSION, value, publication)
        self.assertEqual(m.validate_intent(intent, BINDING), value)
        with self.assertRaises(m.publication_state.PublicationError):
            m.make_intent(BINDING, SESSION, value, dict(publication, path='foreign.blend'))

    def test_request_and_response_limits_fail_before_backend_mutation(self):
        with self.assertRaises(m.LedgerError):
            m.chunks(b'x' * (m.MAX_REQUEST_BYTES + 1), m.MAX_REQUEST_BYTES)
        with self.assertRaises(m.LedgerError):
            m.make_terminal(self.intent, b'x' * (m.MAX_RESPONSE_BYTES + 1))
        with self.assertRaises(m.LedgerError):
            m.unchunk(['ab', 'cd'], 8192)  # Noncanonical chunk boundaries.
        self.assertEqual(len(self.journal._records), 1)

    def test_concurrent_duplicate_admission_returns_only_one_fresh_marker(self):
        results = []; errors = []; start = threading.Barrier(3)
        def worker():
            try:
                start.wait(timeout=2); results.append(self.journal.admit(self.intent, 1001))
            except Exception as error:errors.append(error)
        workers = [threading.Thread(target=worker) for _ in range(2)]
        for worker in workers:worker.start()
        start.wait(timeout=2)
        for worker in workers:worker.join(2)
        self.assertEqual(errors, []); self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(sorted(row[0] for row in results), [False, True])
        self.assertEqual(len(self.journal._records), 2)

    def test_binding_change_and_incomplete_history_fail_closed(self):
        self.admit(); self.journal.finish(self.intent, canonical_bytes(response(self.value).as_dict()), 1002)
        for records in (self.journal._records[1:], self.journal._records[:1] + self.journal._records[2:],
                        self.journal._records + self.journal._records[-1:]):
            with self.assertRaises((m.LedgerError, JournalError)):
                MemoryJournal(records=records).historical(SESSION, self.value.command_id)
        other = m.LedgerBinding(BINDING.project_id, '1' * 32, BINDING.source_sha256,
            BINDING.catalog_digest, BINDING.owner_pin_sha256)
        with self.assertRaisesRegex(m.LedgerError, 'HISTORY_UNKNOWN'):
            MemoryJournal(binding=other, records=self.journal._records).configure(1003)

    def test_semantically_forged_terminal_binding_rejected(self):
        self.admit(); self.journal.finish(self.intent, canonical_bytes(response(self.value).as_dict()), 1002)
        for change in ('response_hash', 'intent', 'status'):
            records = copy.deepcopy(self.journal._records)
            terminal = records[-1]
            if change == 'response_hash':terminal['receipt']['response_sha256'] = 'sha256:' + '0' * 64
            if change == 'intent':terminal['receipt']['intent']['session_id'] = 'session.' + '1' * 32
            if change == 'status':terminal['status'] = 'REJECTED'
            with self.subTest(change=change), self.assertRaisesRegex(m.LedgerError, 'HISTORY_UNKNOWN'):
                MemoryJournal(records=records).historical(SESSION, self.value.command_id)

    def test_terminal_statuses_exact_and_nonterminal_or_ack_rejected(self):
        for status in (Status.COMMITTED, Status.REJECTED, Status.CANCELED, Status.UNKNOWN):
            raw = canonical_bytes(response(self.value, status).as_dict())
            self.assertEqual(m.validate_response(raw, self.intent).status, status)
        for value in (response(self.value, Status.ACCEPTED_PENDING), response(self.value, public_ack=True),
                      response(self.value, ledger_receipt_only=False), response(request('other'))):
            with self.assertRaises(m.LedgerError):
                m.make_terminal(self.intent, canonical_bytes(value.as_dict()))

    def test_byte_exact_response_not_normalized_on_replay(self):
        self.admit(); value = response(self.value).as_dict(); raw = canonical_bytes(value)
        with self.assertRaisesRegex(m.LedgerError, 'CANONICAL'):
            self.journal.finish(self.intent, b' ' + raw, 1002)
        self.journal.finish(self.intent, raw, 1002)
        with self.assertRaisesRegex(m.LedgerError, 'TERMINAL_CONFLICT'):
            self.journal.finish(self.intent, canonical_bytes(response(self.value, Status.UNKNOWN).as_dict()), 1003)
        self.assertEqual(self.journal.historical(SESSION, self.value.command_id), raw)

    def test_pending_and_lifetime_cap_do_not_evict_old_commands(self):
        self.admit()
        with self.assertRaisesRegex(m.LedgerError, 'PENDING_LIMIT'):
            self.admit(request('another'))
        first = canonical_bytes(response(self.value).as_dict())
        self.journal.finish(self.intent, first, 1002)
        for index in range(m.MAX_COMMANDS - 1):
            value = request('command.' + str(index)); _, intent, _ = self.admit(value)
            self.journal.finish(intent, canonical_bytes(response(value).as_dict()), 1002)
        with self.assertRaisesRegex(m.LedgerError, 'CAPACITY'):
            self.admit(request('overflow'))
        self.assertEqual(len(self.journal._records), m.MAX_RECORDS)
        self.assertEqual(self.journal.historical(SESSION, self.value.command_id), first)

    def test_reserved_terminal_envelope_fits_unchanged_core_profile(self):
        self.assertEqual(m.LIMITS.max_records, 1 + 2 * m.MAX_COMMANDS)
        self.assertEqual(m.LIMITS.max_pending_commands, 1)
        self.assertGreaterEqual(m.LIMITS.max_bytes, m.MAX_RECORDS * m.DEFAULT_LIMITS.max_envelope_bytes)
        self.admit()
        large = response(self.value, observation='"\\' * 4000)
        raw = canonical_bytes(large.as_dict()); self.assertLess(len(raw), m.MAX_RESPONSE_BYTES)
        self.journal.finish(self.intent, raw, 1002)  # Uses actual pure core _encoded_record.
        encoded = self.journal._encoded_record(self.journal._records[-1])
        self.assertLess(len(encoded), m.DEFAULT_LIMITS.max_envelope_bytes)

    def test_write_failures_never_mint_fresh_admission_and_visible_intent_is_unknown(self):
        for failure in ('before', 'after'):
            journal = MemoryJournal(); journal.configure(1000); journal.failure = failure
            with self.assertRaises(m.LedgerError) as error:
                journal.admit(self.intent, 1001)
            self.assertTrue(error.exception.outcome_unknown)
            if failure == 'after':
                journal.failure = None
                self.assertFalse(journal.admit(self.intent, 1002)[0])
                self.assertEqual(parse_json(journal.historical(SESSION, self.value.command_id))['status'], 'UNKNOWN')

    def test_terminal_visible_after_failure_requires_fresh_barrier_then_exact_readback(self):
        self.admit(); raw = canonical_bytes(response(self.value).as_dict())
        self.journal.failure = 'after'
        with self.assertRaises(m.LedgerError) as error:
            self.journal.finish(self.intent, raw, 1002)
        self.assertTrue(error.exception.outcome_unknown)
        self.journal.failure = None; self.journal.fail_reload = True
        with self.assertRaisesRegex(JournalError, 'DURABILITY_UNCONFIRMED'):
            self.journal.historical(SESSION, self.value.command_id)
        self.journal.fail_reload = False
        self.assertEqual(self.journal.finish(self.intent, raw, 1003), raw)

    def test_expired_pending_cannot_be_finalized_or_reexecuted(self):
        self.admit(); raw = canonical_bytes(response(self.value).as_dict())
        with self.assertRaises(m.LedgerError) as error:
            self.journal.finish(self.intent, raw, 10**12)
        self.assertTrue(error.exception.outcome_unknown)
        fresh, _, result = self.journal.admit(self.intent, 10**12)
        self.assertFalse(fresh); self.assertEqual(parse_json(result)['status'], 'UNKNOWN')


class FacadeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.backend = MemoryJournal(); self.backend.configure(1000)
        self.owner = SimpleNamespace(_check_native=Mock(), sessions=SimpleNamespace(
            _check_grant=Mock(), validate_public_identifier=Mock(), encode_output=canonical_bytes))
        self.ledger = object.__new__(m.BlenderClientLedger)
        self.ledger._owner = self.owner; self.ledger.binding = BINDING
        self.ledger._binding_raw = canonical_bytes(m.binding_value(BINDING))
        self.ledger._mutex = threading.RLock(); self.ledger._permits = {}; self.ledger._held = False
        self.ledger._journal = self.backend
        self.grant = SimpleNamespace(session_id=SESSION)
        self.clock = patch.object(m, 'epoch_ms', return_value=1001); self.clock.start(); self.addCleanup(self.clock.stop)

    def begin(self, value=None):
        value = value or request()
        return self.ledger.begin(self.grant, value, native(value))

    def test_permit_only_after_readback_and_exact_identity_finish(self):
        first = self.begin(); self.assertFalse(first.replayed); self.assertIsNotNone(first.permit)
        retry = self.begin(); self.assertTrue(retry.replayed); self.assertIsNone(retry.permit)
        self.assertEqual(parse_json(retry.response)['status'], 'UNKNOWN')
        with self.assertRaisesRegex(m.LedgerError, 'PERMIT_REQUIRED'):
            self.ledger.finish(copy.copy(first.permit), response(request()))
        wire = self.ledger.finish(first.permit, response(request()))
        self.assertEqual(self.begin().response, wire)
        self.assertEqual(self.ledger.lookup(self.grant, request().command_id), wire)
        with self.assertRaisesRegex(m.LedgerError, 'PERMIT_REQUIRED'):
            self.ledger.finish(first.permit, response(request()))

    def test_replay_precedes_live_owner_check_even_when_held(self):
        self.begin(); self.owner._check_native.side_effect = RuntimeError('retired owner')
        self.ledger._held = True
        self.assertTrue(self.begin().replayed)
        with self.assertRaisesRegex(m.LedgerError, 'HELD'):
            self.begin(request('new'))

    def test_terminal_failure_retains_owner_and_exact_response_retry(self):
        first = self.begin(); self.backend.failure = 'after'
        with self.assertRaises(m.LedgerError):self.ledger.finish(first.permit, response(request()))
        self.assertTrue(self.ledger._held); self.assertIn(first.permit, self.ledger._permits)
        with self.assertRaisesRegex(m.LedgerError, 'TERMINAL_CONFLICT'):
            self.ledger.finish(first.permit, response(request(), Status.UNKNOWN))
        self.backend.failure = None
        raw = self.ledger.finish(first.permit, response(request()))
        self.assertEqual(self.begin().response, raw)

    def test_redaction_change_denies_admission_and_historical_delivery(self):
        self.owner.sessions.encode_output = lambda value: b'{}'
        with self.assertRaisesRegex(m.LedgerError, 'SENSITIVE_DATA'):self.begin()
        self.assertEqual(len(self.backend._records), 1)
        self.owner.sessions.encode_output = canonical_bytes
        first = self.begin(); self.ledger.finish(first.permit, response(request()))
        before = copy.deepcopy(self.backend._records)
        self.owner.sessions.encode_output = lambda value: b'{}'
        with self.assertRaisesRegex(m.LedgerError, 'SENSITIVE_DATA'):
            self.ledger.lookup(self.grant, request().command_id)
        self.assertEqual(self.backend._records, before)

    def test_new_sensitive_receipt_denies_replay_without_changing_history(self):
        first = self.begin(); self.ledger.finish(first.permit, response(request(), observed_name='private-value'))
        before = copy.deepcopy(self.backend._records)
        def encode(value):
            return b'{}' if value.get('code') == 'TEST_OBSERVED' else canonical_bytes(value)
        self.owner.sessions.encode_output = encode
        with self.assertRaisesRegex(m.LedgerError, 'SENSITIVE_DATA'):self.begin()
        self.assertEqual(self.backend._records, before)

    def test_auth_rejection_and_backend_uncertainty_do_not_return_permits(self):
        self.owner.sessions._check_grant.side_effect = m.LedgerError('DENIED')
        with self.assertRaisesRegex(m.LedgerError, 'DENIED'):self.begin()
        self.assertEqual(len(self.backend._records), 1)
        self.owner.sessions._check_grant.side_effect = None
        self.backend.failure = 'after'
        with self.assertRaises(m.LedgerError):self.begin()
        self.assertTrue(self.ledger._held); self.assertEqual(self.ledger._permits, {})
        self.backend.failure = None
        repeated = self.begin()
        self.assertIsNone(repeated.permit); self.assertEqual(parse_json(repeated.response)['status'], 'UNKNOWN')

    def test_constructor_and_foreign_owner_do_not_create_backend(self):
        with self.assertRaises(TypeError):m.BlenderClientLedger()
        with patch.object(m, '_ClientJournal') as backend:
            with self.assertRaisesRegex(m.LedgerError, 'EXACT_OWNER'):
                m.BlenderClientLedger.from_owner(self.owner)
            backend.assert_not_called()

    def test_guard_release_failure_after_admission_holds_without_issuing_permit(self):
        original_guard = self.backend._writer_lock

        @contextmanager
        def release_failure():
            with original_guard():
                yield
                if len(self.backend._records) == 2:
                    raise OSError('inert native handle release failure')

        with patch.object(self.backend, '_writer_lock', release_failure):
            with self.assertRaisesRegex(m.LedgerError, 'ADMISSION_UNKNOWN') as raised:
                self.begin()
        self.assertTrue(raised.exception.outcome_unknown)
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertTrue(self.ledger._held)
        self.assertEqual(self.ledger._permits, {})
        self.assertEqual(len(self.backend._records), 2)
        self.assertEqual(self.backend._records[-1]['status'], 'ACCEPTED_PENDING')
        retry = self.begin()
        self.assertTrue(retry.replayed)
        self.assertIsNone(retry.permit)
        self.assertEqual(parse_json(retry.response)['status'], 'UNKNOWN')
        self.assertFalse(parse_json(retry.response)['postconditions']['dispatch_permitted'])
        with self.assertRaisesRegex(m.LedgerError, 'HELD'):
            self.begin(request('new-command'))
        self.assertEqual(len(self.backend._records), 2)

    def test_guard_release_failure_after_terminal_retains_exact_retry(self):
        admission = self.begin()
        terminal = response(request())
        expected = canonical_bytes(terminal.as_dict())
        original_guard = self.backend._writer_lock

        @contextmanager
        def release_failure():
            with original_guard():
                yield
                raise OSError('inert terminal guard release failure')

        with patch.object(self.backend, '_writer_lock', release_failure):
            with self.assertRaisesRegex(m.LedgerError, 'TERMINAL_UNKNOWN') as raised:
                self.ledger.finish(admission.permit, terminal)
        self.assertTrue(raised.exception.outcome_unknown)
        self.assertIsInstance(raised.exception.__cause__, OSError)
        self.assertTrue(self.ledger._held)
        self.assertIn(admission.permit, self.ledger._permits)
        self.assertEqual(len(self.backend._records), 3)
        self.assertEqual(self.backend._records[-1]['status'], 'COMMITTED')
        self.assertEqual(self.ledger.finish(admission.permit, terminal), expected)
        self.assertNotIn(admission.permit, self.ledger._permits)
        self.assertEqual(self.begin().response, expected)
        self.assertEqual(len(self.backend._records), 3)


if __name__ == '__main__':
    unittest.main()
