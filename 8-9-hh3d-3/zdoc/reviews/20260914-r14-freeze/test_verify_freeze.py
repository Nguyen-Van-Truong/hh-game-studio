from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("verify_freeze.py")
spec = importlib.util.spec_from_file_location("freeze_verifier", MODULE)
verifier = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(verifier)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FreezeVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="gt01-freeze-")
        self.root = Path(self.tmp.name)
        (self.root / "studio").mkdir()
        self.source = self.root / "studio" / "source.txt"
        self.source.write_text("immutable\n", encoding="utf-8")
        self.logs = self.root / "evidence"
        self.logs.mkdir()
        for name, content in (("stdout.txt", "Godot Engine\n"), ("stderr.txt", "")):
            (self.logs / name).write_text(content, encoding="utf-8")
        rel = "studio/source.txt"
        self.records = {rel: digest(self.source)}
        self.manifest = {
            "status": "CANDIDATE",
            "gaps": [],
            "required_files": [{"path": rel, "required": True, "exists": True, "regular": True,
                                 "symlink": False, "reparse": False, "hard_links": 1,
                                 "sha256": self.records[rel]}],
        }
        self.evidence = {
            "status": "OFFICIAL",
            "source_closure_sha256": verifier.closure_hash(self.records),
            "source_manifest": self.records.copy(),
            "checks": {"trace_exactly_one_pass": True, "streams_clean": True,
                       "process_tree_verified": True},
            "trace_lines": ['GT01_TRACE {"result":"PASS"}'],
            "runs": [{"exit_code": 0, "wrapper_exit_code": 0, "timed_out": False,
                       "tree_verified": True, "ownership": "gated_job_kill_on_close",
                       "stdout": "stdout.txt", "stderr": "stderr.txt"}],
            "log_hashes": {"stdout.txt": digest(self.logs / "stdout.txt"),
                           "stderr.txt": digest(self.logs / "stderr.txt")},
        }
        self.manifest_path = self.root / "manifest.json"
        self.evidence_path = self.logs / "evidence.json"
        self.write()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self):
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.evidence_path.write_text(json.dumps(self.evidence), encoding="utf-8")

    def verify_package(self):
        return verifier.verify(self.manifest_path, self.evidence_path, self.root)

    def test_valid_package(self):
        self.assertEqual(self.verify_package()["status"], "READY_FOR_CRITIC")

    def test_candidate_runtime_rejected(self):
        self.evidence["status"] = "CANDIDATE"
        self.write()
        result = self.verify_package()
        self.assertEqual(result["status"], "GAP")
        self.assertIn("official/accepted", result["failures"][0])

    def test_source_mutation_rejected(self):
        self.source.write_text("mutated\n", encoding="utf-8")
        result = self.verify_package()
        self.assertEqual(result["status"], "GAP")
        self.assertIn("source hash mismatch", result["failures"][0])

    def test_stale_log_rejected(self):
        (self.logs / "stdout.txt").write_text("changed\n", encoding="utf-8")
        result = self.verify_package()
        self.assertEqual(result["status"], "GAP")
        self.assertIn("stale or unbound", result["failures"][0])

    def test_warning_and_unverified_tree_rejected(self):
        self.evidence["runs"][0]["tree_verified"] = False
        self.write()
        result = self.verify_package()
        self.assertEqual(result["status"], "GAP")
        self.assertIn("unverified process", result["failures"][0])

    def test_duplicate_json_key_rejected(self):
        self.evidence_path.write_text('{"status":"OFFICIAL","status":"CANDIDATE"}', encoding="utf-8")
        result = self.verify_package()
        self.assertEqual(result["status"], "GAP")
        self.assertIn("invalid JSON", result["failures"][0])


if __name__ == "__main__":
    unittest.main()
