"""Bounded supplemental self-process memory observation; never a benchmark gate.

Allocates 32 MiB, touches every page, idles, then touches the same pages again.
No foreign process handles, working-set edits, tracing or OS configuration.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import sys
import time


class Memory(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('faults', w.DWORD),
                ('peak_working_set', ctypes.c_size_t), ('working_set', ctypes.c_size_t),
                ('peak_paged', ctypes.c_size_t), ('paged', ctypes.c_size_t),
                ('peak_nonpaged', ctypes.c_size_t), ('nonpaged', ctypes.c_size_t),
                ('pagefile', ctypes.c_size_t), ('peak_pagefile', ctypes.c_size_t),
                ('private_usage', ctypes.c_size_t)]


class SystemMemory(ctypes.Structure):
    _fields_ = [('length', w.DWORD), ('load', w.DWORD)] + [
        (name, ctypes.c_ulonglong) for name in (
            'total_physical', 'available_physical', 'total_pagefile',
            'available_pagefile', 'total_virtual', 'available_virtual', 'extended')]


def main():
    if os.name != 'nt' or len(sys.argv) != 2:
        raise SystemExit('Windows and one exclusive output path required')
    destination = Path(sys.argv[1]).absolute()
    if destination.exists() or not destination.parent.is_dir():
        raise SystemExit('Output must not exist; parent must exist')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], w.HANDLE
    kernel.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(SystemMemory)]
    kernel.GlobalMemoryStatusEx.restype = w.BOOL
    psapi.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]
    psapi.GetProcessMemoryInfo.restype = w.BOOL
    handle = kernel.GetCurrentProcess()  # Pseudo-handle: no CloseHandle ownership.
    started = time.perf_counter()
    rows = []

    def sample(phase):
        memory, system = Memory(), SystemMemory()
        memory.cb, system.length = ctypes.sizeof(memory), ctypes.sizeof(system)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel.GlobalMemoryStatusEx(ctypes.byref(system)):
            raise ctypes.WinError(ctypes.get_last_error())
        rows.append({'phase': phase, 'elapsed_s': time.perf_counter() - started,
                     'working_set_bytes': int(memory.working_set),
                     'private_usage_bytes': int(memory.private_usage),
                     'page_fault_count': int(memory.faults),
                     'available_physical_bytes': int(system.available_physical),
                     'system_load_percent': int(system.load)})

    sample('before_allocation')
    payload = bytearray(32 * 1024 * 1024)
    for phase, seconds, active in (('active', 5, True), ('idle', 90, False),
                                    ('wake', 5, True)):
        until = time.perf_counter() + seconds
        while time.perf_counter() < until:
            if active:
                for index in range(0, len(payload), 4096):
                    payload[index] = (payload[index] + 1) & 255
            sample(phase)
            time.sleep(min(1.0, max(0.0, until - time.perf_counter())))
    sample('complete_same_allocation')
    result = {'schema': 'HH-GT06-S74-RESIDENCY-DIAGNOSTIC-1', 'pid': os.getpid(),
              'allocation_bytes': len(payload), 'memory_struct_bytes': ctypes.sizeof(Memory),
              'observations': rows, 'formal_acceptance': False,
              'scope': 'Supplemental self-process observation only; not Godot or benchmark evidence.'}
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    print('HH_RESIDENCY_COMPLETE ' + json.dumps({'samples': len(rows),
          'elapsed_s': rows[-1]['elapsed_s'], 'formal_acceptance': False}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
