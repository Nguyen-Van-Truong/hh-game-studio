"""Run two regressions with the frozen old method, then the current method.

No source replacement: the old method is compiled from an exact Git blob in
this isolated diagnostic process only. A fresh fixture is used for every test.
"""
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT.parent
BASELINE = '9839be9a77b38199a5c03c86bab5315b9b908955'
RELATIVE = '8-9-hh3d-3/studio/host/core/transport.py'
sys.path.insert(0, str(ROOT))
from studio.host.core import transport

tests = ROOT / 'studio/tests/protocol/test_transport_recovery.py'
spec = importlib.util.spec_from_file_location('phase_regression', tests)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
names = ('test_guard_exit_failure_after_effect_never_persists_no_effect_rejection',
         'test_partial_effect_failure_preserves_unknown_and_blocks_reapply')
baseline = subprocess.check_output(['git', 'show', BASELINE + ':' + RELATIVE], cwd=REPO, timeout=15)
parsed = ast.parse(baseline)
host = next(item for item in parsed.body if isinstance(item, ast.ClassDef) and item.name == 'LoopbackFixtureHost')
method = next(item for item in host.body if isinstance(item, ast.FunctionDef) and item.name == '_execute')
namespace = dict(transport.__dict__)
exec(compile(ast.Module(body=[method], type_ignores=[]), '<frozen-method>', 'exec'), namespace)
current = transport.LoopbackFixtureHost._execute
results = []
try:
    for label, implementation in (('baseline', namespace['_execute']), ('current', current)):
        transport.LoopbackFixtureHost._execute = implementation
        suite = unittest.TestSuite(module.TransportRecoveryTests(name) for name in names)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=2).run(suite)
        results.append({'version': label, 'tests_run': result.testsRun,
                        'failure_count': len(result.failures), 'error_count': len(result.errors),
                        'skips': len(result.skipped),
                        'failures': [{'test_id': test.id(), 'assertion': text.strip().split('\n')[-1]}
                                     for test, text in result.failures]})
finally:
    transport.LoopbackFixtureHost._execute = current
if not (results[0]['failure_count'] == 4 and results[0]['error_count'] == 0
        and results[1]['failure_count'] == results[1]['error_count'] == results[1]['skips'] == 0):
    raise RuntimeError('REGRESSION_DIAGNOSTIC_UNEXPECTED')
record = {'schema': 'hh-gt02-effect-phase-regression-v1',
          'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'baseline_commit': BASELINE,
          'baseline_transport_sha256': hashlib.sha256(baseline).hexdigest(),
          'current_transport_sha256': hashlib.sha256((REPO / RELATIVE).read_bytes()).hexdigest(),
          'test_source_sha256': hashlib.sha256(tests.read_bytes()).hexdigest(),
          'results': results, 'acceptance': False}
output = Path(__file__).with_name('phase-regression.json')
if output.exists():
    raise FileExistsError('Diagnostic output already exists; preserve it')
output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print(json.dumps(record))
