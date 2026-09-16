"""Trusted read-only startup observation; no submitted scripts or writes."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

binary = Path('/tool/Godot_v4.7.2-stable_linux.x86_64')
expected = '8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e'
digest = hashlib.sha256(binary.read_bytes()).hexdigest()
if digest != expected:
    raise SystemExit('PIN_DIGEST_MISMATCH')
result = subprocess.run([str(binary), '--version'], capture_output=True, timeout=10, check=False)
cgroup = {}
for name in ('memory.max', 'memory.swap.max', 'pids.max', 'cpu.max'):
    path = Path('/sys/fs/cgroup') / name
    cgroup[name] = path.read_text().strip() if path.exists() else 'UNAVAILABLE'
status = {}
for line in Path('/proc/self/status').read_text().splitlines():
    name, _, value = line.partition(':')
    if name in ('Uid', 'Gid', 'CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb', 'NoNewPrivs', 'Seccomp'):
        status[name] = value.strip()
out = {'scope': 'TRUSTED_VERSION_STARTUP_ONLY', 'binary_sha256': digest,
       'godot_exit': result.returncode, 'godot_stdout': result.stdout.decode('utf-8', errors='replace').strip(),
       'godot_stderr': result.stderr.decode('utf-8', errors='replace').strip(),
       'uid': os.getuid(), 'gid': os.getgid(), 'status': status, 'cgroup': cgroup,
       'interfaces': socket.if_nameindex(), 'mountinfo': Path('/proc/self/mountinfo').read_text().splitlines(),
       'limits': Path('/proc/self/limits').read_text().splitlines()}
print(json.dumps(out), flush=True)
raise SystemExit(0 if result.returncode == 0 and out['godot_stdout'] == '4.7.2.stable.official.ed1daf0bf' and not out['godot_stderr'] else 1)
