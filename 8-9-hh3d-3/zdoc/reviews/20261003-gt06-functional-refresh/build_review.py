"""Seal the completed F25 evidence for owner-dispatched review; no engine runs.

The archive uses numbered members and an exact origin/hash map. Original raw
stays in place. Private repair stores and caches never enter this public set.
This tool proves byte integrity, not acceptance or independent review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[3]
REVIEWS = ROOT / 'studio/.local/reviews'
OUT = REVIEWS / 'gt06-f25-final-review-20261003-01'
HERE = Path(__file__).resolve().parent
SKIP = {'.godot', '__pycache__', 'appdata', 'localappdata', 'temp', 'tmp',
        'scratch', '.git', '.hh-owner', '.hh-private', 'godot-user', 'unit-localappdata'}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def safe(path):
    need(path.resolve().is_relative_to(ROOT.resolve()), 'OUTSIDE_ROOT')
    for parent in (path, *path.parents):
        info = parent.lstat()
        need(not parent.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'REPARSE_PATH')
        if parent == ROOT:
            break
    need(path.is_file(), 'FILE_MISSING')
    return path


def public_tree(path):
    need(path.is_dir() and not path.is_symlink(), 'MISSING_OR_LINKED_DIRECTORY:' + str(path))
    for directory, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(n for n in dirs if n.lower() not in SKIP
                         and not n.lower().startswith(('hh-private-', '.hh-index-')))
        for name in sorted(files):
            if name.lower().endswith(('.pyc', '.lock', '.sqlite', '.db')):
                continue
            yield safe(Path(directory) / name)


def source_paths():
    tracked = subprocess.check_output(['git', 'ls-files', '8-9-hh3d-3/studio'],
                                      cwd=ROOT.parent, text=True).splitlines()
    paths = [ROOT.parent / name for name in tracked if '/studio/evidence/' not in name]
    paths += list(HERE.glob('*.py')) + list(HERE.glob('*.md'))
    paths += [ROOT / 'AGENTS.md', ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt',
              ROOT / 'zdoc/reviews/20261003-gt06-formal25-critic-package.md']
    return paths


def evidence_paths():
    # Already selected by the unchanged S133 collector, including frozen source.
    for name in ('gt06-f25-functional-20261003-03', 'gt06-f25-managed-20261003-02',
                 'gt06-f25-managed-replay-02', 'gt06-s65-native-04', 'gt06-s65-native-05',
                 'sidecar-verify-20261001-01', 'gt06-f25-final-tests-20261003-01',
                 'gt06-f25-final-tests-20261003-02', 'gt06-f25-final-tests-20261003-03',
                 'gt06-o4-formal-25-critic-package'):
        path = REVIEWS / name
        need(path.is_dir(), 'MISSING_EVIDENCE_ROOT:' + name)
        yield from public_tree(path)
    repair = REVIEWS / 'gt06-f25-managed-repair-02'
    # Public capture-listed journal/events are required. Never traverse storage.
    capture = read(repair / 'capture.json')
    names = set(capture['artifacts']) | {'capture.json', 'repair-stderr.txt'}
    for name in sorted(names):
        need('/' not in name and '\\' not in name and ':' not in name, 'REPAIR_ROOT_ARTIFACT')
        yield safe(repair / name)
    yield from public_tree(repair / 'source')
    for folder in sorted((repair / 'owned/editor').iterdir()):
        need(folder.is_dir() and not folder.is_symlink(), 'EDITOR_DIRECTORY')
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in {'.json', '.txt'}:
                yield safe(path)
    yield from public_tree(repair / 'owned/validation')
    for name in ('20260917-gt05-s63-audit', '20260917-gt05-s64-acceptance'):
        yield from public_tree(ROOT / 'zdoc/reviews' / name)


def assert_completed():
    group = REVIEWS / 'gt06-f25-functional-20261003-03'
    terminal = read(group / 'terminal.json')
    need(terminal['exit_code'] == 0 and terminal['verified_lanes'] == 7
         and terminal['cleanup_verified'], 'FUNCTIONAL_NOT_COMPLETE')
    managed = REVIEWS / 'gt06-f25-managed-20261003-02'
    for lane in ('repair', 'replay'):
        value = read(managed / 'managed' / lane / 'verified.json')
        need(value['actual_target']['exit_code'] == 0 and value['helper_exit'] == 0
             and value['tree_verified'] and value['source_unchanged'], 'MANAGED_NOT_COMPLETE')
    # The parent real guard blocked campaign unit tests in group01. Retain that
    # failure; group02 isolates the child's local namespace and repeats replay,
    # then executes the previously unexecuted tail. Protocol is not repeated.
    for folder, suites in (
        ('gt06-f25-final-tests-20261003-01', ('protocol',)),
        ('gt06-f25-final-tests-20261003-02', ('replay', 'reviewer', 'executor')),
        ('gt06-f25-final-tests-20261003-03', ('adapters',))):
        for suite in suites:
            result = read(REVIEWS / folder / (suite + '-exit.json'))
            need(result['actual_exit'] == 0 and result['source_unchanged'], 'TEST_NOT_COMPLETE:' + suite)
    old = read(REVIEWS / 'gt06-o4-formal-25-critic-package/package.json')
    need(len(old['runs']) == 2 and all(r['batch_count'] == 35 and r['host_exit'] == 0
         and r['editor_exit'] == 0 and r['source_unchanged'] for r in old['runs']), 'FORMAL_NOT_COMPLETE')


def archive_description(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path),
            'size_bytes': path.stat().st_size}


def bound(base, name):
    need(isinstance(name, str) and name and '\\' not in name and ':' not in name,
         'RELATIVE_REFERENCE')
    parts = name.split('/')
    need(all(part not in ('', '.', '..') for part in parts), 'RELATIVE_REFERENCE')
    path = base.joinpath(*parts)
    need(path.resolve().is_relative_to(base.resolve()), 'REFERENCE_OUTSIDE_EVIDENCE')
    return safe(path)


def required_files():
    """Derive required members from frozen inventories, not surviving filenames."""
    result = {}
    def pin(base, name, expected):
        path = bound(base, name)
        need(sha(path) == expected, 'BOUND_ARTIFACT_CHANGED:' + name)
        key = path.relative_to(ROOT).as_posix()
        need(key not in result or result[key] == expected, 'CONFLICTING_PINS')
        result[key] = expected
    group = REVIEWS / 'gt06-f25-functional-20261003-03'
    for name, expected in read(group / 'driver-freeze.json')['source_files'].items():
        pin(group / 'driver-source', name, expected)
    for name, expected in read(group / 'lanes/freeze.json')['source_files'].items():
        pin(group / 'lanes/source', name, expected)
    for lane in read(group / 'lanes/verification.json')['lanes']:
        run_id = lane['run_id']
        need(run_id.startswith('gt06-f25-') and run_id.endswith('-03'), 'FUNCTIONAL_RUN_ID')
        label = run_id[len('gt06-f25-'):-len('-03')]
        inventory = read(bound(group / 'lanes', label + '/raw-files.json'))['files']
        for name, row in inventory.items():
            prefix = 'studio/.local/reviews/'
            need(name.startswith(prefix), 'PUBLIC_INVENTORY_ROOT')
            pin(group / 'lanes/selected', name[len(prefix):], row['sha256'])
    managed = REVIEWS / 'gt06-f25-managed-20261003-02'
    for name, expected in read(managed / 'driver-freeze.json')['source_files'].items():
        pin(managed / 'driver-source', name, expected)
    for name, expected in read(managed / 'managed/freeze.json')['source_files'].items():
        pin(managed / 'managed/source', name, expected)
    repair = REVIEWS / 'gt06-f25-managed-repair-02'
    for name, expected in read(repair / 'capture.json')['artifacts'].items():
        pin(repair, name, expected)
    for editor in read(repair / 'repair-terminal-cleanup.json')['owner_editor_receipts']:
        folder = repair / 'owned/editor' / editor['directory']
        pin(folder, 'close.json', editor['close_sha256'])
        for name in ('process-start.json', 'process-exit.json', 'stdout.txt', 'stderr.txt'):
            artifact = bound(folder, name)
            pin(folder, name, sha(artifact))
    for run in ('gt06-f25-managed-repair-02', 'gt06-f25-managed-replay-02',
                'gt06-s65-native-04', 'gt06-s65-native-05'):
        raw = REVIEWS / run
        for index, (name, expected) in enumerate(read(raw / 'source-files.json').items()):
            pin(raw / 'source', str(index) + Path(name).suffix, expected)
        if run.endswith('repair-02'):
            continue
        for name, expected in read(raw / 'runtime-snapshot.json').items():
            pin(raw / 'project', name, expected)
        capture = read(raw / 'capture.json')
        pin(raw, 'project/out/report.json', capture['report_sha256'])
        pin(raw, 'process-metrics.json', capture['process_metrics_sha256'])
        for phase in ('import', 'runtime'):
            pin(raw, phase + '-host/capture.json', capture[phase + '_capture_sha256'])
            for name, expected in read(raw / (phase + '-host/capture.json'))['artifacts'].items():
                pin(raw / (phase + '-host'), name, expected)
    return result


def build():
    assert_completed()
    origins = sorted(set(safe(p) for p in [*source_paths(), *evidence_paths()]))
    required = required_files()
    need(set(required) <= {p.relative_to(ROOT).as_posix() for p in origins}, 'MISSING_REQUIRED_ARCHIVE_MEMBER')
    OUT.mkdir(exist_ok=False)
    files = {}
    archive = OUT / 'functional-source-review.zip'
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=4) as z:
        for index, path in enumerate(origins):
            raw = path.read_bytes()
            origin = path.relative_to(ROOT).as_posix()
            member = 'e/' + str(index).zfill(6) + path.suffix
            need(len(member) <= 180, 'LONG_MEMBER')
            z.writestr(member, raw)
            files[origin] = {'member': member, 'sha256': digest(raw), 'size_bytes': len(raw)}
    manifest = {
        'schema': 'HH-GT06-F25-FINAL-REVIEW-1', 'formal_acceptance': False,
        'status': 'READY_FOR_OWNER_DISPATCHED_CRITICS', 'files': files,
        'required_artifact_pins': required,
        'payload': archive_description(archive),
        'benchmark_archives': [archive_description(REVIEWS / name) for name in (
            'gt06-o4-formal-25-f-tier.zip', 'gt06-f25-prerequisites.zip')],
        'requirements': (HERE / 'requirements.md').relative_to(ROOT).as_posix(),
        'formal_source_closure': '727f9039c1cc83239f5ef1daff13de5e92e37b5ba442e64be8341ca058800b58',
        'functional_source_closure': '9a9c9c42fa2be7dedf485b25c99245e92073f7b024909a8f72ec948f08219691',
        'critic_policy': 'Owner transfers to two independent models, same manifest hash; no acceptance signatures supplied',
        'limits': ['Three intentional Stop natural exits UNKNOWN, wrapper2, clean Jobs',
                   'Historical S65 fault/perf and GT05 authority retain original sources',
                   'Private owner storage/caches/credentials excluded; original raw retained',
                   'Archive integrity does not replace semantic verifier or critic judgment',
                   'Source review includes unexecuted areas; test scope comes from exact invocations'],
    }
    write(OUT / 'manifest.json', manifest)
    (OUT / 'manifest.sha256').write_text(sha(OUT / 'manifest.json') + '\n', encoding='ascii')
    verify()
    print(json.dumps({'sealed': True, 'files': len(files), 'manifest_sha256': sha(OUT / 'manifest.json')}))


def verify():
    manifest = read(OUT / 'manifest.json')
    need(sha(OUT / 'manifest.json') == (OUT / 'manifest.sha256').read_text().strip(), 'MANIFEST_HASH')
    need(set(manifest['required_artifact_pins']) <= set(manifest['files']), 'REQUIRED_MEMBERS')
    for origin, expected in manifest['required_artifact_pins'].items():
        need(manifest['files'][origin]['sha256'] == expected, 'REQUIRED_PIN_MISMATCH')
    for entry in [manifest['payload'], *manifest['benchmark_archives']]:
        path = safe(ROOT / entry['path'])
        need(path.stat().st_size == entry['size_bytes'] and sha(path) == entry['sha256'], 'ARCHIVE_HASH')
    with zipfile.ZipFile(ROOT / manifest['payload']['path']) as z:
        members = [row['member'] for row in manifest['files'].values()]
        need(len(members) == len(set(members)) and set(z.namelist()) == set(members), 'ARCHIVE_MEMBERS')
        for origin, row in manifest['files'].items():
            raw = z.read(row['member'])
            need(len(raw) == row['size_bytes'] and digest(raw) == row['sha256'], 'MEMBER_HASH')
            need(sha(safe(ROOT / origin)) == row['sha256'], 'ORIGINAL_CHANGED:' + origin)
    print(json.dumps({'byte_integrity_verified': True, 'files': len(manifest['files']),
                      'engines_launched': 0, 'formal_acceptance': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    options = parser.parse_args()
    verify() if options.verify else build()
