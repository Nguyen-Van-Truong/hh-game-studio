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

    def call(self, path, *, control=False, body=None, token=None, headers=None):
        port = self.server.control_port if control else self.server.port
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

    def test_second_listener_start_failure_closes_started_and_unstarted_owners(self):
        # Run under the bounded host test runner: a regression that calls
        # shutdown() on the never-started server must not hang an outer run.
        partial = transport.PublicationTransport(self.backend)
        self.addCleanup(partial.close)
        original_start = threading.Thread.start
        attempted = []

        def fail_second_once(thread):
            attempted.append(thread)
            if len(attempted) == 2:
                raise RuntimeError('INJECT_SECOND_LISTENER_START_FAILURE')
            return original_start(thread)

        started = time.monotonic()
        with patch.object(threading.Thread, 'start', fail_second_once):
            with self.assertRaisesRegex(RuntimeError, 'INJECT_SECOND_LISTENER_START_FAILURE'):
                partial.start()
        self.assertLess(time.monotonic() - started, 2.0, 'partial start cleanup must be bounded')
        self.assertEqual(len(attempted), 2)
        self.assertIsNotNone(attempted[0].ident, 'first listener really started')
        self.assertIsNone(attempted[1].ident, 'second listener never entered its serve loop')
        self.assertFalse(any(thread.is_alive() for thread in attempted))
        self.assertEqual(partial._main.socket.fileno(), -1)
        self.assertEqual(partial._control.socket.fileno(), -1)
        self.assertEqual(partial._connections, 0)
        self.assertTrue(partial._drained.is_set())
        partial.close()  # Cleanup remains idempotent after the start exception.
        with self.assertRaisesRegex(SafetyViolation, 'GODOT_TRANSPORT_ALREADY_STARTED'):
            partial.start()


if __name__ == '__main__':
    unittest.main()
