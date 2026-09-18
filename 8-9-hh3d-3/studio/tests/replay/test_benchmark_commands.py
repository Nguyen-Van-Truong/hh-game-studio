"""Tiny real HTTP fixtures only; never the full benchmark campaign or engine."""
from dataclasses import replace
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_commands as benchmark
from studio.host.core.transport import FixtureClient, TransportLimits
from studio.protocol.core import Response, Status


class SyntheticObserver:
    kind = 'synthetic_test_observer'
    def __init__(self):
        self.identity = {'pid': os.getpid(), 'process_start': 'windows:123456'}
        self.closed = False
        self.fail_close = False

    def sample(self):
        return {'process': dict(self.identity), 'monotonic_us': time.perf_counter_ns() // 1000,
                'counters': {name: {'value': value, 'unavailable_reason': reason} for name, value, reason in (
                    ('rss_bytes', 1000000, None), ('held_handles', 10, None),
                    ('objects', None, 'NOT_APPLICABLE_PYTHON_HOST'),
                    ('resources', None, 'NOT_APPLICABLE_PYTHON_HOST'))}}

    def close(self):
        if self.fail_close:
            raise RuntimeError('synthetic cleanup held')
        self.closed = True


class CommandProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gt06-command-test-')
        self.observer = SyntheticObserver()
        self.producer = benchmark.CommandProducer(Path(self.temp.name) / 'new', 'test.commands', observer=self.observer)

    def tearDown(self):
        self.observer.fail_close = False
        self.producer.close()
        self.temp.cleanup()

    def test_two_small_actual_http_batches_keep_identity_and_effect_chain(self):
        host = self.producer.host
        first = self.producer.run_diagnostic()
        credential = self.producer.credential
        second = self.producer.run_diagnostic()
        self.assertIs(self.producer.host, host)
        self.assertEqual(first['host_process'], second['host_process'])
        self.assertEqual(first['memory_after']['process'], second['memory_after']['process'])
        self.assertEqual(first['effect_count_after'], second['effect_count_before'])
        self.assertEqual(second['effect_count_after'], 4)
        ids = []
        for index, row in enumerate((first, second)):
            self.assertEqual(row['schema_version'], '1.2.0')
            self.assertEqual(row['index'], index)
            self.assertEqual(row['status'], 'DIAGNOSTIC')
            self.assertFalse(row['complete_command_mix'])
            self.assertFalse(row['native_acceptance'])
            self.assertNotIn('transport_failure', row)
            self.assertEqual(row['observation_kind'], 'synthetic_test_observer')
            self.assertEqual(row['effects_kind'], 'in_process_mock_fixture')
            self.assertEqual([n['kind'] for n in row['commands']], ['inspect'] * 5 + ['rejected'] * 3 + ['admitted'] * 2)
            self.assertEqual({k: len(v) for k, v in row['latency_ms'].items()}, {'inspect': 5, 'rejected': 3, 'admitted': 2})
            self.assertEqual(row['effects_per_admission'], [1, 1])
            self.assertEqual(row['cancel']['status'], 'CANCELED')
            self.assertTrue(row['cancel']['separate_from_mix'])
            self.assertTrue(row['cancel']['no_effect'])
            self.assertIsNone(row['memory_after']['counters']['objects']['value'])
            self.assertGreater(row['memory_after']['counters']['rss_bytes']['value'], 0)
            for command in row['commands']:
                ids.append(command['command_id'])
                self.assertGreater(command['latency_ms'], 0)
                if command['kind'] == 'inspect':
                    self.assertEqual(command['latency_ms'], command['terminal_ms'])
                if command['kind'] == 'admitted':
                    self.assertEqual(command['receipt_status'], 'ACCEPTED_PENDING')
                    self.assertEqual(command['terminal_status'], 'COMMITTED')
                    self.assertEqual(command['latency_ms'], command['receipt_ms'])
                if command['kind'] == 'rejected':
                    self.assertEqual(command['lookup_attempts'], [])
                    self.assertNotIn('terminal_response', command)
                else:
                    self.assertEqual(command['terminal_mono_us'], command['lookup_attempts'][-1]['ended_mono_us'])
            raw = json.dumps(row)
            self.assertNotIn(credential.bearer, raw)
            self.assertNotIn(self.producer.credential.bearer, raw)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(host.limits, TransportLimits())
        self.assertEqual(host.limits.max_pending, 16)
        self.assertEqual(host.limits.max_session_history, 64)
        self.assertEqual(self.producer.journal.limits.max_records, 100000)
        with self.assertRaisesRegex(benchmark.CommandError, 'MODE_MIX'):
            self.producer.run_batch(2)

    def test_unexpected_diagnostic_cannot_be_hidden_by_expected_rejections(self):
        self.producer.host._diagnostic('TRANSPORT_FAILED')
        with self.assertRaisesRegex(benchmark.CommandError, 'HOST_DIAGNOSTICS') as caught:
            self.producer.run_diagnostic()
        # Setup responses now surface an existing unexpected diagnostic before
        # the first command can be submitted.
        self.assertEqual(len(caught.exception.report['commands']), 0)
        self.assertTrue(self.producer.failed)

    def test_wrong_auth_is_real_rejection_and_cannot_add_effect(self):
        connection = http.client.HTTPConnection('127.0.0.1', self.producer.host.port, timeout=2)
        try:
            connection.request('POST', '/v1/discovery', json.dumps({'project_id': 'benchmark.commands', 'protocol_version': '1.0'}),
                               {'Authorization': 'Bearer ' + 'a' * 43, 'Content-Type': 'application/json'})
            result = connection.getresponse()
            data = json.loads(result.read())
            self.assertEqual(data['code'], 'AUTH_REQUIRED')
            self.assertGreaterEqual(result.status, 400)
        finally:
            connection.close()
        self.assertEqual(self.producer.host.fixture.effect_count, 0)

    def test_failure_keeps_partial_row_and_latches_no_retry(self):
        self.producer.host.faults.drop_submit_response_once = True
        with self.assertRaises(benchmark.CommandError) as caught:
            self.producer.run_diagnostic()
        error = caught.exception
        self.assertIs(error.cleanup_owner, self.producer)
        self.assertEqual(error.report['status'], 'FAILED')
        self.assertFalse(error.report['complete_command_mix'])
        self.assertEqual(len(error.report['commands']), 1)
        self.assertEqual(error.report['commands'][0]['receipt_status'], 'UNKNOWN')
        failure = error.report['transport_failure']
        self.assertEqual(failure['stage'], 'getresponse')
        self.assertGreaterEqual(failure['elapsed_ms'], 0)
        self.assertNotIn(self.producer.credential.bearer, json.dumps(error.report))
        # Later calls may clear the client's observation; the failed batch keeps
        # its own copy and never becomes a measured success through reconciliation.
        saved = dict(failure)
        self.producer.client.discover()
        self.assertIsNone(self.producer.client.last_transport_failure)
        self.assertEqual(failure, saved)
        with self.assertRaisesRegex(benchmark.CommandError, 'PRODUCER_CLOSED_OR_HELD'):
            self.producer.run_diagnostic()

    def test_process_drift_and_bad_batch_order_fail_before_claim(self):
        with self.assertRaisesRegex(benchmark.CommandError, 'BATCH_ORDER'):
            self.producer.run_batch(True)
        with self.assertRaisesRegex(benchmark.CommandError, 'BATCH_ORDER'):
            self.producer.run_batch(1)
        self.observer.identity['process_start'] = 'windows:999999'
        with self.assertRaisesRegex(benchmark.CommandError, 'HOST_PROCESS_CHANGED') as caught:
            self.producer.run_diagnostic()
        self.assertEqual(caught.exception.report['commands'], [])

    def test_cleanup_held_is_retained_and_retry_is_explicit(self):
        ports = (self.producer.host.port, self.producer.host.control_port)
        self.observer.fail_close = True
        with self.assertRaises(benchmark.CommandError) as caught:
            self.producer.close()
        self.assertEqual(caught.exception.code, 'CLEANUP_HELD')
        self.assertIs(caught.exception.cleanup_owner, self.producer)
        self.assertFalse(self.producer.closed)
        self.observer.fail_close = False
        self.producer.close()
        self.assertTrue(self.producer.closed)
        self.assertTrue(self.observer.closed)
        for port in ports:
            connection = http.client.HTTPConnection('127.0.0.1', port, timeout=.1)
            try:
                with self.assertRaises(OSError):
                    connection.connect()
            finally:
                connection.close()

    def test_readback_duplicate_loss_and_hash_tamper_rejected(self):
        lease = self.producer._connect_batch()
        request = self.producer.client.request('test.readback', lease=lease)
        self.assertIs(self.producer.client.submit(request).status, Status.ACCEPTED_PENDING)
        result, _ = self.producer._terminal(request.command_id, request.digest, {'lookup_attempts': []})
        with self.assertRaisesRegex(benchmark.CommandError, 'DUPLICATE_OR_LOST_EFFECT'):
            self.producer._readback(result, 1)
        tampered = replace(result, result_hash='sha256:' + 'f' * 64)
        with self.assertRaisesRegex(benchmark.CommandError, 'READBACK_HASH'):
            self.producer._readback(tampered, 0)

    def test_setup_records_real_http_returns_without_excluding_startup(self):
        report = self.producer.run_diagnostic()
        discovery, lease = report['setup_responses']
        self.assertEqual([row['kind'] for row in report['setup_responses']], ['discovery', 'lease'])
        self.assertLessEqual(report['started_mono_us'], discovery['started_mono_us'])
        self.assertLessEqual(discovery['receipt_mono_us'], lease['started_mono_us'])
        self.assertLessEqual(lease['receipt_mono_us'], report['memory_before']['monotonic_us'])
        self.assertEqual(report['host_response_mono_us'][:3],
            [report['started_mono_us'], discovery['receipt_mono_us'], lease['receipt_mono_us']])
        expected = [report['started_mono_us'], report['ended_mono_us'],
                    discovery['receipt_mono_us'], lease['receipt_mono_us'],
                    report['cancel']['queued_mono_us'], report['cancel']['receipt_mono_us']]
        for row in report['commands']:
            expected.append(row['receipt_mono_us'])
        for row in report['commands'] + [report['cancel']]:
            expected.extend(item['ended_mono_us'] for item in row.get('lookup_attempts', []))
        self.assertEqual(report['host_response_mono_us'], sorted(expected))

    def test_missing_discovery_response_does_not_create_progress_sample(self):
        with patch.object(benchmark.FixtureClient, 'discover', side_effect=benchmark.CommandError('TEST_NO_RESPONSE')):
            with self.assertRaises(benchmark.CommandError) as caught:
                self.producer.run_diagnostic()
        report = caught.exception.report
        self.assertEqual(report['setup_responses'], [])
        self.assertEqual(report['commands'], [])
        self.assertEqual(report['host_response_mono_us'],
                         [report['started_mono_us'], report['ended_mono_us']])

    def test_real_response_sampling_does_not_hide_a_two_second_setup_stall(self):
        real_clock, real_discover = benchmark._clock, benchmark.FixtureClient.discover
        offset = [0]
        def discover(client):
            # Synthetic elapsed time around an actual HTTP response, no sleep.
            offset[0] += 2_100_000_000
            return real_discover(client)
        with patch.object(benchmark, '_clock', side_effect=lambda: real_clock() + offset[0]), \
             patch.object(benchmark.FixtureClient, 'discover', discover):
            report = self.producer.run_diagnostic()
        self.assertGreater(report['max_status_gap_ms'], 2000)
        self.assertGreater(report['setup_responses'][0]['receipt_mono_us'] - report['started_mono_us'], 2_000_000)

    def test_lost_lookup_responses_reconcile_same_ids_without_resubmit_or_extra_effect(self):
        actual_lookup, actual_submit = FixtureClient.lookup, FixtureClient.submit
        lost, submits = set(), []
        targets = {'test.commands.b0.inspect.0', 'test.commands.b0.cancel'}

        def lookup(client, command_id):
            result = actual_lookup(client, command_id)
            if command_id in targets and command_id not in lost:
                lost.add(command_id)
                return Response(Status.UNKNOWN, 'CONNECTION_LOST_LOOKUP', command_id,
                                postconditions={'next_action': 'lookup'})
            return result

        def submit(client, request):
            submits.append(request.command_id)
            return actual_submit(client, request)

        with patch.object(FixtureClient, 'lookup', lookup), patch.object(FixtureClient, 'submit', submit):
            report = self.producer.run_diagnostic()
        self.assertEqual(lost, targets)
        self.assertEqual(len(submits), 11)  # Exact ten-command mix plus separate Cancel job.
        self.assertEqual(len(set(submits)), len(submits))
        self.assertEqual(self.producer.host.fixture.effect_count, 2)
        self.assertEqual(report['effect_count_after'], 2)
        for row in (report['commands'][0], report['cancel']):
            attempts = row['lookup_attempts']
            self.assertGreaterEqual(len(attempts), 2)
            self.assertEqual((attempts[0]['status'], attempts[0]['code']), ('UNKNOWN', 'CONNECTION_LOST_LOOKUP'))
            self.assertIsNone(attempts[0]['request_digest'])
            self.assertTrue(all(item['command_id'] == row['command_id'] for item in attempts))
            self.assertEqual(attempts[-1]['request_digest'], row['request_digest'])
            self.assertEqual(attempts[-1]['ended_mono_us'], row['terminal_mono_us'])
            self.assertEqual(row['terminal_response']['status'], row['terminal_status'])
            self.assertGreater(row['terminal_ms'], row['receipt_ms'])
            for attempt in attempts:
                self.assertEqual(set(attempt), {'status', 'code', 'command_id', 'request_digest',
                                               'started_mono_us', 'ended_mono_us'})
                self.assertIn(attempt['ended_mono_us'], report['host_response_mono_us'])

    def test_persistent_lookup_uncertainty_exhausts_original_budget_and_restores_timeout(self):
        now = [1_000_000_000]
        calls = []
        def lookup(command_id):
            calls.append((command_id, self.producer.client.timeout))
            now[0] += round(self.producer.client.timeout * 1_000_000_000)
            return Response(Status.UNKNOWN, 'CONNECTION_LOST_LOOKUP', command_id)
        self.producer.client = SimpleNamespace(timeout=2.0, lookup=lookup)
        row = {'lookup_attempts': []}
        with patch.object(benchmark, '_clock', side_effect=lambda: now[0]), patch.object(benchmark.time, 'sleep'):
            with self.assertRaisesRegex(benchmark.CommandError, 'TERMINAL_TIMEOUT'):
                self.producer._terminal('same.command', 'sha256:' + 'a' * 64, row)
        self.assertEqual(calls, [('same.command', 2.0), ('same.command', 2.0), ('same.command', 1.0)])
        self.assertEqual(self.producer.client.timeout, 2.0)
        self.assertEqual(row['terminal_ms'], benchmark.TERMINAL_TIMEOUT_SECONDS * 1000)
        self.assertEqual(len(row['lookup_attempts']), 3)
        self.assertEqual(row['terminal_response']['status'], 'UNKNOWN')
        self.assertEqual(self.producer.host.fixture.effect_count, 0)

    def test_wrong_identity_is_persisted_and_never_reconciled(self):
        actual_lookup, actual_submit = FixtureClient.lookup, FixtureClient.submit
        lookups, submits = [], []
        def lookup(client, command_id):
            lookups.append(command_id)
            actual_lookup(client, command_id)
            return Response(Status.UNKNOWN, 'CONNECTION_LOST_LOOKUP', 'wrong.command')
        def submit(client, request):
            submits.append(request.command_id)
            return actual_submit(client, request)
        with patch.object(FixtureClient, 'lookup', lookup), patch.object(FixtureClient, 'submit', submit):
            with self.assertRaisesRegex(benchmark.CommandError, 'TERMINAL_IDENTITY') as caught:
                self.producer.run_diagnostic()
        row = caught.exception.report['commands'][0]
        self.assertEqual(row['terminal_response']['command_id'], 'wrong.command')
        self.assertEqual(row['lookup_attempts'][0]['command_id'], 'wrong.command')
        self.assertGreater(row['terminal_ms'], 0)
        self.assertEqual(len(lookups), 1)
        self.assertEqual(len(submits), 1)
        self.assertEqual(self.producer.host.fixture.effect_count, 0)

    def test_conflicting_digest_or_arbitrary_rejection_is_not_retryable(self):
        for response, code in (
                (Response(Status.UNKNOWN, 'CONNECTION_LOST_LOOKUP', 'same.command',
                          postconditions={'request_digest': 'sha256:' + 'b' * 64}), 'TERMINAL_IDENTITY'),
                (Response(Status.REJECTED, 'ARBITRARY_REJECTION', 'same.command',
                          postconditions={'request_digest': 'sha256:' + 'a' * 64}), None),
                (Response(Status.UNKNOWN, 'OTHER_UNKNOWN', 'same.command',
                          postconditions={'request_digest': 'sha256:' + 'a' * 64}), None)):
            calls = []
            def lookup(command_id):
                calls.append(command_id)
                return response
            self.producer.client = SimpleNamespace(timeout=2.0, lookup=lookup)
            row = {'lookup_attempts': []}
            with self.subTest(response=response.code):
                if code is not None:
                    with self.assertRaisesRegex(benchmark.CommandError, code):
                        self.producer._terminal('same.command', 'sha256:' + 'a' * 64, row)
                else:
                    result, _ = self.producer._terminal('same.command', 'sha256:' + 'a' * 64, row)
                    self.assertIs(result, response)
                    with self.assertRaisesRegex(benchmark.CommandError, 'TERMINAL_' + response.status.value):
                        self.producer._readback(result, 0)
                self.assertEqual(calls, ['same.command'])
                self.assertEqual(row['terminal_response'], response.as_dict())

    def test_cancel_terminal_failure_retains_partial_response(self):
        actual_lookup = FixtureClient.lookup
        cancel_lookups = []
        def lookup(client, command_id):
            result = actual_lookup(client, command_id)
            if command_id.endswith('.cancel'):
                cancel_lookups.append(command_id)
                return replace(result, command_id='wrong.cancel')
            return result
        with patch.object(FixtureClient, 'lookup', lookup):
            with self.assertRaisesRegex(benchmark.CommandError, 'TERMINAL_IDENTITY') as caught:
                self.producer.run_diagnostic()
        row = caught.exception.report['cancel']
        self.assertEqual(row['terminal_response']['command_id'], 'wrong.cancel')
        self.assertEqual(len(row['lookup_attempts']), 1)
        self.assertEqual(len(cancel_lookups), 1)
        self.assertEqual(self.producer.host.fixture.effect_count, 2)

    def test_terminal_readback_hash_mismatch_is_persisted_without_retry(self):
        actual_lookup, actual_submit = FixtureClient.lookup, FixtureClient.submit
        lookups, submits = [], []
        def lookup(client, command_id):
            lookups.append(command_id)
            result = actual_lookup(client, command_id)
            return Response(Status.COMMITTED, 'READBACK_CONFIRMED', command_id,
                result_hash='sha256:' + 'f' * 64,
                postconditions={'request_digest': result.postconditions['request_digest'],
                                'snapshot': {'effect_count': 0, 'revision': 'rev-0', 'value': 0}})
        def submit(client, request):
            submits.append(request.command_id)
            return actual_submit(client, request)
        with patch.object(FixtureClient, 'lookup', lookup), patch.object(FixtureClient, 'submit', submit):
            with self.assertRaisesRegex(benchmark.CommandError, 'READBACK_HASH') as caught:
                self.producer.run_diagnostic()
        row = caught.exception.report['commands'][0]
        self.assertEqual(row['terminal_response']['result_hash'], 'sha256:' + 'f' * 64)
        self.assertEqual(len(row['lookup_attempts']), 1)
        self.assertEqual(len(lookups), 1)
        self.assertEqual(len(submits), 1)
        self.assertEqual(self.producer.host.fixture.effect_count, 0)


@unittest.skipUnless(os.name == 'nt', 'retained Windows process observation')
class NativeObserverTests(unittest.TestCase):
    def test_native_identity_rss_handles_and_applicability(self):
        observer = benchmark.NativeObserver()
        try:
            first, second = observer.sample(), observer.sample()
            self.assertEqual(first['process'], second['process'])
            self.assertEqual(first['process']['pid'], os.getpid())
            self.assertTrue(first['process']['process_start'].startswith('windows:'))
            self.assertGreater(first['counters']['rss_bytes']['value'], 0)
            self.assertGreater(first['counters']['held_handles']['value'], 0)
            for name in ('objects', 'resources'):
                self.assertEqual(first['counters'][name], {'value': None, 'unavailable_reason': 'NOT_APPLICABLE_PYTHON_HOST'})
        finally:
            observer.close()


if __name__ == '__main__':
    unittest.main()
