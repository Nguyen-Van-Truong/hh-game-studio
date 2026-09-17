"""Real socket framing/auth/Stop; backend below is explicitly an inert double."""
import http.client
import re
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


from studio.host.blender import client_transport as transport
from studio.host.core.transport import SessionAuthority, TransportLimits
from studio.protocol.core import Response, Status

CATALOG = 'sha256:' + '1'*64


class InertSessions:
    """Test double for Blender grant policy; the immutable issuer handles secrets.

    These test operations do not confer native Blender authority and are not a
    substitute for the production Blender session implementation.
    """
    def __init__(self, project, path, catalog):
        self.project_id, self.catalog_digest = project, catalog
        self._issuer = SessionAuthority(project, path, TransportLimits())
        self.operations = {}
        self.stopped = False

    def issue(self, operations=frozenset({'scene.inspect','control.lookup','control.stop'})):
        credential = self._issuer.issue(scopes=frozenset({'fixture.read','control.stop'}))
        self.operations[credential.session_id] = operations
        return credential

    def authenticate(self, authorization):
        return self._issuer.authenticate(authorization)

    def authorize(self, authorization, operation, *, project_id, catalog_digest):
        session = self.authenticate(authorization)
        if project_id != self.project_id or catalog_digest != self.catalog_digest:
            raise SafetyViolation('BLENDER_GRANT_BINDING')
        if operation not in self.operations[session.credential.session_id]:
            raise SafetyViolation('BLENDER_OPERATION_FORBIDDEN')
        return session

    def validate_public_identifier(self, identifier):
        if type(identifier) is not str or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}', identifier):
            raise SafetyViolation('BLENDER_INVALID_IDENTIFIER')
        self._issuer.validate_public_identifier(identifier)

    def encode_output(self, value):
        return self._issuer.encode_output(value)

    def redact_output(self, value):
        return self._issuer.redact_output(value)

    def stop(self, grant):
        self._issuer.check_current(grant)
        self.stopped = True
        return {'stopped': True, 'public_ack': False}

    def status(self):
        return {'stopped': self.stopped}


class InertBackend:
    def __init__(self, path):
        self.sessions = InertSessions('project.fixture', path, CATALOG)
        self.wait = threading.Event(); self.entered = threading.Event()
        self.calls = 0

    def authorize(self, body, operation, kwargs):
        return self.sessions.authorize(kwargs['authorization'], operation,
            project_id=body.get('project_id'), catalog_digest=kwargs['catalog_digest'])

    def discover(self, body, **kwargs):
        self.authorize(body, 'scene.inspect', kwargs)
        return {'enabled':[], 'public_ack':False}

    def lease(self, body, **kwargs):
        self.authorize(body, 'scene.inspect', kwargs)
        if (set(body) != {'project_id', 'ttl_ms', 'access'} or body['access'] != 'read'
                or type(body['ttl_ms']) is not int or not 0 < body['ttl_ms'] <= 30000):
            raise SafetyViolation('BLENDER_INVALID_READ_LEASE')
        return {'lease_id':'read.inert', 'fencing_epoch':0, 'expires_ms':12345, 'access':'read'}

    def submit(self, body, **kwargs):
        self.authorize(body, 'scene.inspect', kwargs)
        if body.get('operation', 'scene.inspect') != 'scene.inspect':
            raise SafetyViolation('BLENDER_OPERATION_FORBIDDEN')
        self.calls += 1
        self.entered.set()
        if not self.wait.wait(timeout=8):
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


class BlenderClientTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-blender-http-')
        self.addCleanup(self.temp.cleanup)
        self.backend = InertBackend(Path(self.temp.name))
        self.credential = self.backend.sessions.issue()
        self.server = transport.BlenderClientTransport(self.backend).start()
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
        for kwargs in ({'token':'z'*43}, {'headers':{'X-HH-Catalog':'sha256:'+'9'*64}},
                       {'body':{'project_id':'project.foreign'}}):
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
            self.assertEqual((code, busy['status'], busy['code']), (400, 'REJECTED', 'BLENDER_LOOKUP_BUSY'))
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
                ({'headers':{'X-HH-Catalog':'sha256:'+'9'*64}}, 'BLENDER_GRANT_BINDING'),
                ({'body':{'project_id':'project.foreign','command_id':'lookup.denied'}}, 'BLENDER_GRANT_BINDING'),
                ({'token':reader.bearer}, 'BLENDER_OPERATION_FORBIDDEN')):
                with self.subTest(expected=expected):
                    request = {'body':{'project_id':'project.fixture','command_id':'lookup.denied'}, **kwargs}
                    code, denied = self.call('/v1/lookup', control=True, **request)
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
            ({'headers':{'X-HH-Catalog':'sha256:'+'9'*64}}, 'BLENDER_GRANT_BINDING'),
            ({'token':reader.bearer}, 'BLENDER_OPERATION_FORBIDDEN'),
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
                partial = transport.BlenderClientTransport(self.backend)
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
                with self.assertRaisesRegex(SafetyViolation, 'BLENDER_TRANSPORT_ALREADY_STARTED'):
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
                        transport.BlenderClientTransport(self.backend)
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

    def test_read_only_lease_and_typed_response_forward_without_fixture_host(self):
        with patch.object(transport.LoopbackFixtureHost, '__init__', side_effect=AssertionError('forbidden')):
            other = transport.BlenderClientTransport(self.backend)
            other.close()
        code, lease = self.call('/v1/lease', body={'project_id':'project.fixture','ttl_ms':30000,'access':'read'})
        self.assertEqual((code, lease['access'], lease['fencing_epoch']), (200, 'read', 0))
        code, denied = self.call('/v1/lease', body={'project_id':'project.fixture','ttl_ms':30000,'access':'write'})
        self.assertEqual((code, denied['code']), (400, 'BLENDER_INVALID_READ_LEASE'))
        for operation in ('scene.node.create', 'scene.save', 'python.eval'):
            code, denied = self.call('/v1/commands', body={'project_id':'project.fixture',
                'command_id':'write.denied','operation':operation})
            self.assertEqual((code, denied['code']), (400, 'BLENDER_OPERATION_FORBIDDEN'))
        self.assertEqual(self.backend.calls, 0)
        response = Response(Status.REJECTED, 'BLENDER_UNSUPPORTED', 'read.inert',
                            postconditions={'effect_scope':'none'})
        with patch.object(self.backend, 'submit', return_value=response):
            code, wire = self.call('/v1/commands', body={'project_id':'project.fixture','command_id':'read.inert'})
        self.assertEqual((code, wire), (200, response.as_dict()))
        self.assertIs(transport._ReaderContext._read_request, transport.LoopbackFixtureHost._read_request)
        self.assertIs(transport.BlenderClientTransport._send, transport.LoopbackFixtureHost._send)

    def _raw(self, header, body=b''):
        with socket.create_connection(('127.0.0.1', self.server.port), timeout=2) as stream:
            stream.sendall(header.encode('ascii') + body)
            received = bytearray()
            while True:
                try:
                    chunk = stream.recv(4096)
                except ConnectionResetError:
                    break
                if not chunk:
                    break
                received.extend(chunk)
        return bytes(received)

    def test_header_and_body_caps_run_before_authentication(self):
        base = (f'POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n'
                'Content-Type: application/json\r\n')
        cases = [(base + f'Content-Length: {self.server.limits.max_body_bytes+1}\r\n\r\n', 'ENVELOPE_TOO_LARGE'),
                 (base + 'Content-Length: 2\r\nX-Large: ' + 'a'*8192 + '\r\n\r\n', 'HEADER_TOO_LARGE'),
                 (base + 'Content-Length: 2\r\n' + ''.join(f'X-{i}: 1\r\n' for i in range(25)) + '\r\n',
                  'HEADER_COUNT_LIMIT')]
        for header, expected in cases:
            with self.subTest(expected=expected), patch.object(self.backend.sessions, 'authenticate',
                    side_effect=AssertionError('must reject before auth')) as authenticate:
                self.assertIn(expected.encode(), self._raw(header, b'{}'))
                authenticate.assert_not_called()
            self._wait_connections(0)
        self.assertEqual(self.backend.calls, 0)

    def test_chunking_expect_and_non_object_json_never_reach_backend(self):
        for headers in ({'Transfer-Encoding':'chunked'}, {'Expect':'100-continue'}):
            code, denied = self.call('/v1/discovery', headers=headers)
            self.assertEqual((code, denied['code']), (400, 'UNSUPPORTED_ENCODING'))
            self._wait_connections(0)
        for body in (b'[]', b'{"project_id":NaN}', b'{"project_id":'):
            header = (f'POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1:{self.server.port}\r\n'
                f'Authorization: Bearer {self.credential.bearer}\r\nX-HH-Catalog: {CATALOG}\r\n'
                f'Content-Type: application/json\r\nContent-Length: {len(body)}\r\n\r\n')
            received = self._raw(header, body)
            self.assertTrue(received.startswith(b'HTTP/1.1 400 '))
            self.assertNotIn(self.credential.bearer.encode(), received)
            self._wait_connections(0)
        self.assertEqual(self.backend.calls, 0)

    def test_connection_overload_is_bounded_and_stop_remains_independent(self):
        streams = []
        try:
            for _ in range(2):
                stream = socket.create_connection(('127.0.0.1', self.server.port), timeout=2)
                streams.append(stream)
                stream.sendall(b'POST /v1/discovery HTTP/1.1\r\n')
            self._wait_connections(2)
            with self.assertRaises((OSError, http.client.HTTPException)):
                self.call('/v1/discovery')
            code, stopped = self.call('/v1/stop', stop=True,
                body={'project_id':'project.fixture','command_id':'stop.overload'})
            self.assertEqual((code, stopped['stopped']), (200, True))
            self.assertEqual(self.backend.calls, 0)
        finally:
            for stream in streams:
                stream.close()
        self._wait_connections(0)

    def test_response_redaction_and_result_byte_limit_use_exact_session_issuer(self):
        with patch.object(self.backend, 'discover', return_value={'message':self.credential.bearer,
                'path':str(self.temp.name)}):
            code, result = self.call('/v1/discovery')
        self.assertEqual(code, 200)
        self.assertNotIn(self.credential.bearer, repr(result))
        self.assertNotIn(self.temp.name, repr(result))
        self._wait_connections(0)
        self.server.limits = TransportLimits(max_connections=2, max_control_connections=2,
                                            max_response_bytes=512)
        with patch.object(self.backend, 'discover', return_value={'payload':'x'*(self.server.limits.max_response_bytes+1)}):
            code, result = self.call('/v1/discovery')
        self.assertEqual((code, result['code']), (413, 'RESULT_TOO_LARGE'))
        self.assertLess(len(canonical_bytes(result)), self.server.limits.max_response_bytes)

    def test_production_blender_session_without_fixture_scopes_works_on_all_listeners(self):
        # Actual production auth with the explicit inert backend: still no
        # Blender process, native observation, or runtime acceptance claim.
        from studio.host.blender.client_session import BlenderClientSession
        from studio.host.blender import client_catalog
        from studio.host.core.transport import epoch_ms
        self.server.close()
        self.backend.sessions = BlenderClientSession('project.fixture', Path(self.temp.name),
            owner_deadline_ms=epoch_ms()+30000)
        self.credential = self.backend.sessions.issue()
        self.assertEqual(self.credential.scopes, frozenset())
        self.server = transport.BlenderClientTransport(self.backend).start()
        headers = {'X-HH-Catalog':client_catalog.CATALOG_DIGEST}
        self.assertEqual(self.call('/v1/discovery', headers=headers),
                         (200, {'enabled':[], 'public_ack':False}))
        self.assertEqual(self.call('/v1/lookup', control=True, headers=headers),
                         (200, {'status':'UNKNOWN', 'public_ack':False}))
        foreign = self.backend.sessions._issuer.issue(scopes=frozenset({'fixture.read','control.stop'}))
        for route, flags in (('/v1/discovery', {}), ('/v1/lookup', {'control':True}),
                             ('/v1/stop', {'stop':True})):
            with self.subTest(route=route):
                code, denied = self.call(route, headers=headers, token=foreign.bearer, **flags)
                self.assertEqual((code, denied['code']), (400, 'BLENDER_GRANT_REQUIRED'))
        rotated = self.backend.sessions.rotate(self.credential)
        code, denied = self.call('/v1/lookup', control=True, headers=headers)
        self.assertEqual((code, denied['code']), (400, 'AUTH_REQUIRED'))
        code, stopped = self.call('/v1/stop', stop=True, headers=headers, token=rotated.bearer)
        self.assertEqual((code, stopped['stopped'], stopped['public_ack']), (200, True, False))
        self.assertTrue(self.backend.sessions._stopped.is_set())
        self.assertEqual(self.backend.calls, 0)

    def test_malformed_owner_output_never_leaks_and_releases_lookup_admission(self):
        cyclic = {}; cyclic['cycle'] = cyclic
        cases = (({'number':float('nan')}, 'REDACTION_INVALID_NUMBER'),
                 (cyclic, 'REDACTION_CYCLE'),
                 ({'unsupported':object()}, 'REDACTION_UNSUPPORTED_TYPE'))
        for value, expected in cases:
            with self.subTest(expected=expected), patch.object(self.backend, 'lookup', return_value=value):
                code, denied = self.call('/v1/lookup', control=True)
                self.assertEqual((code, denied['code']), (400, expected))
                self.assertFalse(denied['public_ack'])
            self._wait_connections(0)
            self.assertEqual(self.call('/v1/lookup', control=True),
                             (200, {'status':'UNKNOWN','public_ack':False}))
        with patch.object(self.backend, 'lookup', side_effect=RuntimeError(self.credential.bearer)):
            code, denied = self.call('/v1/lookup', control=True)
        self.assertEqual((code, denied['status'], denied['code']),
                         (500, 'UNKNOWN', 'BLENDER_TRANSPORT_FAILED'))
        self.assertNotIn(self.credential.bearer, repr(denied))
        self.assertNotIn(self.credential.bearer, repr(self.server.diagnostics))
        self._wait_connections(0)
        self.assertEqual(self.call('/v1/lookup', control=True),
                         (200, {'status':'UNKNOWN','public_ack':False}))

    def test_active_handler_close_requires_retry_after_exact_backend_drains(self):
        results = []
        def client():
            try:
                results.append(self.call('/v1/commands'))
            except BaseException as error:
                results.append(error)
        worker = threading.Thread(target=client)
        worker.start()
        self.assertTrue(self.backend.entered.wait(1))
        try:
            with self.assertRaisesRegex(SafetyViolation, 'BLENDER_TRANSPORT_DRAIN_REQUIRED') as caught:
                self.server.close()
            self.assertIs(caught.exception.cleanup_owner, self.server)
            self.assertEqual(self.server._connections, 1)
            self.assertFalse(self.server._drained.is_set())
            self.assertTrue(all(listener.socket.fileno() == -1 for listener in self.server._listeners))
        finally:
            self.backend.wait.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.server.close()
        self.assertEqual(results, [(200, {'status':'UNKNOWN','public_ack':False})])
        self.assertEqual(self.server._connections, 0)

    def test_request_thread_start_failure_releases_its_connection_slot(self):
        with patch.object(threading.Thread, 'start', side_effect=RuntimeError('INERT_HANDLER_START_FAILURE')):
            with self.assertRaises((OSError, http.client.HTTPException)):
                self.call('/v1/discovery')
            self._wait_connections(0)
        self.assertIn('BLENDER_HANDLER_FAILED', self.server.diagnostics)
        self.assertEqual(self.call('/v1/discovery'), (200, {'enabled':[], 'public_ack':False}))

    def test_failed_start_retains_transport_when_cleanup_cannot_finish(self):
        partial = transport.BlenderClientTransport(self.backend)
        self.addCleanup(partial.close)
        with patch.object(threading.Thread, 'start', side_effect=RuntimeError('INERT_START_FAILURE')):
            with patch.object(partial, 'close', side_effect=SafetyViolation('INERT_DRAIN_FAILURE')):
                with self.assertRaisesRegex(transport.BlenderClientTransportError,
                                             'BLENDER_TRANSPORT_CLEANUP_REQUIRED') as caught:
                    partial.start()
        self.assertIs(caught.exception.cleanup_owner, partial)
        caught.exception.cleanup_owner.close()
        self.assertTrue(all(server.socket.fileno() == -1 for server in partial._listeners))


if __name__ == '__main__':
    unittest.main()
