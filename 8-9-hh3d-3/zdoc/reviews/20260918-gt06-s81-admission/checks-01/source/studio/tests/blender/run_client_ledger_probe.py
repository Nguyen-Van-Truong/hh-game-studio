"""Owned native Blender and real Journal proof for the unadvertised ledger.

Run only in the coordinator's native integration slot. This probe records a
read observation; it does not expose public writes or issue a public ACK.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from run_blender_ipc_probe import load, sources

UNIT_INVENTORY = 'GT04_LEDGER_UNIT_INVENTORY '
UNIT_COMPLETE = 'GT04_LEDGER_UNIT_COMPLETE '
NATIVE_COMPLETE = 'GT04_LEDGER_NATIVE_COMPLETE '


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def host_passed(host):
    if not isinstance(host, dict):
        return False
    return all(type(host.get(key)) is int and host[key] == 0
               for key in ('exit_code', 'wrapper_exit_code')) \
        and all(type(host.get(key)) is int and host[key] > 0
                for key in ('target_pid', 'wrapper_pid')) \
        and host['target_pid'] != host['wrapper_pid'] \
        and host.get('timed_out') is False and host.get('tree_verified') is True


def host_artifact_passed(output, host):
    if not host_passed(host):
        return False
    name = host.get('host')
    if type(name) is not str or not name or Path(name).name != name:
        return False
    try:
        raw = json.loads((output / name).read_bytes())
    except (OSError, ValueError):
        return False
    return type(raw) is dict and type(raw.get('target_pid')) is int \
        and type(raw.get('exit_code')) is int and raw['target_pid'] == host['target_pid'] \
        and raw['exit_code'] == host['exit_code']


def unit_completion(stdout):
    """A PASS banner alone cannot replace a unique, complete test inventory."""
    try:
        inventories = [json.loads(line[len(UNIT_INVENTORY):]) for line in stdout.splitlines()
                       if line.startswith(UNIT_INVENTORY)]
        completions = [json.loads(line[len(UNIT_COMPLETE):]) for line in stdout.splitlines()
                       if line.startswith(UNIT_COMPLETE)]
        if len(inventories) != 1 or len(completions) != 1:
            return False, completions
        ids = inventories[0]
        counts = completions[0]
        valid = isinstance(ids, list) and bool(ids) and all(type(item) is str for item in ids)
        valid = valid and len(set(ids)) == len(ids)
        valid = valid and type(counts) is dict and all(type(counts.get(key)) is int
            for key in ('run', 'failures', 'errors', 'skips'))
        valid = valid and counts == {
            'run': len(ids), 'failures': 0, 'errors': 0, 'skips': 0}
        return bool(valid), completions
    except (ValueError, TypeError):
        return False, []


def cleanup_passed(cleanup, native_pid):
    if not isinstance(cleanup, dict) or type(native_pid) is not int or native_pid <= 0:
        return False
    job = cleanup.get('job')
    actual = cleanup.get('actual_process_exit')
    return type(actual) is dict and type(actual.get('exit_code')) is int \
        and type(actual.get('pid')) is int and cleanup.get('closed') is True and actual == {
        'pid': native_pid, 'exit_code': 0} and cleanup.get('wrapper_exit_code') == 0 \
        and type(cleanup.get('wrapper_exit_code')) is int \
        and cleanup.get('logs_overflow') is False and isinstance(job, dict) \
        and job.get('zero_observed') is True and type(job.get('active_count')) is int \
        and job.get('active_count') == 0 \
        and job.get('closed') is True and job.get('handle_retained') is False


def stop_until_terminal(call, *, timeout=6.0, clock=time.monotonic, pause=time.sleep):
    """Poll the same Stop identity while its existing native call drains."""
    started = clock()
    deadline = started + timeout
    pending = 0
    while True:
        if pending and clock() >= deadline:
            raise TimeoutError('BLENDER_LEDGER_PROBE_STOP_PENDING')
        result = call()
        if result.status.value != 'ACCEPTED_PENDING':
            return result, pending, (clock() - started) * 1000
        pending += 1
        remaining = deadline - clock()
        if remaining <= 0:
            raise TimeoutError('BLENDER_LEDGER_PROBE_STOP_PENDING')
        pause(min(0.02, remaining))


def write_json(output, name, value):
    from studio.protocol.core import canonical_bytes
    raw = canonical_bytes(value)
    with (output / name).open('xb') as stream:
        stream.write(raw)


def safe_failure(error):
    code = getattr(error, 'code', None)
    if type(code) is not str or not re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
        code = None
    return {'type': type(error).__name__, 'code': code}


def decode_disk_snapshot(raw, journal, binding):
    from studio.host.blender.client_ledger import validate_history
    records = [journal._decode_record(line) for line in raw.splitlines(keepends=True)]
    return records, validate_history(records, binding)


def frozen(output, binary):
    from studio.host.blender.client_owner import BlenderClientOwner
    from studio.host.blender import client_catalog as catalog
    from studio.host.blender import client_ledger as ledger_api
    from studio.host.blender.ui_host import BlenderUIHost, HostError
    from studio.host.core.transport import epoch_ms
    from studio.protocol.core import Request, Response, Status, canonical_bytes, parse_json

    gui = None
    owner = None
    read_permit = None
    rows = []
    artifacts = {}
    failure = None
    cleanup = None
    cleanup_errors = []

    def check(label, condition):
        row = {'label': label, 'passed': condition is True}
        rows.append(row)
        print('GT04_LEDGER_CHECK ' + json.dumps(row), flush=True)
        if condition is not True:
            raise AssertionError(label)

    def snapshot(ledger, name):
        path = ledger._journal.path
        raw = path.read_bytes()
        check(name + '_complete_disk_envelopes', bool(raw) and raw.endswith(b'\n'))
        records, state = decode_disk_snapshot(raw, ledger._journal, ledger.binding)
        with (output / (name + '.jsonl')).open('xb') as stream:
            stream.write(raw)
        artifacts[name] = {'sha256': sha(raw), 'bytes': len(raw), 'records': len(records)}
        return records, state

    try:
        try:
            gui = BlenderUIHost(output, binary=binary, session_seconds=90)
        except BaseException as error:
            retained = getattr(error, 'cleanup_owner', None)
            if type(retained) is BlenderUIHost:
                gui = retained
            raise
        owner = BlenderClientOwner.from_host(gui)
        ledger = ledger_api.BlenderClientLedger.from_owner(owner)
        credential = owner.sessions.issue()
        foreign = owner.sessions.issue()
        authorization = 'Bearer ' + credential.bearer
        grant = owner.sessions.authenticate(authorization)
        foreign_grant = owner.sessions.authenticate('Bearer ' + foreign.bearer)
        lease = owner.lease({'project_id': owner.project_id, 'ttl_ms': 30000, 'access': 'read'},
            authorization=authorization, catalog_digest=owner.catalog_digest)
        check('real_journal_at_exact_owned_fixed_path',
            type(ledger._journal) is ledger_api._ClientJournal
            and ledger._journal.path == gui.directory / 'client-ledger' / ledger_api.FILENAME)
        check('binding_matches_exact_live_registered_owner',
            ledger.binding.project_id == owner.project_id
            and ledger.binding.generation == gui._session
            and ledger.binding.source_sha256 == owner._source_sha256
            and ledger.binding.catalog_digest == owner.catalog_digest
            and ledger.binding.owner_pin_sha256 == sha(owner._pin))

        def request(key):
            return Request(command_id=key, project_id=owner.project_id, operation=catalog.READ,
                lease_id=lease['lease_id'], fencing_epoch=0, expected_revision=lease['revision'],
                target=lease['target'], payload={}, payload_hash=sha(canonical_bytes({})),
                deadline_ms=min(lease['expires_ms'], epoch_ms() + catalog.MAX_READ_MS))

        def private(value):
            return {'schema': ledger_api.queue.SCHEMA,
                'command_id': ledger_api.private_alias(ledger.binding, grant.session_id, value.command_id),
                'operation': catalog.READ, 'expected_revision': None, 'expected_context': None, 'payload': {}}

        value = request('Client.Command.' + 'x' * 113)
        native_command = private(value)
        before = gui.channels['data'].sent
        admitted = ledger.begin(grant, value, native_command)
        check('fresh_marker_only_after_persisted_admission', admitted.permit is not None
            and admitted.response is None and admitted.replayed is False)
        check('long_public_id_has_distinct_valid_private_alias', len(value.command_id) == 128
            and len(admitted.private_id) == 47
            and re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', admitted.private_id) is not None
            and admitted.private_id != value.command_id
            and admitted.native_command == ledger_api.queue.c.canonical(native_command))
        records, state = snapshot(ledger, 'intent-before-native')
        persisted = state[admitted.private_id]['intent']
        check('exact_original_request_and_private_bytes_on_disk', len(records) == 2
            and records[-1]['status'] == 'ACCEPTED_PENDING'
            and persisted['session_id'] == grant.session_id
            and persisted['command_id'] == value.command_id
            and persisted['request_digest'] == value.digest
            and ledger_api.unchunk(persisted['request_chunks'], ledger_api.MAX_REQUEST_BYTES)
                == canonical_bytes(value.as_dict())
            and ledger_api.unchunk(persisted['native_chunks'], ledger_api.queue.c.MAX_BYTES)
                == admitted.native_command)
        reopened = ledger_api.BlenderClientLedger.from_owner(owner)
        unresolved = reopened.begin(grant, value, native_command)
        unknown = Response.from_dict(parse_json(unresolved.response))
        check('independent_real_journal_reload_sees_unknown_without_marker',
            reopened._journal is not ledger._journal and unresolved.replayed is True
            and unresolved.permit is None and unknown.status is Status.UNKNOWN
            and unknown.code == 'BLENDER_LEDGER_UNRESOLVED_INTENT'
            and unknown.postconditions['dispatch_permitted'] is False)
        check('intent_persistence_and_reopen_do_not_submit_native', gui.channels['data'].sent == before)

        # The internal owner supplies its existing bounded read checks. The
        # ledger marker alone is deliberately never treated as effect authority.
        registered_lease = owner.sessions.resolve_lease(grant, value.lease_id, value.fencing_epoch)
        read_permit = owner.sessions.start_read(grant, registered_lease, deadline_ms=value.deadline_ms)
        observed = owner._read_native(admitted.private_id, value.deadline_ms)
        owner.sessions.check_read(grant, registered_lease, deadline_ms=value.deadline_ms)
        owner.sessions.finish_read(read_permit)
        read_permit = None
        native_row = gui.result(admitted.private_id)
        check('actual_aliased_native_read_matches_registered_scene',
            gui.channels['data'].sent == before + 1 and native_row['state'] == 'COMPLETED'
            and native_row['command_id'] == admitted.private_id
            and native_row['command_digest'] == ledger_api.queue.c.digest(native_command)
            and canonical_bytes(native_row['result']) == canonical_bytes(observed) == owner._baseline
            and observed['revision'] == value.expected_revision)
        observation = {'scene': observed, 'pid': gui.pid, 'generation': gui._session,
            'source_sha256': owner._source_sha256}
        terminal = Response(Status.COMMITTED, 'BLENDER_LEDGER_NATIVE_READ_OBSERVED', value.command_id,
            observed['revision'], sha(canonical_bytes(observation)),
            {'observation': observation, 'hash_domain': 'jcs-observation-v1', 'public_ack': False,
             'ledger_receipt_only': True, 'live_state_durable': False, 'read_only': True})
        expected_wire = canonical_bytes(terminal.as_dict())
        terminal_wire = ledger.finish(admitted.permit, terminal)
        check('terminal_is_exact_common_response_with_native_observation', terminal_wire == expected_wire
            and canonical_bytes(Response.from_dict(parse_json(terminal_wire)).as_dict()) == expected_wire)
        records, state = snapshot(ledger, 'terminal-readback')
        check('terminal_disk_bytes_exact_after_real_flush_reload', len(records) == 3
            and records[-1]['status'] == 'COMMITTED'
            and state[admitted.private_id]['response'] == expected_wire)
        complete = ledger_api.BlenderClientLedger.from_owner(owner)
        retried = complete.begin(grant, value, native_command)
        changed_authority = replace(value, lease_id='read.historical-only', fencing_epoch=999, deadline_ms=1)
        old_authority = complete.begin(grant, changed_authority, native_command)
        check('reopened_terminal_retry_and_lookup_are_byte_exact',
            retried.replayed is True and retried.permit is None and retried.response == expected_wire
            and old_authority.replayed is True and old_authority.permit is None
            and old_authority.response == expected_wire
            and complete.lookup(grant, value.command_id) == expected_wire)
        try:
            complete.begin(grant, replace(value, expected_revision='sha256:' + '0' * 64), native_command)
        except ledger_api.LedgerError as error:
            conflict = error.code
        else:
            conflict = None
        check('same_identity_changed_request_conflicts', conflict == 'BLENDER_LEDGER_COMMAND_CONFLICT')
        try:
            complete.lookup(foreign_grant, value.command_id)
        except ledger_api.LedgerError as error:
            foreign_code = error.code
        else:
            foreign_code = None
        check('foreign_authenticated_session_cannot_read_terminal',
            foreign_code == 'BLENDER_LEDGER_COMMAND_NOT_FOUND')
        check('terminal_retries_and_denials_never_redispatch', gui.channels['data'].sent == before + 1)

        abandoned = request('Client.Unresolved')
        abandoned_native = private(abandoned)
        second = complete.begin(grant, abandoned, abandoned_native)
        check('second_intent_has_original_in_process_marker', second.permit is not None
            and second.response is None and second.replayed is False)
        restart = ledger_api.BlenderClientLedger.from_owner(owner)
        retry = restart.begin(grant, abandoned, abandoned_native)
        unknown_wire = restart.lookup(grant, abandoned.command_id)
        unknown = Response.from_dict(parse_json(unknown_wire))
        check('unresolved_reopen_is_exact_unknown_and_never_new_admission', retry.replayed is True
            and retry.permit is None and retry.response == unknown_wire and unknown.status is Status.UNKNOWN
            and unknown.postconditions['dispatch_permitted'] is False)
        try:
            gui.result(second.private_id)
        except HostError as error:
            missing_native = str(error) == 'BLENDER_COMMAND_REJECTED'
        else:
            missing_native = False
        check('unresolved_alias_never_entered_native_queue',
            missing_native and gui.channels['data'].sent == before + 1)
        records, state = snapshot(restart, 'unresolved-readback')
        check('complete_disk_chain_preserves_terminal_and_unfinished_intent', len(records) == 4
            and state[admitted.private_id]['response'] == expected_wire
            and state[second.private_id]['response'] is None)

        stop_body = {'project_id': owner.project_id, 'command_id': 'Client.Ledger.Stop'}
        stopped, pending, elapsed = stop_until_terminal(lambda: owner.stop(stop_body,
            authorization=authorization, catalog_digest=owner.catalog_digest))
        check('bounded_stop_reaches_observed_native_terminal', stopped.status is Status.COMMITTED
            and stopped.code == 'BLENDER_STOP_OBSERVED' and stopped.postconditions['public_ack'] is False)
        check('historical_terminal_and_unknown_survive_stop_without_dispatch',
            restart.lookup(grant, value.command_id) == expected_wire
            and restart.lookup(grant, abandoned.command_id) == unknown_wire
            and restart.begin(grant, abandoned, abandoned_native).permit is None
            and gui.channels['data'].sent == before + 1)
        artifacts.update(request=value.as_dict(), private_command=native_command, native_result=native_row,
            terminal_wire=terminal_wire.decode('utf-8'), unresolved_wire=unknown_wire.decode('utf-8'),
            stop=stopped.as_dict(), stop_pending_responses=pending, stop_elapsed_ms=elapsed,
            native_submissions_before=before, native_submissions_after=gui.channels['data'].sent,
            ledger_binding=ledger_api.binding_value(ledger.binding))
        encoded = canonical_bytes(artifacts)
        journal_raw = restart._journal.path.read_bytes()
        check('bearers_absent_from_evidence_and_journal', all(secret.encode('utf-8') not in encoded + journal_raw
            for secret in (credential.bearer, foreign.bearer)))
    except BaseException as error:
        failure = safe_failure(error)
    finally:
        if read_permit is not None and owner is not None:
            try:
                owner.sessions.finish_read(read_permit)
            except Exception as error:
                cleanup_errors.append(safe_failure(error))
        if gui is not None:
            # Keep the exact owner on a close failure, retry boundedly, and
            # capture retained-handle state rather than assuming termination.
            for attempt in range(2):
                try:
                    if not gui._stopped:
                        gui.stop()
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
                try:
                    cleanup = gui.close()
                    break
                except Exception as error:
                    cleanup_errors.append(safe_failure(error))
            native_pid = getattr(gui, 'pid', None)
            rows.append({'label': 'actual_gui_wrapper_exit_zero_and_owned_job_empty',
                         'passed': cleanup_passed(cleanup, native_pid)})
        else:
            native_pid = None
    directory = getattr(gui, 'directory', None)
    result = {'passed': failure is None and bool(rows) and all(row['passed'] is True for row in rows)
              and cleanup_passed(cleanup, native_pid), 'checks': rows, 'failure': failure,
        'cleanup_errors': cleanup_errors, 'cleanup': cleanup, 'probe_pid': os.getpid(),
        'native_pid': native_pid, 'gui_directory': directory.name if isinstance(directory, Path) else None,
        'artifacts': artifacts, 'public_ack': False, 'public_write_facade': False,
        'live_state_durable': False, 'formal_acceptance': False}
    write_json(output, 'ledger-native.json', result)
    print(NATIVE_COMPLETE + json.dumps({'passed': result['passed'], 'checks': len(rows)}), flush=True)
    return int(not result['passed'])


def evidence_inventory(output):
    result = {}
    for path in sorted(output.rglob('*')):
        relative = path.relative_to(output)
        if not path.is_file() or relative.parts[0] == 'source':
            continue
        result[relative.as_posix()] = {'bytes': path.stat().st_size, 'sha256': sha(path.read_bytes())}
    return result


def native_completion(output, host):
    if not host_artifact_passed(output, host) or not (output / 'ledger-native.json').is_file():
        return False
    report = json.loads((output / 'ledger-native.json').read_bytes())
    lines = (output / 'native-stdout.txt').read_text(encoding='utf-8').splitlines()
    markers = [json.loads(line[len(NATIVE_COMPLETE):]) for line in lines if line.startswith(NATIVE_COMPLETE)]
    rows = report.get('checks', [])
    if not rows or len({row['label'] for row in rows}) != len(rows):
        return False
    directory = report.get('gui_directory')
    if type(directory) is not str or Path(directory).name != directory:
        return False
    raw_exit = json.loads((output / directory / 'process-exit.json').read_bytes())
    raw_close = json.loads((output / directory / 'close.json').read_bytes())
    return report.get('passed') is True and report.get('probe_pid') == host.get('target_pid') \
        and report.get('public_ack') is False and report.get('public_write_facade') is False \
        and all(row['passed'] is True for row in rows) \
        and cleanup_passed(report.get('cleanup'), report.get('native_pid')) \
        and type(raw_exit.get('exit_code')) is int \
        and cleanup_passed(raw_close, report.get('native_pid')) \
        and raw_exit == report['cleanup']['actual_process_exit'] and raw_close == report['cleanup'] \
        and len(markers) == 1 and type(markers[0].get('checks')) is int \
        and markers == [{'passed': True, 'checks': len(rows)}]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frozen', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args()
    runner = load(STUDIO / 'build/bootstrap/run_fixture.py')
    runner._reject_reparse_ancestors(args.output)
    output = args.output.resolve()
    if args.frozen:
        manifest = json.loads((output / 'source-closure.json').read_bytes())
        if STUDIO != output / 'source/studio' or sources(STUDIO) != manifest['files'] \
                or runner.source_closure_sha256(manifest['files']) != manifest['source_closure_sha256']:
            raise ValueError('ledger probe requires its exact frozen source')
        return frozen(output, args.binary)
    output.mkdir(exist_ok=False)
    original = sources(STUDIO)
    snapshot = output / 'source/studio'
    for name in original:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    if sources(snapshot) != original:
        raise ValueError('ledger snapshot mismatch')
    closure = runner.source_closure_sha256(original)
    write_json(output, 'source-closure.json', {'files': original, 'source_closure_sha256': closure})
    unit_code = """import json,sys,unittest
s=unittest.TestSuite()
for pattern in ('test_client_ledger.py','test_client_ledger_probe.py'):
 s.addTests(unittest.defaultTestLoader.discover('tests/blender',pattern=pattern))
def flatten(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t.id()
ids=list(flatten(s))
print('GT04_LEDGER_UNIT_INVENTORY '+json.dumps(ids),flush=True)
r=unittest.TextTestRunner(verbosity=2).run(s)
print('GT04_LEDGER_UNIT_COMPLETE '+json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True)
sys.exit(not r.wasSuccessful())
"""
    unit = runner.run_process([sys.executable, '-B', '-c', unit_code], cwd=snapshot,
        output=output, timeout=120, label='unit')
    unit_ok, counts = unit_completion((output / 'unit-stdout.txt').read_text(encoding='utf-8'))
    host = None
    if host_artifact_passed(output, unit) and unit_ok:
        binary = args.binary or STUDIO / '.local/tooling/blender-5.2.1-windows-x64/blender.exe'
        host = runner.run_process([sys.executable, '-B', str(snapshot / 'tests/blender/run_client_ledger_probe.py'),
            '--frozen', '--output', str(output), '--binary', str(binary.resolve())],
            cwd=snapshot, output=output, timeout=100, label='native')
    native_ok = False
    parse_failure = None
    try:
        native_ok = native_completion(output, host)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parse_failure = safe_failure(error)
    result = {'source_closure_sha256': closure, 'unit': unit, 'host': host,
        'unit_completion': unit_ok, 'unit_counts': counts, 'native_completion': native_ok,
        'native_parse_failure': parse_failure, 'source_unchanged': sources(STUDIO) == original,
        'snapshot_unchanged': sources(snapshot) == original, 'public_ack': False,
        'public_write_facade': False, 'formal_acceptance': False}
    result['passed'] = host_artifact_passed(output, unit) and unit_ok and native_ok \
        and result['source_unchanged'] and result['snapshot_unchanged']
    write_json(output, 'capture.json', result)
    write_json(output, 'evidence-inventory.json', evidence_inventory(output))
    print(json.dumps(result), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
