"""S198: bounded CDB handle snapshot; prepare-only unless --supervise is used."""
from __future__ import annotations
import argparse, ctypes, datetime, hashlib, json, os, subprocess, sys, threading, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; STUDIO=ROOT/'studio'; RUN_ID='gt06-s198-cdb-handle-snapshot-01'; RAW=STUDIO/'.local/reviews'/RUN_ID; PROJECT=RAW/'project'
sys.path.insert(0,str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    data=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with p.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
def cdb_path():
    store=subprocess.check_output(['powershell.exe','-NoProfile','-Command','(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation'],text=True,timeout=10).strip()
    return Path(store)/'amd64/cdb.exe'
def pinned():
    paths=[HERE/'idle.gd',HERE/'cdb-commands.txt',Path(__file__),STUDIO/'toolchain.lock.json']+[p for p in PROJECT.rglob('*') if p.is_file() and '.godot' not in p.parts]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
def verify(m):
    for rel,d in m.items():
        if sha(ROOT/rel)!=d: raise RuntimeError('S198_FROZEN_SOURCE_CHANGED:'+rel)
def prepare():
    if RAW.exists(): raise RuntimeError('S198_ALREADY_PREPARED_INSPECT_EXISTING')
    cdb=cdb_path();
    if not cdb.is_file(): raise RuntimeError('S198_CDB_MISSING')
    factory,trusted=native.load_fixture(); PROJECT.mkdir(parents=True); files=dict(trusted)
    files['project.godot']=native.benchmark_project_config(files['project.godot']).replace(b'res://addons/hh_benchmark/plugin.cfg',b'res://addons/hh_idle/plugin.cfg')
    files['scenes/fixture.tscn']=factory.DEFAULT_SCENE; files['scripts/fixture_actor.gd']=factory.DEFAULT_SCRIPT; files['addons/hh_idle/idle.gd']=(HERE/'idle.gd').read_bytes(); files['addons/hh_idle/plugin.cfg']=b'[plugin]\nname="S198 CDB diagnostic"\ndescription="Diagnostic only"\nauthor="HH Studio"\nversion="1.0"\nscript="idle.gd"\n'
    for rel,val in files.items(): dst=PROJECT/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(val)
    lock=json.loads((STUDIO/'toolchain.lock.json').read_bytes())['godot']; exe=STUDIO/'.local/tooling/godot-4.7.2-stable'/lock['gui_executable'];
    if sha(exe)!=lock['gui_sha256']: raise RuntimeError('S198_BINARY_PIN')
    write(RAW/'prepare.json',{'run_id':RUN_ID,'authority':0,'formal_acceptance':False,'executable':str(exe),'binary_sha256':lock['gui_sha256'],'cdb':str(cdb),'cdb_sha256':sha(cdb),'source_files':pinned(),'native_seconds':45,'deadline_seconds':90,'hypothesis':'Can supported CDB attach to the verified Godot target and capture a handle-table snapshot with htrace enabled?','limits':'Diagnostic only; no attribution/root-cause or formal acceptance.'})
    print(json.dumps({'prepared':RUN_ID,'engine_started':False,'cdb':str(cdb)}))
def pump(stream,path,rows):
    with path.open('w',encoding='utf-8',errors='replace') as out:
        for line in iter(stream.readline,''): rows.append(line.rstrip('\r\n')); out.write(line); out.flush()
def run():
    freeze=json.loads((RAW/'prepare.json').read_bytes()); verify(freeze['source_files']); write(RAW/'run-claim.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}); exe=freeze['executable']
    for role,args in [('parse',['--headless','--path',str(PROJECT),'--check-only','--script','res://addons/hh_idle/idle.gd']),('import',['--headless','--editor','--path',str(PROJECT),'--import'])]:
        out=RAW/(role+'-host'); run_trusted_stage([exe,*args],cwd=PROJECT,output=out,source_root=ROOT,source_files=freeze['source_files'],binary_sha256=freeze['binary_sha256']); verify_captured_stage(out,sha(out/'capture.json'))
        if (out/'stderr.txt').read_bytes().strip(): raise RuntimeError('S198_PREFLIGHT_STDERR:'+role)
    runtime=pinned(); write(RAW/'runtime-freeze.json',{'files':runtime,'formal_acceptance':False}); owner=None; cdb=None; rows=[]; errs=[]; cdb_start=time.monotonic()
    try:
        owner=BenchmarkProcess([exe,'--editor','--path',str(PROJECT),'res://scenes/fixture.tscn','--','--hh-s198-cdb-idle'],cwd=PROJECT,output=RAW/'editor-host',source_root=ROOT,source_files=runtime,binary_sha256=freeze['binary_sha256']); launched=time.monotonic()
        while not (owner.output/'process-start.json').exists():
            if owner.tick() is not None or time.monotonic()-launched>15: raise RuntimeError('S198_START_FAILED')
            time.sleep(.05)
        target=json.loads((owner.output/'process-start.json').read_bytes()); write(RAW/'target-identity.json',target); cdb_out=RAW/'cdb.stdout.txt'; cdb_err=RAW/'cdb.stderr.txt'
        cdb=subprocess.Popen([freeze['cdb'],'-p',str(target['pid']),'-pd','-nosqm','-logo',str(RAW/'cdb.logo.txt'),'-cf',str(HERE/'cdb-commands.txt')],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,creationflags=subprocess.CREATE_NO_WINDOW)
        threads=[threading.Thread(target=pump,args=(cdb.stdout,cdb_out,rows),daemon=True),threading.Thread(target=pump,args=(cdb.stderr,cdb_err,errs),daemon=True)]
        for t in threads:t.start()
        write(RAW/'cdb-dispatch.json',{'pid':cdb.pid,'target':target,'cdb':freeze['cdb'],'cdb_sha256':freeze['cdb_sha256'],'formal_acceptance':False})
        while owner.tick() is None:
            if time.monotonic()-launched>freeze['deadline_seconds']: raise RuntimeError('S198_EDITOR_DEADLINE')
            time.sleep(.1)
        capture=owner.finish();
        try: cdb_code=cdb.wait(timeout=15)
        except subprocess.TimeoutExpired: cdb.terminate(); cdb_code=cdb.wait(timeout=10)
        for t in threads:t.join(3)
        text='\n'.join(rows); completed=[json.loads(line.split(' ',1)[1]) for line in (RAW/'editor-host/stdout.txt').read_text(encoding='utf-8').splitlines() if line.startswith('HH_S198_COMPLETE ')]
        write(RAW/'result.json',{'run_id':RUN_ID,'authority':0,'formal_acceptance':False,'target':target,'target_actual_exit':capture['actual_process_exit'],'helper_exit':capture['wrapper_exit_code'],'cdb_exit':cdb_code,'cdb_markers':{'attached':'S198_CDB_ATTACHED' in text,'handle_snapshot':'S198_HANDLE_SNAPSHOT_DONE' in text,'htrace_enabled':'S198_HTRACE_ENABLED' in text,'handle_lines':sum(1 for line in rows if 'Handle ' in line or 'Type' in line)},'native_completion':completed,'job':capture['job'],'cdb_stdout_sha256':sha(cdb_out),'cdb_stderr_sha256':sha(cdb_err),'formal_gate_unchanged':True})
    finally:
        if cdb is not None and cdb.poll() is None: cdb.terminate(); cdb.wait(timeout=10)
        if owner is not None and not owner.closed: owner.close()
def supervise():
    write(RAW/'supervisor-start.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    with (RAW/'driver-stdout.txt').open('xb') as out,(RAW/'driver-stderr.txt').open('xb') as err:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--run'],stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW); write(RAW/'driver-start.json',{'pid':child.pid}); timed=False
        try: code=child.wait(timeout=150)
        except subprocess.TimeoutExpired: timed=True; child.terminate(); code=child.wait(timeout=30)
        write(RAW/'driver-exit.json',{'pid':child.pid,'exit_code':code,'timed_out':timed})
if __name__=='__main__':
    p=argparse.ArgumentParser(); m=p.add_mutually_exclusive_group(); m.add_argument('--run',action='store_true'); m.add_argument('--supervise',action='store_true'); a=p.parse_args()
    if a.supervise: supervise()
    elif a.run:
        try: run()
        except BaseException as e: write(RAW/'driver-failure.json',{'error_type':type(e).__name__,'message':str(e),'formal_acceptance':False}); raise
    else: prepare()

