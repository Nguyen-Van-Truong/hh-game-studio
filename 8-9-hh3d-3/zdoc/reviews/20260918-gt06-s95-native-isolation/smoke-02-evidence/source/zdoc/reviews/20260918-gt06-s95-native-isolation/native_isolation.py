"""Fixed S95 native isolation diagnostic. No HTTP producer or acceptance.

--describe reads source/helper hashes only. Every launching mode requires those
hashes and a fresh mode-specific run ID. preflight imports only; smoke executes
5x1; isolation executes 35x100. Only disposable project bytes are overlaid.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as n
from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture
from studio.tests.replay.benchmark_readiness import validate_startup_readiness
from studio.host.replay.process_probe import ProcessProbe

MODES = {
    'preflight': {'batches': 35, 'cycles': 100, 'wall_seconds': 180, 'launch_editor': False},
    'smoke': {'batches': 5, 'cycles': 1, 'wall_seconds': 180, 'launch_editor': True},
    'isolation': {'batches': 35, 'cycles': 100, 'wall_seconds': 1800, 'launch_editor': True},
}
HELPERS = ('native_isolation.py', 'object_probe_s95.gd')
NATIVE = 'addons/hh_benchmark/benchmark_native.gd'
PROCESS_START_PUBLICATION_SECONDS = 5.0
FLAGS = {'formal_acceptance': False, 'full_benchmark': False,
         'eligible_for_dataset': False, 'host_integrated': False}
LIMITATION = ('Native-only diagnostic excludes HTTP commands, host start/ACK execution and '
              'their idle time/load. Negative means not reproduced in this workload; '
              'it does not rule out a leak or repair any coupled benchmark failure.')


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    raw = value if isinstance(value, bytes) else encode(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def read(path, cap=8 * 1024**2):
    return n.read_regular(path, cap)


def document(path):
    return json.loads(read(path))


def _process_start_bytes(path):
    # Same local no-reparse/cap rules as read_regular, except an empty receipt
    # is a publication state. Reading it directly avoids an empty->complete
    # race between read_regular's nonempty rejection and a later size check.
    for component in (path, *path.parents):
        info = component.lstat()
        n.need(not component.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
               'DIAGNOSTIC_REPARSE')
    n.need(path.is_file() and path.stat().st_size <= 8192, 'DIAGNOSTIC_FILE_SIZE')
    with path.open('rb') as stream:
        raw = stream.read(8193)
    n.need(len(raw) <= 8192, 'DIAGNOSTIC_FILE_SIZE')
    return raw


def process_start_receipt(path, deadline, publication):
    """Poll only publication-in-progress states; never wait inside Stop's loop."""
    now = time.monotonic()
    need(now <= deadline, 'ISOLATION_PROCESS_START_TIMEOUT')
    need(now <= publication.get('deadline', deadline), 'ISOLATION_PROCESS_START_PUBLICATION_TIMEOUT')
    raw = None
    try:
        raw = _process_start_bytes(path)
    except FileNotFoundError:
        pass
    if raw is None or raw == b'':
        if raw == b'':
            publication.setdefault('deadline', min(deadline, now + PROCESS_START_PUBLICATION_SECONDS))
        return None

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'ISOLATION_PROCESS_START_RECORD')
            result[key] = value
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs)
    except json.JSONDecodeError:
        # Once publication began, disappearance or later partial rewrites must
        # not restart its five-second grace. The stage deadline still applies.
        publication.setdefault('deadline', min(deadline, now + PROCESS_START_PUBLICATION_SECONDS))
        return None
    need(type(value) is dict and set(value) == {'pid'}
         and type(value['pid']) is int and 0 < value['pid'] < 0xffffffff,
         'ISOLATION_PROCESS_START_RECORD')
    return value


def pins():
    # Import all local launch/verifier modules before collecting the closure.
    n.load_fixture()
    source = n.source_files()
    helpers = {name: sha(read(BASE / name)) for name in HELPERS}
    return {'source_files': source, 'source_closure_sha256': n.closure(source),
            'helper_files': helpers, 'helper_closure_sha256': sha(encode(helpers)),
            'profile_sha256': n.benchmark_profile.PROFILE_SHA256}


def check_pins(args, expected=None):
    actual = pins()
    need(actual['source_closure_sha256'] == args.source_sha256, 'ISOLATION_SOURCE_PIN')
    need(actual['helper_closure_sha256'] == args.helper_sha256, 'ISOLATION_HELPER_PIN')
    if expected is not None:
        need(actual == expected, 'ISOLATION_PIN_DRIFT')
    return actual


def path_for(args):
    need(re.fullmatch(r'gt06-s95-native-' + args.mode + r'-[a-z0-9-]{1,20}', args.run_id),
         'ISOLATION_RUN_ID')
    path = STUDIO / '.local/reviews' / args.run_id
    need(path.resolve().is_relative_to(STUDIO.resolve()), 'ISOLATION_OUTPUT_PATH')
    return path


def patch_driver(raw, helper, dimensions):
    text = raw.decode('utf-8')
    old = '    if _mode == "diagnostic":\n        _batch_limit = 1\n        _cycle_limit = 1'
    new = ('    if _mode == "diagnostic":\n'
           f'        _batch_limit = {dimensions["batches"]}\n'
           f'        _cycle_limit = {dimensions["cycles"]}')
    need(text.count(old) == 1, 'ISOLATION_DIMENSION_PATCH')
    text = text.replace(old, new, 1)
    begin = text.index('func _write_batch() -> void:\n')
    end = text.index('\n\nfunc _wait_host_ack() -> void:\n', begin)
    section = text[begin:end]
    anchor = '    var ended: int = Time.get_ticks_usec()\n    _heartbeat(true)\n'
    inserted = '    _s95_before_batch()\n    if _failed:\n        return\n'
    # Keep the stock timestamp/heartbeat after the census and publications:
    # the readback time is current and even the final batch covers hook delay.
    need(section.startswith('func _write_batch() -> void:\n' + anchor)
         and section.count(anchor) == 1, 'ISOLATION_COUNTER_PATCH')
    section = section.replace(anchor, inserted + anchor, 1)
    body = helper.decode('utf-8-sig')
    marker = '# S95_SPARSE_HELPER_BOUNDARY\n'
    need(body.startswith(marker) and body.count(marker) == 1
         and 'if _mode != "diagnostic" or _s95_snapshot_count' in body, 'ISOLATION_HELPER_MODE')
    result = text[:begin] + section + text[end:] + '\n' + body.split(marker, 1)[1]
    # Exact reversibility limits this overlay to dimensions and one new hook.
    restored = result[:-(len(body.split(marker, 1)[1]) + 1)].replace(inserted, '', 1).replace(new, old, 1)
    need(restored.encode() == raw, 'ISOLATION_OVERLAY_ROUNDTRIP')
    return result.encode()


def stop_requested(root, args):
    path = root / 'stop-request.json'
    if not os.path.lexists(path):
        return False
    expected = {'schema': 'HH-GT06-S95-NATIVE-STOP-1', 'run_id': args.run_id,
                'source_closure_sha256': args.source_sha256,
                'helper_closure_sha256': args.helper_sha256, 'reason': 'OPERATOR_STOP'}
    need(document(path) == expected, 'ISOLATION_STOP_BINDING')
    return True


def error_row(error):
    return {'type': type(error).__name__, 'code': getattr(error, 'code', str(error))[:240]}


def owner_receipt(owner):
    return {'closed': owner.closed, 'job': owner.job.snapshot() if owner.job else None,
            'wrapper_process_handle': owner.process_handle_snapshot()}


def native_stage(argv, output, project, sources, binary, args, root, *, observe=False):
    owner = probe = None
    primary = None
    observations = []
    started = time.monotonic()
    wall = MODES[args.mode]['wall_seconds']
    try:
        owner = BenchmarkProcess(argv, cwd=project, output=output, source_root=ROOT,
                                 source_files=sources, binary_sha256=binary)
        last_sample = 0.0
        publication = {}
        while owner.tick(stop=stop_requested(root, args) or time.monotonic() - started > wall) is None:
            if observe and probe is None:
                process = process_start_receipt(output / 'process-start.json', started + wall, publication)
                if process is not None:
                    probe = ProcessProbe(process['pid'], Path(argv[0]))
            if probe is not None and time.monotonic() - last_sample >= 1:
                row = probe.sample()
                if row is not None:
                    observations.append(row)
                last_sample = time.monotonic()
            time.sleep(.05)
        if probe is not None:
            probe.close()
        capture = owner.finish()
        verify_capture(output, sha(read(output / 'capture.json')), source_root=ROOT,
                       expected_source_files=sources, expected_binary_sha256=binary)
        need(not (output / 'stderr.txt').read_bytes().strip(), 'ISOLATION_STDERR')
        stdout = (output / 'stdout.txt').read_bytes()
        need(not re.search(rb'(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED', stdout),
             'ISOLATION_ENGINE_DIAGNOSTIC')
        if observe:
            need(probe is not None and probe.pid == capture['actual_process_exit']['pid']
                 and observations and any(row['visible_window_handles'] for row in observations), 'ISOLATION_GUI_OBSERVATION')
        return capture, observations
    except BaseException as exc:
        primary = exc
        retained = getattr(exc, 'cleanup_owner', None)
        if owner is None and isinstance(retained, BenchmarkProcess):
            owner = retained
        if probe is None and isinstance(retained, ProcessProbe):
            probe = retained
        raise
    finally:
        cleanup_errors = []
        if probe is not None:
            try:
                probe.close()
            except BaseException as exc:
                cleanup_errors.append(error_row(exc))
        if owner is not None:
            try:
                owner.close()
            except BaseException as exc:
                cleanup_errors.append(error_row(exc))
        write(root / (output.name + '-terminal.json'), {
            **FLAGS, 'run_id': args.run_id, 'elapsed_seconds': time.monotonic() - started,
            'primary_error': error_row(primary) if primary else None, 'cleanup_errors': cleanup_errors,
            'owner': owner_receipt(owner) if owner else None,
            'probe_handle_retained': probe.handle is not None if probe else False,
            'probe_identity': {'pid': probe.pid, 'process_start': getattr(probe, 'process_start', None)} if probe else None,
            'observations': observations})
        need(not cleanup_errors, 'ISOLATION_CLEANUP_UNCERTAIN')


def verify_sparse(directory, args, counts, pid):
    snapshots = sorted(directory.glob('sparse-[0-9][0-9].json'))
    need(1 <= len(snapshots) <= 2, 'ISOLATION_SPARSE_COUNT')
    baseline = growth = None
    for ordinal, path in enumerate(snapshots):
        row = document(path)
        post = document(directory / f'sparse-post-{ordinal:02d}.json')
        need(path.name == f'sparse-{ordinal:02d}.json' and row['run_id'] == args.run_id
             and row['pid'] == pid and row['schema_id'] == 'hh-studio.gt06.s95-sparse-attribution'
             and row['schema_version'] == '1.0.0'
             and post['schema_id'] == 'hh-studio.gt06.s95-sparse-post' and post['schema_version'] == '1.0.0'
             and row['sequence'] == ordinal and row['phase'] == 'before_batch_counter_readback', 'ISOLATION_SPARSE_BINDING')
        need(row['partial_inventory'] is True and row['complete_within_target_scope'] is True
             and row['formal_acceptance'] is False and row['eligible_for_dataset'] is False
             and row['object_references_retained'] is False and row['user_content_collected'] is False
             and row['id_cap'] == 32768 and row['snapshot_cap'] == 2
             and row['target_scope'] == 'reachable_Tree_owned_TreeItems_and_reachable_Node3D_family'
             and post['formal_acceptance'] is False and post['eligible_for_dataset'] is False, 'ISOLATION_SPARSE_SCOPE')
        need(row['counter_self_drift'] is False and post['counter_self_drift'] is False
             and row['before'] == row['after_collection'] == post['before'] == post['after_publication']
             and post['snapshot_sha256'] == sha(read(path)) and post['run_id'] == args.run_id
             and post['sequence'] == ordinal and post['batch'] == row['batch'], 'ISOLATION_SPARSE_DRIFT')
        batch = row['batch']
        need(type(batch) is int and 4 <= batch < len(counts)
             and row['before']['objects'] == counts[batch]['objects'], 'ISOLATION_SPARSE_PHASE_COUNTER')
        if ordinal == 0:
            need(batch == 4 and row['trigger'] == 'baseline_batch4'
                 and row['baseline_objects'] == row['before']['objects']
                 and row['object_delta_from_baseline'] == 0, 'ISOLATION_SPARSE_BASELINE')
            baseline = row
        else:
            need(batch > 4 and row['trigger'] == 'first_prepublication_object_growth'
                 and row['baseline_objects'] == baseline['before']['objects']
                 and row['object_delta_from_baseline'] == row['before']['objects'] - row['baseline_objects'] > 0,
                 'ISOLATION_SPARSE_GROWTH')
            growth = row
    growth_batches = [row['batch'] for row in counts[5:] if row['objects'] > counts[4]['objects']]
    need((not growth_batches and growth is None) or
         (growth_batches and growth is not None and growth['batch'] == growth_batches[0]), 'ISOLATION_FIRST_GROWTH_CAPTURE')
    return {'baseline_objects': counts[4]['objects'], 'growth_batches': growth_batches,
            'first_growth': growth, 'snapshot_count': len(snapshots),
            'interpretation': 'GROWTH_OBSERVED_IN_ISOLATED_WORKLOAD' if growth else 'NOT_REPRODUCED_IN_ISOLATED_WORKLOAD',
            'no_leak_claim': False}


def verify_native(project, binding, snapshot, capture, lock, args):
    dimensions = MODES[args.mode]
    directory = project / 'benchmark/out'
    index = document(directory / 'index.json')
    pid = capture['actual_process_exit']['pid']
    need(index['schema_id'] == 'hh-studio.native-cycle-benchmark' and index['schema_version'] == '1.3.0'
         and index['input'] == binding and index['pid'] == pid, 'ISOLATION_INDEX_BINDING')
    need(index['completed'] is True and index['benchmark_complete'] is False
         and index['formal_acceptance'] is False and index['host_integrated'] is False
         and index['host_barriers'] == [] and index['start_permits'] == []
         and index['batch_order'] == 'diagnostic_native_cycle_only'
         and index['batches_completed'] == dimensions['batches']
         and index['cycles_per_batch'] == dimensions['cycles'], 'ISOLATION_DIMENSIONS')
    need(index['editor_hint'] is True and index['main_thread'] is True and index['display_server'] == 'Windows'
         and index['engine']['hash'] == lock['source_commit'], 'ISOLATION_NATIVE_CONTEXT')
    native_paths = {'res://' + name for name in ('addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd',
        'addons/hh_studio/jcs_godot.gd', 'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', NATIVE,
        'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json', 'benchmark/.gdignore')}
    need(set(index['source_files']) == native_paths and all(snapshot[key[6:]] == value
         for key, value in index['source_files'].items()), 'ISOLATION_NATIVE_SOURCES')
    refs, counts = [], []
    previous_root = previous_end = previous_generation = None
    first = final_cycle = None
    max_gap = 0.0
    for number in range(dimensions['batches']):
        path = directory / f'batch-{number:02d}.json'
        raw = read(path, 1_048_576)
        batch = json.loads(raw)
        refs.append({'index': number, 'file': path.name, 'sha256': sha(raw), 'size_bytes': len(raw)})
        need(batch['schema_id'] == 'hh-studio.native-cycle-batch' and batch['schema_version'] == '1.2.0'
             and batch['index'] == number and batch['run_id'] == args.run_id and batch['pid'] == pid
             and batch['mode'] == 'diagnostic' and batch['warmup'] is False
             and batch['barrier'] == {'mode': 'diagnostic_none', 'required': False}
             and batch['start_permit'] is None, 'ISOLATION_BATCH_BINDING')
        need(len(batch['cycles']) == len(batch['raw_timings']) == dimensions['cycles'], 'ISOLATION_CYCLE_COUNT')
        memory = batch['memory']
        need(memory['phase'] == 'post_batch_quiescent' and memory['monotonic_us'] == batch['ended_mono_us']
             and memory['settle_frames'] >= 4 and memory['settle_us'] >= 1_100_000
             and (previous_end is None or previous_end <= batch['started_mono_us']), 'ISOLATION_BATCH_PHASE')
        previous_end = batch['ended_mono_us']
        for ordinal, (cycle, timing) in enumerate(zip(batch['cycles'], batch['raw_timings'])):
            need(cycle['index'] == ordinal and cycle['main_thread'] is True
                 and n.integer(cycle['root_before'], 1) and n.integer(cycle['root_after'], 1)
                 and cycle['root_before'] != cycle['root_after']
                 and (previous_root is None or cycle['root_before'] == previous_root), 'ISOLATION_ROOT_CHAIN')
            previous_root = cycle['root_after']
            keys = ('before_sha256', 'created_sha256', 'undone_sha256', 'saved_file_sha256', 'reloaded_sha256')
            need(all(n.digest(cycle[key]) for key in keys)
                 and cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256']
                 and cycle['created_sha256'] != cycle['before_sha256']
                 and index['baseline_revision'] == 'sha256:' + cycle['before_sha256'], 'ISOLATION_SEMANTIC_CHAIN')
            need(cycle['effects'] == dict.fromkeys(('create', 'undo', 'save', 'reload'), 1), 'ISOLATION_EFFECT_COUNT')
            n.validate_cycle_timing(timing, cycle, memory, batch)
            need(previous_generation is None or timing['generation_before'] == previous_generation, 'ISOLATION_GENERATION_CHAIN')
            previous_generation = timing['generation_after']
            final_cycle = cycle
        if first is None:
            first = batch
        row = {'batch': number, 'duration_seconds': (batch['ended_mono_us'] - batch['started_mono_us']) / 1_000_000}
        for name in ('objects', 'resources'):
            counter = memory['editor'][name]
            need(n.integer(counter['value'], 1 if name == 'objects' else 0)
                 and counter['unavailable_reason'] is None, 'ISOLATION_NATIVE_COUNTER')
            row[name] = counter['value']
        need(batch['dropped_commands'] == 0 and batch['dropped_telemetry'] == 0, 'ISOLATION_DROPPED_TELEMETRY')
        gap = batch['max_status_gap_ms']
        need(type(gap) in (int, float) and math.isfinite(gap) and gap >= 0, 'ISOLATION_STATUS_VALUE')
        max_gap = max(max_gap, gap)
        counts.append(row)
    need(index['batches'] == refs and index['quiescence'] == {'minimum_frames': 4, 'minimum_us': 1_100_000},
         'ISOLATION_INDEX_REFERENCES')
    need(sha(read(project / n.MUTABLE_SCENE)) == final_cycle['saved_file_sha256'], 'ISOLATION_FINAL_SCENE')
    validate_startup_readiness(index['startup_readiness'], binding=binding, pid=pid,
        source_files=index['source_files'], baseline_revision=index['baseline_revision'],
        scene_file_sha256=snapshot[n.MUTABLE_SCENE], first_batch_started_mono_us=first['started_mono_us'],
        first_cycle_root_before=first['cycles'][0]['root_before'], run_started_mono_us=index['started_mono_us'])
    sparse = verify_sparse(directory, args, counts, pid)
    expected = {'index.json', *(row['file'] for row in refs)}
    expected.update(f'{prefix}-{ordinal:02d}.json' for ordinal in range(sparse['snapshot_count'])
                    for prefix in ('sparse', 'sparse-post'))
    need({path.name for path in directory.iterdir()} == expected, 'ISOLATION_OUTPUT_SET')
    gap = index['max_status_gap_ms']
    need(type(gap) in (float, int) and math.isfinite(gap) and gap >= max_gap
         and type(index['heartbeat_target_met']) is bool
         and index['heartbeat_target_met'] == (gap <= 2000), 'ISOLATION_HEARTBEAT_BINDING')
    # Report the unchanged native heartbeat criterion honestly. This is a
    # completed diagnostic, never a campaign PASS even when the criterion holds.
    return {'native_batches': dimensions['batches'], 'native_cycles': dimensions['batches'] * dimensions['cycles'],
            'native_elapsed_seconds': (index['ended_mono_us'] - index['started_mono_us']) / 1_000_000,
            'native_max_status_gap_ms': gap, 'native_heartbeat_target_met': index['heartbeat_target_met'],
            'counts': counts, 'sparse': sparse, 'causal_limitations': LIMITATION}


def child(args):
    root = path_for(args)
    meta = document(root / 'diagnostic.json')
    frozen = check_pins(args, meta['pins'])
    dimensions = MODES[args.mode]
    project = root / 'project'
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': args.run_id, 'mode': 'diagnostic', 'source_closure_sha256': args.source_sha256,
        'profile_sha256': frozen['profile_sha256'], 'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
    factory, trusted = n.load_fixture()
    n.prepare(project, factory, trusted, binding)
    driver = project / NATIVE
    raw = read(driver)
    effective = patch_driver(raw, read(BASE / 'object_probe_s95.gd'), dimensions)
    driver.write_bytes(effective)  # Fresh disposable project, before import.
    need(read(driver) == effective, 'ISOLATION_OVERLAY_READBACK')
    snapshot = n.project_files(project)
    write(root / 'project-snapshot.json', snapshot)
    write(root / 'native-overlay.json', {**FLAGS, 'base_sha256': sha(raw), 'effective_sha256': sha(effective),
        'helper_sha256': frozen['helper_files']['object_probe_s95.gd'], 'dimensions': dimensions,
        'original_runtime_source_edited': False, 'formal_thresholds_modified': False})
    write(root / 'source/effective-benchmark_native.gd', effective)
    sources = {'studio/' + key: value for key, value in frozen['source_files'].items()}
    sources.update({(BASE / key).relative_to(ROOT).as_posix(): value for key, value in frozen['helper_files'].items()})
    sources.update({(project / key).relative_to(ROOT).as_posix(): value for key, value in snapshot.items()})
    lock = document(STUDIO / 'toolchain.lock.json')['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(lock['version'] == '4.7.2-stable' and sha(read(executable, 256 * 1024**2)) == lock['gui_sha256'], 'ISOLATION_ENGINE_PIN')
    started = time.monotonic()
    result = {**FLAGS, 'run_id': args.run_id, 'mode': args.mode, 'completed_diagnostic': False,
              'causal_limitations': LIMITATION}
    try:
        imported, _ = native_stage([str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            root / 'import-host', project, sources, lock['gui_sha256'], args, root)
        imported_snapshot = n.project_files(project)
        need(all(imported_snapshot.get(key) == value for key, value in snapshot.items())
             and not list((project / 'benchmark/out').iterdir()), 'ISOLATION_IMPORT_DRIFT')
        # Godot may create UID metadata during import. Freeze those additions
        # before editor launch, as the existing native runner does.
        snapshot = imported_snapshot
        write(root / 'editor-snapshot.json', snapshot)
        sources.update({(project / key).relative_to(ROOT).as_posix(): value for key, value in snapshot.items()})
        result['import_actual_exit'] = imported['actual_process_exit']
        if dimensions['launch_editor']:
            runtime = {key: value for key, value in sources.items() if key != (project / n.MUTABLE_SCENE).relative_to(ROOT).as_posix()}
            capture, observations = native_stage([str(executable), '--editor', '--path', str(project),
                'res://scenes/fixture.tscn', '--', '--hh-benchmark-mode=diagnostic'], root / 'editor-host',
                project, runtime, lock['gui_sha256'], args, root, observe=True)
            result.update(verify_native(project, binding, snapshot, capture, lock, args))
            result['editor_actual_exit'] = capture['actual_process_exit']
            result['editor_job'] = capture['job']
            result['editor_wrapper_handle'] = capture['wrapper_process_handle']
            result['gui_observation_count'] = len(observations)
            after = n.project_files(project)
            need({key: value for key, value in after.items() if key != n.MUTABLE_SCENE}
                 == {key: value for key, value in snapshot.items() if key != n.MUTABLE_SCENE}, 'ISOLATION_PROJECT_DRIFT')
        check_pins(args, frozen)
        result['completed_diagnostic'] = True
        return 0
    except BaseException as exc:
        result['error'] = error_row(exc)
        raise
    finally:
        result['wall_seconds'] = time.monotonic() - started
        write(root / 'child-result.json', result)


def parent(args):
    need(os.name == 'nt', 'ISOLATION_WINDOWS_REQUIRED')
    frozen = check_pins(args)
    root = path_for(args)
    root.mkdir(exist_ok=False)
    write(root / 'diagnostic.json', {**FLAGS, 'schema': 'HH-GT06-S95-NATIVE-ISOLATION-1',
        'run_id': args.run_id, 'mode': args.mode, 'pins': frozen, 'dimensions': MODES[args.mode],
        'analytical_baseline_batch_index': 4, 'native_warmup_field_remains_false': True,
        'no_http_producer': True, 'causal_limitations': LIMITATION})
    sources = {'studio/' + key: value for key, value in frozen['source_files'].items()}
    sources.update({(BASE / key).relative_to(ROOT).as_posix(): value for key, value in frozen['helper_files'].items()})
    for key, digest in sources.items():
        raw = read(ROOT / key)
        need(sha(raw) == digest, 'ISOLATION_FREEZE_DRIFT')
        write(root / 'source' / key, raw)
    executable = Path(sys.executable).with_name('python.exe')
    binary = sha(read(executable, 256 * 1024**2))
    argv = [str(executable), '-B', str(Path(__file__).resolve()), '--mode', args.mode, '--run-id', args.run_id,
            '--source-sha256', args.source_sha256, '--helper-sha256', args.helper_sha256, '--owned-child']
    owner = primary = None
    exit_code = 1
    result = {**FLAGS, 'run_id': args.run_id, 'mode': args.mode, 'completed_diagnostic': False,
              'supervisor_own_actual_exit_not_yet_observed': True}
    start = time.monotonic()
    try:
        owner = BenchmarkProcess(argv, cwd=root, output=root / 'host-owner', source_root=ROOT,
            source_files=sources, binary_sha256=binary, campaign_host=True)
        while owner.tick(stop=stop_requested(root, args) or time.monotonic() - start > MODES[args.mode]['wall_seconds'] + 240) is None:
            time.sleep(.1)
        capture = owner.finish()
        verify_capture(root / 'host-owner', sha(read(root / 'host-owner/capture.json')), source_root=ROOT,
            expected_source_files=sources, expected_binary_sha256=binary, expected_campaign_host=True)
        report = document(root / 'child-result.json')
        need(report['completed_diagnostic'] is True and all(report[key] is False for key in FLAGS), 'ISOLATION_CHILD_RESULT')
        for lane in ('import-host', 'editor-host') if MODES[args.mode]['launch_editor'] else ('import-host',):
            terminal = document(root / (lane + '-terminal.json'))
            need(not terminal['cleanup_errors'] and terminal['owner']['closed'] is True
                 and terminal['probe_handle_retained'] is False, 'ISOLATION_TERMINAL_CLEANUP')
        check_pins(args, frozen)
        result.update(completed_diagnostic=True, child_actual_exit=capture['actual_process_exit'],
                      job=capture['job'], wrapper_handle=capture['wrapper_process_handle'])
        exit_code = 0
    except BaseException as exc:
        primary = exc
        owner = owner or getattr(exc, 'cleanup_owner', None)
        result['error'] = error_row(exc)
        traceback.print_exc()
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as exc:
                result['cleanup_error'] = error_row(exc)
                result['completed_diagnostic'] = False
                exit_code = 1
        result['elapsed_seconds'] = time.monotonic() - start
        result['owner'] = owner_receipt(owner) if owner else None
        write(root / 'supervisor-result.json', result)
        # Seal emitted artifacts only after owned streams/processes have drained;
        # a missing process receipt remains missing, never synthesized as success.
        selected = [path for path in root.glob('*.json') if path.name != 'output-manifest.json']
        selected += list(root.glob('*/capture.json')) + list(root.glob('*/process-*.json'))
        selected += list(root.glob('*/cleanup*.json')) + list(root.glob('*/invocation.json'))
        selected += list(root.glob('*/stdout.txt')) + list(root.glob('*/stderr.txt'))
        selected += list((root / 'project/benchmark/out').glob('*.json'))
        artifacts = {path.relative_to(root).as_posix(): {'sha256': sha(path.read_bytes()), 'size_bytes': path.stat().st_size}
                     for path in sorted(set(selected))}
        write(root / 'output-manifest.json', {**FLAGS, 'run_id': args.run_id, 'artifacts': artifacts,
            'outcome': 'DIAGNOSTIC_COMPLETE' if result['completed_diagnostic'] else 'DIAGNOSTIC_FAILED_OR_UNKNOWN',
            'source_closure_sha256': args.source_sha256, 'helper_closure_sha256': args.helper_sha256,
            'supervisor_own_actual_exit_not_yet_observed': True})
    return exit_code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--mode', choices=MODES)
    parser.add_argument('--run-id')
    parser.add_argument('--source-sha256')
    parser.add_argument('--helper-sha256')
    parser.add_argument('--owned-child', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.describe:
        need(not any((args.mode, args.run_id, args.source_sha256, args.helper_sha256, args.owned_child)), 'ISOLATION_DESCRIBE_ARGS')
        print(json.dumps({**FLAGS, 'pins': pins(), 'modes': MODES, 'launch_performed': False}, sort_keys=True))
        return 0
    need(args.mode in MODES and args.run_id and re.fullmatch('[0-9a-f]{64}', args.source_sha256 or '')
         and re.fullmatch('[0-9a-f]{64}', args.helper_sha256 or ''), 'ISOLATION_REQUIRED_PINS')
    return child(args) if args.owned_child else parent(args)


if __name__ == '__main__':
    raise SystemExit(main())
