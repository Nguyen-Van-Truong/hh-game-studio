from pathlib import Path
import importlib.util,json,os,shutil,sys,tempfile
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent
STUDIO=HERE.parents[2]/'studio'
spec=importlib.util.spec_from_file_location('service_review_helpers',STUDIO/'tests/protocol/run_gt02_candidate.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
out=HERE/'run-01';out.mkdir(exist_ok=False)
before=h.source_manifest();closure=h.RUNNER.source_closure_sha256(before)
(out/'source-closure.json').write_text(json.dumps({'source_closure_sha256':closure,'files':before},indent=2)+'\n',encoding='utf-8')
started=datetime.now(timezone.utc).isoformat()
with tempfile.TemporaryDirectory(prefix='hh-service-review-') as temp:
 snapshot=Path(temp)
 for name,digest in before.items():
  path=snapshot/'studio'/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(STUDIO/name,path);assert h.sha(path)==digest
 shutil.copyfile(HERE/'deadline_reproducer.py',snapshot/'deadline_reproducer.py')
 env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONPATH']=str(snapshot)+os.pathsep+str(snapshot/'studio/tests/protocol')
 run=h.RUNNER.run_process([sys.executable,'-B','deadline_reproducer.py'],cwd=snapshot,output=out,timeout=30,label='diagnostic',env=env)
 snapshot_unchanged=h.source_manifest(snapshot/'studio')==before
after=h.source_manifest()
redactor=h.Redactor(host_paths=[str(STUDIO.parent),str(Path.home()),tempfile.gettempdir()])
for name in (run['stdout'],run['stderr']):
 path=out/name;path.write_text('\n'.join(redactor.text(line) for line in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
record={'schema':'hh-service-design-review-diagnostic-v1','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),'source_closure_sha256':closure,'source_unchanged':before==after,'snapshot_unchanged':snapshot_unchanged,'host':run,'scope':'READ_ONLY_IMPLEMENTATION_REVIEW_NOT_ACCEPTANCE','artifacts':{p.name:h.sha(p) for p in out.iterdir() if p.is_file()}}
(out/'capture.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,sort_keys=True))
raise SystemExit(0 if run['exit_code']==0 and run['tree_verified'] and not run['timed_out'] else 1)
