"""Notification gate checks; no workers, engines or notifications are launched."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("watch_workers", Path(__file__).with_name("watch_workers.py"))
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)


class CompletionGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.report = self.root / "REPORT.md"
        self.report.write_text("Finished; reviewer required.", encoding="utf-8")
        self.worker = {"attempt": str(self.root), "workspace": str(self.root), "report_relative": "REPORT.md",
                       "session_id": "fixture", "pid": 123, "process_start_utc": "2026-09-22T05:03:07Z", "lane": "schema"}
        self.start = {"session_id": "fixture", "pid": 123, "start_utc": self.worker["process_start_utc"],
                      "model_requested": "grok-4.7-xhigh", "workspace": str(self.root)}
        self.marker = {"lane": "s157-schema", "report": "REPORT.md", "report_sha256": watch.digest(self.report),
                       "verdict": "PASS_NO_ACCEPTANCE", "acceptance_claim": False}
        self.terminal = {"session_id": "fixture", "report": str(self.report), "report_sha256": watch.digest(self.report),
                         "cli_exit": 0, "ended_utc": "2026-09-22T05:10:00Z", "formal_acceptance": False}
        self.save()

    def save(self):
        for name, obj in [("wrapper-start.json", self.start), ("dispatch.json", self.start),
                          ("completion.json", self.marker), ("terminal.json", self.terminal)]:
            watch.write(self.root / name, obj)
        (self.root / "exit.txt").write_text(str(self.terminal["cli_exit"]), encoding="utf-8")

    def test_complete_means_review_not_acceptance(self):
        result = watch.validate_result(self.worker)
        self.assertEqual("NEEDS_REVIEW", result["state"])
        self.assertFalse(result["formal_acceptance"])

    def test_process_exit_without_report_is_incomplete(self):
        self.report.unlink()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_report_without_marker_is_incomplete(self):
        (self.root / "completion.json").unlink()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_hash_only_marker_binds_exact_wrapper_and_registry_report(self):
        del self.marker["report"]
        self.save()
        result = watch.validate_result(self.worker)
        self.assertEqual("NEEDS_REVIEW", result["state"])
        self.assertEqual("registry_and_wrapper", result["marker_report_path_source"])
        self.terminal["report"] = str(self.root / "other.md")
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_report_changed_after_final_is_rejected(self):
        self.report.write_text("Later write", encoding="utf-8")
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_wrong_session_or_pid_or_start_is_rejected(self):
        for key, value in [("session_id", "other"), ("pid", 124), ("start_utc", "2026-09-22T05:03:08Z")]:
            with self.subTest(key=key):
                original = copy.deepcopy(self.start)
                self.start[key] = value
                self.save()
                self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])
                self.start = original

    def test_wrong_model_or_lane_or_path_is_rejected(self):
        self.start["model_requested"] = "grok-4.7-xhigh-fast"
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])
        self.start["model_requested"] = "grok-4.7-xhigh"
        self.marker["lane"] = "other"
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])
        self.marker["lane"] = "s157-schema"
        self.marker["report"] = "../other.md"
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_missing_or_conflicting_exit_is_rejected(self):
        (self.root / "exit.txt").write_text("1", encoding="utf-8")
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])
        (self.root / "exit.txt").unlink()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])

    def test_failed_cli_retains_worker_verdict_without_success(self):
        self.terminal["cli_exit"] = 1
        self.save()
        result = watch.validate_result(self.worker)
        self.assertEqual("WORKER_FAILED", result["state"])
        self.assertFalse(result["formal_acceptance"])

    def test_stale_terminal_and_acceptance_claim_are_rejected(self):
        self.terminal["ended_utc"] = "2026-09-21T05:00:00Z"
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])
        self.terminal["ended_utc"] = "2026-09-22T05:10:00Z"
        self.marker["acceptance_claim"] = True
        self.save()
        self.assertEqual("INCOMPLETE", watch.validate_result(self.worker)["state"])


if __name__ == "__main__":
    unittest.main()
