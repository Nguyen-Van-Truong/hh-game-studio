"""Frozen actual publication cuts and authenticated recovery; schedule Linux first.

Each case has a distinct owned publisher process, exact crash exit, protected
custody stream and fresh readback editor. Fault hooks only wrap existing runtime
methods in that process; no runtime source is rewritten. No acceptance claim.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import traceback

STUDIO = Path(__file__).resolve().parents[2]
CASES = {
    'scene-cas': ('scene.save', 'cas-before-selected', 93),
    'script-cas': ('script_text.replace', 'cas-before-selected', 93),
    'scene-committed': ('scene.save', 'committed-before-return', 94),
    'script-committed': ('script_text.replace', 'committed-before-return', 94),
    'script-unwitnessed': ('script_text.replace', 'committed-before-custody', 95),
    'script-retired': ('script_text.replace', 'retired-before-cas', 96),
    'edit-ready': ('scene.node.update', 'edit-ready-before-effect', 97),
    'edit-applied': ('scene.node.update', 'edit-applied-before-commit', 98),
}
DEFAULT_CASES = ('scene-cas', 'script-committed')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def configure_runtime(source):
    global STUDIO, save, sha, call
    STUDIO = source
    base = load('s54_cut_http_helpers', STUDIO / 'tests/godot/run_recovery_publication_probe.py')
    save, sha, call = base.save, base.sha, base.call


def crash_child(output, binary, closure, case):
    sys.path.insert(0, str(STUDIO.parent))
    from studio.protocol.core import Request, canonical_bytes, parse_json
    from studio.host.core.transport import epoch_ms
    operation, cut, exit_code = CASES[case]
    module = load('cut_original_owner', STUDIO / 'godot-addon/publication_owner.py')
    validation = module._load('validation_owner')
    factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    work = output / 'owned'
    work.mkdir()
    actor = server = None
    try:
        actor = module.GodotPublicationOwner.create(work, project_id='project.fixture', initial_bundle=initial,
            editor_binary=binary, source_closure_sha256=closure)
        server = module._load('publication_transport').PublicationTransport(actor).start()
        credential = actor.sessions.issue()
        catalog = actor.contract.CATALOG_DIGEST
        status, lease, _ = call(server, '/v1/lease', {'project_id': actor.project_id, 'ttl_ms': 90000},
                                credential.bearer, catalog)
        assert status == 200, 'original writer lease'
        initial_snapshot, original_identity = actor.inspect(), actor._editor.identity

        def request(command, op, target, payload, before):
            payload = {'expected_generation': before['generation'],
                       'expected_project_revision': before['project_revision'], **payload}
            horizon = 89000 if op in ('scene.save', 'script_text.replace') else 29000
            return Request(command_id=command, project_id=actor.project_id, operation=op,
                lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'], expected_revision=before['revision'],
                target=target, payload=payload, payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                deadline_ms=min(lease['expires_ms'], epoch_ms() + horizon))

        if operation != 'scene.node.update':
            dirty_request = request('matrix.dirty', 'scene.node.update', {'stable_id': 'root'},
                                    {'changes': {'position': [2, 3, 4]}}, initial_snapshot)
            status, dirty_response, wire = call(server, '/v1/commands', dirty_request.as_dict(), credential.bearer, catalog)
            save(output / 'dirty-request.json', dirty_request.as_dict())
            save(output / 'dirty-response.json', dirty_response)
            (output / 'dirty-response-wire.json').write_bytes(wire)
            assert status == 200 and dirty_response.get('code') == 'GODOT_EDITOR_EDITED', 'actual authenticated dirty edit'
            # Give the independently bounded save/script validation a fresh
            # credential and lease after preparation has drained.
            preparation_lease = lease
            credential = actor.sessions.rotate(credential)
            status, lease, _ = call(server, '/v1/lease', {'project_id': actor.project_id, 'ttl_ms': 90000},
                                    credential.bearer, catalog)
            assert status == 200 and lease['fencing_epoch'] > preparation_lease['fencing_epoch'], 'fresh publication fence'
            save(output / 'leases.json', {'preparation': preparation_lease, 'publication': lease})
        before = actor.inspect()
        target = {'stable_id': 'root'}
        if operation == 'script_text.replace':
            text = factory.DEFAULT_SCRIPT.replace(b'int = 7', b'int = 9').decode('utf-8')
            assert text.encode() != factory.DEFAULT_SCRIPT, 'fixture script actually changes'
            target = {'path': actor.contract.SCRIPT_PATH}
            payload = {'expected_sha256': before['working_files'][actor.contract.SCRIPT_PATH]['sha256'], 'text': text}
        elif operation == 'scene.save':
            payload = {'expected_files': {p: before['working_files'][p]['sha256'] for p in
                                         (actor.contract.SCENE_PATH, actor.contract.SCRIPT_PATH)}}
        else:
            payload = {'changes': {'position': [2, 3, 4]}}
        proposed = request('matrix.original', operation, target, payload, before)
        save(output / 'original.json', {'case': case, 'cut': cut, 'storage_id': actor.storage_id,
            'project_id': actor.project_id, 'source_closure_sha256': closure, 'request': proposed.as_dict(),
            'initial': initial_snapshot, 'before': before, 'editor_identity': original_identity,
            'selection': actor._journal.selection_facts(), 'expected_exit_code': exit_code})
        journal = actor._journal

        def crash_boundary(*, pending_binding=None, terminal=None):
            # Read the store directly: after CAS the immutable journal prefix
            # intentionally still describes the old selected version.
            selected = journal._store.inspect_selection()
            bundle = journal._store.read_descriptor(selected.descriptor)
            bindings = [row for row in actor._validator._semantic.values() if row[0] == bundle]
            assert len(bindings) == 1, 'selected bundle has registered isolated semantic validation'
            bound_bundle, receipt, _ = bindings[0]
            observed = actor._validator.semantic_observation(receipt, bound_bundle)
            expected = parse_json(validation.comparator.semantic_state_bytes(observed['semantic']))
            candidate_path = output / 'expected-selected'
            candidate_path.mkdir()
            for name, raw in bundle.files.items():
                path = candidate_path / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
            save(output / 'expected-manifest.json', parse_json(bundle.manifest_bytes))
            save(output / 'expected-state.json', expected)
            save(output / 'selected-validation.json', observed)
            save(output / 'validator.json', actor._validator.snapshot())
            snapshot = journal._state.snapshot()
            command = actor.journal_model.state_model.lookup(journal._state, proposed.command_id, proposed.digest)
            if terminal is not None:
                original_raw = journal.lookup_response(proposed.command_id, proposed.digest)
                assert original_raw is not None
                (output / 'original-response-canonical.json').write_bytes(original_raw)
            elif pending_binding is not None:
                # Candidate bytes are explicitly unwitnessed evidence. They
                # must never be exposed by original_response after restart.
                plan = actor.journal_model.state_model.terminal_plan(snapshot, command)
                (output / 'unwitnessed-response-candidate.json').write_bytes(canonical_bytes(plan['response']))
            boundary = {'case': case, 'cut': cut, 'expected_exit_code': exit_code,
                'public_response_returned': False, 'command': command, 'journal_snapshot': snapshot,
                'publication_events': [parse_json(raw) for raw in journal._state.events],
                'native_head_before_return': asdict(journal._head), 'custody': journal._custody.record,
                'selected': {'selector': parse_json(selected.source_bytes),
                             'selector_version': actor.journal_model._version(selected.version)},
                'retired_editor_cleanup': [old._cleanup for old in actor._retired_editors]}
            if pending_binding is not None:
                boundary['unwitnessed_binding'] = asdict(pending_binding)
            if cut != 'retired-before-cas' and not (operation == 'script_text.replace' and cut == 'cas-before-selected'):
                boundary['actual_editor_at_cut'] = actor._editor.script_observation()
                boundary['actual_editor_identity_at_cut'] = actor._editor.identity
            save(output / 'crash-boundary.json', boundary)
            print('HH_NATIVE_PUBLICATION_CUT ' + json.dumps({'case': case, 'cut': cut, 'exit_code': exit_code}), flush=True)
            os._exit(exit_code)

        if cut == 'cas-before-selected':
            original = journal._store.select
            def select(intent):
                original(intent)
                crash_boundary()
            journal._store.select = select
        elif cut == 'committed-before-return':
            original = journal.commit
            def commit(command, digest, *, observed_ms):
                terminal = original(command, digest, observed_ms=observed_ms)
                crash_boundary(terminal=terminal)
            journal.commit = commit
        elif cut == 'committed-before-custody':
            original = journal.commit
            def commit(command, digest, *, observed_ms):
                journal._custody.persist_binding = lambda binding: crash_boundary(pending_binding=binding)
                return original(command, digest, observed_ms=observed_ms)
            journal.commit = commit
        elif cut == 'retired-before-cas':
            original = journal.retired
            def retired(*args, **kwargs):
                original(*args, **kwargs)
                crash_boundary()
            journal.retired = retired
        elif cut == 'edit-ready-before-effect':
            original = journal.edit_checkpoint
            def ready(*args, **kwargs):
                original(*args, **kwargs)
                crash_boundary()
            journal.edit_checkpoint = ready
        else:
            journal.edit_committed = lambda *args, **kwargs: crash_boundary()
        status, result, wire = call(server, '/v1/commands', proposed.as_dict(), credential.bearer, catalog)
        save(output / 'unexpected-return.json', {'status': status, 'response': result})
        (output / 'unexpected-wire.json').write_bytes(wire)
        if hasattr(actor, '_last_error'):
            traceback.print_exception(actor._last_error)
        raise AssertionError('crash hook did not exit')
    finally:
        failures = []
        if actor is not None:
            actor.sessions.halt()
        for resource in (server, actor):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(error)
        if failures:
            raise failures[0]


def run_case(output, binary, closure, case, run_id, original_case=None):
    sys.path.insert(0, str(STUDIO.parent))
    from studio.protocol.core import canonical_bytes, parse_json
    from studio.host.core.transport import epoch_ms
    runner = load('cut_case_runner', STUDIO / 'build/bootstrap/run_fixture.py')
    operation, cut, exit_code = CASES[case]
    rows = []
    report = {'ok': False, 'case': case, 'cut': cut, 'source_closure_sha256': closure, 'checks': rows,
              'candidate_only': True, 'gt03_acceptance': False}
    actor = server = reopened = None

    def check(label, condition):
        rows.append({'label': label, 'passed': condition is True})
        save(output / 'progress.json', rows)
        if condition is not True:
            raise AssertionError(label)

    try:
        child = (original_case if original_case is not None else output) / 'original'
        if original_case is None:
            child.mkdir()
            host = runner.run_process([sys.executable, '-B', str(STUDIO / 'tests/godot/run_recovery_cut_matrix.py'), '--crash-child',
                '--case', case, '--output', str(child), '--binary', str(binary), '--closure', closure,
                '--run-id', run_id], cwd=STUDIO, output=child, timeout=150, label='publisher')
        else:
            host = json.loads((original_case / 'original-host.json').read_bytes())
            native = json.loads((child / host['host']).read_bytes())
            check('reused_publisher_raw_exit_and_identity_match', native['exit_code'] == host['exit_code']
                  and native['target_pid'] == host['target_pid'])
            report['composite_proof'] = {'original_case': str(original_case),
                'original_outer_exit_missing': not (original_case / 'recovery-cut-host.json').exists(),
                'publisher_reexecuted': False, 'driver_sha256': sha(Path(__file__).resolve())}
        report['original_host'] = host
        save(output / 'original-host.json', host)
        check('actual_cut_exit_wrapper0_owned_tree_clean', host['exit_code'] == exit_code
              and host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out'])
        original = json.loads((child / 'original.json').read_bytes())
        check('original_case_and_frozen_runtime_match', original['case'] == case
              and original['source_closure_sha256'] == closure)
        boundary = json.loads((child / 'crash-boundary.json').read_bytes())
        expected = json.loads((child / 'expected-state.json').read_bytes())
        manifest = json.loads((child / 'expected-manifest.json').read_bytes())
        command, digest = original['request']['command_id'], original['request']['digest']
        expected_phase = {'cas-before-selected': 'ACTIVATING', 'committed-before-return': 'COMMITTED',
            'committed-before-custody': 'READBACK', 'retired-before-cas': 'RETIRED',
            'edit-ready-before-effect': 'EDIT_READY', 'edit-applied-before-commit': 'EDIT_READY'}[cut]
        check('crash_at_exact_original_phase_without_response', boundary['command']['phase'] == expected_phase
              and boundary['public_response_returned'] is False and not (child / 'unexpected-return.json').exists())
        kinds = [event['kind'] for event in boundary['publication_events'] if event.get('command_id') == command]
        if cut == 'cas-before-selected':
            check('actual_cas_precedes_missing_selected_event', 'SELECTED' not in kinds
                  and boundary['selected'] != original['selection'])
        if operation == 'script_text.replace':
            check('actual_old_editor_retired_clean_before_cut', bool(boundary['retired_editor_cleanup']))
            editor_model = load('cut_cleanup_verifier', STUDIO / 'godot-addon/editor_owner.py')
            for cleanup in boundary['retired_editor_cleanup']:
                editor_model.EditorOwner._clean_closed(cleanup, original['editor_identity']['pid'])
        if cut == 'edit-applied-before-commit':
            at_cut = boundary['actual_editor_at_cut']['snapshot']
            check('actual_edit_effect_before_missing_commit', 'EDIT_COMMITTED' not in kinds
                  and at_cut['state']['nodes'][0]['position'] == [2, 3, 4]
                  and at_cut['state'] != expected)
        if cut == 'edit-ready-before-effect':
            check('checkpoint_ready_without_editor_mutation', boundary['actual_editor_at_cut']['snapshot']['state'] == expected)
        module = load('cut_recovery_host', STUDIO / 'godot-addon/recovery_host.py')
        work = output / 'recovery'
        work.mkdir()
        actor = module.GodotRecoveryHost.open(work, storage_id=original['storage_id'], project_id=original['project_id'],
            expected_source_closure_sha256=closure, editor_binary=binary)
        credential = actor.sessions.issue(operations=module.GRANTS)
        server = module.RecoveryTransport(actor).start()
        def rpc(path, body, **kwargs):
            return call(server, path, body, credential.bearer, module.CATALOG_DIGEST, **kwargs)
        lookup_body = {'project_id': actor.project_id, 'command_id': command}
        status, pre_lookup, pre_wire = rpc('/v1/lookup', lookup_body, control=True)
        save(output / 'before-reconcile-lookup.json', {'http_status': status, 'response': pre_lookup})
        recovered_prefix = actor._recovery._journal.snapshot()
        save(output / 'before-reconcile-snapshot.json', recovered_prefix)
        prior_attempts = recovered_prefix.get('recovery', {}).get('attempts', [])
        if prior_attempts and prior_attempts[-1]['phase'] == 'TERMINAL':
            # A resumed process cannot acquire a second recovery effect after a
            # durable terminal. Preserve lookup evidence and stop explicitly;
            # the prior readback/terminal artifacts must be audited separately.
            report['existing_terminal_replay_only'] = True
            raw = actor._recovery._journal.recovered_response(command, digest)
            check('existing_terminal_lookup_replays_without_engine_or_append', status == 200
                  and canonical_bytes(pre_lookup) == raw and actor._recovery._editor is None)
            raise AssertionError('existing durable terminal: replay captured; prior readback audit required')
        original_raw = (child / 'original-response-canonical.json').read_bytes() if cut == 'committed-before-return' else None
        if original_raw is not None:
            check('witnessed_terminal_replays_exact_original_before_reconcile', status == 200
                  and canonical_bytes(pre_lookup) == original_raw)
        else:
            check('unfinished_or_unwitnessed_command_has_no_original_ack', pre_lookup.get('status') != 'COMMITTED'
                  and pre_lookup.get('postconditions', {}).get('public_ack') is not True)
        if cut == 'committed-before-custody':
            check('native_unwitnessed_commit_is_blocked', command in recovered_prefix['recovery']['blocked_original_commands']
                  and actor._recovery._journal.lookup(command, digest)['phase'] == 'COMMITTED')
            try:
                actor._recovery._journal.original_response(command, digest)
            except actor.model.RecoveryError as error:
                check('orphan_original_response_rejected', getattr(error, 'code', '') == 'RECOVERY_ORIGINAL_NOT_WITNESSED')
            else:
                check('orphan_original_response_rejected', False)
        selected = actor._recovery._journal.selection_facts()
        check('recovery_does_not_replace_selected_version', selected == boundary['selected'])
        status, lease, _ = rpc('/v1/lease', {'project_id': actor.project_id, 'ttl_ms': 30000})
        check('new_authority_fencing_epoch', status == 200 and lease['fencing_epoch'] > original['request']['fencing_epoch'])
        body = {'project_id': actor.project_id, 'command_id': command, 'digest': digest,
            'lease_id': lease['lease_id'], 'fencing_epoch': lease['fencing_epoch'],
            'deadline_ms': min(lease['expires_ms'], epoch_ms() + 29000)}
        save(output / 'recovery-request.json', body)
        readonly = actor.sessions.issue(operations=frozenset({'control.lookup'}))
        before_denied = actor._recovery.authority_context()
        denied, _, _ = call(server, '/v1/reconcile', body, readonly.bearer, module.CATALOG_DIGEST)
        check('lookup_only_grant_rejected_before_recovery_effect', denied == 400
              and actor._recovery.authority_context() == before_denied)
        status, response, wire = rpc('/v1/reconcile', body)
        save(output / 'response.json', response)
        (output / 'response-wire.json').write_bytes(wire)
        if response.get('status') not in ('COMMITTED', 'REJECTED') and hasattr(actor, '_last_error'):
            traceback.print_exception(actor._last_error)
        restored = cut in ('retired-before-cas', 'edit-ready-before-effect', 'edit-applied-before-commit')
        check('actual_recovery_has_expected_durable_terminal', status == 200
              and response.get('status') == ('REJECTED' if restored else 'COMMITTED'))
        raw = actor._recovery._journal.recovered_response(command, digest)
        check('exact_recovered_response_bytes', raw == canonical_bytes(response))
        if original_raw is not None:
            check('durable_commit_before_return_preserves_original_ack', raw == original_raw)
        else:
            post = response.get('postconditions', {})
            check('new_terminal_is_explicit_reconciliation', post.get('reconciled') is True
                  and post.get('restored_editor_history') is False and post.get('public_ack') is (not restored))
        if cut == 'committed-before-custody':
            check('recovered_orphan_is_distinct_from_unwitnessed_original', raw != (child / 'unwitnessed-response-candidate.json').read_bytes()
                  and response['postconditions'].get('original_outcome_unknown') is True)
        editor = actor._recovery._editor
        identity = editor.identity
        actual = editor.script_observation()
        snapshot = actual['snapshot']
        save(output / 'actual-editor.json', actual)
        save(output / 'actual-editor-identity.json', identity)
        check('fresh_engine_complete_expected_semantics', snapshot['state'] == expected
              and snapshot['revision'] == manifest['caller_observations']['scene_revision']
              and not snapshot['can_undo'] and not snapshot['can_redo'])
        check('fresh_editor_identity_and_generation', identity['session_id'] != original['editor_identity']['session_id']
              and (identity['pid'], identity['creation_filetime']) != (original['editor_identity']['pid'], original['editor_identity']['creation_filetime'])
              and snapshot['generation'] > original['before']['generation'])
        check('all_selected_input_hashes_match_readback', snapshot['working_files'] == {
            name: {key: row[key] for key in ('sha256', 'size_bytes')} for name, row in manifest['files'].items()})
        bundle = actor._recovery._journal.read_selected_bundle()
        check('all_eleven_selected_bytes_preserved', len(bundle.files) == 11 and all(
            data == (child / 'expected-selected' / name).read_bytes() for name, data in bundle.files.items()))
        script_hash = manifest['files']['scripts/fixture_actor.gd']['sha256']
        check('fresh_script_source_disk_and_default', actual['script']['source_sha256'] == script_hash
              and actual['script']['disk_sha256'] == script_hash
              and actual['script']['defaults']['fixture_value']['value'] == (9 if operation == 'script_text.replace' and not restored else 7))
        after = actor._recovery._journal.snapshot()
        save(output / 'journal-snapshot.json', after)
        save(output / 'recovery-events.json', [parse_json(event) for event in actor._recovery._journal._events])
        check('same_custody_terminal_and_readonly_selection', after['recovery']['attempts'][-1]['phase'] == 'TERMINAL'
              and actor._recovery._journal._files._readonly is True and actor._recovery._journal.selection_facts() == selected)
        status, retry, retry_wire = rpc('/v1/reconcile', body)
        check('retry_exact_without_new_editor_or_event', status == 200 and retry_wire == wire
              and actor._recovery._editor is editor and actor._recovery._journal.snapshot() == after)
        status, looked, _ = rpc('/v1/lookup', lookup_body, control=True)
        check('lookup_exact_terminal', status == 200 and canonical_bytes(looked) == raw)
        actor.sessions.halt()
        server.close()
        server = None
        actor.close()
        save(output / 'editor-close.json', editor._cleanup)
        editor_module = load('cut_final_cleanup_verifier', STUDIO / 'godot-addon/editor_owner.py')
        editor_module.EditorOwner._clean_closed(editor._cleanup, identity['pid'])
        actor = None
        restart = output / 'restart'
        restart.mkdir()
        reopened = module.GodotRecoveryHost.open(restart, storage_id=original['storage_id'], project_id=original['project_id'],
            expected_source_closure_sha256=closure, editor_binary=binary)
        fresh = reopened.sessions.issue(operations=module.GRANTS)
        server = module.RecoveryTransport(reopened).start()
        head = reopened._recovery._journal._head
        status, looked, _ = call(server, '/v1/lookup', lookup_body, fresh.bearer, module.CATALOG_DIGEST, control=True)
        check('fresh_host_replays_exact_terminal', status == 200 and canonical_bytes(looked) == raw)
        status, retry, retry_wire = call(server, '/v1/reconcile', body, fresh.bearer, module.CATALOG_DIGEST)
        check('fresh_host_retry_no_engine_append_or_selection', status == 200 and retry_wire == wire
              and reopened._recovery._editor is None and reopened._recovery._journal._head == head
              and reopened._recovery._journal.selection_facts() == selected)
        report['ok'] = True
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        traceback.print_exception(error)
        if actor is not None:
            try:
                save(output / 'failure-journal-snapshot.json', actor._recovery._journal.snapshot())
                save(output / 'failure-recovery-events.json', [parse_json(event)
                    for event in actor._recovery._journal._events])
            except BaseException as diagnostic:
                report['failure_snapshot_error'] = type(diagnostic).__name__ + ': ' + str(diagnostic)
    finally:
        failures = []
        for resource in (server, actor, reopened):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(type(error).__name__ + ': ' + str(error))
        if failures:
            report['ok'] = False
            report['cleanup_failures'] = failures
        save(output / 'result.json', report)
    print('HH_RECOVERY_CUT_COMPLETE ' + json.dumps({'case': case, 'ok': report['ok'], 'checks': len(rows)}), flush=True)
    return 0 if report['ok'] else 2


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--case', choices=tuple(CASES), action='append')
    parser.add_argument('--list-cases', action='store_true')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--crash-child', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--closure')
    parser.add_argument('--runtime-package', type=Path)
    parser.add_argument('--original-case', type=Path)
    args = parser.parse_args()
    if args.list_cases:
        print(json.dumps({'cases': CASES, 'default': DEFAULT_CASES}, indent=2))
        return 0
    if args.output is None or not args.run_id or not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id):
        parser.error('output and valid run ID required')
    cases = args.case or list(DEFAULT_CASES)
    if len(cases) != len(set(cases)):
        parser.error('duplicate case')
    original_studio = STUDIO
    runtime_package = args.runtime_package.resolve() if args.runtime_package else None
    runtime_source = runtime_package / 'source/studio' if runtime_package else STUDIO
    configure_runtime(runtime_source)
    if runtime_package is not None:
        frozen_record = json.loads((runtime_package / 'source-closure.json').read_bytes())
        if not all(sha(runtime_source / name) == digest for name, digest in frozen_record['files'].items()):
            raise ValueError('existing frozen runtime source changed')
        frozen_runner = load('cut_resume_source_verifier', runtime_source / 'build/bootstrap/run_fixture.py')
        if frozen_runner.source_closure_sha256(frozen_record['files']) != frozen_record['source_closure_sha256']:
            raise ValueError('existing frozen runtime closure mismatch')
        if args.closure and args.closure != frozen_record['source_closure_sha256']:
            raise ValueError('requested runtime closure mismatch')
    if args.original_case is not None and (runtime_package is None or len(cases) != 1 or args.crash_child):
        parser.error('original-case requires one case and existing runtime package')
    if args.frozen or args.crash_child:
        if len(cases) != 1 or args.binary is None or not args.closure:
            parser.error('one case, binary and closure required for owned child')
        if args.crash_child:
            return crash_child(args.output, args.binary, args.closure, cases[0])
        return run_case(args.output, args.binary, args.closure, cases[0], args.run_id,
                        args.original_case.resolve() if args.original_case else None)
    output = args.output.resolve()
    output.relative_to(original_studio.parent / 'zdoc/reviews')
    output.mkdir(parents=True, exist_ok=False)
    inventory = load('cut_matrix_inventory', STUDIO / 'tests/godot/run_editor_probe.py')
    before = frozen_record['files'] if runtime_package else inventory.inputs()
    source = runtime_source if runtime_package else output / 'source/studio'
    if runtime_package is None:
        for name, digest in before.items():
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((STUDIO / name).read_bytes())
            if sha(target) != digest:
                raise ValueError('source changed during freeze')
    runner = load('cut_matrix_runner', source / 'build/bootstrap/run_fixture.py')
    closure = runner.source_closure_sha256(before)
    save(output / 'source-closure.json', {'files': before, 'source_closure_sha256': closure})
    if runtime_package:
        driver = output / 'driver.py'
        driver.write_bytes(Path(__file__).read_bytes())
        save(output / 'runtime-source-reference.json', {'runtime_package': str(runtime_package),
            'source_closure_sha256': closure, 'driver_sha256': sha(driver),
            'scope': 'existing immutable runtime plus separately frozen recovery driver'})
    else:
        driver = source / 'tests/godot/run_recovery_cut_matrix.py'
    lock = json.loads((source / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((original_studio / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary) != lock['gui_sha256']:
        raise ValueError('pinned GUI binary mismatch')
    environment = dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT'] = str(original_studio / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    rows = []
    for case in cases:
        case_output = output / case
        case_output.mkdir()
        extra = ['--runtime-package', str(runtime_package)] if runtime_package else []
        if args.original_case:
            extra.extend(['--original-case', str(args.original_case.resolve())])
        host = runner.run_process([sys.executable, '-B', str(driver),
            '--frozen', '--case', case, '--output', str(case_output), '--run-id', args.run_id,
            '--binary', str(binary), '--closure', closure, *extra], cwd=source, output=case_output, timeout=240,
            label='recovery-cut', env=environment)
        result_path = case_output / 'result.json'
        result = json.loads(result_path.read_bytes()) if result_path.exists() else {}
        log_roots = [case_output] + ([args.original_case / 'original'] if args.original_case else [])
        logs = [p for root in log_roots for p in root.rglob('*.txt') if p.name in ('stdout.txt', 'stderr.txt')
                or p.name.endswith(('-stdout.txt', '-stderr.txt'))]
        clean_logs = all(not re.search(rb'(?i)\b(warning|error|fatal|traceback)\b', p.read_bytes()) for p in logs)
        passed = host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out']
        passed = passed and result.get('ok') is True and bool(result.get('checks')) and all(r['passed'] for r in result['checks']) and clean_logs
        row = {'case': case, 'host': host, 'checks': len(result.get('checks', [])), 'native_logs_clean': clean_logs, 'passed': passed}
        rows.append(row)
        save(output / 'progress.json', rows)
        print(json.dumps(row), flush=True)
        if not passed:
            break
    unchanged = before == inventory.inputs()
    frozen_unchanged = all(sha(source / name) == digest for name, digest in before.items())
    passed = len(rows) == len(cases) and all(row['passed'] for row in rows) and unchanged and frozen_unchanged
    capture = {'run_id': args.run_id, 'cases': rows, 'passed': passed, 'source_closure_sha256': closure,
        'origin_source_unchanged': unchanged, 'snapshot_unchanged': frozen_unchanged,
        'runtime_package': str(runtime_package) if runtime_package else None,
        'driver_sha256': sha(driver), 'composite_proof': args.original_case is not None,
        'candidate_only': True, 'gt03_acceptance': False}
    save(output / 'capture.json', capture)
    print(json.dumps({'passed': passed, 'source_closure_sha256': closure}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
