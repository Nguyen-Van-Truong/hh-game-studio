"""Mutate copies of one hash-bound GT05 native capture; never launch an engine.

Run this fixed worker under the coordinator's bounded owned Python Job. Its
result is diagnostic comparator evidence, not asset acceptance or publication.
Original captured input, source, reports and process logs are read-only.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import sys
import time
import traceback

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.godot import consumer
from studio.pipeline.native_job import verify_captured_stage
from studio.pipeline.run_consumer import admitted
from studio.pipeline.run_validation import owned_run
from studio.pipeline.run_diagnostic import sha, source_map

def need(value, code):
    if not value:
        raise ValueError(code)


def read_json(path):
    raw = path.read_bytes()
    return raw, consumer.strict(raw)


def bound_inputs(consumer_root, validation_root):
    consumer_id, validator_id = consumer_root.name, validation_root.name
    need(consumer_root == owned_run(consumer_id) and validation_root == owned_run(validator_id),
         'REJECTION_FIXED_ROOTS')
    raw_summary, summary = read_json(consumer_root / 'consumer.json')
    need(summary['run_id'] == consumer_id and summary['validator_run_id'] == validator_id
         and summary['formal_acceptance'] is False, 'REJECTION_FIXED_CAPTURE')
    glb, manifest_raw, producer_raw = admitted(validator_id)
    raw_observed, observed = read_json(consumer_root / 'project/out/baseline.json')
    need(sha(raw_observed) == summary['observation_sha256'], 'REJECTION_OBSERVATION_HASH')
    expected_inputs = {'fixture.glb': sha(glb), 'manifest.json': sha(manifest_raw),
                       'producer-report.json': sha(producer_raw)}
    need(observed['input_sha256'] == expected_inputs and observed['phase'] == 'baseline',
         'REJECTION_VALIDATED_INPUT_BINDING')
    for phase in ('import', 'baseline'):
        host = consumer_root / (phase + '-host')
        capture = verify_captured_stage(host, summary['host_captures'][phase])
        need(not (host / 'stderr.txt').read_bytes().strip(), 'REJECTION_CAPTURE_STDERR')
        if phase == 'baseline':
            need(observed['pid'] == capture['actual_process_exit']['pid'], 'REJECTION_NATIVE_PID')
            markers = [consumer.strict(line[len(b'GT05_GODOT_OBSERVED '):])
                for line in (host / 'stdout.txt').read_bytes().splitlines()
                if line.startswith(b'GT05_GODOT_OBSERVED ')]
            need(markers == [{'phase': 'baseline', 'pid': observed['pid'],
                'report_sha256': sha(raw_observed), 'formal_acceptance': False}], 'REJECTION_NATIVE_MARKER')
    raw_sources, sources = read_json(consumer_root / 'source-files.json')
    need(bool(sources), 'REJECTION_SOURCE_CLOSURE')
    snapshot = {}
    for name, digest in sources.items():
        need(type(name) is str and not Path(name).is_absolute() and not Path(name).drive
             and '\\' not in name and all(part not in ('', '.', '..') for part in name.split('/')),
             'REJECTION_SOURCE_SLOT')
        path = consumer_root / 'source' / (sha(name.encode()) + Path(name).suffix)
        raw = path.read_bytes()
        need(sha(raw) == digest, 'REJECTION_SOURCE_SNAPSHOT')
        snapshot[name] = raw
    for name in ('pipeline/godot/consumer.py', 'pipeline/producer/contract.py'):
        need(sources.get(name) == sha((STUDIO / name).read_bytes()), 'REJECTION_COMPARATOR_SOURCE_CHANGED')
    project_prefix = '.local/reviews/' + consumer_id + '/project/'
    for name, digest in expected_inputs.items():
        need(sources.get(project_prefix + 'input/' + name) == digest, 'REJECTION_FROZEN_INPUT')
    for name in consumer.SOURCES:
        need(observed['authored_sha256'].get(name) == sources.get(project_prefix + name),
             'REJECTION_FROZEN_AUTHORED')
    seed_raw = snapshot[project_prefix + 'input/consumer.json']
    seed = consumer.strict(seed_raw)
    need(sha(seed_raw) == observed['consumer_sha256'] and seed['input_sha256'] == expected_inputs
         and seed['authored_sha256'] == observed['authored_sha256'], 'REJECTION_FROZEN_CONSUMER_SEED')
    # Deliberately use frozen source/input slots, not mutable same-project input
    # after the coordinator's reimport experiment.
    bindings = {'consumer_run_id': consumer_id, 'validator_run_id': validator_id,
        'consumer_summary_sha256': sha(raw_summary), 'native_source_map_sha256': sha(raw_sources),
        'observation_sha256': sha(raw_observed), 'input_sha256': expected_inputs,
        'host_captures': summary['host_captures'],
        'validation_summary_sha256': sha((validation_root / 'validation.json').read_bytes())}
    return consumer.strict(producer_raw), observed, bindings


def cases():
    # Every mutation changes one real native field. Exact expected error codes
    # distinguish intended contract failures from a generic thrown exception.
    body = ('meshes', 'chr_fixture_avatar_lod0')
    crate = ('meshes', 'prp_fixture_crate_lod0', 'surfaces', 0, 'material')
    bone = ('rigs', 'chr_fixture_avatar', 'bones')
    return [
        ('mesh-scale', body+('transform_world','scale',0), 2.0, 'CONSUMER_NUMERIC_MISMATCH'),
        ('model-axis', ('meshes','env_fixture_axis_x_lod0','transform_world','rotation_xyzw'),
            [0,0,1,0], 'CONSUMER_ROTATION_MISMATCH'),
        ('world-bounds', body+('bounds_world_max',0), 20.0, 'CONSUMER_NUMERIC_MISMATCH'),
        ('missing-bone', bone, 'DELETE_LAST', 'CONSUMER_BONE_MIGRATION_REQUIRED'),
        ('renamed-bone', bone+(1,'name'), 'bn_unannounced_rename', 'CONSUMER_BONE_MIGRATION_REQUIRED'),
        ('bone-parent', bone+(1,'parent'), 'bn_head', 'CONSUMER_BONE_PARENT'),
        ('inverse-bind', body+('skin_bind_poses',0,'position',0), .01, 'CONSUMER_NUMERIC_MISMATCH'),
        ('skin-weight', body+('vertices',0,'weights'), {}, 'CONSUMER_SKIN_VERTEX_BINDING'),
        ('clip-trim', ('clips','idle','length'), .5, 'CONSUMER_CLIP_CONTRACT'),
        ('clip-loop', ('clips','walk','loop_mode'), 0, 'CONSUMER_CLIP_CONTRACT'),
        ('animation-keys', ('clips','idle','tracks',0,'keys'), 30, 'CONSUMER_ANIMATION_KEY_READBACK'),
        ('animation-optimizer', ('animation_import','optimizer_enabled'), True, 'CONSUMER_ANIMATION_IMPORT_POLICY'),
        ('animation-compression', ('clips','walk','tracks',0,'compressed'), True, 'CONSUMER_ANIMATION_KEY_READBACK'),
        ('missing-texture', crate+('textures','0'), 'DELETE_KEY', 'CONSUMER_DECODED_IMAGE_BINDING'),
        ('texture-pixels', crate+('textures','0','decoded_rgba8_sha256'), '0'*64, 'CONSUMER_DECODED_IMAGE_BINDING'),
        ('material-color', crate+('base_color',0), .5, 'CONSUMER_NUMERIC_MISMATCH'),
        ('material-roughness', crate+('roughness',), .125, 'CONSUMER_PBR_FACTORS'),
        ('socket-world', ('sockets','socket_hand_r','source_world','position',0), 20.0, 'CONSUMER_NUMERIC_MISMATCH'),
        ('authored-socket', ('sockets','socket_hand_r','authored_world','position',0), 20.0, 'CONSUMER_NUMERIC_MISMATCH'),
        ('socket-bone', ('sockets','socket_hand_r','bone'), 'bn_head', 'CONSUMER_ATTACHMENT_BINDING'),
        ('authored-script', ('authored','script'), 'res://generated.gd', 'CONSUMER_AUTHORED_STATE'),
        ('authored-material', ('authored','material','name'), 'mat_generated_override', 'CONSUMER_AUTHORED_STATE'),
        ('authored-color', ('authored','material','base_color',0), .5, 'CONSUMER_NUMERIC_MISMATCH'),
        ('lod-switch', ('lod1','chr_fixture_avatar_lod0'), True, 'CONSUMER_LOD_READBACK'),
        ('collider-ray', ('roles','prp_fixture_crate_collider','ray','collider'), 'wrong_body', 'CONSUMER_COLLIDER_RAY_BINDING'),
        ('nav-region', ('roles','env_fixture_axis_cube_nav','enabled'), False, 'CONSUMER_NAV_READBACK'),
        ('sampled-bone-pose', ('clips','idle','samples',1,'rigs','chr_fixture_avatar','bones',0,'pose_world','position',0),
            .01, 'CONSUMER_NUMERIC_MISMATCH'),
    ]


def mutate(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    old = target[path[-1]]
    if replacement == 'DELETE_LAST':
        need(type(old) is list and bool(old), 'REJECTION_VECTOR_NO_TARGET')
        old.pop()
    elif replacement == 'DELETE_KEY':
        del target[path[-1]]
    else:
        need(old != replacement, 'REJECTION_VECTOR_NO_CHANGE')
        target[path[-1]] = replacement


def run(consumer_root: Path, validation_root: Path, output_root: Path):
    start = time.monotonic()
    roots = [consumer._path(path) for path in (consumer_root, validation_root, output_root)]
    consumer_root, validation_root, output_root = roots
    owned = STUDIO / '.local/reviews'
    need(all(path.is_relative_to(owned) for path in roots) and not output_root.exists()
         and output_root.parent.is_dir(), 'REJECTION_OWNED_ROOTS')
    execution_sources = source_map([Path(__file__).resolve()])
    producer, observed, bindings = bound_inputs(consumer_root, validation_root)
    before = sha(consumer.encoded(observed))
    baseline = consumer.compare_observation(producer, observed)
    need(baseline == {'meshes':12,'bones':12,'pose_bones':792,'skin_vertices':2160,'clips':2,
                      'formal_acceptance':False}, 'REJECTION_BASELINE_COVERAGE')
    rows = []
    for name, path, replacement, expected_code in cases():
        need(time.monotonic()-start <= 16, 'REJECTION_WORKER_WALL_BUDGET')
        changed = copy.deepcopy(observed)
        mutate(changed, path, replacement)
        row = {'case': name, 'field': list(path), 'expected_error': expected_code,
               'mutated_observation_sha256': sha(consumer.encoded(changed)), 'rejected': False}
        try:
            consumer.compare_observation(producer, changed)
        except consumer.ConsumerRejected as error:
            row['actual_error'] = str(error)
            row['rejected'] = str(error) == expected_code
            row['check_sites'] = [{'function': frame.name, 'line': frame.lineno, 'source': frame.line}
                for frame in traceback.extract_tb(error.__traceback__)
                if Path(frame.filename).resolve() == Path(consumer.__file__).resolve()]
        except Exception as error:
            row['unexpected_exception'] = type(error).__name__
        rows.append(row)
    need(sha(consumer.encoded(observed)) == before, 'REJECTION_ORIGINAL_IN_MEMORY_CHANGED')
    _, _, after_bindings = bound_inputs(consumer_root, validation_root)
    need(after_bindings == bindings, 'REJECTION_ORIGINAL_CAPTURE_CHANGED')
    need(source_map([Path(__file__).resolve()]) == execution_sources, 'REJECTION_WORKER_SOURCE_CHANGED')
    passed = all(row['rejected'] for row in rows)
    report = {'schema':'HH-GT05-NATIVE-OBSERVATION-REJECTIONS-1', 'bindings':bindings,
        'execution_source_files':execution_sources, 'baseline_comparison':baseline, 'cases':rows,
        'all_expected_rejections_observed':passed, 'elapsed_seconds':time.monotonic()-start,
        'formal_acceptance':False, 'public_ack':False, 'independent_critic':False}
    output_root.mkdir()
    raw = json.dumps(report, indent=2, allow_nan=False).encode()+b'\n'
    need(len(raw) <= 262144, 'REJECTION_REPORT_CAP')
    with (output_root/'result.json').open('xb') as stream:
        stream.write(raw)
    print('GT05_REJECTIONS_COMPLETE '+json.dumps({'result_sha256':sha(raw),'cases':len(rows),
                      'all_expected_rejections_observed':passed,'formal_acceptance':False}))
    return 0 if passed else 17


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--consumer-root', type=Path, required=True)
    parser.add_argument('--validation-root', type=Path, required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.consumer_root, arguments.validation_root, arguments.output_root))
