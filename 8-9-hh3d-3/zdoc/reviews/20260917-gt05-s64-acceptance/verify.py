"""Verify the accepted GT05 checkpoint without relabeling later working source.

Local raw verification is explicit: Git contains inventories, not generated
native assets. This checks bindings; it does not create a critic verdict.
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


def need(value, code):
    if not value:
        raise ValueError(code)


def closure(files):
    return sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())


def regular(root, name):
    need(type(name) is str and not Path(name).is_absolute() and '\\' not in name
         and all(part not in ('', '.', '..') for part in name.split('/')), 'PATH')
    path = root
    for part in name.split('/'):
        path /= part
        info = path.lstat()
        need(not path.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE')
    return path.read_bytes()


def verify(local_raw=False):
    record = json.loads((HERE / 'acceptance.json').read_bytes())
    ref = record['source_checkpoint']
    need(re.fullmatch('[0-9a-f]{40}', ref), 'COMMIT')
    need(record['gate'] == 'GT-05' and record['status'] == 'ACCEPTED', 'STATUS')
    manifest_path = '8-9-hh3d-3/' + record['review_package'] + '/manifest.json'
    raw = subprocess.check_output(['git', '-c', 'core.longpaths=true', 'show', ref + ':' + manifest_path],
                                  cwd=REPO, timeout=30)
    need(sha(raw) == record['manifest_sha256'], 'MANIFEST_HASH')
    manifest = json.loads(raw)
    inventory = {manifest_path: sha(raw)}
    for domain in ('source', 'review', 'raw'):
        files = manifest[domain + '_files']
        need(closure(files) == manifest[domain + '_closure_sha256'] == record[domain + '_closure_sha256'],
             'CLOSURE_' + domain)
        need(len(files) == record[domain + '_files'], 'COUNT_' + domain)
        if domain != 'raw':
            need(not (inventory.keys() & files.keys()), 'OVERLAPPING_INVENTORY')
            inventory.update(files)
    need(all(name.startswith('8-9-hh3d-3/') and '\n' not in name and '\r' not in name for name in inventory), 'GIT_PATH')
    result = subprocess.run(['git', '-c', 'core.longpaths=true', 'cat-file', '--batch'], cwd=REPO,
        input=''.join(ref + ':' + name + '\n' for name in inventory).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    cursor = 0
    for name, digest in inventory.items():
        end = result.stdout.index(b'\n', cursor)
        header = result.stdout[cursor:end].split()
        need(len(header) == 3 and header[1] == b'blob', 'MISSING_GIT_BLOB:' + name)
        size = int(header[2])
        cursor = end + 1
        need(sha(result.stdout[cursor:cursor + size]) == digest, 'GIT_BYTES:' + name)
        cursor += size
        need(result.stdout[cursor:cursor + 1] == b'\n', 'GIT_DELIMITER')
        cursor += 1
    need(cursor == len(result.stdout), 'GIT_TRAILING')
    critics = record['critics']
    need(len(critics) == 2 and len({item['reviewer'] for item in critics}) == 2
         and len({item['report'] for item in critics}) == 2, 'DISTINCT_REVIEWERS')
    for item in critics:
        data = regular(ROOT, item['report'])
        need(sha(data) == item['sha256'], 'REPORT_BYTES')
        text = data.decode('utf-8')
        need(item['verdict'] == 'PASS' and item['tick'] == 'yes'
             and re.search(r'^VERDICT=PASS\s*$', text, re.MULTILINE)
             and re.search(r'^TICK=yes\s*$', text, re.MULTILINE), 'REPORT_VERDICT')
        need(all(record[key] in text for key in ('manifest_sha256', 'source_closure_sha256',
             'review_closure_sha256', 'raw_closure_sha256', 'source_checkpoint')), 'REPORT_BINDING')
    if local_raw:
        for name, digest in manifest['raw_files'].items():
            need(name.startswith('.local/reviews/'), 'RAW_DOMAIN')
            need(sha(regular(ROOT / 'studio', name)) == digest, 'RAW_BYTES:' + name)
    return {'verified': True, 'gate': 'GT-05', 'source_checkpoint': ref,
            'manifest_sha256': record['manifest_sha256'], 'git_blobs': len(inventory),
            'independent_reports_bound': 2, 'local_raw_verified': local_raw,
            'raw_files': len(manifest['raw_files']) if local_raw else 0,
            'native_engines_launched': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-raw', action='store_true')
    print(json.dumps(verify(parser.parse_args().local_raw)))
