import unittest

from studio.tests.replay import run_journal_microbench as microbench


class JournalMicrobenchContractTests(unittest.TestCase):
    def test_full_schedule_matches_o1_4_windows(self):
        marks = microbench.mark_schedule(microbench.FULL_COMMANDS,
                                         microbench.DEFAULT_MARK)
        self.assertEqual(marks[2:5], microbench.O14_BASELINE_COMMANDS)
        self.assertEqual(marks[5:], microbench.O14_MAIN_COMMANDS)
        self.assertEqual(len(marks), 35)

    def test_short_schedule_is_explicitly_diagnostic(self):
        self.assertEqual(microbench.mark_schedule(100, 10), tuple(range(10, 101, 10)))

    def test_o1_4_uses_late_window_in_main_max(self):
        commands = range(1000, 35001, 1000)
        marks = [{"commands": command,
                  "private_bytes": {"value": 100 if command <= 5000 else
                                     (200 if command == 35000 else 110)}}
                 for command in commands]
        result = microbench._o1_4(marks)
        self.assertEqual(result["main_max_bytes"], 200)
        self.assertEqual(result["main_over_baseline_percent"], 200.0)
        self.assertAlmostEqual(result['late_over_early_percent'], 200 * 100 / 110)
        self.assertEqual(result['gate_codes'], ['PRIVATE_COMMIT_GROWTH', 'PRIVATE_COMMIT_TREND'])

    def test_incomplete_series_cannot_claim_gate(self):
        marks = [{'commands': n, 'private_bytes': {'value': 100}}
                 for n in range(1000, 35001, 1000)]
        self.assertEqual(microbench._o1_4(marks)['gate_codes'], [])
        self.assertIsNone(microbench._o1_4(marks[:-1])['gate_codes'])
        marks[5]['private_bytes']['value'] = None
        self.assertFalse(microbench._o1_4(marks)['available'])

    def test_source_closure_includes_protocol_sources(self):
        files = microbench.source_files()
        self.assertTrue(any(name.startswith("protocol/") for name in files))
        self.assertIn("tests/replay/run_journal_microbench.py", files)


if __name__ == "__main__":
    unittest.main()
