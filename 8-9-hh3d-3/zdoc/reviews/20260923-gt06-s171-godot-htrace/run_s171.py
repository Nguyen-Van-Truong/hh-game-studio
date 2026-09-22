import json, hashlib, os, subprocess, threading, time, queue, shutil
from pathlib import Path
RUN=Path(r"8-9-hh3d-3/zdoc/reviews/20260923-gt06-s171-godot-htrace")
GODOT=Path(r"8-9-hh3d-3/studio/.local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe")
CDB=Path(subprocess.check_output(["powershell.exe","-NoProfile","-Command","(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation"],text=True).strip())/"amd64"/"cdb.exe"
run_id="gt06-s171-godot-htrace-01"; cmd_id="cmd.gt06.s171.godot-htrace.1"
out_file=RUN/"godot.stdout.txt"; err_file=RUN/"godot.stderr.txt"; cdb_out=RUN/"cdb.stdout.txt"; cdb_err=RUN/"cdb.stderr.txt"; cdb_log=RUN/"cdb.logo.txt"
for p in (out_file,err_file,cdb_out,cdb_err,cdb_log):
    try:p.unlink()
    except FileNotFoundError:pass
if not GODOT.exists() or not CDB.exists(): raise SystemExit("missing Godot/CDB")
start=time.time(); target=subprocess.Popen([str(GODOT),'--headless','--path',str(RUN),'--script','res://main.gd'],cwd=str(RUN),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
lines=[]; errs=[]
def pump(stream,arr,path):
    with path.open('w',encoding='utf-8',errors='replace') as f:
      for line in iter(stream.readline,''):
        arr.append(line.rstrip('\r\n')); f.write(line); f.flush()
t1=threading.Thread(target=pump,args=(target.stdout,lines,out_file),daemon=True); t2=threading.Thread(target=pump,args=(target.stderr,errs,err_file),daemon=True); t1.start(); t2.start()
deadline=start+90
while time.time()<deadline and not any('S171_READY' in x for x in lines): time.sleep(.05)
if not any('S171_READY' in x for x in lines):
    target.kill(); target.wait(timeout=10); raise SystemExit('target did not reach READY')
proc=subprocess.Popen([str(CDB),'-p',str(target.pid),'-pd','-nosqm','-logo',str(cdb_log),'-cf',str(RUN/'cdb-commands.txt')],cwd=str(RUN),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
dl=[]; de=[]
t3=threading.Thread(target=pump,args=(proc.stdout,dl,cdb_out),daemon=True); t4=threading.Thread(target=pump,args=(proc.stderr,de,cdb_err),daemon=True); t3.start(); t4.start()
while time.time()<deadline and proc.poll() is None and target.poll() is None:
    if any('S171_EXIT' in x for x in lines): break
    time.sleep(.1)
if target.poll() is None:
    target.wait(timeout=20) if time.time()<deadline else target.kill()
if proc.poll() is None:
    try: proc.wait(timeout=15)
    except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=10)
t1.join(2);t2.join(2);t3.join(2);t4.join(2)
ct='\n'.join(dl)+('\n'+cdb_log.read_text(errors='replace') if cdb_log.exists() else '')
markers={'cdb_attached':'CDB_ATTACHED' in ct,'htrace_enable':'Handle tracing enabled.' in ct,'create_break':'CREATE_BREAK' in ct,'close_break':'CLOSE_BREAK' in ct,'htrace_diff':'!htrace -diff' in ct,'module_offset_resolved':('kernelbase!' in ct or 'Godot_v4.7.2' in ct) and ('+' in ct),'attribution':'UNKNOWN'}
# Only mark resolved if a concrete Godot module+offset appears in htrace output; breakpoint context alone is insufficient.
import re
if re.search(r'Godot_v4\.7\.2[^\s+]*\+[0-9a-fA-F`]+',ct): markers['module_offset_resolved']=True; markers['attribution']='UNKNOWN'
rec={'schema':'gt06-s171-godot-htrace-v1','run_id':run_id,'command_id':cmd_id,'authority':0,'diagnostic_only':True,'source_closure':'fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde','profile_sha256':'0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fc'+'d6dbf4d85','godot':{'path':str(GODOT),'sha256':hashlib.sha256(GODOT.read_bytes()).hexdigest(),'pid':target.pid,'target_exit':target.returncode},'debugger':{'path':str(CDB),'version':subprocess.check_output([str(CDB),'-version'],text=True,stderr=subprocess.STDOUT,timeout=15).strip(),'sha256':hashlib.sha256(CDB.read_bytes()).hexdigest(),'pid':proc.pid,'cdb_exit':proc.returncode},'markers':markers,'target_markers':{k:any(('S171_'+k.upper()) in x for x in lines) for k in ['ready','open','close','exit']},'forced_cleanup':{'target':target.returncode is None,'debugger':proc.returncode is None},'status':'DIAGNOSTIC_RETAINED_AUTHORITY_0','exclusions':['F13','F14','GT06_DATASET','LEAK_PROOF','ROOT_CAUSE','REPAIR_AUTHORIZATION','GT06_ACCEPTANCE'],'stderr':{'debugger':'\n'.join(de),'target':'\n'.join(errs)}}
(RUN/'s171-attribution-result.json').write_text(json.dumps(rec,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rec,indent=2))
