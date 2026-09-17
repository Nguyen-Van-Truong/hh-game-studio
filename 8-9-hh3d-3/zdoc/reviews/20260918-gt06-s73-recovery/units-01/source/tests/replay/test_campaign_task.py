"""Local scheduler request binding and early native error regressions."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.tests.replay import run_campaign_task as task
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.benchmark_job import BenchmarkJobError


class TaskRequestTests(unittest.TestCase):
    def test_exact_request_rejects_changed_mode_id_script_or_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ('script.py', 'pythonw.exe', 'python.exe')]
            for path in paths:
                path.write_bytes(path.name.encode())
            value = {'schema': 'HH-GT06-TASK-REQUEST-1', 'campaign_id': 'gt06-inert',
                'mode': 'probe', 'script_sha256': task.sha(paths[0]),
                'pythonw_sha256': task.sha(paths[1]), 'python_sha256': task.sha(paths[2])}
            task.validate_request(value, 'gt06-inert', 'probe', *paths)
            resumed = {**value, 'launch_number': 2}
            task.validate_request(resumed, 'gt06-inert', 'probe', *paths, launch_number=2)
            for changed in (value, {**resumed, 'launch_number': 3}, {**resumed, 'launch_number': 2.0}):
                with self.assertRaisesRegex(ValueError, 'TASK_REQUEST_BINDING'):
                    task.validate_request(changed, 'gt06-inert', 'probe', *paths, launch_number=2)
            with self.assertRaisesRegex(ValueError, 'TASK_REQUEST_BINDING'):
                task.validate_request(resumed, 'gt06-inert', 'probe', *paths)
            for key in (*value, 'unknown'):
                with self.subTest(field=key):
                    with self.assertRaisesRegex(ValueError, 'TASK_REQUEST_BINDING'):
                        task.validate_request({**value, key: 'changed'}, 'gt06-inert', 'probe', *paths)
            for path in paths:
                previous = path.read_bytes()
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'TASK_REQUEST_BINDING'):
                    task.validate_request(value, 'gt06-inert', 'probe', *paths)
                path.write_bytes(previous)

    def test_launch_numbers_have_fixed_bounded_non_aliasing_slots(self):
        self.assertEqual(task.launch_suffix(1), '')
        self.assertEqual(task.launch_suffix(2), '-launch-02')
        self.assertEqual(len({task.launch_suffix(i) for i in range(1, 100)}), 99)
        for invalid in (0, 100, True, 2.0, '2', '../2'):
            with self.assertRaisesRegex(ValueError, 'TASK_LAUNCH_NUMBER'):
                task.launch_suffix(invalid)

    def test_single_use_evidence_write_cannot_overwrite_a_previous_result(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            task.write(path, {'code': 1})
            previous = path.read_bytes()
            with self.assertRaises(FileExistsError):
                task.write(path, {'code': 0})
            self.assertEqual(path.read_bytes(), previous)


class CampaignEntryClosureTests(unittest.TestCase):
    def test_separate_parent_and_child_interpreters_agree_on_exact_source_map(self):
        # Separate interpreters prevent this test module's imports from hiding
        # the launcher-only dependency that broke the real scheduler run.
        common = (
            'from studio.tests.replay import run_benchmark_campaign as c; '
            'c.load_fixture(); print(json.dumps(c.source_files(),sort_keys=True))'
        )
        maps = []
        for prefix in ('from studio.tests.replay import run_campaign_task; ', ''):
            result = subprocess.run([sys.executable, '-B', '-c', 'import json; ' + prefix + common],
                cwd=campaign.STUDIO.parent, capture_output=True, text=True, timeout=20, check=True)
            self.assertEqual(result.stderr, '')
            maps.append(json.loads(result.stdout))
        self.assertEqual(maps[0], maps[1])
        for relative in campaign.CAMPAIGN_FIXED_SOURCES:
            self.assertEqual(maps[0][relative], task.sha(campaign.STUDIO / relative))
        self.assertIn('host/core/transport.py', maps[0])

    def test_launcher_or_schema_mutation_is_rejected_even_when_not_imported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in campaign.CAMPAIGN_FIXED_SOURCES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(relative.encode())
            with patch.object(campaign, 'STUDIO', root), \
                 patch.object(campaign, 'imported_source_files', return_value={'dependency.py': 'a' * 64}):
                before = campaign.source_files()
                self.assertEqual(before['dependency.py'], 'a' * 64)
                for relative in campaign.CAMPAIGN_FIXED_SOURCES:
                    path = root / relative
                    original = path.read_bytes()
                    path.write_bytes(b'changed launcher')
                    with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_SOURCE_CHANGED'):
                        campaign.verify_sources(before)
                    path.write_bytes(original)
                campaign.verify_sources(before)


class NativeStderrTests(unittest.TestCase):
    def test_stderr_error_fails_even_if_stdout_reports_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stdout.txt').write_bytes(b'HH_GT06_BENCHMARK_READY {"index":0}\n')
            (root / 'stderr.txt').write_bytes(b'ERROR: Could not create child process --test-rd-creation\n')
            owner = SimpleNamespace(output=root, tick=Mock(return_value=None))
            log = campaign.NativeLog(owner)
            with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_NATIVE_STDERR'):
                log.wait('READY', 0, 20)
            self.assertFalse(log.events)
            owner.tick.assert_called_once()

    def test_late_stderr_error_fails_after_an_earlier_clean_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stdout.txt').write_bytes(b'')
            (root / 'stderr.txt').write_bytes(b'')
            log = campaign.NativeLog(SimpleNamespace(output=root, tick=Mock(return_value=None)))
            self.assertIsNone(log.poll())
            (root / 'stderr.txt').write_bytes(b'late error\n')
            with self.assertRaisesRegex(BenchmarkJobError, 'CAMPAIGN_NATIVE_STDERR'):
                log.poll()


if __name__ == '__main__':
    unittest.main()
