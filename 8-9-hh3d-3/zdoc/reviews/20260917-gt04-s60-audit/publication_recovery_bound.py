"""S60 bound native crash/Stop supplement over unchanged frozen runtime.

Fault hooks only pause/cut existing calls. No hook writes publication state or
advances custody. Every case has a new owned GUI/storage root and host deadline.
"""
import argparse
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from unittest.mock import patch
sys.dont_write_bytecode=True
from binding import STUDIO, verify
_execution_binding=verify()
sys.path.insert(0,str(STUDIO.parent));sys.path.insert(0,str(STUDIO/'tests/blender'))
from run_blender_ipc_probe import load,sources
from run_durable_session_probe import command

RUNTIME_SHA256=_execution_binding['runtime_sha256']
CRASH_CASES=('after_intent','before_selector','after_selector','before_terminal_witness','after_terminal_witness')
STOP_CASES=('stop_export','stop_before_selector','stop_after_selector','stop_after_terminal')
CASES=CRASH_CASES+STOP_CASES
CRASH_EXIT=86

def need(value,label):
    if not value:raise AssertionError(label)

def write(path,value):
    from studio.protocol.core import canonical_bytes
    need(not path.exists(),'evidence already exists '+path.name)
    # Native owners pin ancestor namespaces. Evidence is exclusive append-only;
    # cross-process readiness uses a separate marker written after this close.
    with path.open('xb') as stream:
        stream.write(canonical_bytes(value));stream.flush();os.fsync(stream.fileno())

def chain(error):
    result=[]
    while error is not None:
        result.append({'type':type(error).__name__,'code':getattr(error,'code',str(error))})
        error=error.__cause__
    return result

def setup(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost,source_files
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.publication_owner import BlenderPublicationOwner,model
    from studio.protocol.core import canonical_bytes
    verify()
    need(source_files()==_execution_binding['runtime_files'] and model.sha(canonical_bytes(source_files()))==RUNTIME_SHA256,'S60 complete runtime binding changed')
    gui=BlenderUIHost(output,binary=binary,session_seconds=120)
    try:
        session=DurableBlenderSession(gui.directory/'journal',host=gui)
        lease=session.acquire_writer('publisher',ttl_ms=60000)
        def execute(key,op,state=None,payload=None):
            reply=json.loads(session.execute_bytes(command(key,op,state,payload),lease))
            need(reply['status']=='COMMITTED','fixture native setup');return reply['native']['result']
        initial=execute('initial','scene.inspect')
        box=execute('box','mesh.create_box',initial,{'object_id':'box','size':[1,2,3]})['after']
        scene=execute('material','material.set_principled',box,{'object_id':'box','material_id':'copper',
            'base_color':[.7,.2,.1],'metallic':.6,'roughness':.35})['after']
        publisher=BlenderPublicationOwner.create(output,session=session)
        request={'schema':model.SCHEMA,'command_id':'publish','expected_revision':scene['revision'],
            'expected_context':scene['context']}
        return gui,session,publisher,request,lease,scene
    except BaseException:
        gui.close();raise

def image_state(publisher):
    """Read retained handles even when called within an append/custody hook."""
    from studio.host.core.custody import identity_value
    from studio.protocol.core import canonical_bytes
    from studio.host.blender import publication_state as model
    artifacts={}
    for name in ('checkpoint.blend','scene.glb','manifest.json','active.json'):
        if (publisher.files.root/name).exists():
            version,raw=publisher.files.read(name)
            artifacts[name]={'sha256':model.sha(raw),'identity':identity_value(version.identity)}
    actual_head=publisher.log._index[-1][2]
    stream=publisher.log._read_at(0,actual_head.size)
    return {'custody':publisher.custody.record,'phase':publisher._state['phase'],
        'state':json.loads(canonical_bytes(publisher._state)),'artifacts':artifacts,
        'event_head':{'sequence':actual_head.sequence,'sha256':actual_head.sha256,'size':actual_head.size},
        'events_sha256':model.sha(stream),'public_ack':False}

def crash_child(output,binary,case):
    if sys.stdin.buffer.readline(16)!=b'START\n':return 125
    gui,session,publisher,request,lease,scene=setup(output,binary)
    def cut():
        image=image_state(publisher)
        write(output/'ready.json',{'case':case,'host_pid':os.getpid(),'gui_pid':gui.pid,
            'gui_wrapper_pid':gui._process.pid,'gui_directory':gui.directory.name,'request':request,
            'scene':scene,'storage_id':publisher.storage_id,'image':image,'public_ack':False})
        write(output/'ready-complete.json',{'case':case,'host_pid':os.getpid(),'complete':True})
        if sys.stdin.buffer.readline(16)!=b'CRASH\n':os._exit(125)
        os._exit(CRASH_EXIT)  # Real process death: no Python cleanup or publication response.
    append=publisher._append;create=publisher.files.create_new;persist=publisher.custody.persist_binding
    def append_hook(kind,**fields):
        result=append(kind,**fields)
        if (case=='after_intent' and kind=='INTENT') or (case=='before_selector' and kind=='SELECTING'):cut()
        return result
    def create_hook(name,raw):
        result=create(name,raw)
        if case=='after_selector' and name=='active.json':cut()
        return result
    def witness_hook(binding):
        terminal=binding.witnessed.sequence==6
        if case=='before_terminal_witness' and terminal:cut()
        result=persist(binding)
        if case=='after_terminal_witness' and terminal:cut()
        return result
    try:
        with patch.object(publisher,'_append',append_hook),patch.object(publisher.files,'create_new',create_hook),\
                patch.object(publisher.custody,'persist_binding',witness_hook):
            publisher.publish(request,lease)
        raise AssertionError('crash hook not reached')
    finally:
        publisher.close();gui.close()

def kernel_api():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    for name,args,result in (
        ('OpenProcess',[w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
        ('WaitForSingleObject',[w.HANDLE,w.DWORD],w.DWORD),
        ('GetExitCodeProcess',[w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL),
        ('CloseHandle',[w.HANDLE],w.BOOL)):
        function=getattr(kernel,name);function.argtypes,function.restype=args,result
    return kernel

def persisted_graph(output,image):
    from studio.host.blender import publication_state as model
    graph={}
    for key in ('files','blobs','events'):
        root=output/Path(image['custody'][key]['path']).name
        for path in sorted(root.iterdir()):
            if path.is_file():graph[path.relative_to(output).as_posix()]=model.sha(path.read_bytes())
    return graph

def reopen_proof(output,ready):
    from studio.host.blender.publication_owner import BlenderPublicationOwner,model
    from studio.host.core.custody_registry import pending_custody_cleanup
    from studio.host.core.private_events import pending_event_cleanup
    from studio.protocol.core import canonical_bytes
    before=persisted_graph(output,ready['image']);owner=None;case=ready['case']
    try:
        try:owner=BlenderPublicationOwner.reopen(ready['storage_id'])
        except model.PublicationError as error:
            failure=chain(error)
            need(case=='before_terminal_witness' and error.outcome_unknown
                and any(row['code']=='EVENT_CUSTODY_BINDING_MISMATCH' for row in failure),
                'unexpected readonly reopen failure '+str(failure))
            error.cleanup_owner.close()
            result={'status':'HELD','response':None,'failure':failure,'public_ack':False}
        else:
            need(case!='before_terminal_witness','unwitnessed suffix falsely admitted')
            raw=owner.lookup_bytes('publish');response=json.loads(raw)
            committed=case in ('after_terminal_witness','stop_after_terminal')
            need(response['status']==('COMMITTED' if committed else 'UNKNOWN') and response['public_ack'] is False,
                'recovered response phase')
            need(owner._readonly and owner.host is None and owner.session is None,'readonly no GUI authority')
            need(owner.publish(ready['request'],None)==raw and owner.lookup_bytes('publish')==raw,'exact retry without effect')
            result={'status':response['status'],'response':response,'response_sha256':model.sha(raw),
                'readonly':True,'retry_exact':True,'public_ack':False}
            if committed:
                manifest,artifacts=owner.read_selected()
                need(manifest['snapshot']==ready['scene']['snapshot'] and manifest['scene_revision']==ready['scene']['revision']
                    and response['live_scene_recovered'] is False,'selected exact last committed checkpoint')
                need(all(model.sha(data)==ready['image']['artifacts'][name]['sha256'] for name,data in artifacts.items()),
                    'committed artifact hash unchanged')
                terminal=owner._state['terminal'];need(raw==canonical_bytes(terminal['response']),'exact witnessed response bytes')
                result.update(manifest_sha256=model.sha(canonical_bytes(manifest)),artifacts={name:model.sha(data) for name,data in artifacts.items()})
            else:
                try:owner.read_selected()
                except model.PublicationError as error:need(error.code=='PUBLICATION_NOT_COMMITTED','incomplete selected error')
                else:raise AssertionError('incomplete prefix exposed committed selection')
            write(output/'recovered-response.json',response)
    finally:
        if owner is not None:owner.close()
    need(not pending_custody_cleanup() and not pending_event_cleanup(),'reopen leaked native owner')
    after=persisted_graph(output,ready['image']);need(before==after,'readonly recovery modified bytes or replayed effect')
    result.update(persisted_graph=after,bytes_unchanged=True,live_scene_recovered=False)
    write(output/'recovery.json',result);return result

def observe_crash(output,binary,case):
    from studio.host.blender.ui_host import cli_job
    kernel=kernel_api();handles=[];process=job=None;ready=None;result={'case':case,'passed':False,'public_ack':False}
    with (output/'child-stdout.txt').open('xb') as stdout,(output/'child-stderr.txt').open('xb') as stderr:
        try:
            process=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--crash-child',case,
                '--output',str(output),'--binary',str(binary)],stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW,cwd=STUDIO)
            job=cli_job.create(process);process.stdin.write(b'START\n');process.stdin.flush()
            deadline=time.monotonic()+35
            while not (output/'ready-complete.json').exists():
                need(process.poll() is None and time.monotonic()<deadline,'owned crash child ready deadline')
                time.sleep(.02)
            ready=json.loads((output/'ready.json').read_bytes());need(ready['host_pid']==process.pid and ready['case']==case,'ready owner binding')
            observed=[]
            for name in ('gui_pid','gui_wrapper_pid'):
                handle=kernel.OpenProcess(0x1000|0x100000,False,ready[name]);need(handle,'native process handle')
                handles.append(handle);need(kernel.WaitForSingleObject(handle,0)==258,'exact native child live before host death')
                observed.append({'kind':name,'pid':ready[name],'live_wait_before':258})
            process.stdin.write(b'CRASH\n');process.stdin.flush();process.wait(timeout=8)
            need(process.returncode==CRASH_EXIT,'actual host exit at requested cut')
            for row,handle in zip(observed,handles):
                need(kernel.WaitForSingleObject(handle,5000)==0,'owned child orphan after host death')
                code=w.DWORD();need(kernel.GetExitCodeProcess(handle,ctypes.byref(code)),'native child actual exit')
                row.update(dead_wait_after=0,actual_exit_code=code.value)
            deadline=time.monotonic()+3
            while job.active_count()!=0 and time.monotonic()<deadline:time.sleep(.02)
            need(job.active_count()==0,'crash observer Job not empty')
            result.update(host_pid=process.pid,host_exit_code=process.returncode,processes=observed,job_before_close=job.snapshot())
            image=ready['image'];selector='active.json' in image['artifacts'];witness=image['custody']['events']['binding']['witnessed']
            expected={'after_intent':('INTENT',False,3,3),'before_selector':('SELECTING',False,5,5),
                'after_selector':('SELECTING',True,5,5),'before_terminal_witness':('SELECTING',True,6,5),
                'after_terminal_witness':('SELECTING',True,6,6)}[case]
            need((image['phase'],selector,image['event_head']['sequence'],witness['sequence'])==expected,'cut phase/selector/witness evidence')
            stdout.flush();stderr.flush()
            need(not (output/'child-stderr.txt').read_bytes(),'unexpected crash child stderr')
            result['recovery']=reopen_proof(output,ready);result['passed']=True
        except BaseException as error:
            result['failure']=chain(error);raise
        finally:
            if job is not None:job.close();result['job_closed']=job.snapshot()
            if process is not None:
                if process.poll() is None:process.kill();process.wait(timeout=5)
                result['observed_host_exit_code']=process.returncode
                if process.stdin and not process.stdin.closed:process.stdin.close()
            for handle in handles:need(kernel.CloseHandle(handle),'crash observer CloseHandle')
            write(output/'observed.json',result)
    return result

def stop_case(output,binary,case):
    from studio.host.blender import publication_owner as publication
    gui=session=publisher=None;thread=stopper=None;release=threading.Event();reached=threading.Event();native_stopped=threading.Event()
    kernel=kernel_api();export_handle=None
    replies=[];errors=[];stop_replies=[];stop_errors=[];observed={'case':case,'public_ack':False,'passed':False}
    try:
        gui,session,publisher,request,lease,scene=setup(output,binary)
        append=publisher._append;create=publisher.files.create_new;stop=session.stop;export_type=publication.ExportJob
        def gate():
            reached.set();need(release.wait(8),'Stop phase gate deadline')
        def append_hook(kind,**fields):
            result=append(kind,**fields)
            if (case=='stop_before_selector' and kind=='STAGED') or (case=='stop_after_terminal' and kind=='TERMINAL'):gate()
            return result
        def create_hook(name,raw):
            result=create(name,raw)
            if case=='stop_after_selector' and name=='active.json':gate()
            return result
        def stop_hook():
            result=stop();native_stopped.set();return result
        def export_factory(*args,**kwargs):return export_type(*args,**kwargs,diagnostic='pause') if case=='stop_export' else export_type(*args,**kwargs)
        def publish():
            try:replies.append(publisher.publish(request,lease))
            except BaseException as error:errors.append(error)
        def stop_publish():
            try:stop_replies.append(publisher.stop())
            except BaseException as error:stop_errors.append(error)
        with patch.object(publisher,'_append',append_hook),patch.object(publisher.files,'create_new',create_hook),\
                patch.object(session,'stop',stop_hook),patch.object(publication,'ExportJob',export_factory):
            thread=threading.Thread(target=publish);thread.start()
            if case=='stop_export':
                deadline=time.monotonic()+25
                while True:
                    job=publisher._job
                    if job is not None and (job.directory/'fault-ready.json').exists():break
                    need(thread.is_alive() and time.monotonic()<deadline,'paused export reached native preflight');time.sleep(.02)
                ready=json.loads((job.directory/'fault-ready.json').read_bytes())
                actual=json.loads((job.directory/'process-start.json').read_bytes())
                need(ready['pid']==actual['pid'] and ready['phase']=='validated-before-export','native pause identity')
                observed['export_ready']=ready
                export_handle=kernel.OpenProcess(0x1000|0x100000,False,ready['pid'])
                need(export_handle and kernel.WaitForSingleObject(export_handle,0)==258,'exact native export alive before Stop')
                observed['export_process']={'pid':ready['pid'],'live_wait_before':258}
            else:need(reached.wait(25),'publication Stop phase reached')
            began=time.monotonic();stopper=threading.Thread(target=stop_publish);stopper.start()
            need(native_stopped.wait(3),'priority native Stop blocked by publication lock')
            observed['native_stop_ms']=(time.monotonic()-began)*1000
            release.set();thread.join(8);stopper.join(8)
            observed['stop_settled_ms']=(time.monotonic()-began)*1000
            need(not thread.is_alive() and not stopper.is_alive() and not stop_errors,'publication Stop drain failed')
            need(stop_replies==[{'stopped':True,'public_ack':False}] and observed['native_stop_ms']<3000,'native Stop result')
        raw=publisher.lookup_bytes('publish');response=json.loads(raw);committed=case=='stop_after_terminal'
        need(response['status']==('COMMITTED' if committed else 'UNKNOWN') and response['public_ack'] is False,'Stop durable outcome')
        need((len(replies)==1 and not errors and replies[0]==raw) if committed else
            (not replies and len(errors)==1 and getattr(errors[0],'outcome_unknown',False)),'Stop caller outcome')
        need(publisher._state['stopped'] is True,'durable publication Stop')
        image=image_state(publisher);need(('active.json' in image['artifacts']) is (case in ('stop_after_selector','stop_after_terminal')),'Stop selector cut')
        need(image['phase']==({'stop_export':'INTENT','stop_before_selector':'STAGED','stop_after_selector':'SELECTING','stop_after_terminal':'TERMINAL'}[case]),'exact stopped phase')
        need((image['state'].get('terminal') is not None) is committed,'terminal witness required for committed reply')
        need(publisher._held is (not committed),'incomplete effect held without replay')
        if case=='stop_export':
            report=json.loads((publisher._job.directory/'host-result.json').read_bytes())
            need(report['completed'] is False and report['failure']=='EXPORT_CANCELLED'
                and report['job']['zero_observed'] is True and report['job']['active_count']==0
                and not (publisher._job.directory/'output.glb').exists(),'Stop export drain/no artifact')
            need(kernel.WaitForSingleObject(export_handle,1000)==0,'exact native export terminated by Stop')
            actual_exit=w.DWORD();need(kernel.GetExitCodeProcess(export_handle,ctypes.byref(actual_exit)),'native export exit capture')
            observed['export_process'].update(dead_wait_after=0,actual_exit_code=actual_exit.value)
            observed['export_result']=report
        ready={'case':case,'request':request,'scene':scene,'storage_id':publisher.storage_id,'image':image}
        write(output/'ready.json',ready);publisher.close();closed=gui.close()
        need(closed['job']['zero_observed'] is True and closed['job']['active_count']==0
            and closed['actual_process_exit']=={'pid':gui.pid,'exit_code':0},'Stop GUI actual exit')
        observed.update(passed=True,stop=stop_replies[0],response=response,errors=[chain(error) for error in errors],
            cleanup=closed,recovery=reopen_proof(output,ready))
        return observed
    except BaseException as error:
        observed['failure']=chain(error);raise
    finally:
        release.set()
        if publisher is not None and publisher._job is not None:publisher._job.request_stop()
        for worker in (thread,stopper):
            if worker is not None:worker.join(8)
        if publisher is not None:publisher.close()
        if gui is not None:gui.close()
        if export_handle is not None:need(kernel.CloseHandle(export_handle),'Stop observer CloseHandle')
        write(output/'observed.json',observed)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--binary',type=Path);parser.add_argument('--frozen-case',choices=CASES)
    parser.add_argument('--crash-child',choices=CRASH_CASES);parser.add_argument('--case',choices=CASES,action='append')
    args=parser.parse_args();output=args.output.absolute()
    if args.crash_child:return crash_child(output,args.binary,args.crash_child)
    if args.frozen_case:
        result=(observe_crash if args.frozen_case in CRASH_CASES else stop_case)(output,args.binary,args.frozen_case)
        print('GT04_PUBLICATION_RECOVERY '+json.dumps({'case':args.frozen_case,'passed':result['passed'],'public_ack':False}),flush=True)
        return 0
    runner=load(STUDIO/'build/bootstrap/run_fixture.py');runner._reject_reparse_ancestors(output)
    output.mkdir(exist_ok=False);original=sources(STUDIO);snapshot=output/'source/studio'
    for name in original:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,dest)
    need(sources(snapshot)==original,'frozen copy differs');closure=runner.source_closure_sha256(original)
    write(output/'source-closure.json',{'files':original,'source_closure_sha256':closure,'runtime_sha256':RUNTIME_SHA256})
    owned=load(snapshot/'build/bootstrap/run_fixture.py');cases=args.case or list(CASES)
    need(len(set(cases))==len(cases),'duplicate case');runs=[]
    for case in cases:
        out=output/case;out.mkdir()
        record=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_publication_recovery_probe.py'),
            '--frozen-case',case,'--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
            cwd=snapshot,output=out,timeout=60,label='native')
        runs.append({'case':case,'process':record});write(output/(case+'-capture.json'),runs[-1])
        if record['exit_code']!=0 or record['wrapper_exit_code']!=0 or record['timed_out'] or not record['tree_verified']:break
    result={'source_closure_sha256':closure,'runtime_sha256':RUNTIME_SHA256,'runs':runs,'requested_cases':cases,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original,
        'passed':len(runs)==len(cases) and all(row['process']['exit_code']==0 and row['process']['wrapper_exit_code']==0
            and row['process']['tree_verified'] and not row['process']['timed_out'] for row in runs),
        'public_ack':False,'live_scene_recovered':False,'formal_acceptance':False}
    write(output/'capture.json',result);print(json.dumps(result));return int(not result['passed'])

if __name__=='__main__':raise SystemExit(main())
