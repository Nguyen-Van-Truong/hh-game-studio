"""Measurement marker ownership and concurrent-window refusal."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from studio.tests.replay.benchmark_job import BenchmarkJobError
from studio.tests.replay.measure_window import measurement_window


class MeasureWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'measure-window.lock'

    def test_marker_is_visible_and_guard_blocks_second_owner(self):
        with measurement_window('gt06-test', 'test', path=self.path):
            value = json.loads(self.path.read_bytes())
            self.assertEqual(value['run_id'], 'gt06-test')
            self.assertEqual(value['pid'], os.getpid())
            with self.assertRaisesRegex(BenchmarkJobError, 'BUSY'):
                with measurement_window('gt06-other', 'test', path=self.path):
                    self.fail('two windows')
        self.assertFalse(self.path.exists())
        self.assertTrue(self.path.with_suffix('.guard').exists())

    def test_live_expired_owner_is_not_stolen(self):
        self.path.write_text(json.dumps({'pid': os.getpid(), 'expires_utc': '2000-01-01'}))
        with self.assertRaisesRegex(BenchmarkJobError, 'BUSY'):
            with measurement_window('gt06-test', 'test', path=self.path):
                self.fail('stolen')
        self.assertTrue(self.path.exists())

    def test_dead_marker_recovered_under_guard(self):
        self.path.write_text(json.dumps({'pid': 99999999}))
        with patch('studio.tests.replay.measure_window.Journal._pid_alive', return_value=False):
            with measurement_window('gt06-test', 'test', path=self.path):
                self.assertEqual(json.loads(self.path.read_bytes())['run_id'], 'gt06-test')
        self.assertFalse(self.path.exists())

    def test_uncertain_cleanup_retains_marker(self):
        with measurement_window('gt06-test', 'test', path=self.path, safe_to_release=lambda: False):
            pass
        self.assertTrue(self.path.exists())

    def test_foreign_marker_is_never_removed(self):
        with self.assertRaisesRegex(BenchmarkJobError, 'OWNER_CHANGED'):
            with measurement_window('gt06-test', 'test', path=self.path):
                self.path.write_text('foreign')
        self.assertEqual(self.path.read_text(), 'foreign')
