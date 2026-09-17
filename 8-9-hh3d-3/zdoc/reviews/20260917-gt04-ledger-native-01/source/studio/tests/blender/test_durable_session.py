"""Durability and stale-writer tests for the narrow internal Blender session."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
from studio.host.blender.durable_session import DurableBlenderSession,PROJECT,queue,response_bytes
from studio.host.blender.ui_host import HostError
from studio.host.core.journal import JournalError


def command(key='create'):
    return {'schema':queue.SCHEMA,'command_id':key,'operation':'mesh.create_box',
        'expected_revision':'sha256:'+'1'*64,
        'expected_context':{'mode':'OBJECT','active_id':None,'selected_ids':[]},
        'payload':{'object_id':'box','size':[1,1,1]}}


class Host:
    _session='a'*32
    def __init__(self):self.calls=[];self.lease=None;self.stopped=False
    def arm_lease(self,lease):self.lease=dict(lease);return dict(lease)
    def execute(self,value,*,lease):
        self.calls.append(copy.deepcopy(value))
        return {'command_id':value['command_id'],'command_digest':queue.c.digest(value),
            'state':'COMPLETED','result':{'observed':'native-fixture-double'},'public_ack':False}
    def stop(self):self.stopped=True;return {'stopped':True,'public_ack':False}


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-blender-durable-')
        self.root=Path(self.temp.name)/'journal';self.host=Host();self.now=1000
        self.host.directory=self.root.parent
        self.host._api=type('Api',(),{'mkdir':lambda _,path:path.mkdir()})()
        self.session=DurableBlenderSession(self.root,host=self.host,clock=lambda:self.now)
        self.lease=self.session.acquire_writer('writer',ttl_ms=1000)
    def tearDown(self):self.temp.cleanup()
    def test_exact_terminal_bytes_reopen_without_native_dispatch(self):
        raw=self.session.execute_bytes(command(),self.lease)
        self.assertEqual(json.loads(raw)['status'],'COMMITTED')
        reopened=DurableBlenderSession(self.root,clock=lambda:self.now)
        self.assertEqual(reopened.lookup_bytes('create'),raw)
        self.assertEqual(reopened.execute_bytes(command(),None),raw)
        self.assertEqual(len(self.host.calls),1)
    def test_conflicting_duplicate_has_no_effect(self):
        self.session.execute_bytes(command(),self.lease)
        changed=command();changed['payload']['size']=[2,1,1]
        with self.assertRaisesRegex(HostError,'CONFLICT'):self.session.execute_bytes(changed,self.lease)
        self.assertEqual(len(self.host.calls),1)
    def test_stale_lease_rejected_before_intent(self):
        self.session.acquire_writer('writer',ttl_ms=1000)
        with self.assertRaisesRegex(JournalError,'STALE_LEASE'):self.session.execute_bytes(command(),self.lease)
        with self.assertRaisesRegex(JournalError,'NOT_FOUND'):self.session.lookup_bytes('create')
        self.assertEqual(self.host.calls,[])
    def test_second_writer_busy_then_new_fence_after_expiry(self):
        with self.assertRaisesRegex(JournalError,'LEASE_BUSY'):self.session.acquire_writer('other',ttl_ms=1000)
        self.now=2001
        next_lease=self.session.acquire_writer('other',ttl_ms=1000)
        self.assertGreater(next_lease.fencing_epoch,self.lease.fencing_epoch)
        with self.assertRaisesRegex(JournalError,'STALE_LEASE'):self.session.execute_bytes(command(),self.lease)
    def test_lost_native_reply_is_durable_unknown_and_never_reexecuted(self):
        with patch.object(self.host,'execute',side_effect=OSError('reply lost')) as native:
            raw=self.session.execute_bytes(command(),self.lease)
        self.assertEqual(native.call_count,1);self.assertEqual(json.loads(raw)['status'],'UNKNOWN')
        self.assertEqual(self.session.execute_bytes(command(),self.lease),raw)
        self.assertEqual(DurableBlenderSession(self.root,clock=lambda:self.now).lookup_bytes('create'),raw)
    def test_death_after_intent_is_lookup_unknown_without_dispatch(self):
        with patch.object(self.host,'execute',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.session.execute_bytes(command(),self.lease)
        reopened=DurableBlenderSession(self.root,clock=lambda:self.now)
        raw=reopened.lookup_bytes('create')
        self.assertEqual(json.loads(raw)['reason'],'UNRESOLVED_DURABLE_INTENT')
        self.assertEqual(reopened.execute_bytes(command(),None),raw);self.assertEqual(self.host.calls,[])
    def test_terminal_persistence_failure_cannot_return_success(self):
        with patch.object(self.session.journal,'finish_command',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.session.execute_bytes(command(),self.lease)
        self.assertTrue(self.session._held);self.assertEqual(len(self.host.calls),1)
        raw=DurableBlenderSession(self.root,clock=lambda:self.now).lookup_bytes('create')
        self.assertEqual(json.loads(raw)['status'],'UNKNOWN')
        self.assertEqual(self.session.execute_bytes(command(),self.lease),raw);self.assertEqual(len(self.host.calls),1)
    def test_different_native_generation_cannot_resume_old_journal(self):
        other=Host();other._session='b'*32
        other.directory=self.host.directory;other._api=self.host._api
        with self.assertRaisesRegex(HostError,'DIFFERENT_GENERATION'):
            DurableBlenderSession(self.root,host=other,clock=lambda:self.now)
        self.assertEqual(other.calls,[])
    def test_response_tamper_is_rejected(self):
        self.session.execute_bytes(command(),self.lease)
        saved=self.session.journal.lookup(project_id=PROJECT,command_id='create',now_ms=self.now)['receipt']
        saved['wire_chunks'][0]=saved['wire_chunks'][0].replace('COMMITTED','REJECTED')
        with self.assertRaisesRegex(HostError,'BINDING'):response_bytes(saved)
    def test_stop_refuses_new_commands_but_retains_original_bytes(self):
        raw=self.session.execute_bytes(command(),self.lease);self.session.stop()
        self.assertTrue(self.host.stopped);self.assertEqual(self.session.execute_bytes(command(),None),raw)
        with self.assertRaisesRegex(HostError,'HELD'):self.session.execute_bytes(command('second'),self.lease)


class QueueFenceTests(unittest.TestCase):
    def setUp(self):
        self.now=1000;self.calls=[]
        self.q=queue.CommandQueue(lambda cmd:self.calls.append(cmd) or {},lease_clock=lambda:self.now)
        self.lease={'fencing_epoch':1,'expires_ms':2000};self.q.arm_lease(self.lease)
    def test_late_old_lease_after_rotation_never_dispatches(self):
        self.q.submit(queue.c.canonical(command()),lease=self.lease)
        self.q.arm_lease({'fencing_epoch':2,'expires_ms':2500});self.q.tick()
        self.assertEqual(self.calls,[]);self.assertEqual(self.q.result('create')['state'],'REJECTED')
    def test_lease_expired_while_queued_never_dispatches(self):
        self.q.submit(queue.c.canonical(command()),lease=self.lease);self.now=2000;self.q.tick()
        self.assertEqual(self.calls,[]);self.assertEqual(self.q.result('create')['reason'],'WRITER_FENCED_OR_EXPIRED')
    def test_unleased_bypass_and_boolean_fence_rejected(self):
        with self.assertRaisesRegex(queue.c.Rejected,'FENCED'):self.q.submit(queue.c.canonical(command()))
        with self.assertRaisesRegex(queue.c.Rejected,'INVALID_WRITER'):
            self.q.submit(queue.c.canonical(command()),lease=dict(self.lease,fencing_epoch=True))
    def test_old_arm_cannot_lower_high_water(self):
        self.q.arm_lease({'fencing_epoch':2,'expires_ms':2500})
        with self.assertRaisesRegex(queue.c.Rejected,'STALE_WRITER'):self.q.arm_lease(self.lease)


if __name__=='__main__':unittest.main()
