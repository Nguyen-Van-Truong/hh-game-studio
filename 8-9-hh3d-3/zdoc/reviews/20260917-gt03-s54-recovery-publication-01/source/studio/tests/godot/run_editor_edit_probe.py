"""Actual Windows registered editor edits; no public grant or persistence claim."""
import argparse
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s54_native_edit_owner', STUDIO / 'godot-addon/editor_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    sources = owner._release()
    for name in ('run_editor_edit_probe.py', 'test_editor_owner.py'):
        sources['tests/godot/' + name] = hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
    for name, expected in sources.items():
        raw = (STUDIO / name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected
        path = output / 'source/studio' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    report = {'ok': False, 'public_ack': False, 'acceptance': False, 'checks': [], 'source_files': sources,
        'scope': 'actual owned EditorPlugin edits only; no public grant or durable journal claim'}
    editor = None

    def check(name, condition):
        report['checks'].append({'label': name, 'passed': condition is True})
        if condition is not True:
            raise AssertionError(name)

    def denied(name, action):
        try:
            action()
        except owner.EditorOwnerError:
            check(name, True)
        else:
            check(name, False)

    try:
        local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
        binary = Path(local['godot_console']).with_name('Godot_v4.7.2-stable_win64.exe')
        bundle = owner.factory.compose(owner.factory.DEFAULT_SCENE, owner.factory.DEFAULT_SCRIPT,
            scene_revision='sha256:' + '0' * 64,
            engine_sha256='8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e')
        editor = owner.EditorOwner(output, bundle, editor_binary=binary)
        initial = editor.inspect()
        report['identity'] = identity = editor.identity
        steps = [
            ('create', 'scene.node.create', 'root', {'stable_id': 'box-one', 'node_type': 'MeshInstance3D',
                'name': 'BoxOne', 'position': [1, 2, 3], 'rotation_degrees': [0, 0, 0], 'scale': [1, 1, 1],
                'box_size': [1, 1, 1]}),
            ('update', 'scene.node.update', 'box-one', {'changes': {'position': [4, 5, 6], 'box_size': [2, 3, 4]}}),
            ('undo', 'scene.undo', 'root', {'steps': 1}),
            ('redo', 'scene.redo', 'root', {'steps': 1}),
            ('remove', 'scene.node.remove', 'box-one', {}),
            ('restore', 'scene.undo', 'root', {'steps': 1}),
        ]
        observed = {}
        for label, operation, target, payload in steps:
            before = editor.inspect()
            command = 'edit.' + label
            digest = 'sha256:' + hashlib.sha256(command.encode()).hexdigest()
            capture_intent = editor.prepare_effect(command, digest, 'capture', expected_generation=before['generation'],
                expected_revision=before['revision'], deadline_ms=int(time.time() * 1000) + 10000)
            checkpoint = editor.capture(capture_intent)
            projection = {'operation': operation, 'command_id': command, 'expected_generation': before['generation'],
                'expected_revision': before['revision'], 'target_stable_id': target,
                'payload': {'expected_generation': before['generation'], **payload}}
            intent = editor.prepare_edit(command, digest, projection, checkpoint,
                deadline_ms=int(time.time() * 1000) + 10000)
            denied(label + '_copied_intent_rejected', lambda: editor.apply_edit(replace(intent)))
            receipt = editor.apply_edit(intent)
            facts = editor.observation(receipt)
            observed[label] = facts
            (output / (label + '-receipt.json')).write_bytes(owner.canonical_bytes(facts))
            check(label + '_same_generation_root_files', facts['generation_after'] == initial['generation']
                and facts['root_after'] == initial['root_instance_id'] and facts['working_files'] == initial['working_files'])
            check(label + '_bound_checkpoint_unsaved', facts['checkpoint_scene_sha256'] == checkpoint.scene_sha256
                and facts['checkpoint_observation_id'] == checkpoint.observation_id and facts['public_ack'] is False
                and facts['files_saved'] is False and facts['live_state_durable'] is False
                and facts['history_boundary'] is False)
            denied(label + '_single_use', lambda: editor.apply_edit(intent))
            denied(label + '_copied_receipt_rejected', lambda: editor.observation(replace(receipt)))
        check('undo_exact_semantics', observed['undo']['semantic_state'] == observed['create']['semantic_state'])
        check('redo_exact_semantics', observed['redo']['semantic_state'] == observed['update']['semantic_state'])
        check('remove_actual_node', len(observed['remove']['semantic_state']['nodes']) == 1)
        check('remove_undo_exact_semantics', observed['restore']['semantic_state'] == observed['update']['semantic_state'])
        check('script_attachment_preserved', observed['restore']['semantic_state']['nodes'][0]['stored']['script']
            == initial['state']['nodes'][0]['stored']['script'])
        check('native_history_preserved', observed['restore']['can_undo'] is True and observed['restore']['can_redo'] is True)
        # Actual same-process manual edit after capture must invalidate the checkpoint.
        before = editor.inspect()
        command, digest = 'edit.stale', 'sha256:' + 'a' * 64
        capture_intent = editor.prepare_effect(command, digest, 'capture', expected_generation=before['generation'],
            expected_revision=before['revision'], deadline_ms=int(time.time() * 1000) + 10000)
        checkpoint = editor.capture(capture_intent)
        edit = {'operation': 'scene.node.update', 'command_id': command,
            'expected_generation': before['generation'], 'expected_revision': before['revision'],
            'target_stable_id': 'root', 'payload': {'expected_generation': before['generation'],
            'changes': {'position': [8, 8, 8]}}}
        editor.apply_projection({**edit, 'command_id': 'manual.change'})
        manual = editor.inspect()
        denied('stale_checkpoint_after_manual_edit', lambda: editor.prepare_edit(command, digest, edit, checkpoint,
            deadline_ms=int(time.time() * 1000) + 10000))
        check('manual_edit_preserved_after_rejection', editor.inspect() == manual)
        report['close'] = editor.close()
        owner.EditorOwner._clean_closed(report['close'], identity['pid'])
        check('actual_exit_and_job_clean', True)
        check('source_unchanged', all(hashlib.sha256((STUDIO / name).read_bytes()).hexdigest() == digest
            for name, digest in sources.items()))
        report['ok'] = True
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        report['cause'] = str(error.__cause__) if error.__cause__ else None
    finally:
        if editor is not None:
            try:
                report['close'] = editor.close()
            except BaseException as error:
                report['cleanup_failure'] = str(error)
                report['ok'] = False
        report['artifacts'] = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob('*')) if path.is_file() and not any(part in
            ('.godot', '__pycache__', 'appdata', 'localappdata', 'temp', 'tmp') for part in path.relative_to(output).parts)}
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('ok', 'failure', 'cause', 'cleanup_failure')}))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
