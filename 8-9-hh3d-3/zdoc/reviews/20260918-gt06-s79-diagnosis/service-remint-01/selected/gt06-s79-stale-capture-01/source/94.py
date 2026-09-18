"""Bounded internal GT06 native lane over a verified GT05 asset copy.

This is a trusted fixture runner, not an arbitrary executable/project endpoint.
Only the coordinator supplies run IDs and the fixed declarative configuration.
Native completion is separated from gameplay/postcondition acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
from studio.pipeline.godot import consumer
from studio.host.replay.process_probe import ProcessProbe
from studio.host.replay.trace import default_trace, validate_trace

ACCEPTED_MANIFEST = STUDIO.parent / 'zdoc/reviews/20260917-gt05-s63-audit/manifest.json'
MANIFEST_SHA = 'fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b'
TEXT_SUFFIXES = {'.py', '.gd', '.godot', '.tscn', '.tres', '.uid', '.json', '.md'}


class ReplayError(ValueError):
    pass


def need(value, code):
    if not value:
        raise ReplayError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def read_regular(path, cap=8 * 1024 * 1024):
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not parent.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPLAY_REPARSE')
    need(path.is_file() and 0 < path.stat().st_size <= cap, 'REPLAY_FILE_SIZE')
    raw = path.read_bytes()
    need(0 < len(raw) <= cap, 'REPLAY_FILE_SIZE')
    return raw


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if type(value) is bytes else encoded(value))


def accepted_inputs():
    raw = read_regular(ACCEPTED_MANIFEST)
    need(sha(raw) == MANIFEST_SHA, 'REPLAY_ACCEPTED_MANIFEST')
    manifest = json.loads(raw)
    inputs = {}
    for name in consumer.INPUTS:
        relative = '.local/reviews/gt05-validation-s62-01/' + name
        data = read_regular(STUDIO / relative)
        need(manifest['raw_files'].get(relative) == sha(data), 'REPLAY_ASSET_BINDING')
        inputs[name] = data
    return inputs, manifest


def sources(manifest):
    result = {}
    prefix = '8-9-hh3d-3/studio/'
    for name, digest in manifest['source_files'].items():
        need(name.startswith(prefix), 'REPLAY_SOURCE_DOMAIN')
        relative = name[len(prefix):]
        need(sha(read_regular(STUDIO / relative)) == digest, 'REPLAY_REUSE_SOURCE_CHANGED')
        result[relative] = digest
    # Initial native diagnostics bind their execution dependencies. Unrelated
    # perf/observation authors may continue writing while the engine runs.
    for directory in ('godot-addon/observe', 'fixtures/play-observe'):
        for path in (STUDIO / directory).rglob('*'):
            if path.is_file() and path.suffix in ('.gd', '.uid', '.godot', '.tscn', '.tres'):
                result[path.relative_to(STUDIO).as_posix()] = sha(read_regular(path))
    for name in ('godot-addon/script_profile.py', 'host/replay/native_runner.py',
                 'host/replay/process_probe.py', 'host/replay/trace.py', 'host/replay/profile.json'):
        result[name] = sha(read_regular(STUDIO / name))
    return dict(sorted(result.items()))


def configuration(speed):
    need(speed in ('0.0', '3.0'), 'REPLAY_FIXED_SPEED')
    data = ('extends Node3D\n@export var fixture_value: int = 1\n'
            '@export var move_speed: float = ' + speed + '\n').encode()
    path = STUDIO / 'godot-addon/script_profile.py'
    spec = importlib.util.spec_from_file_location('gt06_declarative_profile', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.validate_script(data)
    return data


def prepare(root, trace, config, inputs):
    project = root / 'project'
    project.mkdir()
    for relative, destination in (('fixtures/play-observe', ''), ('godot-addon/observe', 'observe')):
        source = STUDIO / relative
        need(source.is_dir(), 'REPLAY_SOURCE_MISSING')
        for path in source.rglob('*'):
            if path.is_file() and path.suffix in ('.gd', '.uid', '.tscn', '.godot', '.tres'):
                write(project / destination / path.relative_to(source), read_regular(path))
    for name in ('authored.gd', 'authored_material.tres'):
        write(project / 'gt05' / name, read_regular(STUDIO / 'pipeline/godot' / name))
    for name, raw in inputs.items():
        write(project / 'input' / name, raw)
    write(project / 'input/fixture.glb.import', consumer.PRESET.encode())
    write(project / 'input/trace.json', trace.raw)
    write(project / 'config/fixture_actor.gd', config)
    (project / 'out').mkdir()
    return project


class Sampler:
    """Poll only the PID emitted by the owned stage, then retain its handle."""
    def __init__(self, output, executable):
        self.output, self.executable = output, executable
        self.done = threading.Event()
        self.rows, self.identity, self.errors = [], None, []
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        probe = None
        started = time.monotonic()
        try:
            while not self.done.wait(.025):
                if time.monotonic() - started > 22:
                    raise ReplayError('REPLAY_SAMPLER_DEADLINE')
                if probe is None:
                    try:
                        raw = (self.output / 'process-start.json').read_bytes()
                        start = json.loads(raw)
                    except (FileNotFoundError, json.JSONDecodeError):
                        continue
                    need(set(start) == {'pid'}, 'REPLAY_START_SHAPE')
                    probe = ProcessProbe(start['pid'], self.executable)
                    self.identity = {'pid': probe.pid, 'process_start': probe.process_start}
                row = probe.sample()
                if row is None:
                    break
                need(len(self.rows) < 1000, 'REPLAY_RSS_CAP')
                self.rows.append(row)
        except BaseException as error:
            self.errors.append(type(error).__name__ + ':' + str(error))
        finally:
            if probe is not None:
                try:
                    probe.close()
                except BaseException as error:
                    self.errors.append(type(error).__name__ + ':' + str(error))

    def close(self):
        self.done.set()
        self.thread.join(2)
        need(not self.thread.is_alive(), 'REPLAY_SAMPLER_DRAIN')


def run(run_id, *, speed='3.0', seed=17, stop=None, config_bytes=None, repair_binding=None):
    need(os.name == 'nt' and re.fullmatch('gt06-[a-z0-9-]{1,80}', run_id), 'REPLAY_RUN_ID')
    inputs, accepted = accepted_inputs()
    before = sources(accepted)
    trace, config = default_trace(seed), configuration(speed)
    if config_bytes is not None:
        # Internal managed-repair composition only. The fixed native fixture
        # cannot be used to inject general GDScript or change its profile.
        need(type(config_bytes) is bytes and config_bytes == config and type(repair_binding) is dict,
             'REPLAY_MANAGED_CONFIG')
        config = config_bytes
    else:
        need(repair_binding is None, 'REPLAY_REPAIR_WITHOUT_CONFIG')
    validate_trace(trace.raw)
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = prepare(root, trace, config, inputs)
    write(root / 'source-files.json', before)
    for index, name in enumerate(before):
        write(root / 'source' / (str(index) + Path(name).suffix), read_regular(STUDIO / name))
    write(root / 'invocation.json', {'run_id': run_id, 'speed': speed, 'seed': seed,
        'source_files': before, 'source_closure_sha256': closure(before), 'accepted_gt05_manifest_sha256': MANIFEST_SHA,
        'scope': 'trusted fixed fixture diagnostic; no formal acceptance',
        'managed_repair_binding': repair_binding})
    lock = json.loads(read_regular(STUDIO / 'toolchain.lock.json'))['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    import_result = run_trusted_stage([str(executable), '--headless', '--editor', '--path', str(project), '--import'],
        cwd=project, output=root / 'import-host', source_files=before, source_root=STUDIO,
        binary_sha256=lock['gui_sha256'], stop=stop)
    # run.json carries the digest of all runtime input/script bytes except itself.
    # Generated cache is separately retained evidence, not promoted to source.
    snapshot = {p.relative_to(project).as_posix(): sha(read_regular(p)) for p in project.rglob('*')
        if p.is_file() and '.godot' not in p.relative_to(project).parts and 'out' not in p.relative_to(project).parts}
    binding = {'run_id': run_id, 'command_id': run_id + '.play', 'runtime_instance_id': run_id + '.runtime',
        'source_closure_sha256': closure(before), 'runtime_snapshot_sha256': closure(snapshot),
        'trace_sha256': trace.raw_sha256, 'glb_sha256': sha(inputs['fixture.glb']), 'generation': 1}
    write(root / 'runtime-snapshot.json', snapshot)
    write(project / 'input/run.json', binding)
    runtime_source = dict(before)
    runtime_source.update({(project / name).relative_to(STUDIO).as_posix(): digest for name, digest in snapshot.items()})
    runtime_source[(project / 'input/run.json').relative_to(STUDIO).as_posix()] = sha(encoded(binding))
    sampler = Sampler(root / 'runtime-host', executable)
    sampler.thread.start()
    start_utc_ms, host_start_us = time.time_ns() // 1000000, time.perf_counter_ns() // 1000
    runtime_result = None
    try:
        runtime_result = run_trusted_stage([str(executable), '--path', str(project)], cwd=project,
            output=root / 'runtime-host', source_files=runtime_source, source_root=STUDIO,
            binary_sha256=lock['gui_sha256'], stop=stop)
    finally:
        sampler.close()
        write(root / 'process-metrics.json', {'identity': sampler.identity, 'samples': sampler.rows,
            'errors': sampler.errors, 'started_utc_ms': start_utc_ms, 'ended_utc_ms': time.time_ns() // 1000000,
            'host_start_mono_us': host_start_us, 'host_end_mono_us': time.perf_counter_ns() // 1000})
    need(not sampler.errors and sampler.identity is not None and sampler.rows, 'REPLAY_PROCESS_METRICS')
    need(sampler.identity['pid'] == runtime_result['actual_process_exit']['pid'], 'REPLAY_NATIVE_PID')
    report_raw = read_regular(project / 'out/report.json')
    report = json.loads(report_raw)
    need(report.get('binding') == binding and report.get('completed') is True, 'REPLAY_REPORT_BINDING')
    need(report['native']['pid'] == sampler.identity['pid'], 'REPLAY_OBSERVED_PID')
    need(str(report['native']['native_window_handle']) in {h for row in sampler.rows for h in row['visible_window_handles']}, 'REPLAY_NATIVE_WINDOW')
    markers = [json.loads(line.split(' ', 1)[1]) for line in (root / 'runtime-host/stdout.txt').read_text(encoding='utf-8').splitlines()
               if line.startswith('HH_GT06_COMPLETE ')]
    need(len(markers) == 1 and markers[0]['report_sha256'] == sha(report_raw)
         and all(markers[0][key] == binding[key] for key in ('run_id', 'command_id', 'runtime_instance_id'))
         and markers[0]['pid'] == sampler.identity['pid'], 'REPLAY_COMPLETE_MARKER')
    for phase in ('import', 'runtime'):
        capture = root / (phase + '-host')
        verify_captured_stage(capture, sha(read_regular(capture / 'capture.json')))
        need(not (capture / 'stderr.txt').read_bytes().strip(), 'REPLAY_STDERR')
        need(not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', (capture / 'stdout.txt').read_bytes()), 'REPLAY_LOG_ERROR')
    need(sources(accepted) == before, 'REPLAY_SOURCE_CHANGED')
    result = {'schema': 'HH-GT06-NATIVE-CAPTURE-1', 'run_id': run_id, 'completed_native': True,
        'formal_acceptance': False, 'public_ack': False, 'binding': binding,
        'process': sampler.identity, 'report_sha256': sha(report_raw), 'source_unchanged': True,
        'import_capture_sha256': sha(read_regular(root / 'import-host/capture.json')),
        'runtime_capture_sha256': sha(read_regular(root / 'runtime-host/capture.json')),
        'process_metrics_sha256': sha(read_regular(root / 'process-metrics.json'))}
    write(root / 'capture.json', result)
    print(json.dumps(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--speed', choices=('0.0', '3.0'), default='3.0')
    parser.add_argument('--seed', type=int, default=17)
    args = parser.parse_args()
    run(args.run_id, speed=args.speed, seed=args.seed)
