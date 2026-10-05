"""Marker regression; native phase execution is tested by the owned Godot run."""
import copy
import unittest

from studio.tests.replay import run_save_boundary_test as boundary


class RealSaveBoundaryMarkerTests(unittest.TestCase):
    def fixture(self):
        state = {'phase': 7, 'returned': False, 'recorded': True, 'save_end_us': 0,
                 'batch': 0, 'cycle': 0, 'root_id': 1234}
        result = {'run_id': 'sample', 'actual_exits': {'editor': {'pid': 42}}}
        return {'run_id': 'sample', 'pid': 42, 'failed': False,
                'before': state.copy(), 'after': state.copy()}, result

    def test_placeholder_key_is_not_a_published_hash(self):
        row, result = self.fixture()
        self.assertEqual(boundary.verify_real_marker([row], result), row)

    def test_fault_suite_requires_actual_pid_and_every_unique_check(self):
        row = {'pid': 42, 'passed': True, 'fault_injected': True, 'real_save_exercised': False,
               'formal14_root_cause_proven': False,
               'checks': [{'name': name, 'passed': True} for name in sorted(boundary.EXPECTED_CHECKS)]}
        capture = {'actual_process_exit': {'pid': 42}}
        self.assertEqual(boundary.verify_fault_marker([row], capture), row)
        for checks in ([], row['checks'][:-1], row['checks'][:-1] + [row['checks'][0]],
                       [{**row['checks'][0], 'passed': False}, *row['checks'][1:]]):
            with self.assertRaises(boundary.native.DiagnosticError):
                boundary.verify_fault_marker([{**row, 'checks': checks}], capture)
        with self.assertRaises(boundary.native.DiagnosticError):
            boundary.verify_fault_marker([{**row, 'pid': 43}], capture)

    def test_advancement_return_and_identity_changes_are_rejected(self):
        row, result = self.fixture()
        for field, value in [('phase', 8), ('returned', True), ('save_end_us', 999),
                             ('batch', 1), ('cycle', 1), ('root_id', 5678)]:
            changed = copy.deepcopy(row)
            changed['after'][field] = value
            with self.subTest(field=field), self.assertRaises(boundary.native.DiagnosticError):
                boundary.verify_real_marker([changed], result)
        for field, value in [('failed', True), ('pid', 43), ('run_id', 'other')]:
            with self.subTest(field=field), self.assertRaises(boundary.native.DiagnosticError):
                boundary.verify_real_marker([{**row, field: value}], result)

    def test_already_completed_or_missing_duplicate_marker_is_rejected(self):
        row, result = self.fixture()
        for field, value in [('phase', 8), ('returned', True), ('save_end_us', 999)]:
            changed = copy.deepcopy(row)
            changed['before'][field] = changed['after'][field] = value
            with self.subTest(field=field), self.assertRaises(boundary.native.DiagnosticError):
                boundary.verify_real_marker([changed], result)
        for rows in ([], [row, row]):
            with self.assertRaises(boundary.native.DiagnosticError):
                boundary.verify_real_marker(rows, result)


if __name__ == '__main__':
    unittest.main()
