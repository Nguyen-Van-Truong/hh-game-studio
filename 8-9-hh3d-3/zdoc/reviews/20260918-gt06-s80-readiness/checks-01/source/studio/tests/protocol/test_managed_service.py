"""Real custody/storage and service threads; substituted endpoint peer/I/O.

These exercise lifecycle ownership and races, not the OS AppContainer boundary.
The separate native runner supplies that proof on the same frozen closure.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.managed_fixture import ManagedFixtureOwner
from studio.host.core.managed_service import ManagedPipeService, ManagedServiceError
from studio.host.core.pipe_endpoint import AppContainerEndpoint
from studio.host.core.pipe_io import PipeIOError
from studio.host.core.selector_pipe import SelectorFixtureBroker
from studio.host.core.transport import TransportLimits, epoch_ms
from studio.host.core.limits import Request, payload_digest, SafetyViolation
from studio.protocol.core import canonical_bytes, PROTOCOL_VERSION


@unittest.skipUnless(os.name == 'nt', 'Windows managed custody/storage required')
class ManagedServiceTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-service-')
        self.stack.callback(self.temp.cleanup)
        self.owner = ManagedFixtureOwner.create(self.temp.name, project_id='project.fixture',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        storage_id = self.owner.storage_id
        def delete_registry():
            import winreg
            winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, BASE_PATH+'\\'+storage_id, winreg.KEY_WOW64_64KEY)
        self.stack.callback(delete_registry)
        self.stack.callback(self.owner.close)
        self.broker = SelectorFixtureBroker.from_managed(self.owner,
            limits=TransportLimits(request_timeout_ms=5000))
        self.stack.callback(self.broker.close)
        self.credential = self.broker.sessions.issue(scopes=frozenset(
            {'fixture.read','fixture.write','control.stop','control.cancel'}))
        self.work = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7',role='work')
        self.control = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7',role='control')
        self.stack.callback(self.work.close)
        self.stack.callback(self.control.close)
        self.queues, self.replies = {}, {}
        self.release = threading.Event()
        self.stack.callback(self.release.set)
        for endpoint in (self.work,self.control):
            endpoint._identity = (123,456)
            self.stack.enter_context(mock.patch.object(endpoint,'_check_peer'))
            requests, replies = queue.Queue(), queue.Queue()
            self.queues[endpoint.role], self.replies[endpoint.role] = requests, replies
            def read(*, timeout_ms, endpoint=endpoint, requests=requests):
                deadline = time.monotonic()+timeout_ms/1000
                while not endpoint._pipe._stop.is_set():
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        raise PipeIOError('PIPE_TIMEOUT')
                    try:
                        value = requests.get(timeout=min(remaining,.01))
                    except queue.Empty:
                        continue
                    if isinstance(value, BaseException):
                        raise value
                    return value
                raise PipeIOError('PIPE_STOPPED')
            self.stack.enter_context(mock.patch.object(endpoint,'read_frame',side_effect=read))
            self.stack.enter_context(mock.patch.object(endpoint,'write_frame',side_effect=
                lambda data, timeout_ms, replies=replies: replies.put(json.loads(data))))
        self.service = None
        # Service must drain before restoring its mocked frame boundaries.
        self.stack.callback(self.close_service)

    def close_service(self):
        self.release.set()
        if self.service is not None:
            self.service.close()

    def create(self, **kwargs):
        self.service = ManagedPipeService(self.owner,self.broker,self.work,self.control,self.credential,**kwargs)
        return self.service

    def start(self, **kwargs):
        self.create(**kwargs).start()
        bootstrap = self.replies['work'].get(timeout=2)
        self.assertEqual(bootstrap, {'schema':'hh-selector-session-1','project_id':'project.fixture',
            'session_id':self.credential.session_id,'expires_ms':self.credential.expires_ms,
            'scopes':sorted(self.credential.scopes),'bearer':self.credential.bearer})

    def send(self, route, body, *, control=False):
        role = 'control' if control else 'work'
        self.queues[role].put(('Bearer '+self.credential.bearer+'\n'+route+'\n').encode()+canonical_bytes(body))

    def rpc(self, route, body, *, control=False):
        self.send(route,body,control=control)
        result = self.replies['control' if control else 'work'].get(timeout=3)
        self.assertNotIn(self.credential.bearer, json.dumps(result))
        return result

    def inspect(self):
        return self.rpc('/v1/inspect',{'project_id':'project.fixture','protocol_version':PROTOCOL_VERSION},control=True)

    def request(self):
        state = self.inspect()
        lease = self.rpc('/v1/lease',{'project_id':'project.fixture','ttl_ms':30_000})
        payload = {'assets':{'scene':{'value':'service','references':[]}},'entrypoint':'scene',
            'expected_generation':state['generation'],'expected_selection_hash':state['selection_hash'],
            **{'expected_'+key:value for key,value in state['revisions'].items()}}
        target = {'stable_id':'active-release'}
        return Request('cmd.service','project.fixture','fixture.release.activate',lease['lease_id'],lease['fencing_epoch'],
            state['revisions']['game_revision'],target,payload,
            payload_digest('fixture.release.activate',target,payload,'hh-studio-0.1'),epoch_ms()+10000).as_dict()

    def wait_for(self, predicate):
        deadline = time.monotonic()+3
        while not predicate():
            if time.monotonic()>=deadline:
                self.fail('bounded lifecycle condition did not complete')
            threading.Event().wait(.005)

    def test_constructor_rejects_identity_mismatch_without_transfer(self):
        self.control._identity=(123,457)
        with self.assertRaisesRegex(SafetyViolation,'SERVICE_ENDPOINT_BINDING_MISMATCH'):
            self.create()
        self.assertIsNone(self.owner._service)
        self.assertIsNone(self.broker._service_owner)
        self.assertFalse(self.work._closed)

    def test_late_read_cannot_dispatch_before_watchdog_observes_expiry(self):
        self.create()
        before=self.owner.log.binding().witnessed
        self.send('/v1/lease',{'project_id':'project.fixture','ttl_ms':1000})
        with mock.patch.object(self.broker,'dispatch') as dispatch:
            with self.assertRaisesRegex(SafetyViolation,'SELECTOR_SESSION_DEADLINE'):
                self.service._work_server.serve_one(deadline=time.monotonic()-1)
            dispatch.assert_not_called()
        self.assertEqual(self.owner.log.binding().witnessed,before)

    def test_owner_and_broker_cannot_close_beneath_unstarted_service(self):
        self.create()
        with self.assertRaisesRegex(SafetyViolation,'MANAGED_FIXTURE_SERVICE_ACTIVE'):
            self.owner.close()
        with self.assertRaisesRegex(SafetyViolation,'SELECTOR_SERVICE_ACTIVE'):
            self.broker.close()
        self.service.close()
        self.assertIsNone(self.owner._service)
        self.assertEqual(self.service.status()['live_threads'],0)
        self.owner.close()

    def test_bootstrap_once_and_clean_shutdown_retain_durable_owner(self):
        self.start()
        self.assertEqual(self.service.status()['live_threads'],4)
        with self.assertRaisesRegex(SafetyViolation,'SERVICE_ALREADY_STARTED_OR_CLOSED'):
            self.service.start()
        result=self.rpc('/v1/discovery',{'project_id':'project.fixture','protocol_version':PROTOCOL_VERSION})
        self.assertEqual(result['server'],'gt02-managed-selector')
        self.service.close()
        self.assertTrue(self.service.status()['closed'])
        self.assertEqual(self.service.status()['live_threads'],0)
        self.assertIsNotNone(self.owner.selector)
        self.assertEqual(self.owner.custody.binding.witnessed,self.owner.log.binding().witnessed)

    def test_job_runs_while_accepted_reply_is_blocked_and_control_remains_live(self):
        self.start()
        request=self.request()
        blocked=threading.Event()
        original=self.work.write_frame.side_effect
        def delayed(data,*,timeout_ms):
            value=json.loads(data)
            if value.get('status')=='ACCEPTED_PENDING':
                blocked.set()
                self.release.wait(3)
            original(data,timeout_ms=timeout_ms)
        self.work.write_frame.side_effect=delayed
        self.send('/v1/commands',request)
        self.assertTrue(blocked.wait(2))
        self.wait_for(lambda:self.owner.selector.lookup('cmd.service').get('status')=='COMMITTED')
        lookup=self.rpc('/v1/lookup',{'project_id':'project.fixture','command_id':'cmd.service'},control=True)
        self.assertEqual(lookup['status'],'COMMITTED')
        self.assertTrue(self.inspect()['ready'])
        self.assertEqual(self.owner.consumer.adoption_count,1)
        self.release.set()
        self.assertEqual(self.replies['work'].get(timeout=2)['status'],'ACCEPTED_PENDING')

    def test_work_failure_holds_admission_but_preserves_control_stop(self):
        self.start()
        self.queues['work'].put(PipeIOError('PIPE_DISCONNECTED'))
        self.wait_for(lambda:self.service.status()['work_failed'])
        self.assertFalse(self.service.status()['session_ended'])
        self.assertFalse(self.inspect()['stopped'])
        stop=self.rpc('/v1/stop',{'project_id':'project.fixture','command_id':'cmd.none'},control=True)
        self.assertTrue(stop['stopped'])
        self.assertTrue(self.owner.selector.snapshot()['stopped'])
        self.assertTrue(self.broker._hold.is_set())

    def test_lost_accepted_reply_holds_after_admitted_phase_without_replay(self):
        self.start()
        request=self.request()
        entered=threading.Event()
        stage=self.owner.selector.stage
        def delayed(*args,**kwargs):
            entered.set()
            self.release.wait(3)
            return stage(*args,**kwargs)
        send=self.work.write_frame.side_effect
        def lose(data,*,timeout_ms):
            if json.loads(data).get('status')=='ACCEPTED_PENDING':
                if not entered.wait(2):
                    raise AssertionError('admitted phase never reached')
                raise PipeIOError('PIPE_WRITE_FAILED',delivery_unknown=True)
            send(data,timeout_ms=timeout_ms)
        self.work.write_frame.side_effect=lose
        with mock.patch.object(self.owner.selector,'stage',side_effect=delayed) as call:
            self.send('/v1/commands',request)
            self.assertTrue(entered.wait(2))
            self.wait_for(lambda:self.service.status()['work_failed'])
            self.release.set()
            self.wait_for(lambda:self.owner.selector.lookup('cmd.service').get('phase')=='STAGED')
            response=self.rpc('/v1/lookup',{'project_id':'project.fixture','command_id':'cmd.service'},control=True)
            self.assertEqual(response['status'],'UNKNOWN')
            self.assertEqual(call.call_count,1)
            self.assertEqual(self.owner.consumer.adoption_count,0)
            self.assertIsNone(self.owner.selector.snapshot()['selected'])
        stopped=self.rpc('/v1/stop',{'project_id':'project.fixture','command_id':'cmd.service'},control=True)
        self.assertTrue(stopped['stopped'])
        self.assertEqual(stopped['command']['status'],'CANCELED')

    def test_control_failure_revokes_rotated_session_and_stops_work(self):
        self.start()
        rotated=self.broker.sessions.rotate(self.credential)
        self.queues['control'].put(PipeIOError('PIPE_DISCONNECTED'))
        self.wait_for(lambda:self.service.status()['session_ended'])
        with self.assertRaises(SafetyViolation):
            self.broker.sessions.authenticate('Bearer '+rotated.bearer)
        self.wait_for(lambda:self.service.status()['live_threads']==0)
        self.assertTrue(self.work._pipe._stop.is_set())

    def test_close_timeout_retains_entire_chain_until_blocked_phase_finishes(self):
        self.start(drain_timeout_ms=40)
        request=self.request()
        entered=threading.Event()
        original=self.owner.selector.stage
        def delayed(*args,**kwargs):
            entered.set()
            self.release.wait(3)
            return original(*args,**kwargs)
        with mock.patch.object(self.owner.selector,'stage',side_effect=delayed):
            self.send('/v1/commands',request)
            self.assertTrue(entered.wait(2))
            begin=time.monotonic()
            with self.assertRaises(ManagedServiceError) as raised:
                self.service.close()
            self.assertEqual(raised.exception.code,'SERVICE_DRAIN_PENDING')
            self.assertLess(time.monotonic()-begin,.5)
            self.assertIs(raised.exception.cleanup_owner,self.service)
            self.assertIs(self.owner._service,self.service)
            self.assertFalse(self.work._closed)
            self.assertIs(self.owner.selector._pipe_broker,self.broker)
            with self.assertRaises(SafetyViolation):
                self.owner.close()
            self.release.set()
            self.wait_for(lambda:self.service.status()['live_threads']==0)
        self.service.close()
        self.assertTrue(self.service.status()['closed'])
        self.assertEqual(self.owner.selector.lookup('cmd.service')['phase'],'STAGED')
        self.assertEqual(self.owner.consumer.adoption_count,0)

    def test_endpoint_close_failure_preserves_owner_and_retries_same_handle(self):
        self.create()
        handle=self.work._pipe._handle
        with mock.patch.object(self.work,'close',side_effect=PipeIOError('PIPE_CLEANUP_PENDING')):
            with self.assertRaisesRegex(ManagedServiceError,'SERVICE_ENDPOINT_CLEANUP_PENDING'):
                self.service.close()
        self.assertEqual(self.work._pipe._handle,handle)
        self.assertIs(self.broker._service_owner,self.service)
        with self.assertRaises(SafetyViolation):
            self.owner.close()
        self.service.close()
        self.assertTrue(self.work._closed)

    def test_bootstrap_delivery_failure_keeps_cleanup_owner_without_readers(self):
        self.create()
        self.work.write_frame.side_effect=PipeIOError('PIPE_TIMEOUT',delivery_unknown=True)
        with self.assertRaises(ManagedServiceError) as raised:
            self.service.start()
        self.assertIs(raised.exception.cleanup_owner,self.service)
        self.assertEqual(self.service.status()['live_threads'],0)
        self.assertTrue(self.service.status()['session_ended'])
        self.service.close()

    def test_partial_thread_start_failure_drains_the_started_thread(self):
        self.create()
        start=threading.Thread.start
        count=0
        def partial(thread):
            nonlocal count
            count+=1
            if count==2:
                raise RuntimeError('simulated thread resource exhaustion')
            return start(thread)
        with mock.patch.object(threading.Thread,'start',partial):
            with self.assertRaisesRegex(ManagedServiceError,'SERVICE_START_FAILED'):
                self.service.start()
        self.service.close()
        self.assertEqual(self.service.status()['live_threads'],0)

    def test_deadline_revokes_admission_even_while_phase_pump_is_blocked(self):
        self.start(session_timeout_ms=1000)
        request=self.request()
        entered=threading.Event()
        stage=self.owner.selector.stage
        def delayed(*args,**kwargs):
            entered.set()
            self.release.wait(3)
            return stage(*args,**kwargs)
        with mock.patch.object(self.owner.selector,'stage',side_effect=delayed):
            self.send('/v1/commands',request)
            self.assertTrue(entered.wait(2))
            self.wait_for(lambda:self.service.status()['session_ended'])
            self.assertEqual(self.service.status()['reason'],'SERVICE_SESSION_EXPIRED')
            self.assertTrue(self.broker._hold.is_set())
            with self.assertRaises(SafetyViolation):
                self.broker.sessions.authenticate('Bearer '+self.credential.bearer)
            self.assertTrue(self.work._pipe._stop.is_set())
            self.assertTrue(self.control._pipe._stop.is_set())
            self.assertGreater(self.service.status()['live_threads'],0)
            self.release.set()
            self.wait_for(lambda:self.service.status()['live_threads']==0)
        self.assertIsNone(self.owner.selector.snapshot()['selected'])
        self.assertEqual(self.owner.consumer.adoption_count,0)

    def test_idle_session_deadline_ends_all_threads(self):
        self.start(session_timeout_ms=80)
        self.wait_for(lambda:self.service.status()['live_threads']==0)
        self.assertEqual(self.service.status()['reason'],'SERVICE_SESSION_EXPIRED')
        self.assertTrue(self.service.status()['session_ended'])
        self.service.close()


if __name__=='__main__':
    unittest.main(verbosity=2)
