"""Owned sequential GT06 campaign; raw capture is never an acceptance verdict.

Each of ten fresh host/editor pairs retains both identities for 35 batches.
Native ready -> 1000 real HTTP commands -> bound start permit -> 100 native
cycles -> quiescent OS observation -> bound ACK with fresh native counters.
Only a fully captured run can be resumed as part of the same source campaign.
Interrupted runs retain their artifacts and are restarted with a fresh pair;
their partial samples never enter the dataset. No production limits change.
"""
from __future__ import annotations

import argparse
import ctypes
from dataclasses import asdict
import gc
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import stat
import sys
import threading
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay.benchmark_commands import CommandProducer
from studio.tests.replay.benchmark_job import (
    BenchmarkJobError, BenchmarkProcess, require, verify_capture, write as write_cleanup,
)
from studio.tests.replay.benchmark_readiness import validate_startup_readiness
from studio.tests.replay.benchmark_import_observer import ImportObserver, validate_import_snapshot
from studio.tests.replay.benchmark_http_phases import validate_phase_snapshot
from studio.tests.replay import benchmark_profile as profile
from studio.tests.replay.benchmark_assembly import read_artifact, assemble_sample, assemble_run, assemble_dataset
from studio.tests.replay.run_native_benchmark import (
    load_fixture, source_files as imported_source_files, closure, read_regular, write, sha, encoded,
    prepare, project_files, MUTABLE_SCENE, validate_cycle_timing,
)
from studio.host.replay.process_probe import ProcessProbe
from studio.pipeline import native_job

SEQUENCE = 'host1000_then_native100_then_joint_ack_v1'
MAX_ATTEMPTS = 3

# Both entry points belong to the campaign even when only one is imported in
# this process. Bind the scheduler registration too, without weakening the
# imported dependency closure or the exact parent/child equality check.
CAMPAIGN_FIXED_SOURCES = (
    'tests/replay/run_benchmark_campaign.py',
    'tests/replay/run_campaign_task.py',
    'tests/replay/campaign_task.ps1',
    'contracts/perf-collector.schema.json',
)


def source_files():
    files = imported_source_files()
    for relative in CAMPAIGN_FIXED_SOURCES:
        files[relative] = sha(read_regular(STUDIO / relative))
    return dict(sorted(files.items()))


def clock():
    return time.perf_counter_ns() // 1000


def reference(root, path):
    raw = artifact_bytes(path)
    return {'file': path.relative_to(root).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw)}


def artifact_bytes(path):
    """Empty logs/guard files are evidence too; reject links and growing files."""
    for component in (path, *path.parents):
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'CAMPAIGN_ARTIFACT_REPARSE')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and 0 <= info.st_size <= 128 * 1024**2,
            'CAMPAIGN_ARTIFACT_SIZE')
    raw = path.read_bytes()
    require(len(raw) == info.st_size, 'CAMPAIGN_ARTIFACT_CHANGED')
    return raw


def publish(path, value):
    """Trusted fixed-slot fixture input, exclusive temp + no-overwrite rename."""
    require(not path.exists(), 'CAMPAIGN_INPUT_EXISTS')
    temporary = path.with_suffix(path.suffix + '.tmp')
    raw = encoded(value)
    with temporary.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    # On Windows rename rejects an existing destination; do not use replace.
    temporary.rename(path)
    require(read_regular(path) == raw, 'CAMPAIGN_INPUT_READBACK')
    return clock()


class NativeLog:
    """Consume complete lines only; retain bounded markers, not heartbeat history."""
    def __init__(self, owner):
        self.owner, self.offset, self.tail = owner, 0, b''
        self.events = {}
        self.last_heartbeat = None

    def poll(self):
        code = self.owner.tick()
        # Startup errors arrive on stderr before the first native marker.
        # This lane already requires empty stderr at completion; fail at the
        # first observation instead of spending hours on an invalid prefix.
        errors = self.owner.output / 'stderr.txt'
        if errors.exists():
            require(errors.stat().st_size == 0, 'CAMPAIGN_NATIVE_STDERR')
        path = self.owner.output / 'stdout.txt'
        try:
            with path.open('rb') as stream:
                stream.seek(self.offset)
                raw = stream.read(1024 * 1024)
                self.offset += len(raw)
        except FileNotFoundError:
            raw = b''
        rows = (self.tail + raw).split(b'\n')
        self.tail = rows.pop()
        require(len(self.tail) <= 65_536, 'CAMPAIGN_LOG_LINE_LIMIT')
        for line in rows:
            text = line.decode('utf-8').strip()
            require(not re.search(r'\b(?:ERROR|WARNING)\b|ObjectDB instances leaked', text), 'CAMPAIGN_NATIVE_LOG')
            if not text.startswith('HH_GT06_BENCHMARK_'):
                continue
            tag, payload = text.split(' ', 1)
            value = json.loads(payload)
            require(not tag.endswith('_FAILED'), 'CAMPAIGN_NATIVE_FAILURE')
            if tag.endswith('_HEARTBEAT'):
                self.last_heartbeat = value
            else:
                require(sum(len(v) for v in self.events.values()) < 256, 'CAMPAIGN_MARKER_LIMIT')
                self.events.setdefault(tag, []).append(value)
        return code

    def wait(self, suffix, index, timeout):
        end = time.monotonic() + timeout
        tag = 'HH_GT06_BENCHMARK_' + suffix
        while True:
            code = self.poll()
            matches = [row for row in self.events.get(tag, [])
                       if row.get('index', row.get('batch_index')) == index]
            require(len(matches) <= 1, 'CAMPAIGN_DUPLICATE_MARKER')
            if matches:
                return matches[0]
            require(code is None, 'CAMPAIGN_EARLY_NATIVE_EXIT')
            require(time.monotonic() < end, 'CAMPAIGN_PHASE_TIMEOUT')
            time.sleep(.02)


class CampaignProducer(CommandProducer):
    def __init__(self, root, run_id, log):
        self.native_log = log
        super().__init__(root, run_id)

    def _received(self):
        observed = super()._received()
        require(self.native_log.poll() is None, 'CAMPAIGN_NATIVE_EXIT_DURING_COMMANDS')
        return observed


def sample_editor(probe):
    from ctypes import wintypes as w
    observed = probe.sample()
    require(observed is not None and observed['visible_window_handles'], 'CAMPAIGN_EDITOR_UNOBSERVED')
    count = w.DWORD()
    method = probe.k.GetProcessHandleCount
    method.argtypes, method.restype = [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL
    require(method(probe.handle, ctypes.byref(count)), 'CAMPAIGN_EDITOR_HANDLES')
    return {'host_mono_us': observed['host_mono_us'],
            'rss_bytes': {'value': observed['rss_bytes'], 'unavailable_reason': None},
            'held_handles': {'value': count.value, 'unavailable_reason': None},
            'visible_window_handles': observed['visible_window_handles']}


def open_probe(owner, executable):
    end = time.monotonic() + 10
    while True:
        require(owner.tick() is None, 'CAMPAIGN_EDITOR_START_EXIT')
        try:
            start = json.loads((owner.output / 'process-start.json').read_bytes())
        except (FileNotFoundError, json.JSONDecodeError):
            require(time.monotonic() < end, 'CAMPAIGN_EDITOR_START_TIMEOUT')
            time.sleep(.02)
            continue
        require(set(start) == {'pid'} and type(start['pid']) is int, 'CAMPAIGN_EDITOR_START_SHAPE')
        return ProcessProbe(start['pid'], executable)


def verify_sources(files):
    require(source_files() == files, 'CAMPAIGN_SOURCE_CHANGED')


def stop_requested(output, *, run_id, source_closure_sha256, campaign_sha256):
    """Local fixed-slot control; a request can only stop this exact owned run.

    Publish with an exclusive temp file and no-overwrite rename. Invalid or
    stale control fails closed through the same owner cleanup. No new process,
    resume, PID-based signal, or successful measurement is inferred from it.
    """
    path = output / 'stop-request.json'
    if not os.path.lexists(path):
        return False

    def unique_pairs(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'CAMPAIGN_STOP_DUPLICATE_KEY')
            value[key] = item
        return value

    value = json.loads(read_regular(path, 4096), object_pairs_hook=unique_pairs)
    expected = {'schema': 'HH-GT06-CAMPAIGN-STOP-1', 'run_id': run_id,
        'source_closure_sha256': source_closure_sha256,
        'campaign_sha256': campaign_sha256, 'reason': 'OPERATOR_STOP'}
    require(type(value) is dict and value == expected, 'CAMPAIGN_STOP_BINDING')
    return True


def require_campaign_running(root, *, active=None):
    """A Stop in any fixed attempt slot stays latched across run boundaries.

    The active run validates its control payload separately. Presence in an
    older slot is sufficient to fail closed, including a broken symlink.
    Check only the bounded 10 x MAX_ATTEMPTS slots, not arbitrary directories.
    """
    for index in range(10):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            if output != active:
                require(not os.path.lexists(output / 'stop-request.json'), 'CAMPAIGN_STOP_LATCHED')


def wait_owned_run(owner, output, *, run_id, source_closure_sha256, campaign_sha256,
                   check_campaign_stop=None):
    while True:
        if check_campaign_stop is not None:
            check_campaign_stop()
        stop = stop_requested(output, run_id=run_id,
            source_closure_sha256=source_closure_sha256, campaign_sha256=campaign_sha256)
        if owner.tick(stop=stop) is not None:
            # Stop can arrive while tick observes the terminal process exit.
            require(not stop_requested(output, run_id=run_id,
                source_closure_sha256=source_closure_sha256, campaign_sha256=campaign_sha256),
                'BENCHMARK_STOPPED')
            if check_campaign_stop is not None:
                check_campaign_stop()
            return
        time.sleep(.05)


def screen_sample(sample, baseline):
    """Stop an already-failing prefix; only all ten complete runs can pass."""
    for role in ('host', 'editor'):
        for name, row in sample['memory'][role].items():
            if role == 'host' and name in ('objects', 'resources'):
                continue
            value = row['value']
            require(type(value) is int, 'CAMPAIGN_COUNTER_UNAVAILABLE')
            if sample['index'] < 5:
                continue
            reference_value = baseline[role][name]['value']
            require(value * 100 <= reference_value * 110 if name == 'rss_bytes' else value <= reference_value,
                    'CAMPAIGN_RSS_GROWTH' if name == 'rss_bytes' else 'CAMPAIGN_RETAINED_COUNTER_GROWTH')
    if sample['index'] >= 5:
        require(sample['max_status_gap_ms'] <= 2000, 'CAMPAIGN_STATUS_GAP')


def workstation_profile():
    """Machine facts fixed before samples; free RAM/load are not baseline pins."""
    from ctypes import wintypes as w
    import winreg
    class Memory(ctypes.Structure):
        _fields_ = [('length', w.DWORD), ('load', w.DWORD)] + [
            (name, ctypes.c_ulonglong) for name in ('physical', 'available', 'page_total',
            'page_available', 'virtual_total', 'virtual_available', 'extended_available')]
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalMemoryStatusEx.argtypes, kernel.GlobalMemoryStatusEx.restype = [ctypes.POINTER(Memory)], w.BOOL
    require(kernel.GlobalMemoryStatusEx(ctypes.byref(memory)), 'CAMPAIGN_MACHINE_MEMORY')
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        cpu = winreg.QueryValueEx(key, 'ProcessorNameString')[0].strip()
    class Display(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('name', w.WCHAR * 32), ('description', w.WCHAR * 128),
                    ('flags', w.DWORD), ('device_id', w.WCHAR * 128), ('key', w.WCHAR * 128)]
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.EnumDisplayDevicesW.argtypes = [w.LPCWSTR, w.DWORD, ctypes.POINTER(Display), w.DWORD]
    user.EnumDisplayDevicesW.restype = w.BOOL
    displays = []
    for index in range(32):
        display = Display()
        display.cb = ctypes.sizeof(display)
        if not user.EnumDisplayDevicesW(None, index, ctypes.byref(display), 0):
            break
        displays.append({'description': display.description, 'flags': display.flags})
    require(displays, 'CAMPAIGN_MACHINE_DISPLAY')
    return {'schema_id': 'hh-studio.benchmark-workstation', 'schema_version': '1.0.0',
        'os': platform.win32_ver(), 'machine': platform.machine(), 'cpu': cpu,
        'logical_processors': os.cpu_count(), 'physical_memory_bytes': memory.physical,
        'displays': displays, 'python': platform.python_version(), 'pointer_bits': ctypes.sizeof(ctypes.c_void_p) * 8,
        'renderer': 'gl_compatibility', 'sequence': SEQUENCE,
        'scope': 'current machine fixed before campaign; not a claim of performance on other devices'}


def verify_owner_captures(root, context):
    """Delegate raw exits/limits/invocation/source binding to the checked owner."""
    sources = context['source_files']
    verify_capture(root / 'host-owner', sha(read_regular(root / 'host-owner/capture.json')),
        source_root=STUDIO, expected_source_files=sources,
        expected_binary_sha256=sha(read_regular(Path(sys.executable), 256 * 1024**2)),
        expected_campaign_host=True)
    snapshot = json.loads(read_regular(root / 'editor-snapshot.json'))
    runtime = dict(sources)
    runtime.update({(root / 'project' / name).relative_to(STUDIO).as_posix(): value
                    for name, value in snapshot.items() if name != MUTABLE_SCENE})
    lock = json.loads(read_regular(root / 'toolchain.lock.json'))['godot']
    verify_capture(root / 'editor-host', sha(read_regular(root / 'editor-host/capture.json')),
        source_root=STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
    native_job.verify_captured_stage(root / 'import-host', sha(read_regular(root / 'import-host/capture.json')))


def verify_run_capture(root, captured, source_digest, *, campaign_id, index, attempt, campaign_sha256):
    """Re-hash the entire completed run before treating it as resumable."""
    require(captured.get('schema_id') == 'hh-studio.benchmark-owned-run'
            and captured.get('completed') is True and captured.get('source_closure_sha256') == source_digest
            and captured.get('profile_sha256') == profile.PROFILE_SHA256, 'CAMPAIGN_RESUME_BINDING')
    run_id = f'{campaign_id}.r{index:02d}.a{attempt:02d}'
    require(captured.get('index') == index and captured.get('run_id') == run_id, 'CAMPAIGN_RESUME_SLOT')
    context = json.loads(read_regular(root / 'context.json'))
    require(context['index'] == index and context['attempt'] == attempt and context['run_id'] == run_id
            and context['campaign_sha256'] == campaign_sha256
            and context['source_closure_sha256'] == source_digest
            and closure(context['source_files']) == source_digest, 'CAMPAIGN_RESUME_CONTEXT')
    files = captured['artifacts']
    require(type(files) is dict and files, 'CAMPAIGN_RESUME_ARTIFACTS')
    for relative, digest in files.items():
        require(type(relative) is str and '\\' not in relative and not Path(relative).is_absolute()
                and all(part not in ('', '.', '..') for part in relative.split('/')), 'CAMPAIGN_ARTIFACT_PATH')
        require(sha(artifact_bytes(root / relative)) == digest, 'CAMPAIGN_RESUME_ARTIFACT_CHANGED')
    require({'context.json', 'child-result.json', 'child-terminal-cleanup.json',
             'http-phases-final.json', 'import-observation.json',
             'host-owner/capture.json', 'editor-host/capture.json',
             'host-owner/process-start.json', 'host-owner/process-exit.json', 'host-owner/stdout.txt',
             'host-owner/stderr.txt', 'editor-host/process-start.json', 'editor-host/process-exit.json',
             'editor-host/stdout.txt', 'editor-host/stderr.txt'}.issubset(files), 'CAMPAIGN_RESUME_MISSING_ARTIFACTS')
    host = json.loads(read_regular(root / 'host-owner/capture.json'))
    child = json.loads(read_regular(root / 'child-result.json'))
    editor = json.loads(read_regular(root / 'editor-host/capture.json'))
    require(child['source_closure_sha256'] == source_digest and child['completed'] is True
            and child['run_id'] == captured['run_id'] and child['processes'] == captured['processes'],
            'CAMPAIGN_RESUME_CHILD')
    require(child['index'] == index, 'CAMPAIGN_RESUME_CHILD_SLOT')
    for role, value in (('host', host), ('editor', editor)):
        actual = value['actual_process_exit']
        require(value['completed'] is True and value['source_unchanged'] is True
                and value['wrapper_exit_code'] == 0 and actual['exit_code'] == 0
                and actual['pid'] == child['processes'][role]['pid']
                and value['natural_tree_exit'] is True and value['job']['closed'] is True
                and value['job']['zero_observed'] is True and value['job']['tainted'] is False,
                'CAMPAIGN_RESUME_OWNERSHIP')
    require(len(child['batches']) == 35, 'CAMPAIGN_RESUME_BATCH_COUNT')
    verify_child_terminal_cleanup(root, context, child)
    verify_observations(root, context, child)
    verify_owner_captures(root, context)
    return child


def run_campaign(campaign_id, root):
    load_fixture()  # Same dynamic dependency closure in parent and child.
    before = source_files()
    digest = closure(before)
    machine = workstation_profile()
    lock_raw = read_regular(STUDIO / 'toolchain.lock.json')
    frozen = {'schema_id': 'hh-studio.benchmark-campaign', 'schema_version': '1.0.0',
        'campaign_id': campaign_id, 'source_files': before, 'source_closure_sha256': digest,
        'profile_sha256': profile.PROFILE_SHA256, 'workstation': machine, 'sequence': SEQUENCE,
        'toolchain_sha256': sha(lock_raw), 'formal_acceptance': False,
        'python_executable_sha256': sha(read_regular(Path(sys.executable), 256 * 1024**2)),
        'run_count': 10, 'batches_per_run': 35, 'max_attempts_per_run': MAX_ATTEMPTS}
    if root.exists():
        require(json.loads(read_regular(root / 'campaign.json')) == json.loads(encoded(frozen)),
                'CAMPAIGN_RESUME_SOURCE_OR_MACHINE_CHANGED')
    else:
        root.mkdir(exist_ok=False)
        write(root / 'campaign.json', frozen)
        write(root / 'benchmark-profile.json', json.dumps(asdict(profile.PROFILE), sort_keys=True,
              separators=(',', ':'), allow_nan=False).encode())
        for name, expected in before.items():
            raw = read_regular(STUDIO / name)
            require(sha(raw) == expected, 'CAMPAIGN_FREEZE_CHANGED')
            write(root / 'source/studio' / name, raw)
    completed = []
    identities = set()
    campaign_sha = sha(read_regular(root / 'campaign.json'))

    def remember(captured):
        for process in captured['processes'].values():
            identity = (process['pid'], process['process_start'])
            require(identity not in identities, 'CAMPAIGN_PROCESS_REUSE')
            identities.add(identity)

    for index in range(10):
        require_campaign_running(root)
        finished = []
        attempts = []
        for attempt in range(1, MAX_ATTEMPTS + 1):
            output = root / f'run-{index:02d}-attempt-{attempt:02d}'
            if not output.exists():
                break
            attempts.append(output)
            capture_path = output / 'run-capture.json'
            if capture_path.is_file():
                captured = json.loads(read_regular(capture_path))
                verify_run_capture(output, captured, digest, campaign_id=campaign_id,
                                   index=index, attempt=attempt, campaign_sha256=campaign_sha)
                finished.append((output, captured))
        require(len(finished) <= 1, 'CAMPAIGN_DUPLICATE_SUCCESS')
        require_campaign_running(root)
        if finished:
            output, captured = finished[0]
            remember(captured)
            completed.append({'index': index, 'run_id': captured['run_id'], 'capture': reference(root, output / 'run-capture.json')})
            continue
        require(len(attempts) < MAX_ATTEMPTS, 'CAMPAIGN_ATTEMPTS_EXHAUSTED')
        # A failed process pair is never silently reused. Prior attempts must
        # have a parent-captured closed/zero record before starting another.
        for prior in attempts:
            require(not (prior / 'stop-request.json').exists(), 'CAMPAIGN_STOP_LATCHED')
            failure = json.loads(read_regular(prior / 'parent-failure.json'))
            require(failure.get('owned_tree_zero') is True and failure.get('owner_closed') is True,
                    'CAMPAIGN_PRIOR_OWNER_HELD')
        attempt = len(attempts) + 1
        output = root / f'run-{index:02d}-attempt-{attempt:02d}'
        output.mkdir(exist_ok=False)
        run_id = f'{campaign_id}.r{index:02d}.a{attempt:02d}'
        write(output / 'context.json', {'run_id': run_id, 'index': index, 'attempt': attempt,
            'source_files': before, 'source_closure_sha256': digest, 'profile_sha256': profile.PROFILE_SHA256,
            'campaign_sha256': sha(read_regular(root / 'campaign.json'))})
        write(output / 'source-files.json', before)
        write(output / 'toolchain.lock.json', lock_raw)
        write(output / 'benchmark-profile.json', read_regular(root / 'benchmark-profile.json'))
        for name, expected in before.items():
            raw = read_regular(root / 'source/studio' / name)
            require(sha(raw) == expected, 'CAMPAIGN_FROZEN_COPY_CHANGED')
            write(output / 'source/studio' / name, raw)
        owner = None
        primary = None
        try:
            verify_sources(before)
            require_campaign_running(root)
            owner = BenchmarkProcess([sys.executable, '-B', str(Path(__file__).resolve()), '--campaign-id', campaign_id,
                '--child-index', str(index), '--attempt', str(attempt)], cwd=output, output=output / 'host-owner',
                source_root=STUDIO, source_files=before,
                binary_sha256=sha(read_regular(Path(sys.executable), 256 * 1024**2)), campaign_host=True)
            wait_owned_run(owner, output, run_id=run_id,
                source_closure_sha256=digest, campaign_sha256=campaign_sha,
                check_campaign_stop=lambda: require_campaign_running(root, active=output))
            host = owner.finish()
            require_campaign_running(root)
            child = json.loads(read_regular(output / 'child-result.json'))
            require(host['actual_process_exit']['pid'] == child['processes']['host']['pid'], 'CAMPAIGN_HOST_IDENTITY')
            write(output / 'cleanup.json', {'schema_id': 'hh-studio.benchmark-cleanup', 'schema_version': '1.0.0',
                'run_id': run_id, 'processes': child['processes'], 'host_exit_code': host['actual_process_exit']['exit_code'],
                'editor_exit_code': child['cleanup']['editor_exit_code'],
                'owned_tree_zero': host['job']['zero_observed'] and child['cleanup']['editor_owned_tree_zero'],
                'held_handles': child['cleanup']['held_handles']})
            manifest = {'schema_id': 'hh-studio.benchmark-run-assembly', 'schema_version': '1.0.0',
                'run_id': run_id, 'index': index, 'profile_sha256': profile.PROFILE_SHA256,
                'source_closure_sha256': digest, 'processes': child['processes'],
                'refs': {name: reference(output, output / relative) for name, relative in {
                    'native_index': 'project/benchmark/out/index.json', 'source_manifest': 'source-files.json',
                    'toolchain': 'toolchain.lock.json', 'profile': 'benchmark-profile.json',
                    'native_stdout': 'editor-host/stdout.txt', 'native_stderr': 'editor-host/stderr.txt',
                    'cleanup': 'cleanup.json'}.items()}}
            for name, key in {'native_batches': 'native', 'command_batches': 'command',
                'joint_observations': 'joint', 'ready_artifacts': 'ready', 'start_artifacts': 'start', 'ack_artifacts': 'ack'}.items():
                manifest[name] = [row[key] for row in child['batches']]
            assembled = assemble_run(output, manifest)
            require_campaign_running(root)
            write(output / 'assembly-manifest.json', manifest)
            write(output / 'assembled-run.json', assembled.value['run'])
            artifacts = {p.relative_to(output).as_posix(): sha(artifact_bytes(p))
                         for p in sorted(output.rglob('*')) if p.is_file()
                         and '.godot' not in p.relative_to(output).parts}
            captured = {'schema_id': 'hh-studio.benchmark-owned-run', 'schema_version': '1.0.0',
                'run_id': run_id, 'index': index, 'completed': True, 'source_closure_sha256': digest,
                'profile_sha256': profile.PROFILE_SHA256, 'processes': child['processes'],
                'artifacts': artifacts, 'formal_acceptance': False, 'measurement_acceptance': 'RUN_ASSEMBLED_DATASET_PENDING'}
            verify_run_capture(output, captured, digest, campaign_id=campaign_id,
                               index=index, attempt=attempt, campaign_sha256=campaign_sha)
            require_campaign_running(root)
            write(output / 'run-capture.json', captured)
            require_campaign_running(root)
            remember(captured)
            completed.append({'index': index, 'run_id': run_id, 'capture': reference(root, output / 'run-capture.json')})
            print('HH_GT06_CAMPAIGN_RUN_COMPLETE ' + json.dumps(completed[-1]), flush=True)
        except BaseException as error:
            primary = error
            owner = owner or getattr(error, 'cleanup_owner', None)
            cleanup_error = None
            if owner is not None:
                try:
                    owner.close()
                except BaseException as cleanup:
                    cleanup_error = cleanup
            try:
                write(output / 'parent-failure.json', {'completed': False, 'run_id': run_id,
                    'code': getattr(error, 'code', type(error).__name__), 'formal_acceptance': False,
                    'owner_closed': owner.closed if owner else False,
                    'owned_tree_zero': owner.job.zero_observed if owner and owner.job else False,
                    'cleanup_error': type(cleanup_error).__name__ if cleanup_error else None})
            except BaseException as capture_error:
                raise error from capture_error
            if cleanup_error is not None:
                raise error from cleanup_error
            raise
        finally:
            if owner is not None and primary is None:
                owner.close()
    verify_sources(before)
    require_campaign_running(root)
    result = {'schema_id': 'hh-studio.benchmark-campaign-capture', 'schema_version': '1.0.0',
        'campaign_id': campaign_id, 'completed': True, 'formal_acceptance': False,
        'source_closure_sha256': digest, 'profile_sha256': profile.PROFILE_SHA256,
        'campaign_sha256': sha(read_regular(root / 'campaign.json')), 'runs': completed,
        'measurement_acceptance': 'REQUIRES_STRICT_ASSEMBLY_AND_REVIEW'}
    final = root / 'campaign-capture.json'
    if final.exists():
        require(json.loads(read_regular(final)) == result, 'CAMPAIGN_EXISTING_CAPTURE_CHANGED')
    else:
        write(final, result)
    runs = []
    for row in completed:
        require_campaign_running(root)
        output = root / row['capture']['file'].rsplit('/', 1)[0]
        runs.append(assemble_run(output, json.loads(read_regular(output / 'assembly-manifest.json'))))
    provenance = {'source_closure_sha256': digest, 'toolchain_sha256': sha(lock_raw),
        'workstation_profile_sha256': sha(encoded(machine)), 'driver_sha256': before[Path(__file__).relative_to(STUDIO).as_posix()],
        'capture_manifest_sha256': sha(read_regular(final))}
    dataset = assemble_dataset(provenance, runs)
    summary = profile.summarize_dataset(dataset)
    for name, value in (('dataset.json', dataset), ('summary.json', summary)):
        require_campaign_running(root)
        target = root / name
        if target.exists():
            require(json.loads(read_regular(target, profile.MAX_BYTES)) == value, 'CAMPAIGN_FINAL_CHANGED')
        else:
            write(target, value)
    require(summary['status'] == 'PASS', 'CAMPAIGN_MEASUREMENTS_NOT_PASS')
    require_campaign_running(root)
    return 0


def _cleanup_error(stage, error):
    code = getattr(error, 'code', None)
    return {'stage': stage, 'type': type(error).__name__,
            'code': code if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,63}', code) else None}


def _write_observation(root, context, kind, observation):
    """A separate exact artifact; command/sample schemas and gates stay fixed."""
    names = {'http': 'http-phases-final.json', 'import': 'import-observation.json'}
    require(kind in names, 'CAMPAIGN_OBSERVATION_KIND')
    write(root / names[kind], {
        'schema_id': 'hh-studio.benchmark-observation', 'schema_version': '1.0.0',
        'kind': kind, 'run_id': context['run_id'],
        'source_closure_sha256': context['source_closure_sha256'],
        'profile_sha256': context['profile_sha256'],
        'context': reference(root, root / 'context.json'),
        'available': observation is not None, 'observation': observation,
        'missing_reason': 'PRODUCER_NOT_CREATED' if observation is None else None,
        'formal_acceptance': False,
        'scope': 'Always-on bounded observation; no timing/overhead subtraction or acceptance override'})


def verify_observations(root, context, child):
    """Bind the new observation artifacts without treating telemetry as PASS."""
    for kind, name in [('http', 'http-phases-final.json'), ('import', 'import-observation.json')]:
        value = json.loads(read_regular(root / name))
        require(value.get('schema_id') == 'hh-studio.benchmark-observation'
                and value.get('schema_version') == '1.0.0' and value.get('kind') == kind
                and value.get('run_id') == context['run_id']
                and value.get('source_closure_sha256') == context['source_closure_sha256']
                and value.get('profile_sha256') == context['profile_sha256']
                and value.get('context') == reference(root, root / 'context.json')
                and value.get('available') is True and value.get('missing_reason') is None
                and type(value.get('observation')) is dict and value.get('formal_acceptance') is False,
                'CAMPAIGN_OBSERVATION_BINDING')
        if kind == 'http':
            require(value['observation'].get('pid') == child['processes']['host']['pid'],
                    'CAMPAIGN_OBSERVATION_HOST_IDENTITY')
            validate_phase_snapshot(value['observation'], child['processes']['host']['pid'])
        else:
            validate_import_snapshot(value['observation'])
            identity = value['observation']['target_identity']
            if identity is not None:
                target = _target_exit_state(root, 'import-host')['actual_target_exit']
                require(target is not None and target['pid'] == identity['pid'],
                        'CAMPAIGN_OBSERVATION_IMPORT_IDENTITY')


def _observed_import(root, context, project, executable, binary_hash, observer, errors):
    """Never let observer cleanup or persistence erase the import's failure."""
    primary = None
    local_errors = []
    try:
        observer.start()
        return native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=context['source_files'], source_root=STUDIO,
            binary_sha256=binary_hash)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            observer.close()
        except BaseException as error:
            local_errors.append(('import_observer_close', error))
        try:
            snapshot = observer.snapshot()
            _write_observation(root, context, 'import', snapshot)
            validate_import_snapshot(snapshot)
        except BaseException as error:
            local_errors.append(('import_observation_receipt', error))
        errors.extend(local_errors)
        if local_errors and primary is None:
            raise BenchmarkJobError('CAMPAIGN_IMPORT_OBSERVATION_INCOMPLETE') from local_errors[0][1]


def _probe_cleanup_state(probe):
    if probe is None:
        return {'present': False}
    return {'present': True, 'handle_retained': probe.handle is not None,
            'close_uncertain': probe.close_uncertain}


def _import_cleanup_state(observer):
    if observer is None:
        return {'present': False}
    snapshot = observer.snapshot()
    fields = ('closed', 'thread_alive', 'handle_retained', 'handle_close_uncertain',
              'probe_handles_released', 'global_held_probe_count', 'error_count')
    return dict(present=True, **{field: snapshot[field] for field in fields})


def _producer_cleanup_state(producer):
    if producer is None:
        return {'present': False}
    host, journal = producer.host, producer.journal
    index = journal._index_store if journal is not None else None
    return {'present': True, 'closed': producer.closed, 'failed': producer.failed,
            'host': None if host is None else {
                'stopped': host._stopped.is_set(), 'closing': host._closing.is_set(),
                'threads_alive': [thread.is_alive() for thread in host._threads],
                'main_socket_closed': host._main.socket.fileno() == -1,
                'control_socket_closed': host._control.socket.fileno() == -1},
            'observer_probe': _probe_cleanup_state(producer.observer.probe)
                if producer.observer is not None else {'present': False},
            'journal': None if journal is None else {
                'cache_closed': journal._cache_closed, 'index_retained': index is not None,
                'database_retained': index._db is not None if index is not None else False,
                'directory_retained': index._dir is not None if index is not None else False}}


def _editor_cleanup_state(owner):
    if owner is None:
        return {'present': False}
    process = owner.process
    return {'present': True, 'closed': owner.closed,
            'job': owner.job.snapshot() if owner.job is not None else None,
            'wrapper_process_handle': owner.process_handle_snapshot(),
            'drain_threads_alive': [thread.is_alive() for thread in owner.threads],
            # close() already waited. Never poll a released native process handle.
            'helper_pid': process.pid if process is not None else None,
            'helper_exit_code': process.returncode if process is not None else None}


def _target_exit_state(root, role):
    """A missing target receipt never inherits its helper's exit code."""
    records, refs = {}, {}
    for kind in ('start', 'exit'):
        path = root / role / f'process-{kind}.json'
        if not path.exists():
            records[kind], refs[kind] = None, None
            continue
        raw = read_regular(path)
        record = json.loads(raw)
        keys = {'pid'} if kind == 'start' else {'pid', 'exit_code'}
        require(type(record) is dict and set(record) == keys
                and type(record['pid']) is int and record['pid'] > 0
                and (kind == 'start' or type(record['exit_code']) is int), 'CAMPAIGN_TERMINAL_EXIT_SHAPE')
        records[kind] = record
        refs[kind] = {'file': path.relative_to(root).as_posix(), 'sha256': sha(raw), 'size_bytes': len(raw)}
    if records['exit'] is not None:
        require(records['start'] is not None and records['start']['pid'] == records['exit']['pid'],
                'CAMPAIGN_TERMINAL_EXIT_IDENTITY')
    return {'actual_target_exit': records['exit'], 'start': refs['start'], 'exit': refs['exit'],
            'missing_reason': 'TARGET_EXIT_NOT_RECORDED' if records['exit'] is None else None,
            'natural_exit_not_inferred': True}


def _finish_child_cleanup(root, context, progress, batches, *, producer, probe, owner,
                          retained, done, thread, primary, errors, import_observer=None):
    """Observe every independent role after all closes, even on body failure.

    Only live checked state and exact target receipts are recorded. This is not
    a successful-run cleanup receipt or a claim about the child's own exit.
    """
    owners = [('producer', producer), ('editor_probe', probe), ('editor_owner', owner)]
    if import_observer is not None:
        owners.append(('import_observer', import_observer))
    if retained is not None and all(retained is not value for _, value in owners):
        owners.append(('constructor_owner', retained))
    for stage, action in [('heartbeat_stop', done.set),
                          ('heartbeat_join', lambda: thread.join(2) if thread.ident is not None else None)]:
        try:
            action()
        except BaseException as error:
            errors.append((stage, error))
    seen = set()
    for role, owned in owners:
        if owned is None or id(owned) in seen:
            continue
        seen.add(id(owned))
        try:
            owned.close()
        except BaseException as error:
            errors.append((role + '_close', error))

    # No close or native probe operation occurs below this point. A failed
    # snapshot cannot skip another role or erase a retained exception owner.
    observations = {}
    getters = [('heartbeat_alive', thread.is_alive),
               ('producer', lambda: _producer_cleanup_state(producer)),
               ('editor_probe', lambda: _probe_cleanup_state(probe)),
               ('editor_owner', lambda: _editor_cleanup_state(owner)),
               ('import_observer', lambda: _import_cleanup_state(import_observer)),
               ('editor_target', lambda: _target_exit_state(root, 'editor-host')),
               ('import_target', lambda: _target_exit_state(root, 'import-host'))]
    if any(role == 'constructor_owner' for role, _ in owners):
        getters.append(('constructor_owner', lambda: {'present': True,
            'job': retained.snapshot()} if isinstance(retained, native_job.cli_job.Owner)
            else {'present': True, 'state_unavailable': True}))
    for name, getter in getters:
        try:
            observations[name] = getter()
        except BaseException as error:
            observations[name] = None
            errors.append((name + '_observe', error))
    if observations.get('heartbeat_alive') is True:
        errors.append(('heartbeat_alive', BenchmarkJobError('CAMPAIGN_CLEANUP_HELD')))
    try:
        _write_observation(root, context, 'http', producer.phase_snapshot() if producer is not None else None)
    except BaseException as error:
        errors.append(('http_observation_receipt', error))
    try:
        context_ref = reference(root, root / 'context.json')
        write_cleanup(root / 'child-terminal-cleanup.json', {
            'schema_id': 'hh-studio.benchmark-child-terminal-cleanup', 'schema_version': '1.0.0',
            'run_id': context['run_id'], 'source_closure_sha256': context['source_closure_sha256'],
            'profile_sha256': context['profile_sha256'], 'context': context_ref,
            'observed_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'observed_mono_us': clock(), 'phase': dict(progress), 'completed_batches': len(batches),
            'primary_error': _cleanup_error('body', primary) if primary is not None else None,
            'errors': [_cleanup_error(stage, error) for stage, error in errors],
            'observations': observations, 'host_actual_exit': None, 'supervisor_actual_exit': None,
            'self_exit_missing_reason': 'NOT_OBSERVABLE_BY_CHILD_TERMINAL_RECORD',
            'scope': 'Post-finally cleanup observations; no benchmark acceptance or natural-exit inference',
            'formal_acceptance': False})
    except BaseException as error:
        errors.append(('terminal_receipt', error))
    if errors:
        failure = primary if primary is not None else BenchmarkJobError('CAMPAIGN_CLEANUP_HELD')
        # Keep every exception (and its cleanup_owner), plus the original role
        # references. Do not replace the initiating error's explicit cause.
        failure.cleanup_errors = tuple(error for _, error in errors)
        failure.cleanup_owners = tuple(owned for _, owned in owners if owned is not None)
        if primary is None:
            raise failure


def verify_child_terminal_cleanup(root, context, child):
    """Current runs require the new receipt; historical frozen runs are unchanged."""
    record = json.loads(read_regular(root / 'child-terminal-cleanup.json'))
    require(record['schema_id'] == 'hh-studio.benchmark-child-terminal-cleanup'
            and record['schema_version'] == '1.0.0' and record['run_id'] == context['run_id']
            and record['source_closure_sha256'] == context['source_closure_sha256']
            and record['profile_sha256'] == context['profile_sha256']
            and record['context'] == reference(root, root / 'context.json')
            and record['completed_batches'] == 35 and record['primary_error'] is None
            and record['errors'] == [] and record['formal_acceptance'] is False,
            'CAMPAIGN_TERMINAL_BINDING')
    observed = record['observations']
    require(observed['heartbeat_alive'] is False and 'constructor_owner' not in observed,
            'CAMPAIGN_TERMINAL_HELD')
    expected_import = {'present': True, 'closed': True, 'thread_alive': False,
        'handle_retained': False, 'handle_close_uncertain': False,
        'probe_handles_released': True, 'global_held_probe_count': 0, 'error_count': 0}
    imported = observed.get('import_observer')
    require(type(imported) is dict and imported.keys() == expected_import.keys()
            and all(type(imported[key]) is type(value) and imported[key] == value
                    for key, value in expected_import.items()), 'CAMPAIGN_TERMINAL_IMPORT_OBSERVER_HELD')
    producer, editor = observed['producer'], observed['editor_owner']
    for probe in (observed['editor_probe'], producer['observer_probe']):
        expected_probe = {'present': True, 'handle_retained': False, 'close_uncertain': False}
        require(type(probe) is dict and probe.keys() == expected_probe.keys()
                and all(probe[key] is value for key, value in expected_probe.items()),
                'CAMPAIGN_TERMINAL_PROBE_HELD')
    host, journal = producer['host'], producer['journal']
    require(producer['present'] is True and producer['closed'] is True
            and host['stopped'] is True and host['closing'] is True
            and all(value is False for value in host['threads_alive'])
            and host['main_socket_closed'] is True and host['control_socket_closed'] is True
            and type(journal) is dict and journal.keys() == {
                'cache_closed', 'index_retained', 'database_retained', 'directory_retained'}
            and journal['cache_closed'] is True and journal['index_retained'] is False
            and journal['database_retained'] is False and journal['directory_retained'] is False,
            'CAMPAIGN_TERMINAL_PRODUCER_HELD')
    capture = json.loads(read_regular(root / 'editor-host/capture.json'))
    require(editor['present'] is True and editor['closed'] is True
            and all(value is False for value in editor['drain_threads_alive'])
            and type(editor['helper_exit_code']) is int and editor['helper_exit_code'] == 0
            and editor['helper_exit_code'] == capture['wrapper_exit_code']
            and type(editor['helper_pid']) is int and editor['helper_pid'] > 0
            and editor['helper_pid'] != capture['actual_process_exit']['pid']
            and encoded(editor['job']) == encoded(capture['job'])
            and encoded(editor['wrapper_process_handle']) == encoded(capture['wrapper_process_handle']),
            'CAMPAIGN_TERMINAL_OWNER_HELD')
    for role in ('editor', 'import'):
        target = _target_exit_state(root, role + '-host')
        require(observed[role + '_target'] == target and target['actual_target_exit'] is not None
                and target['actual_target_exit']['exit_code'] == 0, 'CAMPAIGN_TERMINAL_TARGET_EXIT')
    require(observed['editor_target']['actual_target_exit']['pid'] == child['processes']['editor']['pid']
            and record['host_actual_exit'] is None and record['supervisor_actual_exit'] is None,
            'CAMPAIGN_TERMINAL_EXIT_SCOPE')


def run_child(root):
    factory, trusted = load_fixture()
    context = json.loads(read_regular(root / 'context.json'))
    before, run_id = context['source_files'], context['run_id']
    verify_sources(before)
    lock = json.loads(read_regular(STUDIO / 'toolchain.lock.json'))['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'full', 'source_closure_sha256': closure(before),
        'profile_sha256': profile.PROFILE_SHA256, 'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}
    project = root / 'project'
    initial = prepare(project, factory, trusted, binding)
    (project / 'benchmark/input').mkdir()
    write(root / 'initial-project-files.json', initial)
    owner = producer = probe = import_observer = None
    done = threading.Event()
    progress = {'batch': -1, 'phase': 'import'}

    def heartbeat():
        while not done.wait(1):
            print('HH_GT06_CAMPAIGN_PROGRESS ' + json.dumps({'run_id': run_id, **progress}), flush=True)

    thread = threading.Thread(target=heartbeat, daemon=True)
    batches = []
    baseline_memory = None
    primary = retained = None
    cleanup_errors = []
    try:
        thread.start()
        import_observer = ImportObserver(root / 'import-host', project, executable)
        imported = _observed_import(root, context, project, executable, lock['gui_sha256'],
                                    import_observer, cleanup_errors)
        native_job.verify_captured_stage(root / 'import-host', sha(read_regular(root / 'import-host/capture.json')))
        require(not list((project / 'benchmark/out').iterdir()), 'CAMPAIGN_IMPORT_ACTIVATED')
        snapshot = project_files(project)
        require(all(snapshot.get(name) == value for name, value in initial.items()), 'CAMPAIGN_IMPORT_DRIFT')
        write(root / 'editor-snapshot.json', snapshot)
        runtime_sources = dict(before)
        runtime_sources.update({(project / name).relative_to(STUDIO).as_posix(): value
                               for name, value in snapshot.items() if name != MUTABLE_SCENE})
        owner = BenchmarkProcess([str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
            '--', '--hh-benchmark-mode=full'], cwd=project, output=root / 'editor-host', source_root=STUDIO,
            source_files=runtime_sources, binary_sha256=lock['gui_sha256'])
        log = NativeLog(owner)
        probe = open_probe(owner, executable)
        producer = CampaignProducer(root / 'commands', run_id, log)
        processes = {'host': dict(producer.identity), 'editor': {'pid': probe.pid, 'process_start': probe.process_start}}
        for index in range(35):
            progress.update(batch=index, phase='ready')
            ready_marker = log.wait('READY', index, 20)
            ready_path = project / f'benchmark/out/ready-{index:02d}.json'
            ready_raw = read_regular(ready_path)
            ready = json.loads(ready_raw)
            require(ready_marker['sha256'] == sha(ready_raw), 'CAMPAIGN_READY_HASH')
            require(ready['run_id'] == run_id and ready['batch_index'] == index
                    and ready['source_closure_sha256'] == closure(before)
                    and ready['profile_sha256'] == profile.PROFILE_SHA256, 'CAMPAIGN_READY_BINDING')
            started = clock()
            progress['phase'] = 'commands'
            command_path = root / f'command-{index:02d}.json'
            report = producer.run_batch(index)
            write(command_path, report)
            command_ref = reference(root, command_path)
            effect_count = report['effect_count_after']
            del report
            gc.collect()
            start_path = project / f'benchmark/input/start-{index:02d}.json'
            start = {'schema_id': 'hh-studio.native-cycle-batch-start', 'schema_version': '1.0.0',
                'run_id': run_id, 'batch_index': index, 'source_closure_sha256': closure(before),
                'profile_sha256': profile.PROFILE_SHA256, 'command_batch_sha256': command_ref['sha256'],
                'ready_sha256': sha(ready_raw), 'deadline_mono_us': ready['deadline_mono_us']}
            publish(start_path, start)
            progress['phase'] = 'native_cycles'
            marker = log.wait('BATCH', index, 185)
            native_path = project / f'benchmark/out/batch-{index:02d}.json'
            native_raw = read_regular(native_path)
            native = json.loads(native_raw)
            require(marker['sha256'] == sha(native_raw) and native['pid'] == probe.pid
                    and native['run_id'] == run_id and native['index'] == index
                    and len(native['cycles']) == len(native['raw_timings']) == 100, 'CAMPAIGN_NATIVE_BATCH')
            for cycle, timing in zip(native['cycles'], native['raw_timings']):
                validate_cycle_timing(timing, cycle, native['memory'], native)
            progress['phase'] = 'joint_observation'
            host = producer._observe()
            editor = sample_editor(probe)
            ack_path = project / f'benchmark/input/ack-{index:02d}.json'
            ack = {'schema_id': 'hh-studio.native-cycle-batch-ack', 'schema_version': '1.0.0',
                'run_id': run_id, 'batch_index': index, 'native_batch_sha256': sha(native_raw),
                'source_closure_sha256': closure(before), 'profile_sha256': profile.PROFILE_SHA256,
                'deadline_mono_us': native['barrier']['deadline_mono_us']}
            ack_written = publish(ack_path, ack)
            receipt = log.wait('ACK', index, 30)
            ended = clock()
            editor['native_observation'] = {'source': 'native_ack',
                'native_mono_us': receipt['ack_observed_mono_us'], 'process_frame': receipt['process_frame'],
                'objects': receipt['objects'], 'resources': receipt['resources']}
            joint_path = root / f'joint-{index:02d}.json'
            joint = {'schema_id': 'hh-studio.benchmark-joint-observation', 'schema_version': '1.0.0',
                'run_id': run_id, 'index': index, 'profile_sha256': profile.PROFILE_SHA256,
                'source_closure_sha256': closure(before), 'native_batch_sha256': sha(native_raw),
                'command_batch_sha256': command_ref['sha256'], 'processes': processes,
                'phase': 'post_batch_quiescent', 'host_window': {'started_mono_us': started,
                    'ended_mono_us': ended, 'ack_written_mono_us': ack_written},
                'host': {'monotonic_us': host['monotonic_us'], 'counters': host['counters']},
                'editor': editor, 'host_effect_count': effect_count, 'barrier_receipt': receipt,
                'ack_ref': reference(root, ack_path)}
            write(joint_path, joint)
            batches.append({'index': index, 'command': command_ref, 'native': reference(root, native_path),
                'joint': reference(root, joint_path), 'ack': reference(root, ack_path),
                'ready': reference(root, ready_path), 'start': reference(root, start_path)})
            write(root / f'batch-capture-{index:02d}.json', batches[-1])
            bound = {name: read_artifact(root, ref) for name, ref in batches[-1].items() if name != 'index'}
            sample = assemble_sample(bound['native'], bound['command'], bound['joint'],
                run_id=run_id, index=index, processes=processes, source_closure_sha256=closure(before),
                barrier_receipt=receipt, ack=bound['ack'], ready=bound['ready'], start=bound['start'])
            write(root / f'sample-preview-{index:02d}.json', sample)
            screen_sample(sample, baseline_memory)
            if index == 4:
                baseline_memory = sample['memory']
            del native, native_raw, joint, editor, host, receipt
            del bound, sample
            gc.collect()
        progress['phase'] = 'draining'
        while log.poll() is None:
            time.sleep(.02)
        native_capture = owner.finish()
        require(not (root / 'editor-host/stderr.txt').read_bytes().strip(), 'CAMPAIGN_NATIVE_STDERR')
        index_path = project / 'benchmark/out/index.json'
        native_index = json.loads(read_regular(index_path))
        require(native_index['schema_version'] == '1.3.0'
                and native_index['completed'] is True and native_index['benchmark_complete'] is True
                and native_index['input'] == binding and native_index['pid'] == probe.pid
                and len(native_index['host_barriers']) == len(native_index['batches']) == 35,
                'CAMPAIGN_NATIVE_COMPLETION')
        first_ready = json.loads(read_regular(project / 'benchmark/out/ready-00.json'))
        first_batch = json.loads(read_regular(project / 'benchmark/out/batch-00.json'))
        validate_startup_readiness(native_index['startup_readiness'], binding=binding,
            pid=probe.pid, source_files={name: snapshot[name.removeprefix('res://')]
                for name in native_index['source_files']},
            baseline_revision=native_index['baseline_revision'],
            scene_file_sha256=snapshot[MUTABLE_SCENE],
            first_batch_started_mono_us=first_batch['started_mono_us'],
            first_cycle_root_before=first_batch['cycles'][0]['root_before'],
            run_started_mono_us=native_index['started_mono_us'],
            first_ready_mono_us=first_ready['issued_mono_us'],
            first_ready_frame=first_ready['process_frame'])
        expected_inputs = {f'benchmark/input/{kind}-{i:02d}.json' for kind in ('ack', 'start') for i in range(35)}
        after = project_files(project)
        require({k: v for k, v in after.items() if k != MUTABLE_SCENE and k not in expected_inputs}
                == {k: v for k, v in snapshot.items() if k != MUTABLE_SCENE}, 'CAMPAIGN_PROJECT_DRIFT')
        probe.close()
        producer.close()
        # Derive the retained owner/probe handle count after checked cleanup.
        # The parent independently verifies its wrapper handle after host exit.
        held_handles = sum((
            int(native_capture['job']['handle_retained']),
            int(native_capture['wrapper_process_handle']['handle_retained']),
            int(probe.handle is not None),
            int(producer.observer.probe.handle is not None),
        ))
        require(owner.closed and producer.closed and held_handles == 0, 'CAMPAIGN_CLEANUP_HELD')
        verify_sources(before)
        write(root / 'child-result.json', {'completed': True, 'formal_acceptance': False,
            'run_id': run_id, 'index': context['index'], 'sequence': SEQUENCE, 'processes': processes,
            'source_closure_sha256': closure(before), 'profile_sha256': profile.PROFILE_SHA256,
            'batches': batches, 'native_index': reference(root, index_path),
            'editor_capture': reference(root, root / 'editor-host/capture.json'),
            'import_capture': reference(root, root / 'import-host/capture.json'),
            'source_unchanged': True, 'cleanup': {'editor_exit_code': native_capture['actual_process_exit']['exit_code'],
                'editor_owned_tree_zero': native_capture['job']['zero_observed'], 'held_handles': held_handles},
            'host_exit_not_yet_observed': True})
    except BaseException as error:
        primary = error
        retained = getattr(error, 'cleanup_owner', None)
        if owner is None and isinstance(retained, BenchmarkProcess):
            owner = retained
        elif producer is None and isinstance(retained, CommandProducer):
            producer = retained
        elif probe is None and isinstance(retained, ProcessProbe):
            probe = retained
        try:
            write(root / 'child-failure.json', {'completed': False, 'formal_acceptance': False,
                'run_id': run_id, 'completed_batches': len(batches), 'phase': progress,
                'code': getattr(error, 'code', type(error).__name__), 'partial_command': getattr(error, 'report', None)})
        except BaseException as receipt_error:
            cleanup_errors.append(('failure_receipt', receipt_error))
        raise
    finally:
        _finish_child_cleanup(root, context, progress, batches, producer=producer, probe=probe,
            owner=owner, retained=retained, done=done, thread=thread, primary=primary, errors=cleanup_errors,
            import_observer=import_observer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--child-index', type=int)
    parser.add_argument('--attempt', type=int)
    args = parser.parse_args()
    require(os.name == 'nt' and re.fullmatch(r'gt06-[a-z0-9-]{1,25}', args.campaign_id), 'CAMPAIGN_ID')
    root = STUDIO / '.local/reviews' / args.campaign_id
    if args.child_index is not None:
        require(0 <= args.child_index < 10 and type(args.attempt) is int and 1 <= args.attempt <= MAX_ATTEMPTS,
                'CAMPAIGN_CHILD_ARGUMENTS')
        run_child(root / f'run-{args.child_index:02d}-attempt-{args.attempt:02d}')
        return 0
    require(args.attempt is None, 'CAMPAIGN_ARGUMENTS')
    return run_campaign(args.campaign_id, root)


if __name__ == '__main__':
    raise SystemExit(main())
