"""One owned S107 native-only preview-cost diagnostic; no implicit launch.

Forty semantic cycles (ten ABBA groups), original phase limits, no HTTP/PSS.
The native overlay and collector are separate from the unchanged base53/profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import types

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CORE_SHA256 = '956a1c56d215693fb5828e04b74db04fba45a57bfb0bde12bf76a11c21dcc1a0'
CORE_ORIGINAL = 'zdoc/reviews/20260919-gt06-s106-handle-boundary/owned_handles.py'
NATIVE_HELPER_SHA256 = '413b0127113f10967cb42dc7921298c3dcf54d6e218a68212f8ba8109bcede1a'
RUN_ID = re.compile(r'gt06-s107-preview-[a-z0-9][a-z0-9-]{0,30}\Z')
OUTER_SECONDS = 180
ROW_MARKER = 'HH_GT06_S107_PREVIEW_COST '
COMPLETE_MARKER = 'HH_GT06_S107_PREVIEW_COST_COMPLETE '


def _load_core():
    path = HERE / 'core.py' if (HERE / 'core.py').is_file() else REPO / CORE_ORIGINAL
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CORE_SHA256:
        raise RuntimeError('S107_CORE_PIN')
    module = types.ModuleType('_s107_pinned_core')
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


c = _load_core()


def check(repo=REPO):
    pins, _unused_s103_overlay, reused = c.checked_pins(repo)
    raw = c.read(HERE / 'native_probe.py')
    c.need(c.sha(raw) == NATIVE_HELPER_SHA256, 'S107_NATIVE_HELPER_PIN')
    helper = c.frozen_module(HERE / 'native_probe.py', raw, '_s107_native_helper')
    source = c.read(repo / 'studio/tests/replay/benchmark_native.gd')
    c.need(c.sha(source) == c.NATIVE_SHA == helper.BASE_SOURCE_SHA256, 'S107_NATIVE_SOURCE_PIN')
    overlay = helper.build_overlay(source)
    c.need(type(overlay) is bytes and overlay, 'S107_OVERLAY')
    c.need(helper.ROW_MARKER == ROW_MARKER and helper.COMPLETE_MARKER == COMPLETE_MARKER,
           'S107_MARKER_CONTRACT')
    return pins, helper, overlay, reused


def campaign_hash(context):
    return c.sha(c.encoded({k: v for k, v in context.items() if k != 'campaign_sha256'}))


def validate_context(context, root):
    c.need(context['schema'] == 'gt06-s107-preview-cost-context-v1'
           and RUN_ID.fullmatch(context['run_id']) and root.name == context['run_id'], 'S107_CONTEXT_RUN')
    c.need(context['source_closure_sha256'] == c.SOURCE_SHA and context['profile_sha256'] == c.PROFILE_SHA
           and len(context['source_files']) == 53 and c.closure(context['source_files']) == c.SOURCE_SHA,
           'S107_BASE_SOURCE_PIN')
    c.need(context['native_helper_sha256'] == NATIVE_HELPER_SHA256
           and context['core_sha256'] == CORE_SHA256
           and context['diagnostic_closure_sha256'] == c.closure(context['diagnostic_files'])
           and context['campaign_sha256'] == campaign_hash(context), 'S107_CONTEXT_HASH')
    c.need(context['index'] == 0 and context['attempt'] == 1 and context['cycles'] == 40
           and context['groups'] == 10 and context['sequence'] == 'ABBA'
           and context['outer_seconds'] == OUTER_SECONDS
           and context['formal_acceptance'] is False and context['eligible_for_dataset'] is False,
           'S107_SCOPE')


def native_binding(context):
    return {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
            'run_id': context['run_id'], 'mode': 'diagnostic',
            'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
            'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}


def supplemental_binding(context):
    return {'schema_id': 'hh-studio.s107-preview-cost-context', 'schema_version': '1.0.0',
            'run_id': context['run_id'], 'base_source_closure_sha256': c.SOURCE_SHA,
            'profile_sha256': c.PROFILE_SHA, 'recipe_sha256': context['recipe_sha256'],
            'generated_overlay_sha256': context['generated_overlay_sha256'],
            'diagnostic_closure_sha256': context['diagnostic_closure_sha256']}


def freeze(run_id, pins, helper, overlay, reused):
    c.need(RUN_ID.fullmatch(run_id), 'S107_RUN_ID')
    root = REPO / 'studio/.local/reviews' / run_id
    owned = HERE / 'owned' / run_id
    c.need(not os.path.lexists(root) and not os.path.lexists(owned), 'S107_FRESH_RUN_REQUIRED')
    root.mkdir(parents=True)
    owned.mkdir(parents=True)
    values = {'run_probe.py': c.read(Path(__file__)), 'core.py': c.read(REPO / CORE_ORIGINAL),
              'native_probe.py': c.read(HERE / 'native_probe.py'), 'overlay.gd': overlay,
              'read_preview.py': c.read(HERE / 'read_preview.py'),
              'recipe.json': c.encoded(helper.RECIPE)}
    values.update({'historical-' + Path(name).name: raw for name, raw in reused.items()})
    files, paths = {}, {}
    for name, raw in values.items():
        target = owned / name
        c.write_new(target, raw)
        relative = target.relative_to(REPO).as_posix()
        files[relative], paths[name] = c.sha(raw), relative
    context = {'schema': 'gt06-s107-preview-cost-context-v1', 'run_id': run_id, 'index': 0, 'attempt': 1,
               'source_files': pins['sources'], 'source_closure_sha256': c.SOURCE_SHA,
               'profile_sha256': c.PROFILE_SHA, 'core_sha256': CORE_SHA256,
               'native_helper_sha256': NATIVE_HELPER_SHA256, 'recipe_sha256': helper.RECIPE_SHA256,
               'reader_sha256': c.sha(values['read_preview.py']),
               'generated_overlay_sha256': c.sha(overlay), 'diagnostic_files': files,
               'diagnostic_paths': paths, 'diagnostic_closure_sha256': c.closure(files),
               'godot_executable': str(pins['executable']), 'godot_sha256': pins['godot_sha256'],
               'python_sha256': pins['python_sha256'], 'outer_seconds': OUTER_SECONDS,
               'cycles': 40, 'groups': 10, 'sequence': 'ABBA', 'formal_acceptance': False,
               'eligible_for_dataset': False}
    context['campaign_sha256'] = campaign_hash(context)
    validate_context(context, root)
    c.write_new(root / 'context.json', context)
    c.write_new(root / 'source-files.json', pins['sources'])
    return root, context


def prepare(root, context, campaign):
    repo, studio = root.parents[3], root.parents[2]
    c.verify_files(repo, context['diagnostic_files'])
    c.verify_files(studio, context['source_files'])
    factory, trusted = campaign.load_fixture()
    c.need(campaign.source_files() == context['source_files'], 'S107_IMPORTED_SOURCE_SET')
    project = root / 'project'
    initial = campaign.prepare(project, factory, trusted, native_binding(context))
    target = project / 'addons/hh_benchmark/benchmark_native.gd'
    c.need(c.sha(c.read(target)) == c.NATIVE_SHA, 'S107_GENERATED_BASE_PIN')
    overlay = c.read(repo / context['diagnostic_paths']['overlay.gd'])
    c.need(c.sha(overlay) == context['generated_overlay_sha256'], 'S107_OVERLAY_PIN')
    temporary = target.with_name(target.name + '.s107-overlay')
    c.write_new(temporary, overlay)
    temporary.replace(target)
    c.need(c.read(target) == overlay, 'S107_OVERLAY_READBACK')
    initial['addons/hh_benchmark/benchmark_native.gd'] = c.sha(overlay)
    sidecar = project / 'benchmark/s107-context.json'
    c.write_new(sidecar, supplemental_binding(context))
    initial['benchmark/s107-context.json'] = c.sha(c.read(sidecar))
    c.write_new(root / 'initial-project-files.json', initial)
    return project, initial


def marked(raw, marker):
    return [c.decode(line[len(marker):]) for line in raw.decode('utf-8').splitlines() if line.startswith(marker)]


def collect(root, context, snapshot, editor_capture, campaign, *, analyzer=None):
    """Bind raw output; root's versioned reader owns timing interpretation."""
    project = root / 'project'
    stdout = (root / 'editor-host/stdout.txt').read_bytes()
    stderr = (root / 'editor-host/stderr.txt').read_bytes()
    c.need(not stderr.strip() and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked', stdout),
           'S107_NATIVE_LOG')
    c.need(not marked(stdout, 'HH_GT06_BENCHMARK_FAILED '), 'S107_NATIVE_FAILED')
    rows, complete = marked(stdout, ROW_MARKER), marked(stdout, COMPLETE_MARKER)
    c.need(len(rows) == 40 and len(complete) == 1, 'S107_BOUNDARY_COUNT')
    index_path = project / 'benchmark/out/index.json'
    batch_path = project / 'benchmark/out/batch-00.json'
    report_path = project / 'benchmark/out/preview-cost.json'
    index, batch, report = (c.decode(c.read(path)) for path in (index_path, batch_path, report_path))
    actual = editor_capture['actual_process_exit']
    c.need(actual['exit_code'] == 0 and editor_capture['wrapper_exit_code'] == 0, 'S107_NATIVE_EXIT')
    c.need(index['input'] == native_binding(context) and index['completed'] is True
           and index['benchmark_complete'] is False and index['host_integrated'] is False
           and index['batches_completed'] == 1 and index['cycles_per_batch'] == 40
           and index['pid'] == actual['pid'] and len(batch['cycles']) == len(batch['raw_timings']) == 40,
           'S107_NATIVE_COMPLETION')
    c.need(batch['run_id'] == context['run_id'] and batch['mode'] == 'diagnostic'
           and batch['pid'] == actual['pid'] and batch['index'] == 0, 'S107_BATCH_BINDING')
    c.need(index['batches'] == [{'index': 0, 'file': 'batch-00.json',
           'sha256': c.sha(c.read(batch_path)), 'size_bytes': batch_path.stat().st_size}],
           'S107_INDEX_BATCH_HASH')
    for number, row in enumerate(rows):
        semantic, timing = batch['cycles'][number], batch['raw_timings'][number]
        c.need(all(row[key] == semantic[key] for key in
               ('before_sha256', 'created_sha256', 'undone_sha256', 'reloaded_sha256',
                'root_before', 'root_after', 'effects'))
               and row['scene_sha256'] == semantic['saved_file_sha256']
               and row['save_start_us'] == timing['save']['start_us']
               and row['readback_end_us'] == timing['save']['end_us']
               and row['signal_us'] == timing['save_signal_mono_us'], 'S107_ROW_NATIVE_BINDING')
        c.need(row['schema_id'] == 'hh-studio.s107-preview-cost-cycle' and row['schema_version'] == '1.0.0'
               and row['cycle'] == number and row['group'] == number // 4
               and row['position'] == number % 4 and row['arm'] == 'ABBA'[number % 4]
               and row['completed'] is True and row['run_id'] == context['run_id']
               and row['pid'] == actual['pid'], 'S107_ROW_BINDING')
        for key in ('recipe_sha256', 'generated_overlay_sha256', 'diagnostic_closure_sha256'):
            c.need(row[key] == context[key], 'S107_ROW_PROVENANCE')
        c.need(row['source_closure_sha256'] == c.SOURCE_SHA and row['profile_sha256'] == c.PROFILE_SHA,
               'S107_ROW_BASE')
        c.need((row['method'] == 'save_scene' and type(row['return_error']) is int and row['return_error'] == 0)
               if row['arm'] == 'A' else (row['method'] == 'save_scene_as' and row['return_error'] is None),
               'S107_RETURN_CONTRACT')
    if analyzer is None:
        reader_path = root.parents[3] / context['diagnostic_paths']['read_preview.py']
        reader_raw = c.read(reader_path)
        c.need(c.sha(reader_raw) == context['reader_sha256'], 'S107_READER_PIN')
        reader = c.frozen_module(reader_path, reader_raw, '_s107_frozen_reader')
        analyzer = reader.analyze
    expected = {'run_id': context['run_id'], 'pid': actual['pid'],
                'source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
                'base_source_sha256': c.NATIVE_SHA, 'recipe_sha256': context['recipe_sha256'],
                'generated_overlay_sha256': context['generated_overlay_sha256'],
                'diagnostic_closure_sha256': context['diagnostic_closure_sha256'],
                'context_sha256': c.sha(c.read(project / 'benchmark/s107-context.json'))}
    analysis = analyzer(stdout, c.read(report_path), c.read(index_path), expected)
    c.need(analysis.get('artifact_status') == 'VALIDATED' and analysis.get('formal_acceptance') is False
           and analysis.get('eligible_for_dataset') is False, 'S107_READER_INCOMPLETE')
    after = campaign.project_files(project)
    c.need({k: v for k, v in after.items() if k != campaign.MUTABLE_SCENE}
           == {k: v for k, v in snapshot.items() if k != campaign.MUTABLE_SCENE}, 'S107_PROJECT_DRIFT')
    c.need(campaign.source_files() == context['source_files'], 'S107_SOURCE_DRIFT')
    return {'schema': 'gt06-s107-native-output-capture-v1', 'run_id': context['run_id'],
            'cycles': 40, 'groups': 10, 'sequence': 'ABBA', 'pid': actual['pid'],
            'rows': rows, 'completion': complete[0], 'report': c.ref(root, report_path),
            'native_index': c.ref(root, index_path), 'native_batch': c.ref(root, batch_path),
            'native_stdout': c.ref(root, root / 'editor-host/stdout.txt'),
            'analysis': analysis, 'reader_sha256': context.get('reader_sha256'),
            'interpretation': 'VERSIONED_READER_DERIVED_NO_ACCEPTANCE', 'formal_acceptance': False,
            'eligible_for_dataset': False}


def execute_child(root, context, campaign, *, writer=c.write_new, collector=collect, wait=c.wait_owner):
    """Owned lifecycle seam for fake tests; production supplies unchanged APIs."""
    owner = probe = imported_observer = retained = None
    primary, errors, result = None, [], None
    phase = 'prepare'
    try:
        c.need(not campaign.stop_requested(root, run_id=context['run_id'],
               source_closure_sha256=c.SOURCE_SHA, campaign_sha256=context['campaign_sha256']), 'BENCHMARK_STOPPED')
        project, initial = prepare(root, context, campaign)
        executable = Path(context['godot_executable'])
        phase = 'import'
        imported_observer = campaign.ImportObserver(root / 'import-host', project, executable)
        campaign._observed_import(root, context, project, executable, context['godot_sha256'], imported_observer, errors)
        campaign.native_job.verify_captured_stage(root / 'import-host', c.sha(c.read(root / 'import-host/capture.json')))
        c.need(not list((project / 'benchmark/out').iterdir()), 'S107_IMPORT_ACTIVATED')
        snapshot = campaign.project_files(project)
        c.need(all(snapshot.get(k) == v for k, v in initial.items()), 'S107_IMPORT_DRIFT')
        writer(root / 'editor-snapshot.json', snapshot)
        runtime = dict(context['source_files'])
        studio = root.parents[2]
        runtime.update({(project / name).relative_to(studio).as_posix(): digest
                        for name, digest in snapshot.items() if name != campaign.MUTABLE_SCENE})
        c.need(not campaign.stop_requested(root, run_id=context['run_id'],
               source_closure_sha256=c.SOURCE_SHA, campaign_sha256=context['campaign_sha256']), 'BENCHMARK_STOPPED')
        phase = 'editor'
        owner = campaign.BenchmarkProcess([str(executable), '--editor', '--path', str(project),
                  'res://scenes/fixture.tscn', '--', '--hh-benchmark-mode=diagnostic'],
                  cwd=project, output=root / 'editor-host', source_root=studio,
                  source_files=runtime, binary_sha256=context['godot_sha256'])
        probe = campaign.open_probe(owner, executable)
        identity = {'pid': probe.pid, 'process_start': probe.process_start}
        writer(root / 'editor-identity.json', identity)
        code = wait(owner, root, context, campaign.stop_requested, OUTER_SECONDS)
        c.need(code == 0, 'S107_EDITOR_HELPER_EXIT')
        captured = owner.finish()  # Wait for natural target exit0; do not kill at cycle40.
        c.need(captured['actual_process_exit']['pid'] == identity['pid'], 'S107_EDITOR_IDENTITY')
        campaign.verify_capture(root / 'editor-host', c.sha(c.read(root / 'editor-host/capture.json')),
             source_root=studio, expected_source_files=runtime, expected_binary_sha256=context['godot_sha256'])
        phase = 'collect'
        result = collector(root, context, snapshot, captured, campaign)
        result['editor_identity'] = identity
    except BaseException as error:
        primary, retained = error, getattr(error, 'cleanup_owner', None)
    finally:
        seen = set()
        for role, item in (('probe', probe), ('editor_owner', owner), ('import_observer', imported_observer),
                           ('constructor_owner', retained)):
            if item is None or id(item) in seen:
                continue
            seen.add(id(item))
            try:
                item.close()
            except BaseException as error:
                errors.append((role, error))
        observations = {}
        for role, getter in (
            ('editor_probe', lambda: campaign._probe_cleanup_state(probe)),
            ('editor_owner', lambda: campaign._editor_cleanup_state(owner)),
            ('import_observer', lambda: campaign._import_cleanup_state(imported_observer)),
            ('editor_target', lambda: c.target_exit(root, 'editor-host')),
            ('import_target', lambda: c.target_exit(root, 'import-host'))):
            try:
                observations[role] = getter()
            except BaseException as error:
                observations[role] = {'status': 'UNKNOWN', 'error': c.error_record(error)}
                errors.append((role + '_observe', error))
        try:
            terminal = {'schema': 'gt06-s107-child-terminal-v1', 'run_id': context['run_id'],
                        'phase': phase, 'context': c.ref(root, root / 'context.json'),
                        'primary_error': c.error_record(primary) if primary is not None else None,
                        'errors': [{'stage': role, **c.error_record(error)} for role, error in errors],
                        'observations': observations, 'constructor_owner_retained': retained is not None,
                        'import_wrapper_native_handle_closure': 'UNKNOWN_NOT_RECORDED',
                        'child_self_actual_exit': None, 'outer_runner_actual_exit': None,
                        'formal_acceptance': False, 'eligible_for_dataset': False}
            writer(root / 'child-terminal-cleanup.json', terminal)
        except BaseException as error:
            errors.append(('terminal_receipt', error))
    if primary is None and errors:
        primary = c.DiagnosticError('S107_CLEANUP_OR_OBSERVATION_FAILED')
    if primary is None:
        try:
            writer(root / 'child-result.json', result)
            return result
        except BaseException as error:
            primary = error
    try:
        writer(root / 'child-failure.json', {'schema': 'gt06-s107-child-failure-v1',
               'run_id': context['run_id'], 'phase': phase, 'primary_error': c.error_record(primary),
               'secondary_errors': [{'stage': role, **c.error_record(error)} for role, error in errors],
               'formal_acceptance': False, 'eligible_for_dataset': False})
    except BaseException as error:
        errors.append(('failure_receipt', error))
    primary.s107_secondary_errors = tuple(error for _, error in errors)
    raise primary


def child(root):
    root = root.resolve()
    context = c.decode(c.read(root / 'context.json'))
    validate_context(context, root)
    sys.path.insert(0, str(root.parents[3]))
    from studio.tests.replay import run_benchmark_campaign as campaign
    return execute_child(root, context, campaign)


def summarize(root, context, owner_result, postflight_errors):
    result = {'schema': 'gt06-s107-owned-preview-cost-result-v1', 'run_id': context['run_id'],
              'status': 'INCOMPLETE', 'formal_acceptance': False, 'eligible_for_dataset': False,
              'owner': owner_result, 'errors': list(postflight_errors), 'actual_exits': {},
              'outer_runner_actual_exit': None, 'outer_runner_exit_reason': 'NOT_OBSERVABLE_BY_SELF',
              'import_wrapper_native_handle_closure': 'UNKNOWN_NOT_RECORDED',
              'base_source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
              'diagnostic_closure_sha256': context['diagnostic_closure_sha256'],
              'generated_overlay_sha256': context['generated_overlay_sha256'],
              'recipe_sha256': context['recipe_sha256'], 'interpretation': 'PENDING_VERSIONED_READER'}
    for role in ('host-owner', 'editor-host', 'import-host'):
        try:
            result['actual_exits'][role] = c.target_exit(root, role)
        except BaseException as error:
            result['actual_exits'][role] = {'status': 'UNKNOWN', 'error': c.error_record(error)}
    if (root / 'child-failure.json').is_file():
        try:
            result['child_failure'] = c.decode(c.read(root / 'child-failure.json'))
        except BaseException as error:
            result['child_failure'] = {'status': 'UNKNOWN', 'error': c.error_record(error)}
    try:
        c.need(owner_result['primary_error'] is None and not owner_result['cleanup_errors']
               and not postflight_errors and owner_result['helper_exit_observed_by_tick'] == 0,
               'S107_OWNER_FAILURE')
        c.need(not (root / 'child-failure.json').exists(), 'S107_CHILD_FAILED')
        terminal = c.decode(c.read(root / 'child-terminal-cleanup.json'))
        c.need(terminal['run_id'] == context['run_id'] and terminal['primary_error'] is None
               and terminal['errors'] == [] and terminal['context'] == c.ref(root, root / 'context.json')
               and terminal['constructor_owner_retained'] is False, 'S107_TERMINAL')
        observations = terminal['observations']
        c.need(observations['editor_probe'] == {'present': True, 'handle_retained': False, 'close_uncertain': False},
               'S107_PROBE_HELD')
        editor = observations['editor_owner']
        c.need(editor['present'] is True and editor['closed'] is True and c.clean_job(editor['job'])
               and c.clean_handle(editor['wrapper_process_handle']) and editor['helper_exit_code'] == 0
               and all(v is False for v in editor['drain_threads_alive']), 'S107_EDITOR_HELD')
        c.need(observations['import_observer'] == {'present': True, 'closed': True, 'thread_alive': False,
               'handle_retained': False, 'handle_close_uncertain': False, 'probe_handles_released': True,
               'global_held_probe_count': 0, 'error_count': 0}, 'S107_IMPORT_OBSERVER_HELD')
        for role, state in result['actual_exits'].items():
            c.need(state['status'] == 'OBSERVED' and state['actual_exit']['exit_code'] == 0, 'S107_ACTUAL_EXIT')
        for role in ('host-owner', 'editor-host', 'import-host'):
            capture = c.decode(c.read(root / role / 'capture.json'))
            c.need(capture['actual_process_exit'] == result['actual_exits'][role]['actual_exit']
                   and capture['wrapper_exit_code'] == 0 and c.clean_job(capture['job']), 'S107_CAPTURE_LIFECYCLE')
            if role != 'import-host':
                c.need(c.clean_handle(capture['wrapper_process_handle']), 'S107_WRAPPER_HANDLE_HELD')
        child_result = c.decode(c.read(root / 'child-result.json'))
        c.need(child_result['run_id'] == context['run_id'] and child_result['cycles'] == 40
               and child_result['pid'] == result['actual_exits']['editor-host']['start']['pid'], 'S107_CHILD_RESULT')
        result.update(status='CAPTURED', child_result=c.ref(root, root / 'child-result.json'),
                      terminal=c.ref(root, root / 'child-terminal-cleanup.json'),
                      cleanup_status='RECORDED_JOB_PROBE_EDITOR_AND_HOST_HANDLE_RELEASES_VERIFIED')
    except BaseException as error:
        result['errors'].append(c.error_record(error))
    if owner_result['primary_error']:
        code = owner_result['primary_error']['code']
        if code == 'BENCHMARK_STOPPED':
            result['status'] = 'STOPPED'
        elif code == 'S106_OUTER_TIMEOUT':
            result['status'] = 'TIMED_OUT'
    return result


def selected_capture_paths(root):
    """Explicit bounded evidence domains; never walk cache/temp/localappdata."""
    selected = set()
    root_names = ('context.json', 'source-files.json', 'initial-project-files.json',
                  'editor-snapshot.json', 'editor-identity.json', 'import-observation.json',
                  'child-result.json', 'child-failure.json', 'child-terminal-cleanup.json',
                  'diagnostic-result.json')
    for name in root_names:
        if (root / name).is_file():
            selected.add(root / name)
    for stage in ('host-owner', 'editor-host', 'import-host'):
        directory = root / stage
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file() and (path.suffix == '.json' or path.name in ('stdout.txt', 'stderr.txt')):
                    selected.add(path)
    initial_path = root / 'initial-project-files.json'
    if initial_path.is_file():
        for name in c.decode(c.read(initial_path)):
            c.need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'S107_PROJECT_PATH')
            path = root / 'project' / name
            if path.is_file():
                selected.add(path)
    for name in ('index.json', 'batch-00.json', 'preview-cost.json'):
        path = root / 'project/benchmark/out' / name
        if path.is_file():
            selected.add(path)
    c.need(len(selected) <= 160, 'S107_CAPTURE_FILE_BOUND')
    return sorted(selected)


def run(run_id):
    pins, helper, overlay, reused = check()
    root, context = freeze(run_id, pins, helper, overlay, reused)
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    sources = {'studio/' + name: digest for name, digest in pins['sources'].items()}
    sources.update(context['diagnostic_files'])
    sources[(root / 'context.json').relative_to(REPO).as_posix()] = c.sha(c.read(root / 'context.json'))
    argv = [sys.executable, '-B', str(REPO / context['diagnostic_paths']['run_probe.py']), '--child', str(root)]
    factory = lambda: BenchmarkProcess(argv, cwd=root, output=root / 'host-owner', source_root=REPO,
                  source_files=sources, binary_sha256=pins['python_sha256'], campaign_host=True)
    # Natural child success needs finish(), not only close(), for checked exit0.
    def wait_and_finish(owner, *args):
        code = c.wait_owner(owner, *args)
        if code == 0:
            owner.finish()
        return code
    owner_result, _owner = c.own_run(factory, root, context, pins['campaign'].stop_requested,
                                    OUTER_SECONDS, wait=wait_and_finish)
    postflight = []
    try:
        c.verify_files(REPO, sources)
    except BaseException as error:
        postflight.append(c.error_record(error))
    result = summarize(root, context, owner_result, postflight)
    c.write_new(root / 'diagnostic-result.json', result)
    manifest = {'schema': 'gt06-s107-capture-manifest-v1', 'run_id': run_id,
                'formal_acceptance': False, 'eligible_for_dataset': False,
                'diagnostic_files': context['diagnostic_files'], 'base_source_files': context['source_files'],
                'exclusions': ['project/.godot', 'localappdata', 'temp', 'unlisted caches and outputs'],
                'files': [pins['campaign'].reference(root, path) for path in selected_capture_paths(root)]}
    c.write_new(root / 'capture-manifest.json', manifest)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--launch', action='store_true')
    group.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--run-id')
    args = parser.parse_args(argv)
    if args.child is not None:
        child(args.child)
        return 0
    c.need(type(args.run_id) is str and RUN_ID.fullmatch(args.run_id), 'S107_RUN_ID')
    if args.check:
        pins, helper, overlay, _reused = check()
        result = {'status': 'STATIC_PINS_VERIFIED', 'run_id': args.run_id, 'engine_started': False,
                  'base_source_closure_sha256': c.SOURCE_SHA, 'profile_sha256': c.PROFILE_SHA,
                  'native_helper_sha256': NATIVE_HELPER_SHA256, 'recipe_sha256': helper.RECIPE_SHA256,
                  'generated_overlay_sha256': c.sha(overlay), 'source_file_count': len(pins['sources']),
                  'formal_acceptance': False, 'eligible_for_dataset': False}
    else:
        result = run(args.run_id)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('STATIC_PINS_VERIFIED', 'CAPTURED') else 3


if __name__ == '__main__':
    raise SystemExit(main())
