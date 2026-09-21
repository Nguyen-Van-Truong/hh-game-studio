"""Pure fixture constants, geometry and fixed staging-path admission."""
from __future__ import annotations

import hashlib
import json
import math
import struct
import zlib
from pathlib import Path

SCHEMA = 'HH-GT05-PRODUCER-1'
PROFILE = 'gt05-original-fixture-v1'
MAX_ARTIFACT = 1024 * 1024
MAX_REPORT = 1024 * 1024
SLOTS = ('fixture.blend', 'fixture.glb', 'producer-report.json')
VARIANTS = ('baseline', 'edited')
RIG = 'chr_fixture_avatar_rig'
CLIPS = ('idle', 'walk')
MATERIAL_OWNERS = {
    'mat_axis_cube': 'env_fixture_axis_cube', 'mat_axis_x': 'env_fixture_axis_x',
    'mat_axis_y': 'env_fixture_axis_y', 'mat_axis_z': 'env_fixture_axis_z',
    'mat_fixture_crate': 'prp_fixture_crate', 'mat_fixture_skin': 'chr_fixture_avatar',
    'mat_fixture_cloth': 'chr_fixture_outfit',
}
TEXTURE_BINDINGS = {'base_color': 'img_fixture_base', 'normal': 'img_fixture_normal',
                    'metallic_roughness': 'img_fixture_orm'}
FPS = 30
FRAMES = tuple(range(31))
FACES = ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
         (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7))

# All supported knobs are explicit and checked against the installed pinned RNA.
EXPORT_SETTINGS = {
    'check_existing': False, 'export_format': 'GLB', 'export_yup': True,
    'export_apply': False, 'export_texcoords': True, 'export_normals': True,
    'export_tangents': True, 'export_materials': 'EXPORT',
    'export_image_format': 'AUTO', 'export_image_add_webp': False,
    'export_image_webp_fallback': False, 'export_unused_images': False,
    'export_unused_textures': False, 'export_attributes': False,
    'export_cameras': False, 'export_lights': False, 'export_extras': False,
    'export_gpu_instances': False, 'export_gn_mesh': False,
    'export_use_gltfpack': False, 'export_draco_mesh_compression_enable': False,
    'export_meshopt_compression_enable': False, 'export_shared_accessors': False,
    'use_selection': False, 'use_visible': False, 'use_renderable': False,
    'use_active_scene': True, 'use_mesh_edges': False, 'use_mesh_vertices': False,
    'export_animations': True, 'export_animation_mode': 'ACTIONS',
    'export_frame_range': True, 'export_frame_step': 1, 'export_force_sampling': True,
    'export_sampling_interpolation_fallback': 'LINEAR',
    'export_anim_single_armature': True, 'export_action_filter': False,
    'export_merge_animation': 'NONE', 'export_reset_pose_bones': True,
    'export_negative_frame': 'CROP', 'export_anim_slide_to_zero': True,
    'export_bake_animation': False, 'export_optimize_animation_size': False,
    'export_optimize_animation_keep_anim_armature': True,
    'export_optimize_animation_keep_anim_object': False,
    'export_pointer_animation': False, 'export_convert_animation_pointer': False,
    'export_skins': True, 'export_influence_nb': 4, 'export_all_influences': False,
    'export_rest_position_armature': True, 'export_current_frame': False,
    'export_def_bones': False, 'export_leaf_bone': False,
    'export_armature_object_remove': False,
    'export_hierarchy_flatten_bones': False, 'export_hierarchy_flatten_objs': False,
    'export_morph': False, 'export_morph_animation': False,
    'export_try_sparse_sk': False, 'will_save_settings': False,
}

# (name, parent, head, tail), all original source coordinates in meters/Z-up.
BONES = (
    ('bn_root', None, (0, 0, 0), (0, 0, .2)),
    ('bn_pelvis', 'bn_root', (0, 0, .85), (0, 0, 1.05)),
    ('bn_spine', 'bn_pelvis', (0, 0, 1.05), (0, 0, 1.45)),
    ('bn_head', 'bn_spine', (0, 0, 1.45), (0, 0, 1.85)),
    ('bn_upperarm_l', 'bn_spine', (.24, 0, 1.4), (.48, 0, 1.12)),
    ('bn_hand_l', 'bn_upperarm_l', (.48, 0, 1.12), (.57, 0, .91)),
    ('bn_upperarm_r', 'bn_spine', (-.24, 0, 1.4), (-.48, 0, 1.12)),
    ('bn_hand_r', 'bn_upperarm_r', (-.48, 0, 1.12), (-.57, 0, .91)),
    ('bn_thigh_l', 'bn_pelvis', (.14, 0, .88), (.14, 0, .47)),
    ('bn_shin_l', 'bn_thigh_l', (.14, 0, .47), (.14, 0, .06)),
    ('bn_thigh_r', 'bn_pelvis', (-.14, 0, .88), (-.14, 0, .47)),
    ('bn_shin_r', 'bn_thigh_r', (-.14, 0, .47), (-.14, 0, .06)),
)

# center, size, bone. Each part is a closed outward-facing rectangular solid.
BODY = (
    ((0, 0, 1.22), (.44, .24, .46), 'bn_spine'),
    ((0, 0, .9), (.38, .24, .22), 'bn_pelvis'),
    ((0, 0, 1.67), (.34, .3, .38), 'bn_head'),
    ((0, -.19, 1.65), (.12, .12, .1), 'bn_head'),
    ((.35, 0, 1.24), (.19, .2, .33), 'bn_upperarm_l'),
    ((-.35, 0, 1.24), (.19, .2, .33), 'bn_upperarm_r'),
    ((.51, 0, 1.0), (.16, .19, .25), 'bn_hand_l'),
    ((-.51, 0, 1.0), (.16, .19, .25), 'bn_hand_r'),
    ((.14, 0, .66), (.19, .21, .36), 'bn_thigh_l'),
    ((-.14, 0, .66), (.19, .21, .36), 'bn_thigh_r'),
    ((.14, -.035, .25), (.18, .28, .4), 'bn_shin_l'),
    ((-.14, -.035, .25), (.18, .28, .4), 'bn_shin_r'),
)
OUTFIT = (
    ((0, 0, 1.21), (.48, .275, .36), 'bn_spine'),
    ((0, 0, .91), (.415, .275, .2), 'bn_pelvis'),
    ((.35, 0, 1.31), (.225, .235, .16), 'bn_upperarm_l'),
    ((-.35, 0, 1.31), (.225, .235, .16), 'bn_upperarm_r'),
    ((.14, 0, .77), (.22, .245, .16), 'bn_thigh_l'),
    ((-.14, 0, .77), (.22, .245, .16), 'bn_thigh_r'),
)


class ProducerRejected(ValueError):
    pass


def need(value, code):
    if not value:
        raise ProducerRejected(code)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while raw := stream.read(65536):
            result.update(raw)
    return result.hexdigest()


def png_rgba8(pixels):
    """Fixed original 4x4 RGBA8 source, only critical chunks and filter zero."""
    need(len(pixels) == 16 and all(len(p) == 4 and all(type(v) in (int, float)
         and math.isfinite(v) and 0 <= v <= 1 for v in p) for p in pixels), 'PIXEL_PROFILE')
    rgba = bytes(round(v*255) for p in pixels for v in p)
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind+data))
    scanlines = b''.join(b'\0'+rgba[y*16:(y+1)*16] for y in range(4))
    raw = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB',4,4,8,6,0,0,0))
           + chunk(b'IDAT',zlib.compress(scanlines,9)) + chunk(b'IEND',b''))
    return raw


def source_png_pixels(raw):
    """Read back this producer's exact PNG format, not a general intake decoder."""
    need(type(raw) is bytes and 0 < len(raw) < 1024 and raw[:8] == b'\x89PNG\r\n\x1a\n', 'SOURCE_PNG')
    offset, chunks = 8, []
    for expected in (b'IHDR', b'IDAT', b'IEND'):
        need(offset+12 <= len(raw), 'SOURCE_PNG_CHUNK')
        size, kind = struct.unpack_from('>I4s', raw, offset)
        need(kind == expected and offset+12+size <= len(raw), 'SOURCE_PNG_CHUNK')
        data = raw[offset+8:offset+8+size]
        need(zlib.crc32(kind+data) == struct.unpack_from('>I',raw,offset+8+size)[0], 'SOURCE_PNG_CRC')
        chunks.append(data)
        offset += size+12
    need(offset == len(raw) and chunks[0] == struct.pack('>IIBBBBB',4,4,8,6,0,0,0)
         and chunks[2] == b'', 'SOURCE_PNG_PROFILE')
    inflater = zlib.decompressobj()
    decoded = inflater.decompress(chunks[1],69)
    need(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail and len(decoded)==68
         and all(decoded[y*17]==0 for y in range(4)), 'SOURCE_PNG_PIXELS')
    return b''.join(decoded[y*17+1:(y+1)*17] for y in range(4))


def exported_image_observation(raw, source_images):
    """Bind this trusted export's actual PNG pixels and material texture slots.

    This narrow postcondition does not replace independent complete GLB intake.
    """
    need(20 <= len(raw) <= MAX_ARTIFACT and raw[:4] == b'glTF', 'EXPORT_CONTAINER')
    version, length, json_length, kind = struct.unpack_from('<4I',raw,4)
    need(version==2 and length==len(raw) and kind==0x4e4f534a and json_length<=262144, 'EXPORT_CONTAINER')
    end=20+json_length
    need(end+8<=len(raw), 'EXPORT_CONTAINER')
    bin_length,kind=struct.unpack_from('<2I',raw,end)
    need(kind==0x004e4942 and end+8+bin_length==len(raw), 'EXPORT_CONTAINER')
    document=json.loads(raw[20:end])
    binary=raw[end+8:]
    need(len(document.get('images',[]))==len(source_images)==3, 'EXPORT_IMAGE_SET')
    images={}
    for row in document['images']:
        need(row['name'] in source_images and row['name'] not in images and row['mimeType']=='image/png'
             and 'uri' not in row, 'EXPORT_IMAGE_IDENTITY')
        view=document['bufferViews'][row['bufferView']]
        start=view.get('byteOffset',0);stop=start+view['byteLength']
        need(view['buffer']==0 and 0<=start<stop<=len(binary), 'EXPORT_IMAGE_BOUNDS')
        png=binary[start:stop]
        pixels=source_png_pixels(png)
        wanted=source_images[row['name']]
        need(sha(png)==wanted['packed_png_sha256'] and sha(pixels)==wanted['rgba8_sha256'], 'EXPORT_IMAGE_PIXELS')
        images[row['name']]={'png_sha256':sha(png),'rgba8_sha256':sha(pixels),'bytes':len(png)}
    need(len({row['rgba8_sha256'] for row in images.values()})==3, 'EXPORT_IMAGE_DISTINCT')
    material=next(row for row in document['materials'] if row['name']=='mat_fixture_crate')
    pbr=material['pbrMetallicRoughness']
    bindings={}
    for semantic,info in (('base_color',pbr['baseColorTexture']),('normal',material['normalTexture']),
                          ('metallic_roughness',pbr['metallicRoughnessTexture'])):
        texture=document['textures'][info['index']]
        name=document['images'][texture['source']]['name']
        need(name==TEXTURE_BINDINGS[semantic], 'EXPORT_TEXTURE_BINDING')
        sampler=document['samplers'][texture['sampler']]
        actual={key:sampler.get(key,default) for key,default in
                (('magFilter',None),('minFilter',None),('wrapS',10497),('wrapT',10497))}
        need(actual=={'magFilter':9728,'minFilter':9984,'wrapS':10497,'wrapT':10497}, 'EXPORT_SAMPLER')
        bindings[semantic]={'image':name,'sampler':actual}
    return {'images':images,'texture_bindings':bindings,'exact_source_pngs':True}


def admit_root(root, allowed_base):
    """Trusted host provisions one empty private output directory under .local.

    The host still owns ACL/identity pinning and process limits. This lexical
    and reparse check is not a substitute for the protected publication owner.
    """
    root, base = Path(root), Path(allowed_base).absolute()
    need(root.is_absolute() and '..' not in root.parts, 'STAGING_ABSOLUTE_CHILD_REQUIRED')
    need(root != base and root.is_relative_to(base), 'STAGING_SCOPE')
    for path in (root, *root.parents):
        info = path.lstat()
        need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'STAGING_REPARSE')
    need(root.is_dir() and not any(root.iterdir()), 'STAGING_NOT_EMPTY')
    return {name: root / name for name in SLOTS}


def pose_angles(clip, frame):
    need(clip in CLIPS and type(frame) in (int, float) and 0 <= frame <= 30, 'POSE_ARGUMENT')
    phase = math.sin(frame * 2 * math.pi / 30)
    result = {name: [0.0, 0.0, 0.0] for name, *_ in BONES}
    if clip == 'idle':
        result['bn_spine'][1] = .025 * phase
        result['bn_head'][2] = .035 * phase
    else:
        for side, sign in (('l', 1), ('r', -1)):
            result['bn_thigh_' + side][0] = .35 * phase * sign
            result['bn_shin_' + side][0] = .18 * max(0, -phase * sign)
            result['bn_upperarm_' + side][0] = -.3 * phase * sign
            result['bn_hand_' + side][0] = -.08 * phase * sign
    return result


def box_geometry(parts, divisions=1):
    """Original mesh data with predictable outward winding and rigid weights."""
    need(type(divisions) is int and divisions in (1, 2), 'DIVISIONS')
    vertices, faces, weights = [], [], []
    for center, size, bone in parts:
        need(len(center) == len(size) == 3 and all(math.isfinite(x) for x in (*center, *size))
             and all(x > 0 for x in size), 'BOX_DIMENSIONS')
        corners = [(center[0] + x * size[0] / 2, center[1] + y * size[1] / 2,
                    center[2] + z * size[2] / 2)
                   for x, y, z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                                   (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1))]
        for face in FACES:
            a, b, _, d = [corners[i] for i in face]
            start = len(vertices)
            for v in range(divisions + 1):
                for u in range(divisions + 1):
                    vertices.append(tuple(a[k] + (b[k]-a[k])*u/divisions + (d[k]-a[k])*v/divisions for k in range(3)))
                    weights.append(bone)
            for v in range(divisions):
                for u in range(divisions):
                    i = start + v * (divisions + 1) + u
                    faces.append((i, i+1, i+divisions+2, i+divisions+1))
    return vertices, faces, weights


def arrow_geometry(origin, axis):
    """Square shaft and a four-sided point, all transforms baked into vertices."""
    need(axis in ('x', 'y', 'z', 'front'), 'ARROW_AXIS')
    vertices, faces, weights = box_geometry([((0,0,.25),(.045,.045,.5),None)])
    start = len(vertices)
    vertices += [(-.11,-.11,.5),(.11,-.11,.5),(.11,.11,.5),(-.11,.11,.5),(0,0,.75)]
    faces += [tuple(start+i for i in face) for face in ((0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4))]
    weights += [None]*5
    def convert(p):
        x,y,z = p
        value = {'x':(z,x,y),'y':(y,z,x),'z':(x,y,z),'front':(x,-z,y)}[axis]
        return tuple(origin[i]+value[i] for i in range(3))
    return [convert(p) for p in vertices], faces, weights


def asset_catalog():
    rows = []
    for asset, materials in (
        ('env_fixture_axis_cube', ['mat_axis_cube']), ('env_fixture_axis_x', ['mat_axis_x']),
        ('env_fixture_axis_y', ['mat_axis_y']), ('env_fixture_axis_z', ['mat_axis_z']),
        ('env_fixture_front', ['mat_axis_y']), ('prp_fixture_crate', ['mat_fixture_crate']),
        ('chr_fixture_avatar', ['mat_fixture_skin']), ('chr_fixture_outfit', ['mat_fixture_cloth'])):
        character = asset.startswith('chr_')
        nodes = [{'name': asset+'_lod'+str(lod), 'role':'render', 'lod':lod}
                 for lod in ((0,1) if character else (0,))]
        if asset == 'prp_fixture_crate': nodes.append({'name':asset+'_collider','role':'collider'})
        if asset == 'env_fixture_axis_cube': nodes.append({'name':asset+'_nav','role':'nav'})
        if asset == 'chr_fixture_avatar': nodes.append({'name':RIG,'role':'rig'})
        rows.append({'asset_id':asset,'class':'character' if character else 'prop' if asset.startswith('prp_') else 'environment',
            'nodes':nodes, 'bones':[b[0] for b in BONES] if asset=='chr_fixture_avatar' else [],
            'clips':list(CLIPS) if asset=='chr_fixture_avatar' else [],'materials':materials,
            'sockets':['socket_hand_r'] if asset=='chr_fixture_avatar' else []})
    return {'schema':'HH-ASSET-NAMES-1','assets':rows}
