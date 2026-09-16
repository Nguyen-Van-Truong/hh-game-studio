"""Frozen real HTTP script publication, Linux validation and editor succession.

Uses actual owners and native journal. This is candidate evidence, not GT-03
acceptance or support for scripts outside the closed declarative profile.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import traceback

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frozen(output, binary, closure):
    sys.path.insert(0, str(STUDIO.parent))
    from studio.protocol.core import Request, canonical_bytes, parse_json
    from studio.host.core.transport import epoch_ms
    module = load('script_publication_probe_owner', STUDIO / 'godot-addon/publication_owner.py')
    validation = module._load('validation_owner')
    factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    workspace = output / 'owned'
    workspace.mkdir()
    owner = server = reopened = old_editor = new_editor = None
    rows = []

    def check(label, condition):
        rows.append({'label': label, 'passed': condition is True})
        save(output / 'progress.json', rows)
        if condition is not True:
            raise AssertionError(label)

    try:
        owner = module.GodotPublicationOwner.create(workspace, project_id='project.fixture',
            initial_bundle=initial, editor_binary=binary, source_closure_sha256=closure)
        credential = owner.sessions.issue()
        transport = module._load('publication_transport')
        server = transport.PublicationTransport(owner).start()

        def call(path, body, *, control=False, bearer=None):
            connection = http.client.HTTPConnection('127.0.0.1',
                server.control_port if control else server.port, timeout=95)
            try:
                connection.request('POST', path, canonical_bytes(body), {
                    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + (bearer or credential.bearer),
                    'X-HH-Catalog': owner.contract.CATALOG_DIGEST})
                response = connection.getresponse()
                raw = response.read()
                return response.status, parse_json(raw), raw
            finally:
                connection.close()

        status, discovery, _ = call('/v1/discovery', {'project_id': owner.project_id})
        save(output / 'discovery.json', discovery)
        check('authenticated_discovery', status == 200)
        status, _, _ = call('/v1/discovery', {'project_id': owner.project_id}, bearer='z' * 43)
        check('foreign_bearer_denied', status == 400)
        before = owner.inspect()
        save(output / 'before.json', before)
        old_editor = owner._editor
        old_identity = old_editor.identity
        save(output / 'old-editor-identity.json', old_identity)
        changed = old_editor.apply_projection({'operation': 'scene.node.update', 'command_id': 'local.dirty',
            'expected_revision': before['revision'], 'expected_generation': before['generation'],
            'target_stable_id': 'root', 'payload': {'expected_generation': before['generation'],
            'changes': {'position': [2, 3, 4]}}})
        check('actual_editor_transform', changed.get('ok') is True)
        dirty = owner.inspect()
        save(output / 'dirty.json', dirty)
        check('dirty_scene_differs_from_selection', dirty['revision'] != before['revision']
            and dirty['project_revision'] == before['project_revision'])
        status, lease, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000, 'access': 'read'})
        save(output / 'preview-lease.json', lease)
        check('authenticated_read_lease', status == 200)
        text = factory.DEFAULT_SCRIPT.replace(b'int = 7', b'int = 9').decode('utf-8')
        script_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        payload = {'expected_generation': dirty['generation'],
            'expected_project_revision': dirty['project_revision'],
            'expected_sha256': dirty['working_files'][owner.contract.SCRIPT_PATH]['sha256'], 'text': text}
        script_target = {'path': owner.contract.SCRIPT_PATH}

        def request(command_id, operation, target, value, horizon):
            return Request(command_id=command_id, project_id=owner.project_id, operation=operation,
                lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'],
                expected_revision=dirty['revision'], target=target, payload=value,
                payload_hash='sha256:' + hashlib.sha256(canonical_bytes(value)).hexdigest(),
                deadline_ms=min(lease['expires_ms'], epoch_ms() + horizon))

        preview_payload = {'expected_generation': dirty['generation'],
            'expected_project_revision': dirty['project_revision'], 'operation': 'script_text.replace',
            'target': script_target, 'payload': payload}
        preview_request = request('preview.script', 'scene.preview', {'stable_id': 'root'}, preview_payload, 29_000)
        validators_before = owner._validator.snapshot()
        events_before = tuple(owner._journal._state.events)
        status, preview, _ = call('/v1/commands', preview_request.as_dict())
        save(output / 'preview.json', preview)
        plan = preview.get('postconditions', {})
        check('authenticated_script_diff_preview', status == 200 and preview.get('code') == 'GODOT_PREVIEW_READY'
            and plan.get('changes_applied') is False and plan.get('script_parse_status') == 'NOT_RUN'
            and plan.get('diff', [{}])[0].get('before_sha256') == payload['expected_sha256']
            and plan.get('diff', [{}])[0].get('after_sha256') == script_hash
            and bool(plan.get('diff', [{}])[0].get('unified_diff')))
        check('preview_has_no_engine_or_journal_effect', owner._validator.snapshot() == validators_before
            and tuple(owner._journal._state.events) == events_before and owner.inspect() == dirty)
        invalid_payload = {**preview_payload, 'payload': {**payload, 'text': text + 'func unsafe():\n\tpass\n'}}
        invalid = request('preview.unsupported', 'scene.preview', {'stable_id': 'root'}, invalid_payload, 29_000)
        status, rejected, _ = call('/v1/commands', invalid.as_dict())
        save(output / 'unsupported-preview.json', rejected)
        check('unsupported_script_rejected_before_activation', status == 400
            and owner._validator.snapshot() == validators_before
            and tuple(owner._journal._state.events) == events_before and owner.inspect() == dirty)

        # Preview used read authority; obtain the first write lease only now.
        status, lease, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 90_000})
        save(output / 'publication-lease.json', lease)
        check('publication_write_lease', status == 200)
        replacement = request('command.script', 'script_text.replace', script_target, payload, 89_000)
        save(output / 'request.json', replacement.as_dict())
        status, result, original_wire = call('/v1/commands', replacement.as_dict())
        save(output / 'response.json', result)
        (output / 'response-wire.json').write_bytes(original_wire)
        if result.get('status') != 'COMMITTED' and hasattr(owner, '_last_error'):
            traceback.print_exception(owner._last_error)
        check('authenticated_script_replace_committed', status == 200 and result.get('status') == 'COMMITTED'
            and result.get('code') == 'GODOT_MANAGED_SCRIPT_REPLACED'
            and result.get('postconditions', {}).get('public_ack') is True)
        new_editor = owner._editor
        new_identity = new_editor.identity
        after = owner.inspect()
        script_state = new_editor.script_observation()
        selected = owner._journal.read_selected_bundle()
        save(output / 'after.json', after)
        save(output / 'script-readback.json', script_state)
        save(output / 'new-editor-identity.json', new_identity)
        expected_state = parse_json(canonical_bytes(dirty['state']))
        expected_state['nodes'][0]['stored']['script']['source_sha256'] = script_hash
        check('full_dirty_scene_retained_with_new_script', canonical_bytes(after['state']) == canonical_bytes(expected_state)
            and after['state']['nodes'][0]['position'] == [2, 3, 4])
        check('fresh_native_editor_identity', new_editor is not old_editor
            and new_identity['session_id'] != old_identity['session_id']
            and int(new_identity['creation_filetime']) > int(old_identity['creation_filetime']))
        check('next_editor_generation', after['generation'] == dirty['generation'] + 1)
        check('script_default_changed_despite_scene_override', script_state['script']['defaults']['fixture_value']['value'] == 9
            and after['state']['nodes'][0]['stored']['fixture_value'] == 23)
        check('actual_script_source_and_disk_bytes', script_state['script']['source_sha256'] == script_hash
            and script_state['script']['disk_sha256'] == script_hash
            and selected.files[owner.contract.SCRIPT_PATH] == text.encode('utf-8'))
        check('selected_complete_eleven_inputs', len(selected.files) == 11
            and after['working_files'] == {name: {key: row[key] for key in ('sha256', 'size_bytes')}
                for name, row in parse_json(selected.manifest_bytes)['files'].items()}
            and all(selected.files[name] == initial.files[name] for name in initial.files
                    if name not in (owner.contract.SCENE_PATH, owner.contract.SCRIPT_PATH)))
        check('selected_project_changed', after['project_revision'] != before['project_revision'])
        check('fresh_history_boundary', after['can_undo'] is False and after['can_redo'] is False)
        old_close = old_editor.close()
        save(output / 'old-editor-close.json', old_close)
        owner.editor_model.EditorOwner._clean_closed(old_close, old_identity['pid'])
        check('old_editor_actual_clean_exit', True)
        events = [parse_json(raw) for raw in owner._journal._state.events]
        save(output / 'events.json', events)
        command_events = [event for event in events if event.get('command_id') == replacement.command_id]
        kinds = [event['kind'] for event in command_events]
        check('ordered_validation_retirement_selection_commit', kinds == [
            'CAPTURE_PREPARED', 'CAPTURED', 'PREPARED', 'STAGED', 'VALIDATED',
            'RETIRE_PREPARED', 'RETIRED', 'ACTIVATING', 'SELECTED', 'READBACK', 'COMMITTED'])
        retired = next(event['retirement'] for event in command_events if event['kind'] == 'RETIRED')
        adopted = next(event['adoption'] for event in command_events if event['kind'] == 'READBACK')
        validated = next(event['validation'] for event in command_events if event['kind'] == 'VALIDATED')
        check('actual_isolated_linux_candidate_validation', len(owner._validator.snapshot()['attempts']) == 2
            and validated['validator_engine_sha256'] == validation.executor.BINARY_SHA256
            and validated['context_kind'] == 'isolated_candidate'
            and validated['project_revision'] == selected.project_revision
            and validated['scene_revision'] == after['revision']
            and validated['public_ack'] is False
            and validated['validation_completed_ms'] <= retired['effect_started_ms'])
        check('retirement_before_successor_launch', retired['close_completed_ms'] <= adopted['effect_started_ms']
            and adopted['old_editor'] == old_identity and adopted['new_editor'] == new_identity)
        selection = owner._journal.selection_facts()
        save(output / 'selection.json', selection)
        save(output / 'journal.json', owner._journal.snapshot())
        save(output / 'validator.json', owner._validator.snapshot())
        durable = owner._journal.lookup_response(replacement.command_id, replacement.digest)
        check('durable_original_response', parse_json(durable) == result)
        status, duplicate, duplicate_wire = call('/v1/commands', replacement.as_dict())
        save(output / 'duplicate-response.json', duplicate)
        check('duplicate_exact_reply_no_effect', status == 200 and duplicate == result
            and duplicate_wire == original_wire and owner._journal.selection_facts() == selection
            and [parse_json(raw) for raw in owner._journal._state.events] == events)
        status, lookup, lookup_wire = call('/v1/lookup', {'project_id': owner.project_id,
            'command_id': replacement.command_id}, control=True)
        save(output / 'lookup-response.json', lookup)
        check('control_lookup_exact_reply', status == 200 and lookup == result and lookup_wire == original_wire)
        _, stopped, _ = call('/v1/stop', {'project_id': owner.project_id, 'command_id': 'control.stop'}, control=True)
        save(output / 'stop-response.json', stopped)
        check('authenticated_stop', stopped.get('stopped') is True and stopped.get('draining') is False)
        journal_model, storage_id = owner.journal_model, owner.storage_id
        server.close()
        server = None
        owner.close()
        owner = None
        new_close = new_editor.close()
        save(output / 'new-editor-close.json', new_close)
        module._load('editor_owner').EditorOwner._clean_closed(new_close, new_identity['pid'])
        check('successor_actual_clean_exit', True)
        reopened = journal_model.PublicationJournalV4.reopen(storage_id, project_id='project.fixture')
        check('readonly_reopen_exact_selection', reopened.selection_facts() == selection)
        restored = reopened.lookup(replacement.command_id, replacement.digest)
        check('readonly_reopen_durable_commit', restored['phase'] == 'COMMITTED'
            and restored['receipt']['status'] == 'COMMITTED' and restored['public_ack'] is False)
        check('readonly_reopen_original_response', reopened.lookup_response(replacement.command_id, replacement.digest) == durable)
        check('readonly_reopen_complete_selected_bundle', reopened.read_selected_bundle() == selected)
        save(output / 'reopened.json', reopened.snapshot())
        reopened.close()
        reopened = None
        save(output / 'publication.json', {'passed': True, 'checks': rows, 'candidate_only': True,
            'gt03_acceptance': False, 'authenticated_script_replace_observed': True,
            'source_closure_sha256': closure})
        print('HH_SCRIPT_PUBLICATION_COMPLETE ' + json.dumps({'passed': True, 'checks': len(rows)}), flush=True)
        return 0
    finally:
        failures = []
        if owner is not None:
            owner.sessions.halt()
        for resource in (server, owner, reopened, old_editor, new_editor):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise failures[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--closure')
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id):
        parser.error('invalid run ID')
    if args.frozen:
        return frozen(args.output, args.binary, args.closure)
    output = args.output.resolve()
    output.relative_to(STUDIO.parent / 'zdoc/reviews')
    output.mkdir(parents=True, exist_ok=False)
    inventory = load('script_publication_inventory', STUDIO / 'tests/godot/run_editor_probe.py')
    before = inventory.inputs()
    source = output / 'source/studio'
    for name, digest in before.items():
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
        if sha(target) != digest:
            raise ValueError('source changed during freeze')
    runner = load('script_publication_runner', source / 'build/bootstrap/run_fixture.py')
    closure = runner.source_closure_sha256(before)
    save(output / 'source-closure.json', {'files': before, 'source_closure_sha256': closure})
    lock = json.loads((source / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary) != lock['gui_sha256']:
        raise ValueError('GUI pin mismatch')
    environment = dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host = runner.run_process([sys.executable, '-B', str(source / 'tests/godot/run_script_publication_probe.py'),
        '--frozen', '--output', str(output), '--run-id', args.run_id, '--binary', str(binary), '--closure', closure],
        cwd=source, output=output, timeout=240, label='script-publication', env=environment)
    unchanged = before == inventory.inputs()
    frozen_unchanged = all(sha(source / name) == digest for name, digest in before.items())
    passed = (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified']
        and not host['timed_out'] and frozen_unchanged)
    save(output / 'capture.json', {'run_id': args.run_id, 'host': host, 'passed': passed,
        'source_closure_sha256': closure, 'origin_source_unchanged': unchanged,
        'snapshot_unchanged': frozen_unchanged, 'candidate_only': True, 'gt03_acceptance': False})
    print(json.dumps({'passed': passed, 'host': host, 'origin_source_unchanged': unchanged}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
