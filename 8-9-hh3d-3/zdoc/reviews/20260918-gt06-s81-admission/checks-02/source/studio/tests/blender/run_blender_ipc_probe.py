"""Frozen, owned GUI IPC proof; this is an internal fixture, not publication."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import time

sys.dont_write_bytecode=True
STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))


def load(path):
    spec=importlib.util.spec_from_file_location('gt04_owned_ipc_runner',path)
    module=importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root):
    paths=[root/name for name in ('build/bootstrap/run_fixture.py','godot-addon/cli_job.py','toolchain.lock.json')]
    for name in ('blender-addon','host/blender','host/core','protocol','tests/blender'):
        paths.extend(path for path in (root/name).rglob('*') if path.is_file()
                     and path.suffix in ('.py','.json','.gd','.md','.glb') and '__pycache__' not in path.parts)
    return {path.relative_to(root).as_posix():sha(path) for path in sorted(set(paths))}


def host_death_child(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost
    if sys.stdin.buffer.readline(16)!=b'START\n':return 125
    owner=BlenderUIHost(output,binary=binary)
    (output/'death-ready.json').write_text(json.dumps({'host_pid':os.getpid(),'blender_pid':owner.pid,
        'owner_directory':owner.directory.name,'job':owner._job.snapshot()})+'\n',encoding='utf-8')
    if sys.stdin.buffer.readline(16)!=b'DIE\n':return 125
    os._exit(73)  # Intentionally skip Python cleanup: the OS closes the owned Job handle.


def observe_host_death(output,binary):
    import ctypes
    from ctypes import wintypes as w
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes,kernel.OpenProcess.restype=[w.DWORD,w.BOOL,w.DWORD],w.HANDLE
    kernel.WaitForSingleObject.argtypes,kernel.WaitForSingleObject.restype=[w.HANDLE,w.DWORD],w.DWORD
    kernel.GetExitCodeProcess.argtypes,kernel.GetExitCodeProcess.restype=[w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL
    kernel.CloseHandle.argtypes,kernel.CloseHandle.restype=[w.HANDLE],w.BOOL
    parent=output/'host-death';parent.mkdir()
    process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--frozen','--host-death',
        '--output',str(parent),'--binary',str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    handle=None
    try:
        process.stdin.write(b'START\n');process.stdin.flush()
        deadline=time.monotonic()+25
        while not (parent/'death-ready.json').is_file():
            if time.monotonic()>=deadline or process.poll() is not None:raise RuntimeError('owned host-death setup failed')
            time.sleep(.01)
        ready=json.loads((parent/'death-ready.json').read_bytes())
        if ready['host_pid']!=process.pid:raise RuntimeError('owned host PID mismatch')
        handle=kernel.OpenProcess(0x1000|0x100000,False,ready['blender_pid'])
        if not handle or kernel.WaitForSingleObject(handle,0)!=258:raise RuntimeError('native Blender not live before host death')
        process.stdin.write(b'DIE\n');process.stdin.flush()
        stdout,stderr=process.communicate(timeout=5)
        waited=kernel.WaitForSingleObject(handle,5000);exit_code=w.DWORD()
        if waited!=0 or not kernel.GetExitCodeProcess(handle,ctypes.byref(exit_code)):
            raise RuntimeError('native Blender exit not observed after host death')
        value={'host_pid':process.pid,'host_exit_code':process.returncode,'blender_pid':ready['blender_pid'],
            'live_wait_before':258,'dead_wait_after':waited,'native_exit_code':exit_code.value,
            'job_assigned_before':ready['job']['assigned'],'public_ack':False,'intentional_host_death':True}
        (parent/'stdout.txt').write_bytes(stdout);(parent/'stderr.txt').write_bytes(stderr)
        (parent/'observed.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        if process.returncode!=73 or stdout or stderr:raise RuntimeError('unexpected owned host-death exit/log')
        return value
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        for pipe in (process.stdin,process.stdout,process.stderr):
            if pipe is not None and not pipe.closed:pipe.close()
        if handle and not kernel.CloseHandle(handle):raise RuntimeError('native observer handle close failed')


def frozen(output,binary,*,export=False):
    from studio.host.blender.ui_host import BlenderUIHost,HostError
    rows=[];owners=[]
    def check(label,value):
        rows.append({'label':label,'passed':value is True})
        print('GT04_IPC_CHECK '+json.dumps(rows[-1]),flush=True)
        if value is not True:raise ValueError(label)
    def command(key,op,state=None,payload=None):
        return {'schema':'HH-BLENDER-UI-COMMAND-1','command_id':key,'operation':op,
            'expected_revision':state['revision'] if state else None,
            'expected_context':state['context'] if state else None,'payload':payload or {}}
    def inspect(owner,key):
        row=owner.execute(command(key,'scene.inspect'))
        check(key+'_complete',row['state']=='COMPLETED' and row['public_ack'] is False)
        return row['result']
    try:
        owner=BlenderUIHost(output,binary=binary);owners.append(owner)
        secret=owner.channels['data'].key.hex().encode()
        live_count=owner._job.active_count()
        check('actual_owned_gui',owner.pid>0 and type(live_count) is int and live_count>=2)
        before=inspect(owner,'initial')
        check('fresh_empty_owned_scene',before['snapshot']['objects']==[])
        create=command('create','mesh.create_box',before,{'object_id':'box','size':[1,2,3]})
        created=owner.execute(create)
        check('authenticated_native_create',created['state']=='COMPLETED'
              and len(created['result']['after']['snapshot']['objects'])==1)
        after=created['result']['after']
        check('duplicate_original_receipt',owner.execute(create)==created)
        undone=owner.execute(command('undo','history.undo',after))
        check('native_undo_over_ipc',undone['state']=='COMPLETED' and undone['result']['after']==before)
        redone=owner.execute(command('redo','history.redo',before))
        check('native_redo_over_ipc',redone['state']=='COMPLETED' and redone['result']['after']==after)
        changed=owner.execute(command('transform','object.transform.set',after,
            {'object_id':'box','location':[2,-3,4],'rotation':[.2,-.3,.4] if export else [0,0,0],'scale':[1,2,1]}))
        check('native_transform_readback',changed['state']=='COMPLETED'
              and changed['result']['after']['snapshot']['objects'][0]['location']==[2,-3,4])
        stale=owner.execute(command('stale','history.undo',before))
        check('stale_revision_rejected',stale['state']=='REJECTED')
        now=inspect(owner,'after-stale')
        check('stale_has_no_effect',now==changed['result']['after'])
        saved=owner.execute(command('save','checkpoint.save',now,{'slot':'fixture'}))
        check('fixed_owned_save',saved['state']=='COMPLETED' and saved['result']['durable_publication'] is False)
        artifact=saved['result']['artifact']; path=owner.project/artifact['name']
        check('saved_file_exact_bytes',path.stat().st_size==artifact['size_bytes'] and sha(path)==artifact['sha256'])
        if export:
            export_command=command('export','export.prepare',now,{'slot':'export'})
            exported=owner.export_glb(export_command)
            check('background_export_native_complete',exported['completed'] is True
                  and exported['actual_process_exit']['exit_code']==0 and exported['wrapper_exit_code']==0)
            check('background_export_job_caps_and_cleanup',exported['job']['zero_observed'] is True
                  and exported['limits']['job_memory_bytes']==2*1024**3
                  and exported['limits']['job_user_time_100ns']==15*10_000_000
                  and exported['limits']['active_process_limit']==4)
            preflight=exported['preflight']
            check('bounded_glb_preflight',preflight['objects']==1 and preflight['triangles']==12
                  and preflight['materials']==0 and preflight['images']==0 and preflight['uri_count']==0
                  and preflight['extensions']==[])
            check('native_glb_transform_readback',preflight['meshes'][0]['translation']==[2,4,3]
                  and all(abs(a-b)<1e-5 for a,b in zip(preflight['meshes'][0]['scale'],[1,1,2]))
                  and preflight['meshes'][0]['rotation']!=[0,0,0,1] and exported['snapshot_geometry_bound'] is True)
            check('export_does_not_change_ui_state',inspect(owner,'after-export')==now)
            (output/'export.json').write_text(json.dumps(exported,indent=2)+'\n',encoding='utf-8')
            directories=set(owner.directory.glob('export-*'))
            check('export_retry_original_receipt_no_new_job',owner.export_glb(export_command)==exported
                  and set(owner.directory.glob('export-*'))==directories)
            from studio.host.blender.export_job import ExportJob
            admission=ExportJob(owner,owner.result('export')['result'],admission_probe=True).run()
            check('native_library_texture_driver_addon_rejected',admission['completed'] is True
                and len(admission['native']['admission_probe'])==9
                and all(row['passed'] is True for row in admission['native']['admission_probe']))
            (output/'admission.json').write_text(json.dumps(admission,indent=2)+'\n',encoding='utf-8')
            faults=load(STUDIO/'tests/blender/export_fault_probe.py').run(owner,owner.result('export')['result'],output)
            check('native_export_deadline_owned_cleanup',faults['deadline']['dead_wait_after']==0)
            check('native_export_memory_limit_owned_cleanup',faults['oom']['host_result']['actual_process_exit']['exit_code']==17)
            check('active_export_priority_stop_owned_cleanup',faults['stop']['dead_wait_after']==0
                  and faults['stop']['stop_elapsed_ms']<2000)
        start=time.monotonic(); stopped=owner.stop(); elapsed=(time.monotonic()-start)*1000
        check('priority_control_stop',stopped=={'stopped':True,'public_ack':False} and elapsed<2000)
        check('stop_retains_original_result',owner.result('create')==created)
        try:owner.submit(create)
        except HostError as exc:rejected=str(exc)=='BLENDER_STOPPED'
        else:rejected=False
        check('stop_refuses_new_dispatch',rejected)
        cleanup=owner.close()
        check('graceful_actual_gui_exit',cleanup['actual_process_exit']=={'pid':owner.pid,'exit_code':0}
              and cleanup['wrapper_exit_code']==0 and cleanup['job']['closed'] is True
              and cleanup['job']['zero_observed'] is True and cleanup['job']['active_count']==0)
        files={path.relative_to(owner.directory).as_posix():sha(path) for path in owner.directory.iterdir() if path.is_file()}
        check('no_secret_in_host_artifacts',all(secret not in (owner.directory/name).read_bytes() for name in files))
        (output/'happy.json').write_text(json.dumps({'checks':rows,'cleanup':cleanup,'save':artifact,
            'stop_elapsed_ms':elapsed,'live_job_count':live_count,'files':files,'public_ack':False,'acceptance':False},indent=2)+'\n',encoding='utf-8')
        dead=BlenderUIHost(output,binary=binary);owners.append(dead)
        for channel in dead.channels.values():channel.close()
        dead._process.wait(timeout=5)
        closed=dead.close()
        check('dead_host_channels_quit_gui',closed['actual_process_exit']=={'pid':dead.pid,'exit_code':0}
              and closed['wrapper_exit_code']==0 and closed['job']['zero_observed'] is True)
        death=observe_host_death(output,binary)
        check('actual_host_death_kills_owned_blender',death['host_exit_code']==73
              and death['live_wait_before']==258 and death['dead_wait_after']==0 and death['job_assigned_before'] is True)
        result={'passed':True,'checks':rows,'public_ack':False,'acceptance':False,
                'dead_cleanup':closed,'host_death':death,'source_files':sources(STUDIO)}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_IPC_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        for owner in owners:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--host-death',action='store_true')
    parser.add_argument('--export',action='store_true')
    args=parser.parse_args();out=args.output.absolute()
    if args.frozen:return host_death_child(out,args.binary) if args.host_death else frozen(out,args.binary,export=args.export)
    runner=load(STUDIO/'build/bootstrap/run_fixture.py')
    runner._reject_reparse_ancestors(out)
    out.mkdir(exist_ok=False)
    original=sources(STUDIO); snapshot=out/'source/studio'
    for name in original:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,dest)
    if sources(snapshot)!=original:raise ValueError('source snapshot differs')
    closure=runner.source_closure_sha256(original)
    (out/'source-closure.json').write_text(json.dumps({'files':original,'source_closure_sha256':closure},indent=2)+'\n',encoding='utf-8')
    owned=load(snapshot/'build/bootstrap/run_fixture.py')
    binary=STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe'
    unit=owned.run_process([sys.executable,'-B','-m','unittest','discover','-s','tests/blender','-p','test_*.py','-v'],
        cwd=snapshot,output=out,timeout=30,label='unit')
    argv=[sys.executable,'-B',str(snapshot/'tests/blender/run_blender_ipc_probe.py'),
        '--frozen','--output',str(out),'--binary',str(binary)]
    if args.export:argv.append('--export')
    host=owned.run_process(argv,cwd=snapshot,output=out,timeout=100,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())
