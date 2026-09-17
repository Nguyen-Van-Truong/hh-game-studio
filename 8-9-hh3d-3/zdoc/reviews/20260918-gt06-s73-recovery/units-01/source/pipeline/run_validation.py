"""Fixed diagnostic admission of a captured original producer, then Khronos.

All results remain candidate evidence. This does not publish or activate assets.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import sys

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
from studio.pipeline.preflight import inspect_asset
from studio.pipeline.run_diagnostic import source_map, sha, write, producer_warnings


def need(value, code):
    if not value:
        raise ValueError(code)


def owned_run(run_id):
    need(type(run_id) is str and re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run_id), 'RUN_ID')
    return STUDIO / '.local/reviews' / run_id


def freeze_stage_sources(root, folder, files):
    """Copy the exact already-hashed bytes before releasing the child GO gate."""
    target_root = root / folder
    target_root.mkdir(exist_ok=False)
    for name, digest in files.items():
        raw = (STUDIO / name).read_bytes()
        need(sha(raw) == digest, 'VALIDATION_SOURCE_DRIFT_BEFORE_SNAPSHOT')
        target = target_root / (sha(name.encode()) + Path(name).suffix)
        with target.open('xb') as stream:
            stream.write(raw)


def captured_producer(run_id):
    root = owned_run(run_id)
    diagnostic = json.loads((root / 'diagnostic.json').read_bytes())
    verify_captured_stage(root / 'host', diagnostic['host_capture_sha256'])
    producer_warnings((root / 'host/stdout.txt').read_bytes(), (root / 'host/stderr.txt').read_bytes())
    need(type(diagnostic['source_files']) is dict and bool(diagnostic['source_files'])
         and diagnostic['source_files'] == json.loads((root / 'source-files.json').read_bytes()),
         'PRODUCER_SOURCE_MAP')
    for name, digest in diagnostic['source_files'].items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name,
             'PRODUCER_SOURCE_PATH')
        need(sha((root / 'source' / name).read_bytes()) == digest, 'PRODUCER_SOURCE_SNAPSHOT')
    raw_report = (root / 'fixture/producer-report.json').read_bytes()
    need(sha(raw_report) == diagnostic['report_sha256'], 'PRODUCER_REPORT_HASH')
    producer = json.loads(raw_report)
    pins = producer['pins']['source_files']
    need(type(pins) is dict and bool(pins)
         and all(diagnostic['source_files'].get(name) == digest for name, digest in pins.items())
         and producer['pins']['source_sha256'] == sha(json.dumps(pins, sort_keys=True,
             separators=(',', ':'), allow_nan=False).encode()), 'PRODUCER_SOURCE_PINS')
    need(producer['license'] == 'original-fixture' and producer['external_inputs'] == []
         and producer['artifacts'] == diagnostic['artifacts'], 'PRODUCER_PROVENANCE')
    need(set(producer['artifacts']) == {'fixture.glb', 'fixture.blend'}, 'PRODUCER_SLOT_SET')
    payloads = {}
    for name, item in producer['artifacts'].items():
        need(name in ('fixture.glb', 'fixture.blend'), 'PRODUCER_SLOT')
        raw = (root / 'fixture' / name).read_bytes()
        need(0 < len(raw) <= 1048576 and item == {'sha256': sha(raw), 'bytes': len(raw)}, 'PRODUCER_BYTES')
        payloads[name] = raw
    prefix = b'GT05_PRODUCER_COMPLETE '
    markers = [json.loads(line[len(prefix):]) for line in (root / 'host/stdout.txt').read_bytes().splitlines()
               if line.startswith(prefix)]
    need(markers == [{'variant': producer['variant'], 'source_sha256': producer['pins']['source_sha256'],
        'report_sha256': sha(raw_report), 'blend_bytes': len(payloads['fixture.blend']),
        'glb_bytes': len(payloads['fixture.glb']), 'formal_acceptance': False}], 'PRODUCER_CAPTURE_MARKER')
    return root, producer, raw_report, payloads


def validate(producer_id, run_id):
    upstream, producer, raw_producer, payloads = captured_producer(producer_id)
    root = owned_run(run_id)
    root.mkdir(exist_ok=False)
    raw = payloads['fixture.glb']
    # Decode BEFORE Khronos in its own resource-bounded Python Job; allocation
    # bounds alone do not establish a CPU/wall limit on the supervisor.
    admission = root / 'admission'
    admission.mkdir()
    (admission / 'fixture.glb').write_bytes(raw)
    write(admission / 'expected.json', {'artifact_sha256': sha(raw)})
    admission_script = STUDIO / 'pipeline/admission_worker.py'
    admission_files = source_map([admission_script, admission / 'fixture.glb', admission / 'expected.json'])
    write(root / 'admission-source-files.json', admission_files)
    freeze_stage_sources(root, 'admission-source', admission_files)
    admission_host = run_trusted_stage([sys.executable, '-B', str(admission_script), str(admission)],
        cwd=admission, output=root / 'admission-host', source_root=STUDIO, source_files=admission_files,
        binary_sha256=sha(Path(sys.executable).read_bytes()))
    raw_report = (admission / 'preflight.json').read_bytes()
    raw_semantic = (admission / 'semantic.json').read_bytes()
    need(len(raw_report) <= 1048576 and len(raw_semantic) <= 16 * 1048576, 'ADMISSION_OUTPUT_CAP')
    report = json.loads(raw_report)
    markers = [json.loads(line[len(b'GT05_ADMISSION_COMPLETE '):])
        for line in (root / 'admission-host/stdout.txt').read_bytes().splitlines()
        if line.startswith(b'GT05_ADMISSION_COMPLETE ')]
    need(markers == [{'artifact_sha256': sha(raw), 'preflight_sha256': sha(raw_report),
                      'semantic_sha256': sha(raw_semantic)}]
         and report['artifact_sha256'] == sha(raw)
         and not (root / 'admission-host/stderr.txt').read_bytes().strip(), 'ADMISSION_COMPLETION')
    admission_marker = markers[0]
    expected_images = producer['observed']['images']
    need(len(report['images']) == len(expected_images)
         and {item['name'] for item in report['images']} == set(expected_images), 'IMAGE_SET')
    for item in report['images']:
        expected = expected_images[item['name']]
        need(all(item[key] == expected[key] for key in ('width', 'height', 'rgba8_sha256')),
             'EXPORTED_PIXEL_MISMATCH')
    (root / 'preflight.json').write_bytes(raw_report)
    (root / 'semantic.json').write_bytes(raw_semantic)
    (root / 'producer-report.json').write_bytes(raw_producer)
    (root / 'fixture.glb').write_bytes(raw)
    write(root / 'admission.json', {'schema': 'HH-GT05-VALIDATOR-INPUT-1', 'artifact_sha256': sha(raw)})
    lock_path = STUDIO / 'pipeline/dependencies/gltf-validator.lock.json'
    lock = json.loads(lock_path.read_bytes())
    cache = STUDIO / '.local/tooling/gt05' / ('gltf-validator-' + lock['version'])
    extra = [STUDIO / 'pipeline/validate_glb.cjs', lock_path,
             STUDIO / 'pipeline/dependencies/node.lock.json']
    for name, digest in lock['files'].items():
        need(name.startswith('package/') and '..' not in name and '\\' not in name, 'DEPENDENCY_SLOT')
        source = cache / name
        need(sha(source.read_bytes()) == digest, 'DEPENDENCY_CACHE_HASH')
        target = root / 'dependency' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        extra.append(target)
    (root / 'gltf-validator.lock.json').write_bytes(lock_path.read_bytes())
    extra += [root / name for name in ('fixture.glb', 'admission.json', 'gltf-validator.lock.json')]
    files = source_map(extra)
    write(root / 'source-files.json', files)
    freeze_stage_sources(root, 'source', files)
    node = Path(shutil.which('node') or '')
    runtime = json.loads((STUDIO / 'pipeline/dependencies/node.lock.json').read_bytes())
    host = run_trusted_stage([str(node), '--max-old-space-size=256',
        str(STUDIO / 'pipeline/validate_glb.cjs'), str(root)], cwd=root, output=root / 'host',
        source_root=STUDIO, source_files=files, binary_sha256=runtime['binary_sha256'])
    raw_validator = (root / 'validator.json').read_bytes()
    validator = json.loads(raw_validator)
    need(validator['artifact_sha256'] == sha(raw) and not validator['external_resource_requested']
         and validator['validator_version'] == lock['version']
         and validator['dependency_lock_sha256'] == sha(lock_path.read_bytes())
         and validator['result']['issues']['numErrors'] == validator['result']['issues']['numWarnings'] == 0
         and validator['result']['issues']['truncated'] is False, 'VALIDATOR_RESULT')
    prefix = b'GT05_KHRONOS_COMPLETE '
    markers = [json.loads(line[len(prefix):]) for line in (root / 'host/stdout.txt').read_bytes().splitlines()
               if line.startswith(prefix)]
    need(markers == [{'artifact_sha256': sha(raw), 'report_sha256': sha(raw_validator)}], 'VALIDATOR_MARKER')
    manifest = {'schema': 'HH-GT05-ASSET-MANIFEST-1', 'profile_id': producer['profile_id'],
        'license': producer['license'], 'external_inputs': [], 'variant': producer['variant'],
        'source_pins': producer['pins'], 'artifacts': producer['artifacts'],
        'producer_report_sha256': sha(raw_producer), 'preflight_sha256': sha((root / 'preflight.json').read_bytes()),
        'validator_sha256': sha(raw_validator), 'semantic_sha256': report['semantic_sha256'],
        'semantic_hash_domain': report['semantic_hash_domain'], 'catalog': producer['catalog'],
        'formal_acceptance': False, 'public_ack': False}
    write(root / 'manifest.json', manifest)
    write(root / 'validation.json', {'run_id': run_id, 'upstream_run_id': producer_id,
        'manifest_sha256': sha((root / 'manifest.json').read_bytes()),
        'host_capture_sha256': sha((root / 'host/capture.json').read_bytes()),
        'admission_capture_sha256': sha((root / 'admission-host/capture.json').read_bytes()),
        'admission_outputs': admission_marker,
        'completed': host['completed'], 'formal_acceptance': False})
    print(json.dumps({'run_id': run_id, 'completed': True, 'preflight': report}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--producer-id', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    validate(args.producer_id, args.run_id)
