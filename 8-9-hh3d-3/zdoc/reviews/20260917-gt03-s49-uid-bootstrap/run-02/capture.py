"""Capture UID source for trusted fixed addon files through an owned import."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[2] / 'studio'
MAP = {
    'addons/hh_studio/plugin.cfg': 'godot-addon/addons/hh_studio/plugin.cfg',
    'addons/hh_studio/plugin.gd': 'godot-addon/addons/hh_studio/plugin.gd',
    'addons/hh_studio/scene_commands.gd': 'godot-addon/addons/hh_studio/scene_commands.gd',
    'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
}
PROBE = '''extends SceneTree
func _initialize() -> void:
\tvar rows: Array[Dictionary] = []
\tvar valid := true
\tfor path: String in ["res://addons/hh_studio/plugin.gd", "res://addons/hh_studio/scene_commands.gd", "res://addons/hh_studio/jcs_godot.gd", "res://scripts/fixture_actor.gd"]:
\t\tvar raw: String = FileAccess.get_file_as_string(path + ".uid")
\t\tvar expected: int = ResourceUID.text_to_id(raw.strip_edges())
\t\tvar actual: int = ResourceLoader.get_resource_uid(path)
\t\tvar ok: bool = expected != ResourceUID.INVALID_ID and actual == expected
\t\tvalid = valid and ok
\t\trows.append({"path": path, "uid": raw, "uid_sha256": raw.sha256_text(), "matches": ok})
\tprint("HH_GT03_UID_READBACK " + JSON.stringify({"ok": valid, "rows": rows}))
\tquit(0 if valid else 29)
'''
CONFIG = ('config_version=5\n[application]\nconfig/name="HH managed fixture"\n'
    'run/main_scene="res://scenes/fixture.tscn"\n[rendering]\n'
    'renderer/rendering_method="gl_compatibility"\n'
    '[threading]\nworker_pool/max_threads=4\n'
    '[editor_plugins]\nenabled=PackedStringArray("res://addons/hh_studio/plugin.cfg")\n')
SCENE = ('[gd_scene load_steps=2 format=3]\n\n'
    '[ext_resource type="Script" path="res://scripts/fixture_actor.gd" id="1_script"]\n\n'
    '[node name="Fixture" type="Node3D"]\nscript = ExtResource("1_script")\n'
    'fixture_value = 23\nmetadata/hh_studio_id = "root"\n')
SCRIPT = 'extends Node3D\n@export var fixture_value: int = 7\n'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    output = HERE / 'run-02'
    output.mkdir(exist_ok=False)
    (output / 'capture.py').write_bytes(Path(__file__).read_bytes())
    runner_path = STUDIO / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('s49_uid_owned', runner_path)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    pin = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(pin['gui_executable'])
    if sha(binary.read_bytes()) != pin['gui_sha256']:
        raise ValueError('binary pin mismatch')
    source = {name: (STUDIO / name).read_bytes() for name in
        (*MAP.values(), 'build/bootstrap/run_fixture.py', 'toolchain.lock.json')}
    for name, raw in source.items():
        copy = output / 'source' / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(raw)
    save(output / 'source-manifest.json', {name: sha(raw) for name, raw in source.items()})
    result = {'scope': 'TRUSTED_SOURCE_UID_CAPTURE_ONLY', 'public_ack': False, 'lanes': [], 'passed': False}
    with tempfile.TemporaryDirectory(prefix='hh-gt03-uid-') as temp:
        project = Path(temp) / 'project'
        project.mkdir()
        for relative, original in MAP.items():
            target = project / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source[original])
        (project / 'scripts').mkdir()
        (project / 'scenes').mkdir()
        (project / 'project.godot').write_bytes(CONFIG.encode())
        (project / 'scenes/fixture.tscn').write_bytes(SCENE.encode())
        (project / 'scripts/fixture_actor.gd').write_bytes(SCRIPT.encode())
        (project / 'uid_probe.gd').write_bytes(PROBE.encode())
        # Reuse the actual sidecars captured in run-01. Do not mint a second
        # identity merely because the GUI executable has no stdout console.
        for uid in (HERE / 'run-01/uid-source').rglob('*.uid'):
            relative = uid.relative_to(HERE / 'run-01/uid-source')
            (project / relative).write_bytes(uid.read_bytes())
        initial = {p.relative_to(project).as_posix(): sha(p.read_bytes())
            for p in project.rglob('*') if p.is_file()}
        save(output / 'input-manifest.json', initial)
        env = runner._isolated_user_env(Path(temp))
        for label, flags in (('import', ['--editor', '--import', 'res://scenes/fixture.tscn']),
                             ('readback', ['--script', 'res://uid_probe.gd'])):
            engine_log = output / (label + '-engine.log')
            host = runner.run_process([str(binary), '--headless', '--path', str(project),
                '--log-file', str(engine_log), *flags],
                cwd=project, output=output, timeout=45, label=label, env=env)
            text = '\n'.join((output / host[key]).read_text(encoding='utf-8', errors='strict')
                for key in ('stdout', 'stderr'))
            # Windows GUI builds use the explicit log file for engine output.
            text += '\n' + engine_log.read_text(encoding='utf-8', errors='strict')
            clean = re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', text) is None
            okay = (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified']
                    and not host['timed_out'] and clean)
            result['lanes'].append({'host': host, 'clean': clean, 'passed': okay})
            if label == 'readback':
                markers = [json.loads(line.removeprefix('HH_GT03_UID_READBACK '))
                    for line in text.splitlines() if line.startswith('HH_GT03_UID_READBACK ')]
                result['readback'] = markers[0] if len(markers) == 1 else None
            if not okay:
                break
        result['input_unchanged'] = all(sha((project / name).read_bytes()) == digest
            for name, digest in initial.items())
        result['source_unchanged'] = all((STUDIO / name).read_bytes() == raw for name, raw in source.items())
        result['binary_unchanged'] = sha(binary.read_bytes()) == pin['gui_sha256']
        uids = {}
        for name in ('addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd',
                     'addons/hh_studio/jcs_godot.gd', 'scripts/fixture_actor.gd'):
            uid_path = project / (name + '.uid')
            if uid_path.exists():
                raw = uid_path.read_bytes()
                target = output / 'uid-source' / (name + '.uid')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
                uids[name + '.uid'] = sha(raw)
        result['uids'] = uids
        readback = result.get('readback') or {}
        result['passed'] = (len(result['lanes']) == 2 and all(row['passed'] for row in result['lanes'])
            and result['input_unchanged'] and result['source_unchanged'] and result['binary_unchanged']
            and len(uids) == 4 and readback.get('ok') is True and len(readback.get('rows', [])) == 4
            and all(row.get('matches') is True and uids.get(row['path'].removeprefix('res://') + '.uid')
                    == row['uid_sha256'] for row in readback['rows']))
        (output / 'project.godot').write_bytes((project / 'project.godot').read_bytes())
        save(output / 'capture.json', result)
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
