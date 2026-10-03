"""Focused O9.3 role baseline/current evidence regressions."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

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


if __name__ == '__main__':
    unittest.main()
