"""Create a portable, read-only S119 evidence view with an external seal hash."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
RAW = ROOT / 'studio/.local/reviews/gt06-s119-lookup-boundary-01'
LAUNCH = BASE / 'task-diagnostic'
OUT = BASE / 's119-seal-v2'
EXCLUDED = {'.godot', '__pycache__', 'commands', 'localappdata', 'appdata'}


def digest(path):
    data = path.read_bytes()
    return sha256(data).hexdigest(), len(data)


def copy_domain(source, domain, files, excluded):
    for path in sorted(source.rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        key = f'{domain}/{relative.as_posix()}'
        target = OUT / key
        target.parent.mkdir(parents=True, exist_ok=True)
        item = {'source': path.relative_to(ROOT).as_posix(),
                'portable': target.relative_to(OUT).as_posix()}
        item['sha256'], item['bytes'] = digest(path)
        if any(part.lower() in EXCLUDED for part in relative.parts):
            excluded[key] = item
            continue
        shutil.copyfile(path, target)
        got = digest(target)
        if got != (item['sha256'], item['bytes']):
            raise RuntimeError(f'COPY_MISMATCH:{key}')
        files[key] = item


def main():
    if OUT.exists():
        raise SystemExit('S119_SEAL_V2_ALREADY_EXISTS')
    OUT.mkdir()
    files, excluded = {}, {}
    copy_domain(RAW, 'raw', files, excluded)
    copy_domain(LAUNCH, 'launcher', files, excluded)
    manifest = {
        'schema': 'hh-studio.s119-portable-seal.2', 'AUTHORITY': 0,
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'run_id': 'gt06-s119-lookup-boundary-01',
        'disposition': 'ORIGINAL_FAILURE_ADMISSION_UNKNOWN_BATCH8',
        'source_closure': '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467',
        'profile_sha256': '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85',
        'native_sha256': '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95',
        'completed_batches': 8, 'gates_passed': 8,
        'failure': {'code': 'ADMISSION_UNKNOWN', 'lookup_timeout_ms': 2006.271,
                    'max_status_gap_ms': 5208.0547,
                    'first_failure_route': 'lookup', 'command_route_failure': 'commands'},
        'cleanup': {'source_unchanged': True, 'execution_unchanged': True,
                    'job_zero_closed': True, 'handles_retained': False,
                    'editor_target_exit': 'UNKNOWN', 'import_exit': 0,
                    'supervisor_exit': 1, 'import_wrapper_close_handle': 'UNKNOWN'},
        'correlation': {'status': 'OBSERVED_BOUNDARY',
                        'reader': 'read_terminal_v2.py',
                        'claim_limit': 'Correlation and containment only; lock wait is static inference, no root cause, leak, repair or PASS.'},
        'files': files, 'local_excluded': excluded,
        'gaps': ['editor target natural exit receipt missing',
                 'import wrapper native CloseHandle is UNKNOWN'],
    }
    target = OUT / 'manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    seal, size = digest(target)
    (OUT / 'manifest.sha256').write_text(f'{seal}  manifest.json\n', encoding='ascii')
    print(json.dumps({'portable_count': len(files), 'excluded_count': len(excluded),
                      'manifest_sha256': seal, 'manifest_bytes': size}))


if __name__ == '__main__':
    main()
