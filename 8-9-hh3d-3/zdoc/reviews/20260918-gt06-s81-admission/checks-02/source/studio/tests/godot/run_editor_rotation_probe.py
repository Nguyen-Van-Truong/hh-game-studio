"""Actual registered edits: exact transform/component history across capture and delay."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
spec = importlib.util.spec_from_file_location('s54_rotation_editor', STUDIO / 'godot-addon/editor_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)


def transform_bytes(snapshot):
    """Preserve float32 bits, including signed zero; no numeric epsilon."""
    node = next(node for node in snapshot['state']['nodes'] if node['stable_id'] == 'box.rotation')
    basis, origin = node['stored']['transform']['value']
    values = [value for column in basis['value'] for value in column['value']] + origin['value']
    return struct.pack('<12f', *values)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    output = parser.parse_args().output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    report = {'ok': False, 'public_ack': False, 'acceptance': False, 'checks': [],
              'source_files': owner._release(), 'cases': []}
    actor = None

    def save(path, value):
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')

    def check(label, value):
        report['checks'].append({'label': label, 'passed': value is True})
        if value is not True:
            raise AssertionError(label)

    try:
        local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
        binary = Path(local['godot_console']).with_name('Godot_v4.7.2-stable_win64.exe')
        bundle = owner.factory.compose(owner.factory.DEFAULT_SCENE, owner.factory.DEFAULT_SCRIPT,
            scene_revision='sha256:' + '0' * 64,
            engine_sha256='8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e')
        cases = [
            ('yaw_translation', [0, 15, 0], [1, 1, 1], {'position': [4, 5, 6]}),
            ('xyz_nonuniform', [17, -31, 43], [0.5, 2, 3.25],
             {'position': [-4, 5, 6], 'rotation_degrees': [-23, 47, 61], 'scale': [1.75, 0.25, 4.5]})]
        for case, rotation, scale, changes in cases:
            case_path = output / case
            case_path.mkdir()
            actor = owner.EditorOwner(case_path, bundle, editor_binary=binary)
            case_report = {'name': case, 'identity': actor.identity, 'captures': []}
            report['cases'].append(case_report)
            snapshots = {}
            initial = actor.inspect()
            steps = [
                ('create', 'scene.node.create', 'root', {'stable_id': 'box.rotation',
                 'node_type': 'MeshInstance3D', 'name': 'RotatedBox', 'position': [1, 2, 3],
                 'rotation_degrees': rotation, 'scale': scale, 'box_size': [2, 3, 4]}),
                ('update', 'scene.node.update', 'box.rotation', {'changes': changes}),
                ('undo', 'scene.undo', 'root', {'steps': 1}),
                ('redo', 'scene.redo', 'root', {'steps': 1}),
                ('remove', 'scene.node.remove', 'box.rotation', {}),
                ('restore', 'scene.undo', 'root', {'steps': 1})]
            for label, operation, target, payload in steps:
                before = actor.inspect()
                command = case + '.' + label
                digest = 'sha256:' + hashlib.sha256(command.encode()).hexdigest()
                capture_intent = actor.prepare_effect(command, digest, 'capture',
                    expected_generation=before['generation'], expected_revision=before['revision'],
                    deadline_ms=int(time.time() * 1000) + 10000)
                checkpoint = actor.capture(capture_intent)
                captured_at = time.monotonic()
                time.sleep(0.25)
                after_delay = actor.inspect()
                case_report['captures'].append({'command_id': command, 'checkpoint_sha256': checkpoint.scene_sha256,
                    'delay_seconds': time.monotonic() - captured_at})
                check(command + '_capture_and_delay_preserve_exact_state', after_delay == before)
                projection = {'operation': operation, 'command_id': command,
                    'expected_generation': before['generation'], 'expected_revision': before['revision'],
                    'target_stable_id': target, 'payload': {'expected_generation': before['generation'], **payload}}
                intent = actor.prepare_edit(command, digest, projection, checkpoint,
                    deadline_ms=int(time.time() * 1000) + 10000)
                facts = actor.observation(actor.apply_edit(intent))
                save(case_path / (label + '-receipt.json'), facts)
                snapshots[label] = after = actor.inspect()
                save(case_path / (label + '.json'), after)
                check(command + '_registered_unsaved_same_editor_history', facts['semantic_state'] == after['state']
                    and facts['files_saved'] is False and facts['live_state_durable'] is False
                    and facts['public_ack'] is False and facts['history_boundary'] is False
                    and after['generation'] == initial['generation']
                    and after['root_instance_id'] == initial['root_instance_id']
                    and after['history_id'] == initial['history_id']
                    and after['working_files'] == initial['working_files'])
            for restored, expected in (('undo', 'create'), ('redo', 'update'), ('restore', 'update')):
                check(case + '_' + restored + '_exact_complete_semantics',
                      snapshots[restored]['state'] == snapshots[expected]['state'])
                check(case + '_' + restored + '_bit_exact_transform',
                      transform_bytes(snapshots[restored]) == transform_bytes(snapshots[expected]))
            case_report['transform_f32_hex'] = {label: transform_bytes(snapshot).hex()
                for label, snapshot in snapshots.items() if label != 'remove'}
            check(case + '_history_preserved', snapshots['restore']['can_undo'] is True
                  and snapshots['restore']['can_redo'] is True)
            case_report['close'] = actor.close()
            owner.EditorOwner._clean_closed(case_report['close'], case_report['identity']['pid'])
            actor = None
        check('source_unchanged', report['source_files'] == owner._release())
        report['ok'] = True
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        report['cause'] = str(error.__cause__) if error.__cause__ else None
    finally:
        if actor is not None:
            try:
                report['cleanup'] = actor.close()
                owner.EditorOwner._clean_closed(report['cleanup'], case_report['identity']['pid'])
            except BaseException as error:
                report['ok'] = False
                report['cleanup_failure'] = str(error)
        save(output / 'result.json', report)
    print(json.dumps({key: report.get(key) for key in ('ok', 'failure', 'cause', 'cleanup_failure')}))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
