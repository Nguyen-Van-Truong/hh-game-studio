"""Read-only terminal observation; all outputs are new files beside this script."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
PWSH = r'C:\Users\truon\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def write(name, raw):
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream:
        stream.write(raw)

def capture(name, args):
    started = utc()
    result = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    write(name + '.stdout.txt', result.stdout)
    write(name + '.stderr.txt', result.stderr)
    value = {'started_utc': started, 'finished_utc': utc(), 'argv': args, 'cwd': str(ROOT),
             'returncode': result.returncode,
             'stdout_sha256': hashlib.sha256(result.stdout).hexdigest(),
             'stderr_sha256': hashlib.sha256(result.stderr).hexdigest(),
             'scope': 'Read-only observation; not a native target exit receipt'}
    write(name + '.capture.json', (json.dumps(value, indent=2) + '\n').encode())
    if result.returncode:
        raise RuntimeError(name)
    return result.stdout

scheduler = json.loads(capture('observations/scheduler-terminal', [PWSH, '-NoProfile', '-ExecutionPolicy',
    'Bypass', '-File', str(ROOT / 'studio/tests/replay/campaign_task.ps1'), '-Command', 'status',
    '-CampaignId', 'gt06-s80-campaign-01', '-LaunchNumber', '1']))
capture('observations/processes', [PWSH, '-NoProfile', '-Command',
    '$items = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CreationDate); '
    'ConvertTo-Json -InputObject $items -Depth 4'])
capture('observations/git-head', ['git', 'rev-parse', 'HEAD'])
capture('observations/tracked-status', ['git', 'status', '--porcelain=v1', '--untracked-files=no'])
assert scheduler['state'] == 3 and scheduler['last_task_result'] == 1 and scheduler['instances'] == []
print(json.dumps(scheduler))
