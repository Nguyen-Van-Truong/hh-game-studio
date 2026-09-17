"""Archive and verify existing S71 A/B evidence only; never launch an engine.

Fixed input roots. Imports only preserved verification functions, not either
diagnostic collector. Exclusive/idempotent matching writes under this directory.
The original failure/result and all raw roots remain unchanged.
"""
import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys
import types

OUT = Path(__file__).resolve().parent
SCOPE = Path(__file__).resolve().parents[4]
STUDIO = SCOPE / 'studio'
GROWTH = OUT.parent
COPIES = {}
MAX_FILE_BYTES = 8 * 1024 * 1024


def need(value, message):
    if not value:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def raw(path):
    for part in (path, *path.parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
             f'reparse path: {part}')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= MAX_FILE_BYTES,
         f'not bounded regular file: {path}')
    value = path.read_bytes()
    need(len(value) == info.st_size, f'changed during read: {path}')
    return value


def obj(path):
    return json.loads(raw(path))


def relative(value):
    need(type(value) is str and '\\' not in value and not Path(value).is_absolute()
         and all(p not in ('', '.', '..') for p in value.split('/')), 'unsafe relative path')
    return value


def write(path, value):
    need(path.is_relative_to(OUT), 'write outside collection lease')
    data = value if type(value) is bytes else (json.dumps(value, indent=2, sort_keys=True,
                                                        allow_nan=False) + '\n').encode()
    if path.exists():
        need(raw(path) == data, f'existing archive differs: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    need(raw(path) == data, 'write readback')


def copy(source, target, expected=None):
    data = raw(source)
    digest = sha(data)
    if expected is not None:
        need(digest == expected, f'frozen source hash mismatch: {source}')
    write(target, data)
    need(sha(raw(source)) == digest, f'original changed after copy: {source}')
    COPIES[target.relative_to(OUT).as_posix()] = {
        'source': str(source), 'size_bytes': len(data), 'sha256': digest,
        'copy_byte_verified': True, 'source_rehashed_after_copy': True,
    }


def setup(cap):
    run_id = f'gt06-s71-output-cap-{cap}-01'
    original = STUDIO / '.local/reviews' / run_id
    target = OUT / f'cap-{cap}'
    diagnostic = obj(original / 'diagnostic.json')
    runtime = obj(original / 'runtime-source-files.json')
    source = diagnostic['source_files']
    need(diagnostic['run_id'] == run_id and diagnostic['output_max_lines'] == cap
         and diagnostic['batches'] == 3 and diagnostic['cycles_per_batch'] == 50
         and diagnostic['full_benchmark'] is False and diagnostic['formal_acceptance'] is False,
         'diagnostic dimensions/binding')
    collector = GROWTH / ('diagnose_output_retention-v1.py' if cap == 10000 else 'diagnose_output_retention.py')
    copy(collector, target / 'collector.py', diagnostic['runner_sha256'])
    for name in ('diagnostic.json', 'runtime-source-files.json', 'failure.json' if cap == 10000 else 'result.json'):
        copy(original / name, target / name)
    for owner in ('import-host', 'editor-host'):
        for name in ('capture.json', 'invocation.json', 'process-start.json', 'process-exit.json', 'stdout.txt', 'stderr.txt'):
            copy(original / owner / name, target / owner / name)
    copy(original / 'editor-host/cleanup-001.json', target / 'editor-host/cleanup-001.json')

    # Reconstruct the exact old source-root namespace. Base source always comes
    # from that arm's frozen source/studio; runtime project files come only from
    # the exact recorded project prefix, never changed live production sources.
    verification = target / 'verification-source/studio'
    prefix = f'.local/reviews/{run_id}/project/'
    need(all(runtime.get(name) == digest for name, digest in source.items()), 'runtime/base map mismatch')
    for name, digest in runtime.items():
        relative(name)
        if name in source:
            origin = original / 'source/studio' / name
        else:
            need(name.startswith(prefix), 'unexpected runtime source path')
            origin = original / 'project' / relative(name[len(prefix):])
        copy(origin, verification / name, digest)
    project = verification / prefix
    copy(original / 'project/scenes/fixture.tscn', project / 'scenes/fixture.tscn')
    for name in ('index.json', 'batch-00.json', 'batch-01.json', 'batch-02.json'):
        copy(original / 'project/benchmark/out' / name, project / 'benchmark/out' / name)
    return {'cap': cap, 'run_id': run_id, 'original': original, 'target': target,
            'diagnostic': diagnostic, 'runtime': runtime, 'source': source,
            'verification': verification, 'project': project}


def frozen_helpers(verification):
    # The original dynamic Python map omitted perf-collector.schema.json.
    # Do not fill that gap with today's live schema. These exact pure helper
    # definitions use no schema data, process launch, fixture loader or worker.
    def selected_module(relative_path, names, module_name):
        path = verification / relative_path
        parsed = ast.parse(raw(path), filename=str(path))
        nodes = []
        for node in parsed.body:
            selected = isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names
            if isinstance(node, ast.Assign):
                selected = any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
            if selected:
                nodes.append(node)
        module = types.ModuleType(module_name)
        module.__file__ = str(path)
        module.__dict__.update(Path=Path, math=math, re=re, hashlib=hashlib,
                               json=json, dataclass=dataclass, asdict=asdict)
        sys.modules[module_name] = module
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), module.__dict__)
        need(all(hasattr(module, name) for name in names), 'missing frozen pure definition')
        return module
    profile = selected_module('tests/replay/benchmark_profile.py',
        {'BenchmarkError', 'BenchmarkProfile', '_encoded', 'PROFILE', 'PROFILE_SHA256'},
        '_s71_frozen_profile_definitions')
    native = selected_module('tests/replay/run_native_benchmark.py',
        {'SAFE_INTEGER', 'MUTABLE_SCENE', 'DiagnosticError', 'need', 'sha', 'encoded', 'closure',
         'read_regular', 'project_files', 'validate_cycle_timing', 'integer', 'digest', 'markers'},
        '_s71_frozen_native_definitions')
    from studio.pipeline import native_job
    native.native_job = native_job
    native.benchmark_profile = profile
    return native


def verify(arm, native, owner_module):
    cap, diagnostic, source = arm['cap'], arm['diagnostic'], arm['source']
    project, target = arm['project'], arm['target']
    binding = diagnostic['binding']
    need(native.closure(source) == binding['source_closure_sha256'], 'source closure mismatch')
    need(binding['profile_sha256'] == native.benchmark_profile.PROFILE_SHA256, 'profile mismatch')
    lock = obj(arm['verification'] / 'toolchain.lock.json')['godot']
    capture_sha = sha(raw(target / 'editor-host/capture.json'))
    capture = owner_module.verify_capture(target / 'editor-host', capture_sha,
        source_root=arm['verification'], expected_source_files=arm['runtime'],
        expected_binary_sha256=lock['gui_sha256'])
    import_sha = sha(raw(target / 'import-host/capture.json'))
    imported = native.native_job.verify_captured_stage(target / 'import-host', import_sha)
    invocation = obj(target / 'import-host/invocation.json')
    need(invocation['source_files'] == source and invocation['binary_sha256'] == lock['gui_sha256'],
         'import invocation binding')
    for name, digest in source.items():
        need(sha(raw(arm['verification'] / relative(name))) == digest, 'base source byte drift')
    for owner in ('import-host', 'editor-host'):
        need(raw(target / owner / 'stderr.txt') == b'', 'stderr is not empty')
        need(re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                       raw(target / owner / 'stdout.txt')) is None, 'unclean stdout')

    stdout = raw(target / 'editor-host/stdout.txt').decode('utf-8')
    need([line for line in stdout.splitlines() if line.startswith('HH_S71_OUTPUT_CAP ')]
         == [f'HH_S71_OUTPUT_CAP {cap}'], 'cap readback marker')
    config = raw(project / 'project.godot').decode('utf-8')
    need(config.count('[editor_overrides]') == 1 and re.findall(r'^run/output/max_lines=(\d+)$', config, re.M)
         == [str(cap)], 'project override binding')
    for name, digest in diagnostic['initial_project_files'].items():
        if name != native.MUTABLE_SCENE:
            need(sha(raw(project / relative(name))) == digest, 'initial project source drift')
    actual_project = native.project_files(project)
    runtime_project = {name.split('/project/', 1)[1]: digest for name, digest in arm['runtime'].items()
                       if name.startswith(f'.local/reviews/{arm["run_id"]}/project/')}
    need({name: digest for name, digest in actual_project.items() if name != native.MUTABLE_SCENE}
         == runtime_project, 'project immutable closure mismatch')

    index_raw = raw(project / 'benchmark/out/index.json')
    index = json.loads(index_raw)
    pid = capture['actual_process_exit']['pid']
    need(index['schema_id'] == 'hh-studio.native-cycle-benchmark' and index['schema_version'] == '1.2.0'
         and index['input'] == binding and index['pid'] == pid, 'index identity/binding')
    need(index['completed'] is True and index['benchmark_complete'] is False
         and index['formal_acceptance'] is False and index['host_integrated'] is False
         and index['host_barriers'] == [] and index['start_permits'] == []
         and index['batch_order'] == 'diagnostic_native_cycle_only'
         and index['batches_completed'] == 3 and index['cycles_per_batch'] == 50,
         'index diagnostic scope')
    need(index['engine']['hash'] == lock['source_commit'] and index['editor_hint'] is True
         and index['main_thread'] is True and index['display_server'] == 'Windows', 'native context')
    need(index['quiescence'] == {'minimum_frames': 4, 'minimum_us': 1100000}
         and index['heartbeat_target_met'] is True and 0 <= index['max_status_gap_ms'] <= 2000,
         'index quiescence/heartbeat')
    expected_native_sources = {'res://' + name for name in (
        'addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd',
        'addons/hh_studio/jcs_godot.gd', 'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd',
        'addons/hh_benchmark/benchmark_native.gd', 'addons/hh_benchmark/plugin.cfg',
        'project.godot', 'benchmark/input.json')}
    need(set(index['source_files']) == expected_native_sources, 'native source map fields')
    for name, digest in index['source_files'].items():
        rel = name.removeprefix('res://')
        need(diagnostic['initial_project_files'][rel] == digest and actual_project[rel] == digest,
             'native before/after source binding')
    completion = native.markers(stdout.encode(), 'HH_GT06_BENCHMARK_COMPLETE ')
    need(len(completion) == 1 and completion[0] == {'batches': 3, 'benchmark_complete': False,
        'host_integrated': False, 'index_sha256': sha(index_raw), 'mode': 'diagnostic',
        'pid': pid, 'run_id': arm['run_id']}, 'stdout completion/index binding')
    markers = native.markers(stdout.encode(), 'HH_GT06_BENCHMARK_BATCH ')
    need(len(markers) == 3, 'batch marker count')

    rows, refs = [], []
    final_scene_hash = sha(raw(project / native.MUTABLE_SCENE))
    previous_root = None
    previous_generation = 1
    previous_end = index['started_mono_us']
    for number in range(3):
        batch_raw = raw(project / f'benchmark/out/batch-{number:02d}.json')
        batch = json.loads(batch_raw)
        refs.append({'index': number, 'file': f'batch-{number:02d}.json',
                     'sha256': sha(batch_raw), 'size_bytes': len(batch_raw)})
        need(batch['schema_id'] == 'hh-studio.native-cycle-batch' and batch['schema_version'] == '1.2.0'
             and batch['run_id'] == arm['run_id'] and batch['pid'] == pid and batch['index'] == number
             and batch['mode'] == 'diagnostic' and batch['warmup'] is False
             and batch['barrier'] == {'mode': 'diagnostic_none', 'required': False}
             and batch['start_permit'] is None, 'batch identity/scope')
        need(len(batch['cycles']) == len(batch['raw_timings']) == 50, 'cycle count')
        memory = batch['memory']
        need(memory['phase'] == 'post_batch_quiescent' and memory['settle_frames'] >= 4
             and memory['settle_us'] >= 1100000 and memory['monotonic_us'] == batch['ended_mono_us'],
             'batch quiescence')
        need(batch['started_mono_us'] >= previous_end and batch['ended_mono_us'] <= index['ended_mono_us'],
             'batch chronology')
        for cycle_number, (cycle, timing) in enumerate(zip(batch['cycles'], batch['raw_timings'])):
            fields = set('index root_before root_after before_sha256 created_sha256 undone_sha256 saved_file_sha256 reloaded_sha256 latency_ms effects main_thread'.split())
            need(set(cycle) == fields and cycle['index'] == cycle_number and cycle['main_thread'] is True,
                 'cycle identity')
            need(native.integer(cycle['root_before'], 1) and native.integer(cycle['root_after'], 1)
                 and cycle['root_before'] != cycle['root_after'], 'root did not change')
            if previous_root is not None:
                need(cycle['root_before'] == previous_root, 'root continuity')
            need(all(native.digest(cycle[name]) for name in ('before_sha256', 'created_sha256',
                'undone_sha256', 'saved_file_sha256', 'reloaded_sha256')), 'semantic digest shape')
            need(cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256']
                 and cycle['created_sha256'] != cycle['before_sha256']
                 and index['baseline_revision'] == 'sha256:' + cycle['before_sha256']
                 and cycle['saved_file_sha256'] == final_scene_hash, 'semantic readback')
            steps = ('create', 'undo', 'save', 'reload')
            need(cycle['effects'] == dict.fromkeys(steps, 1) and set(cycle['latency_ms']) == set(steps),
                 'effect count/latency fields')
            native.validate_cycle_timing(timing, cycle, memory, batch)
            need(timing['generation_before'] == previous_generation
                 and timing['create']['start_us'] >= previous_end, 'cycle generation/chronology')
            previous_root = cycle['root_after']
            previous_generation = timing['generation_after']
            previous_end = timing['reload']['end_us']
        previous_end = batch['ended_mono_us']
        need(batch['dropped_commands'] == batch['dropped_telemetry'] == 0
             and 0 <= batch['max_status_gap_ms'] <= 2000, 'batch telemetry')
        for counter in ('objects', 'resources'):
            value = memory['editor'][counter]
            need(native.integer(value['value'], 1 if counter == 'objects' else 0)
                 and value['unavailable_reason'] is None, 'native counter')
        for unavailable in ('rss_bytes', 'held_handles'):
            need(memory['editor'][unavailable]['value'] is None
                 and memory['editor'][unavailable]['unavailable_reason'] == 'Requires retained host process sampler',
                 'unmeasured OS counter scope')
        marker = markers[number]
        need(marker['index'] == number and marker['sha256'] == sha(batch_raw)
             and marker['run_id'] == arm['run_id'] and marker['pid'] == pid
             and marker['memory_mono_us'] == memory['monotonic_us'], 'batch log/reference')
        rows.append({'index': number, 'cycles_verified': 50, 'memory': memory,
                     'batch_sha256': sha(batch_raw), 'max_status_gap_ms': batch['max_status_gap_ms']})
    need(index['batches'] == refs and previous_generation == 151, 'index references/total generation')
    need(set(p.name for p in (project / 'benchmark/out').iterdir())
         == {'index.json', 'batch-00.json', 'batch-01.json', 'batch-02.json'}, 'native output set')
    cleanup = obj(target / 'editor-host/cleanup-001.json')
    need(cleanup['closed'] is True and cleanup['job']['closed'] is True
         and cleanup['job']['zero_observed'] is True and cleanup['job']['handle_retained'] is False
         and cleanup['wrapper_exit_code'] == 0 and cleanup['wrapper_process_handle'] == capture['wrapper_process_handle'],
         'postcapture close proof')

    collector_result = {'formal_acceptance': False, 'full_benchmark': False, 'completed_diagnostic': True,
        'output_max_lines': cap, 'batches': [{'index': row['index'], 'memory': row['memory']} for row in rows],
        'actual_process_exit': capture['actual_process_exit'], 'job': capture['job'], 'capture_sha256': capture_sha}
    if cap == 10000:
        need(obj(target / 'failure.json') == {'detail': "'batch_index'", 'formal_acceptance': False, 'type': 'KeyError'},
             'original collector failure')
        need(not (arm['original'] / 'result.json').exists(), 'original result unexpectedly exists')
        write(target / 'recovered-result.json', {'recovery': 'read-only reconstruction from existing batch index keys',
              'original_collector_failed': True, 'original_failure_retained': True, 'no_native_rerun': True,
              'formal_acceptance': False, 'recovered_result': collector_result})
    else:
        need(obj(target / 'result.json') == collector_result, 'original second result disagreement')
    return {'run_id': arm['run_id'], 'output_max_lines': cap, 'read_only_verified': True,
        'formal_acceptance': False, 'full_benchmark': False, 'host_integrated': False,
        'rss_or_os_handle_measurement_acceptance': False, 'source_closure_sha256': native.closure(source),
        'base_source_count': len(source), 'runtime_source_count': len(arm['runtime']),
        'native_source_before_after_bindings_verified': len(index['source_files']),
        'runner_sha256': diagnostic['runner_sha256'], 'capture_sha256': capture_sha,
        'index_sha256': sha(index_raw), 'import_capture_sha256': import_sha,
        'actual_process_exit': capture['actual_process_exit'], 'wrapper_exit_code': capture['wrapper_exit_code'],
        'natural_tree_exit': capture['natural_tree_exit'], 'job': capture['job'],
        'wrapper_process_handle': capture['wrapper_process_handle'],
        'import_actual_process_exit': imported['actual_process_exit'],
        'editor_owner_elapsed_seconds': capture['elapsed_seconds'], 'cap_readback_verified': True,
        'stdout_stderr_copied_complete_and_hash_verified': True, 'logs_clean': True,
        'total_cycles_verified': 150, 'effects_verified': dict.fromkeys(('create', 'undo', 'save', 'reload'), 150),
        'last_generation': previous_generation, 'batch_observations': rows,
        'collector_outcome': 'KeyError after checked owner completion; separate recovered report' if cap == 10000 else 'original result verified'}


def main():
    arms = [setup(cap) for cap in (10000, 100)]
    need(arms[0]['source'] == arms[1]['source'], 'A/B base-source maps differ')
    sys.path.insert(0, str(arms[0]['verification'].parent))
    from studio.tests.replay import benchmark_job as owner_module
    native = frozen_helpers(arms[0]['verification'])
    need(Path(native.__file__).resolve().is_relative_to(arms[0]['verification']), 'live driver import refused')
    need(Path(owner_module.__file__).resolve().is_relative_to(arms[0]['verification']), 'live owner import refused')
    results = [verify(arm, native, owner_module) for arm in arms]
    # Check imported studio Python code came from the first arm's exact map.
    imported = {}
    for module in tuple(sys.modules.values()):
        value = getattr(module, '__file__', None)
        if value is None:
            continue
        path = Path(value).absolute()
        if path.is_relative_to(arms[0]['verification']) and path.suffix == '.py':
            name = path.relative_to(arms[0]['verification']).as_posix()
            digest = sha(raw(path))
            need(arms[0]['source'].get(name) == digest, 'unbound imported verifier source')
            imported[name] = digest
    result = {'schema': 'HH-GT06-S71-OUTPUT-COMPARISON-1', 'formal_acceptance': False,
        'full_benchmark': False, 'execution': 'read-only existing artifact verification; no engines or collector rerun',
        'verifier_script_sha256': sha(raw(Path(__file__))), 'frozen_imported_verifier_modules': imported,
        'frozen_pure_helpers_ast_selected': True,
        'unused_transitive_dependency_gap': 'Original diagnostic map omits perf-collector.schema.json; whole driver import avoided, no live schema substituted.',
        'arms': results, 'objects': {str(arm['output_max_lines']): [b['memory']['editor']['objects']['value']
            for b in arm['batch_observations']] for arm in results},
        'resources': {str(arm['output_max_lines']): [b['memory']['editor']['resources']['value']
            for b in arm['batch_observations']] for arm in results},
        'scope': 'Native3x50 per arm only; no host API workload, RSS/OS-handle sample, full benchmark or acceptance claim.'}
    write(OUT / 'comparison.json', result)
    inventory = {'schema': 'HH-GT06-S71-OUTPUT-COPY-INVENTORY-1', 'formal_acceptance': False,
        'created_utc': datetime.now(timezone.utc).isoformat(), 'copied_file_count': len(COPIES),
        'copied_total_bytes': sum(row['size_bytes'] for row in COPIES.values()), 'files': COPIES,
        'generated_files_excluded': ['collect_verify.py', 'comparison.json', 'inventory.json', 'README.md',
            '.gitattributes', 'cap-10000/recovered-result.json'],
        'originals_preserved': True, 'read_only_checks_used_frozen_maps_not_changed_live_source': True}
    write(OUT / 'inventory.json', inventory)
    print(json.dumps({'verified': True, 'objects': result['objects'], 'resources': result['resources'],
        'copied_files': len(COPIES), 'copied_bytes': inventory['copied_total_bytes'],
        'comparison_sha256': sha(raw(OUT / 'comparison.json'))}))


if __name__ == '__main__':
    main()
