"""Prepared S102 import + twenty-command integration preflight; no implicit launch.

--check imports and validates the current 53-file closure without launching work.
--launch exclusively freezes run-01 and owns a copied --child through the accepted
BenchmarkProcess. The child uses the unchanged 20-second native import, then two
existing ten-command diagnostic groups. This never creates acceptance samples.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]  # original helper: HH3D/zdoc/reviews/<packet>
RUN_ID = 'gt06.s102.observability-preflight.01'
SOURCE_COUNT = 53
LOCKED_PROFILE_SHA256 = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'
CHILD_SECONDS = 75
OUTER_TARGET_SECONDS = 90  # Leave normal bounded owner cleanup outside the child budget.


class PreflightError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(condition, code):
    if not condition:
        raise PreflightError(code)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(65_536):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    need(Path(path).read_bytes() == raw, 'PREFLIGHT_EVIDENCE_READBACK')


def errors_record(errors):
    result = []
    for stage, error in errors:
        chain, seen = [], set()
        while error is not None and id(error) not in seen and len(chain) < 8:
            seen.add(id(error))
            name = type(error).__name__
            row = {'exception_class': name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception'}
            code = getattr(error, 'code', None)
            if code is None and len(error.args) == 1:
                code = error.args[0]
            if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
                row['code'] = code
            frames, trace = [], error.__traceback__
            while trace is not None:
                filename = Path(trace.tb_frame.f_code.co_filename).name
                frames.append({'file': filename if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', filename) else 'unknown',
                               'line': trace.tb_lineno})
                trace = trace.tb_next
            row['frames'] = frames[-16:]
            chain.append(row)
            error = error.__cause__ or error.__context__
        result.append({'stage': stage, 'chain': chain})
    return result


def load_campaign(root):
    sys.path.insert(0, str(root))
    from studio.tests.replay import run_benchmark_campaign as campaign
    factory, trusted = campaign.load_fixture()
    sources = campaign.source_files()
    need(len(sources) == SOURCE_COUNT, 'PREFLIGHT_SOURCE_COUNT')
    need(campaign.native_job.WALL_SECONDS == 20, 'PREFLIGHT_NATIVE_LIMIT_CHANGED')
    need(campaign.profile.PROFILE_SHA256 == LOCKED_PROFILE_SHA256, 'PREFLIGHT_PROFILE_CHANGED')
    need(callable(campaign.validate_import_snapshot) and callable(campaign.validate_phase_snapshot),
         'PREFLIGHT_VALIDATOR_MISSING')
    return campaign, factory, trusted, sources


def check():
    compile(Path(__file__).read_bytes(), str(Path(__file__)), 'exec')
    campaign, _, _, sources = load_campaign(ROOT)
    lock = json.loads((ROOT / 'studio/toolchain.lock.json').read_bytes())['godot']
    executable = ROOT / 'studio/.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(sha(executable) == lock['gui_sha256'], 'PREFLIGHT_BINARY_PIN')
    need(campaign.source_files() == sources, 'PREFLIGHT_SOURCE_CHANGED')
    return campaign, sources, executable, {
        'schema_id': 'hh-studio.observability-preflight-check', 'schema_version': '1.0.0',
        'source_files': sources, 'source_closure_sha256': campaign.closure(sources),
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        'python_sha256': sha(Path(sys.executable)), 'helper_sha256': sha(Path(__file__)),
        'godot_executable': str(executable), 'godot_sha256': lock['gui_sha256'],
        'native_wall_seconds': 20, 'child_budget_seconds': CHILD_SECONDS,
        'outer_target_seconds': OUTER_TARGET_SECONDS,
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'launched': False, 'engine_runs': 0, 'http_groups': 0}


def unchanged_sources(campaign, originals, copied, frozen):
    return (campaign.source_files() == originals
            and all(sha(copied / name) == digest for name, digest in frozen.items()))


def launch():
    started = time.monotonic()
    campaign, sources, executable, checked = check()
    run = BASE / 'run-01'
    run.mkdir(exist_ok=False)
    source = run / 'source'
    source.mkdir()
    frozen = {}
    for name, digest in sources.items():
        relative = Path(name)
        need(not relative.is_absolute() and not relative.drive and '..' not in relative.parts,
             'PREFLIGHT_SOURCE_PATH')
        original = ROOT / 'studio' / relative
        raw = campaign.read_regular(original)
        need(hashlib.sha256(raw).hexdigest() == digest, 'PREFLIGHT_SOURCE_CHANGED')
        target = source / 'studio' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        need(sha(target) == digest, 'PREFLIGHT_COPY_HASH')
        frozen['studio/' + relative.as_posix()] = digest
    helper = run / 'preflight.py'
    shutil.copyfile(Path(__file__), helper)
    need(sha(helper) == checked['helper_sha256'], 'PREFLIGHT_HELPER_CHANGED')
    need(unchanged_sources(campaign, sources, source, frozen), 'PREFLIGHT_FREEZE_DRIFT')
    freeze = {**checked, 'run_id': RUN_ID, 'frozen_files': frozen,
              'original_root': str(ROOT), 'freeze_started_monotonic_ns': time.perf_counter_ns()}
    write(run / 'freeze.json', freeze)
    child = run / 'child'
    child.mkdir()
    context = {'schema_id': 'hh-studio.observability-preflight-context', 'schema_version': '1.0.0',
        'run_id': RUN_ID, 'source_files': sources,
        'source_closure_sha256': checked['source_closure_sha256'],
        'profile_sha256': checked['profile_sha256'], 'formal_acceptance': False,
        'eligible_for_dataset': False, 'freeze_sha256': sha(run / 'freeze.json')}
    write(child / 'context.json', context)
    execution = {'source/' + name: digest for name, digest in frozen.items()}
    execution.update({'preflight.py': sha(helper), 'freeze.json': sha(run / 'freeze.json'),
                      'child/context.json': sha(child / 'context.json')})
    write(run / 'execution-source-files.json', execution)
    owner, capture, primary = None, None, None
    errors, observed = [], {}
    deadline = started + CHILD_SECONDS
    try:
        need(time.monotonic() < deadline, 'PREFLIGHT_PREPARE_LIMIT')
        owner = campaign.BenchmarkProcess(
            [str(Path(sys.executable)), '-B', str(helper), '--child', str(run)],
            cwd=run, output=run / 'owned', source_root=run, source_files=execution,
            binary_sha256=checked['python_sha256'], campaign_host=True)
        while owner.tick() is None:
            need(time.monotonic() < deadline, 'PREFLIGHT_OUTER_WALL_LIMIT')
            time.sleep(.02)
        capture = owner.finish()
        campaign.verify_capture(run / 'owned', sha(run / 'owned/capture.json'),
            source_root=run, expected_source_files=execution,
            expected_binary_sha256=checked['python_sha256'], expected_campaign_host=True)
        child_report = json.loads((child / 'report.json').read_bytes())
        need(child_report['completed'] is True and child_report['errors'] == [], 'PREFLIGHT_CHILD_INCOMPLETE')
        actual_pid = capture['actual_process_exit']['pid']
        need(child_report['processes']['host']['pid'] == actual_pid, 'PREFLIGHT_HOST_PID_MISMATCH')
        campaign.native_job.verify_captured_stage(child / 'import-host', sha(child / 'import-host/capture.json'))
        campaign.verify_observations(child, context, child_report)
        observed['observations_verified_against_actual_host_exit'] = True
    except BaseException as error:
        primary = error
        errors.append(('parent', error))
        retained = getattr(error, 'cleanup_owner', None)
        if owner is None and isinstance(retained, campaign.BenchmarkProcess):
            owner = retained
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(('outer_owner_close', error))
        getters = [
            ('owner', lambda: campaign._editor_cleanup_state(owner)),
            ('target', lambda: campaign._target_exit_state(run, 'owned')),
            ('source_unchanged', lambda: unchanged_sources(campaign, sources, source, frozen)),
            ('helper_original_unchanged', lambda: sha(Path(__file__)) == checked['helper_sha256']),
            ('execution_copy_unchanged', lambda: all(sha(run / name) == digest for name, digest in execution.items())),
            ('godot_binary_unchanged', lambda: sha(executable) == checked['godot_sha256']),
        ]
        for name, getter in getters:
            try:
                observed[name] = getter()
            except BaseException as error:
                observed[name] = None
                errors.append((name, error))
        for name in ('source_unchanged', 'helper_original_unchanged', 'execution_copy_unchanged', 'godot_binary_unchanged'):
            if observed.get(name) is not True:
                errors.append((name, PreflightError('PREFLIGHT_FINAL_PIN_CHANGED')))
        if primary is None and capture is None:
            errors.append(('capture', PreflightError('PREFLIGHT_CAPTURE_MISSING')))
        result = {'schema_id': 'hh-studio.observability-preflight-result', 'schema_version': '1.0.0',
            'run_id': RUN_ID, 'completed': capture is not None and not errors,
            'formal_acceptance': False, 'eligible_for_dataset': False,
            'source_closure_sha256': checked['source_closure_sha256'],
            'profile_sha256': checked['profile_sha256'], 'freeze_sha256': sha(run / 'freeze.json'),
            'execution_source_sha256': sha(run / 'execution-source-files.json'),
            'elapsed_seconds': time.monotonic() - started,
            'child_budget_seconds': CHILD_SECONDS, 'outer_target_seconds': OUTER_TARGET_SECONDS,
            'errors': errors_record(errors), 'observations': observed,
            'outer_capture_sha256': sha(run / 'owned/capture.json') if (run / 'owned/capture.json').is_file() else None,
            'child_report_sha256': sha(child / 'report.json') if (child / 'report.json').is_file() else None,
            'scope': 'One unchanged 20s import and two ten-command HTTP diagnostic groups on frozen source; no native benchmark cycles or acceptance samples'}
        write(run / 'result.json', result)
    print(json.dumps({'completed': result['completed'], 'result': str(run / 'result.json'),
                      'formal_acceptance': False, 'elapsed_seconds': result['elapsed_seconds']}), flush=True)
    return 0 if result['completed'] else 1


def child(run):
    run = Path(run).resolve()
    need(Path(__file__).resolve() == run / 'preflight.py', 'PREFLIGHT_COPIED_CHILD_REQUIRED')
    freeze = json.loads((run / 'freeze.json').read_bytes())
    root, source = run / 'child', run / 'source'
    context = json.loads((root / 'context.json').read_bytes())
    need(sha(run / 'freeze.json') == context['freeze_sha256'], 'PREFLIGHT_FREEZE_HASH')
    need(sha(Path(__file__)) == freeze['helper_sha256'], 'PREFLIGHT_HELPER_CHANGED')
    need(all(sha(source / name) == digest for name, digest in freeze['frozen_files'].items()), 'PREFLIGHT_COPY_HASH')
    campaign, factory, trusted, sources = load_campaign(source)
    need(sources == freeze['source_files'] == context['source_files'], 'PREFLIGHT_CHILD_SOURCE_CHANGED')
    need(campaign.profile.PROFILE_SHA256 == context['profile_sha256'], 'PREFLIGHT_PROFILE_CHANGED')
    executable = Path(freeze['godot_executable'])
    need(sha(executable) == freeze['godot_sha256'], 'PREFLIGHT_BINARY_PIN')
    producer = observer = retained = None
    errors, reports, states = [], [], {}
    body_done = False
    try:
        binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
            'run_id': RUN_ID, 'mode': 'full', 'source_closure_sha256': context['source_closure_sha256'],
            'profile_sha256': context['profile_sha256'], 'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}
        project = root / 'project'
        initial = campaign.prepare(project, factory, trusted, binding)
        (project / 'benchmark/input').mkdir()
        write(root / 'initial-project-files.json', initial)
        observer = campaign.ImportObserver(root / 'import-host', project, executable)
        campaign._observed_import(root, context, project, executable, freeze['godot_sha256'], observer, errors)
        campaign.native_job.verify_captured_stage(root / 'import-host', sha(root / 'import-host/capture.json'))
        need(not list((project / 'benchmark/out').iterdir()), 'PREFLIGHT_IMPORT_ACTIVATED')
        imported_files = campaign.project_files(project)
        need(all(imported_files.get(name) == digest for name, digest in initial.items()),
             'PREFLIGHT_IMPORT_SOURCE_CHANGED')
        producer = campaign.CommandProducer(root / 'commands', RUN_ID)
        for index in range(2):
            report = producer.run_diagnostic()
            write(root / f'command-{index:02d}.json', report)
            need(report['schema_version'] == '1.3.0' and report['mode'] == 'diagnostic'
                 and report['status'] == 'DIAGNOSTIC' and len(report['commands']) == 10
                 and report['complete_command_mix'] is False and report['native_acceptance'] is False
                 and report['effect_count_after'] == 2 * (index + 1)
                 and report['cancel']['no_effect'] is True, 'PREFLIGHT_COMMAND_POSTCONDITION')
            reports.append({'index': index, 'sha256': sha(root / f'command-{index:02d}.json'),
                            'max_status_gap_ms': report['max_status_gap_ms'], 'effect_count_after': report['effect_count_after']})
        body_done = True
    except BaseException as error:
        errors.append(('child', error))
        retained = getattr(error, 'cleanup_owner', None)
        if producer is None and isinstance(retained, campaign.CommandProducer):
            producer = retained
        partial = getattr(error, 'report', None)
        if partial is not None:
            try:
                write(root / 'partial-command.json', partial)
            except BaseException as receipt_error:
                errors.append(('partial_command_receipt', receipt_error))
    finally:
        seen = set()
        for name, owned in (('producer', producer), ('import_observer', observer), ('constructor_owner', retained)):
            if owned is None or id(owned) in seen:
                continue
            seen.add(id(owned))
            try:
                owned.close()
            except BaseException as error:
                errors.append((name + '_close', error))
        try:
            campaign._write_observation(root, context, 'http', None if producer is None else producer.phase_snapshot())
        except BaseException as error:
            errors.append(('http_observation_receipt', error))
        if not (root / 'import-observation.json').exists():
            try:
                campaign._write_observation(root, context, 'import', None if observer is None else observer.snapshot())
            except BaseException as error:
                errors.append(('import_observation_receipt', error))
        for name, getter in (
            ('producer', lambda: campaign._producer_cleanup_state(producer)),
            ('import_observer', lambda: campaign._import_cleanup_state(observer)),
            ('import_target', lambda: campaign._target_exit_state(root, 'import-host')),
            ('source_unchanged', lambda: campaign.source_files() == sources),
            ('copied_source_unchanged', lambda: all(sha(source / name) == digest for name, digest in freeze['frozen_files'].items())),
        ):
            try:
                states[name] = getter()
            except BaseException as error:
                states[name] = None
                errors.append((name + '_observe', error))
        identity = dict(producer.identity) if producer is not None and hasattr(producer, 'identity') else {'pid': os.getpid()}
        processes = {'host': identity}
        try:
            campaign.verify_observations(root, context, {'processes': processes})
            states['observations_verified'] = True
        except BaseException as error:
            states['observations_verified'] = False
            errors.append(('verify_observations', error))
        try:
            need(states['source_unchanged'] is True and states['copied_source_unchanged'] is True,
                 'PREFLIGHT_CHILD_SOURCE_CHANGED')
            state = states['producer']
            need(state is not None and state.get('closed') is True, 'PREFLIGHT_PRODUCER_HELD')
            need(not any(state['host']['threads_alive']) and state['host']['main_socket_closed'] is True
                 and state['host']['control_socket_closed'] is True
                 and state['observer_probe']['handle_retained'] is False
                 and state['observer_probe']['close_uncertain'] is False
                 and state['journal']['cache_closed'] is True and state['journal']['index_retained'] is False,
                 'PREFLIGHT_PRODUCER_HELD')
        except BaseException as error:
            errors.append(('cleanup_verify', error))
        report = {'schema_id': 'hh-studio.observability-preflight-child', 'schema_version': '1.0.0',
            'run_id': RUN_ID, 'completed': body_done and not errors, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'source_closure_sha256': context['source_closure_sha256'],
            'profile_sha256': context['profile_sha256'], 'processes': processes, 'groups': reports,
            'groups_requested': 2, 'groups_completed': len(reports), 'native_benchmark_cycles': 0,
            'states': states, 'errors': errors_record(errors),
            'host_actual_exit': None, 'host_exit_missing_reason': 'PARENT_OBSERVES_EXIT_AFTER_THIS_REPORT'}
        write(root / 'report.json', report)
    return 0 if report['completed'] else 1


def main():
    if sys.argv[1:] == ['--check']:
        _, _, _, result = check()
        print(json.dumps(result, sort_keys=True), flush=True)
        return 0
    if sys.argv[1:] == ['--launch']:
        return launch()
    if len(sys.argv) == 3 and sys.argv[1] == '--child':
        return child(sys.argv[2])
    print('Use --check (read-only) or coordinator-authorized --launch.', flush=True)
    return 2


if __name__ == '__main__':
    try:
        code = main()
    except BaseException as error:
        diagnostic = {'status': 'PREFLIGHT_INCOMPLETE', 'formal_acceptance': False,
                      'errors': errors_record([('top_level', error)])}
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
        code = 1
    raise SystemExit(code)
