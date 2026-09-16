"""Read-only GT04 IPC05 candidate evidence check. Never starts engines."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

AUDIT=Path(__file__).resolve().parent
ROOT=AUDIT.parents[2]
PACKAGE=AUDIT.parent/'20260917-gt04-ipc-05'
FILES={}


def need(value,reason):
    if not value:raise ValueError(reason)


def digest(raw):return hashlib.sha256(raw).hexdigest()


def add(path):
    need(path.is_file() and not path.is_symlink(),'missing/aliased proof file')
    relative=path.relative_to(ROOT).as_posix()
    need(not any(part in ('.godot','__pycache__','temp','user') for part in Path(relative).parts),'cache in proof')
    FILES[relative]=digest(path.read_bytes())
    return path


def read(path):return json.loads(add(path).read_bytes())
def text(path):return add(path).read_text(encoding='utf-8')
def integer(value,expected=None):return type(value) is int and (expected is None or value==expected)


def host(row):
    raw=read(PACKAGE/row['host'])
    need(integer(raw['target_pid']) and raw['target_pid']>0 and integer(row['target_pid'],raw['target_pid'])
         and integer(row['wrapper_pid']) and row['wrapper_pid']>0,'host PIDs')
    need(all(integer(code,0) for code in (raw['exit_code'],row['exit_code'],row['wrapper_exit_code'])),'host exits')
    need(row['tree_verified'] is True and row['timed_out'] is False
         and row['ownership']=='gated_job_kill_on_close','host process tree')
    return text(PACKAGE/row['stdout']),text(PACKAGE/row['stderr'])


def job(value):
    need(all(value[key] is True for key in ('configured','assigned','closed','zero_observed')),'Job incomplete')
    need(all(value[key] is False for key in ('handle_retained','tainted','create_uncertain','close_uncertain')),'Job uncertain')
    need(integer(value['active_count'],0) and value['failed_operations']==[] and value['native_error'] is None,'Job not empty')


def main():
    manifest=read(PACKAGE/'source-closure.json');files=manifest['files']
    closure=digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(files.items())).encode())
    need(closure==manifest['source_closure_sha256'],'closure digest')
    snapshot=PACKAGE/'source/studio'
    observed={path.relative_to(snapshot).as_posix():digest(path.read_bytes()) for path in snapshot.rglob('*') if path.is_file()}
    need(observed==files,'complete frozen inventory')
    for name,value in files.items():
        add(snapshot/name)
        need(digest((ROOT/'studio'/name).read_bytes())==value,'current source differs: '+name)
    capture=read(PACKAGE/'capture.json')
    need(capture['candidate_only'] is True and capture['public_ack'] is False
         and capture['source_unchanged'] is True and capture['snapshot_unchanged'] is True
         and capture['source_closure_sha256']==closure,'capture source/authority')
    _,stderr=host(capture['unit'])
    need(re.findall(r'Ran (\d+) tests in ',stderr)==['61'] and stderr.rstrip().endswith('OK')
         and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',stderr,re.MULTILINE))==61,'raw 61 tests')
    stdout,err=host(capture['host']);need(not err,'native outer stderr')
    native=read(PACKAGE/'native.json');happy=read(PACKAGE/'happy.json')
    checks=[json.loads(line.removeprefix('GT04_IPC_CHECK ')) for line in stdout.splitlines() if line.startswith('GT04_IPC_CHECK ')]
    need(native['passed'] is True and native['public_ack'] is False and native['acceptance'] is False
         and native['source_files']==files and checks==native['checks'] and len(checks)==20
         and len({row['label'] for row in checks})==20 and all(row['passed'] is True for row in checks),'native raw checks')
    need([json.loads(line.removeprefix('GT04_IPC_COMPLETE ')) for line in stdout.splitlines()
          if line.startswith('GT04_IPC_COMPLETE ')]==[{'passed':True,'checks':20}],'native completion')
    need(happy['checks']==checks[:18] and happy['public_ack'] is False and happy['acceptance'] is False
         and type(happy['stop_elapsed_ms']) in (int,float) and 0<=happy['stop_elapsed_ms']<2000,'happy Stop facts')
    roots=sorted(PACKAGE.glob('blender-*'));need(len(roots)==2,'owned GUI inventory')
    expected_source={name:value for name,value in files.items() if name.endswith('.py')
        and name.startswith(('blender-addon/','host/core/','protocol/')) or
        name in ('host/blender/ui_host.py','host/blender/__init__.py','godot-addon/cli_job.py','toolchain.lock.json')}
    happy_root=None
    for directory in roots:
        launch=read(directory/'launch.json');start=read(directory/'process-start.json');end=read(directory/'process-exit.json')
        close=read(directory/'close.json');job(close['job'])
        need(launch['source_files']==expected_source and launch['public_ack'] is False,'launched source map')
        need(integer(end['pid'],start['pid']) and integer(end['exit_code'],0)
             and close['actual_process_exit']==end and integer(close['wrapper_exit_code'],0)
             and close['closed'] is True and close['held'] is False and close['logs_overflow'] is False,'native GUI cleanup')
        for lane in ('control','data'):
            hello=read(directory/(lane+'-hello.json'))
            need(hello=={'pid':start['pid'],'version':'5.2.1 LTS','main_thread':True,
                         'background':False,'python_threads':1,'public_ack':False},'native main-thread hello')
        need(not text(directory/'stderr.txt'),'native stderr')
        need(not re.search(r'(?im)^.*\b(?:error|warning|traceback)\b',text(directory/'stdout.txt')),'native diagnostic')
        if close==happy['cleanup']:happy_root=directory
    need(happy_root is not None,'happy actual lifecycle binding')
    artifact=happy['save'];saved=add(happy_root/'project'/artifact['name'])
    need(saved.stat().st_size==artifact['size_bytes'] and digest(saved.read_bytes())==artifact['sha256'],'saved fixture bytes')
    for name,value in happy['files'].items():need(digest(add(happy_root/name).read_bytes())==value,'happy raw artifact bytes')
    death=read(PACKAGE/'host-death/observed.json');ready=read(PACKAGE/'host-death/death-ready.json')
    need(death==native['host_death'] and integer(death['host_pid'],ready['host_pid'])
         and integer(death['blender_pid'],ready['blender_pid']) and integer(death['host_exit_code'],73)
         and integer(death['live_wait_before'],258) and integer(death['dead_wait_after'],0)
         and integer(death['native_exit_code']) and death['job_assigned_before'] is True
         and ready['job']['assigned'] is True and ready['job']['configured'] is True
         and death['intentional_host_death'] is True and death['public_ack'] is False,'actual host-death binding')
    for name in ('stdout.txt','stderr.txt'):need(not text(PACKAGE/'host-death'/name),'host-death diagnostic')
    deadroot=PACKAGE/'host-death'/ready['owner_directory']
    for name in ('launch.json','process-start.json','control-hello.json','data-hello.json','stdout.txt','stderr.txt'):
        add(deadroot/name)
    add(Path(__file__));add(AUDIT/'README.md')
    result={'passed':True,'status':'CANDIDATE','formal_acceptance':False,'public_ack':False,
        'source_closure_sha256':closure,'source_files':len(files),'portable_artifacts':len(FILES),
        'python_tests':61,'native_checks':20,'ordinary_gui_sessions':2,'intentional_host_exit':73}
    (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(FILES.items()))},indent=2)+'\n',encoding='utf-8')
    (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
