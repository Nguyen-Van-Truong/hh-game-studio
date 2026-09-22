"""One bounded S170 htrace detail run; raw output is retained even on failure."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path

RUN_DIR=Path(__file__).resolve().parent; TEMP=Path(tempfile.gettempdir()); STAMP=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%d-%H%M%S')
EXE=TEMP/f'hh3d-s170-{STAMP}.exe'; CSC=Path(os.environ['WINDIR'])/'Microsoft.NET'/'Framework64'/'v4.0.30319'/'csc.exe'
PKG=Path(subprocess.check_output(['powershell.exe','-NoProfile','-Command','(Get-AppxPackage -Name Microsoft.WinDbg).InstallLocation'],text=True).strip()); CDB=PKG/'amd64'/'cdb.exe'
SOURCE=RUN_DIR/'native_fixture_s170.cs'; COMMANDS=RUN_DIR/'cdb-commands.txt'; RECEIPT=RUN_DIR/'s170-attribution-result.json'
TARGET_OUT=RUN_DIR/'target.stdout.jsonl'; TARGET_ERR=RUN_DIR/'target.stderr.txt'; CDB_OUT=RUN_DIR/'cdb.stdout.txt'; CDB_ERR=RUN_DIR/'cdb.stderr.txt'; CDB_LOG=RUN_DIR/'cdb.logo.txt'
def pump(stream,q):
    for line in iter(stream.readline,''): q.put(line.rstrip('\r\n'))
    stream.close()
def start(argv):
    p=subprocess.Popen(argv,cwd=RUN_DIR,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1); oq=queue.Queue(); eq=queue.Queue(); threading.Thread(target=pump,args=(p.stdout,oq),daemon=True).start(); threading.Thread(target=pump,args=(p.stderr,eq),daemon=True).start(); return p,oq,eq
def wait(q,lines,marker,seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        try: x=q.get(timeout=.1)
        except queue.Empty: continue
        lines.append(x)
        if marker in x:return True
    return False
def drain(q,lines):
    while True:
        try:lines.append(q.get_nowait())
        except queue.Empty:return
def main():
    cp=subprocess.run([str(CSC),'/nologo','/target:exe',f'/out:{EXE}',str(SOURCE)],cwd=RUN_DIR,capture_output=True,text=True,timeout=30); (RUN_DIR/'compile.stdout.txt').write_text(cp.stdout); (RUN_DIR/'compile.stderr.txt').write_text(cp.stderr)
    if cp.returncode: raise RuntimeError(f'compile exit {cp.returncode}')
    target,tq,teq=start([str(EXE)]); tl=[]; tel=[]; dbg=None; dq=deq=None; dl=[]; del_=[]; forced_t=False; forced_d=False; attached=False
    try:
        if not wait(tq,tl,'"kind":"ready"',10): raise RuntimeError('target no ready')
        dbg,dq,deq=start([str(CDB),'-p',str(target.pid),'-pd','-nosqm','-logo',str(CDB_LOG),'-cf',str(COMMANDS)]); attached=wait(dq,dl,'CDB_ATTACHED',20)
        if not attached: raise RuntimeError('cdb no attached marker')
        target.stdin.write('break_ready\nopen\n'); target.stdin.flush(); end=time.monotonic()+60
        while dbg.poll() is None and time.monotonic()<end:time.sleep(.1)
        if dbg.poll() is None:forced_d=True;dbg.kill()
        end=time.monotonic()+15
        while target.poll() is None and time.monotonic()<end:time.sleep(.1)
        if target.poll() is None:forced_t=True;target.kill()
    finally:
        if dbg is not None and dbg.poll() is None:forced_d=True;dbg.kill()
        if target.poll() is None:forced_t=True;target.kill()
        if dbg is not None:dbg.wait(timeout=5)
        target.wait(timeout=5); drain(tq,tl);drain(teq,tel)
        if dq is not None:drain(dq,dl)
        if deq is not None:drain(deq,del_)
    ctext='\n'.join(dl)+('\n'+CDB_LOG.read_text(errors='replace') if CDB_LOG.exists() else ''); TARGET_OUT.write_text('\n'.join(tl)+'\n'); TARGET_ERR.write_text('\n'.join(tel)+'\n'); CDB_OUT.write_text('\n'.join(dl)+'\n'); CDB_ERR.write_text('\n'.join(del_)+'\n')
    # The generic words KERNELBASE/ntdll in debugger banners are not a
    # resolved creator stack.  Record the actual discriminators separately:
    # htrace supplied the target PID/TID and OPEN/CLOSE history, while the
    # per-handle !handle query failed because the handles were already gone
    # by the time that command ran.  No module/offset for CreateEventW or
    # CreateIoCompletionPort was resolved, so attribution remains UNKNOWN.
    rec={'schema':'gt06-s170-windbg-htrace-detail-v1','run_id':'gt06-s170-windbg-htrace-detail-01','command_id':'cmd.gt06.s170.windbg-htrace-detail.1','authority':0,'diagnostic_only':True,'source_closure':'fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde','profile_sha256':'0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fc'+'d6dbf4d85','debugger':{'path':str(CDB),'version':subprocess.check_output([str(CDB),'-version'],text=True).strip(),'sha256':hashlib.sha256(CDB.read_bytes()).hexdigest(),'attached_marker':attached,'cdb_exit':dbg.returncode if dbg else None},'target':{'pid':target.pid,'target_exit':target.returncode,'executable':str(EXE)},'markers':{'htrace_enable':'Handle tracing enabled.' in ctext,'open_break':'OPEN_BREAK' in ctext,'close_break':'CLOSE_BREAK' in ctext,'target_pid_tid_observed':('Thread ID =' in ctext and 'Process ID =' in ctext),'open_close_history_observed':('Outstanding handles opened' in ctext and 'No outstanding handles opened' in ctext),'caller_module_offset_resolved':False,'per_handle_query_resolved':False,'attribution':'UNKNOWN'},'target_markers':{'start':any('"kind":"start"' in x for x in tl),'ready':any('"kind":"ready"' in x for x in tl),'open':any('"kind":"open"' in x for x in tl),'close':any('"kind":"close"' in x for x in tl),'exit':any('"kind":"exit"' in x for x in tl)},'forced_cleanup':{'debugger':forced_d,'target':forced_t},'status':'DIAGNOSTIC_RETAINED_AUTHORITY_0','exclusions':['F13','F14','GT06_DATASET','LEAK_PROOF','ROOT_CAUSE','REPAIR_AUTHORIZATION','GT06_ACCEPTANCE'],'stderr':{'debugger':'\n'.join(del_),'target':'\n'.join(tel)}}
    RECEIPT.write_text(json.dumps(rec,indent=2)+'\n'); print(json.dumps({'receipt':str(RECEIPT),'target_exit':target.returncode,'cdb_exit':dbg.returncode if dbg else None,'forced_cleanup':rec['forced_cleanup']}))
if __name__=='__main__':
    try:main()
    except Exception as e: print(f'S170_RUNNER_ERROR: {type(e).__name__}: {e}',flush=True); raise
