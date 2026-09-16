"""Capture the independent host-death diagnostic with the final S51 closure."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
FROZEN = AUDIT.parent / '20260917-gt03-s51-editor-01' / 'source' / 'studio'
OUTPUT = AUDIT.parent / '20260917-gt03-s51-host-death-01'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    OUTPUT.mkdir(exist_ok=False)
    frozen_manifest = json.loads((FROZEN.parents[1] / 'source-closure.json').read_bytes())
    files = frozen_manifest['files']
    script = AUDIT / 'probe_host_death.py'
    runner_path = FROZEN / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('s51_host_death_owned', runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    before = {name: sha(FROZEN / name) for name in files}
    if before != files:
        raise ValueError('frozen source mismatch')
    env = dict(os.environ)
    env['HH_S51_FROZEN_STUDIO'] = str(FROZEN)
    env['HH_STUDIO_LINUX_GODOT'] = str(ROOT / 'studio/.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    save(OUTPUT / 'invocation.json', {
        'run_id': 'GT03-S51-HOST-DEATH-01',
        'source_closure_sha256': frozen_manifest['source_closure_sha256'],
        'source_files': files,
        'probe_sha256': sha(script), 'runner_sha256': sha(runner_path),
        'capture_script_sha256': sha(Path(__file__)),
    })
    host = runner.run_process([sys.executable, '-B', str(script), str(OUTPUT / 'probe')],
                              cwd=FROZEN, output=OUTPUT, timeout=120, label='host-death', env=env)
    result_path = OUTPUT / 'probe/probe-result.json'
    result = json.loads(result_path.read_bytes()) if result_path.is_file() else None
    capture = {'host': host, 'source_closure_sha256': frozen_manifest['source_closure_sha256'],
               'source_files': files, 'result': result,
               'snapshot_unchanged': files == {name: sha(FROZEN / name) for name in files},
               'source_unchanged': files == {name: sha(ROOT / 'studio' / name) for name in files},
               'public_ack': False, 'sandbox_acceptance': False}
    capture['passed'] = bool(result and result.get('observed') is True
        and host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified']
        and not host['timed_out'] and capture['snapshot_unchanged'] and capture['source_unchanged'])
    save(OUTPUT / 'capture.json', capture)
    print(json.dumps({'passed': capture['passed'], 'host': host,
                      'closure': capture['source_closure_sha256']}))
    return 0 if capture['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
