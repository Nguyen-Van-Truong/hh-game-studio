"""Capture actual bounded child exit for the engine-free copied-history probe."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

root = Path(__file__).resolve().parent
script = root / 'probe.py'
start = datetime.datetime.now(datetime.timezone.utc).isoformat()
begin = time.perf_counter()
with (root / 'stdout.txt').open('wb') as out, (root / 'stderr.txt').open('wb') as err:
    child = subprocess.Popen([sys.executable, '-B', str(script)], stdout=out, stderr=err,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    timed_out = False
    try:
        code = child.wait(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True
        child.kill()  # retained child handle; this script launches no descendants
        code = child.wait(timeout=10)
result = {'started_utc': start, 'ended_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'actual_pid': child.pid, 'actual_exit': code, 'timeout_seconds': 180,
          'timed_out': timed_out, 'elapsed_seconds': time.perf_counter() - begin,
          'child_running_after_wait': child.poll() is None,
          'script_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
          'stdout_sha256': hashlib.sha256((root / 'stdout.txt').read_bytes()).hexdigest(),
          'stderr_sha256': hashlib.sha256((root / 'stderr.txt').read_bytes()).hexdigest(),
          'engine_runs': 0, 'native_acceptance': False, 'formal_acceptance': False}
(root / 'host.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))
sys.exit(code if not timed_out else 124)
