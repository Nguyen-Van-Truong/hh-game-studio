"""Retained no-engine tests of the frozen S131 empty-Job repair."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import time
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
from studio.tests.replay import benchmark_job as job

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(path, value):
    job.write(path, value)

def main():
    output = BASE / 'validation-01'
    output.mkdir(exist_ok=False)
    helper = ROOT / 'zdoc/reviews/20260919-gt06-s123-lookup-repair/support.py'
    spec = importlib.util.spec_from_file_location('s131_support', helper)
    util = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(util)
    campaign, _, _, sources = util.load_campaign(ROOT)
    closure = campaign.closure(sources)
    assert closure == '763191109cd7c7f63de499680291c6b99d77a501dad869078e6d77384ecb20b4'
    binary_hash = sha(sys.executable)
    rows = []
    for role in ('editor', 'host'):
        for failed in (False, True):
            lane = output / (role + ('-configure-reject' if failed else '-success'))
            lane.mkdir()
            workspace = lane / 'workspace'
            workspace.mkdir()
            kwargs = dict(cwd=workspace, output=lane/'owner', source_root=ROOT/'studio',
                          source_files=sources, binary_sha256=binary_hash, campaign_host=role=='host')
            owner = None
            record = {'role':role,'injected_configure_rejection':failed,'engine_launched':False}
            try:
                if failed:
                    with patch.object(job,'configure',side_effect=job.BenchmarkJobError('S131_INJECTED_CONFIGURE_REJECT')):
                        try:
                            job.BenchmarkProcess([sys.executable,'-B','-c',
                                'from pathlib import Path; Path("unexpected-target").touch()'],**kwargs)
                        except BaseException as error:
                            owner = error.cleanup_owner
                            record['exception_code'] = getattr(error,'code',type(error).__name__)
                            record['cause_code'] = getattr(error.__cause__,'code',None)
                            assert record['cause_code']=='S131_INJECTED_CONFIGURE_REJECT'
                        else:
                            raise AssertionError('injected failure admitted target')
                    assert owner.closed and not owner.released and owner.process.returncode is not None
                    assert not (workspace/'unexpected-target').exists()
                    assert not (lane/'owner/process-start.json').exists()
                    record['target_started']=False
                else:
                    owner=job.BenchmarkProcess([sys.executable,'-B','-c','print("HH_S131_PYTHON_TARGET_OK")'],**kwargs)
                    deadline=time.monotonic()+30
                    while owner.tick() is None:
                        assert time.monotonic()<deadline
                        time.sleep(.02)
                    capture=owner.finish()
                    job.verify_capture(lane/'owner',sha(lane/'owner/capture.json'),
                        source_root=ROOT/'studio',expected_source_files=sources,
                        expected_binary_sha256=binary_hash,expected_campaign_host=role=='host')
                    record['target_started']=True
                    record['actual_target_exit']=capture['actual_process_exit']
                    record['limits']=capture['limits']
                record.update(helper_pid=owner.process.pid,helper_exit=owner.process.returncode,
                    job=owner.job.snapshot(),process_handle=owner.process_handle_snapshot())
                assert record['job']['closed'] and record['job']['zero_observed']
                assert record['process_handle']['closed'] and not job.HELD_OWNERS
            finally:
                if owner is not None:
                    owner.close()
            save(lane/'result.json',record)
            rows.append(record)
    tests=[]
    for name,folder,pattern in [('cli-job','godot','test_cli_job.py'),
                                ('benchmark','replay','test_benchmark*.py')]:
        lane=output/name
        lane.mkdir()
        command=[sys.executable,'-B','-W','default','-m','unittest','discover',
                 '-s',str(ROOT/'studio/tests'/folder),'-p',pattern,'-v']
        before_tests={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'studio/tests'/folder).glob(pattern)}
        started=datetime.now(timezone.utc).isoformat()
        with (lane/'stdout.txt').open('xb') as out,(lane/'stderr.txt').open('xb') as err:
            process=subprocess.run(command,cwd=ROOT,stdout=out,stderr=err,timeout=600)
        stderr=(lane/'stderr.txt').read_text(encoding='utf8')
        count=re.findall(r'Ran (\d+) tests? in',stderr)
        receipt=dict(command=command,started_utc=started,ended_utc=datetime.now(timezone.utc).isoformat(),
            actual_exit=process.returncode,tests_run=int(count[-1]) if count else None,
            source_files=sources,source_closure=closure,source_unchanged=campaign.source_files()==sources,
            test_files=before_tests,test_files_unchanged=all(sha(ROOT/p)==h for p,h in before_tests.items()),
            streams={n:sha(lane/n) for n in ('stdout.txt','stderr.txt')},engine_launched=False,
            formal_acceptance=False,eligible_for_dataset=False)
        save(lane/'receipt.json',receipt)
        assert process.returncode==0 and receipt['source_unchanged'] and receipt['test_files_unchanged']
        tests.append({'lane':name,'count':receipt['tests_run'],'actual_exit':process.returncode})
    save(output/'summary.json',dict(native_python_lanes=rows,tests=tests,source_files=sources,
         source_closure=closure,runner_sha256=sha(__file__),formal_acceptance=False,engine_launched=False))
    print(json.dumps({'native_lanes':len(rows),'tests':tests,'closure':closure}))

if __name__=='__main__':
    main()
