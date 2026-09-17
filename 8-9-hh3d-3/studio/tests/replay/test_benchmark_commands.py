"""Tiny real HTTP fixtures only; never the full benchmark campaign or engine."""
from dataclasses import replace
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import benchmark_commands as benchmark
from studio.host.core.transport import FixtureClient, TransportLimits
from studio.protocol.core import Status


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
            self.assertEqual(row['index'], index)
            self.assertEqual(row['status'], 'DIAGNOSTIC')
            self.assertFalse(row['complete_command_mix'])
            self.assertFalse(row['native_acceptance'])
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
        self.assertEqual(len(caught.exception.report['commands']), 1)
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
        result = self.producer._terminal(request.command_id)
        with self.assertRaisesRegex(benchmark.CommandError, 'DUPLICATE_OR_LOST_EFFECT'):
            self.producer._readback(result, 1)
        tampered = replace(result, result_hash='sha256:' + 'f' * 64)
        with self.assertRaisesRegex(benchmark.CommandError, 'READBACK_HASH'):
            self.producer._readback(tampered, 0)


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
