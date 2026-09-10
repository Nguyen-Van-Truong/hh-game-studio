import hashlib
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).parents[2] / "build" / "bootstrap" / "run_fixture.py"
spec = importlib.util.spec_from_file_location("run_fixture", MODULE)
run_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run_fixture)


class RunFixtureTests(unittest.TestCase):
    def test_hash_and_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "space-đ"
            root.mkdir()
            file = root / "sample.txt"
            file.write_text("hello", encoding="utf-8")
            self.assertEqual(run_fixture.hash_file(file), hashlib.sha256(b"hello").hexdigest())
            self.assertIn("sample.txt", run_fixture.checked_files(root))

    def test_timeout_captures_owned_child(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = run_fixture.run_process(
                ["python", "-c", "import time; time.sleep(10)"],
                cwd=output, output=output, timeout=1, label="timeout")
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["tree_verified"])
            self.assertTrue((output / "timeout-stdout.txt").exists())

    def test_timeout_kills_descendant_and_keeps_real_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            code = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); time.sleep(20)"
            result = run_fixture.run_process([sys.executable, "-c", code], cwd=output,
                                             output=output, timeout=1, label="descendant")
            self.assertTrue(result["timed_out"])
            self.assertTrue(result["tree_verified"])
            self.assertIn("wrapper_pid", result)

    def test_real_exit_and_separate_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = run_fixture.run_process(
                ["python", "-c", "print('ok')"],
                cwd=output, output=output, timeout=5, label="ok")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["wrapper_exit_code"], 0)
            self.assertTrue(result["tree_verified"])
            self.assertEqual((output / "ok-stdout.txt").read_text().strip(), "ok")

    def test_reject_duplicate_output_before_spawn(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            self.assertEqual(run_fixture.main([
                "--studio-root", str(Path(temporary)), "--godot-exe", str(Path(temporary) / "missing.exe"),
                "--expected-version", "4.7.1", "--console-sha256", "0" * 64,
                "--gui-sha256", "0" * 64, "--run-id", "r", "--command-id", "c",
                "--output", str(output)]), 2)


if __name__ == "__main__":
    unittest.main()
