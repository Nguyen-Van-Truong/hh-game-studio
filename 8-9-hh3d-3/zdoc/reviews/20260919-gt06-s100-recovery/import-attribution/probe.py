"""One cold S100 import; --check is inert, --launch is coordinator-only.

Source/fixture bytes, Godot argv, stdin bootstrap and native 20s stage are pinned.
Delegate taps observe host boundaries; a retained handle observes only this target.
No engine launch occurs at import time. No acceptance or causality claim is made.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
STUDIO = ROOT / 'studio'
FAILURE = BASE.parent / 'failure'
CLOSURE = 'cfc4b55a5407891bfd54d22d9f1ac45a74b6c744898199a0e4690d6230a6c1d6'
OUTER_SECONDS = 90


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def checked(path, digest):
    for part in (path, *path.parents):
        info = part.lstat()
        need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'REPARSE_PATH')
    need(path.is_file() and sha(path) == digest, 'PIN_MISMATCH')
    return path.read_bytes()


def inputs():
    manifest = read(FAILURE / 'manifest.json')
    def saved(relative):
        entry = manifest['files'][relative]
        return checked(FAILURE / relative, entry['sha256'])
    source = json.loads(saved('raw/run-00-attempt-01/source-files.json'))
    closure = hashlib.sha256(''.join(k + '\0' + source[k] + '\n'
                                    for k in sorted(source)).encode()).hexdigest()
    need(closure == CLOSURE, 'SOURCE_CLOSURE')
    project = json.loads(saved('raw/run-00-attempt-01/initial-project-files.json'))
    for name, digest in source.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        saved('raw/source/studio/' + name)
        checked(STUDIO / name, digest)
    for name, digest in project.items():
        checked(FAILURE / 'raw/run-00-attempt-01/project' / name, digest)
    lock = json.loads(saved('raw/source/studio/toolchain.lock.json'))['godot']
    binary = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    checked(binary, lock['gui_sha256'])
    return source, project, binary, lock['gui_sha256']


class Observer:
    def __init__(self, stage, project, binary, ProcessProbe):
        self.stage, self.project, self.binary = stage, project, binary
        self.Probe = ProcessProbe
        self.events, self.samples, self.errors = [], [], []
        self.lock, self.done = threading.Lock(), threading.Event()
        self.target = self.helper = None
        self.target_exit = None
        self.dropped = 0
        self.seen = set()
        self.thread = threading.Thread(target=self.observe, name='import-observer', daemon=True)

    def mark(self, phase, **fields):
        row = {'phase': phase, 'mono_ns': time.perf_counter_ns(), **fields}
        with self.lock:
            if len(self.events) < 512:
                self.events.append(row)
            else:
                self.dropped += 1

    def configure(self):
        k = self.target.k
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
        self.IO = IO
        k.GetProcessIoCounters.argtypes = [w.HANDLE, ctypes.POINTER(IO)]
        k.GetProcessIoCounters.restype = w.BOOL
        k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
        k.GetExitCodeProcess.restype = w.BOOL
        k.GetPriorityClass.argtypes, k.GetPriorityClass.restype = [w.HANDLE], w.DWORD

    def sample(self):
        p, stamp = self.target, time.perf_counter_ns()
        state = p.k.WaitForSingleObject(p.handle, 0)
        need(state in (0, 258), 'TARGET_WAIT')
        if state == 0:
            code = w.DWORD()
            need(p.k.GetExitCodeProcess(p.handle, ctypes.byref(code)), 'TARGET_EXIT_QUERY')
            if self.target_exit is None:
                self.target_exit = {'pid': p.pid, 'process_start': p.process_start,
                                    'exit_code': int(code.value), 'observed_mono_ns': stamp}
                self.mark('target_exit_observed', exit_code=int(code.value))
            return
        times = [w.FILETIME() for _ in range(4)]
        memory, io = p.Memory(), self.IO()
        memory.cb = ctypes.sizeof(memory)
        need(p.k.GetProcessTimes(p.handle, *(ctypes.byref(v) for v in times)), 'CPU_QUERY')
        need(p.p.GetProcessMemoryInfo(p.handle, ctypes.byref(memory), memory.cb), 'MEMORY_QUERY')
        need(p.k.GetProcessIoCounters(p.handle, ctypes.byref(io)), 'IO_QUERY')
        row = {'mono_ns': stamp, 'pid': p.pid, 'wait_state': 'running_or_waiting',
               'user_100ns': (times[3].dwHighDateTime << 32) | times[3].dwLowDateTime,
               'kernel_100ns': (times[2].dwHighDateTime << 32) | times[2].dwLowDateTime,
               'page_faults': int(memory.page_faults), 'working_set_bytes': int(memory.working_set),
               'private_commit_bytes': int(memory.pagefile), 'priority_class': int(p.k.GetPriorityClass(p.handle)),
               'io': {name: int(getattr(io, name)) for name, _ in self.IO._fields_}}
        if len(self.samples) < 256:
            self.samples.append(row)
        else:
            self.dropped += 1

    def observe(self):
        try:
            while not self.done.is_set():
                start = self.stage / 'process-start.json'
                if self.target is None and start.is_file():
                    try:
                        pid = read(start)['pid']
                    except (json.JSONDecodeError, KeyError):
                        self.done.wait(.1)
                        continue
                    self.mark('target_start_receipt_observed', pid=pid)
                    self.target = self.Probe(pid, self.binary)
                    self.configure()
                    self.mark('target_identity_bound', pid=pid, process_start=self.target.process_start)
                for name in ('.godot/.gdignore', '.godot/global_script_class_cache.cfg',
                             '.godot/editor/filesystem_cache10'):
                    if name not in self.seen and (self.project / name).is_file():
                        self.seen.add(name)
                        self.mark('project_milestone_observed', file=name)
                if self.target is not None:
                    self.sample()
                self.done.wait(.1)
        except BaseException as error:
            self.errors.append(type(error).__name__)
            self.mark('observer_error', exception_class=type(error).__name__)

    def close(self):
        self.done.set()
        self.thread.join(3)
        need(not self.thread.is_alive(), 'OBSERVER_THREAD_HELD')
        if self.target is not None:
            try:
                self.sample()
            finally:
                self.target.close()


class PipeTap:
    def __init__(self, pipe, role, observer):
        self.pipe, self.role, self.observer = pipe, role, observer

    def __getattr__(self, name):
        return getattr(self.pipe, name)

    def write(self, data):
        self.observer.mark('gate_write_begin', bytes=len(data))
        result = self.pipe.write(data)
        self.observer.mark('gate_write_returned', bytes=result)
        return result

    def close(self):
        self.pipe.close()
        self.observer.mark(self.role + '_pipe_closed')

    def read1(self, size):
        data = self.pipe.read1(size)
        self.observer.mark(self.role + '_read', bytes=len(data),
                           first_scan=b'first_scan_filesystem' in data,
                           sha256=hashlib.sha256(data).hexdigest())
        return data


def subprocess_delegate(module, popen):
    """Expose every subprocess member used by the pinned native stage."""
    return SimpleNamespace(Popen=popen, PIPE=module.PIPE, CREATE_NO_WINDOW=module.CREATE_NO_WINDOW)


def selfcheck():
    """Tiny ABI/delegate check against this Python process; launches nothing."""
    import io
    import subprocess
    source = read(FAILURE / 'raw/run-00-attempt-01/source-files.json')
    checked(STUDIO / 'host/replay/process_probe.py', source['host/replay/process_probe.py'])
    sys.path.insert(0, str(ROOT))
    from studio.host.replay.process_probe import ProcessProbe, HELD_PROBES
    need(not HELD_PROBES, 'SELFCHECK_PREEXISTING_PROBE')
    observer = Observer(BASE, BASE, Path(sys.executable), ProcessProbe)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.argtypes, kernel.GetCurrentProcess.restype = [], w.HANDLE
    kernel.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    kernel.GetProcessHandleCount.restype = w.BOOL
    def handle_count():
        value = w.DWORD()
        need(kernel.GetProcessHandleCount(kernel.GetCurrentProcess(), ctypes.byref(value)),
             'SELFCHECK_HANDLE_COUNT')
        return int(value.value)
    before_handles = handle_count()
    before_threads = {thread.ident for thread in threading.enumerate()}
    try:
        observer.target = ProcessProbe(os.getpid(), Path(sys.executable))
        observer.configure()
        need(ctypes.sizeof(observer.IO) == 48, 'SELFCHECK_IO_LAYOUT')
        observer.sample()
        need(len(observer.samples) == 1 and observer.samples[0]['pid'] == os.getpid(),
             'SELFCHECK_SAMPLE')
    finally:
        if observer.target is not None:
            observer.target.close()
    need(observer.target.handle is None and not HELD_PROBES, 'SELFCHECK_PROBE_HELD')
    need(observer.thread.ident is None and not observer.thread.is_alive(), 'SELFCHECK_THREAD_STARTED')
    def forbidden_popen(*args, **kwargs):
        raise AssertionError('SELFCHECK_MUST_NOT_LAUNCH')
    delegated = subprocess_delegate(subprocess, forbidden_popen)
    need(delegated.PIPE is subprocess.PIPE and delegated.CREATE_NO_WINDOW == subprocess.CREATE_NO_WINDOW
         and delegated.Popen is forbidden_popen, 'SELFCHECK_SUBPROCESS_DELEGATE')
    raw = io.BytesIO()
    tap = PipeTap(raw, 'stdin', observer)
    need(tap.write(b'{}\n') == 3 and raw.getvalue() == b'{}\n', 'SELFCHECK_GATE_BYTES')
    tap.close()
    output = PipeTap(io.BytesIO(b'first_scan_filesystem'), 'stdout', observer)
    need(output.read1(4096) == b'first_scan_filesystem', 'SELFCHECK_OUTPUT_BYTES')
    output.close()
    after_handles = handle_count()
    need(after_handles == before_handles, 'SELFCHECK_HANDLE_COUNT_CHANGED')
    need({thread.ident for thread in threading.enumerate()} == before_threads, 'SELFCHECK_THREAD_CHANGED')
    result = {'selfcheck': 'PASS', 'engine_launches': 0, 'subprocess_launches': 0,
              'driver_sha256': sha(Path(__file__)),
              'sample_count': len(observer.samples), 'io_counter_bytes': ctypes.sizeof(observer.IO),
              'handle_count_before': before_handles, 'handle_count_after': after_handles,
              'probe_handle_released': True, 'observer_thread_started': False,
              'checked_subprocess_members': ['Popen', 'PIPE', 'CREATE_NO_WINDOW'],
              'sample': observer.samples[0]}
    print(json.dumps(result, sort_keys=True))
    return 0


def child(run):
    freeze = read(run / 'freeze.json')
    sys.path.insert(0, str(run / 'source'))
    from studio.pipeline import native_job as stage
    from studio.host.replay.process_probe import ProcessProbe, HELD_PROBES
    from studio.tests.replay.benchmark_job import close_process_handle_native
    source = freeze['source_files']
    binary, project = Path(freeze['binary']), run / 'project'
    output = run / 'import-host'
    observer = Observer(output, project, binary, ProcessProbe)
    originals = stage.subprocess, stage.configure_limits
    def popen(*args, **kwargs):
        observer.mark('helper_create_begin')
        process = originals[0].Popen(*args, **kwargs)
        observer.helper = process
        observer.mark('helper_created', pid=process.pid)
        for role in ('stdin', 'stdout', 'stderr'):
            setattr(process, role, PipeTap(getattr(process, role), role, observer))
        return process
    def limits(job):
        observer.mark('job_assigned_limits_begin')
        result = originals[1](job)
        observer.mark('job_limits_verified')
        return result
    # Only this diagnostic process's references change; all delegates and bytes are pinned.
    stage.subprocess = subprocess_delegate(originals[0], popen)
    stage.configure_limits = limits
    observer.thread.start()
    error = None
    cleanup_errors = []
    helper_handle_closed = False
    observer.mark('stage_call_begin')
    try:
        stage.run_trusted_stage([str(binary), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=output, source_files=source, source_root=run / 'source/studio',
            binary_sha256=freeze['binary_sha256'])
    except BaseException as exc:
        error = {'class': type(exc).__name__, 'code': str(exc) if isinstance(exc, stage.StageFailed) else None}
    finally:
        observer.mark('stage_call_returned')
        stage.subprocess, stage.configure_limits = originals
        try:
            observer.close()
        except BaseException as exc:
            cleanup_errors.append(type(exc).__name__)
        process = observer.helper
        if process is not None and process.poll() is not None:
            handle = process._handle
            handle.closed = True  # Prevent destructor double-close on uncertain native return.
            try:
                helper_handle_closed = close_process_handle_native(int(handle))
                if not helper_handle_closed:
                    handle.closed = False
                    cleanup_errors.append('HELPER_HANDLE_CLOSE_FALSE')
            except BaseException as exc:
                cleanup_errors.append(type(exc).__name__)
    capture = read(output / 'capture.json') if (output / 'capture.json').is_file() else None
    target_receipt = read(output / 'process-exit.json') if (output / 'process-exit.json').is_file() else None
    natural = target_receipt if capture and capture.get('natural_tree_exit') is True else None
    probe_closed = observer.target is None or observer.target.handle is None
    source_ok = all(sha(run / 'source/studio' / name) == value for name, value in source.items())
    report = {'schema': 'HH-S100-COLD-IMPORT-ATTRIBUTION-1', 'formal_acceptance': False,
        'eligible_for_dataset': False, 'stage_error': error, 'stage_capture': capture,
        'target_exit_from_retained_handle': observer.target_exit,
        'helper_target_exit_receipt': target_receipt, 'natural_target_exit_receipt': natural,
        'natural_target_exit_status': 'RECORDED' if natural is not None else 'UNKNOWN',
        'helper_handle_closed': helper_handle_closed, 'probe_handles_released': probe_closed and not HELD_PROBES,
        'cleanup_errors': cleanup_errors, 'observer_errors': observer.errors,
        'events_dropped': observer.dropped, 'clock': 'perf_counter_ns', 'sample_interval_seconds': .1,
        'events': observer.events, 'samples': observer.samples, 'source_unchanged': source_ok,
        'limitations': ['Observer overhead remains inside the unchanged deadline.',
            'File milestones are observation times, not filesystem creation timestamps.',
            'CPU and IO deltas distinguish progress; low deltas do not identify a wait cause.',
            'Private commit is PROCESS_MEMORY_COUNTERS.PagefileUsage; page faults include soft faults.',
            'A forced target exit code never establishes natural import completion.']}
    write(run / 'attribution.json', report)
    clean = (capture is not None and capture['job']['closed'] and capture['job']['zero_observed']
             and not capture['job']['handle_retained'] and not capture['job']['tainted']
             and helper_handle_closed and probe_closed and not HELD_PROBES and not cleanup_errors)
    return 0 if clean and not observer.errors and not observer.dropped and source_ok else 1


def launch():
    source, project, binary, binary_hash = inputs()
    run = BASE / 'run-01'
    run.mkdir(exist_ok=False)
    for prefix, names, origin in (('source/studio', source, FAILURE / 'raw/source/studio'),
                                 ('project', project, FAILURE / 'raw/run-00-attempt-01/project')):
        for name, digest in names.items():
            target = run / prefix / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(checked(origin / name, digest))
    (run / 'project/benchmark/out').mkdir()
    (run / 'project/benchmark/input').mkdir()
    need(not (run / 'project/.godot').exists(), 'COLD_PROJECT_REQUIRED')
    driver = run / 'driver.py'
    with driver.open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    write(run / 'freeze.json', {'source_files': source, 'source_closure_sha256': CLOSURE,
        'initial_project_files': project, 'binary': str(binary), 'binary_sha256': binary_hash,
        'driver_sha256': sha(driver), 'python_sha256': sha(Path(sys.executable)),
        'failure_manifest_sha256': sha(FAILURE / 'manifest.json'), 'outer_seconds': OUTER_SECONDS,
        'formal_acceptance': False, 'binding_scope': 'Exact inert S100 input copied; no campaign/native activation.'})
    sys.path.insert(0, str(run / 'source'))
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    owner = None
    failure = None
    started = time.monotonic()
    bound = {'source/studio/' + name: digest for name, digest in source.items()}
    bound['driver.py'] = sha(driver)
    bound['freeze.json'] = sha(run / 'freeze.json')
    try:
        owner = BenchmarkProcess([sys.executable, '-B', str(driver), '--child', str(run)],
            cwd=run, output=run / 'host-owner', source_root=run, source_files=bound,
            binary_sha256=sha(Path(sys.executable)), campaign_host=True)
        while owner.tick() is None:
            need(time.monotonic() - started < OUTER_SECONDS, 'DIAGNOSTIC_OUTER_WALL_LIMIT')
            time.sleep(.05)
        owner.finish()
    except BaseException as exc:
        owner = owner or getattr(exc, 'cleanup_owner', None)
        failure = type(exc).__name__
    finally:
        if owner is not None:
            owner.close()
    write(run / 'outer-result.json', {'formal_acceptance': False, 'eligible_for_dataset': False,
        'failure': failure, 'owner_closed': owner.closed if owner else None,
        'job': owner.job.snapshot() if owner and owner.job else None,
        'wrapper_process_handle': owner.process_handle_snapshot() if owner else None,
        'original_source_unchanged': all(sha(STUDIO / name) == value for name, value in source.items()),
        'driver_unchanged': sha(driver) == sha(Path(__file__))})
    print(json.dumps({'run': str(run), 'failure': failure, 'formal_acceptance': False}), flush=True)
    return 0 if failure is None else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        originals, fixture, _, _ = inputs()
        print(json.dumps({'checked_source_files': len(originals), 'checked_fixture_files': len(fixture),
                          'engine_launches': 0, 'source_closure_sha256': CLOSURE}))
    elif sys.argv[1:] == ['--launch']:
        raise SystemExit(launch())
    elif sys.argv[1:] == ['--selfcheck']:
        raise SystemExit(selfcheck())
    elif len(sys.argv) == 3 and sys.argv[1] == '--child':
        raise SystemExit(child(Path(sys.argv[2]).resolve()))
    else:
        print('Use --check for pins, --selfcheck for this-process ABI checks; coordinator --launch runs one cold import.')
        raise SystemExit(2)
