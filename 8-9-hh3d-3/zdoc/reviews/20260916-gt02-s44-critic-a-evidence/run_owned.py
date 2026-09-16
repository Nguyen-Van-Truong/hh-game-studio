"""Run critic A's diagnostic with the accepted bounded owned Job runner."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
STUDIO = PRODUCT / 'studio'
MANIFEST = json.loads((PRODUCT/'zdoc/reviews/20260916-gt02-s44-02/source-closure.json').read_text())


def manifest():
    return {name:hashlib.sha256((STUDIO/name).read_bytes()).hexdigest() for name in MANIFEST['files']}


before = manifest()
assert before==MANIFEST['files']
spec = importlib.util.spec_from_file_location('critic_a_owned_runner',STUDIO/'build/bootstrap/run_fixture.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
env = dict(os.environ)
env['PYTHONDONTWRITEBYTECODE']='1'
result = runner.run_process([sys.executable,'-B',str(HERE/'reproduce.py')],
    cwd=PRODUCT,output=HERE,timeout=30,label='readonly-admission',env=env)
result['source_unchanged']=manifest()==before
result['source_closure_sha256']=runner.source_closure_sha256(before)
result['scope']='Diagnostic completion is not a compliance PASS.'
(HERE/'capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,sort_keys=True))
assert result['exit_code']==result['wrapper_exit_code']==0
assert result['tree_verified'] and not result['timed_out'] and result['source_unchanged']
