"""Actual HTTP Stop while a captured scene is in real Linux validation.

The sole test hook signals entry/return around the real validator method. It
never supplies a receipt or delays/replaces the engine. A separate owned Docker
inspect proves the exact validator container is running before Stop is sent.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_publication_probe import load, save, sha


def milliseconds():
    return time.time_ns() // 1_000_000


def timestamp_ms(value):
    return int(datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp() * 1000)


def frozen(output, binary, closure):
    sys.path.insert(0, str(STUDIO.parent))
    from studio.protocol.core import Request, canonical_bytes, parse_json
    module = load('publication_stop_owner', STUDIO / 'godot-addon/publication_owner.py')
    validation = module._load('validation_owner')
    executor, factory = validation.executor, validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + hashlib.sha256(factory.DEFAULT_SCENE).hexdigest(),
        engine_sha256=executor.BINARY_SHA256)
    workspace = output / 'owned'; workspace.mkdir()
    observed = output / 'stop-observer'; observed.mkdir()
    owner = server = reopened = save_thread = None
    entered, completed, response_ready = threading.Event(), threading.Event(), threading.Event()
    rows, timing, response_box = [], {}, {}

    def check(label, condition):
        rows.append({'label': label, 'passed': condition is True})
        save(output / 'progress.json', rows)
        if condition is not True: raise AssertionError(label)

    try:
        owner = module.GodotPublicationOwner.create(workspace, project_id='project.fixture',
            initial_bundle=initial, editor_binary=binary, source_closure_sha256=closure)
        credential = owner.sessions.issue()
        transport = module._load('publication_transport')
        server = transport.PublicationTransport(owner).start()

        def call(path, body, *, control=False, timeout=95):
            connection = http.client.HTTPConnection('127.0.0.1',
                server.control_port if control else server.port, timeout=timeout)
            try:
                connection.request('POST', path, canonical_bytes(body), {'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + credential.bearer,
                    'X-HH-Catalog': owner.contract.CATALOG_DIGEST})
                response = connection.getresponse()
                return response.status, parse_json(response.read())
            finally:
                connection.close()

        before = owner.inspect()
        selection_before = owner._journal.selection_facts()
        native_names_before = sorted(p.name for p in owner._journal._files.root.iterdir())
        save(output / 'selection-before.json', selection_before)
        changed = owner._editor.apply_projection({'operation': 'scene.node.update', 'command_id': 'local.dirty',
            'expected_revision': before['revision'], 'expected_generation': before['generation'],
            'target_stable_id': 'root', 'payload': {'expected_generation': before['generation'],
                                                    'changes': {'position': [5, 6, 7]}}})
        check('actual_editor_mutation', changed.get('ok') is True)
        dirty = owner.inspect(); save(output / 'dirty.json', dirty)
        check('dirty_editor_differs_from_selection', dirty['revision'] != before['revision']
              and dirty['project_revision'] == before['project_revision'])
        status, lease = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 90_000})
        check('authenticated_lease', status == 200)
        payload = {'expected_generation': dirty['generation'], 'expected_project_revision': dirty['project_revision'],
            'expected_files': {path: dirty['working_files'][path]['sha256']
                               for path in (owner.contract.SCENE_PATH, owner.contract.SCRIPT_PATH)}}
        request = Request(command_id='command.save', project_id=owner.project_id, operation='scene.save',
            lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'], expected_revision=dirty['revision'],
            target={'stable_id': 'root'}, payload=payload,
            payload_hash='sha256:' + hashlib.sha256(canonical_bytes(payload)).hexdigest(),
            deadline_ms=min(lease['expires_ms'], milliseconds() + 89_000))
        save(output / 'request.json', request.as_dict())

        original_validate = owner._validator.validate

        def observed_validate(command_id, candidate, **options):
            if command_id != request.command_id:
                return original_validate(command_id, candidate, **options)
            timing.update(validation_entered_ms=milliseconds(), candidate_project_revision=candidate.project_revision)
            entered.set()
            try:
                receipt = original_validate(command_id, candidate, **options)
                timing['registered_validation_receipt'] = asdict(receipt)
                return receipt
            finally:
                timing['validation_returned_ms'] = milliseconds()
                completed.set()

        owner._validator.validate = observed_validate

        def submit():
            try:
                status, result = call('/v1/commands', request.as_dict())
                response_box.update(status=status, result=result)
            except BaseException as error:
                response_box['error_type'] = type(error).__name__
            finally:
                response_box['received_ms'] = milliseconds()
                response_ready.set()

        save_thread = threading.Thread(target=submit, name='hh-publication-stop-save', daemon=True)
        save_thread.start()
        check('real_validator_entered_after_capture', entered.wait(timeout=35))

        # Read only the executor's existing owned record. Require our PID and
        # exact container labels, then observe its native Running state. Neither
        # this polling nor the hook delays the executor or alters its evidence.
        owner_record_path = executor._owner_path()
        inspect_runner = executor._owned_runner()
        running = None
        inspected = []
        end = time.monotonic() + 25
        attempt = 0
        while time.monotonic() < end and not completed.is_set():
            record = None
            try:
                record = executor._read_owner(owner_record_path)
            except (OSError, executor.ExecutorError):
                pass  # An atomic owner-record transition may be in progress.
            if (record is not None and type(record.get('host_pid')) is int
                    and record['host_pid'] == os.getpid() and record.get('container_id')
                    and record.get('phase') == 'start_pending'):
                attempt += 1
                row, raw = executor._cli(inspect_runner, ['inspect', record['container_id']],
                    observed, 'running-' + str(attempt), timeout=3)
                observed_ms = milliseconds()
                inspected.append({'owner': record, 'observed_ms': observed_ms, 'host': row})
                if executor._cli_clean(row):
                    native = json.loads(raw)
                    if (type(native) is list and len(native) == 1
                            and executor._owned_identity(native[0], record['name'], record['container_id'])
                            and native[0].get('State', {}).get('Running') is True
                            and type(native[0]['State'].get('Pid')) is int and native[0]['State']['Pid'] > 0):
                        running = {'record': record, 'native': native[0], 'observed_ms': observed_ms, 'host': row}
                        break
            time.sleep(.02)
        save(output / 'running-observations.json', inspected)
        check('actual_owned_linux_validator_running', running is not None and not completed.is_set())
        save(output / 'running.json', running)
        timing['stop_started_ms'] = milliseconds()
        stop_clock = time.monotonic()
        status, stopped = call('/v1/stop', {'project_id': owner.project_id, 'command_id': 'control.stop'},
                               control=True, timeout=3)
        timing['stop_elapsed_ms'] = round((time.monotonic() - stop_clock) * 1000, 3)
        timing['stop_completed_ms'] = milliseconds()
        timing['validation_returned_at_stop_response'] = completed.is_set()
        save(output / 'stop-response.json', {'http_status': status, 'response': stopped, 'timing': dict(timing)})
        check('http_stop_latches_without_waiting_validation', status == 200 and stopped.get('stopped') is True
              and stopped.get('public_ack') is False and timing['stop_elapsed_ms'] < 500
              and not timing['validation_returned_at_stop_response'])
        check('save_drained_bounded', response_ready.wait(timeout=60))
        save_thread.join(timeout=1)
        check('save_http_thread_exited', not save_thread.is_alive())
        owner._stop_thread.join(timeout=25)
        check('stop_drain_persists_after_command_accounting',not owner._stop_thread.is_alive()
              and owner._stop_persistence=='DURABLE' and owner._journal.snapshot()['stopped'] is True)
        save(output / 'save-response.json', response_box)
        result = response_box.get('result', {})
        check('interrupted_save_unknown_no_ack', response_box.get('status') == 200
              and result.get('status') == 'UNKNOWN' and result.get('postconditions', {}).get('public_ack') is False)
        check('real_validation_completed_with_registered_receipt', completed.is_set()
              and timing.get('registered_validation_receipt', {}).get('command_id') == request.command_id)
        receipt = timing['registered_validation_receipt']
        validation_record = owner._validator._records[request.command_id]
        native_result_path = validation_record.directory / 'executor/result.json'
        native_result = json.loads(native_result_path.read_bytes())
        native_state = native_result['container_state']
        check('same_validator_run_exited_cleanly', native_result['run_id'] == receipt['run_id']
              == running['record']['name'] and native_result['container_id'] == running['record']['container_id']
              and native_result['diagnostic_process_clean'] is True and native_result['owned_removed'] is True
              and native_state['Running'] is False and type(native_state['Pid']) is int and native_state['Pid'] == 0
              and type(native_state['ExitCode']) is int and native_state['ExitCode'] == 0)
        check('stop_time_inside_native_validation_interval', timestamp_ms(native_state['StartedAt'])
              <= timing['stop_started_ms'] <= timestamp_ms(native_state['FinishedAt']))
        timing.update(native_started_at=native_state['StartedAt'], native_finished_at=native_state['FinishedAt'],
            native_result_relative=native_result_path.relative_to(output).as_posix(),
            native_result_sha256=sha(native_result_path))
        save(output / 'timing.json', timing)
        selection_after = owner._journal.selection_facts()
        check('selected_native_bytes_and_identity_unchanged', canonical_bytes(selection_after)
              == canonical_bytes(selection_before))
        check('no_native_stage_objects_created', sorted(p.name for p in owner._journal._files.root.iterdir())
              == native_names_before)
        events = [parse_json(raw) for raw in owner._journal._state.events]
        save(output / 'events.json', events)
        check('durable_unknown_before_stage_select_adopt', [e['kind'] for e in events]
              == ['CONFIG', 'CAPTURE_PREPARED', 'CAPTURED', 'UNKNOWN', 'STOP'])
        after = owner.inspect(); save(output / 'after.json', after)
        check('same_dirty_editor_root_no_adoption', all(after[key] == dirty[key]
              for key in ('revision', 'generation', 'root_instance_id', 'working_files', 'state', 'project_revision')))
        status, lookup = call('/v1/lookup', {'project_id': owner.project_id, 'command_id': request.command_id}, control=True)
        check('authenticated_lookup_original_unknown', status == 200 and canonical_bytes(lookup) == canonical_bytes(result))
        journal_model, storage_id, editor = owner.journal_model, owner.storage_id, owner._editor
        editor_pid = editor.identity['pid']
        server.close(); server = None
        owner.close(); owner = None
        editor_closed = editor.close()
        save(output / 'editor-close.json', editor_closed)
        actual_exit, job = editor_closed.get('actual_process_exit', {}), editor_closed.get('job', {})
        check('actual_editor_exit_and_owned_job_clean', actual_exit.get('pid') == editor_pid
              and type(actual_exit.get('exit_code')) is int and actual_exit['exit_code'] == 0
              and type(editor_closed.get('wrapper_exit_code')) is int and editor_closed['wrapper_exit_code'] == 0
              and editor_closed.get('closed') is True and editor_closed.get('logs_overflow') is False
              and job.get('closed') is True and job.get('zero_observed') is True
              and type(job.get('active_count')) is int and job['active_count'] == 0
              and job.get('tainted') is False and job.get('handle_retained') is False)
        reopened = journal_model.PublicationJournalV5.reopen(storage_id, project_id='project.fixture')
        record = reopened.lookup(request.command_id, request.digest)
        check('readonly_reopen_preserves_unknown_and_original_selection', record['phase'] == 'UNKNOWN'
              and record['uncertain_phase'] == 'CAPTURED' and record['public_ack'] is False
              and reopened.snapshot()['stopped'] is True
              and canonical_bytes(reopened.selection_facts()) == canonical_bytes(selection_before)
              and reopened.read_selected_bundle().project_revision == before['project_revision'])
        save(output / 'reopened.json', reopened.snapshot())
        reopened.close(); reopened = None
        save(output / 'publication-stop.json', {'passed': True, 'checks': rows, 'candidate_only': True,
            'gt03_acceptance': False, 'actual_http_stop_during_linux_validation': True,
            'source_closure_sha256': closure, 'stop_elapsed_ms': timing['stop_elapsed_ms']})
        print('HH_PUBLICATION_STOP_COMPLETE ' + json.dumps({'passed': True, 'checks': len(rows)}), flush=True)
        return 0
    finally:
        failures = []
        if owner is not None: owner.sessions.halt()
        if save_thread is not None and save_thread.is_alive():
            save_thread.join(timeout=95)
            if save_thread.is_alive(): failures.append(RuntimeError('save HTTP thread still requires drain'))
        for resource in (server, owner, reopened):
            if resource is not None:
                try: resource.close()
                except BaseException as error: failures.append(error)
        if failures: raise failures[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--closure')
    args = parser.parse_args()
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id): parser.error('invalid run ID')
    if args.frozen: return frozen(args.output, args.binary, args.closure)
    output = args.output.resolve(); output.relative_to(STUDIO.parent / 'zdoc/reviews')
    output.mkdir(parents=True, exist_ok=False)
    inventory = load('publication_stop_inventory', STUDIO / 'tests/godot/run_editor_probe.py')
    before = inventory.inputs(); source = output / 'source/studio'
    for name, digest in before.items():
        target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
        if sha(target) != digest: raise ValueError('source changed during freeze')
    runner = load('publication_stop_runner', source / 'build/bootstrap/run_fixture.py')
    closure = runner.source_closure_sha256(before)
    save(output / 'source-closure.json', {'files': before, 'source_closure_sha256': closure})
    lock = json.loads((source / 'toolchain.lock.json').read_bytes())['godot']
    local = json.loads((STUDIO / '.local/toolchain.local.json').read_bytes())
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    if sha(binary) != lock['gui_sha256']: raise ValueError('GUI pin mismatch')
    environment = dict(os.environ)
    environment['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host = runner.run_process([sys.executable, '-B', str(source / 'tests/godot/run_publication_stop_probe.py'),
        '--frozen', '--output', str(output), '--run-id', args.run_id, '--binary', str(binary), '--closure', closure],
        cwd=source, output=output, timeout=180, label='publication-stop', env=environment)
    unchanged = before == inventory.inputs()
    frozen_unchanged = all(sha(source / name) == digest for name, digest in before.items())
    passed = (type(host['exit_code']) is int and host['exit_code'] == 0
        and type(host['wrapper_exit_code']) is int and host['wrapper_exit_code'] == 0
        and host['tree_verified'] is True and host['timed_out'] is False and frozen_unchanged)
    save(output / 'capture.json', {'run_id': args.run_id, 'host': host, 'passed': passed,
        'source_closure_sha256': closure, 'origin_source_unchanged': unchanged,
        'snapshot_unchanged': frozen_unchanged, 'candidate_only': True, 'gt03_acceptance': False})
    print(json.dumps({'passed': passed, 'host': host, 'origin_source_unchanged': unchanged}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
