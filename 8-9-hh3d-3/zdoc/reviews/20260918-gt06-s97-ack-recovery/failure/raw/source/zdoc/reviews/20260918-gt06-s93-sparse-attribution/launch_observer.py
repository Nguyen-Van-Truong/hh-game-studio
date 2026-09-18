"""Fixed, demand-only S91 scheduler observer. No benchmark acceptance authority.

The scheduler owns this observer. A gated child becomes the fixed supervisor
in the same PID only after assignment to a checked outer kill-on-close Job.
The outer Job allows seven processes; the original inner limits stay intact.
Retained process handles outlive inner Job termination and preserve actual
exit observations. Missing adoption/exit is reported as unknown, never zero.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
RUN_ID = 'gt06-s93-sparse-attribution-01'
HELPER = BASE / 'diagnose_sequence_s91.py'
LAUNCH = BASE / 'launch-01'
OUTPUT = STUDIO / '.local/reviews' / RUN_ID
WALL_SECONDS = 7530
OUTER_PROCESS_LIMIT = 7
HELPER_NAMES = ('launch_observer.py', 'register_task.ps1', 'diagnose_sequence_s91.py',
                'test_launch_observer.py')
sys.path.insert(0, str(ROOT))


def need(value, code):
    if not value:
        raise RuntimeError(code)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'OBSERVER_REPARSE')
    return path


def sha(path):
    path = plain(path)
    need(path.is_file(), 'OBSERVER_NOT_FILE')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path = plain(path)
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(path.read_bytes() == raw, 'OBSERVER_WRITE_READBACK')


def read(path):
    path = plain(path)
    need(path.is_file() and path.stat().st_size <= 65536, 'OBSERVER_JSON_SIZE')
    return json.loads(path.read_bytes())


def pins(console, windowed):
    lock = read(STUDIO / 'toolchain.lock.json')['godot']
    godot = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(sha(godot) == lock['gui_sha256'], 'OBSERVER_GODOT_PIN')
    return {'schema': 'HH-GT06-S91-OBSERVER-REQUEST-1', 'run_id': RUN_ID,
            'helper_files': {name: sha(BASE / name) for name in HELPER_NAMES},
            'python_sha256': sha(console), 'pythonw_sha256': sha(windowed),
            'godot_sha256': lock['gui_sha256'], 'working_directory': str(STUDIO),
            'wall_seconds': WALL_SECONDS, 'outer_process_limit': OUTER_PROCESS_LIMIT}, godot


def validate_request(request, expected):
    need(type(request) is dict and request == expected, 'OBSERVER_REQUEST_BINDING')


def native():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [w.HANDLE, w.DWORD], w.DWORD
    kernel.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.GetExitCodeProcess.restype = w.BOOL
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    return kernel


def process_times(kernel, handle):
    values = [w.FILETIME() for _ in range(4)]
    need(kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)), 'OBSERVER_PROCESS_TIMES')
    return [v.dwLowDateTime | v.dwHighDateTime << 32 for v in values]


def parent_pid(handle):
    # PROCESS_BASIC_INFORMATION's pointer-sized reserved layout is the Win32
    # documented query layout; its final pointer is the inherited parent PID.
    class Basic(ctypes.Structure):
        _fields_ = [('reserved1', ctypes.c_void_p), ('peb', ctypes.c_void_p),
                    ('reserved2', ctypes.c_void_p * 2), ('pid', ctypes.c_size_t),
                    ('parent', ctypes.c_size_t)]
    dll = ctypes.WinDLL('ntdll')
    dll.NtQueryInformationProcess.argtypes = [w.HANDLE, w.ULONG, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
    dll.NtQueryInformationProcess.restype = w.LONG
    value, length = Basic(), w.ULONG()
    result = dll.NtQueryInformationProcess(handle, 0, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(length))
    need(result == 0 and length.value == ctypes.sizeof(value), 'OBSERVER_PARENT_QUERY')
    return int(value.parent)


class Retained:
    def __init__(self, pid, executable, *, expected_parent=None, earliest_start=None):
        from studio.host.replay.process_probe import ProcessProbe
        self.probe = ProcessProbe(pid, executable)
        self.kernel = native()
        self.row = {'pid': pid, 'executable': str(executable), 'observed_utc': utc(),
                    'process_start': self.probe.process_start, 'actual_exit': None,
                    'handle_closed': False, 'natural_exit_not_inferred': True}
        try:
            need(self.kernel.WaitForSingleObject(self.probe.handle, 0) == 258, 'OBSERVER_NOT_LIVE_AT_ADOPTION')
            self.row['parent_pid'] = parent_pid(self.probe.handle)
            self.start = process_times(self.kernel, self.probe.handle)[0]
            need(self.probe.process_start == 'windows:' + str(self.start), 'OBSERVER_START_IDENTITY')
            if expected_parent is not None:
                need(self.row['parent_pid'] == expected_parent, 'OBSERVER_PARENT_IDENTITY')
            if earliest_start is not None:
                need(self.start >= earliest_start, 'OBSERVER_START_ORDER')
        except BaseException:
            self.probe.close()
            raise

    def observe_exit(self):
        if self.row['actual_exit'] is not None:
            return True
        wait = self.kernel.WaitForSingleObject(self.probe.handle, 0)
        need(wait in (0, 258), 'OBSERVER_WAIT')
        if wait == 258:
            return False
        code = w.DWORD()
        need(self.kernel.GetExitCodeProcess(self.probe.handle, ctypes.byref(code)), 'OBSERVER_EXIT_CODE')
        times = process_times(self.kernel, self.probe.handle)
        need(times[0] == self.start and times[1] >= times[0], 'OBSERVER_EXIT_IDENTITY')
        self.row['actual_exit'] = {'exit_code_uint32': code.value, 'exit_filetime': times[1],
                                   'observed_utc': utc(), 'wait_result': wait,
                                   'source': 'retained_handle_GetExitCodeProcess'}
        return True

    def close(self):
        self.probe.close()
        self.row['handle_closed'] = True


def configure_outer(job):
    limits = job._native.ExtendedLimit()
    limits.basic.flags = 0x2000 | 0x8
    limits.basic.active_limit = OUTER_PROCESS_LIMIT
    kernel = job._native.kernel
    need(kernel.SetInformationJobObject(job._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)),
         'OBSERVER_OUTER_CONFIGURE')
    # The existing API types its query as Accounting; use a separate function
    # object for the ExtendedLimit readback without changing the shared owner.
    query = ctypes.WinDLL('kernel32', use_last_error=True).QueryInformationJobObject
    query.argtypes = [w.HANDLE, w.DWORD, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    query.restype = w.BOOL
    observed, size = job._native.ExtendedLimit(), w.DWORD()
    need(query(job._handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), ctypes.byref(size)),
         'OBSERVER_OUTER_READBACK')
    need(size.value == ctypes.sizeof(observed) and observed.basic.flags == limits.basic.flags
         and observed.basic.active_limit == OUTER_PROCESS_LIMIT, 'OBSERVER_OUTER_LIMITS')
    return {'limit_flags': int(observed.basic.flags), 'process_limit': int(observed.basic.active_limit),
            'wall_seconds': WALL_SECONDS, 'wall_enforcement': 'observer_watchdog',
            'inner_benchmark_limits_changed': False, 'diagnostic_only': True}


def close_popen_handle(process):
    need(type(process.returncode) is int, 'OBSERVER_POPEN_EXIT_UNOBSERVED')
    from studio.tests.replay.benchmark_job import close_process_handle_native
    handle = process._handle
    need(not handle.closed, 'OBSERVER_POPEN_HANDLE_ALREADY_CLOSED')
    handle.closed = True
    if not close_process_handle_native(int(handle)):
        handle.closed = False
        raise RuntimeError('OBSERVER_POPEN_HANDLE_CLOSE')


def start_owned(console, directory, *, test_mode=None):
    from studio.host.blender.ui_host import cli_job
    args = [str(console), '-B', str(Path(__file__).resolve()), '--owned-supervisor']
    if test_mode is not None:
        need(test_mode in ('success', 'wait'), 'OBSERVER_TEST_MODE')
        args = [str(console), '-B', str(Path(__file__).resolve()), '--test-child', test_mode]
    streams = [(directory / name).open('xb') for name in ('supervisor-console-stdout.txt', 'supervisor-console-stderr.txt')]
    process = job = None
    try:
        process = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=streams[0], stderr=streams[1],
                                   cwd=STUDIO, creationflags=subprocess.CREATE_NO_WINDOW)
        job = cli_job.create(process)
        limits = configure_outer(job)
        target = Retained(process.pid, console, expected_parent=os.getpid())
        return process, job, target, streams, limits
    except BaseException:
        if job is not None:
            job.close()
        elif process is not None:
            owner = cli_job.owner_for_process(process)
            if owner is not None:
                owner.close()
            elif process.poll() is None:
                # The exact unreleased Popen child cannot have spawned a target.
                process.kill()
        if process is not None:
            process.wait(timeout=3)
            close_popen_handle(process)
        for stream in streams:
            stream.close()
        raise


def adopt_child(role, executable, parent, console, retained, directory):
    receipt = OUTPUT / ('host-owner' if role == 'host' else 'editor-host') / 'process-start.json'
    if not receipt.exists():
        return False
    try:
        data = read(receipt)
    except (json.JSONDecodeError, PermissionError):
        return False  # Helper may still be publishing the small start receipt.
    need(type(data) is dict and set(data) == {'pid'} and type(data['pid']) is int and data['pid'] > 0,
         'OBSERVER_START_RECEIPT')
    child = Retained(data['pid'], executable, earliest_start=parent.start)
    helper = None
    try:
        helper = Retained(child.row['parent_pid'], console,
                          expected_parent=parent.row['pid'], earliest_start=parent.start)
        need(helper.start <= child.start, 'OBSERVER_HELPER_START_ORDER')
        need(parent.kernel.WaitForSingleObject(parent.probe.handle, 0) == 258,
             'OBSERVER_PARENT_EXITED_AT_ADOPTION')
        retained[role + '_helper'], retained[role] = helper, child
        write(directory / (role + '-adoption.json'), {'role': role, 'receipt_sha256': sha(receipt),
              'target': child.row, 'helper': helper.row, 'ancestor': parent.row,
              'formal_acceptance': False})
        return True
    except BaseException:
        child.close()
        if helper is not None:
            helper.close()
        raise


def observer():
    need(os.name == 'nt', 'OBSERVER_WINDOWS_ONLY')
    windowed = Path(sys.executable).absolute()
    need(windowed.name.lower() == 'pythonw.exe', 'OBSERVER_SCHEDULER_PYTHONW_REQUIRED')
    console = windowed.with_name('python.exe')
    expected, godot = pins(console, windowed)
    request = read(LAUNCH / 'request.json')
    validate_request(request, expected)
    directory = plain(LAUNCH / 'observer')
    directory.mkdir(exist_ok=False)
    write(directory / 'claim.json', {'run_id': RUN_ID, 'pid': os.getpid(), 'utc': utc(),
                                    'request_sha256': sha(LAUNCH / 'request.json')})
    process = job = None
    streams, retained, errors = [], {}, []
    timeout = False
    supervisor_code = None
    limits = None
    started = time.monotonic()
    try:
        process, job, target, streams, limits = start_owned(console, directory)
        retained['supervisor'] = target
        write(directory / 'supervisor-adoption.json', {'process': target.row, 'limits': limits,
                                                     'formal_acceptance': False})
        process.stdin.write(b'START\n')
        process.stdin.close()
        while True:
            for role, executable, parent_role in (('host', console, 'supervisor'), ('editor', godot, 'host')):
                if role not in retained and parent_role in retained:
                    adopt_child(role, executable, retained[parent_role], console, retained, directory)
            for role, item in retained.items():
                before = item.row['actual_exit']
                if item.observe_exit() and before is None:
                    write(directory / (role + '-exit.json'), item.row)
            supervisor_code = process.poll()
            if supervisor_code is not None:
                break
            if time.monotonic() - started >= WALL_SECONDS:
                timeout = True
                raise TimeoutError('OBSERVER_WALL_LIMIT')
            time.sleep(.05)
    except BaseException as error:
        errors.append({'stage': 'body', 'type': type(error).__name__, 'message': str(error)})
        write(directory / 'failure.json', {'errors': errors, 'traceback': traceback.format_exc(),
                                          'formal_acceptance': False})
    finally:
        # Observation occurs before and after bounded cleanup. It never equates
        # a killed Job with a naturally completed diagnostic.
        for role, item in retained.items():
            try:
                item.observe_exit()
            except BaseException as error:
                errors.append({'stage': role + '_before_cleanup', 'message': str(error)})
        active_before = None
        try:
            active_before = job.active_count() if job is not None else None
        except BaseException as error:
            errors.append({'stage': 'outer_job_before_cleanup', 'message': str(error)})
        if job is not None:
            try:
                job.close()
            except BaseException as error:
                errors.append({'stage': 'outer_job_close', 'message': str(error)})
        if process is not None:
            try:
                supervisor_code = process.wait(timeout=5)
            except BaseException as error:
                errors.append({'stage': 'supervisor_wait', 'message': str(error)})
        for role, item in retained.items():
            try:
                item.kernel.WaitForSingleObject(item.probe.handle, 1000)
                item.observe_exit()
                if item.row['actual_exit'] is None:
                    errors.append({'stage': role + '_exit', 'message': 'ACTUAL_EXIT_UNOBSERVED'})
                if not (directory / (role + '-exit.json')).exists() and item.row['actual_exit'] is not None:
                    write(directory / (role + '-exit.json'), item.row)
            except BaseException as error:
                errors.append({'stage': role + '_exit', 'message': str(error)})
            finally:
                try:
                    item.close()
                except BaseException as error:
                    errors.append({'stage': role + '_handle_close', 'message': str(error)})
        for index, stream in enumerate(streams):
            try:
                stream.close()
            except BaseException as error:
                errors.append({'stage': 'stream_close_' + str(index), 'message': str(error)})
        popen_handle_closed = process is None
        if process is not None:
            try:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                close_popen_handle(process)
                popen_handle_closed = True
            except BaseException as error:
                errors.append({'stage': 'popen_handle_close', 'message': str(error)})
        try:
            current, _ = pins(console, windowed)
            validate_request(current, request)
            validate_request(read(LAUNCH / 'request.json'), request)
        except BaseException as error:
            errors.append({'stage': 'source_readback', 'message': str(error)})
        missing = [name for name in ('supervisor', 'host', 'editor') if name not in retained]
        result = {'schema': 'HH-GT06-S91-OBSERVER-TERMINAL-1', 'run_id': RUN_ID,
                  'observed_utc': utc(), 'elapsed_seconds': time.monotonic() - started,
                  'supervisor_popen_actual_exit_code': supervisor_code,
                  'supervisor_popen_handle_closed': popen_handle_closed,
                  'processes': {name: item.row for name, item in retained.items()},
                  'unobserved_processes': missing, 'errors': errors, 'timeout': timeout,
                  'outer_job_active_before_cleanup': active_before,
                  'outer_job': job.snapshot() if job is not None else None,
                  'limits': limits, 'natural_exit_not_inferred': True,
                  'observer_actual_exit_not_yet_observed': True,
                  'scheduler_terminal_result_still_required': True,
                  'formal_acceptance': False, 'eligible_for_dataset': False}
        result['observer_exit_code'] = 0 if (supervisor_code == 0 and not errors and not missing
            and job is not None and job.closed and job.zero_observed and not job.tainted) else 1
        write(directory / 'terminal.json', result)
        write(directory / 'manifest.json', {'schema': 'HH-GT06-S91-OBSERVER-MANIFEST-1',
              'run_id': RUN_ID, 'helper_files': expected['helper_files'],
              'artifacts': {p.name: sha(p) for p in directory.iterdir() if p.is_file()},
              'request_sha256': sha(LAUNCH / 'request.json'),
              'task_definition_sha256': sha(LAUNCH / 'task.xml'),
              'formal_acceptance': False, 'eligible_for_dataset': False})
    return result['observer_exit_code']


def gated_child(test_mode=None):
    need(sys.stdin.buffer.readline(16) == b'START\n', 'OBSERVER_START_GATE')
    if test_mode is not None:
        need(test_mode in ('success', 'wait'), 'OBSERVER_TEST_MODE')
        if test_mode == 'wait':
            time.sleep(30)
        return 0
    console = Path(sys.executable).absolute()
    expected, _ = pins(console, console.with_name('pythonw.exe'))
    validate_request(read(LAUNCH / 'request.json'), expected)
    sys.argv = [str(HELPER), '--supervisor']
    runpy.run_path(str(HELPER), run_name='__main__')
    return 0


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['--observer']:
        raise SystemExit(observer())
    if args == ['--owned-supervisor']:
        raise SystemExit(gated_child())
    if len(args) == 2 and args[0] == '--test-child' and args[1] in ('success', 'wait'):
        raise SystemExit(gated_child(args[1]))
    raise SystemExit('Expected fixed --observer or --owned-supervisor mode.')
