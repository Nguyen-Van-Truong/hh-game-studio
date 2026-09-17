"""One fresh read-only GUI loads a verified checkpoint after clean producer exit."""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys
import time
sys.dont_write_bytecode=True
STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent));sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_blender_ipc_probe import load,sources
from run_durable_session_probe import command

def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost,HostError,source_files
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.publication_owner import BlenderPublicationOwner,model
    from studio.host.blender.recovery_owner import CheckpointRecoveryOwner
    from studio.protocol.core import canonical_bytes
    from studio.host.core.custody_registry import pending_custody_cleanup
    from studio.host.core.private_events import pending_event_cleanup
    rows=[];gui=publisher=reopened=recovery=failed_owner=None
    def write(name,value):
        with (output/name).open('xb') as stream:stream.write(canonical_bytes(value))
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_CHECKPOINT_RECOVERY_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    def denied(label,action,reason):
        try:action()
        except HostError as error:result=str(error)==reason
        else:result=False
        check(label,result)
    def closed(value,pid):
        return value['closed'] is True and value['actual_process_exit']=={'pid':pid,'exit_code':0}\
            and value['wrapper_exit_code']==0 and value['job']['zero_observed'] is True\
            and value['job']['active_count']==0 and value['job']['closed'] is True\
            and value['job']['handle_retained'] is False
    try:
        gui=BlenderUIHost(output,binary=binary,session_seconds=120)
        session=DurableBlenderSession(gui.directory/'journal',host=gui)
        lease=session.acquire_writer('publisher',ttl_ms=60000)
        def execute(key,op,state=None,payload=None):
            value=json.loads(session.execute_bytes(command(key,op,state,payload),lease))
            assert value['status']=='COMMITTED';return value['native']['result']
        initial=execute('initial','scene.inspect')
        box=execute('box','mesh.create_box',initial,{'object_id':'box','size':[1,2,3]})['after']
        copper=execute('material','material.set_principled',box,{'object_id':'box','material_id':'copper',
            'base_color':[.7,.2,.1],'metallic':.6,'roughness':.35})['after']
        scene=execute('pose','object.transform.set',copper,{'object_id':'box','location':[2,-3,4],
            'rotation':[.2,-.3,.4],'scale':[1,2,1]})['after']
        publisher=BlenderPublicationOwner.create(output,session=session)
        request={'schema':model.SCHEMA,'command_id':'publish','expected_revision':scene['revision'],
            'expected_context':scene['context']}
        response=publisher.publish(request,lease);manifest,artifacts=publisher.read_selected()
        check('current_source_protected_publication_committed',json.loads(response)['status']=='COMMITTED'
            and manifest['source_files']==source_files() and manifest['snapshot']==scene['snapshot'])
        storage_id=publisher.storage_id
        roots={key:getattr(publisher,key).root.name for key in ('files','store','log')}
        write('response.json',json.loads(response));write('publication-manifest.json',manifest)
        write('custody.json',publisher.custody.record);write('expected-scene.json',scene)
        def collect(events,row):return events+[json.loads(row.event)]
        _,events=publisher.log.fold([],collect);write('events.json',events)
        def graph():
            return {p.relative_to(output).as_posix():model.sha(p.read_bytes())
                for name in roots.values() for p in sorted((output/name).iterdir()) if p.is_file()}
        publisher.close();producer_cleanup=gui.close();before=graph()
        check('clean_predecessor_actual_exit_and_job_zero',closed(producer_cleanup,gui.pid))
        reopened=BlenderPublicationOwner.reopen(storage_id)
        check('readonly_reopen_exact_original_response',reopened.lookup_bytes('publish')==response
            and reopened._readonly is True and reopened.session is None and reopened.host is None)
        check('readonly_selected_bundle_exact',reopened.read_selected()==(manifest,artifacts))
        recovery=CheckpointRecoveryOwner.open(output,binary=binary,publication=reopened,predecessor=gui)
        native=recovery._host;observation=recovery.inspect()
        check('new_owned_gui_pid_and_generation',native.pid!=gui.pid and native._session!=gui._session)
        check('exact_revision_context_mesh_transform_and_material',observation['readback']==scene)
        check('verified_fixed_checkpoint_copy',model.sha((native.directory/'recovery-input/checkpoint.blend').read_bytes())
            ==model.sha(artifacts['checkpoint.blend']) and list(native.project.iterdir())==[])
        descriptor=json.loads(recovery.descriptor)
        check('authenticated_profile_source_and_pid_readback',native._recovery_observation['pid']==native.pid
            and native._recovery_observation['profile']==manifest['native']['profile']
            and native._recovery_observation['source_sha256']==model.sha(canonical_bytes(source_files()))
            and native._recovery_observation['descriptor_sha256']==model.sha(recovery.descriptor))
        check('readback_only_no_recovery_receipt_grant_or_ack',observation['live_scene_readback_verified'] is True
            and all(observation[key] is False for key in ('recovery_durable','new_edit_grant','undo_history_restored','public_ack')))
        edit=command('forbidden','object.transform.set',scene,{'object_id':'box','location':[9,9,9],
            'rotation':[0,0,0],'scale':[1,1,1]})
        counters={lane:channel.sent for lane,channel in native.channels.items()}
        denied('host_edit_denied',lambda:native.submit(edit),'BLENDER_RECOVERY_READONLY')
        denied('host_lease_denied',lambda:native.arm_lease({}),'BLENDER_RECOVERY_READONLY')
        check('host_denials_before_native_delivery',counters=={lane:channel.sent for lane,channel in native.channels.items()})
        denied('native_edit_denied_independently',lambda:native._ask('data','submit',{'command':edit,'ttl_ms':5000}),
            'BLENDER_COMMAND_REJECTED')
        denied('native_lease_denied_independently',lambda:native._ask('control','lease',{'lease':{}}),
            'BLENDER_COMMAND_REJECTED')
        read=command('lease-inspect','scene.inspect')
        denied('native_inspect_with_lease_denied',lambda:native._ask('data','submit',{'command':read,'ttl_ms':5000,'lease':{}}),
            'BLENDER_COMMAND_REJECTED')
        check('live_scene_exact_after_denied_mutations',recovery.inspect()['readback']==scene)
        check('original_retry_has_no_effect_or_receipt_change',reopened.publish(request,None)==response
            and len(list(gui.directory.glob('export-*')))==1 and not list(native.directory.glob('export-*')))
        write('recovery-observation.json',observation);write('recovery-descriptor.json',descriptor)
        started=time.monotonic();stop=recovery.stop();stop_ms=(time.monotonic()-started)*1000
        check('priority_native_stop',stop=={'stopped':True,'public_ack':False} and stop_ms<3000)
        recovery.close();consumer_cleanup=native._cleanup
        check('fresh_gui_actual_exit_and_job_zero',closed(consumer_cleanup,native.pid))
        check('original_receipt_still_exact_after_consumer',reopened.lookup_bytes('publish')==response)
        reopened.close()
        check('publication_graph_unchanged_after_consumer',before==graph())
        check('native_storage_owners_fully_closed',not pending_event_cleanup() and not pending_custody_cleanup())
        result={'passed':True,'checks':rows,'source_files':source_files(),'storage_id':storage_id,'roots':roots,
            'producer':{'directory':gui.directory.name,'pid':gui.pid,'generation':gui._session,'cleanup':producer_cleanup},
            'consumer':{'directory':native.directory.name,'pid':native.pid,'generation':native._session,'cleanup':consumer_cleanup},
            'observation':observation,'persisted_graph':before,'stop':stop,'stop_ms':stop_ms,
            'response_sha256':model.sha(response),'public_ack':False,'recovery_durable':False,
            'crashed_predecessor_supported':False,'formal_acceptance':False}
        write('native.json',result)
        print('GT04_CHECKPOINT_RECOVERY_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    except BaseException as error:
        cleanup_owner=getattr(error,'cleanup_owner',None)
        if type(cleanup_owner) in (CheckpointRecoveryOwner,BlenderUIHost,BlenderPublicationOwner):failed_owner=cleanup_owner
        chain=[];current=error
        while current is not None:
            chain.append({'type':type(current).__name__,'code':getattr(current,'code',str(current))})
            current=current.__cause__
        write('failure.json',{'checks':rows,'chain':chain,'public_ack':False})
        raise
    finally:
        cleanup_errors=[];seen=set()
        for owner in (failed_owner,recovery,reopened,publisher,gui):
            if owner is not None and id(owner) not in seen:
                seen.add(id(owner))
                try:owner.close()
                except BaseException as error:cleanup_errors.append({'type':type(owner).__name__,'error':str(error)})
        if cleanup_errors:
            write('cleanup-failure.json',cleanup_errors)
            raise AssertionError('owned cleanup remains held')

def process_passed(value):
    return value is not None and value['exit_code']==0 and value['wrapper_exit_code']==0\
        and value['timed_out'] is False and value['tree_verified'] is True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    args=parser.parse_args();out=args.output.absolute()
    if args.frozen:return frozen(out,args.binary)
    runner=load(STUDIO/'build/bootstrap/run_fixture.py');runner._reject_reparse_ancestors(out)
    out.mkdir(exist_ok=False);original=sources(STUDIO);snapshot=out/'source/studio'
    for name in original:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,dest)
    assert sources(snapshot)==original
    closure=runner.source_closure_sha256(original)
    (out/'source-closure.json').write_text(json.dumps({'files':original,'source_closure_sha256':closure},indent=2)+'\n',encoding='utf-8')
    owned=load(snapshot/'build/bootstrap/run_fixture.py')
    unit=owned.run_process([sys.executable,'-B','-m','unittest','discover','-s','tests/blender','-p','test_*.py','-v'],
        cwd=snapshot,output=out,timeout=30,label='unit')
    host=None
    if process_passed(unit):
        host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_checkpoint_recovery_probe.py'),
            '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
            cwd=snapshot,output=out,timeout=90,label='native')
    unit_log=(out/'unit-stderr.txt').read_text(encoding='utf-8')
    count=re.findall(r'^Ran (\d+) tests in [0-9.]+s$',unit_log,re.M)
    unit_completion=len(count)==1 and unit_log.rstrip().endswith('\nOK') and int(count[0])==150
    native_completion=False
    if process_passed(host) and (out/'native.json').is_file():
        report=json.loads((out/'native.json').read_bytes())
        markers=[json.loads(line.removeprefix('GT04_CHECKPOINT_RECOVERY_COMPLETE '))
            for line in (out/'native-stdout.txt').read_text(encoding='utf-8').splitlines()
            if line.startswith('GT04_CHECKPOINT_RECOVERY_COMPLETE ')]
        native_completion=report['passed'] is True and len(report['checks'])==22\
            and all(row['passed'] is True for row in report['checks'])\
            and markers==[{'passed':True,'checks':22}] and not (out/'native-stderr.txt').read_bytes()
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'unit_count':int(count[0]) if len(count)==1 else None,'unit_completion':unit_completion,
        'native_completion':native_completion,
        'recovery_durable':False,'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    value['passed']=process_passed(unit) and process_passed(host) and unit_completion and native_completion\
        and value['source_unchanged'] and value['snapshot_unchanged']
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(not value['passed'])

if __name__=='__main__':raise SystemExit(main())
