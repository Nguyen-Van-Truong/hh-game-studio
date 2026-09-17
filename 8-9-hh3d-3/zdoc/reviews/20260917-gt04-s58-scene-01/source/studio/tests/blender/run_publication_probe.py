"""One frozen protected .blend/GLB publication, lost reply and read-only reopen."""
import argparse
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
sys.dont_write_bytecode=True
STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent));sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_blender_ipc_probe import load,sources
from run_durable_session_probe import command

def native_reopen(output):
    import bpy
    from studio.host.blender.publication_state import sha
    expected=json.loads((output/'reopen-expected.json').read_bytes());path=Path(expected['path'])
    assert sha(path.read_bytes())==expected['sha256'] and bpy.app.background and bpy.app.version[:3]==(5,2,1)
    assert bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)=={'FINISHED'}
    profile=load(STUDIO/'blender-addon/export_profile.py');profile.preflight(bpy)
    adapter=load(STUDIO/'blender-addon/adapter.py');observed=adapter.FixtureAdapter().inspect()
    assert observed['snapshot']==expected['snapshot'] and observed['revision']==expected['revision']
    result={'passed':True,'snapshot':observed['snapshot'],'revision':observed['revision'],
        'checkpoint_sha256':expected['sha256'],'public_ack':False}
    (output/'reopened-native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('GT04_PUBLICATION_REOPEN '+json.dumps(result),flush=True);return 0

def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.publication_owner import BlenderPublicationOwner,model
    from studio.protocol.core import canonical_bytes
    from studio.host.core.custody_registry import pending_custody_cleanup
    from studio.host.core.private_events import pending_event_cleanup
    rows=[];gui=publisher=reopened=None
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_PUBLICATION_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    try:
        gui=BlenderUIHost(output,binary=binary,session_seconds=120)
        session=DurableBlenderSession(gui.directory/'journal',host=gui)
        lease=session.acquire_writer('publisher',ttl_ms=30000)
        def execute(key,op,state=None,payload=None):
            value=json.loads(session.execute_bytes(command(key,op,state,payload),lease))
            assert value['status']=='COMMITTED';return value['native']['result']
        initial=execute('initial','scene.inspect')
        box=execute('box','mesh.create_box',initial,{'object_id':'box','size':[1,2,3]})['after']
        material=execute('material','material.set_principled',box,{'object_id':'box','material_id':'copper',
            'base_color':[.7,.2,.1],'metallic':.6,'roughness':.35})['after']
        posed=execute('pose','object.transform.set',material,{'object_id':'box','location':[2,-3,4],
            'rotation':[.2,-.3,.4],'scale':[1,2,1]})['after']
        publisher=BlenderPublicationOwner.create(output,session=session)
        request={'schema':model.SCHEMA,'command_id':'publish','expected_revision':posed['revision'],
            'expected_context':posed['context']}
        head=publisher._head
        try:publisher.publish(dict(request,path='C:/foreign.blend'),lease)
        except model.PublicationError:path_denied=True
        else:path_denied=False
        check('foreign_path_rejected_before_intent_or_native_file',path_denied and publisher._head==head
            and not (gui.project/'export.blend').exists())
        invalid=dict(request,expected_context={'mode':'EDIT_MESH','active_id':'box','selected_ids':['box']})
        try:publisher.publish(invalid,lease)
        except model.PublicationError:mode_denied=True
        else:mode_denied=False
        check('unsupported_context_rejected_before_intent',mode_denied and publisher._head==head)
        lease=session.acquire_writer('publisher',ttl_ms=30000)
        append=publisher._append;fault={'armed':False,'fired':False}
        def drop_reply(kind,**fields):
            append(kind,**fields)
            if kind=='TERMINAL':
                fault.update(armed=True,fired=True,terminal_sha256=fields['response_sha256'])
                raise OSError('test cut after witnessed terminal before reply')
        with patch.object(publisher,'_append',drop_reply):
            try:publisher.publish(request,lease)
            except model.PublicationError as error:
                unknown=error.outcome_unknown;chain=[];current=error
                while current is not None:
                    chain.append({'type':type(current).__name__,'code':getattr(current,'code',None)})
                    current=current.__cause__
                (output/'reply-loss-or-failure.json').write_bytes(canonical_bytes({'fault':fault,'chain':chain}))
            else:unknown=False
        check('actual_terminal_reply_loss_is_reported_unknown',unknown and fault['fired'])
        response=publisher.lookup_bytes('publish');decoded=json.loads(response)
        check('lookup_recovers_exact_durable_committed_response',decoded['status']=='COMMITTED'
            and decoded['public_ack'] is False and model.sha(response)==fault['terminal_sha256'])
        before_retry=publisher._head;exports=len(list(gui.directory.glob('export-*')))
        check('duplicate_after_reply_loss_has_no_new_effect',publisher.publish(request,lease)==response
            and publisher._head==before_retry and len(list(gui.directory.glob('export-*')))==exports==1)
        try:publisher.publish(dict(request,expected_revision='sha256:'+'0'*64),lease)
        except model.PublicationError as error:conflict=error.code=='PUBLICATION_COMMAND_CONFLICT'
        else:conflict=False
        check('conflicting_duplicate_preserves_original_receipt',conflict and publisher.lookup_bytes('publish')==response)
        manifest,artifacts=publisher.read_selected()
        check('complete_protected_binary_manifest_closure',set(artifacts)==set(model.NAMES)
            and set(p.name for p in publisher.files.root.iterdir())=={'.writer','checkpoint.blend','scene.glb','manifest.json','active.json'}
            and manifest['external_inputs']==[] and manifest['snapshot']==posed['snapshot'])
        check('all_artifacts_exact_native_hashes',all(model.sha(raw)==manifest['artifacts'][name]['sha256']
            for name,raw in artifacts.items()) and manifest['native']['input_sha256']==model.sha(artifacts['checkpoint.blend']))
        check('native_ui_unchanged_after_publication',execute('after','scene.inspect')==posed)
        (output/'response.json').write_bytes(response)
        (output/'publication-manifest.json').write_bytes(canonical_bytes(manifest))
        (output/'custody.json').write_bytes(canonical_bytes(publisher.custody.record))
        def collect(events,row):return events+[json.loads(row.event)]
        _,events=publisher.log.fold([],collect);(output/'events.json').write_bytes(canonical_bytes(events))
        root_names={name:getattr(publisher,name).root.name for name in ('files','store','log')}
        info={'path':str(publisher.files.root/'checkpoint.blend'),'sha256':model.sha(artifacts['checkpoint.blend']),
            'snapshot':posed['snapshot'],'revision':posed['revision']}
        (output/'reopen-expected.json').write_bytes(canonical_bytes(info))
        storage_id=publisher.storage_id;publisher.close()
        check('managed_native_handles_closed_before_reopen',publisher._closed and not pending_event_cleanup()
            and not pending_custody_cleanup())
        reopened=BlenderPublicationOwner.reopen(storage_id)
        check('custody_reopen_exact_response_without_gui_replay',reopened.lookup_bytes('publish')==response
            and reopened.session is None and reopened.host is None and reopened._readonly is True)
        reopened_manifest,reopened_artifacts=reopened.read_selected()
        check('protected_readonly_reopen_exact_complete_bundle',reopened_manifest==manifest and reopened_artifacts==artifacts)
        check('readonly_duplicate_only_returns_original',reopened.publish(request,None)==response)
        reopened.close();closed=gui.close()
        check('actual_gui_exit_and_job_zero',closed['actual_process_exit']=={'pid':gui.pid,'exit_code':0}
            and closed['wrapper_exit_code']==0 and closed['job']['zero_observed'] is True and closed['job']['active_count']==0)
        runner=load(STUDIO/'build/bootstrap/run_fixture.py')
        process=runner.run_process([str(binary),'--background','--factory-startup','--disable-autoexec','--offline-mode',
            '--threads','1','--python-exit-code','17','--python',str(Path(__file__).resolve()),'--','--native-reopen',
            '--output',str(output)],cwd=STUDIO,output=output,timeout=25,label='reopen')
        check('native_protected_checkpoint_reopen_actual_exit',process['exit_code']==0 and process['wrapper_exit_code']==0
            and process['tree_verified'] is True)
        observed=json.loads((output/'reopened-native.json').read_bytes())
        check('native_published_mesh_transform_material_readback',observed['snapshot']==posed['snapshot']
            and observed['revision']==posed['revision'] and observed['checkpoint_sha256']==info['sha256'])
        result={'passed':True,'checks':rows,'public_ack':False,'formal_acceptance':False,'source_files':sources(STUDIO),
            'cleanup':closed,'reopen':process,'storage_id':storage_id,'roots':root_names,'fault':fault,
            'response_sha256':model.sha(response),'publication_source_schema':model.SCHEMA}
        (output/'native.json').write_bytes(canonical_bytes(result))
        print('GT04_PUBLICATION_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        for owner in (reopened,publisher,gui):
            if owner is not None:owner.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--native-reopen',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None);out=args.output.absolute()
    if args.native_reopen:return native_reopen(out)
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
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_publication_probe.py'),
        '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
        cwd=snapshot,output=out,timeout=90,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)

if __name__=='__main__':raise SystemExit(main())
