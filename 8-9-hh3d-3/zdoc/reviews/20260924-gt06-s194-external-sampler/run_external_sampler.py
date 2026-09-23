"""S194: prepare-only by default; bounded idle editor with an independent sampler process."""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, subprocess, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[2]; STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage

RUN_ID='gt06-s194-external-sampler-01'; RAW=STUDIO/'.local/reviews'/RUN_ID; PROJECT=RAW/'project'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):
    raw=(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    with p.open('xb') as f: f.write(raw); f.flush(); os.fsync(f.fileno())
    if p.read_bytes()!=raw: raise RuntimeError('S194_EVIDENCE_READBACK')
def pinned():
    paths=[HERE/'idle.gd', HERE/'external_sampler.py', Path(__file__), STUDIO/'toolchain.lock.json']
    paths += [p for p in PROJECT.rglob('*') if p.is_file() and '.godot' not in p.parts]
    return {p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(paths))}
def verify(files):
    for rel,d in files.items():
        if sha(ROOT/rel)!=d: raise RuntimeError('S194_FROZEN_SOURCE_CHANGED:'+rel)
def prepare():
    if RAW.exists(): raise RuntimeError('S194_ALREADY_PREPARED_INSPECT_EXISTING')
    factory,trusted=native.load_fixture(); PROJECT.mkdir(parents=True); files=dict(trusted)
    files['project.godot']=native.benchmark_project_config(files['project.godot']).replace(b'res://addons/hh_benchmark/plugin.cfg',b'res://addons/hh_idle/plugin.cfg')
    files['scenes/fixture.tscn']=factory.DEFAULT_SCENE; files['scripts/fixture_actor.gd']=factory.DEFAULT_SCRIPT
    files['addons/hh_idle/idle.gd']=(HERE/'idle.gd').read_bytes(); files['addons/hh_idle/plugin.cfg']=b'[plugin]\nname="S194 idle diagnostic"\ndescription="Diagnostic only"\nauthor="HH Studio"\nversion="1.0"\nscript="idle.gd"\n'
    for rel,val in files.items():
        dst=PROJECT/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(val)
    lock=json.loads((STUDIO/'toolchain.lock.json').read_bytes())['godot']; exe=STUDIO/'.local/tooling/godot-4.7.2-stable'/lock['gui_executable']
    if sha(exe)!=lock['gui_sha256']: raise RuntimeError('S194_BINARY_PIN')
    freeze={'run_id':RUN_ID,'authority':0,'formal_acceptance':False,'executable':str(exe),'binary_sha256':lock['gui_sha256'],'source_files':pinned(),'native_seconds':90,'editor_deadline_seconds':130,'external_sampler_seconds':105,'sample_interval_seconds':.25,'hypothesis':'Does an independently opened observer handle report the same idle editor counter variation as the retained ProcessProbe route?','limits':'Diagnostic only; no attribution to owner/leak/root cause, no formal gate.'}
    write(RAW/'prepare.json',freeze); print(json.dumps({'prepared':RUN_ID,'engine_started':False,'files':len(freeze['source_files'])}))
def run():
    freeze=json.loads((RAW/'prepare.json').read_bytes()); verify(freeze['source_files']); write(RAW/'run-claim.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}); exe=freeze['executable']
    for role,args in [('parse',['--headless','--path',str(PROJECT),'--check-only','--script','res://addons/hh_idle/idle.gd']),('import',['--headless','--editor','--path',str(PROJECT),'--import'])]:
        out=RAW/(role+'-host'); run_trusted_stage([exe,*args],cwd=PROJECT,output=out,source_root=ROOT,source_files=freeze['source_files'],binary_sha256=freeze['binary_sha256']); verify_captured_stage(out,sha(out/'capture.json'))
        if (out/'stderr.txt').read_bytes().strip(): raise RuntimeError('S194_PREFLIGHT_STDERR:'+role)
    verify(freeze['source_files']); runtime=pinned(); write(RAW/'runtime-freeze.json',{'files':runtime,'formal_acceptance':False})
    owner=None; sampler=None
    try:
        owner=BenchmarkProcess([exe,'--editor','--path',str(PROJECT),'res://scenes/fixture.tscn','--','--hh-s194-idle'],cwd=PROJECT,output=RAW/'editor-host',source_root=ROOT,source_files=runtime,binary_sha256=freeze['binary_sha256'])
        launched=time.monotonic()
        while not (owner.output/'process-start.json').exists():
            if owner.tick() is not None or time.monotonic()-launched>15: raise RuntimeError('S194_START_FAILED')
            time.sleep(.05)
        pid=json.loads((owner.output/'process-start.json').read_bytes())['pid']; sampler_out=RAW/'external-sampler'
        sampler=subprocess.Popen([sys.executable,'-B',str(HERE/'external_sampler.py'),'--pid',str(pid),'--expected-image',exe,'--out',str(sampler_out),'--duration',str(freeze['external_sampler_seconds'])],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        write(RAW/'sampler-dispatch.json',{'sampler_pid':sampler.pid,'target_pid':pid,'target_executable':exe,'formal_acceptance':False})
        while owner.tick() is None:
            if time.monotonic()-launched>freeze['editor_deadline_seconds']: raise RuntimeError('S194_EDITOR_DEADLINE')
            time.sleep(.1)
        capture=owner.finish(); sampler_code=sampler.wait(timeout=20); write(RAW/'sampler-process-exit.json',{'pid':sampler.pid,'actual_exit':sampler_code})
        output=(owner.output/'stdout.txt').read_text(encoding='utf-8'); completed=[json.loads(line.split(' ',1)[1]) for line in output.splitlines() if line.startswith('HH_S194_COMPLETE ')]
        if len(completed)!=1 or completed[0]['pid']!=pid or completed[0]['elapsed_us']<90000000: raise RuntimeError('S194_NATIVE_COMPLETION')
        if (owner.output/'stderr.txt').read_bytes().strip(): raise RuntimeError('S194_EDITOR_STDERR')
        if sampler_code!=0 or not (sampler_out/'sampler-result.json').is_file(): raise RuntimeError('S194_SAMPLER_FAILED')
        write(RAW/'result.json',{'run_id':RUN_ID,'authority':0,'formal_acceptance':False,'completed_idle_control':True,'native_completion':completed[0],'actual_target_exit':capture['actual_process_exit'],'helper_exit':capture['wrapper_exit_code'],'sampler_exit':sampler_code,'job':capture['job'],'sampler_result_sha256':sha(sampler_out/'sampler-result.json'),'samples_sha256':sha(sampler_out/'samples.jsonl')})
    finally:
        if sampler is not None and sampler.poll() is None: sampler.terminate(); sampler.wait(timeout=10)
        if owner is not None and not owner.closed: owner.close()
def supervise():
    write(RAW/'supervisor-start.json',{'pid':os.getpid(),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
    with (RAW/'driver-stdout.txt').open('xb') as out,(RAW/'driver-stderr.txt').open('xb') as err:
        child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--run'],stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW); write(RAW/'driver-start.json',{'pid':child.pid}); timed=False
        try: code=child.wait(timeout=180)
        except subprocess.TimeoutExpired: timed=True; child.terminate(); code=child.wait(timeout=30)
        write(RAW/'driver-exit.json',{'pid':child.pid,'exit_code':code,'timed_out':timed})
if __name__=='__main__':
    p=argparse.ArgumentParser(); m=p.add_mutually_exclusive_group(); m.add_argument('--run',action='store_true'); m.add_argument('--supervise',action='store_true'); a=p.parse_args()
    if a.supervise: supervise()
    elif a.run:
        try: run()
        except BaseException as e: write(RAW/'driver-failure.json',{'error_type':type(e).__name__,'message':str(e),'formal_acceptance':False}); raise
    else: prepare()
