"""Read-only S62 repeat/edit check; outputs diagnostics, never acceptance."""
import hashlib
import json
from pathlib import Path
import sys

STUDIO = Path(__file__).resolve().parents[3] / 'studio'
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.preflight import compare_repeat, PreflightRejected


def verify():
    raw_root = STUDIO / '.local/reviews'
    names = ('gt05-producer-native-05', 'gt05-producer-repeat-01', 'gt05-producer-edited-01')
    reports = [json.loads((raw_root / name / 'fixture/producer-report.json').read_bytes()) for name in names]
    first, repeated, edited = reports
    assert first['pins'] == repeated['pins'] == edited['pins']
    assert first['observed'] == repeated['observed']
    assert first['observed_sha256'] == repeated['observed_sha256'] != edited['observed_sha256']
    changed_meshes = {'prp_fixture_crate_lod0', 'prp_fixture_crate_collider'}
    left = json.loads(json.dumps(first['observed']))
    right = json.loads(json.dumps(edited['observed']))
    for name in changed_meshes:
        before, after = left['meshes'].pop(name), right['meshes'].pop(name)
        assert before['geometry_sha256'] != after['geometry_sha256']
        for key in ('geometry_sha256', 'source_local_bounds', 'source_world_bounds', 'gltf_world_bounds'):
            before.pop(key); after.pop(key)
        assert before == after
        a = first['observed']['meshes'][name]['gltf_world_bounds']
        b = edited['observed']['meshes'][name]['gltf_world_bounds']
        assert abs((a['max'][0] - a['min'][0]) - .6) < .001
        assert abs((b['max'][0] - b['min'][0]) - .8) < .001
    assert left == right
    hashes = [hashlib.sha256((raw_root / name / 'fixture/fixture.glb').read_bytes()).hexdigest() for name in names]
    assert hashes[0] == hashes[1] != hashes[2]
    validations = ('gt05-validation-native-04', 'gt05-validation-repeat-01', 'gt05-validation-edited-01')
    semantics = [json.loads((raw_root / name / 'semantic.json').read_bytes()) for name in validations]
    repeat = compare_repeat(semantics[0], semantics[1])
    try:
        compare_repeat(semantics[0], semantics[2])
    except PreflightRejected as error:
        sensitivity = str(error)
    else:
        raise AssertionError('actual source edit did not change semantics')
    return {'producer_runs': names, 'validation_runs': validations, 'glb_sha256': hashes,
            'repeat': repeat, 'edited_rejects_repeat': sensitivity,
            'changed_meshes': sorted(changed_meshes), 'crate_width_m': [.6, .8],
            'formal_acceptance': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
