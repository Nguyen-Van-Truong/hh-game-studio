"""Bounded outer owner for one serialized disposable diagnostic arm."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import sys

p=argparse.ArgumentParser();p.add_argument('--responsive',action='store_true');a=p.parse_args()
base=Path(__file__).resolve().parent;root=base.parents[2]
arm='responsive' if a.responsive else 'stock';out=base/(arm+('-owner-01' if a.responsive else '-owner-02'));out.mkdir(exist_ok=False)
files=['pss_handles.py','diagnose_handles.py','run_handle_probe.py']
before={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in files}
for name in files:(out/name).write_bytes((base/name).read_bytes())
runner=root/'studio/build/bootstrap/run_fixture.py'
spec=importlib.util.spec_from_file_location('owned_fixture',runner);owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
argv=[sys.executable,'-B',str(base/'diagnose_handles.py')]+(['--responsive'] if a.responsive else [])
(out/'invocation.json').write_text(json.dumps({'source_files':before,'argv':argv,
    'runner_sha256':hashlib.sha256(runner.read_bytes()).hexdigest(),'timeout_seconds':600,
    'formal_acceptance':False},indent=2)+'\n',encoding='utf-8')
result=owned.run_process(argv,cwd=root,output=out,timeout=600,label='probe')
after={name:hashlib.sha256((base/name).read_bytes()).hexdigest() for name in files}
(out/'capture.json').write_text(json.dumps({'host':result,'source_unchanged':before==after},indent=2)+'\n',encoding='utf-8')
print(json.dumps(result),flush=True)
assert before==after
sys.exit(result['exit_code'])
