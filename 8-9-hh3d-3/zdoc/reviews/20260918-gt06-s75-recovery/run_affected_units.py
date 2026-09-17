"""Bounded replay benchmark regression lane, including assembly adversaries."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_benchmark_campaign as campaign

campaign.load_fixture()
source = campaign.source_files()
studio = ROOT / 'studio'
runner = studio / 'build/bootstrap/run_fixture.py'
spec = importlib.util.spec_from_file_location('owned_runner', runner)
owned = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owned)
out = ROOT / 'zdoc/reviews/20260918-gt06-s75-recovery/affected-units-01'
out.mkdir(exist_ok=False)
tests = sorted((studio / 'tests/replay').glob('test_benchmark*.py')) + [
    studio / 'tests/replay/test_native_benchmark.py',
    studio / 'tests/replay/test_campaign_task.py']
inputs = {**source, **{str(p.relative_to(studio)).replace('\\', '/'):
    hashlib.sha256(p.read_bytes()).hexdigest() for p in tests}}
for name, digest in inputs.items():
    raw = (studio / name).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    target = out / 'source/studio' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
code = """import unittest,json,sys
suite=unittest.TestSuite()
for pattern in ('test_benchmark*.py','test_native_benchmark.py','test_campaign_task.py'):
    suite.addTests(unittest.defaultTestLoader.discover('studio/tests/replay',pattern=pattern))
r=unittest.TextTestRunner(verbosity=2).run(suite)
print('S75_AFFECTED_COMPLETE '+json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True)
sys.exit(not r.wasSuccessful())
"""
campaign.write(out / 'invocation.json', {'code': code, 'source_files': inputs,
    'runtime_closure': campaign.closure(source), 'runtime_source_files': source,
    'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
    'formal_acceptance': False})
result = owned.run_process([sys.executable, '-B', '-c', code], cwd=ROOT,
    output=out, timeout=180, label='unit')
unchanged = all(hashlib.sha256((studio / name).read_bytes()).hexdigest() == digest
                for name, digest in inputs.items())
campaign.write(out / 'capture.json', {'host': result, 'source_unchanged': unchanged,
    'runtime_closure': campaign.closure(source), 'formal_acceptance': False})
print(json.dumps({'host': result, 'source_unchanged': unchanged}), flush=True)
assert unchanged
sys.exit(result['exit_code'])
