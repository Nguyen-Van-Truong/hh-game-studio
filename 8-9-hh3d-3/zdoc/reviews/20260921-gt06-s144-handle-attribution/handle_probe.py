"""S144 read-only handle attribution: fresh process, stock versus candidate journal snapshot.
No Godot/native editor and no campaign acceptance. Seven one-group diagnostic batches
exercise the same journal/loopback host path while recording this Python process handle count.
"""
from __future__ import annotations
import argparse, ast, ctypes, hashlib, json, os, subprocess, sys, time
from pathlib import Path
from ctypes import wintypes as w
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
RUNS=7

def count_handles():
 k=ctypes.WinDLL('kernel32',use_last_error=True); k.GetCurrentProcess.restype=w.HANDLE
 k.GetProcessHandleCount.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)];k.GetProcessHandleCount.restype=w.BOOL
 n=w.DWORD(); ok=k.GetProcessHandleCount(k.GetCurrentProcess(),ctypes.byref(n));return int(n.value) if ok else None

def stock_method():
 src=subprocess.check_output(['git','show','ceb83e4c:8-9-hh3d-3/studio/host/replay/verified_journal.py'],cwd=ROOT,text=True)
 tree=ast.parse(src);node=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='VerifiedJournal')
 fn=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=='_snapshot')
 mod=ast.Module(body=[fn],type_ignores=[]);ast.fix_missing_locations(mod)
 ns={'hashlib':hashlib,'os':os,'stat':__import__('stat'),'JournalError':__import__('studio.host.core.journal',fromlist=['JournalError']).JournalError}
 exec(compile(mod,'<stock_snapshot>','exec'),ns);return ns['_snapshot']

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['candidate','stock'],required=True);a=ap.parse_args()
 sys.path.insert(0,str(ROOT/'8-9-hh3d-3'));from studio.host.replay import verified_journal
 if a.arm=='stock':verified_journal.VerifiedJournal._snapshot=stock_method()
 from studio.tests.replay.benchmark_commands import CommandProducer
 run_root=OUT/('run-'+a.arm+'-03');# CommandProducer creates its own root
 producer=CommandProducer(run_root,'s144-'+a.arm)
 rows=[];errors=[]
 try:
  rows.append({'phase':'start','handles':count_handles(),'rss':producer._observe()['counters']['rss_bytes']['value']})
  for i in range(RUNS):
   before=count_handles(); report=producer.run_diagnostic(i); after=count_handles()
   rows.append({'index':i,'before_handles':before,'after_handles':after,'delta':None if before is None or after is None else after-before,'rss_after':report['memory_after']['counters']['rss_bytes']['value'],'journal_bytes':report['journal_bytes'],'status':report['status']})
 finally:
  try:producer.close()
  except BaseException as e:errors.append(type(e).__name__+':'+str(e))
 rows.append({'phase':'closed','handles':count_handles()})
 (run_root/'result.json').write_text(json.dumps({'authority':0,'arm':a.arm,'rows':rows,'errors':errors,'runs':RUNS,'formal_acceptance':False,'eligible_for_dataset':False},indent=2)+'\n')
 print(json.dumps({'arm':a.arm,'rows':rows,'errors':errors}))
if __name__=='__main__':main()





