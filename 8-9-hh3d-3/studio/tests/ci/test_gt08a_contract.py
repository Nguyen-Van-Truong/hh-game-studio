from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


HERE = Path(__file__).resolve()
MODULE_PATH = HERE.parents[2] / "build" / "ci" / "gt08a_matrix.py"
SPEC = importlib.util.spec_from_file_location("gt08a_matrix", MODULE_PATH)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class GT08AMatrixContractTests(unittest.TestCase):
    def test_scenario_table_is_explicit_and_unique(self):
        ids = [row[0] for row in M.SCENARIOS]
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[:5], ["W01", "W02", "W03", "L01", "L02"])

    def test_dry_run_is_engine_and_network_free(self):
        result = M.dry_run()
        self.assertEqual(result["schema"], M.SCHEMA)
        self.assertFalse(result["engine_launched"])
        self.assertFalse(result["network_used"])
        self.assertEqual(len(result["scenarios"]), 18)

    def test_cache_key_binds_target_and_template(self):
        tools = M.toolchain()
        source = M.closure_hash(M.checked_tree(M.FIXTURE))
        windows = M.cache_key(source, tools, "Windows")
        linux = M.cache_key(source, tools, "Linux-headless")
        altered_template = M.cache_key(source, tools, "Windows", "other-template")
        self.assertNotEqual(windows, linux)
        self.assertNotEqual(windows, altered_template)
        self.assertEqual(windows, M.cache_key(source, tools, "Windows"))

    def test_local_signer_rejects_all_mutations(self):
        rows = M.signature_rows()
        self.assertEqual([r["id"] for r in rows], ["S01", "S02", "S03", "S04", "S05", "S06"])
        self.assertTrue(all(r["status"] == "PASS" for r in rows))

    def test_closure_hash_rejects_unsafe_paths(self):
        with self.assertRaises(M.MatrixError):
            M.closure_hash({"../outside": "a" * 64})

    def test_dry_run_does_not_create_review_output(self):
        with tempfile.TemporaryDirectory() as directory:
            before = sorted(Path(directory).iterdir())
            _ = M.dry_run()
            self.assertEqual(before, sorted(Path(directory).iterdir()))


if __name__ == "__main__":
    unittest.main()
