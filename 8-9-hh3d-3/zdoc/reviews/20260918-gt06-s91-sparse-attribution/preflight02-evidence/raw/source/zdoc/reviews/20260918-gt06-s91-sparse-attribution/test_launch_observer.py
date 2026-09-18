"""Small real-Python exit/Job checks; never opens Godot or registers a task."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('s91_observer', BASE / 'launch_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class BindingTests(unittest.TestCase):
    def test_changed_or_extra_binding_is_rejected(self):
        expected = {'run_id': 'example', 'digest': 'a'}
        observer.validate_request(dict(expected), expected)
        for changed in ({**expected, 'digest': 'b'}, {**expected, 'extra': True}):
            with self.assertRaisesRegex(RuntimeError, 'OBSERVER_REQUEST_BINDING'):
                observer.validate_request(changed, expected)


@unittest.skipUnless(os.name == 'nt', 'Windows retained handles')
class NativeExitTests(unittest.TestCase):
    def exercise(self, mode):
        root = BASE / ('observer-tests-' + str(os.getpid()))
        root.mkdir(exist_ok=True)
        directory = root / mode
        directory.mkdir(exist_ok=False)
        console = Path(sys.executable).with_name('python.exe')
        process = job = target = None
        streams = []
        result = {'mode': mode, 'formal_acceptance': False}
        try:
            process, job, target, streams, limits = observer.start_owned(console, directory, test_mode=mode)
            self.assertEqual(limits['process_limit'], 7)
            with self.assertRaisesRegex(RuntimeError, 'OBSERVER_PARENT_IDENTITY'):
                observer.Retained(process.pid, console, expected_parent=os.getpid() + 1)
            process.stdin.write(b'START\n')
            process.stdin.close()
            if mode == 'success':
                self.assertEqual(process.wait(timeout=5), 0)
                self.assertTrue(target.observe_exit())
                self.assertEqual(target.row['actual_exit']['exit_code_uint32'], 0)
            else:
                self.assertIsNone(process.poll())
                self.assertFalse(target.observe_exit())
                job.close()
                self.assertEqual(process.wait(timeout=5), 2)
                self.assertTrue(target.observe_exit())
                self.assertEqual(target.row['actual_exit']['exit_code_uint32'], 2)
            job.close()
            self.assertTrue(job.closed and job.zero_observed)
            self.assertFalse(job.tainted)
            target.close()
            self.assertTrue(target.row['handle_closed'])
            result.update(process=target.row, actual_popen_exit=process.returncode,
                          job=job.snapshot(), limits=limits, passed=True)
        finally:
            if job is not None:
                job.close()
            if process is not None:
                process.wait(timeout=5)
            if target is not None and target.probe.handle is not None:
                target.close()
            for stream in streams:
                stream.close()
            if process is not None:
                observer.close_popen_handle(process)
                result['popen_handle_closed'] = True
            observer.write(directory / 'result.json', result)

    def test_success_actual_exit(self):
        self.exercise('success')

    def test_forced_job_cleanup_actual_exit(self):
        self.exercise('wait')


if __name__ == '__main__':
    unittest.main(verbosity=2)
