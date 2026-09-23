"""S194 external sampler: independent process identity and handle counter only."""
from __future__ import annotations
import argparse, ctypes, datetime, hashlib, json, os, time
from ctypes import wintypes as w
from pathlib import Path

RUN_ID = 'gt06-s194-external-sampler-01'
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(path: Path, value) -> None:
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    if path.read_bytes() != raw:
        raise RuntimeError('S194_EVIDENCE_READBACK')

def api():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
    k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4; k.GetProcessTimes.restype = w.BOOL
    k.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]; k.GetProcessHandleCount.restype = w.BOOL
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]; k.QueryFullProcessImageNameW.restype = w.BOOL
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; k.WaitForSingleObject.restype = w.DWORD
    return k

def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument('--pid', type=int, required=True); p.add_argument('--expected-image', required=True)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--duration', type=float, default=105.0)
    a = p.parse_args(); out = a.out; out.mkdir(parents=True, exist_ok=False)
    k = api(); handle = None; opened = time.monotonic(); rows = 0; start = None
    write(out / 'sampler-start.json', {'run_id': RUN_ID, 'observer_pid': os.getpid(), 'target_pid': a.pid, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'duration_seconds': a.duration, 'sampler': 'external-process-OpenProcess-GetProcessHandleCount'})
    try:
        while handle is None and time.monotonic() - opened < 20:
            handle = k.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, a.pid)
            if not handle: time.sleep(.05); continue
            times = [w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)):
                raise ctypes.WinError(ctypes.get_last_error())
            start = 'windows:' + str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
            size, text = w.DWORD(32768), ctypes.create_unicode_buffer(32768)
            if not k.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            image = os.path.normcase(text.value)
            if image != os.path.normcase(os.path.abspath(a.expected_image)):
                raise RuntimeError('S194_IMAGE_IDENTITY')
        if not handle: raise RuntimeError('S194_TARGET_OPEN_TIMEOUT')
        with (out / 'samples.jsonl').open('x', encoding='utf-8') as log:
            while time.monotonic() - opened < a.duration:
                wait = k.WaitForSingleObject(handle, 0)
                if wait == 0: break
                if wait != 258: raise RuntimeError('S194_WAIT')
                count = w.DWORD()
                if not k.GetProcessHandleCount(handle, ctypes.byref(count)):
                    raise ctypes.WinError(ctypes.get_last_error())
                row = {'observer_pid': os.getpid(), 'target_pid': a.pid, 'target_process_start': start,
                       'mono_us': time.perf_counter_ns() // 1000, 'held_handles': int(count.value), 'sequence': rows}
                log.write(json.dumps(row, separators=(',', ':')) + '\n'); rows += 1
                if rows % 20 == 0: log.flush()
                time.sleep(.25)
        write(out / 'sampler-result.json', {'run_id': RUN_ID, 'target_pid': a.pid, 'target_process_start': start,
            'sample_count': rows, 'target_wait_zero': k.WaitForSingleObject(handle, 0) == 0,
            'samples_sha256': sha(out / 'samples.jsonl'), 'formal_acceptance': False})
        return 0
    except BaseException as e:
        write(out / 'sampler-failure.json', {'run_id': RUN_ID, 'error_type': type(e).__name__, 'message': str(e), 'sample_count': rows, 'formal_acceptance': False})
        return 1
    finally:
        if handle is not None:
            if not k.CloseHandle(handle):
                write(out / 'sampler-close-failure.json', {'winerror': ctypes.get_last_error()})

if __name__ == '__main__': raise SystemExit(main())
