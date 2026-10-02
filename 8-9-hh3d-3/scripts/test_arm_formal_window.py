import unittest
from datetime import datetime, timedelta, timezone
from arm_formal_window import PROFILE, decision


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 10, 2, 3, tzinfo=timezone.utc)
        self.config = {'start': self.at.isoformat(), 'end': (self.at + timedelta(hours=4)).isoformat(), 'source': 'frozen'}
        self.observation = {'source': 'frozen', 'profile': PROFILE, **dict.fromkeys(
            ('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'), True)}

    def test_ready_and_last_start(self):
        self.assertEqual(decision(self.config, self.observation, self.at), 'DISPATCH')
        self.assertEqual(decision(self.config, self.observation, self.at + timedelta(minutes=30)), 'DISPATCH')
        self.assertEqual(decision(self.config, self.observation, self.at + timedelta(minutes=30, seconds=1)), 'TOO_LATE')

    def test_before_window(self):
        self.assertEqual(decision(self.config, self.observation, self.at - timedelta(seconds=1)), 'BEFORE_WINDOW')

    def test_short_window(self):
        self.config['end'] = (self.at + timedelta(hours=3)).isoformat()
        self.assertEqual(decision(self.config, self.observation, self.at), 'WINDOW_TOO_SHORT')

    def test_required_observations_fail_closed(self):
        for key in ('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'):
            for value in (False, None, 1):
                with self.subTest(key=key, value=value):
                    self.assertEqual(decision(self.config, {**self.observation, key: value}, self.at), key.upper() + '_NOT_PASS')

    def test_changed_source_or_profile(self):
        for key in ('source', 'profile'):
            self.assertEqual(decision(self.config, {**self.observation, key: 'changed'}, self.at), 'SOURCE_OR_PROFILE_CHANGED')


if __name__ == '__main__':
    unittest.main()
