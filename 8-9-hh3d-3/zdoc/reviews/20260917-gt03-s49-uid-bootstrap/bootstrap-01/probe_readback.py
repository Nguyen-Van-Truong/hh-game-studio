"""Bounded trusted-input bootstrap diagnostic; no sandbox/public ACK claim."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / 'studio'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    output = HERE / 'bootstrap-01'
    output.mkdir(exist_ok=False)
    own = importlib.util.spec_from_file_location('s49_bootstrap_owned', STUDIO / 'build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(own)
    own.loader.exec_module(runner)
    pins = json.loads((STUDIO / 'godot-addon/fixture_profile/source-pins.json').read_bytes())['files']
    inputs = {name: (STUDIO / row['source']).read_bytes() for name, row in pins.items()}
    if not all(digest(inputs[name]) == row['sha256'] for name, row in pins.items()):
        raise ValueError('release pin changed')
    inputs['scripts/fixture_actor.gd'] = (b'extends Node3D\n@export var fixture_value: int = 9\n'
        b'@export var move_speed: float = 2.25\n@export var turn_speed: float = 90.0\n'
        b'@export var enabled: bool = false\n')
    inputs['scenes/fixture.tscn'] = (b'[gd_scene load_steps=2 format=3]\n\n'
        b'[ext_resource type="Script" path="res://scripts/fixture_actor.gd" id="1_script"]\n\n'
        b'[node name="Fixture" type="Node3D"]\nscript = ExtResource("1_script")\n'
        b'fixture_value = 23\nmetadata/hh_studio_id = "root"\n')
    bootstrap = (STUDIO / 'godot-addon/validation_bootstrap.gd').read_bytes()
    (output / 'validation_bootstrap.gd').write_bytes(bootstrap)
    (output / 'probe_readback.py').write_bytes(Path(__file__).read_bytes())
    for name, raw in inputs.items():
        target = output / 'inputs' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    pin = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    binary = Path(local['godot_console']).with_name(pin['gui_executable'])
    if digest(binary.read_bytes()) != pin['gui_sha256']:
        raise ValueError('binary pin')
    result = {'scope': 'TRUSTED_LITERAL_FIXTURE_READBACK_ONLY', 'public_ack': False,
        'bootstrap_sha256': digest(bootstrap), 'input_hashes': {k: digest(v) for k,v in inputs.items()},
        'lanes': [], 'passed': False}
    with tempfile.TemporaryDirectory(prefix='hh-gt03-profile-') as temp:
        project = Path(temp) / 'project'
        for name, raw in inputs.items():
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        helper = Path(temp) / 'validation_bootstrap.gd'
        helper.write_bytes(bootstrap)
        env = runner._isolated_user_env(Path(temp))
        for mode, flags in (('import', ['--editor', '--import', 'res://scenes/fixture.tscn']),
                            ('readback', ['--script', str(helper)])):
            log = output / (mode + '-engine.log')
            host = runner.run_process([str(binary), '--headless', '--path', str(project),
                '--log-file', str(log), *flags], cwd=project, output=output, timeout=45, label=mode, env=env)
            text = '\n'.join((output / host[k]).read_text(encoding='utf-8') for k in ('stdout', 'stderr'))
            text += '\n' + log.read_text(encoding='utf-8')
            clean = re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', text) is None
            passed = host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out'] and clean
            result['lanes'].append({'mode': mode, 'host': host, 'clean': clean, 'passed': passed})
            if mode == 'readback':
                rows = [json.loads(line.removeprefix('HH_PROFILE_READBACK '))
                        for line in text.splitlines() if line.startswith('HH_PROFILE_READBACK ')]
                result['observation'] = rows[0] if len(rows) == 1 else None
            if not passed:
                break
        result['inputs_unchanged'] = all((project/name).read_bytes() == raw for name,raw in inputs.items())
        result['bootstrap_unchanged'] = helper.read_bytes() == bootstrap == (STUDIO/'godot-addon/validation_bootstrap.gd').read_bytes()
        result['binary_unchanged'] = digest(binary.read_bytes()) == pin['gui_sha256']
        result['passed'] = (len(result['lanes']) == 2 and all(row['passed'] for row in result['lanes'])
            and result['inputs_unchanged'] and result['bootstrap_unchanged'] and result['binary_unchanged']
            and (result.get('observation') or {}).get('ok') is True)
    (output/'capture.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'lanes': result['lanes'], 'observation': result.get('observation')}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
