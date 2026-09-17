"""Frozen native opaque material edit/undo/checkpoint/reopen/export proof."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

STUDIO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(STUDIO.parent))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_blender_ipc_probe import load,sources
from run_durable_session_probe import command


def reopen_native(output):
    import bpy
    expected=json.loads((output/'checkpoint-expected.json').read_bytes())
    path=Path(expected['path']);raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==expected['sha256']
    assert bpy.app.background and bpy.app.version[:3]==(5,2,1)
    assert bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False,use_scripts=False)=={'FINISHED'}
    adapter=load(STUDIO/'blender-addon/adapter.py');owner=adapter.FixtureAdapter()
    observed=owner.inspect();assert observed['snapshot']==expected['snapshot'] and observed['revision']==expected['revision']
    assert len(observed['snapshot']['objects'])==1 and 'material' in observed['snapshot']['objects'][0]
    result={'passed':True,'snapshot':observed['snapshot'],'revision':observed['revision'],
        'checkpoint_sha256':expected['sha256'],'public_ack':False}
    (output/'checkpoint-reopened.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('GT04_MATERIAL_REOPEN '+json.dumps(result),flush=True)
    return 0


def frozen(output,binary):
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.export_job import ExportJob
    rows=[];owner=None
    def check(label,value):
        row={'label':label,'passed':value is True};rows.append(row)
        print('GT04_MATERIAL_CHECK '+json.dumps(row),flush=True)
        if value is not True:raise AssertionError(label)
    def execute(key,op,state=None,payload=None):
        row=owner.execute(command(key,op,state,payload))
        if row['state']!='COMPLETED':raise AssertionError((key,row))
        return row
    try:
        owner=BlenderUIHost(output,binary=binary)
        before=execute('initial','scene.inspect')['result']
        box=execute('create','mesh.create_box',before,{'object_id':'box','size':[1,2,3]})['result']['after']
        payload={'object_id':'box','material_id':'copper','base_color':[.7,.2,.1],'metallic':.6,'roughness':.35}
        request=command('material','material.set_principled',box,payload)
        first=owner.execute(request)
        check('native_material_create_complete',first['state']=='COMPLETED')
        material=first['result']['after'];observed=material['snapshot']['objects'][0]['material']
        check('native_closed_pbr_readback',observed['material_id']=='copper'
            and all(abs(a-b)<1e-6 for a,b in zip(observed['base_color'],[.7,.2,.1,1]))
            and abs(observed['metallic']-.6)<1e-6 and abs(observed['roughness']-.35)<1e-6)
        check('duplicate_material_has_original_receipt',owner.execute(request)==first)
        undone=execute('undo-material','history.undo',material)['result']['after']
        check('native_material_creation_undo',undone==box)
        redone=execute('redo-material','history.redo',box)['result']['after']
        check('native_material_creation_redo',redone==material)
        updated=execute('update-material','material.set_principled',material,
            dict(payload,base_color=[.1,.4,.8],metallic=.2,roughness=.8))['result']['after']
        check('native_material_update_changes_revision',updated['revision']!=material['revision'])
        check('native_material_update_undo',execute('undo-update','history.undo',updated)['result']['after']==material)
        check('native_material_update_redo',execute('redo-update','history.redo',material)['result']['after']==updated)
        posed=execute('pose','object.transform.set',updated,{'object_id':'box','location':[2,-3,4],
            'rotation':[.2,-.3,.4],'scale':[1,2,1]})['result']['after']
        check('transform_preserves_material',posed['snapshot']['objects'][0]['material']==updated['snapshot']['objects'][0]['material'])
        saved=execute('checkpoint','checkpoint.save',posed,{'slot':'checkpoint'})['result']
        expected={'path':str(owner.project/'checkpoint.blend'),'sha256':saved['artifact']['sha256'],
            'snapshot':posed['snapshot'],'revision':posed['revision']}
        (output/'checkpoint-expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
        export=owner.export_glb(command('export','export.prepare',posed,{'slot':'export'}))
        check('material_export_reopen_and_geometry_bound',export['completed'] is True
            and export['snapshot_geometry_bound'] is True and export['native']['snapshot']==posed['snapshot'])
        check('bounded_glb_material_readback',export['preflight']['materials']==1
            and export['preflight']['images']==0 and export['preflight']['extensions']==[]
            and abs(export['preflight']['meshes'][0]['material']['roughness']-.8)<1e-6)
        (output/'export.json').write_text(json.dumps(export,indent=2)+'\n',encoding='utf-8')
        admission=ExportJob(owner,owner.result('export')['result'],admission_probe=True).run()
        check('actual_hostile_material_grammar_rejected',admission['completed'] is True
            and len(admission['native']['admission_probe'])==14
            and all(row['passed'] is True for row in admission['native']['admission_probe']))
        (output/'admission.json').write_text(json.dumps(admission,indent=2)+'\n',encoding='utf-8')
        check('export_preserves_ui_snapshot',execute('after-export','scene.inspect')['result']==posed)
        closed=owner.close();check('gui_actual_exit_zero',closed['actual_process_exit']=={'pid':owner.pid,'exit_code':0}
            and closed['wrapper_exit_code']==0 and closed['job']['zero_observed'] is True)
        runner=load(STUDIO/'build/bootstrap/run_fixture.py')
        reopened=runner.run_process([str(binary),'--background','--factory-startup','--disable-autoexec','--offline-mode',
            '--threads','1','--python-exit-code','17','--python',str(Path(__file__).resolve()),'--','--reopen-native',
            '--output',str(output)],cwd=STUDIO,output=output,timeout=20,label='reopen')
        check('fresh_checkpoint_reopen_actual_exit',reopened['exit_code']==0 and reopened['wrapper_exit_code']==0
            and reopened['tree_verified'] is True)
        readback=json.loads((output/'checkpoint-reopened.json').read_bytes())
        check('fresh_checkpoint_mesh_transform_material_equal',readback['passed'] is True
            and readback['snapshot']==posed['snapshot'] and readback['revision']==posed['revision'])
        result={'passed':True,'checks':rows,'public_ack':False,'candidate_only':True,'source_files':sources(STUDIO),
            'cleanup':closed,'reopen':reopened,'checkpoint':saved}
        (output/'native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print('GT04_MATERIAL_COMPLETE '+json.dumps({'passed':True,'checks':len(rows)}),flush=True)
        return 0
    finally:
        if owner is not None:owner.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--frozen',action='store_true');parser.add_argument('--binary',type=Path)
    parser.add_argument('--reopen-native',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else None);out=args.output.absolute()
    if args.reopen_native:return reopen_native(out)
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
    host=owned.run_process([sys.executable,'-B',str(snapshot/'tests/blender/run_material_probe.py'),
        '--frozen','--output',str(out),'--binary',str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
        cwd=snapshot,output=out,timeout=90,label='native')
    value={'source_closure_sha256':closure,'unit':unit,'host':host,'candidate_only':True,'public_ack':False,
        'source_unchanged':sources(STUDIO)==original,'snapshot_unchanged':sources(snapshot)==original}
    (out/'capture.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8');print(json.dumps(value))
    return int(unit['exit_code']!=0 or host['exit_code']!=0)


if __name__=='__main__':raise SystemExit(main())
