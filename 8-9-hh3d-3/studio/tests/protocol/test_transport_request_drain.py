"""Request-thread ownership on shutdown; real loopback sockets, no engine."""
from __future__ import annotations

import gc
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock
import weakref

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT.parent))
from studio.host.core.journal import Journal
from studio.host.core.limits import SafetyViolation
from studio.host.core import transport
from studio.host.core.transport import LoopbackFixtureHost, TransportLimits


class RequestDrainTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt02-request-drain-')
        self.root = Path(self.temp.name)
        self.host = None

    def tearDown(self):
        if self.host is not None:
            self.host.close()
        self.temp.cleanup()

    def host_for(self, *, limits=TransportLimits()):
        self.host = LoopbackFixtureHost('project.fixture', self.root,
            Journal(self.root / 'commands.jsonl'), limits=limits)
        return self.host

    def partial(self, port):
        stream = socket.create_connection(('127.0.0.1', port), timeout=2)
        stream.sendall(b'POST /v1/discovery HTTP/1.1\r\nHost: 127.0.0.1\r\n')
        return stream

    def test_close_waits_for_partial_unauthenticated_requests_on_both_listeners(self):
        host = self.host_for()
        entered = {role: threading.Event() for role in (False, True)}
        requests, threads, clients = {}, {}, []
        original = host._handle

        def handle(stream, listener):
            requests[listener.control] = stream
            threads[listener.control] = threading.current_thread()
            entered[listener.control].set()
            return original(stream, listener)

        with mock.patch.object(host, '_handle', handle):
            host.start()
            try:
                clients = [self.partial(host.port), self.partial(host.control_port)]
                self.assertTrue(all(event.wait(2) for event in entered.values()))
                self.assertTrue(all(thread.is_alive() for thread in threads.values()))
                host.close()
                # Check before the client closes its side: close() must own the drain.
                self.assertEqual({role: thread.is_alive() for role, thread in threads.items()},
                                 {False: False, True: False})
                self.assertTrue(all(stream.fileno() == -1 for stream in requests.values()))
                self.assertFalse(any(thread.is_alive() for thread in host._threads))
                for client in clients:
                    self.assertEqual(client.recv(1), b'')
            finally:
                for client in clients:
                    client.close()
                for thread in threads.values():
                    thread.join(3)

    def test_both_accept_loops_stop_before_request_drain(self):
        host = self.host_for().start()
        events = []
        patches = []
        for role, listener in (('main', host._main), ('control', host._control)):
            shutdown, drain = listener.shutdown, listener.drain_requests
            def stop(role=role, shutdown=shutdown):
                shutdown()
                events.append(role + '-stopped')
            def drained(timeout, role=role, drain=drain):
                self.assertIn('main-stopped', events)
                self.assertIn('control-stopped', events)
                self.assertEqual(host._main.socket.fileno(), -1)
                self.assertEqual(host._control.socket.fileno(), -1)
                events.append(role + '-drained')
                return drain(timeout)
            patches.extend([mock.patch.object(listener, 'shutdown', stop),
                            mock.patch.object(listener, 'drain_requests', drained)])
        from contextlib import ExitStack
        with ExitStack() as stack:
            for item in patches:
                stack.enter_context(item)
            host.close()
        self.assertEqual(events, ['main-stopped', 'control-stopped', 'main-drained', 'control-drained'])

    def test_failed_request_thread_start_releases_slot_and_weak_registration(self):
        host = self.host_for(limits=TransportLimits(max_connections=1))
        listener = host._main
        captured = []
        failure = RuntimeError('synthetic thread start failure')

        def fail_start(thread):
            captured.append(weakref.ref(thread))
            self.assertIn(thread, listener._request_threads)
            raise failure

        with mock.patch.object(threading.Thread, 'start', fail_start):
            with self.assertRaises(RuntimeError) as raised:
                listener.process_request(mock.Mock(spec=socket.socket), ('127.0.0.1', 100))
        self.assertIs(raised.exception, failure)
        self.assertEqual(list(listener._request_threads), [])
        self.assertTrue(listener.slots.acquire(blocking=False))
        self.assertFalse(listener.slots.acquire(blocking=False))
        listener.slots.release()
        # The exception's traceback is an external reference; the listener is not.
        failure.__traceback__ = None
        del raised
        gc.collect()
        self.assertIsNone(captured[0]())

    def test_completed_requests_are_not_strongly_retained_by_listener(self):
        host = self.host_for()
        entered, finished = threading.Event(), threading.Event()
        weak_threads = []

        def handle(stream, listener):
            weak_threads.append(weakref.ref(threading.current_thread()))
            entered.set()
            finished.set()

        with mock.patch.object(host, '_handle', handle):
            host.start()
            with socket.create_connection(('127.0.0.1', host.port), timeout=2) as client:
                self.assertTrue(entered.wait(2))
                self.assertTrue(finished.wait(2))
                self.assertEqual(client.recv(1), b'')
            thread = weak_threads[0]()
            if thread is not None:
                thread.join(2)
            del thread
            gc.collect()
            self.assertIsNone(weak_threads[0]())
            host.close()
        gc.collect()
        self.assertIsNone(weak_threads[0]())
        self.assertIsInstance(host._main._request_threads, weakref.WeakSet)
        self.assertEqual(list(host._main._request_threads), [])

    def test_bounded_drain_failure_still_cleans_other_listener_and_can_retry(self):
        host = self.host_for(limits=TransportLimits(readback_timeout_ms=50))
        held, release, control_entered = threading.Event(), threading.Event(), threading.Event()
        requests, threads, clients = {}, {}, []
        original = host._handle

        def handle(stream, listener):
            requests[listener.control] = stream
            threads[listener.control] = threading.current_thread()
            if listener.control:
                control_entered.set()
                return original(stream, listener)
            held.set()
            release.wait(10)

        with mock.patch.object(host, '_handle', handle):
            host.start()
            try:
                clients = [self.partial(host.port), self.partial(host.control_port)]
                self.assertTrue(held.wait(2))
                self.assertTrue(control_entered.wait(2))
                with mock.patch.object(host._control, 'drain_requests',
                                       wraps=host._control.drain_requests) as second:
                    began = time.monotonic()
                    with self.assertRaisesRegex(SafetyViolation, 'HOST_DRAIN_TIMEOUT') as raised:
                        host.close()
                    elapsed = time.monotonic() - began
                    second.assert_called_once()
                self.assertLess(elapsed, 4)
                self.assertIs(raised.exception.cleanup_owner, host)
                self.assertTrue(threads[False].is_alive())
                self.assertIn(threads[False], host._main._request_threads)
                self.assertFalse(threads[True].is_alive())
                self.assertEqual(requests[True].fileno(), -1)
                self.assertEqual(host._main.socket.fileno(), -1)
                self.assertEqual(host._control.socket.fileno(), -1)
                self.assertFalse(any(thread.is_alive() for thread in host._threads))
                release.set()
                raised.exception.cleanup_owner.close()
                self.assertFalse(threads[False].is_alive())
                self.assertEqual(requests[False].fileno(), -1)
            finally:
                release.set()
                for client in clients:
                    client.close()
                for thread in threads.values():
                    thread.join(3)

    def test_listener_close_failure_does_not_skip_second_listener_or_fixed_joins(self):
        host = self.host_for().start()
        failure = OSError('synthetic close failure')
        with mock.patch.object(host._main, 'server_close', side_effect=failure), \
             mock.patch.object(host._control, 'server_close', wraps=host._control.server_close) as second:
            with self.assertRaises(OSError) as raised:
                host.close()
        self.assertIs(raised.exception, failure)
        self.assertIs(raised.exception.cleanup_owner, host)
        second.assert_called_once()
        self.assertEqual(host._control.socket.fileno(), -1)
        self.assertFalse(any(thread.is_alive() for thread in host._threads))
        host.close()
        self.assertEqual(host._main.socket.fileno(), -1)

    def test_unstarted_and_failed_fixed_thread_start_close_without_deadlock(self):
        host = self.host_for()
        host.close()
        host.close()
        self.assertEqual(host._main.socket.fileno(), -1)
        self.assertEqual(host._control.socket.fileno(), -1)
        self.assertEqual(host._threads, [])
        with self.assertRaisesRegex(SafetyViolation, 'HOST_ALREADY_STARTED'):
            host.start()
        host = self.host_for()
        original = threading.Thread.start
        starts = 0
        def fail_second(thread):
            nonlocal starts
            starts += 1
            if starts == 2:
                raise RuntimeError('synthetic second accept thread start failure')
            return original(thread)
        with mock.patch.object(threading.Thread, 'start', fail_second):
            with self.assertRaises(RuntimeError):
                host.start()
        host.close()
        self.assertFalse(any(thread.is_alive() for thread in host._threads))
        self.assertEqual(host._main.socket.fileno(), -1)
        self.assertEqual(host._control.socket.fileno(), -1)

    def test_second_listener_constructor_failure_closes_first_without_request_drain(self):
        listener_type = transport._Listener
        created = []
        def construct(owner, control):
            if control:
                raise OSError('synthetic second listener construction failure')
            listener = listener_type(owner, control)
            created.append(listener)
            return listener
        with mock.patch.object(transport, '_Listener', side_effect=construct):
            with self.assertRaises(OSError):
                self.host_for()
        self.assertEqual(created[0].socket.fileno(), -1)
        self.assertEqual(list(created[0]._request_threads), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
