"""Real socket framing/auth/Stop; backend below is explicitly an inert double."""
import http.client
import importlib.util
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.protocol.core import canonical_bytes, parse_json
from studio.host.core.limits import SafetyViolation


def load(name):
    spec = importlib.util.spec_from_file_location('s52_transport_test_' + name, STUDIO/'godot-addon'/(name+'.py'))
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


auth, transport = load('publication_session'), load('publication_transport')
CATALOG = 'sha256:' + '1'*64


class InertBackend:
    def __init__(self, path):
        self.sessions = auth.PublicationSession('project.fixture', path, CATALOG)
        self.wait = threading.Event(); self.entered = threading.Event()
        self.calls = 0

    def authorize(self, body, operation, kwargs):
        return self.sessions.authorize(kwargs['authorization'], operation,
            project_id=body.get('project_id'), catalog_digest=kwargs['catalog_digest'])

    def discover(self, body, **kwargs):
        self.authorize(body, 'scene.inspect', kwargs)
        return {'enabled':[], 'public_ack':False}

    def submit(self, body, **kwargs):
        self.authorize(body, 'scene.save', kwargs)
        self.calls += 1
        self.entered.set()
        if not self.wait.wait(timeout=3):
            raise SafetyViolation('TEST_TIMEOUT')
        return {'status':'UNKNOWN', 'public_ack':False}

    def stop(self, body, **kwargs):
        grant = self.authorize(body, 'control.stop', kwargs)
        result = self.sessions.stop(grant)
        self.wait.set()
        return result

    def lookup(self, body, **kwargs):
        self.authorize(body, 'control.lookup', kwargs)
        return {'status':'UNKNOWN', 'public_ack':False}


class PublicationTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-godot-http-')
        self.addCleanup(self.temp.cleanup)
        self.backend = InertBackend(Path(self.temp.name))
        self.credential = self.backend.sessions.issue()
        self.server = transport.PublicationTransport(self.backend).start()
        self.addCleanup(self.close)

    def close(self):
        self.backend.wait.set()
        self.server.close()

    def call(self, path, *, control=False, stop=False, body=None, token=None, headers=None):
        port = self.server.stop_port if stop else self.server.control_port if control else self.server.port
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=4)
        try:
            head = {'Content-Type':'application/json', 'Authorization':'Bearer '+(token or self.credential.bearer),
                    'X-HH-Catalog':CATALOG}
            head.update(headers or {})
            conn.request('POST', path, canonical_bytes(body or {'project_id':'project.fixture'}), head)
            response = conn.getresponse()
            return response.status, parse_json(response.read())
        finally:
            conn.close()

    def test_actual_loopback_requires_both_registered_bearer_and_catalog(self):
        self.assertEqual(self.call('/v1/discovery'), (200, {'enabled':[], 'public_ack':False}))
        for kwargs in ({'token':'z'*43}, {'headers':{'X-HH-Catalog':'sha256:'+'9'*64}}):
            code, result = self.call('/v1/discovery', **kwargs)
            self.assertEqual(code, 400)
            self.assertEqual(result['status'], 'REJECTED')
        self.assertEqual(self.backend.calls, 0)

    def test_control_listener_stops_while_work_handler_waits(self):
        results = []
        work = threading.Thread(target=lambda: results.append(self.call('/v1/commands')))
        work.start()
        self.assertTrue(self.backend.entered.wait(timeout=1))
        code, stopped = self.call('/v1/stop', control=True)
        self.assertEqual(code, 200)
        self.assertTrue(stopped['stopped'])
        work.join(timeout=2)
        self.assertFalse(work.is_alive())
        self.assertEqual(results[0][1]['status'], 'UNKNOWN')

    def _wait_connections(self, expected):
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with self.server._guard:
                if self.server._connections == expected:
                    return
            time.sleep(.005)
        self.fail('HTTP handlers did not drain to expected count')

    def _blocked_lookup(self):
        entered, release = threading.Event(), threading.Event()
        calls, results = [], []
        def lookup(body, **kwargs):
            self.backend.authorize(body, 'control.lookup', kwargs)
            calls.append(body['command_id'])
            entered.set()
            if not release.wait(5):
                raise SafetyViolation('TEST_LOOKUP_TIMEOUT')
            return {'status':'UNKNOWN', 'public_ack':False}
        self.backend.lookup = lookup
        def client():
            try:
                results.append(self.call('/v1/lookup', control=True,
                    body={'project_id':'project.fixture','command_id':'lookup.first'}))
            except BaseException as error:
                results.append(error)
        worker = threading.Thread(target=client)
        worker.start()
        self.assertTrue(entered.wait(1))
        return release, calls, results, worker

    def test_second_historical_lookup_is_busy_and_stop_keeps_control_admission(self):
        release, calls, results, worker = self._blocked_lookup()
        try:
            started = time.perf_counter()
            code, busy = self.call('/v1/lookup', control=True,
                body={'project_id':'project.fixture','command_id':'lookup.second'})
            self.assertLess(time.perf_counter() - started, .5)
            self.assertEqual((code, busy['status'], busy['code']), (400, 'REJECTED', 'GODOT_LOOKUP_BUSY'))
            self.assertFalse(busy['public_ack'])
            self.assertEqual(calls, ['lookup.first'])
            # The rejected client has closed. Wait for its bounded send/drain
            # bookkeeping, without releasing the first owner-I/O operation.
            self._wait_connections(1)
            started = time.perf_counter()
            code, stopped = self.call('/v1/stop', control=True,
                body={'project_id':'project.fixture','command_id':'control.stop'})
            self.assertLess(time.perf_counter() - started, .5)
            self.assertEqual(code, 200)
            self.assertTrue(stopped['stopped'])
            self.assertTrue(self.backend.sessions.status()['stopped'])
            self.assertTrue(worker.is_alive())
            self.assertFalse(release.is_set())
        finally:
            release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [(200, {'status':'UNKNOWN','public_ack':False})])

    def test_lookup_busy_path_still_checks_catalog_and_operation_authority(self):
        release, calls, results, worker = self._blocked_lookup()
        reader = self.backend.sessions.issue(operations=frozenset({'scene.inspect'}))
        try:
            for kwargs, expected in (
                ({'headers':{'X-HH-Catalog':'sha256:'+'9'*64}}, 'GODOT_GRANT_BINDING'),
                ({'token':reader.bearer}, 'GODOT_OPERATION_FORBIDDEN')):
                with self.subTest(expected=expected):
                    code, denied = self.call('/v1/lookup', control=True,
                        body={'project_id':'project.fixture','command_id':'lookup.denied'}, **kwargs)
                    self.assertEqual((code, denied['code']), (400, expected))
                    self._wait_connections(1)
            self.assertEqual(calls, ['lookup.first'])
        finally:
            release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [(200, {'status':'UNKNOWN','public_ack':False})])

    def test_lookup_reservation_released_after_owner_error_and_response_disconnect(self):
        body = {'project_id':'project.fixture','command_id':'lookup.retry'}
        original = self.backend.lookup
        def reject(body, **kwargs):
            self.backend.authorize(body, 'control.lookup', kwargs)
            raise SafetyViolation('INERT_LOOKUP_FAILURE')
        self.backend.lookup = reject
        code, rejected = self.call('/v1/lookup', control=True, body=body)
        self.assertEqual((code, rejected['code']), (400, 'INERT_LOOKUP_FAILURE'))
        self._wait_connections(0)
        self.backend.lookup = original
        with patch.object(self.server, '_send', side_effect=OSError('inert response disconnect')):
            with self.assertRaises((OSError, http.client.HTTPException)):
                self.call('/v1/lookup', control=True, body=body)
            self._wait_connections(0)
        self.assertEqual(self.call('/v1/lookup', control=True, body=body),
                         (200, {'status':'UNKNOWN','public_ack':False}))

    def test_canonical_stop_is_available_while_work_and_control_have_partial_headers(self):
        streams = []
        try:
            for port in (self.server.port, self.server.control_port):
                for _ in range(2):
                    stream = socket.create_connection(('127.0.0.1', port), timeout=2)
                    streams.append(stream)
                    stream.sendall(b'POST /v1/lookup HTTP/1.1\r\n')
            self._wait_connections(4)
            started = time.perf_counter()
            code, stopped = self.call('/v1/stop', stop=True,
                body={'project_id':'project.fixture','command_id':'stop.canonical'})
            self.assertLess(time.perf_counter() - started, .5)
            self.assertEqual(code, 200)
            self.assertTrue(stopped['stopped'])
            self.assertTrue(self.backend.sessions.status()['stopped'])
            with self.server._guard:
                self.assertGreaterEqual(self.server._connections, 4,
                    'Stop must finish while the other four reader slots are still occupied')
        finally:
            for stream in streams:
                stream.close()
        self._wait_connections(0)

    def test_canonical_stop_is_available_with_blocked_lookup_and_slow_control_client(self):
        release, calls, results, worker = self._blocked_lookup()
        stream = socket.create_connection(('127.0.0.1', self.server.control_port), timeout=2)
        try:
            stream.sendall(b'POST /v1/lookup HTTP/1.1\r\n')
            self._wait_connections(2)
            started = time.perf_counter()
            code, stopped = self.call('/v1/stop', stop=True,
                body={'project_id':'project.fixture','command_id':'stop.canonical'})
            self.assertLess(time.perf_counter() - started, .5)
            self.assertEqual(code, 200)
            self.assertTrue(stopped['stopped'])
            self.assertEqual(calls, ['lookup.first'])
            self.assertTrue(worker.is_alive())
            self.assertFalse(release.is_set())
        finally:
            stream.close(); release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [(200, {'status':'UNKNOWN','public_ack':False})])

    def test_canonical_listener_rejects_other_routes_and_requires_same_authority(self):
        for route in ('/v1/lookup', '/v1/discovery', '/v1/commands', '/v1/lease', '/v1/reconcile'):
            with self.subTest(route=route):
                code, denied = self.call(route, stop=True)
                self.assertEqual((code, denied['code']), (400, 'UNSUPPORTED_ROUTE'))
        reader = self.backend.sessions.issue(operations=frozenset({'scene.inspect'}))
        for kwargs, expected in (
            ({'token':'z'*43}, 'AUTH_REQUIRED'),
            ({'headers':{'X-HH-Catalog':'sha256:'+'9'*64}}, 'GODOT_GRANT_BINDING'),
            ({'token':reader.bearer}, 'GODOT_OPERATION_FORBIDDEN'),
            ({'headers':{'Origin':'https://example.com'}}, 'ORIGIN_REJECTED'),
            ({'headers':{'Content-Encoding':'gzip'}}, 'UNSUPPORTED_ENCODING')):
            with self.subTest(expected=expected):
                code, denied = self.call('/v1/stop', stop=True,
                    body={'project_id':'project.fixture','command_id':'stop.denied'}, **kwargs)
                self.assertEqual(code, 400)
                if expected == 'AUTH_REQUIRED':
                    self.assertIn(denied['code'], ('AUTH_REQUIRED', 'AUTH_FAILED'))
                else:
                    self.assertEqual(denied['code'], expected)
                self.assertFalse(denied['public_ack'])
                self.assertFalse(self.backend.sessions.status()['stopped'])

    def test_host_allowlist_is_specific_to_each_of_the_three_listeners(self):
        cases = (('/v1/discovery', {}, self.server.port),
                 ('/v1/lookup', {'control':True}, self.server.control_port),
                 ('/v1/stop', {'stop':True}, self.server.stop_port))
        ports = {port for _, _, port in cases}
        self.assertEqual(len(ports), 3)
        for route, flags, actual in cases:
            for foreign in ports - {actual}:
                with self.subTest(route=route, foreign=foreign):
                    code, denied = self.call(route, headers={'Host':f'127.0.0.1:{foreign}'}, **flags)
                    self.assertEqual((code, denied['code']), (400, 'HOST_REJECTED'))
        self.assertFalse(self.backend.sessions.status()['stopped'])

    def test_control_work_routes_cannot_consume_each_others_capacity(self):
        for path, control in (('/v1/stop', False), ('/v1/commands', True)):
            code, result = self.call(path, control=control)
            self.assertEqual((code, result['code']), (400, 'UNSUPPORTED_ROUTE'))

    def test_browser_origin_foreign_host_and_compression_are_rejected(self):
        for headers, expected in (({'Origin':'https://example.com'}, 'ORIGIN_REJECTED'),
                                  ({'Host':'example.com'}, 'HOST_REJECTED'),
                                  ({'Content-Encoding':'gzip'}, 'UNSUPPORTED_ENCODING')):
            code, result = self.call('/v1/discovery', headers=headers)
            self.assertEqual((code, result['code']), (400, expected))

    def test_duplicate_headers_are_rejected_before_backend(self):
        raw = (f'POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n'
               'Content-Type: application/json\r\nContent-Length: 2\r\nContent-Length: 2\r\n\r\n{}').encode()
        with socket.create_connection(('127.0.0.1', self.server.port), timeout=2) as stream:
            stream.sendall(raw)
            received = bytearray()
            while True:
                chunk = stream.recv(4096)
                if not chunk:
                    break
                received.extend(chunk)
        self.assertIn(b'INVALID_HEADER', received)
        self.assertEqual(self.backend.calls, 0)

    def test_secret_identifier_not_echoed_and_diagnostics_stay_bounded(self):
        code, result = self.call('/v1/lookup', control=True,
            body={'project_id':'project.fixture', 'command_id':self.credential.bearer})
        self.assertEqual(code, 400)
        self.assertNotIn(self.credential.bearer, repr(result))
        self.assertNotIn(self.credential.bearer, repr(self.server.diagnostics))
        self.assertEqual(self.server.diagnostics.maxlen, 32)

    def test_listener_start_failure_closes_all_started_and_unstarted_owners(self):
        # Run under the bounded host test runner: a regression that calls
        # shutdown() on the never-started server must not hang an outer run.
        original_start = threading.Thread.start
        for failure_at in (1, 2, 3):
            with self.subTest(failure_at=failure_at):
                partial = transport.PublicationTransport(self.backend)
                self.addCleanup(partial.close)
                attempted = []
                def fail_once(thread):
                    attempted.append(thread)
                    if len(attempted) == failure_at:
                        raise RuntimeError('INJECT_LISTENER_START_FAILURE')
                    return original_start(thread)
                started = time.monotonic()
                with patch.object(threading.Thread, 'start', fail_once):
                    with self.assertRaisesRegex(RuntimeError, 'INJECT_LISTENER_START_FAILURE'):
                        partial.start()
                self.assertLess(time.monotonic() - started, 2.0, 'partial start cleanup must be bounded')
                self.assertEqual(len(attempted), failure_at)
                self.assertTrue(all(thread.ident is not None for thread in attempted[:-1]))
                self.assertIsNone(attempted[-1].ident, 'failed listener never entered its serve loop')
                self.assertFalse(any(thread.is_alive() for thread in attempted))
                self.assertEqual(len(partial._listeners), 3)
                self.assertTrue(all(server.socket.fileno() == -1 for server in partial._listeners))
                self.assertEqual(partial._connections, 0)
                self.assertTrue(partial._drained.is_set())
                partial.close()  # Cleanup remains idempotent after the start exception.
                with self.assertRaisesRegex(SafetyViolation, 'GODOT_TRANSPORT_ALREADY_STARTED'):
                    partial.start()

    def test_partial_listener_constructor_failure_closes_previously_created_sockets(self):
        original_port = transport._Port
        for failure_at in (1, 2, 3):
            with self.subTest(failure_at=failure_at):
                created = []
                def fail_once(owner, role):
                    if len(created) + 1 == failure_at:
                        raise OSError('INJECT_LISTENER_CONSTRUCTOR_FAILURE')
                    server = original_port(owner, role); created.append(server)
                    return server
                with patch.object(transport, '_Port', side_effect=fail_once):
                    with self.assertRaisesRegex(OSError, 'INJECT_LISTENER_CONSTRUCTOR_FAILURE'):
                        transport.PublicationTransport(self.backend)
                self.assertEqual(len(created), failure_at - 1)
                self.assertTrue(all(server.socket.fileno() == -1 for server in created))

    def test_normal_close_drains_and_closes_all_three_listeners(self):
        self.server.close()
        self.assertEqual(len(self.server._listeners), 3)
        self.assertTrue(all(server.socket.fileno() == -1 for server in self.server._listeners))
        self.assertFalse(any(thread.is_alive() for thread in self.server._threads))
        self.assertEqual(self.server._connections, 0)
        self.assertTrue(self.server._drained.is_set())
        self.server.close()


if __name__ == '__main__':
    unittest.main()
