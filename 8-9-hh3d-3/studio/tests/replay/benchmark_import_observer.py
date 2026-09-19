"""Bounded read-only import telemetry; native_job alone owns the target lifecycle.

Caller starts before the pinned import, closes after its finally/cleanup, and
writes snapshot separately. Observation errors never alter a stage verdict.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import threading
import time

from studio.host.replay.process_probe import HELD_PROBES, ProcessProbe

INTERVAL_SECONDS = .1
MAX_SAMPLES = 256
MILESTONES = ('.godot/.gdignore', '.godot/global_script_class_cache.cfg',
              '.godot/editor/filesystem_cache10')
LIMITATIONS = (
    'Polling timestamps bound observation, not exact gate release or file creation.',
    'Native stage logs are buffered; file byte counts do not timestamp first engine output.',
    'Actual target exit may be forced by stage cleanup; natural exit needs the stage receipt.',
    'No thread wait-chain or global system trace is collected; low CPU alone identifies no cause.',
)


class ImportObserverError(RuntimeError):
    pass


class _MetricsProbe(ProcessProbe):
    def __init__(self, pid: int, executable: Path):
        super().__init__(pid, executable)
        try:
            class IO(ctypes.Structure):
                _fields_ = [(name, ctypes.c_uint64) for name in
                    ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
            self.IO = IO
            self.k.GetProcessIoCounters.argtypes = [w.HANDLE, ctypes.POINTER(IO)]
            self.k.GetProcessIoCounters.restype = w.BOOL
            self.k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
            self.k.GetExitCodeProcess.restype = w.BOOL
            self.k.GetPriorityClass.argtypes, self.k.GetPriorityClass.restype = [w.HANDLE], w.DWORD
        except BaseException:
            self.close()
            raise

    def observe(self) -> dict:
        self._need(self.handle is not None and not self.close_uncertain, 'IMPORT_OBSERVER_CLOSED_OR_UNCERTAIN')
        wait = self.k.WaitForSingleObject(self.handle, 0)
        self._need(wait in (0, 258), 'IMPORT_OBSERVER_WAIT')
        if wait == 0:
            code = w.DWORD()
            self._need(self.k.GetExitCodeProcess(self.handle, ctypes.byref(code)), 'IMPORT_OBSERVER_EXIT')
            return {'exited': True, 'exit_code': int(code.value)}
        times, memory, io = [w.FILETIME() for _ in range(4)], self.Memory(), self.IO()
        memory.cb = ctypes.sizeof(memory)
        self._need(self.k.GetProcessTimes(self.handle, *(ctypes.byref(v) for v in times)), 'IMPORT_OBSERVER_CPU')
        self._need(self.p.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb), 'IMPORT_OBSERVER_MEMORY')
        self._need(self.k.GetProcessIoCounters(self.handle, ctypes.byref(io)), 'IMPORT_OBSERVER_IO')
        return {'exited': False,
            'user_100ns': (times[3].dwHighDateTime << 32) | times[3].dwLowDateTime,
            'kernel_100ns': (times[2].dwHighDateTime << 32) | times[2].dwLowDateTime,
            'page_faults': int(memory.page_faults), 'working_set_bytes': int(memory.working_set),
            'private_commit_bytes': int(memory.pagefile), 'priority_class': int(self.k.GetPriorityClass(self.handle)),
            'io': {name: int(getattr(io, name)) for name, _ in self.IO._fields_}}


class ImportObserver:
    def __init__(self, stage_dir: Path, project: Path, binary: Path):
        self.stage_dir, self.project, self.binary = Path(stage_dir), Path(project), Path(binary)
        self._done, self._lock = threading.Event(), threading.Lock()
        self._thread: threading.Thread | None = None
        self._probe: _MetricsProbe | None = None
        self._started = self._closed = self._binding_attempted = False
        self._started_ns: int | None = None
        self._identity: dict | None = None
        self._exit: dict | None = None
        self._samples: list[dict] = []
        self._errors: list[dict] = []
        self._error_count = 0
        self._receipt_partial = self._sample_cap = False

    def _error(self, phase: str, error: BaseException) -> None:
        with self._lock:
            self._error_count += 1
            if len(self._errors) < 16:
                self._errors.append({'phase': phase, 'exception_class': type(error).__name__,
                                     'mono_ns': time.perf_counter_ns()})

    def start(self) -> None:
        if self._started or self._closed:
            raise ImportObserverError('IMPORT_OBSERVER_ALREADY_USED')
        self._started = True
        self._started_ns = time.perf_counter_ns()
        self._thread = threading.Thread(target=self._run, name='hh-import-observer', daemon=True)
        try:
            self._thread.start()
        except BaseException as error:
            self._error('thread_start', error)
            raise

    def _bind(self) -> None:
        receipt = self.stage_dir / 'process-start.json'
        if self._binding_attempted or not receipt.is_file():
            return
        if receipt.stat().st_size > 4096:
            self._binding_attempted = True
            raise ImportObserverError('IMPORT_OBSERVER_RECEIPT_SIZE')
        try:
            value = json.loads(receipt.read_bytes())
        except json.JSONDecodeError:
            self._receipt_partial = True  # The helper can still be writing its receipt.
            return
        self._receipt_partial = False
        self._binding_attempted = True
        if type(value) is not dict or set(value) != {'pid'} or type(value['pid']) is not int or value['pid'] <= 0:
            raise ImportObserverError('IMPORT_OBSERVER_RECEIPT')
        self._identity = {'pid': value['pid'], 'receipt_observed_ns': time.perf_counter_ns(),
                          'process_start': None, 'handle_bound_ns': None}
        try:
            self._probe = _MetricsProbe(value['pid'], self.binary)
        except BaseException as error:
            retained = getattr(error, 'cleanup_owner', None)
            if isinstance(retained, ProcessProbe):
                self._probe = retained
            self._error('target_bind', error)
            return  # Never reopen a PID after a failed identity binding.
        self._identity.update(process_start=self._probe.process_start, handle_bound_ns=time.perf_counter_ns())

    @staticmethod
    def _size(path: Path) -> int | None:
        try:
            return path.stat().st_size
        except FileNotFoundError:
            return None

    def _poll(self) -> bool:
        with self._lock:
            if len(self._samples) >= MAX_SAMPLES:
                self._sample_cap = True
                return False
        self._bind()
        row = {'mono_ns': time.perf_counter_ns(),
               'stdout_file_bytes': self._size(self.stage_dir / 'stdout.txt'),
               'stderr_file_bytes': self._size(self.stage_dir / 'stderr.txt'),
               'milestones_observed': [name for name in MILESTONES if (self.project / name).is_file()],
               'target': None}
        if self._probe is not None and self._identity and self._identity['handle_bound_ns'] is not None:
            row['target'] = self._probe.observe()
            if row['target']['exited'] and self._exit is None:
                self._exit = {'pid': self._identity['pid'], 'process_start': self._identity['process_start'],
                              'exit_code': row['target']['exit_code'], 'observed_ns': row['mono_ns']}
        with self._lock:
            self._samples.append(row)
        return True

    def _run(self) -> None:
        try:
            while not self._done.is_set() and self._poll():
                self._done.wait(INTERVAL_SECONDS)
        except BaseException as error:
            self._error('poll', error)

    def close(self) -> None:
        if self._closed:
            return
        self._done.set()
        if self._thread is not None and self._thread.ident is not None:
            self._thread.join(3)
            if self._thread.is_alive():
                error = ImportObserverError('IMPORT_OBSERVER_THREAD_HELD')
                self._error('thread_close', error)
                raise error
        # The polling thread has stopped. Only this owner can use/close its handle now.
        if self._probe is not None:
            try:
                if (self._identity and self._identity['handle_bound_ns'] is not None
                        and self._probe.handle is not None and not self._probe.close_uncertain):
                    row = self._probe.observe()
                    if row['exited'] and self._exit is None:
                        self._exit = {'pid': self._identity['pid'], 'process_start': self._identity['process_start'],
                                      'exit_code': row['exit_code'], 'observed_ns': time.perf_counter_ns()}
            except BaseException as error:
                self._error('final_observation', error)
            try:
                self._probe.close()
            except BaseException as error:
                self._error('handle_close', error)
                raise
        self._closed = True

    def snapshot(self) -> dict:
        with self._lock:
            samples = json.loads(json.dumps(self._samples))
            errors = [dict(row) for row in self._errors]
        gaps = []
        if self._identity is None:
            gaps.append('TARGET_START_RECEIPT_NOT_OBSERVED')
        elif self._identity['handle_bound_ns'] is None:
            gaps.append('TARGET_HANDLE_NOT_BOUND_POSSIBLY_EXITED_BETWEEN_POLLS')
        if not any(row['target'] and not row['target']['exited'] for row in samples):
            gaps.append('NO_LIVE_TARGET_SAMPLE')
        if self._receipt_partial:
            gaps.append('TARGET_START_RECEIPT_INCOMPLETE')
        if self._sample_cap:
            gaps.append('SAMPLE_CAP_REACHED')
        return {'schema': 'HH-GT06-IMPORT-OBSERVATION-1', 'formal_acceptance': False,
            'clock': 'perf_counter_ns', 'started_ns': self._started_ns,
            'sample_interval_seconds': INTERVAL_SECONDS, 'sample_limit': MAX_SAMPLES,
            'sample_count': len(samples), 'samples': samples,
            'target_identity': dict(self._identity) if self._identity else None,
            'target_exit_observed': dict(self._exit) if self._exit else None,
            'natural_target_exit_status': 'UNKNOWN', 'api_gaps': gaps,
            'closed': self._closed, 'thread_alive': bool(self._thread and self._thread.is_alive()),
            'handle_retained': bool(self._probe and self._probe.handle is not None),
            'probe_handles_released': not (self._probe and self._probe.handle is not None) and not HELD_PROBES,
            'handle_close_uncertain': bool(self._probe and self._probe.close_uncertain),
            'global_held_probe_count': len(HELD_PROBES), 'errors': errors, 'error_count': self._error_count,
            'limitations': list(LIMITATIONS)}


def validate_import_snapshot(snapshot: dict) -> dict:
    """Validate observation integrity and cleanup, never import performance.

No-target and no-live-sample gaps remain valid if explicitly represented. An
observed target exit is not required and never becomes a natural-exit verdict.
Returns the same unchanged object or raises the one fixed validation error.
"""
    def need(condition: bool) -> None:
        if not condition:
            raise ValueError('INVALID_IMPORT_OBSERVATION')

    def shape(value: object, names: str) -> None:
        need(type(value) is dict and set(value) == set(names.split()))

    def integer(value: object, minimum: int = 0, maximum: int = (1 << 64) - 1) -> None:
        need(type(value) is int and minimum <= value <= maximum)

    def timestamp(value: object, minimum: int) -> None:
        integer(value, minimum, (1 << 63) - 1)

    def process_start(value: object) -> None:
        need(type(value) is str and value.startswith('windows:'))
        suffix = value[8:]
        need(1 <= len(suffix) <= 20 and suffix.isascii() and suffix.isdigit()
             and not suffix.startswith('0') and int(suffix) <= (1 << 64) - 1)

    shape(snapshot, 'schema formal_acceptance clock started_ns sample_interval_seconds sample_limit '
        'sample_count samples target_identity target_exit_observed natural_target_exit_status api_gaps '
        'closed thread_alive handle_retained probe_handles_released handle_close_uncertain '
        'global_held_probe_count errors error_count limitations')
    need(snapshot['schema'] == 'HH-GT06-IMPORT-OBSERVATION-1'
         and snapshot['formal_acceptance'] is False and snapshot['clock'] == 'perf_counter_ns')
    timestamp(snapshot['started_ns'], 1)
    need(type(snapshot['sample_interval_seconds']) is float
         and snapshot['sample_interval_seconds'] == INTERVAL_SECONDS)
    integer(snapshot['sample_limit'], MAX_SAMPLES, MAX_SAMPLES)
    integer(snapshot['sample_count'], 0, MAX_SAMPLES)
    need(type(snapshot['samples']) is list and len(snapshot['samples']) == snapshot['sample_count'])
    need(snapshot['closed'] is True and snapshot['thread_alive'] is False
         and snapshot['handle_retained'] is False and snapshot['probe_handles_released'] is True
         and snapshot['handle_close_uncertain'] is False)
    integer(snapshot['global_held_probe_count'], 0, 0)
    integer(snapshot['error_count'], 0, 0)
    need(type(snapshot['errors']) is list and snapshot['errors'] == [])
    need(snapshot['natural_target_exit_status'] == 'UNKNOWN'
         and type(snapshot['limitations']) is list and snapshot['limitations'] == list(LIMITATIONS))
    identity = snapshot['target_identity']
    if identity is not None:
        shape(identity, 'pid receipt_observed_ns process_start handle_bound_ns')
        integer(identity['pid'], 1, (1 << 32) - 2)
        timestamp(identity['receipt_observed_ns'], snapshot['started_ns'])
        if identity['handle_bound_ns'] is None:
            need(identity['process_start'] is None)
        else:
            timestamp(identity['handle_bound_ns'], identity['receipt_observed_ns'])
            process_start(identity['process_start'])
    bound = identity is not None and identity['handle_bound_ns'] is not None
    exited = snapshot['target_exit_observed']
    if exited is not None:
        need(bound)
        shape(exited, 'pid process_start exit_code observed_ns')
        need(type(exited['pid']) is int and exited['pid'] == identity['pid']
             and exited['process_start'] == identity['process_start'])
        integer(exited['exit_code'], 0, (1 << 32) - 1)
        timestamp(exited['observed_ns'], identity['handle_bound_ns'])
    previous_ns, live = snapshot['started_ns'], False
    io_names = 'read_ops write_ops other_ops read_bytes write_bytes other_bytes'
    for row in snapshot['samples']:
        shape(row, 'mono_ns stdout_file_bytes stderr_file_bytes milestones_observed target')
        timestamp(row['mono_ns'], previous_ns)
        previous_ns = row['mono_ns']
        for field in ('stdout_file_bytes', 'stderr_file_bytes'):
            if row[field] is not None:
                integer(row[field], 0, 262144)
        milestones = row['milestones_observed']
        need(type(milestones) is list and milestones == [name for name in MILESTONES if name in milestones])
        target = row['target']
        if target is None:
            need(not bound or row['mono_ns'] < identity['handle_bound_ns'])
            continue
        need(bound and row['mono_ns'] >= identity['handle_bound_ns'] and type(target) is dict)
        if target.get('exited') is True:
            shape(target, 'exited exit_code')
            integer(target['exit_code'], 0, (1 << 32) - 1)
            need(exited is not None and target['exit_code'] == exited['exit_code']
                 and row['mono_ns'] >= exited['observed_ns'])
        else:
            shape(target, 'exited user_100ns kernel_100ns page_faults working_set_bytes '
                          'private_commit_bytes priority_class io')
            need(target['exited'] is False and (exited is None or row['mono_ns'] <= exited['observed_ns']))
            for field in ('user_100ns', 'kernel_100ns', 'working_set_bytes', 'private_commit_bytes'):
                integer(target[field])
            integer(target['page_faults'], 0, (1 << 32) - 1)
            need(type(target['priority_class']) is int
                 and target['priority_class'] in (32, 64, 128, 256, 16384, 32768))
            shape(target['io'], io_names)
            for field in io_names.split():
                integer(target['io'][field])
            live = True
    gaps = snapshot['api_gaps']
    required = []
    if identity is None:
        required.append('TARGET_START_RECEIPT_NOT_OBSERVED')
    elif not bound:
        required.append('TARGET_HANDLE_NOT_BOUND_POSSIBLY_EXITED_BETWEEN_POLLS')
    if not live:
        required.append('NO_LIVE_TARGET_SAMPLE')
    need(type(gaps) is list and gaps[:len(required)] == required)
    extra = gaps[len(required):]
    optional = ['TARGET_START_RECEIPT_INCOMPLETE', 'SAMPLE_CAP_REACHED']
    need(extra == [name for name in optional if name in extra])
    need('TARGET_START_RECEIPT_INCOMPLETE' not in extra or identity is None)
    need('SAMPLE_CAP_REACHED' not in extra or snapshot['sample_count'] == MAX_SAMPLES)
    return snapshot
