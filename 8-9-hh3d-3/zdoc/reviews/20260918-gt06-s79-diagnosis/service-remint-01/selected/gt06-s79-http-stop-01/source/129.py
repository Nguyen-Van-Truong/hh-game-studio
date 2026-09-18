"""Pinned background-only original fixture producer. No foreign-file intake.

Host owns process/ACL/resource limits. Arguments after --: empty staging root,
then baseline|edited. Every filename and supported operation is fixed here.
"""
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import sys
import threading

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1]
spec = importlib.util.spec_from_file_location('gt05_producer_contract', HERE/'contract.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def load_json(path):
    raw = path.read_bytes()
    c.need(len(raw) <= 256*1024, 'SOURCE_JSON_CAP')
    def pairs(rows):
        result = {}
        for key, value in rows:
            c.need(key not in result, 'SOURCE_DUPLICATE_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(c.ProducerRejected('SOURCE_NONFINITE')))


def pins(bpy):
    c.need(threading.current_thread() is threading.main_thread(), 'MAIN_THREAD_REQUIRED')
    c.need(bpy.app.background and bpy.app.version[:3] == (5, 2, 1), 'PINNED_BACKGROUND_REQUIRED')
    c.need(not bpy.context.preferences.filepaths.use_scripts_auto_execute, 'AUTOEXEC_DISABLED_REQUIRED')
    toolchain = load_json(STUDIO/'toolchain.lock.json')
    binary = Path(bpy.app.binary_path)
    c.need(c.file_sha(binary) == toolchain['blender']['executable_sha256'], 'BINARY_PIN')
    lock = load_json(STUDIO/'blender-addon/exporter.lock.json')
    import io_scene_gltf2
    base = Path(io_scene_gltf2.__file__).resolve().parent
    actual = {p.relative_to(base).as_posix(): c.sha(p.read_bytes())
              for p in sorted(base.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    c.need(actual == lock['files'] and list(io_scene_gltf2.bl_info['version']) == lock['exporter_version'], 'EXPORTER_PIN')
    c.need(sorted(bpy.context.preferences.addons.keys()) == lock['factory_addons'], 'ADDON_PIN')
    props = bpy.ops.export_scene.gltf.get_rna_type().properties
    c.need(all(key in props for key in c.EXPORT_SETTINGS), 'EXPORT_SETTINGS_RNA')
    files = [p for p in HERE.glob('*.py')]
    files += [STUDIO/name for name in ('fixtures/assets-src/fixture-source.json',
        'tests/asset-profile.json', 'contracts/naming-convention-v1.md', 'pipeline/naming.py',
        'toolchain.lock.json', 'blender-addon/exporter.lock.json')]
    source = {p.relative_to(STUDIO).as_posix(): c.sha(p.read_bytes()) for p in sorted(files)}
    return {'source_files': source, 'source_sha256': c.digest(source),
        'blender_version': bpy.app.version_string, 'blender_binary_sha256': toolchain['blender']['executable_sha256'],
        'python_version': sys.version.split()[0], 'exporter_version': lock['exporter_version'],
        'exporter_files_sha256': c.digest(actual), 'exporter_file_count': len(actual),
        'profile_sha256': source['tests/asset-profile.json'],
        'naming_sha256': source['contracts/naming-convention-v1.md'],
        'toolchain_sha256': source['toolchain.lock.json'], 'settings_sha256': c.digest(c.EXPORT_SETTINGS)}


def mesh(bpy, name, parts, material, *, divisions=1, rig=None, asset=None, role='render', lod=None, geometry=None):
    vertices, faces, weights = c.box_geometry(parts, divisions) if geometry is None else geometry
    data = bpy.data.meshes.new(name+'_mesh')
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    data.materials.append(material)
    uv = data.uv_layers.new(name='uv_main')
    for poly in data.polygons:
        for i, loop in enumerate(poly.loop_indices):
            uv.data[loop].uv = ((0,0),(1,0),(1,1),(0,1))[i]
    if rig is not None:
        modifier = obj.modifiers.new('fixture_skin', 'ARMATURE')
        modifier.object = rig
        for bone in sorted(set(weights)):
            group = obj.vertex_groups.new(name=bone)
            group.add([i for i, value in enumerate(weights) if value == bone], 1.0, 'REPLACE')
    obj['asset_id'], obj['role'] = asset, role
    if lod is not None: obj['lod'] = lod
    return obj


def material(bpy, name, color, metallic=0.0, roughness=.6):
    result = bpy.data.materials.new(name)
    c.need(result.node_tree is not None, 'MATERIAL_NODE_TREE')
    result.diffuse_color = (*color, 1)
    result.metallic, result.roughness = metallic, roughness
    result.use_backface_culling = True
    bsdf = next(n for n in result.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    return result


def image(bpy, name, pixels, *, color_space, staging):
    c.need(name in c.TEXTURE_BINDINGS.values(), 'FIXED_IMAGE_NAME')
    raw = c.png_rgba8(pixels)
    scratch = staging/(name+'.png')
    with scratch.open('xb') as stream: stream.write(raw)
    result = bpy.data.images.load(str(scratch),check_existing=False)
    result.name = name
    result.colorspace_settings.name = color_space
    result.pack()
    result.filepath_raw = ''
    c.need(result.packed_file is not None and bytes(result.packed_file.data)==raw and result.filepath == ''
           and result.source=='FILE' and not result.is_dirty, 'PACKED_IMAGE_REQUIRED')
    c.need(scratch.read_bytes()==raw and scratch.is_file() and not scratch.is_symlink(), 'SCRATCH_IDENTITY')
    scratch.unlink()
    return result


def crate_material(bpy, staging):
    mat = material(bpy, 'mat_fixture_crate', (1,1,1), metallic=1, roughness=1)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next(n for n in nodes if n.type == 'BSDF_PRINCIPLED')
    colors = [(.9,.28,.08,1) if (x+y)%2 else (.08,.35,.55,1) for y in range(4) for x in range(4)]
    base = image(bpy, 'img_fixture_base', colors, color_space='sRGB',staging=staging)
    normal = image(bpy, 'img_fixture_normal', [(.5,.5,1,1)]*16, color_space='Non-Color',staging=staging)
    orm = image(bpy, 'img_fixture_orm', [(1,.55,.3,1)]*16, color_space='Non-Color',staging=staging)
    textures = {}
    for semantic, img in (('base_color',base),('normal',normal),('metallic_roughness',orm)):
        texture = nodes.new('ShaderNodeTexImage')
        texture.image = img
        texture.interpolation = 'Closest'
        texture.extension = 'REPEAT'
        textures[semantic] = texture
    links.new(textures['base_color'].outputs['Color'], bsdf.inputs['Base Color'])
    normal_node = nodes.new('ShaderNodeNormalMap')
    normal_node.inputs['Strength'].default_value = 1
    links.new(textures['normal'].outputs['Color'], normal_node.inputs['Color'])
    links.new(normal_node.outputs['Normal'], bsdf.inputs['Normal'])
    separate = nodes.new('ShaderNodeSeparateColor')
    separate.mode = 'RGB'
    links.new(textures['metallic_roughness'].outputs['Color'], separate.inputs['Color'])
    links.new(separate.outputs['Green'], bsdf.inputs['Roughness'])
    links.new(separate.outputs['Blue'], bsdf.inputs['Metallic'])
    return mat


def make_rig(bpy):
    data = bpy.data.armatures.new(c.RIG+'_data')
    rig = bpy.data.objects.new(c.RIG, data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for name, parent, head, tail in c.BONES:
        bone = data.edit_bones.new(name)
        bone.head, bone.tail = head, tail
        if parent: bone.parent = data.edit_bones[parent]
        bone.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')
    rig['asset_id'], rig['role'] = 'chr_fixture_avatar', 'rig'
    return rig


def make_actions(bpy, rig):
    from io_scene_gltf2.blender.com.data_path import get_channelbag_for_slot
    rig.animation_data_create()
    for clip in c.CLIPS:
        action = bpy.data.actions.new(clip)
        action.use_fake_user = True
        rig.animation_data.action = action
        for frame in c.FRAMES:
            for name, angles in c.pose_angles(clip, frame).items():
                bone = rig.pose.bones[name]
                bone.rotation_mode = 'XYZ'
                bone.rotation_euler = angles
                bone.keyframe_insert(data_path='rotation_euler', frame=frame, group=name)
        action.use_frame_range = True
        action.frame_start, action.frame_end = 0, 30
        slot = rig.animation_data.action_slot
        bag = get_channelbag_for_slot(action, slot)
        c.need(bag is not None and len(bag.fcurves) == 3*len(c.BONES), 'ANIMATION_CHANNELS')
        for curve in bag.fcurves:
            for key in curve.keyframe_points: key.interpolation = 'LINEAR'
        action['fixture_loop'], action['fixture_root_motion'] = True, 'in_place'
    rig.animation_data.action = bpy.data.actions['idle']
    rig.animation_data.action_slot = bpy.data.actions['idle'].slots[0]
    bpy.context.scene.frame_set(0)


def generate(bpy, source, variant, staging):
    c.need(len(bpy.data.scenes) == 1 and not bpy.data.filepath, 'FRESH_FACTORY_REQUIRED')
    for obj in list(bpy.data.objects): bpy.data.objects.remove(obj, do_unlink=True)
    for name in ('meshes','cameras','lights','materials','images','worlds','brushes'):
        for value in list(getattr(bpy.data,name)): getattr(bpy.data,name).remove(value)
    scene = bpy.context.scene
    scene.name = 'gt05_fixture'
    scene.unit_settings.system, scene.unit_settings.scale_length = 'METRIC', 1
    scene.render.fps, scene.render.fps_base = c.FPS, 1
    scene.frame_start, scene.frame_end = 0, 30
    bpy.context.preferences.filepaths.save_version = 0
    colors = {'mat_axis_cube':(.7,.72,.75), 'mat_axis_x':(.8,.04,.025),
              'mat_axis_y':(.035,.6,.09), 'mat_axis_z':(.025,.18,.85),
              'mat_fixture_skin':(.7,.4,.22), 'mat_fixture_cloth':(.045,.22,.27)}
    mats = {name: material(bpy,name,color) for name,color in colors.items()}
    mats['mat_fixture_crate'] = crate_material(bpy,staging)
    axis = 'env_fixture_axis_cube'
    mesh(bpy,axis+'_lod0',[((-2,0,.5),(1,1,1),None)],mats['mat_axis_cube'],asset=axis,lod=0)
    mesh(bpy,axis+'_nav',[((0,0,-.025),(6,4,.05),None)],mats['mat_axis_cube'],asset=axis,role='nav')
    # Outward-wound arrow points distinguish positive axes geometrically.
    for suffix in ('x','y','z'):
        asset='env_fixture_axis_'+suffix
        mesh(bpy,asset+'_lod0',[],mats['mat_axis_'+suffix],asset=asset,lod=0,
             geometry=c.arrow_geometry((-2,-1.2,.08),suffix))
    asset='env_fixture_front'
    mesh(bpy,asset+'_lod0',[],mats['mat_axis_y'],asset=asset,lod=0,
         geometry=c.arrow_geometry((0,-.35,.12),'front'))
    width = source['variants'][variant]['crate_width_m']
    asset='prp_fixture_crate'
    mesh(bpy,asset+'_lod0',[((1.8,0,.4),(width,.6,.8),None)],mats['mat_fixture_crate'],asset=asset,lod=0)
    mesh(bpy,asset+'_collider',[((1.8,0,.4),(width,.6,.8),None)],mats['mat_axis_cube'],asset=asset,role='collider')
    rig = make_rig(bpy)
    for asset, parts, mat in (('chr_fixture_avatar',c.BODY,mats['mat_fixture_skin']),
                               ('chr_fixture_outfit',c.OUTFIT,mats['mat_fixture_cloth'])):
        for lod in (0,1):
            mesh(bpy,asset+'_lod'+str(lod),parts,mat,divisions=2 if lod==0 else 1,
                 rig=rig,asset=asset,lod=lod)
    socket = bpy.data.objects.new('socket_hand_r',None)
    scene.collection.objects.link(socket)
    socket.parent, socket.parent_type, socket.parent_bone = rig, 'BONE', 'bn_hand_r'
    socket.location = (0,.05,0)
    socket['asset_id'], socket['role'] = 'chr_fixture_avatar', 'socket'
    make_actions(bpy,rig)
    for obj in scene.objects: obj.select_set(False)
    bpy.context.view_layer.objects.active = None
    bpy.context.view_layer.update()


def basis_matrix():
    from mathutils import Matrix
    return Matrix(((1,0,0,0),(0,0,1,0),(0,-1,0,0),(0,0,0,1)))


def trs(matrix):
    pos, rot, scale = matrix.decompose()
    rot.normalize()
    if rot.w < 0: rot.negate()
    return {'position':list(pos), 'rotation_xyzw':[rot.x,rot.y,rot.z,rot.w], 'scale':list(scale)}


def gltf_trs(matrix):
    basis=basis_matrix()
    return trs(basis @ matrix @ basis.inverted())


def joint_trs(matrix, *, root=False, world=False):
    # Exporter tree.py appends C to each bone world before joints.py swizzling.
    # Thus world/root-local uses C M; a child joint's local transform stays M.
    return trs(basis_matrix() @ matrix if root or world else matrix)


def bounds(points):
    return {'min':[min(p[i] for p in points) for i in range(3)],
            'max':[max(p[i] for p in points) for i in range(3)]}


def image_observation(img):
    c.need(img.source=='FILE' and not img.is_dirty and not img.is_float and tuple(img.size)==(4,4), 'IMAGE_NATIVE_STATE')
    png=bytes(img.packed_file.data)
    pixels=c.source_png_pixels(png)
    native=list(img.pixels)
    c.need(len(native)==64 and all(math.isfinite(v) for v in native), 'IMAGE_NATIVE_PIXELS')
    # Pinned Blender's byte-backed FILE image exposes bottom-up encoded samples
    # normalized to floats. The sRGB label is not a transfer applied by .pixels.
    expected=[]
    for y in reversed(range(4)):
        for x in range(4):
            for channel in range(4):
                value=pixels[(y*4+x)*4+channel]/255
                expected.append(value)
    error=max(abs(a-b) for a,b in zip(native,expected))
    c.need(error<=2e-5, 'IMAGE_NATIVE_PIXEL_MISMATCH_'+str(round(error,6)))
    return {'width':img.size[0],'height':img.size[1],'channels':img.channels,
        'color_space':img.colorspace_settings.name,'packed_png_sha256':c.sha(png),
        'rgba8_sha256':c.sha(pixels),'native_pixels_sha256':c.digest(native),
        'native_pixels_max_error':error,'external_path':False}


def observe(bpy):
    c.need(not bpy.data.libraries and not bpy.data.texts and not bpy.data.node_groups,
           'FOREIGN_DEPENDENCY')
    c.need(len(bpy.data.armatures)==1 and set(a.name for a in bpy.data.actions)==set(c.CLIPS), 'RIG_CLIP_SET')
    rig = bpy.data.objects[c.RIG]
    c.need(list(bpy.data.images) and all(i.packed_file is not None and i.filepath=='' for i in bpy.data.images), 'EXTERNAL_IMAGE')
    scene = bpy.context.scene
    rig.animation_data.action = bpy.data.actions['idle']
    rig.animation_data.action_slot = bpy.data.actions['idle'].slots[0]
    scene.frame_set(0)
    bpy.context.view_layer.update()
    meshes = {}
    for obj in sorted(scene.objects, key=lambda o:o.name):
        c.need(tuple(obj.scale)==(1,1,1) and not obj.constraints and not obj.library, 'OBJECT_PROFILE')
        c.need(obj.animation_data is None or obj is rig, 'UNSUPPORTED_OBJECT_ANIMATION')
        if obj.type != 'MESH': continue
        c.need(not obj.data.shape_keys and not obj.data.animation_data, 'MESH_PROFILE')
        c.need(all(m.type=='ARMATURE' and m.object is rig for m in obj.modifiers), 'MODIFIER_PROFILE')
        obj.data.calc_loop_triangles()
        local = [list(v.co) for v in obj.data.vertices]
        world = [list(obj.matrix_world@v.co) for v in obj.data.vertices]
        weights = [[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups] for v in obj.data.vertices]
        skinned = bool(obj.modifiers)
        c.need(not skinned or all(len(w)==1 and abs(w[0][1]-1)<1e-6 for w in weights), 'SKIN_WEIGHTS')
        row = {'asset_id':obj['asset_id'],'role':obj['role'],'vertices':len(local),
            'triangles':len(obj.data.loop_triangles),'source_local_bounds':bounds(local),
            'source_world_bounds':bounds(world),'gltf_world_bounds':bounds([(p[0],p[2],-p[1]) for p in world]),
            'gltf_world_transform':gltf_trs(obj.matrix_world),
            'materials':[m.name for m in obj.data.materials],
            'material_references':[{'owner_asset_id':c.MATERIAL_OWNERS[m.name],'name':m.name}
                                   for m in obj.data.materials],
            'geometry_sha256':c.digest({'vertices':local,'faces':[list(p.vertices) for p in obj.data.polygons]}),
            'skinned':skinned,'rig_owner':'chr_fixture_avatar' if skinned else None,
            'rig_name':c.RIG if skinned else None,'influences_max':max(map(len,weights),default=0),
            'weight_sum_range':[min((sum(w for _,w in row) for row in weights),default=0),
                                max((sum(w for _,w in row) for row in weights),default=0)],
            'weights_sha256':c.digest(weights)}
        if 'lod' in obj: row['lod']=obj['lod']
        meshes[obj.name]=row
    bones = {}
    for bone in rig.data.bones:
        local = bone.parent.matrix_local.inverted()@bone.matrix_local if bone.parent else bone.matrix_local
        bones[bone.name]={'parent':bone.parent.name if bone.parent else None,
            'rest_gltf_local':joint_trs(local,root=bone.parent is None),
            'rest_gltf_world':joint_trs(rig.matrix_world@bone.matrix_local,world=True)}
    socket = bpy.data.objects['socket_hand_r']
    socket_bone = rig.matrix_world@rig.pose.bones[socket.parent_bone].matrix
    sockets = {socket.name:{'owner_asset_id':'chr_fixture_avatar','rig_name':c.RIG,'bone':socket.parent_bone,
        'rest_gltf_world':gltf_trs(socket.matrix_world),
        'rest_gltf_bone_local':trs(socket_bone.inverted()@socket.matrix_world@basis_matrix().inverted())}}
    clips = {}
    for clip in c.CLIPS:
        action=bpy.data.actions[clip]
        rig.animation_data.action=action
        rig.animation_data.action_slot=action.slots[0]
        samples=[]
        for frame in sorted(set(c.FRAMES)|{7.5,22.5}):
            scene.frame_set(int(frame),subframe=frame-int(frame))
            bpy.context.view_layer.update()
            poses={}
            for bone in rig.pose.bones:
                local=bone.parent.matrix.inverted()@bone.matrix if bone.parent else bone.matrix
                poses[bone.name]={'local':joint_trs(local,root=bone.parent is None),
                                  'world':joint_trs(rig.matrix_world@bone.matrix,world=True)}
            samples.append({'frame':frame,'time':frame/c.FPS,'bones':poses,
                            'socket_world':gltf_trs(socket.matrix_world)})
        clips[clip]={'fps':c.FPS,'frame_start':int(action.frame_start),'frame_end':int(action.frame_end),
            'duration_seconds':(action.frame_end-action.frame_start)/c.FPS,
            'loop':True,'root_motion':'in_place','events':[], 'samples':samples}
    rig.animation_data.action=bpy.data.actions['idle']
    rig.animation_data.action_slot=bpy.data.actions['idle'].slots[0]
    scene.frame_set(0)
    bpy.context.view_layer.update()
    materials={}
    for mat in bpy.data.materials:
        bsdf=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
        materials[mat.name]={'owner_asset_id':c.MATERIAL_OWNERS[mat.name],
            'base_color':[1,1,1,1] if bsdf.inputs['Base Color'].is_linked else list(bsdf.inputs['Base Color'].default_value),
            'metallic':1 if bsdf.inputs['Metallic'].is_linked else bsdf.inputs['Metallic'].default_value,
            'roughness':1 if bsdf.inputs['Roughness'].is_linked else bsdf.inputs['Roughness'].default_value,
            'source_defaults':{'base_color':list(bsdf.inputs['Base Color'].default_value),
                'metallic':bsdf.inputs['Metallic'].default_value,'roughness':bsdf.inputs['Roughness'].default_value},
            'alpha_mode':'OPAQUE','double_sided':not mat.use_backface_culling,
            'normal_scale':1.0,'texture_bindings':dict(c.TEXTURE_BINDINGS) if mat.name=='mat_fixture_crate' else {},
            'images':sorted(n.image.name for n in mat.node_tree.nodes if n.type=='TEX_IMAGE')}
    images={i.name:image_observation(i) for i in bpy.data.images}
    return {'coordinate_spaces':{'source':'meters Blender +Z up, -Y asset front',
        'gltf':'meters +Y up, +Z asset front','bone_local':'absolute parent-relative joint transform; not pose delta',
        'bone_world':'absolute fixture world joint transform','rotation':'normalized xyzw; q and -q equivalent',
        'mesh_bounds':'unposed/rest mesh in fixture world; both LODs retained, consumer selects one'},
        'meshes':meshes,'rig':{'owner_asset_id':'chr_fixture_avatar','name':c.RIG,'bones':bones},
        'clips':clips,'materials':materials,'images':images,'sockets':sockets,
        'shared_rigs':{'chr_fixture_outfit':{'owner_asset_id':'chr_fixture_avatar','rig_name':c.RIG}},
        'scene_triangles':sum(m['triangles'] for m in meshes.values()),'object_count':len(scene.objects),
        'fps':scene.render.fps,'meters_per_unit':scene.unit_settings.scale_length}


def admit_observation(value):
    c.need(value['fps']==30 and value['meters_per_unit']==1,'UNITS_FPS')
    expected={n['name'] for a in c.asset_catalog()['assets'] for n in a['nodes'] if n['role']!='rig'}
    c.need(set(value['meshes'])==expected and set(value['rig']['bones'])=={b[0] for b in c.BONES},'OBSERVED_NAME_SET')
    for clip in value['clips'].values():
        c.need(clip['frame_start']==0 and clip['frame_end']==30 and clip['duration_seconds']==1,'CLIP_LENGTH')
        rest=value['rig']['bones']['bn_root']['rest_gltf_world']
        c.need(all(s['bones']['bn_root']['world']==rest for s in clip['samples']),'ROOT_MOTION')
    for asset, cap in (('chr_fixture_avatar',8000),('chr_fixture_outfit',8000)):
        for lod in (0,1):
            m=value['meshes'][asset+'_lod'+str(lod)]
            c.need(0<m['triangles']<=(cap if lod==0 else 2000) and m['skinned'],'LOD_SKIN_BUDGET')
            c.need(m['rig_owner']=='chr_fixture_avatar' and m['rig_name']==c.RIG
                   and len(m['materials'])<=2,'SHARED_RIG_MATERIAL_BUDGET')
        c.need(value['meshes'][asset+'_lod0']['triangles']>value['meshes'][asset+'_lod1']['triangles'],'LOD_REDUCTION')
    c.need(set(value['materials'])==set(c.MATERIAL_OWNERS) and set(value['images'])==set(c.TEXTURE_BINDINGS.values()),'MATERIAL_IMAGE_SET')
    c.need(value['object_count']==14 and value['scene_triangles']<=300000,'SCENE_BUDGET')


def main():
    c.need(threading.current_thread() is threading.main_thread(),'MAIN_THREAD_REQUIRED')
    args=sys.argv[sys.argv.index('--')+1:]
    c.need(len(args)==2 and args[1] in c.VARIANTS,'FIXED_ARGUMENTS')
    paths=c.admit_root(args[0],STUDIO/'.local')
    import bpy
    before_pins=pins(bpy)
    profile=load_json(STUDIO/'tests/asset-profile.json')
    c.need(profile['profile_id']==c.PROFILE and profile['publication']['per_blob_bytes']==c.MAX_ARTIFACT,'PROFILE_PIN')
    source=load_json(STUDIO/'fixtures/assets-src/fixture-source.json')
    c.need(source['license']=='original-fixture' and source['external_inputs']==[],'PROVENANCE')
    spec=importlib.util.spec_from_file_location('gt05_names',STUDIO/'pipeline/naming.py')
    names=importlib.util.module_from_spec(spec);spec.loader.exec_module(names)
    catalog=c.asset_catalog(); names.validate_catalog(catalog)
    generate(bpy,source,args[1],paths['fixture.blend'].parent)
    before=observe(bpy);admit_observation(before)
    c.need(bpy.ops.wm.save_as_mainfile(filepath=str(paths['fixture.blend']),check_existing=False,compress=True)=={'FINISHED'},'SAVE_FAILED')
    blend=paths['fixture.blend'].read_bytes()
    c.need(0<len(blend)<=c.MAX_ARTIFACT,'BLEND_CAP')
    blend_sha=c.sha(blend)
    c.need(bpy.ops.wm.open_mainfile(filepath=str(paths['fixture.blend']),load_ui=False,use_scripts=False)=={'FINISHED'},'REOPEN_FAILED')
    reopened=observe(bpy);admit_observation(reopened)
    c.need(reopened==before and c.sha(paths['fixture.blend'].read_bytes())==blend_sha,'REOPEN_READBACK')
    c.need(bpy.ops.export_scene.gltf(filepath=str(paths['fixture.glb']),**c.EXPORT_SETTINGS)=={'FINISHED'},'EXPORT_FAILED')
    glb=paths['fixture.glb'].read_bytes()
    c.need(0<len(glb)<=c.MAX_ARTIFACT and glb[:4]==b'glTF','GLB_CAP_OR_HEADER')
    exported_images=c.exported_image_observation(glb,reopened['images'])
    after=observe(bpy)
    c.need(after==reopened and pins(bpy)==before_pins,'EXPORT_CHANGED_SOURCE')
    report={'schema':c.SCHEMA,'profile_id':c.PROFILE,'variant':args[1],
        'license':source['license'],'external_inputs':[],'pins':before_pins,
        'settings':c.EXPORT_SETTINGS,'catalog':catalog,'observed':reopened,
        'exported_images':exported_images,
        'observed_sha256':c.digest(reopened),'source_reopened_exact':True,'export_preserved_source':True,
        'artifacts':{'fixture.blend':{'sha256':blend_sha,'bytes':len(blend)},
                     'fixture.glb':{'sha256':c.sha(glb),'bytes':len(glb)}},
        'proof_scope':'native original producer observation only; validator/Godot/publication not claimed',
        'formal_acceptance':False,'public_ack':False}
    raw=c.encoded(report)
    c.need(len(raw)<=c.MAX_REPORT,'REPORT_CAP')
    with paths['producer-report.json'].open('xb') as f:f.write(raw)
    print('GT05_PRODUCER_COMPLETE '+json.dumps({'variant':args[1],'source_sha256':before_pins['source_sha256'],
        'report_sha256':c.sha(raw),'blend_bytes':len(blend),'glb_bytes':len(glb),'formal_acceptance':False}),flush=True)


if __name__=='__main__':
    main()
