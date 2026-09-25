"""Read-only verification of the interrupted S239 packet, never acceptance."""
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    packet = json.loads((HERE / 'manifest.json').read_bytes())
    check(packet['authority'] == 0 and packet['formal_acceptance'] is False, 'scope')
    check({r['path'] for r in packet['files']} ==
          {p.name for p in HERE.iterdir() if p.is_file() and p.name != 'manifest.json'},
          'packet members')
    for row in packet['files']:
        data = (HERE / row['path']).read_bytes()
        check(len(data) == row['bytes'] and digest(data) == row['sha256'], row['path'])
    integrity = json.loads((HERE / 'integrity.json').read_bytes())
    manifest = (HERE / 'raw-manifest.json').read_bytes()
    check(digest(manifest) == integrity['raw_manifest_sha256'], 'manifest digest')
    archive = ROOT / integrity['archive']
    check(digest(archive.read_bytes()) == integrity['archive_sha256'], 'archive digest')
    rows = json.loads(manifest)['files']
    raw = ROOT / 'studio/.local/reviews/gt06-s239-formal-01'
    supervisor = raw.with_name(raw.name + '-supervisor')
    with zipfile.ZipFile(archive) as z:
        expected = {r['path'] for r in rows} | {'raw-manifest.json'}
        check(len(z.namelist()) == len(expected) == integrity['archive_members'], 'zip count')
        check(set(z.namelist()) == expected and z.read('raw-manifest.json') == manifest, 'zip members')
        for row in rows:
            label, relative = row['path'].split('/', 1)
            check(label in ('raw', 'supervisor') and '..' not in Path(relative).parts, 'path')
            data = z.read(row['path'])
            check(len(data) == row['bytes'] and digest(data) == row['sha256'], row['path'])
            root = raw if label == 'raw' else supervisor
            check((root / relative).read_bytes() == data, 'retained:' + row['path'])
        campaign = json.loads(z.read('raw/campaign.json'))
        sources = campaign['source_files']
        closure = digest(''.join(n + '\0' + sources[n] + '\n' for n in sorted(sources)).encode())
        check(len(sources) == 53 and closure == integrity['computed_source_closure'], 'source closure')
        for name, sha in sources.items():
            for prefix in ('raw/source/studio/', 'raw/run-00-attempt-01/source/studio/'):
                check(digest(z.read(prefix + name)) == sha, 'frozen:' + name)
        attempt = 'raw/run-00-attempt-01/'
        check(json.loads(z.read(attempt + 'import-host/process-exit.json'))['exit_code'] == 0, 'import exit')
        for missing in ('editor-host/process-exit.json', 'host-owner/process-exit.json',
                        'child-result.json', 'child-terminal-cleanup.json', 'joint-00.json'):
            check(attempt + missing not in expected, 'unexpected receipt:' + missing)
        check('supervisor/return.json' not in expected, 'unexpected supervisor return')
    deleted = json.loads((HERE / 'task-deleted.json').read_bytes())
    check(deleted['campaign_id'] == campaign['campaign_id'] and not deleted['formal_acceptance'], 'task')
    print(json.dumps({'verified': True, 'raw_files': len(rows), 'archive_members': len(expected),
                      'source_files': len(sources), 'authority': 0, 'formal_acceptance': False}))


if __name__ == '__main__':
    main()
