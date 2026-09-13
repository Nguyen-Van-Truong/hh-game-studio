import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("evidence_binder", HERE / "evidence_binder.py")
mod = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(mod)


class BinderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.pack = Path(self.tmp.name) / "pack"
        self.root.mkdir(); self.pack.mkdir()
        source = self.root / "fixture.txt"; source.write_text("frozen\n", encoding="utf-8")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        self.manifest = self.pack / "manifest.json"
        self.manifest.write_text(json.dumps({"status": "FROZEN", "gaps": [], "required_files": [{"path": "fixture.txt", "sha256": digest, "required": True, "exists": True, "regular": True, "symlink": False, "reparse": False, "hard_links": 1}]}), encoding="utf-8")
        for name, text in (("out.txt", "GT01_TRACE ok\n"), ("err.txt", "")):
            (self.pack / name).write_text(text, encoding="utf-8")
        hashes = {name: hashlib.sha256((self.pack / name).read_bytes()).hexdigest() for name in ("out.txt", "err.txt")}
        trace = {"observations": [{"label": x} for x in ("menu", "start", "moved", "paused_frozen", "resumed", "quitting")], "phase": "QUITTING", "result": "PASS"}
        self.evidence = {"status": "OFFICIAL", "run_id": "R1", "command_id": "C1", "source_manifest": {"fixture.txt": digest}, "checks": {"trace": True}, "runs": [{"wrapper_pid": 11, "target_pid": 12, "started_at": "2026-09-15T00:00:00Z", "argv": ["godot", "--headless"], "exit_code": 0, "wrapper_exit_code": 0, "timed_out": False, "tree_verified": True, "ownership": "gated_job_kill_on_close", "stdout": "out.txt", "stderr": "err.txt"}], "log_hashes": hashes, "trace_lines": ["GT01_TRACE " + json.dumps(trace, separators=(",", ":"))]}
        self.evidence_path = self.pack / "evidence.json"
        self._write()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self):
        self.evidence_path.write_text(json.dumps(self.evidence), encoding="utf-8")

    def _bind(self):
        return mod.bind(self.manifest, self.evidence_path, self.root)

    def test_valid_binds_computed_hash(self):
        result = self._bind()
        self.assertEqual(result["status"], "READY_FOR_CRITIC")
        expected = mod.closure_sha256({"fixture.txt": self.evidence["source_manifest"]["fixture.txt"]})
        self.assertEqual(result["source_closure_sha256"], expected)

    def test_candidate_rejected_even_if_all_checks_true(self):
        self.evidence["status"] = "CANDIDATE"; self._write()
        self.assertEqual(self._bind()["status"], "GAP")

    def test_source_mutation_rejected(self):
        (self.root / "fixture.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(self._bind()["status"], "GAP")

    def test_log_mutation_rejected(self):
        (self.pack / "out.txt").write_text("changed\n", encoding="utf-8")
        self.assertEqual(self._bind()["status"], "GAP")

    def test_exit_and_tree_are_fail_closed(self):
        self.evidence["runs"][0]["exit_code"] = 1; self._write()
        self.assertEqual(self._bind()["status"], "GAP")
        self.evidence["runs"][0]["exit_code"] = 0; self.evidence["runs"][0]["tree_verified"] = False; self._write()
        self.assertEqual(self._bind()["status"], "GAP")

    def test_duplicate_or_wrong_trace_rejected(self):
        self.evidence["trace_lines"] = self.evidence["trace_lines"] * 2; self._write()
        self.assertEqual(self._bind()["status"], "GAP")

    def test_warning_rejected(self):
        (self.pack / "err.txt").write_text("WARNING: noisy\n", encoding="utf-8")
        self.evidence["log_hashes"]["err.txt"] = hashlib.sha256((self.pack / "err.txt").read_bytes()).hexdigest(); self._write()
        self.assertEqual(self._bind()["status"], "GAP")

    def test_runner_hash_is_not_trusted(self):
        self.evidence["source_closure_sha256"] = "0" * 64; self._write()
        self.assertEqual(self._bind()["status"], "READY_FOR_CRITIC")


if __name__ == "__main__":
    unittest.main()
