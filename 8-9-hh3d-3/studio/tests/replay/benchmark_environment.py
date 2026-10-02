"""O4 environment observation. May stop a run; never grants measurement PASS.

The observer lives in the campaign supervisor, outside the measured host Job.
Unknown attribution fails closed. No process is stopped by name or PID.
"""
from __future__ import annotations

import ctypes
import base64
from ctypes import wintypes as w
from datetime import datetime
import json
import os
import re
import subprocess
import time
import zlib

from studio.tests.replay.benchmark_job import BenchmarkJobError, require
from studio.tests.replay.benchmark_docker_inventory import query_containers, InventoryError

# O8.1: only the executor's owned-container naming contract blocks a formal
# campaign. Other hh-* containers may belong to a different local project;
# they remain in the inventory for evidence and are handled by CPU/RAM
# watchdogs. Inventory/query errors remain fail-closed in running_containers.
STUDIO_CONTAINER_RE = re.compile(r'^hh-gt03-[0-9a-f]{32}$')

GIB = 1024**3
INTERVAL_SECONDS = 5
# O9.1c: a mandatory sample stream may be absent for less than 30 seconds;
# only a longer continuous gap is a harness failure. The normal poll cadence
# remains five seconds and O1 product timeouts are unchanged.
MAX_SAMPLE_GAP_SECONDS = 30
SCHEMA = 'hh-studio.benchmark-environment-preflight'
VERSION = '1.2.0'
SAMPLE_STREAM_SCHEMA = 'HH-GT06-WATCHDOG-SAMPLE-STREAM-3'


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
    k.GetProcessTimes.argtypes = [w.HANDLE, ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME),
                                  ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME)]
    k.GetProcessTimes.restype = w.BOOL
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


def running_containers(processes):
    """Fresh read-only inventory from the fixed local Docker Desktop pipe.

    Bypass CLI startup, never the daemon or its current response. The same
    two-second total budget and fail-closed unknown semantics apply. No retry
    is allowed after malformed output or unverified native cleanup.
    """
    if not any('docker' in row['name'].lower() for row in processes):
        return []
    started = time.monotonic()
    total_budget = 2.0
    deadline = started + total_budget
    # A timed-out _io may drain once, and owner.close() may need a second
    # bounded drain when the first completion is unverified. Reserve both
    # 250 ms cleanup windows plus scheduler margin inside the same absolute
    # observer budget so a second timeout cannot report after t0+2 s.
    cleanup_reserve = 0.6
    operation_deadline = deadline - cleanup_reserve
    diagnostic = None
    for attempt in range(1, 3):
        if time.monotonic() >= operation_deadline:
            break
        try:
            # Retries reuse one absolute operation cutoff. A quick transient
            # failure can retry, but a full timeout leaves only cleanup grace
            # and cannot start another read.
            names = query_containers(operation_deadline)
        except InventoryError as error:
            diagnostic = {'reason': error.reason, 'attempt': attempt}
            if type(error.detail) is int:
                diagnostic['returncode' if error.reason == 'nonzero' else 'errno'] = error.detail
            if not error.retryable:
                break
        else:
            if time.monotonic() >= operation_deadline:
                diagnostic = {'reason': 'timeout', 'attempt': attempt}
                break
            return names
    diagnostic = diagnostic or {'reason': 'timeout', 'attempt': 1}
    diagnostic['elapsed_seconds'] = round(max(0, time.monotonic() - started), 6)
    error = BenchmarkJobError('WATCHDOG_DOCKER_INVENTORY')
    error.docker_inventory = diagnostic
    raise error from None


def foreign_container_names(containers):
    """Return only studio-owned GT03 names that block a formal campaign."""
    require(type(containers) is list and all(type(name) is str for name in containers),
            'DOCKER_INVENTORY_SHAPE')
    return [name for name in containers if STUDIO_CONTAINER_RE.fullmatch(name)]


SYSTEM_PROCESS_INFORMATION = 5
STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
NTQSI_INITIAL_BYTES = 256 * 1024
NTQSI_MAX_BYTES = 64 * 1024 * 1024
_REQUIRE_DOCKER_INVENTORY = object()


class _SystemProcessInformationPrefix(ctypes.Structure):
    """Stable x64 prefix of SYSTEM_PROCESS_INFORMATION.

    NtQuerySystemInformation returns a variable-length record chain.  We only
    read fields documented by the stable prefix; no process image string or
    variable tail is dereferenced.  A non-x64 interpreter is rejected rather
    than guessing offsets for the protected-process watchdog path.
    """
    _fields_ = [
        ('next_entry_offset', ctypes.c_ulong),
        ('thread_count', ctypes.c_ulong),
        ('working_set_private', ctypes.c_longlong),
        ('hard_fault_count', ctypes.c_ulong),
        ('thread_count_high_watermark', ctypes.c_ulong),
        ('cycle_time', ctypes.c_ulonglong),
        ('create_time', ctypes.c_longlong),
        ('user_time', ctypes.c_longlong),
        ('kernel_time', ctypes.c_longlong),
        ('image_name_length', ctypes.c_ushort),
        ('image_name_maximum_length', ctypes.c_ushort),
        ('image_name_buffer', ctypes.c_void_p),
        ('base_priority', ctypes.c_long),
        ('unique_process_id', ctypes.c_void_p),
        ('inherited_process_id', ctypes.c_void_p),
    ]


def _parse_nt_process_information(raw, target_pids=None):
    """Parse a bounded NT process-record chain into cumulative CPU counters."""
    require(type(raw) in (bytes, bytearray), 'WATCHDOG_NTQSI_SHAPE')
    require(ctypes.sizeof(ctypes.c_void_p) == 8
            and ctypes.sizeof(_SystemProcessInformationPrefix) == 96,
            'WATCHDOG_NTQSI_PLATFORM')
    target = None if target_pids is None else set(target_pids)
    require(target is None or all(type(pid) is int and pid > 0 for pid in target),
            'WATCHDOG_NTQSI_PID')
    size = ctypes.sizeof(_SystemProcessInformationPrefix)
    found, offset, visited = {}, 0, set()
    while True:
        require(offset not in visited and offset + size <= len(raw), 'WATCHDOG_NTQSI_SHAPE')
        visited.add(offset)
        record = _SystemProcessInformationPrefix.from_buffer_copy(raw, offset)
        pid = int(record.unique_process_id or 0)
        require(record.create_time >= 0 and record.user_time >= 0 and record.kernel_time >= 0,
                'WATCHDOG_NTQSI_SHAPE')
        if target is None or pid in target:
            require(pid not in found, 'WATCHDOG_NTQSI_SHAPE')
            found[pid] = {
                'cpu_total_100ns': int(record.user_time + record.kernel_time),
                'process_start_100ns': int(record.create_time),
                'cpu_source': 'NtQuerySystemInformation'}
        next_offset = int(record.next_entry_offset)
        if next_offset == 0:
            break
        require(next_offset >= size and next_offset % 8 == 0
                and offset + next_offset <= len(raw), 'WATCHDOG_NTQSI_SHAPE')
        offset += next_offset
    if target is not None:
        require(target <= set(found), 'WATCHDOG_NTQSI_MISSING')
    return found


def _nt_process_times(target_pids=None):
    """Read process CPU counters with one kernel API snapshot.

    ``target_pids`` is retained for the compatibility helper used by older
    callers.  The in-measure watchdog passes ``None`` so one
    NtQuerySystemInformation call supplies CPU counters for every process in
    the sample, including protected ``vmmem``/Docker/WSL processes, without
    opening a process handle for CPU accounting.
    """
    require(os.name == 'nt', 'WATCHDOG_NTQSI_PLATFORM')
    if target_pids is not None:
        require(all(type(pid) is int and pid > 0 for pid in target_pids),
                'WATCHDOG_NTQSI_PID')
    ntdll = ctypes.WinDLL('ntdll', use_last_error=True)
    query = ntdll.NtQuerySystemInformation
    query.argtypes = [w.ULONG, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
    query.restype = ctypes.c_long
    size = NTQSI_INITIAL_BYTES
    for _attempt in range(9):
        buffer = (ctypes.c_ubyte * size)()
        returned = w.ULONG()
        status = ctypes.c_ulong(query(SYSTEM_PROCESS_INFORMATION, buffer, size,
                                      ctypes.byref(returned))).value
        if status == 0:
            used = int(returned.value) or size
            require(0 < used <= size, 'WATCHDOG_NTQSI_SHAPE')
            return _parse_nt_process_information(bytes(buffer[:used]), target_pids)
        if status != STATUS_INFO_LENGTH_MISMATCH:
            error = BenchmarkJobError('WATCHDOG_NTQSI_QUERY')
            error.ntqsi = {'status': status}
            raise error from None
        requested = int(returned.value)
        next_size = max(size * 2, requested, size + 1)
        require(next_size <= NTQSI_MAX_BYTES, 'WATCHDOG_NTQSI_QUERY')
        size = next_size
    error = BenchmarkJobError('WATCHDOG_NTQSI_QUERY')
    error.ntqsi = {'status': STATUS_INFO_LENGTH_MISMATCH}
    raise error from None


def perf_process_times(processes):
    """Compatibility name for the protected-process kernel CPU lookup.

    The old implementation spawned PowerShell/PerfProc, which could block the
    in-measure watchdog.  Keep callers stable while making the lookup entirely
    in-process and kernel-backed through NtQuerySystemInformation.
    """
    missing = {row['pid'] for row in processes
               if row.get('cpu_total_100ns') is None
               and any(token in row.get('name', '').lower() for token in ('vmmem', 'docker', 'wsl'))}
    if not missing:
        return {}
    return _nt_process_times(missing)


def native_snapshot(processes, *, job_handle=None, heavy_names=frozenset(),
                    docker_inventory=_REQUIRE_DOCKER_INVENTORY):
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
        row = {'pid': pid, 'name': name, 'private_bytes': None,
               'cpu_total_100ns': None, 'process_start_100ns': None, 'owned': False}
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
            # CPU and process-start counters deliberately come only from the
            # single NTQSI snapshot below. A process that exits between the
            # Toolhelp and NTQSI snapshots remains unknown for this sample;
            # it is never filled with a fabricated zero or a second handle
            # query that would violate O9.1a's source binding.
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
    # O9.1a: exactly one kernel process-information snapshot supplies the CPU
    # counters for every process in this sample.  Keep the legacy
    # ``perf_process_times`` helper above for callers/tests that explicitly
    # request a bounded PID lookup; the measured watchdog never uses it.
    fallback = _nt_process_times(None)
    for row in rows:
        # The System Idle row has no usable creation timestamp; keep it as an
        # explicitly unknown sentinel rather than violating the CPU inventory
        # shape contract with a zero start time.
        if row['pid'] == 0:
            row['cpu_total_100ns'] = None
            row['process_start_100ns'] = None
        elif row['pid'] in fallback:
            row.update(fallback[row['pid']])
    docker_inventory_status = 'KNOWN'
    docker_inventory_error = None
    if docker_inventory is _REQUIRE_DOCKER_INVENTORY:
        containers = running_containers(processes)
    else:
        require(type(docker_inventory) is list and
                all(type(name) is str for name in docker_inventory),
                'DOCKER_INVENTORY_SHAPE')
        containers = list(docker_inventory)
        docker_inventory_status = 'DEFERRED'
    foreign.extend({'name': name, 'ownership': 'outside_campaign_job', 'kind': 'docker_container'}
                   for name in foreign_container_names(containers))
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
        # The watchdog derives interval CPU from these cumulative process
        # counters.  Keep the full bounded inventory so an external process
        # cannot disappear merely because it is small in private memory.
        'processes': rows,
        'running_containers': containers, 'docker_inventory_status': docker_inventory_status,
        'docker_inventory_error': docker_inventory_error,
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


def require_snapshot(result):
    """Validate the recorded inventory without applying launch-only limits."""
    require(type(result) is dict and result.get('schema_id') == SCHEMA
            and result.get('schema_version') == VERSION, 'CAMPAIGN_PREFLIGHT_SHAPE')
    require(type(result.get('heavy_processes')) is list
            and result.get('required_heavy_processes_closed') is False, 'CAMPAIGN_PREFLIGHT_APP_INVENTORY')
    require(type(result.get('foreign_engines')) is list, 'CAMPAIGN_PREFLIGHT_ENGINE_INVENTORY')
    available, total, limit = (result.get(key) for key in (
        'available_memory_bytes', 'commit_total_bytes', 'commit_limit_bytes'))
    require(type(available) is int and available >= 0 and type(total) is int and total >= 0
            and type(limit) is int and limit > 0, 'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')
    expected = preflight(result)
    require(type(result.get('pass')) is bool and result['pass'] == expected['pass'],
            'CAMPAIGN_PREFLIGHT_FOREIGN_ENGINE' if result['foreign_engines'] else 'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')


def require_preflight(result):
    require_snapshot(result)
    require(not result['foreign_engines'], 'CAMPAIGN_PREFLIGHT_FOREIGN_ENGINE')
    require(result['pass'], 'CAMPAIGN_PREFLIGHT_RESOURCE_LIMIT')


def cpu_interval(previous, row):
    """Process CPU as percent of total machine capacity, keyed by creation time.

    GetSystemTimes is summed across logical CPUs. Dividing process ticks by
    its delta avoids treating one busy core as 100% of a many-core machine.
    An inaccessible or newly observed process is unknown, never zero CPU.
    """
    processes = row.get('processes')
    require(type(processes) is list and len(processes) <= 65536,
            'WATCHDOG_CPU_INVENTORY')
    seen = set()
    for item in processes:
        require(type(item) is dict and type(item.get('pid')) is int and item['pid'] >= 0
                and item['pid'] not in seen and type(item.get('name')) is str
                and type(item.get('owned')) is bool, 'WATCHDOG_CPU_INVENTORY')
        seen.add(item['pid'])
        cpu, start = item.get('cpu_total_100ns'), item.get('process_start_100ns')
        require(cpu is None or (type(cpu) is int and cpu >= 0 and type(start) is int and start > 0),
                'WATCHDOG_CPU_INVENTORY')
    old = {(p['pid'], p.get('process_start_100ns')): p
           for p in previous['processes']} if previous is not None else {}
    total = row['cpu_total_100ns'] - previous['cpu_total_100ns'] if previous is not None else 0
    require(total >= 0, 'WATCHDOG_CPU_DELTA')
    intervals, unknown = [], []
    for item in processes:
        key = (item['pid'], item.get('process_start_100ns'))
        before = old.get(key)
        current_cpu = item.get('cpu_total_100ns')
        before_cpu = before.get('cpu_total_100ns') if before is not None else None
        if (item['pid'] == 0 or total == 0 or before is None or current_cpu is None
                or before_cpu is None or key[1] is None or before['owned'] != item['owned']):
            unknown.append(item['pid'])
            continue
        require(current_cpu >= before_cpu, 'WATCHDOG_PROCESS_CPU_REGRESSION')
        intervals.append({'pid': item['pid'], 'name': item['name'], 'owned': item['owned'],
                          'process_start_100ns': key[1],
                          'cpu_delta_100ns': current_cpu - before_cpu,
                          'interval_cpu_percent': 100 * (current_cpu - before_cpu) / total})
    intervals.sort(key=lambda p: (-p['interval_cpu_percent'], p['pid']))
    external_ticks = sum(p['cpu_delta_100ns'] for p in intervals if not p['owned'])
    external_percent = 100 * external_ticks / total if total else 0
    return {'basis': 'process_tick_delta_over_system_tick_delta',
            'system_delta_100ns': total, 'top_processes': intervals[:10],
            'hot_external_processes': [p for p in intervals
                                       if not p['owned'] and p['cpu_delta_100ns'] * 100 >= total * 50],
            'external_cpu_percent': external_percent,
            'unavailable_or_new_pids': unknown}


class Policy:
    """Replayable sampled policy; counters/measurement acceptance stay elsewhere."""
    def __init__(self):
        self.first = self.previous = None
        self.low_since = None
        self.external_cpu_since = None
        self.previous_observed = None

    def observe(self, row):
        require(type(row) is dict, 'WATCHDOG_SAMPLE_INVALID')
        required = {'observed_utc', 'heavy_processes', 'docker_wsl_processes',
                    'top_private_processes', 'owned_processes',
                    'unavailable_process_count'}
        require(required.issubset(row), 'WATCHDOG_SAMPLE_INVALID')
        for name in ('available_memory_bytes', 'commit_total_bytes', 'commit_limit_bytes',
                     'uptime_ms', 'awake_100ns', 'cpu_idle_100ns', 'cpu_total_100ns',
                     'owned_private_bytes', 'unavailable_process_count'):
            require(type(row.get(name)) is int and row[name] >= 0, 'WATCHDOG_SAMPLE_INVALID')
        require(row['commit_limit_bytes'] > 0 and type(row.get('foreign_engines')) is list
                and type(row.get('owned_inventory_complete')) is bool, 'WATCHDOG_SAMPLE_INVALID')
        for name in ('heavy_processes', 'docker_wsl_processes', 'top_private_processes',
                     'owned_processes'):
            require(type(row[name]) is list, 'WATCHDOG_SAMPLE_INVALID')
        require(type(row['observed_utc']) is str, 'WATCHDOG_SAMPLE_INVALID')
        try:
            observed = datetime.strptime(row['observed_utc'], '%Y-%m-%dT%H:%M:%SZ')
        except (TypeError, ValueError):
            raise BenchmarkJobError('WATCHDOG_SAMPLE_INVALID') from None
        require(self.previous_observed is None or observed >= self.previous_observed,
                'WATCHDOG_TIMESTAMP_REGRESSION')
        self.previous_observed = observed
        now = row['uptime_ms'] / 1000
        previous = self.previous
        cpu = cpu_interval(previous, row)
        if 'cpu_observation' in row:
            require(row['cpu_observation'] == cpu, 'WATCHDOG_CPU_OBSERVATION_MISMATCH')
        if self.first is None:
            self.first = row
        reasons = []
        classification = 'INFRA_ABORT'
        if previous is not None:
            elapsed = now - previous['uptime_ms'] / 1000
            awake_elapsed = (row['awake_100ns'] - previous['awake_100ns']) / 10_000_000
            require(elapsed >= 0 and awake_elapsed >= 0, 'WATCHDOG_CLOCK_REGRESSION')
            # Two Windows uptime clocks avoid false sleep detection from NTP.
            if elapsed - awake_elapsed > 0.1:
                reasons.append('SLEEP_RESUME')
            elif elapsed > MAX_SAMPLE_GAP_SECONDS:
                reasons.append('SAMPLE_GAP')
                classification = 'HARNESS_FAIL'
            total = row['cpu_total_100ns'] - previous['cpu_total_100ns']
            idle = row['cpu_idle_100ns'] - previous['cpu_idle_100ns']
            require(total >= 0 and 0 <= idle <= total, 'WATCHDOG_CPU_DELTA')
            # Sum all external process CPU. Tracking only the hottest PID
            # would miss two moderate processes crossing the O9 threshold.
            if cpu['external_cpu_percent'] >= 50:
                if self.external_cpu_since is None:
                    self.external_cpu_since = previous['uptime_ms'] / 1000
            else:
                self.external_cpu_since = None
        self.low_since = (self.low_since if self.low_since is not None else now) if row['available_memory_bytes'] < 1.5 * GIB else None
        if row['foreign_engines']:
            reasons.append('FOREIGN_ENGINE')
        if row['commit_total_bytes'] * 100 > row['commit_limit_bytes'] * 92:
            reasons.append('COMMIT_PRESSURE')
        if self.low_since is not None and now - self.low_since >= 60:
            reasons.append('AVAILABLE_PRESSURE')
        if self.external_cpu_since is not None and now - self.external_cpu_since >= 60:
            reasons.append('EXTERNAL_CPU_PRESSURE')
        product_pressure = []
        for pressure in ('COMMIT_PRESSURE', 'AVAILABLE_PRESSURE'):
            if pressure not in reasons:
                continue
            # Do not claim a causal leak from correlation. If the budget would
            # still be violated after subtracting ALL campaign private bytes,
            # external pressure is sufficient. Otherwise keep a product hold.
            owned = row['owned_private_bytes']
            external_sufficient = (row['commit_total_bytes'] - owned) * 100 > row['commit_limit_bytes'] * 92
            if pressure == 'AVAILABLE_PRESSURE':
                external_sufficient = row['available_memory_bytes'] + owned < 1.5 * GIB
            if not (row['owned_inventory_complete'] and external_sufficient):
                product_pressure.append(pressure)
        # A simultaneous foreign engine, sleep or sampling gap cannot mask
        # product memory pressure. Preserve every trigger for later review.
        if product_pressure:
            classification = 'PRODUCT_FAIL'
        reason = product_pressure[0] if product_pressure else (reasons[0] if reasons else None)
        self.previous = row
        return None if reason is None else {
            'reason': reason, 'reasons': reasons, 'classification': classification, 'formal_acceptance': False,
            'top_cpu_processes': cpu['top_processes'],
            'attribution': ('external_pressure_sufficient_without_campaign_private'
                            if reason in ('COMMIT_PRESSURE', 'AVAILABLE_PRESSURE') and classification == 'INFRA_ABORT'
                            else 'no_product_failure_is_waived')}


def pack_sample(row):
    """Lossless bounded CPU inventory encoding; top-ten remains plain JSON."""
    processes = row.get('processes')
    if type(processes) is not list or len(processes) <= 64:
        return row
    raw = json.dumps(processes, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    require(len(raw) <= 16 * 1024**2, 'WATCHDOG_CPU_INVENTORY_SIZE')
    packed = dict(row)
    del packed['processes']
    packed['process_inventory_zlib_b64'] = base64.b64encode(zlib.compress(raw)).decode('ascii')
    return packed


def unpack_sample(row):
    if 'process_inventory_zlib_b64' not in row:
        return row
    require('processes' not in row and type(row['process_inventory_zlib_b64']) is str,
            'WATCHDOG_CPU_ENCODING')
    try:
        packed = base64.b64decode(row['process_inventory_zlib_b64'], validate=True)
        decoder = zlib.decompressobj()
        raw = decoder.decompress(packed, 16 * 1024**2 + 1)
        require(len(raw) <= 16 * 1024**2 and decoder.eof and not decoder.unused_data
                and not decoder.unconsumed_tail, 'WATCHDOG_CPU_ENCODING')
        result = dict(row)
        del result['process_inventory_zlib_b64']
        result['processes'] = json.loads(raw)
        return result
    except (ValueError, zlib.error) as error:
        raise BenchmarkJobError('WATCHDOG_CPU_ENCODING') from error


class Watchdog:
    def __init__(self, output, sample, binding, write, *, docker_probe=None):
        self.output, self.sample, self.binding, self.write = output, sample, binding, write
        self.docker_probe = docker_probe
        self.docker_last = None
        self.docker_names = []
        self.policy, self.last, self.count = Policy(), None, 0
        require(type(binding) is dict and set(binding) == {
            'run_id', 'source_closure_sha256', 'campaign_sha256'}, 'WATCHDOG_BINDING')
        self.stream = (output / 'environment-samples.jsonl').open('xb')
        try:
            self._append({'schema': SAMPLE_STREAM_SCHEMA, **binding})
        except BaseException:
            self.stream.close()
            raise

    def _append(self, row):
        raw = (json.dumps(pack_sample(row), sort_keys=True, separators=(',', ':'),
                          allow_nan=False) + '\n').encode()
        require(self.stream.tell() + len(raw) <= 64 * 1024**2, 'WATCHDOG_SAMPLE_STREAM_FULL')
        self.stream.write(raw)
        self.stream.flush()
        os.fsync(self.stream.fileno())

    def _observer_failure(self, error, row=None):
        # Persist a bounded diagnostic and a stop latch before surfacing a
        # harness error. Never turn an observer/validation failure into a
        # product failure or silently drop the malformed sample.
        persistence_errors = []
        if row is not None:
            try:
                try:
                    self._append(row)
                    self.count += 1
                except (TypeError, ValueError):
                    self._append({'schema': 'HH-GT06-WATCHDOG-INVALID-SAMPLE-1',
                                  'exception_class': type(error).__name__})
                    self.count += 1
            except BaseException as persistence_error:
                persistence_errors.append('sample:' + type(persistence_error).__name__)
        event = {'schema': 'HH-GT06-WATCHDOG-OBSERVATION-ERROR-1', **self.binding,
                     'classification': 'HARNESS_FAIL', 'reason': 'OBSERVER_ERROR',
                     'exception_class': type(error).__name__,
                     'error_code': getattr(error, 'code', str(error))[:128],
                     'sample_index': self.count - 1 if self.count else None}
        for code, field in (('WATCHDOG_DOCKER_INVENTORY', 'docker_inventory'),
                            ('WATCHDOG_PERF_COUNTER_QUERY', 'perf_counter')):
            diagnostic = getattr(error, field, None)
            if (getattr(error, 'code', None) == code
                    and type(diagnostic) is dict
                    and diagnostic.get('reason') in ('timeout', 'nonzero', 'oserror', 'bad_output')
                    and type(diagnostic.get('attempt')) is int and 1 <= diagnostic['attempt'] <= 2
                    and type(diagnostic.get('elapsed_seconds')) in (int, float)
                    and 0 <= diagnostic['elapsed_seconds'] < float('inf')):
                event[field] = {name: diagnostic[name]
                    for name in ('reason', 'attempt', 'elapsed_seconds')}
                for name in ('errno', 'returncode'):
                    if type(diagnostic.get(name)) is int:
                        event[field][name] = diagnostic[name]
        ntqsi = getattr(error, 'ntqsi', None)
        if (getattr(error, 'code', None) == 'WATCHDOG_NTQSI_QUERY'
                and type(ntqsi) is dict and type(ntqsi.get('status')) is int
                and 0 <= ntqsi['status'] < 2**32):
            event['ntqsi'] = {'status': ntqsi['status']}
        stop = {'schema': 'HH-GT06-WATCHDOG-STOP-1', **self.binding,
                        'classification': 'HARNESS_FAIL', 'reason': 'OBSERVER_ERROR',
                        'formal_acceptance': False,
                        'sample_index': self.count - 1 if self.count else None}
        for name, payload in (('watchdog-observation-error.json', event), ('watchdog-stop.json', stop)):
            try:
                self.write(self.output / name, payload)
            except BaseException as persistence_error:
                persistence_errors.append(name + ':' + type(persistence_error).__name__)
        raised = BenchmarkJobError('CAMPAIGN_WATCHDOG_OBSERVER_ERROR')
        raised.classification = 'HARNESS_FAIL'
        raised.watchdog_persistence_errors = persistence_errors
        raise raised from error

    def poll(self, *, force=False):
        now = time.monotonic()
        if not force and self.last is not None and now - self.last < INTERVAL_SECONDS:
            return
        try:
            row = self.sample()
        except BaseException as error:
            self._observer_failure(error)
        if self.docker_probe is not None:
            try:
                row = self._poll_docker(row)
            except BaseException as error:
                self._observer_failure(error, row)
        persisted = False
        try:
            row['cpu_observation'] = cpu_interval(self.policy.previous, row)
            # Raw sample durability precedes policy interpretation.
            self._append(row)
            self.count += 1
            persisted = True
            decision = self.policy.observe(row)
        except BaseException as error:
            if isinstance(error, BenchmarkJobError) and getattr(error, 'code', '').startswith('CAMPAIGN_WATCHDOG_'):
                raise
            self._observer_failure(error, None if persisted else row)
        self.last = now
        if decision:
            event = {'schema': 'HH-GT06-WATCHDOG-STOP-1', **self.binding, **decision,
                     'sample_index': self.count - 1}
            try:
                self.write(self.output / 'watchdog-stop.json', event)
            except BaseException as error:
                self._observer_failure(error)
            error = BenchmarkJobError('CAMPAIGN_WATCHDOG_' + decision['reason'])
            error.classification = decision['classification']
            raise error

    def _poll_docker(self, row):
        """Poll Docker at most once per minute; an error is recorded as UNKNOWN.

        CPU, RAM, commit and sleep samples remain mandatory and continue even
        when the optional Docker pipe is slow or unavailable. A previously
        observed studio container remains conservatively visible until a
        later successful poll proves it gone.
        """
        now = time.monotonic()
        due = self.docker_last is None or now - self.docker_last >= 60
        if due:
            self.docker_last = now
            try:
                names = self.docker_probe(row.get('processes', []))
                require(type(names) is list and all(type(name) is str for name in names),
                        'DOCKER_INVENTORY_SHAPE')
                self.docker_names = list(names)
                row['docker_inventory_status'] = 'KNOWN'
                row['docker_inventory_error'] = None
            except Exception as error:
                row['docker_inventory_status'] = 'UNKNOWN'
                diagnostic = {'code': type(error).__name__}
                detail = getattr(error, 'docker_inventory', None)
                if type(detail) is dict:
                    diagnostic = {name: detail[name] for name in
                                  ('reason', 'attempt', 'elapsed_seconds', 'errno', 'returncode')
                                  if name in detail and type(detail[name]) in (str, int, float)}
                    diagnostic['code'] = getattr(error, 'code', type(error).__name__)
                row['docker_inventory_error'] = diagnostic
        else:
            row['docker_inventory_status'] = 'CACHED'
            row['docker_inventory_error'] = None
        row['running_containers'] = list(self.docker_names)
        foreign = [item for item in row.get('foreign_engines', [])
                   if item.get('kind') != 'docker_container']
        foreign.extend({'name': name, 'ownership': 'outside_campaign_job',
                        'kind': 'docker_container'}
                       for name in foreign_container_names(self.docker_names))
        row['foreign_engines'] = foreign
        return row

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


def verify_watchdog(output, read_regular, *, elapsed_seconds=None, expected_binding=None,
                    require_docker_inventory=False):
    require(not (output / 'watchdog-stop.json').exists(), 'CAMPAIGN_WATCHDOG_STOP_LATCHED')
    require(type(expected_binding) is dict and set(expected_binding) == {
            'run_id', 'source_closure_sha256', 'campaign_sha256'}, 'CAMPAIGN_WATCHDOG_BINDING')
    raw = read_regular(output / 'environment-samples.jsonl', 64 * 1024**2)
    lines = raw.splitlines()
    require(lines, 'CAMPAIGN_WATCHDOG_SAMPLES_MISSING')
    header = json.loads(lines[0])
    require(header == {'schema': SAMPLE_STREAM_SCHEMA, **expected_binding},
            'CAMPAIGN_WATCHDOG_BINDING')
    policy, count = Policy(), 0
    for line in lines[1:]:
        row = unpack_sample(json.loads(line))
        require('cpu_observation' in row, 'CAMPAIGN_WATCHDOG_CPU_OBSERVATION_MISSING')
        if require_docker_inventory:
            status = row.get('docker_inventory_status')
            require(status in ('KNOWN', 'CACHED', 'UNKNOWN'),
                    'CAMPAIGN_WATCHDOG_DOCKER_STATUS')
            require(type(row.get('running_containers')) is list and
                    all(type(name) is str for name in row['running_containers']),
                    'CAMPAIGN_WATCHDOG_DOCKER_STATUS')
            if status == 'UNKNOWN':
                require(type(row.get('docker_inventory_error')) is dict,
                        'CAMPAIGN_WATCHDOG_DOCKER_STATUS')
            else:
                require(row.get('docker_inventory_error') is None,
                        'CAMPAIGN_WATCHDOG_DOCKER_STATUS')
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
