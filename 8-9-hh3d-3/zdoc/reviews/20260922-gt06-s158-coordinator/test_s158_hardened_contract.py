"""Process-free tests for the future S158 helper contract."""
import hashlib
import tempfile
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s158_hardened_contract as contract


class S158ContractTests(unittest.TestCase):
    def test_helper_map_and_child_are_required_and_hashed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            child = root / "child.py"
            child.write_bytes(b"child\n")
            digest = hashlib.sha256(child.read_bytes()).hexdigest()
            freeze = {"helper_root": str(root), "child_script": "child.py",
                      "helper_files": {"child.py": digest}}
            self.assertEqual(contract.validate_helper_pin(freeze, child_script="child.py")["child_script"], "child.py")
            child.write_bytes(b"drift\n")
            with self.assertRaisesRegex(contract.ContractError, "S158_HELPER_DRIFT"):
                contract.validate_helper_pin(freeze, child_script="child.py")

    def test_missing_helper_map_is_blocked(self):
        with self.assertRaisesRegex(contract.ContractError, "S158_HELPER_PIN_MISSING"):
            contract.validate_helper_pin({"helper_root": "C:/helper"}, child_script="child.py")

    def test_boundary_requires_prefix_and_target_pid_binding(self):
        with self.assertRaisesRegex(contract.ContractError, "S158_PREFIX_MISSING"):
            contract.validate_boundary_binding({"screened_batches": []}, {})
        summary = {"screened_batches": [{"index": 0}, {"index": 2}], "pid": 7001}
        with self.assertRaisesRegex(contract.ContractError, "S158_PREFIX_NOT_CONTIGUOUS"):
            contract.validate_boundary_binding(summary, {"actual_target_exit": {"pid": 7001}})
        summary["screened_batches"][1]["index"] = 1
        with self.assertRaisesRegex(contract.ContractError, "S158_TARGET_PID_NOT_BOUND"):
            contract.validate_boundary_binding(summary, {"actual_target_exit": {"pid": 7002}})
        self.assertEqual(contract.validate_boundary_binding(summary, {"actual_target_exit": {"pid": 7001}})["prefix_count"], 2)


if __name__ == "__main__":
    unittest.main()
