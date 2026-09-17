"""A separate authenticated HTTP client observes an owned native Blender GUI.

Credentials travel only through the bounded child stdin pipe, never argv or
evidence. The facade is read-only; this probe makes no durable/public-write ACK.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from run_blender_ipc_probe import load, sources


def sha(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def client():
    from studio.protocol.core import Discovery, Request, Response, canonical_bytes, parse_json
    from studio.host.core.transport import epoch_ms
    from studio.host.blender import client_catalog as catalog

    config = json.loads(sys.stdin.buffer.read(65537))
    rows, artifacts, calls = [], {}, []

    def check(label, condition):
        rows.append({'label': label, 'passed': condition is True})
        if condition is not True:
            raise AssertionError(label)

    def call(path, body, *, credential='primary', digest=None, port=None):
        selected = config['stop_port'] if path == '/v1/stop' else (
            config['control_port'] if path == '/v1/lookup' else config['port'])
        connection = http.client.HTTPConnection('127.0.0.1', port or selected, timeout=5)
        try:
            connection.request('POST', path, canonical_bytes(body), {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + config[credential],
                'X-HH-Catalog': digest or catalog.CATALOG_DIGEST})
            received = connection.getresponse()
            raw = received.read(catalog.MAX_WIRE + 1)
            check('bounded_response_' + str(len(rows)), len(raw) <= catalog.MAX_WIRE)
            calls.append({'route': path, 'request': parse_json(canonical_bytes(body)),
                'client_role': credential,
                'listener': {config['port']: 'work', config['control_port']: 'control',
                             config['stop_port']: 'stop'}[port or selected],
                'catalog_digest': digest or catalog.CATALOG_DIGEST,
                'http_status': received.status, 'response_wire': raw.decode('utf-8')})
            return received.status, parse_json(raw), raw
        finally:
            connection.close()

    project = {'project_id': config['project_id']}
    status, discovery, _ = call('/v1/discovery', project)
    parsed = Discovery.from_dict(discovery)
    check('read_only_typed_discovery', status == 200 and
          tuple(item.operation for item in parsed.capabilities) == (catalog.READ,) and
          not any(item.write_scopes for item in parsed.capabilities)
          and parsed.project_id == config['project_id']
          and parsed.schema_digest == catalog.CATALOG_DIGEST
          and parsed.server == 'hh.blender.readonly' and parsed.build == config['source_sha256'])
    artifacts['discovery'] = discovery
    status, _, _ = call('/v1/discovery', project, credential='revoked')
    check('revoked_credential_rejected', status == 400)
    status, _, _ = call('/v1/discovery', project, digest='sha256:' + '0' * 64)
    check('wrong_catalog_rejected', status == 400)
    status, _, _ = call('/v1/lease', {**project, 'ttl_ms': 30000, 'access': 'write'})
    check('write_lease_rejected', status == 400)
    status, lease, _ = call('/v1/lease', {**project, 'ttl_ms': 30000, 'access': 'read'})
    check('read_lease_exact_registered_revision', status == 200 and lease['access'] == 'read'
          and lease['fencing_epoch'] == 0 and lease['revision'] == config['expected']['revision'])
    artifacts['lease'] = lease

    def request(key, operation=catalog.READ, revision=None):
        return Request(command_id=key, project_id=config['project_id'], operation=operation,
            lease_id=lease['lease_id'], fencing_epoch=0,
            expected_revision=revision or lease['revision'], target=lease['target'], payload={},
            payload_hash=sha(canonical_bytes({})),
            deadline_ms=min(lease['expires_ms'], epoch_ms() + catalog.MAX_READ_MS)).as_dict()

    submitted = request('client.inspect')
    status, reply, wire = call('/v1/commands', submitted)
    response = Response.from_dict(reply)
    check('native_observation_committed', status == 200 and response.status.value == 'COMMITTED'
          and response.code == 'BLENDER_READ_CONFIRMED'
          and response.command_id == submitted['command_id'] and response.result_revision == lease['revision'])
    observation = reply['postconditions']['observation']
    check('native_scene_revision_context_and_identity_exact',
          observation['scene'] == config['expected'] and observation['pid'] == config['native_pid']
          and observation['generation'] == config['generation']
          and observation['native_revision'] == lease['revision']
          and observation['source_sha256'] == parsed.build)
    check('explicit_hash_domain_and_volatile_read_scope',
          response.result_hash == sha(canonical_bytes(observation))
          and reply['postconditions']['hash_domain'] == 'jcs-observation-v1'
          and reply['postconditions']['read_only'] is True
          and reply['postconditions']['durable'] is False
          and reply['postconditions']['public_ack'] is False)
    artifacts.update(request=submitted, response=reply, response_wire=wire.decode('utf-8'))
    status, _, duplicate = call('/v1/commands', submitted)
    check('duplicate_returns_exact_original_wire', status == 200 and duplicate == wire)
    query = {**project, 'command_id': 'client.inspect'}
    status, _, looked_up = call('/v1/lookup', query)
    check('lookup_returns_exact_original_wire', status == 200 and looked_up == wire)
    status, denied, _ = call('/v1/lookup', query, credential='second')
    check('other_session_cannot_lookup_receipt', status == 200 and denied['code'] == 'COMMAND_NOT_FOUND')
    status, denied, _ = call('/v1/commands', request('client.edit', 'object.transform.set'))
    check('unsupported_mutation_rejected', status == 200 and denied['status'] == 'REJECTED')
    status, denied, _ = call('/v1/commands', request('client.stale', revision='sha256:' + '0' * 64))
    check('stale_revision_rejected', status == 200 and denied['code'] == 'BLENDER_STALE_REVISION')
    status, denied, _ = call('/v1/lookup', query, port=config['stop_port'])
    check('canonical_stop_listener_rejects_lookup', status == 400 and denied['code'] == 'UNSUPPORTED_ROUTE')
    started = time.monotonic()
    status, stopped, _ = call('/v1/stop', {**project, 'command_id': 'client.stop'})
    elapsed = (time.monotonic() - started) * 1000
    check('canonical_native_stop_observed', status == 200 and stopped['code'] == 'BLENDER_STOP_OBSERVED'
          and stopped['status'] == 'COMMITTED' and elapsed < 3000)
    status, stopped_discovery, _ = call('/v1/discovery', project)
    check('stopped_discovery_has_no_read_capability', status == 200 and not stopped_discovery['capabilities'])
    status, _, after_stop = call('/v1/lookup', query)
    check('historical_observation_survives_stop_without_new_effect', status == 200 and after_stop == wire)
    artifacts.update(stop=stopped, stop_ms=elapsed, discovery_after_stop=stopped_discovery)
    report = {'passed': True, 'checks': rows, 'artifacts': artifacts, 'calls': calls,
              'pid': os.getpid(), 'public_ack': False, 'durable': False}
    print('GT04_HTTP_CLIENT_COMPLETE ' + json.dumps(report), flush=True)
    return 0


def frozen(output, binary):
    from studio.host.blender.ui_host import BlenderUIHost
    from studio.host.blender.durable_session import DurableBlenderSession
    from studio.host.blender.client_owner import BlenderClientOwner
    from studio.host.blender.client_transport import BlenderClientTransport
    from studio.protocol.core import canonical_bytes
    from run_durable_session_probe import command

    gui = server = None
    rows = []

    def write(name, value):
        raw = canonical_bytes(value)
        with (output / name).open('xb') as stream:
            stream.write(raw)

    def check(label, condition):
        rows.append({'label': label, 'passed': condition is True})
        if condition is not True:
            raise AssertionError(label)

    try:
        try:
            gui = BlenderUIHost(output, binary=binary, session_seconds=90)
        except BaseException as error:
            retained = getattr(error, 'cleanup_owner', None)
            if type(retained) is BlenderUIHost:
                gui = retained
            raise
        setup = DurableBlenderSession(gui.directory / 'journal', host=gui)
        writer = setup.acquire_writer('trusted-fixture-setup', ttl_ms=30000)
        initial = json.loads(setup.execute_bytes(command('setup-inspect', 'scene.inspect'), writer))['native']['result']
        created = json.loads(setup.execute_bytes(command('setup-box', 'mesh.create_box', initial,
            {'object_id': 'box', 'size': [1, 2, 3]}), writer))['native']['result']['after']
        owner = BlenderClientOwner.from_host(gui)
        credential = owner.sessions.issue()
        second = owner.sessions.issue()
        revoked = owner.sessions.issue()
        owner.sessions.revoke(revoked)
        # Retain the exact transport even if start reports deferred cleanup.
        server = BlenderClientTransport(owner)
        server.start()
        before = gui.channels['data'].sent
        config = {'project_id': owner.project_id, 'port': server.port, 'control_port': server.control_port,
            'stop_port': server.stop_port, 'primary': credential.bearer, 'second': second.bearer,
            'revoked': revoked.bearer, 'expected': created, 'native_pid': gui.pid, 'generation': gui._session,
            'source_sha256': owner._source_sha256}
        process = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--client'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            stdout, stderr = process.communicate(json.dumps(config).encode('utf-8'), timeout=25)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
            raise
        check('client_secrets_absent_from_logs', all(value.encode() not in stdout + stderr
            for value in (credential.bearer, second.bearer, revoked.bearer)))
        (output / 'client-stdout.txt').write_bytes(stdout)
        (output / 'client-stderr.txt').write_bytes(stderr)
        write('client-exit.json', {'pid': process.pid, 'exit_code': process.returncode})
        check('separate_client_actual_exit_zero', process.pid != os.getpid() and process.returncode == 0 and not stderr)
        lines = stdout.decode('utf-8').splitlines()
        check('single_client_completion', len(lines) == 1 and lines[0].startswith('GT04_HTTP_CLIENT_COMPLETE '))
        child = json.loads(lines[0].removeprefix('GT04_HTTP_CLIENT_COMPLETE '))
        check('client_checks_complete', child['passed'] is True and child['pid'] == process.pid
              and child['checks'] and all(item['passed'] is True for item in child['checks']))
        check('only_one_new_native_read_despite_retries_and_denials', gui.channels['data'].sent == before + 1)
        write('client.json', child)
        write('expected-scene.json', created)
        server.close()
        cleanup = gui.close()
        check('native_gui_and_wrapper_exit_zero_owned_job_empty', cleanup['closed'] is True
            and cleanup['actual_process_exit'] == {'pid': gui.pid, 'exit_code': 0}
            and cleanup['wrapper_exit_code'] == 0 and cleanup['job']['zero_observed'] is True
            and cleanup['job']['active_count'] == 0 and cleanup['job']['closed'] is True
            and cleanup['job']['handle_retained'] is False)
        report = {'passed': True, 'checks': rows, 'client_checks': len(child['checks']),
            'client_pid': process.pid, 'native_pid': gui.pid, 'generation': gui._session,
            'cleanup': cleanup, 'public_ack': False, 'durable': False, 'formal_acceptance': False}
        write('native.json', report)
        print('GT04_CLIENT_NATIVE_COMPLETE ' + json.dumps({'passed': True, 'checks': len(rows),
              'client_checks': len(child['checks'])}), flush=True)
        return 0
    finally:
        errors = []
        drained = server is None
        if server is not None:
            for attempt in range(2):
                try:
                    server.close()
                    drained = True
                    break
                except Exception as error:
                    if attempt == 1:
                        errors.append(type(error).__name__)
                    elif gui is not None:
                        # Preserve GUI/process ownership while native reads
                        # drain; do not release it behind a retained handler.
                        try:
                            gui.stop()
                        except Exception:
                            pass
        if gui is not None and drained:
            try:
                gui.close()
            except Exception as error:
                errors.append(type(error).__name__)
        if errors:
            write('cleanup-failure.json', {'types': errors})
            raise RuntimeError('owned cleanup remains held')


def passed(host):
    return host is not None and host['exit_code'] == host['wrapper_exit_code'] == 0 \
        and host['timed_out'] is False and host['tree_verified'] is True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', action='store_true')
    parser.add_argument('--frozen', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--binary', type=Path)
    args = parser.parse_args()
    if args.client:
        return client()
    if args.output is None:
        parser.error('--output required')
    output = args.output.resolve()
    if args.frozen:
        return frozen(output, args.binary)
    runner = load(STUDIO / 'build/bootstrap/run_fixture.py')
    runner._reject_reparse_ancestors(output)
    output.mkdir(exist_ok=False)
    original = sources(STUDIO)
    snapshot = output / 'source/studio'
    for name in original:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    assert sources(snapshot) == original
    closure = runner.source_closure_sha256(original)
    (output / 'source-closure.json').write_text(json.dumps({'files': original,
        'source_closure_sha256': closure}, indent=2) + '\n', encoding='utf-8')
    unit_code = """import json,sys,unittest
s=unittest.defaultTestLoader.discover('tests/blender',pattern='test_*.py')
def flatten(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t.id()
ids=list(flatten(s));print('GT04_UNIT_INVENTORY '+json.dumps(ids),flush=True)
r=unittest.TextTestRunner(verbosity=2).run(s)
print('GT04_UNIT_COMPLETE '+json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True)
sys.exit(not r.wasSuccessful())
"""
    unit = runner.run_process([sys.executable, '-B', '-c', unit_code], cwd=snapshot,
        output=output, timeout=120, label='unit')
    lines = (output / 'unit-stdout.txt').read_text(encoding='utf-8').splitlines()
    inventories = [json.loads(line.removeprefix('GT04_UNIT_INVENTORY ')) for line in lines
                   if line.startswith('GT04_UNIT_INVENTORY ')]
    completions = [json.loads(line.removeprefix('GT04_UNIT_COMPLETE ')) for line in lines
                   if line.startswith('GT04_UNIT_COMPLETE ')]
    complete = len(inventories) == len(completions) == 1 and inventories[0] \
        and len(set(inventories[0])) == len(inventories[0]) \
        and completions[0] == {'run': len(inventories[0]), 'failures': 0, 'errors': 0, 'skips': 0}
    host = None
    if passed(unit) and complete:
        host = runner.run_process([sys.executable, '-B', str(snapshot / 'tests/blender/run_client_probe.py'),
            '--frozen', '--output', str(output), '--binary',
            str(STUDIO / '.local/tooling/blender-5.2.1-windows-x64/blender.exe')],
            cwd=snapshot, output=output, timeout=90, label='native')
    native_complete = False
    if passed(host) and (output / 'native.json').is_file():
        native = json.loads((output / 'native.json').read_bytes())
        markers = [json.loads(line.removeprefix('GT04_CLIENT_NATIVE_COMPLETE ')) for line in
            (output / 'native-stdout.txt').read_text(encoding='utf-8').splitlines()
            if line.startswith('GT04_CLIENT_NATIVE_COMPLETE ')]
        native_complete = native['passed'] is True and native['checks'] \
            and all(item['passed'] is True for item in native['checks']) and markers == [{
                'passed': True, 'checks': len(native['checks']), 'client_checks': native['client_checks']}]
    result = {'source_closure_sha256': closure, 'unit': unit, 'host': host,
        'unit_completion': bool(complete), 'native_completion': bool(native_complete),
        'unit_counts': completions, 'source_unchanged': sources(STUDIO) == original,
        'snapshot_unchanged': sources(snapshot) == original, 'formal_acceptance': False}
    result['passed'] = passed(unit) and passed(host) and bool(complete) and bool(native_complete) \
        and result['source_unchanged'] and result['snapshot_unchanged']
    (output / 'capture.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    return int(not result['passed'])


if __name__ == '__main__':
    raise SystemExit(main())
