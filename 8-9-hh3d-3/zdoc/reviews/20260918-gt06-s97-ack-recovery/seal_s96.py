"""Preserve S96 terminal failure; never launches or accepts a benchmark."""
from pathlib import Path
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s96-coupled-phases-01'
HELPER = ROOT / 'zdoc/reviews/20260918-gt06-s96-coupled-phases'
OBSERVER = HELPER / 'launch-01/observer'
PACK = BASE / 'failure'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def need(value, code):
    if not value:
        raise ValueError(code)


def verify():
    manifest = read(PACK / 'manifest.json')
    for relative, row in manifest['files'].items():
        data = (PACK / relative).read_bytes()
        need(sha(data) == row['sha256'] and len(data) == row['size_bytes'], relative)
        need(data == (ROOT / row['source']).read_bytes(), 'ORIGINAL_BYTES:' + relative)
    for relative, row in manifest['declared_raw_artifacts'].items():
        data = (RAW / relative).read_bytes()
        need(sha(data) == row['sha256'] and len(data) == row['size_bytes'], relative)
    diagnostic = read(RAW / 'diagnostic.json')
    sources = diagnostic['base_source_files']
    closure = sha(''.join(k + '\0' + v + '\n' for k, v in sorted(sources.items())).encode())
    need(closure == diagnostic['base_source_closure_sha256'], 'SOURCE_CLOSURE')
    for relative, digest in sources.items():
        need(sha((RAW / 'source/studio' / relative).read_bytes()) == digest, relative)
    for relative, digest in diagnostic['helper_files'].items():
        need(sha((RAW / 'source' / relative).read_bytes()) == digest, relative)
    for relative, digest in read(OBSERVER / 'manifest.json')['artifacts'].items():
        need(sha((OBSERVER / relative).read_bytes()) == digest, relative)
    supplement = BASE / 'effective-native-supplement.json'
    if supplement.exists():
        row = read(supplement)
        data = (BASE / row['file']).read_bytes()
        need(sha((PACK / 'manifest.json').read_bytes()) == row['base_manifest_sha256'], 'SUPPLEMENT_BASE')
        need(sha(data) == row['sha256'] and len(data) == row['size_bytes'], 'EFFECTIVE_NATIVE_BYTES')
        need(data == (RAW / 'effective-benchmark-native.gd').read_bytes(), 'EFFECTIVE_NATIVE_ORIGINAL')
        need(sha(data) == read(RAW / 'native-overlay.json')['effective_sha256'], 'EFFECTIVE_NATIVE_BINDING')
    print(json.dumps({'exact_copies': len(manifest['files']),
                      'declared_raw_artifacts': len(manifest['declared_raw_artifacts']),
                      'runtime_files': len(sources), 'helpers': len(diagnostic['helper_files']),
                      'verified': True, 'formal_acceptance': False,
                      'manifest_sha256': sha((PACK / 'manifest.json').read_bytes())}))


def seal():
    need(not PACK.exists(), 'Preserve prior packet; do not overwrite')
    failure = read(RAW / 'child-failure.json')
    need(failure['code'] == 'CAMPAIGN_NATIVE_FAILURE' and failure['completed_batches'] == 17,
         'EXPECTED_FAILURE')
    terminal = read(OBSERVER / 'terminal.json')
    job = terminal['outer_job']
    need(job['zero_observed'] and job['closed'] and not job['handle_retained']
         and not terminal['errors'] and not terminal['unobserved_processes'], 'OUTER_CLEANUP')
    scheduler = read(BASE / 'scheduler-terminal.json')
    need(scheduler['scheduler']['state'] == 3 and scheduler['scheduler']['last_task_result'] == 1
         and not scheduler['scheduler']['instances'] and not scheduler['known_pids_current'], 'TASK_TERMINAL')
    diagnostic = read(RAW / 'diagnostic-manifest.json')
    need(diagnostic['outcome'] == 'DIAGNOSTIC_FAILED', 'DIAGNOSTIC_OUTCOME')
    pins = read(RAW / 'diagnostic.json')
    for relative, digest in pins['base_source_files'].items():
        need(sha((ROOT / 'studio' / relative).read_bytes()) == digest, 'CURRENT_SOURCE:' + relative)
    for relative, digest in pins['helper_files'].items():
        need(sha((ROOT / relative).read_bytes()) == digest, 'CURRENT_HELPER:' + relative)
    sources = set(RAW.glob('*.json')) | set(RAW.glob('*.txt'))
    sources = {p for p in sources if not p.name.startswith('command-') or p.name == 'command-17.json'}
    for pattern in ('*/process-*.json', '*/capture.json', '*/cleanup*.json', '*/invocation.json',
                    '*/stdout.txt', '*/stderr.txt', 'project/benchmark/out/*.json', 'project/benchmark/input/*.json'):
        sources.update(RAW.glob(pattern))
    sources.update(p for p in (RAW / 'source').rglob('*') if p.is_file())
    sources.update(p for p in OBSERVER.iterdir() if p.is_file())
    sources.update(p for p in (HELPER / 'launch-01').iterdir() if p.is_file())
    sources.add(BASE / 'scheduler-terminal.json')
    PACK.mkdir()
    files = {}
    for source in sorted(sources):
        if source.is_relative_to(RAW):
            domain, parent = 'raw', RAW
        elif source.is_relative_to(OBSERVER):
            domain, parent = 'observer', OBSERVER
        elif source.is_relative_to(HELPER):
            domain, parent = 'launch', HELPER / 'launch-01'
        else:
            domain, parent = 'scheduler', BASE
        relative = domain + '/' + source.relative_to(parent).as_posix()
        data = source.read_bytes()
        target = PACK / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files[relative] = {'source': source.relative_to(ROOT).as_posix(), 'sha256': sha(data), 'size_bytes': len(data)}
    manifest = {'authority': 0, 'run_id': failure['run_id'], 'formal_acceptance': False,
                'eligible_for_dataset': False, 'failure': failure, 'files': files,
                'declared_raw_artifacts': diagnostic['artifacts'],
                'missing_terminal_artifacts': diagnostic['missing_terminal_artifacts'],
                'source_closure_sha256': diagnostic['source_closure_sha256'],
                'profile_sha256': diagnostic['profile_sha256'],
                'scope': 'Exact failure copies; omitted command00-16 remain hashed raw. External retained-handle exits supplement missing inner editor exit without natural-exit inference. No acceptance.'}
    (PACK / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    verify()


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify']:
        verify()
    elif sys.argv[1:] == []:
        seal()
    else:
        raise SystemExit('Usage: seal_s96.py [--verify]')
