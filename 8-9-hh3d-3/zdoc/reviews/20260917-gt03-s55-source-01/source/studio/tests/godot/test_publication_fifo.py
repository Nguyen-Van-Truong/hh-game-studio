"""Registered authority and inert concurrency tests; no engine/native proof."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import sys
import tempfile
import threading
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def load(name):
    path = STUDIO / 'godot-addon' / (name + '.py')
    raw = path.read_bytes()
    key = '_hh_fifo_test_' + hashlib.sha256(str(path).encode() + b'\0' + raw).hexdigest()
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


fifo = load('publication_fifo')
session = fifo.session_model
from studio.host.core import transport
from studio.host.core.limits import SafetyViolation
from studio.protocol.core import canonical_bytes


class PublicationFifoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1_800_000_000_000
        self.clock = mock.patch.object(session, 'epoch_ms', side_effect=lambda: self.now)
        self.issuer_clock = mock.patch.object(transport, 'epoch_ms', side_effect=lambda: self.now)
        self.clock.start(); self.issuer_clock.start()
        self.sessions = session.PublicationSession('project.fixture', Path(self.temp.name), 'sha256:' + 'a' * 64)
        self.queue = fifo.PublicationFifo(self.sessions)
        self.credentials = []

    def tearDown(self):
        self.queue.halt()
        self.clock.stop(); self.issuer_clock.stop()
        self.temp.cleanup()

    def grant(self, operations=frozenset({'scene.save', 'control.stop'})):
        credential = self.sessions.issue(operations=operations)
        self.credentials.append(credential)
        return self.sessions.authenticate('Bearer ' + credential.bearer)

    def enqueue(self, grant, name, **kwargs):
        return self.queue.enqueue(grant, request_id=name, ttl_ms=kwargs.get('ttl_ms', 1000), wait_ms=kwargs.get('wait_ms', 5000))

    def test_requires_exact_source_addressed_session_and_single_wrapper(self):
        with self.assertRaisesRegex(SafetyViolation, 'REGISTERED_SESSION_REQUIRED'):
            fifo.PublicationFifo(object())
        with self.assertRaisesRegex(SafetyViolation, 'OWNER_ALREADY_REGISTERED'):
            fifo.PublicationFifo(self.sessions)

    def test_publication_owner_loader_uses_identical_session_authority_class(self):
        owner = load('publication_owner')
        self.assertIs(owner._load('publication_session'), session)
        self.assertIs(owner._load('publication_fifo').session_model.PublicationSession, type(self.sessions))

    def test_copied_mutated_readonly_grants_never_enqueue(self):
        grant = self.grant()
        for forged in (copy.copy(grant), object()):
            with self.assertRaises(SafetyViolation):
                self.enqueue(forged, 'forged')
        reader = self.grant(frozenset({'scene.inspect'}))
        with self.assertRaisesRegex(SafetyViolation, 'OPERATION_FORBIDDEN'):
            self.enqueue(reader, 'reader')
        self.assertEqual(self.queue.snapshot()['retained'], 0)

    def test_fifo_survives_reverse_poll_order_and_incumbent_requeue(self):
        a, b, c = self.grant(), self.grant(), self.grant()
        first = self.enqueue(a, 'a.first')
        self.assertEqual(first['state'], 'GRANTED')
        second = self.enqueue(b, 'b.first')
        third = self.enqueue(c, 'c.first')
        incumbent = self.enqueue(a, 'a.renew')
        self.assertEqual([x['state'] for x in (second, third, incumbent)], ['QUEUED'] * 3)
        self.now += 1001
        self.assertEqual(self.queue.poll(a, incumbent['ticket_id'])['state'], 'QUEUED')
        second_reply = self.queue.poll(b, second['ticket_id'])
        self.assertEqual(second_reply['lease']['fencing_epoch'], 2)
        self.now += 1001
        self.queue.poll(a, incumbent['ticket_id'])
        self.assertEqual(self.queue.poll(c, third['ticket_id'])['lease']['fencing_epoch'], 3)
        self.now += 1001
        self.assertEqual(self.queue.poll(a, incumbent['ticket_id'])['lease']['fencing_epoch'], 4)

    def test_exact_duplicate_never_extends_absolute_wait_or_rearms_grant(self):
        owner, waiter = self.grant(), self.grant()
        self.enqueue(owner, 'owner')
        pending = self.enqueue(waiter, 'waiter', wait_ms=100)
        self.now += 101
        expired = self.enqueue(waiter, 'waiter', wait_ms=100)
        self.assertEqual(expired['wait_deadline_ms'], pending['wait_deadline_ms'])
        self.assertEqual(expired['state'], 'EXPIRED')
        self.now += 2000
        self.assertEqual(self.enqueue(waiter, 'waiter', wait_ms=100), expired)
        with self.assertRaisesRegex(SafetyViolation, 'REQUEST_CONFLICT'):
            self.enqueue(waiter, 'waiter', wait_ms=101)
        self.assertEqual(self.sessions._fence, 1)

    def test_granted_reply_loss_is_exact_but_expired_receipt_is_not_authority(self):
        grant = self.grant()
        result = self.enqueue(grant, 'first')
        lease = self.queue.granted_lease(grant, result['ticket_id'])
        self.assertIs(lease, self.sessions._lease)
        original = canonical_bytes(result)
        result['lease']['fencing_epoch'] = 99
        self.assertEqual(canonical_bytes(self.enqueue(grant, 'first')), original)
        self.now += 1001
        self.assertEqual(canonical_bytes(self.queue.poll(grant, result['ticket_id'])), original)
        with self.assertRaisesRegex(SafetyViolation, 'DEADLINE_EXPIRED'):
            self.queue.granted_lease(grant, result['ticket_id'])
        self.assertEqual(self.sessions._fence, 1)

    def test_cancel_queued_does_not_bypass_remaining_order_or_cancel_granted(self):
        a, b, c = self.grant(), self.grant(), self.grant()
        first = self.enqueue(a, 'a')
        second = self.enqueue(b, 'b')
        third = self.enqueue(c, 'c')
        canceled = self.queue.cancel(b, second['ticket_id'])
        self.assertEqual(canceled['state'], 'CANCELED')
        self.assertEqual(self.queue.cancel(a, first['ticket_id']), first)
        self.now += 1001
        self.assertEqual(self.queue.poll(c, third['ticket_id'])['state'], 'GRANTED')
        self.assertEqual(self.queue.poll(b, second['ticket_id']), canceled)

    def test_expired_or_revoked_head_is_skipped_without_a_grant(self):
        a, b, c = self.grant(), self.grant(), self.grant()
        self.enqueue(a, 'a')
        expired = self.enqueue(b, 'b', wait_ms=50)
        next_row = self.enqueue(c, 'c')
        self.now += 1001
        self.assertEqual(self.queue.poll(c, next_row['ticket_id'])['state'], 'GRANTED')
        self.assertEqual(self.queue.poll(b, expired['ticket_id'])['state'], 'EXPIRED')
        fourth, fifth = self.grant(), self.grant()
        revoked = self.enqueue(fourth, 'fourth')
        following = self.enqueue(fifth, 'fifth')
        self.sessions.revoke(self.credentials[-2])
        self.now += 1001
        self.assertEqual(self.queue.poll(fifth, following['ticket_id'])['state'], 'GRANTED')
        self.assertEqual(self.queue._rows[revoked['ticket_id']]['state'], 'REJECTED')

    def test_queue_full_can_still_grant_head_and_retains_original_tickets(self):
        current = self.grant(); self.enqueue(current, 'current')
        waiting = [(self.grant(), 'wait.' + str(i)) for i in range(fifo.MAX_WAITERS)]
        rows = [self.enqueue(g, name) for g, name in waiting]
        with self.assertRaisesRegex(SafetyViolation, 'QUEUE_FULL'):
            self.enqueue(self.grant(), 'overflow')
        self.now += 1001
        self.assertEqual(self.queue.poll(waiting[0][0], rows[0]['ticket_id'])['state'], 'GRANTED')
        self.assertEqual(self.queue.snapshot()['queued'], 7)
        self.assertEqual(self.queue.snapshot()['retained'], 9)

    def test_total_ticket_budget_rejects_without_dropping_tombstones(self):
        current, waiter = self.grant(), self.grant()
        self.enqueue(current, 'current')
        with mock.patch.object(fifo, 'MAX_TICKETS', 3):
            one = self.enqueue(waiter, 'one'); self.queue.cancel(waiter, one['ticket_id'])
            two = self.enqueue(waiter, 'two'); self.queue.cancel(waiter, two['ticket_id'])
            with self.assertRaisesRegex(SafetyViolation, 'TICKET_LIMIT'):
                self.enqueue(waiter, 'three')
            self.assertEqual(self.queue.poll(waiter, one['ticket_id'])['state'], 'CANCELED')

    def test_waiter_ownership_limits_and_duplicate_request_bindings(self):
        a, b, c = self.grant(), self.grant(), self.grant()
        self.enqueue(a, 'a')
        row = self.enqueue(b, 'b')
        with self.assertRaisesRegex(SafetyViolation, 'WAITER_ALREADY_OWNED'):
            self.enqueue(b, 'b.second')
        for method in (self.queue.poll, self.queue.cancel, self.queue.granted_lease):
            with self.assertRaisesRegex(SafetyViolation, 'TICKET_NOT_OWNED'):
                method(c, row['ticket_id'])
        for kw in ({'ttl_ms': True}, {'wait_ms': 0}, {'wait_ms': fifo.MAX_WAIT_MS + 1}, {'ttl_ms': 90001}):
            with self.assertRaisesRegex(SafetyViolation, 'INVALID_LIMIT'):
                self.enqueue(c, 'invalid', **kw)

    def run_blocked_grant(self, action):
        grant = self.grant()
        entered, release = threading.Event(), threading.Event()
        native = self.sessions.lease
        result = []
        def blocked(*args, **kwargs):
            lease = native(*args, **kwargs)
            entered.set()
            if not release.wait(2):
                raise AssertionError('test release not signaled')
            return lease
        with mock.patch.object(self.sessions, 'lease', side_effect=blocked):
            thread = threading.Thread(target=lambda: result.append(self.enqueue(grant, 'blocked')))
            thread.start()
            self.assertTrue(entered.wait(1))
            ticket = self.queue._requests['blocked']
            try:
                immediate = action(grant, ticket)
            finally:
                release.set(); thread.join(2)
            self.assertFalse(thread.is_alive())
        return grant, ticket, immediate, result[0]

    def test_cancel_during_minted_grant_never_exposes_lease_or_reissues_ticket(self):
        grant, ticket, immediate, result = self.run_blocked_grant(self.queue.cancel)
        self.assertEqual(immediate, result)
        self.assertEqual(result['state'], 'CANCELED')
        self.assertEqual(result['grant_outcome'], 'UNKNOWN')
        self.assertIsNone(result['lease'])
        with self.assertRaisesRegex(SafetyViolation, 'NOT_GRANTED'):
            self.queue.granted_lease(grant, ticket)
        next_grant = self.grant(); waiting = self.enqueue(next_grant, 'next')
        self.assertEqual(waiting['state'], 'QUEUED')
        self.now += 1001
        self.assertEqual(self.queue.poll(next_grant, waiting['ticket_id'])['lease']['fencing_epoch'], 2)
        self.assertEqual(self.enqueue(grant, 'blocked'), result)

    def test_stop_during_grant_latches_native_first_and_keeps_exact_terminal(self):
        def stop(grant, ticket):
            self.queue.stop(grant)
            return self.queue.poll(grant, ticket)
        grant, ticket, immediate, result = self.run_blocked_grant(stop)
        self.assertTrue(self.sessions.status()['stopped'])
        self.assertEqual(result, immediate)
        self.assertEqual(result['state'], 'STOPPED')
        self.assertIsNone(result['lease'])
        self.assertEqual(self.queue.poll(grant, ticket), result)

    def test_lost_native_grant_return_is_unknown_and_never_rearmed(self):
        grant = self.grant(); native = self.sessions.lease
        def lost(*args, **kwargs):
            native(*args, **kwargs)
            raise OSError('inert injected lost native return')
        with mock.patch.object(self.sessions, 'lease', side_effect=lost) as call:
            unknown = self.enqueue(grant, 'unknown')
            self.assertEqual(self.enqueue(grant, 'unknown'), unknown)
            self.assertEqual(call.call_count, 1)
        self.assertEqual(unknown['state'], 'UNKNOWN')
        self.assertIsNone(unknown['lease'])
        waiter = self.grant(); next_row = self.enqueue(waiter, 'next')
        self.assertEqual(next_row['state'], 'QUEUED')
        self.now += 1001
        self.assertEqual(self.queue.poll(waiter, next_row['ticket_id'])['lease']['fencing_epoch'], 2)
        self.assertEqual(self.queue.poll(grant, unknown['ticket_id']), unknown)

    def test_expired_incumbent_with_started_effect_does_not_admit_next_writer(self):
        first, second = self.grant(), self.grant()
        row = self.enqueue(first, 'first')
        lease = self.queue.granted_lease(first, row['ticket_id'])
        permit = self.sessions.reserve_phase(first, lease, command_id='effect', digest='sha256:' + 'b' * 64,
            phase='capture', deadline_ms=self.now + 500, operation='scene.save')
        self.sessions.start_effect(permit)
        pending = self.enqueue(second, 'second')
        self.now += 1001
        self.assertEqual(self.queue.poll(second, pending['ticket_id'])['state'], 'QUEUED')
        self.sessions.finish_effect(permit, known=True)
        self.assertEqual(self.queue.poll(second, pending['ticket_id'])['state'], 'GRANTED')

    def test_external_stop_cancels_waiters_and_terminal_grant_stays_historical(self):
        first, second = self.grant(), self.grant()
        granted = self.enqueue(first, 'first'); pending = self.enqueue(second, 'second')
        self.sessions.stop(first)
        self.assertEqual(self.queue.poll(second, pending['ticket_id'])['state'], 'STOPPED')
        self.assertEqual(self.queue.poll(first, granted['ticket_id']), granted)
        with self.assertRaisesRegex(SafetyViolation, 'STOPPED'):
            self.queue.granted_lease(first, granted['ticket_id'])


if __name__ == '__main__':
    unittest.main()
