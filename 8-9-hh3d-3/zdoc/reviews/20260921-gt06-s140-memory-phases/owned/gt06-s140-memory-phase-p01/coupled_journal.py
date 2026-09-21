"""S129 diagnostic: original 35-batch gates plus post-rejection identity capture.

Stock native workload and original profile. No formal dataset. New helper fixes
PSS schema/role/completion joins and permits natural full-run drain. A passive
external observer must retain the launcher before any background dispatch.
"""
from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

import memory_phases as phase_memory

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN_ID = 'gt06-s140-memory-phase-p01'
CLOSURE = '763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4'
NATIVE_HASH = '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95'
PSS_SHA256 = '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76'
HELPER_PINS = {'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py': 'ad4e2d15cbcb3f890f22a7d2be339aee6b726c62a9c339dfac4478fdaf21e998', 'zdoc/reviews/20260920-gt06-s129-helper-repair/post_failure_handles.py': '1b883befacb9c7bb6e81f65a0c660bf68ec11ee6930bed890c7837cf2ce670a6', 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py': '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76'}
PREFIX_BATCHES = 1
STOP_AT_BOUNDARY = False
OUTER_SECONDS = 7530


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Boundary(RuntimeError):
    code = 'S129_BOUNDARY_CAPTURED'


def retained_cleanup_errors(error):
    return [('retained_cleanup', item) for item in getattr(error, 'cleanup_errors', ())]


def helper_layout(root, base, run_id):
    owned = (base / 'owned' / run_id).resolve()
    if owned.is_relative_to((root / 'studio').resolve()):
        raise RuntimeError('S129_HELPER_INSIDE_RUNTIME_SCOPE')
    return owned


def check(root=ROOT):
    support_path = root / 'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    for name, expected in HELPER_PINS.items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError('S129_HELPER_PIN_CHANGED')
    util = load(support_path, 'S129_support')
    campaign, _, _, sources = util.load_campaign(root)
    util.need(campaign.closure(sources) == CLOSURE, 'S129_SOURCE_DRIFT')
    util.need(util.sha(root / 'studio/tests/replay/benchmark_native.gd') == NATIVE_HASH, 'S129_NATIVE_DRIFT')
    lock = json.loads((root / 'studio/toolchain.lock.json').read_bytes())['godot']
    binary = root / 'studio/.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    util.need(util.sha(binary) == lock['gui_sha256'], 'S129_BINARY_DRIFT')
    util.need(util.sha(root / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py') == PSS_SHA256, 'S129_PSS_PIN')
    return util, campaign, sources, support_path


def launch():
    util, campaign, sources, support_path = check()
    run = ROOT / 'studio/.local/reviews' / RUN_ID
    owned_helpers = helper_layout(ROOT, BASE, RUN_ID)
    util.need(not run.exists() and not owned_helpers.exists(), 'S129_FRESH_ID_REQUIRED')
    run.mkdir(exist_ok=False)
    (run / 'attempt').mkdir()
    owned_helpers.mkdir(parents=True, exist_ok=False)
    execution = {'studio/' + name: digest for name, digest in sources.items()}
    for name, path in (('coupled_journal.py', Path(__file__)), ('support.py', support_path),
                       ('post_failure_handles.py', BASE.parent / '20260920-gt06-s129-helper-repair/post_failure_handles.py'),
                       ('pss_adapter.py', ROOT / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py')):
        target = owned_helpers / name
        expected = util.sha(path) if path == Path(__file__) else HELPER_PINS[path.relative_to(ROOT).as_posix()]
        shutil.copyfile(path, target)
        util.need(util.sha(target) == expected, 'S129_HELPER_COPY_CHANGED')
        execution[target.relative_to(ROOT).as_posix()] = expected
    freeze = {'schema': 'S129.post-failure.freeze.1', 'run_id': RUN_ID,
        'source_files': sources, 'source_closure': CLOSURE,
        'native_sha256': NATIVE_HASH, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'original_root': str(ROOT), 'helper_root': str(owned_helpers), 'prefix_batches': PREFIX_BATCHES,
        'outer_seconds': OUTER_SECONDS, 'python_sha256': util.sha(Path(sys.executable)),
        'execution_files': execution, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'helper_pins': HELPER_PINS,
        'scope': 'S129 diagnostic with stock native and original gates; tested request-drain candidate; PSS only after original rejection, no accepted samples'}
    util.write(run / 'freeze.json', freeze)
    campaign_doc = {'schema_id': 'hh-studio.benchmark-campaign-diagnostic', 'schema_version': '1.0.0',
        'campaign_id': RUN_ID, 'source_files': sources, 'source_closure_sha256': CLOSURE,
        'profile_sha256': campaign.profile.PROFILE_SHA256, 'formal_acceptance': False,
        'eligible_for_dataset': False, 'prefix_batches': PREFIX_BATCHES}
    util.write(run / 'campaign.json', campaign_doc)
    campaign_sha = util.sha(run / 'campaign.json')
    context = {'run_id': f'{RUN_ID}.r00.a01', 'index': 0, 'attempt': 1,
        'source_files': sources,
        'source_closure_sha256': CLOSURE, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'campaign_sha256': campaign_sha, 'formal_acceptance': False, 'eligible_for_dataset': False}
    util.write(run / 'attempt/context.json', context)
    for name in ('freeze.json', 'campaign.json', 'attempt/context.json'):
        execution[(run / name).relative_to(ROOT).as_posix()] = util.sha(run / name)
    util.write(run / 'execution-source-files.json', execution)
    def check_stop():
        util.need(not campaign.stop_requested(run / 'attempt', run_id=context['run_id'],
            source_closure_sha256=CLOSURE, campaign_sha256=campaign_sha), 'BENCHMARK_STOPPED')
    owner, capture, errors = None, None, []
    started = time.monotonic()
    try:
        check_stop()
        owner = campaign.BenchmarkProcess([sys.executable, '-B', str(owned_helpers / 'coupled_journal.py'),
            '--child', str(run)], cwd=run, output=run / 'owned', source_root=ROOT,
            source_files=execution, binary_sha256=freeze['python_sha256'], campaign_host=True)
        while True:
            check_stop()
            if owner.tick() is not None:
                check_stop()
                break
            util.need(time.monotonic() - started < OUTER_SECONDS, 'S129_OUTER_LIMIT')
            time.sleep(.1)
        capture = owner.finish()
        campaign.verify_capture(run / 'owned', util.sha(run / 'owned/capture.json'),
            source_root=ROOT, expected_source_files=execution,
            expected_binary_sha256=freeze['python_sha256'], expected_campaign_host=True)
    except BaseException as error:
        # Adopt retained ownership before any optional evidence write can fail.
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
        errors.append(('parent', error))
        try:
            trace = error.__traceback__
            while trace is not None:
                local = trace.tb_frame.f_locals
                if (trace.tb_frame.f_code.co_name == 'configure'
                        and Path(trace.tb_frame.f_code.co_filename).name == 'benchmark_job.py'
                        and all(key in local for key in ('limits', 'observed', 'size'))):
                    def fixed_fields(value):
                        return {'flags': int(value.basic.flags), 'active_limit': int(value.basic.active_limit),
                                'job_time': int(value.basic.job_time), 'job_memory': int(value.job_memory)}
                    util.write(run / 'job-configure-readback.json', {'requested': fixed_fields(local['limits']),
                        'observed': fixed_fields(local['observed']), 'returned_size': local['size'].value,
                        'formal_acceptance': False})
                trace = trace.tb_next
        except BaseException as receipt_error:
            errors.append(('job_readback_receipt', receipt_error))
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                errors.append(('owner_close', error))
        observations = {}
        for name, getter in (
            ('owner', lambda: campaign._editor_cleanup_state(owner)),
            ('target', lambda: campaign._target_exit_state(run, 'owned')),
            ('source_unchanged', lambda: campaign.source_files() == sources),
            ('execution_unchanged', lambda: all(util.sha(ROOT / p) == h for p, h in execution.items())),
        ):
            try:
                observations[name] = getter()
            except BaseException as error:
                errors.append((name, error))
                observations[name] = None
        for name in ('source_unchanged', 'execution_unchanged'):
            if observations.get(name) is not True:
                errors.append((name, RuntimeError('S129_PIN_CHANGED')))
        util.write(run / 'result.json', {'schema': 'S129.post-failure.result.1', 'run_id': RUN_ID,
            'owned_child_natural_exit0': capture is not None, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'elapsed_seconds': time.monotonic() - started,
            'ended_utc': datetime.now(timezone.utc).isoformat(),
            'observations': observations, 'errors': util.errors_record(errors)})
    return 0 if capture is not None and not errors else 1


def child(run):
    run = Path(run).resolve()
    freeze = json.loads((run / 'freeze.json').read_bytes())
    helpers = Path(freeze['helper_root'])
    util = load(helpers / 'support.py', 'S129_support')
    root = Path(freeze['original_root'])
    util.need(Path(__file__).resolve() == helpers / 'coupled_journal.py', 'S129_COPIED_CHILD_REQUIRED')
    util.need(not helpers.resolve().is_relative_to((root / 'studio').resolve()), 'S129_HELPER_INSIDE_RUNTIME_SCOPE')
    execution = json.loads((run / 'execution-source-files.json').read_bytes())
    util.need(all(util.sha(root / p) == h for p, h in execution.items()), 'S129_EXECUTION_DRIFT')
    campaign, _, _, sources = util.load_campaign(root)
    util.need(campaign.closure(sources) == CLOSURE, 'S129_SOURCE_DRIFT')
    original_screen, gates, errors = campaign.screen_sample, [], []
    observation = load(helpers / 'post_failure_handles.py', 'S129_observation')
    pss = load(helpers / 'pss_adapter.py', 'S129_pss')
    context = json.loads((run / 'attempt/context.json').read_bytes())
    retained = {}
    original_open = campaign.open_probe
    original_producer = campaign.CampaignProducer

    def open_probe(owner, executable):
        probe = original_open(owner, executable)
        retained['probe'] = probe
        return probe

    def make_producer(*args, **kwargs):
        producer = original_producer(*args, **kwargs)
        retained['producer'] = producer
        retained['host_probe'] = producer.observer.probe
        return producer

    def check_stop():
        util.need(not campaign.stop_requested(run / 'attempt', run_id=context['run_id'],
            source_closure_sha256=CLOSURE, campaign_sha256=context['campaign_sha256']), 'BENCHMARK_STOPPED')

    def binding(sample):
        index = sample['index']
        joint_path = run / 'attempt' / f'joint-{index:02d}.json'
        joint = json.loads(joint_path.read_bytes())
        observation.validate_roles(joint['processes'],
            editor=observation.probe_identity(retained['probe']),
            host=observation.probe_identity(retained['host_probe']))
        return {'run_id': context['run_id'], 'index': index,
            'editor': joint['processes']['editor'], 'host': joint['processes']['host'],
            'source_closure_sha256': CLOSURE,
            'profile_sha256': context['profile_sha256'], 'context_sha256': util.sha(run / 'attempt/context.json'),
            'joint_sha256': util.sha(joint_path),
            'sample_sha256': util.sha(run / 'attempt' / f'sample-preview-{index:02d}.json')}

    def write_observation(name, value):
        util.write(run / name, value)

    def observe_failure(probe, binding):
        check_stop()
        observation.observe(probe, binding=binding, sample_editor=campaign.sample_editor,
            capture=pss.capture_owned, write=write_observation, check_stop=check_stop)

    def observe_host_failure(probe, binding):
        check_stop()
        observation.observe_host(probe, binding=binding,
            sample_host=lambda _probe: retained['producer']._observe(),
            capture=pss.capture_owned, write=write_observation, check_stop=check_stop)

    gate_observer = observation.GateObserver(original=original_screen, boundary=Boundary,
        limit=PREFIX_BATCHES, stop_at_boundary=STOP_AT_BOUNDARY, binding=binding, probe=lambda: retained['probe'],
        observe_fn=observe_failure, host_probe=lambda: retained['host_probe'],
        observe_host_fn=observe_host_failure, write=write_observation,
        error_record=util.errors_record, check_stop=check_stop)
    gates = gate_observer.gates

    def screen(sample, baseline):
        check_stop()
        gate_observer(sample, baseline)

    disposition = 'INCOMPLETE'
    with ExitStack() as stack:
        for target, name, value in ((campaign, 'screen_sample', screen),
                                    (campaign, 'open_probe', open_probe),
                                    (campaign, 'CampaignProducer', make_producer)):
            stack.enter_context(patch.object(target, name, value))
        phase_recorder = phase_memory.PhaseMemoryRecorder(
            f'{RUN_ID}.r00.a01', PREFIX_BATCHES)
        phase_status, phase_error = 'INCOMPLETE', None
        try:
            with phase_memory.install_phase_memory_wrappers(campaign, phase_recorder):
                campaign.run_child(run / 'attempt')
            disposition, phase_status = 'COMPLETED_FULL_DIAGNOSTIC', 'COMPLETED'
        except phase_memory.BoundedPhaseStop as error:
            disposition, phase_status, phase_error = 'BOUNDARY_CAPTURED', 'BOUNDARY_STOP', error.code
        except Boundary as error:
            disposition, phase_status = 'BOUNDARY_CAPTURED', 'ORIGINAL_BOUNDARY'
            errors.extend(retained_cleanup_errors(error))
        except BaseException as error:
            disposition, phase_status, phase_error = 'ORIGINAL_FAILURE', 'ORIGINAL_GATE_FAILURE', type(error).__name__
            errors.append(('campaign', error))
            errors.extend(retained_cleanup_errors(error))
        finally:
            phase_report = phase_recorder.persist(
                run / 'phase-memory.json', status=phase_status, error_code=phase_error)
    # Original child has already persisted primary/cause, HTTP window and cleanup.
    util.write(run / 'diagnostic-summary.json', {'schema': 'S129.post-failure-diagnostic.1',
        'run_id': RUN_ID, 'pid': os.getpid(), 'disposition': disposition,
        'formal_acceptance': False, 'eligible_for_dataset': False, 'gates': gates,
        'source_unchanged': campaign.source_files() == sources,
        'errors': util.errors_record(errors),
        'phase_memory': {'file': 'phase-memory.json', 'rows': phase_report['row_count'], 'status': phase_report['status'], 'sha256': util.sha(run / 'phase-memory.json')},
        'limits': 'Diagnostic only; PSS after original rejection cannot alter the gate. No root-cause, no-leak or formal PASS claim.',
        'exit_scope': 'Natural full completion must drain original child; failure may leave editor natural exit UNKNOWN. External observer supplies launcher actual exit.'})
    return 0 if disposition == 'COMPLETED_FULL_DIAGNOSTIC' and not errors else 1


if __name__ == '__main__':
    if sys.argv[1:] == ['--check']:
        util, campaign, sources, *_ = check()
        print(json.dumps({'checked': True, 'source_count': len(sources), 'closure': campaign.closure(sources),
            'native_sha256': NATIVE_HASH, 'profile': campaign.profile.PROFILE_SHA256, 'launched': False}))
    elif sys.argv[1:] == ['--launch']:
        raise SystemExit(launch())
    elif len(sys.argv) == 3 and sys.argv[1] == '--child':
        raise SystemExit(child(sys.argv[2]))
    else:
        raise SystemExit('Use --check, --launch, or --child <run>')
