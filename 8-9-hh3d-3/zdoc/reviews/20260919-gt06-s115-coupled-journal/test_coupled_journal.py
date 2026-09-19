"""No-engine controls: diagnostic boundaries cannot bypass original gates."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('s115', Path(__file__).with_name('coupled_journal.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Controls(unittest.TestCase):
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

    def test_boundary_only_after_seventh_successful_gate(self):
        rows, calls = [], []
        def original(sample, baseline):
            calls.append((sample, baseline))
        for index in range(6):
            probe.boundary_screen(original, index, 'baseline', rows)
        with self.assertRaises(probe.Boundary):
            probe.boundary_screen(original, 6, 'baseline', rows)
        self.assertEqual(7, len(calls))
        self.assertEqual(list(range(7)), [r['index'] for r in rows])

    def test_rejection_at_last_boundary_stays_original(self):
        rows = [{'index': i, 'original_gate': 'PASSED'} for i in range(6)]
        def reject(sample, baseline):
            raise ValueError('RETAINED_COUNTER_GROWTH')
        with self.assertRaisesRegex(ValueError, 'RETAINED_COUNTER_GROWTH'):
            probe.boundary_screen(reject, {}, {}, rows)
        self.assertEqual(6, len(rows))


if __name__ == '__main__':
    unittest.main()
