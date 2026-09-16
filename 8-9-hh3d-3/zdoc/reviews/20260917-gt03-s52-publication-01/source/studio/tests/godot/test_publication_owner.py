"""Coordinator boundary regressions with inert owners; native proof is separate."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s52_owner_test',STUDIO/'godot-addon/publication_owner.py')
owner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=owner;spec.loader.exec_module(owner)
auth=owner._load('publication_session')
from studio.protocol.core import Status


class PublicationOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-owner-unit-');self.addCleanup(self.temp.cleanup)
        self.value=object.__new__(owner.GodotPublicationOwner)
        self.value._lock=threading.RLock();self.value._work=threading.Lock()
        self.value.sessions=auth.PublicationSession('project.fixture',Path(self.temp.name),'sha256:'+'1'*64)
        self.value._held=self.value._closed=False
        self.value._editor=self.value._validator=None
        self.value._journal=types.SimpleNamespace(lookup=lambda *_:{'phase':'COMMITTED','receipt_sha256':'2'*64})
        self.record={'status':'COMMITTED','code':'GODOT_MANAGED_SCENE_SAVED','digest':'sha256:'+'3'*64,
            'postconditions':{'public_ack':True,'durable_receipt_sha256':'2'*64}}

    def test_original_reply_requires_current_durable_receipt(self):
        result=self.value._reply('command.save',self.record)
        self.assertEqual(result.status,Status.COMMITTED)
        self.value._journal.lookup=lambda *_:None
        result=self.value._reply('command.save',self.record)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        self.assertTrue(self.value._held)

    def test_different_durable_receipt_cannot_relabel_cached_ack(self):
        self.value._journal.lookup=lambda *_:{'phase':'COMMITTED','receipt_sha256':'4'*64}
        self.assertEqual(self.value._reply('command.save',self.record).status,Status.UNKNOWN)
        self.assertEqual(self.record['status'],'COMMITTED')  # Historical result preserved.

    def test_pending_lookup_does_not_wait_for_disk_effect(self):
        self.value._journal.lookup=lambda *_:(_ for _ in ()).throw(AssertionError('unexpected disk wait'))
        record={'status':'ACCEPTED_PENDING','code':'GODOT_SAVE_PENDING','digest':'sha256:'+'3'*64}
        self.assertEqual(self.value._reply('command.save',record).status,Status.ACCEPTED_PENDING)

    def test_close_stops_before_attempting_child_cleanup_and_retains_failed_owner(self):
        observed=[]
        def close_editor():
            observed.append(self.value.sessions.status()['stopped'])
            raise RuntimeError('inert owned close failure')
        editor=types.SimpleNamespace(close=close_editor)
        self.value._editor=editor
        with self.assertRaises(owner.PublicationOwnerError) as failure:
            self.value.close()
        self.assertEqual(observed,[True])
        self.assertIs(failure.exception.cleanup_owner,self.value)
        self.assertIs(self.value._editor,editor)

    def test_root_instance_strings_are_exact_safe_integers(self):
        self.assertEqual(self.value._instance('123456'),123456)
        for value in (123,True,'01','1e3','0',str(2**53)):
            with self.subTest(value=value),self.assertRaises(owner.PublicationOwnerError):
                self.value._instance(value)

    def test_reserved_phase_revocation_never_calls_effect(self):
        credential=self.value.sessions.issue()
        grant=self.value.sessions.authorize('Bearer '+credential.bearer,'scene.save',
            project_id='project.fixture',catalog_digest='sha256:'+'1'*64)
        lease=self.value.sessions.lease(grant)
        request=types.SimpleNamespace(command_id='command.save',digest='sha256:'+'2'*64,deadline_ms=lease.expires_ms)
        original=self.value.sessions.start_effect
        def revoke_first(permit):
            self.value.sessions.revoke(credential)
            return original(permit)
        self.value.sessions.start_effect=revoke_first
        calls=[]
        with self.assertRaises(auth.SafetyViolation):
            self.value._phase(request,grant,lease,'capture',lambda:calls.append(1))
        self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()
