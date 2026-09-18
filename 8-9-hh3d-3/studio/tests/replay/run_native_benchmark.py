"""One owned GUI editor / one native cycle, explicitly not the full benchmark.

Coordinator CLI: python -B studio/tests/replay/run_native_benchmark.py
    --run-id gt06-benchmark-diagnostic-01
Output is a new studio/.local/reviews/<run-id>/ directory. No caller paths,
scripts, commands, counts, caps or full-mode options are accepted. Failed runs
remain intact; use a fresh run ID. Import has no activation argument/environment.
The editor uses the unchanged trusted stage's finite limits and Job ownership.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import threading
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline import native_job
from studio.host.replay.process_probe import HELD_PROBES, ProcessProbe
from studio.tests.replay import benchmark_profile
from studio.tests.replay.benchmark_readiness import ReadinessError, validate_startup_readiness

SAFE_INTEGER = (1 << 53) - 1
MUTABLE_SCENE = 'scenes/fixture.tscn'
DRIVER_SOURCES = {
    'addons/hh_benchmark/benchmark_native.gd': 'tests/replay/benchmark_native.gd',
    'addons/hh_benchmark/plugin.cfg': 'tests/replay/benchmark_plugin.cfg',
}
DIAGNOSTIC_PROFILE = {
    'schema_id': 'hh-studio.native-cycle-diagnostic-profile', 'schema_version': '1.1.0',
    'mode': 'diagnostic', 'batches': 1, 'cycles_per_batch': 1, 'warmup_batches': 0,
    'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate', 'host_integrated': False,
    'minimum_settle_frames': 4, 'minimum_settle_us': 1_100_000,
    'runner': 'studio.pipeline.native_job.run_trusted_stage',
    'wall_seconds': native_job.WALL_SECONDS, 'runner_limits_unchanged': True,
    'full_benchmark': False, 'formal_acceptance': False,
}


class DiagnosticError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise DiagnosticError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                       allow_nan=False) + '\n').encode('utf-8')


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def read_regular(path, cap=8 * 1024 * 1024):
    for component in (path, *path.parents):
        info = component.lstat()
        need(not component.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'DIAGNOSTIC_REPARSE')
    need(path.is_file() and 0 < path.stat().st_size <= cap, 'DIAGNOSTIC_FILE_SIZE')
    raw = path.read_bytes()
    need(0 < len(raw) <= cap, 'DIAGNOSTIC_FILE_SIZE')
    return raw


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if type(value) is bytes else encoded(value))


def load_fixture():
    path = STUDIO / 'godot-addon/fixture_profile.py'
    spec = importlib.util.spec_from_file_location('_gt06_benchmark_fixture', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Verifies the accepted installed-release plugin, config and UID source pins.
    return module, dict(module.trusted_files())


def source_files():
    paths = {Path(__file__).resolve(), STUDIO / 'toolchain.lock.json',
             STUDIO / 'contracts/perf-collector.schema.json',
             STUDIO / 'godot-addon/fixture_profile/source-pins.json'}
    paths.update(STUDIO / relative for relative in DRIVER_SOURCES.values())
    pins = json.loads(read_regular(STUDIO / 'godot-addon/fixture_profile/source-pins.json'))
    paths.update(STUDIO / row['source'] for row in pins['files'].values())
    # Include the actual imported local Python dependency closure, including
    # dynamically loaded accepted factory/Job modules, without unrelated tests.
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name is None:
            continue
        path = Path(name).absolute()
        if path.suffix == '.py' and path.is_relative_to(STUDIO):
            paths.add(path)
    return {path.relative_to(STUDIO).as_posix(): sha(read_regular(path))
            for path in sorted(paths)}


def project_files(project):
    result = {}
    for path in sorted(project.rglob('*')):
        relative = path.relative_to(project)
        if '.godot' in relative.parts or relative.parts[:2] == ('benchmark', 'out'):
            continue
        if path.is_file():
            result[relative.as_posix()] = sha(read_regular(path))
    return result


def prepare(project, factory, trusted, binding):
    files = dict(trusted)
    files['project.godot'] = benchmark_project_config(files['project.godot'])
    files[MUTABLE_SCENE] = factory.DEFAULT_SCENE
    files['scripts/fixture_actor.gd'] = factory.DEFAULT_SCRIPT
    for destination, source in DRIVER_SOURCES.items():
        files[destination] = read_regular(STUDIO / source)
    files['benchmark/input.json'] = encoded(binding)
    # Evidence is accessed through FileAccess, never imported as an asset.
    # Otherwise editor rescans retain a TreeItem/TextParagraph for every JSON.
    files['benchmark/.gdignore'] = b'# HH Studio benchmark evidence is not a Godot asset.\n'
    for name, raw in files.items():
        write(project / name, raw)
    (project / 'benchmark/out').mkdir()
    return {name: sha(raw) for name, raw in sorted(files.items())}


def benchmark_project_config(trusted):
    """Pinned 4.7 editor serialization, frozen before any measured mutation.

    The installed fixture remains unchanged. Godot normalizes minimal project
    text on editor startup; that is not an allowed source mutation in this run.
    Add the benchmark plugin, pinned engine feature declaration, and a fixed
    stock Output display limit and focus-independent editor sleep. Full
    stdout/stderr remain externally captured; no profile or deadline changes.
    """
    sections = {}
    current = None
    for line in trusted.decode('utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = line[1:-1]
            need(current not in sections, 'DIAGNOSTIC_PLUGIN_CONFIG')
            sections[current] = []
        elif current is None:
            need(line == 'config_version=5', 'DIAGNOSTIC_PLUGIN_CONFIG')
        else:
            sections[current].append(line)
    need(sections == {
        'application': ['config/name="HH managed fixture"', 'run/main_scene="res://scenes/fixture.tscn"'],
        'rendering': ['renderer/rendering_method="gl_compatibility"'],
        'threading': ['worker_pool/max_threads=4'],
        'editor_plugins': ['enabled=PackedStringArray("res://addons/hh_studio/plugin.cfg")'],
    }, 'DIAGNOSTIC_PLUGIN_CONFIG')
    sections['application'].append('config/features=PackedStringArray("4.7")')
    # Visible Output paragraphs own Objects. Bound the display before startup,
    # so warmup can fill it; raw counters and externally captured logs remain.
    # EditorLog retains message strings separately, still covered by RSS checks.
    # Both focus states retain the stock focused sleep. Configure before import;
    # the restart-required setting must not depend on which window has focus.
    sections['editor_overrides'] = [
        'interface/editor/display/update_continuously=false',
        'interface/editor/timers/low_processor_mode_sleep_usec=6900',
        'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=6900',
        'run/output/max_lines=100',
    ]
    sections['editor_plugins'] = ['enabled=PackedStringArray("res://addons/hh_studio/plugin.cfg", "res://addons/hh_benchmark/plugin.cfg")']
    header = ("; Engine configuration file.\n; It's best edited using the editor UI and not directly,\n"
        "; since the parameters that go here are not all obvious.\n;\n; Format:\n"
        ";   [section] ; section goes between []\n;   param=value ; assign values to parameters\n\nconfig_version=5\n")
    return (header + ''.join('\n[' + name + ']\n\n' + '\n'.join(sections[name]) + '\n'
                            for name in sorted(sections))).encode('utf-8')


def validate_cycle_timing(timing, cycle, memory, batch):
    steps = ('create', 'undo', 'save', 'reload')
    need(type(timing) is dict and set(timing) == set(steps) | {
        'index', 'generation_before', 'generation_after', 'save_signal_mono_us',
        'reload_observed_process_frame'}, 'DIAGNOSTIC_TIMING_SHAPE')
    need(integer(timing['index']) and timing['index'] == cycle['index']
         and integer(timing['generation_before'], 1)
         and integer(timing['generation_after'], 2)
         and timing['generation_after'] == timing['generation_before'] + 1, 'DIAGNOSTIC_GENERATION')
    need(integer(batch.get('started_mono_us'), 1)
         and integer(batch.get('ended_mono_us'), batch['started_mono_us'] + 1), 'DIAGNOSTIC_BATCH_CLOCK')
    previous = batch['started_mono_us']
    for step in steps:
        record, latency = timing[step], cycle['latency_ms'][step]
        need(type(record) is dict and set(record) == {'start_us', 'end_us'}
             and integer(record['start_us'], previous) and integer(record['end_us'], record['start_us'] + 1)
             and record['end_us'] <= batch['ended_mono_us'], 'DIAGNOSTIC_STEP_CLOCK')
        need(type(latency) in (float, int) and math.isfinite(latency) and latency > 0
             and abs(latency * 1000 - (record['end_us'] - record['start_us'])) < .00001, 'DIAGNOSTIC_LATENCY')
        previous = record['end_us']
    need(integer(timing['save_signal_mono_us'], timing['save']['start_us'])
         and timing['save_signal_mono_us'] <= timing['save']['end_us'] < timing['reload']['start_us'],
         'DIAGNOSTIC_SAVE_SIGNAL')
    need(integer(memory.get('process_frame'), 1) and integer(memory.get('settle_frames'), 4)
         and integer(timing['reload_observed_process_frame'], 1)
         and timing['reload_observed_process_frame'] < memory['process_frame'] - memory['settle_frames'],
         'DIAGNOSTIC_RELOAD_FRAME')


class Sampler:
    """Read-only PID/creation identity/RSS/window observations; no process kills."""
    def __init__(self, output, executable):
        self.output, self.executable = output, executable
        self.done = threading.Event()
        self.rows, self.errors, self.identity = [], [], None
        self.thread = threading.Thread(target=self._run, name='benchmark-process-probe', daemon=True)

    def _run(self):
        probe = None
        start = time.monotonic()
        try:
            while not self.done.wait(.025):
                need(time.monotonic() - start <= native_job.WALL_SECONDS + 2, 'DIAGNOSTIC_PROBE_DEADLINE')
                if probe is None:
                    try:
                        record = json.loads((self.output / 'process-start.json').read_bytes())
                    except (FileNotFoundError, json.JSONDecodeError):
                        continue
                    need(set(record) == {'pid'}, 'DIAGNOSTIC_PROCESS_START')
                    probe = ProcessProbe(record['pid'], self.executable)
                    self.identity = {'pid': probe.pid, 'process_start': probe.process_start}
                row = probe.sample()
                if row is None:
                    break
                need(len(self.rows) < 1000, 'DIAGNOSTIC_SAMPLE_CAP')
                self.rows.append(row)
        except BaseException as error:
            self.errors.append(type(error).__name__)
        finally:
            if probe is not None:
                try:
                    probe.close()
                except BaseException as error:
                    self.errors.append(type(error).__name__)

    def close(self):
        self.done.set()
        self.thread.join(2)
        need(not self.thread.is_alive(), 'DIAGNOSTIC_PROBE_DRAIN')


def integer(value, low=0):
    return type(value) is int and low <= value <= SAFE_INTEGER


def digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def markers(raw, prefix):
    return [json.loads(line[len(prefix):]) for line in raw.decode('utf-8').splitlines()
            if line.startswith(prefix)]


def validate_native(project, binding, snapshot, stage, process, lock):
    need(set(binding) == {'schema_id', 'schema_version', 'run_id', 'mode', 'source_closure_sha256',
         'profile_sha256', 'batch_barrier', 'batch_start'}
         and binding.get('schema_id') == 'hh-studio.native-cycle-benchmark-run'
         and binding.get('schema_version') == '1.2.0' and binding.get('mode') == 'diagnostic'
         and binding.get('batch_barrier') == 'diagnostic_none'
         and binding.get('batch_start') == 'diagnostic_immediate', 'DIAGNOSTIC_INPUT_PROFILE')
    index_raw = read_regular(project / 'benchmark/out/index.json', 1_048_576)
    batch_raw = read_regular(project / 'benchmark/out/batch-00.json', 1_048_576)
    index, batch = json.loads(index_raw), json.loads(batch_raw)
    pid = stage['actual_process_exit']['pid']
    need(process['identity'] is not None and process['identity']['pid'] == pid
         and process['samples'] and not process['errors'], 'DIAGNOSTIC_PROCESS_OBSERVATION')
    need(any(row['visible_window_handles'] for row in process['samples']), 'DIAGNOSTIC_GUI_WINDOW')
    need(index.get('schema_id') == 'hh-studio.native-cycle-benchmark' and index.get('schema_version') == '1.3.0'
         and index.get('input') == binding and index.get('pid') == pid, 'DIAGNOSTIC_INDEX_BINDING')
    need(index.get('completed') is True and index.get('benchmark_complete') is False
         and index.get('formal_acceptance') is False and index.get('host_integrated') is False
         and index.get('host_barriers') == [] and index.get('start_permits') == []
         and index.get('batch_order') == 'diagnostic_native_cycle_only'
         and index.get('host_start_timeout_us') == 600_000_000
         and index.get('host_barrier_timeout_us') == 30_000_000 and index.get('batches_completed') == 1
         and index.get('cycles_per_batch') == 1, 'DIAGNOSTIC_SCOPE')
    need(index.get('editor_hint') is True and index.get('main_thread') is True
         and index.get('display_server') == 'Windows'
         and index.get('engine', {}).get('hash') == lock['source_commit'], 'DIAGNOSTIC_NATIVE_CONTEXT')
    expected_ref = {'index': 0, 'file': 'batch-00.json', 'sha256': sha(batch_raw), 'size_bytes': len(batch_raw)}
    need(index.get('batches') == [expected_ref], 'DIAGNOSTIC_BATCH_REFERENCE')
    native_sources = index.get('source_files')
    required_sources = {'res://' + name for name in (
        'addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd', 'addons/hh_studio/jcs_godot.gd',
        'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', 'addons/hh_benchmark/benchmark_native.gd',
        'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json',
        'benchmark/.gdignore')}
    need(type(native_sources) is dict and set(native_sources) == required_sources
         and all(snapshot[name.removeprefix('res://')] == value for name, value in native_sources.items()),
         'DIAGNOSTIC_NATIVE_SOURCE')
    need(batch.get('schema_id') == 'hh-studio.native-cycle-batch' and batch.get('schema_version') == '1.2.0'
         and batch.get('run_id') == binding['run_id'] and batch.get('pid') == pid
         and batch.get('index') == 0 and batch.get('mode') == 'diagnostic' and batch.get('warmup') is False
         and batch.get('barrier') == {'mode': 'diagnostic_none', 'required': False}
         and 'start_permit' in batch and batch['start_permit'] is None, 'DIAGNOSTIC_BATCH_BINDING')
    need(type(batch.get('cycles')) is list and len(batch['cycles']) == 1
         and type(batch.get('raw_timings')) is list and len(batch['raw_timings']) == 1, 'DIAGNOSTIC_CYCLE_COUNT')
    cycle, timing = batch['cycles'][0], batch['raw_timings'][0]
    fields = 'index root_before root_after before_sha256 created_sha256 undone_sha256 saved_file_sha256 reloaded_sha256 latency_ms effects main_thread'.split()
    need(type(cycle) is dict and set(cycle) == set(fields) and cycle['index'] == 0 and cycle['main_thread'] is True,
         'DIAGNOSTIC_CYCLE_SHAPE')
    need(integer(cycle['root_before'], 1) and integer(cycle['root_after'], 1)
         and cycle['root_before'] != cycle['root_after'], 'DIAGNOSTIC_ROOT_CHANGE')
    try:
        validate_startup_readiness(index.get('startup_readiness'), binding=binding, pid=pid,
            source_files=native_sources, baseline_revision=index.get('baseline_revision'),
            scene_file_sha256=snapshot[MUTABLE_SCENE], first_batch_started_mono_us=batch.get('started_mono_us'),
            first_cycle_root_before=cycle['root_before'], run_started_mono_us=index.get('started_mono_us'))
    except ReadinessError as error:
        raise DiagnosticError(error.code) from error
    need(all(digest(cycle[key]) for key in ('before_sha256', 'created_sha256', 'undone_sha256',
         'saved_file_sha256', 'reloaded_sha256')) and cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256']
         and cycle['created_sha256'] != cycle['before_sha256']
         and index.get('baseline_revision') == 'sha256:' + cycle['before_sha256']
         and sha(read_regular(project / MUTABLE_SCENE)) == cycle['saved_file_sha256'], 'DIAGNOSTIC_SEMANTIC_READBACK')
    steps = ('create', 'undo', 'save', 'reload')
    need(cycle['effects'] == dict.fromkeys(steps, 1) and set(cycle['latency_ms']) == set(steps), 'DIAGNOSTIC_EFFECTS')
    memory = batch.get('memory', {})
    validate_cycle_timing(timing, cycle, memory, batch)
    need(memory.get('phase') == 'post_batch_quiescent' and memory.get('settle_frames', 0) >= 4
         and memory.get('settle_us', 0) >= 1_100_000 and memory.get('monotonic_us') == batch.get('ended_mono_us')
         and index.get('quiescence') == {'minimum_frames': 4, 'minimum_us': 1_100_000}, 'DIAGNOSTIC_QUIESCENCE')
    for name in ('objects', 'resources'):
        counter = memory.get('editor', {}).get(name, {})
        need(integer(counter.get('value'), 1 if name == 'objects' else 0)
             and counter.get('unavailable_reason') is None, 'DIAGNOSTIC_NATIVE_COUNTER')
    need(index.get('heartbeat_target_met') is True and 0 <= index.get('max_status_gap_ms', -1) <= 2000
         and batch.get('dropped_commands') == 0 and batch.get('dropped_telemetry') == 0, 'DIAGNOSTIC_TELEMETRY')
    need(set(path.name for path in (project / 'benchmark/out').iterdir()) == {'batch-00.json', 'index.json'},
         'DIAGNOSTIC_OUTPUT_SET')
    return index, batch, index_raw, batch_raw


def run(run_id):
    need(os.name == 'nt' and type(run_id) is str and re.fullmatch('gt06-[a-z0-9-]{1,59}', run_id),
         'DIAGNOSTIC_RUN_ID')
    factory, trusted = load_fixture()
    before = source_files()
    lock_raw = read_regular(STUDIO / 'toolchain.lock.json')
    lock = json.loads(lock_raw)['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(sha(read_regular(executable, 256 * 1024 * 1024)) == lock['gui_sha256'], 'DIAGNOSTIC_ENGINE_PIN')
    profile_raw = json.dumps(asdict(benchmark_profile.PROFILE), sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    need(sha(profile_raw) == benchmark_profile.PROFILE_SHA256, 'DIAGNOSTIC_PROFILE_HASH')
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'diagnostic', 'source_closure_sha256': closure(before),
        'profile_sha256': benchmark_profile.PROFILE_SHA256, 'batch_barrier': 'diagnostic_none',
        'batch_start': 'diagnostic_immediate'}
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = root / 'project'
    initial = prepare(project, factory, trusted, binding)
    for name, expected in before.items():
        raw = read_regular(STUDIO / name)
        need(sha(raw) == expected, 'DIAGNOSTIC_SOURCE_FREEZE')
        write(root / 'source/studio' / name, raw)
    write(root / 'source-files.json', before)
    write(root / 'initial-project-files.json', initial)
    write(root / 'benchmark-profile.json', profile_raw)
    write(root / 'diagnostic-profile.json', DIAGNOSTIC_PROFILE)
    write(root / 'initial-scene.tscn', read_regular(project / MUTABLE_SCENE))
    write(root / 'invocation.json', {'run_id': run_id, 'mode': 'diagnostic', 'root': str(root),
        'project': str(project), 'executable': str(executable), 'binary_sha256': lock['gui_sha256'],
        'python_executable': sys.executable, 'python_executable_sha256': sha(read_regular(Path(sys.executable), 256 * 1024 * 1024)),
        'toolchain_sha256': sha(lock_raw), 'source_closure_sha256': closure(before),
        'source_files': before, 'benchmark_profile_sha256': sha(profile_raw),
        'diagnostic_profile_sha256': sha(encoded(DIAGNOSTIC_PROFILE)),
        'input_sha256': sha(encoded(binding)), 'binding': binding,
        'mutable_project_paths': [MUTABLE_SCENE], 'full_benchmark': False, 'formal_acceptance': False})
    stages = {}
    try:
        stages['import'] = native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=before, source_root=STUDIO,
            binary_sha256=lock['gui_sha256'])
        need(not list((project / 'benchmark/out').iterdir()), 'DIAGNOSTIC_IMPORT_ACTIVATED')
        snapshot = project_files(project)
        need(all(snapshot.get(name) == value for name, value in initial.items()), 'DIAGNOSTIC_IMPORT_SOURCE_DRIFT')
        write(root / 'editor-snapshot.json', snapshot)
        runtime_source = dict(before)
        runtime_source.update({(project / name).relative_to(STUDIO).as_posix(): value
                               for name, value in snapshot.items() if name != MUTABLE_SCENE})
        sampler = Sampler(root / 'editor-host', executable)
        sampler.thread.start()
        started_utc_ms = time.time_ns() // 1_000_000
        try:
            stages['editor'] = native_job.run_trusted_stage(
                [str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
                 '--', '--hh-benchmark-mode=diagnostic'], cwd=project, output=root / 'editor-host',
                source_files=runtime_source, source_root=STUDIO, binary_sha256=lock['gui_sha256'])
        finally:
            try:
                sampler.close()
            finally:
                process = {'identity': sampler.identity, 'samples': sampler.rows, 'errors': sampler.errors,
                           'started_utc_ms': started_utc_ms, 'ended_utc_ms': time.time_ns() // 1_000_000}
                write(root / 'process-metrics.json', process)
        captures = {}
        for name, directory in (('import', 'import-host'), ('editor', 'editor-host')):
            raw = read_regular(root / directory / 'capture.json')
            native_job.verify_captured_stage(root / directory, sha(raw))
            captures[name] = sha(raw)
            stderr = (root / directory / 'stderr.txt').read_bytes()
            stdout = (root / directory / 'stdout.txt').read_bytes()
            need(not stderr.strip() and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked', stdout),
                 'DIAGNOSTIC_NATIVE_LOG')
        index, batch, index_raw, batch_raw = validate_native(project, binding, snapshot, stages['editor'], process, lock)
        stdout = read_regular(root / 'editor-host/stdout.txt', native_job.LOG_BYTES)
        complete = markers(stdout, 'HH_GT06_BENCHMARK_COMPLETE ')
        expected = {'run_id': run_id, 'pid': process['identity']['pid'], 'mode': 'diagnostic',
                    'batches': 1, 'index_sha256': sha(index_raw), 'benchmark_complete': False, 'host_integrated': False}
        need(complete == [expected] and not markers(stdout, 'HH_GT06_BENCHMARK_FAILED ')
             and not markers(stdout, 'HH_GT06_BENCHMARK_ACK ')
             and not markers(stdout, 'HH_GT06_BENCHMARK_READY ')
             and not markers(stdout, 'HH_GT06_BENCHMARK_START '), 'DIAGNOSTIC_COMPLETE_MARKER')
        batch_markers = markers(stdout, 'HH_GT06_BENCHMARK_BATCH ')
        need(batch_markers == [{'run_id': run_id, 'pid': process['identity']['pid'], 'index': 0,
             'sha256': sha(batch_raw), 'memory_mono_us': batch['ended_mono_us'],
             'barrier': {'mode': 'diagnostic_none', 'required': False}}], 'DIAGNOSTIC_BATCH_MARKER')
        after = project_files(project)
        need({k: v for k, v in after.items() if k != MUTABLE_SCENE}
             == {k: v for k, v in snapshot.items() if k != MUTABLE_SCENE}, 'DIAGNOSTIC_PROJECT_DRIFT')
        need(source_files() == before, 'DIAGNOSTIC_SOURCE_DRIFT')
        write(root / 'final-scene.tscn', read_regular(project / MUTABLE_SCENE))
        write(root / 'final-project-files.json', after)
        result = {'schema_id': 'hh-studio.native-cycle-diagnostic-capture', 'schema_version': '1.0.0',
            'run_id': run_id, 'completed_diagnostic': True, 'full_benchmark': False,
            'formal_acceptance': False, 'public_ack': False, 'host_integrated': False,
            'binding': binding, 'process': process['identity'], 'source_unchanged': True,
            'binary_sha256': lock['gui_sha256'], 'profile_sha256': sha(profile_raw),
            'input_sha256': sha(encoded(binding)), 'index_sha256': sha(index_raw),
            'batch_sha256': sha(batch_raw), 'stage_captures': captures,
            'actual_exits': {name: value['actual_process_exit'] for name, value in stages.items()},
            'jobs': {name: value['job'] for name, value in stages.items()},
            'process_metrics_sha256': sha(read_regular(root / 'process-metrics.json')),
            'scope': 'one GUI editor, one direct-semantic cycle; no full campaign or host/API mix'}
        write(root / 'capture.json', result)
        return result
    except BaseException as error:
        write(root / 'diagnostic-failure.json', {'run_id': run_id, 'completed_diagnostic': False,
            'full_benchmark': False, 'formal_acceptance': False, 'error_type': type(error).__name__,
            'code': str(error) if isinstance(error, (DiagnosticError, native_job.StageFailed)) else 'DIAGNOSTIC_EXCEPTION',
            'cleanup_owner_retained': getattr(error, 'cleanup_owner', None) is not None or bool(HELD_PROBES)})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.run_id), sort_keys=True))
