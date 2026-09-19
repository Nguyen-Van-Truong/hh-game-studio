"""Offline, create-once S119 preservation; fail closed on missing roots or drift."""
import hashlib
import json
from pathlib import Path
import stat
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s119-lookup-boundary-01'
OUT = BASE / 's119-seal-v3'
EXCLUDED = {'.godot', '__pycache__', 'commands', 'localappdata', 'appdata'}


def need(ok, code):
    if not ok:
        raise ValueError(code)


def read(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and not info.st_file_attributes & 0x400, 'NOT_REGULAR')
    return path.read_bytes()


def h(data):
    return hashlib.sha256(data).hexdigest()


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)
    need(read(path) == data, 'COPY_MISMATCH')


def create():
    required = ('result.json', 'freeze.json', 'attempt/http-phases-final.json',
                'attempt/child-failure.json', 'attempt/child-terminal-cleanup.json',
                'timing-summary.json', 'owned/process-exit.json')
    need(RAW.is_dir() and all((RAW / p).is_file() for p in required), 'RAW_REQUIRED')
    need(not OUT.exists(), 'FRESH_PACKET_REQUIRED')
    old = json.loads(read(BASE / 's119-seal/manifest.json'))
    # V1 inventory is retained historical metadata; verify its exact recorded
    # files before copying, not its erroneous embedded self-hash field.
    for entry in list(old['files'].values()) + list(old['local_excluded'].values()):
        data = read(ROOT / entry['source'])
        need(h(data) == entry['sha256'] and len(data) == entry['bytes'], 'V1_RAW_DRIFT')
    execution = json.loads(read(RAW / 'execution-source-files.json'))
    for name, digest in execution.items():
        need(h(read(ROOT / name)) == digest, 'EXECUTION_DRIFT')
    OUT.mkdir()
    files, excluded = {}, {}
    def copy(source, key, omit=False):
        data = read(source)
        entry = {'source': source.relative_to(ROOT).as_posix(), 'sha256': h(data), 'bytes': len(data)}
        if omit:
            entry['reason'] = 'LOCAL_PRIVATE_JOURNAL_OR_GENERATED_CACHE'
            excluded[key] = entry
        else:
            put(OUT / key, data)
            files[key] = entry
    for domain, origin in (('raw', RAW), ('launcher', BASE / 'task-diagnostic'),
                           ('launcher-probe', BASE / 'task-probe')):
        need(origin.is_dir(), 'DOMAIN_REQUIRED')
        for path in sorted(origin.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(origin)
            copy(path, domain + '/' + rel.as_posix(), any(p.lower() in EXCLUDED for p in rel.parts))
    for name in execution:
        copy(ROOT / name, 'execution/' + name)
    for name in ('s119-seal/manifest.json', 'seal_s119.py', 'seal_s119_v2.py',
                 's119-seal-v2/manifest.json', 's119-seal-v2/manifest.sha256'):
        copy(BASE / name, 'historical-metadata/' + name)
    manifest = {'schema': 'S119.portable.3', 'AUTHORITY': 0, 'formal_acceptance': False,
        'eligible_for_dataset': False, 'run_id': RAW.name, 'files': files,
        'local_excluded': excluded, 'validated_v1_inventory': len(old['files']),
        'execution_files': len(execution), 'corrections': [
            'V1 was an inventory, not portable copies; embedded manifest_sha256 is not its final hash.',
            'V2 selected a wrong root, copied only 10 launcher files; invalid as complete evidence.',
            'V3 requires raw and exit artifacts before output; external hash, verified exact copies.',
            'V1 and V2 remain immutable historical metadata; neither is an acceptance seal.'],
        'gaps': ['editor target natural exit UNKNOWN', 'import wrapper native CloseHandle UNKNOWN']}
    data = (json.dumps(manifest, indent=2) + '\n').encode('utf8')
    put(OUT / 'manifest.json', data)
    put(OUT / 'manifest.sha256', (h(data) + '  manifest.json\n').encode('ascii'))
    return verify()


def verify():
    data = read(OUT / 'manifest.json')
    need(h(data) == (OUT / 'manifest.sha256').read_text('ascii').split()[0], 'SEAL_MISMATCH')
    manifest = json.loads(data)
    for key, entry in manifest['files'].items():
        copy = read(OUT / key)
        need(h(copy) == entry['sha256'] and len(copy) == entry['bytes'], 'PORTABLE_MISMATCH')
        need(read(ROOT / entry['source']) == copy, 'RAW_DRIFT')
    for entry in manifest['local_excluded'].values():
        original = read(ROOT / entry['source'])
        need(h(original) == entry['sha256'] and len(original) == entry['bytes'], 'EXCLUDED_DRIFT')
    return {'AUTHORITY': 0, 'manifest_sha256': h(data), 'copies': len(manifest['files']),
            'excluded': len(manifest['local_excluded']), 'missing': 0, 'hash_mismatch': 0,
            'formal_acceptance': False, 'eligible_for_dataset': False}


if __name__ == '__main__':
    need(sys.argv[1:] in (['create'], ['verify']), 'USE_CREATE_OR_VERIFY')
    print(json.dumps(create() if sys.argv[1] == 'create' else verify(), indent=2))
