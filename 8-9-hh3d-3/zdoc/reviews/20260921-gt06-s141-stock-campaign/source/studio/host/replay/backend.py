"""Owned, fixed-profile Play backend for the replay service.

Preparation imports a disposable immutable snapshot before any remote grant is
issued. Start returns only after a pinned process handle has been observed;
completion and retained runtime inspection are separate. This is not a live
arbitrary-project debugger or an arbitrary executable endpoint.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

from . import native_runner as native
from .observation import validate_observation
from .trace import default_trace

HELD_BACKENDS = []


class BackendError(RuntimeError):
    def __init__(self, code, *, cleanup_owner=None):
        self.code, self.cleanup_owner = code, cleanup_owner
        super().__init__(code)


def need(value, code):
    if not value:
        raise BackendError(code)


class PreparedPlay:
    """One preparation, one runtime launch, one irreversible Stop latch."""
    def __init__(self):
        raise TypeError('use prepare')

    @classmethod
    def prepare(cls, run_id, *, seed=17):
        need(not HELD_BACKENDS, 'REPLAY_BACKEND_CLEANUP_HELD')
        need(type(run_id) is str and re.fullmatch('gt06-[a-z0-9-]{1,50}', run_id), 'REPLAY_BACKEND_RUN_ID')
        owner = object.__new__(cls)
        owner._stop = threading.Event()
        owner._done = threading.Event()
        owner._guard = threading.RLock()
        owner._thread = owner._sampler = None
        owner._state, owner._error, owner._result = 'PREPARING', None, None
        owner._binding = {'runtime_instance_id': run_id + '.runtime'}
        owner._closed = False
        inputs, owner.accepted = native.accepted_inputs()
        owner.source = native.sources(owner.accepted)
        owner.trace = default_trace(seed)
        owner.root = native.STUDIO / '.local/reviews' / run_id
        owner.root.mkdir(exist_ok=False)
        owner.project = native.prepare(owner.root, owner.trace, native.configuration('3.0'), inputs)
        native.write(owner.root / 'source-files.json', owner.source)
        for index, name in enumerate(owner.source):
            native.write(owner.root / 'source' / (str(index) + Path(name).suffix), native.read_regular(native.STUDIO / name))
        native.write(owner.root / 'invocation.json', {'run_id': run_id, 'speed': '3.0', 'seed': seed,
            'source_files': owner.source, 'source_closure_sha256': native.closure(owner.source),
            'accepted_gt05_manifest_sha256': native.MANIFEST_SHA,
            'scope': 'trusted fixed fixture prepared for authenticated replay; no formal acceptance',
            'managed_repair_binding': None})
        owner.lock = json.loads(native.read_regular(native.STUDIO / 'toolchain.lock.json'))['godot']
        owner.executable = native.STUDIO / '.local/tooling/godot-4.7.2-stable' / owner.lock['gui_executable']
        try:
            native.run_trusted_stage([str(owner.executable), '--headless', '--editor', '--path',
                str(owner.project), '--import'], cwd=owner.project, output=owner.root / 'import-host',
                source_files=owner.source, source_root=native.STUDIO,
                binary_sha256=owner.lock['gui_sha256'], stop=owner._stop)
            snapshot = {p.relative_to(owner.project).as_posix(): native.sha(native.read_regular(p))
                for p in owner.project.rglob('*') if p.is_file()
                and '.godot' not in p.relative_to(owner.project).parts and 'out' not in p.relative_to(owner.project).parts}
            owner._binding = {'run_id': run_id, 'command_id': run_id + '.play', 'runtime_instance_id': run_id + '.runtime',
                'source_closure_sha256': native.closure(owner.source),
                'runtime_snapshot_sha256': native.closure(snapshot), 'trace_sha256': owner.trace.raw_sha256,
                'glb_sha256': native.sha(inputs['fixture.glb']), 'generation': 1}
            native.write(owner.root / 'runtime-snapshot.json', snapshot)
            native.write(owner.project / 'input/run.json', owner._binding)
            owner.runtime_source = dict(owner.source)
            owner.runtime_source.update({(owner.project / name).relative_to(native.STUDIO).as_posix(): digest
                for name, digest in snapshot.items()})
            owner.runtime_source[(owner.project / 'input/run.json').relative_to(native.STUDIO).as_posix()] = native.sha(native.encoded(owner._binding))
            owner._state = 'PREPARED'
            return owner
        except BaseException as error:
            held = getattr(error, 'cleanup_owner', None)
            if held is not None:
                owner._held_native = held
                HELD_BACKENDS.append(owner)
                raise BackendError('REPLAY_BACKEND_PREPARE_HELD', cleanup_owner=owner) from error
            raise

    @property
    def binding(self):
        return json.loads(native.encoded(self._binding))

    def start(self):
        with self._guard:
            need(not self._closed and not self._stop.is_set() and self._state == 'PREPARED', 'REPLAY_BACKEND_ALREADY_STARTED_OR_STOPPED')
            self._state = 'STARTING'
            try:
                self._sampler = native.Sampler(self.root / 'runtime-host', self.executable)
                self._thread = threading.Thread(target=self._execute, name='hh-gt06-owned-play', daemon=True)
                self._thread.start()
            except BaseException as error:
                self._state = 'UNKNOWN'
                self._stop.set()
                if self not in HELD_BACKENDS:
                    HELD_BACKENDS.append(self)
                raise BackendError('REPLAY_BACKEND_START_HELD', cleanup_owner=self) from error
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self._done.wait(.01):
                return self.status()
            if self._sampler.identity is not None and self._sampler.rows:
                with self._guard:
                    if self._state == 'STARTING':
                        self._state = 'RUNNING'
                return self.status()
        self.stop()
        if self not in HELD_BACKENDS:
            HELD_BACKENDS.append(self)
        raise BackendError('REPLAY_BACKEND_START_UNKNOWN', cleanup_owner=self)

    def _execute(self):
        sampler = self._sampler
        runtime_result = None
        start_utc, start_mono = time.time_ns() // 1000000, time.perf_counter_ns() // 1000
        try:
            try:
                sampler.thread.start()
                runtime_result = native.run_trusted_stage([str(self.executable), '--path', str(self.project)],
                    cwd=self.project, output=self.root / 'runtime-host', source_files=self.runtime_source,
                    source_root=native.STUDIO, binary_sha256=self.lock['gui_sha256'], stop=self._stop)
            except BaseException as error:
                # Preserve native ownership before sampler/log finalization can
                # raise a second error and replace the exception being handled.
                retained = getattr(error, 'cleanup_owner', None)
                if retained is not None:
                    self._held_native = retained
                raise
            finally:
                if sampler.thread.ident is not None:
                    sampler.close()
                native.write(self.root / 'process-metrics.json', {'identity': sampler.identity,
                    'samples': sampler.rows, 'errors': sampler.errors, 'started_utc_ms': start_utc,
                    'ended_utc_ms': time.time_ns() // 1000000, 'host_start_mono_us': start_mono,
                    'host_end_mono_us': time.perf_counter_ns() // 1000})
            need(not sampler.errors and sampler.identity is not None and sampler.rows, 'REPLAY_BACKEND_METRICS')
            need(sampler.identity['pid'] == runtime_result['actual_process_exit']['pid'], 'REPLAY_BACKEND_PID')
            report_raw = native.read_regular(self.project / 'out/report.json')
            report = json.loads(report_raw)
            need(report.get('binding') == self._binding and report.get('completed') is True, 'REPLAY_BACKEND_REPORT')
            for phase in ('import', 'runtime'):
                path = self.root / (phase + '-host')
                native.verify_captured_stage(path, native.sha(native.read_regular(path / 'capture.json')))
                need(not (path / 'stderr.txt').read_bytes().strip()
                    and not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', (path / 'stdout.txt').read_bytes()), 'REPLAY_BACKEND_LOG')
            markers = [json.loads(row.split(' ', 1)[1])
                for row in (self.root / 'runtime-host/stdout.txt').read_text(encoding='utf-8').splitlines()
                if row.startswith('HH_GT06_COMPLETE ')]
            need(len(markers) == 1 and markers[0]['report_sha256'] == native.sha(report_raw)
                and markers[0]['pid'] == sampler.identity['pid']
                and all(markers[0][key] == self._binding[key] for key in ('run_id', 'command_id', 'runtime_instance_id')),
                'REPLAY_BACKEND_MARKER')
            need(all(native.sha(native.read_regular(native.STUDIO / name)) == digest for name, digest in self.source.items()),
                'REPLAY_BACKEND_SOURCE_CHANGED')
            checks = validate_observation(report_raw, trace=self.trace, binding=self._binding, config_speed=3.0,
                project=self.project, process=json.loads(native.read_regular(self.root / 'process-metrics.json')))
            need(checks['all_postconditions'] is True, 'REPLAY_BACKEND_POSTCONDITION')
            capture = {'schema': 'HH-GT06-NATIVE-CAPTURE-1', 'run_id': self._binding['run_id'],
                'completed_native': True, 'formal_acceptance': False, 'public_ack': False, 'binding': self._binding,
                'process': sampler.identity, 'report_sha256': native.sha(report_raw), 'source_unchanged': True,
                'import_capture_sha256': native.sha(native.read_regular(self.root / 'import-host/capture.json')),
                'runtime_capture_sha256': native.sha(native.read_regular(self.root / 'runtime-host/capture.json')),
                'process_metrics_sha256': native.sha(native.read_regular(self.root / 'process-metrics.json'))}
            native.write(self.root / 'capture.json', capture)
            native.write(self.root / 'observation-checks.json', checks)
            with self._guard:
                self._result = capture
                self._state = 'COMPLETED' if not self._stop.is_set() else 'STOPPED_AFTER_COMPLETION'
        except BaseException as error:
            with self._guard:
                self._error = getattr(error, 'code', None) or (str(error) if type(error).__name__ == 'StageFailed' else type(error).__name__)
                self._state = 'STOPPED' if self._stop.is_set() and self._error == 'STAGE_STOPPED' else 'UNKNOWN'
                held = getattr(error, 'cleanup_owner', None)
                if held is not None:
                    self._held_native = held
                if self not in HELD_BACKENDS:
                    HELD_BACKENDS.append(self)
                self._stop.set()
        finally:
            self._done.set()

    def status(self):
        with self._guard:
            return {'phase': self._state, 'runtime_instance_id': self._binding['runtime_instance_id'],
                'process': dict(self._sampler.identity) if self._sampler and self._sampler.identity else None,
                'stopped': self._stop.is_set(), 'draining': bool(self._thread and self._thread.is_alive()),
                'error': self._error, 'completed_native': self._result is not None,
                'historical_inspection_available': self._state == 'COMPLETED', 'public_ack': False}

    def stop(self):
        self._stop.set()
        with self._guard:
            if self._state == 'PREPARED':
                self._state = 'STOPPED'
            elif self._state == 'COMPLETED':
                self._state = 'STOPPED_AFTER_COMPLETION'
        return self.status()

    def close(self):
        self.stop()
        if self._thread is not None and self._thread.ident is not None:
            self._thread.join(5)
            if self._thread.is_alive():
                if self not in HELD_BACKENDS:
                    HELD_BACKENDS.append(self)
                raise BackendError('REPLAY_BACKEND_DRAIN_HELD', cleanup_owner=self)
        held = getattr(self, '_held_native', None)
        if held is not None:
            held.close()
            self._held_native = None
        if self._sampler is not None and self._sampler.thread.ident is not None:
            self._sampler.close()
        with self._guard:
            self._closed = True
        if self in HELD_BACKENDS:
            HELD_BACKENDS.remove(self)
        return self.status()
