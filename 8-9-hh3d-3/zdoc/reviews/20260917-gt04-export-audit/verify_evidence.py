"""Read-only export04 candidate binding. No engines or evidence normalization."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import sys

AUDIT=Path(__file__).resolve().parent
helper=AUDIT.parent/'20260917-gt04-ipc-audit/verify_evidence.py'
spec=importlib.util.spec_from_file_location('gt04_ipc_evidence_helpers',helper)
H=importlib.util.module_from_spec(spec);exec(compile(helper.read_bytes(),str(helper),'exec'),H.__dict__)
H.AUDIT=AUDIT;H.PACKAGE=AUDIT.parent/'20260917-gt04-export-04'
P=H.PACKAGE;need=H.need;read=H.read;text=H.text;add=H.add;integer=H.integer


def caps(value,wall=20):
    expected={'job_memory_bytes':2*1024**3,'job_user_time_100ns':150000000,
        'active_process_limit':4,'limit_flags':8716,'wall_seconds':wall,
        'workspace_bytes_limit':32*1024**2,'workspace_limit_is_watchdog':True,'each_log_capture_bytes':262144}
    need(value==expected and all(type(value[k]) is type(v) for k,v in expected.items()),'queried native caps')


def main():
    H.FILES.clear()
    manifest=read(P/'source-closure.json');files=manifest['files'];snapshot=P/'source/studio'
    closure=H.digest(''.join('8-9-hh3d-3/studio/'+name+'\0'+value+'\n' for name,value in sorted(files.items())).encode())
    need(closure==manifest['source_closure_sha256'],'closure digest')
    observed={p.relative_to(snapshot).as_posix():H.digest(p.read_bytes()) for p in snapshot.rglob('*') if p.is_file()}
    need(observed==files,'complete frozen inventory')
    for name,value in files.items():
        add(snapshot/name);need(H.digest((H.ROOT/'studio'/name).read_bytes())==value,'current source differs: '+name)
    runtime={name:value for name,value in files.items() if (name.endswith('.py') and
        name.startswith(('blender-addon/','host/core/','protocol/','host/blender/'))) or
        name in ('blender-addon/exporter.lock.json','godot-addon/cli_job.py','toolchain.lock.json')}
    capture=read(P/'capture.json')
    need(capture['candidate_only'] is True and capture['public_ack'] is False and capture['source_unchanged'] is True
         and capture['snapshot_unchanged'] is True and capture['source_closure_sha256']==closure,'source capture')
    _,stderr=H.host(capture['unit'])
    need(re.findall(r'Ran (\d+) tests in ',stderr)==['83'] and stderr.rstrip().endswith('OK')
        and len(re.findall(r'^test\w+ \([^\n]+\) \.\.\. ok$',stderr,re.MULTILINE))==83,'raw 83 tests')
    stdout,stderr=H.host(capture['host']);need(not stderr,'outer native stderr')
    checks=[json.loads(line[15:]) for line in stdout.splitlines() if line.startswith('GT04_IPC_CHECK ')]
    native=read(P/'native.json');happy=read(P/'happy.json')
    need(len(checks)==31 and len({row['label'] for row in checks})==31 and all(row['passed'] is True for row in checks)
        and native['checks']==checks and native['source_files']==files and native['passed'] is True
        and native['public_ack'] is False and native['acceptance'] is False,'native checks/map')
    need([json.loads(line[18:]) for line in stdout.splitlines() if line.startswith('GT04_IPC_COMPLETE ')]
        ==[{'passed':True,'checks':31}],'native completion')
    need(happy['checks']==checks[:-2] and happy['public_ack'] is False and happy['acceptance'] is False
        and 0<=happy['stop_elapsed_ms']<2000,'happy raw binding')
    roots=sorted(P.glob('blender-*'));need(len(roots)==2,'GUI owner inventory');happy_root=None
    for root in roots:
        launch=read(root/'launch.json');start=read(root/'process-start.json');end=read(root/'process-exit.json')
        close=read(root/'close.json');H.job(close['job'])
        need(launch['source_files']==runtime and launch['public_ack'] is False,'GUI launched source')
        need(integer(start['pid']) and start['pid']>0 and integer(end['pid'],start['pid']) and integer(end['exit_code'],0)
            and close['actual_process_exit']==end and integer(close['wrapper_exit_code'],0) and close['closed'] is True
            and close['held'] is False and close['logs_overflow'] is False,'GUI cleanup')
        for lane in ('control','data'):
            need(read(root/(lane+'-hello.json'))=={'pid':start['pid'],'version':'5.2.1 LTS','main_thread':True,
                'background':False,'python_threads':1,'public_ack':False},'native main-thread handshake')
        need(not text(root/'stderr.txt'),'GUI stderr')
        need(not re.search(r'(?im)^.*\b(?:error|warning|traceback)\b',text(root/'stdout.txt')),'GUI diagnostic')
        if close==happy['cleanup']:happy_root=root
    need(happy_root is not None,'happy native lifecycle')
    saved=add(happy_root/'project'/happy['save']['name'])
    need(saved.stat().st_size==happy['save']['size_bytes'] and H.digest(saved.read_bytes())==happy['save']['sha256'],'saved bytes')
    for name,value in happy['files'].items():need(H.digest(add(happy_root/name).read_bytes())==value,'happy raw bytes')
    sys.path.insert(0,str(snapshot.parent))
    from studio.host.blender.glb_preflight import inspect_glb,bind_snapshot
    exports=sorted(happy_root.glob('export-*'));need(len(exports)==5,'one export, one admission, three fault jobs')
    completed=[];failed={}
    for root in exports:
        launch=read(root/'launch.json');report=read(root/'host-result.json');start=read(root/'process-start.json')
        need(launch['source_files']==runtime and launch['public_ack'] is False,'background launched source')
        need(report['public_ack'] is False and report['candidate_only'] is True,'background authority')
        H.job(report['job']);limits=read(root/'limits.json');need(limits==report['limits'],'captured caps binding')
        expected=read(root/'expected.json');source=add(root/'input.blend')
        need(source.stat().st_size<=8*1024**2 and H.digest(source.read_bytes())==expected['input_sha256'],'copied input hash')
        prepared=add(happy_root/'project/export.blend');need(H.digest(prepared.read_bytes())==expected['input_sha256'],'UI snapshot binding')
        outlog=text(root/'stdout.txt');errlog=text(root/'stderr.txt')
        if report['completed'] is True:
            caps(limits);end=read(root/'process-exit.json');result=read(root/'result.json');glb=add(root/'output.glb')
            need(integer(end['pid'],start['pid']) and integer(end['exit_code'],0) and report['actual_process_exit']==end
                and integer(report['wrapper_exit_code'],0),'background success exit')
            markers=[json.loads(line[len('GT04_EXPORT_COMPLETE '):]) for line in outlog.splitlines() if line.startswith('GT04_EXPORT_COMPLETE ')]
            need(markers==[result] and result==report['native'] and result['public_ack'] is False
                and result['native_finished'] is True and result['context_unchanged'] is True,'native export marker')
            need(not errlog and not re.search(r'(?im)^.*\b(?:error|warning|traceback)\b',outlog),'export diagnostic')
            need(result['snapshot']==expected['snapshot'] and result['scene_revision']==expected['revision']
                and result['input_sha256']==expected['input_sha256'],'reopened exact scene')
            preflight=inspect_glb(glb.read_bytes());bind_snapshot(preflight,expected['snapshot'])
            need(preflight==report['preflight'] and report['snapshot_geometry_bound'] is True
                and result['output_sha256']==preflight['sha256'] and result['output_size_bytes']==preflight['size_bytes']
                and report['artifact']=={'name':'output.glb','sha256':preflight['sha256'],'size_bytes':preflight['size_bytes']},'actual GLB postcondition')
            completed.append(report)
        else:
            need(report['completed'] is False and not (root/'output.glb').exists() and not (root/'result.json').exists(),'failure cannot publish')
            ready=read(root/'fault-ready.json');need(integer(ready['pid'],start['pid']) and ready['phase']=='validated-before-export'
                and ready['public_ack'] is False,'actual native fault phase')
            failure=report['failure'];need(failure not in failed,'unique fault job');failed[failure]=(root,report,ready,errlog)
            caps(limits,4 if failure=='EXPORT_DEADLINE' else 20)
    exported=read(P/'export.json');admission=read(P/'admission.json')
    need(len(completed)==2 and exported in completed and admission in completed and exported!=admission,'raw result bindings')
    cases=admission['native']['admission_probe'];need(len(cases)==9 and len({row['label'] for row in cases})==9
        and all(row['passed'] is True for row in cases),'nine actual admission rejects')
    for kind,reason in (('deadline','EXPORT_DEADLINE'),('stop','EXPORT_CANCELLED'),('oom','EXPORT_NATIVE_FAILED')):
        observed=read(P/(kind+'.json'));root,report,ready,errlog=failed[reason]
        need(observed['directory']==root.relative_to(P).as_posix() and observed['host_result']==report
            and observed['fault_ready']==ready and observed['public_ack'] is False,'fault raw binding')
        if kind=='oom':
            end=read(root/'process-exit.json')
            need(end=={'pid':ready['pid'],'exit_code':17} and report['actual_process_exit']==end
                and integer(report['wrapper_exit_code'],17) and 'MemoryError' in errlog,'actual OOM rejection')
        else:
            need(integer(observed['live_wait_before'],258) and integer(observed['dead_wait_after'],0)
                and integer(observed['actual_native_exit_code'],2) and integer(report['wrapper_exit_code'],2)
                and report['actual_process_exit'] is None and not (root/'process-exit.json').exists(),'forced native exit observer')
            if kind=='stop':need(observed['stop']=={'stopped':True,'public_ack':False}
                and 0<=observed['stop_elapsed_ms']<2000,'active export Stop budget')
    death=read(P/'host-death/observed.json');ready=read(P/'host-death/death-ready.json')
    need(death==native['host_death'] and integer(death['host_pid'],ready['host_pid'])
        and integer(death['blender_pid'],ready['blender_pid']) and integer(death['host_exit_code'],73)
        and integer(death['live_wait_before'],258) and integer(death['dead_wait_after'],0)
        and death['job_assigned_before'] is True and ready['job']['assigned'] is True
        and death['intentional_host_death'] is True and death['public_ack'] is False,'owned host death')
    for name in ('stdout.txt','stderr.txt'):need(not text(P/'host-death'/name),'host death diagnostic')
    deadroot=P/'host-death'/ready['owner_directory']
    for name in ('launch.json','process-start.json','control-hello.json','data-hello.json','stdout.txt','stderr.txt'):add(deadroot/name)
    need(read(deadroot/'launch.json')['source_files']==runtime,'dead-host source map')
    add(Path(__file__));add(helper);add(AUDIT/'README.md')
    add(AUDIT/'test_evidence.py')
    result={'passed':True,'status':'CANDIDATE','formal_acceptance':False,'public_ack':False,
        'source_closure_sha256':closure,'source_files':len(files),'runtime_files':len(runtime),
        'portable_artifacts':len(H.FILES),'python_tests':83,'native_checks':31,'admission_rejections':9,
        'background_jobs':5,'successes':2,'expected_faults':3,'active_export_stop_ms':read(P/'stop.json')['stop_elapsed_ms']}
    (AUDIT/'portable-artifacts.json').write_text(json.dumps({'files':dict(sorted(H.FILES.items()))},indent=2)+'\n',encoding='utf-8')
    (AUDIT/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()
