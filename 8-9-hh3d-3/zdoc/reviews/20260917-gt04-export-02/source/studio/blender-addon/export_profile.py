"""Strict internal box-only export admission. No arbitrary .blend authority."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import threading

MAX_BLEND_BYTES=8*1024*1024
MAX_GLB_BYTES=4*1024*1024


class ExportRejected(ValueError):pass


def need(value,code):
    if not value:raise ExportRejected(code)


def exporter_files(base):
    return {path.relative_to(base).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(base.rglob('*')) if path.is_file() and '__pycache__' not in path.parts}


def preflight(bpy):
    need(threading.current_thread() is threading.main_thread(),'EXPORT_MAIN_THREAD')
    need(bpy.app.version[:3]==(5,2,1),'EXPORT_BLENDER_PIN')
    need(not bpy.context.preferences.filepaths.use_scripts_auto_execute,'EXPORT_AUTOEXEC_ENABLED')
    lock=json.loads(Path(__file__).with_name('exporter.lock.json').read_bytes())
    need(sorted(bpy.context.preferences.addons.keys())==lock['factory_addons'],'EXPORT_ADDON_SET')
    for library in bpy.data.libraries:
        path=Path(bpy.path.abspath(library.filepath))
        need(path.is_file(),'EXPORT_MISSING_LIBRARY')
    need(not bpy.data.libraries,'EXPORT_LINKED_LIBRARY_UNSUPPORTED')
    for image in bpy.data.images:
        if image.source=='FILE' and not image.packed_file:
            need(Path(bpy.path.abspath(image.filepath)).is_file(),'EXPORT_MISSING_TEXTURE')
    for name in ('objects','meshes','scenes','materials','worlds','node_groups','armatures','shape_keys'):
        collection=getattr(bpy.data,name)
        need(len(collection)<=64,'EXPORT_DATABLOCK_CAP')
        for item in collection:
            animation=getattr(item,'animation_data',None)
            need(animation is None or not animation.drivers,'EXPORT_DRIVER_UNSUPPORTED')
    need(1<=len(bpy.data.objects)<=16 and len(bpy.data.scenes)==1,'EXPORT_OBJECT_CAP')
    need(not any(getattr(bpy.data,name) for name in ('materials','images','worlds','actions','node_groups',
        'armatures','cameras','lights','texts','libraries','sounds','movieclips')),'EXPORT_DEPENDENCY_UNSUPPORTED')
    need(bpy.context.mode=='OBJECT','EXPORT_OBJECT_MODE_REQUIRED')
    for obj in bpy.data.objects:
        need(obj.type=='MESH' and obj.parent is None and not obj.constraints and not obj.modifiers
             and obj.animation_data is None and obj.data.animation_data is None
             and obj.data.shape_keys is None and not obj.data.materials,'EXPORT_OBJECT_UNSUPPORTED')
        need((len(obj.data.vertices),len(obj.data.edges),len(obj.data.polygons))==(8,12,6),'EXPORT_MESH_CAP')
    import io_scene_gltf2
    base=Path(io_scene_gltf2.__file__).resolve().parent
    need(list(io_scene_gltf2.bl_info['version'])==lock['exporter_version']
         and exporter_files(base)==lock['files'],'EXPORTER_RELEASE_MISMATCH')
    return {'schema':'HH-BLENDER-BOX-EXPORT-PROFILE-1','objects':len(bpy.data.objects),
        'vertices':8*len(bpy.data.objects),'triangles':12*len(bpy.data.objects),
        'materials':0,'images':0,'bones':0,'clips':0,'libraries':0,'drivers':0,
        'exporter_version':lock['exporter_version'],'exporter_files_sha256':hashlib.sha256(
            json.dumps(lock['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        'public_ack':False}
