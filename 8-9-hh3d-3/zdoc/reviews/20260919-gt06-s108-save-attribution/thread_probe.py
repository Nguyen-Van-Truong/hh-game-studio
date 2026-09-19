"""Bounded read-only CPU samples from the owned editor's native GUI thread.

The runner owns process/binary pinning, native clock alignment, persistence and
the 1,200-second outer bound. This collector never launches, stops, suspends or
reopens a process. Godot's logical thread ID is deliberately not accepted.
CPU counters are cumulative accounting, not exact-instant CPU measurements;
their 100 ns units do not guarantee 100 ns resolution or identify a wait cause.
All observations remain diagnostic.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
import time

INTERVAL_NS = 50_000_000
MAX_SAMPLES = 8000
QUERY_ACCESS = 0x100000 | 0x0800  # SYNCHRONIZE | THREAD_QUERY_LIMITED_INFORMATION.
STILL_ACTIVE = 259
HELD_PROBES = []


class ThreadProbeError(RuntimeError):
    def __init__(self, code, *, winerror=None, cleanup_owner=None, thread_exit_code=None):
        super().__init__(code)
        self.code, self.winerror, self.cleanup_owner = code, winerror, cleanup_owner
        self.thread_exit_code = thread_exit_code


def need(condition, code):
    if not condition:
        raise ThreadProbeError(code)


def positive(value):
    return type(value) is int and value > 0


def path_key(value):
    return ntpath.normcase(ntpath.normpath(value))


class WinAPI:
    """Small injectable boundary; all handles belong to the supplied owner."""
    def __init__(self):
        need(os.name == 'nt', 'S108_WINDOWS_REQUIRED')
        from ctypes import wintypes as w
        self.w = w
        try:
            self.k = ctypes.WinDLL('kernel32', use_last_error=True)
            self.u = ctypes.WinDLL('user32', use_last_error=True)
            signatures = {
                'OpenThread': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
                'CloseHandle': ([w.HANDLE], w.BOOL),
                'GetThreadId': ([w.HANDLE], w.DWORD),
                'GetProcessIdOfThread': ([w.HANDLE], w.DWORD),
                'GetProcessId': ([w.HANDLE], w.DWORD),
                'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
                'GetExitCodeThread': ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
                'GetThreadTimes': ([w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4, w.BOOL),
                'GetProcessTimes': ([w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4, w.BOOL),
                'QueryFullProcessImageNameW': ([w.HANDLE, w.DWORD, w.LPWSTR,
                                               ctypes.POINTER(w.DWORD)], w.BOOL),
            }
            for name, (args, result) in signatures.items():
                function = getattr(self.k, name)
                function.argtypes, function.restype = args, result
            self.callback_type = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
            self.u.EnumWindows.argtypes = [self.callback_type, w.LPARAM]
            self.u.EnumWindows.restype = w.BOOL
            self.u.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
            self.u.GetWindowThreadProcessId.restype = w.DWORD
        except (AttributeError, OSError) as error:
            raise ThreadProbeError('S108_WINAPI_UNAVAILABLE',
                                   winerror=getattr(error, 'winerror', None)) from error

    @staticmethod
    def last_error():
        return ctypes.get_last_error()

    def checked(self, result, code):
        if not result:
            raise ThreadProbeError(code, winerror=self.last_error())
        return result

    def times(self, function, handle, code):
        values = [self.w.FILETIME() for _ in range(4)]
        self.checked(function(handle, *(ctypes.byref(v) for v in values)), code)
        return [(v.dwHighDateTime << 32) | v.dwLowDateTime for v in values]

    def process_identity(self, handle):
        pid = self.checked(self.k.GetProcessId(handle), 'S108_PROCESS_ID')
        created, _, _, _ = self.times(self.k.GetProcessTimes, handle, 'S108_PROCESS_TIMES')
        size, buffer = self.w.DWORD(32768), ctypes.create_unicode_buffer(32768)
        self.checked(self.k.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)),
                     'S108_PROCESS_IMAGE')
        return {'pid': int(pid), 'process_start': 'windows:' + str(created),
                'executable': buffer.value}

    def window_identity(self, hwnd):
        owner = self.w.DWORD()
        tid = self.checked(self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner)),
                           'S108_WINDOW_ID')
        return int(owner.value), int(tid)

    def owned_windows(self, pid):
        result, errors = [], []
        def visit(hwnd, _):
            try:
                owner = self.w.DWORD()
                tid = self.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
                # An unrelated window can disappear during enumeration. The
                # announced HWND is separately queried before and after this.
                if tid and owner.value == pid:
                    need(len(result) < 256, 'S108_WINDOW_LIMIT')
                    result.append({'hwnd': int(hwnd), 'pid': int(owner.value), 'tid': int(tid)})
                return True
            except BaseException as error:
                errors.append(error)
                return False
        callback = self.callback_type(visit)
        result_ok = self.u.EnumWindows(callback, 0)
        if errors:
            raise errors[0]
        self.checked(result_ok, 'S108_ENUM_WINDOWS')
        return result

    def open_thread(self, tid):
        return self.checked(self.k.OpenThread(QUERY_ACCESS, False, tid), 'S108_OPEN_THREAD')

    def thread_identity(self, handle):
        tid = self.checked(self.k.GetThreadId(handle), 'S108_THREAD_ID')
        pid = self.checked(self.k.GetProcessIdOfThread(handle), 'S108_THREAD_PROCESS_ID')
        return int(pid), int(tid)

    def thread_exit(self, handle):
        value = self.w.DWORD()
        self.checked(self.k.GetExitCodeThread(handle, ctypes.byref(value)), 'S108_THREAD_EXIT_QUERY')
        return int(value.value)

    def thread_wait(self, handle):
        value = int(self.k.WaitForSingleObject(handle, 0))
        if value == 0xffffffff:
            raise ThreadProbeError('S108_THREAD_WAIT', winerror=self.last_error())
        return value

    def thread_times(self, handle):
        created, _, kernel, user = self.times(self.k.GetThreadTimes, handle, 'S108_THREAD_TIMES')
        # The exit FILETIME is undefined while alive and is never retained.
        return {'created_100ns': created, 'kernel_100ns': kernel, 'user_100ns': user}

    def close_thread(self, handle):
        return bool(self.k.CloseHandle(handle))


class ThreadProbe:
    def __init__(self, process_probe, expected_identity, announced_hwnd, *, api=None,
                 clock_ns=time.perf_counter_ns, max_samples=MAX_SAMPLES):
        self.process_probe, self.expected = process_probe, dict(expected_identity)
        self.clock_ns, self.api = clock_ns, api if api is not None else WinAPI()
        self.handle, self.close_uncertain, self.closed = None, False, False
        self.records, self.errors, self.identity, self.close_receipt = [], [], {}, None
        self.window_rows = []
        self._last_start, self._last_cpu, self._last_batch = None, None, None
        self._failure = None
        need(all(callable(getattr(self.api, name, None)) for name in (
            'process_identity', 'window_identity', 'owned_windows', 'open_thread',
            'thread_identity', 'thread_exit', 'thread_wait', 'thread_times', 'close_thread', 'last_error')),
            'S108_WINAPI_UNAVAILABLE')
        need(set(self.expected) == {'pid', 'process_start', 'executable'}, 'S108_EXPECTED_FIELDS')
        need(positive(self.expected['pid']) and self.expected['pid'] < 0xffffffff
             and type(self.expected['process_start']) is str
             and self.expected['process_start'].startswith('windows:')
             and self.expected['process_start'][8:].isdigit()
             and int(self.expected['process_start'][8:]) > 0
             and type(self.expected['executable']) is str
             and ntpath.isabs(self.expected['executable']), 'S108_EXPECTED_IDENTITY')
        need(positive(announced_hwnd) and announced_hwnd < 2**64, 'S108_ANNOUNCED_HWND')
        need(type(max_samples) is int and 1 <= max_samples <= MAX_SAMPLES, 'S108_SAMPLE_LIMIT_VALUE')
        self.max_samples, self.hwnd = max_samples, announced_hwnd
        self.process_handle = process_probe.handle
        try:
            self._check_process()
            self._check_process_identity()
            pid, tid = self.api.window_identity(self.hwnd)
            need(pid == self.expected['pid'] and positive(tid), 'S108_WINDOW_PROCESS_BINDING')
            windows = self.api.owned_windows(pid)
            need(type(windows) is list and 0 < len(windows) <= 256
                 and all(type(row) is dict and set(row) == {'hwnd', 'pid', 'tid'}
                         and positive(row['hwnd']) and row['pid'] == pid and positive(row['tid'])
                         for row in windows), 'S108_WINDOW_ENUMERATION')
            need(len({row['hwnd'] for row in windows}) == len(windows)
                 and self.hwnd in {row['hwnd'] for row in windows}, 'S108_ANNOUNCED_WINDOW_MISSING')
            self.window_rows = [{'hwnd': row['hwnd'], 'pid': row['pid'], 'tid': row['tid']}
                                for row in windows]
            if {row['tid'] for row in windows} != {tid}:
                error = ThreadProbeError('S108_AMBIGUOUS_GUI_THREAD')
                error.announced_tid = tid
                error.owned_window_rows = list(self.window_rows)
                raise error
            self.tid = tid
            self.handle = self.api.open_thread(tid)
            need(self.handle, 'S108_OPEN_THREAD')
            HELD_PROBES.append(self)
            times, _, _ = self._read_thread()
            need(times['created_100ns'] >= int(self.expected['process_start'][8:]),
                 'S108_THREAD_PREDATES_PROCESS')
            need(self.api.window_identity(self.hwnd) == (pid, tid), 'S108_WINDOW_IDENTITY_RACE')
            self._check_process_identity()
            self._check_process()
            self.identity = {**self.expected, 'executable': path_key(self.expected['executable']),
                'hwnd': self.hwnd, 'tid': tid, 'thread_created_100ns': times['created_100ns'],
                'query_access': QUERY_ACCESS, 'owned_window_handles': sorted(row['hwnd'] for row in windows)}
            self._last_cpu = times
        except BaseException as error:
            error.cleanup_owner = self if self.handle is not None else None
            try:
                self.close()
            except BaseException as cleanup_error:
                error.cleanup_error = cleanup_error
            raise

    def _check_process(self):
        probe = self.process_probe
        def same():
            return (probe.handle is not None and probe.handle == self.process_handle
                    and not probe.close_uncertain and probe.pid == self.expected['pid']
                    and probe.process_start == self.expected['process_start'])
        need(same(), 'S108_RETAINED_PROCESS_CHANGED')
        value = probe.sample()
        need(value is not None, 'S108_PROCESS_ENDED')
        need(same(), 'S108_RETAINED_PROCESS_CHANGED')
        need(type(value) is dict and type(value.get('host_mono_us')) is int
             and value['host_mono_us'] >= 0 and type(value.get('rss_bytes')) is int
             and value['rss_bytes'] >= 0 and type(value.get('visible_window_handles')) is list,
             'S108_PROCESS_SAMPLE')
        return value

    def _check_process_identity(self):
        value = self.api.process_identity(self.process_handle)
        need(type(value) is dict and value.get('pid') == self.expected['pid']
             and value.get('process_start') == self.expected['process_start']
             and type(value.get('executable')) is str
             and path_key(value['executable']) == path_key(self.expected['executable']),
             'S108_PROCESS_IDENTITY')

    def _read_thread(self):
        self._check_thread_alive()
        need(self.api.thread_identity(self.handle) == (self.expected['pid'], self.tid),
             'S108_THREAD_IDENTITY')
        before = self.clock_ns()
        values = self.api.thread_times(self.handle)
        after = self.clock_ns()
        need(type(before) is int and type(after) is int and 0 <= before <= after, 'S108_SAMPLE_CLOCK')
        need(type(values) is dict and set(values) == {'created_100ns', 'kernel_100ns', 'user_100ns'}
             and positive(values['created_100ns'])
             and all(type(values[key]) is int and values[key] >= 0
                     for key in ('kernel_100ns', 'user_100ns')), 'S108_THREAD_TIMES_VALUE')
        self._check_thread_alive()
        if self._last_cpu is not None:
            need(values['created_100ns'] == self._last_cpu['created_100ns'], 'S108_THREAD_CREATION_CHANGED')
            need(all(values[key] >= self._last_cpu[key] for key in ('kernel_100ns', 'user_100ns')),
                 'S108_CPU_COUNTER_REVERSED')
        return values, before, after

    def _check_thread_alive(self):
        wait = self.api.thread_wait(self.handle)
        need(type(wait) is int and wait in (0, 258), 'S108_THREAD_WAIT_VALUE')
        if wait == 258:
            return
        code = self.api.thread_exit(self.handle)
        need(type(code) is int and 0 <= code < 2**32, 'S108_THREAD_EXIT_VALUE')
        # A signaled thread has ended even when its actual exit code is 259.
        raise ThreadProbeError('S108_THREAD_ENDED', thread_exit_code=code)

    def sample(self, batch):
        """Return one bounded observation, or None when the cadence is not due."""
        started = self.clock_ns()
        try:
            need(self.handle is not None and not self.closed and not self.close_uncertain,
                 'S108_THREAD_CLOSED_OR_UNCERTAIN')
            need(self._failure is None, 'S108_COLLECTOR_ALREADY_FAILED')
            need(type(batch) is int and batch in (5, 6), 'S108_SAMPLE_BATCH')
            need(self._last_batch is None or batch >= self._last_batch, 'S108_BATCH_REVERSED')
            need(type(started) is int and started >= 0
                 and (self._last_start is None or started >= self._last_start), 'S108_SAMPLE_CLOCK')
            if self._last_start is not None and started - self._last_start < INTERVAL_NS:
                return None
            need(len(self.records) < self.max_samples, 'S108_SAMPLE_LIMIT')
            self._check_process()
            values, before, after = self._read_thread()
            ended = self.clock_ns()
            need(started <= before <= after <= ended, 'S108_SAMPLE_CLOCK')
            row = {'schema': 'gt06-s108-thread-cpu-sample-v1', 'index': len(self.records),
                'batch': batch, 'pid': self.expected['pid'], 'process_start': self.expected['process_start'],
                'tid': self.tid, 'thread_created_100ns': values['created_100ns'],
                'sample_started_perf_ns': started, 'sample_ended_perf_ns': ended,
                'host_before_ns': before, 'host_after_ns': after,
                'times_api_duration_ns': after - before, 'sample_duration_ns': ended - started,
                'kernel_100ns': values['kernel_100ns'], 'user_100ns': values['user_100ns'],
                'formal_acceptance': False, 'eligible_for_dataset': False}
            self.records.append(row)
            self._last_start, self._last_cpu, self._last_batch = started, values, batch
            return row
        except BaseException as error:
            if self._failure is None:
                self._failure = getattr(error, 'code', type(error).__name__)
                self.errors.append({'code': self._failure, 'winerror': getattr(error, 'winerror', None),
                    'thread_exit_code': getattr(error, 'thread_exit_code', None),
                    'batch': batch, 'sample_index': len(self.records), 'started_perf_ns': started,
                    'ended_perf_ns': self.clock_ns()})
            error.cleanup_owner = self if self.handle is not None else None
            raise

    def close(self):
        """A checked failure retains retry authority; an uncertain call does not."""
        if self.closed:
            return self.close_receipt
        if self.handle is None:
            self.closed = True
            self.close_receipt = {'status': 'NOT_OPENED', 'native_close_result': None}
            return self.close_receipt
        if self.close_uncertain:
            raise ThreadProbeError('S108_THREAD_CLOSE_UNCERTAIN', cleanup_owner=self)
        self.close_receipt = {'status': 'UNCERTAIN', 'native_close_result': None,
                              'started_perf_ns': self.clock_ns()}
        self.close_uncertain = True
        try:
            result = self.api.close_thread(self.handle)
        except BaseException as error:
            self.close_receipt['ended_perf_ns'] = self.clock_ns()
            error.cleanup_owner = self
            raise
        self.close_receipt.update(ended_perf_ns=self.clock_ns(), native_close_result=result)
        if type(result) is not bool:
            raise ThreadProbeError('S108_THREAD_CLOSE_RESULT_UNKNOWN', cleanup_owner=self)
        if not result:
            self.close_uncertain = False
            self.close_receipt.update(status='FAILED', winerror=self.api.last_error())
            raise ThreadProbeError('S108_THREAD_CLOSE_FAILED', winerror=self.close_receipt['winerror'],
                                   cleanup_owner=self)
        self.close_receipt['status'] = 'CLOSED'
        self.handle, self.close_uncertain, self.closed = None, False, True
        HELD_PROBES.remove(self)
        return self.close_receipt
