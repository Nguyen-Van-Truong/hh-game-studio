"""Bounded Python-only Win32 Job ordering experiment. No engine or profile edits."""
from __future__ import annotations
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import benchmark_job as bj

HELPER = '''import pathlib,sys,time
end=time.thread_time()+0.10
while time.thread_time()<end: pass
pathlib.Path(sys.argv[1]).write_text('READY',encoding='ascii')
assert sys.stdin.readline() == 'GO\\n'
'''

def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')

def one(out, *, before, host):
    name = ('before' if before else 'after') + ('-host' if host else '-editor')
    lane = out / name
    lane.mkdir()
    native = bj.cli_job._Native()
    # A private native owner is sufficient: this probe never creates descendants.
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD]
    kernel.SetInformationJobObject.restype = w.BOOL
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    kernel.QueryInformationJobObject.restype = w.BOOL
    handle, process = None, None
    data = {'lane': name, 'authority': 0, 'engine_launched': False,
            'formal_acceptance': False, 'events': [], 'cleanup': {}}
    limits = native.ExtendedLimit()
    limits.basic.flags = 0x2000 | 0x200 | 0x8 | 0x4
    limits.basic.active_limit = bj.owner_profile(host)['process_limit']
    limits.basic.job_time = bj.PROFILE['cpu_seconds'] * 10_000_000
    limits.job_memory = bj.PROFILE['memory_bytes']
    def query(stage):
        observed, size = native.ExtendedLimit(), w.DWORD()
        native._checked(kernel.QueryInformationJobObject(handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), ctypes.byref(size)), 'QueryLimits')
        accounting, accounting_size = native.Accounting(), w.DWORD()
        native._checked(kernel.QueryInformationJobObject(handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), ctypes.byref(accounting_size)), 'QueryAccounting')
        assert size.value == ctypes.sizeof(observed)
        assert accounting_size.value == ctypes.sizeof(accounting)
        row = {'stage': stage, 'job_time': observed.basic.job_time,
               'requested_job_time': limits.basic.job_time,
               'delta': observed.basic.job_time - limits.basic.job_time,
               'job_user_time': accounting.user_time, 'job_kernel_time': accounting.kernel_time,
               'active': accounting.active_processes, 'flags': observed.basic.flags,
               'active_limit': observed.basic.active_limit, 'memory': observed.job_memory}
        data['events'].append(row)
        return row
    def set_limits():
        native._checked(kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)), 'SetLimits')
    try:
        handle = native.create()
        native.configure(handle)
        if before:
            set_limits()
            query('configured_empty')
        ready = lane / 'ready.txt'
        with (lane / 'stdout.txt').open('xb') as stdout, (lane / 'stderr.txt').open('xb') as stderr:
            process = subprocess.Popen([sys.executable, '-B', '-c', HELPER, str(ready)],
                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            data['pid'] = process.pid
            deadline = time.monotonic() + 5
            while not ready.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('HELPER_READY_FAILED')
                time.sleep(.01)
            native.assign(handle, process)
            query('assigned_ready_before_set' if not before else 'assigned_ready')
            if not before:
                for index in range(3):
                    set_limits()
                    query('set_after_assignment_' + str(index))
            process.stdin.write(b'GO\n')
            process.stdin.close()
            data['actual_exit'] = process.wait(timeout=5)
            query('after_natural_exit')
    except BaseException as error:
        data['error'] = type(error).__name__ + ':' + str(error)
    finally:
        if handle:
            try:
                if native.active_count(handle):
                    native.terminate(handle)
                deadline = time.monotonic() + 3
                while native.active_count(handle) and time.monotonic() < deadline:
                    time.sleep(.01)
                data['cleanup']['job_active'] = native.active_count(handle)
                native.close(handle)
                data['cleanup']['native_job_close'] = True
            except BaseException as error:
                data['cleanup']['error'] = type(error).__name__
        if process:
            if process.poll() is None:
                process.kill()
            data['cleanup']['actual_exit'] = process.wait(timeout=3)
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            owned_handle = process._handle
            if bj.close_process_handle_native(int(owned_handle)):
                owned_handle.closed = True
                data['cleanup']['native_process_close'] = True
    write(lane / 'result.json', data)
    return data

def main():
    out = BASE / sys.argv[1]
    out.mkdir(exist_ok=False)
    rows = [one(out, before=before, host=host) for host in (False, True) for before in (False, True)]
    clean = all(not row.get('error') and row.get('actual_exit') == 0
                and row['cleanup'] == {'job_active': 0, 'native_job_close': True, 'actual_exit': 0, 'native_process_close': True}
                for row in rows)
    write(out / 'summary.json', {'schema': 'S131.job-order-probe.1', 'authority': 0,
          'observed_utc': datetime.now(timezone.utc).isoformat(), 'clean': clean,
          'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          'engine_launched': False, 'formal_acceptance': False, 'rows': rows})
    print(json.dumps({'clean': clean, 'rows': [{'lane': r['lane'], 'events': r['events'], 'exit': r.get('actual_exit'), 'cleanup': r['cleanup']} for r in rows]}, indent=2))
    return 0 if clean else 1

if __name__ == '__main__':
    raise SystemExit(main())
