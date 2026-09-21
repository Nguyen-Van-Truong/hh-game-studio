"""No engine/HTTP: original gates and retained process binding fail closed."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('s149', Path(__file__).with_name('host_handles.py'))
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def counters(rss=1000, handles=204):
    return {'counters': {'rss_bytes': {'value': rss}, 'held_handles': {'value': handles}}}


class Checks(unittest.TestCase):
    def test_baseline_not_applied_to_warmup(self):
        subject.screen(counters(100000, 999), None, 2500, 4)

    def test_exact_limits_retained(self):
        subject.screen(counters(1100, 204), counters(), 2000, 5)

    def test_single_handle_growth_rejected(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'CAMPAIGN_RETAINED_COUNTER_GROWTH'):
            subject.screen(counters(900, 205), counters(), 100, 10)

    def test_rss_growth_rejected(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'CAMPAIGN_RSS_GROWTH'):
            subject.screen(counters(1101), counters(), 100, 5)

    def test_status_gap_rejected(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'CAMPAIGN_STATUS_GAP'):
            subject.screen(counters(), counters(), 2000.001, 5)

    def test_missing_counter_rejected_even_warmup(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'CAMPAIGN_COUNTER_UNAVAILABLE'):
            subject.screen(counters(handles=None), None, 100, 0)

    def test_owned_identity_matches(self):
        subject.bind_identity(SimpleNamespace(pid=10, process_start='windows:123'),
            {'pid': 10}, {'process': {'pid': 10, 'process_start': 'windows:123'}})

    def test_pid_reuse_rejected(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'S149_START_BINDING'):
            subject.bind_identity(SimpleNamespace(pid=10, process_start='windows:456'),
                {'pid': 10}, {'process': {'pid': 10, 'process_start': 'windows:123'}})

    def test_foreign_pid_rejected(self):
        with self.assertRaisesRegex(subject.job.BenchmarkJobError, 'S149_PID_BINDING'):
            subject.bind_identity(SimpleNamespace(pid=11, process_start='windows:123'),
                {'pid': 10}, {'process': {'pid': 11, 'process_start': 'windows:123'}})

    def test_fresh_smoke_and_work_ids_are_distinct(self):
        self.assertNotEqual(subject.paths(True), subject.paths(False))


if __name__ == '__main__':
    unittest.main(verbosity=2)
