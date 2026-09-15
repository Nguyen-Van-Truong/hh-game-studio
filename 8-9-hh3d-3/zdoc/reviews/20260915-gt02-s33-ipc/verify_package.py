"""Verify frozen diagnostic bytes/observations; never run IPC or rewrite pins."""
import argparse
import hashlib
import json
from pathlib import Path
import re

BASE=Path(__file__).resolve().parent
PRODUCT=BASE.parents[2]


def need(condition,message):
    if not condition:raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()


def read(path):return json.loads(path.read_text(encoding='utf-8'))


def safe(base,name):
    need('\\' not in name and ':' not in name and all(p not in ('','..','.') for p in name.split('/')),'Unsafe path')
    path=base/name
    path.resolve().relative_to(base.resolve())
    return path


def redact(raw):
    text=json.dumps(raw)
    for case in raw.get('cases',[]):
        descriptor=case.get('effective_pipe_sddl','')
        match=re.search(r'O:(S-1-5-21-\d+-\d+-\d+-\d+)',descriptor)
        if match:text=text.replace(match.group(1),'<BROKER_SID>')
        for sid in re.findall(r'S-1-15-2(?:-\d+)+',descriptor):
            text=text.replace(sid,'<APPCONTAINER_SID>')
    return json.loads(re.sub(r'S-1-5-21-\d+-\d+-\d+-\d+','<HOST_ACCOUNT_SID>',text))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--public-only',action='store_true')
    args=parser.parse_args()
    manifest=read(BASE/'pinned-manifest.json')
    need(manifest['schema']=='S33_IPC_DIAGNOSTIC_V1','Wrong schema')
    for name,digest in manifest['artifacts'].items():
        data=safe(BASE,name).read_bytes()
        need(sha(data)==digest,'Pinned hash mismatch: '+name)
        need(not re.search(rb'S-1-5-21-\d+-\d+-\d+-\d+',data),'Public account SID')
        need(not re.search(rb'(?i)[A-Z]:\\+Users\\+',data),'Public host path')
    for name,digest in manifest['dependencies'].items():
        need(sha(safe(PRODUCT,name).read_bytes())==digest,'Dependency changed: '+name)
    closure=read(PRODUCT/'zdoc/reviews/20260915-gt02-s32-01/source-closure.json')
    need(closure['source_closure_sha256']==manifest['runtime_source_closure'],'Wrong runtime closure')
    for name,digest in closure['files'].items():
        need(sha(safe(PRODUCT/'studio',name).read_bytes())==digest,'Runtime source changed: '+name)
    ledger=read(BASE/'redaction-ledger.json')
    for i in range(1,6):
        record=read(BASE/f'run-{i:02}.stdout.json')
        host=read(BASE/f'run-{i:02}.host.json')
        producer='ipc_probe.py' if i==5 else f'ipc_probe_run{i:02}.py'
        native='boundary_child.c' if i==5 else f'boundary_child_run{i:02}.c'
        need(record['source_sha256']==manifest['artifacts'][producer],'Producer changed')
        need(record['native_source_sha256']==manifest['artifacts'][native],'C source changed')
        need(record['private_store_sha256']==closure['files']['host/core/private_store.py'],'Wrong private-store source')
        need(host['run_id']==record['run_id']==f'GT02-S33-IPC-{i:02}','Wrong run ID')
        need(host['host_exit']==(0 if i>=4 else 1),'Host exit mismatch')
        need((BASE/f'run-{i:02}.stderr.txt').read_bytes()==b'','Unexpected stderr')
        need(record['profile_absent_before'] and record['profile_absent_after'] and record['owned_temp_removed'],'Owned cleanup not proved')
        need(record['create_profile_hresult']==record['delete_profile_hresult']==0,'Profile API failed')
        output_name=f'run-{i:02}.stdout.json'
        capture=ledger.get(output_name)
        need(host['stdout_sha256']==(capture['captured_sha256'] if capture else manifest['artifacts'][output_name]),'Capture hash mismatch')
        if not args.public_only:
            relative=record['raw_relative']
            need(relative.startswith('studio/.local/review-raw/S33/'),'Raw not owned')
            raw=safe(PRODUCT,relative).read_bytes()
            need(sha(raw)==record['raw_sha256'],'Raw changed')
            expected=redact(json.loads(raw))
            need({key:record[key] for key in expected}==expected,'Public derivation mismatch')
            if capture:
                original=safe(PRODUCT,capture['captured_relative']).read_bytes()
                need(sha(original)==capture['captured_sha256'],'Original capture changed')
                derived=re.sub(rb'S-1-5-21-\d+-\d+-\d+-\d+',b'<HOST_ACCOUNT_SID>',original)
                need(sha(derived)==manifest['artifacts'][output_name]==capture['public_sha256'],'Capture redaction mismatch')
    final=read(BASE/'run-05.stdout.json')
    need(final['diagnostic_complete'] and final['marker']=='S33_IPC_STAGING_DIAGNOSTIC_COMPLETE','Completion missing')
    need(final['profile_exists_after_create'],'Profile creation readback missing')
    need(final['safe_write']=='UNSUPPORTED_SAFE_OPEN_WINDOWS' and final['production_protocol'] is False,'Unsupported claim drift')
    for case in final['cases']:
        stage=case['mode']=='stage'
        need(case['mode'] in ('stage','wrong_pid'),'Unknown case')
        need(case['primary_token']=={'appcontainer':1,'sid_matches':True,'integrity':'S-1-16-4096','capabilities':0},'Wrong primary token')
        need(case['pipe_token']=={'appcontainer':1,'sid_matches':True},'Wrong pipe token')
        need(case['actual_pipe_pid']==case['pid'],'Wrong observed pipe PID')
        need(case['identity_binding_accepted']==stage and case['new_blob_count']==int(stage),'Binding/effect mismatch')
        need(case['host_exit']==case['final_host_exit']==53 and case['final_job_active']==0 and case['final_job_pids']==[],'Process not closed')
        native=case['native']
        need(native['started']=='S33_NATIVE_STARTED' and native['complete']=='S33_NATIVE_COMPLETE','Native marker missing')
        need(native['pipe_open_error']==0 and native['second_pipe_instance_error']==5,'Pipe rights mismatch')
        need('0x12019b' in case['effective_pipe_sddl'] and '(ML;;NW;;;LW)' in case['effective_pipe_sddl'],'Pipe security mismatch')
        if stage:
            need(native['direct_read_error']==native['direct_write_error']==5,'Direct file authority escaped')
            need(case['staged_blob']['sha256']==sha(b'S33_FIXED_STAGE_BYTES'),'Staged payload mismatch')
        else:need(native['reply']=='REJECTED_IDENTITY','Wrong identity not rejected')
    need(len(final['cases'])==2,'Missing cases')
    if not args.public_only:
        binary=safe(PRODUCT,final['native_executable_relative']).read_bytes()
        need(sha(binary)==final['native_executable_sha256'],'Native binary mismatch')
    print(json.dumps({'verified':'S33_FIXED_IPC_STAGING_ONLY','runtime_source_closure':manifest['runtime_source_closure'],
                      'artifacts':len(manifest['artifacts']),'raw_derivation_verified':not args.public_only,'writes':0,
                      'manifest_sha256':sha((BASE/'pinned-manifest.json').read_bytes()),'formal_acceptance':False}))


if __name__=='__main__':main()
