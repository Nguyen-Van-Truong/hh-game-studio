"""Managed registration + native storage/custody, with substituted frame I/O."""
import hashlib
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
from studio.protocol.core import Discovery, PROTOCOL_VERSION, Request, Status, canonical_bytes
from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.limits import SafetyViolation, payload_digest
from studio.host.core.managed_fixture import ManagedFixtureOwner
from studio.host.core.pipe_endpoint import AppContainerEndpoint
from studio.host.core.pipe_io import PipeIOError
from studio.host.core.safe_open import capabilities
from studio.host.core.selector_contract import (SELECTOR_DESCRIPTOR, SELECTOR_SCHEMA_DIGEST,
                                                SELECTOR_SCOPE, SELECTOR_INSPECT_MAX_BYTES)
from studio.host.core.selector_pipe import SelectorFixtureBroker, SelectorPipeServer
from studio.host.core.transport import epoch_ms


def fixture_frame(credential, route, body):
    # Public selector adds /v1/inspect; the older fixture-only helper has a
    # narrower route allowlist. Exercise actual frame parsing for every route.
    return ('Bearer '+credential.bearer+'\n'+route+'\n').encode('ascii')+canonical_bytes(body)


@unittest.skipUnless(os.name == 'nt', 'Windows protected managed fixture required')
class SelectorPublicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-public-selector-')
        self.addCleanup(self.temp.cleanup)
        self.owner = ManagedFixtureOwner.create(self.temp.name, project_id='public-fixture',
            initial_revisions={'source_revision':'source-0','source_sha256':'a'*64,'game_revision':'game-0'})
        self.storage_id = self.owner.storage_id
        self.addCleanup(self.delete_leaf)
        self.addCleanup(lambda: self.owner.close())
        self.broker = SelectorFixtureBroker.from_managed(self.owner)
        self.addCleanup(lambda: self.broker.close())
        self.work = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='work')
        self.addCleanup(self.work.close)
        self.control = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role='control')
        self.addCleanup(self.control.close)
        self.set_credential(frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))

    def delete_leaf(self):
        import winreg
        # Only the UUID created by this test. No shared-parent deletion.
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, BASE_PATH+'\\'+self.storage_id, winreg.KEY_WOW64_64KEY)

    def set_credential(self, scopes):
        self.credential = self.broker.sessions.issue(scopes=scopes)
        self.server = SelectorPipeServer(self.work, self.broker, self.credential)
        self.control_server = SelectorPipeServer(self.control, self.broker, self.credential)

    def rpc(self, route, body, *, control=False, raw=None):
        endpoint, server = (self.control, self.control_server) if control else (self.work, self.server)
        wire = fixture_frame(self.credential, route, body) if raw is None else raw
        with mock.patch.object(endpoint, 'read_frame', return_value=wire), mock.patch.object(endpoint, 'write_frame') as send:
            server.serve_one()
        self.assertEqual(send.call_count, 1)
        result = send.call_args.args[0]
        self.assertNotIn(self.credential.bearer.encode(), result)
        return json.loads(result)

    def metadata_request(self):
        return {'project_id':self.owner.project_id,'protocol_version':PROTOCOL_VERSION}

    def observe(self):
        return (self.owner.log.binding().witnessed, self.owner.registry.read(),
                sorted(path.name for path in self.owner.store.root.iterdir()),
                sorted(path.name for path in self.owner.files.root.iterdir()))

    def request(self, name='public.one', value='one'):
        lease = self.rpc('/v1/lease', {'project_id':self.owner.project_id,'ttl_ms':30_000})
        self.assertIn('lease_id', lease)
        state = self.rpc('/v1/inspect', self.metadata_request(), control=True)
        payload = {'assets':{'scene':{'value':value,'references':[]}},'entrypoint':'scene',
                   'expected_generation':state['generation'],'expected_selection_hash':state['selection_hash'],
                   **{'expected_'+key:value for key,value in state['revisions'].items()}}
        target, operation = {'stable_id':'active-release'}, 'fixture.release.activate'
        return Request(name,self.owner.project_id,operation,lease['lease_id'],lease['fencing_epoch'],
                       state['revisions']['game_revision'],target,payload,
                       payload_digest(operation,target,payload,'hh-studio-0.1'),epoch_ms()+10_000).as_dict()

    def activate(self, request):
        self.assertEqual(self.rpc('/v1/commands', request)['status'],'ACCEPTED_PENDING')
        results = [self.broker.advance() for _ in range(3)]
        self.assertEqual([result.status for result in results],[Status.ACCEPTED_PENDING,Status.UNKNOWN,Status.COMMITTED])
        return results[-1].as_dict()

    def reopen(self):
        self.broker.close()
        self.owner.close()
        self.owner = ManagedFixtureOwner.reopen(self.storage_id, project_id='public-fixture', now_ms=epoch_ms())
        self.broker = SelectorFixtureBroker.from_managed(self.owner)
        self.set_credential(frozenset({'fixture.read','fixture.write','control.stop','control.cancel'}))

    def test_discovery_exact_digest_finite_scope_and_metadata_have_no_event_effect(self):
        before = self.observe()
        discovery = Discovery.from_dict(self.rpc('/v1/discovery', self.metadata_request()))
        self.assertEqual(discovery.schema_digest, SELECTOR_SCHEMA_DIGEST)
        self.assertEqual(SELECTOR_SCHEMA_DIGEST, 'sha256:'+hashlib.sha256(canonical_bytes(SELECTOR_DESCRIPTOR)).hexdigest())
        self.assertEqual({cap.operation for cap in discovery.capabilities}, {'fixture.release.activate','fixture.release.inspect'})
        for cap in discovery.capabilities:
            self.assertEqual(cap.write_scopes if cap.operation.endswith('activate') else cap.read_scopes, (SELECTOR_SCOPE,))
            self.assertTrue(cap.limits and all(type(value) is int and value > 0 for value in cap.limits.values()))
        state = self.rpc('/v1/inspect', self.metadata_request(), control=True)
        self.assertEqual(set(state), set(SELECTOR_DESCRIPTOR['operations']['fixture.release.inspect']['fields']))
        self.assertEqual((state['generation'],state['ready'],state['pending_command']), (0,False,None))
        self.assertLessEqual(len(canonical_bytes(state)), SELECTOR_INSPECT_MAX_BYTES)
        self.assertEqual(self.observe(), before)
        self.assertFalse(capabilities()['safe_write'])
        self.assertFalse(capabilities()['atomic_replace'])

    def test_internal_broker_and_unbound_or_closed_owner_cannot_register(self):
        self.broker.close()
        for invalid in (object(), {'owner':self.owner}, ManagedFixtureOwner()):
            with self.subTest(kind=type(invalid).__name__), self.assertRaises(SafetyViolation):
                SelectorFixtureBroker.from_managed(invalid)
        with mock.patch.object(self.owner.log, '_custody', None):
            with self.assertRaisesRegex(SafetyViolation, 'MANAGED_BINDING_INVALID'):
                SelectorFixtureBroker.from_managed(self.owner)
        self.broker = SelectorFixtureBroker(self.owner.selector)
        self.set_credential(frozenset({'fixture.read','fixture.write'}))
        before = self.observe()
        self.assertEqual(self.rpc('/v1/discovery',self.metadata_request())['code'],'SELECTOR_NOT_REGISTERED')
        self.assertEqual(self.rpc('/v1/inspect',self.metadata_request(),control=True)['code'],'SELECTOR_NOT_REGISTERED')
        self.assertEqual(self.observe(), before)
        self.broker.close()
        self.owner.close()
        with self.assertRaisesRegex(SafetyViolation, 'MANAGED_BINDING_INVALID'):
            SelectorFixtureBroker.from_managed(self.owner)

    def test_authentication_revocation_roles_and_versions_reject_without_events(self):
        before = self.observe()
        with mock.patch('studio.host.core.selector_pipe.parse_json_utf8', side_effect=AssertionError('unauthenticated parse')):
            result = self.rpc('',{},raw=b'Bearer '+b'x'*43+b'\n/v1/discovery\n{broken')
        self.assertEqual(result['code'],'AUTH_REQUIRED')
        for route,control in (('/v1/discovery',False),('/v1/inspect',True)):
            for change,expected in (({'protocol_version':'2.0'},'UNSUPPORTED_VERSION'),
                                    ({'project_id':'other'},'PROJECT_MISMATCH'),({'extra':1},'INVALID_ENVELOPE')):
                with self.subTest(route=route,change=change):
                    self.assertEqual(self.rpc(route,{**self.metadata_request(),**change},control=control)['code'],expected)
            self.assertEqual(self.rpc(route,self.metadata_request(),control=not control)['code'],'UNSUPPORTED_ROUTE')
        self.broker.sessions.revoke(self.credential)
        self.assertEqual(self.rpc('/v1/discovery',self.metadata_request())['code'],'AUTH_REQUIRED')
        self.assertEqual(self.rpc('/v1/inspect',self.metadata_request(),control=True)['code'],'AUTH_REQUIRED')
        self.assertEqual(self.observe(),before)

    def test_read_only_session_sees_only_inspect_and_cannot_lease(self):
        self.set_credential(frozenset({'fixture.read'}))
        before = self.observe()
        discovery = Discovery.from_dict(self.rpc('/v1/discovery',self.metadata_request()))
        self.assertEqual([cap.operation for cap in discovery.capabilities],['fixture.release.inspect'])
        self.assertIn('generation',self.rpc('/v1/inspect',self.metadata_request(),control=True))
        self.assertEqual(self.rpc('/v1/lease',{'project_id':self.owner.project_id,'ttl_ms':1000})['code'],'SCOPE_DENIED')
        self.set_credential(frozenset({'fixture.write'}))
        self.assertEqual(self.rpc('/v1/inspect',self.metadata_request(),control=True)['code'],'SCOPE_DENIED')
        self.assertEqual(self.observe(),before)

    def test_managed_public_mutation_has_actual_readback_and_custody_then_inspect_omits_assets(self):
        secret_content = 'inert-source-text-must-not-appear-in-inspect'
        first = self.activate(self.request(value=secret_content))
        first_version, raw = self.owner.files.read('active.json')
        self.assertEqual(json.loads(raw)['assets']['scene']['value'],secret_content)
        self.assertEqual(self.owner.custody.binding.witnessed,self.owner.log.binding().witnessed)
        state = self.rpc('/v1/inspect',self.metadata_request(),control=True)
        self.assertTrue(state['ready'])
        self.assertEqual(state['selected']['manifest_sha256'],first['postconditions']['manifest_sha256'])
        encoded = canonical_bytes(state)
        for forbidden in (secret_content, self.storage_id, str(self.owner.files.root), str(self.owner.store.root),
                          self.owner.files.root_identity.file_id, 'object_id', 'assets', 'handle', BASE_PATH):
            self.assertNotIn(forbidden.encode(),encoded)
        second_request = self.request('public.two','replacement')
        second = self.activate(second_request)
        second_version, actual = self.owner.files.read('active.json')
        self.assertFalse(first_version.identity.same_file(second_version.identity))
        self.assertEqual(json.loads(actual)['assets']['scene']['value'],'replacement')
        before = self.observe()
        self.assertEqual(self.rpc('/v1/commands',second_request),second)
        self.assertEqual(self.observe(),before)
        self.assertEqual(self.owner.custody.binding.witnessed,self.owner.log.binding().witnessed)

    def test_readonly_restart_and_held_or_stopped_broker_never_advertise_write(self):
        # No committed file exists, so a valid restart remains read-only.
        self.reopen()
        before = self.observe()
        discovery = Discovery.from_dict(self.rpc('/v1/discovery',self.metadata_request()))
        self.assertEqual([cap.operation for cap in discovery.capabilities],['fixture.release.inspect'])
        self.assertEqual(self.rpc('/v1/lease',{'project_id':self.owner.project_id,'ttl_ms':1000})['code'],
                         'SAFE_REOPEN_REQUIRES_RECONCILIATION')
        self.assertEqual(self.observe(),before)
        self.broker._hold.set()
        discovery = Discovery.from_dict(self.rpc('/v1/discovery',self.metadata_request()))
        self.assertFalse(discovery.supports('fixture.release.activate'))
        self.assertEqual(self.observe(),before)
        self.owner.selector.stop()
        after_stop = self.observe()
        self.assertTrue(self.rpc('/v1/inspect',self.metadata_request(),control=True)['stopped'])
        self.assertFalse(Discovery.from_dict(self.rpc('/v1/discovery',self.metadata_request())).supports('fixture.release.activate'))
        self.assertEqual(self.observe(),after_stop)

    def test_pending_restart_advertises_no_write_and_never_pumps_old_work(self):
        request = self.request()
        self.assertEqual(self.rpc('/v1/commands',request)['status'],'ACCEPTED_PENDING')
        self.reopen()
        before = self.observe()
        self.assertFalse(Discovery.from_dict(self.rpc('/v1/discovery',self.metadata_request())).supports('fixture.release.activate'))
        state = self.rpc('/v1/inspect',self.metadata_request(),control=True)
        self.assertEqual(state['pending_command'],request['command_id'])
        self.assertIsNone(self.broker.advance())
        self.assertEqual(self.observe(),before)

    def test_registration_is_rechecked_after_custody_detaches(self):
        before = self.observe()
        with mock.patch.object(self.owner.log, '_custody', None):
            result = self.rpc('/v1/discovery',self.metadata_request())
            self.assertEqual(result['code'],'SELECTOR_MANAGED_BINDING_INVALID')
            result = self.rpc('/v1/lease',{'project_id':self.owner.project_id,'ttl_ms':1000})
            self.assertEqual(result['code'],'SELECTOR_MANAGED_BINDING_INVALID')
        self.assertEqual(self.observe(),before)

    def test_job_wake_precedes_failed_response_and_service_owns_close(self):
        request = self.request()
        def fail_response(*args, **kwargs):
            self.assertTrue(self.broker._wake.is_set())
            self.assertEqual(self.broker._job.command_id,request['command_id'])
            raise PipeIOError('PIPE_BROKEN',delivery_unknown=True)
        with mock.patch.object(self.work,'read_frame',return_value=fixture_frame(self.credential,'/v1/commands',request)), \
             mock.patch.object(self.work,'write_frame',side_effect=fail_response):
            with self.assertRaises(PipeIOError):
                self.server.serve_one()
        with self.owner._lifecycle_lock:
            self.broker._service_owner = object()
            try:
                with self.assertRaisesRegex(SafetyViolation,'SELECTOR_SERVICE_ACTIVE'):
                    self.broker.close()
                self.assertFalse(self.broker._closed)
            finally:
                self.broker._service_owner = None

    def test_authorized_stop_signals_before_waiting_for_managed_binding_lock(self):
        request = self.request()
        self.assertEqual(self.rpc('/v1/commands',request)['status'],'ACCEPTED_PENDING')
        results, failures = [], []
        def stop():
            try:
                results.append(self.rpc('/v1/stop',{'project_id':self.owner.project_id,
                    'command_id':request['command_id']},control=True))
            except BaseException as exc:
                failures.append(exc)
        with self.owner.selector._mutex:
            worker = threading.Thread(target=stop,daemon=True)
            worker.start()
            signaled = self.owner.selector._stop_requested.wait(2)
            canceled = self.broker._job.cancel.is_set()
            blocked = worker.is_alive()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures,[])
        self.assertTrue(signaled)
        self.assertTrue(canceled)
        self.assertTrue(blocked)
        self.assertTrue(results[0]['stopped'])

    def test_revoked_control_cannot_signal_stop_or_cancel(self):
        request = self.request()
        self.assertEqual(self.rpc('/v1/commands',request)['status'],'ACCEPTED_PENDING')
        self.broker.sessions.revoke(self.credential)
        before = self.observe()
        for route in ('/v1/stop','/v1/cancel'):
            self.assertEqual(self.rpc(route,{'project_id':self.owner.project_id,
                'command_id':request['command_id']},control=True)['code'],'AUTH_REQUIRED')
        self.assertFalse(self.broker._job.cancel.is_set())
        self.assertFalse(self.owner.selector._stop_requested.is_set())
        self.assertEqual(self.observe(),before)


if __name__ == '__main__':
    unittest.main()
