"""Two bounded owned Python diagnostics from immutable baseline/repaired inputs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    baseline = json.loads((BASE / 'baseline-freeze.json').read_bytes())['files']
    repaired = BASE / 'repaired-source'
    repaired.mkdir(exist_ok=False)
    current = {}
    for name in baseline:
        data = (ROOT / name).read_bytes()
        target = repaired / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        current[name] = hashlib.sha256(data).hexdigest()
    write(BASE / 'repaired-freeze.json', {'files': current, 'formal_acceptance': False})
    spec = importlib.util.spec_from_file_location('owned', BASE / 'owned-runner.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    for arm in ('baseline', 'repaired'):
        out = BASE / ('result-' + arm)
        out.mkdir(exist_ok=False)
        argv = [sys.executable, '-B', str(BASE / 'probe.py'), arm]
        write(out / 'invocation.json', {'argv': argv, 'timeout_seconds': 120,
            'driver_sha256': sha(BASE / 'probe.py'), 'owner_sha256': sha(Path(__file__)),
            'runner_sha256': sha(BASE / 'owned-runner.py'), 'python_sha256': sha(Path(sys.executable)),
            'source_manifest_sha256': sha(BASE / (arm + '-freeze.json')), 'formal_acceptance': False})
        result = runner.run_process(argv, cwd=BASE / (arm + '-source'), output=out, timeout=120, label='startup')
        result['formal_acceptance'] = False
        result['engine_runs'] = 0
        result['evidence_hashes'] = {p.relative_to(out).as_posix(): sha(p) for p in out.rglob('*') if p.is_file()}
        write(out / 'capture.json', result)
        print(json.dumps({'arm': arm, **{k:result.get(k) for k in ('exit_code','wrapper_exit_code','tree_verified','timed_out')}}), flush=True)
        if result['exit_code'] != 0 or result['wrapper_exit_code'] != 0 or not result['tree_verified'] or result['timed_out']:
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
