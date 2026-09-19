"""One fresh import-only diagnostic. Original limits; only --verbose differs."""
from pathlib import Path
from datetime import datetime, timezone
import importlib.util
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN_ID = 'gt06-s118-import-01'
CLOSURE = '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467'


def check():
    path = ROOT / 'zdoc/reviews/20260919-gt06-s102-observability/preflight.py'
    spec = importlib.util.spec_from_file_location('s118_support', path)
    util = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(util)
    campaign, factory, trusted, sources = util.load_campaign(ROOT)
    util.need(campaign.closure(sources) == CLOSURE, 'S118_SOURCE_DRIFT')
    return util, campaign, factory, trusted, sources, path


def launch():
    util, campaign, factory, trusted, sources, support = check()
    run = ROOT / 'studio/.local/reviews' / RUN_ID
    run.mkdir(exist_ok=False)
    lock = json.loads((ROOT/'studio/toolchain.lock.json').read_bytes())['godot']
    binary = ROOT/'studio/.local/tooling/godot-4.7.2-stable'/lock['gui_executable']
    util.need(util.sha(binary) == lock['gui_sha256'], 'S118_BINARY_DRIFT')
    project = run/'project'
    binding = {'schema_id':'hh-studio.native-cycle-benchmark-run','schema_version':'1.2.0',
        'run_id':RUN_ID,'mode':'full','source_closure_sha256':CLOSURE,
        'profile_sha256':campaign.profile.PROFILE_SHA256,
        'batch_barrier':'host_ack_v1','batch_start':'host_permit_v1'}
    initial = campaign.prepare(project, factory, trusted, binding)
    (project/'benchmark/input').mkdir()
    execution = {'studio/'+k:v for k,v in sources.items()}
    for path in (Path(__file__), support):
        execution[path.relative_to(ROOT).as_posix()] = util.sha(path)
    for name, digest in initial.items():
        execution[(project/name).relative_to(ROOT).as_posix()] = digest
    argv = [str(binary),'--headless','--editor','--path',str(project),'--import','--verbose']
    util.write(run/'freeze.json', {'run_id':RUN_ID,'source_files':sources,
        'source_closure':CLOSURE,'profile_sha256':campaign.profile.PROFILE_SHA256,
        'execution':execution,'initial_project_files':initial,'argv':argv,
        'formal_acceptance':False,'eligible_for_dataset':False,
        'scope':'Import only; --verbose additive log overhead, not a stock timing comparison',
        'started_utc':datetime.now(timezone.utc).isoformat()})
    observer = campaign.ImportObserver(run/'import-host', project, binary)
    errors, capture, observation = [], None, None
    try:
        observer.start()
        capture = campaign.native_job.run_trusted_stage(argv, cwd=project,
            output=run/'import-host', source_root=ROOT, source_files=execution,
            binary_sha256=lock['gui_sha256'])
        campaign.native_job.verify_captured_stage(run/'import-host', util.sha(run/'import-host/capture.json'))
    except BaseException as error:
        errors.append(('import',error))
    finally:
        try:
            observer.close()
            observation=observer.snapshot()
            util.write(run/'import-observation.json',observation)
            campaign.validate_import_snapshot(observation)
        except BaseException as error:
            errors.append(('observer',error))
        unchanged=campaign.source_files()==sources
        execution_unchanged=all(util.sha(ROOT/name)==digest for name,digest in execution.items())
        util.write(run/'result.json',{'run_id':RUN_ID,'formal_acceptance':False,
            'eligible_for_dataset':False,'completed_import':capture is not None and not errors,
            'errors':util.errors_record(errors),'source_unchanged':unchanged,
            'execution_unchanged':execution_unchanged,
            'actual_target':campaign._target_exit_state(run,'import-host'),
            'observer_cleanup':campaign._import_cleanup_state(observer),
            'ended_utc':datetime.now(timezone.utc).isoformat(),
            'import_wrapper_native_close':'UNKNOWN_UNRECORDED_BY_NATIVE_STAGE',
            'limits':'No coupled batches, status-gap repair, no-leak or acceptance claim.'})
    return int(capture is None or bool(errors) or not unchanged or not execution_unchanged)


if __name__=='__main__':
    if sys.argv[1:]==['--check']:
        _,campaign,_,_,sources,_=check()
        print(json.dumps({'checked':True,'source_count':len(sources),'closure':campaign.closure(sources),'launched':False}))
    elif sys.argv[1:]==['--launch']:
        raise SystemExit(launch())
    else:
        raise SystemExit('Use --check or --launch')
