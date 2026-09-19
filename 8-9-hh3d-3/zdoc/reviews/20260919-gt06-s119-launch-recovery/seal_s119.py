"""Seal S119 raw/portable domains without copying private caches."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / 'studio/.local/reviews/gt06-s119-lookup-boundary-01'
LAUNCH = Path(__file__).resolve().parent / 'task-diagnostic'
OUT = Path(__file__).resolve().parent / 's119-seal'


def record(path, base):
    raw = path.read_bytes()
    return {'source': path.relative_to(ROOT).as_posix(),
            'sha256': sha256(raw).hexdigest(), 'bytes': len(raw),
            'relative': path.relative_to(base).as_posix()}


def main():
    if OUT.exists():
        raise SystemExit('S119_SEAL_ALREADY_EXISTS')
    OUT.mkdir()
    files, excluded = {}, {}
    roots = [('raw', RAW), ('launcher', LAUNCH)]
    for domain, base in roots:
        for path in sorted(base.rglob('*')):
            if not path.is_file():
                continue
            rel = path.relative_to(base)
            item = record(path, base)
            key = f'{domain}/{rel.as_posix()}'
            # Exact local runtime caches/command journals are retained separately.
            if any(part.lower() in {'.godot', 'commands', 'localappdata', 'appdata', '__pycache__'}
                   for part in rel.parts):
                excluded[key] = item
            else:
                files[key] = item
    manifest = {
        'AUTHORITY': 0,
        'formal_acceptance': False,
        'eligible_for_dataset': False,
        'run_id': 'gt06-s119-lookup-boundary-01',
        'disposition': 'ORIGINAL_FAILURE_ADMISSION_UNKNOWN_BATCH8',
        'source_closure': '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467',
        'profile_sha256': '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85',
        'native_sha256': '13e65360cd0bc0033d0ad414fb3238e216b0d6dcc08e57dc7026ec4fc9eb8b95',
        'completed_batches': 8,
        'gates_passed': 8,
        'failure': {'code': 'ADMISSION_UNKNOWN', 'lookup_timeout_ms': 2006.271,
                    'max_status_gap_ms': 5208.0547,
                    'first_failure_route': 'lookup', 'command_route_failure': 'commands'},
        'cleanup': {'source_unchanged': True, 'execution_unchanged': True,
                    'job_zero_closed': True, 'handles_retained': False,
                    'editor_target_exit': 'UNKNOWN', 'import_exit': 0,
                    'supervisor_exit': 1},
        'correlation': {'status': 'OBSERVED_OVERLAP',
                        'lookup_headers_ms': 2003.5173,
                        'spans': ['coupled.reload', 'coupled.snapshot_true',
                                  'coupled.append', 'coupled.sqlite_commit'],
                        'claim_limit': 'Correlation only; no system cause, no leak, no repair.'},
        'files': files, 'local_excluded': excluded,
        'gaps': ['editor target natural exit receipt missing',
                 'supervisor scheduler task is separate from child target exit']
    }
    target = OUT / 'manifest.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    manifest['manifest_sha256'] = sha256(target.read_bytes()).hexdigest()
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'file_count': len(files), 'excluded_count': len(excluded),
                      'manifest_sha256': sha256(target.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
