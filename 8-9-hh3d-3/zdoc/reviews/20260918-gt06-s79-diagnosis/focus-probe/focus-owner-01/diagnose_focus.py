"""One native cycle, two explicit SYNTHETIC focus notifications.

Diagnostic only. No threshold changes, HTTP campaign, runtime source edits,
OS focus manipulation, private Tree edits or full-ObjectDB census claim.
The disposable plugin propagates APPLICATION_FOCUS_IN as a synthetic stimulus.
Run the no-argument entry point after coordinator verifies other lanes clean.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
RUN_ID = 'gt06-s79-focus-diagnostic-01'
OUTER_WALL_SECONDS = 180
INNER_WALL_SECONDS = 150  # Includes the unchanged <=20s import stage.


def instrument_driver(script, probe):
    replacements = [
        ('    if _mode != "full":\n        _advance_batch()',
         '    if _mode != "full":\n        _focus_probe_after_batch()'),
        ('    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n',
         '    if _focus_probe_tick():\n        return\n    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n'),
    ]
    for old, new in replacements:
        assert script.count(old) == 1, old
        script = script.replace(old, new)
    assert script.count('        _batch_limit = 1\n        _cycle_limit = 1') == 1
    assert 'func _notification(' not in script
    return script + '\n' + probe


def outer():
    output = BASE / 'focus-owner-01'
    output.mkdir(exist_ok=False)
    helper_files = ['diagnose_focus.py', 'focus_probe.gd']
    before = {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in helper_files}
    for name in helper_files:
        (output / name).write_bytes((BASE / name).read_bytes())
    runner = ROOT / 'studio/build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('owned_focus_probe', runner)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    executable = Path(sys.executable).with_name('python.exe')
    assert executable.is_file()
    argv = [str(executable), '-B', str(BASE / 'diagnose_focus.py'), '--owned-child']
    (output / 'invocation.json').write_text(json.dumps({
        'argv': argv, 'helper_files': before, 'timeout_seconds': OUTER_WALL_SECONDS,
        'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
        'formal_acceptance': False, 'full_benchmark': False}, indent=2) + '\n', encoding='utf-8')
    result = owned.run_process(argv, cwd=ROOT, output=output, timeout=OUTER_WALL_SECONDS, label='probe')
    after = {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in helper_files}
    (output / 'capture.json').write_text(json.dumps({
        'host': result, 'helper_source_unchanged': before == after}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    assert before == after
    code = result.get('exit_code')
    if (type(code) is not int or result.get('wrapper_exit_code') != 0
            or result.get('timed_out') is not False or result.get('tree_verified') is not True):
        return 1
    return code


def child():
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_native_benchmark as n
    from studio.tests.replay.benchmark_job import BenchmarkProcess, PROFILE, verify_capture

    factory, trusted = n.load_fixture()
    source = n.source_files()
    lock = json.loads(n.read_regular(n.STUDIO / 'toolchain.lock.json'))['godot']
    executable = n.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    root = n.STUDIO / '.local/reviews' / RUN_ID
    root.mkdir(exist_ok=False)
    project = root / 'project'
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
               'run_id': RUN_ID, 'mode': 'diagnostic', 'source_closure_sha256': n.closure(source),
               'profile_sha256': n.benchmark_profile.PROFILE_SHA256,
               'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
    n.prepare(project, factory, trusted, binding)
    driver = project / 'addons/hh_benchmark/benchmark_native.gd'
    script = instrument_driver(driver.read_text(encoding='utf-8'),
                               (BASE / 'focus_probe.gd').read_text(encoding='utf-8'))
    driver.write_text(script, encoding='utf-8', newline='\n')
    initial = n.project_files(project)
    for name, digest in source.items():
        raw = n.read_regular(n.STUDIO / name)
        assert n.sha(raw) == digest
        n.write(root / 'source/studio' / name, raw)
    n.write(root / 'diagnostic.json', {
        'formal_acceptance': False, 'full_benchmark': False, 'run_id': RUN_ID,
        'source_files': source, 'initial_project_files': initial, 'native_batches': 1,
        'cycles_each': 1, 'synthetic_focus_stimuli': 2, 'inner_wall_seconds': INNER_WALL_SECONDS,
        'outer_wall_seconds': OUTER_WALL_SECONDS, 'import_wall_seconds': n.native_job.WALL_SECONDS,
        'editor_owner_profile_unchanged': PROFILE,
        'limits_note': '150s host watchdog inside unchanged 7410s Job profile; 180s outer owned cap',
        'os_focus_manipulation': False, 'private_tree_mutation': False,
        'settle_minimum_us': 1500000, 'settle_minimum_frames': 8,
        'runner_sha256': n.sha(Path(__file__).read_bytes()),
        'probe_sha256': n.sha((BASE / 'focus_probe.gd').read_bytes()),
        'inventory_complete_objectdb': False, 'binding': binding})
    owner = None
    started = time.monotonic()
    try:
        n.native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=source,
            source_root=n.STUDIO, binary_sha256=lock['gui_sha256'])
        n.native_job.verify_captured_stage(root / 'import-host',
            n.sha(n.read_regular(root / 'import-host/capture.json')))
        snapshot = n.project_files(project)
        assert all(snapshot.get(key) == value for key, value in initial.items())
        runtime = dict(source)
        runtime.update({(project / name).relative_to(n.STUDIO).as_posix(): value
                        for name, value in snapshot.items() if name != n.MUTABLE_SCENE})
        n.write(root / 'runtime-source-files.json', runtime)
        owner = BenchmarkProcess(
            [str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
             '--', '--hh-benchmark-mode=diagnostic'], cwd=project, output=root / 'editor-host',
            source_root=n.STUDIO, source_files=runtime, binary_sha256=lock['gui_sha256'])
        while owner.tick(stop=time.monotonic() - started >= INNER_WALL_SECONDS) is None:
            time.sleep(.1)
        capture = owner.finish()
        verify_capture(root / 'editor-host', n.sha(n.read_regular(root / 'editor-host/capture.json')),
            source_root=n.STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        batches = sorted((project / 'benchmark/out').glob('batch-*.json'))
        assert len(batches) == 1
        batch_raw = n.read_regular(batches[0])
        batch = json.loads(batch_raw)
        assert batch['index'] == 0 and len(batch['cycles']) == len(batch['raw_timings']) == 1
        assert batch['run_id'] == RUN_ID and batch['pid'] == capture['actual_process_exit']['pid']
        cycle = batch['cycles'][0]
        assert cycle['index'] == 0 and cycle['main_thread'] is True
        assert cycle['effects'] == dict.fromkeys(('create', 'undo', 'save', 'reload'), 1)
        assert cycle['root_before'] != cycle['root_after']
        assert cycle['created_sha256'] != cycle['before_sha256']
        assert cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256']
        n.validate_cycle_timing(batch['raw_timings'][0], cycle, batch['memory'], batch)
        out = project / 'benchmark/out'
        native_index = json.loads(n.read_regular(out / 'index.json'))
        assert native_index['completed'] is True and native_index['benchmark_complete'] is False
        assert native_index['formal_acceptance'] is False and native_index['input'] == binding
        assert native_index['pid'] == capture['actual_process_exit']['pid']
        assert native_index['engine']['hash'] == lock['source_commit']
        assert native_index['editor_hint'] is True and native_index['main_thread'] is True
        assert native_index['display_server'] == 'Windows' and native_index['host_integrated'] is False
        assert native_index['batches'] == [{'index': 0, 'file': batches[0].name,
                                           'sha256': n.sha(batch_raw), 'size_bytes': len(batch_raw)}]
        assert native_index['batches_completed'] == native_index['cycles_per_batch'] == 1
        focus_raw = n.read_regular(out / 'focus-index.json')
        assert len(focus_raw) <= 1048576
        focus = json.loads(focus_raw)
        points = verify_focus(out, focus, capture['actual_process_exit']['pid'], n)
        first_point = json.loads(n.read_regular(points[0]))
        assert first_point['mono_us'] >= batch['ended_mono_us']
        assert first_point['files']['res://' + n.MUTABLE_SCENE]['sha256'] == cycle['saved_file_sha256']
        after = n.project_files(project)
        assert {k: v for k, v in after.items() if k != n.MUTABLE_SCENE} == {
            k: v for k, v in snapshot.items() if k != n.MUTABLE_SCENE}
        assert after[n.MUTABLE_SCENE] == cycle['saved_file_sha256']
        for name, record in first_point['files'].items():
            assert record['sha256'] == after[name.removeprefix('res://')]
        n.write(root / 'final-project-files.json', after)
        for lane in ['import-host', 'editor-host']:
            assert not (root / lane / 'stderr.txt').read_bytes().strip()
            assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                                 (root / lane / 'stdout.txt').read_bytes())
        assert n.source_files() == source
        owner.close()
        owner = None
        n.write(root / 'result.json', {
            'formal_acceptance': False, 'full_benchmark': False, 'completed_diagnostic': True,
            'actual_process_exit': capture['actual_process_exit'], 'job': capture['job'],
            'source_unchanged': True, 'point_count': len(points),
            'project_unchanged_after_native_cycle': True,
            'root_cause_proven': False, 'stimulus_is_synthetic_not_os_focus': True,
            'focus_index_sha256': n.sha(focus_raw),
            'points': {path.name: n.sha(n.read_regular(path)) for path in points}})
        return 0
    except BaseException as exc:
        if owner is None:
            owner = getattr(exc, 'cleanup_owner', None)
        n.write(root / 'failure.json', {
            'type': type(exc).__name__, 'detail': str(exc), 'formal_acceptance': False})
        raise
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as cleanup_error:
                n.write(root / 'cleanup-failure.json', {
                    'type': type(cleanup_error).__name__, 'detail': str(cleanup_error),
                    'formal_acceptance': False})
                raise


def verify_focus(out, focus, pid, n):
    assert focus['schema_id'] == 'hh-studio.focus-causal-diagnostic' and focus['schema_version'] == '1.0.0'
    assert focus['run_id'] == RUN_ID and focus['pid'] == pid and focus['completed_diagnostic'] is True
    assert focus['formal_acceptance'] is False and focus['full_benchmark'] is False
    assert focus['root_cause_proven'] is False and focus['stimulus_is_synthetic_not_os_focus'] is True
    assert focus['private_tree_mutation'] is False
    assert focus['settle_minimum_us'] == 1500000 and focus['settle_minimum_frames'] == 8
    expected = ['natural_after_cycle', 'before_first_stimulus', 'after_first_return',
                'after_first_settle_before_second', 'after_second_return', 'after_second_settle']
    paths = [out / f'focus-{index:02d}.json' for index in range(6)]
    assert sorted(out.glob('focus-[0-9][0-9].json')) == paths
    assert len(focus['points']) == 6 and len(focus['stimuli']) == 2 and len(focus['events']) <= 64
    assert not list(out.glob('*.tmp'))
    rows = []
    for index, path in enumerate(paths):
        raw = n.read_regular(path)
        assert len(raw) <= 262145
        row = json.loads(raw)
        assert focus['points'][index] == {'file': path.name, 'sha256': n.sha(raw),
            'size_bytes': len(raw), 'sequence': index, 'label': expected[index]}
        assert row['run_id'] == RUN_ID and row['pid'] == pid and row['sequence'] == index
        assert row['label'] == expected[index] and row['formal_acceptance'] is False
        assert row['schema_id'] == 'hh-studio.focus-causal-diagnostic-point' and row['schema_version'] == '1.0.0'
        assert row['full_benchmark'] is False and row['full_objectdb_attribution'] is False
        assert row['batch'] == 0 and row['cycle'] == 1 and row['phase'] == 'BATCH_WRITE'
        assert row['focus_probe_stage'] == [0, 1, 1, 2, 2, 3][index]
        assert 0 <= row['event_count'] <= len(focus['events'])
        assert 0 < row['mono_us'] <= row['collection_end_us']
        if rows:
            assert row['mono_us'] >= rows[-1]['collection_end_us'] and row['frame'] >= rows[-1]['frame']
            assert row['files'] == rows[0]['files']
            assert row['main_window_title'] == rows[0]['main_window_title']
        window_title = row['main_window_title']
        assert not window_title['truncated'] and window_title['length'] == len(window_title['text']) <= 512
        assert n.sha(window_title['text'].encode()) == window_title['sha256']
        assert set(row['files']) == {'res://' + name for name in (
            'addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd', 'addons/hh_studio/jcs_godot.gd',
            'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', 'addons/hh_benchmark/benchmark_native.gd',
            'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json', 'benchmark/.gdignore',
            'scenes/fixture.tscn')}
        assert all(n.digest(record['sha256']) and n.integer(record['size_bytes'], 1)
                   and n.integer(record['modified_time'], 1) for record in row['files'].values())
        assert row['counters_equal_across_collection'] is (row['counters_before'] == row['counters_after'])
        for counters in (row['counters_before'], row['counters_after']):
            assert set(counters) == {'objects', 'cached_resources', 'tree_nodes', 'orphan_nodes',
                                     'filesystem_scanning_before', 'filesystem_scanning_after'}
            assert all(n.integer(counters[key]) for key in ('objects', 'cached_resources', 'tree_nodes', 'orphan_nodes'))
            assert type(counters['filesystem_scanning_before']) is type(counters['filesystem_scanning_after']) is bool
        assert set(row['owners']) == {'editor_disk_changes', 'script_disk_changes'}
        for role, owned in row['owners'].items():
            expected_method, expected_class = {'editor_disk_changes': ('_reload_modified_scenes', 'EditorNode'),
                                               'script_disk_changes': ('reload_scripts', 'ScriptEditor')}[role]
            assert 1 <= len(owned['confirmed_callbacks']) <= 16
            assert any(callback['method'].split('::')[-1] == expected_method
                       and callback['target_class'] == expected_class
                       and callback['target_id'].isdigit() and int(callback['target_id']) > 0
                       for callback in owned['confirmed_callbacks'])
            title = owned['dialog_title']
            assert not title['truncated'] and title['length'] == len(title['text']) <= 512
            assert n.sha(title['text'].encode()) == title['sha256']
            assert owned['dialog_id'].isdigit() and owned['tree_id'].isdigit()
            if rows:
                assert owned['dialog_id'] == rows[0]['owners'][role]['dialog_id']
                assert owned['tree_id'] == rows[0]['owners'][role]['tree_id']
                assert owned['confirmed_callbacks'] == rows[0]['owners'][role]['confirmed_callbacks']
                assert owned['dialog_title'] == rows[0]['owners'][role]['dialog_title']
            previous_id = rows[-1]['owners'][role]['root_item_id'] if rows else ''
            assert owned['previous_root_item_id'] == previous_id
            if previous_id:
                assert type(owned['previous_root_still_valid']) is bool
            else:
                assert owned['previous_root_still_valid'] is None
            if previous_id and previous_id == owned['root_item_id']:
                assert owned['previous_root_still_valid'] is True
            assert owned['item_count'] == len(owned['items']) <= 64
            assert owned['root_present'] is bool(owned['root_item_id'])
            assert (owned['items'][0]['id'] if owned['items'] else '') == owned['root_item_id']
            assert len({item['id'] for item in owned['items']}) == len(owned['items'])
            if owned['items']:
                assert owned['items'][0]['parent_item_id'] == ''
            for item in owned['items']:
                assert item['owner_tree_id'] == owned['tree_id'] and item['columns'] == owned['columns']
                assert len(item['cell_texts']) == min(owned['columns'], 8)
                for cell in item['cell_texts']:
                    assert len(cell['text']) == min(cell['length'], 512)
                    assert cell['truncated'] is (cell['length'] > 512)
                    if not cell['truncated']:
                        assert n.sha(cell['text'].encode()) == cell['sha256']
        rows.append(row)
    assert rows[1]['mono_us'] - rows[0]['collection_end_us'] >= 1500000
    assert rows[1]['frame'] - rows[0]['frame'] >= 8
    for index, event in enumerate(focus['events']):
        assert event['ordinal'] == index and event['pid'] == pid and event['notification'] in (2016, 2017)
        assert event['probe_synthetic_dispatch'] in (0, 1, 2)
        assert event['origin'] == ('probe_synthetic' if event['probe_synthetic_dispatch'] else 'received_outside_probe_dispatch')
    for number, stimulus in enumerate(focus['stimuli'], 1):
        assert stimulus['ordinal'] == number and stimulus['synthetic'] is True and stimulus['notification'] == 2016
        assert stimulus['operation'] == 'SceneTree.root.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)'
        before = 1 if number == 1 else 3
        assert stimulus['before_point_sequence'] == before
        assert rows[before]['collection_end_us'] <= stimulus['begin_mono_us'] <= stimulus['end_mono_us'] <= rows[before + 1]['mono_us']
        assert rows[before + 2]['mono_us'] - rows[before + 1]['collection_end_us'] >= 1500000
        assert rows[before + 2]['frame'] - rows[before + 1]['frame'] >= 8
        assert stimulus['event_end_index'] == stimulus['event_start_index'] + 1
        assert 0 <= stimulus['event_start_index'] < len(focus['events'])
        assert rows[before]['event_count'] == stimulus['event_start_index']
        assert rows[before + 1]['event_count'] == stimulus['event_end_index']
        event = focus['events'][stimulus['event_start_index']]
        assert event['notification'] == 2016 and event['probe_synthetic_dispatch'] == number
        assert event['origin'] == 'probe_synthetic' and event['pid'] == pid
        assert stimulus['begin_mono_us'] <= event['mono_us'] <= stimulus['end_mono_us']
    # Raw deltas and all owner identities are retained for independent review.
    # Already-initialized roots or non-reproduction never become a +4 claim.
    return paths


if __name__ == '__main__':
    if not __debug__:
        raise SystemExit('Optimized Python disables diagnostic checks; rerun without optimization.')
    if sys.argv[1:] == ['--owned-child']:
        raise SystemExit(child())
    if sys.argv[1:]:
        raise SystemExit('No public arguments; use the fixed owned diagnostic entry point.')
    try:
        code = outer()
    except Exception as error:
        import traceback
        with (BASE / 'outer-failure-01.json').open('x', encoding='utf-8') as log:
            json.dump({'type': type(error).__name__, 'detail': str(error),
                       'traceback': traceback.format_exc(), 'formal_acceptance': False}, log, indent=2)
        code = 1
    raise SystemExit(code)
