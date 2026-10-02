import json
from pathlib import Path
import tempfile
import unittest

from studio.tests.replay.review_formal21_gap import review


class Formal21GapReviewTests(unittest.TestCase):
    def test_reports_largest_monotonic_gap_without_claiming_cause(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command-00.json"
            path.write_text(json.dumps({
                "commands": [{
                    "command_id": "run.admitted.153",
                    "lookup_attempts": [
                        {"ended_mono_us": 100, "status": "ACCEPTED_PENDING", "code": "QUEUED", "transport_failure": None},
                        {"ended_mono_us": 150, "status": "ACCEPTED_PENDING", "code": "QUEUED", "transport_failure": None},
                        {"ended_mono_us": 2_700, "status": "COMMITTED", "code": "READBACK_CONFIRMED", "transport_failure": None},
                    ],
                }]
            }), encoding="utf-8")
            result = review(path)
        self.assertEqual(result["largest_gap"]["gap_us"], 2_550)
        self.assertFalse(result["formal_acceptance"])
        self.assertFalse(result["root_cause_proven"])
        self.assertFalse(result["transport_failure_in_gap"])

    def test_ignores_other_command_suffixes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "command-00.json"
            path.write_text(json.dumps({
                "commands": [{"command_id": "run.admitted.152", "lookup_attempts": [
                    {"ended_mono_us": 1}, {"ended_mono_us": 2}
                ]}]
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "GAP_CANDIDATE_MISSING"):
                review(path)


if __name__ == "__main__":
    unittest.main()
