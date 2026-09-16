"""Fixed owned snapshot export; only launched by the trusted capped host."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent


def load(name):
    path=HERE/(name+'.py');spec=importlib.util.spec_from_file_location('_gt04_export_'+name,path)
    module=importlib.util.module_from_spec(spec);exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


def main():
    import bpy
    profile=load('export_profile');base=load('adapter')
    args=sys.argv[sys.argv.index('--')+1:]
    profile.need(len(args)==1,'EXPORT_FIXED_ARGUMENTS')
    root=Path(args[0]).absolute();manifest=root/'expected.json';source=root/'input.blend';target=root/'output.glb'
    for path in (root,*root.parents,manifest,source):
        profile.need(not path.is_symlink() and not getattr(path.lstat(),'st_file_attributes',0)&0x400,'EXPORT_REPARSE')
    profile.need(not target.exists() and 0<source.stat().st_size<=profile.MAX_BLEND_BYTES,'EXPORT_INPUT_OR_SLOT')
    expected=json.loads(manifest.read_bytes())
    profile.need(hashlib.sha256(source.read_bytes()).hexdigest()==expected['input_sha256'],'EXPORT_INPUT_HASH')
    profile.need(bpy.app.background and bpy.app.version[:3]==(5,2,1),'EXPORT_BACKGROUND_PIN')
    profile.need(bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)=={'FINISHED'},'EXPORT_OPEN_FAILED')
    admitted=profile.preflight(bpy);owner=base.FixtureAdapter();before=owner.inspect()
    profile.need(before['snapshot']==expected['snapshot'] and before['revision']==expected['revision'],'EXPORT_REOPEN_READBACK')
    result=bpy.ops.export_scene.gltf(filepath=str(target),check_existing=False,export_format='GLB',
        export_materials='NONE',export_animations=False,export_skins=False,export_morph=False,
        export_yup=True,export_normals=True,export_tangents=False,use_selection=False,use_active_scene=True,
        export_cameras=False,export_lights=False,export_extras=False,export_attributes=False,will_save_settings=False)
    profile.need(result=={'FINISHED'} and target.is_file() and 0<target.stat().st_size<=profile.MAX_GLB_BYTES,'EXPORT_NATIVE_OUTPUT')
    profile.need(owner.inspect()==before,'EXPORT_CHANGED_SOURCE_CONTEXT')
    report={'schema':'HH-BLENDER-EXPORT-RESULT-1','profile':admitted,'input_sha256':expected['input_sha256'],
        'scene_revision':before['revision'],'snapshot':before['snapshot'],'context':before['context'],
        'output_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'output_size_bytes':target.stat().st_size,
        'public_ack':False,'native_finished':True,'context_unchanged':True}
    (root/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('GT04_EXPORT_COMPLETE '+json.dumps(report),flush=True)


if __name__=='__main__':main()
