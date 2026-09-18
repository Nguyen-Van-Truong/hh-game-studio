"""Actual HTTP/auth/lease boundaries with an inert recovery backend, not engine proof."""
from dataclasses import asdict
import http.client
import importlib.util
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
spec=importlib.util.spec_from_file_location('s54_recovery_host_test',STUDIO/'godot-addon/recovery_host.py')
host=importlib.util.module_from_spec(spec);sys.modules[spec.name]=host;spec.loader.exec_module(host)
from studio.protocol.core import Response,Status,canonical_bytes,parse_json
session=host._load('publication_session')


class RecoveryHostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hh-recovery-host-unit-');self.addCleanup(self.temp.cleanup)
        value=self.value=object.__new__(host.GodotRecoveryHost)
        value._lock=threading.RLock();value._work=threading.Lock()
        value._closed=value._held=False;value._attempt=None;value._lease=None
        value._cleanup=[];value.project_id='project.fixture'
        value._editor_parent=Path(self.temp.name);value._binary=Path(self.temp.name)/'inert.exe'
        value.sessions=session.PublicationSession(value.project_id,Path(self.temp.name),host.CATALOG_DIGEST,
                                                 minimum_fencing_epoch=100)
        self.credential=value.sessions.issue(operations=host.GRANTS)
        self.args={'authorization':'Bearer '+self.credential.bearer,'catalog_digest':host.CATALOG_DIGEST}
        self.lease=value.lease({'project_id':value.project_id,'ttl_ms':30000},**self.args)
        self.body={'project_id':value.project_id,'command_id':'command.original','digest':'sha256:'+'2'*64,
            'lease_id':self.lease['lease_id'],'fencing_epoch':self.lease['fencing_epoch'],
            'deadline_ms':self.lease['expires_ms']-1}
        self.response=Response(Status.REJECTED,'GODOT_RECOVERED_LAST_GOOD','command.original',
            postconditions={'request_digest':self.body['digest'],'recovery_complete':True,
                            'public_ack':False,'new_mutation_permitted':False})
        self.raw=canonical_bytes(self.response.as_dict())
        self.value.model=types.SimpleNamespace(ReconciliationAuthority=Mock(return_value=object()))
        value._recovery=Mock()
        value._recovery._journal.recovered_response.return_value=self.raw
        value._recovery._journal.snapshot.return_value={'stopped':False,'recovery':{'attempts':[]}}
        def persist_stop(**kwargs):
            value._recovery._journal.snapshot.return_value['stopped']=True
        value._recovery._journal.stop_recovery.side_effect=persist_stop
        def drain():
            thread=getattr(value,'_stop_thread',None)
            if thread is not None:thread.join(4)
        self.addCleanup(drain)

    def test_new_fence_and_durable_response_retry_after_stop(self):
        self.assertEqual(self.lease['fencing_epoch'],101)
        first=self.value.reconcile(self.body,**self.args)
        self.assertEqual(canonical_bytes(first.as_dict()),self.raw)
        self.value.sessions.halt()
        second=self.value.reconcile(self.body,**self.args)
        self.assertEqual(second,first)
        self.value._recovery.reconcile.assert_called_once()

    def test_invalid_shape_scope_fence_and_deadline_do_not_reach_recovery(self):
        for changes in ({'path':'elsewhere'},{'fencing_epoch':True},{'lease_id':'other'},
                        {'deadline_ms':1},{'digest':'bad'},{'project_id':'project.other'}):
            with self.subTest(changes=changes),self.assertRaises(host.SafetyViolation):
                self.value.reconcile({**self.body,**changes},**self.args)
        reader=self.value.sessions.issue(operations=frozenset({'control.lookup'}))
        with self.assertRaises(host.SafetyViolation):
            self.value.reconcile(self.body,authorization='Bearer '+reader.bearer,catalog_digest=host.CATALOG_DIGEST)
        self.value._recovery.reconcile.assert_not_called()
        self.assertIsNone(self.value._attempt)

    def test_response_loss_after_durable_terminal_replays_exact_bytes(self):
        self.value._recovery.reconcile.side_effect=OSError('inert lost return')
        self.assertEqual(self.value.reconcile(self.body,**self.args),self.response)
        self.assertTrue(self.value._held)
        self.assertEqual(self.value.reconcile(self.body,**self.args),self.response)
        self.value._recovery.reconcile.assert_called_once()

    def test_failed_recovery_without_terminal_is_unknown_and_keeps_owner(self):
        self.value._recovery.reconcile.side_effect=OSError('inert engine start failure')
        self.value._recovery._journal.recovered_response.side_effect=ValueError('no terminal')
        result=self.value.reconcile(self.body,**self.args)
        self.assertEqual(result.status,Status.UNKNOWN)
        self.assertFalse(result.postconditions['public_ack'])
        resource=self.value._recovery
        resource.close.side_effect=OSError('inert close failure')
        with self.assertRaises(host.RecoveryHostError) as error:self.value.close()
        self.assertIs(error.exception.cleanup_owner,self.value)
        self.assertIs(self.value._recovery,resource)
        resource.close.side_effect=None;self.value.close()
        self.assertIsNone(self.value._recovery)

    def test_terminal_tamper_cannot_return_cached_ack(self):
        self.value.reconcile(self.body,**self.args)
        self.value._recovery._journal.recovered_response.return_value=self.raw+b' '
        response=self.value.lookup({'project_id':self.value.project_id,'command_id':self.body['command_id']},**self.args)
        self.assertEqual(response.status,Status.UNKNOWN)
        self.assertTrue(self.value._held)

    def test_changed_command_or_digest_is_conflict(self):
        self.value.reconcile(self.body,**self.args)
        for changes in ({'command_id':'command.other'},{'digest':'sha256:'+'3'*64}):
            with self.assertRaisesRegex(host.SafetyViolation,'COMMAND_CONFLICT'):
                self.value.reconcile({**self.body,**changes},**self.args)
        self.value._recovery.reconcile.assert_called_once()

    def test_fresh_host_restores_verified_terminal_before_lookup_or_retry(self):
        self.value._recovery._journal.snapshot.return_value={'recovery':{'attempts':[
            {'phase':'TERMINAL','command_id':self.body['command_id'],'digest':self.body['digest']}]}}
        self.value._restore_terminal()
        result=self.value.lookup({'project_id':self.value.project_id,'command_id':self.body['command_id']},**self.args)
        self.assertEqual(result,self.response)
        # Restored duplicate does not require the old lease/deadline to live.
        retry=self.value.reconcile({**self.body,'deadline_ms':1},**self.args)
        self.assertEqual(retry,self.response)
        self.value._recovery.reconcile.assert_not_called()

    def test_busy_close_error_retains_exact_host(self):
        self.value._work=Mock()
        self.value._work.acquire.return_value=False
        with self.assertRaises(host.RecoveryHostError) as error:self.value.close()
        self.assertIs(error.exception.cleanup_owner,self.value)
        self.value._recovery.close.assert_not_called()

    def test_reopened_durable_stop_disables_discovery_and_new_lease(self):
        self.value._recovery._journal.snapshot.return_value={'stopped':True,'recovery':{'attempts':[]}}
        self.value._restore_terminal()
        discovery=self.value.discover({'project_id':self.value.project_id},**self.args)
        self.assertFalse(discovery['runtime_enabled']);self.assertTrue(discovery['durable_stopped'])
        self.assertEqual(discovery['stop_persistence'],'DURABLE')
        with self.assertRaisesRegex(host.SafetyViolation,'DURABLY_STOPPED'):
            self.value.lease({'project_id':self.value.project_id,'ttl_ms':10000},**self.args)
        with self.assertRaisesRegex(host.SafetyViolation,'DURABLY_STOPPED'):
            self.value.reconcile(self.body,**self.args)
        self.value._recovery.reconcile.assert_not_called()

    def test_stop_drain_failure_never_claims_persisted_and_keeps_owner(self):
        resource=self.value._recovery
        resource._journal.stop_recovery.side_effect=OSError('inert fsync failure')
        reply=self.value.stop({'project_id':self.value.project_id,'command_id':'stop.one'},**self.args)
        self.assertTrue(reply['stopped'])
        self.value._stop_thread.join(3)
        self.assertEqual(self.value._stop_persistence,'UNKNOWN')
        self.assertFalse(getattr(self.value,'_durable_stopped',False))
        self.assertIs(self.value._recovery,resource)

    def test_blocked_historical_lookup_does_not_block_stop(self):
        self.value.reconcile(self.body,**self.args)
        entered=threading.Event();release=threading.Event();result=[]
        def blocked(*args):
            entered.set()
            if not release.wait(3):raise TimeoutError('inert receipt read')
            return self.raw
        self.value._recovery._journal.recovered_response.side_effect=blocked
        body={'project_id':self.value.project_id,'command_id':self.body['command_id']}
        worker=threading.Thread(target=lambda:result.append(self.value.lookup(body,**self.args)))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            stopped=self.value.stop(body,**self.args)
            self.assertTrue(stopped['stopped'])
            self.assertFalse(release.is_set());self.assertTrue(worker.is_alive())
        finally:release.set();worker.join(4)
        self.assertFalse(worker.is_alive());self.assertEqual(result,[self.response])

    def test_actual_socket_stop_and_pending_lookup_do_not_wait_on_work(self):
        server=host.RecoveryTransport(self.value).start();self.addCleanup(server.close)
        entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def paused(*args,**kwargs):
            entered.set()
            if not release.wait(3):raise TimeoutError('inert deadline')
        self.value._recovery.reconcile.side_effect=paused
        def call(path,body,control=False):
            conn=http.client.HTTPConnection('127.0.0.1',server.control_port if control else server.port,timeout=3)
            try:
                conn.request('POST',path,canonical_bytes(body),{'Content-Type':'application/json',
                    'Authorization':self.args['authorization'],'X-HH-Catalog':host.CATALOG_DIGEST})
                result=conn.getresponse();return result.status,parse_json(result.read())
            finally:conn.close()
        responses=[];worker=threading.Thread(target=lambda:responses.append(call('/v1/reconcile',self.body)))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            control={'project_id':self.value.project_id,'command_id':self.body['command_id']}
            self.value._recovery._journal.recovered_response.reset_mock()
            code,pending=call('/v1/lookup',control,True)
            self.assertEqual((code,pending['status']),(200,'ACCEPTED_PENDING'))
            self.value._recovery._journal.recovered_response.assert_not_called()
            code,stopped=call('/v1/stop',control,True)
            self.assertEqual(code,200);self.assertTrue(stopped['stopped'])
            code,rejected=call('/v1/commands',self.body)
            self.assertEqual((code,rejected['code']),(400,'UNSUPPORTED_ROUTE'))
            code,rejected=call('/v1/reconcile',self.body,True)
            self.assertEqual((code,rejected['code']),(400,'UNSUPPORTED_ROUTE'))
        finally:
            release.set();worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(responses[0][0],200)


if __name__=='__main__':unittest.main()
