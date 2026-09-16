"""Tamper copies only; no engine process or changes to captured evidence."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("gt04_readonly_auditor", Path(__file__).with_name("verify_probe.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-gt04-audit-")
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "capture"
        shutil.copytree(audit.PACKAGE, self.package)

    def write_json(self, relative, value):
        (self.package / relative).write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def reindex(self):
        report = audit.read_json(self.package / "result.json")
        report["artifacts"] = audit.inventory(self.package)
        self.write_json("result.json", report)

    def mutate_native(self, phase, mutate):
        relative = "fixture/" + phase + "-result.json"
        value = audit.read_json(self.package / relative)
        mutate(value)
        self.write_json(relative, value)
        log_path = self.package / (phase + "-stdout.txt")
        raw = log_path.read_text(encoding="utf-8")
        checks = iter(value["checks"])
        lines = []
        for line in raw.splitlines():
            if line.startswith("GT04_CHECK "):
                line = "GT04_CHECK " + json.dumps(next(checks))
            elif line.startswith("GT04_RESULT "):
                line = "GT04_RESULT " + json.dumps(value)
            lines.append(line)
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.reindex()

    def test_actual_complete_package(self):
        result = audit.verify(self.package)
        self.assertTrue(result["ok"])
        self.assertFalse(result["acceptance"])
        self.assertEqual(result["artifact_count"], 28)

    def test_host_exit_cannot_be_replaced_by_summary_pass(self):
        host = audit.read_json(self.package / "reopen-host.json")
        host["exit_code"] = 17
        self.write_json("reopen-host.json", host)
        self.reindex()
        with self.assertRaisesRegex(ValueError, "actual process exit"):
            audit.verify(self.package)

    def test_boolean_is_not_native_exit_integer(self):
        report = audit.read_json(self.package / "result.json")
        report["runs"][0]["wrapper_exit_code"] = False
        self.write_json("result.json", report)
        with self.assertRaisesRegex(ValueError, "integer types"):
            audit.verify(self.package)

    def test_one_is_not_true_even_when_both_logs_match(self):
        self.mutate_native("edit", lambda value: value["checks"][0].update(passed=1))
        with self.assertRaisesRegex(ValueError, "check type"):
            audit.verify(self.package)

    def test_checkpoint_readback_cannot_be_relabelled_saved_scene(self):
        self.mutate_native("checkpoint", lambda value: value["result"].update(revision=audit.REVISION))
        with self.assertRaisesRegex(ValueError, "checkpoint readback"):
            audit.verify(self.package)

    def test_duplicate_raw_terminal_marker(self):
        log_path = self.package / "reopen-stdout.txt"
        raw = log_path.read_text(encoding="utf-8")
        terminal = next(line for line in raw.splitlines() if line.startswith("GT04_RESULT "))
        log_path.write_text(raw + "\n" + terminal + "\n", encoding="utf-8")
        self.reindex()
        with self.assertRaisesRegex(ValueError, "raw final mismatch"):
            audit.verify(self.package)

    def test_changed_source_after_inventory_rehash(self):
        path = self.package / "source/studio/blender-addon/adapter.py"
        path.write_bytes(path.read_bytes() + b"\n# drift\n")
        self.reindex()
        with self.assertRaisesRegex(ValueError, "source bytes drift"):
            audit.verify(self.package)

    def test_changed_saved_file_after_inventory_rehash(self):
        path = self.package / "fixture/fixture.blend"
        raw = path.read_bytes()
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        self.reindex()
        with self.assertRaisesRegex(ValueError, "saved/checkpoint bytes"):
            audit.verify(self.package)

    def test_unlisted_artifact_rejected(self):
        (self.package / "unlisted.txt").write_text("extra", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory/hash"):
            audit.verify(self.package)

    def test_extra_artifact_cannot_be_blessed_by_inventory(self):
        (self.package / "unlisted.txt").write_text("extra", encoding="utf-8")
        self.reindex()
        with self.assertRaisesRegex(ValueError, "membership"):
            audit.verify(self.package)


if __name__ == "__main__":
    unittest.main()
