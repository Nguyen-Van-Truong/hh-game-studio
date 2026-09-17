"""One-shot pinned defaults inspection, diagnostic only."""
import json
from pathlib import Path
import sys

if '--native' in sys.argv:
    import bpy
    material=bpy.data.materials.new('HH_DEFAULT_INSPECTION');material.use_nodes=True
    shader=next(node for node in material.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
    def value(socket):
        item=getattr(socket,'default_value',None)
        return list(item) if hasattr(item,'__len__') and not isinstance(item,str) else item
    result={'version':list(bpy.app.version),'inputs':{socket.name:value(socket) for socket in shader.inputs},
        'shader_properties':{key:getattr(shader,key) for key in ('distribution','subsurface_method')},
        'material_properties':{key:getattr(material,key) for key in ('surface_render_method','use_backface_culling')},
        'diagnostic_only':True}
    print('HH_MATERIAL_DEFAULTS '+json.dumps(result),flush=True)
else:
    from run_blender_ipc_probe import load,STUDIO
    runner=load(STUDIO/'build/bootstrap/run_fixture.py')
    output=Path(sys.argv[1]).absolute();output.mkdir(exist_ok=False)
    row=runner.run_process([str(STUDIO/'.local/tooling/blender-5.2.1-windows-x64/blender.exe'),
        '--background','--factory-startup','--disable-autoexec','--offline-mode','--threads','1',
        '--python-exit-code','17','--python',str(Path(__file__).resolve()),'--','--native'],
        cwd=STUDIO,output=output,timeout=20,label='defaults')
    print(json.dumps(row))
    raise SystemExit(int(row['exit_code']!=0))
