"""Bounded observation/delegation tests with mocked I/O; no listeners or engines."""
from contextlib import contextmanager
import copy
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_commands as commands
from studio.tests.replay import benchmark_http_phases as phases
from studio.tests.replay.benchmark_transport import BenchmarkFixtureClient
from studio.host.core.transport import SessionCredential
from studio.tests.replay.benchmark_http_phases import (
    PhaseRecorder, observed_client_type, observed_connection_type,
    observed_host_type, observed_journal_type, validate_phase_snapshot,
)
from studio.protocol.core import Response, Status


class TestFailure(RuntimeError):
    pass


class FakeSocket:
    def __init__(self, client=False):
        self.client = client

    def getsockname(self):
        return '127.0.0.1', 43210 if self.client else 12345

    def getpeername(self):
        return '127.0.0.1', 12345 if self.client else 43210


class PhaseRecorderTests(unittest.TestCase):
    def test_constructor_capacity_matches_validator_contract(self):
        with self.assertRaisesRegex(ValueError, 'INVALID_OBSERVATION_CAPACITY'):
            PhaseRecorder(active_capacity=65)

    def test_ring_active_and_failure_copy_are_bounded_and_counters_are_explicit(self):
        recorder = PhaseRecorder(event_capacity=4, active_capacity=1)
        for _ in range(20):
            with recorder.span('client.call', route='lookup'):
                with recorder.span('client.headers'):
                    recorder.bind_socket(None, client=True)
        with recorder.span('client.call', route='lookup') as call_id:
            recorder.capture_failure(call_id, route='lookup')
        snapshot = recorder.snapshot()
        self.assertEqual(len(snapshot['events']), 4)
        self.assertEqual(snapshot['unfinished'], [])
        self.assertGreater(snapshot['events_evicted'], 0)
        self.assertEqual(snapshot['spans_dropped'], 20)
        self.assertEqual(snapshot['identity_missing'], 20)
        self.assertLessEqual(len(snapshot['first_failure']['events']), 4)
        self.assertEqual(len(snapshot['first_failure']['unfinished']), 1)
        self.assertEqual(snapshot['transport_failures_by_route']['lookup'], 1)

    def test_first_lookup_failure_survives_other_routes_later_failure_and_mutated_snapshot(self):
        recorder = PhaseRecorder(event_capacity=8)
        with recorder.span('client.call', route='commands') as call_id:
            recorder.capture_failure(call_id, route='commands')
        self.assertIsNone(recorder.snapshot()['first_failure'])
        with recorder.span('client.call', route='lookup') as first_id:
            recorder.capture_failure(first_id, route='lookup')
        first = recorder.snapshot()['first_failure']
        with recorder.span('client.call', route='lookup') as later_id:
            recorder.capture_failure(later_id, route='lookup')
        self.assertEqual(recorder.snapshot()['first_failure'], first)
        changed = recorder.snapshot()
        changed['first_failure']['events'][0]['phase'] = 'forged'
        changed['first_failure']['transport_failures_by_route']['lookup'] = 999
        changed['events'].clear()
        self.assertEqual(recorder.snapshot()['first_failure'], first)
        self.assertEqual(first['failed_call_id'], first_id)
        self.assertNotEqual(first_id, later_id)

    def test_span_exception_identity_and_numeric_socket_pair_are_preserved(self):
        recorder = PhaseRecorder(event_capacity=8)
        failure = TestFailure('private-exception-text')
        with self.assertRaises(TestFailure) as caught:
            with recorder.span('client.call', route='lookup'):
                recorder.bind_socket(FakeSocket(client=True), client=True)
                raise failure
        self.assertIs(caught.exception, failure)
        snapshot = recorder.snapshot()
        self.assertEqual(snapshot['unfinished'], [])
        self.assertEqual(snapshot['events'][-1]['outcome'], 'raised')
        self.assertEqual((snapshot['events'][-1]['server_port'], snapshot['events'][-1]['client_port']),
                         (12345, 43210))
        self.assertNotIn('private', json.dumps(snapshot))


class SnapshotValidationTests(unittest.TestCase):
    def snapshot(self, *, fail=False, capacity=8):
        recorder = PhaseRecorder(event_capacity=capacity, active_capacity=1)
        with recorder.span('client.call', route='lookup') as call_id:
            recorder.bind_socket(FakeSocket(client=True), client=True)
            if fail:
                recorder.capture_failure(call_id, route='lookup')
        return recorder.snapshot()

    def rejected(self, value):
        with self.assertRaisesRegex(ValueError, '^INVALID_HTTP_PHASE_SNAPSHOT$'):
            validate_phase_snapshot(value, os.getpid())

    def test_normal_empty_active_completed_and_first_failure_snapshots_validate(self):
        recorder = PhaseRecorder()
        self.assertIsNone(validate_phase_snapshot(recorder.snapshot(), os.getpid()))
        with recorder.span('client.call', route='lookup'):
            self.assertIsNone(validate_phase_snapshot(recorder.snapshot(), os.getpid()))
        for fail in (False, True):
            self.assertIsNone(validate_phase_snapshot(self.snapshot(fail=fail), os.getpid()))
        first_without_span = PhaseRecorder()
        first_without_span.capture_failure(None, route='lookup')
        self.assertIsNone(validate_phase_snapshot(first_without_span.snapshot(), os.getpid()))

    def test_eviction_drop_missing_identity_and_failure_counts_are_valid_observations(self):
        recorder = PhaseRecorder(event_capacity=2, active_capacity=1)
        for _ in range(4):
            with recorder.span('client.call', route='commands'):
                with recorder.span('client.headers'):
                    recorder.bind_socket(None, client=True)
        with recorder.span('client.call', route='lookup') as call_id:
            recorder.capture_failure(call_id, route='lookup')
        snapshot = recorder.snapshot()
        self.assertGreater(snapshot['events_evicted'], 0)
        self.assertGreater(snapshot['spans_dropped'], 0)
        self.assertGreater(snapshot['identity_missing'], 0)
        self.assertGreater(snapshot['transport_failures_observed'], 0)
        self.assertIsNone(validate_phase_snapshot(snapshot, os.getpid()))

    def test_empty_pid_only_unknown_fields_schema_and_oversized_shapes_are_rejected(self):
        self.rejected({})
        self.rejected({'pid': os.getpid()})
        source = self.snapshot()
        variants = []
        for key, value in (('schema_id', 'unknown'), ('schema_version', '2.0.0'),
                           ('formal_acceptance', True), ('pid', os.getpid() + 1),
                           ('clock', 'other'), ('event_capacity', 8193),
                           ('active_capacity', 65), ('events_evicted', -1),
                           ('spans_dropped', True), ('identity_missing', 0.5),
                           ('transport_failures_observed', 1), ('events', source['events'] * 9),
                           ('unfinished', [{}] * 65)):
            changed = copy.deepcopy(source)
            changed[key] = value
            variants.append(changed)
        changed = copy.deepcopy(source)
        changed['unexpected'] = 1
        variants.append(changed)
        for changed in variants:
            with self.subTest(keys=set(changed), capacity=changed.get('event_capacity')):
                self.rejected(changed)

    def test_event_enum_numeric_identity_and_temporal_shapes_are_rejected(self):
        source = self.snapshot()
        for key, value in (('span_id', True), ('thread_id', 0), ('parent_id', 1),
                           ('root_id', -1), ('route', 'private-path'), ('phase', 'private-phase'),
                           ('server_port', 12345), ('client_port', 65536), ('kind', 'unknown'),
                           ('event_id', 99), ('outcome', 'returned'),
                           ('started_ns', source['captured_ns'] + 1),
                           ('timestamp_ns', source['captured_ns'] + 1)):
            changed = copy.deepcopy(source)
            changed['events'][0][key] = value
            with self.subTest(field=key):
                self.rejected(changed)
        changed = copy.deepcopy(source)
        changed['events'][0]['extra'] = 1
        self.rejected(changed)

    def test_first_failure_must_match_identity_shape_time_and_known_call(self):
        source = self.snapshot(fail=True)
        for key, value in (('schema_id', 'wrong'), ('pid', os.getpid() + 1),
                           ('captured_ns', source['captured_ns'] + 1),
                           ('failed_call_id', 999), ('failed_call_id', True),
                           ('event_capacity', 9), ('active_capacity', 2)):
            changed = copy.deepcopy(source)
            changed['first_failure'][key] = value
            with self.subTest(field=key, value=value):
                self.rejected(changed)
        changed = copy.deepcopy(source)
        changed['first_failure'] = {'pid': os.getpid()}
        self.rejected(changed)
        changed = copy.deepcopy(source)
        changed['first_failure'] = None
        self.rejected(changed)
        changed = copy.deepcopy(source)
        changed['first_failure']['transport_failures_by_route']['lookup'] = 2
        self.rejected(changed)
        with self.assertRaisesRegex(ValueError, '^INVALID_HTTP_PHASE_SNAPSHOT$'):
            validate_phase_snapshot(source, True)


class DelegationTests(unittest.TestCase):
    def test_observed_client_factory_preserves_wire_errors_timeout_and_close(self):
        credential = SessionCredential('private.session', 'private.project', 9999999999999,
                                       frozenset({'fixture.read'}), 'private-bearer')
        traces, fail = [], [False]

        class Reply:
            status = 200

            def read(self, size):
                traces.append(('read', size))
                return b'{"result":"same"}'

        class Connection:
            def __init__(self, *args, **kwargs):
                traces.append(('construct', args, kwargs))

            def request(self, *args, **kwargs):
                traces.append(('request', args, kwargs))

            def getresponse(self):
                traces.append(('getresponse',))
                if fail[0]:
                    raise TimeoutError('private transport failure')
                return Reply()

            def close(self):
                traces.append(('close',))

        class Plain(BenchmarkFixtureClient):
            def _connection(self, port):
                return Connection('127.0.0.1', port, timeout=self.timeout)

        recorder = PhaseRecorder()
        original_connection = http.client.HTTPConnection
        with patch.object(phases, 'observed_connection_type', return_value=Connection) as factory:
            observed = observed_client_type(BenchmarkFixtureClient, recorder)
        factory.assert_called_once_with(original_connection, recorder)
        for failure in (False, True):
            fail[0] = failure
            results, calls = [], []
            for client_type in (Plain, observed):
                traces.clear()
                client = client_type(12345, 12346, credential, timeout=0.75)
                results.append(client._call('/v1/lookup', {'command_id': 'private-command'}, control=True))
                calls.append(list(traces))
                self.assertEqual(client.timeout, 0.75)
                self.assertEqual(traces[0], ('construct', ('127.0.0.1', 12346), {'timeout': 0.75}))
                self.assertEqual(traces[-1], ('close',))
            self.assertEqual(results[0], results[1])
            self.assertEqual(calls[0], calls[1])
        self.assertIs(http.client.HTTPConnection, original_connection)
        self.assertEqual(recorder.snapshot()['transport_failures_observed'], 1)
        self.assertNotIn('private', json.dumps(recorder.snapshot()))

    def test_connection_return_arguments_exception_and_response_read_delegate_once(self):
        calls, value = [], object()
        failure = TestFailure('private transport error')

        class Reply:
            def read(self, *args, **kwargs):
                calls.append(('read', args, kwargs))
                return value

        class Connection:
            response_class = Reply
            sock = FakeSocket(client=True)

            def connect(self):
                calls.append(('connect',))
                return value

            def request(self, *args, **kwargs):
                calls.append(('request', args, kwargs))
                raise failure

            def getresponse(self):
                calls.append(('getresponse',))
                return self.response_class()

        recorder = PhaseRecorder()
        connection = observed_connection_type(Connection, recorder)()
        self.assertIs(connection.connect(), value)
        with self.assertRaises(TestFailure) as caught:
            connection.request('private method', body='private body')
        self.assertIs(caught.exception, failure)
        self.assertIs(connection.getresponse().read(123, keyword='private'), value)
        self.assertEqual(calls, [('connect',), ('request', ('private method',), {'body': 'private body'}),
                                 ('getresponse',), ('read', (123,), {'keyword': 'private'})])
        snapshot = recorder.snapshot()
        self.assertEqual(snapshot['unfinished'], [])
        self.assertNotIn('private', json.dumps(snapshot))
        self.assertEqual({row['phase'] for row in snapshot['events']},
                         {'client.connect', 'client.request', 'client.headers', 'client.body'})

    def test_host_arguments_return_error_and_socket_binding_delegate_without_secrets(self):
        calls, value = [], object()
        failure = TestFailure('private host error')

        class Host:
            def _handle(self, *args):
                calls.append(('handle', args))
                return value

            def _dispatch(self, *args):
                calls.append(('dispatch', args))
                return value

            def _lookup(self, command_id):
                calls.append(('lookup', command_id))
                raise failure

        recorder = PhaseRecorder()
        host = observed_host_type(Host, recorder)()
        sock, session = FakeSocket(), object()
        self.assertIs(host._handle(sock, 'private-listener'), value)
        body = {'secret': 'private-body'}
        self.assertIs(host._dispatch('/v1/lookup', body, session, True), value)
        with self.assertRaises(TestFailure) as caught:
            host._lookup('private-command')
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls, [('handle', (sock, 'private-listener')),
                                ('dispatch', ('/v1/lookup', body, session, True)),
                                ('lookup', 'private-command')])
        self.assertNotIn('private', json.dumps(recorder.snapshot()))
        self.assertEqual(recorder.snapshot()['unfinished'], [])

    def test_journal_guard_preserves_original_suppression_and_cleanup(self):
        calls, value = [], object()

        class Journal:
            @contextmanager
            def _writer_lock(self):
                calls.append('acquire')
                try:
                    yield value
                except TestFailure:
                    calls.append('suppressed')
                finally:
                    calls.append('release')

            def _snapshot(self, *, synchronize):
                calls.append(('snapshot', synchronize))
                return value

        recorder = PhaseRecorder()
        journal = observed_journal_type(Journal, recorder)()
        with journal._writer_lock() as held:
            self.assertIs(held, value)
            self.assertIs(journal._snapshot(synchronize=True), value)
            raise TestFailure('private error suppressed by original')
        self.assertEqual(calls, ['acquire', ('snapshot', True), 'suppressed', 'release'])
        self.assertEqual(recorder.snapshot()['unfinished'], [])

    def test_journal_guard_preserves_exception_identity_through_exit(self):
        failure = TestFailure('private failure')
        releases = []

        class Journal:
            @contextmanager
            def _writer_lock(self):
                try:
                    yield
                finally:
                    releases.append(True)

        recorder = PhaseRecorder()
        journal = observed_journal_type(Journal, recorder)()
        with self.assertRaises(TestFailure) as caught:
            with journal._writer_lock():
                raise failure
        self.assertIs(caught.exception, failure)
        self.assertEqual(releases, [True])
        self.assertEqual(recorder.snapshot()['unfinished'], [])

    def test_original_terminal_retry_retains_first_lookup_failure_before_metadata_clears(self):
        recorder = PhaseRecorder(event_capacity=32)
        digest = 'sha256:' + 'a' * 64

        class Client:
            timeout = 2.0
            last_transport_failure = None

            def __init__(self):
                self.calls = []

            def _call(self, path, body, *, control=False):
                self.calls.append((path, dict(body), control, self.timeout))
                self.last_transport_failure = None
                if len(self.calls) == 1:
                    self.last_transport_failure = {'endpoint': 'lookup', 'stage': 'getresponse',
                                                   'category': 'timeout', 'elapsed_ms': 0.01}
                    return Response(Status.UNKNOWN, 'CONNECTION_LOST_LOOKUP', body['command_id'])
                return Response(Status.COMMITTED, 'READBACK_CONFIRMED', body['command_id'],
                                postconditions={'request_digest': digest})

            def lookup(self, command_id):
                return self._call('/v1/lookup', {'command_id': command_id, 'secret': 'private-bearer'}, control=True)

        producer = object.__new__(commands.CommandProducer)
        producer.client = observed_client_type(Client, recorder)()
        producer._received = time.perf_counter_ns
        row = {'lookup_attempts': []}
        with patch.object(commands.time, 'sleep'):
            result, _ = producer._terminal('private-command', digest, row)
        self.assertIs(result.status, Status.COMMITTED)
        self.assertEqual(len(producer.client.calls), 2)
        self.assertTrue(all(call[0] == '/v1/lookup' and call[1]['command_id'] == 'private-command'
                            for call in producer.client.calls))
        self.assertIsNone(producer.client.last_transport_failure)
        self.assertEqual(producer.client.timeout, 2.0)
        self.assertEqual(row['lookup_attempts'][0]['transport_failure']['category'], 'timeout')
        snapshot = recorder.snapshot()
        self.assertEqual(snapshot['transport_failures_observed'], 1)
        self.assertIsNotNone(snapshot['first_failure'])
        self.assertEqual(len(snapshot['first_failure']['unfinished']), 1)
        self.assertEqual(snapshot['unfinished'], [])
        self.assertNotIn('private', json.dumps(snapshot))


class ProducerLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='phase-unit-')
        self.addCleanup(self.directory.cleanup)
        self.events = []
        events = self.events

        class Journal:
            def __init__(self, path):
                events.append('journal')
                self._snapshot(synchronize=False)

            def _snapshot(self, *, synchronize):
                return None

            def close(self):
                events.append('journal.close')

        class Host:
            def __init__(self, project, root, journal):
                events.append('host')

            def start(self):
                events.append('host.start')

            def close(self):
                events.append('host.close')

        class Observer:
            kind = 'synthetic_test_observer'
            identity = {'pid': os.getpid(), 'process_start': 'synthetic:phase'}
            fail_close = False

            def sample(self):
                events.append('baseline')
                return {'process': dict(self.identity), 'counters': {'rss_bytes': {'value': 1024}}}

            def close(self):
                events.append('observer.close')
                if self.fail_close:
                    raise TestFailure('private cleanup held')

        self.observer = Observer()
        self.enterContext(patch.object(commands, 'Journal', Journal))
        self.enterContext(patch.object(commands, 'LoopbackFixtureHost', Host))

    def create(self):
        return commands.CommandProducer(Path(self.directory.name) / 'new', 'test.phases', observer=self.observer)

    def test_wrappers_exist_before_baseline_and_snapshot_survives_cleanup(self):
        original_connection = http.client.HTTPConnection
        producer = self.create()
        self.addCleanup(producer.close)
        self.assertEqual(self.events, ['journal', 'host', 'host.start', 'baseline'])
        snapshot = producer.phase_snapshot()
        self.assertEqual(snapshot['schema_version'], '1.0.0')
        self.assertEqual({row['phase'] for row in snapshot['events']}, {'journal.snapshot'})
        self.assertEqual(snapshot['event_capacity'], 8192)
        self.assertEqual(snapshot['active_capacity'], 64)
        self.assertIs(http.client.HTTPConnection, original_connection)
        self.assertTrue(issubclass(producer._client_type, commands.FixtureClient))
        producer.close()
        self.assertTrue(producer.closed)
        self.assertEqual(producer.phase_snapshot()['unfinished'], [])
        self.assertEqual(self.events[-3:], ['host.close', 'observer.close', 'journal.close'])

    def test_held_cleanup_retains_recorder_without_claiming_closed(self):
        producer = self.create()
        self.observer.fail_close = True
        try:
            with self.assertRaises(commands.CommandError) as caught:
                producer.close()
            self.assertIs(caught.exception.cleanup_owner, producer)
            self.assertFalse(producer.closed)
            self.assertEqual(producer.phase_snapshot()['unfinished'], [])
        finally:
            self.observer.fail_close = False
            producer.close()

    def test_constructor_cleanup_failure_retains_initialized_recorder(self):
        self.observer.fail_close = True
        with patch.object(self.observer, 'sample', side_effect=TestFailure('private startup failure')):
            with self.assertRaises(commands.CommandError) as caught:
                self.create()
        retained = caught.exception.cleanup_owner
        self.assertFalse(retained.closed)
        self.assertEqual(retained.phase_snapshot()['schema_id'], 'hh-studio.benchmark-http-phase-window')
        self.assertNotIn('private', json.dumps(retained.phase_snapshot()))
        self.observer.fail_close = False
        retained.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
