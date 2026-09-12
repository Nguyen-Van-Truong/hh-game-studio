"""Run the pinned real fixture after the small version-probe change."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / 'studio'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    lock = json.loads((STUDIO/'toolchain.lock.json').read_text(encoding='utf-8'))
    local = json.loads((STUDIO/'.local/toolchain.local.json').read_text(encoding='utf-8'))
    pin = lock['godot']
    run_id = 'GT01-R8-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = Path(tempfile.mkdtemp(prefix='hh3d-r8-verify-'))
    output = root/'runtime'
    command = [sys.executable, str(STUDIO/'build/bootstrap/run_fixture.py'), '--studio-root',str(STUDIO),
               '--godot-exe',local['godot_console'], '--expected-version',pin['version'],
               '--console-sha256',pin['console_sha256'], '--gui-sha256',pin['gui_sha256'],
               '--run-id',run_id, '--command-id',run_id+'-cmd', '--output',str(output), '--timeout-seconds','60']
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    with (root/'host.stdout').open('xb') as out, (root/'host.stderr').open('xb') as err:
        proc = subprocess.Popen(command, stdout=out, stderr=err, env=env)
        exit_code = proc.wait(timeout=210)
    evidence = json.loads((output/'evidence.json').read_text(encoding='utf-8')) if (output/'evidence.json').exists() else {}
    report = {'proof_class':'PARTIAL_RUNTIME_NOT_GT01_ACCEPTANCE', 'run_id':run_id, 'host_exit':exit_code,
              'observed_version':evidence.get('observed_version'), 'expected_version':pin['observed_version'],
              'checks':evidence.get('checks'), 'runs':evidence.get('runs'), 'raw_evidence_sha256':digest(output/'evidence.json') if evidence else None,
              'source': [{'path':p,'sha256':digest(STUDIO/p)} for p in ['build/bootstrap/run_fixture.py','tests/bootstrap/test_version_probe.py','toolchain.lock.json']],
              'diagnostic_logs':{p.name:digest(p) for p in root.glob('host.*')},
              'limitations':['Only current headless fixture rerun; prior window/Blender evidence belongs to older source freeze.',
                             'Bootstrap/rollback, headed+Blender remint, TQ01/TX12/TX14 and independent critics remain pending.']}
    report['pass'] = exit_code == 0 and evidence.get('observed_version') == pin['observed_version'] and evidence.get('status') == 'CANDIDATE'
    (HERE/'version-runtime.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    (HERE/'version-runtime.local.json').write_text(json.dumps({'root':str(root),'command':command,'pid':proc.pid},indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['pass'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
