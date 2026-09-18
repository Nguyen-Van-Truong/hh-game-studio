"""Persisted FIFO ordering, capacity, terminal IDs and native fence boundaries."""
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
STUDIO=Path(__file__).resolve().parents[2];sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.durable_session import DurableBlenderSession
from studio.host.blender.writer_journal import MAX_WAITERS
from studio.host.core.journal import JournalError,Lease
from studio.host.blender.ui_host import HostError
import test_durable_session as fixture


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-writer-fifo-');self.now=1000
        self.host=fixture.Host();self.host.directory=Path(self.temp.name)
        self.host._api=type('Api',(),{'mkdir':lambda _,path:path.mkdir()})()
        self.a=self.session();self.blocker=self.a.acquire_writer('initial',ttl_ms=100)
        self.b=self.session()
    def session(self):
        return DurableBlenderSession(self.host.directory/'journal',host=self.host,clock=lambda:self.now)
    def tearDown(self):self.temp.cleanup()
    def request(self,session,key,writer,**kwargs):return session.request_writer(key,writer,lease_ms=100,**kwargs)
    def test_two_clients_fifo_reopen_handoff_and_no_legacy_bypass(self):
        self.request(self.a,'first','alice');self.request(self.b,'second','bob')
        with self.assertRaisesRegex(JournalError,'FIFO_REQUIRED'):self.a.acquire_writer('initial')
        self.assertIsNone(self.b.pump_writers())
        self.now=1101
        grant_a=self.b.pump_writers();self.assertEqual(grant_a['ticket_id'],'first')
        self.assertEqual(self.session().writer_status('first','alice'),grant_a)
        self.assertEqual(self.b.writer_status('second','bob')['state'],'WAITING')
        self.now=1202
        grant_b=self.a.pump_writers();self.assertEqual(grant_b['ticket_id'],'second')
        self.assertGreater(grant_b['lease']['fencing_epoch'],grant_a['lease']['fencing_epoch'])
        with self.assertRaisesRegex(JournalError,'STALE_LEASE'):
            self.a.execute_bytes(fixture.command(),Lease(**grant_a['lease']))
        self.b.execute_bytes(fixture.command(),Lease(**grant_b['lease']))
        self.assertEqual(len(self.host.calls),1)
    def test_duplicate_ticket_retains_deadline_conflict_never_requeues(self):
        first=self.request(self.a,'ticket','alice',wait_ms=50)
        self.now=1010;self.assertEqual(self.request(self.b,'ticket','alice',wait_ms=50),first)
        with self.assertRaisesRegex(JournalError,'TICKET_CONFLICT'):self.request(self.b,'ticket','alice',wait_ms=51)
        self.now=1101;self.assertIsNone(self.b.pump_writers())
        ended=self.a.writer_status('ticket','alice');self.assertEqual(ended['state'],'EXPIRED')
        self.assertEqual(self.request(self.b,'ticket','alice',wait_ms=50),ended)
    def test_cancel_head_persists_and_next_waiter_gets_turn(self):
        self.request(self.a,'first','alice');self.request(self.b,'second','bob')
        canceled=self.b.cancel_writer('first','alice');self.assertEqual(canceled['state'],'CANCELED')
        self.assertEqual(self.session().writer_status('first','alice'),canceled)
        self.now=1101;self.assertEqual(self.a.pump_writers()['ticket_id'],'second')
        self.assertEqual(self.b.cancel_writer('first','alice'),canceled)
    def test_queue_capacity_is_bounded_and_rejected_ticket_has_no_record(self):
        for index in range(MAX_WAITERS):self.request(self.a,'ticket-'+str(index),'writer-'+str(index))
        with self.assertRaisesRegex(JournalError,'QUEUE_FULL'):self.request(self.b,'overflow','extra')
        with self.assertRaisesRegex(JournalError,'TICKET_UNKNOWN'):self.b.writer_status('overflow','extra')
        self.a.cancel_writer('ticket-0','writer-0')
        self.assertEqual(self.request(self.b,'overflow','extra')['state'],'WAITING')
        self.now=1101
        self.assertEqual(self.a.pump_writers()['ticket_id'],'ticket-1')
    def test_one_waiting_ticket_per_writer_and_owner_binding(self):
        self.request(self.a,'first','alice')
        with self.assertRaisesRegex(JournalError,'ALREADY_QUEUED'):self.request(self.b,'second','alice')
        with self.assertRaisesRegex(JournalError,'TICKET_OWNER'):self.b.cancel_writer('first','bob')
        self.assertEqual(self.a.writer_status('first','alice')['state'],'WAITING')
    def test_lost_grant_reply_never_rearms_same_ticket(self):
        self.request(self.a,'first','alice');self.now=1101
        with patch.object(self.host,'arm_lease',side_effect=OSError('lost native reply')) as arm:
            with self.assertRaises(OSError):self.a.pump_writers()
        self.assertEqual(arm.call_count,1);self.assertTrue(self.a._held)
        self.assertEqual(self.b.writer_status('first','alice')['state'],'GRANTING')
        self.now=1202;self.assertIsNone(self.b.pump_writers())
        self.assertEqual(self.b.writer_status('first','alice')['state'],'UNKNOWN')
        self.assertEqual(self.request(self.b,'first','alice')['state'],'UNKNOWN')
    def test_cancel_during_grant_does_not_publish_grant_receipt(self):
        self.request(self.a,'first','alice');self.now=1101
        original=self.host.arm_lease
        def cancel(wire):
            self.b.cancel_writer('first','alice');return original(wire)
        with patch.object(self.host,'arm_lease',side_effect=cancel):
            with self.assertRaisesRegex(JournalError,'GRANT_NOT_PENDING'):self.a.pump_writers()
        self.assertEqual(self.b.writer_status('first','alice')['state'],'CANCELED')
        self.assertEqual(self.host.calls,[])
    def test_stop_cancels_waiters_durably_and_blocks_other_session(self):
        self.request(self.a,'first','alice');self.request(self.b,'second','bob')
        self.a.stop();self.assertTrue(self.host.stopped)
        self.assertEqual(self.b.writer_status('second','bob')['reason'],'HOST_STOPPED')
        with self.assertRaisesRegex(JournalError,'WRITER_STOPPED'):self.b.pump_writers()
        with self.assertRaisesRegex(JournalError,'WRITER_STOPPED'):self.b.execute_bytes(fixture.command(),self.blocker)
        self.assertEqual(self.host.calls,[])
    def test_stop_does_not_wait_for_scene_command_lock(self):
        ready=threading.Event();release=threading.Event()
        def hold():
            with self.a._lock:ready.set();release.wait(2)
        thread=threading.Thread(target=hold);thread.start();self.assertTrue(ready.wait(1))
        try:self.assertEqual(self.a.stop(),{'stopped':True,'public_ack':False})
        finally:release.set();thread.join(1)
        self.assertFalse(thread.is_alive())
    def test_concurrent_clients_do_not_lose_either_ticket(self):
        barrier=threading.Barrier(2);errors=[]
        def enqueue(session,key,writer):
            try:barrier.wait(1);self.request(session,key,writer)
            except BaseException as error:errors.append(error)
        threads=[threading.Thread(target=enqueue,args=(self.a,'first','alice')),
                 threading.Thread(target=enqueue,args=(self.b,'second','bob'))]
        for thread in threads:thread.start()
        for thread in threads:thread.join(2)
        self.assertEqual(errors,[]);self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(self.a.writer_status('first','alice')['state'],'WAITING')
        self.assertEqual(self.b.writer_status('second','bob')['state'],'WAITING')
        self.now=1101;first=self.a.pump_writers();self.now=1202;second=self.b.pump_writers()
        self.assertEqual({first['ticket_id'],second['ticket_id']},{'first','second'})
    def test_granted_ticket_cannot_be_canceled_or_renewed_by_retry(self):
        self.request(self.a,'first','alice');self.now=1101;grant=self.a.pump_writers()
        with self.assertRaisesRegex(JournalError,'ALREADY_GRANTED'):self.b.cancel_writer('first','alice')
        self.now=1202;self.assertEqual(self.request(self.b,'first','alice'),grant)
        with self.assertRaisesRegex(JournalError,'STALE_LEASE'):
            self.a.execute_bytes(fixture.command(),Lease(**grant['lease']))


if __name__=='__main__':unittest.main()
