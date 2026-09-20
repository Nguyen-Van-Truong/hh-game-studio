"""S129 passive top-launcher observation. No Job, termination, restart or engine API.

Reuses S106's retained process handle / wait / exit observation sequence.
The exact native CloseHandle BOOL is additional evidence, not workload cleanup.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
REVIEWS = BASE.parent
HH3D = REVIEWS.parent.parent
SCHEMA = 'HH-S129-PASSIVE-REQUEST-1'
FILES = ('passive_observer.py', 'controller_probe.py', 'validate_supervision.py', 'prepare_task.ps1')


class ObserverError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class RetainedPopen(subprocess.Popen):
    def __del__(self):
        # An explicitly released live handle must never be polled by Popen's
        # destructor. This flag records ownership release, never an exit code.
        if not getattr(self, '_s129_native_handle_released', False):
            super().__del__()


def need(value, code):
    if not value:
        raise ObserverError(code)


def error_record(error):
    return {'type': type(error).__name__,
            'code': error.code if isinstance(error, ObserverError) else 'S129_OBSERVER_EXCEPTION',
            'native_error_number': getattr(error, 'winerror', None) or getattr(error, 'errno', None)}


def utc():
    return datetime.now(timezone.utc).isoformat()


def plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'S129_REPARSE')
    return path


def sha(path):
    return hashlib.sha256(plain(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write(path, value):
    raw = canonical(value) + b'\n'
    with plain(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(path.read_bytes() == raw, 'S129_WRITE_READBACK')


def own_pins():
    return {name: sha(BASE / name) for name in FILES}


@lru_cache(maxsize=1)
def kernel():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.WaitForSingleObject.argtypes, k.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    k.GetExitCodeProcess.argtypes, k.GetExitCodeProcess.restype = [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL
    k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    k.GetProcessTimes.restype = w.BOOL
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    k.QueryFullProcessImageNameW.restype = w.BOOL
    k.CloseHandle.argtypes, k.CloseHandle.restype = [w.HANDLE], w.BOOL
    return k


def identity(handle, pid):
    k = kernel()
    times = [w.FILETIME() for _ in range(4)]
    need(k.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)), 'S129_PROCESS_TIMES')
    size = w.DWORD(32768)
    image = ctypes.create_unicode_buffer(size.value)
    need(k.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)), 'S129_PROCESS_IMAGE')
    return {'pid': pid, 'process_start': 'windows:' + str(times[0].dwLowDateTime | times[0].dwHighDateTime << 32),
            'executable': str(Path(image.value).absolute())}


def observe_exit(handle, expected):
    k = kernel()
    wait = int(k.WaitForSingleObject(handle, 0))
    need(wait in (0, 258), 'S129_WAIT_FAILED')
    if wait == 258:
        return None
    # The executable was checked while alive. QueryFullProcessImageName can
    # fail after exit; the same retained handle + creation FILETIME bind exit.
    times = [w.FILETIME() for _ in range(4)]
    need(k.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)), 'S129_EXIT_TIMES')
    started = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
    exited = times[1].dwLowDateTime | times[1].dwHighDateTime << 32
    need(expected['process_start'] == 'windows:' + str(started) and exited >= started, 'S129_EXIT_IDENTITY')
    code = w.DWORD()
    need(k.GetExitCodeProcess(handle, ctypes.byref(code)), 'S129_EXIT_QUERY')
    return {'exit_code_uint32': int(code.value), 'exit_filetime': exited, 'observed_utc': utc(), 'wait_result': wait,
            'source': 'retained_handle_GetExitCodeProcess', 'natural_exit_inferred': False}


def close_popen(process):
    # CPython's Handle.Close marks closed before checking the native result.
    # Keep this exact object and suppress destructor retry while uncertain.
    need(isinstance(process, RetainedPopen) or type(process.returncode) is int, 'S129_LIVE_CLOSE_REQUIRES_DESTRUCTOR_GUARD')
    handle = process._handle
    need(not handle.closed, 'S129_HANDLE_ALREADY_CLOSED')
    handle.closed = True
    ok = bool(kernel().CloseHandle(int(handle)))
    if not ok:
        handle.closed = False
        raise OSError(ctypes.get_last_error(), 'S129_CLOSE_HANDLE_FAILED')
    process._s129_native_handle_released = True
    return {'native_close_bool_observed': True, 'native_close_succeeded': True,
            'process_handle_closed': True, 'observed_utc': utc()}


def make_request(run_id, launcher, arguments, *, cwd=BASE, observation_seconds=15, scheduler_seconds=60,
                 source_files=None):
    console = Path(sys.executable).absolute().with_name('python.exe')
    argv = [str(console), '-B', str(Path(launcher).absolute()), *arguments]
    return {'schema': SCHEMA, 'run_id': run_id, 'argv': argv, 'argv_sha256': digest(argv),
            'cwd': str(Path(cwd).absolute()), 'python_sha256': sha(console), 'launcher_sha256': sha(Path(launcher)),
            'observer_sha256': sha(Path(__file__)), 'observation_seconds': observation_seconds,
            'scheduler_seconds': scheduler_seconds, 'source_files': dict(source_files or {}),
            'formal_acceptance': False, 'eligible_for_dataset': False}


def validate_request(request):
    fields = {'schema', 'run_id', 'argv', 'argv_sha256', 'cwd', 'python_sha256', 'launcher_sha256',
              'observer_sha256', 'observation_seconds', 'scheduler_seconds', 'source_files',
              'formal_acceptance', 'eligible_for_dataset'}
    need(type(request) is dict and set(request) == fields and request['schema'] == SCHEMA, 'S129_REQUEST_SCHEMA')
    need(type(request['run_id']) is str and re.fullmatch(r'gt06-s129-[a-z0-9-]{1,45}', request['run_id']), 'S129_RUN_ID')
    argv = request['argv']
    need(type(argv) is list and 3 <= len(argv) <= 24 and all(type(v) is str and len(v) <= 4096 and '\0' not in v for v in argv), 'S129_ARGV')
    console = Path(sys.executable).absolute().with_name('python.exe')
    launcher = plain(argv[2])
    need(argv[0] == str(console) and argv[1] == '-B' and launcher.suffix == '.py'
         and launcher.is_relative_to(REVIEWS) and Path(argv[2]).is_absolute(), 'S129_FIXED_PYTHON_REVIEW_LAUNCHER')
    cwd = plain(request['cwd'])
    need(cwd in (BASE, HH3D, HH3D.parent) and cwd.is_dir() and digest(argv) == request['argv_sha256'], 'S129_ARGV_BINDING')
    need(type(request['observation_seconds']) is int and 1 <= request['observation_seconds'] <= 86400, 'S129_OBSERVATION_BOUND')
    need(type(request['scheduler_seconds']) is int and request['observation_seconds'] < request['scheduler_seconds'] <= 86400,
         'S129_SCHEDULER_BOUND')
    need(type(request['source_files']) is dict, 'S129_SOURCE_FILES')
    for name, expected in request['source_files'].items():
        path = plain(name)
        need(Path(name).is_absolute() and path.is_relative_to(HH3D) and sha(path) == expected, 'S129_CLOSURE_PIN')
    need(request['formal_acceptance'] is False and request['eligible_for_dataset'] is False, 'S129_DIAGNOSTIC_ONLY')
    need(sha(console) == request['python_sha256'] and sha(launcher) == request['launcher_sha256']
         and sha(Path(__file__)) == request['observer_sha256'], 'S129_SOURCE_PIN')
    return request


def observe(request, *, fixture_hook=None):
    """Library entry; fixture_hook is used only by the owned no-engine harness.

    Timeout closes observation handles without killing any workload. Absence of
    a terminal record when this observer is lost remains UNKNOWN.
    """
    validate_request(request)
    output = plain(BASE / 'runs' / request['run_id'])
    output.parent.mkdir(exist_ok=True)
    output.mkdir(exist_ok=False)
    write(output / 'request.json', request)
    process = None
    actual = start = close = None
    errors = []
    began = time.monotonic()
    with (output / 'stdout.txt').open('xb') as stdout, (output / 'stderr.txt').open('xb') as stderr:
        try:
            process = RetainedPopen(request['argv'], cwd=request['cwd'], stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
            handle = int(process._handle)
            start = identity(handle, process.pid)
            need(Path(start['executable']) == Path(request['argv'][0]), 'S129_LAUNCH_IMAGE')
            write(output / 'launcher-start.json', {'identity': start, 'argv_sha256': request['argv_sha256'],
                'request_sha256': sha(output / 'request.json'), 'handle_retained': True,
                'observer_pid': os.getpid(), 'observed_utc': utc()})
            if fixture_hook is not None:
                fixture_hook(process, start, output)
            while actual is None:
                actual = observe_exit(handle, start)
                if actual is not None:
                    break
                need(time.monotonic() - began < request['observation_seconds'], 'S129_OBSERVATION_TIMEOUT_WORKLOAD_UNCHANGED')
                time.sleep(.1)
            process.wait(timeout=1)
            need((process.returncode & 0xffffffff) == actual['exit_code_uint32'], 'S129_EXIT_DOUBLE_READBACK')
            write(output / 'launcher-exit.json', {'identity': start, 'actual_exit': actual,
                'argv_sha256': request['argv_sha256'], 'observer_forced_launcher': False})
            validate_request(request)
        except BaseException as error:
            errors.append(error_record(error))
        finally:
            if process is not None:
                try:
                    close = close_popen(process)
                    write(output / 'handle-close.json', close)
                except BaseException as error:
                    errors.append(error_record(error))
    terminal = {'schema': 'HH-S129-PASSIVE-TERMINAL-1', 'run_id': request['run_id'],
        'identity': start, 'actual_exit': actual, 'handle_close': close, 'errors': errors,
        'status': 'EXIT_OBSERVED' if actual is not None and not errors else 'UNKNOWN_OR_OBSERVER_ERROR',
        'elapsed_seconds': time.monotonic() - began, 'observed_utc': utc(),
        'observer_actual_exit_not_yet_observed': True, 'child_cleanup_not_inferred': True,
        'observer_lost_or_receipt_missing_means_unknown': True, 'no_poweroff_coverage': True,
        'formal_acceptance': False, 'eligible_for_dataset': False}
    write(output / 'terminal.json', terminal)
    return terminal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    request_path = plain(args.request)
    need(request_path.parent == BASE and request_path.suffix == '.json', 'S129_LOCAL_REQUEST_REQUIRED')
    request = validate_request(json.loads(request_path.read_bytes()))
    if args.check:
        print(json.dumps({'checked': True, 'request_sha256': sha(request_path), 'run_id': request['run_id'],
                          'argv_sha256': request['argv_sha256'], 'launched': False}))
        return 0
    result = observe(request)
    if result['errors'] or result['actual_exit'] is None:
        return 1
    return result['actual_exit']['exit_code_uint32']


if __name__ == '__main__':
    raise SystemExit(main())
