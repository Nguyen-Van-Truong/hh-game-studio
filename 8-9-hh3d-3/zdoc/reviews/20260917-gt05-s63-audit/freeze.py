"""Freeze the S63 review inventory; never rewrites an existing manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
STUDIO = REPO / '8-9-hh3d-3/studio'
RUNS = {'units': 'gt05-units-s64-02', 'snapshot_native': 'gt05-snapshot-native-s64-02',
        'publication': 'gt05-publication-s64-02', 'visual_review': 'gt05-visual-review-s64-01',
        'snapshot_staged': 'gt05-staged-cut-s64-02', 'bone_migration': 'gt05-bone-migration-s64-02'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def checked(path, root):
    relative = path.relative_to(root)
    current = root
    for part in relative.parts:
        current /= part
        info = current.lstat()
        if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('REPARSE: ' + relative.as_posix())
    return sha(path.read_bytes())


def main():
    output = HERE / 'manifest.json'
    if output.exists():
        raise ValueError('IMMUTABLE_REVIEW_MANIFEST_ALREADY_EXISTS')
    base = STUDIO / '.local/reviews'
    frozen = json.loads((base / RUNS['units'] / 'source-closure.json').read_bytes())
    source = {'8-9-hh3d-3/studio/' + name: digest for name, digest in frozen['files'].items()}
    if any(checked(REPO / name, REPO) != digest for name, digest in source.items()):
        raise ValueError('SOURCE_DRIFT')
    proof = json.loads((base / RUNS['publication'] / 'verified-chain.json').read_bytes())
    raw = {name: digest for name, digest in proof['evidence_files'].items()
           if name.startswith('.local/reviews/')}
    for run in RUNS.values():
        for path in (base / run).rglob('*'):
            if path.is_file():
                name = path.relative_to(STUDIO).as_posix()
                digest = checked(path, STUDIO)
                if name in raw and raw[name] != digest:
                    raise ValueError('RAW_DRIFT: ' + name)
                raw[name] = digest
    for name, digest in raw.items():
        if checked(STUDIO / name, STUDIO) != digest:
            raise ValueError('RAW_DRIFT: ' + name)
    # Bind governance as exact snapshots. The coordinator may advance the live
    # progress header after review without changing what the critics inspected.
    governance = HERE / 'governance'
    governance.mkdir(exist_ok=True)
    review_paths = []
    for name, target_name in (('.gitattributes', 'gitattributes.snapshot'),
            ('AGENTS.md', 'agents.snapshot'),
            ('zdoc/8-9-godot-blender-agent-studio-plan.txt', 'tools-plan.snapshot')):
        original = REPO / '8-9-hh3d-3' / name
        snapshot = governance / target_name
        data = original.read_bytes()
        if snapshot.exists():
            if snapshot.read_bytes() != data:
                raise ValueError('GOVERNANCE_SNAPSHOT_ALREADY_FROZEN')
        else:
            with snapshot.open('xb') as stream:
                stream.write(data)
        review_paths.append(snapshot)
    review_paths += [HERE / name for name in ('README.md', 'requirements-s64.md', 'freeze.py',
                                             'verify.py', 'test_verify.py', 'run_staged_cut.py',
                                             'run_bone_migration.py')]
    review_paths += [REPO / '8-9-hh3d-3/zdoc/reviews' / name for name in (
        '20260916-gt02-s46-audit/acceptance.json',
        '20260917-gt03-s55-audit/acceptance.json',
        '20260917-gt04-s60-acceptance/acceptance.json')]
    review = {p.relative_to(REPO).as_posix(): checked(p, REPO) for p in review_paths}
    value = {'schema': 'HH-GT05-REVIEW-CLOSURE-1', 'wp': 'GT-05',
             'formal_acceptance': False, 'runs': RUNS,
             'hash_domain': 'sha256:utf8(sorted(path+NUL+sha256+LF))',
             'source_closure_sha256': closure(source), 'source_files': dict(sorted(source.items())),
             'review_closure_sha256': closure(review), 'review_files': dict(sorted(review.items())),
             'raw_closure_sha256': closure(raw), 'raw_files': dict(sorted(raw.items()))}
    if value['source_closure_sha256'] != frozen['source_closure_sha256']:
        raise ValueError('SOURCE_HASH_DOMAIN')
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'manifest_sha256': sha(output.read_bytes()),
                     **{k: value[k] for k in ('source_closure_sha256', 'review_closure_sha256', 'raw_closure_sha256')},
                     'source_files': len(source), 'review_files': len(review), 'raw_files': len(raw)}))


if __name__ == '__main__':
    main()
