"""Offline Windows Job readback probe; never launches Godot or native fixture."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import benchmark_job as bj
from studio.host.blender import ui_host

def one(index):
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(5)'],
                               creationflags=subprocess.CREATE_NO_WINDOW)
    owner = None
    record = {'index': index, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'requested_job_time': bj.PROFILE['cpu_seconds'] * 10_000_000,
              'requested_flags': 0x2000 | 0x200 | 0x8 | 0x4,
              'requested_active_limit': bj.HOST_PROFILE['process_limit'],
              'requested_memory': bj.PROFILE['memory_bytes']}
    try:
        owner = ui_host.cli_job.create(process)
        limits = owner._native.ExtendedLimit()
        limits.basic.flags = record['requested_flags']
        limits.basic.active_limit = record['requested_active_limit']
        limits.basic.job_time = record['requested_job_time']
        limits.job_memory = record['requested_memory']
        kernel = owner._native.kernel
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD]
        kernel.SetInformationJobObject.restype = w.BOOL
        kernel.QueryInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
        kernel.QueryInformationJobObject.restype = w.BOOL
        if not kernel.SetInformationJobObject(owner._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ctypes.WinError(ctypes.get_last_error())
        observed, size = owner._native.ExtendedLimit(), w.DWORD()
        if not kernel.QueryInformationJobObject(owner._handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        record.update({'actual_size': int(size.value), 'expected_size': ctypes.sizeof(observed),
                       'observed_job_time': int(observed.basic.job_time),
                       'observed_flags': int(observed.basic.flags),
                       'observed_active_limit': int(observed.basic.active_limit),
                       'observed_memory': int(observed.job_memory),
                       'delta_job_time': int(observed.basic.job_time) - record['requested_job_time'],
                       'status': 'OBSERVED'})
    except BaseException as error:
        record.update({'status': 'ERROR', 'error': type(error).__name__ + ':' + str(error)})
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                record['cleanup_error'] = type(error).__name__ + ':' + str(error)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=3)
        record['owner'] = owner.snapshot() if owner is not None else None
        record['process_exit'] = process.returncode
        record['ended_utc'] = datetime.now(timezone.utc).isoformat()
    return record

def main():
    rows = [one(i) for i in range(5)]
    out = Path(__file__).with_name('job-readback-probe.json')
    out.write_text(json.dumps({'authority': 0, 'engine_launched': False, 'rows': rows}, indent=2) + '\n', encoding='utf-8')
    print(out.read_text(encoding='utf-8'))

if __name__ == '__main__':
    main()
