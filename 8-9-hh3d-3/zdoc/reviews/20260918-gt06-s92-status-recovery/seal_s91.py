"""Preserve terminal S91 evidence; never launches or accepts a benchmark."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s91-sparse-attribution-01'
HELPER = ROOT / 'zdoc/reviews/20260918-gt06-s91-sparse-attribution'
OBSERVER = HELPER / 'launch-02/observer'
PACK = BASE / 'failure'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def verify():
    manifest = read(PACK / 'manifest.json')
    for relative, row in manifest['files'].items():
        data = (PACK / relative).read_bytes()
        assert sha(data) == row['sha256'] and len(data) == row['size_bytes'], relative
        assert data == (ROOT / row['source']).read_bytes(), relative
    for relative, row in manifest['declared_raw_artifacts'].items():
        data = (RAW / relative).read_bytes()
        assert sha(data) == row['sha256'] and len(data) == row['size_bytes'], relative
    for relative, digest in read(RAW / 'source-files.json').items():
        assert sha((RAW / 'source/studio' / relative).read_bytes()) == digest, relative
    for relative, digest in read(RAW / 'diagnostic.json')['helper_files'].items():
        assert sha((RAW / 'source' / relative).read_bytes()) == digest, relative
    for relative, digest in read(OBSERVER / 'manifest.json')['artifacts'].items():
        assert sha((OBSERVER / relative).read_bytes()) == digest, relative
    print(json.dumps({'exact_copies': len(manifest['files']),
                      'declared_raw_artifacts': len(manifest['declared_raw_artifacts']),
                      'runtime_files': 51, 'helpers': 6, 'verified': True,
                      'formal_acceptance': False, 'manifest_sha256': sha((PACK / 'manifest.json').read_bytes())}))


def seal():
    assert not PACK.exists(), 'Preserve prior packet; do not overwrite'
    failure = read(RAW / 'child-failure.json')
    assert failure['code'] == 'CAMPAIGN_STATUS_GAP' and failure['completed_batches'] == 17
    terminal = read(OBSERVER / 'terminal.json')
    assert terminal['outer_job']['zero_observed'] and terminal['outer_job']['closed']
    assert not terminal['errors'] and not terminal['unobserved_processes']
    task = subprocess.run(['schtasks.exe', '/Query', '/TN', r'\HHStudio.GT06.gt06-s91-sparse-attribution-01', '/XML'], capture_output=True)
    assert task.returncode == 0, 'Task must remain queryable until terminal preservation'
    PACK.mkdir()
    diagnostic = read(RAW / 'diagnostic-manifest.json')
    sources = set(RAW.glob('*.json')) | set(RAW.glob('*.txt'))
    sources = {p for p in sources if not p.name.startswith(('command-', 'sample-preview-')) or p.name in ('command-16.json', 'sample-preview-16.json')}
    for pattern in ('*/process-*.json', '*/capture.json', '*/cleanup*.json', '*/invocation.json', '*/stdout.txt', '*/stderr.txt', 'project/benchmark/out/*.json', 'project/benchmark/input/*.json'):
        sources.update(RAW.glob(pattern))
    sources.update(p for p in OBSERVER.iterdir() if p.is_file())
    sources.update(p for p in (HELPER / 'launch-02').iterdir() if p.is_file())
    files = {}
    for source in sorted(sources):
        domain = 'raw' if source.is_relative_to(RAW) else 'observer' if source.is_relative_to(OBSERVER) else 'launch'
        parent = RAW if domain == 'raw' else OBSERVER if domain == 'observer' else HELPER / 'launch-02'
        relative = domain + '/' + source.relative_to(parent).as_posix()
        data = source.read_bytes()
        target = PACK / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[relative] = {'source': source.relative_to(ROOT).as_posix(), 'sha256': sha(data), 'size_bytes': len(data)}
    write(PACK / 'manifest.json', {'authority': 0, 'run_id': failure['run_id'],
          'formal_acceptance': False, 'eligible_for_dataset': False,
          'failure': failure, 'files': files,
          'declared_raw_artifacts': diagnostic['artifacts'],
          'source_closure_sha256': diagnostic['source_closure_sha256'],
          'profile_sha256': diagnostic['profile_sha256'],
          'limits': 'Exact copies and original declared raw inventory; external observer supplements missing inner editor exit. Diagnostic only; stable counters do not prove absence of leaks.'})
    verify()


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify']:
        verify()
    elif sys.argv[1:] == []:
        seal()
    else:
        raise SystemExit('Usage: seal_s91.py [--verify]')
