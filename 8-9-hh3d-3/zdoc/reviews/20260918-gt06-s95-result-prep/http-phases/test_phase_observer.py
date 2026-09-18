"""Focused fake-only checks; no runtime imports, sockets, engine or disk writes."""
from contextlib import contextmanager
import http.client
import itertools
import json
import threading
import unittest
from unittest.mock import patch

import phase_observer as phases


def rows(snapshot, phase, kind):
    return [row for row in snapshot['events'] if row['phase'] == phase and row['kind'] == kind]


class Socket:
    def __init__(self, *, client, port=48001):
        endpoints = (('127.0.0.1', port), ('127.0.0.1', 32101))
        self.local, self.peer = endpoints if client else endpoints[::-1]

    def getsockname(self):
        return self.local

    def getpeername(self):
        return self.peer


class RecorderTests(unittest.TestCase):
    def test_qpc_entries_and_unfinished_span_survive_ring_eviction(self):
        ticks = itertools.count(1_000_000, 1000)
        recorder = phases.PhaseRecorder(event_capacity=2)
        with patch.object(phases.time, 'perf_counter_ns', side_effect=lambda: next(ticks)), \
                patch.object(phases.time, 'monotonic_ns', side_effect=AssertionError('coarse clock')):
            with recorder.span('server.handle') as outer:
                with recorder.span('server.lookup'):
                    pass
                snapshot = recorder.snapshot()
                self.assertEqual(snapshot['unfinished'][0]['span_id'], outer)
                self.assertEqual(snapshot['unfinished'][0]['started_ns'], 1_000_000)
                self.assertEqual(snapshot['events_evicted'], 1)
                self.assertFalse(rows(snapshot, 'server.handle', 'enter'))
            final = recorder.snapshot()
        self.assertEqual(final['unfinished'], [])
        self.assertEqual(final['events_evicted'], 2)
        self.assertEqual(rows(final, 'server.handle', 'exit')[0]['timestamp_ns'], 1_004_000)

    def test_active_overflow_is_explicit_without_skipping_operation(self):
        recorder = phases.PhaseRecorder(active_capacity=1)
        executed = []
        with recorder.span('client.call'):
            with recorder.span('client.request') as missing:
                executed.append('delegated')
                self.assertIsNone(missing)
                recorder.capture_failure(missing, route='lookup')
        snapshot = recorder.snapshot()
        self.assertEqual(executed, ['delegated'])
        self.assertEqual(snapshot['spans_dropped'], 1)
        self.assertEqual(len(snapshot['first_failure']['unfinished']), 1)
        self.assertIsNone(snapshot['first_failure']['failed_call_id'])

    def test_failure_copy_and_returned_snapshots_cannot_mutate_retained_state(self):
        recorder = phases.PhaseRecorder()
        with recorder.span('client.call') as first:
            recorder.capture_failure(first, route='lookup')
        with recorder.span('client.call') as second:
            recorder.capture_failure(second, route='lookup')
        snapshot = recorder.snapshot()
        self.assertEqual(snapshot['transport_failures_observed'], 2)
        self.assertEqual(snapshot['first_failure']['failed_call_id'], first)
        self.assertEqual(snapshot['first_failure']['unfinished'][0]['span_id'], first)
        snapshot['events'][0]['phase'] = 'secret'
        snapshot['first_failure']['unfinished'][0]['phase'] = 'secret'
        snapshot['first_failure']['events'].clear()
        snapshot['first_failure']['transport_failures_by_route']['lookup'] = 99
        again = recorder.snapshot()
        self.assertEqual(again['events'][0]['phase'], 'client.call')
        self.assertEqual(len(again['first_failure']['events']), 1)
        self.assertEqual(again['first_failure']['unfinished'][0]['phase'], 'client.call')
        self.assertEqual(again['first_failure']['transport_failures_by_route']['lookup'], 1)
        self.assertEqual(again['unfinished'], [])

    def test_fixed_enums_capacity_guards_and_missing_socket_identity(self):
        for kwargs in ({'event_capacity': True}, {'event_capacity': 0},
                       {'event_capacity': 8193}, {'active_capacity': 257}):
            with self.assertRaises(ValueError):
                phases.PhaseRecorder(**kwargs)
        recorder = phases.PhaseRecorder()
        for name, route in (('secret', None), ('client.call', 'secret')):
            with self.assertRaises(ValueError):
                with recorder.span(name, route=route):
                    self.fail('invalid enum admitted')
        for bad_id in (True, 0, -1, 'secret', object()):
            with self.assertRaises(ValueError):
                recorder.capture_failure(bad_id, route='lookup')
        with self.assertRaises(ValueError):
            recorder.capture_failure(None, route='secret')
        stream = Socket(client=True)
        stream.peer = ('example.invalid', 32101)
        with recorder.span('client.call'):
            recorder.bind_socket(stream, client=True)
        self.assertEqual(recorder.snapshot()['identity_missing'], 1)
        self.assertEqual(phases.route_for('/v1/lookup?secret'), 'other')
        self.assertNotIn('secret', json.dumps(recorder.snapshot()))

    def test_failure_freezes_unfinished_server_span_from_another_thread(self):
        recorder = phases.PhaseRecorder()
        entered, release = threading.Event(), threading.Event()
        errors = []
        def server():
            try:
                with recorder.span('server.handle'):
                    recorder.bind_socket(Socket(client=False), client=False)
                    with recorder.span('server.lookup'):
                        entered.set()
                        if not release.wait(5):
                            raise AssertionError('server release not signaled')
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=server, daemon=True)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with recorder.span('client.call', route='lookup') as call_id:
                recorder.bind_socket(Socket(client=True), client=True)
                recorder.capture_failure(call_id, route='lookup')
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        snapshot = recorder.snapshot()
        unfinished = snapshot['first_failure']['unfinished']
        self.assertEqual({row['phase'] for row in unfinished}, {'client.call', 'server.handle', 'server.lookup'})
        self.assertEqual({(row['server_port'], row['client_port']) for row in unfinished}, {(32101, 48001)})
        server_root = next(row['root_id'] for row in unfinished if row['phase'] == 'server.lookup')
        self.assertNotEqual(server_root, call_id)
        self.assertEqual(len({row['thread_id'] for row in unfinished}), 2)
        self.assertEqual(snapshot['unfinished'], [])
        self.assertEqual(rows(snapshot, 'server.lookup', 'exit')[0]['outcome'], 'returned')


class ResponseBase:
    def __init__(self, connection):
        self.connection, self.status = connection, 200

    def read(self, *args, **kwargs):
        self.connection.read_args = (args, kwargs)
        self.connection.maybe_raise('body')
        return b'SECRET_RESPONSE'


class ConnectionBase:
    response_class = ResponseBase
    instances = []
    failures = []

    def __init__(self, host, port, *, timeout):
        self.constructor_args = (host, port, timeout)
        self.sock = None
        self.closed = 0
        self.failure = self.failures.pop(0) if self.failures else None
        self.error = TimeoutError('SECRET_EXCEPTION')
        self.client_port = 48001 + len(self.instances)
        self.instances.append(self)

    def maybe_raise(self, phase):
        if self.failure == phase:
            raise self.error

    def connect(self):
        self.maybe_raise('connect')
        self.sock = Socket(client=True, port=self.client_port)

    def request(self, *args, **kwargs):
        self.request_args = (args, kwargs)
        self.connect()
        self.maybe_raise('request')

    def getresponse(self):
        self.maybe_raise('headers')
        return self.response_class(self)

    def close(self):
        self.closed += 1


class ClientBase:
    last_transport_failure = None

    def _call(self, path, body, *, control=False):
        self.last_transport_failure = None
        self.received_args = (path, body, control)
        connection = http.client.HTTPConnection('127.0.0.1', 32101, timeout=2.0)
        try:
            connection.request('POST', path, b'SECRET_BODY', {'Authorization': 'SECRET_BEARER'})
            response = connection.getresponse()
            self.response_type = type(response)
            return response.read(4097)
        except OSError as error:
            self.received_error = error
            self.last_transport_failure = {'stage': connection.failure}
            return {'status': 'UNKNOWN', 'code': 'CONNECTION_LOST_LOOKUP'}
        finally:
            connection.close()


class ClientTests(unittest.TestCase):
    def setUp(self):
        ConnectionBase.instances, ConnectionBase.failures = [], []
        self.recorder = phases.PhaseRecorder()
        self.connection_type = phases.observed_connection_type(ConnectionBase, self.recorder)
        self.client = phases.observed_client_type(ClientBase, self.recorder)()

    def test_delegation_preserves_wire_arguments_results_close_and_secret_absence(self):
        body = {'command_id': 'SECRET_COMMAND'}
        with patch.object(http.client, 'HTTPConnection', self.connection_type):
            result = self.client._call('/v1/lookup', body, control=True)
        connection = ConnectionBase.instances[0]
        self.assertEqual(result, b'SECRET_RESPONSE')
        self.assertIs(self.client.received_args[1], body)
        self.assertEqual(self.client.received_args[2], True)
        self.assertEqual(connection.constructor_args, ('127.0.0.1', 32101, 2.0))
        self.assertEqual(connection.request_args, (
            ('POST', '/v1/lookup', b'SECRET_BODY', {'Authorization': 'SECRET_BEARER'}), {}))
        self.assertEqual(connection.read_args, ((4097,), {}))
        self.assertEqual(connection.closed, 1)
        self.assertTrue(issubclass(self.client.response_type, ResponseBase))
        snapshot = self.recorder.snapshot()
        self.assertNotIn('SECRET', json.dumps(snapshot))
        self.assertIsNone(snapshot['first_failure'])
        for phase in ('client.call', 'client.connect', 'client.request', 'client.headers', 'client.body'):
            row = rows(snapshot, phase, 'exit')[0]
            self.assertEqual((row['server_port'], row['client_port']), (32101, 48001))
            self.assertEqual(row['route'], 'lookup')
            self.assertEqual(row['outcome'], 'returned')

    def test_retry_has_distinct_call_and_port_and_freezes_before_metadata_reset(self):
        ConnectionBase.failures = ['headers', None]
        body = {'command_id': 'same.id'}
        with patch.object(http.client, 'HTTPConnection', self.connection_type):
            failed = self.client._call('/v1/lookup', body, control=True)
            success = self.client._call('/v1/lookup', body, control=True)
        self.assertEqual(failed['status'], 'UNKNOWN')
        self.assertEqual(success, b'SECRET_RESPONSE')
        self.assertIsNone(self.client.last_transport_failure)
        snapshot = self.recorder.snapshot()
        calls = rows(snapshot, 'client.call', 'exit')
        self.assertNotEqual(calls[0]['root_id'], calls[1]['root_id'])
        self.assertEqual([row['client_port'] for row in calls], [48001, 48002])
        first = snapshot['first_failure']
        self.assertEqual(first['failed_call_id'], calls[0]['span_id'])
        self.assertEqual([row['span_id'] for row in first['unfinished']], [calls[0]['span_id']])
        self.assertEqual(rows(first, 'client.headers', 'exit')[0]['outcome'], 'raised')
        self.assertFalse(rows(first, 'client.call', 'exit'))
        self.assertNotIn(calls[1]['span_id'], [row['span_id'] for row in first['events']])

    def test_each_failure_phase_preserves_exception_and_operation_count(self):
        for phase in ('connect', 'request', 'headers', 'body'):
            with self.subTest(phase=phase):
                self.setUp()
                ConnectionBase.failures = [phase]
                with patch.object(http.client, 'HTTPConnection', self.connection_type):
                    result = self.client._call('/v1/lookup', {})
                self.assertEqual(result['status'], 'UNKNOWN')
                self.assertEqual(len(ConnectionBase.instances), 1)
                connection = ConnectionBase.instances[0]
                self.assertIs(self.client.received_error, connection.error)
                self.assertEqual(connection.closed, 1)
                snapshot = self.recorder.snapshot()
                self.assertEqual(snapshot['transport_failures_observed'], 1)
                self.assertEqual(rows(snapshot, 'client.' + phase, 'exit')[0]['outcome'], 'raised')
                self.assertNotIn('SECRET', json.dumps(snapshot))

    def test_commands_drop_does_not_consume_later_lookup_failure_window(self):
        ConnectionBase.failures = ['headers', 'headers', None]
        with patch.object(http.client, 'HTTPConnection', self.connection_type):
            self.client._call('/v1/commands', {'command_id': 'same.id'})
            after_commands = self.recorder.snapshot()
            self.assertIsNone(after_commands['first_failure'])
            self.assertEqual(after_commands['transport_failures_by_route']['commands'], 1)
            self.client._call('/v1/lookup', {'command_id': 'same.id'}, control=True)
            self.client._call('/v1/lookup', {'command_id': 'same.id'}, control=True)
        snapshot = self.recorder.snapshot()
        calls = rows(snapshot, 'client.call', 'exit')
        self.assertEqual(snapshot['transport_failures_observed'], 2)
        self.assertEqual(snapshot['transport_failures_by_route']['commands'], 1)
        self.assertEqual(snapshot['transport_failures_by_route']['lookup'], 1)
        self.assertEqual(set(snapshot['transport_failures_by_route']), phases.ROUTES)
        self.assertEqual(snapshot['failure_trigger'], 'first_lookup_transport_failure')
        self.assertEqual(snapshot['first_failure']['failed_call_id'], calls[1]['span_id'])
        self.assertEqual(snapshot['first_failure']['unfinished'][0]['route'], 'lookup')
        self.assertNotEqual(calls[0]['span_id'], calls[1]['span_id'])


class HostTests(unittest.TestCase):
    def test_boundaries_delegate_same_arguments_and_join_client_server_ports(self):
        recorder, received, result = phases.PhaseRecorder(), [], object()
        class HostBase:
            def _handle(self, stream, listener):
                received.append(('handle', stream, listener))
                path, body = self._read_request(stream)
                reply = self._dispatch(path, body, listener, True)
                return self._send(stream, reply, 201, listener)

            def _read_request(self, stream):
                received.append(('read', stream))
                return '/v1/lookup', {'command_id': 'SECRET_COMMAND'}

            def _dispatch(self, path, body, session, control):
                received.append(('dispatch', path, body, session, control))
                return self._lookup(body['command_id'])

            def _lookup(self, command_id):
                received.append(('lookup', command_id))
                return result

            def _send(self, stream, value, status=200, redactor=None):
                received.append(('send', stream, value, status, redactor))
                return value

            def _finish(self, job, response):
                received.append(('finish', job, response))
                return response

        host = phases.observed_host_type(HostBase, recorder)()
        stream, listener, job = Socket(client=False), object(), object()
        self.assertIs(host._handle(stream, listener), result)
        self.assertIs(host._finish(job, result), result)
        self.assertEqual([item[0] for item in received], ['handle', 'read', 'dispatch', 'lookup', 'send', 'finish'])
        self.assertEqual(received[-2], ('send', stream, result, 201, listener))
        self.assertEqual(received[-1], ('finish', job, result))
        snapshot = recorder.snapshot()
        dispatch = rows(snapshot, 'server.dispatch', 'enter')[0]
        lookup = rows(snapshot, 'server.lookup', 'enter')[0]
        send = rows(snapshot, 'server.send', 'enter')[0]
        self.assertLess(dispatch['event_id'], lookup['event_id'])
        self.assertLess(rows(snapshot, 'server.lookup', 'exit')[0]['event_id'], send['event_id'])
        self.assertEqual(lookup['route'], 'lookup')
        self.assertEqual((lookup['server_port'], lookup['client_port']), phases.loopback_pair(Socket(client=True), client=True))
        self.assertEqual(send['root_id'], lookup['root_id'])
        self.assertNotIn('SECRET', json.dumps(snapshot))
        self.assertNotIn('lock_wait', json.dumps(snapshot))


class JournalTests(unittest.TestCase):
    def test_method_delegation_and_nested_snapshot(self):
        recorder, arguments, marker = phases.PhaseRecorder(), [], object()
        class JournalBase:
            def _snapshot(self, *, synchronize):
                arguments.append(synchronize)
                return marker

            def _reload(self):
                return self._snapshot(synchronize=True)

            def _append(self, record):
                arguments.append(record)
                return record

            def _load(self):
                return marker

        journal = phases.observed_journal_type(JournalBase, recorder)()
        self.assertIs(journal._reload(), marker)
        self.assertIs(journal._append(marker), marker)
        self.assertIs(journal._load(), marker)
        self.assertEqual(arguments, [True, marker])
        snapshot = recorder.snapshot()
        reload = rows(snapshot, 'journal.reload', 'enter')[0]
        nested = rows(snapshot, 'journal.snapshot', 'enter')[0]
        self.assertEqual(nested['parent_id'], reload['span_id'])

    def test_guard_acquisition_body_release_and_suppression_preserve_base_semantics(self):
        for failure in (None, 'acquire', 'body', 'release', 'suppressed'):
            with self.subTest(failure=failure):
                recorder, calls, marker = phases.PhaseRecorder(), [], object()
                error = ValueError('SECRET_EXCEPTION')
                class JournalBase:
                    @contextmanager
                    def _writer_lock(self):
                        calls.append('acquire')
                        if failure == 'acquire':
                            raise error
                        try:
                            yield marker
                        except ValueError:
                            if failure != 'suppressed':
                                raise
                        finally:
                            calls.append('release')
                            # Guard release must occur inside the held span.
                            active = recorder.snapshot()['unfinished']
                            self_case.assertIn('journal.guard_held', [row['phase'] for row in active])
                            if failure == 'release':
                                raise error

                self_case = self
                journal = phases.observed_journal_type(JournalBase, recorder)()
                caught = None
                try:
                    with journal._writer_lock() as value:
                        self.assertIs(value, marker)
                        calls.append('body')
                        if failure in ('body', 'suppressed'):
                            raise error
                except ValueError as actual:
                    caught = actual
                if failure in ('acquire', 'body', 'release'):
                    self.assertIs(caught, error)
                else:
                    self.assertIsNone(caught)
                snapshot = recorder.snapshot()
                wait = rows(snapshot, 'journal.guard_wait', 'exit')[0]
                self.assertEqual(wait['outcome'], 'raised' if failure == 'acquire' else 'returned')
                if failure == 'acquire':
                    self.assertEqual(calls, ['acquire'])
                    self.assertFalse(rows(snapshot, 'journal.guard_held', 'enter'))
                else:
                    self.assertEqual(calls, ['acquire', 'body', 'release'])
                    held = rows(snapshot, 'journal.guard_held', 'exit')[0]
                    self.assertEqual(held['outcome'], 'raised' if failure in ('body', 'release') else 'returned')
                self.assertEqual(snapshot['unfinished'], [])
                self.assertNotIn('SECRET', json.dumps(snapshot))


if __name__ == '__main__':
    unittest.main()
