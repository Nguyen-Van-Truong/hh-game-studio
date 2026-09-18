"""Read-only observations; exclusively create outputs inside this packet."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
PWSH = r'C:\Users\truon\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'


def capture(name, argv):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=45)
    base = OUT / 'observations'
    base.mkdir(exist_ok=True)
    for suffix, data in [('stdout.txt', result.stdout), ('stderr.txt', result.stderr)]:
        with (base / (name + '.' + suffix)).open('xb') as stream:
            stream.write(data)
    receipt = dict(started_utc=started,
                   finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   argv=argv, cwd=str(ROOT), returncode=result.returncode,
                   stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
                   stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),
                   scope='Read-only observation; never a native target exit receipt')
    with (base / (name + '.capture.json')).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    assert result.returncode == 0, name
    return result.stdout


scheduler = json.loads(capture('scheduler-terminal', [PWSH, '-NoProfile', '-File',
    str(ROOT / 'studio/tests/replay/campaign_task.ps1'), '-Command', 'status',
    '-CampaignId', 'gt06-s81-campaign-01', '-LaunchNumber', '1']))
capture('processes', [PWSH, '-NoProfile', '-Command',
    '$items = @(Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CreationDate); '
    'ConvertTo-Json -InputObject $items -Depth 4'])
capture('git-head', ['git', 'rev-parse', 'HEAD'])
capture('tracked-status', ['git', 'status', '--porcelain=v1', '--untracked-files=no'])
assert scheduler['state'] == 3 and scheduler['last_task_result'] == 1 and scheduler['instances'] == []
print(json.dumps({k: scheduler[k] for k in ['campaign_id', 'state', 'last_task_result', 'instances']}))
