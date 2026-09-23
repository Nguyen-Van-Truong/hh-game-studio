"""Read retained authoring evidence without launching an engine or rewriting raw.

Original collector failures remain failures. Derived evidence proves only the
listed artifact/exit bindings; absent parent receipts remain UNKNOWN.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio.protocol.core import canonical_bytes


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def safe(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('relative artifact path required')
    path = root / relative
    path.resolve().relative_to(root.resolve())
    for parent in [path, *path.parents]:
        if parent.exists() and (parent.is_symlink() or getattr(parent.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('reparse artifact path')
        if parent == root:
            break
    return path


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def clean_job(value):
    return (value.get('active_count') == 0 and value.get('closed') is True
        and value.get('zero_observed') is True and value.get('handle_retained') is False
        and value.get('close_uncertain') is False and not value.get('failed_operations'))


def verify_godot(root):
    original = read(root / 'author-result.json')
    response = read(root / 'save-response.json')
    saved = response['response']
    need(response['http_status'] == 200 and saved['status'] == 'COMMITTED'
         and saved['code'] == 'GODOT_MANAGED_SCENE_SAVED' and saved['postconditions']['public_ack'] is True,
         'committed native save required')
    need(hashlib.sha256(canonical_bytes(saved)).hexdigest() == response['wire_sha256'], 'save wire hash')
    adoptions = list((root / 'owned/editor').glob('editor-*/adoption-*.json'))
    need(len(adoptions) == 1, 'unique adoption required')
    adoption = read(adoptions[0])
    need(adoption['command_id'] == saved['command_id']
         and adoption['request_digest'] == saved['postconditions']['request_digest']
         and adoption['semantic_revision'] == saved['postconditions']['scene_revision']
         and adoption['selection'] == saved['postconditions']['selection'], 'save/adoption binding')
    directory = adoptions[0].parent
    close = read(directory / 'close.json')
    actual = read(directory / 'process-exit.json')
    need(actual == close['actual_process_exit'] and actual['pid'] == adoption['editor_pid']
         and actual['exit_code'] == 0 and close['wrapper_exit_code'] == 0
         and close['closed'] is True and clean_job(close['job']), 'Godot actual exit/cleanup')
    need(not (directory / 'stderr.txt').read_bytes(), 'editor stderr')
    map_data = read(root / 'map.json')
    need(map_data['source']['run_id'] == original['run_id'], 'map run identity')
    keys = ('stable_id', 'name', 'position', 'rotation_degrees', 'scale', 'box_size')
    projected = [{k: node[k] for k in keys} for node in adoption['semantic_state']['nodes']
                 if node['stable_id'] in ('floor', 'player', 'pickup')]
    need(projected == map_data['nodes'] and len(projected) == 3
         and map_data['source']['editor_revision'] == adoption['semantic_revision'], 'map differs from saved native adoption')
    need(original['map_sha256'] == sha(root / 'map.json'), 'map hash')
    manifest = read(root / 'source-closure.json')
    need(original['source_closure_sha256'] == map_data['source']['source_closure_sha256']
         == manifest['source_closure_sha256'], 'source closure binding')
    for relative, digest in manifest['files'].items():
        need(sha(safe(ROOT / 'studio', relative)) == digest, 'GT03 source drift: ' + relative)
    return {'run_id': original['run_id'], 'artifact_binding_verified': True,
        'map_sha256': sha(root / 'map.json'), 'actual_editor_cleanup': close,
        'adoption_path': adoptions[0].relative_to(root).as_posix(),
        'source_closure_sha256': manifest['source_closure_sha256'],
        'gaps': ['author parent exit was observed by exec session but has no retained host receipt',
                 'raw author-result cleanup is null; derived receipt reads post-close artifact']}


def verify_blender(root):
    nested = root / 'gt04'
    capture = read(nested / 'capture.json')
    manifest = read(nested / 'source-closure.json')
    snapshot = nested / 'source/studio'
    for relative, digest in manifest['files'].items():
        need(sha(safe(snapshot, relative)) == digest, 'frozen Blender source drift: ' + relative)
    # The retained native verifier rechecks actual process reports and full
    # native/client check sets; this is read-only and calls no engine.
    sys.path.insert(0, str(snapshot / 'tests/blender'))
    spec = importlib.util.spec_from_file_location('retained_writer_probe', snapshot / 'tests/blender/run_writer_client_probe.py')
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    need(probe.native_completion(nested, capture['host']), 'GT04 retained native verifier')
    need(capture['run_id'] == manifest['run_id'] and capture['source_closure_sha256'] == manifest['source_closure_sha256']
         and capture['logs_clean'] is True and capture['passed'] is True, 'GT04 capture binding')
    publication = read(nested / 'publication.json')
    receipt = publication['publication']['receipt']
    need(receipt['status'] == 'COMMITTED' and publication['publication']['operation'] == 'export.publish', 'GT04 publication')
    need('sha256:' + hashlib.sha256(canonical_bytes(receipt)).hexdigest() == publication['publication']['receipt_sha256'], 'GT04 receipt digest')
    need(clean_job(publication['export_cleanup']['job'])
         and publication['export_cleanup']['actual_process_exit']['exit_code'] == 0
         and publication['export_cleanup']['wrapper_exit_code'] == 0, 'export exit/cleanup')
    files = safe(nested, publication['roots']['files'])
    need(set(receipt['artifacts']) == {'scene.glb', 'checkpoint.blend'}, 'exact asset set')
    assets = {}
    for name, expected in receipt['artifacts'].items():
        path = safe(files, name)
        need(sha(path) == expected['sha256'] == publication['manifest']['artifacts'][name]['sha256']
             and path.stat().st_size == expected['size_bytes'], 'selected asset mismatch: ' + name)
        assets[name] = {'path': path.relative_to(root).as_posix(), **expected}
    return {'run_id': capture['run_id'], 'artifact_binding_verified': True,
        'assets': assets, 'native_host': capture['host'], 'export_cleanup': publication['export_cleanup'],
        'source_closure_sha256': capture['source_closure_sha256'],
        'gaps': ['outer collector failed after native success; outer wrapper/job result was not serialized']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path, required=True)
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'derived output must be fresh')
    result = {'schema': 1, 'authority': 0, 'engine_started': False,
        'formal_acceptance': False, 'pilot_acceptance': False,
        'godot': verify_godot(args.godot.resolve()), 'blender': verify_blender(args.blender.resolve())}
    # Compact manifest links existing bytes without copying entire projects.
    result['raw_manifest'] = {}
    for label, root in [('godot', args.godot.resolve()), ('blender', args.blender.resolve())]:
        result['raw_manifest'][label] = {p.relative_to(root).as_posix(): sha(p)
            for p in sorted(root.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and '.godot' not in p.parts}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'derived': str(args.output), 'native_artifact_bindings': True,
                      'pilot_acceptance': False, 'engine_started': False}))


if __name__ == '__main__':
    main()
