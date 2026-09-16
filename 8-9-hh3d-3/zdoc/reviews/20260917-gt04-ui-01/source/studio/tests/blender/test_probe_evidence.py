import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("gt04_runner_test", Path(__file__).with_name("run_blender_probe.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    report = {"schema": "HH-GT04-NATIVE-PROBE-1", "phase": "reopen", "actual_blender": True,
              "version": "5.2.1 LTS", "ok": True, "public_ack": False, "acceptance": False,
              "checks": [{"label": label, "passed": True} for label in runner.REQUIRED["reopen"]]}
    return report


def log(report):
    return "\n".join(["GT04_CHECK " + json.dumps(row) for row in report["checks"]] + ["GT04_RESULT " + json.dumps(report)])


class EvidenceTests(unittest.TestCase):
    def test_complete_synthetic_report(self):
        report = fixture()
        runner.evaluate("reopen", report, log(report))

    def test_wrong_native_phase_and_flags(self):
        for key, value in (("actual_blender", False), ("phase", "edit"), ("ok", False), ("version", "5.2.0"), ("public_ack", True)):
            report = fixture()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.evaluate("reopen", report, log(report))

    def test_missing_duplicate_false_checks(self):
        for action in (lambda rows: rows.pop(), lambda rows: rows.append(rows[0]), lambda rows: rows[0].update(passed=False)):
            report = fixture()
            action(report["checks"])
            with self.assertRaises(ValueError):
                runner.evaluate("reopen", report, log(report))

    def test_raw_log_mismatch_or_diagnostic(self):
        report = fixture()
        raw = log(report)
        for broken in (raw.replace("GT04_CHECK ", "NOT_A_CHECK ", 1), raw + "\nGT04_RESULT " + json.dumps(report), raw + "\nWarning: bad\n"):
            with self.assertRaises(ValueError):
                runner.evaluate("reopen", report, broken)


if __name__ == "__main__":
    unittest.main()
