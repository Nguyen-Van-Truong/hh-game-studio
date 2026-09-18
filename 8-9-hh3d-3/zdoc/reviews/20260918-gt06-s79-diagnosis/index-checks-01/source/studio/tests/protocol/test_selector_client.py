"""Real connected pipes + managed broker; no peer-binding/sandbox claim."""
from dataclasses import replace
from contextlib import ExitStack
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.protocol.core import Discovery, Response, Status, canonical_bytes
from studio.host.core.limits import SafetyViolation, parse_json_utf8
from studio.host.core.managed_fixture import ManagedFixtureOwner
from studio.host.core.managed_service import ManagedPipeService
from studio.host.core.pipe_endpoint import AppContainerEndpoint
from studio.host.core.custody_registry import BASE_PATH
from studio.host.core.pipe_io import OwnedPipe, PipeIOError
from studio.host.core import pipe_io as native_pipe_io
from studio.host.core.selector_pipe import SelectorFixtureBroker
from studio.host.core.selector_client import (ManagedFixtureClient, SelectorClientError, SelectorSnapshot,
    SelectorLease, SelectorStopResult, pending_selector_client_cleanup, parse_bootstrap)
from studio.host.core.transport import epoch_ms
import test_pipe_io


@unittest.skipUnless(os.name == 'nt', 'Windows managed broker and real pipes required')
class SelectorClientTests(unittest.TestCase):
    def setUp(self):
        self.native_before = set(native_pipe_io._OWNERS)
        self.addCleanup(lambda: self.assertEqual(set(native_pipe_io._OWNERS), self.native_before))
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-selector-client-')
        self.addCleanup(self.temp.cleanup)
        self.owner = ManagedFixtureOwner.create(self.temp.name, project_id='project-one', initial_revisions={
            'source_revision': 'source-0', 'source_sha256': 'a' * 64, 'game_revision': 'game-0'})
        self.addCleanup(self.remove_registry)
        self.addCleanup(self.owner.close)
        self.broker = SelectorFixtureBroker.from_managed(self.owner)
        self.addCleanup(self.broker.close)
        self.credential = self.broker.sessions.issue(scopes=frozenset({
            'fixture.read', 'fixture.write', 'control.stop', 'control.cancel'}))

        class NativePairs(test_pipe_io.PipeIOTests):
            # Reuse the existing real CreateNamedPipe/CreateFile pair helper,
            # adopting into the same package namespace as the typed client.
            def retain(fixture, handle):
                try:
                    pipe = OwnedPipe._adopt(handle, cancel_grace_ms=30)
                except BaseException:
                    fixture.k.CloseHandle(handle)
                    raise
                fixture.owners.append(pipe)
                return pipe
        self.pairs = NativePairs()
        self.pairs.setUp()
        self.addCleanup(self.pairs.tearDown)
        self.work_server, work = self.pairs.pair()
        self.control_server, control = self.pairs.pair()
        self.client = ManagedFixtureClient(work, control, self.credential, timeout_ms=800)
        self.addCleanup(self.client.close)

    def remove_registry(self):
        import winreg
        path = BASE_PATH + '\\' + self.owner.storage_id
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_WOW64_64KEY) as key:
            value, kind = winreg.QueryValueEx(key, 'Format')
        self.assertEqual((value, kind), (b'hh-registry-custody-1\0' + self.owner.storage_id.encode(), winreg.REG_BINARY))
        winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, path, winreg.KEY_WOW64_64KEY, 0)

    def serve(self, *, control=False, reply=None, drop=False, entered=None, release=None):
        pipe = self.control_server if control else self.work_server
        raw = pipe.read_frame(timeout_ms=2000)
        authorization, route, body = raw.split(b'\n', 2)
        session = self.broker.sessions.authenticate(authorization.decode('ascii'))
        self.assertEqual(session.credential, self.credential)
        value = self.broker.dispatch(route.decode('ascii'), parse_json_utf8(body), session, control=control)
        if entered is not None:
            entered.set()
            self.assertTrue(release.wait(2))
        if drop:
            pipe.close()
            return
        if reply is not None:
            encoded = reply
        else:
            encoded = canonical_bytes(value.as_dict() if hasattr(value, 'as_dict') else value)
        pipe.write_frame(encoded, timeout_ms=2000)

    def rpc(self, action, *, control=False, reply=None, drop=False):
        errors = []
        def serve():
            try:
                self.serve(control=control, reply=reply, drop=drop)
            except BaseException as exc:
                errors.append(exc)
        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            return action()
        finally:
            thread.join(3)
            self.assertFalse(thread.is_alive())
            if errors:
                raise errors[0]

    def request(self, identifier='activation-one'):
        self.assertIsInstance(self.rpc(self.client.discover), Discovery)
        snapshot = self.rpc(self.client.inspect, control=True)
        lease = self.rpc(self.client.lease)
        return self.client.build_activation(identifier, assets={'scene': {'value': 'one', 'references': []}},
            entrypoint='scene', inspection=snapshot, lease=lease)

    def test_real_roundtrip_discovery_inspect_activation_and_lookup(self):
        request = self.request()
        pending = self.rpc(lambda: self.client.activate(request))
        self.assertEqual(pending.status, Status.ACCEPTED_PENDING)
        for _ in range(3):
            self.broker.advance()
        receipt = self.rpc(lambda: self.client.lookup(request.command_id), control=True)
        self.assertEqual(receipt.status, Status.COMMITTED)
        actual = json.loads(self.owner.files.read('active.json')[1])
        self.assertEqual(actual['assets']['scene']['value'], 'one')
        snapshot = self.rpc(self.client.inspect, control=True)
        self.assertIsInstance(snapshot, SelectorSnapshot)
        self.assertEqual(snapshot.generation, 1)
        self.assertTrue(snapshot.ready)
        self.assertEqual(snapshot.selected.manifest_sha256, receipt.postconditions['manifest_sha256'])

    def test_real_native_service_bootstrap_two_replacements_retry_and_stop(self):
        # This path uses actual endpoint creation/security/frame I/O and the
        # service's readers/pump. Only peer checking is substituted; the native
        # AppContainer worker package separately proves that trust boundary.
        self.client.close()
        self.work_server.close()
        self.control_server.close()
        with ExitStack() as stack:
            endpoints, channels = [], []
            fixture_identity = (os.getpid(), 1)
            for role in ('work', 'control'):
                endpoint = AppContainerEndpoint.create('S-1-15-2-1-2-3-4-5-6-7', role=role)
                stack.callback(endpoint.close)
                stack.enter_context(mock.patch.object(endpoint, '_check_peer'))
                endpoint._identity = fixture_identity
                handle = self.pairs.k.CreateFileW(endpoint.address, 0xC0000000, 0, None, 3, 0x40000000, None)
                if handle == C.c_void_p(-1).value:
                    raise C.WinError(C.get_last_error())
                channel = self.pairs.retain(handle)
                stack.callback(channel.close)
                endpoint.connect(timeout_ms=1000)
                endpoints.append(endpoint)
                channels.append(channel)
            service = ManagedPipeService(self.owner, self.broker, *endpoints, self.credential,
                                         session_timeout_ms=30_000)
            stack.callback(service.close)
            service.start()
            # The launcher consumes exactly one frame before transferring the
            # already-connected channels. Client constructor reads nothing.
            credential = parse_bootstrap(channels[0].read_frame(timeout_ms=1000),
                                         expected_project_id=self.owner.project_id)
            self.assertEqual(credential, self.credential)
            client = ManagedFixtureClient(*channels, credential, timeout_ms=1000)
            stack.callback(client.close)

            def await_committed(identifier):
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    response = client.lookup(identifier)
                    if response.status is Status.COMMITTED:
                        return response
                    self.assertIn(response.status, (Status.ACCEPTED_PENDING, Status.UNKNOWN))
                    # This repeats only read-only lookup, never activation.
                    threading.Event().wait(.005)
                self.fail('managed service did not reach a committed receipt within the bound')

            versions = []
            for ordinal, value in enumerate(('first-native', 'second-native'), 1):
                self.assertTrue(client.discover().supports('fixture.release.activate'))
                inspection = client.inspect()
                self.assertEqual(inspection.generation, ordinal - 1)
                request = client.build_activation('service-activation-' + str(ordinal),
                    assets={'scene': {'value': value, 'references': []}}, entrypoint='scene',
                    inspection=inspection, lease=client.lease())
                self.assertEqual(client.activate(request).status, Status.ACCEPTED_PENDING)
                receipt = await_committed(request.command_id)
                version, raw = self.owner.files.read('active.json')
                self.assertEqual(json.loads(raw)['assets']['scene']['value'], value)
                self.assertEqual(version.sha256, hashlib.sha256(raw).hexdigest())
                versions.append(version)
                snapshot = client.inspect()
                self.assertEqual(snapshot.generation, ordinal)
                self.assertTrue(snapshot.ready)
                self.assertEqual(snapshot.selected.manifest_sha256, receipt.postconditions['manifest_sha256'])
                before_retry = self.owner.log.binding().witnessed
                self.assertEqual(client.activate(request), receipt)
                self.assertEqual(self.owner.log.binding().witnessed, before_retry)
                self.assertEqual(self.owner.consumer.adoption_count, ordinal)
            self.assertNotEqual(versions[0].identity.file_id, versions[1].identity.file_id)
            self.assertNotEqual(versions[0].sha256, versions[1].sha256)
            stop = client.stop(request.command_id)
            self.assertIsInstance(stop, SelectorStopResult)
            self.assertTrue(stop.stopped)
            self.assertEqual(stop.command, receipt)
            self.assertTrue(client.inspect().stopped)
            client.close()
            service.close()
            self.assertTrue(service.status()['closed'])
            self.assertEqual(service.status()['live_threads'], 0)
            self.assertTrue(all(channel.closed for channel in channels))
            self.assertTrue(all(endpoint._closed for endpoint in endpoints))
            self.assertEqual(self.owner.log.binding().witnessed, self.owner.custody.binding.witnessed)

    def test_cancel_and_stop_are_typed_control_calls(self):
        request = self.request()
        self.rpc(lambda: self.client.activate(request))
        canceled = self.rpc(lambda: self.client.cancel(request.command_id), control=True)
        self.assertEqual(canceled.status, Status.CANCELED)
        stopped = self.rpc(lambda: self.client.stop(request.command_id), control=True)
        self.assertIsInstance(stopped, SelectorStopResult)
        self.assertTrue(stopped.stopped)
        self.assertEqual(stopped.command, canceled)

    def test_lost_reply_is_unknown_control_lookup_and_no_work_resend(self):
        request = self.request()
        before = self.owner.log.binding().witnessed
        unknown = self.rpc(lambda: self.client.activate(request), drop=True)
        self.assertEqual(unknown.status, Status.UNKNOWN)
        self.assertEqual(unknown.postconditions['next_action'], 'lookup')
        after = self.owner.log.binding().witnessed
        self.assertEqual(after.sequence, before.sequence + 1)
        # A further explicit call cannot reuse the ambiguous pipe stream.
        with mock.patch.object(self.client._pipes[0], 'write_frame', side_effect=AssertionError('no resend')):
            self.assertEqual(self.client.activate(request).status, Status.UNKNOWN)
        receipt = self.rpc(lambda: self.client.lookup(request.command_id), control=True)
        self.assertEqual(receipt.status, Status.ACCEPTED_PENDING)
        self.assertEqual(self.owner.log.binding().witnessed, after)

    def test_control_remains_available_while_work_reply_stalls(self):
        entered, release = threading.Event(), threading.Event()
        errors, results = [], []
        def server():
            try:
                self.serve(entered=entered, release=release)
            except BaseException as exc:
                errors.append(exc)
        def call():
            try:
                results.append(self.client.discover())
            except BaseException as exc:
                errors.append(exc)
        server_thread = threading.Thread(target=server, daemon=True)
        caller = threading.Thread(target=call, daemon=True)
        server_thread.start(); caller.start()
        try:
            self.assertTrue(entered.wait(2))
            stopped = self.rpc(self.client.stop, control=True)
            self.assertTrue(stopped.stopped)
            self.assertTrue(caller.is_alive())
        finally:
            release.set(); caller.join(2); server_thread.join(2)
        self.assertFalse(caller.is_alive() or server_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 1)

    def test_schema_mismatch_does_not_enable_builder(self):
        session = self.broker.sessions.authenticate('Bearer ' + self.credential.bearer)
        value = self.broker.discovery(session).as_dict()
        value['schema_digest'] = 'sha256:' + '0' * 64
        with self.assertRaises(SelectorClientError) as caught:
            self.rpc(self.client.discover, reply=canonical_bytes(value))
        self.assertTrue(caught.exception.outcome_unknown)
        with self.assertRaisesRegex(SelectorClientError, 'CLIENT_ACTIVATION_UNAVAILABLE'):
            self.client.build_activation('never', assets={}, entrypoint='scene', inspection=None, lease=None)

    def test_capability_scope_mismatch_does_not_enable_builder(self):
        session = self.broker.sessions.authenticate('Bearer ' + self.credential.bearer)
        value = self.broker.discovery(session).as_dict()
        activate = next(cap for cap in value['capabilities'] if cap['operation'] == 'fixture.release.activate')
        activate['write_scopes'] = ['other.scope']
        with self.assertRaises(SelectorClientError) as caught:
            self.rpc(self.client.discover, reply=canonical_bytes(value))
        self.assertTrue(caught.exception.outcome_unknown)
        with self.assertRaisesRegex(SelectorClientError, 'CLIENT_ACTIVATION_UNAVAILABLE'):
            self.client.build_activation('never', assets={}, entrypoint='scene', inspection=None, lease=None)

    def test_stopped_discovery_withholds_new_activation_builder(self):
        self.rpc(self.client.stop, control=True)
        discovery = self.rpc(self.client.discover)
        self.assertFalse(discovery.supports('fixture.release.activate'))
        with self.assertRaisesRegex(SelectorClientError, 'CLIENT_ACTIVATION_UNAVAILABLE'):
            self.client.build_activation('never', assets={}, entrypoint='scene', inspection=None, lease=None)

    def test_inspect_extra_paths_and_oversized_reply_reject(self):
        session = self.broker.sessions.authenticate('Bearer ' + self.credential.bearer)
        value = self.broker.inspect(session)
        value['path'] = 'C:\\untrusted'
        with self.assertRaises(SelectorClientError):
            self.rpc(self.client.inspect, control=True, reply=canonical_bytes(value))
        # Separate native channel/client needed after malformed reply quarantine.
        server, channel = self.pairs.pair()
        with mock.patch.object(channel, 'read_frame', return_value=b'x' * 4097), \
             mock.patch.object(channel, 'write_frame'):
            work_server, work = self.pairs.pair()
            client = ManagedFixtureClient(work, channel, self.credential)
            try:
                with self.assertRaises(SelectorClientError):
                    client.inspect()
            finally:
                client.close()

    def test_builder_copies_assets_and_rejects_bad_graph_and_deadline(self):
        self.rpc(self.client.discover)
        snapshot = self.rpc(self.client.inspect, control=True)
        lease = self.rpc(self.client.lease)
        assets = {'scene': {'value': ['one'], 'references': []}}
        request = self.client.build_activation('one', assets=assets, entrypoint='scene', inspection=snapshot, lease=lease)
        digest = request.digest
        assets['scene']['value'].append('caller-edit')
        self.assertEqual(request.digest, digest)
        self.assertEqual(request.payload['assets']['scene']['value'], ['one'])
        for deadline in (0, True, 30_001):
            with self.assertRaisesRegex(SelectorClientError, 'CLIENT_DEADLINE_INVALID'):
                self.client.build_activation('bad', assets=assets, entrypoint='scene', inspection=snapshot,
                                             lease=lease, deadline_after_ms=deadline)
        with self.assertRaises(SafetyViolation):
            self.client.build_activation('bad', assets={'scene': {'value': 1, 'references': ['missing']}},
                                         entrypoint='scene', inspection=snapshot, lease=lease)
        with self.assertRaisesRegex(SelectorClientError, 'CLIENT_PAYLOAD_LIMIT'):
            self.client.build_activation('large', assets={'scene': {'value': 'x' * 7900, 'references': []}},
                                         entrypoint='scene', inspection=snapshot, lease=lease)
        with self.assertRaisesRegex(SelectorClientError, 'CLIENT_AUTHORITY_EXPIRED'):
            self.client.build_activation('expired', assets=assets, entrypoint='scene', inspection=snapshot,
                                         lease=replace(lease, expires_ms=1))

    def test_response_command_mismatch_is_unknown(self):
        wrong = Response(Status.COMMITTED, 'WRONG', 'another-command').as_dict()
        result = self.rpc(lambda: self.client.lookup('requested'), control=True, reply=canonical_bytes(wrong))
        self.assertEqual(result.status, Status.UNKNOWN)
        self.assertEqual(result.command_id, 'requested')

    def test_one_budget_covers_write_and_read(self):
        self.client.timeout_ms = 70
        observed = []
        def write(data, *, timeout_ms):
            observed.append(timeout_ms)
            time.sleep(.045)
        def read(*, timeout_ms):
            observed.append(timeout_ms)
            raise PipeIOError('PIPE_TIMEOUT')
        with mock.patch.object(self.client._pipes[0], 'write_frame', side_effect=write), \
             mock.patch.object(self.client._pipes[0], 'read_frame', side_effect=read):
            with self.assertRaises(SelectorClientError):
                self.client.discover()
        self.assertEqual(len(observed), 2)
        self.assertLess(observed[1], observed[0] - 20)

    def test_busy_channel_times_out_without_sending_and_close_retains_owner(self):
        self.client.timeout_ms = 30
        self.client._locks[0].acquire()
        try:
            with mock.patch.object(self.client._pipes[0], 'write_frame') as writer:
                with self.assertRaisesRegex(SelectorClientError, 'CLIENT_CHANNEL_BUSY'):
                    self.client.discover()
                writer.assert_not_called()
            with self.assertRaisesRegex(SelectorClientError, 'CLIENT_CLOSE_PENDING') as caught:
                self.client.close()
            self.assertIs(caught.exception.cleanup_owner, self.client)
            self.assertIn(self.client, pending_selector_client_cleanup())
            self.assertTrue(self.client._pipes[1].closed)
        finally:
            self.client._locks[0].release()
        self.client.close()
        self.assertNotIn(self.client, pending_selector_client_cleanup())

    def test_native_read_timeout_quarantines_only_work_channel(self):
        self.client.timeout_ms = 30
        with self.assertRaises(SelectorClientError) as caught:
            self.client.discover()  # Connected server deliberately does not reply.
        self.assertTrue(caught.exception.outcome_unknown)
        self.assertIsNone(self.client._pipes[0]._operation)
        self.assertIsInstance(self.rpc(self.client.inspect, control=True), SelectorSnapshot)
        with mock.patch.object(self.client._pipes[0], 'write_frame', side_effect=AssertionError('no resend')):
            with self.assertRaisesRegex(SelectorClientError, 'CLIENT_CHANNEL_RECOVERY_REQUIRED'):
                self.client.discover()

    def test_close_failure_keeps_actual_native_handle_until_retry(self):
        work = self.client._pipes[0]
        handle = work._handle
        with mock.patch.object(work._api, 'close', side_effect=PipeIOError('INJECTED_CLOSE_REFUSAL')):
            with self.assertRaisesRegex(SelectorClientError, 'CLIENT_CLOSE_PENDING') as caught:
                self.client.close()
            self.assertIs(caught.exception.cleanup_owner, self.client)
            self.assertIn(self.client, pending_selector_client_cleanup())
            self.assertTrue(self.pairs.valid(handle))
            self.assertFalse(work.closed)
        self.client.close()
        self.assertFalse(self.pairs.valid(handle))
        self.assertNotIn(self.client, pending_selector_client_cleanup())

    def test_constructor_refusal_keeps_channels_with_original_owner(self):
        work, control = self.client._pipes
        for args in ((work, work, self.credential), (object(), control, self.credential),
                     (work, control, replace(self.credential, expires_ms=1)),
                     (work, control, self.credential)):
            with self.assertRaises(SelectorClientError):
                ManagedFixtureClient(*args)
        self.assertFalse(work.closed or control.closed)

    def test_bootstrap_is_explicit_bounded_and_never_exposes_bearer_in_repr(self):
        value = {'schema': 'hh-selector-session-1', 'project_id': self.credential.project_id,
                 'session_id': self.credential.session_id, 'expires_ms': self.credential.expires_ms,
                 'scopes': sorted(self.credential.scopes), 'bearer': self.credential.bearer}
        credential = parse_bootstrap(canonical_bytes(value), expected_project_id='project-one')
        self.assertEqual(credential, self.credential)
        self.assertNotIn(self.credential.bearer, repr(credential))
        for bad in ({**value, 'path': 'outside'}, {**value, 'project_id': 'other'},
                    {**value, 'scopes': ['fixture.read', 'fixture.read']}, {**value, 'expires_ms': 1}):
            with self.assertRaises(SafetyViolation):
                parse_bootstrap(canonical_bytes(bad), expected_project_id='project-one')
        with self.assertRaises(SafetyViolation):
            parse_bootstrap(b'x' * 4097, expected_project_id='project-one')


if __name__ == '__main__':
    unittest.main(verbosity=2)
