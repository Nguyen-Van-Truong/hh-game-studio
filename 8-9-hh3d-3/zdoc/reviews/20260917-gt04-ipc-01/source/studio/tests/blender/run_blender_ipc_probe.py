"""Frozen, owned GUI IPC proof; this is an internal fixture, not publication."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
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
                     and path.suffix in ('.py','.json','.gd','.md') and '__pycache__' not in path.parts)
    return {path.relative_to(root).as_posix():sha(path) for path in sorted(set(paths))}


def frozen(output,binary):
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
        check('actual_owned_gui',owner.pid>0 and owner._job.active_count()==2)
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
            {'object_id':'box','location':[2,-3,4],'rotation':[0,0,0],'scale':[1,2,1]}))
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
            'stop_elapsed_ms':elapsed,'files':files,'public_ack':False,'acceptance':False},indent=2)+'\n',encoding='utf-8')
        dead=BlenderUIHost(output,binary=binary);owners.append(dead)
        for channel in dead.channels.values():channel.close()
        dead._process.wait(timeout=5)
        closed=dead.close()
        check('dead_host_channels_quit_gui',closed['actual_process_exit']=={'pid':dead.pid,'exit_code':0}
              and closed['wrapper_exit_code']==0 and closed['job']['zero_observed'] is True)
        result={'passed':True,'checks':rows,'public_ack':False,'acceptance':False,
                'dead_cleanup':closed,'source_files':sources(STUDIO)}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_IPC_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        for owner in owners:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    args=parser.parse_args();out=args.output.absolute()
    if args.frozen:return frozen(out,args.binary)
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
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_blender_ipc_probe.py'),
        '--frozen','--output',str(out),'--binary',str(binary)],cwd=snapshot,output=out,timeout=100,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())
