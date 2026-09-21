"""Trusted GT06 benchmark process owner; never a remote execution endpoint.

Long benchmark workloads have their own declared finite budget. The accepted
20-second native stage and its production limits are not changed. The helper
cannot launch its target until checked Job assignment and limits are applied.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time

from studio.pipeline.native_job import isolated_env, verify_captured_stage
from studio.host.blender.ui_host import HELPER, cli_job

PROFILE = {'schema': 'HH-GT06-BENCHMARK-OWNER-1', 'wall_seconds': 7410,
           'cpu_seconds': 7200, 'memory_bytes': 2 * 1024**3,
           'process_limit': 4, 'log_bytes_each': 8 * 1024**2,
           'workspace_bytes': 512 * 1024**2, 'workspace_cap_is_watchdog': True}
# The campaign host owns its helper and Python process plus the entire nested
# editor Job. Windows counts all descendants against both Jobs. Reserving only
# four aggregate slots accidentally excludes stock Godot's transient RD probe.
HOST_PROFILE = {**PROFILE, 'schema': 'HH-GT06-BENCHMARK-HOST-OWNER-1',
                'process_limit': 2 + PROFILE['process_limit'],
                'host_process_slots': 2, 'nested_editor_process_slots': PROFILE['process_limit']}
HELD_OWNERS = []


class BenchmarkJobError(RuntimeError):
    def __init__(self, code, *, cleanup_owner=None):
        super().__init__(code)
        self.code, self.cleanup_owner = code, cleanup_owner


def require(condition, code):
    if not condition:
        raise BenchmarkJobError(code)


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    require(path.read_bytes() == raw, 'BENCHMARK_EVIDENCE_READBACK')


def valid_hash(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def validate_sources(value):
    require(type(value) is dict and bool(value), 'BENCHMARK_SOURCE_MAP')
    for relative, digest in value.items():
        require(type(relative) is str and relative and not Path(relative).is_absolute()
                and not Path(relative).drive and '\\' not in relative and ':' not in relative
                and all(part not in ('', '.', '..') for part in relative.split('/')), 'BENCHMARK_SOURCE_PATH')
        require(valid_hash(digest), 'BENCHMARK_SOURCE_HASH')


def validate_invocation(argv, source_files, binary_sha256):
    require(type(argv) in (list, tuple) and bool(argv)
            and all(type(arg) is str and arg and '\0' not in arg for arg in argv), 'BENCHMARK_INVOCATION')
    validate_sources(source_files)
    require(Path(argv[0]).is_absolute() and valid_hash(binary_sha256), 'BENCHMARK_BINARY_BINDING')


def owner_profile(campaign_host):
    require(type(campaign_host) is bool, 'BENCHMARK_OWNER_ROLE')
    return dict(HOST_PROFILE if campaign_host else PROFILE)


def configure(job, *, campaign_host=False):
    profile = owner_profile(campaign_host)
    # JOB_TIME is relative to the user CPU already accumulated by members.
    # Configure only the empty owned Job so exact readback is an absolute cap.
    require(job.assigned is False and job.active_count() == 0, 'BENCHMARK_JOB_NOT_EMPTY')
    limits = job._native.ExtendedLimit()
    limits.basic.flags = 0x2000 | 0x200 | 0x8 | 0x4
    limits.basic.active_limit = profile['process_limit']
    limits.basic.job_time = PROFILE['cpu_seconds'] * 10_000_000
    limits.job_memory = PROFILE['memory_bytes']
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD]
    kernel.SetInformationJobObject.restype = w.BOOL
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, w.INT, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    kernel.QueryInformationJobObject.restype = w.BOOL
    require(kernel.SetInformationJobObject(job._handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)), 'BENCHMARK_JOB_CONFIGURE')
    observed, size = job._native.ExtendedLimit(), w.DWORD()
    require(kernel.QueryInformationJobObject(job._handle, 9, ctypes.byref(observed), ctypes.sizeof(observed), ctypes.byref(size)),
            'BENCHMARK_JOB_QUERY')
    require(size.value == ctypes.sizeof(observed) and observed.basic.flags == limits.basic.flags
            and observed.basic.active_limit == limits.basic.active_limit and observed.basic.job_time == limits.basic.job_time
            and observed.job_memory == limits.job_memory, 'BENCHMARK_JOB_LIMIT_MISMATCH')
    return {'limit_flags': int(observed.basic.flags), 'active_process_limit': int(observed.basic.active_limit),
            'job_user_time_100ns': int(observed.basic.job_time), 'job_memory_bytes': int(observed.job_memory)}


def close_process_handle_native(handle):
    """Return the checked Win32 BOOL; callers own uncertainty and retry state."""
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    return bool(kernel.CloseHandle(handle))


def check_path(path):
    for part in (path, *path.parents):
        info = part.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'BENCHMARK_REPARSE')


def _read_checked(path, cap):
    check_path(path)
    require(path.is_file() and 0 <= path.stat().st_size <= cap, 'BENCHMARK_CAPTURE_SIZE')
    raw = path.read_bytes()
    require(len(raw) <= cap, 'BENCHMARK_CAPTURE_SIZE')
    return raw


def _decode(raw):
    def pairs(items):
        value = {}
        for name, item in items:
            require(name not in value, 'BENCHMARK_CAPTURE_DUPLICATE_KEY')
            value[name] = item
        return value

    def constant(_value):
        raise BenchmarkJobError('BENCHMARK_CAPTURE_NONFINITE')

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def verify_capture(output, expected_sha256, *, source_root, expected_source_files, expected_binary_sha256,
                   expected_campaign_host=False):
    """Read-only proof check; expected hashes/maps come from the caller's freeze.

    source_root can be a retained source copy; it is never taken from the report
    to choose files to read. Invocation paths remain recorded original paths.
    No process is launched, signaled, or inferred alive from these artifacts.
    """
    output, source_root = Path(output).absolute(), Path(source_root).absolute()
    profile = owner_profile(expected_campaign_host)
    validate_sources(expected_source_files)
    require(valid_hash(expected_sha256) and valid_hash(expected_binary_sha256), 'BENCHMARK_CAPTURE_EXPECTED_HASH')
    capture_raw = _read_checked(output / 'capture.json', 1024 * 1024)
    require(hashlib.sha256(capture_raw).hexdigest() == expected_sha256, 'BENCHMARK_CAPTURE_HASH')
    capture = _decode(capture_raw)
    require(type(capture) is dict and capture.get('schema') == 'HH-GT06-BENCHMARK-CAPTURE-2', 'BENCHMARK_CAPTURE_SCHEMA')
    for name in ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json'):
        raw = _read_checked(output / name, PROFILE['log_bytes_each'] if name.endswith('.txt') else 8192)
        if name.endswith('.json'):
            _decode(raw)
    # Includes exact four artifact hashes, positive same PID, actual target and
    # helper exit0, pre-cleanup zero, closed untainted Job and no retained handle.
    verified = verify_captured_stage(output, expected_sha256)
    require(verified == capture, 'BENCHMARK_CAPTURE_READ_DRIFT')
    job = capture['job']
    require(job.get('configured') is True and job.get('assigned') is True
            and type(job.get('active_count')) is int and job['active_count'] == 0
            and job.get('create_uncertain') is False and job.get('close_uncertain') is False
            and job.get('failed_operations') == [] and job.get('native_error') is None,
            'BENCHMARK_CAPTURE_JOB_STATE')
    wrapper_handle = capture.get('wrapper_process_handle')
    expected_handle = {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False}
    require(type(wrapper_handle) is dict and set(wrapper_handle) == set(expected_handle)
            and all(type(wrapper_handle[key]) is bool and wrapper_handle[key] is value
                    for key, value in expected_handle.items()), 'BENCHMARK_CAPTURE_PROCESS_HANDLE')
    elapsed = capture.get('elapsed_seconds')
    require(type(elapsed) in (float, int) and math.isfinite(elapsed) and elapsed > 0,
            'BENCHMARK_CAPTURE_ELAPSED')
    invocation_raw = _read_checked(output / 'invocation.json', 1024 * 1024)
    require(hashlib.sha256(invocation_raw).hexdigest() == capture.get('invocation_sha256'), 'BENCHMARK_INVOCATION_HASH')
    invocation = _decode(invocation_raw)
    require(type(invocation) is dict and set(invocation) == {
        'argv', 'cwd', 'source_root', 'source_files', 'binary_sha256', 'profile', 'formal_acceptance'},
        'BENCHMARK_INVOCATION_FIELDS')
    validate_invocation(invocation['argv'], invocation['source_files'], invocation['binary_sha256'])
    require(invocation['formal_acceptance'] is False and capture.get('formal_acceptance') is False
            and capture.get('source_unchanged') is True, 'BENCHMARK_CAPTURE_SCOPE')
    for field in ('argv', 'cwd', 'source_root', 'source_files', 'binary_sha256', 'profile'):
        require(capture.get(field) == invocation[field], 'BENCHMARK_INVOCATION_BINDING')
    require(type(invocation['cwd']) is str and Path(invocation['cwd']).is_absolute()
            and type(invocation['source_root']) is str and Path(invocation['source_root']).is_absolute(),
            'BENCHMARK_INVOCATION_PATH')
    require(invocation['source_files'] == expected_source_files
            and invocation['binary_sha256'] == expected_binary_sha256, 'BENCHMARK_CAPTURE_FREEZE_BINDING')
    require(json.dumps(invocation['profile'], sort_keys=True, allow_nan=False) == json.dumps(profile, sort_keys=True),
            'BENCHMARK_CAPTURE_PROFILE')
    expected_limits = {'limit_flags': 0x2000 | 0x200 | 0x8 | 0x4,
        'active_process_limit': profile['process_limit'], 'job_user_time_100ns': PROFILE['cpu_seconds'] * 10_000_000,
        'job_memory_bytes': PROFILE['memory_bytes']}
    limits = capture.get('limits')
    require(type(limits) is dict and set(limits) == set(expected_limits)
            and all(type(limits[key]) is int and limits[key] == value for key, value in expected_limits.items()),
            'BENCHMARK_CAPTURE_LIMITS')
    launched = _decode(_read_checked(output / 'process-start.json', 8192))
    require(capture.get('actual_process_start') == launched
            and type(capture.get('active_at_wrapper_exit')) is int and capture['active_at_wrapper_exit'] >= 0,
            'BENCHMARK_CAPTURE_PROCESS_START')
    for relative, digest in expected_source_files.items():
        require(hashlib.sha256(_read_checked(source_root / relative, 8 * 1024 * 1024)).hexdigest() == digest,
                'BENCHMARK_CAPTURE_SOURCE_BYTES')
    executable = Path(invocation['argv'][0])
    require(hashlib.sha256(_read_checked(executable, 256 * 1024 * 1024)).hexdigest() == expected_binary_sha256,
            'BENCHMARK_CAPTURE_EXECUTABLE_BYTES')
    return capture


class BenchmarkProcess:
    """Retained helper/Job/streams; caller polls tick and always closes owner."""
    def __init__(self, argv, *, cwd, output, source_root, source_files, binary_sha256,
                 campaign_host=False):
        require(os.name == 'nt' and not HELD_OWNERS, 'BENCHMARK_ENVIRONMENT_OR_HELD_OWNER')
        self.profile = owner_profile(campaign_host)
        validate_invocation(argv, source_files, binary_sha256)
        self.cwd, self.output, self.source_root = Path(cwd).absolute(), Path(output).absolute(), Path(source_root).absolute()
        self.source_files, self.argv = dict(source_files), list(argv)
        self.process = self.job = None
        self._process_handle = None
        self._process_handle_closed = False
        self._process_handle_close_uncertain = False
        self.threads, self.errors = [], []
        self.overflow = threading.Event()
        self.closed = self.released = False
        self._failure_code = None
        self._finishing = False
        self._cleanup_lock = threading.RLock()
        self.binary_sha256 = binary_sha256
        self.limits = None
        self.started = time.monotonic()
        self._last_disk = 0.0
        self._report_number = 0
        for path in (self.cwd, self.output.parent, Path(argv[0]).absolute()):
            check_path(path)
        self.check_sources()
        require(hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest() == binary_sha256, 'BENCHMARK_BINARY_PIN')
        self.output.mkdir(exist_ok=False)
        write(self.output / 'invocation.json', {'argv': self.argv, 'cwd': str(self.cwd),
            'source_root': str(self.source_root), 'source_files': self.source_files,
            'binary_sha256': binary_sha256, 'profile': self.profile, 'formal_acceptance': False})
        HELD_OWNERS.append(self)
        try:
            self.process = subprocess.Popen([sys.executable, '-B', '-c', HELPER, str(self.output / 'process'), *argv],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.cwd,
                env=isolated_env(self.output), creationflags=subprocess.CREATE_NO_WINDOW)
            def before_assign(job):
                # Retain ownership before configuration can fail or cancel.
                self.job = job
                self.limits = configure(job, campaign_host=campaign_host)
            self.job = cli_job.create(self.process, before_assign=before_assign)
            require(self.limits is not None, 'BENCHMARK_JOB_LIMITS_MISSING')
            for name, pipe in (('stdout', self.process.stdout), ('stderr', self.process.stderr)):
                thread = threading.Thread(target=self._drain, args=(name, pipe), daemon=True)
                self.threads.append(thread)
                thread.start()
            self.check_sources()
            self.process.stdin.write(b'{}\n')
            self.process.stdin.close()
            self.released = True
        except BaseException as error:
            self._remember_failure(error)
            # A failed constructor never reaches the caller's assignment. Keep
            # this owner discoverable even when cleanup has already succeeded.
            # Preserve the initiating exception and its existing explicit cause.
            error.cleanup_owner = self
            try:
                self.close()
            except BaseException as cleanup_error:
                error.cleanup_error = cleanup_error
                raise error
            raise

    def check_sources(self):
        validate_sources(self.source_files)
        for relative, digest in self.source_files.items():
            path = self.source_root / relative
            check_path(path)
            require(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'BENCHMARK_SOURCE_CHANGED')

    def _remember_failure(self, error):
        if getattr(self, '_failure_code', None) is None:
            self._failure_code = getattr(error, 'code', type(error).__name__)

    def _require_healthy(self):
        code = getattr(self, '_failure_code', None)
        require(code is None, code or 'BENCHMARK_RUN_FAILED')

    def _drain(self, name, pipe):
        count = 0
        try:
            with (self.output / (name + '.txt')).open('xb') as stream:
                while raw := pipe.read1(4096):
                    stream.write(raw[:max(0, PROFILE['log_bytes_each'] - count)])
                    stream.flush()  # fixed batch markers are observed during execution
                    count += len(raw)
                    if count > PROFILE['log_bytes_each']:
                        self.overflow.set()
        except BaseException as error:
            self.errors.append(type(error).__name__)
            self.overflow.set()
        finally:
            pipe.close()

    def tick(self, *, stop=False):
        try:
            self._require_healthy()
            return self._tick(stop=stop)
        except BaseException as error:
            self._remember_failure(error)
            raise

    def _tick(self, *, stop=False):
        require(not self.closed, 'BENCHMARK_OWNER_CLOSED')
        require(type(stop) is bool, 'BENCHMARK_STOP_VALUE')
        require(not stop, 'BENCHMARK_STOPPED')
        now = time.monotonic()
        require(now - self.started <= PROFILE['wall_seconds'], 'BENCHMARK_WALL_LIMIT')
        require(not self.overflow.is_set() and not self.errors, 'BENCHMARK_LOG_LIMIT_OR_IO')
        if now - self._last_disk >= 1:
            self._last_disk = now
            size = 0
            roots = [self.cwd] + ([] if self.output.is_relative_to(self.cwd) else [self.output])
            for root in roots:
                for path in root.rglob('*'):
                    try:
                        info = path.lstat()
                    except FileNotFoundError:
                        continue
                    require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                            'BENCHMARK_WORKSPACE_REPARSE')
                    if stat.S_ISREG(info.st_mode):
                        size += info.st_size
                    require(size <= PROFILE['workspace_bytes'], 'BENCHMARK_WORKSPACE_LIMIT')
        return self.process.poll()

    def finish(self):
        """Natural target exit is checked before cleanup, never inferred from kill."""
        self._finishing = True
        try:
            self._require_healthy()
            return self._finish_success()
        except BaseException as error:
            self._remember_failure(error)
            raise
        finally:
            self._finishing = False

    def _finish_success(self):
        require(self.tick() == 0, 'BENCHMARK_WRAPPER_EXIT')
        active_at_exit = active = self.job.active_count()
        deadline = min(self.started + PROFILE['wall_seconds'], time.monotonic() + .5)
        while active is not None and active > 0 and time.monotonic() < deadline:
            time.sleep(.01)
            active = self.job.active_count()
        require(type(active) is int and active == 0 and not self.job.tainted, 'BENCHMARK_DESCENDANTS_OR_TAINT')
        for thread in self.threads:
            thread.join(2)
        require(not any(thread.is_alive() for thread in self.threads) and not self.errors
                and not self.overflow.is_set(), 'BENCHMARK_STREAM_DRAIN')
        self.check_sources()
        launched = json.loads((self.output / 'process-start.json').read_bytes())
        actual = json.loads((self.output / 'process-exit.json').read_bytes())
        require(type(launched) is dict and set(launched) == {'pid'} and type(launched['pid']) is int and launched['pid'] > 0
                and type(actual) is dict and set(actual) == {'pid', 'exit_code'}
                and type(actual['pid']) is int and actual['pid'] == launched['pid']
                and type(actual['exit_code']) is int and actual['exit_code'] == 0, 'BENCHMARK_TARGET_EXIT')
        self.close()
        self._require_healthy()
        require(not self.job.tainted, 'BENCHMARK_JOB_TAINTED')
        hashes = {name: hashlib.sha256((self.output / name).read_bytes()).hexdigest()
                  for name in ('stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json')}
        result = {'schema': 'HH-GT06-BENCHMARK-CAPTURE-2', 'completed': True,
                  'actual_process_start': launched, 'actual_process_exit': actual, 'wrapper_exit_code': 0,
                  'active_at_wrapper_exit': active_at_exit, 'active_before_cleanup': active,
                  'natural_tree_exit': True, 'job': self.job.snapshot(), 'artifacts': hashes,
                  'wrapper_process_handle': self.process_handle_snapshot(),
                  'source_unchanged': True, 'formal_acceptance': False, 'elapsed_seconds': time.monotonic() - self.started,
                  'argv': self.argv, 'cwd': str(self.cwd), 'source_root': str(self.source_root),
                  'source_files': self.source_files, 'binary_sha256': self.binary_sha256,
                  'profile': self.profile, 'limits': self.limits,
                  'invocation_sha256': hashlib.sha256((self.output / 'invocation.json').read_bytes()).hexdigest()}
        write(self.output / 'capture.json', result)
        return result

    def process_handle_snapshot(self):
        required = self.process is not None
        closed = not required or getattr(self, '_process_handle_closed', False)
        return {'required': required, 'closed': closed,
                'close_uncertain': getattr(self, '_process_handle_close_uncertain', False),
                'handle_retained': required and not closed}

    def _close_process_handle(self):
        if self.process is None:
            return
        handle = self.process._handle
        retained = getattr(self, '_process_handle', None)
        if retained is None:
            self._process_handle = retained = handle
        require(handle is retained, 'BENCHMARK_PROCESS_HANDLE_CHANGED')
        if getattr(self, '_process_handle_closed', False):
            return
        require(not getattr(self, '_process_handle_close_uncertain', False),
                'BENCHMARK_PROCESS_HANDLE_CLOSE_UNCERTAIN')
        require(not handle.closed and type(self.process.returncode) is int,
                'BENCHMARK_PROCESS_HANDLE_STATE')
        # CPython 3.11 Handle.Close sets closed=True BEFORE native CloseHandle;
        # it cannot distinguish a checked failure from successful release.
        # Suppress its destructor while the native result is uncertain. Keep
        # the exact Handle object, and re-arm it only after a checked FALSE.
        # No cancellation path may retry/auto-close a potentially reused value.
        self._process_handle_close_uncertain = True
        handle.closed = True
        if not close_process_handle_native(int(handle)):
            handle.closed = False
            self._process_handle_close_uncertain = False
            raise BenchmarkJobError('BENCHMARK_PROCESS_HANDLE_CLOSE')
        self._process_handle_closed = True
        self._process_handle_close_uncertain = False

    def close(self):
        # Ordinary instances initialize this before launch. The fallback also
        # permits isolated lifecycle tests without creating a native process.
        if not hasattr(self, '_cleanup_lock'):
            self._cleanup_lock = threading.RLock()
        with self._cleanup_lock:
            return self._close()

    def _close(self):
        if self.closed:
            return True
        if self.job is not None and self.job.tainted:
            self._remember_failure(BenchmarkJobError('BENCHMARK_JOB_TAINTED'))
        if not getattr(self, '_finishing', False):
            self._remember_failure(BenchmarkJobError('BENCHMARK_CLOSED_BEFORE_FINISH'))
        self._report_number += 1
        try:
            require(not getattr(self, '_process_handle_close_uncertain', False),
                    'BENCHMARK_PROCESS_HANDLE_CLOSE_UNCERTAIN')
            if self.job is None and self.process is not None:
                self.job = cli_job.owner_for_process(self.process)
            # A callback/configure failure leaves this exact helper gated and
            # unassigned. Stop it before attempting Job close so a checked
            # close failure cannot strand a live helper outside the retained
            # owner. The owner/Job error is still propagated below; this is
            # cleanup, never a success or an automatic retry.
            unassigned_live = (self.process is not None and self.process.poll() is None
                               and (self.job is None or self.job.assigned is False))
            if unassigned_live:
                require(not self.released, 'BENCHMARK_UNOWNED_RELEASED_PROCESS')
                self.process.kill()
            try:
                if self.job is not None:
                    self.job.close()
            except BaseException:
                # Preserve the Job close uncertainty, but still wait for the
                # exact helper that was already terminated above.
                if self.process is not None:
                    self.process.wait(timeout=3)
                raise
            if self.process is not None:
                self.process.wait(timeout=3)
            for thread in self.threads:
                if thread.ident is not None:
                    thread.join(2)
            require(not any(t.is_alive() for t in self.threads), 'BENCHMARK_CLEANUP_THREADS')
            if self.job is not None:
                require(self.job.closed and self.job.zero_observed, 'BENCHMARK_CLEANUP_JOB')
                if self.job.tainted:
                    self._remember_failure(BenchmarkJobError('BENCHMARK_JOB_TAINTED'))
            if self.process is not None:
                for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                    if pipe is not None and not pipe.closed:
                        pipe.close()
            self._close_process_handle()
            write(self.output / f'cleanup-{self._report_number:03d}.json', {'closed': True,
                'job': self.job.snapshot() if self.job else None, 'wrapper_exit_code': self.process.returncode if self.process else None,
                'wrapper_process_handle': self.process_handle_snapshot(),
                'failure_code': getattr(self, '_failure_code', None), 'completed': False})
            self.closed = True
            HELD_OWNERS.remove(self)
            return True
        except BaseException as error:
            self._remember_failure(error)
            raise BenchmarkJobError('BENCHMARK_CLEANUP_HELD', cleanup_owner=self) from error
