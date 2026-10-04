"""Real Windows process proof for diagnostic cuts, without Godot/Blender."""
import os
from pathlib import Path
import sys
import tempfile
import unittest

from studio.tests.jobs.gt07_crash_process import run_cut


@unittest.skipUnless(os.name == "nt", "Windows Job Object required")
class CrashProcessTests(unittest.TestCase):
    def _run(self, wrong_pid=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            child = root / "child.py"
            child.write_text('''import json, os, pathlib, sys, time
if sys.stdin.readline() != "GO\\n":
    raise SystemExit(74)
path = pathlib.Path(sys.argv[1])
payload = {"schema": "HH-GT07-FAILPOINT-REACHED-1", "run_id": "unit-cut",
           "phase": "ACK", "pid": os.getpid() + int(sys.argv[2]), "monotonic_ns": time.monotonic_ns()}
tmp = path.with_suffix(".pending")
tmp.write_text(json.dumps(payload))
tmp.rename(path)
while True: time.sleep(1)
''', encoding="utf-8")
            report = run_cut([sys.executable, "-B", str(child), str(root / "receipt.json"),
                              str(int(wrong_pid))], cwd=root, output=root,
                env=os.environ.copy(), receipt_path=root / "receipt.json",
                run_id="unit-cut", phase="ACK", timeout=5)
            self.assertEqual((root / "crash.stderr.log").read_bytes(), b"")
            return report

    def test_real_cut_uses_pid_start_handle_and_cleans_owned_job(self):
        report = self._run()
        self.assertTrue(report["cut_verified"], report)
        self.assertFalse(report["natural_exit"])
        self.assertNotEqual(report["exit_code"], 0)
        self.assertGreater(report["target_creation_filetime"], 0)
        self.assertEqual(report["receipt"]["pid"], report["target_pid"])
        self.assertFalse(report["tree_cleanup_terminated"])
        self.assertTrue(report["process_handle_closed"])

    def test_wrong_pid_is_cleanup_only_never_a_verified_cut(self):
        report = self._run(wrong_pid=True)
        self.assertFalse(report["cut_verified"])
        self.assertFalse(report["target_terminated"])
        self.assertTrue(report["tree_verified"], report)
        self.assertTrue(report["process_handle_closed"])
        self.assertEqual(report["errors"][0]["code"], "CRASH_RECEIPT_BINDING_MISMATCH")


if __name__ == "__main__":
    unittest.main()
