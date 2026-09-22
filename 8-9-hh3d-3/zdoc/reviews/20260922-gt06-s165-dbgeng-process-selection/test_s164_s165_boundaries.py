import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
S164 = ROOT / "20260922-gt06-s164-dbgeng-index-repair"
S165 = ROOT / "20260922-gt06-s165-dbgeng-process-selection"


class InvalidDbgEngBoundaryTests(unittest.TestCase):
    def _load(self, folder: Path, name: str):
        with (folder / name).open(encoding="utf-8") as stream:
            return json.load(stream)

    def test_both_packets_are_diagnostic_only(self):
        for folder, name in (
            (S164, "s164-debugger-attribution-attempt.json"),
            (S165, "s165-debugger-attribution-attempt.json"),
        ):
            packet = self._load(folder, name)
            self.assertEqual(packet["authority"], 0)
            self.assertFalse(packet["formal_acceptance"])
            self.assertFalse(packet["eligible_for_dataset"])
            self.assertFalse(packet["engine_started"])
            self.assertFalse(packet["debugger_attached"])
            self.assertFalse(packet["attribution_proven"])
            self.assertFalse(packet["auto_retry"])
            self.assertEqual(packet["harness_compile_exit"], 0)
            self.assertEqual(packet["harness_actual_exit"], 1)

    def test_index_repair_is_rejected_by_complete_sdk_count(self):
        for folder, name in (
            (S164, "s164-debugger-attribution-attempt.json"),
            (S165, "s165-debugger-attribution-attempt.json"),
        ):
            packet = self._load(folder, name)
            self.assertEqual(packet["wait_for_event_index_used"], 90)
            self.assertEqual(packet["execute_index_used"], 63)
            self.assertEqual(packet["authoritative_wait_for_event_index"], 93)
            self.assertEqual(packet["authoritative_execute_index"], 66)

    def test_no_fixture_output_was_created(self):
        for folder, name in (
            (S164, "s164-debugger-attribution-attempt.json"),
            (S165, "s165-debugger-attribution-attempt.json"),
        ):
            packet = self._load(folder, name)
            self.assertFalse(packet["fixture_output_created"])


if __name__ == "__main__":
    unittest.main()
