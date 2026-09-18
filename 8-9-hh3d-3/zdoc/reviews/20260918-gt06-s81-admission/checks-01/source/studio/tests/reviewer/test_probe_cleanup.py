"""Evidence-staging failures must release or retain the exact prepared owner.

No GUI, network, engines, or evidence files are created by these regressions.
"""
from contextlib import ExitStack
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.reviewer import main as lifecycle
from studio.tests.reviewer import run_reviewer_probe as probe


class EvidencePath:
    def __init__(self, mkdir_error=None):
        self.mkdir_error = mkdir_error

    def __truediv__(self, _):
        return self

    def mkdir(self):
        if self.mkdir_error is not None:
            raise self.mkdir_error


class ProbeCleanupTests(unittest.TestCase):
    def stage_failure(self, original, *, mkdir=False, write_number=1, cleanup_error=None):
        owner = lifecycle.PreparedReviewer()
        close = Mock(side_effect=cleanup_error)
        owner.backend = SimpleNamespace(root=EvidencePath(original if mkdir else None), close=close)
        held = []
        outcomes = [None] * (write_number - 1) + [original]
        with ExitStack() as stack:
            stack.enter_context(patch.object(lifecycle, 'HELD_REVIEWERS', held))
            prepare = stack.enter_context(patch.object(probe.PreparedReviewer, 'prepare', return_value=owner))
            write = stack.enter_context(patch.object(probe.native, 'write', side_effect=outcomes))
            gui = stack.enter_context(patch.object(probe.tk, 'Tk', side_effect=AssertionError('GUI forbidden')))
            with self.assertRaises(type(original)) as caught:
                probe.run('gt06-reviewer-staging-regression', 'complete')
            self.assertIs(caught.exception, original)
            prepare.assert_called_once_with('gt06-reviewer-staging-regression')
            close.assert_called_once_with()
            gui.assert_not_called()
            self.assertEqual(write.call_count, 0 if mkdir else write_number)
            if cleanup_error is None:
                self.assertTrue(owner.closed)
                self.assertEqual(held, [])
            else:
                self.assertFalse(owner.closed)
                self.assertEqual(held, [owner])
                self.assertIs(caught.exception.__cause__, cleanup_error)
                # The actual PreparedReviewer retains and later drains this owner.
                close.side_effect = None
                self.assertTrue(owner.close())
                self.assertEqual(held, [])
                self.assertTrue(owner.closed)

    def test_directory_creation_failure_closes_prepared_owner(self):
        self.stage_failure(OSError('injected directory failure'), mkdir=True)

    def test_manifest_write_failure_closes_prepared_owner(self):
        self.stage_failure(OSError('injected manifest write failure'))

    def test_partial_source_staging_failure_closes_prepared_owner(self):
        self.stage_failure(OSError('injected source write failure'), write_number=3)

    def test_original_staging_error_survives_uncertain_cleanup_with_owner_retained(self):
        self.stage_failure(OSError('injected staging failure'),
                           cleanup_error=RuntimeError('injected cleanup failure'))

    def test_interrupted_staging_still_closes_prepared_owner(self):
        self.stage_failure(KeyboardInterrupt())


if __name__ == '__main__':
    unittest.main()
