"""Trusted native failure fixtures; no diagnostic mode is a remote operation."""
import ctypes
from ctypes import wintypes as w
import json
import threading
import time


def run(owner, prepared, output):
    from studio.host.blender import export_job as module
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [w.DWORD, w.BOOL, w.DWORD], w.HANDLE
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    kernel.GetExitCodeProcess.argtypes, kernel.GetExitCodeProcess.restype = [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    results = {}

    def paused(kind):
        job = module.ExportJob(owner, prepared, diagnostic='pause')
        errors = []; handle = None; stopped = None; elapsed = None
        budget = module.WALL_SECONDS
        if kind == 'deadline': module.WALL_SECONDS = 4
        else:
            with owner._export_lock:
                assert owner._export_job is None
                owner._export_job = job
        def execute():
            try: job.run()
            except BaseException as exc: errors.append(str(exc))
        thread = threading.Thread(target=execute)
        thread.start()
        try:
            ready_path = job.directory / 'fault-ready.json'
            deadline = time.monotonic() + 10
            while not ready_path.exists():
                if not thread.is_alive() or time.monotonic() >= deadline:
                    raise RuntimeError('export fault fixture did not reach native preflight')
                time.sleep(.005)
            ready = json.loads(ready_path.read_bytes())
            start = json.loads((job.directory / 'process-start.json').read_bytes())
            assert ready['pid'] == start['pid'] and ready['phase'] == 'validated-before-export'
            handle = kernel.OpenProcess(0x1000 | 0x100000, False, ready['pid'])
            assert handle and kernel.WaitForSingleObject(handle, 0) == 258
            if kind == 'stop':
                began = time.monotonic(); stopped = owner.stop(); elapsed = (time.monotonic() - began) * 1000
            thread.join(8)
            assert not thread.is_alive() and job.done.is_set() and not job.cleanup_held
            expected = 'EXPORT_DEADLINE' if kind == 'deadline' else 'EXPORT_CANCELLED'
            assert errors == [expected], errors
            assert kernel.WaitForSingleObject(handle, 1000) == 0
            native_exit = w.DWORD()
            assert kernel.GetExitCodeProcess(handle, ctypes.byref(native_exit))
            report = json.loads((job.directory / 'host-result.json').read_bytes())
            assert report['completed'] is False and report['failure'] == expected
            assert report['job']['closed'] and report['job']['zero_observed'] and report['job']['active_count'] == 0
            assert not (job.directory / 'output.glb').exists()
            if kind == 'stop': assert stopped == {'stopped': True, 'public_ack': False} and elapsed < 2000
            row = {'kind': kind, 'directory': job.directory.relative_to(output).as_posix(), 'failure': expected,
                   'fault_ready': ready, 'live_wait_before': 258, 'dead_wait_after': 0,
                   'actual_native_exit_code': native_exit.value, 'host_result': report,
                   'stop': stopped, 'stop_elapsed_ms': elapsed, 'public_ack': False}
            (output / (kind + '.json')).write_text(json.dumps(row, indent=2) + '\n', encoding='utf-8')
            return row
        finally:
            job.request_stop(); thread.join(5); module.WALL_SECONDS = budget
            if kind == 'stop' and job.done.is_set() and not job.cleanup_held:
                with owner._export_lock: owner._export_job = None
            if handle and not kernel.CloseHandle(handle): raise RuntimeError('fault native observer close failed')
            assert not thread.is_alive()

    results['deadline'] = paused('deadline')
    job = module.ExportJob(owner, prepared, diagnostic='oom')
    try: job.run()
    except Exception as exc: failure = str(exc)
    else: raise AssertionError('over-limit allocation unexpectedly passed')
    report = json.loads((job.directory / 'host-result.json').read_bytes())
    ready = json.loads((job.directory / 'fault-ready.json').read_bytes())
    assert failure == 'EXPORT_NATIVE_FAILED' and report['completed'] is False
    assert report['actual_process_exit'] == {'pid': ready['pid'], 'exit_code': 17}
    assert report['wrapper_exit_code'] == 17 and 'MemoryError' in (job.directory / 'stderr.txt').read_text()
    assert report['limits']['job_memory_bytes'] == 2 * 1024 ** 3
    assert report['job']['closed'] and report['job']['zero_observed'] and report['job']['active_count'] == 0
    assert not (job.directory / 'output.glb').exists() and job.done.is_set() and not job.cleanup_held
    results['oom'] = {'kind': 'oom', 'directory': job.directory.relative_to(output).as_posix(),
                      'fault_ready': ready, 'host_result': report, 'public_ack': False}
    (output / 'oom.json').write_text(json.dumps(results['oom'], indent=2) + '\n', encoding='utf-8')
    results['stop'] = paused('stop')
    return results
