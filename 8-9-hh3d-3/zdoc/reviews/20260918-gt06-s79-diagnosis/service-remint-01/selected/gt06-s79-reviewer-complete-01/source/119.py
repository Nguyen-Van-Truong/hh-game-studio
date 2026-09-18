"""Trusted fixed GT05 staging and native-observation checks; never launches Godot.

The coordinator must run complete GLB/PNG/Khronos admission before calling
prepare or replace_inputs. This repeats byte-container/name checks, not those
independent admission stages. Only an isolated coordinator-owned directory is
accepted; no transport, arbitrary scripts, user file intake or publish authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import struct
import zlib

from studio.pipeline.glb_container import inspect_glb
from studio.pipeline.naming import validate_catalog
from studio.pipeline.png_decode import PNGRejected, decode_png
from studio.pipeline.producer import contract

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1]
SOURCES = ('project.godot', 'authored.tscn', 'authored.gd', 'authored_material.tres', 'probe.gd')
INPUTS = ('fixture.glb', 'manifest.json', 'producer-report.json')
PHASES = ('baseline', 'reimport', 'visual')
MAX_JSON = 1024 * 1024
SAMPLE_TIMES = sorted([frame/30 for frame in range(31)] + [.25, .75])
VISUAL_VIEWS = {'front': [0,2,8], 'back': [0,2,-8], 'left': [-8,2,0],
                'right': [8,2,0], 'top': [0,9,0], 'bottom': [0,-7,0]}
VISUAL_LABELS = (*VISUAL_VIEWS, *(f'{clip}_{frame:02d}' for clip in ('idle','walk') for frame in range(31)))
PRESET = '''[remap]
importer="scene"
importer_version=1
type="PackedScene"

[deps]
source_file="res://input/fixture.glb"

[params]
nodes/root_type="Node3D"
nodes/root_name="fixture"
nodes/apply_root_scale=true
nodes/root_scale=1.0
nodes/import_as_skeleton_bones=false
nodes/use_name_suffixes=false
nodes/use_node_type_suffixes=false
meshes/ensure_tangents=true
meshes/generate_lods=false
meshes/create_shadow_meshes=false
meshes/light_baking=0
meshes/force_disable_compression=true
skins/use_named_skins=true
animation/import=true
animation/fps=30
animation/trimming=false
animation/remove_immutable_tracks=false
animation/import_rest_as_RESET=false
import_script/path=""
materials/extract=0
gltf/naming_version=2
gltf/embedded_image_handling=3
gltf/texture_map_mode=0
_subresources={"nodes": {"PATH:AnimationPlayer": {"optimizer/enabled": false, "compression/enabled": false, "import_tracks/position": 0, "import_tracks/rotation": 0, "import_tracks/scale": 0}}, "animations": {"idle": {"settings/loop_mode": 1}, "walk": {"settings/loop_mode": 1}}}
'''


class ConsumerRejected(ValueError):
    """Stable code; no untrusted values or local paths in messages."""


def need(value, code):
    if not value:
        raise ConsumerRejected(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def strict(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MAX_JSON, 'CONSUMER_JSON_SIZE')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'CONSUMER_DUPLICATE_KEY')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ConsumerRejected('CONSUMER_NONFINITE')))
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, ConsumerRejected):
            raise
        raise ConsumerRejected('CONSUMER_JSON_SYNTAX') from None
    need(type(value) is dict, 'CONSUMER_JSON_OBJECT')
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop(); count += 1
        need(depth <= 32 and count <= 100000, 'CONSUMER_JSON_GRAPH')
        if type(item) is dict:
            need(len(item) <= 512, 'CONSUMER_JSON_MEMBERS')
            pending.extend((v, depth + 1) for v in item.values())
        elif type(item) is list:
            need(len(item) <= 8192, 'CONSUMER_JSON_ARRAY')
            pending.extend((v, depth + 1) for v in item)
        elif type(item) is float:
            need(math.isfinite(item), 'CONSUMER_NONFINITE')
    return value


def _path(path):
    path = Path(path)
    need('..' not in path.parts, 'CONSUMER_TRAVERSAL')
    path = path.absolute()
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
                 'CONSUMER_REPARSE')
    return path


def _payload(glb, manifest, producer_report):
    container = inspect_glb(glb)
    strict(manifest)
    expected = strict(producer_report)
    need(expected.get('schema') == contract.SCHEMA, 'CONSUMER_PRODUCER_SCHEMA')
    catalog = contract.asset_catalog()
    validate_catalog(catalog)
    need(expected.get('catalog') == catalog and expected.get('profile_id') == contract.PROFILE,
         'CONSUMER_FIXED_PRODUCER_PROFILE')
    need(expected.get('artifacts', {}).get('fixture.glb') == {'sha256': sha(glb), 'bytes': len(glb)},
         'CONSUMER_PRODUCER_ARTIFACT_BINDING')
    need(expected.get('observed_sha256') == contract.digest(expected['observed']), 'CONSUMER_PRODUCER_OBSERVATION_HASH')
    for field, relative in (('profile_sha256', 'tests/asset-profile.json'),
                            ('naming_sha256', 'contracts/naming-convention-v1.md'),
                            ('toolchain_sha256', 'toolchain.lock.json')):
        need(expected['pins'][field] == sha((STUDIO/relative).read_bytes()), 'CONSUMER_PRODUCER_PINS')
    nodes = [dict(node, asset_id=asset['asset_id']) for asset in catalog['assets'] for node in asset['nodes']]
    mesh_names = {row['name'] for row in nodes if row['role'] != 'rig'}
    doc_nodes = container.document.get('nodes', ())
    actual_names = [node.get('name') for node in doc_nodes if 'mesh' in node]
    need(len(actual_names) == len(set(actual_names)) and set(actual_names) == mesh_names,
         'CONSUMER_FIXED_MESH_NAMES')
    need({animation.get('name') for animation in container.document.get('animations', ())} == {'idle', 'walk'},
         'CONSUMER_FIXED_CLIP_NAMES')
    raw = dict(zip(INPUTS, (glb, manifest, producer_report)))
    seed = {'schema': 'HH-GT05-GODOT-CONSUMER-1', 'input_sha256': {k: sha(v) for k, v in raw.items()},
        'authored_sha256': {name: sha((HERE/name).read_bytes()) for name in SOURCES},
        'profile_sha256': sha((STUDIO/'tests/asset-profile.json').read_bytes()),
        'naming_sha256': sha((STUDIO/'contracts/naming-convention-v1.md').read_bytes()),
        'toolchain_sha256': sha((STUDIO/'toolchain.lock.json').read_bytes()),
        'preset_sha256': sha(PRESET.encode()), 'nodes': nodes,
        'rigs': [{'asset_id': 'chr_fixture_avatar', 'reference_mesh': 'chr_fixture_avatar_lod0'}],
        'sockets': [{'name': 'socket_hand_r', 'bone': 'bn_hand_r', 'rig_asset_id': 'chr_fixture_avatar',
                     'local_pose': expected['observed']['sockets']['socket_hand_r']['rest_gltf_bone_local']}],
        'override_mesh': 'prp_fixture_crate_lod0', 'formal_acceptance': False}
    raw['consumer.json'] = encoded(seed)
    _trs(seed['sockets'][0]['local_pose'], seed['sockets'][0]['local_pose'])
    return raw, seed


def prepare(project: Path, *, glb: bytes, manifest: bytes, producer_report: bytes):
    """Provision a NEW isolated project. Complete intake admission precedes this.

    Path is a trusted supervisor output, never a request-selected asset path.
    Provisioning has no engine, active-project or protected-publication effect.
    """
    raw, seed = _payload(glb, manifest, producer_report)
    project = _path(project)
    need(not project.exists() and project.parent.is_dir(), 'CONSUMER_FRESH_PROJECT')
    project.mkdir()
    (project/'input').mkdir(); (project/'out').mkdir()
    for name in SOURCES:
        (project/name).write_bytes((HERE/name).read_bytes())
    for name, value in raw.items():
        (project/'input'/name).write_bytes(value)
    (project/'input/fixture.glb.import').write_bytes(PRESET.encode())
    return seed


def replace_inputs(project: Path, *, glb: bytes, manifest: bytes, producer_report: bytes):
    """Replace only fixed staged inputs while the coordinator's engine is stopped.

    Requires a previous baseline observation. Save the immutable previous source
    and evidence in the run package before calling. This is a reimport fixture,
    not an atomic multi-file active publication implementation.
    """
    project = _path(project)
    old = strict((project/'input/consumer.json').read_bytes())
    baseline = strict((project/'out/baseline.json').read_bytes())
    need(baseline.get('input_sha256') == old['input_sha256'], 'CONSUMER_BASELINE_BINDING')
    raw, seed = _payload(glb, manifest, producer_report)
    need(seed['authored_sha256'] == old['authored_sha256'], 'CONSUMER_SOURCE_CHANGED')
    for name, digest in old['authored_sha256'].items():
        need(name in SOURCES and sha((project/name).read_bytes()) == digest, 'CONSUMER_AUTHORED_CHANGED')
    need(old['preset_sha256'] == sha(PRESET.encode()), 'CONSUMER_PRESET_CHANGED')
    for name, value in raw.items():
        target = _path(project/'input'/name)
        temporary = target.with_name(target.name + '.next')
        need(not temporary.exists(), 'CONSUMER_STALE_NEXT')
        with temporary.open('xb') as stream:
            stream.write(value); stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    return seed


def command(binary: Path, project: Path, phase: str):
    """Return a fixed argv. Caller pins binary, source, Job, env, exit and trees."""
    need(phase in ('import', *PHASES), 'CONSUMER_PHASE')
    common = [str(binary), '--headless'] if phase != 'visual' else [str(binary)]
    if phase == 'import':
        return common + ['--editor', '--path', str(project), '--import']
    return common + ['--path', str(project), '--script', 'res://probe.gd', '--', '--phase', phase]


def verify_binding(project: Path, *, phase: str, stdout: bytes):
    """Check completed native bytes and fixed requirements; not host-exit proof."""
    need(phase in PHASES, 'CONSUMER_PHASE')
    project = _path(project)
    seed = strict((project/'input/consumer.json').read_bytes())
    raw = (project/'out'/f'{phase}.json').read_bytes()
    observed = strict(raw)
    need(observed.get('schema') == 'HH-GT05-GODOT-OBSERVATION-1' and observed.get('phase') == phase
         and observed.get('formal_acceptance') is False, 'CONSUMER_OBSERVATION_SCHEMA')
    need(type(observed.get('pid')) is int and observed['pid'] > 0, 'CONSUMER_NATIVE_PID')
    engine = observed.get('engine', {})
    need((engine.get('major'), engine.get('minor'), engine.get('patch'), engine.get('status')) == (4,7,2,'stable')
         and str(engine.get('hash', '')).startswith('ed1daf0bf'), 'CONSUMER_NATIVE_PIN')
    need(observed.get('input_sha256') == seed['input_sha256'] and observed.get('authored_sha256') == seed['authored_sha256']
         and observed.get('consumer_sha256') == sha((project/'input/consumer.json').read_bytes()), 'CONSUMER_OBSERVATION_BINDING')
    for name, digest in seed['input_sha256'].items():
        need(name in INPUTS and sha((project/'input'/name).read_bytes()) == digest, 'CONSUMER_INPUT_CHANGED')
    for name, digest in seed['authored_sha256'].items():
        need(name in SOURCES and sha((project/name).read_bytes()) == digest, 'CONSUMER_AUTHORED_CHANGED')
    markers = [strict(line[len(b'GT05_GODOT_OBSERVED '):]) for line in stdout.splitlines()
               if line.startswith(b'GT05_GODOT_OBSERVED ')]
    need(markers == [{'phase': phase, 'pid': observed['pid'], 'report_sha256': sha(raw), 'formal_acceptance': False}],
         'CONSUMER_COMPLETION_MARKER')
    if phase == 'reimport':
        before = strict((project/'out/baseline.json').read_bytes())
        need(before['authored_sha256'] == observed['authored_sha256'] and before['authored'] == observed['authored'],
             'CONSUMER_REIMPORT_AUTHORED_STATE')
        need(before['input_sha256']['fixture.glb'] != observed['input_sha256']['fixture.glb'],
             'CONSUMER_REIMPORT_REQUIRES_CHANGED_GLB')
    if phase == 'visual':
        _verify_visual_observation(observed)
        need({path.name for path in (project/'out').glob('*.png')} ==
             {label+'.png' for label in VISUAL_LABELS}, 'CONSUMER_VISUAL_FILE_SET')
        decoded = set()
        for label, capture in observed['captures'].items():
            path = _path(project/'out'/(label+'.png'))
            need(path.stat().st_size <= 1048576, 'CONSUMER_VISUAL_PNG_BYTES')
            raw_png = path.read_bytes()
            need(sha(raw_png) == capture['sha256'], 'CONSUMER_VISUAL_BYTES')
            if capture['sha256'] not in decoded:
                _verify_visual_png(raw_png)
                decoded.add(capture['sha256'])
    return observed


def _numbers(value, length):
    need(type(value) is list and len(value) == length and
         all(type(x) in (int, float) and math.isfinite(x) for x in value), 'CONSUMER_FINITE_VECTOR')
    return value


def _near(actual, expected, tolerance, *, euclidean=False):
    actual = _numbers(actual, len(expected)); _numbers(expected, len(actual))
    delta = math.dist(actual, expected) if euclidean else max(abs(a-b) for a,b in zip(actual, expected))
    need(delta <= tolerance, 'CONSUMER_NUMERIC_MISMATCH')
    return delta


def _trs(actual, expected):
    need(type(actual) is dict and set(actual) == {'position', 'rotation_xyzw', 'scale'}, 'CONSUMER_TRS_FIELDS')
    _near(actual['position'], expected['position'], .001, euclidean=True)
    _near(actual['scale'], expected['scale'], .0001)
    a, b = _numbers(actual['rotation_xyzw'], 4), _numbers(expected['rotation_xyzw'], 4)
    need(abs(math.sqrt(sum(x*x for x in a))-1) <= .0001 and
         abs(math.sqrt(sum(x*x for x in b))-1) <= .0001, 'CONSUMER_UNIT_QUATERNION')
    dot = abs(sum(x*y for x,y in zip(a,b))) / math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))
    need(math.degrees(2*math.acos(min(1.0, dot))) <= .1, 'CONSUMER_ROTATION_MISMATCH')


def _fields(value, fields, code):
    need(type(value) is dict and set(value) == set(fields), code)
    return value


def _rotate(quaternion, vector):
    x, y, z, w = quaternion
    px, py, pz = vector
    tx, ty, tz = 2*(y*pz-z*py), 2*(z*px-x*pz), 2*(x*py-y*px)
    return [px+w*tx+y*tz-z*ty, py+w*ty+z*tx-x*tz, pz+w*tz+x*ty-y*tx]


def _visual_camera(camera, label):
    _fields(camera, ('transform','projection','size','near','far','target'), 'CONSUMER_VISUAL_CAMERA_FIELDS')
    need(type(camera['projection']) is int and camera['projection'] == 1, 'CONSUMER_VISUAL_PROJECTION')
    _near([camera['size'],camera['near'],camera['far']], [6,.05,100], .0001)
    _near(camera['target'], [0,1,0], .0001)
    transform = camera['transform']
    _trs(transform, transform)
    position = VISUAL_VIEWS[label if label in VISUAL_VIEWS else 'front']
    _near(transform['position'], position, .001, euclidean=True)
    _near(transform['scale'], [1,1,1], .0001)
    back = [a-b for a,b in zip(position, [0,1,0])]
    length = math.sqrt(sum(value*value for value in back))
    back = [value/length for value in back]
    up = [0,0,-1] if label in ('top','bottom') else [0,1,0]
    # Godot look_at uses local -Z toward the target and orthogonalizes its up.
    dot = sum(a*b for a,b in zip(up,back))
    up = [a-dot*b for a,b in zip(up,back)]
    length = math.sqrt(sum(value*value for value in up))
    up = [value/length for value in up]
    _near(_rotate(transform['rotation_xyzw'], [0,0,1]), back, .0001)
    _near(_rotate(transform['rotation_xyzw'], [0,1,0]), up, .0001)


def _verify_visual_observation(observed):
    """Readback-only visual contract; image bytes and owned host exits are separate.

    Fixed source invokes native rendering counters after frame_post_draw. These
    records bind what that probe captured; they do not replace reviewing the
    six-view stills for occlusion, lighting, or the appearance of the original art.
    """
    material = _fields(observed.get('visual_material'), ('mesh','original_material','override_disabled'),
                       'CONSUMER_VISUAL_MATERIAL_FIELDS')
    need(material['mesh'] == 'prp_fixture_crate_lod0' and material['override_disabled'] is True,
         'CONSUMER_VISUAL_ORIGINAL_MATERIAL')
    original = material['original_material']
    need(type(original) is dict and original.get('name') == 'mat_fixture_crate' and original.get('textures'),
         'CONSUMER_VISUAL_ORIGINAL_MATERIAL')
    meshes = observed.get('meshes', {})
    need(type(meshes) is dict and type(meshes.get(material['mesh'])) is dict, 'CONSUMER_VISUAL_PBR_READBACK')
    surfaces = meshes[material['mesh']].get('surfaces')
    need(type(surfaces) is list and len(surfaces) == 1 and type(surfaces[0]) is dict and
         surfaces[0].get('material') == original, 'CONSUMER_VISUAL_PBR_READBACK')
    authored = observed.get('authored')
    need(type(authored) is dict and authored.get('override_mesh') == material['mesh'] and
         type(authored.get('material')) is dict and authored['material'].get('name') == 'mat_authored_override' and
         observed.get('authored_after_capture') == authored, 'CONSUMER_VISUAL_AUTHORED_RESTORE')
    lighting = _fields(observed.get('visual_lighting'), ('key_energy','fill_energy','ambient_energy',
        'key_transform','key_color','fill_color','ambient_color','background_color','tonemap_mode','exposure',
        'fill_transform_local','fill_is_camera_child','shadows_enabled'), 'CONSUMER_VISUAL_LIGHTING_FIELDS')
    _near([lighting[name] for name in ('key_energy','fill_energy','ambient_energy','exposure')], [.65,.35,.2,1], .0001)
    for name, expected in (('key_color',[1,1,1]), ('fill_color',[1,1,1]), ('ambient_color',[.8,.8,.8]),
                           ('background_color',[.055,.065,.08])):
        _near(lighting[name], expected, .0001)
    need(type(lighting['tonemap_mode']) is int and lighting['tonemap_mode'] == 0 and
         lighting['fill_is_camera_child'] is True and lighting['shadows_enabled'] is False,
         'CONSUMER_VISUAL_LIGHTING_POLICY')
    identity = {'position': [0,0,0], 'rotation_xyzw': [0,0,0,1], 'scale': [1,1,1]}
    _trs(lighting['fill_transform_local'], identity)
    x, y = math.radians(-45)/2, math.radians(-35)/2
    _trs(lighting['key_transform'], dict(identity, rotation_xyzw=
        [math.sin(x)*math.cos(y), math.cos(x)*math.sin(y), -math.sin(x)*math.sin(y), math.cos(x)*math.cos(y)]))
    captures = observed.get('captures')
    need(type(captures) is dict and set(captures) == set(VISUAL_LABELS), 'CONSUMER_VISUAL_SET')
    clips = _fields(observed.get('clips'), ('idle','walk'), 'CONSUMER_VISUAL_LOOP_READBACK')
    for clip in clips.values():
        need(type(clip) is dict and type(clip.get('loop_mode')) is int and clip['loop_mode'] == 1 and
             type(clip.get('length')) in (int,float) and clip['length'] == 1.0, 'CONSUMER_VISUAL_LOOP_READBACK')
    previous = dict(frame=0, rendered_frame=0, monotonic_us=0, captured_at_unix=0)
    for label in VISUAL_LABELS:
        capture = _fields(captures[label], ('sha256','width','height','pid','frame','rendered_frame','captured_at_unix',
            'monotonic_us','source_sha256','producer_report_sha256','consumer_sha256','clip','requested_time',
            'clip_time','sample_frame','camera','draw_calls','material_name','override_is_null','prop_visible'),
            'CONSUMER_VISUAL_CAPTURE_FIELDS')
        need(type(capture['sha256']) is str and len(capture['sha256']) == 64 and
             all(char in '0123456789abcdef' for char in capture['sha256']), 'CONSUMER_VISUAL_IMAGE_HASH')
        need(type(capture['pid']) is int and capture['pid'] == observed['pid'] and
             type(capture['width']) is int and type(capture['height']) is int and
             capture['width'] == capture['height'] == 640, 'CONSUMER_VISUAL_DIMENSIONS_PID')
        for field in ('frame','rendered_frame','monotonic_us'):
            need(type(capture[field]) is int and capture[field] > previous[field], 'CONSUMER_VISUAL_FRAME_ORDER')
        _numbers([capture['captured_at_unix']], 1)
        need(capture['captured_at_unix'] > previous['captured_at_unix'], 'CONSUMER_VISUAL_TIME_ORDER')
        previous = {field: capture[field] for field in previous}
        need(capture['source_sha256'] == observed['input_sha256']['fixture.glb'] and
             capture['producer_report_sha256'] == observed['input_sha256']['producer-report.json'] and
             capture['consumer_sha256'] == observed['consumer_sha256'], 'CONSUMER_VISUAL_SOURCE_BINDING')
        clip, frame = ('idle', 0) if label in VISUAL_VIEWS else (label.rsplit('_',1)[0], int(label[-2:]))
        need(capture['clip'] == clip and type(capture['sample_frame']) is int and capture['sample_frame'] == frame,
             'CONSUMER_VISUAL_CLIP_SAMPLE')
        _near([capture['requested_time']], [frame/30], 1e-8)
        if frame == 30:
            # Pinned 4.7.2 AnimationPlayer::_process_playback_data uses fposmod
            # for LOOP_LINEAR. Seeking this verified 1s clip to its exact end
            # yields current_animation_position == 0, not the requested 1s.
            _numbers([capture['clip_time']], 1)
            need(capture['clip_time'] == 0.0, 'CONSUMER_VISUAL_LOOP_ENDPOINT')
        else:
            _near([capture['clip_time']], [frame/30], 1e-8)
        _visual_camera(capture['camera'], label)
        calls = _fields(capture['draw_calls'], ('visible','shadow','total'), 'CONSUMER_VISUAL_DRAW_CALL_FIELDS')
        need(all(type(value) is int for value in calls.values()) and calls['visible'] > 0 and calls['shadow'] == 0 and
             calls['total'] == calls['visible'] + calls['shadow'] and calls['total'] <= 150,
             'CONSUMER_VISUAL_DRAW_CALL_BUDGET')
        need(capture['material_name'] == 'mat_fixture_crate' and capture['override_is_null'] is True and
             capture['prop_visible'] is True, 'CONSUMER_VISUAL_MATERIAL_STATE')


def _verify_visual_png(raw):
    """Decode the native RGB(A) PNG profile, including Godot's sole sRGB chunk.

    Texture intake's closed chunk allowlist stays unchanged. This capture-only
    adapter validates/removes the optional fixed sRGB intent before that decoder.
    """
    need(type(raw) is bytes and 57 <= len(raw) <= 1048576, 'CONSUMER_VISUAL_PNG_BYTES')
    if raw[37:41] == b'sRGB':
        need(raw[33:37] == b'\0\0\0\1' and raw[41:42] == b'\0' and
             struct.unpack('>I', raw[42:46])[0] == zlib.crc32(b'sRGB\0'), 'CONSUMER_VISUAL_PNG_SRGB')
        raw = raw[:33] + raw[46:]
    try:
        image = decode_png(raw)
    except PNGRejected:
        raise ConsumerRejected('CONSUMER_VISUAL_PNG_INVALID') from None
    need(image.width == image.height == 640, 'CONSUMER_VISUAL_PNG_DIMENSIONS')
    # A constant clear frame or transparent output cannot serve as a scene still.
    need(image.rgba8[3::4] == b'\xff' * (640*640) and
         any(image.rgba8[index::4].count(image.rgba8[index]) < 640*640 for index in range(3)),
         'CONSUMER_VISUAL_PNG_EMPTY')


def _albedo_linear(value):
    """Godot BaseMaterial albedo is sRGB; glTF baseColorFactor is linear.

    Pinned gltf_document.cpp imports the factor with Color.linear_to_srgb().
    Convert only RGB back to the factor domain; PNG samples and alpha stay raw.
    """
    value = _numbers(value, 4)
    need(all(0 <= channel <= 1 for channel in value), 'CONSUMER_ALBEDO_RANGE')
    return [channel / 12.92 if channel < .04045 else ((channel + .055) / 1.055) ** 2.4
            for channel in value[:3]] + [value[3]]


def _inverse_rigid_trs(value):
    """Inverse of this fixed fixture's rigid glTF joint-world rest transform.

    The fixture has identity mesh/rig object transforms and unit joint scales.
    This is not a general bind-shape or scaled/sheared skeleton adapter.
    """
    _trs(value, value)
    _near(value['scale'], [1, 1, 1], .0001)
    x, y, z, w = value['rotation_xyzw']
    length = math.sqrt(x*x + y*y + z*z + w*w)
    x, y, z, w = -x/length, -y/length, -z/length, w/length
    px, py, pz = [-component for component in value['position']]
    # q_inverse * (-translation) * q, using two quaternion/vector crosses.
    tx, ty, tz = 2*(y*pz-z*py), 2*(z*px-x*pz), 2*(x*py-y*px)
    position = [px+w*tx+y*tz-z*ty, py+w*ty+z*tx-x*tz, pz+w*tz+x*ty-y*tx]
    return {'position': position, 'rotation_xyzw': [x,y,z,w], 'scale': [1,1,1]}


def _skin_inverse_binds(actual, expected_bones):
    names, poses = actual['skin_bind_names'], actual['skin_bind_poses']
    need(len(names) == len(set(names)) == len(poses) and set(names) == set(expected_bones),
         'CONSUMER_SKIN_BIND_POSE_SET')
    # Godot 4.7.2 copies each glTF inverseBindMatrices row into the named Skin
    # bind. Match by exact joint name, never by Skeleton3D's reorderable index.
    for name, pose in zip(names, poses):
        _trs(pose, _inverse_rigid_trs(expected_bones[name]['rest_gltf_world']))


def _nav_path(role, mesh, observed, name):
    """Verify actual synchronized server queries over the imported proxy top.

    This fixture has a convex 6x4m floor. Two diagonal routes must reach their
    exact insets on that floor; nearest-point snapping, counts or an enabled
    region alone cannot establish reachability.
    """
    bounds = mesh['gltf_world_bounds']
    low, high = _numbers(bounds['min'], 3), _numbers(bounds['max'], 3)
    need(role.get('surface_policy') == 'imported_box_top_triangles' and
         type(role.get('vertices')) is int and role['vertices'] == 4 and
         type(role.get('polygons')) is int and role['polygons'] == 2, 'CONSUMER_NAV_TOP_SURFACE')
    vertices = role.get('surface_vertices_world')
    need(type(vertices) is list and len(vertices) == 4, 'CONSUMER_NAV_TOP_VERTICES')
    corners = [[x,high[1],z] for x in (low[0],high[0]) for z in (low[2],high[2])]
    matched = set()
    for vertex in vertices:
        _numbers(vertex, 3)
        indices = [index for index,corner in enumerate(corners) if math.dist(vertex,corner) <= .001]
        need(len(indices) == 1, 'CONSUMER_NAV_TOP_VERTICES')
        matched.add(indices[0])
    need(len(matched) == 4, 'CONSUMER_NAV_TOP_VERTICES')
    _near([role.get('surface_area')], [(high[0]-low[0])*(high[2]-low[2])], .0001)
    query = _fields(role.get('path_query'), ('pid','source_sha256','consumer_sha256','map_id','region_id','region_name',
        'map_active','region_enabled','navigation_layers','map_iteration','map_iteration_after','region_iteration',
        'sync_wait_frames','sync_elapsed_ms','physics_frame','sync_observations','optimize','queries'), 'CONSUMER_NAV_QUERY_FIELDS')
    need(type(query['pid']) is int and query['pid'] == observed['pid'] and
         query['source_sha256'] == observed['input_sha256']['fixture.glb'] and
         query['consumer_sha256'] == observed['consumer_sha256'], 'CONSUMER_NAV_QUERY_SOURCE')
    for field in ('map_id','region_id','map_iteration','region_iteration','physics_frame'):
        need(type(query[field]) is int and query[field] > 0, 'CONSUMER_NAV_SYNC_READBACK')
    need(type(role.get('map_iteration_before')) is int and role['map_iteration_before'] >= 0 and
         type(query['map_iteration_after']) is int and
         role['map_iteration_before'] < query['map_iteration'] == query['map_iteration_after'], 'CONSUMER_NAV_SYNC_READBACK')
    need(type(query['sync_wait_frames']) is int and 0 <= query['sync_wait_frames'] <= 120 and
         type(query['sync_elapsed_ms']) is int and 0 <= query['sync_elapsed_ms'] <= 2000, 'CONSUMER_NAV_SYNC_BUDGET')
    history = query['sync_observations']
    need(type(history) is list and len(history) == query['sync_wait_frames']+1, 'CONSUMER_NAV_SYNC_HISTORY')
    previous = {'map_iteration': 0, 'region_iteration': 0, 'physics_frame': 0}
    for index, sample in enumerate(history):
        _fields(sample, ('map_iteration','region_iteration','physics_frame','endpoint_owner_region_ids'),
                'CONSUMER_NAV_SYNC_HISTORY')
        for field in ('map_iteration','region_iteration'):
            need(type(sample[field]) is int and previous[field] <= sample[field] <= query[field],
                 'CONSUMER_NAV_SYNC_HISTORY')
        need(type(sample['physics_frame']) is int and
             previous['physics_frame'] < sample['physics_frame'] <= query['physics_frame'], 'CONSUMER_NAV_SYNC_HISTORY')
        owners = sample['endpoint_owner_region_ids']
        need(type(owners) is list and len(owners) == 4 and all(type(owner) is int and owner >= 0 for owner in owners),
             'CONSUMER_NAV_SYNC_HISTORY')
        ready = (sample['map_iteration'] > role['map_iteration_before'] and sample['region_iteration'] > 0 and
                 all(owner == query['region_id'] for owner in owners))
        # A region can finish building while the map still queries its older
        # empty snapshot. Iteration counters alone must never end this wait.
        need(ready is (index == len(history)-1), 'CONSUMER_NAV_SYNC_SNAPSHOT')
        previous = sample
    need(all(history[-1][field] == query[field] for field in ('map_iteration','region_iteration','physics_frame')),
         'CONSUMER_NAV_SYNC_HISTORY')
    need(query['map_active'] is True and query['region_enabled'] is True and query['optimize'] is True and
         type(query['navigation_layers']) is int and query['navigation_layers'] == 1 and
         query['region_name'] == name+'_region', 'CONSUMER_NAV_QUERY_REGION')
    routes = {'diagonal_a': ([low[0]+.5,high[1],low[2]+.5], [high[0]-.5,high[1],high[2]-.5]),
              'diagonal_b': ([low[0]+.5,high[1],high[2]-.5], [high[0]-.5,high[1],low[2]+.5])}
    _fields(query['queries'], routes, 'CONSUMER_NAV_QUERY_SET')
    for label, (start,end) in routes.items():
        row = _fields(query['queries'][label], ('requested_start','requested_end','points','surface_points',
            'surface_normals','owner_region_ids','path_length'), 'CONSUMER_NAV_PATH_FIELDS')
        _near(row['requested_start'], start, .001, euclidean=True)
        _near(row['requested_end'], end, .001, euclidean=True)
        points = row['points']
        need(type(points) is list and 2 <= len(points) <= 32 and
             all(type(row[key]) is list and len(row[key]) == len(points)
                 for key in ('surface_points','surface_normals','owner_region_ids')), 'CONSUMER_NAV_PATH_SIZE')
        _near(points[0], start, .001, euclidean=True)
        _near(points[-1], end, .001, euclidean=True)
        for index, point in enumerate(points):
            _numbers(point, 3)
            need(abs(point[1]-high[1]) <= .001 and low[0]-.001 <= point[0] <= high[0]+.001 and
                 low[2]-.001 <= point[2] <= high[2]+.001, 'CONSUMER_NAV_WALKABLE_FLOOR')
            _near(row['surface_points'][index], point, .001, euclidean=True)
            _near(row['surface_normals'][index], [0,1,0], .0001)
            need(type(row['owner_region_ids'][index]) is int and row['owner_region_ids'][index] == query['region_id'],
                 'CONSUMER_NAV_PATH_OWNER')
        length = sum(math.dist(a,b) for a,b in zip(points, points[1:]))
        _near([row['path_length']], [length], .001)
        need(length > 0 and abs(length-math.dist(start,end)) <= .001, 'CONSUMER_NAV_PATH_REACHABILITY')


def compare_observation(producer, observed):
    """Compare actual native values; counts/flags supplied by a caller are no proof.

    Complete GLB admission and actual owned process exits remain host gates.
    Exact fixture identities live in producer.contract; tolerance lives in the
    predeclared asset profile. Returns checked counts, never publication rights.
    """
    need(producer['schema'] == contract.SCHEMA and producer['catalog'] == contract.asset_catalog(),
         'CONSUMER_EXPECTED_SCHEMA')
    expected = producer['observed']
    need(contract.digest(expected) == producer['observed_sha256'], 'CONSUMER_EXPECTED_HASH')
    need(observed['schema'] == 'HH-GT05-GODOT-OBSERVATION-1' and observed['formal_acceptance'] is False,
         'CONSUMER_OBSERVED_SCHEMA')
    need(observed['input_sha256']['fixture.glb'] == producer['artifacts']['fixture.glb']['sha256'],
         'CONSUMER_OBSERVED_ARTIFACT')
    fixed_nodes = {node['name']: dict(node, asset_id=asset['asset_id'])
                   for asset in contract.asset_catalog()['assets'] for node in asset['nodes'] if node['role'] != 'rig'}
    need(set(expected['meshes']) == set(fixed_nodes) and set(expected['rig']['bones']) == {bone[0] for bone in contract.BONES}
         and set(expected['clips']) == {'idle','walk'}, 'CONSUMER_REQUIRED_FIXTURE')
    need(set(observed['meshes']) == set(expected['meshes']), 'CONSUMER_MESH_SET')
    need(set(observed['rigs']) == {'chr_fixture_avatar'}, 'CONSUMER_RIG_SET')
    actual_rig = observed['rigs']['chr_fixture_avatar']
    bone_rows = {bone['name']: bone for bone in actual_rig['bones']}
    need(len(bone_rows) == len(actual_rig['bones']) and set(bone_rows) == set(expected['rig']['bones']),
         'CONSUMER_BONE_MIGRATION_REQUIRED')
    for name, bone in expected['rig']['bones'].items():
        actual = bone_rows[name]
        need(actual['parent'] == (bone['parent'] or ''), 'CONSUMER_BONE_PARENT')
        _trs(actual['rest_local'], bone['rest_gltf_local']); _trs(actual['rest_world'], bone['rest_gltf_world'])
    skin_vertices = 0
    for name, mesh in expected['meshes'].items():
        required = fixed_nodes[name]
        need(all(mesh.get(key) == value for key,value in required.items() if key != 'name'), 'CONSUMER_FIXED_ROLE_BINDING')
        actual = observed['meshes'][name]
        need(actual['name'] == name and actual['triangles'] == mesh['triangles'], 'CONSUMER_MESH_IDENTITY_TOPOLOGY')
        _near(actual['bounds_world_min'], mesh['gltf_world_bounds']['min'], .001)
        _near(actual['bounds_world_max'], mesh['gltf_world_bounds']['max'], .001)
        _trs(actual['transform_world'], mesh['gltf_world_transform'])
        materials = [surface['material']['name'] for surface in actual['surfaces']]
        need(materials == mesh['materials'], 'CONSUMER_MATERIAL_BINDING')
        for surface in actual['surfaces']:
            material = surface['material']; source = expected['materials'][material['name']]
            _near(_albedo_linear(material['base_color']), source.get('gltf_base_color_factor', source['base_color']), .0001)
            need(abs(material['metallic']-source.get('gltf_metallic_factor', source['metallic'])) <= .0001 and
                 abs(material['roughness']-source.get('gltf_roughness_factor', source['roughness'])) <= .0001,
                 'CONSUMER_PBR_FACTORS')
            need(material['transparency'] == 0 and material['cull_mode'] == (2 if source['double_sided'] else 0),
                 'CONSUMER_PBR_POLICY')
            need(bool(material['textures']) == bool(source['images']), 'CONSUMER_TEXTURE_PRESENCE')
            for texture in material['textures'].values():
                need(type(texture['width']) is int and 0 < texture['width'] <= 4096 and
                     type(texture['height']) is int and 0 < texture['height'] <= 4096 and
                     len(texture['decoded_rgba8_sha256']) == 64, 'CONSUMER_TEXTURE_READBACK')
            bindings = source.get('texture_bindings', {})
            for semantic, slots in (('base_color', ('0',)), ('normal', ('4',)), ('metallic_roughness', ('1','2'))):
                if semantic not in bindings:
                    continue
                image = expected['images'][bindings[semantic]]
                for slot in slots:
                    texture = material['textures'].get(slot, material['textures'].get('17') if semantic == 'metallic_roughness' else None)
                    need(texture is not None and texture['width'] == image['width'] and texture['height'] == image['height']
                         and texture['decoded_rgba8_sha256'] == image['rgba8_sha256'], 'CONSUMER_DECODED_IMAGE_BINDING')
            if 'normal' in bindings:
                need(material['normal_enabled'] is True and abs(material['normal_scale']-source['normal_scale']) <= .0001,
                     'CONSUMER_NORMAL_BASIS')
            if 'metallic_roughness' in bindings and '17' not in material['textures']:
                need(material['metallic_channel'] == 2 and material['roughness_channel'] == 1, 'CONSUMER_ORM_CHANNEL_BASIS')
        if mesh['skinned']:
            need(actual['skeleton_path'] == actual_rig['path'] and set(actual['skin_bind_names']) <= set(bone_rows)
                 and len(actual['skin_bind_names']) == len(set(actual['skin_bind_names'])) > 0, 'CONSUMER_SKIN_BINDING')
            identity = {'position': [0,0,0], 'rotation_xyzw': [0,0,0,1], 'scale': [1,1,1]}
            _trs(mesh['gltf_world_transform'], identity)
            _skin_inverse_binds(actual, expected['rig']['bones'])
            parts = contract.OUTFIT if mesh['asset_id'] == 'chr_fixture_outfit' else contract.BODY
            positions, _, weights = contract.box_geometry(parts, 2 if mesh['lod'] == 0 else 1)
            target = [([p[0], p[2], -p[1]], {bone: 1.0}) for p,bone in zip(positions, weights)]
            seen = set()
            for vertex in actual['vertices']:
                _numbers(vertex['world'], 3)
                matches = [index for index,(position,weight) in enumerate(target)
                           if math.dist(vertex['world'],position) <= .001 and vertex['weights'] == weight]
                need(bool(matches), 'CONSUMER_SKIN_VERTEX_BINDING')
                seen.update(matches); skin_vertices += 1
            need(len(seen) == len(target), 'CONSUMER_SKIN_VERTEX_OMITTED')
        else:
            need(not actual['skin_bind_names'] and all(not v['weights'] for v in actual['vertices']), 'CONSUMER_UNEXPECTED_SKIN')
        role = observed['roles'][name]
        need(role['kind'] == mesh['role'], 'CONSUMER_EXPLICIT_ROLE')
        if mesh['role'] == 'render':
            need(role['lod'] == mesh['lod'], 'CONSUMER_EXPLICIT_LOD')
            paired = mesh['asset_id'] in ('chr_fixture_avatar', 'chr_fixture_outfit')
            for level in (0,1):
                need(observed['lod'+str(level)][name] is (mesh['lod'] == level if paired else True), 'CONSUMER_LOD_READBACK')
        elif mesh['role'] == 'collider':
            need(role['body_class'] == 'StaticBody3D' and role['shape_class'] == 'ConcavePolygonShape3D'
                 and role['face_vertices'] == mesh['triangles']*3 and role['disabled'] is False, 'CONSUMER_COLLIDER_READBACK')
            need(role['ray']['collider'] == name+'_body', 'CONSUMER_COLLIDER_RAY_BINDING')
            bounds = mesh['gltf_world_bounds']
            _near(role['ray']['position'], [(bounds['min'][0]+bounds['max'][0])/2, bounds['max'][1],
                                           (bounds['min'][2]+bounds['max'][2])/2], .001, euclidean=True)
        elif mesh['role'] == 'nav':
            need(role['region_class'] == 'NavigationRegion3D' and role['polygons'] > 0
                 and role['vertices'] > 0 and role['enabled'] is True, 'CONSUMER_NAV_READBACK')
            _nav_path(role, mesh, observed, name)
    need(set(observed['clips']) == {'idle','walk'}, 'CONSUMER_CLIP_SET')
    need(observed['animation_import'] == {'player_path': 'AnimationPlayer',
        'optimizer_enabled': False, 'compression_enabled': False}, 'CONSUMER_ANIMATION_IMPORT_POLICY')
    samples_checked = 0
    for name in ('idle','walk'):
        clip, source = observed['clips'][name], expected['clips'][name]
        need(source['fps'] == 30 and source['frame_start'] == 0 and source['frame_end'] == 30
             and source['duration_seconds'] == 1 and source['loop'] is True and source['root_motion'] == 'in_place'
             and source['events'] == [], 'CONSUMER_FIXED_CLIP_PROFILE')
        need(clip['loop_mode'] == 1 and abs(clip['length']-source['duration_seconds']) <= 1/30
             and len(clip['track_types']) > 0 and all(kind in (1,2,3) for kind in clip['track_types']), 'CONSUMER_CLIP_CONTRACT')
        _near([sample['time'] for sample in clip['samples']], SAMPLE_TIMES, 1e-8)
        tracks = clip['tracks']
        need(len(tracks) == len(bone_rows)*3 and
             {(track['bone'], track['type']) for track in tracks} ==
             {(bone,kind) for bone in bone_rows for kind in (1,2,3)}, 'CONSUMER_ANIMATION_TRACK_SET')
        for track in tracks:
            need(track['keys'] == 31 and track['compressed'] is False and track['interpolation'] == 1,
                 'CONSUMER_ANIMATION_KEY_READBACK')
            _near(track['times'], [frame/30 for frame in range(31)], 1e-6)
        for sample in clip['samples']:
            candidates = [row for row in source['samples'] if abs(row['time']-sample['time']) < 1e-8]
            need(len(candidates) == 1, 'CONSUMER_EXPECTED_SAMPLE')
            wanted = candidates[0]
            bones = sample['rigs']['chr_fixture_avatar']['bones']
            need({bone['name'] for bone in bones} == set(bone_rows) and len(bones) == len(bone_rows), 'CONSUMER_POSE_BONES')
            for bone in bones:
                # Skeleton3D pose is the complete local bone transform.
                _trs(bone['pose_local'], wanted['bones'][bone['name']]['local'])
                _trs(bone['pose_world'], wanted['bones'][bone['name']]['world'])
                samples_checked += 1
            for socket in sample['sockets'].values():
                _trs(socket['source_world'], wanted['socket_world']); _trs(socket['authored_world'], wanted['socket_world'])
    need(set(observed['sockets']) == {'socket_hand_r'}, 'CONSUMER_SOCKET_SET')
    socket = observed['sockets']['socket_hand_r']; wanted = expected['sockets']['socket_hand_r']
    need(socket['bone'] == wanted['bone'] and socket['bone_index'] >= 0 and socket['override_pose'] is False,
         'CONSUMER_ATTACHMENT_BINDING')
    _trs(socket['source_world'], wanted['rest_gltf_world']); _trs(socket['authored_world'], wanted['rest_gltf_world'])
    authored = observed['authored']
    need(authored['marker'] == 'gt05-authored-consumer-v1' and authored['script'] == 'res://authored.gd'
         and authored['override_mesh'] == 'prp_fixture_crate_lod0'
         and authored['material']['name'] == 'mat_authored_override', 'CONSUMER_AUTHORED_STATE')
    _near(authored['material']['base_color'], [.18,.48,.72,1], .0001)
    if observed.get('phase') == 'visual':
        _verify_visual_observation(observed)
    return {'meshes': len(expected['meshes']), 'bones': len(bone_rows), 'pose_bones': samples_checked,
            'skin_vertices': skin_vertices, 'clips': 2, 'formal_acceptance': False}
