"""File-only GT04 read-client component audit; no engine/native/storage handles."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
DEFAULT_PACKAGE = '20260917-gt04-client-04'
EXPECTED_CLOSURE = 'bf2236b0229100062ec266b55722db7196fc0af84716bf6e29e01bd7595ef15f'
EXPECTED_TESTS = 233
FILES = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def need(condition, label):
    if not condition:
        raise ValueError(label)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def pure_protocol(snapshot):
    # Load only the already-hashed pure protocol package, with a unique namespace.
    # It never imports a Blender host, journal, Registry or engine adapter.
    name = '_gt04_client_audit_protocol'
    for key in list(sys.modules):
        if key == name or key.startswith(name + '.'):
            del sys.modules[key]
    spec = importlib.util.spec_from_file_location(name, snapshot / 'protocol/__init__.py',
        submodule_search_locations=[str(snapshot / 'protocol')])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verify(package_name=DEFAULT_PACKAGE, overrides=None, *, expected_closure=None, check_live=False):
    need(re.fullmatch(r'20260917-gt04-client-[0-9]{2}', package_name) is not None, 'package name')
    package = AUDIT.parent / package_name
    overrides = overrides or {}
    FILES.clear()

    def raw(path):
        relative = path.relative_to(ROOT).as_posix()
        need(not path.is_symlink(), 'artifact symlink')
        data = overrides[relative] if relative in overrides else path.read_bytes()
        need(len(data) <= 8 * 1024 * 1024, 'artifact byte cap')
        FILES[relative] = sha(data)
        return data

    def read(path):
        return strict_json(raw(path))

    source = read(package / 'source-closure.json')
    files = source['files']
    need(type(files) is dict and files, 'source inventory')
    for name, value in files.items():
        need(type(name) is str and '\\' not in name and not PurePosixPath(name).is_absolute()
             and '..' not in PurePosixPath(name).parts and ':' not in name
             and re.fullmatch(r'[0-9a-f]{64}', value) is not None, 'source inventory entry')
    closure = sha(''.join('8-9-hh3d-3/studio/' + name + '\0' + value + '\n'
                         for name, value in sorted(files.items())).encode())
    expected = expected_closure or (EXPECTED_CLOSURE if package_name == DEFAULT_PACKAGE else None)
    need(expected is not None, 'explicit reviewed closure required')
    need(closure == source['source_closure_sha256'] == expected, 'closure digest')
    snapshot = package / 'source/studio'
    observed = {path.relative_to(snapshot).as_posix(): sha(raw(path)) for path in snapshot.rglob('*')
                if path.is_file() and '__pycache__' not in path.parts}
    need(observed == files, 'frozen source inventory')
    if check_live:
        for name, value in files.items():
            need(sha((ROOT / 'studio' / name).read_bytes()) == value, 'live source ' + name)
    runtime = {name: value for name, value in files.items()
               if (name.endswith('.py') and name.startswith(('blender-addon/', 'host/core/',
                                                           'host/blender/', 'protocol/')))
               or name in ('blender-addon/exporter.lock.json', 'godot-addon/cli_job.py', 'toolchain.lock.json')}
    protocol = pure_protocol(snapshot)
    canonical = protocol.canonical_bytes
    runtime_digest = 'sha256:' + sha(canonical(runtime))
    capture = read(package / 'capture.json')
    need(capture['source_closure_sha256'] == closure and capture['source_unchanged'] is True
         and capture['snapshot_unchanged'] is True and capture['formal_acceptance'] is False
         and capture['passed'] is True and capture['unit_completion'] is True
         and capture['native_completion'] is True, 'completed candidate required')

    def process(label, record):
        need(record['host'] == label + '-host.json' and record['stdout'] == label + '-stdout.txt'
             and record['stderr'] == label + '-stderr.txt', 'process artifact names')
        actual = read(package / record['host'])
        need(record['exit_code'] == actual['exit_code'] == record['wrapper_exit_code'] == 0
             and actual['target_pid'] == record['target_pid']
             and type(actual['target_pid']) is int and actual['target_pid'] > 0
             and type(record['wrapper_pid']) is int and record['wrapper_pid'] > 0
             and record['wrapper_pid'] != actual['target_pid']
             and record['timed_out'] is False and record['tree_verified'] is True
             and record['ownership'] == 'gated_job_kill_on_close', 'actual ' + label + ' exit')
        return raw(package / record['stdout']).decode('utf-8'), raw(package / record['stderr']).decode('utf-8')

    unit_stdout, unit_stderr = process('unit', capture['unit'])
    native_stdout, native_stderr = process('native', capture['host'])
    need(not native_stderr, 'native stderr')

    def markers(text, prefix):
        return [strict_json(line[len(prefix):]) for line in text.splitlines() if line.startswith(prefix)]

    inventories = markers(unit_stdout, 'GT04_UNIT_INVENTORY ')
    completions = markers(unit_stdout, 'GT04_UNIT_COMPLETE ')
    need(len(inventories) == 1 and len(completions) == 1, 'unit markers')
    ids = inventories[0]
    need(type(ids) is list and len(ids) == EXPECTED_TESTS and len(set(ids)) == len(ids)
         and all(type(value) is str and value.startswith('test_') for value in ids), 'unit inventory count')
    expected_count = {'run': len(ids), 'failures': 0, 'errors': 0, 'skips': 0}
    need(completions == capture['unit_counts'] == [expected_count], 'unit completion counts')
    rows = re.findall(r'^test\w+ \(([^\r\n]+)\) \.\.\. ok$', unit_stderr.replace('\r\n', '\n'), re.M)
    need(rows == ids and re.findall(r'Ran (\d+) tests in ', unit_stderr) == [str(len(ids))]
         and unit_stderr.rstrip().endswith('OK'), 'raw unit inventory and completion')

    native = read(package / 'native.json')
    client = read(package / 'client.json')
    client_exit = read(package / 'client-exit.json')
    client_stdout = raw(package / 'client-stdout.txt').decode('utf-8')
    need(not raw(package / 'client-stderr.txt'), 'client stderr')
    need(len(client_stdout.splitlines()) == 1
         and markers(client_stdout, 'GT04_HTTP_CLIENT_COMPLETE ') == [client], 'exact client completion')

    def checks(value, label):
        need(type(value) is list and value and all(type(row) is dict and
             set(row) == {'label', 'passed'} and row['passed'] is True for row in value)
             and len({row['label'] for row in value}) == len(value), label)
        return [row['label'] for row in value]

    native_labels = checks(native['checks'], 'native checks')
    checks(client['checks'], 'client checks')
    need(native_labels == ['client_secrets_absent_from_logs', 'separate_client_actual_exit_zero',
         'single_client_completion', 'client_checks_complete', 'only_one_new_native_read_despite_retries_and_denials',
         'native_gui_and_wrapper_exit_zero_owned_job_empty'], 'required native check inventory')
    need(native['passed'] is True and client['passed'] is True and native['formal_acceptance'] is False
         and native['public_ack'] is client['public_ack'] is False
         and native['durable'] is client['durable'] is False
         and native['client_checks'] == len(client['checks']), 'read-only component flags')
    need(markers(native_stdout, 'GT04_CLIENT_NATIVE_COMPLETE ') == [{
         'passed': True, 'checks': len(native_labels), 'client_checks': len(client['checks'])}], 'native completion marker')
    need(client_exit == {'pid': client['pid'], 'exit_code': 0}
         and native['client_pid'] == client['pid']
         and len({client['pid'], native['native_pid'], capture['host']['target_pid'], capture['host']['wrapper_pid']}) == 4,
         'independent client/native/host PIDs')

    roots = list(package.glob('blender-*'))
    need(len(roots) == 1 and roots[0].is_dir(), 'one owned GUI root')
    gui = roots[0]
    start = read(gui / 'process-start.json')
    end = read(gui / 'process-exit.json')
    closed = read(gui / 'close.json')
    launch = read(gui / 'launch.json')
    lock = read(snapshot / 'toolchain.lock.json')
    need(start == {'pid': native['native_pid']} and end == {'pid': native['native_pid'], 'exit_code': 0}
         and closed == native['cleanup'] and closed['actual_process_exit'] == end
         and closed['wrapper_exit_code'] == 0 and closed['closed'] is True and closed['held'] is False
         and closed['logs_overflow'] is False and closed['public_ack'] is False, 'GUI exit and cleanup binding')
    job = closed['job']
    need(job['assigned'] is True and job['configured'] is True and job['closed'] is True
         and job['zero_observed'] is True and job['active_count'] == 0 and job['handle_retained'] is False
         and job['tainted'] is False and job['close_uncertain'] is False and job['create_uncertain'] is False
         and not job['failed_operations'] and job['native_error'] is None, 'native Job cleanup')
    need(launch['source_files'] == runtime and launch['session'] == native['generation']
         and re.fullmatch(r'[0-9a-f]{32}', native['generation']) is not None
         and launch['binary_sha256'] == lock['blender']['executable_sha256']
         and launch['public_ack'] is False, 'GUI source/pin/generation binding')
    argv = launch['argv']
    need(len(argv) == 10 and argv[0].replace('\\', '/').endswith('/blender.exe')
         and argv[1:9] == ['--factory-startup', '--disable-autoexec', '--offline-mode', '--threads', '1',
                          '--python-exit-code', '17', '--python']
         and argv[9].replace('\\', '/').endswith('/' + package_name + '/source/studio/blender-addon/ipc_client.py'),
         'owned GUI argv')
    hello = {'pid': native['native_pid'], 'version': '5.2.1 LTS', 'main_thread': True,
             'background': False, 'python_threads': 1, 'public_ack': False}
    need(read(gui / 'control-hello.json') == read(gui / 'data-hello.json') == hello, 'native authenticated hello')
    raw(gui / 'stdout.txt')
    need(not raw(gui / 'stderr.txt'), 'GUI stderr')

    descriptor = {'schema': 'HH-BLENDER-READ-CLIENT-1', 'protocol_version': '1.0',
        'schema_version': 'hh-studio-0.1', 'registration': 'exact-live-owned-BlenderUIHost-source-pid-generation',
        'request': 'Request', 'response': 'Response', 'target': {'stable_id': 'blender.owned-scene'},
        'operations': {'scene.inspect': {'read_scopes': ['blender.scene.read'], 'write_scopes': [],
            'payload': {}, 'read_lease_required': True, 'expected_revision': 'exact registered live revision'}},
        'controls': ['discovery', 'read-lease', 'lookup-own-session', 'stop'],
        'limits': {'max_commands': 32, 'max_pending': 1, 'max_read_ms': 2000, 'max_lease_ms': 30000,
                   'max_response_bytes': 65536}, 'retention': 'bounded owner lifetime; no eviction or restart replay',
        'scene_durable': False, 'writer_grants': False, 'public_ack': False}
    catalog_digest = 'sha256:' + sha(canonical(descriptor))
    artifacts = client['artifacts']
    calls = client['calls']
    need(type(calls) is list and len(calls) == 15, 'exact HTTP call inventory')
    route_expected = ['/v1/discovery', '/v1/discovery', '/v1/discovery', '/v1/lease', '/v1/lease',
        '/v1/commands', '/v1/commands', '/v1/lookup', '/v1/lookup', '/v1/commands', '/v1/commands',
        '/v1/lookup', '/v1/stop', '/v1/discovery', '/v1/lookup']
    replies = []
    for index, row in enumerate(calls):
        need(set(row) == {'route', 'request', 'client_role', 'listener', 'catalog_digest',
                          'http_status', 'response_wire'}, 'HTTP call shape')
        need(row['route'] == route_expected[index] and row['client_role'] ==
             ('revoked' if index == 1 else 'second' if index == 8 else 'primary'), 'HTTP route/caller')
        need(row['listener'] == ('stop' if index in (11, 12) else 'control' if index in (7, 8, 14) else 'work'),
             'HTTP listener isolation')
        need(row['catalog_digest'] == ('sha256:' + '0' * 64 if index == 2 else catalog_digest), 'HTTP catalog binding')
        need(type(row['response_wire']) is str and 0 < len(row['response_wire'].encode()) <= 65536, 'HTTP wire cap')
        value = protocol.parse_json(row['response_wire'])
        need(canonical(value).decode() == row['response_wire'], 'canonical HTTP wire')
        need(row['request']['project_id'] == 'blender.owned-fixture', 'HTTP request project')
        replies.append(value)
    discovery = protocol.Discovery.from_dict(replies[0])
    need(calls[0]['http_status'] == 200 and replies[0] == artifacts['discovery']
         and discovery.project_id == 'blender.owned-fixture' and discovery.schema_digest == catalog_digest
         and discovery.server == 'hh.blender.readonly' and discovery.build == runtime_digest
         and discovery.limits == descriptor['limits']
         and [c.as_dict() for c in discovery.capabilities] == [{'operation': 'scene.inspect',
             'read_scopes': ['blender.scene.read'], 'write_scopes': [],
             'limits': {'max_pending': 1, 'max_read_ms': 2000, 'max_response_bytes': 65536}}], 'exact Discovery')
    for index, code in ((1, 'AUTH_REQUIRED'), (2, 'BLENDER_GRANT_BINDING'),
                        (3, 'BLENDER_READ_ONLY'), (11, 'UNSUPPORTED_ROUTE')):
        need(calls[index]['http_status'] == 400 and replies[index]['status'] == 'REJECTED'
             and replies[index]['code'] == code and replies[index]['public_ack'] is False, 'HTTP rejection ' + str(index))
    lease = replies[4]
    expected_scene = read(package / 'expected-scene.json')
    need(all(calls[index]['request'] == {'project_id': discovery.project_id} for index in (0, 1, 2, 13))
         and calls[3]['request'] == {'project_id': discovery.project_id, 'ttl_ms': 30000, 'access': 'write'}
         and calls[4]['request'] == {'project_id': discovery.project_id, 'ttl_ms': 30000, 'access': 'read'},
         'Discovery and lease request shapes')
    need(calls[4]['http_status'] == 200 and lease == artifacts['lease'] and lease['access'] == 'read'
         and lease['fencing_epoch'] == 0 and lease['revision'] == expected_scene['revision']
         and lease['target'] == descriptor['target'] and lease['catalog_digest'] == catalog_digest
         and lease['public_ack'] is False and lease['durable'] is False, 'exact read lease')
    request = protocol.Request.from_dict(calls[5]['request'])
    need(calls[5]['request'] == artifacts['request'] == calls[6]['request']
         and request.command_id == 'client.inspect' and request.operation == 'scene.inspect'
         and request.lease_id == lease['lease_id'] and request.fencing_epoch == 0
         and request.expected_revision == lease['revision'] and request.target == descriptor['target']
         and request.payload == {} and request.deadline_ms <= lease['expires_ms'], 'exact inspect Request')
    response = protocol.Response.from_dict(replies[5])
    observation = response.postconditions['observation']
    need(calls[5]['http_status'] == 200 and replies[5] == artifacts['response']
         and calls[5]['response_wire'] == artifacts['response_wire']
         and response.status.value == 'COMMITTED' and response.code == 'BLENDER_READ_CONFIRMED'
         and response.command_id == request.command_id and response.result_revision == lease['revision']
         and response.result_hash == 'sha256:' + sha(canonical(observation)), 'read response/hash')
    need(observation == {'native_revision': lease['revision'], 'scene': expected_scene, 'pid': native['native_pid'],
         'generation': native['generation'], 'source_sha256': runtime_digest}
         and response.postconditions['hash_domain'] == 'jcs-observation-v1'
         and response.postconditions['public_ack'] is False and response.postconditions['durable'] is False
         and response.postconditions['read_only'] is True, 'native observation identity')
    need(all(calls[i]['http_status'] == 200 and calls[i]['response_wire'] == calls[5]['response_wire']
             for i in (6, 7, 14)), 'exact duplicate and lookup wires')
    need(all(calls[i]['request'] == {'project_id': discovery.project_id, 'command_id': request.command_id}
             for i in (7, 8, 11, 14)), 'lookup command binding')
    for index, key, operation, revision in ((9, 'client.edit', 'object.transform.set', lease['revision']),
            (10, 'client.stale', 'scene.inspect', 'sha256:' + '0' * 64)):
        rejected_request = protocol.Request.from_dict(calls[index]['request'])
        need(rejected_request.command_id == key and rejected_request.operation == operation
             and rejected_request.expected_revision == revision and rejected_request.payload == {}
             and rejected_request.target == request.target and rejected_request.lease_id == request.lease_id,
             'rejected Request binding ' + str(index))
    for index, code in ((8, 'COMMAND_NOT_FOUND'), (9, 'UNSUPPORTED_OPERATION'), (10, 'BLENDER_STALE_REVISION')):
        denied = protocol.Response.from_dict(replies[index])
        need(calls[index]['http_status'] == 200 and denied.status.value == 'REJECTED' and denied.code == code
             and denied.postconditions['public_ack'] is False and 'observation' not in denied.postconditions,
             'typed rejection ' + str(index))
    stop = protocol.Response.from_dict(replies[12])
    need(calls[12]['http_status'] == 200 and replies[12] == artifacts['stop']
         and calls[12]['request'] == {'project_id': discovery.project_id, 'command_id': 'client.stop'}
         and stop.command_id == 'client.stop' and stop.status.value == 'COMMITTED' and stop.code == 'BLENDER_STOP_OBSERVED'
         and stop.postconditions['stopped'] is True and stop.postconditions['public_ack'] is False
         and stop.postconditions['read_draining'] is False
         and stop.postconditions['durable'] is False and stop.postconditions['read_only'] is True
         and type(artifacts['stop_ms']) in (float, int) and 0 <= artifacts['stop_ms'] < 3000, 'exact Stop observation')
    after = protocol.Discovery.from_dict(replies[13])
    need(calls[13]['http_status'] == 200 and replies[13] == artifacts['discovery_after_stop']
         and not after.capabilities and {**replies[13], 'capabilities': replies[0]['capabilities']} == replies[0],
         'stopped discovery identity')

    # Secrets were deliberately not captured. Independently check no raw bearer
    # header/token-shaped value is in retained text, and bind the executed exact
    # secret scanner row/source; this is not a reconstruction of unknown tokens.
    for relative in list(FILES):
        if relative.endswith(('.json', '.txt')) and '/source/' not in relative:
            data = raw(ROOT / relative)
            need(re.search(rb'Bearer\s+[A-Za-z0-9_-]{43}', data) is None, 'bearer header in evidence')
    failed_history = []
    for number, error_code in (('01', 'invalid identifier'), ('02', 'BLENDER_COMMAND_REJECTED'),
                                ('03', 'SECRET_FIELD_FORBIDDEN')):
        old = AUDIT.parent / ('20260917-gt04-client-' + number)
        old_capture = read(old / 'capture.json')
        old_source = read(old / 'source-closure.json')
        old_closure = sha(''.join('8-9-hh3d-3/studio/' + name + '\0' + value + '\n'
            for name, value in sorted(old_source['files'].items())).encode())
        old_exit = read(old / 'native-host.json')
        old_unit_exit = read(old / 'unit-host.json')
        old_stderr = raw(old / 'native-stderr.txt').decode('utf-8')
        need(old_capture['passed'] is False and old_capture['native_completion'] is False
             and old_capture['formal_acceptance'] is False and old_capture['unit_completion'] is True
             and old_capture['source_closure_sha256'] == old_source['source_closure_sha256'] == old_closure
             and old_capture['host']['exit_code'] == old_exit['exit_code'] == 1
             and old_capture['host']['target_pid'] == old_exit['target_pid']
             and old_capture['host']['wrapper_exit_code'] == 0 and old_capture['host']['tree_verified'] is True
             and old_capture['unit']['exit_code'] == old_unit_exit['exit_code'] == 0
             and error_code in old_stderr, 'historical failure ' + number)
        row = {'package': old.name, 'passed': False, 'source_closure_sha256': old_closure,
               'unit_tests': old_capture['unit_counts'][0]['run'], 'native_parent_exit': 1, 'diagnostic': error_code}
        if number == '03':
            old_client_exit = read(old / 'client-exit.json')
            old_lines = raw(old / 'client-stdout.txt').decode('utf-8')
            old_child = markers(old_lines, 'GT04_HTTP_CLIENT_COMPLETE ')
            need(len(old_child) == 1 and old_child[0]['passed'] is True
                 and old_client_exit == {'pid': old_child[0]['pid'], 'exit_code': 0}, 'failed03 child/parent distinction')
            row.update(child_checks=len(old_child[0]['checks']), child_exit=0,
                       note='Child succeeded; parent artifact serialization failed. Not a completed candidate.')
            previous_runtime = {name: value for name, value in old_source['files'].items() if name in runtime}
            need(previous_runtime == runtime, '03 to 04 runtime unchanged')
        failed_history.append(row)
    return {'passed': True, 'package': package_name, 'source_closure_sha256': closure,
        'source_files': len(files), 'runtime_source_sha256': runtime_digest, 'unit_tests': len(ids),
        'unit_inventory_sha256': sha(canonical(ids)), 'client_checks': len(client['checks']),
        'http_calls': len(calls), 'client_pid': client['pid'], 'native_pid': native['native_pid'],
        'stop_ms': artifacts['stop_ms'], 'artifacts_checked': len(FILES),
        'preserved_failed_history': failed_history,
        'secret_check_scope': 'pinned executed scanner plus retained raw-header inspection; ephemeral tokens unavailable',
        'public_ack': False, 'durable': False, 'formal_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', default=DEFAULT_PACKAGE)
    parser.add_argument('--expected-closure')
    parser.add_argument('--check-live', action='store_true')
    parser.add_argument('--write-derived', action='store_true')
    args = parser.parse_args()
    result = verify(args.package, expected_closure=args.expected_closure, check_live=args.check_live)
    if args.write_derived:
        (AUDIT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        (AUDIT / 'portable-artifacts.json').write_text(json.dumps(dict(sorted(FILES.items())), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
