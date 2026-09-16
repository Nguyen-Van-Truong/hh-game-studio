"""Bounded owned process tree; immutable unique diagnostic output directory."""
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
for name in ('managed_probe.py','boundary_child.c','capture.py'):
    (out/name).write_bytes((BASE/name).read_bytes())
original = runner._job_active_count
samples = []
class PIDLIST(C.Structure):
    _fields_ = [('assigned',W.DWORD),('count',W.DWORD),('pids',C.c_size_t*64)]
kernel = C.WinDLL('kernel32',use_last_error=True)
kernel.QueryInformationJobObject.argtypes = [W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
kernel.QueryInformationJobObject.restype = W.BOOL
def inspect(job):
    count = original(job); pids = PIDLIST()
    if kernel.QueryInformationJobObject(job[1],3,C.byref(pids),C.sizeof(pids),None):
        row = {'active':count,'pids':list(pids.pids)[:pids.count]}
        if not samples or samples[-1] != row: samples.append(row)
    return count
runner._job_active_count = inspect
host = runner.run_process([sys.executable,'-B',str(BASE/'managed_probe.py'),*sys.argv[2:]],
    cwd=PRODUCT/'studio',output=out,timeout=100,label='managed-native')
(out/'capture.json').write_text(json.dumps({'host':host,'job_samples':samples},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'host':host,'job_samples':samples}))
sys.exit(0 if host['exit_code'] == 0 and host['tree_verified'] and not host['timed_out'] else 1)
