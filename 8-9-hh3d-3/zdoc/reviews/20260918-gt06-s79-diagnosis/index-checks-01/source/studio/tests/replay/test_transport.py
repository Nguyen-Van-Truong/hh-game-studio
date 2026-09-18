"""Real loopback framing/admission tests with an inert replay owner, no engine."""
from __future__ import annotations

import http.client
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.core.limits import SafetyViolation
from studio.host.core.transport import TransportLimits, epoch_ms
from studio.host.replay.session import ReplaySession
from studio.host.replay.transport import ReplayTransport
from studio.protocol.core import canonical_bytes, parse_json

CATALOG = 'sha256:' + '1' * 64


def binding():
    return {'run_id': 'run.replay.01', 'command_id': 'command.run.01',
            'runtime_instance_id': 'runtime.01', 'source_closure_sha256': '3' * 64,
            'runtime_snapshot_sha256': '4' * 64, 'trace_sha256': '5' * 64,
            'glb_sha256': '6' * 64, 'generation': 1}


class StubOwner:
    def __init__(self, root):
        self.binding = binding()
        self.sessions = ReplaySession('project.replay', root, catalog_digest=CATALOG,
                                      binding=self.binding, owner_deadline_ms=epoch_ms() + 90_000)
        self.calls = []
        self.work_entered, self.lookup_entered = threading.Event(), threading.Event()
        self.work_release, self.lookup_release = threading.Event(), threading.Event()
        self.block_work = self.block_lookup = False

    def authorize(self, body, operation, kwargs):
        return self.sessions.authorize(kwargs['authorization'], operation,
            project_id=body.get('project_id'), catalog_digest=kwargs['catalog_digest'], binding=self.binding)

    def discover(self, body, **kwargs):
        self.authorize(body, 'play.inspect', kwargs)
        self.calls.append('discover')
        return {'enabled': ['play.inspect'], 'public_ack': False}

    def lease(self, body, **kwargs):
        self.authorize(body, 'play.start', kwargs)
        self.calls.append('lease')
        return {'status': 'LEASE_STUB', 'public_ack': False}

    def submit(self, body, **kwargs):
        self.authorize(body, 'play.start', kwargs)
        self.calls.append('submit')
        self.work_entered.set()
        if self.block_work and not self.work_release.wait(5):
            raise SafetyViolation('TEST_WORK_TIMEOUT')
        return {'status': 'UNKNOWN', 'public_ack': False}

    def lookup(self, body, **kwargs):
        self.authorize(body, 'control.lookup', kwargs)
        self.calls.append('lookup')
        self.lookup_entered.set()
        if self.block_lookup and not self.lookup_release.wait(5):
            raise SafetyViolation('TEST_LOOKUP_TIMEOUT')
        return {'status': 'UNKNOWN', 'public_ack': False}

    def stop(self, body, **kwargs):
        grant = self.authorize(body, 'control.stop', kwargs)
        self.calls.append('stop')
        return self.sessions.stop(grant)


class ReplayTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-replay-http-')
        self.addCleanup(self.temp.cleanup)
        self.owner = StubOwner(Path(self.temp.name))
        self.credential = self.owner.sessions.issue()
        self.server = ReplayTransport(self.owner).start()
        self.addCleanup(self.close)

    def close(self):
        self.owner.work_release.set()
        self.owner.lookup_release.set()
        self.server.close()

    def call(self, path, *, listener='work', body=None, token=None, headers=None):
        port = {'work': self.server.port, 'control': self.server.control_port, 'stop': self.server.stop_port}[listener]
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
        try:
            head = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (token or self.credential.bearer),
                    'X-HH-Catalog': CATALOG}
            head.update(headers or {})
            conn.request('POST', path, canonical_bytes(body if body is not None else {'project_id': 'project.replay'}), head)
            response = conn.getresponse()
            return response.status, parse_json(response.read())
        finally:
            conn.close()

    def wait_connections(self, expected):
        end = time.monotonic() + 1
        while time.monotonic() < end:
            with self.server._guard:
                if self.server._connections == expected:
                    return
            time.sleep(.005)
        self.fail('HTTP handlers did not reach expected connection count')

    def worker(self, path, listener):
        results = []
        def request():
            try:
                results.append(self.call(path, listener=listener))
            except BaseException as error:
                results.append(error)
        thread = threading.Thread(target=request)
        thread.start()
        self.addCleanup(lambda: thread.join(2))
        return thread, results

    def raw(self, request, *, port=None):
        with socket.create_connection(('127.0.0.1', port or self.server.port), timeout=2) as stream:
            stream.sendall(request)
            received = bytearray()
            while True:
                chunk = stream.recv(4096)
                if not chunk:
                    return bytes(received)
                received.extend(chunk)

    def test_work_routes_forward_to_owner_with_unchanged_limits(self):
        for path, call in (('/v1/discovery', 'discover'), ('/v1/lease', 'lease'), ('/v1/commands', 'submit')):
            with self.subTest(path=path):
                code, result = self.call(path)
                self.assertEqual(code, 200)
                self.assertFalse(result['public_ack'])
                self.assertEqual(self.owner.calls[-1], call)
        self.assertEqual(self.server.limits, TransportLimits(max_connections=2, max_control_connections=2))
        self.assertEqual(len({self.server.port, self.server.control_port, self.server.stop_port}), 3)

    def test_wrong_bearer_catalog_project_origin_and_encoding_rejected(self):
        cases = (({'token': 'z' * 43}, ('AUTH_REQUIRED', 'AUTH_FAILED')),
                 ({'headers': {'X-HH-Catalog': 'sha256:' + '9' * 64}}, ('REPLAY_GRANT_BINDING',)),
                 ({'body': {'project_id': 'project.other'}}, ('REPLAY_GRANT_BINDING',)),
                 ({'headers': {'Origin': 'https://example.com'}}, ('ORIGIN_REJECTED',)),
                 ({'headers': {'Content-Encoding': 'gzip'}}, ('UNSUPPORTED_ENCODING',)))
        for kwargs, expected in cases:
            with self.subTest(expected=expected):
                code, result = self.call('/v1/discovery', **kwargs)
                self.assertEqual(code, 400)
                self.assertIn(result['code'], expected)
                self.assertFalse(result['public_ack'])
        self.assertEqual(self.owner.calls, [])

    def test_lookup_precheck_uses_detached_owner_binding(self):
        original = self.owner.sessions.authorize
        observed = []
        def record(*args, **kwargs):
            observed.append(kwargs['binding'].copy())
            return original(*args, **kwargs)
        # Transport precheck retains the original scope even if a caller
        # supplies a different binding. The owner remains responsible for
        # rejecting unexpected fields in its complete envelope.
        with patch.object(self.owner.sessions, 'authorize', side_effect=record):
            code, _ = self.call('/v1/lookup', listener='control',
                                body={'project_id': 'project.replay', 'binding': {'generation': 99}})
        self.assertEqual(code, 200)
        self.assertEqual(observed, [binding(), binding()])
        self.owner.binding['generation'] = 2
        grant = self.server.sessions.authorize('Bearer ' + self.credential.bearer, 'control.lookup',
                                              project_id='project.replay', catalog_digest=CATALOG)
        self.assertEqual(grant.binding_sha256, self.owner.sessions.binding_sha256)

    def test_mismatched_owner_binding_rejected_before_socket_creation(self):
        self.owner.binding['generation'] = 2
        with self.assertRaisesRegex(SafetyViolation, 'REPLAY_TRANSPORT_BINDING'):
            ReplayTransport(self.owner)

    def test_lookup_busy_still_checks_catalog_and_operation_grant(self):
        self.owner.block_lookup = True
        worker, results = self.worker('/v1/lookup', 'control')
        self.assertTrue(self.owner.lookup_entered.wait(1))
        restricted = self.owner.sessions.issue(operations=frozenset({'play.inspect'}))
        try:
            for kwargs, expected in (({}, 'GODOT_LOOKUP_BUSY'),
                    ({'headers': {'X-HH-Catalog': 'sha256:' + '9' * 64}}, 'REPLAY_GRANT_BINDING'),
                    ({'token': restricted.bearer}, 'REPLAY_OPERATION_FORBIDDEN')):
                code, result = self.call('/v1/lookup', listener='control', **kwargs)
                self.assertEqual((code, result['code']), (400, expected))
                self.wait_connections(1)
            self.assertEqual(self.owner.calls, ['lookup'])
        finally:
            self.owner.lookup_release.set()
            worker.join(2)
        self.assertEqual(results, [(200, {'status': 'UNKNOWN', 'public_ack': False})])

    def test_stop_listener_works_with_work_and_control_partial_headers(self):
        streams = []
        try:
            for port in (self.server.port, self.server.control_port):
                for _ in range(2):
                    stream = socket.create_connection(('127.0.0.1', port), timeout=2)
                    streams.append(stream)
                    stream.sendall(b'POST /v1/commands HTTP/1.1\r\n')
            self.wait_connections(4)
            code, result = self.call('/v1/stop', listener='stop')
            self.assertEqual(code, 200)
            self.assertTrue(result['stopped'])
            with self.server._guard:
                self.assertGreaterEqual(self.server._connections, 4)
        finally:
            for stream in streams:
                stream.close()
        self.wait_connections(0)

    def test_stop_isolated_from_blocked_owner_work_lookup_and_slow_control(self):
        self.owner.block_work = self.owner.block_lookup = True
        work, work_results = self.worker('/v1/commands', 'work')
        lookup, lookup_results = self.worker('/v1/lookup', 'control')
        self.assertTrue(self.owner.work_entered.wait(1))
        self.assertTrue(self.owner.lookup_entered.wait(1))
        stream = socket.create_connection(('127.0.0.1', self.server.control_port), timeout=2)
        try:
            stream.sendall(b'POST /v1/lookup HTTP/1.1\r\n')
            self.wait_connections(3)
            code, result = self.call('/v1/stop', listener='stop')
            self.assertEqual(code, 200)
            self.assertTrue(result['stopped'])
            self.assertTrue(work.is_alive())
            self.assertTrue(lookup.is_alive())
            self.assertFalse(self.owner.work_release.is_set())
            self.assertFalse(self.owner.lookup_release.is_set())
        finally:
            stream.close()
            self.owner.work_release.set()
            self.owner.lookup_release.set()
            work.join(2)
            lookup.join(2)
        self.assertEqual(work_results, [(200, {'status': 'UNKNOWN', 'public_ack': False})])
        self.assertEqual(lookup_results, [(200, {'status': 'UNKNOWN', 'public_ack': False})])

    def test_control_stop_compatibility_and_closed_route_sets(self):
        cases = [('work', '/v1/lookup'), ('work', '/v1/stop'), ('control', '/v1/commands'),
                 ('stop', '/v1/lookup'), ('stop', '/v1/discovery'), ('stop', '/v1/lease'),
                 ('work', '/v1/lease/enqueue'), ('work', '/v1/lease/poll'), ('work', '/v1/lease/cancel')]
        for listener, route in cases:
            code, result = self.call(route, listener=listener)
            self.assertEqual((code, result['code']), (400, 'UNSUPPORTED_ROUTE'))
        self.assertEqual(self.owner.calls, [])
        code, result = self.call('/v1/stop', listener='control')
        self.assertEqual(code, 200)
        self.assertTrue(result['stopped'])

    def test_stop_requires_scope_and_same_authority(self):
        reader = self.owner.sessions.issue(operations=frozenset({'play.inspect'}))
        for kwargs, expected in (({'token': reader.bearer}, 'REPLAY_OPERATION_FORBIDDEN'),
                ({'headers': {'X-HH-Catalog': 'sha256:' + '9' * 64}}, 'REPLAY_GRANT_BINDING'),
                ({'headers': {'Origin': 'https://example.com'}}, 'ORIGIN_REJECTED')):
            code, result = self.call('/v1/stop', listener='stop', **kwargs)
            self.assertEqual((code, result['code']), (400, expected))
            self.assertFalse(self.owner.sessions.status()['stopped'])

    def test_body_cap_precedes_auth_body_read_and_owner(self):
        request = (f'POST /v1/commands HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n'
            'Content-Type: application/json\r\n'
            f'Content-Length: {self.server.limits.max_body_bytes + 1}\r\n\r\n').encode()
        self.assertIn(b'ENVELOPE_TOO_LARGE', self.raw(request))
        self.assertEqual(self.owner.calls, [])

    def test_each_listener_rejects_other_listener_host_header(self):
        for listener, route, foreign in (('work', '/v1/discovery', self.server.control_port),
                ('control', '/v1/lookup', self.server.stop_port), ('stop', '/v1/stop', self.server.port)):
            code, result = self.call(route, listener=listener, headers={'Host': f'127.0.0.1:{foreign}'})
            self.assertEqual((code, result['code']), (400, 'HOST_REJECTED'))
        self.assertEqual(self.owner.calls, [])

    def test_secret_identifier_and_secret_owner_output_not_exposed(self):
        code, result = self.call('/v1/lookup', listener='control',
            body={'project_id': 'project.replay', 'command_id': self.credential.bearer})
        self.assertEqual(code, 400)
        self.assertNotIn(self.credential.bearer, repr(result))
        self.owner.discover = lambda *_args, **_kwargs: {'leak': self.credential.bearer}
        code, result = self.call('/v1/discovery')
        self.assertEqual((code, result['code']), (400, 'REPLAY_SENSITIVE_OUTPUT'))
        self.assertNotIn(self.credential.bearer, repr(result))
        self.assertNotIn(self.credential.bearer, repr(self.server.diagnostics))

    def test_close_tears_down_all_listeners_and_is_idempotent(self):
        self.server.close()
        self.assertTrue(all(server.socket.fileno() == -1 for server in self.server._listeners))
        self.assertFalse(any(thread.is_alive() for thread in self.server._threads))
        self.assertEqual(self.server._connections, 0)
        self.assertTrue(self.server._drained.is_set())
        self.server.close()
        with self.assertRaisesRegex(SafetyViolation, 'GODOT_TRANSPORT_ALREADY_STARTED'):
            self.server.start()


if __name__ == '__main__':
    unittest.main()
