"""O4 environment observation. May stop a run; never grants measurement PASS.

The observer lives in the campaign supervisor, outside the measured host Job.
Unknown attribution fails closed. No process is stopped by name or PID.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
import os
import time

from studio.tests.replay.benchmark_job import BenchmarkJobError, require

GIB = 1024**3
INTERVAL_SECONDS = 5
MAX_SAMPLE_GAP_SECONDS = 10
SCHEMA = 'hh-studio.benchmark-environment-preflight'
VERSION = '1.2.0'


class Memory(ctypes.Structure):
    _fields_ = [('length', w.DWORD), ('load', w.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in ('physical', 'available', 'page_total',
        'page_available', 'virtual_total', 'virtual_available', 'extended_available')]


class Performance(ctypes.Structure):
    _fields_ = [('cb', w.DWORD)] + [(name, ctypes.c_size_t) for name in (
        'commit_total', 'commit_limit', 'commit_peak', 'physical_total',
        'physical_available', 'system_cache', 'kernel_total', 'kernel_paged',
        'kernel_nonpaged', 'page_size')] + [
        (name, w.DWORD) for name in ('handle_count', 'process_count', 'thread_count')]


class Counters(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('page_faults', w.DWORD)] + [
        (name, ctypes.c_size_t) for name in ('peak_working_set', 'working_set',
        'peak_paged', 'paged', 'peak_nonpaged', 'nonpaged', 'pagefile',
        'peak_pagefile', 'private')]


def api():
    require(os.name == 'nt', 'CAMPAIGN_PREFLIGHT_PLATFORM')
    k, p = ctypes.WinDLL('kernel32', use_last_error=True), ctypes.WinDLL('psapi', use_last_error=True)
    k.GlobalMemoryStatusEx.argtypes, k.GlobalMemoryStatusEx.restype = [ctypes.POINTER(Memory)], w.BOOL
    p.GetPerformanceInfo.argtypes, p.GetPerformanceInfo.restype = [ctypes.POINTER(Performance), w.DWORD], w.BOOL
    k.OpenProcess.argtypes, k.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL
    k.IsProcessInJob.argtypes, k.IsProcessInJob.restype = [w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL
    k.QueryInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    k.QueryInformationJobObject.restype = w.BOOL
    k.GetSystemTimes.argtypes, k.GetSystemTimes.restype = [ctypes.POINTER(w.FILETIME)] * 3, w.BOOL
    k.GetTickCount64.argtypes, k.GetTickCount64.restype = [], ctypes.c_ulonglong
    k.QueryUnbiasedInterruptTime.argtypes = [ctypes.POINTER(ctypes.c_ulonglong)]
    k.QueryUnbiasedInterruptTime.restype = w.BOOL
    p.GetProcessMemoryInfo.argtypes, p.GetProcessMemoryInfo.restype = [w.HANDLE, ctypes.POINTER(Counters), w.DWORD], w.BOOL
    return k, p


class KeepAwake:
    """Restore this thread's prior execution state even on run failure."""
    def __enter__(self):
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.SetThreadExecutionState.argtypes, self.k.SetThreadExecutionState.restype = [w.DWORD], w.DWORD
        self.previous = self.k.SetThreadExecutionState(0x80000001)
        require(self.previous != 0, 'CAMPAIGN_KEEP_AWAKE_FAILED')
        return self

    def __exit__(self, kind, error, _trace):
        if not self.k.SetThreadExecutionState(self.previous | 0x80000000):
            if error is not None:
                error.add_note('CAMPAIGN_KEEP_AWAKE_RESTORE_FAILED')
            else:
                raise BenchmarkJobError('CAMPAIGN_KEEP_AWAKE_RESTORE_FAILED')


def job_members(k, handle):
    if handle is None:
        return set()
    class Pids(ctypes.Structure):
        _fields_ = [('assigned', w.DWORD), ('count', w.DWORD), ('pids', ctypes.c_size_t * 64)]
    value, returned = Pids(), w.DWORD()
    require(k.QueryInformationJobObject(handle, 3, ctypes.byref(value), ctypes.sizeof(value),
                                       ctypes.byref(returned)), 'WATCHDOG_JOB_MEMBERS')
    require(value.count <= 64 and value.assigned == value.count, 'WATCHDOG_JOB_MEMBERS_TRUNCATED')
    return set(int(value.pids[i]) for i in range(value.count))


def native_snapshot(processes, *, job_handle=None, heavy_names=frozenset()):
    k, p = api()
    memory, perf = Memory(), Performance()
    memory.length, perf.cb = ctypes.sizeof(memory), ctypes.sizeof(perf)
    require(k.GlobalMemoryStatusEx(ctypes.byref(memory)), 'CAMPAIGN_PREFLIGHT_MEMORY')
    require(p.GetPerformanceInfo(ctypes.byref(perf), ctypes.sizeof(perf)), 'CAMPAIGN_PREFLIGHT_COMMIT')
    require(perf.commit_limit > 0 and perf.page_size > 0, 'CAMPAIGN_PREFLIGHT_COMMIT_LIMIT')
    idle, kernel, user = w.FILETIME(), w.FILETIME(), w.FILETIME()
    require(k.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)), 'WATCHDOG_CPU_QUERY')
    ticks = lambda v: int(v.dwLowDateTime | v.dwHighDateTime << 32)
    awake = ctypes.c_ulonglong()
    uptime_ms = int(k.GetTickCount64())
    require(k.QueryUnbiasedInterruptTime(ctypes.byref(awake)), 'WATCHDOG_AWAKE_QUERY')
    members = job_members(k, job_handle)
    rows, foreign, owned_private, owned_complete = [], [], 0, True
    # Include members created after the Toolhelp snapshot. No PID is trusted:
    # IsProcessInJob rechecks membership on the retained process handle.
    names = {row['pid']: row['name'] for row in processes}
    for pid in members:
        names.setdefault(pid, '<job-member>')
    for pid, name in names.items():
        engine = name.startswith(('godot', 'blender'))
        row = {'pid': pid, 'name': name, 'private_bytes': None, 'owned': False}
        h = k.OpenProcess(0x1000, False, pid)
        if not h:
            row['unavailable_error'] = ctypes.get_last_error()
            # An inaccessible engine is never assumed owned or gone.
            if engine:
                foreign.append({'pid': pid, 'name': name, 'ownership': 'unverified'})
            if pid in members:
                owned_complete = False
            rows.append(row)
            continue
        try:
            inside = w.BOOL(False)
            if job_handle is not None:
                require(k.IsProcessInJob(h, job_handle, ctypes.byref(inside)), 'WATCHDOG_JOB_MEMBERSHIP')
            row['owned'] = bool(inside.value)
            if engine and not row['owned']:
                foreign.append({'pid': pid, 'name': name, 'ownership': 'outside_campaign_job'})
            counter = Counters()
            counter.cb = ctypes.sizeof(counter)
            if p.GetProcessMemoryInfo(h, ctypes.byref(counter), ctypes.sizeof(counter)):
                row['private_bytes'] = int(counter.private)
                if row['owned']:
                    owned_private += int(counter.private)
            else:
                row['unavailable_error'] = ctypes.get_last_error()
                if row['owned']:
                    owned_complete = False
        finally:
            require(k.CloseHandle(h), 'WATCHDOG_PROCESS_HANDLE_CLOSE')
        rows.append(row)
    return {
        'observed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'available_memory_bytes': int(memory.available),
        'commit_total_bytes': int(perf.commit_total * perf.page_size),
        'commit_limit_bytes': int(perf.commit_limit * perf.page_size),
        'uptime_ms': uptime_ms, 'awake_100ns': int(awake.value),
        'cpu_idle_100ns': ticks(idle), 'cpu_total_100ns': ticks(kernel) + ticks(user),
        'foreign_engines': foreign, 'owned_private_bytes': owned_private,
        'owned_inventory_complete': owned_complete,
        'owned_processes': [row for row in rows if row['owned']],
        'heavy_processes': [row for row in rows if row['name'] in heavy_names],
        'docker_wsl_processes': [row for row in rows if any(
            label in row['name'] for label in ('docker', 'wsl', 'vmmem'))],
        'top_private_processes': sorted(
            (row for row in rows if row['private_bytes'] is not None),
            key=lambda row: row['private_bytes'], reverse=True)[:20],
        'unavailable_process_count': sum(row['private_bytes'] is None for row in rows),
    }


def preflight(snapshot):
    result = {**snapshot, 'schema_id': SCHEMA, 'schema_version': VERSION,
              'required_available_memory_bytes': 4 * GIB,
              'required_commit_max_percent': 85.0,
              'required_heavy_processes_closed': False, 'pass': False, 'failure_code': None,
              'scope': 'O4.1 launch gate; inventory names are not an application ban'}
    result['commit_used_percent'] = 100 * snapshot['commit_total_bytes'] / snapshot['commit_limit_bytes']
    result['pass'] = (not snapshot['foreign_engines'] and snapshot['available_memory_bytes'] >= 4 * GIB
                      and snapshot['commit_total_bytes'] * 100 <= snapshot['commit_limit_bytes'] * 85)
    if not result['pass']:
        result['failure_code'] = ('CAMPAIGN_PREFLIGHT_FOREIGN_ENGINE' if snapshot['foreign_engines']
                                  else 'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')
    return result


def require_preflight(result):
    require(type(result) is dict and result.get('schema_id') == SCHEMA
            and result.get('schema_version') == VERSION, 'CAMPAIGN_PREFLIGHT_SHAPE')
    require(type(result.get('heavy_processes')) is list
            and result.get('required_heavy_processes_closed') is False, 'CAMPAIGN_PREFLIGHT_APP_INVENTORY')
    require(type(result.get('foreign_engines')) is list, 'CAMPAIGN_PREFLIGHT_ENGINE_INVENTORY')
    require(not result['foreign_engines'], 'CAMPAIGN_PREFLIGHT_FOREIGN_ENGINE')
    available, total, limit = (result.get(key) for key in (
        'available_memory_bytes', 'commit_total_bytes', 'commit_limit_bytes'))
    require(type(available) is int and available >= 4 * GIB and type(total) is int and total >= 0
            and type(limit) is int and limit > 0 and total * 100 <= limit * 85
            and result.get('pass') is True, 'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')


class Policy:
    """Replayable sampled policy; counters/measurement acceptance stay elsewhere."""
    def __init__(self):
        self.first = self.previous = None
        self.low_since = self.cpu_since = None

    def observe(self, row):
        for name in ('available_memory_bytes', 'commit_total_bytes', 'commit_limit_bytes',
                     'uptime_ms', 'awake_100ns', 'cpu_idle_100ns', 'cpu_total_100ns',
                     'owned_private_bytes'):
            require(type(row.get(name)) is int and row[name] >= 0, 'WATCHDOG_SAMPLE_INVALID')
        require(row['commit_limit_bytes'] > 0 and type(row.get('foreign_engines')) is list
                and type(row.get('owned_inventory_complete')) is bool, 'WATCHDOG_SAMPLE_INVALID')
        now = row['uptime_ms'] / 1000
        previous = self.previous
        if self.first is None:
            self.first = row
        reason, classification = None, 'INFRA_ABORT'
        if previous is not None:
            elapsed = now - previous['uptime_ms'] / 1000
            awake_elapsed = (row['awake_100ns'] - previous['awake_100ns']) / 10_000_000
            require(elapsed >= 0 and awake_elapsed >= 0, 'WATCHDOG_CLOCK_REGRESSION')
            # Two Windows uptime clocks avoid false sleep detection from NTP.
            if elapsed - awake_elapsed > 0.1:
                reason = 'SLEEP_RESUME'
            elif elapsed > MAX_SAMPLE_GAP_SECONDS:
                reason, classification = 'SAMPLE_GAP', 'HARNESS_FAIL'
            total = row['cpu_total_100ns'] - previous['cpu_total_100ns']
            idle = row['cpu_idle_100ns'] - previous['cpu_idle_100ns']
            require(total >= 0 and 0 <= idle <= total, 'WATCHDOG_CPU_DELTA')
            cpu_hot = total > 0 and (total - idle) * 100 > total * 95
            self.cpu_since = (self.cpu_since if self.cpu_since is not None else previous['uptime_ms'] / 1000) if cpu_hot else None
        self.low_since = (self.low_since if self.low_since is not None else now) if row['available_memory_bytes'] < 1.5 * GIB else None
        if row['foreign_engines']:
            reason = reason or 'FOREIGN_ENGINE'
        if row['commit_total_bytes'] * 100 > row['commit_limit_bytes'] * 92:
            reason = reason or 'COMMIT_PRESSURE'
        if self.low_since is not None and now - self.low_since >= 60:
            reason = reason or 'AVAILABLE_PRESSURE'
        if self.cpu_since is not None and now - self.cpu_since >= 60:
            reason = reason or 'CPU_PRESSURE'
        if reason in ('COMMIT_PRESSURE', 'AVAILABLE_PRESSURE'):
            # Do not claim a causal leak from correlation. If the budget would
            # still be violated after subtracting ALL campaign private bytes,
            # external pressure is sufficient. Otherwise keep a product hold.
            owned = row['owned_private_bytes']
            external_sufficient = (row['commit_total_bytes'] - owned) * 100 > row['commit_limit_bytes'] * 92
            if reason == 'AVAILABLE_PRESSURE':
                external_sufficient = row['available_memory_bytes'] + owned < 1.5 * GIB
            classification = ('INFRA_ABORT' if row['owned_inventory_complete'] and external_sufficient
                              else 'PRODUCT_FAIL')
        self.previous = row
        return None if reason is None else {
            'reason': reason, 'classification': classification, 'formal_acceptance': False,
            'attribution': ('external_pressure_sufficient_without_campaign_private'
                            if reason in ('COMMIT_PRESSURE', 'AVAILABLE_PRESSURE') and classification == 'INFRA_ABORT'
                            else 'no_product_failure_is_waived')}


class Watchdog:
    def __init__(self, output, sample, binding, write):
        self.output, self.sample, self.binding, self.write = output, sample, binding, write
        self.policy, self.last, self.count = Policy(), None, 0
        self.stream = (output / 'environment-samples.jsonl').open('xb')

    def poll(self, *, force=False):
        now = time.monotonic()
        if not force and self.last is not None and now - self.last < INTERVAL_SECONDS:
            return
        row = self.sample()
        decision = self.policy.observe(row)
        self.stream.write((json.dumps(row, sort_keys=True, allow_nan=False) + '\n').encode())
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.count += 1
        self.last = now
        if decision:
            event = {'schema': 'HH-GT06-WATCHDOG-STOP-1', **self.binding, **decision,
                     'sample_index': self.count - 1}
            self.write(self.output / 'watchdog-stop.json', event)
            error = BenchmarkJobError('CAMPAIGN_WATCHDOG_' + decision['reason'])
            error.classification = decision['classification']
            raise error

    def close(self):
        self.stream.close()


def failure_classification(error, output):
    """Existing child failures win over a simultaneous infrastructure stop."""
    if (output / 'child-failure.json').exists():
        return 'PRODUCT_FAIL'
    if getattr(error, 'code', '').startswith('CAMPAIGN_PREFLIGHT_'):
        return 'INFRA_ABORT'
    return getattr(error, 'classification', 'PRODUCT_FAIL')


def require_infra_budget(reviews, read_regular):
    today = time.strftime('%Y-%m-%d')
    count = 0
    for path in reviews.glob('gt06-*/run-*-attempt-*/parent-failure.json'):
        row = json.loads(read_regular(path))
        if row.get('classification') == 'INFRA_ABORT' and row.get('attempt_local_date') == today:
            count += 1
    require(count < 2, 'CAMPAIGN_INFRA_DAILY_LIMIT')


def verify_watchdog(output, read_regular, *, elapsed_seconds=None):
    require(not (output / 'watchdog-stop.json').exists(), 'CAMPAIGN_WATCHDOG_STOP_LATCHED')
    raw = read_regular(output / 'environment-samples.jsonl', 64 * 1024**2)
    policy, count = Policy(), 0
    for line in raw.splitlines():
        row = json.loads(line)
        require(policy.observe(row) is None, 'CAMPAIGN_WATCHDOG_REPLAY_FAILED')
        count += 1
    require(count >= 2, 'CAMPAIGN_WATCHDOG_SAMPLES_MISSING')
    if elapsed_seconds is not None:
        require(type(elapsed_seconds) in (float, int) and elapsed_seconds > 0,
                'CAMPAIGN_WATCHDOG_DURATION')
        covered = (policy.previous['uptime_ms'] - policy.first['uptime_ms']) / 1000
        # Launch and natural-exit bookkeeping may add a bounded edge interval;
        # removing a prefix/suffix of telemetry cannot silently pass replay.
        require(abs(covered - elapsed_seconds) <= MAX_SAMPLE_GAP_SECONDS,
                'CAMPAIGN_WATCHDOG_COVERAGE')
