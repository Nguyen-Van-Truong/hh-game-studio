"""Real private selector/storage, substituted frame boundary; not OS auth proof."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.selector_pipe import SelectorFixtureBroker, SelectorPipeServer
from studio.host.core.fixture_pipe import fixture_frame
from studio.host.core.fixture_selector import FixtureSelector, FixtureReleaseConsumer, SelectorError
from studio.host.core.private_events import PrivateEventLog, EventLogError
from studio.host.core.private_store import PrivateBlobStore
from studio.host.core.pipe_endpoint import AppContainerEndpoint
from studio.host.core.pipe_io import PipeIOError
from studio.host.core.transport import epoch_ms
from studio.host.core.limits import Request, payload_digest, SafetyViolation
from studio.protocol.core import Status


@unittest.skipUnless(os.name == 'nt', 'Windows private fixture required')
class SelectorPipeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='gt02-selector-rpc-')))
        self.log = self.stack.enter_context(PrivateEventLog.create(self.root))
        self.store = self.stack.enter_context(PrivateBlobStore.create(self.root))
        self.consumer = FixtureReleaseConsumer('project.fixture')
        self.selector = FixtureSelector(self.log, self.store, self.consumer, project_id='project.fixture',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        self.stack.callback(lambda: self.selector.close())
        self.broker = SelectorFixtureBroker(self.selector)
        self.stack.callback(lambda: self.broker.close())
        self.credential = self.broker.sessions.issue(scopes=frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))
        self.work = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='work')
        self.control = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='control')
        self.stack.callback(self.work.close); self.stack.callback(self.control.close)
        self.server = SelectorPipeServer(self.work, self.broker, self.credential)
        self.control_server = SelectorPipeServer(self.control, self.broker, self.credential)
        self.body = {'project_id':'project.fixture','command_id':'activation.one'}
        self.lease = self.rpc('/v1/lease', {'project_id':'project.fixture','ttl_ms':30_000})

    def rpc(self, route, body, *, control=False, credential=None, raw=None):
        endpoint, server = (self.control, self.control_server) if control else (self.work, self.server)
        wire = raw if raw is not None else fixture_frame(credential or self.credential, route, body)
        with mock.patch.object(endpoint, 'read_frame', return_value=wire), mock.patch.object(endpoint, 'write_frame') as send:
            server.serve_one()
            self.assertEqual(send.call_count, 1)
            data = send.call_args.args[0]
            self.assertNotIn(self.credential.bearer.encode(), data)
            return json.loads(data)

    def request(self, *, value='inert'):
        snap = self.selector.snapshot()
        payload = {'assets':{'scene':{'value':value,'references':['leaf']},'leaf':{'value':1,'references':[]}},
                   'entrypoint':'scene','expected_generation':snap['generation'],
                   'expected_selection_hash':snap['selection_hash'],
                   **{'expected_'+k:v for k,v in snap['revisions'].items()}}
        operation, target = 'fixture.release.activate', {'stable_id':'active-release'}
        return Request('activation.one','project.fixture',operation,self.lease['lease_id'],self.lease['fencing_epoch'],
                       snap['revisions']['game_revision'],target,payload,
                       payload_digest(operation,target,payload,'hh-studio-0.1'),epoch_ms()+10_000).as_dict()

    def test_admission_and_three_phases_have_one_durable_receipt(self):
        request = self.request()
        self.assertEqual(self.rpc('/v1/commands',request)['status'],'ACCEPTED_PENDING')
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),0)
        phases = [self.broker.advance() for _ in range(3)]
        self.assertEqual([p.status for p in phases],[Status.ACCEPTED_PENDING,Status.UNKNOWN,Status.COMMITTED])
        receipt = self.rpc('/v1/lookup',self.body,control=True)
        self.assertEqual(receipt, self.rpc('/v1/commands',request))
        self.assertEqual(receipt['status'],'COMMITTED')
        self.assertEqual(self.consumer.adoption_count,1)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),3)
        self.assertTrue(self.selector.snapshot()['ready'])

    def test_auth_before_parse_and_session_binding_rejects_another_valid_token(self):
        other = self.broker.sessions.issue()
        before = self.log.binding().witnessed
        for header, expected in [('Bearer '+'x'*43,'AUTH_REQUIRED'),('Bearer '+other.bearer,'SESSION_BINDING_MISMATCH')]:
            with mock.patch('studio.host.core.selector_pipe.parse_json_utf8') as parser:
                response = self.rpc('',{},raw=(header+'\n/v1/commands\n{broken').encode())
                self.assertEqual(response['code'],expected); parser.assert_not_called()
        self.assertEqual(self.log.binding().witnessed,before)

    def test_wrong_project_role_scope_and_lease_never_stage(self):
        request = self.request(); before = self.log.binding().witnessed
        for change in ({'project_id':'other'},{'fencing_epoch':self.lease['fencing_epoch']+1}):
            self.assertEqual(self.rpc('/v1/commands',{**request,**change})['status'],'REJECTED')
        self.assertEqual(self.rpc('/v1/commands',request,control=True)['code'],'UNSUPPORTED_ROUTE')
        self.assertEqual(self.rpc('/v1/stop',self.body)['code'],'UNSUPPORTED_ROUTE')
        read = self.broker.sessions.issue()
        self.server = SelectorPipeServer(self.work,self.broker,read)
        self.assertEqual(self.rpc('/v1/commands',request,credential=read)['code'],'SCOPE_DENIED')
        self.assertEqual(self.log.binding().witnessed,before)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),0)

    def test_lease_belongs_to_session_even_with_stolen_public_lease_fields(self):
        request=self.request(); other=self.broker.sessions.issue(scopes=frozenset({'fixture.read','fixture.write'}))
        self.server=SelectorPipeServer(self.work,self.broker,other)
        self.assertEqual(self.rpc('/v1/commands',request,credential=other)['code'],'SELECTOR_STALE_LEASE')
        self.assertIsNone(self.selector.lookup('activation.one'))

    def test_rotation_before_next_phase_cancels_without_consumer_effect(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance()
        self.broker.sessions.rotate(self.credential)
        self.assertEqual(self.broker.advance().status,Status.CANCELED)
        self.assertIsNone(self.consumer.readback())
        self.assertEqual(self.selector.snapshot()['generation'],0)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),3)

    def test_revocation_after_selection_holds_unknown_until_explicit_recovery(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance(); self.broker.advance()
        self.broker.sessions.revoke(self.credential)
        self.assertEqual(self.broker.advance().status,Status.UNKNOWN)
        self.assertTrue(self.broker._hold.is_set())
        self.assertIsNone(self.consumer.readback())
        self.assertEqual(self.selector.lookup('activation.one')['phase'],'SELECTED')

    def test_cancel_after_staging_preserves_files_without_selection(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance()
        result=self.rpc('/v1/cancel',self.body,control=True)
        self.assertEqual(result['status'],'CANCELED')
        self.assertEqual(result['postconditions'],{'selection_effect':False,'staging_may_exist':True})
        self.assertEqual(self.broker.advance().as_dict(),result)
        self.assertEqual(self.selector.snapshot()['generation'],0)
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),3)

    def test_durable_stop_returns_work_receipt_and_duplicate_never_resumes(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance()
        result=self.rpc('/v1/stop',self.body,control=True)
        self.assertTrue(result['stopped']); self.assertIsNone(result['pending_command'])
        self.assertEqual(result['command']['status'],'CANCELED')
        head=self.log.binding().witnessed
        self.assertEqual(self.rpc('/v1/stop',self.body,control=True),result)
        self.assertEqual(self.log.binding().witnessed,head)
        self.assertEqual(self.rpc('/v1/lease',{'project_id':'project.fixture','ttl_ms':1000})['code'],'SELECTOR_STOPPED')

    def test_stop_after_selection_keeps_unknown_and_restore_is_local_only(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance(); self.broker.advance()
        reply=self.rpc('/v1/stop',self.body,control=True)
        self.assertTrue(reply['stopped']); self.assertEqual(reply['command']['status'],'UNKNOWN')
        raw=('Bearer '+self.credential.bearer+'\n/v1/reconcile\n'+json.dumps(self.body)).encode()
        self.assertEqual(self.rpc('',{},raw=raw,control=True)['code'],'UNSUPPORTED_ROUTE')
        self.selector.reconcile('activation.one','restore',now_ms=epoch_ms())
        final=self.rpc('/v1/lookup',self.body,control=True)
        self.assertEqual(final['code'],'FIXTURE_ACTIVATION_RESTORED')
        self.assertEqual(self.selector.snapshot()['generation'],2)

    def test_lost_pending_reply_can_lookup_and_execute_only_one_activation(self):
        request=self.request(); wire=fixture_frame(self.credential,'/v1/commands',request)
        with mock.patch.object(self.work,'read_frame',return_value=wire), \
             mock.patch.object(self.work,'write_frame',side_effect=PipeIOError('PIPE_BROKEN',delivery_unknown=True)):
            with self.assertRaises(PipeIOError): self.server.serve_one()
        self.assertEqual(self.rpc('/v1/lookup',self.body,control=True)['status'],'ACCEPTED_PENDING')
        for _ in range(3): self.broker.advance()
        self.assertEqual(self.rpc('/v1/commands',request)['status'],'COMMITTED')
        self.assertEqual(self.consumer.adoption_count,1)

    def test_new_broker_does_not_pump_inherited_pending_intent(self):
        self.rpc('/v1/commands',self.request())
        self.broker.close()
        self.broker=SelectorFixtureBroker(self.selector)
        self.credential=self.broker.sessions.issue()
        self.control_server=SelectorPipeServer(self.control,self.broker,self.credential)
        self.assertIsNone(self.broker.advance())
        self.assertEqual(self.rpc('/v1/lookup',self.body,control=True)['status'],'UNKNOWN')
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),0)

    def test_bearer_in_inert_payload_is_rejected_before_persistent_intent(self):
        old=self.credential.bearer
        self.credential=self.broker.sessions.rotate(self.credential)
        self.server=SelectorPipeServer(self.work,self.broker,self.credential)
        for secret in (old,self.credential.bearer):
            result=self.rpc('/v1/commands',self.request(value=secret))
            self.assertEqual(result['code'],'SENSITIVE_INPUT_FORBIDDEN')
            self.assertNotIn(secret.encode(),b''.join(self.broker._diagnostics))
            for sequence in range(1,self.log.binding().witnessed.sequence+1):
                self.assertNotIn(secret.encode(),self.log.read(sequence).event)
        self.assertIsNone(self.selector.lookup('activation.one'))

    def test_uncertain_intent_error_is_unknown_and_holds_admission(self):
        with mock.patch.object(self.selector,'prepare',side_effect=EventLogError('EVENT_APPEND_UNKNOWN',outcome_unknown=True)):
            result=self.rpc('/v1/commands',self.request())
        self.assertEqual(result['status'],'UNKNOWN'); self.assertTrue(self.broker._hold.is_set())
        self.assertEqual(self.rpc('/v1/commands',self.request())['code'],'SELECTOR_RECONCILIATION_REQUIRED')

    def test_control_auth_is_available_during_admitted_storage_phase(self):
        self.rpc('/v1/commands',self.request())
        entered, release, stopped = threading.Event(),threading.Event(),threading.Event()
        errors=[]; original=self.selector._stage_capacity
        def blocking(payload):
            original(payload); entered.set()
            if not release.wait(5): raise TimeoutError('bounded storage test gate')
        def pump():
            try: self.broker.advance()
            except SafetyViolation as exc: errors.append(exc.code)
        def stop():
            try: self.rpc('/v1/stop',self.body,control=True)
            except BaseException as exc: errors.append(type(exc).__name__)
            finally: stopped.set()
        with mock.patch.object(self.selector,'_stage_capacity',side_effect=blocking):
            worker=threading.Thread(target=pump,daemon=True); worker.start()
            try:
                self.assertTrue(entered.wait(5))
                control=threading.Thread(target=stop,daemon=True); control.start()
                self.assertTrue(self.selector._stop_requested.wait(5))
            finally:
                release.set(); worker.join(5)
                if 'control' in locals(): control.join(5)
        self.assertTrue(stopped.is_set()); self.assertEqual(errors,['SELECTOR_STOPPED'])
        self.assertEqual(len(list(self.store.root.glob('blob-*'))),0)
        self.assertEqual(self.selector.lookup('activation.one')['status'],'CANCELED')

    def test_broker_ownership_cannot_transfer_during_active_phase(self):
        with self.assertRaisesRegex(SafetyViolation,'SELECTOR_BROKER_ALREADY_BOUND'):
            SelectorFixtureBroker(self.selector)
        with self.broker._pump:
            with self.assertRaisesRegex(SafetyViolation,'SELECTOR_BROKER_BUSY'):
                self.broker.close()
        self.assertIs(self.selector._pipe_broker,self.broker)
        old=self.broker; old.close()
        self.broker=SelectorFixtureBroker(self.selector)
        with self.assertRaisesRegex(SafetyViolation,'SELECTOR_BROKER_CLOSED'):
            old.advance()

    def test_cancel_rechecks_phase_after_waiting_for_storage(self):
        self.rpc('/v1/commands',self.request()); self.broker.advance()
        started=threading.Event(); replies=[]
        def cancel():
            started.set(); replies.append(self.rpc('/v1/cancel',self.body,control=True))
        with self.selector._mutex:
            thread=threading.Thread(target=cancel,daemon=True); thread.start()
            self.assertTrue(started.wait(5))
            self.selector.select('activation.one',now_ms=epoch_ms())
        thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(replies[0]['status'],'UNKNOWN')
        self.assertEqual(replies[0]['code'],'CANCEL_TOO_LATE_LOOKUP')
        self.assertEqual(self.selector.lookup('activation.one')['phase'],'SELECTED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
