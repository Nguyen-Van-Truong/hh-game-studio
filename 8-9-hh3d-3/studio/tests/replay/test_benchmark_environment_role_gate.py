"""Focused O9.3 role baseline/current evidence regressions."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import benchmark_environment as env
from studio.tests.replay.benchmark_job import BenchmarkJobError


def _cell(value, reason=None):
    return {'value': value, 'unavailable_reason': reason}


def memory(*, host_private=100, host_handles=10, editor_private=200,
           editor_handles=20, editor_objects=30):
    return {
        'phase': 'post_batch_quiescent',
        'host': {
            'rss_bytes': _cell(1000), 'private_commit_bytes': _cell(host_private),
            'objects': _cell(None, 'NOT_APPLICABLE_PYTHON_HOST'),
            'resources': _cell(None, 'NOT_APPLICABLE_PYTHON_HOST'),
            'held_handles': _cell(host_handles),
        },
        'editor': {
            'rss_bytes': _cell(2000), 'private_commit_bytes': _cell(editor_private),
            'objects': _cell(editor_objects), 'resources': _cell(4),
            'held_handles': _cell(editor_handles),
        },
    }


def trigger(*, host_private=110, editor_private=210, batch_index=8):
    return {
        'batch_index': batch_index,
        'owned_processes': [
            {'role': 'host', 'owned': True, 'pid': 101, 'process_start_100ns': 1001,
             'private_bytes': host_private},
            {'role': 'editor', 'owned': True, 'pid': 202, 'process_start_100ns': 2002,
             'private_bytes': editor_private},
        ],
    }


def watchdog_sample(second=0, **changes):
    return {
        'observed_utc': '2026-10-03T00:00:00Z',
        'available_memory_bytes': 4 * env.GIB,
        'commit_total_bytes': 80 * env.GIB,
        'commit_limit_bytes': 100 * env.GIB,
        'uptime_ms': second * 1000,
        'awake_100ns': second * 10_000_000,
        'cpu_total_100ns': second * 10_000_000,
        'cpu_idle_100ns': second * 5_000_000,
        'owned_private_bytes': 0,
        'owned_inventory_complete': True,
        'foreign_engines': [], 'heavy_processes': [], 'docker_wsl_processes': [],
        'top_private_processes': [], 'owned_processes': [], 'processes': [],
        'unavailable_process_count': 0, **changes,
    }


class RoleGateTests(unittest.TestCase):
    def setUp(self):
        self.binding = {'run_id': 'campaign.r00.a01', 'source_closure_sha256': 'a' * 64,
                        'campaign_sha256': 'b' * 64}
        self.baseline = memory()
        self.batches = [{'index': 2, 'memory': memory()},
                        {'index': 4, 'memory': memory()},
                        {'index': 8, 'memory': memory()}]
        self.watchdog = trigger()

    def bind(self, **changes):
        row = deepcopy(self.watchdog)
        row.update(changes)
        return env.bind_role_counter_evidence(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=row,
            baseline_memory=self.baseline, batch_samples=self.batches)

    def test_binding_uses_nearest_batch_and_trigger_private_values(self):
        evidence = self.bind()
        self.assertEqual(evidence['nearest_batch_index'], 8)
        self.assertEqual(evidence['roles']['host']['current']['private_commit_bytes'], 110)
        self.assertEqual(evidence['roles']['editor']['current']['private_commit_bytes'], 210)
        self.assertEqual(evidence['roles']['editor']['current']['objects'], 30)
        env.verify_role_counter_evidence(
            evidence, binding=self.binding, watchdog_sample_index=7,
            watchdog_row=self.watchdog, baseline_memory=self.baseline,
            batch_samples=self.batches)

    def test_digest_rejects_baseline_or_current_tampering(self):
        evidence = self.bind()
        changed = deepcopy(evidence)
        changed['roles']['host']['baseline']['held_handles'] = 11
        with self.assertRaisesRegex(BenchmarkJobError, 'O9_3_EVIDENCE_(HASH|BINDING)'):
            env.verify_role_counter_evidence(
                changed, binding=self.binding, watchdog_sample_index=7,
                watchdog_row=self.watchdog, baseline_memory=self.baseline,
                batch_samples=self.batches)
        changed = deepcopy(evidence)
        changed['roles']['editor']['current']['objects'] = 31
        with self.assertRaisesRegex(BenchmarkJobError, 'O9_3_EVIDENCE_(HASH|BINDING)'):
            env.verify_role_counter_evidence(
                changed, binding=self.binding, watchdog_sample_index=7,
                watchdog_row=self.watchdog, baseline_memory=self.baseline,
                batch_samples=self.batches)

    def test_nearest_batch_is_recomputed_and_stale_evidence_rejected(self):
        evidence = self.bind()
        batches = self.batches + [{'index': 9, 'memory': memory(editor_objects=31)}]
        watchdog = trigger(batch_index=9)
        with self.assertRaisesRegex(BenchmarkJobError, 'O9_3_EVIDENCE_(HASH|BINDING)'):
            env.verify_role_counter_evidence(
                evidence, binding=self.binding, watchdog_sample_index=7,
                watchdog_row=watchdog, baseline_memory=self.baseline,
                batch_samples=batches)

    def test_missing_role_or_batch_classifies_infrastructure_without_values(self):
        missing_role = deepcopy(self.watchdog)
        missing_role['owned_processes'].pop()
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=missing_role,
            baseline_memory=self.baseline, batch_samples=self.batches,
            trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertEqual(result['reason'], 'ROLE_COUNTER_EVIDENCE_GAP')
        self.assertIsNone(result['evidence'])
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=self.watchdog,
            baseline_memory=self.baseline, batch_samples=[], trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertIsNone(result['evidence'])

    def test_o1_2_thresholds_use_role_private_and_nearest_batch_counters(self):
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7,
            watchdog_row=trigger(host_private=151), baseline_memory=self.baseline,
            batch_samples=self.batches, trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'PRODUCT_FAIL')
        self.assertEqual(result['reason'], 'ROLE_COUNTER_LIMIT')
        self.assertEqual(result['failures'][0]['counter'], 'private_commit_bytes')
        batch = deepcopy(self.batches[-1])
        batch['memory']['editor']['held_handles'] = _cell(85)
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=self.watchdog,
            baseline_memory=self.baseline, batch_samples=self.batches[:-1] + [batch],
            trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'PRODUCT_FAIL')
        self.assertTrue(any(row['counter'] == 'held_handles' for row in result['failures']))

    def test_valid_below_threshold_is_infrastructure_with_bound_evidence(self):
        helper = {'owned': True, 'pid': 303, 'process_start_100ns': 3003,
                  'private_bytes': 50}
        self.watchdog['owned_processes'].append(helper)
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=self.watchdog,
            baseline_memory=self.baseline, batch_samples=self.batches,
            trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertEqual(result['reason'], 'COMMIT_PRESSURE')
        self.assertIsNotNone(result['evidence'])

    def test_process_role_identity_is_required(self):
        row = deepcopy(self.watchdog)
        del row['owned_processes'][0]['role']
        with self.assertRaisesRegex(BenchmarkJobError, 'O9_3_TRIGGER_ROLE_BINDING'):
            env.bind_role_counter_evidence(
                watchdog_row=row, binding=self.binding, watchdog_sample_index=7,
                baseline_memory=self.baseline, batch_samples=self.batches)

    def test_process_start_accepts_real_unsigned_filetime(self):
        row = trigger()
        row['owned_processes'][0]['process_start_100ns'] = 134064000000000000
        row['owned_processes'][1]['process_start_100ns'] = 134064000000100000
        evidence = env.bind_role_counter_evidence(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=row,
            baseline_memory=self.baseline, batch_samples=self.batches)
        self.assertEqual(evidence['roles']['host']['process']['process_start_100ns'],
                         134064000000000000)

    def test_prebaseline_without_exact_2_to_4_window_is_an_evidence_gap(self):
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=1,
            watchdog_row=trigger(host_private=151, batch_index=1),
            baseline_memory=None,
            batch_samples=[{'index': 0, 'memory': memory()}],
            trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertEqual(result['reason'], 'ROLE_COUNTER_EVIDENCE_GAP')
        self.assertIsNone(result['evidence'])

    def test_missing_role_counter_is_not_treated_as_zero(self):
        row = trigger()
        row['owned_processes'][0]['private_bytes'] = None
        result = env.classify_role_counter_trigger(
            binding=self.binding, watchdog_sample_index=7, watchdog_row=row,
            baseline_memory=self.baseline, batch_samples=self.batches,
            trigger_reason='COMMIT_PRESSURE')
        self.assertEqual(result['classification'], 'INFRA_ABORT')
        self.assertEqual(result['reason'], 'ROLE_COUNTER_EVIDENCE_GAP')
        self.assertIsNone(result['evidence'])

    def test_harness_sample_gap_cannot_be_overridden_by_role_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write = lambda path, payload: path.write_text(
                json.dumps(payload, sort_keys=True) + '\n', encoding='utf-8')
            callback = Mock(return_value={
                'classification': 'INFRA_ABORT', 'formal_acceptance': False,
            })
            watch = env.Watchdog(
                root, Mock(side_effect=[watchdog_sample(0), watchdog_sample(31)]),
                self.binding, write, role_classifier=callback)
            try:
                watch.poll(force=True)
                with self.assertRaisesRegex(BenchmarkJobError, 'SAMPLE_GAP') as raised:
                    watch.poll(force=True)
            finally:
                watch.close()
            self.assertEqual(raised.exception.classification, 'HARNESS_FAIL')
            callback.assert_not_called()
            event = json.loads((root / 'watchdog-stop.json').read_text())
            self.assertEqual(event['classification'], 'HARNESS_FAIL')
            self.assertEqual(len((root / 'environment-samples.jsonl').read_text().splitlines()), 3)

    def test_observation_only_records_and_replays_environment_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write = lambda path, payload: path.write_text(
                json.dumps(payload, sort_keys=True) + '\n', encoding='utf-8')
            rows = [watchdog_sample(0),
                    watchdog_sample(5, commit_total_bytes=93 * env.GIB)]
            watch = env.Watchdog(root, Mock(side_effect=rows), self.binding, write,
                                 observation_only=True)
            try:
                watch.poll(force=True)
                watch.poll(force=True)
            finally:
                watch.close()
            self.assertFalse((root / 'watchdog-stop.json').exists())
            event_lines = (root / 'environment-events.jsonl').read_text().splitlines()
            self.assertEqual(len(event_lines), 2)
            env.verify_watchdog(
                root, lambda path, *_args: path.read_text(),
                expected_binding=self.binding, observation_only=True,
                elapsed_seconds=5)


if __name__ == '__main__':
    unittest.main()
