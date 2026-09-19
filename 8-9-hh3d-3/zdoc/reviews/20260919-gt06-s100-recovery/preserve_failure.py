"""Seal the terminal S100 import failure without modifying any raw artifact."""
from pathlib import Path
import hashlib
import json
import stat

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s100-campaign-01'
SUP = RAW.with_name(RAW.name + '-supervisor')
PACK = BASE / 'failure'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def regular(path):
    info = path.lstat()
    assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1
    assert not getattr(info, 'st_file_attributes', 0) & 0x400
    data = path.read_bytes()
    assert len(data) == info.st_size
    return data


def main():
    assert not PACK.exists(), 'Do not overwrite a sealed packet'
    child = RAW / 'run-00-attempt-01'
    failure = read(child / 'child-failure.json')
    imported = read(child / 'import-host/capture.json')
    parent = read(child / 'parent-failure.json')
    assert failure['phase'] == {'batch': -1, 'phase': 'import'}
    assert failure['completed_batches'] == 0
    assert imported['failure'] == 'STAGE_WALL_LIMIT'
    assert imported['limits']['effective_wall_seconds'] == 20
    assert parent['owned_tree_zero'] and parent['owner_closed']
    assert imported['job']['closed'] and imported['job']['zero_observed']
    assert not imported['job']['handle_retained']
    pins = read(RAW / 'campaign.json')
    for name, digest in pins['source_files'].items():
        assert sha(regular(ROOT / 'studio' / name)) == digest, name
    files = {}
    PACK.mkdir()
    for domain, folder in [('raw', RAW), ('supervisor', SUP)]:
        for path in sorted(folder.rglob('*')):
            if not path.is_file():
                continue
            data = regular(path)
            name = domain + '/' + path.relative_to(folder).as_posix()
            output = PACK / name
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as stream:
                stream.write(data)
            assert output.read_bytes() == data
            files[name] = {'sha256': sha(data), 'size_bytes': len(data),
                           'source': path.relative_to(ROOT).as_posix()}
    manifest = {
        'schema': 'HH-GT06-S100-IMPORT-FAILURE-1', 'authority': 0,
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'source_closure_sha256': pins['source_closure_sha256'],
        'profile_sha256': pins['profile_sha256'],
        'completed_batches': 0, 'import_failure': imported['failure'],
        'import_wall_limit_seconds': 20,
        'import_elapsed_seconds': imported['elapsed_seconds'],
        'import_natural_exit': None, 'import_helper_exit': imported['wrapper_exit_code'],
        'host_actual_exit': read(child / 'host-owner/process-exit.json'),
        'source_current_bytes_verified': True,
        'scope': 'Exact S100 failed import raw and supervisor copies, including cache; no PASS inference.',
        'files': files,
    }
    output = PACK / 'manifest.json'
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    for name, row in files.items():
        assert sha(regular(PACK / name)) == row['sha256']
    print(json.dumps({'files': len(files), 'manifest_sha256': sha(output.read_bytes()),
                      'failure': imported['failure'], 'formal_acceptance': False}))


if __name__ == '__main__':
    main()
