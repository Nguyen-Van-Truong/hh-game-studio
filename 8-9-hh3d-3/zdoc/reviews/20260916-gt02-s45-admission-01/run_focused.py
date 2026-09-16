"""Bounded owned focused regression run, with disposable exact-source snapshot."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
STUDIO = PRODUCT/'studio'
spec = importlib.util.spec_from_file_location('s45_candidate_helpers', STUDIO/'tests/protocol/run_gt02_candidate.py')
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', default='attempt-01', choices=('attempt-01','attempt-02','attempt-03'))
    args = parser.parse_args()
    output = HERE/args.attempt
    output.mkdir(exist_ok=False)
    before = helpers.source_manifest()
    closure = helpers.RUNNER.source_closure_sha256(before)
    (output/'source-closure.json').write_text(json.dumps({'schema':'hh-gt02-source-closure-v1',
        'source_closure_sha256':closure,'files':before},indent=2)+'\n',encoding='utf-8')
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix='hh-s45-admission-frozen-') as temporary:
        snapshot = Path(temporary)
        for name, expected in before.items():
            destination = snapshot/'studio'/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(STUDIO/name,destination)
            assert helpers.sha(destination)==expected
        code = '\n'.join([
            'import json,sys,unittest',
            "sys.path.insert(0,'studio/tests/protocol')",
            "modules=['test_safe_replace','test_file_consumer','test_fixture_selector','test_selector_pipe']",
            'suite=unittest.defaultTestLoader.loadTestsFromNames(modules)',
            'def flatten(item):',
            ' return [item.id()] if isinstance(item,unittest.TestCase) else [key for child in item for key in flatten(child)]',
            'ids=flatten(suite)',
            'r=unittest.TextTestRunner(verbosity=2).run(suite)',
            "print('HH_S45_ADMISSION_RESULT '+json.dumps({'tests_run':r.testsRun,'test_ids':ids,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True)",
            'sys.exit(0 if r.wasSuccessful() else 1)',
        ])
        env=dict(os.environ)
        env['PYTHONDONTWRITEBYTECODE']='1'
        env['PYTHONPATH']=str(snapshot)
        run=helpers.RUNNER.run_process([sys.executable,'-B','-c',code],cwd=snapshot,output=output,
            timeout=90,label='focused',env=env)
        snapshot_unchanged=helpers.source_manifest(snapshot/'studio')==before
    after=helpers.source_manifest()
    stdout=(output/run['stdout']).read_text(encoding='utf-8')
    markers=[line[len('HH_S45_ADMISSION_RESULT '):] for line in stdout.splitlines() if line.startswith('HH_S45_ADMISSION_RESULT ')]
    summary=json.loads(markers[0]) if len(markers)==1 else None
    host=json.loads((output/run['host']).read_text()) if (output/run['host']).exists() else {}
    passed=(run['exit_code']==run['wrapper_exit_code']==host.get('exit_code')==0
        and run['tree_verified'] and not run['timed_out'] and summary is not None
        and summary['failures']==summary['errors']==summary['skips']==0
        and len(set(summary['test_ids']))==summary['tests_run']
        and before==after and snapshot_unchanged)
    redactor=helpers.Redactor(host_paths=[str(PRODUCT),str(Path.home()),tempfile.gettempdir()])
    for name in (run['stdout'],run['stderr']):
        path=output/name
        path.write_text('\n'.join(redactor.text(line) for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    record={'schema':'hh-s45-admission-focused-v1','run_id':'GT02-S45-ADMISSION-01-'+args.attempt,
        'command_id':'cmd.gt02-s45-admission-01.'+args.attempt,'seed':8785,'started_utc':started,
        'completed_utc':datetime.now(timezone.utc).isoformat(),'source_closure_sha256':closure,
        'source_unchanged':before==after,'snapshot_unchanged':snapshot_unchanged,
        'host':run,'summary':summary,'passed':passed,'acceptance':'IMPLEMENTER_ONLY_NOT_REVIEWED'}
    record['artifacts']={path.name:helpers.sha(path) for path in sorted(output.iterdir()) if path.is_file()}
    (output/'capture.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in record.items() if key not in ('artifacts','summary')},sort_keys=True))
    print(json.dumps({key:value for key,value in (summary or {}).items() if key!='test_ids'},sort_keys=True))
    return 0 if passed else 1


if __name__=='__main__':
    raise SystemExit(main())
