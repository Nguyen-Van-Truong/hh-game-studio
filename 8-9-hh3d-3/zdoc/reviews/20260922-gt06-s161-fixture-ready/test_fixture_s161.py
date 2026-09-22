import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent

class S161FixtureTests(unittest.TestCase):
    def test_source_emits_ready_before_open(self):
        source = (ROOT / "native_fixture_s161.cs").read_text(encoding="utf-8")
        self.assertLess(source.index('\\"handles_opened\\":false'), source.index('command.Equals("open"'))
        self.assertIn('observer_attach_before_open', source)
    def test_receipt_is_lifecycle_only(self):
        receipt = json.loads((ROOT / "s161-native-fixture-run.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["actual_exit"], 0)
        self.assertFalse(receipt["debugger_attached"])
        self.assertFalse(receipt["eligible_for_dataset"])
    def test_manifest_binds_receipt(self):
        manifest = json.loads((ROOT / "s161-native-fixture-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["actual_exit"], 0)
        self.assertIn("s161-native-fixture-run.json", manifest["files"])

if __name__ == "__main__":
    unittest.main()
