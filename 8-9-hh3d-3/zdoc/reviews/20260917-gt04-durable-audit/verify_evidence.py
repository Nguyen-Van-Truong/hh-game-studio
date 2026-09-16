"""Read-only by default. --write-derived writes only this audit's metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[2]
PACKAGE=AUDIT.parent/'20260917-gt04-durable-01'
FILES={}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def need(value,label):
    if not value:raise ValueError(label)
def verify(overrides=None,*,check_live=False):
    overrides=overrides or {};FILES.clear()
    def raw(path):
        name=path.relative_to(ROOT).as_posix()
        data=overrides.get(name,path.read_bytes());FILES[name]=digest(data);return data
    def read(path):return json.loads(raw(path))
    def clean_job(job):
        need(job['closed'] is True and job['zero_observed'] is True and job['active_count']==0
            and job['handle_retained'] is False and job['close_uncertain'] is False,'checked native Job close')
    manifest=read(PACKAGE/'source-closure.json');source=manifest['files'];snapshot=PACKAGE/'source/studio'
    expected=digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(source.items())).encode())
    need(expected==manifest['source_closure_sha256'],'closure digest')
    inventory={p.relative_to(snapshot).as_posix():digest(raw(p)) for p in snapshot.rglob('*') if p.is_file()}
    need(inventory==source,'frozen inventory')
    if check_live:
        for name,value in source.items():need(digest((ROOT/'studio'/name).read_bytes())==value,'live source '+name)
    runtime={name:value for name,value in source.items() if (name.endswith('.py') and
        name.startswith(('blender-addon/','host/core/','protocol/','host/blender/'))) or
        name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
    capture=read(PACKAGE/'capture.json')
    need(capture['source_closure_sha256']==expected and capture['source_unchanged'] is True
        and capture['snapshot_unchanged'] is True and capture['public_ack'] is False,'capture source binding')
    for lane in ('unit','host'):
        record=capture[lane];actual=read(PACKAGE/record['host'])
        need(record['exit_code']==0 and record['wrapper_exit_code']==0 and actual['exit_code']==0
            and record['target_pid']==actual['target_pid'] and record['timed_out'] is False
            and record['tree_verified'] is True,'actual captured exit '+lane)
        raw(PACKAGE/record['stdout']);raw(PACKAGE/record['stderr'])
    tests=raw(PACKAGE/'unit-stderr.txt').decode().replace('\r\n','\n')
    need(re.findall(r'Ran (\d+) tests in ',tests)==['103'] and tests.rstrip().endswith('OK')
        and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',tests,re.M))==103,'103 raw test rows')
    native=read(PACKAGE/'native.json');cleanup=read(PACKAGE/'cleanup/native.json')
    stdout=raw(PACKAGE/'native-stdout.txt').decode();need(not raw(PACKAGE/'native-stderr.txt'),'native stderr')
    for prefix,count,report in (('GT04_CLEANUP',13,cleanup),('GT04_DURABLE',16,native)):
        checks=[json.loads(line[len(prefix)+7:]) for line in stdout.splitlines() if line.startswith(prefix+'_CHECK ')]
        need(len(checks)==count and len({row['label'] for row in checks})==count
            and all(row['passed'] is True for row in checks) and report['checks']==checks,'native checks '+prefix)
        complete=[json.loads(line[len(prefix)+10:]) for line in stdout.splitlines() if line.startswith(prefix+'_COMPLETE ')]
        need(complete==[{'passed':True,'checks':count}] and report['source_files']==source
            and report['passed'] is True and report['public_ack'] is False,'native completion '+prefix)
    for parent in (PACKAGE,PACKAGE/'cleanup'):
        roots=list(parent.glob('blender-*'));need(len(roots)==1,'one GUI owner')
        root=roots[0];launch=read(root/'launch.json');start=read(root/'process-start.json')
        end=read(root/'process-exit.json');closed=read(root/'close.json');clean_job(closed['job'])
        need(launch['source_files']==runtime and end=={'pid':start['pid'],'exit_code':0}
            and closed['actual_process_exit']==end and closed['wrapper_exit_code']==0,'native GUI binding')
        for name in ('control-hello.json','data-hello.json','stdout.txt','stderr.txt'):raw(root/name)
    sys.path.insert(0,str(snapshot.parent))
    from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot
    from studio.host.blender.durable_session import response_bytes,queue
    from studio.host.core.journal import Journal
    from studio.host.core.limits import DEFAULT_LIMITS
    failed=PACKAGE/'cleanup'/cleanup['failed_directory']
    original=raw(failed/'host-result.json');report=json.loads(original)
    need(digest(original)==cleanup['original_failed_report_sha256'] and report['completed'] is False
        and report['cleanup_held'] is True and report['status']=='EXPORT_CLEANUP_HELD','unknown report retained')
    attempts=[read(path) for path in sorted(failed.glob('cleanup-attempt-*.json'))]
    need([x['cleanup_held'] for x in attempts]==[True,True,False]
        and [x['attempt'] for x in attempts]==[1,2,3],'append-only retry sequence')
    for attempt in attempts[:2]:
        need(attempt['job']['handle_retained'] is True and attempt['job']['closed'] is False
            and attempt['job']['active_count']==0 and 'CLOSE' in attempt['job']['failed_operations'],'retained checked handle')
    clean_job(attempts[-1]['job']);need(cleanup['cleanup']['export_cleanup']==attempts[-1],'outer cleanup binding')
    exports=list(failed.parent.glob('export-*'));need(len(exports)==2,'two native export jobs')
    for root in exports:
        launch=read(root/'launch.json');need(launch['source_files']==runtime,'export runtime map')
        start=read(root/'process-start.json');end=read(root/'process-exit.json')
        need(end=={'pid':start['pid'],'exit_code':0},'actual export exit')
        expected_input=read(root/'expected.json');native_export=read(root/'result.json')
        need(digest(raw(root/'input.blend'))==expected_input['input_sha256'],'export input hash')
        geometry=inspect_glb(raw(root/'output.glb'));bind_snapshot(geometry,expected_input['snapshot'])
        need(geometry['sha256']==native_export['output_sha256'],'GLB native binding')
        raw(root/'limits.json');raw(root/'host-result.json');raw(root/'stdout.txt');raw(root/'stderr.txt')
        for path in root.glob('cleanup-attempt-*.json'):raw(path)
    raw(PACKAGE/'cleanup/normal-export.json')
    def journal(path):
        decoder=object.__new__(Journal);decoder.profile=DEFAULT_LIMITS
        decoder._records=[];decoder._commands={};decoder._pending=set();decoder._leases={}
        for line in raw(path).splitlines(keepends=True):
            row=decoder._decode_record(line);decoder._apply_loaded(row,len(decoder._records));decoder._records.append(row)
        return decoder
    active_root=next(PACKAGE.glob('blender-*'))
    live=journal(active_root/'journal/blender-journal.jsonl')
    terminal=live._command(('blender.owned-fixture','create'))
    need(terminal['status']=='COMMITTED' and response_bytes(terminal['receipt'])==raw(PACKAGE/'committed-response.json'),
        'durable original bytes')
    death=read(PACKAGE/'host-death/observed.json');ready=read(PACKAGE/'host-death/death-ready.json')
    need(death==native['host_death'] and death['host_pid']==ready['host_pid']
        and death['blender_pid']==ready['blender_pid'] and death['host_exit_code']==74
        and death['live_wait_before']==258 and death['dead_wait_after']==0 and death['native_exit_code']==0,
        'native death observer')
    orphan=journal(PACKAGE/'host-death'/ready['journal_directory']/'blender-journal.jsonl')
    intent=orphan._command(('blender.owned-fixture','interrupted'))
    need(intent['status']=='ACCEPTED_PENDING' and intent['digest']==queue.c.digest(ready['request'])
        and ready['native_observed_before_death']['native']['state']=='COMPLETED'
        and death['recovered_response']['status']=='UNKNOWN','post-effect orphan stays unknown')
    deadroot=PACKAGE/'host-death'/ready['owner_directory']
    need(read(deadroot/'launch.json')['source_files']==runtime,'host-death launch map')
    for name in ('process-start.json','control-hello.json','data-hello.json','stdout.txt','stderr.txt'):raw(deadroot/name)
    for name in ('stdout.txt','stderr.txt'):need(not raw(PACKAGE/'host-death'/name),'host-death diagnostics')
    for name in ('verify_evidence.py','README.md','test_evidence.py'):raw(AUDIT/name)
    return {'passed':True,'source_closure_sha256':expected,'source_files':len(source),
        'python_tests':103,'cleanup_native_checks':13,'durable_native_checks':16,
        'public_ack':False,'formal_acceptance':False,'portable_artifacts':len(FILES),'current_source_checked':check_live}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-derived',action='store_true')
    parser.add_argument('--check-live',action='store_true');args=parser.parse_args()
    result=verify(check_live=args.check_live)
    if args.write_derived:
        (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(FILES.items()))},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
