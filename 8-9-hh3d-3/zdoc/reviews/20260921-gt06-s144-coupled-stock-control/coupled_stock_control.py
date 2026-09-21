"""Bounded candidate check: seven original-gate batches; no native overlay or timing instrumentation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import ast
import subprocess
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
RUN_ID = 'gt06-s144-coupled-stock-control-01'
CLOSURE = '4bd7972b803a877777166ece82d85b6f841755d82bcec42ed78c28ae78c78a01'
NATIVE_HASH = '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95'
PREFIX_BATCHES = 7
OUTER_SECONDS = 1230


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Boundary(RuntimeError):
    code = 'S144_BOUNDARY_CAPTURED'


def retained_cleanup_errors(error):
    return [('retained_cleanup', item) for item in getattr(error, 'cleanup_errors', ())]


def helper_layout(root, base, run_id):
    owned = (base / 'owned' / run_id).resolve()
    if owned.is_relative_to((root / 'studio').resolve()):
        raise RuntimeError('S144_HELPER_INSIDE_RUNTIME_SCOPE')
    return owned


def boundary_screen(original, sample, baseline, gate_rows):
    """Never swallow an original gate rejection, or count it as passed."""
    original(sample, baseline)
    gate_rows.append({'index': len(gate_rows), 'original_gate': 'PASSED'})
    if len(gate_rows) == PREFIX_BATCHES:
        raise Boundary('S144_BOUNDARY_CAPTURED')


def check(root=ROOT):
    support_path = root / 'zdoc/reviews/20260919-gt06-s102-observability/preflight.py'
    util = load(support_path, 'S144_support')
    campaign, _, _, sources = util.load_campaign(root)
    util.need(campaign.closure(sources) == CLOSURE, 'S144_SOURCE_DRIFT')
    util.need(util.sha(root / 'studio/tests/replay/benchmark_native.gd') == NATIVE_HASH, 'S144_NATIVE_DRIFT')
    lock = json.loads((root / 'studio/toolchain.lock.json').read_bytes())['godot']
    binary = root / 'studio/.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    util.need(util.sha(binary) == lock['gui_sha256'], 'S144_BINARY_DRIFT')
    return util, campaign, sources, support_path


def launch():
    util, campaign, sources, support_path = check()
    run = ROOT / 'studio/.local/reviews' / RUN_ID
    owned_helpers = helper_layout(ROOT, BASE, RUN_ID)
    util.need(not run.exists() and not owned_helpers.exists(), 'S144_FRESH_ID_REQUIRED')
    run.mkdir(exist_ok=False)
    (run / 'attempt').mkdir()
    owned_helpers.mkdir(parents=True, exist_ok=False)
    execution = {'studio/' + name: digest for name, digest in sources.items()}
    for name, path in (('coupled_journal.py', Path(__file__)), ('support.py', support_path)):
        target = owned_helpers / name
        shutil.copyfile(path, target)
        execution[target.relative_to(ROOT).as_posix()] = util.sha(target)
    freeze = {'schema': 'S144.coupled-journal.freeze.1', 'run_id': RUN_ID,
        'source_files': sources, 'source_closure': CLOSURE,
        'native_sha256': NATIVE_HASH, 'profile_sha256': campaign.profile.PROFILE_SHA256,
        'original_root': str(ROOT), 'helper_root': str(owned_helpers), 'prefix_batches': PREFIX_BATCHES,
        'outer_seconds': OUTER_SECONDS, 'python_sha256': util.sha(Path(sys.executable)),
        'execution_files': execution, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Coupled stock control: dynamic original _snapshot method; diagnostic only'}
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
    owner, capture, errors = None, None, []
    started = time.monotonic()
    try:
        owner = campaign.BenchmarkProcess([sys.executable, '-B', str(owned_helpers / 'coupled_journal.py'),
            '--child', str(run)], cwd=run, output=run / 'owned', source_root=ROOT,
            source_files=execution, binary_sha256=freeze['python_sha256'], campaign_host=True)
        while owner.tick() is None:
            util.need(time.monotonic() - started < OUTER_SECONDS, 'S144_OUTER_LIMIT')
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
                errors.append((name, RuntimeError('S144_PIN_CHANGED')))
        util.write(run / 'result.json', {'schema': 'S144.coupled-journal.result.1', 'run_id': RUN_ID,
            'owned_child_natural_exit0': capture is not None, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'elapsed_seconds': time.monotonic() - started,
            'ended_utc': datetime.now(timezone.utc).isoformat(),
            'observations': observations, 'errors': util.errors_record(errors)})
    return 0 if capture is not None and not errors else 1


def child(run):
    run = Path(run).resolve()
    freeze = json.loads((run / 'freeze.json').read_bytes())
    helpers = Path(freeze['helper_root'])
    util = load(helpers / 'support.py', 'S144_support')
    root = Path(freeze['original_root'])
    util.need(Path(__file__).resolve() == helpers / 'coupled_journal.py', 'S144_COPIED_CHILD_REQUIRED')
    util.need(not helpers.resolve().is_relative_to((root / 'studio').resolve()), 'S144_HELPER_INSIDE_RUNTIME_SCOPE')
    execution = json.loads((run / 'execution-source-files.json').read_bytes())
    util.need(all(util.sha(root / p) == h for p, h in execution.items()), 'S144_EXECUTION_DRIFT')
    campaign, _, _, sources = util.load_campaign(root)
    # S144 control: restore the pre-candidate snapshot method only in this child.
    # Additive diagnostic overlay; source/profile/native hashes remain pinned.
    old = subprocess.check_output(['git','show','ceb83e4c:8-9-hh3d-3/studio/host/replay/verified_journal.py'], cwd=root.parent, text=True)
    tree = ast.parse(old)
    cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == 'VerifiedJournal')
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == '_snapshot')
    mod = ast.Module(body=[fn], type_ignores=[]); ast.fix_missing_locations(mod)
    ns = {'hashlib': hashlib, 'os': os, 'stat': __import__('stat'),
          'JournalError': __import__('studio.host.core.journal', fromlist=['JournalError']).JournalError}
    exec(compile(mod, '<stock_snapshot>', 'exec'), ns)
    import studio.host.replay.verified_journal as _vj
    _vj.VerifiedJournal._snapshot = ns['_snapshot']
    util.need(campaign.closure(sources) == CLOSURE, 'S144_SOURCE_DRIFT')
    original_screen, gates, errors = campaign.screen_sample, [], []

    def screen(sample, baseline):
        boundary_screen(original_screen, sample, baseline, gates)

    disposition = 'INCOMPLETE'
    with patch.object(campaign, 'screen_sample', screen):
        try:
            campaign.run_child(run / 'attempt')
            errors.append(('unexpected_full_run', RuntimeError('S144_BOUNDARY_NOT_REACHED')))
        except Boundary as error:
            disposition = 'BOUNDARY_CAPTURED'
            errors.extend(retained_cleanup_errors(error))
        except BaseException as error:
            disposition = 'ORIGINAL_FAILURE'
            errors.append(('campaign', error))
            errors.extend(retained_cleanup_errors(error))
    # Original child has already persisted primary/cause, HTTP window and cleanup.
    util.write(run / 'diagnostic-summary.json', {'schema': 'S144.coupled-candidate.summary.1',
        'run_id': RUN_ID, 'pid': os.getpid(), 'disposition': disposition,
        'formal_acceptance': False, 'eligible_for_dataset': False, 'gates': gates,
        'source_unchanged': campaign.source_files() == sources,
        'errors': util.errors_record(errors),
        'limits': 'Bounded diagnostic, no native overlay/timing instrumentation. No formal PASS/rootcause/no-leak claim.',
        'exit_scope': 'Outer child may exit0 for captured planned boundary; editor natural exit can be UNKNOWN after owned boundary cleanup.'})
    return 0 if disposition == 'BOUNDARY_CAPTURED' and not errors else 1


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
