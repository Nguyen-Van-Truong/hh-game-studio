"""Collect existing S75 native and guard outcomes without rerunning engines."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.pipeline import native_job

BASE = Path(__file__).parent
OUT = BASE / 'native-validation'
OUT.mkdir(exist_ok=True)
assert not (OUT / 'manifest.json').exists(), 'already sealed'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def put(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    if path.exists():
        assert path.read_bytes() == raw, 'different retained partial copy: ' + str(path)
        return
    with path.open('xb') as stream:
        stream.write(raw)


inventory, copies, results = {}, {}, {}
for run_id in ('gt06-s75-native-01', 'gt06-s75-ignore-guard-01',
               'gt06-s75-native-02', 'gt06-s75-ignore-bom-01'):
    raw_root = ROOT / 'studio/.local/reviews' / run_id
    files = sorted(p for p in raw_root.rglob('*') if p.is_file())
    for path in files:
        relative = path.relative_to(raw_root)
        key = run_id + '/' + relative.as_posix()
        data = path.read_bytes()
        inventory[key] = {'sha256': sha(data), 'size_bytes': len(data)}
        # Select source and process evidence, not disposable engine/user caches.
        selected = len(relative.parts) == 1 or relative.parts[0] == 'source'
        selected |= relative.parts[0] in ('import-host', 'editor-host') and len(relative.parts) == 2
        selected |= relative.parts[:2] == ('project', 'benchmark')
        if selected:
            put(key, data)
            copies[key] = inventory[key]
    capture = load(raw_root / 'editor-host/capture.json')
    exited = load(raw_root / 'editor-host/process-exit.json')
    # Negative StageFailed captures keep real exit as a bound artifact, without
    # duplicating it in the successful-capture-only actual_process_exit field.
    assert capture['artifacts']['process-exit.json'] == sha((raw_root / 'editor-host/process-exit.json').read_bytes())
    assert load(raw_root / 'editor-host/process-start.json')['pid'] == exited['pid']
    assert capture['wrapper_exit_code'] == exited['exit_code']
    if 'actual_process_exit' in capture:
        assert capture['actual_process_exit'] == exited
    job = capture['job']
    assert job['closed'] and job['zero_observed'] and job['active_count'] == 0
    assert not job['handle_retained'] and not job['tainted']
    positive = '-native-' in run_id
    assert exited['exit_code'] == (0 if positive else 86)
    if positive:
        for lane in ('import-host', 'editor-host'):
            native_job.verify_captured_stage(raw_root / lane,
                sha((raw_root / lane / 'capture.json').read_bytes()))
        result = load(raw_root / 'capture.json')
        assert result['completed_diagnostic'] and result['source_unchanged']
        assert result['full_benchmark'] is False
    else:
        log = (raw_root / 'editor-host/stdout.txt').read_text(encoding='utf-8')
        assert '"code":"BENCHMARK_EVIDENCE_IGNORE"' in log
        assert not list((raw_root / 'project/benchmark/out').glob('batch-*.json'))
        result = {'guard_rejected': True, 'actual_exit': exited,
            'result_file_present': (raw_root / 'result.json').is_file(),
            'collector_asserted_on_expected_early_exit_scan_warning': run_id.endswith('guard-01')}
    results[run_id] = {'result': result, 'job': job,
        'stderr': (raw_root / 'editor-host/stderr.txt').read_text(encoding='utf-8')}
put('raw-inventory.json', inventory)
put('copies.json', copies)
put('verification.json', {'formal_acceptance': False, 'full_benchmark': False,
    'runs': results, 'raw_files': len(inventory), 'exact_copies': len(copies),
    'notes': ['native01/guard01 precede bytearray/assembly correction; historical only',
              'native02 and BOM guard verify final affected native path; no full campaign proof',
              'negative scan-thread warning retained; not allowed in positive runs']})
manifest = {p.relative_to(OUT).as_posix(): sha(p.read_bytes())
    for p in sorted(OUT.rglob('*')) if p.is_file()}
put('manifest.json', manifest)
print(json.dumps({'copied': len(copies), 'raw_files': len(inventory),
    'manifest_sha256': sha((OUT / 'manifest.json').read_bytes())}))
