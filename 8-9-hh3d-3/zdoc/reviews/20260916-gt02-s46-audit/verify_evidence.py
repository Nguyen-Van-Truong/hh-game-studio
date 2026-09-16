"""S46 evidence integrity and outcomes; never an independent acceptance vote."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT/'studio'
AUDIT = Path(__file__).resolve().parent
PACK = ROOT/'zdoc/reviews/20260916-gt02-s46-01'
MANAGED = ROOT/'zdoc/reviews/20260916-gt02-s46-native/run-01'
BOUNDARY = ROOT/'zdoc/reviews/20260916-gt02-s46-boundary/run-01'
REGISTRY = ROOT/'zdoc/reviews/20260916-gt02-s46-registry-native/run-01'
CLOSURE = 'f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def confined(base, relative):
    path = base.joinpath(*relative.replace(chr(92),'/').split('/'))
    path.resolve().relative_to(base.resolve())
    return path


def host_ok(folder, run):
    actual = read(confined(folder, run['host']))
    assert actual['exit_code'] == run['exit_code'] == run['wrapper_exit_code'] == 0
    assert actual['target_pid'] == run['target_pid']
    assert run['tree_verified'] is True and run['timed_out'] is False


def native_common(folder, name, source):
    capture = read(folder/'capture.json')
    host_ok(folder,capture['host'])
    native = read(folder/(name+'-stdout.txt'))
    assert native['runtime_closure']['source_closure_sha256'] == CLOSURE
    assert native['runtime_closure']['files'] == source['files']
    assert (folder/(name+'-stderr.txt')).read_bytes() == b''
    assert native['acceptance'] is False
    assert native['delete_profile_hresult'] == 0
    assert native['profile_absent_after'] is True and native['owned_temp_removed'] is True
    for path,digest in native['diagnostic_sources'].items():
        if folder == BOUNDARY:
            assert path in {'replace_probe.py','boundary_child.c','compile_native.py','boundary_probe.py','windows_api.py'}
            base=folder.parent if path in {'replace_probe.py','boundary_child.c','compile_native.py'} else ROOT/'zdoc/reviews/20260915-gt02-s32-boundary'
        else:
            base=ROOT/'zdoc/reviews'
        assert sha(confined(base,path)) == digest, path
    for lane in ('compile','link'):
        result=native['compiler'][lane]
        assert result['host_exit'] == result['wait_result'] == result['job_active'] == 0
        assert result['helper_cleanup'] == 'owned_build_job_after_root_exit'
        assert result['stderr'] == ''
    return native


def verify():
    for name,digest in read(AUDIT/'diagnostic-manifest.json')['files'].items():
        assert sha(confined(ROOT,name)) == digest, name
    source, candidate = read(PACK/'source-closure.json'), read(PACK/'candidate.json')
    assert candidate['status'] == 'CANDIDATE' and candidate['acceptance_ready'] is False
    assert candidate['source_unchanged'] is True and candidate['acceptance'] == 'NOT_REVIEWED'
    assert candidate['source_closure_sha256'] == source['source_closure_sha256'] == CLOSURE
    assert len(source['files']) == 106 and len(candidate['artifacts']) == 9
    rows=[]
    for relative,digest in sorted(source['files'].items()):
        assert re.fullmatch('[0-9a-f]{64}',digest)
        assert sha(confined(STUDIO,relative)) == digest, relative
        rows.append(f'8-9-hh3d-3/studio/{relative}\0{digest}\n')
    assert hashlib.sha256(''.join(rows).encode()).hexdigest() == CLOSURE
    excluded={'__pycache__','.godot','.local','evidence'}
    actual={'toolchain.lock.json'}
    for folder in ('protocol','host/core','tests/protocol','tests/bootstrap','build/bootstrap','fixtures'):
        actual.update(p.relative_to(STUDIO).as_posix() for p in (STUDIO/folder).rglob('*')
                      if p.is_file() and not set(p.relative_to(STUDIO).parts)&excluded)
    assert actual == set(source['files'])
    for name,digest in candidate['artifacts'].items():
        assert sha(confined(PACK,name)) == digest, name
    for lane in candidate['lanes']:
        host_ok(PACK,lane['host'])
        summary=lane['summary']
        assert lane['passed'] is True and summary['errors'] == summary['failures'] == 0
        assert len(summary['test_ids']) == len(set(summary['test_ids'])) == summary['tests_run']
        out=confined(PACK,lane['host']['stdout']).read_text(encoding='utf-8')
        markers=[json.loads(line.removeprefix('HH_GT02_TEST_RESULT ')) for line in out.split('\n')
                 if line.startswith('HH_GT02_TEST_RESULT ')]
        assert markers == [summary]
    assert [(lane['suite'],lane['summary']['tests_run'],lane['summary']['skips']) for lane in candidate['lanes']] == [
        ('protocol',417,4),('bootstrap',56,0)]

    spec=importlib.util.spec_from_file_location('s46_golden',STUDIO/'tests/protocol/test_golden_vectors.py')
    golden=importlib.util.module_from_spec(spec); spec.loader.exec_module(golden)
    golden.GoldenVectorTests.setUpClass(); expected=golden.GoldenVectorTests.expected
    assert len(expected)==2396
    records=[read(path) for path in sorted((PACK/'golden').glob('*.json'))]
    assert len(records)==2
    for record in records:
        assert record['host_exit']==0 and record['stderr']==''
        assert record['test_source_sha256']==source['files']['tests/protocol/test_golden_vectors.py']
        if 'rows' in record:
            assert record['rows']==expected
        else:
            parsed=[json.loads(line.removeprefix('HH_GT02_JCS ')) for line in record['stdout'].split('\n')
                    if line.startswith('HH_GT02_JCS ')]
            assert len(parsed)==1 and parsed[0]['rows']==expected
            assert record['leftover_before']==record['leftover_after']==[]
            assert record['source_unchanged'] is True

    boundary=native_common(BOUNDARY,'native',source)
    registry=native_common(REGISTRY,'registry-native',source)
    for native, exit_code in ((boundary,67),(registry,89)):
        assert native['host_exit']==native['final_host_exit']==exit_code
        assert native['final_job_active']==0 and native['final_job_pids']==[]
        assert native['token_is_appcontainer']==1 and native['token_package_matches'] is True
        assert native['integrity_sid']=='S-1-16-4096' and native['capabilities']==0
        for key in ('snapshot_used','source_unchanged','snapshot_unchanged','snapshot_removed','complete'):
            assert native[key] is True,key
        assert native['safe_write'] is False
    assert boundary['marker']=='S44_REPLACE_BOUNDARY_COMPLETE'
    assert boundary['outside_alias_absent'] is True
    assert len(boundary['replacements'])==20
    for change in boundary['replacements']:
        assert change['old_id'] != change['new_id'] and re.fullmatch('[0-9a-f]{64}',change['sha256'])
    attack=boundary['native']
    assert attack['complete']=='S44_NATIVE_COMPLETE' and attack['scratch_control'] is True
    assert attack['attempts']==306==attack['loops']*9
    assert attack['allowed']==attack['unexpected_errors']==0
    assert registry['marker']=='S45_REGISTRY_BOUNDARY_VERIFIED'
    for key in ('file_writer_guard_held','protected_state_verified','positive_control_read_write_verified'):
        assert registry[key] is True,key
    attack=registry['native']
    assert attack['complete']=='S45_REGISTRY_BOUNDARY_COMPLETE'
    assert attack['denied']==attack['attempts']==36==attack['loops']*9
    assert attack['allowed']==attack['unexpected']==0 and attack['control_read_write'] is True
    assert len(registry['custody_updates'])==len(set(registry['custody_updates']))==12
    assert registry['owned_registry_leaves_removed']==2

    managed=native_common(MANAGED,'managed-native',source)
    assert managed['marker']=='S46_MANAGED_SERVICE_NATIVE_COMPLETE'
    for key in ('runtime_snapshot_used','reopen_used_storage_id_only','native_create_replace_and_retry_verified',
                'work_disconnect_control_stop_verified','runtime_source_unchanged','runtime_snapshot_unchanged',
                'runtime_snapshot_removed','diagnostic_complete'):
        assert managed[key] is True,key
    assert managed['general_safe_write'] is False
    assert managed['owned_registry_leaves_removed']==3
    assert managed['remaining_endpoint_owners']==managed['remaining_io_owners']==managed['remaining_event_owners']==0
    for module in managed['loaded_runtime_modules'].values():
        assert module['sha256']==source['files'][module['relative']]
    cases=managed['cases']
    assert [case['mode'] for case in cases]==['create','replace_stop','drop_reply']
    for case in cases:
        assert case['host_exit']==case['final_host_exit']==86
        assert case['final_job_active']==0 and case['final_job_pids']==[]
        assert case['inherit_handles'] is False and case['credentials_in_environment'] is False
        assert case['launcher_calls_dispatch_or_advance'] is False
        assert case['credential_artifact_scan_passed'] is True
        assert case['protected_custody_binding_and_names_unchanged_before_bootstrap'] is True
        assert case['registry_positive_control_host_readback'] is True
        assert case['retained_process_binding']['work']==case['retained_process_binding']['control']
        assert case['retained_process_binding']['work'][0]==case['pid']
        assert case['service_closed']['closed'] is True and case['service_closed']['live_threads']==0
        child=case['native']
        assert child['complete']=='S46_NATIVE_COMPLETE'
        assert child['registry_positive_control_read_write'] is True and child['bootstrap_received_not_logged'] is True
        for right in ('pipe_write_dac_error','pipe_write_owner_error','second_instance_error',
                      'private_read_error','private_write_error','events_access_error','registry_read_write_error'):
            assert child[right]==5,right
        for name,value in case['decoded_replies'].items():
            assert json.loads(bytes.fromhex(child[name+'_hex']))==value
        assert case['custody_epoch']==case['event_high_water']
    for generation,case in enumerate(cases[:2],1):
        reply=case['decoded_replies']
        assert reply['submit']['status']=='ACCEPTED_PENDING'
        assert reply['lookup']['status']=='COMMITTED' and reply['retry']==reply['lookup']
        assert case['snapshot']['generation']==generation and case['snapshot']['ready'] is True
        assert case['active_bytes_sha256']==case['active_file']['sha256']
        assert case['active_generation_value']=='native generation '+str(generation)
    assert cases[0]['active_file']['identity']['file_id'] != cases[1]['active_file']['identity']['file_id']
    assert cases[1]['existing_active_file_identity_and_bytes_unchanged_before_bootstrap'] is True
    assert cases[1]['snapshot']['stopped'] is True and cases[1]['decoded_replies']['stop']['stopped'] is True
    dropped=cases[2]
    assert dropped['native']['work_reply_received'] is False
    assert dropped['decoded_replies']['lookup']['status']=='UNKNOWN'
    assert dropped['decoded_replies']['stop']['stopped'] is True and dropped['snapshot']['stopped'] is True
    return {'schema':'hh-gt02-s46-coordinator-verification-v1','status':'COORDINATOR_LOGIC_VERIFIED',
            'source_closure_sha256':CLOSURE,'source_files':106,'candidate_artifacts':9,
            'protocol':{'run':417,'passed':413,'skipped':4},'bootstrap':{'run':56,'passed':56},
            'golden_rows_per_consumer':2396,'native_service_cases':3,'concurrent_replacements':20,
            'file_boundary_denied_attempts':306,'registry_denied_attempts':36,
            'formal_acceptance':False,'limits':['generic arbitrary-path mutation unsupported',
            'native restart opens owner in same broker process; actual process-crash restart covered by unit subprocess',
            'pending, stopped and verified-empty restart held; no power-loss claim',
            'two independent same-closure verdicts required separately']}


if __name__=='__main__':
    if not __debug__: raise SystemExit('OPTIMIZED_VERIFICATION_FORBIDDEN')
    result=verify()
    (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
