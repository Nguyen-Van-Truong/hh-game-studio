import json,hashlib,subprocess,threading,time,re
from pathlib import Path
RUN=Path(__file__).parent.resolve(); GODOT=Path(r"8-9-hh3d-3/studio/.local/tooling/godot-4.7.2-stable/Godot_v4.7.2-stable_win64_console.exe").resolve(); CDB=Path(subprocess.check_output(["powershell.exe","-NoProfile","-Command","(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation"],text=True).strip())/"amd64"/"cdb.exe"
run_id='gt06-s171-godot-htrace-03'; cmd_id='cmd.gt06.s171.godot-htrace.3'; start=time.time(); deadline=start+60
paths={k:RUN/f for k,f in {'go':'godot.stdout.txt','ge':'godot.stderr.txt','co':'cdb.stdout.txt','ce':'cdb.stderr.txt','cl':'cdb.logo.txt'}.items()}
for p in paths.values():
 try:p.unlink()
 except:pass
gl=[]; ge=[]; cl=[]; ce=[]
def pump(stream,arr,p):
 with p.open('w',encoding='utf-8',errors='replace') as f:
  for line in iter(stream.readline,''):
   arr.append(line.rstrip('\r\n')); f.write(line); f.flush()
t=subprocess.Popen([str(GODOT),'--headless','--path',str(RUN),'--script','res://main.gd'],cwd=str(RUN),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
a=threading.Thread(target=pump,args=(t.stdout,gl,paths['go']),daemon=True); b=threading.Thread(target=pump,args=(t.stderr,ge,paths['ge']),daemon=True); a.start();b.start()
while time.time()<deadline and t.poll() is None and not any('S171_READY' in x for x in gl):time.sleep(.05)
if not any('S171_READY' in x for x in gl):
 if t.poll() is None:t.kill();t.wait(timeout=10)
 raise SystemExit('no ready '+repr(gl))
dbg=subprocess.Popen([str(CDB),'-p',str(t.pid),'-pd','-nosqm','-logo',str(paths['cl']),'-cf',str(RUN/'cdb-commands.txt')],cwd=str(RUN),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
c=threading.Thread(target=pump,args=(dbg.stdout,cl,paths['co']),daemon=True); d=threading.Thread(target=pump,args=(dbg.stderr,ce,paths['ce']),daemon=True);c.start();d.start()
while time.time()<deadline and (t.poll() is None or dbg.poll() is None):time.sleep(.05)
if t.poll() is None:t.kill();t.wait(timeout=10)
if dbg.poll() is None:
 try:dbg.wait(timeout=10)
 except subprocess.TimeoutExpired:dbg.kill();dbg.wait(timeout=10)
a.join(2);b.join(2);c.join(2);d.join(2)
ct='\n'.join(cl)+('\n'+paths['cl'].read_text(errors='replace') if paths['cl'].exists() else '')
rec={'schema':'gt06-s171-godot-htrace-v1','run_id':run_id,'command_id':cmd_id,'authority':0,'diagnostic_only':True,'source_closure':'fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde','profile_sha256':'0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fc'+'d6dbf4d85','godot':{'path':str(GODOT),'sha256':hashlib.sha256(GODOT.read_bytes()).hexdigest(),'pid':t.pid,'target_exit':t.returncode},'debugger':{'path':str(CDB),'version':subprocess.check_output([str(CDB),'-version'],text=True,stderr=subprocess.STDOUT,timeout=15).strip(),'sha256':hashlib.sha256(CDB.read_bytes()).hexdigest(),'pid':dbg.pid,'cdb_exit':dbg.returncode},'markers':{'cdb_attached':'CDB_ATTACHED' in ct,'htrace_enable':'Handle tracing enabled.' in ct,'create_break':'CREATE_BREAK' in ct,'close_break':'CLOSE_BREAK' in ct,'htrace_diff':('Outstanding handles opened' in ct or 'No outstanding handles opened' in ct),'module_offset_resolved':bool(re.search(r'Godot_v4\.7\.2[^\s+]*\+[0-9a-fA-F`]+',ct)),'attribution':'UNKNOWN'},'target_markers':{k:any(('S171_'+k.upper()) in x for x in gl) for k in ['ready','open','close','exit']},'forced_cleanup':{'target':t.returncode is None,'debugger':dbg.returncode is None},'status':'DIAGNOSTIC_RETAINED_AUTHORITY_0','exclusions':['F13','F14','GT06_DATASET','LEAK_PROOF','ROOT_CAUSE','REPAIR_AUTHORIZATION','GT06_ACCEPTANCE'],'stderr':{'debugger':'\n'.join(ce),'target':'\n'.join(ge)}}
(RUN/'s171-attribution-result.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec,indent=2))
