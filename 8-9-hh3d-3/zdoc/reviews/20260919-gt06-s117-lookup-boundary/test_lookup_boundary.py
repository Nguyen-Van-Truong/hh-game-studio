"""No-engine controls: diagnostic boundaries cannot bypass original gates."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('s117', Path(__file__).with_name('lookup_boundary.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Controls(unittest.TestCase):
    def test_executable_helper_is_outside_imported_runtime_scope(self):
        root = Path.cwd()
        result = probe.helper_layout(root, root / 'zdoc/reviews/probe', 'test')
        self.assertFalse(result.is_relative_to(root / 'studio'))
        with self.assertRaisesRegex(RuntimeError, 'S117_HELPER_INSIDE_RUNTIME_SCOPE'):
            probe.helper_layout(root, root / 'studio/.local/reviews', 'test')

    def test_boundary_keeps_original_cleanup_failure(self):
        boundary = probe.Boundary()
        failure = OSError('CLOSE_FAILED')
        boundary.cleanup_errors = (failure,)
        self.assertEqual([('retained_cleanup', failure)], probe.retained_cleanup_errors(boundary))

    def test_original_rejection_not_swallowed(self):
        rows = []
        def reject(sample, baseline):
            raise ValueError('ORIGINAL_GATE')
        with self.assertRaisesRegex(ValueError, 'ORIGINAL_GATE'):
            probe.boundary_screen(reject, {}, None, rows)
        self.assertEqual([], rows)

    def test_boundary_only_after_eleventh_successful_gate(self):
        rows, calls = [], []
        def original(sample, baseline):
            calls.append((sample, baseline))
        for index in range(10):
            probe.boundary_screen(original, index, 'baseline', rows)
        with self.assertRaises(probe.Boundary):
            probe.boundary_screen(original, 10, 'baseline', rows)
        self.assertEqual(11, len(calls))
        self.assertEqual(list(range(11)), [r['index'] for r in rows])

    def test_rejection_at_last_boundary_stays_original(self):
        rows = [{'index': i, 'original_gate': 'PASSED'} for i in range(10)]
        def reject(sample, baseline):
            raise ValueError('RETAINED_COUNTER_GROWTH')
        with self.assertRaisesRegex(ValueError, 'RETAINED_COUNTER_GROWTH'):
            probe.boundary_screen(reject, {}, {}, rows)
        self.assertEqual(10, len(rows))

    def test_sqlite_controls_preserve_return_and_arguments(self):
        calls, labels = [], []
        sentinel = object()
        class Timings:
            def call(self, label, function, *args, **kwargs):
                labels.append(label)
                return function(*args, **kwargs)
        def original(*args, **kwargs):
            calls.append((args, kwargs))
            return sentinel
        for sql in ('BEGIN IMMEDIATE', 'COMMIT', 'ROLLBACK', 'SELECT private_data'):
            self.assertIs(sentinel, probe.measured_execute(original, Timings(), sentinel,
                sql, ('private_value',), fetch=True))
        self.assertEqual(['sqlite_begin', 'sqlite_commit', 'sqlite_rollback'], labels)
        self.assertEqual(4, len(calls))
        self.assertEqual((sentinel, 'SELECT private_data', ('private_value',)), calls[-1][0])
        self.assertEqual({'fetch': True}, calls[-1][1])

    def test_sqlite_original_exception_is_not_remapped(self):
        failure = OSError('original')
        class Timings:
            def call(self, label, function, *args, **kwargs):
                return function(*args, **kwargs)
        def original(*args, **kwargs):
            raise failure
        for sql in ('COMMIT', 'SELECT private_data'):
            with self.assertRaises(OSError) as captured:
                probe.measured_execute(original, Timings(), None, sql)
            self.assertIs(failure, captured.exception)


if __name__ == '__main__':
    unittest.main()


