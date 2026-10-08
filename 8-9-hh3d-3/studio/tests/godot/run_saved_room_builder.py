"""Build one private script-free room through validated candidate proposals.

The editor applies one UndoRedo transaction, serializes actual Godot objects,
and reloads their semantics. No gameplay code runs in the Windows editor.
This diagnostic does not register a profile or grant AUTH/GT09 acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline import native_job
from studio.tests.godot.saved_room_recipe import build_recipe, source_paths


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def raw_file(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        info = part.stat(follow_symlinks=False)
        need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'BUILDER_REPARSE')
    need(path.is_file() and path.stat().st_size <= 2 * 1024**2, 'BUILDER_FILE_LIMIT')
    return path.read_bytes()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)


def idle_window():
    need(os.environ.get('LOCALAPPDATA'), 'BUILDER_LOCALAPPDATA')
    need(not (Path(os.environ['LOCALAPPDATA']) / 'HHGodotAgent/measure-window.lock').exists(),
         'MEASUREMENT_WINDOW_HELD')


def expected_checks(recipe):
    names = {'editor_empty_workbench', 'recipe_scope', 'prepared_exact', 'empty_history', 'json_numeric_semantics',
             'do_exact', 'undo_transition', 'undo_exact', 'redo_transition', 'redo_exact',
             'pack_ok', 'fresh_output', 'save_ok', 'load_ok', 'reload_exact', 'history_cleared'}
    for row in recipe['expected_snapshot']['nodes']:
        names.update(('class_' + row['node_type'], 'unknown_property_rejected_' + row['node_type']))
        for prop in row['properties']:
            names.update((f"property_exists_{row['stable_id']}_{prop}", f"set_{row['stable_id']}_{prop}"))
    for kind in ('node', 'resource'):
        names.update(kind + '_operation_' + row['command_id'] for row in recipe[kind + '_commands'])
    return names


def verify_observation(observation, recipe, recipe_bytes, scene_bytes, pid):
    need(observation.get('schema') == 'hh-o2-saved-room-native-1'
         and observation.get('authority') == 0 and observation.get('runtime_authorized') is False
         and observation.get('public_ack') is False and observation.get('pid') == pid
         and observation.get('failures') == [], 'BUILDER_NATIVE_BINDING')
    checks = observation.get('checks', {})
    need(set(checks) == expected_checks(recipe) and all(value is True for value in checks.values()),
         'BUILDER_NATIVE_CHECKS')
    snapshots = observation.get('snapshots', {})
    expected = recipe['expected_snapshot']
    empty = {'asset_resources': expected.get('asset_resources', []),
             'nodes': [], 'resources': []}
    need(snapshots == {'before': empty, 'prepared': expected, 'after_do': expected,
         'after_undo': empty, 'after_redo': expected, 'after_reload': expected}, 'BUILDER_SEMANTICS')
    need(observation.get('recipe_sha256') == sha(recipe_bytes)
         and observation.get('room_sha256') == sha(scene_bytes), 'BUILDER_NATIVE_BYTES')


def _bound_file(root, name, digest):
    need(type(name) is str and not Path(name).is_absolute() and '\\' not in name
         and not any(part in ('', '.', '..') for part in name.split('/')), 'BUILDER_BINDING_PATH')
    raw = raw_file(root / name)
    need(sha(raw) == digest, 'BUILDER_BOUND_HASH')
    return raw


def verify_saved_room(root: Path, *, require_current_source: bool = True) -> bytes:
    """Re-derive frozen bytes, native semantics and real process cleanup.

    A caller's PASS boolean, generated text or result.json alone is insufficient.
    This is a local diagnostic evidence chain, not a cryptographic attestation.
    Consumers may reuse the immutable artifact from an older producer closure;
    they still check its original source, actual native receipts and recipe
    against today's semantic contract. They never execute that retained source
    or attribute the historical run to the current producer.
    """
    return _verify_saved_room(root.absolute(), json.loads(raw_file(root / 'result.json')),
                              require_current_source=require_current_source)


def verify_source_binding(root, files, *, require_current_source):
    need(type(require_current_source) is bool, 'BUILDER_SOURCE_POLICY')
    for name, digest in files.items():
        _bound_file(root / 'source', name, digest)
        if require_current_source:
            _bound_file(STUDIO, name, digest)


def _verify_saved_room(root, result, *, require_current_source=True):
    binding = json.loads(raw_file(root / 'binding.json'))
    need(binding.get('schema') == 'hh-o2-saved-room-binding-1'
         and result.get('schema') == 'hh-o2-saved-room-result-1'
         and binding.get('run_id') == result.get('run_id')
         and result.get('status') == 'DIAGNOSTIC_PASS'
         and result.get('authority') == 0 and result.get('public_ack') is False, 'BUILDER_RESULT')
    need(result.get('binding_sha256') == sha(raw_file(root / 'binding.json')), 'BUILDER_BINDING_HASH')
    required = set(source_paths()) | {'tests/godot/run_saved_room_builder.py',
                                   'tests/godot/saved_room_builder.gd', 'toolchain.lock.json'}
    need(required <= set(binding['source_files']), 'BUILDER_SOURCE_SET')
    verify_source_binding(root, binding['source_files'], require_current_source=require_current_source)
    need(set(binding.get('project_files', {})) == {'project.godot', 'scenes/workbench.tscn',
        'addons/builder/plugin.cfg', 'addons/builder/plugin.gd', 'recipe.json'}, 'BUILDER_PROJECT_SET')
    for name, digest in binding['project_files'].items():
        _bound_file(root / 'project', name, digest)
    need(raw_file(root / 'project/addons/builder/plugin.gd') == raw_file(root / 'source/tests/godot/saved_room_builder.gd'),
         'BUILDER_PLUGIN_BINDING')
    required_artifacts = {'recipe.json', 'native-observation.json', 'project/scenes/room.tscn',
        'editor-host/capture.json', 'editor-host/process-start.json', 'editor-host/process-exit.json',
        'editor-host/stdout.txt', 'editor-host/stderr.txt', 'editor-host/invocation.json'}
    need(set(result.get('artifacts', {})) == required_artifacts, 'BUILDER_ARTIFACT_SET')
    for name, digest in result['artifacts'].items():
        _bound_file(root, name, digest)
    stage = native_job.verify_captured_stage(root / 'editor-host', result['artifacts']['editor-host/capture.json'])
    recipe_bytes = raw_file(root / 'recipe.json')
    need(recipe_bytes == raw_file(root / 'project/recipe.json'), 'BUILDER_RECIPE_COPY')
    recipe = json.loads(recipe_bytes)
    need(recipe == build_recipe(), 'BUILDER_RECIPE_SOURCE')
    scene_bytes = raw_file(root / 'project/scenes/room.tscn')
    observation = json.loads(raw_file(root / 'native-observation.json'))
    need(raw_file(root / 'native-observation.json') == raw_file(root / 'project/native-observation.json'),
         'BUILDER_OBSERVATION_COPY')
    verify_observation(observation, recipe, recipe_bytes, scene_bytes, stage['actual_process_exit']['pid'])
    need(not raw_file(root / 'editor-host/stderr.txt').strip()
         and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked',
                           raw_file(root / 'editor-host/stdout.txt')), 'BUILDER_NATIVE_LOG')
    invocation = json.loads(raw_file(root / 'editor-host/invocation.json'))
    pin = json.loads(raw_file(root / 'source/toolchain.lock.json'))['godot']
    project = root / 'project'
    executable = Path(binding['binary_path'])
    need(executable.is_absolute(), 'BUILDER_BINARY_PATH')
    need(invocation.get('source_files') == binding['source_files']
         and invocation.get('binary_sha256') == binding['binary_sha256'] == pin['gui_sha256']
         and invocation.get('cwd') == str(project)
         and invocation.get('argv') == [str(executable), '--headless', '--editor', '--path', str(project),
                                        'res://scenes/workbench.tscn'], 'BUILDER_INVOCATION_BINDING')
    return scene_bytes


def saved_room_provenance(root: Path, *, require_current_source: bool = True) -> dict:
    verify_saved_room(root, require_current_source=require_current_source)
    result = json.loads(raw_file(root / 'result.json'))
    files = {name: sha(raw_file(root / name)) for name in
             ('binding.json', 'result.json', *result['artifacts'])}
    return {'schema': 'hh-o2-saved-room-provenance-1', 'authority': 0,
            'run_id': result['run_id'], 'files': files}


def source_manifest():
    names = set(source_paths()) | {'tests/godot/run_saved_room_builder.py',
        'tests/godot/saved_room_builder.gd', 'toolchain.lock.json'}
    # Include the actual imported trusted Python closure, not just the facade.
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(STUDIO) and path.suffix == '.py':
                names.add(path.relative_to(STUDIO).as_posix())
    return {name: sha(raw_file(STUDIO / name)) for name in sorted(names)}


def run(run_id, godot):
    need(re.fullmatch(r'o2-saved-room-[a-z0-9-]{1,40}', run_id), 'BUILDER_RUN_ID')
    idle_window()
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = root / 'project'
    recipe = build_recipe()  # Validate the whole planned recipe before editor mutation.
    recipe_bytes = (json.dumps(recipe, sort_keys=True, indent=2) + '\n').encode()
    project_files = {
        'project.godot': b'config_version=5\n[application]\nconfig/name="HH Saved Room Diagnostic"\n'
            b'run/main_scene="res://scenes/workbench.tscn"\n[editor_plugins]\n'
            b'enabled=PackedStringArray("res://addons/builder/plugin.cfg")\n'
            b'[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
        'scenes/workbench.tscn': b'[gd_scene format=3]\n[node name="Workbench" type="Node"]\n',
        'addons/builder/plugin.cfg': b'[plugin]\nname="HH saved room candidate"\n'
            b'description="Trusted diagnostic"\nauthor="HH Studio"\nversion="0.1"\nscript="plugin.gd"\n',
        'addons/builder/plugin.gd': raw_file(STUDIO / 'tests/godot/saved_room_builder.gd'),
        'recipe.json': recipe_bytes,
    }
    for name, raw in project_files.items():
        write(project / name, raw)
    write(root / 'recipe.json', recipe_bytes)
    files = source_manifest()
    for name, digest in files.items():
        raw = raw_file(STUDIO / name)
        need(sha(raw) == digest, 'BUILDER_FREEZE_RACE')
        write(root / 'source' / name, raw)
    pin = json.loads(raw_file(STUDIO / 'toolchain.lock.json'))['godot']
    executable = godot.resolve(strict=True)
    binding = {'schema': 'hh-o2-saved-room-binding-1', 'authority': 0, 'run_id': run_id,
        'source_files': files, 'project_files': {name: sha(raw) for name, raw in project_files.items()},
        'binary_sha256': pin['gui_sha256'], 'binary_path': str(executable),
        'catalog_sha256': recipe['catalog_sha256']}
    write(root / 'binding.json', binding)
    result = {'schema': 'hh-o2-saved-room-result-1', 'run_id': run_id, 'authority': 0,
        'public_ack': False, 'status': 'INCOMPLETE', 'binding_sha256': sha(raw_file(root / 'binding.json'))}
    try:
        idle_window()
        native_job.run_trusted_stage([str(executable), '--headless', '--editor', '--path', str(project),
            'res://scenes/workbench.tscn'], cwd=project, output=root / 'editor-host',
            source_root=STUDIO, source_files=files, binary_sha256=pin['gui_sha256'])
        write(root / 'native-observation.json', raw_file(project / 'native-observation.json'))
        artifacts = ('recipe.json', 'native-observation.json', 'project/scenes/room.tscn',
            'editor-host/capture.json', 'editor-host/process-start.json', 'editor-host/process-exit.json',
            'editor-host/stdout.txt', 'editor-host/stderr.txt', 'editor-host/invocation.json')
        result.update(status='DIAGNOSTIC_PASS', artifacts={name: sha(raw_file(root / name)) for name in artifacts})
    except Exception as error:
        result.update(status='DIAGNOSTIC_FAIL', error_class=type(error).__name__)
        if re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', str(error)):
            result['error_code'] = str(error)
    failure = None
    if result['status'] == 'DIAGNOSTIC_PASS':
        try:
            _verify_saved_room(root, result)
        except Exception as error:
            failure = str(error) if re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', str(error)) else type(error).__name__
            result.update(status='DIAGNOSTIC_FAIL', verification_error=failure)
    verified = result['status'] == 'DIAGNOSTIC_PASS' and failure is None
    write(root / 'result.json', result)
    write(root / 'verification.json', {'verified': verified, 'error': failure, 'authority': 0})
    print(json.dumps({'run_id': run_id, 'verified': verified, 'error': failure, 'authority': 0}), flush=True)
    return 0 if verified else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--godot', required=True, type=Path)
    arguments = parser.parse_args()
    raise SystemExit(run(arguments.run_id, arguments.godot))
