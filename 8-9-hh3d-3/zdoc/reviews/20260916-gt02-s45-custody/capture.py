"""Focused custody implementation evidence, never whole-candidate acceptance."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
STUDIO = PRODUCT / 'studio'
spec = importlib.util.spec_from_file_location('owned', STUDIO / 'build/bootstrap/run_fixture.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
out = BASE / sys.argv[1]
out.mkdir(exist_ok=False)
sources = ('host/core/custody_registry.py', 'host/core/CUSTODY_REGISTRY.md', 'tests/protocol/test_custody_registry.py')
before = {p: hashlib.sha256((STUDIO / p).read_bytes()).hexdigest() for p in sources if (STUDIO / p).exists()}
code = "import json,unittest,sys; suite=unittest.defaultTestLoader.discover('tests/protocol',pattern='test_custody_registry.py'); r=unittest.TextTestRunner(verbosity=2).run(suite); print('HH_CUSTODY_TEST_RESULT '+json.dumps({'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True); sys.exit(0 if r.wasSuccessful() else 1)"
host = runner.run_process([sys.executable, '-B', '-c', code], cwd=STUDIO, output=out, timeout=120, label='custody')
after = {p: hashlib.sha256((STUDIO / p).read_bytes()).hexdigest() for p in before}
record = {'schema':'hh-custody-focused-evidence-1','timestamp':datetime.now(timezone.utc).isoformat(),
          'host':host,'source_sha256':before,'source_unchanged':before == after,
          'scope':'standalone registry custody; not whole GT02 acceptance; no AppContainer boundary claim'}
(out / 'capture.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
sys.exit(0 if host['exit_code']==0 and host['tree_verified'] and not host['timed_out'] and before==after else 1)
