"""Owned bounded native run, with read-only diagnostics of retained Job PIDs."""
import ctypes as C
from ctypes import wintypes as W
import importlib.util
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
spec = importlib.util.spec_from_file_location('owned',PRODUCT/'studio/build/bootstrap/run_fixture.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
out = BASE/sys.argv[1]; out.mkdir(exist_ok=False)
for name in ('replace_probe.py','boundary_child.c','capture_run.py'):
    (out/name).write_bytes((BASE/name).read_bytes())
original = runner._job_active_count
samples = []
class PIDLIST(C.Structure):
    _fields_ = [('assigned',W.DWORD),('count',W.DWORD),('pids',C.c_size_t*64)]
kernel = C.WinDLL('kernel32',use_last_error=True)
kernel.QueryInformationJobObject.argtypes = [W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
kernel.QueryInformationJobObject.restype = W.BOOL
kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [W.DWORD,W.BOOL,W.DWORD],W.HANDLE
kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
kernel.QueryFullProcessImageNameW.restype = W.BOOL
kernel.CloseHandle.argtypes,kernel.CloseHandle.restype = [W.HANDLE],W.BOOL
def inspect(job):
    count = original(job)
    pids = PIDLIST()
    if kernel.QueryInformationJobObject(job[1],3,C.byref(pids),C.sizeof(pids),None):
        row = {'active':count,'pids':list(pids.pids)[:pids.count],'images':[]}
        for pid in row['pids']:
            handle = kernel.OpenProcess(0x1000,False,pid)
            if handle:
                try:
                    buf,size = C.create_unicode_buffer(32768),W.DWORD(32768)
                    if kernel.QueryFullProcessImageNameW(handle,0,buf,C.byref(size)):
                        row['images'].append({'pid':pid,'image':buf.value})
                finally: kernel.CloseHandle(handle)
        if not samples or samples[-1] != row: samples.append(row)
    return count
runner._job_active_count = inspect
result = runner.run_process([sys.executable,'-B',str(BASE/'replace_probe.py'),sys.argv[2]],
    cwd=PRODUCT/'studio',output=out,timeout=90,label='native')
(out/'capture.json').write_text(json.dumps({'host':result,'job_samples':samples},indent=2)+'\n')
print(json.dumps({'host':result,'job_samples':samples}))
sys.exit(0 if result['exit_code']==0 and result['tree_verified'] and not result['timed_out'] else 1)
