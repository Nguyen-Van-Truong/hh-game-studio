"""Adversarial reviewer checks; synthetic protocol/local sockets, not native proof."""
from contextlib import contextmanager
import copy
import http.client
from pathlib import Path
import select
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.core.transport import epoch_ms
from studio.host.replay.trace import default_trace
from studio.protocol.core import Response, Status
from studio.reviewer import client as client_module
from studio.reviewer.client import ReplayClient
from studio.reviewer.model import UiAction, Phase, UiCode


_SECRET = 'private-adversary-bearer'


def binding():
    return {'run_id': 'run.client-adversary', 'command_id': 'run.client-adversary.play',
        'runtime_instance_id': 'runtime.client-adversary', 'generation': 1,
        'source_closure_sha256': '1' * 64, 'runtime_snapshot_sha256': '2' * 64,
        'trace_sha256': default_trace(17).raw_sha256, 'glb_sha256': '3' * 64}


def make_client(port=12340):
    return ReplayClient(port=port, control_port=1, stop_port=2,
        credential=SimpleNamespace(bearer=_SECRET), project_id='fixture.client-adversary',
        binding=binding())


def terminal(client):
    return Response(Status.COMMITTED, 'REPLAY_NATIVE_COMPLETED', client._command,
        postconditions={'public_ack': False, 'binding': binding(),
            'native_capture_sha256': '5' * 64,
            'process': {'pid': 123, 'process_start': 'windows:123456'},
            'artifact': {'kind': 'observation', 'sha256': '4' * 64, 'size_bytes': 100}}).as_dict()


def inspection():
    return {'schema_id': 'hh-studio.retained-play-inspection', 'schema_version': '1.0.0',
        'historical': True, 'completed': True, 'live': False, 'formal_acceptance': False,
        'provenance': {'binding': binding(), 'native_capture_sha256': '5' * 64,
            'report_sha256': '4' * 64, 'process': {'pid': 123, 'process_start': 'windows:123456'}},
        'semantics': {'complete': True, 'all_postconditions': True, 'movement_fault_observed': False},
        'rows': [{'tick': 165, 'properties': {'phase': 'PAUSED', 'sim_tick': 140,
            'ui_tick': 165, 'body_position': [1.5, 0.925, 0.0]}}],
        'returned_count': 1, 'total_matches': 1, 'next_cursor': None}


@contextmanager
def slow_http_peer(part):
    """Finite valid response stream, with causal disconnect/completion witnesses."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    listener.settimeout(5)
    port = listener.getsockname()[1]
    stop = threading.Event()
    connected = []
    peer = SimpleNamespace(port=port, complete=threading.Event(),
        disconnected=threading.Event(), done=threading.Event())

    def serve():
        try:
            conn, _ = listener.accept()
            connected.append(conn)
            with conn:
                conn.settimeout(5)
                request = b''
                while b'\r\n\r\n' not in request and len(request) <= 8192:
                    piece = conn.recv(1024)
                    if not piece:
                        peer.disconnected.set()
                        return
                    request += piece
                headers, buffered = request.split(b'\r\n\r\n', 1)
                length = next(int(line.split(b':', 1)[1]) for line in headers.split(b'\r\n')
                    if line.lower().startswith(b'content-length:'))
                if length > 1024:
                    return
                while len(buffered) < length:
                    piece = conn.recv(1024)
                    if not piece:
                        peer.disconnected.set()
                        return
                    buffered += piece
                # Never retain or emit credentials received in these headers.
                del request, headers, buffered
                if part == 'headers':
                    conn.sendall(b'HTTP/1.1 200 OK\r\nX-Slow: ')
                    fragment = b'x'
                    finish = b'\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}'
                else:
                    conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 258\r\nConnection: close\r\n\r\n{')
                    fragment = b' '
                    finish = b'}'
                # ~5 seconds of regular traffic defeats an inactivity-only
                # timeout. There is no unbounded peer, even in a failed test.
                for _ in range(256):
                    if stop.wait(0.02):
                        return
                    if select.select([conn], [], [], 0)[0] and not conn.recv(1):
                        peer.disconnected.set()
                        return
                    conn.sendall(fragment)
                conn.sendall(finish)
                peer.complete.set()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            if connected:
                peer.disconnected.set()
        except OSError:
            pass  # A peer timeout is not evidence of a deadline disconnect.
        finally:
            peer.done.set()

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        yield peer
    finally:
        stop.set()
        listener.close()
        for conn in connected:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        worker.join(5)
        if worker.is_alive():
            raise AssertionError('owned slow HTTP peer did not drain')


class BoundProjectionTests(unittest.TestCase):
    def setUp(self):
        self.client = make_client()

    def lookup(self, receipt):
        self.client._attempted = True
        with patch.object(self.client, '_call', return_value=receipt):
            return self.client.perform(UiAction.LOOKUP)

    def inspect(self, observed):
        self.assertEqual(self.lookup(terminal(self.client)).phase, Phase.COMMITTED)

        def submit(command, operation, payload):
            self.assertEqual(operation, 'play.inspect')
            self.assertEqual(payload['phase'], 'PAUSED')
            return Response(Status.COMMITTED, 'REPLAY_INSPECTION_READY', command,
                postconditions={'public_ack': False, 'observation': observed}).as_dict()

        with patch.object(self.client, '_submit', side_effect=submit):
            return self.client.perform(UiAction.INSPECT)

    def assert_invalid(self, event):
        self.assertEqual((event.phase, event.code), (Phase.UNKNOWN, UiCode.INVALID_RESPONSE))
        self.assertIsNone(event.historical)
        self.assertNotIn(_SECRET, repr(event))

    def test_terminal_requires_native_capture_digest_before_retention(self):
        for digest in (None, True, 'x' * 64, '5' * 63, '5' * 65, 'A' * 64):
            with self.subTest(digest=digest):
                receipt = terminal(self.client)
                receipt['postconditions']['native_capture_sha256'] = digest
                self.assert_invalid(self.lookup(receipt))
                self.assertIsNone(self.client._terminal)

    def test_terminal_requires_present_native_capture_digest(self):
        receipt = terminal(self.client)
        del receipt['postconditions']['native_capture_sha256']
        self.assert_invalid(self.lookup(receipt))
        self.assertIsNone(self.client._terminal)

    def test_process_start_is_canonical_positive_uint64(self):
        for start in ('windows:not-a-number', 'windows:0', 'windows:0123',
                      'windows:18446744073709551616', 'windows:123\n', True):
            with self.subTest(start=start):
                receipt = terminal(self.client)
                receipt['postconditions']['process']['process_start'] = start
                self.assert_invalid(self.lookup(receipt))
                self.assertIsNone(self.client._terminal)

    def test_uint64_max_process_start_remains_admissible(self):
        receipt = terminal(self.client)
        receipt['postconditions']['process']['process_start'] = 'windows:18446744073709551615'
        self.assertEqual(self.lookup(receipt).phase, Phase.COMMITTED)

    def test_inspection_requires_same_native_capture_anchor(self):
        observed = inspection()
        observed['provenance']['native_capture_sha256'] = '6' * 64
        self.assert_invalid(self.inspect(observed))

    def test_inspection_rejects_changed_schema_and_projection(self):
        cases = []
        observed = inspection()
        observed['schema_id'] = 'other.schema'
        cases.append(observed)
        observed = inspection()
        observed['rows'][0]['properties']['phase'] = 'PLAY'
        cases.append(observed)
        observed = inspection()
        observed['returned_count'] = True
        cases.append(observed)
        observed = inspection()
        observed['rows'][0]['properties']['private_path'] = _SECRET
        cases.append(observed)
        for index, observed in enumerate(cases):
            with self.subTest(case=index):
                self.assert_invalid(self.inspect(observed))

    def test_inspection_rejects_duplicate_or_descending_ticks(self):
        for second_tick in (165, 164):
            with self.subTest(second_tick=second_tick):
                observed = inspection()
                observed['rows'].append(copy.deepcopy(observed['rows'][0]))
                observed['rows'][1]['tick'] = second_tick
                observed['returned_count'] = observed['total_matches'] = 2
                self.assert_invalid(self.inspect(observed))

    def test_valid_inspection_is_detached_and_secret_free(self):
        observed = inspection()
        event = self.inspect(observed)
        self.assertEqual((event.phase, event.code), (Phase.COMMITTED, UiCode.INSPECTION_READY))
        observed['rows'][0]['properties']['body_position'][0] = 999
        self.assertEqual(event.historical.rows[0].body_position, (1.5, 0.925, 0.0))
        self.assertNotIn(_SECRET, repr(event))
        self.assertNotIn('process_start', repr(event))


class StopRaceTests(unittest.TestCase):
    def test_stop_during_lease_prevents_later_play_submission(self):
        client = make_client()
        lease_entered, release_lease = threading.Event(), threading.Event()
        calls, results = [], []

        def wire(route, body):
            calls.append(route)
            if route == '/v1/lease':
                lease_entered.set()
                if not release_lease.wait(1):
                    raise TimeoutError()
                return {'binding': binding(), 'lease_id': 'lease.adversary', 'fencing_epoch': 1,
                    'expected_revision': 'sha256:' + '2' * 64, 'expires_ms': epoch_ms() + 30_000}
            if route == '/v1/stop':
                return {'stopped': True, 'runtime_instance_id': binding()['runtime_instance_id']}
            if route == '/v1/lookup':
                return Response(Status.UNKNOWN, 'REPLAY_UNKNOWN', client._command).as_dict()
            raise AssertionError('Play submitted after Stop')

        with patch.object(client, '_call', side_effect=wire):
            worker = threading.Thread(target=lambda: results.append(client.perform(UiAction.PLAY)))
            worker.start()
            try:
                self.assertTrue(lease_entered.wait(1))
                self.assertEqual(client.perform(UiAction.STOP).phase, Phase.DRAINING)
            finally:
                release_lease.set()
                worker.join(2)
            self.assertFalse(worker.is_alive())
            client.perform(UiAction.PLAY)
        self.assertNotIn('/v1/commands', calls)
        self.assertEqual(calls.count('/v1/lease'), 1)
        self.assertEqual(calls.count('/v1/lookup'), 1)
        self.assertTrue(client._stopped.is_set())

    def test_late_committed_play_cannot_overwrite_stop_latch(self):
        client = make_client()
        command_entered, release_command = threading.Event(), threading.Event()
        results = []

        def wire(route, body):
            if route == '/v1/lease':
                return {'binding': binding(), 'lease_id': 'lease.adversary', 'fencing_epoch': 1,
                    'expected_revision': 'sha256:' + '2' * 64, 'expires_ms': epoch_ms() + 30_000}
            if route == '/v1/commands':
                command_entered.set()
                if not release_command.wait(1):
                    raise TimeoutError()
                return terminal(client)
            if route == '/v1/stop':
                return {'stopped': True, 'runtime_instance_id': binding()['runtime_instance_id']}
            raise AssertionError(route)

        with patch.object(client, '_call', side_effect=wire):
            worker = threading.Thread(target=lambda: results.append(client.perform(UiAction.PLAY)))
            worker.start()
            try:
                self.assertTrue(command_entered.wait(1))
                self.assertEqual(client.perform(UiAction.STOP).phase, Phase.DRAINING)
            finally:
                release_command.set()
                worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(results), 1)
        self.assertEqual((results[0].phase, results[0].code), (Phase.DRAINING, UiCode.DRAINING))
        self.assertIsNone(results[0].historical)
        self.assertTrue(client._stopped.is_set())


class HttpDeadlineTests(unittest.TestCase):
    def assert_bounded_drip(self, part):
        real_timer = threading.Timer
        real_connection = http.client.HTTPConnection
        fired = threading.Event()
        timers = []

        def recorded_timer(interval, callback):
            def expire():
                fired.set()
                callback()
            timer = real_timer(interval, expire)
            timers.append(timer)
            return timer

        def patient_connection(*args, **kwargs):
            # Isolate the total-deadline mechanism from incidental per-read
            # timeouts when the operating system delays either test thread.
            kwargs['timeout'] = 10
            return real_connection(*args, **kwargs)

        with slow_http_peer(part) as peer:
            client = make_client(peer.port)
            with patch.object(client_module, 'HTTP_CALL_SECONDS', 0.2), \
                 patch.object(client_module.threading, 'Timer', side_effect=recorded_timer), \
                 patch.object(client_module.http.client, 'HTTPConnection', side_effect=patient_connection):
                started = time.monotonic()
                with self.assertRaises((OSError, http.client.HTTPException)):
                    client._call('/v1/discovery', {})
                elapsed = time.monotonic() - started
            self.assertEqual(len(timers), 1)
            self.assertTrue(fired.is_set(), 'read failed without the whole-call timer firing')
            self.assertFalse(peer.complete.is_set(), 'peer sent its complete response before interruption')
            self.assertTrue(peer.disconnected.wait(5), 'peer did not observe the deadline disconnect')
            self.assertTrue(peer.done.wait(5), 'interrupted peer did not drain')
            timers[0].join(5)
            self.assertFalse(timers[0].is_alive(), 'owned deadline timer did not drain')
            # Generous outer safety bound only; this test makes no subsecond
            # scheduling or latency-percentile claim under machine pressure.
            self.assertLess(elapsed, 15, 'whole-call test exceeded its outer safety bound')

    def test_dripping_headers_obey_whole_request_deadline(self):
        self.assert_bounded_drip('headers')

    def test_dripping_body_obeys_whole_request_deadline(self):
        self.assert_bounded_drip('body')

    def test_complete_response_after_expiry_is_never_returned(self):
        client = make_client()
        closed = threading.Event()
        response = SimpleNamespace(status=200, read=lambda _: b'{}')
        connection = SimpleNamespace(sock=SimpleNamespace(shutdown=lambda _: None),
            connect=lambda: None, request=lambda *args: None,
            getresponse=lambda: response, close=closed.set)
        # Model delayed timer scheduling: the full response arrives after the
        # monotonic deadline, before its timer callback has been scheduled.
        timer = SimpleNamespace(start=lambda: None, cancel=lambda: None)
        with patch.object(client_module, 'HTTP_CALL_SECONDS', 0.2), \
             patch.object(client_module.http.client, 'HTTPConnection', return_value=connection), \
             patch.object(client_module.threading, 'Timer', return_value=timer), \
             patch.object(client_module.time, 'monotonic', side_effect=[10.0, 10.01, 11.0]):
            with self.assertRaises(TimeoutError):
                client._call('/v1/discovery', {})
        self.assertTrue(closed.is_set())


if __name__ == '__main__':
    unittest.main()
