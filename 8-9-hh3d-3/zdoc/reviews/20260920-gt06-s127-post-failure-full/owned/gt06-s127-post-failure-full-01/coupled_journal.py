"""one original-gate, stock-native lookup-boundary prefix with additive host journal timings.

No source/profile edit, seed, native overlay, additional fault or formal retry.
The existing campaign child performs every original gate; after gate 6 passes,
a diagnostic boundary exception takes its existing failure/cleanup path.
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

sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN_ID = 'gt06-s127-post-failure-full-01'
CLOSURE = '6d580e30e6d9368a5118749687589e4893fc5b88bcaf6b0af4414ce15ce91fc2'
NATIVE_HASH = '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95'
PSS_SHA256 = '797398a54cac5f7c772df7ec9c5ad988fe9e54c26c3c10e172a768e39dc25c76'
PREFIX_BATCHES = 35
STOP_AT_BOUNDARY = False
OUTER_SECONDS = 7530


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Boundary(RuntimeError):
    code = 'S126_BOUNDARY_CAPTURED'


def retained_cleanup_errors(error):
    return [('retained_cleanup', item) for item in getattr(error, 'cleanup_errors', ())]


def helper_layout(root, base, run_id):
    owned = (base / 'owned' / run_id).resolve()
    if owned.is_relative_to((root / 'studio').resolve()):
        raise RuntimeError('S126_HELPER_INSIDE_RUNTIME_SCOPE')
    return owned


def boundary_screen(original, sample, baseline, gate_rows):
    """Never swallow an original gate rejection, or count it as passed."""
    original(sample, baseline)
    gate_rows.append({'index': len(gate_rows), 'original_gate': 'PASSED'})
    if len(gate_rows) == PREFIX_BATCHES and STOP_AT_BOUNDARY:
        raise Boundary('S126_PREFIX_BOUNDARY')


def measured_execute(original, timings, owner, sql, args=(), *, fetch=False):
    """Time only fixed transaction controls; never retain SQL, args or results."""
    label = {'BEGIN IMMEDIATE': 'sqlite_begin', 'COMMIT': 'sqlite_commit',
             'ROLLBACK': 'sqlite_rollback'}.get(sql)
    if label is None:
        return original(owner, sql, args, fetch=fetch)
    return timings.call(label, original, owner, sql, args, fetch=fetch)


def check(root=ROOT):
    support_path = root / 'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    timing_path = root / 'zdoc/reviews/20260919-gt06-s114-history-replay/history_replay.py'
    util = load(support_path, 'S126_support')
    campaign, _, _, sources = util.load_campaign(root)
    util.need(campaign.closure(sources) == CLOSURE, 'S126_SOURCE_DRIFT')
    util.need(util.sha(root / 'studio/tests/replay/benchmark_native.gd') == NATIVE_HASH, 'S126_NATIVE_DRIFT')
    lock = json.loads((root / 'studio/toolchain.lock.json').read_bytes())['godot']
    binary = root / 'studio/.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    util.need(util.sha(binary) == lock['gui_sha256'], 'S126_BINARY_DRIFT')
    util.need(util.sha(root / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py') == PSS_SHA256, 'S126_PSS_PIN')
    return util, campaign, sources, support_path, timing_path


def launch():
    util, campaign, sources, support_path, timing_path = check()
    run = ROOT / 'studio/.local/reviews' / RUN_ID
    owned_helpers = helper_layout(ROOT, BASE, RUN_ID)
    util.need(not run.exists() and not owned_helpers.exists(), 'S126_FRESH_ID_REQUIRED')
    run.mkdir(exist_ok=False)
    (run / 'attempt').mkdir()
    owned_helpers.mkdir(parents=True, exist_ok=False)
    execution = {'studio/' + name: digest for name, digest in sources.items()}
    for name, path in (('coupled_journal.py', Path(__file__)), ('support.py', support_path),
                       ('timings.py', timing_path), ('post_failure_handles.py', BASE / 'post_failure_handles.py'),
                       ('pss_adapter.py', ROOT / 'zdoc/reviews/20260919-gt06-s105-handles/pss_adapter.py')):
        target = owned_helpers / name
        shutil.copyfile(path, target)
        execution[target.relative_to(ROOT).as_posix()] = util.sha(target)
    freeze = {'schema': 'S126.coupled-journal.freeze.1', 'run_id': RUN_ID,
        'source_files': sources, 'source_closure': CLOSURE,
        'native_sha256': NATIVE_HASH, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'original_root': str(ROOT), 'helper_root': str(owned_helpers), 'prefix_batches': PREFIX_BATCHES,
        'outer_seconds': OUTER_SECONDS, 'python_sha256': util.sha(Path(sys.executable)),
        'execution_files': execution, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'S126 full stock campaign, unmodified native/host workload; capture handles/PSS only after the original retained-counter gate and preserve the primary failure'}
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
            util.need(time.monotonic() - started < OUTER_SECONDS, 'S126_OUTER_LIMIT')
            time.sleep(.1)
        capture = owner.finish()
        campaign.verify_capture(run / 'owned', util.sha(run / 'owned/capture.json'),
            source_root=ROOT, expected_source_files=execution,
            expected_binary_sha256=freeze['python_sha256'], expected_campaign_host=True)
    except BaseException as error:
        errors.append(('parent', error))
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
        if owner is None:
            owner = getattr(error, 'cleanup_owner', None)
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
                errors.append((name, RuntimeError('S126_PIN_CHANGED')))
        util.write(run / 'result.json', {'schema': 'S126.coupled-journal.result.1', 'run_id': RUN_ID,
            'owned_child_natural_exit0': capture is not None, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'elapsed_seconds': time.monotonic() - started,
            'ended_utc': datetime.now(timezone.utc).isoformat(),
            'observations': observations, 'errors': util.errors_record(errors)})
    return 0 if capture is not None and not errors else 1


def child(run):
    run = Path(run).resolve()
    freeze = json.loads((run / 'freeze.json').read_bytes())
    helpers = Path(freeze['helper_root'])
    util = load(helpers / 'support.py', 'S126_support')
    timing_module = load(helpers / 'timings.py', 'S126_timings')
    root = Path(freeze['original_root'])
    util.need(Path(__file__).resolve() == helpers / 'coupled_journal.py', 'S126_COPIED_CHILD_REQUIRED')
    util.need(not helpers.resolve().is_relative_to((root / 'studio').resolve()), 'S126_HELPER_INSIDE_RUNTIME_SCOPE')
    execution = json.loads((run / 'execution-source-files.json').read_bytes())
    util.need(all(util.sha(root / p) == h for p, h in execution.items()), 'S126_EXECUTION_DRIFT')
    campaign, _, _, sources = util.load_campaign(root)
    util.need(campaign.closure(sources) == CLOSURE, 'S126_SOURCE_DRIFT')
    from studio.tests.replay import benchmark_commands as commands
    from studio.host.replay.disk_journal_index import DiskJournalIndex
    timings = timing_module.Timings()
    original_journal, original_fsync = commands.Journal, os.fsync
    original_execute = DiskJournalIndex._execute
    original_screen, gates, errors = campaign.screen_sample, [], []
    observation = load(helpers / 'post_failure_handles.py', 'S126_observation')
    pss = load(helpers / 'pss_adapter.py', 'S126_pss')
    context = json.loads((run / 'attempt/context.json').read_bytes())
    retained = {}
    original_open = campaign.open_probe

    def open_probe(owner, executable):
        probe = original_open(owner, executable)
        retained['probe'] = probe
        return probe

    def check_stop():
        util.need(not campaign.stop_requested(run / 'attempt', run_id=context['run_id'],
            source_closure_sha256=CLOSURE, campaign_sha256=context['campaign_sha256']), 'BENCHMARK_STOPPED')

    def binding(sample):
        index = sample['index']
        joint_path = run / 'attempt' / f'joint-{index:02d}.json'
        joint = json.loads(joint_path.read_bytes())
        probe = retained['probe']
        util.need(joint['processes']['editor'] == {'pid': probe.pid, 'process_start': probe.process_start}, 'S126_RETAINED_IDENTITY')
        return {'run_id': context['run_id'], 'index': index,
            'editor': joint['processes']['editor'], 'source_closure_sha256': CLOSURE,
            'profile_sha256': context['profile_sha256'], 'context_sha256': util.sha(run / 'attempt/context.json'),
            'joint_sha256': util.sha(joint_path),
            'sample_sha256': util.sha(run / 'attempt' / f'sample-preview-{index:02d}.json')}

    def write_observation(name, value):
        util.write(run / name, value)

    def observe_failure(probe, binding):
        check_stop()
        observation.observe(probe, binding=binding, sample_editor=campaign.sample_editor,
            capture=pss.capture_owned, write=write_observation, check_stop=check_stop)

    gate_observer = observation.GateObserver(original=original_screen, boundary=Boundary,
        limit=PREFIX_BATCHES, binding=binding, probe=lambda: retained['probe'],
        observe_fn=observe_failure, write=write_observation, error_record=util.errors_record)
    gates = gate_observer.gates

    class MeasuredJournal(original_journal):
        def _snapshot(self, *, synchronize):
            return timings.call('snapshot_' + str(synchronize).lower(),
                super()._snapshot, synchronize=synchronize)

        def _load(self):
            return timings.call('load', super()._load)

        def _reload(self):
            return timings.call('reload', super()._reload)

        def _append(self, *args, **kwargs):
            return timings.call('append', super()._append, *args, **kwargs)

    def fsync(fd):
        scope = getattr(timings.local, 'scope', 'none')
        if scope == 'none':
            return original_fsync(fd)
        return timings.call('fsync_' + scope, original_fsync, fd)

    def screen(sample, baseline):
        check_stop()
        gate_observer(sample, baseline)

    def execute(owner, sql, args=(), *, fetch=False):
        return measured_execute(original_execute, timings, owner, sql, args, fetch=fetch)

    disposition = 'INCOMPLETE'
    timings.phase = 'coupled'
    with ExitStack() as stack:
        for target, name, value in ((campaign, 'screen_sample', screen),
                                    (campaign, 'open_probe', open_probe)):
            stack.enter_context(patch.object(target, name, value))
        try:
            campaign.run_child(run / 'attempt')
            disposition = 'COMPLETED_FULL_DIAGNOSTIC'
        except Boundary as error:
            disposition = 'BOUNDARY_CAPTURED'
            errors.extend(retained_cleanup_errors(error))
        except BaseException as error:
            disposition = 'ORIGINAL_FAILURE'
            errors.append(('campaign', error))
            errors.extend(retained_cleanup_errors(error))
    # Original child has already persisted primary/cause, HTTP window and cleanup.
    util.write(run / 'timing-summary.json', {'schema': 'S126.coupled-journal.timings.1',
        'run_id': RUN_ID, 'pid': os.getpid(), 'disposition': disposition,
        'formal_acceptance': False, 'eligible_for_dataset': False, 'gates': gates,
        'source_unchanged': campaign.source_files() == sources,
        'errors': util.errors_record(errors), 'timings': timings.rows,
        'limits': 'Nested wall/CPU spans overlap; fixed SQLite transaction controls timed separately; Python fsync excludes SQLite internal sync. No I/O/rootcause/no-leak claim.',
        'exit_scope': 'Outer child may exit0 for captured planned boundary; editor natural exit can be UNKNOWN after owned boundary cleanup.'})
    return 0 if disposition in ('BOUNDARY_CAPTURED', 'COMPLETED_FULL_DIAGNOSTIC') and not errors else 1


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


