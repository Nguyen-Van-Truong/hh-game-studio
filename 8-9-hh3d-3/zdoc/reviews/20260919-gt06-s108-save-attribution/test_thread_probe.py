"""Pure injected-API checks; never open a process, window, thread or engine."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import thread_probe as p

EXPECTED = {'pid': 123, 'process_start': 'windows:100', 'executable': r'C:\pinned\Godot.exe'}


class Clock:
    def __init__(self):
        self.now = 1_000_000_000

    def __call__(self):
        self.now += 1000
        return self.now

    def advance(self):
        self.now += p.INTERVAL_NS


class Process:
    def __init__(self):
        self.pid, self.process_start, self.handle = 123, 'windows:100', 900
        self.close_uncertain, self.ended, self.calls, self.mutate = False, False, 0, None

    def sample(self):
        self.calls += 1
        if self.mutate:
            self.mutate(self)
        return None if self.ended else {'host_mono_us': 10, 'rss_bytes': 1024,
                                      'visible_window_handles': ['555']}


class API:
    def __init__(self):
        self.process = dict(EXPECTED)
        self.window = (123, 456)
        self.windows = [{'hwnd': 555, 'pid': 123, 'tid': 456},
                        {'hwnd': 556, 'pid': 123, 'tid': 456}]
        self.thread = (123, 456)
        self.times = {'created_100ns': 101, 'kernel_100ns': 1000, 'user_100ns': 2000}
        self.exit_code, self.opened, self.closed = p.STILL_ACTIVE, [], []
        self.wait_result = None
        self.close_result, self.close_error, self.open_effect = True, None, None
        self.times_error = None

    def process_identity(self, handle):
        assert handle == 900
        return dict(self.process)

    def window_identity(self, hwnd):
        assert hwnd == 555
        return self.window

    def owned_windows(self, pid):
        assert pid == 123
        return copy.deepcopy(self.windows)

    def open_thread(self, tid):
        self.opened.append(tid)
        if self.open_effect:
            self.open_effect(self)
        return 999

    def thread_identity(self, handle):
        assert handle == 999
        return self.thread

    def thread_exit(self, handle):
        assert handle == 999
        return self.exit_code

    def thread_wait(self, handle):
        assert handle == 999
        if self.wait_result is not None:
            return self.wait_result
        return 258 if self.exit_code == p.STILL_ACTIVE else 0

    def thread_times(self, handle):
        assert handle == 999
        if self.times_error:
            raise self.times_error
        return dict(self.times)

    def close_thread(self, handle):
        self.closed.append(handle)
        if self.close_error:
            raise self.close_error
        return self.close_result

    def last_error(self):
        return 5


class Tests(unittest.TestCase):
    def setUp(self):
        self.clock, self.api, self.process = Clock(), API(), Process()

    def tearDown(self):
        # Injected handles only. Uncertain closes are deliberately not retried.
        p.HELD_PROBES.clear()

    def make(self, **kw):
        return p.ThreadProbe(self.process, EXPECTED, 555, api=self.api, clock_ns=self.clock, **kw)

    def fails(self, code, function):
        with self.assertRaises(p.ThreadProbeError) as captured:
            function()
        self.assertEqual(captured.exception.code, code)
        return captured.exception

    def test_valid_identity_cadence_samples_and_close(self):
        probe = self.make()
        self.assertEqual(probe.identity['tid'], 456)
        self.assertEqual(probe.identity['thread_created_100ns'], 101)
        self.assertEqual(probe.identity['owned_window_handles'], [555, 556])
        self.assertEqual(probe.identity['query_access'], 0x100800)
        row = probe.sample(5)
        self.assertEqual(row['index'], 0)
        self.assertLessEqual(row['sample_started_perf_ns'], row['host_before_ns'])
        self.assertLessEqual(row['host_before_ns'], row['host_after_ns'])
        self.assertLessEqual(row['host_after_ns'], row['sample_ended_perf_ns'])
        self.assertEqual(row['times_api_duration_ns'], row['host_after_ns'] - row['host_before_ns'])
        self.assertEqual(row['kernel_100ns'], 1000)
        self.assertIs(row['formal_acceptance'], False)
        self.assertIsNone(probe.sample(5))
        self.clock.advance()
        self.api.times['user_100ns'] += 100
        self.assertEqual(probe.sample(6)['index'], 1)
        receipt = probe.close()
        self.assertEqual(receipt['status'], 'CLOSED')
        self.assertIs(receipt['native_close_result'], True)
        self.assertEqual(probe.close(), receipt)
        self.assertEqual(self.api.closed, [999])
        self.assertEqual(p.HELD_PROBES, [])

    def test_process_reuse_and_binary_mismatch_before_open(self):
        for key, value in [('pid', 124), ('process_start', 'windows:101'),
                           ('executable', r'C:\other\Godot.exe')]:
            with self.subTest(key=key):
                self.api.process = {**EXPECTED, key: value}
                self.fails('S108_PROCESS_IDENTITY', self.make)
                self.assertEqual(self.api.opened, [])

    def test_announced_window_wrong_owner_missing_or_multiple_gui_threads(self):
        self.api.window = (124, 456)
        self.fails('S108_WINDOW_PROCESS_BINDING', self.make)
        self.api.window = (123, 456)
        self.api.windows = [{'hwnd': 556, 'pid': 123, 'tid': 456}]
        self.fails('S108_ANNOUNCED_WINDOW_MISSING', self.make)
        self.api.windows.append({'hwnd': 555, 'pid': 123, 'tid': 457})
        self.fails('S108_AMBIGUOUS_GUI_THREAD', self.make)
        self.assertEqual(self.api.opened, [])

    def test_open_thread_identity_and_window_races_close_owned_handle(self):
        for field, value, code in [('thread', (124, 456), 'S108_THREAD_IDENTITY'),
                                    ('window', (123, 457), 'S108_WINDOW_IDENTITY_RACE')]:
            with self.subTest(field=field):
                self.api = API()
                self.api.open_effect = lambda api: setattr(api, field, value)
                error = self.fails(code, self.make)
                self.assertEqual(self.api.closed, [999])
                self.assertTrue(error.cleanup_owner.closed)

    def test_process_identity_race_after_thread_open(self):
        self.api.open_effect = lambda api: api.process.update(process_start='windows:102')
        self.fails('S108_PROCESS_IDENTITY', self.make)
        self.assertEqual(self.api.closed, [999])

    def test_missing_api_is_explicit_before_open(self):
        self.api.thread_times = None
        self.fails('S108_WINAPI_UNAVAILABLE', self.make)
        self.assertEqual(self.api.opened, [])

    def test_retained_process_change_and_exit(self):
        for change, code in [(lambda proc: setattr(proc, 'handle', None), 'S108_RETAINED_PROCESS_CHANGED'),
                              (lambda proc: setattr(proc, 'ended', True), 'S108_PROCESS_ENDED'),
                              (lambda proc: setattr(proc, 'process_start', 'windows:900'), 'S108_RETAINED_PROCESS_CHANGED')]:
            with self.subTest(code=code):
                self.process, self.api = Process(), API()
                probe = self.make()
                self.process.mutate = change
                error = self.fails(code, lambda: probe.sample(5))
                self.assertIs(error.cleanup_owner, probe)
                self.assertEqual(probe.records, [])
                self.assertEqual(probe.errors[0]['code'], code)
                probe.close()

    def test_thread_end_and_creation_reuse(self):
        for mutate, code in [(lambda api: setattr(api, 'exit_code', 86), 'S108_THREAD_ENDED'),
                              (lambda api: api.times.update(created_100ns=102), 'S108_THREAD_CREATION_CHANGED')]:
            with self.subTest(code=code):
                self.api = API()
                probe = self.make()
                mutate(self.api)
                error = self.fails(code, lambda: probe.sample(6))
                if code == 'S108_THREAD_ENDED':
                    self.assertEqual(error.thread_exit_code, 86)
                    self.assertEqual(probe.errors[0]['thread_exit_code'], 86)
                probe.close()

    def test_counter_reversal_failure_is_latched(self):
        for field in ('kernel_100ns', 'user_100ns'):
            with self.subTest(field=field):
                self.api = API()
                probe = self.make()
                self.api.times[field] -= 1
                self.fails('S108_CPU_COUNTER_REVERSED', lambda: probe.sample(5))
                self.api.times[field] += 1
                self.fails('S108_COLLECTOR_ALREADY_FAILED', lambda: probe.sample(5))
                self.assertEqual(len(probe.errors), 1)
                probe.close()

    def test_signaled_thread_exit_259_is_ended_not_running(self):
        probe = self.make()
        self.api.wait_result = 0
        self.api.exit_code = 259
        error = self.fails('S108_THREAD_ENDED', lambda: probe.sample(5))
        self.assertEqual(error.thread_exit_code, 259)
        self.assertEqual(probe.records, [])
        probe.close()

    def test_thread_ending_during_query_is_not_a_completed_sample(self):
        probe = self.make()
        def ending(_):
            self.api.wait_result, self.api.exit_code = 0, 0
            return dict(self.api.times)
        self.api.thread_times = ending
        error = self.fails('S108_THREAD_ENDED', lambda: probe.sample(6))
        self.assertEqual(error.thread_exit_code, 0)
        self.assertEqual(probe.records, [])
        probe.close()

    def test_backwards_clock_and_batch_fail_closed(self):
        for kind, code in [('clock', 'S108_SAMPLE_CLOCK'), ('batch', 'S108_BATCH_REVERSED')]:
            with self.subTest(kind=kind):
                self.api = API()
                probe = self.make()
                probe.sample(6)
                if kind == 'clock':
                    self.clock.now -= p.INTERVAL_NS
                else:
                    self.clock.advance()
                self.fails(code, lambda: probe.sample(6 if kind == 'clock' else 5))
                self.assertEqual(len(probe.records), 1)
                probe.close()

    def test_thread_cannot_predate_bound_process(self):
        self.api.times['created_100ns'] = 99
        self.fails('S108_THREAD_PREDATES_PROCESS', self.make)
        self.assertEqual(self.api.closed, [999])

    def test_fixed_limit_and_batch_scope(self):
        probe = self.make(max_samples=1)
        probe.sample(5)
        self.clock.advance()
        self.fails('S108_SAMPLE_LIMIT', lambda: probe.sample(6))
        self.assertEqual(len(probe.records), 1)
        probe.close()
        for batch in (4, 7, True, 5.0):
            self.api = API()
            probe = self.make()
            self.fails('S108_SAMPLE_BATCH', lambda: probe.sample(batch))
            probe.close()
        self.fails('S108_SAMPLE_LIMIT_VALUE', lambda: self.make(max_samples=8001))

    def test_native_times_failure_preserves_winerror(self):
        probe = self.make()
        self.api.times_error = p.ThreadProbeError('S108_THREAD_TIMES', winerror=6)
        self.fails('S108_THREAD_TIMES', lambda: probe.sample(5))
        self.assertEqual(probe.errors[0]['winerror'], 6)
        probe.close()

    def test_checked_close_failure_retains_then_retries(self):
        probe = self.make()
        self.api.close_result = False
        error = self.fails('S108_THREAD_CLOSE_FAILED', probe.close)
        self.assertIs(error.cleanup_owner, probe)
        self.assertEqual(error.winerror, 5)
        self.assertEqual(probe.handle, 999)
        self.assertFalse(probe.close_uncertain)
        self.assertEqual(probe.close_receipt['status'], 'FAILED')
        self.assertIn(probe, p.HELD_PROBES)
        self.api.close_result = True
        self.assertEqual(probe.close()['status'], 'CLOSED')
        self.assertEqual(self.api.closed, [999, 999])

    def test_uncertain_close_never_retries_native_handle(self):
        for result in ('raise', None):
            with self.subTest(result=result):
                self.api = API()
                probe = self.make()
                if result == 'raise':
                    self.api.close_error = RuntimeError('native-call-outcome-unknown')
                    with self.assertRaisesRegex(RuntimeError, 'native-call-outcome-unknown'):
                        probe.close()
                else:
                    self.api.close_result = None
                    self.fails('S108_THREAD_CLOSE_RESULT_UNKNOWN', probe.close)
                self.assertTrue(probe.close_uncertain)
                error = self.fails('S108_THREAD_CLOSE_UNCERTAIN', probe.close)
                self.assertIs(error.cleanup_owner, probe)
                self.assertEqual(self.api.closed, [999])

    def test_constructor_preserves_primary_and_cleanup_failure(self):
        self.api.thread = (124, 456)
        self.api.close_result = False
        error = self.fails('S108_THREAD_IDENTITY', self.make)
        self.assertEqual(error.cleanup_error.code, 'S108_THREAD_CLOSE_FAILED')
        self.assertIn(error.cleanup_owner, p.HELD_PROBES)
        self.api.close_result = True
        error.cleanup_owner.close()


if __name__ == '__main__':
    unittest.main()
