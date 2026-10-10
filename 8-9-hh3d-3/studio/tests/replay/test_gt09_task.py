"""Fixed Scheduled Task selection, without launching a task or engine."""
from pathlib import Path
import unittest

from studio.tests.replay import run_gt09_task as task


class TaskSelectionTests(unittest.TestCase):
    def test_final_and_rehearsal_have_distinct_bound_commands(self):
        console, output = Path('python.exe'), Path('output')
        final = task._command(console, 'gt09-matrix-final-20261010-test', output, [])
        rehearsal = task._command(console, 'gt09-matrix-rehearsal-20261010-test', output, ['K3'])
        self.assertEqual(final[3:5], ['--matrix', 'final'])
        self.assertEqual(rehearsal[3:5], ['--rows', 'K3'])
        self.assertNotIn('--matrix', rehearsal)

    def test_selection_cannot_disguise_rehearsal_as_final_or_inject_arguments(self):
        for kind, rows in [('final', ['K3']), ('rehearsal', []),
                           ('rehearsal', ['K4']), ('rehearsal', ['K3', 'K3']),
                           ('rehearsal', 'K3'), ('final', None),
                           ('rehearsal', ['K3', '--matrix', 'final'])]:
            with self.subTest(kind=kind, rows=rows):
                with self.assertRaisesRegex(ValueError, 'GT09_TASK_ROW_SELECTION'):
                    task._selection('gt09-matrix-' + kind + '-20261010-test', rows)


if __name__ == '__main__':
    unittest.main()
