"""Inert runner regressions. No Godot, container, native journal or subprocess."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('matrix_under_test', HERE / 'run_unit_matrix.py')
matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(matrix)


class InertRunner:
    def __init__(self, modes=None):
        self.calls = []
        self.modes = modes or {}
        self.ids = sorted([label + '.Case.test_one' for label in matrix.LABELS[:-1]] +
                          ['test_editor.Case.test_one', 'test_editor.Case.test_two'])

    def run_process(self, argv, *, cwd, output, timeout, label):
        lane = argv[-1]
        self.calls.append(lane)
        assert timeout == matrix.TIMEOUTS[lane] and label == 'run'
        assert argv[1:-1] == ['-B', '-c', matrix.CODE]
        mode = self.modes.get(lane, 'pass')
        ids = self.ids + (['test_z_extra.Case.test_one'] if mode == 'different_inventory' else [])
        chosen = matrix.partition_ids(ids, lane)
        inventory = {'all': ids, 'chosen': chosen}
        counts = {'run': len(chosen), 'failures': 0, 'errors': int(mode == 'fail'), 'skips': 0}
        lines = ['GT03_UNIT_INVENTORY ' + json.dumps(inventory)]
        if mode != 'timeout':
            lines.append('GT03_UNIT_COMPLETE ' + json.dumps(counts))
        (output / 'run-stdout.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        (output / 'run-stderr.txt').write_text('inert unittest output\n', encoding='utf-8')
        target_pid = 200 + len(self.calls)
        if mode != 'timeout':
            matrix.save(output / 'run-host.json', {'target_pid': target_pid,
                        'started_at': '2026-09-17T00:00:00+00:00', 'exit_code': int(mode == 'fail')})
        return {'wrapper_pid': 100, 'started_at': '2026-09-17T00:00:00+00:00',
                'argv': [Path(argv[0]).name, *argv[1:]], 'target_pid': target_pid,
                'exit_code': None if mode == 'timeout' else int(mode == 'fail'),
                'wrapper_exit_code': 1 if mode == 'timeout' else 0,
                'timed_out': mode == 'timeout', 'tree_verified': True,
                'ownership': 'gated_job_kill_on_close', 'stdout': 'run-stdout.txt',
                'stderr': 'run-stderr.txt', 'host': 'run-host.json'}


class MatrixRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hh-unit-runner-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root / 'runtime'
        source = self.package / 'source/studio'
        (source / 'build/bootstrap').mkdir(parents=True)
        (source / 'build/bootstrap/run_fixture.py').write_text('# inert runtime\n', encoding='utf-8')
        (source / 'test.txt').write_text('frozen\n', encoding='utf-8')
        files = {p.relative_to(source).as_posix(): matrix.sha(p) for p in source.rglob('*') if p.is_file()}
        matrix.save(self.package / 'source-closure.json',
                    {'files': files, 'source_closure_sha256': matrix.closure_hash(files)})
        self.controller = self.root / 'controller-source.py'
        self.controller.write_text('# inert controller\n', encoding='utf-8')
        self.output = self.root / 'result'
        self.source, self.document, self.invocation = matrix.prepare(
            self.output, runtime_package=self.package, controller=self.controller)

    def run_matrix(self, runner=None):
        runner = runner or InertRunner()
        with redirect_stdout(io.StringIO()):
            result = matrix.run_matrix(self.output, self.source, self.document,
                                       self.invocation, runner, origin_files=self.document['files'])
        return result, runner

    def resume(self, **kwargs):
        return matrix.prepare(self.output, resume=True, controller=self.controller, **kwargs)

    def attempt(self, label='other', number='0001'):
        return self.output / 'attempts' / label / number

    def reseal(self, path):
        record = matrix.read(path / 'attempt.json')
        record['artifacts'] = {p.name: matrix.sha(p) for p in path.iterdir()
                               if p.is_file() and p.name != 'attempt.json'}
        matrix.save(path / 'attempt.json', record, replace=True)

    def rewrite_markers(self, path, transform):
        lines = (path / 'run-stdout.txt').read_text(encoding='utf-8').splitlines()
        (path / 'run-stdout.txt').write_text('\n'.join(transform(lines)) + '\n', encoding='utf-8')
        self.reseal(path)

    def test_shared_runtime_uses_reference_without_copy_and_resume_retains_it(self):
        self.assertFalse((self.output / 'source').exists())
        self.assertEqual(self.resume()[0], self.source)
        self.assertEqual(self.resume(runtime_package=self.package)[2], self.invocation)

    def test_complete_resume_revalidates_and_reuses_all_six_without_new_attempts(self):
        first, _ = self.run_matrix()
        before = {p.relative_to(self.output).as_posix(): matrix.sha(p)
                  for p in (self.output / 'attempts').rglob('*') if p.is_file()}
        self.resume()
        second, runner = self.run_matrix()
        self.assertTrue(first['passed'] and second['passed'])
        self.assertEqual(runner.calls, [])
        self.assertTrue(all(row['reused'] for row in second['lanes'].values()))
        self.assertEqual(first['counts']['run'], 7)
        self.assertEqual(before, {p.relative_to(self.output).as_posix(): matrix.sha(p)
                                 for p in (self.output / 'attempts').rglob('*') if p.is_file()})
        self.assertTrue((self.output / 'rounds/0001/capture.json').is_file())
        self.assertTrue((self.output / 'rounds/0002/capture.json').is_file())

    def test_timeout_reruns_only_failed_lane_and_preserves_failure_bytes(self):
        lane = matrix.LABELS[3]
        first, _ = self.run_matrix(InertRunner({lane: 'timeout'}))
        original = {p.name: p.read_bytes() for p in self.attempt(lane).iterdir()}
        self.assertFalse(first['passed'])
        self.assertIsNone(first['counts'])
        self.resume()
        second, runner = self.run_matrix()
        self.assertTrue(second['passed'])
        self.assertEqual(runner.calls, [lane])
        self.assertEqual(original, {p.name: p.read_bytes() for p in self.attempt(lane).iterdir()})
        self.assertEqual(second['lanes'][lane]['attempt'], f'attempts/{lane}/0002')
        self.assertIn(lane, second['rejected_previous_attempts'])

    def test_failed_completed_lane_is_never_reused(self):
        first, _ = self.run_matrix(InertRunner({'other': 'fail'}))
        self.assertFalse(first['passed'])
        second, runner = self.run_matrix()
        self.assertTrue(second['passed'])
        self.assertEqual(runner.calls, ['other'])

    def test_missing_attempt_seal_after_controller_death_gets_new_directory(self):
        self.run_matrix()
        self.attempt('other').joinpath('attempt.json').unlink()
        result, runner = self.run_matrix()
        self.assertTrue(result['passed'])
        self.assertEqual(runner.calls, ['other'])
        self.assertTrue(self.attempt('other', '0002').is_dir())

    def test_missing_raw_exit_forces_only_that_lane_to_retry(self):
        self.run_matrix()
        self.attempt('other').joinpath('run-host.json').unlink()
        result, runner = self.run_matrix()
        self.assertTrue(result['passed'])
        self.assertEqual(runner.calls, ['other'])

    def test_tampered_stdout_hash_is_rejected_for_reuse(self):
        self.run_matrix()
        with self.attempt().joinpath('run-stdout.txt').open('a') as handle:
            handle.write('changed\n')
        result, runner = self.run_matrix()
        self.assertEqual(runner.calls, ['other'])
        self.assertEqual(result['rejected_previous_attempts']['other']['reason'], 'ARTIFACT_HASH_MISMATCH')

    def test_raw_pid_exit_must_match_even_if_artifact_hashes_are_resealed(self):
        self.run_matrix()
        for field, value in [('target_pid', 99999), ('exit_code', 9)]:
            with self.subTest(field=field):
                path = self.attempt()
                raw = matrix.read(path / 'run-host.json')
                original = dict(raw)
                raw[field] = value
                matrix.save(path / 'run-host.json', raw, replace=True)
                self.reseal(path)
                self.assertFalse(matrix.inspect_attempt(path, self.invocation, 'other')['passed'])
                matrix.save(path / 'run-host.json', original, replace=True)
                self.reseal(path)

    def test_stale_attempt_source_or_controller_identity_is_not_reusable(self):
        self.run_matrix()
        path = self.attempt()
        for key in ('controller_sha256', 'source_closure_sha256', 'invocation_sha256'):
            with self.subTest(key=key):
                record = matrix.read(path / 'attempt.json')
                original = dict(record)
                record[key] = '0' * 64
                matrix.save(path / 'attempt.json', record, replace=True)
                self.assertFalse(matrix.inspect_attempt(path, self.invocation, 'other')['passed'])
                matrix.save(path / 'attempt.json', original, replace=True)

    def test_completion_marker_missing_duplicate_and_count_mismatch_fail_closed(self):
        self.run_matrix()
        path = self.attempt()
        original = (path / 'run-stdout.txt').read_bytes()
        transformations = [lambda lines: lines[:-1], lambda lines: lines + [lines[-1]],
                           lambda lines: [lines[0], 'GT03_UNIT_COMPLETE ' +
                                          json.dumps({'run': 1, 'failures': 0, 'errors': 0, 'skips': 0})]]
        for transform in transformations:
            with self.subTest(transform=repr(transform)):
                (path / 'run-stdout.txt').write_bytes(original)
                self.rewrite_markers(path, transform)
                self.assertFalse(matrix.inspect_attempt(path, self.invocation, 'other')['passed'])

    def test_mispartitioned_inventory_is_not_reusable(self):
        self.run_matrix()
        path = self.attempt()
        def change(lines):
            inventory = json.loads(lines[0].split(' ', 1)[1])
            inventory['chosen'] = inventory['all'][-2:]
            return ['GT03_UNIT_INVENTORY ' + json.dumps(inventory), lines[1]]
        self.rewrite_markers(path, change)
        self.assertEqual(matrix.inspect_attempt(path, self.invocation, 'other')['reason'], 'PARTITION_MISMATCH')

    def test_individually_clean_lanes_with_different_full_inventories_cannot_pass(self):
        result, _ = self.run_matrix(InertRunner({'other': 'different_inventory'}))
        self.assertTrue(all(row['passed'] for row in result['lanes'].values()))
        self.assertFalse(result['partitions_disjoint_complete'])
        self.assertFalse(result['passed'])

    def test_resume_rejects_changed_frozen_bytes_or_extra_unmapped_source(self):
        (self.source / 'test.txt').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SOURCE_FILES_MISMATCH'):
            self.resume()
        (self.source / 'test.txt').write_text('frozen\n', encoding='utf-8')
        (self.source / 'extra.py').write_text('# new', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'SOURCE_FILES_MISMATCH'):
            self.resume()

    def test_resume_rejects_changed_controller_and_changed_saved_controller(self):
        self.controller.write_text('# changed controller', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CONTROLLER_MISMATCH'):
            self.resume()
        self.controller.write_text('# inert controller\n', encoding='utf-8')
        (self.output / 'controller.py').write_text('# corrupt', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'CONTROLLER_MISMATCH'):
            self.resume()

    def test_resume_rejects_other_runtime_reference_even_with_identical_bytes(self):
        clone = self.root / 'runtime-copy'
        shutil.copytree(self.package, clone)
        with self.assertRaisesRegex(ValueError, 'RUNTIME_REFERENCE_MISMATCH'):
            self.resume(runtime_package=clone)

    def test_resume_rejects_rewritten_manifest_even_when_contents_are_valid(self):
        manifest = self.package / 'source-closure.json'
        manifest.write_text(json.dumps(self.document), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'INVOCATION_OR_SOURCE_MISMATCH'):
            self.resume()

    def test_wrong_host_ownership_wrapper_exit_or_command_is_rejected(self):
        self.run_matrix()
        path = self.attempt()
        original = matrix.read(path / 'process.json')
        for field, value in [('ownership', 'unverified'), ('wrapper_exit_code', 7),
                             ('argv', ['python.exe', '-c', 'print(1)']), ('tree_verified', False)]:
            with self.subTest(field=field):
                matrix.save(path / 'process.json', {**original, field: value}, replace=True)
                self.reseal(path)
                self.assertFalse(matrix.inspect_attempt(path, self.invocation, 'other')['passed'])

    def test_runtime_change_during_lane_keeps_capture_failed_and_blocks_resume(self):
        inert = InertRunner()
        original = inert.run_process
        def mutate(*args, **kwargs):
            host = original(*args, **kwargs)
            (self.source / 'test.txt').write_text('changed', encoding='utf-8')
            return host
        with patch.object(inert, 'run_process', side_effect=mutate):
            result, _ = self.run_matrix(inert)
        self.assertFalse(result['passed'])
        self.assertFalse(result['snapshot_unchanged'])
        with self.assertRaisesRegex(ValueError, 'SOURCE_FILES_MISMATCH'):
            self.resume()

    def test_synthetic_pass_field_does_not_override_failed_raw_outputs(self):
        self.run_matrix(InertRunner({'other': 'fail'}))
        path = self.attempt()
        record = matrix.read(path / 'attempt.json')
        matrix.save(path / 'attempt.json', {**record, 'passed': True, 'counts': {'run': 2}}, replace=True)
        self.assertFalse(matrix.inspect_attempt(path, self.invocation, 'other')['passed'])

    def test_origin_drift_is_distinct_from_unchanged_frozen_runtime(self):
        with redirect_stdout(io.StringIO()):
            result = matrix.run_matrix(self.output, self.source, self.document, self.invocation,
                                       InertRunner(), origin_files={})
        self.assertTrue(result['passed'])
        self.assertTrue(result['snapshot_unchanged'])
        self.assertFalse(result['origin_source_unchanged'])
        self.assertFalse(result['formal_acceptance'])


    def test_capture_stays_false_until_all_partitions_complete(self):
        inert = InertRunner()
        original = inert.run_process
        observations = []
        def observe(*args, **kwargs):
            observations.append(matrix.read(self.output / 'capture.json'))
            return original(*args, **kwargs)
        with patch.object(inert, 'run_process', side_effect=observe):
            result, _ = self.run_matrix(inert)
        self.assertTrue(result['passed'])
        self.assertEqual(len(observations), len(matrix.LABELS))
        self.assertTrue(all(row['passed'] is False and row['state'] == 'RUNNING' for row in observations))

    def test_origin_change_during_run_is_recorded_in_final_capture(self):
        with redirect_stdout(io.StringIO()):
            result = matrix.run_matrix(self.output, self.source, self.document, self.invocation,
                InertRunner(), origin_files=self.document['files'], origin_probe=lambda: {})
        self.assertTrue(result['passed'])
        self.assertTrue(result['origin_source_unchanged_before'])
        self.assertFalse(result['origin_source_unchanged_after'])
        self.assertFalse(result['origin_source_unchanged'])

    def test_incomplete_process_exception_retries_in_fresh_attempt(self):
        inert = InertRunner()
        original = inert.run_process
        def crash(*args, **kwargs):
            if args[0][-1] == 'other':
                raise OSError('inert injected failure')
            return original(*args, **kwargs)
        with patch.object(inert, 'run_process', side_effect=crash):
            first, _ = self.run_matrix(inert)
        self.assertFalse(first['passed'])
        failed = self.attempt() / 'process.json'
        self.assertEqual(matrix.read(failed), {'controller_error': 'OSError'})
        second, runner = self.run_matrix()
        self.assertTrue(second['passed'])
        self.assertEqual(runner.calls, ['other'])
        self.assertTrue(failed.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
