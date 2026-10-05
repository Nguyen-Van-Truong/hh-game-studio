"""O1 replay of SHA-bound numeric extracts from retained partial campaigns.

PASS below means only available historical measurements fit O1 bounds.
No missing private counter is synthesized, no prefix is padded, and no old
campaign receives a new formal verdict. Full validation remains strict.
"""
from pathlib import Path
import hashlib
import json
import sys
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import benchmark_profile as profile

REVIEWS = STUDIO / '.local' / 'reviews'
FIXTURE = Path(__file__).parent / 'fixtures/o1-historical-counters.json'


def replay(rows):
    failures, unassessed = [], []
    for role in ('host', 'editor'):
        for counter in profile._COUNTERS:
            if role == 'host' and counter in ('objects', 'resources'):
                continue
            if not all(counter in row['counters'][role] for row in rows):
                unassessed.append((role, counter))
                continue
            baseline = sorted(row['counters'][role][counter] for row in rows if 2 <= row['index'] <= 4)[1]
            measured = [row for row in rows if 5 <= row['index'] <= 34]
            early = [row['counters'][role][counter] for row in measured if row['index'] <= 19]
            late = [row['counters'][role][counter] for row in measured if row['index'] >= 20]
            codes = profile.memory_gate_codes(role, counter, baseline,
                max(row['counters'][role][counter] for row in measured), max(early), max(late) if late else None)
            failures.extend((role, counter, code) for code in codes)
    if max(row['max_status_gap_ms'] for row in rows) > profile.PROFILE.max_status_gap_ms:
        failures.append(('both', 'status', 'STATUS_UPDATE_GAP'))
    return failures, unassessed


class O1HistoricalSeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_bytes())

    def check_packet(self, label, count):
        packet = self.fixture['cases'][label]
        rows = packet['rows']
        self.assertFalse(self.fixture['formal_acceptance'])
        self.assertEqual([row['index'] for row in rows], list(range(count)))
        self.assertTrue(all(row['phase'] == profile.PROFILE.quiescent_phase for row in rows))
        failures, unassessed = replay(rows)
        self.assertEqual('FAIL' if failures else 'PASS', packet['expected_available_checks'])
        self.assertEqual(unassessed, [('host', 'private_commit_bytes'), ('editor', 'private_commit_bytes')])
        self.assertFalse(any(row['index'] >= 20 for row in rows), 'late-window evidence must not be invented')
        if label == 's241':
            self.assertEqual(failures, [('both', 'status', 'STATUS_UPDATE_GAP')])
            self.assertAlmostEqual(self.fixture['s241_command']['max_status_gap_ms'], 2055.5275)
            self.assertGreater(self.fixture['s241_command']['max_status_gap_ms'], profile.PROFILE.max_status_gap_ms)

    def test_s218_rss_spike_is_report_only(self):
        self.check_packet('s218', 6)
        rows = self.fixture['cases']['s218']['rows']
        self.assertTrue(any(rows[5]['counters'][role]['rss_bytes'] > rows[4]['counters'][role]['rss_bytes'] * 1.1
                            for role in ('host', 'editor')))

    def test_s229_object_increment(self):
        self.check_packet('s229', 17)
        rows = self.fixture['cases']['s229']['rows']
        self.assertEqual(rows[-1]['counters']['editor']['objects'] - rows[4]['counters']['editor']['objects'], 2)

    def test_s232_handle_increment(self):
        self.check_packet('s232', 9)

    def test_s236_handle_decrease(self):
        self.check_packet('s236', 9)

    def test_s241_status_gap_still_fails(self):
        self.check_packet('s241', 17)

    def test_s246_handle_noise(self):
        self.check_packet('s246', 8)
        self.assertEqual([row['counters']['editor']['held_handles'] for row in self.fixture['cases']['s246']['rows'][5:]],
                         [558, 556, 559])

    def test_numeric_extracts_match_available_immutable_raw(self):
        checked = 0
        for packet in self.fixture['cases'].values():
            for row in packet['rows']:
                path = REVIEWS / row['source']
                if not path.exists():
                    continue
                raw = path.read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'], row['source'])
                sample = json.loads(raw)
                self.assertEqual(sample['index'], row['index'])
                self.assertEqual(sample['max_status_gap_ms'], row['max_status_gap_ms'])
                self.assertEqual({role: {key: item['value'] for key, item in sample['memory'][role].items()}
                                  for role in ('host', 'editor')}, row['counters'])
                checked += 1
        if checked == 0:
            self.skipTest('ignored raw not installed; six portable regression cases still execute')
        else:
            self.assertEqual(checked, 66, 'local historical replay requires every retained sample')
        command = self.fixture['s241_command']
        path = REVIEWS / command['source']
        if path.exists():
            raw = path.read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), command['sha256'])
            self.assertEqual(json.loads(raw)['max_status_gap_ms'], command['max_status_gap_ms'])


if __name__ == '__main__':
    unittest.main()
