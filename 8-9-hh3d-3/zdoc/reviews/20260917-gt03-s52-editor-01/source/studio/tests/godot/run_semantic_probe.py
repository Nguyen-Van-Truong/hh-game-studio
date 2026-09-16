"""Frozen, sequential Linux candidate / actual Windows editor JCS diagnostic.

The Windows project has an explicit trusted diagnostic plugin-config overlay.
Scene/script and original addon bytes remain identical. No selected state,
publication, caller-controlled scripts, or public ACK is exercised.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def editor_observation(bundle, case, runner, binary):
    temporary = Path(tempfile.mkdtemp(prefix='hh-gt03-semantic-')).resolve()
    project = temporary / 'project'
    try:
        for name, raw in bundle.files.items():
            target = project / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        overlay = 'addons/hh_studio/semantic_probe.gd'
        (project / overlay).write_bytes((STUDIO / 'tests/godot/semantic_editor_probe.gd').read_bytes())
        config = project / 'addons/hh_studio/plugin.cfg'
        config.write_bytes(config.read_bytes().replace(b'script="plugin.gd"', b'script="semantic_probe.gd"'))
        files = {name: sha(project / name) for name in (*bundle.files, overlay)}
        save(case / 'editor-inputs.json', {'files': files,
            'overlay_paths': ['addons/hh_studio/plugin.cfg', overlay],
            'unchanged_bundle_paths': [name for name in bundle.files if name != 'addons/hh_studio/plugin.cfg']})
        host = runner.run_process([str(binary), '--headless', '--editor', '--path', str(project),
            '--log-file', str(temporary / 'engine.log'), 'res://scenes/fixture.tscn'],
            cwd=project, output=case, timeout=25, label='editor', env=runner._isolated_user_env(temporary))
        stdout = (case / host['stdout']).read_text(encoding='utf-8', errors='strict')
        stderr = (case / host['stderr']).read_text(encoding='utf-8', errors='strict')
        log = temporary / 'engine.log'
        log_text = log.read_text(encoding='utf-8', errors='strict') if log.exists() else ''
        if log.exists(): shutil.copyfile(log, case / 'editor-engine.log')
        # The pinned Windows GUI executable emits this explicit engine log;
        # its inherited stdout can be empty even in headless editor mode.
        markers = [line.removeprefix('HH_EDITOR_SEMANTIC ') for line in log_text.splitlines()
                   if line.startswith('HH_EDITOR_SEMANTIC ')]
        from studio.protocol.core import parse_json
        report = parse_json(markers[0].encode()) if len(markers) == 1 else None
        unchanged = all(sha(project / name) == digest for name, digest in files.items())
        clean = re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked',
                          stdout + '\n' + stderr + '\n' + log_text) is None
        passed = bool(host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified']
            and not host['timed_out'] and clean and unchanged and report
            and report.get('schema') == 'hh-editor-semantic-probe-1'
            and report.get('editor_hint') is True and report.get('context_kind') == 'live_editor'
            and type(report.get('pid')) is int and report['pid'] == host.get('target_pid')
            and report.get('engine_version') == '4.7.2-stable (official)'
            and report.get('public_ack') is False and report.get('snapshot', {}).get('ok') is True)
        result = {'passed': passed, 'host': host, 'inputs_unchanged': unchanged,
                  'logs_clean': clean, 'observation': report, 'observation_source': 'editor-engine.log',
                  'binary_sha256': sha(binary)}
        save(case / 'editor-observation.json', result)
        return result
    finally:
        # Owned synchronous runner drains its exact Job before returning. Keep
        # the namespace if no actual tree-drain record was obtained.
        if 'host' in locals() and host.get('tree_verified') is True:
            target = temporary.resolve()
            if target.parent != Path(tempfile.gettempdir()).resolve() or not target.name.startswith('hh-gt03-semantic-'):
                raise ValueError('owned temporary path changed')
            shutil.rmtree(target)


def frozen_cases(output, binary):
    sys.path.insert(0, str(STUDIO.parent))
    comparator = load('s51_frozen_comparator', STUDIO / 'godot-addon/profile_readback.py')
    executor = load('s51_frozen_executor', STUDIO / 'godot-addon/linux_executor.py')
    runner = load('s51_frozen_owned', STUDIO / 'build/bootstrap/run_fixture.py')
    profile = load('s51_frozen_profile_cases', STUDIO / 'tests/godot/run_profile_probe.py')
    cases = profile.cases(comparator.factory)
    # Same scene bytes and overridden value, changed script default/source.
    cases.insert(1, ('script_replaced', cases[0][1], cases[0][2].replace(b'int = 9', b'int = 11')))
    rows = []
    for name, scene, script in cases:
        case = output / name
        case.mkdir()
        bundle = comparator.factory.compose(scene, script, scene_revision='sha256:' + '1' * 64,
                                             engine_sha256=executor.BINARY_SHA256)
        comparator.factory.qualify(bundle)
        (case / 'manifest.json').write_bytes(bundle.manifest_bytes)
        project = case / 'input'
        for path, raw in bundle.files.items():
            target = project / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        native = executor.run(project, mode='profile-validate', output=case / 'executor', timeout_seconds=20)
        stdout = (case / 'executor/engine-stdout.txt').read_text(encoding='utf-8')
        stderr = (case / 'executor/engine-stderr.txt').read_text(encoding='utf-8')
        linux = profile.evaluate(native, stdout, stderr, bundle, comparator)
        save(case / 'linux-observation.json', linux)
        row = {'name': name, 'passed': False, 'linux': linux, 'public_ack': False}
        if linux['passed'] and linux['comparison']['semantic_observed'] is True:
            editor = editor_observation(bundle, case, runner, binary)
            row['editor'] = editor
            if editor['passed']:
                semantic = linux['observation']['semantic']
                snapshot = editor['observation']['snapshot']
                left = comparator.semantic_state_bytes(semantic)
                right = comparator.factory.bundle_codec.canonical_bytes(snapshot['state'])
                (case / 'linux-state.jcs').write_bytes(left)
                (case / 'editor-state.jcs').write_bytes(right)
                row['exact_state_bytes_equal'] = left == right
                row['exact_revision_equal'] = semantic['revision'] == snapshot['revision']
                row['editor_hash_recomputed'] = snapshot['revision'] == 'sha256:' + hashlib.sha256(right).hexdigest()
                row['passed'] = all(row[k] is True for k in
                    ('exact_state_bytes_equal', 'exact_revision_equal', 'editor_hash_recomputed'))
                if name == 'defaults_override' and row['passed']:
                    # Actual raw process evidence for current-release unit replays.
                    save(output / 'validation-run-semantic-baseline.json', {'result': native,
                        'stdout': stdout, 'stderr': stderr, 'scene': scene.decode(), 'script': script.decode()})
        rows.append(row)
        save(output / 'semantic-cases.json', {'passed': all(r['passed'] for r in rows), 'cases': rows,
             'public_ack': False, 'sandbox_acceptance': False})
        if not row['passed']: break
    result = {'passed': len(rows) == len(cases) and all(row['passed'] for row in rows),
              'cases': rows, 'public_ack': False, 'sandbox_acceptance': False}
    if result['passed']:
        result['script_replacement_changed_revision'] = (rows[0]['linux']['comparison']['semantic_revision'] !=
                                                        rows[1]['linux']['comparison']['semantic_revision'])
        result['passed'] = result['script_replacement_changed_revision']
    save(output / 'semantic-cases.json', result)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id): parser.error('run ID')
    output = args.output.resolve()
    output.relative_to(STUDIO.parent / 'zdoc/reviews')
    output.mkdir(parents=True, exist_ok=False)
    common = load('s51_freezer', STUDIO / 'tests/godot/run_editor_probe.py')
    before = common.inputs()
    source = output / 'source/studio'
    for name, digest in before.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
        if sha(target) != digest: raise ValueError('source changed during snapshot')
    runner = load('s51_freeze_owned', source / 'build/bootstrap/run_fixture.py')
    closure = runner.source_closure_sha256(before)
    save(output / 'source-closure.json', {'files': before, 'source_closure_sha256': closure})
    lock = json.loads((source / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary) != lock['gui_sha256']: raise ValueError('Windows binary pin')
    code = ('import importlib.util,sys;from pathlib import Path;'
        'p=Path("tests/godot/run_semantic_probe.py").resolve();'
        's=importlib.util.spec_from_file_location("frozen_semantic",p);'
        'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
        'sys.exit(m.frozen_cases(Path(sys.argv[1]),Path(sys.argv[2])))')
    env = dict(os.environ)
    env['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host = runner.run_process([sys.executable, '-B', '-c', code, str(output), str(binary)],
        cwd=source, output=output, timeout=240, label='semantic', env=env)
    case_file = output / 'semantic-cases.json'
    cases = json.loads(case_file.read_bytes()) if case_file.exists() else None
    capture = {'run_id': args.run_id, 'source_closure_sha256': closure, 'host': host, 'cases': cases,
        'snapshot_unchanged': all(sha(source / name) == digest for name, digest in before.items()),
        'origin_source_unchanged': before == common.inputs(), 'windows_binary_unchanged': sha(binary) == lock['gui_sha256'],
        'public_ack': False, 'sandbox_acceptance': False, 'selected_state_verified': False}
    # Concurrent edits to the origin are reported, not substituted into this
    # diagnostic's immutable executed closure. A later final run must re-freeze.
    capture['passed'] = bool(cases and cases['passed'] and capture['snapshot_unchanged']
        and capture['windows_binary_unchanged'] and host['exit_code'] == host['wrapper_exit_code'] == 0
        and host['tree_verified'] and not host['timed_out'])
    save(output / 'capture.json', capture)
    print(json.dumps({'passed': capture['passed'], 'closure': closure,
                      'cases': len(cases['cases']) if cases else 0, 'host': host}))
    return 0 if capture['passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
