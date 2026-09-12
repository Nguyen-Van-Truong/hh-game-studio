"""Bounded GT01 candidate packager (status is always CANDIDATE/PARTIAL)."""
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, sys, tempfile, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]; STUDIO=ROOT/'studio'
def sha(p:Path):
 h=hashlib.sha256();
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''): h.update(b)
 return h.hexdigest()
def closure(root:Path):
 out={}
 for d,ns,fs in os.walk(root,followlinks=False):
  ns[:]=[n for n in ns if n not in {'.godot','__pycache__','evidence','.local'}]
  for n in fs:
   p=Path(d)/n
   if p.suffix!='.pyc' and p.is_file() and not p.is_symlink(): out[p.relative_to(root).as_posix()]=sha(p)
 return out
def redact(s,*roots):
 # Evidence must remain portable and must not expose source, temp, or user paths.
 for i, root in enumerate(roots):
  if root:
   token='$SNAPSHOT' if i == 0 else '$RUNTIME_OUTPUT'
   absolute=str(Path(root).resolve())
   s=s.replace(absolute, token).replace(absolute.replace('\\','\\\\'), token)
 s=s.replace(str(Path.home()),'$USER_HOME')
 s=re.sub(r'(?i)(token|secret|password)=\S+',r'\1=[REDACTED]',s)
 # Catch nested Windows/POSIX absolute paths that were emitted by child tools.
 s=re.sub(r'(?i)(?:[A-Z]:\\|/)[^\s"\\]+(?:\\[^\s"\\]+)*', '$PATH', s)
 return s
def run_process(argv,cwd,out,label,timeout=40):
 from importlib.util import spec_from_file_location,module_from_spec
 sp=spec_from_file_location('rf',STUDIO/'build/bootstrap/run_fixture.py'); m=module_from_spec(sp); sp.loader.exec_module(m)
 return m.run_process([str(x) for x in argv],cwd=cwd,output=out,timeout=timeout,label=label)
def invocation_succeeded(rows, nested_status, enabled):
 if not enabled: return True
 if not rows: return False
 row=rows[0]
 return (row.get('exit_code') == 0 and row.get('wrapper_exit_code') == 0
         and row.get('timed_out') is False and row.get('tree_verified') is True
         and nested_status == 'CANDIDATE')
def main(argv=None):
 ap=argparse.ArgumentParser(); ap.add_argument('--output',required=True); ap.add_argument('--invoke-run-fixture',action='store_true'); a=ap.parse_args(argv)
 out=Path(a.output).resolve(); out.mkdir(parents=True,exist_ok=False)
 run_id='GT01CAND-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]; snap=out/'snapshot'; shutil.copytree(STUDIO/'fixtures/sample-game',snap)
 before=closure(STUDIO); snap_manifest=closure(snap)
 rows=[]; nested_status=None; runtime_root=None
 if a.invoke_run_fixture:
  lock=json.loads((STUDIO/'toolchain.lock.json').read_text(encoding='utf-8'))['godot']
  exe=STUDIO/'.local/tooling/godot-4.7.2-stable'/lock['console_executable']
  # run_fixture deliberately rejects output below the studio source root;
  # keep its native output in a fresh external directory and copy only
  # redacted evidence into this review package below.
  fixture_parent=Path(tempfile.mkdtemp(prefix='hh3d-gt01-candidate-')); runtime_root=fixture_parent
  fixture_out=fixture_parent/'run-output'
  rows.append(run_process([sys.executable,str(STUDIO/'build/bootstrap/run_fixture.py'),
    '--studio-root',str(STUDIO),'--godot-exe',str(exe),
    '--expected-version',lock['observed_version'],
    '--console-sha256',lock['console_sha256'],'--gui-sha256',lock['gui_sha256'],
    '--run-id',run_id,'--command-id','cmd.gt01.candidate.'+uuid.uuid4().hex,
    '--output',str(fixture_out)],ROOT,out,'admission',120))
  published=out/'official-run'; published.mkdir()
  for item in fixture_out.iterdir():
   if item.is_file():
    raw=item.read_text(encoding='utf-8',errors='replace')
    item_target=published/item.name
    item_target.write_text(redact(raw,fixture_out,STUDIO),encoding='utf-8')
  # Preserve the child result while never claiming success for a failed run.
  nested_status = 'UNKNOWN'
  nested_evidence = fixture_out/'evidence.json'
  if nested_evidence.exists():
   try: nested_status = json.loads(nested_evidence.read_text(encoding='utf-8')).get('status','UNKNOWN')
   except (OSError, ValueError, TypeError): nested_status = 'INVALID'
 after=closure(STUDIO); logs={}
 for p in out.glob('*-stdout.txt'):
  raw=p.read_text(errors='replace'); raw_hash=sha(p); red=redact(raw,snap,out,runtime_root); rp=p.with_name(p.stem+'-redacted.txt'); rp.write_text(red); p.unlink(); logs[p.name]={'raw_sha256':raw_hash,'redacted_file':rp.name,'redacted_sha256':sha(rp)}
 invocation_ok = invocation_succeeded(rows, nested_status, a.invoke_run_fixture)
 status = 'CANDIDATE' if invocation_ok and before == after else 'PARTIAL'
 manifest={'schema':'gt01-candidate-v1','run_id':run_id,'status':status,'source_root':'$PRODUCT_ROOT','source_manifest_before':before,'source_manifest_after':after,'source_unchanged':before==after,'source_hash_mapping':{'before':before,'after':after},'snapshot_manifest':snap_manifest,'snapshot_portable':True,'runs':rows,'logs':logs,'invocation_ok':bool(invocation_ok),'nested_status':nested_status if a.invoke_run_fixture else None,'limits':['No real Godot/Blender execution in this bounded driver unless --invoke-run-fixture','Candidate evidence; requires official engine runs, archive verifier and independent critics.']}
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'status':manifest['status'],'run_id':run_id,'output':str(out)})); return 0 if invocation_ok else 2
if __name__=='__main__': raise SystemExit(main())
