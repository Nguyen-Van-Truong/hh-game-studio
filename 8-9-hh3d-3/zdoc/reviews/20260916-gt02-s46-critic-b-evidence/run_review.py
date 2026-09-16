"""Read-only source critic run with immutable snapshot and owned Job timeout."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / 'studio'
EXPECTED = 'f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf'
spec = importlib.util.spec_from_file_location('critic_runner', STUDIO/'tests/protocol/run_gt02_candidate.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
out = HERE / 'run-01'
out.mkdir(exist_ok=False)
before = h.source_manifest()
closure = h.RUNNER.source_closure_sha256(before)
assert closure == EXPECTED and len(before) == 106
(out/'source-closure.json').write_text(json.dumps({'source_closure_sha256':closure,'files':before}, indent=2)+'\n', encoding='utf-8')
started = datetime.now(timezone.utc).isoformat()
with tempfile.TemporaryDirectory(prefix='hh-critic-b-s46-') as temp:
    snapshot = Path(temp)
    for name, digest in before.items():
        target = snapshot/'studio'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO/name, target)
        assert h.sha(target) == digest
    shutil.copyfile(HERE/'recovery_probe.py', snapshot/'recovery_probe.py')
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONPATH'] = str(snapshot)+os.pathsep+str(snapshot/'studio/tests/protocol')
    host = h.RUNNER.run_process([sys.executable, '-B', 'recovery_probe.py'],
        cwd=snapshot, output=out, timeout=40, label='recovery', env=env)
    snapshot_unchanged = h.source_manifest(snapshot/'studio') == before
source_unchanged = h.source_manifest() == before
raw_host = json.loads((out/host['host']).read_text(encoding='utf-8'))
summary_rows = [line.removeprefix('HH_CRITIC_B_TEST_RESULT ') for line in
    (out/host['stdout']).read_text(encoding='utf-8').split('\n') if line.startswith('HH_CRITIC_B_TEST_RESULT ')]
assert len(summary_rows) == 1
summary = json.loads(summary_rows[0])
passed = (host['exit_code'] == host['wrapper_exit_code'] == raw_host['exit_code'] == 0
          and host['target_pid'] == raw_host['target_pid'] and host['tree_verified']
          and not host['timed_out'] and snapshot_unchanged and source_unchanged
          and summary == {'run':19,'failures':0,'errors':0,'skips':0})
record = {'schema':'hh-critic-b-focused-v1','run_id':'GT02-S46-CRITIC-B-20260916-01',
    'command_id':'cmd.gt02-s46-critic-b.recovery.1','started_utc':started,
    'completed_utc':datetime.now(timezone.utc).isoformat(),'source_closure_sha256':closure,
    'source_unchanged':source_unchanged,'snapshot_unchanged':snapshot_unchanged,
    'host':host,'summary':summary,'passed':passed,
    'harness_sha256':{p.name:h.sha(p) for p in (HERE/'run_review.py',HERE/'recovery_probe.py')},
    'artifacts':{p.name:h.sha(p) for p in out.iterdir() if p.is_file()}}
(out/'capture.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
raise SystemExit(0 if passed else 1)
