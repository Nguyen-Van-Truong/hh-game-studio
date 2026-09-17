"""Read-only verification of the accepted S60 Git revision and review binding.

The current plan may advance. Its old bytes are verified at source_checkpoint,
not relabeled as a new signed closure. Original native files are optional and
explicitly reported; portable-only checking does not verify original raw bytes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = ROOT.parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def blob(ref, name):
    return subprocess.check_output(
        ['git', '-c', 'core.longpaths=true', 'show', ref + ':' + name],
        cwd=REPO, timeout=30)


def verify(local_raw=False):
    record = json.loads((HERE / 'acceptance.json').read_bytes())
    ref = record['source_checkpoint']
    assert re.fullmatch('[0-9a-f]{40}', ref)
    base = '8-9-hh3d-3/' + record['review_package'] + '/'
    manifest = json.loads(blob(ref, base + 'review-closure.json'))
    digest = sha(json.dumps({k: manifest[k] for k in ('git_files', 'local_raw_files')},
                            sort_keys=True, separators=(',', ':')).encode())
    assert digest == manifest['review_closure_sha256'] == record['review_closure_sha256']
    assert record['source_closure_sha256'] == manifest['source_closure_sha256']
    execution = json.loads(blob(ref, base + 'execution-closure.json'))
    # The execution file map is itself bound by the reviewed Git inventory.
    assert record['execution_closure_sha256'] == execution['execution_closure_sha256']
    assert execution['source_closure_sha256'] == record['source_closure_sha256']
    assert sha(json.dumps(execution['files'], sort_keys=True,
                          separators=(',', ':')).encode()) == record['execution_closure_sha256']
    inventory = json.loads(blob(ref, base + 'files.json'))['files']
    assert len(inventory) == record['git_byte_inventory_files']
    assert all(inventory[name] == value for name, value in manifest['git_files'].items())
    assert inventory[base + 'review-closure.json'] == sha(blob(ref, base + 'review-closure.json'))
    assert all(name.startswith('8-9-hh3d-3/') and '\n' not in name for name in inventory)
    result = subprocess.run(['git', '-c', 'core.longpaths=true', 'cat-file', '--batch'],
        cwd=REPO, input=''.join(ref + ':' + n + '\n' for n in inventory).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    cursor = 0
    for name, hashed in inventory.items():
        end = result.stdout.index(b'\n', cursor)
        header = result.stdout[cursor:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2]); cursor = end + 1
        assert sha(result.stdout[cursor:cursor + size]) == hashed, name
        cursor += size
        assert result.stdout[cursor:cursor + 1] == b'\n'
        cursor += 1
    assert cursor == len(result.stdout)
    assert len(record['critics']) == 2
    assert len({critic['reviewer'] for critic in record['critics']}) == 2
    for critic in record['critics']:
        raw = (ROOT / critic['report']).read_bytes()
        assert sha(raw) == critic['sha256']
        text = raw.decode('utf-8')
        assert critic['verdict'] == 'PASS' and critic['tick'] == 'yes'
        assert 'PASS' in text and 'TICK=yes' in text
        assert all(record[key] in text for key in
                   ('review_closure_sha256', 'source_closure_sha256', 'execution_closure_sha256'))
    if local_raw:
        for name, hashed in manifest['local_raw_files'].items():
            assert sha((REPO / name).read_bytes()) == hashed, name
    return {'verified': True, 'gate': record['gate'], 'source_checkpoint': ref,
            'review_closure_sha256': digest, 'git_files': len(inventory),
            'independent_reports_bound': 2, 'local_raw_verified': local_raw,
            'local_raw_files': len(manifest['local_raw_files']) if local_raw else 0,
            'native_engines_launched': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-raw', action='store_true')
    print(json.dumps(verify(parser.parse_args().local_raw)))
