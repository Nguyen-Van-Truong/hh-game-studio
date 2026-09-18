"""Actual short owned processes exercise GT05 harness failure boundaries."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import StageFailed, run_trusted_stage
from studio.pipeline import native_job


@unittest.skipUnless(os.name == 'nt', 'Windows Job ownership is required')
class NativeJobTests(unittest.TestCase):
    def setUp(self):
        parent = STUDIO / '.local/reviews'
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix='gt05-job-test-', dir=parent))
        self.script = self.root / 'trusted.py'
        self.script.write_text("print('owned child')\n", encoding='utf-8')
        self.source = {'trusted.py': hashlib.sha256(self.script.read_bytes()).hexdigest()}

    def run_stage(self, code=None, **kwargs):
        if code is not None:
            self.script.write_text(code, encoding='utf-8')
            self.source['trusted.py'] = hashlib.sha256(self.script.read_bytes()).hexdigest()
        return run_trusted_stage([sys.executable, '-B', str(self.script)],
            cwd=self.root, output=self.root / 'host', source_root=self.root,
            source_files=self.source,
            binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            **kwargs)

    def assert_closed(self):
        report = json.loads((self.root / 'host/capture.json').read_bytes())
        self.assertTrue(report['job']['closed'])
        self.assertTrue(report['job']['zero_observed'])
        self.assertFalse(report['job']['tainted'])
        self.assertFalse(report['job']['handle_retained'])
        return report

    def test_success_has_actual_pid_exit_and_queried_zero_job(self):
        report = self.run_stage()
        self.assertTrue(report['completed'])
        self.assertEqual(report['wrapper_exit_code'], 0)
        self.assertEqual(report['actual_process_exit']['exit_code'], 0)
        self.assertGreater(report['actual_process_exit']['pid'], 0)
        self.assertTrue(report['natural_tree_exit'])
        self.assertEqual(report['active_before_cleanup'], 0)
        self.assert_closed()

    def test_successful_parent_with_live_child_is_rejected_before_cleanup(self):
        with self.assertRaisesRegex(StageFailed, 'STAGE_DESCENDANTS_REMAIN'):
            self.run_stage("import subprocess,sys\nsubprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n")
        report = self.assert_closed()
        self.assertFalse(report['completed'])
        self.assertFalse(report['natural_tree_exit'])
        self.assertGreater(report['active_before_cleanup'], 0)

    def test_disk_budget_combines_sibling_roots_without_double_count(self):
        cwd = self.root / 'cwd'; cwd.mkdir()
        output = self.root / 'output'; output.mkdir()
        (cwd / 'one').write_bytes(b'x' * 40)
        (output / 'two').write_bytes(b'x' * 40)
        with mock.patch.object(native_job, 'DISK_BYTES', 64):
            with self.assertRaisesRegex(StageFailed, 'STAGE_DISK_CAP'):
                native_job._combined_workspace_size(cwd, output)
        with mock.patch.object(native_job, 'DISK_BYTES', 128):
            self.assertEqual(native_job._combined_workspace_size(cwd, output), 80)
            self.assertEqual(native_job._combined_workspace_size(self.root, output), 80 + self.script.stat().st_size)

    def test_disk_watchdog_tolerates_deleted_owned_scratch_only(self):
        missing = mock.Mock()
        missing.stat.side_effect = FileNotFoundError()
        root = mock.Mock()
        root.rglob.return_value = [missing]
        self.assertEqual(native_job._workspace_size(root), 0)
        missing.stat.side_effect = PermissionError()
        with self.assertRaises(PermissionError):
            native_job._workspace_size(root)

    def test_nonzero_child_is_not_promoted_to_success(self):
        with self.assertRaisesRegex(StageFailed, 'STAGE_NATIVE_EXIT'):
            self.run_stage('raise SystemExit(7)\n')
        self.assertFalse(self.assert_closed()['completed'])
        actual = json.loads((self.root / 'host/process-exit.json').read_bytes())
        self.assertEqual(actual['exit_code'], 7)

    def test_actual_short_deadline_kills_only_owned_job(self):
        with self.assertRaisesRegex(StageFailed, 'STAGE_WALL_LIMIT'):
            self.run_stage('import time\ntime.sleep(10)\n', timeout_seconds=0.2)
        self.assertFalse(self.assert_closed()['completed'])

    def test_pre_stopped_gate_never_starts_target(self):
        stopped = threading.Event()
        stopped.set()
        with self.assertRaisesRegex(StageFailed, 'STAGE_STOPPED'):
            self.run_stage(stop=stopped)
        self.assertFalse((self.root / 'host/process-start.json').exists())
        self.assertFalse(self.assert_closed()['completed'])

    def test_source_drift_blocks_before_launch(self):
        self.script.write_text("print('unreviewed')", encoding='utf-8')
        with self.assertRaisesRegex(StageFailed, 'STAGE_SOURCE_CHANGED'):
            self.run_stage()
        self.assertFalse((self.root / 'host').exists())

    def test_stream_overflow_preserved_and_rejected(self):
        with self.assertRaisesRegex(StageFailed, 'STAGE_LOG_CAP_OR_IO|STAGE_STREAM_DRAIN'):
            self.run_stage("import sys\nsys.stdout.write('x'*300000)\nsys.stdout.flush()\n")
        report = self.assert_closed()
        self.assertFalse(report['completed'])
        self.assertLessEqual((self.root / 'host/stdout.txt').stat().st_size, 262144)


if __name__ == '__main__':
    unittest.main()
