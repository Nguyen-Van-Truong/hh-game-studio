"""Offline retained-control reuse; no producer, scheduler or performance run."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import journal_scaling_metrics as scaling
from studio.tests.replay import residency_metrics as metrics
from studio.tests.replay.test_journal_scaling_metrics import _write_bound_fixture
from studio.tests.replay import test_residency_metrics as residency_test_support


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def fixture(root):
    paths = _write_bound_fixture(root)
    profile_name = scaling.PROFILE_NEWLINE_BRIDGE['file']
    original = b"LIMIT = 130\r\nWORKLOAD = 'fixed'\n"
    current = original.replace(b'\r\n', b'\n')
    profile = paths['source'] / profile_name
    profile.parent.mkdir(parents=True)
    profile.write_bytes(current)
    paths['manifest'][profile_name] = hashlib.sha256(original).hexdigest()
    paths['payload']['source_before'] = paths['manifest']
    paths['payload']['source_closure'] = scaling.source_closure(paths['manifest'])
    write_json(paths['probe'], paths['payload'])
    write_json(paths['soak'] / 'source-files.json', paths['manifest'])
    original_result = json.loads((paths['soak'] / 'result.json').read_bytes())
    original_result['source_closure_sha256'] = scaling.source_closure(paths['manifest'])
    write_json(paths['soak'] / 'result.json', original_result)
    for name in paths['manifest']:
        snapshot = paths['soak'] / 'source' / name
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_bytes(original if name == profile_name else (paths['source'] / name).read_bytes())
    paths['pins'] = {'probe_result': sha(paths['probe']),
                     'soak_manifest': sha(paths['soak'] / 'source-files.json'),
                     'soak_result': sha(paths['soak'] / 'result.json')}
    paths['bridge'] = {'file': profile_name, 'retained_sha256': hashlib.sha256(original).hexdigest(),
                       'current_sha256': hashlib.sha256(current).hexdigest()}
    current_manifest = {name: sha(paths['source'] / name) for name in paths['manifest']}
    paths['current_manifest'] = current_manifest
    fresh = root / 'fresh-host'
    fresh.mkdir()
    paths['fresh'] = fresh
    write_json(fresh / 'source-files.json', current_manifest)
    write_json(fresh / 'result.json', {'run_id': fresh.name, 'completed': True,
               'source_unchanged': True, 'formal_acceptance': False, 'full_benchmark': False,
               'source_closure_sha256': scaling.source_closure(current_manifest)})
    # Deliberately unrelated to the retained seed journal.
    (fresh / 'commands').mkdir()
    (fresh / 'commands/commands.jsonl').write_bytes(b'{"fresh_command_id": "other"}\n')
    summaries, timings, recoveries = residency_test_support.ResidencyMetricTests().fixture(
        lookup_tail=1.21, append_tail=1.21)
    mix = ('inspect',) * 5 + ('rejected',) * 3 + ('admitted',) * 2
    for index in range(35):
        batch = {'index': index, 'run_id': fresh.name, 'host_process': summaries[index]['host_process'],
                 'commands': [{'kind': mix[n % 10], 'ordinal': n} for n in range(1000)],
                 'max_status_gap_ms': 1.0, 'transport_recovery': recoveries[index],
                 'schema_id': 'hh-studio.benchmark-command-batch', 'schema_version': '1.5.0',
                 'mode': 'benchmark', 'complete_command_mix': True, 'native_acceptance': False,
                 'effects_kind': 'in_process_mock_fixture',
                 'transport_kind': 'accepted_loopback_fixture_http'}
        for prefix, value in (('summary', summaries[index]), ('journal-timing', timings[index]), ('batch', batch)):
            write_json(fresh / f'{prefix}-{index:02d}.json', value)
    return paths


class RetainedControlTests(unittest.TestCase):
    def controls(self, paths):
        stack = ExitStack()
        stack.enter_context(mock.patch.object(scaling, 'INSPECTED_PROBE_SHA256', paths['probe_sha']))
        stack.enter_context(mock.patch.object(scaling, 'RETAINED_CONTROL_PINS', paths['pins']))
        stack.enter_context(mock.patch.object(scaling, 'PROFILE_NEWLINE_BRIDGE', paths['bridge']))
        stack.enter_context(mock.patch.object(scaling, 'current_probe_sources',
            side_effect=lambda root: {name: sha(root / name) for name in paths['manifest']}))
        return stack

    def read(self, paths):
        return scaling.read_retained_control(paths['probe'], paths['seeds'],
                    source_root=paths['source'], reference_soak=paths['soak'])

    def report(self, paths):
        return metrics.from_run_with_retained_control(paths['fresh'], interleaved_probe=paths['probe'],
                    seed_directory=paths['seeds'], reference_soak=paths['soak'], source_root=paths['source'])

    def test_readiness_and_fresh_metrics_keep_separate_origin_bindings(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixture(Path(td))
            with self.controls(paths):
                readiness = self.read(paths)
                self.assertNotIn('current_soak', readiness['evidence_binding'])
                report = self.report(paths)
            self.assertTrue(report['metrics_pass'])
            self.assertFalse(report['legacy_policy_result']['metrics_pass'])
            self.assertFalse(report['formal_acceptance'])
            binding = report['interleaved_journal']['evidence_binding']
            self.assertEqual(binding['seed_soak']['run_id'], paths['soak'].name)
            self.assertEqual(binding['current_soak']['run_id'], paths['fresh'].name)
            self.assertFalse(binding['seeds_bound_to_current_soak'])
            self.assertFalse(binding['historical_harness_closure_complete'])
            self.assertEqual(binding['reviewed_byte_normalizations'][0]['retained_crlf_count'], 1)
            self.assertEqual(binding['reviewed_byte_normalizations'][0]['retained_lf_count'], 2)

    def test_changed_raw_seed_source_or_snapshot_never_reuses_control(self):
        mutations = (
            (lambda p: p['probe'].write_bytes(p['probe'].read_bytes() + b' '), 'RETAINED_PROBE_RAW_CHANGED'),
            (lambda p: (p['seeds'] / 'early.jsonl').write_bytes(b'{}\n'), 'PROBE_SEED_HASH'),
            (lambda p: (p['source'] / 'host/core/journal.py').write_bytes(b'changed'), 'PROBE_SOURCE_CHANGED'),
            (lambda p: (p['source'] / p['bridge']['file']).write_bytes(b'LIMIT = 131\n'), 'PROBE_SOURCE_CHANGED'),
            (lambda p: (p['soak'] / 'source/host/core/journal.py').write_bytes(b'changed'), 'PROBE_SOURCE_CHANGED'),
            (lambda p: (p['soak'] / 'source' / p['bridge']['file']).write_bytes(b'changed'),
             'PROBE_PROFILE_NORMALIZATION_UNPROVEN'),
        )
        for mutate, code in mutations:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as td:
                paths = fixture(Path(td))
                with self.controls(paths):
                    mutate(paths)
                    with self.assertRaisesRegex(ValueError, code):
                        self.read(paths)

    def test_retained_passing_control_cannot_mask_fresh_counter_or_mix_failure(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixture(Path(td))
            summary_path = paths['fresh'] / 'summary-05.json'
            summary = json.loads(summary_path.read_bytes())
            summary['memory_after_release']['counters']['private_commit_bytes']['value'] = 111
            write_json(summary_path, summary)
            with self.controls(paths):
                report = self.report(paths)
                self.assertFalse(report['metrics_pass'])
                self.assertIn('private_growth', report['failed_checks'])
                batch_path = paths['fresh'] / 'batch-34.json'
                batch = json.loads(batch_path.read_bytes())
                batch['commands'][5]['kind'] = 'inspect'
                write_json(batch_path, batch)
                with self.assertRaisesRegex(ValueError, 'CURRENT_SOAK_WORKLOAD'):
                    self.report(paths)

    def test_fresh_source_manifest_cannot_claim_a_different_dependency(self):
        with tempfile.TemporaryDirectory() as td:
            paths = fixture(Path(td))
            manifest = dict(paths['current_manifest'])
            manifest['host/core/journal.py'] = '0' * 64
            write_json(paths['fresh'] / 'source-files.json', manifest)
            with self.controls(paths), self.assertRaisesRegex(ValueError, 'PROBE_SOURCE_CHANGED'):
                self.report(paths)


if __name__ == '__main__':
    unittest.main()
