import json
from pathlib import Path
import unittest
from verify_s179 import inspect

HERE = Path(__file__).resolve().parent

class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.result = json.loads((HERE / "s179-child-attribution-result.json").read_bytes())
        self.stdout = (HERE / "wrapper.stdout.txt").read_text()
        self.debugger = (HERE / "cdb.stdout.txt").read_text()

    def test_observed_identity_preserves_exit_and_authority_gaps(self):
        facts = inspect(self.result, self.stdout, self.debugger)
        self.assertEqual(facts["attribution"], "UNKNOWN")
        self.assertEqual(facts["debugger_actual_exit"], 2147942430)
        self.assertEqual(facts["child_actual_exit"], "UNKNOWN_NOT_INDEPENDENTLY_RETAINED")
        self.assertFalse(facts["gt06_acceptance"])
        self.assertGreater(facts["breakpoint_hit_counts"]["CLOSE_BREAK"], 0)

    def test_wrapper_pid_is_rejected(self):
        self.result["debugger"]["attached_pid"] = self.result["wrapper"]["pid"]
        with self.assertRaisesRegex(ValueError, "attach binding"):
            inspect(self.result, self.stdout, self.debugger)

    def test_runtime_pid_must_match_child(self):
        with self.assertRaisesRegex(ValueError, "runtime PID"):
            inspect(self.result, self.stdout.replace("pid=31048", "pid=1"), self.debugger)

    def test_echoes_are_not_hits(self):
        text = "\n".join(line for line in self.debugger.splitlines()
                         if line not in ("NT_CREATE_BREAK", "CREATE2_BREAK", "CLOSE_BREAK"))
        with self.assertRaisesRegex(ValueError, "actual breakpoint hits"):
            inspect(self.result, self.stdout, text)

    def test_other_image_is_rejected(self):
        self.result["child"]["executable"] += ".changed"
        with self.assertRaisesRegex(ValueError, "executable module"):
            inspect(self.result, self.stdout, self.debugger)

if __name__ == "__main__":
    unittest.main()

