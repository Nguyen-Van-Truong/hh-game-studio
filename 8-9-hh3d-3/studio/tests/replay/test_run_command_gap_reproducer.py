import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from studio.tests.replay import run_command_gap_reproducer as reproducer


class CommandGapReproducerTests(unittest.TestCase):
    def test_reproducer_schema_declares_controlled_boundary(self):
        self.assertEqual(reproducer.SCHEMA, 'HH-GT06-COMMAND-GAP-REPRODUCER-1')
        self.assertTrue(reproducer.RUN_ID.fullmatch('gt06-gap-repro-test'))

    def test_reproducer_rejects_unbounded_delay(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, 'REPRODUCER_DELAY'):
                reproducer.run(Path(directory) / 'out', 'gt06-gap-test', 1.0)

    def test_reproducer_requires_unique_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'out'
            output.mkdir()
            with self.assertRaisesRegex(RuntimeError, 'REPRODUCER_OUTPUT_EXISTS'):
                reproducer.run(output, 'gt06-gap-test', 2.5)


if __name__ == '__main__':
    unittest.main()
