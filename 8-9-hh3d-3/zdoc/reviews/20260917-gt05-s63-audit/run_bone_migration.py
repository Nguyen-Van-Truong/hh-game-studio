"""Two bounded native bone edits; unsupported migration must fail admission.

Only the literal-pinned original repeat fixture is opened. No export, publisher,
editor command, arbitrary asset path or automatic migration is exposed here.
The coordinator invokes this driver when it owns the serial native-engine lane.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[2]
STUDIO = PROJECT / 'studio'
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(STUDIO / 'tests/pipeline'))
from run_unit_suite import source_files

BASELINE = 'gt05-producer-repeat-01'
PINS = {
    'fixture.blend': 'ad88ee8d6c15d85acc7332d6896818f82309869a57c9cf4667ea91019a245956',
    'fixture.glb': 'e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377',
    'producer-report.json': '13a0416950aa2f6e4589442e1fa917c023bfe8395af717f803d1a1362fce8eee',
}
BONE = 'bn_head'
NEW_BONE = 'bn_head_migrated'
CASES = ('rename', 'delete')
MARKER = 'GT05_BONE_MIGRATION_REJECTED '


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read(path, cap=32 * 1024 * 1024):
    for part in (path, *path.parents):
        info = part.lstat()
        need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
    need(path.is_file() and path.stat().st_size <= cap, 'FILE_CAP_OR_KIND')
    raw = path.read_bytes()
    need(len(raw) <= cap, 'FILE_CAP_OR_KIND')
    return raw


def write(path, value):
    with path.open('xb') as stream:
        stream.write(encoded(value) + b'\n')


def owned(run_id):
    need(type(run_id) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run_id), 'RUN_ID')
    return STUDIO / '.local/reviews' / run_id


def graph(root):
    """Exact retained files, including private custody and visible payloads."""
    need(root.is_dir(), 'LAST_GOOD_MISSING')
    result = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = sha(read(path))
    need(result, 'LAST_GOOD_EMPTY')
    return result


def dependencies(glb, producer):
    """Resolve exact consumer references from pinned GLB bytes and catalog."""
    from studio.pipeline.glb_container import inspect_glb
    from studio.pipeline.accessor_values import decode_accessors
    need(sha(glb) == PINS['fixture.glb'], 'BASELINE_GLB_PIN')
    container = inspect_glb(glb)
    values = decode_accessors(container)
    document = container.document
    nodes = document['nodes']
    targets = [i for i, node in enumerate(nodes) if node.get('name') == BONE]
    need(len(targets) == 1, 'BASELINE_BONE_ID')
    target = targets[0]
    catalog = producer['catalog']['assets']
    node_owners = {node['name']: asset['asset_id'] for asset in catalog for node in asset['nodes']}
    owners = [asset['asset_id'] for asset in catalog if BONE in asset['bones']]
    need(len(owners) == 1, 'BASELINE_BONE_OWNER')
    parents = {child: index for index, node in enumerate(nodes) for child in node.get('children', ())}
    skins, meshes, clips, sockets = [], [], [], []
    for index, skin in enumerate(document['skins']):
        if target not in skin['joints']:
            continue
        joint = skin['joints'].index(target)
        skins.append({'skin_index': index, 'skin_id': skin['name'], 'joint_index': joint,
            'joint_node_index': target, 'joint_count': len(skin['joints']),
            'inverse_bind_accessor': skin['inverseBindMatrices']})
        for node_index, node in enumerate(nodes):
            if node.get('skin') != index:
                continue
            primitives = []
            for primitive_index, primitive in enumerate(document['meshes'][node['mesh']]['primitives']):
                joints = primitive['attributes']['JOINTS_0']; weights = primitive['attributes']['WEIGHTS_0']
                weighted = sum(any(j == joint and w > 0 for j, w in zip(js, ws))
                    for js, ws in zip(values[joints].values, values[weights].values))
                primitives.append({'primitive_index': primitive_index, 'joints_accessor': joints,
                    'weights_accessor': weights, 'weighted_vertices': weighted})
            meshes.append({'node_index': node_index, 'mesh_index': node['mesh'], 'mesh_id': node['name'],
                'asset_id': node_owners[node['name']], 'skin_index': index, 'primitives': primitives,
                'directly_weighted_vertices': sum(p['weighted_vertices'] for p in primitives)})
    for index, animation in enumerate(document['animations']):
        channels = [{'channel_index': i, 'path': channel['target']['path'], 'sampler': channel['sampler']}
            for i, channel in enumerate(animation['channels']) if channel['target']['node'] == target]
        if channels:
            clips.append({'animation_index': index, 'clip_id': animation['name'], 'channels': channels})
    for asset in catalog:
        for name in asset['sockets']:
            found = [i for i, node in enumerate(nodes) if node.get('name') == name]
            need(len(found) == 1, 'BASELINE_SOCKET_ID')
            ancestors = []; current = found[0]
            while current in parents:
                current = parents[current]; ancestors.append(current)
            sockets.append({'socket_id': name, 'node_index': found[0], 'asset_id': asset['asset_id'],
                'bone': producer['observed']['sockets'][name]['bone'],
                'ancestor_node_indices': ancestors, 'affected_by_changed_bone': target in ancestors})
    need(skins and meshes and clips and any(m['directly_weighted_vertices'] for m in meshes), 'BASELINE_DEPENDENCIES')
    need(sockets and not any(s['affected_by_changed_bone'] for s in sockets), 'NON_SOCKET_BONE_REQUIRED')
    return {'bone_id': BONE, 'bone_node_index': target, 'owner_asset_id': owners[0],
        'baseline_glb_sha256': sha(glb), 'catalog_sha256': sha(encoded(producer['catalog'])),
        'skins': skins, 'meshes': meshes, 'clips': clips, 'sockets': sockets,
        'affected_ids': {'bones': [BONE], 'skins': [s['skin_id'] for s in skins],
            'meshes': [m['mesh_id'] for m in meshes], 'clips': [c['clip_id'] for c in clips],
            'sockets': [s['socket_id'] for s in sockets if s['affected_by_changed_bone']]},
        'interpretation': 'All meshes sharing the changed skin need migration review; direct weight counts distinguish geometry influence. Socket ancestry is checked separately.'}


def native_state(bpy, producer):
    rig = bpy.data.objects[producer.c.RIG]
    weights = {}
    for obj in bpy.context.scene.objects:
        if obj.type == 'MESH' and any(m.type == 'ARMATURE' and m.object is rig for m in obj.modifiers):
            counts = {}
            for vertex in obj.data.vertices:
                for group in vertex.groups:
                    if group.weight > 0:
                        name = obj.vertex_groups[group.group].name
                        counts[name] = counts.get(name, 0) + 1
            weights[obj.name] = counts
    return {'bones': sorted(b.name for b in rig.data.bones), 'weighted_vertex_groups': weights,
        'sockets': {obj.name: obj.parent_bone for obj in bpy.context.scene.objects
            if obj.parent is rig and obj.parent_type == 'BONE'}}


def worker(run_id, case):
    need(case in CASES, 'CASE')
    root = owned(run_id); lane = root / case; work = lane / 'work'
    config = json.loads(read(root / 'invocation.json'))
    need(config['run_id'] == run_id and config['baseline_run_id'] == BASELINE, 'INVOCATION_BINDING')
    need(source_files(STUDIO) == config['source_files'] and sha(read(Path(__file__))) == config['driver_sha256'], 'SOURCE_DRIFT')
    baseline = {name: read(work / name) for name in PINS}
    need({name: sha(raw) for name, raw in baseline.items()} == PINS, 'FIXED_BASELINE_PIN')
    original = json.loads(baseline['producer-report.json'])
    refs = dependencies(baseline['fixture.glb'], original)
    need(refs == config['dependencies'], 'DEPENDENCY_BINDING')
    path = STUDIO / 'pipeline/producer/run_blender.py'
    spec = importlib.util.spec_from_file_location('gt05_bone_native_producer', path)
    producer = importlib.util.module_from_spec(spec); spec.loader.exec_module(producer)
    import bpy
    pins = producer.pins(bpy)
    need(pins == original['pins'], 'PRODUCER_RUNTIME_PIN')
    need(bpy.ops.wm.open_mainfile(filepath=str(work / 'fixture.blend'), load_ui=False, use_scripts=False) == {'FINISHED'}, 'BASELINE_OPEN')
    before = producer.observe(bpy); producer.admit_observation(before)
    need(before == original['observed'], 'BASELINE_NATIVE_READBACK')
    native_before = native_state(bpy, producer)
    rig = bpy.data.objects[producer.c.RIG]
    bone = rig.data.bones[BONE]
    need(bone.parent is not None and not bone.children and BONE not in native_before['sockets'].values(), 'SAFE_BONE_SELECTION')
    if case == 'rename':
        bone.name = NEW_BONE
    else:
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        rig.select_set(True); bpy.context.view_layer.objects.active = rig
        need(bpy.ops.object.mode_set(mode='EDIT') == {'FINISHED'}, 'EDIT_MODE')
        rig.data.edit_bones.remove(rig.data.edit_bones[BONE])
        need(bpy.ops.object.mode_set(mode='OBJECT') == {'FINISHED'}, 'OBJECT_MODE')
    bpy.context.view_layer.update()
    changed = work / 'changed.blend'
    bpy.context.preferences.filepaths.save_version = 0
    need(bpy.ops.wm.save_as_mainfile(filepath=str(changed), check_existing=False, compress=True) == {'FINISHED'}, 'CHANGED_SAVE')
    changed_raw = read(changed, producer.c.MAX_ARTIFACT)
    need(sha(changed_raw) != PINS['fixture.blend'], 'MUTATION_BYTES_REQUIRED')
    need(bpy.ops.wm.open_mainfile(filepath=str(changed), load_ui=False, use_scripts=False) == {'FINISHED'}, 'CHANGED_REOPEN')
    native_after = native_state(bpy, producer)
    expected = sorted((set(native_before['bones']) - {BONE}) | ({NEW_BONE} if case == 'rename' else set()))
    need(native_after['bones'] == expected and native_after['sockets'] == native_before['sockets'], 'NATIVE_BONE_DIFF')
    # Preserve actual observation failure if Blender cannot observe the edit.
    # A setup/observe exception never counts as the expected admission rejection.
    try:
        after = producer.observe(bpy)
    except Exception as error:
        write(lane / 'observation-failure.json', {'stage': 'observe', 'error': str(error),
            'native_before': native_before, 'native_after': native_after, 'formal_acceptance': False})
        raise
    write(lane / 'before-observation.json', before)
    write(lane / 'after-observation.json', after)
    rejected = None
    try:
        producer.admit_observation(after)
    except producer.c.ProducerRejected as error:
        rejected = str(error)
    need(rejected == 'OBSERVED_NAME_SET', 'EXACT_ADMISSION_REJECTION_REQUIRED')
    need(sorted(after['rig']['bones']) == expected and producer.pins(bpy) == pins, 'REOPENED_OBSERVATION_BINDING')
    need(sha(read(changed)) == sha(changed_raw) and {n: sha(read(work / n)) for n in PINS} == PINS, 'INPUT_OR_OUTPUT_CHANGED')
    need(set(p.name for p in work.iterdir()) == {*PINS, 'changed.blend'}, 'NO_EXPORT_OR_PUBLICATION')
    report = {'schema': 'HH-GT05-BONE-MIGRATION-1', 'run_id': run_id, 'case': case, 'native_pid': os.getpid(),
        'baseline_run_id': BASELINE, 'baseline_files': PINS, 'changed_blend_sha256': sha(changed_raw),
        'changed_blend_bytes': len(changed_raw), 'pins': pins, 'native_before': native_before, 'native_after': native_after,
        'bone_diff': {'missing': sorted(set(native_before['bones']) - set(native_after['bones'])),
            'added': sorted(set(native_after['bones']) - set(native_before['bones']))},
        'before_observation_sha256': sha(read(lane / 'before-observation.json')),
        'after_observation_sha256': sha(read(lane / 'after-observation.json')), 'dependencies': refs,
        'admission': {'stage': 'installed_admit_observation_after_save_reopen', 'error': rejected},
        'migration_required': True, 'unsupported': True, 'accepted_mapping': False,
        'proposed_mapping': {BONE: NEW_BONE if case == 'rename' else None},
        'migration_policy': 'unsupported bone rename/delete; regenerate dependent assets before resubmission',
        'automatic_migration_performed': False, 'export_performed': False, 'publication_performed': False,
        'public_ack': False, 'formal_acceptance': False}
    write(lane / 'report.json', report)
    need(source_files(STUDIO) == config['source_files'], 'SOURCE_DRIFT')
    print(MARKER + json.dumps({'case': case, 'native_pid': os.getpid(), 'report_sha256': sha(read(lane / 'report.json')),
        'changed_blend_sha256': sha(changed_raw), 'rejection': rejected, 'migration_required': True,
        'formal_acceptance': False}), flush=True)


def run(run_id, last_good_run_id):
    from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
    from studio.pipeline.run_validation import captured_producer
    root = owned(run_id); last_good = owned(last_good_run_id)
    need(root != last_good and root != owned(BASELINE), 'RUN_ALIAS')
    previous = graph(last_good)
    receipt = json.loads(read(last_good / 'receipt.json'))
    need(receipt['status'] == 'COMMITTED' and receipt['public_ack'] is False, 'LAST_GOOD_COMMITTED_REQUIRED')
    baseline_root, producer, report_raw, payloads = captured_producer(BASELINE)
    baseline = {**payloads, 'producer-report.json': report_raw}
    need({name: sha(raw) for name, raw in baseline.items()} == PINS, 'FIXED_BASELINE_PIN')
    refs = dependencies(payloads['fixture.glb'], producer)
    before = source_files(STUDIO)
    driver = read(Path(__file__)); driver_name = Path(__file__).relative_to(PROJECT).as_posix()
    stage_sources = {'studio/' + name: digest for name, digest in before.items()}
    stage_sources[driver_name] = sha(driver)
    root.mkdir(exist_ok=False)
    (root / 'driver.snapshot').write_bytes(driver)
    for name, digest in before.items():
        raw = read(STUDIO / name); need(sha(raw) == digest, 'SOURCE_DRIFT')
        target = root / 'source' / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    config = {'schema': 'HH-GT05-BONE-MIGRATION-INVOCATION-1', 'run_id': run_id,
        'baseline_run_id': BASELINE, 'baseline_files': PINS, 'source_files': before,
        'driver_sha256': sha(driver), 'driver_path': driver_name, 'dependencies': refs,
        'last_good_run_id': last_good_run_id, 'last_good_graph': previous, 'timeout_seconds_per_case': 20,
        'cases': list(CASES), 'formal_acceptance': False}
    write(root / 'invocation.json', config)
    binary = STUDIO / '.local/tooling/blender-5.2.1-windows-x64/blender.exe'
    binary_sha = json.loads(read(STUDIO / 'toolchain.lock.json'))['blender']['executable_sha256']
    rows = []
    for case in CASES:
        lane = root / case; work = lane / 'work'; work.mkdir(parents=True)
        for name, raw in baseline.items():
            (work / name).write_bytes(raw)
        files = {**stage_sources, (root / 'invocation.json').relative_to(PROJECT).as_posix(): sha(read(root / 'invocation.json'))}
        files.update({(work / name).relative_to(PROJECT).as_posix(): digest for name, digest in PINS.items()})
        write(lane / 'source-files.json', files)
        argv = [str(binary), '--background', '--factory-startup', '--disable-autoexec', '--offline-mode',
            '--threads', '1', '--python-exit-code', '17', '--python', str(Path(__file__).resolve()),
            '--', '--worker', '--run-id', run_id, '--case', case]
        run_trusted_stage(argv, cwd=work, output=lane / 'host', source_root=PROJECT,
            source_files=files, binary_sha256=binary_sha, timeout_seconds=20)
        capture_sha = sha(read(lane / 'host/capture.json'))
        capture = verify_captured_stage(lane / 'host', capture_sha)
        raw = read(lane / 'report.json'); report = json.loads(raw)
        expected = {'case': case, 'native_pid': capture['actual_process_exit']['pid'], 'report_sha256': sha(raw),
            'changed_blend_sha256': sha(read(work / 'changed.blend')), 'rejection': 'OBSERVED_NAME_SET',
            'migration_required': True, 'formal_acceptance': False}
        stdout = read(lane / 'host/stdout.txt'); prefix = MARKER.encode()
        markers = [json.loads(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
        need(markers == [expected] and report['native_pid'] == expected['native_pid']
            and report['changed_blend_sha256'] == expected['changed_blend_sha256'], 'NATIVE_MARKER_BINDING')
        need(not read(lane / 'host/stderr.txt').strip(), 'NATIVE_STDERR')
        need(not any(word in line for line in stdout.splitlines() for word in (b'WARNING', b'ERROR', b'Error:')), 'NATIVE_UNEXPLAINED_LOG')
        need(graph(last_good) == previous and {name: sha(read(baseline_root / 'fixture' / name)) for name in PINS} == PINS,
            'LAST_GOOD_OR_BASELINE_CHANGED')
        rows.append({'case': case, 'host_capture_sha256': capture_sha, 'report_sha256': sha(raw),
            'changed_blend_sha256': expected['changed_blend_sha256'], 'native_pid': expected['native_pid'],
            'rejection': 'OBSERVED_NAME_SET', 'last_good_unchanged': True})
    need(source_files(STUDIO) == before and sha(read(Path(__file__))) == sha(driver), 'SOURCE_DRIFT')
    summary = {'schema': 'HH-GT05-BONE-MIGRATION-CAPTURE-1', 'run_id': run_id, 'cases': rows,
        'invocation_sha256': sha(read(root / 'invocation.json')), 'last_good_graph': previous,
        'last_good_unchanged': True, 'migration_required': True, 'automatic_migration_performed': False,
        'public_ack': False, 'formal_acceptance': False}
    write(root / 'capture.json', summary)
    print(json.dumps({'run_id': run_id, 'cases': 2, 'capture_sha256': sha(read(root / 'capture.json')),
        'migration_required': True, 'formal_acceptance': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--last-good-run-id')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--case', choices=CASES)
    arguments = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(arguments)
    if args.worker:
        need(args.last_good_run_id is None, 'WORKER_ARGUMENTS')
        worker(args.run_id, args.case)
    else:
        need(args.case is None and args.last_good_run_id is not None, 'DRIVER_ARGUMENTS')
        run(args.run_id, args.last_good_run_id)


if __name__ == '__main__':
    main()
