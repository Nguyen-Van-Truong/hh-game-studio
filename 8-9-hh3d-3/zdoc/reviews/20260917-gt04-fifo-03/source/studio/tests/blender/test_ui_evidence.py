import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("gt04_ui_runner_test", Path(__file__).with_name("run_blender_ui_probe.py"))
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def fixture():
    return {"schema": "HH-GT04-UI-PROBE-1", "phase": "reopen", "actual_blender_gui": True,
            "version": "5.2.1 LTS", "ok": True, "public_ack": False, "acceptance": False,
            "checks": [{"label": label, "passed": True} for label in runner.REQUIRED["reopen"]]}


def log(report):
    return "\n".join(["GT04_UI_CHECK " + json.dumps(row) for row in report["checks"]] + ["GT04_UI_RESULT " + json.dumps(report)])


class UIEvidenceTests(unittest.TestCase):
    def test_synthetic_complete(self):
        report = fixture()
        runner.evaluate("reopen", report, log(report))

    def test_wrong_flags(self):
        for key, value in (("actual_blender_gui", False), ("ok", False), ("public_ack", True), ("acceptance", True), ("phase", "edit")):
            report = fixture()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner.evaluate("reopen", report, log(report))

    def test_missing_duplicate_false_rows(self):
        for action in (lambda rows: rows.pop(), lambda rows: rows.append(rows[0]), lambda rows: rows[0].update(passed=False)):
            report = fixture()
            action(report["checks"])
            with self.assertRaises(ValueError):
                runner.evaluate("reopen", report, log(report))

    def test_raw_mismatch_and_diagnostic(self):
        report = fixture()
        raw = log(report)
        for value in (raw.replace("GT04_UI_CHECK ", "OTHER ", 1), raw + "\nGT04_UI_RESULT " + json.dumps(report), raw + "\nWarning: bad"):
            with self.assertRaises(ValueError):
                runner.evaluate("reopen", report, value)


if __name__ == "__main__":
    unittest.main()
