"""Frozen HTTP FIFO with two real credentials, real expiry and native edits.

Authoring this harness does not run it. The coordinator schedules the single
bootstrap Linux validator and owned Windows editor. Queue receipts are volatile;
edit replies are durable historical observations, not saved scene/history proof.
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
import time
import traceback

STUDIO = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
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
    module = load('s54_fifo_publication_owner', STUDIO / 'godot-addon/publication_owner.py')
    validation = module._load('validation_owner'); factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=validation.executor.BINARY_SHA256)
    work = output / 'owned'; work.mkdir()
    owner = server = reopened = None
    checks = []
    result = {'passed': False, 'checks': checks, 'source_closure_sha256': closure,
              'candidate_only': True, 'gt03_acceptance': False, 'queue_durable_across_restart': False}

    def check(label, value):
        checks.append({'label': label, 'passed': value is True})
        save(output / 'progress.json', checks)
        if value is not True:
            raise AssertionError(label)

    try:
        owner = module.GodotPublicationOwner.create(work, project_id='project.fixture', initial_bundle=initial,
            editor_binary=binary, source_closure_sha256=closure)
        server = module._load('publication_transport').PublicationTransport(owner).start()
        # Credential lifetime covers both independent 30-second lease-expiry
        # cases and durable cleanup. Work leases retain their normal 30s bound.
        credentials = {name: owner.sessions.issue(ttl_ms=240_000) for name in ('a', 'b')}
        check('two_distinct_registered_credentials', credentials['a'].session_id != credentials['b'].session_id)
        save(output / 'authority-sessions.json', {name: value.session_id for name, value in credentials.items()})
        catalog = owner.contract.CATALOG_DIGEST

        def call(who, route, body, *, control=False):
            connection = http.client.HTTPConnection('127.0.0.1', server.control_port if control else server.port, timeout=95)
            try:
                connection.request('POST', route, canonical_bytes(body), {'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + credentials[who].bearer, 'X-HH-Catalog': catalog})
                response = connection.getresponse(); wire = response.read()
                return response.status, parse_json(wire), wire
            finally:
                connection.close()

        def queue(who, request_id):
            body = {'project_id': owner.project_id, 'request_id': request_id, 'ttl_ms': 30_000, 'wait_ms': 90_000}
            status, ticket, wire = call(who, '/v1/lease/enqueue', body)
            save(output / (request_id + '-enqueue.json'), {'http_status': status, 'request': body, 'ticket': ticket})
            check(request_id + '_enqueue_accepted', status == 200 and ticket.get('state') in ('QUEUED', 'GRANTED'))
            return body, ticket, wire

        def poll(who, ticket):
            return call(who, '/v1/lease/poll', {'project_id': owner.project_id, 'ticket_id': ticket['ticket_id']})

        def wait_expiry(label, lease):
            # Real wall-clock expiry; no fixture clock or authority revocation.
            started_ms = epoch_ms(); started = time.monotonic()
            deadline = started + 35
            while epoch_ms() <= lease['expires_ms']:
                if time.monotonic() >= deadline:
                    raise AssertionError('bounded real lease expiry wait: ' + label)
                time.sleep(min(0.1, max(0.001, (lease['expires_ms'] - epoch_ms()) / 1000)))
            ended_ms = epoch_ms()
            save(output / (label + '-actual-expiry.json'), {'wait_started_ms': started_ms,
                'lease_expires_ms': lease['expires_ms'], 'observed_expired_ms': ended_ms,
                'monotonic_wait_seconds': time.monotonic() - started, 'fake_clock': False,
                'credential_rotation': False, 'forced_revocation': False})
            check(label + '_lease_really_expired', ended_ms > lease['expires_ms'])

        status, discovery, _ = call('a', '/v1/discovery', {'project_id': owner.project_id})
        save(output / 'discovery.json', discovery)
        check('authenticated_discovery', status == 200)
        before = owner.inspect(); editor = owner._editor; identity = editor.identity
        selected = owner._journal.selection_facts()
        save(output / 'before.json', before); save(output / 'editor-identity.json', identity)
        save(output / 'selection-before.json', selected)
        status, lease_a, wire = call('a', '/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
        save(output / 'legacy-lease-a.json', {'http_status': status, 'lease': lease_a})
        check('legacy_route_issues_real_registered_lease', status == 200 and lease_a['fencing_epoch'] > 0)

        def request(command, stable_id, position, lease):
            observed = owner.inspect()
            payload = {'expected_generation': observed['generation'], 'expected_project_revision': observed['project_revision'],
                'stable_id': stable_id, 'node_type': 'MeshInstance3D', 'name': 'BoxA' if stable_id == 'box.a' else 'BoxB',
                'position': position, 'rotation_degrees': [0, 0, 0], 'scale': [1, 1, 1], 'box_size': [1, 2, 3]}
            return Request(command_id=command, project_id=owner.project_id, operation='scene.node.create',
                lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'], expected_revision=observed['revision'],
                target={'stable_id': 'root'}, payload=payload,
                payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
                deadline_ms=min(lease['expires_ms'], epoch_ms() + 29_000))

        edits = []
        def edit(who, command, stable_id, position, lease):
            proposed = request(command, stable_id, position, lease)
            status, response, wire = call(who, '/v1/commands', proposed.as_dict())
            save(output / (command + '-request.json'), proposed.as_dict())
            save(output / (command + '-response.json'), response)
            (output / (command + '-wire.json')).write_bytes(wire)
            if response.get('status') != 'COMMITTED' and hasattr(owner, '_last_error'):
                traceback.print_exception(owner._last_error)
            post = response.get('postconditions', {})
            check(command + '_actual_authenticated_edit', status == 200 and response.get('code') == 'GODOT_EDITOR_EDITED'
                  and response.get('status') == 'COMMITTED' and post.get('public_ack') is True)
            check(command + '_truthful_editor_session_scope', post.get('effect_scope') == 'editor_session'
                  and post.get('files_saved') is False and post.get('live_state_durable') is False
                  and post.get('journal_receipt_durable') is True)
            observed = owner.inspect(); save(output / (command + '-after.json'), observed)
            check(command + '_native_node_observed', any(node['stable_id'] == stable_id and node['position'] == position
                  for node in observed['state']['nodes']))
            check(command + '_exact_durable_reply', owner._journal.lookup_response(command, proposed.digest) == canonical_bytes(response))
            edits.append((who, proposed, response, wire))
            return observed

        first = edit('a', 'fifo.edit.a', 'box.a', [1, 2, 3], lease_a)
        body_b, ticket_b, _ = queue('b', 'fifo.wait.b')
        _, ticket_a, _ = queue('a', 'fifo.wait.a')
        check('two_waiters_stay_queued_behind_active_writer', ticket_b['state'] == ticket_a['state'] == 'QUEUED')
        events = tuple(owner._journal._state.events)
        status, denied_legacy, _ = call('a', '/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
        save(output / 'legacy-bypass-denied.json', {'http_status': status, 'response': denied_legacy})
        check('legacy_lease_cannot_duplicate_own_waiter', status == 400
              and denied_legacy.get('code') == 'GODOT_FIFO_WAITER_ALREADY_OWNED'
              and tuple(owner._journal._state.events) == events)
        status, waiting_a, _ = poll('a', ticket_a)
        check('later_waiter_poll_cannot_jump_active_writer', status == 200 and waiting_a['state'] == 'QUEUED')
        wait_expiry('first', lease_a)
        status, waiting_a, _ = poll('a', ticket_a)
        check('later_poll_grants_head_without_jumping_it', status == 200 and waiting_a['state'] == 'QUEUED')
        # The head's first poll response is deliberately left unread by the client.
        # Its lease was already minted by the previous (later waiter's) poll.
        connection = http.client.HTTPConnection('127.0.0.1', server.port, timeout=5)
        try:
            connection.request('POST', '/v1/lease/poll', canonical_bytes({'project_id': owner.project_id,
                'ticket_id': ticket_b['ticket_id']}), {'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + credentials['b'].bearer, 'X-HH-Catalog': catalog})
            time.sleep(0.1)
        finally:
            connection.close()  # No getresponse/read: client received no parsed receipt.
        status, granted_b, granted_wire = poll('b', ticket_b)
        save(output / 'granted-b.json', granted_b); (output / 'granted-b-wire.json').write_bytes(granted_wire)
        lease_b = granted_b.get('lease', {})
        check('head_gets_fresh_registered_fence_after_expiry', status == 200 and granted_b['state'] == 'GRANTED'
              and lease_b['fencing_epoch'] > lease_a['fencing_epoch'] and lease_b['lease_id'] != lease_a['lease_id'])
        status, duplicate, duplicate_wire = call('b', '/v1/lease/enqueue', body_b)
        check('ticket_retry_after_unread_response_is_exact', status == 200 and duplicate == granted_b and duplicate_wire == granted_wire)
        save(output / 'reply-loss.json', {'route': '/v1/lease/poll', 'ticket_id': ticket_b['ticket_id'],
            'client_read_headers': False, 'client_read_body': False,
            'retry_wire_sha256': hashlib.sha256(granted_wire).hexdigest(), 'queue_persistent': False})
        proposed = request('fifo.stale.fence', 'box.stale', [9, 9, 9], lease_b).as_dict()
        proposed['fencing_epoch'] = lease_a['fencing_epoch']  # Only the fence is stale.
        before_reject = owner.inspect(); head = owner._journal._head; intents = len(editor._intents)
        status, rejected, _ = call('b', '/v1/commands', proposed)
        save(output / 'stale-fence.json', {'http_status': status, 'request': proposed, 'response': rejected})
        check('stale_fence_rejected_before_native_edit_or_intent', status == 400 and owner._journal._head == head
              and len(editor._intents) == intents and owner.inspect() == before_reject)
        after = edit('b', 'fifo.edit.b', 'box.b', [4, 5, 6], lease_b)
        check('both_writer_edits_survive_in_same_owned_editor', owner._editor is editor and editor.identity == identity
              and after['generation'] == before['generation'] and after['root_instance_id'] == before['root_instance_id']
              and after['history_id'] == before['history_id'] and all(any(node['stable_id'] == stable_id
                  and node['position'] == position for node in after['state']['nodes'])
                  for stable_id, position in (('box.a', [1, 2, 3]), ('box.b', [4, 5, 6]))))
        check('edits_did_not_publish_project_or_script_bytes', after['working_files'] == before['working_files']
              and owner._journal.selection_facts() == selected and after['project_revision'] == before['project_revision'])
        cancel_body = {'project_id': owner.project_id, 'ticket_id': ticket_a['ticket_id']}
        status, canceled, cancel_wire = call('a', '/v1/lease/cancel', cancel_body)
        save(output / 'canceled-a.json', canceled)
        check('queued_incumbent_cancellation_does_not_revoke_head', status == 200 and canceled['state'] == 'CANCELED'
              and canceled['lease'] is None and owner.sessions._lease.lease_id == lease_b['lease_id'])
        status, repeated, repeated_wire = call('a', '/v1/lease/cancel', cancel_body)
        check('cancel_terminal_is_exact', status == 200 and repeated_wire == cancel_wire)

        # A fresh legacy request must not jump an older waiter even once the
        # incumbent's real lease has expired. This case is independent of the
        # duplicate-waiter rejection above; both clients still use HTTP only.
        _, legacy_head, _ = queue('a', 'fifo.wait.legacy.head')
        check('legacy_case_has_one_older_waiter', legacy_head['state'] == 'QUEUED')
        wait_expiry('second', lease_b)
        events = tuple(owner._journal._state.events)
        status, legacy_result, _ = call('b', '/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
        save(output / 'legacy-after-expiry.json', {'http_status': status, 'response': legacy_result})
        check('fresh_legacy_request_cannot_bypass_older_waiter_after_real_expiry', status == 400
              and legacy_result.get('code') == 'GODOT_LEASE_BUSY'
              and tuple(owner._journal._state.events) == events and owner.inspect()['state'] == after['state'])
        status, legacy_granted, _ = poll('a', legacy_head)
        save(output / 'legacy-head-granted.json', legacy_granted)
        check('legacy_route_grants_only_older_head_then_cancels_own_waiter', status == 200
              and legacy_granted['state'] == 'GRANTED'
              and legacy_granted['lease']['fencing_epoch'] == lease_b['fencing_epoch'] + 1
              and legacy_granted['lease']['session_id'] == credentials['a'].session_id
              and owner._writer_fifo().snapshot()['queued'] == 0)
        status, historical_b, historical_b_wire = poll('b', ticket_b)
        check('expired_ticket_retry_is_exact_without_reviving_stale_writer', status == 200
              and historical_b_wire == granted_wire
              and owner.sessions._lease.lease_id == legacy_granted['lease']['lease_id'])
        _, stopped_ticket, _ = queue('b', 'fifo.wait.stop')
        check('stop_case_has_pending_writer', stopped_ticket['state'] == 'QUEUED')
        started = time.monotonic()
        status, stop_result, _ = call('b', '/v1/stop', {'project_id': owner.project_id, 'command_id': 'fifo.stop'}, control=True)
        stop_ms = (time.monotonic() - started) * 1000
        save(output / 'stop.json', {'http_status': status, 'response': stop_result, 'elapsed_ms': stop_ms})
        check('stop_control_latches_without_queue_wait', status == 200 and stop_result.get('stopped') is True and stop_ms < 500)
        status, stopped, _ = poll('b', stopped_ticket)
        save(output / 'stopped-ticket.json', stopped)
        check('stop_cancels_pending_writer_ticket', status == 200 and stopped['state'] == 'STOPPED' and stopped['lease'] is None)
        status, stopped_lease, _ = call('b', '/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 30_000})
        check('stopped_owner_cannot_grant_new_writer', status == 400)
        stop_deadline = time.monotonic() + 20
        while owner._stop_persistence == 'PENDING' and time.monotonic() < stop_deadline:
            time.sleep(0.05)
        check('idle_stop_is_durable_after_owned_drain', owner._stop_persistence == 'DURABLE' and owner._journal.snapshot()['stopped'])
        for who, command, response, wire in edits:
            status, looked, _ = call(who, '/v1/lookup', {'project_id': owner.project_id,
                'command_id': command.command_id}, control=True)
            check(command.command_id + '_lookup_after_stop_exact', status == 200 and canonical_bytes(looked) == canonical_bytes(response))
        check('stop_preserves_both_actual_edits', owner.inspect()['state'] == after['state'])
        save(output / 'after.json', owner.inspect()); save(output / 'journal.json', owner._journal.snapshot())
        save(output / 'events.json', [parse_json(value) for value in owner._journal._state.events])
        validator_snapshot = owner._validator.snapshot()
        save(output / 'validator.json', validator_snapshot)
        check('one_actual_bootstrap_validator_only', tuple(validator_snapshot['attempts']) == ('bootstrap.validation',))
        save(output / 'transport-diagnostics.json', list(server.diagnostics))
        storage_id = owner.storage_id
        owner.sessions.halt(); server.close(); server = None; owner.close()
        save(output / 'editor-close.json', editor._cleanup)
        module._load('editor_owner').EditorOwner._clean_closed(editor._cleanup, identity['pid'])
        reopened = module._load('publication_journal_v5').PublicationJournalV5.reopen(storage_id, project_id='project.fixture')
        check('readonly_reopen_keeps_stop_and_original_selection', reopened.snapshot()['stopped'] is True
              and reopened.snapshot()['source_closure_sha256'] == closure and reopened.selection_facts() == selected)
        for _, command, response, _ in edits:
            check(command.command_id + '_historical_durable_reply_reopens', reopened.lookup_response(command.command_id,
                  command.digest) == canonical_bytes(response))
        result.update(passed=True, actual_authenticated_two_writer_fifo=True, actual_clock_expiry=True,
            editor_edits_observed=2, files_saved=False, live_state_durable=False, bootstrap_validators=1)
    except BaseException as error:
        result['failure'] = type(error).__name__ + ': ' + str(error)
        traceback.print_exception(error)
    finally:
        failures = []
        if owner is not None:
            owner.sessions.halt()
        for resource in (server, owner, reopened):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    failures.append(type(error).__name__ + ': ' + str(error))
        if failures:
            result['passed'] = False; result['cleanup_failures'] = failures
        save(output / 'fifo-publication.json', result)
    print('HH_FIFO_PUBLICATION_COMPLETE ' + json.dumps({'passed': result['passed'], 'checks': len(checks)}), flush=True)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--output', type=Path); parser.add_argument('--run-id')
    parser.add_argument('--frozen', action='store_true'); parser.add_argument('--binary', type=Path)
    parser.add_argument('--closure'); parser.add_argument('--describe', action='store_true')
    args = parser.parse_args()
    if args.describe:
        print(json.dumps({'cases': ['two_credentials', 'legacy_no_bypass', 'real_30s_expiry', 'FIFO_reverse_poll',
            'unread_reply_exact_ticket_retry', 'stale_fence_no_effect', 'two_native_edits', 'cancel', 'Stop',
            'durable_historical_replies'], 'engines_started': 0, 'requires_coordinator_native_slot': True}))
        return 0
    if args.output is None or not args.run_id or not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id):
        parser.error('output and valid run ID required')
    if args.frozen:
        if args.binary is None or not args.closure:
            parser.error('binary and closure required for frozen run')
        return frozen(args.output, args.binary, args.closure)
    output = args.output.resolve(); output.relative_to(STUDIO.parent / 'zdoc/reviews')
    output.mkdir(parents=True, exist_ok=False)
    inventory = load('fifo_publication_inventory', STUDIO / 'tests/godot/run_editor_probe.py')
    before = inventory.inputs(); source = output / 'source/studio'
    for name, digest in before.items():
        target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
        if sha(target) != digest:
            raise ValueError('source changed during freeze')
    runner = load('fifo_publication_runner', source / 'build/bootstrap/run_fixture.py')
    closure = runner.source_closure_sha256(before)
    save(output / 'source-closure.json', {'files': before, 'source_closure_sha256': closure})
    lock = json.loads((source / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary) != lock['gui_sha256']:
        raise ValueError('GUI pin mismatch')
    environment = dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host = runner.run_process([sys.executable, '-B', str(source / 'tests/godot/run_fifo_publication_probe.py'),
        '--frozen', '--output', str(output), '--run-id', args.run_id, '--binary', str(binary), '--closure', closure],
        cwd=source, output=output, timeout=210, label='fifo-publication', env=environment)
    unchanged = before == inventory.inputs()
    snapshot_unchanged = all(sha(source / name) == digest for name, digest in before.items())
    report_path = output / 'fifo-publication.json'
    report = json.loads(report_path.read_bytes()) if report_path.exists() else {}
    logs = [path for path in output.rglob('*.txt') if path.name in ('stdout.txt', 'stderr.txt')]
    logs_clean = all(not re.search(rb'(?i)\b(error|warning|leaked)\b', path.read_bytes()) for path in logs)
    passed = (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified'] and not host['timed_out']
              and snapshot_unchanged and report.get('passed') is True and logs_clean)
    save(output / 'capture.json', {'run_id': args.run_id, 'host': host, 'passed': passed,
        'source_closure_sha256': closure, 'origin_source_unchanged': unchanged, 'snapshot_unchanged': snapshot_unchanged,
        'native_logs_clean': logs_clean, 'candidate_only': True, 'gt03_acceptance': False})
    print(json.dumps({'passed': passed, 'host': host, 'origin_source_unchanged': unchanged}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
