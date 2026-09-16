"""S43 coordinator evidence verification; never an independent critic."""
import hashlib, json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
PACK = ROOT / 'zdoc/reviews/20260916-gt02-s43-01'
DIAG = ROOT / 'zdoc/reviews/20260916-gt02-s43-audit'
MANIFEST_HASH = '71f3169dc1234c8b50f5a0f10001fca28e3af8e1dc2a061326688f64a766cf36'

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def confined(base, name):
    p = base.joinpath(*name.split('/'))
    p.resolve().relative_to(base.resolve())
    return p

def verify():
    assert sha(DIAG/'diagnostic-manifest.json') == MANIFEST_HASH
    dm = read(DIAG/'diagnostic-manifest.json')
    for name, digest in dm['files'].items(): assert sha(confined(ROOT, name)) == digest
    candidate, source = read(PACK/'candidate.json'), read(PACK/'source-closure.json')
    assert candidate['status'] == 'CANDIDATE' and candidate['acceptance_ready'] is False
    assert candidate['acceptance'] == 'NOT_REVIEWED' and candidate['source_unchanged'] is True
    assert candidate['source_closure_sha256'] == source['source_closure_sha256']
    assert len(source['files']) == 86 and len(candidate['artifacts']) == 9
    rows = []
    for name, digest in sorted(source['files'].items()):
        assert re.fullmatch('[0-9a-f]{64}', digest)
        assert sha(confined(STUDIO, name)) == digest
        rows.append(f'8-9-hh3d-3/studio/{name}\0{digest}\n')
    closure = hashlib.sha256(''.join(rows).encode()).hexdigest()
    assert closure == source['source_closure_sha256'] == candidate['source_closure_sha256']
    excluded = {'__pycache__','.godot','.local','evidence'}
    actual = {'toolchain.lock.json'}
    for folder in ('protocol','host/core','tests/protocol','tests/bootstrap','build/bootstrap','fixtures'):
        actual.update(p.relative_to(STUDIO).as_posix() for p in (STUDIO/folder).rglob('*')
                      if p.is_file() and not set(p.relative_to(STUDIO).parts)&excluded)
    assert actual == set(source['files'])
    for name, digest in candidate['artifacts'].items(): assert sha(confined(PACK,name)) == digest
    for lane in candidate['lanes']:
        run, summary = lane['host'], lane['summary']
        host = read(confined(PACK,run['host']))
        assert run['exit_code'] == run['wrapper_exit_code'] == host['exit_code'] == 0
        assert run['tree_verified'] is True and run['timed_out'] is False
        assert lane['passed'] is True and summary['failures'] == summary['errors'] == 0
        out = confined(PACK,run['stdout']).read_text(encoding='utf-8')
        marker = [json.loads(x.removeprefix('HH_GT02_TEST_RESULT ')) for x in out.split('\n') if x.startswith('HH_GT02_TEST_RESULT ')]
        assert marker == [summary]
    assert candidate['lanes'][0]['summary']['tests_run'] == 294
    assert candidate['lanes'][0]['summary']['skips'] == 4
    assert candidate['lanes'][1]['summary']['tests_run'] == 56
    # Focused RPC run has one real owned host exit and no errors.
    rpc = ROOT/'zdoc/reviews/20260916-gt02-s39-rpc-02'; cap=read(rpc/'capture.json'); h=cap['host']
    assert cap['source_unchanged'] is True and h['exit_code']==h['wrapper_exit_code']==0
    assert sha(rpc/'selector_pipe.py') == source['files']['host/core/selector_pipe.py']
    assert sha(rpc/'test_selector_pipe.py') == source['files']['tests/protocol/test_selector_pipe.py']
    assert h['tree_verified'] is True and h['timed_out'] is False
    line=[x for x in (rpc/h['stdout']).read_text().split('\n') if x.startswith('SELECTOR_RPC_COMPLETE ')]
    assert len(line)==1 and json.loads(line[0].removeprefix('SELECTOR_RPC_COMPLETE ')) == {'run':16,'failures':0,'errors':0,'skips':0}
    # Native probe has seven cases, each actual AppContainer child exit 61,
    # plus private-root/event access denial and clean Job/process ownership.
    native=ROOT/'zdoc/reviews/20260916-gt02-s43-native'; host=read(native/'run-01.host.json'); raw=read(native/'run-01.stdout.json')
    assert raw['runtime_closure']['source_closure_sha256'] == source['source_closure_sha256']
    assert raw['runtime_closure']['files'] == source['files']
    assert host['host_exit']==0 and host['timed_out'] is False
    assert raw['marker']=='S39_SELECTOR_IPC_DIAGNOSTIC_COMPLETE' and raw['diagnostic_complete'] is True
    assert len(raw['cases'])==7 and raw['remaining_endpoint_owners']==raw['remaining_io_owners']==raw['remaining_event_owners']==0
    for case in raw['cases']:
        assert 'error' not in case and case['host_exit']==case['final_host_exit']==61
        assert case['final_job_active']==0 and case['final_job_pids']==[]
        native_case=case['native']; assert native_case['complete']=='S39_NATIVE_COMPLETE'
        assert all(native_case[k]==5 for k in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error','private_read_error','private_write_error','events_access_error'))
    return {'schema':'hh-gt02-s43-coordinator-verification-v1','status':'COORDINATOR_LOGIC_VERIFIED',
            'source_closure_sha256':closure,'source_files':86,'candidate_artifacts':9,
            'protocol':{'run':294,'passed':290,'skipped':4},'bootstrap':{'run':56,'passed':56,'skipped':0},
            'selector_rpc':{'run':16,'passed':16},'native_cases':7,'native_exit':61,
            'private_access_denied':True,'formal_acceptance':False,'independent_critic_signatures':0,'critic_verdicts':[],
            'limits':['S43 native endpoint now exercises selector fixture only; no Godot/Blender consumer',
                      'source/game revisions and clock are trusted broker observations',
                      'safe_write/atomic_replace remain unsupported; power-loss witness custody is open',
                      'S41 critics apply to the old closure; this S43 closure has not been independently reviewed']}

if __name__ == '__main__':
    if not __debug__: raise SystemExit('OPTIMIZED_VERIFICATION_FORBIDDEN')
    result=verify(); (DIAG/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
