"""Frozen native journal/fence/crash proof plus cleanup regression on one closure."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
from run_blender_ipc_probe import load,sources


def command(key,op,state=None,payload=None):
    return {'schema':'HH-BLENDER-UI-COMMAND-1','command_id':key,'operation':op,
        'expected_revision':state['revision'] if state else None,
        'expected_context':state['context'] if state else None,'payload':payload or {}}


def death_child(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.durable_session import DurableBlenderSession
    if sys.stdin.buffer.readline(16)!=b'START\n':return 125
    owner=BlenderUIHost(output,binary=binary)
    session=DurableBlenderSession(owner.directory/'journal',host=owner)
    lease=session.acquire_writer('death-writer')
    inspected=session.execute_bytes(command('initial','scene.inspect'),lease)
    state=json.loads(inspected)['native']['result']
    request=command('interrupted','mesh.create_box',state,{'object_id':'interrupted','size':[1,1,1]})
    def die_after_effect(**kwargs):
        assert kwargs['command_id']=='interrupted' and kwargs['status']=='COMMITTED'
        observed=json.loads(''.join(kwargs['receipt']['wire_chunks']))
        ready={'host_pid':os.getpid(),'blender_pid':owner.pid,'owner_directory':owner.directory.name,
            'journal_directory':session.directory.relative_to(output).as_posix(),'request':request,
            'native_observed_before_death':observed,'public_ack':False}
        (output/'death-ready.json').write_text(json.dumps(ready,indent=2)+'\n',encoding='utf-8')
        if sys.stdin.buffer.readline(16)!=b'DIE\n':os._exit(125)
        os._exit(74)
    with patch.object(session.journal,'finish_command',die_after_effect):session.execute_bytes(request,lease)
    raise AssertionError('crash fixture unexpectedly returned')


def observe_death(output,binary):
    from studio.host.blender.durable_session import DurableBlenderSession
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes,kernel.OpenProcess.restype=[w.DWORD,w.BOOL,w.DWORD],w.HANDLE
    kernel.WaitForSingleObject.argtypes,kernel.WaitForSingleObject.restype=[w.HANDLE,w.DWORD],w.DWORD
    kernel.GetExitCodeProcess.argtypes,kernel.GetExitCodeProcess.restype=[w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL
    kernel.CloseHandle.argtypes,kernel.CloseHandle.restype=[w.HANDLE],w.BOOL
    output.mkdir()
    process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--frozen','--death-child',
        '--output',str(output),'--binary',str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    handle=None
    try:
        process.stdin.write(b'START\n');process.stdin.flush()
        deadline=time.monotonic()+25
        while not (output/'death-ready.json').is_file():
            if process.poll() is not None or time.monotonic()>=deadline:raise RuntimeError('native death fixture not ready')
            time.sleep(.01)
        ready=json.loads((output/'death-ready.json').read_bytes())
        assert ready['host_pid']==process.pid
        handle=kernel.OpenProcess(0x1000|0x100000,False,ready['blender_pid'])
        assert handle and kernel.WaitForSingleObject(handle,0)==258
        process.stdin.write(b'DIE\n');process.stdin.flush()
        stdout,stderr=process.communicate(timeout=5)
        assert process.returncode==74 and not stdout and not stderr
        assert kernel.WaitForSingleObject(handle,5000)==0
        code=w.DWORD();assert kernel.GetExitCodeProcess(handle,ctypes.byref(code))
        reopened=DurableBlenderSession(output/ready['journal_directory'])
        unknown=reopened.lookup_bytes('interrupted')
        assert json.loads(unknown)['status']=='UNKNOWN'
        assert reopened.execute_bytes(ready['request'],None)==unknown
        observed=ready['native_observed_before_death']
        assert observed['status']=='COMMITTED' and observed['native']['state']=='COMPLETED'
        assert len(observed['native']['result']['after']['snapshot']['objects'])==1
        result={'host_pid':process.pid,'host_exit_code':process.returncode,'blender_pid':ready['blender_pid'],
            'live_wait_before':258,'dead_wait_after':0,'native_exit_code':code.value,
            'native_effect_observed_before_terminal_persist':True,'recovered_response':json.loads(unknown),
            'retry_without_host_same_bytes':True,'public_ack':False}
        (output/'stdout.txt').write_bytes(stdout);(output/'stderr.txt').write_bytes(stderr)
        (output/'observed.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return result
    finally:
        if process.poll() is None:process.kill();process.wait(timeout=5)
        for pipe in (process.stdin,process.stdout,process.stderr):
            if pipe is not None and not pipe.closed:pipe.close()
        if handle and not kernel.CloseHandle(handle):raise RuntimeError('observer CloseHandle failed')


def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost,HostError
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.core.journal import JournalError
    from run_export_cleanup_probe import frozen as cleanup_probe
    cleanup=output/'cleanup';cleanup.mkdir();cleanup_probe(cleanup,binary)
    rows=[];owner=None
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_DURABLE_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    try:
        owner=BlenderUIHost(output,binary=binary)
        session=DurableBlenderSession(owner.directory/'journal',host=owner)
        lease=session.acquire_writer('writer')
        inspect_raw=session.execute_bytes(command('initial','scene.inspect'),lease)
        before=json.loads(inspect_raw)['native']['result']
        request=command('create','mesh.create_box',before,{'object_id':'box','size':[1,2,3]})
        raw=session.execute_bytes(request,lease);response=json.loads(raw)
        after=response['native']['result']['after']
        check('durable_native_create_postcondition',response['status']=='COMMITTED'
            and len(after['snapshot']['objects'])==1 and response['public_ack'] is False)
        check('exact_retry_same_bytes',session.execute_bytes(request,lease)==raw)
        readonly=DurableBlenderSession(session.directory)
        check('reopen_exact_response_without_native_owner',readonly.lookup_bytes('create')==raw
            and readonly.execute_bytes(request,None)==raw)
        changed=command('create','mesh.create_box',before,{'object_id':'box','size':[2,2,2]})
        try:session.execute_bytes(changed,lease)
        except HostError as error:conflict=str(error)=='BLENDER_COMMAND_CONFLICT'
        else:conflict=False
        check('changed_duplicate_rejected',conflict)
        try:session.acquire_writer('other')
        except JournalError as error:busy=error.code=='LEASE_BUSY'
        else:busy=False
        check('second_writer_busy',busy)
        next_lease=session.acquire_writer('writer')
        late=command('late','object.transform.set',after,{'object_id':'box','location':[7,0,0],
            'rotation':[0,0,0],'scale':[1,1,1]})
        try:session.execute_bytes(late,lease)
        except JournalError as error:stale=error.code=='STALE_LEASE'
        else:stale=False
        check('old_durable_lease_rejected_before_intent',stale)
        try:session.lookup_bytes('late')
        except JournalError as error:absent=error.code=='COMMAND_NOT_FOUND'
        else:absent=False
        check('old_lease_created_no_intent',absent)
        old_wire={'fencing_epoch':lease.fencing_epoch,'expires_ms':lease.expires_ms}
        try:owner.execute(late,lease=old_wire)
        except HostError as error:native_rejected=str(error)=='BLENDER_COMMAND_REJECTED'
        else:native_rejected=False
        check('native_consumer_rejects_late_authenticated_fence',native_rejected)
        try:owner.arm_lease(old_wire)
        except HostError as error:arm_rejected=str(error)=='BLENDER_COMMAND_REJECTED'
        else:arm_rejected=False
        check('native_high_water_cannot_move_backwards',arm_rejected)
        current=json.loads(session.execute_bytes(command('after-late','scene.inspect'),next_lease))['native']['result']
        check('stale_writer_has_no_native_effect',current==after)
        short=session.acquire_writer('writer',ttl_ms=150)
        time.sleep(.2)
        renewed=session.acquire_writer('other')
        check('new_writer_after_expiry_has_larger_fence',renewed.owner=='other'
            and renewed.fencing_epoch>short.fencing_epoch)
        stopped=session.stop()
        check('priority_stop_retains_exact_durable_response',stopped=={'stopped':True,'public_ack':False}
            and session.execute_bytes(request,None)==raw)
        closed=owner.close()
        check('durable_gui_actual_exit_zero',closed['actual_process_exit']=={'pid':owner.pid,'exit_code':0}
            and closed['wrapper_exit_code']==0 and closed['job']['closed'] is True
            and closed['job']['zero_observed'] is True)
        (output/'committed-response.json').write_bytes(raw)
        death=observe_death(output/'host-death',binary)
        check('actual_death_after_effect_before_terminal',death['host_exit_code']==74
            and death['native_effect_observed_before_terminal_persist'] is True)
        check('death_kills_exact_owned_native_process',death['live_wait_before']==258 and death['dead_wait_after']==0)
        check('restart_orphan_unknown_without_duplicate_effect',death['recovered_response']['status']=='UNKNOWN'
            and death['retry_without_host_same_bytes'] is True)
        result={'passed':True,'checks':rows,'cleanup':closed,'host_death':death,
            'public_ack':False,'candidate_only':True,'source_files':sources(STUDIO)}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_DURABLE_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        if owner is not None:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--death-child',action='store_true')
    args=parser.parse_args();out=args.output.absolute()
    if args.frozen:return death_child(out,args.binary) if args.death_child else frozen(out,args.binary)
    runner=load(STUDIO/'build/bootstrap/run_fixture.py');runner._reject_reparse_ancestors(out)
    out.mkdir(exist_ok=False);original=sources(STUDIO);snapshot=out/'source/studio'
    for name in original:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,dest)
    if sources(snapshot)!=original:raise ValueError('source snapshot differs')
    closure=runner.source_closure_sha256(original)
    (out/'source-closure.json').write_text(json.dumps({'files':original,'source_closure_sha256':closure},indent=2)+'\n',encoding='utf-8')
    owned=load(snapshot/'build/bootstrap/run_fixture.py')
    unit=owned.run_process([sys.executable,'-B','-m','unittest','discover','-s','tests/blender','-p','test_*.py','-v'],
        cwd=snapshot,output=out,timeout=30,label='unit')
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_durable_session_probe.py'),
        '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
        cwd=snapshot,output=out,timeout=100,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())
