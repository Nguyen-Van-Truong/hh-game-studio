"""Fixed owned fault/regression lane. New evidence directory; no engine runs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
OUTPUT = BASE / 'checks-01'
MODULES = ['studio.tests.replay.test_benchmark_readiness', 'studio.tests.replay.test_native_benchmark', 'studio.tests.replay.test_benchmark_assembly', 'studio.tests.replay.test_benchmark_campaign', 'studio.tests.replay.test_benchmark_campaign_stop_completion', 'studio.tests.replay.test_campaign_task', 'studio.tests.replay.test_benchmark_profile']


def main():
    if sys.argv[1:]:
        raise ValueError('fixed invocation only')
    OUTPUT.mkdir(exist_ok=False)
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--', 'studio'], cwd=ROOT).decode().split('\0')
    paths += ['studio/tests/replay/benchmark_readiness.py', 'studio/tests/replay/test_benchmark_readiness.py']
    selected = sorted({p for p in paths if p and Path(p).suffix in {'.py', '.json', '.gd', '.cfg', '.tscn', '.tres'}})
    hashes = {}
    for relative in selected:
        raw = (ROOT / relative).read_bytes()
        hashes[relative] = hashlib.sha256(raw).hexdigest()
        target = OUTPUT / 'source' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    runner = ROOT / 'studio/build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('s80_owned', runner)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    code = ('import unittest,json,sys; names=' + repr(MODULES) + '; '
            'suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names); '
            'r=unittest.TextTestRunner(verbosity=2).run(suite); '
            'print("S80_READINESS_CHECKS "+json.dumps({"run":r.testsRun,"failures":len(r.failures),'
            '"errors":len(r.errors),"skips":len(r.skipped)}),flush=True); '
            'sys.exit(not r.wasSuccessful())')
    invocation = {'code': code, 'cwd': str(ROOT), 'timeout_seconds': 120,
                  'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
                  'source_files': hashes, 'formal_acceptance': False}
    (OUTPUT / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n', encoding='utf-8')
    result = owned.run_process([sys.executable, '-B', '-c', code], cwd=ROOT,
                               output=OUTPUT, timeout=120, label='unit')
    unchanged = all(hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h for p, h in hashes.items())
    (OUTPUT / 'capture.json').write_text(json.dumps({'host': result, 'source_unchanged': unchanged}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'host': result, 'source_unchanged': unchanged, 'source_files': len(hashes)}))
    return int(not (unchanged and result.get('exit_code') == 0 and result.get('wrapper_exit_code') == 0
                   and result.get('timed_out') is False and result.get('tree_verified') is True))


if __name__ == '__main__':
    raise SystemExit(main())
