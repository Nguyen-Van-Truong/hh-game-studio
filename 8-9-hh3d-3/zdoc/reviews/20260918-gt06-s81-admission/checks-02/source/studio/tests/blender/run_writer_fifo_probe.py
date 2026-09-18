"""Two synthetic client processes contend through the owned native host."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
sys.dont_write_bytecode=True
STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent));sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_blender_ipc_probe import load,sources
from run_durable_session_probe import command


def client():
    def read():
        raw=sys.stdin.buffer.readline(65537)
        assert 0<len(raw)<=65536 and raw.endswith(b'\n');return json.loads(raw)
    def send(value):print(json.dumps(value),flush=True)
    config=read();writer=config['writer'];ticket=config['ticket_id']
    send({'op':'enqueue','pid':os.getpid(),'ticket_id':ticket,'writer':writer})
    status=read();assert status['state']=='WAITING'
    send({'op':'wait','ticket_id':ticket,'writer':writer})
    granted=read();assert granted['ticket']['state']=='GRANTED'
    request=command('create-'+writer,'mesh.create_box',granted['state'],{'object_id':writer,'size':[1,1,1]})
    send({'op':'execute','ticket_id':ticket,'writer':writer,'command':request})
    response=read();assert response['status']=='COMMITTED' and response['public_ack'] is False
    send({'op':'done','pid':os.getpid(),'ticket_id':ticket,'writer':writer,'command_id':request['command_id']})
    return 0


def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost,HostError
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.writer_journal import MAX_WAITERS
    from studio.host.core.journal import JournalError,Lease
    owner=None;clients=[];rows=[];events=[]
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_FIFO_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    def send(process,value):
        raw=json.dumps(value).encode()+b'\n';assert len(raw)<=65536
        process.stdin.write(raw);process.stdin.flush()
    def read(process):
        raw=process.stdout.readline(65537);assert 0<len(raw)<=65536 and raw.endswith(b'\n')
        value=json.loads(raw);events.append({'client_pid':process.pid,'message':value});return value
    try:
        owner=BlenderUIHost(output,binary=binary)
        a=DurableBlenderSession(owner.directory/'journal',host=owner)
        initial=a.acquire_writer('initial',ttl_ms=10000)
        empty=json.loads(a.execute_bytes(command('initial','scene.inspect'),initial))['native']['result']
        a.request_writer('cancel-first','cancel-writer',wait_ms=10000,lease_ms=1000)
        a.request_writer('expire-first','expire-writer',wait_ms=50,lease_ms=1000)
        check('cancel_before_grant_has_terminal_ticket',a.cancel_writer('cancel-first','cancel-writer')['state']=='CANCELED')
        b=DurableBlenderSession(a.directory,host=owner)
        for writer,ticket in (('alice','ticket-alice'),('bob','ticket-bob')):
            process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--client'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            clients.append(process);send(process,{'writer':writer,'ticket_id':ticket})
        queued=[]
        for process,session in zip(clients,(a,b)):
            request=read(process);assert request['op']=='enqueue' and request['pid']==process.pid
            queued.append(session.request_writer(request['ticket_id'],request['writer'],wait_ms=30000,
                lease_ms=10000))
            send(process,queued[-1]);assert read(process)['op']=='wait'
        check('two_actual_clients_are_distinct_live_processes',clients[0].pid!=clients[1].pid
            and all(process.poll() is None for process in clients))
        check('two_persisted_waiters_no_lost_enqueue',a.writer_status('ticket-alice','alice')['state']=='WAITING'
            and b.writer_status('ticket-bob','bob')['state']=='WAITING')
        try:a.acquire_writer('initial')
        except JournalError as error:bypass=error.code=='BLENDER_FIFO_REQUIRED'
        else:bypass=False
        check('immediate_renew_cannot_bypass_fifo',bypass)
        grants=[];responses=[]
        for process,session,writer,ticket in zip(clients,(a,b),('alice','bob'),('ticket-alice','ticket-bob')):
            deadline=time.monotonic()+20;granted=None
            while granted is None:
                granted=session.pump_writers()
                if time.monotonic()>=deadline:raise RuntimeError('bounded FIFO grant deadline')
                if granted is None:time.sleep(.05)
            check('fifo_grants_'+writer,granted['ticket_id']==ticket)
            grants.append(granted);lease=Lease(**granted['lease'])
            state=json.loads(session.execute_bytes(command('inspect-'+writer,'scene.inspect'),lease))['native']['result']
            send(process,{'ticket':granted,'state':state})
            request=read(process);assert request['op']=='execute' and request['ticket_id']==ticket
            response=json.loads(session.execute_bytes(request['command'],lease));responses.append(response);send(process,response)
            done=read(process);assert done['op']=='done' and done['pid']==process.pid
            process.stdin.close();process.wait(timeout=3);stderr=process.stderr.read(65537)
            check('client_'+writer+'_native_edit_and_exit',response['status']=='COMMITTED'
                and process.returncode==0 and not stderr)
            (output/('client-'+writer+'.json')).write_text(json.dumps({'pid':process.pid,'exit_code':process.returncode,
                'done':done,'ticket':granted,'response':response},indent=2)+'\n',encoding='utf-8')
        check('handoff_increases_native_fence',grants[1]['lease']['fencing_epoch']>grants[0]['lease']['fencing_epoch'])
        check('expired_head_was_not_granted',a.writer_status('expire-first','expire-writer')['state']=='EXPIRED')
        check('reopened_host_client_retains_ticket_receipt',DurableBlenderSession(a.directory,host=owner).writer_status(
            'ticket-bob','bob')==grants[1])
        after=responses[-1]['native']['result']['after']
        check('exact_two_native_objects',[row['object_id'] for row in after['snapshot']['objects']]==['alice','bob'])
        old=Lease(**grants[0]['lease']);new=Lease(**grants[1]['lease'])
        late=command('late-alice','object.transform.set',after,{'object_id':'alice','location':[9,0,0],
            'rotation':[0,0,0],'scale':[1,1,1]})
        try:a.execute_bytes(late,old)
        except JournalError as error:stale=error.code=='STALE_LEASE'
        else:stale=False
        check('old_writer_rejected_before_intent',stale)
        try:owner.execute(late,lease={'fencing_epoch':old.fencing_epoch,'expires_ms':old.expires_ms})
        except HostError as error:stale_native=str(error)=='BLENDER_COMMAND_REJECTED'
        else:stale_native=False
        check('native_consumer_rejects_old_authenticated_fence',stale_native)
        check('stale_writer_did_not_change_native_scene',json.loads(b.execute_bytes(command('before-stop','scene.inspect'),new))['native']['result']==after)
        for index in range(MAX_WAITERS):b.request_writer('flood-'+str(index),'waiter-'+str(index),lease_ms=1000)
        try:a.request_writer('overflow','overflow-writer')
        except JournalError as error:bounded=error.code=='BLENDER_WRITER_QUEUE_FULL'
        else:bounded=False
        check('bounded_waiter_capacity_before_native_dispatch',bounded)
        started=time.monotonic();stopped=a.stop();elapsed=(time.monotonic()-started)*1000
        check('stop_priority_cancels_all_waiters',stopped=={'stopped':True,'public_ack':False} and elapsed<2000
            and all(b.writer_status('flood-'+str(index),'waiter-'+str(index))['state']=='CANCELED' for index in range(MAX_WAITERS)))
        try:b.pump_writers()
        except JournalError as error:no_grant=error.code=='BLENDER_WRITER_STOPPED'
        else:no_grant=False
        check('stop_prevents_any_new_grant_or_effect_request',no_grant
            and owner.result('before-stop')['result']==after)
        closed=owner.close();check('actual_gui_exit_and_zero_job',closed['actual_process_exit']=={'pid':owner.pid,'exit_code':0}
            and closed['wrapper_exit_code']==0 and closed['job']['zero_observed'] is True and closed['job']['active_count']==0)
        result={'passed':True,'checks':rows,'grants':grants,'responses':responses,'client_events':events,
            'client_pids':[p.pid for p in clients],'client_exit_codes':[p.returncode for p in clients],
            'stop_elapsed_ms':elapsed,'cleanup':closed,'source_files':sources(STUDIO),
            'public_ack':False,'candidate_only':True,'clients_are_synthetic_stdio_fixture':True}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_FIFO_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        for index,process in enumerate(clients):
            if process.poll() is None:process.kill();process.wait(timeout=3)
            tail=process.stderr.read(65537) if process.stderr is not None and not process.stderr.closed else b''
            (output/('client-%d-stderr.txt'%index)).write_bytes(tail)
            (output/('client-%d-exit.json'%index)).write_text(json.dumps({'pid':process.pid,'exit_code':process.returncode})+'\n',encoding='utf-8')
            for pipe in (process.stdin,process.stdout,process.stderr):
                if pipe is not None and not pipe.closed:pipe.close()
        if owner is not None:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--client',action='store_true');args=parser.parse_args()
    if args.client:return client()
    out=args.output.absolute()
    if args.frozen:return frozen(out,args.binary)
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
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_writer_fifo_probe.py'),
        '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
        cwd=snapshot,output=out,timeout=60,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())
