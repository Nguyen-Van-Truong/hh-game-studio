"""Preserve S181 terminal bytes locally; publish only hashes and small receipts."""
from pathlib import Path
import hashlib
import json
import stat
import zipfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUN = 'gt06-s181-formal-01'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def put(name, value):
    path = OUT / name
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    assert not (OUT / 'raw-manifest.json').exists(), 'Already sealed; do not overwrite'
    raw = ROOT / 'studio/.local/reviews' / RUN
    supervisor = raw.with_name(RUN + '-supervisor')
    attempt = raw / 'run-00-attempt-01'
    failure = json.loads((attempt / 'child-failure.json').read_bytes())
    assert failure['code'] == 'TERMINAL_TIMEOUT' and failure['completed_batches'] == 22
    # Captured by the owning PowerShell session: spawning Windows PowerShell
    # through Python inherits a different module path on this workstation.
    parsed = json.loads((OUT / 'scheduler-terminal.json').read_text(encoding='utf-8-sig'))
    assert parsed['state'] != 4 and not parsed['instances'], 'Scheduler still running'
    archive = ROOT / 'studio/.local/archives' / (RUN + '-s182-terminal.zip')
    archive.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as pack:
        for base in (raw, supervisor):
            for path in sorted(base.rglob('*')):
                assert not path.is_symlink() and not (getattr(path.lstat(), 'st_file_attributes', 0)
                       & stat.FILE_ATTRIBUTE_REPARSE_POINT), 'Unexpected link'
                if not path.is_file():
                    continue
                data = path.read_bytes()
                name = base.name + '/' + path.relative_to(base).as_posix()
                pack.writestr(name, data)
                rows.append({'member': name, 'size': len(data), 'sha256': sha(data)})
    with zipfile.ZipFile(archive) as pack:
        assert len(pack.namelist()) == len(rows) == len(set(pack.namelist()))
        for row in rows:
            data = pack.read(row['member'])
            assert len(data) == row['size'] and sha(data) == row['sha256']
    # Check originals again after packaging to reject a changing capture.
    bases = {base.name: base for base in (raw, supervisor)}
    for row in rows:
        base, relative = row['member'].split('/', 1)
        assert sha((bases[base] / relative).read_bytes()) == row['sha256']
    plan = ROOT / 'zdoc/8-9-godot-blender-agent-studio-plan.txt'
    before = plan.read_bytes()
    with (OUT / 'plan-before-s182.txt').open('xb') as stream:
        stream.write(before)
    selected = [
        'child-terminal-cleanup.json', 'parent-failure.json', 'benchmark-profile.json',
        'host-owner/process-exit.json', 'host-owner/cleanup-001.json',
        'editor-host/cleanup-001.json', 'import-host/process-exit.json',
    ]
    copies = []
    for name in selected:
        data = (attempt / name).read_bytes()
        target = OUT / 'receipts' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        copies.append({'file': target.relative_to(OUT).as_posix(), 'source_member': RUN + '/run-00-attempt-01/' + name,
                       'sha256': sha(data), 'size': len(data)})
    put('raw-manifest.json', {
        'authority': 0, 'formal_acceptance': False, 'accepted_full_runs': 0,
        'run_id': RUN, 'captured_utc': datetime.now(timezone.utc).isoformat(),
        'archive': archive.relative_to(ROOT).as_posix(), 'archive_sha256': sha(archive.read_bytes()),
        'archive_size': archive.stat().st_size, 'verified_members': len(rows),
        'originals_rechecked': True, 'missing_members': 0, 'hash_mismatches': 0,
        'plan_before_sha256': sha(before), 'rows': rows, 'selected_copies': copies,
        'exclusions': ['F13', 'F14', 'PASS', 'no_leak', 'root_cause', 'inferred_natural_exit'],
    })
    print(json.dumps({'archive': str(archive), 'verified_members': len(rows),
                      'manifest_sha256': sha((OUT / 'raw-manifest.json').read_bytes())}))


if __name__ == '__main__':
    main()
