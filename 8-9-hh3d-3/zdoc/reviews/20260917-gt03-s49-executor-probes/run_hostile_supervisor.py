from pathlib import Path
import json
from probe_supervisor import probe

ROOT = Path(__file__).resolve().parent
CASES = {
    'pid1-stop-ptrace': '''import os,signal,time,ctypes,json,pathlib
signal.signal(signal.SIGTERM,signal.SIG_IGN)
libc=ctypes.CDLL(None,use_errno=True)
observed={"pid":os.getpid(),"parent":os.getppid(),"yama":pathlib.Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip()}
for label,sig in [('stop',signal.SIGSTOP),('kill',signal.SIGKILL),('tstp',signal.SIGTSTP)]:
 try: os.kill(1,sig); observed[label]='sent'
 except OSError as error: observed[label]=error.errno
time.sleep(.15)
observed['pid1_state']=next(x for x in pathlib.Path('/proc/1/status').read_text().splitlines() if x.startswith('State:'))
ctypes.set_errno(0); observed['ptrace_result']=libc.ptrace(16,1,0,0); observed['ptrace_errno']=ctypes.get_errno()
try:
 fd=os.open('/proc/1/mem',os.O_RDWR); os.close(fd); observed['proc_mem']='opened'
except OSError as error: observed['proc_mem_errno']=error.errno
print(json.dumps(observed),flush=True)
while True: time.sleep(.1)
''',
    'pid1-alarm-flood': '''import os,signal,time,json
signal.signal(signal.SIGTERM,signal.SIG_IGN)
print(json.dumps({'pid':os.getpid(),'parent':os.getppid(),'action':'repeated SIGALRM after delay'}),flush=True)
time.sleep(1)
while True:
 os.kill(1,signal.SIGALRM)
 time.sleep(.01)
''',
    'pid1-chld-flood': '''import os,signal,time,json
signal.signal(signal.SIGTERM,signal.SIG_IGN)
print(json.dumps({'pid':os.getpid(),'parent':os.getppid(),'action':'SIGCHLD and SIGCONT flood'}),flush=True)
while True:
 os.kill(1,signal.SIGCHLD); os.kill(1,signal.SIGCONT)
 time.sleep(.002)
''',
}
for name, child in CASES.items():
    result=probe(ROOT / (name + '-01'), child, duration=4)
    print(json.dumps({'case':name,'state':result['state'],'elapsed_seconds':result['command_host']['elapsed_seconds'],'owned_removed':result['owned_removed']}),flush=True)
