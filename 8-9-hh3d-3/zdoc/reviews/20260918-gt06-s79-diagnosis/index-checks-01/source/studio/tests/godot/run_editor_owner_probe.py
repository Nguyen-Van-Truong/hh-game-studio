"""Focused native IPC slice, not authenticated publication/selector acceptance."""
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
spec = importlib.util.spec_from_file_location('s52_owned_editor_probe', STUDIO / 'godot-addon/editor_owner.py')
owner = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner
spec.loader.exec_module(owner)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    output.mkdir(parents=True, exist_ok=False)
    source = owner._release()
    for relative in source:
        target = output / 'source/studio' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / relative).read_bytes())
    for name in ('run_editor_owner_probe.py', 'test_editor_owner.py'):
        target = output / 'source/studio/tests/godot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(Path(__file__).with_name(name).read_bytes())
        source['tests/godot/' + name] = hashlib.sha256(target.read_bytes()).hexdigest()
    report = {'ok': False, 'acceptance': False, 'public_ack': False, 'scope': 'owned Windows editor IPC only; no selector or user auth',
              'source_files': source, 'checks': []}
    editor = None
    def check(label, value):
        report['checks'].append({'label': label, 'passed': value is True})
        if value is not True:
            raise RuntimeError(label)
    def denied(label, action):
        try:
            action()
        except owner.EditorOwnerError:
            check(label, True)
        else:
            check(label, False)
    try:
        local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
        binary = Path(local['godot_console']).with_name('Godot_v4.7.2-stable_win64.exe')
        bundle = owner.factory.compose(owner.factory.DEFAULT_SCENE, owner.factory.DEFAULT_SCRIPT,
            scene_revision='sha256:' + '0' * 64, engine_sha256='8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e')
        editor = owner.EditorOwner(output, bundle, editor_binary=binary)
        report['identity'] = editor.identity
        initial = editor.inspect()
        check('real_editor_session_bound', initial['editor_session_id'] == editor.identity['session_id'])
        projection = {'operation': 'scene.node.update', 'command_id': 'probe.move', 'expected_revision': initial['revision'],
            'expected_generation': initial['generation'], 'target_stable_id': 'root',
            'payload': {'expected_generation': initial['generation'], 'changes': {'position': [2.0, 0.0, 0.0]}}}
        editor.apply_projection(projection)
        moved = editor.inspect()
        check('actual_semantic_transform', moved['revision'] != initial['revision'] and moved['can_undo'] is True)
        denied('stale_prepare_rejected', lambda: editor.prepare_effect('save.stale', 'sha256:' + '1' * 64, 'capture',
            expected_generation=initial['generation'], expected_revision=initial['revision'], deadline_ms=int(time.time() * 1000) + 10000))
        intent = editor.prepare_effect('save.good', 'sha256:' + '2' * 64, 'capture', expected_generation=moved['generation'],
            expected_revision=moved['revision'], deadline_ms=int(time.time() * 1000) + 20000)
        check('prepare_no_capture_file', not (editor._scratch / intent.scratch_name).exists())
        denied('copied_intent_rejected', lambda: editor.capture(replace(intent)))
        capture = editor.capture(intent)
        captured = editor.capture_bytes(capture)
        check('captured_actual_scene_bytes', len(captured) > 0 and hashlib.sha256(captured).hexdigest() == capture.scene_sha256)
        check('capture_keeps_live_revision_and_generation', editor.inspect()['revision'] == moved['revision'] and editor.inspect()['generation'] == moved['generation'])
        denied('copied_capture_receipt_rejected', lambda: editor.capture_bytes(replace(capture)))
        denied('single_use_capture_rejected', lambda: editor.capture(intent))
        final = owner.factory.compose(captured, bundle.files['scripts/fixture_actor.gd'], scene_revision=capture.semantic_revision,
                                       engine_sha256=bundle.engine_sha256)
        owner.factory.qualify(final)
        check('capture_complete_profile_eligible', True)
        adoption_intent = editor.prepare_effect('save.good', 'sha256:' + '2' * 64, 'adopt', expected_generation=moved['generation'],
            expected_revision=moved['revision'], deadline_ms=int(time.time() * 1000) + 20000)
        adoption = editor.adopt(adoption_intent, final, {'generation': 1, 'identity': 'sha256:' + '3' * 64})
        facts = editor.observation(adoption, final)
        report['capture'] = editor.observation(capture)
        report['adoption'] = facts
        check('same_editor_new_root_generation', facts['editor_session_id'] == capture.editor_session_id
              and facts['generation_after'] > facts['generation_before'] and facts['root_before'] != facts['root_after'])
        check('post_adoption_exact_semantics', owner.canonical_bytes(facts['semantic_state']) == editor.captured_semantic(capture))
        check('post_adoption_exact11bytes', facts['working_files'] == owner._metadata(final.files))
        check('declared_history_boundary', facts['history_boundary'] is True and facts['can_undo'] is False and facts['can_redo'] is False)
        denied('copied_adoption_receipt_rejected', lambda: editor.observation(replace(adoption), final))
        denied('old_generation_command_rejected', lambda: editor.apply_projection(projection))
        editor.stop()
        denied('stop_blocks_new_effect', lambda: editor.prepare_effect('save.stopped', 'sha256:' + '4' * 64, 'capture',
            expected_generation=facts['generation_after'], expected_revision=facts['semantic_revision'], deadline_ms=int(time.time() * 1000) + 10000))
        report['close'] = editor.close()
        check('actual_clean_exit_and_checked_job', report['close']['actual_process_exit']['exit_code'] == 0
            and report['close']['wrapper_exit_code'] == 0 and report['close']['job']['closed'] is True
            and report['close']['job']['zero_observed'] is True and report['close']['job']['tainted'] is False)
        check('source_unchanged', all(hashlib.sha256((STUDIO / path).read_bytes()).hexdigest() == digest for path, digest in source.items()))
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
        report['artifacts'] = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob('*')) if path.is_file() and '__pycache__' not in path.parts}
        (output / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({key: report.get(key) for key in ('ok', 'failure', 'cause', 'cleanup_failure')}))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
