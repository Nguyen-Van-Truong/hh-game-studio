import hashlib
from pathlib import Path
import tempfile
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import s159_helper_contract as contract


class S159HelperContractTests(unittest.TestCase):
    def test_exact_helper_closure_and_bytes_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            child = root / "child.py"
            child.write_bytes(b"child\n")
            digest = hashlib.sha256(child.read_bytes()).hexdigest()
            files = {"child.py": digest}
            freeze = {"helper_root": str(root), "helper_files": files,
                      "helper_closure_sha256": contract.closure_for(files)}
            contract.validate_helper_freeze(freeze, child_script="child.py")
            freeze["helper_closure_sha256"] = "0" * 64
            with self.assertRaisesRegex(contract.ContractError, "S159_HELPER_CLOSURE_MISMATCH"):
                contract.validate_helper_freeze(freeze, child_script="child.py")

    def test_prefix_bound_and_pid_are_required(self):
        summary = {"screened_batches": [{"index": 0}, {"index": 1}], "pid": 7001}
        self.assertEqual(contract.validate_prefix_and_pid(summary, {"actual_target_exit": {"pid": 7001}})["prefix_count"], 2)
        summary["screened_batches"] = [{"index": index} for index in range(9)]
        with self.assertRaisesRegex(contract.ContractError, "S159_PREFIX_BOUND"):
            contract.validate_prefix_and_pid(summary, {"actual_target_exit": {"pid": 7001}})

    def test_invalid_identity_is_not_accepted(self):
        with self.assertRaisesRegex(contract.ContractError, "S159_TARGET_PID_NOT_BOUND"):
            contract.validate_prefix_and_pid({"screened_batches": [{"index": 0}], "pid": 7001}, {"actual_target_exit": {"pid": 7002}})


if __name__ == "__main__":
    unittest.main()
