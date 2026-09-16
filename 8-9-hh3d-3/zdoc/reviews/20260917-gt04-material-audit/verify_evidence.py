"""Material02 portable evidence: read-only unless --write-derived is explicit."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

AUDIT=Path(__file__).resolve().parent;ROOT=AUDIT.parents[2]
PACKAGE=AUDIT.parent/'20260917-gt04-material-02';FILES={}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def need(value,label):
    if not value:raise ValueError(label)
def verify(overrides=None,*,check_live=False):
    overrides=overrides or {};FILES.clear()
    def raw(path):
        name=path.relative_to(ROOT).as_posix();data=overrides.get(name,path.read_bytes())
        FILES[name]=digest(data);return data
    def read(path):return json.loads(raw(path))
    def clean_job(job):
        need(job['closed'] is True and job['zero_observed'] is True and job['active_count']==0
            and job['handle_retained'] is False and job['tainted'] is False,'checked native Job')
    source=read(PACKAGE/'source-closure.json');files=source['files'];snapshot=PACKAGE/'source/studio'
    closure=digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(files.items())).encode())
    need(closure==source['source_closure_sha256'],'closure digest')
    need({path.relative_to(snapshot).as_posix():digest(raw(path)) for path in snapshot.rglob('*')
        if path.is_file() and '__pycache__' not in path.parts}==files,
        'frozen inventory')
    if check_live:
        for name,value in files.items():need(digest((ROOT/'studio'/name).read_bytes())==value,'live source '+name)
    runtime={name:value for name,value in files.items() if (name.endswith('.py') and
        name.startswith(('blender-addon/','host/core/','protocol/','host/blender/'))) or
        name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
    capture=read(PACKAGE/'capture.json');native=read(PACKAGE/'native.json')
    need(capture['source_closure_sha256']==closure and capture['source_unchanged'] is True
        and capture['snapshot_unchanged'] is True and capture['public_ack'] is False
        and native['source_files']==files,'source map binding')
    for name,record in (('unit',capture['unit']),('native',capture['host']),('reopen',native['reopen'])):
        actual=read(PACKAGE/record['host'])
        need(record['exit_code']==0 and record['wrapper_exit_code']==0 and actual['exit_code']==0
            and actual['target_pid']==record['target_pid'] and record['timed_out'] is False
            and record['tree_verified'] is True,'captured process exit '+name)
        raw(PACKAGE/record['stdout']);raw(PACKAGE/record['stderr'])
    tests=raw(PACKAGE/'unit-stderr.txt').decode().replace('\r\n','\n')
    need(re.findall(r'Ran (\d+) tests in ',tests)==['108'] and tests.rstrip().endswith('OK')
        and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',tests,re.M))==108,'raw 108 tests')
    stdout=raw(PACKAGE/'native-stdout.txt').decode();need(not raw(PACKAGE/'native-stderr.txt'),'native stderr')
    checks=[json.loads(line[len('GT04_MATERIAL_CHECK '):]) for line in stdout.splitlines() if line.startswith('GT04_MATERIAL_CHECK ')]
    need(checks==native['checks'] and len(checks)==16 and len({row['label'] for row in checks})==16
        and all(row['passed'] is True for row in checks),'native 16 checks')
    complete=[json.loads(line[len('GT04_MATERIAL_COMPLETE '):]) for line in stdout.splitlines() if line.startswith('GT04_MATERIAL_COMPLETE ')]
    need(complete==[{'passed':True,'checks':16}] and native['passed'] is True and native['public_ack'] is False,'native completion')
    roots=list(PACKAGE.glob('blender-*'));need(len(roots)==1,'one GUI owner');root=roots[0]
    launch=read(root/'launch.json');start=read(root/'process-start.json');end=read(root/'process-exit.json');closed=read(root/'close.json')
    need(launch['source_files']==runtime and end=={'pid':start['pid'],'exit_code':0}
        and closed==native['cleanup'] and closed['actual_process_exit']==end and closed['wrapper_exit_code']==0,'GUI binding')
    clean_job(closed['job'])
    for name in ('control-hello.json','data-hello.json','stdout.txt','stderr.txt'):raw(root/name)
    expected=read(PACKAGE/'checkpoint-expected.json');checkpoint=root/'project/checkpoint.blend'
    need(Path(expected['path']).name==checkpoint.name and digest(raw(checkpoint))==expected['sha256']
        and native['checkpoint']['artifact']['sha256']==expected['sha256'],'checkpoint exact bytes')
    reopened=read(PACKAGE/'checkpoint-reopened.json')
    markers=[json.loads(line[len('GT04_MATERIAL_REOPEN '):]) for line in raw(PACKAGE/'reopen-stdout.txt').decode().splitlines()
        if line.startswith('GT04_MATERIAL_REOPEN ')]
    need(markers==[reopened] and reopened['passed'] is True and reopened['snapshot']==expected['snapshot']
        and reopened['revision']==expected['revision'] and reopened['checkpoint_sha256']==expected['sha256']
        and not raw(PACKAGE/'reopen-stderr.txt'),'native checkpoint reopen marker')
    sys.path.insert(0,str(snapshot.parent))
    from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot
    exports=list(root.glob('export-*'));need(len(exports)==2,'two material export jobs')
    reports=[]
    for export in exports:
        launched=read(export/'launch.json');prepared=read(export/'expected.json');result=read(export/'result.json')
        report=read(export/'host-result.json');reports.append(report);caps=read(export/'limits.json')
        begin=read(export/'process-start.json');finish=read(export/'process-exit.json')
        need(launched['source_files']==runtime and finish=={'pid':begin['pid'],'exit_code':0}
            and report['actual_process_exit']==finish and report['wrapper_exit_code']==0
            and report['completed'] is True,'actual export binding')
        clean_job(report['job'])
        need(caps==report['limits'] and caps['job_memory_bytes']==2*1024**3 and caps['active_process_limit']==4
            and caps['job_user_time_100ns']==150000000 and caps['workspace_limit_is_watchdog'] is True,'native caps')
        need(digest(raw(export/'input.blend'))==prepared['input_sha256'] and prepared['snapshot']==expected['snapshot']
            and prepared['revision']==expected['revision'] and result['snapshot']==expected['snapshot'],'native material input')
        preflight=inspect_glb(raw(export/'output.glb'));bind_snapshot(preflight,expected['snapshot'])
        need(preflight==report['preflight'] and preflight['materials']==1 and preflight['images']==0
            and preflight['extensions']==[] and result['output_sha256']==preflight['sha256'],'native GLB material binding')
        stdout=raw(export/'stdout.txt').decode();need(not raw(export/'stderr.txt'),'export stderr')
        markers=[json.loads(line[len('GT04_EXPORT_COMPLETE '):]) for line in stdout.splitlines() if line.startswith('GT04_EXPORT_COMPLETE ')]
        need(markers==[result] and result['native_finished'] is True and result['context_unchanged'] is True,'export marker')
        for path in export.glob('cleanup-attempt-*.json'):raw(path)
    exported=read(PACKAGE/'export.json');admission=read(PACKAGE/'admission.json')
    need(exported in reports and admission in reports and exported!=admission,'separate export/admission receipts')
    rejected=admission['native']['admission_probe']
    need(len(rejected)==14 and len({row['label'] for row in rejected})==14
        and all(row['passed'] is True for row in rejected),'14 native rejected inputs')
    for name in ('README.md','verify_evidence.py','test_evidence.py'):raw(AUDIT/name)
    return {'passed':True,'source_closure_sha256':closure,'source_files':len(files),'python_tests':108,
        'native_checks':16,'native_admission_rejections':14,'background_exports':2,'checkpoint_reopens':1,
        'portable_artifacts':len(FILES),'public_ack':False,'formal_acceptance':False,'current_source_checked':check_live}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--write-derived',action='store_true')
    parser.add_argument('--check-live',action='store_true');args=parser.parse_args();result=verify(check_live=args.check_live)
    if args.write_derived:
        (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(FILES.items()))},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))
