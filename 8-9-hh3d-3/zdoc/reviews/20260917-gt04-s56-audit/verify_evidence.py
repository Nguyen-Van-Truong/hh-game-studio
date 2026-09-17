"""File-only S56 component audit; no Journal construction or native operations."""
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import struct
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVIEWS = HERE.parent
DEADLINE = REVIEWS / '20260917-gt04-s56-deadline-02'
WRITER = REVIEWS / '20260917-gt04-s56-writer-01'
SOURCE = WRITER / 'source/studio'
CLOSURE = '71332451f3914f42f3a35dc8702a1c0eb3cb3cb6d99adfa4b8ca317373dd8162'
FILES = {}
COPIES = {}
CHECKS = []


def need(value, label):
    if not value:
        raise ValueError(label)
    CHECKS.append(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def raw(path, *, inventory=True):
    path = path.absolute()
    relative = path.relative_to(ROOT).as_posix()
    for current in (path, *path.parents):
        info = current.lstat()
        need(not current.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'regular artifact path')
        if current == ROOT:
            break
    value = path.read_bytes()
    need(len(value) <= 8 * 1024**2, 'artifact byte cap')
    if inventory:
        FILES[relative] = sha(value)
    return value


def read(path):
    return strict(raw(path))


def secret_shape(value):
    if isinstance(value, dict):
        need(not set(key.lower() for key in value) & {
            'authorization', 'bearer', 'token', 'secret', 'hmac_key', 'ipc_key', 'session_key'},
            'no credential-bearing artifact fields')
        for child in value.values():
            secret_shape(child)
    elif isinstance(value, list):
        for child in value:
            secret_shape(child)
    elif isinstance(value, str):
        need(re.search(r'Bearer\s+[A-Za-z0-9_.-]{24,}', value, re.I) is None,
             'no captured bearer value')


def snapshot(package):
    manifest = read(package / 'source-closure.json')
    mapping = manifest['files']
    base = package / 'source/studio'
    observed = {path.relative_to(base).as_posix(): sha(raw(path))
                for path in base.rglob('*') if path.is_file()}
    need(observed == mapping, 'complete snapshot inventory')
    closure = sha(''.join('8-9-hh3d-3/studio/' + name + '\0' + digest + '\n'
                         for name, digest in sorted(mapping.items())).encode())
    need(closure == manifest['source_closure_sha256'] == CLOSURE, 'exact source closure')
    return manifest


def zero_job(job):
    need(job['assigned'] is True and job['configured'] is True and job['closed'] is True
         and job['zero_observed'] is True and type(job['active_count']) is int and job['active_count'] == 0
         and job['handle_retained'] is False and job['tainted'] is False
         and job['failed_operations'] == [] and job['native_error'] is None
         and job.get('close_uncertain', False) is False and job.get('create_uncertain', False) is False,
         'owned Job closed and empty')


def host(package, captured):
    fact = read(package / captured['host'])
    need(type(fact['exit_code']) is int and fact['exit_code'] == captured['exit_code'] == 0
         and type(captured['wrapper_exit_code']) is int and captured['wrapper_exit_code'] == 0
         and type(fact['target_pid']) is int and fact['target_pid'] > 0
         and fact['target_pid'] == captured['target_pid'] and captured['timed_out'] is False
         and captured['tree_verified'] is True and captured['ownership'] == 'gated_job_kill_on_close',
         'raw host exit and bounded ownership')
    need(datetime.fromisoformat(captured['started_at']) <= datetime.fromisoformat(fact['started_at']),
         'wrapper before target startup')
    return raw(package / captured['stdout']).decode('utf-8'), raw(package / captured['stderr'])


def package_facts(package, manifest, runner, count, report_name):
    capture = read(package / 'capture.json')
    need(capture['source_closure_sha256'] == CLOSURE and capture['run_id'] == manifest['run_id']
         and all(capture[name] is True for name in ('passed', 'source_unchanged', 'snapshot_unchanged',
             'unit_completion', 'native_completion', 'logs_clean'))
         and capture['public_ack'] is False and capture['formal_acceptance'] is False,
         'capture identity and component-only scope')
    unit_out, unit_err = host(package, capture['unit'])
    native_out, native_err = host(package, capture['host'])
    ids = [strict(line[len(runner.UNIT_INVENTORY):]) for line in unit_out.splitlines()
           if line.startswith(runner.UNIT_INVENTORY)]
    counts = [strict(line[len(runner.UNIT_COMPLETE):]) for line in unit_out.splitlines()
              if line.startswith(runner.UNIT_COMPLETE)]
    need(len(ids) == 1 and len(ids[0]) == len(set(ids[0])) == count
         and counts == capture['unit_counts'] == [{'run': count, 'failures': 0, 'errors': 0, 'skips': 0}],
         'unique unit inventory and exact completed counts')
    test_rows = re.findall(r'^(\S+) \(([^)]+)\) \.\.\. ok\r?$', unit_err.decode('utf-8'), re.M)
    logged = {owner + '.' + name for name, owner in test_rows}
    # Newer unittest prints the method in the parenthesized test id as well.
    logged |= {owner for _, owner in test_rows}
    need(set(ids[0]) <= logged and re.search(rb'Ran ' + str(count).encode() + rb' tests? in ', unit_err)
         and re.search(rb'\nOK\s*$', unit_err), 'raw unittest completion matches inventory')
    need(runner.unit_completion(unit_out)[0] and runner.native_completion(package, capture['host']),
         'verified frozen completion gates')
    report = read(package / report_name)
    need(report['failure'] is None and report['cleanup_errors'] == []
         and report['source_closure_sha256'] == CLOSURE and report['run_id'] == manifest['run_id']
         and report['probe_pid'] == capture['host']['target_pid'], 'native report identity')
    need(native_err == b'', 'no native host stderr')
    directory = report['gui_directory']
    need(re.fullmatch(r'blender-[0-9a-f]{32}', directory) is not None, 'fixed owned GUI directory')
    gui = package / directory
    close = read(gui / 'close.json')
    exited = read(gui / 'process-exit.json')
    started = read(gui / 'process-start.json')
    need(close == report['cleanup'] and close['actual_process_exit'] == exited
         and type(exited['exit_code']) is int and exited['exit_code'] == 0
         and type(close['wrapper_exit_code']) is int and close['wrapper_exit_code'] == 0
         and started['pid'] == exited['pid'] == report['native_pid']
         and close['closed'] is True and close['held'] is False and close['logs_overflow'] is False,
         'GUI raw PID native exit wrapper exit and cleanup')
    zero_job(close['job'])
    launch = read(gui / 'launch.json')
    mapping = manifest['files']
    runtime = {name: value for name, value in mapping.items()
        if (name.endswith('.py') and (name.startswith(('blender-addon/', 'host/blender/', 'host/core/', 'protocol/'))))
        or name in ('blender-addon/exporter.lock.json', 'godot-addon/cli_job.py', 'toolchain.lock.json')}
    need(launch['source_files'] == runtime, 'launch complete runtime closure')
    need(launch['binary_sha256'] == read(package / 'source/studio/toolchain.lock.json')['blender']['executable_sha256']
         and all(flag in launch['argv'] for flag in ('--factory-startup', '--disable-autoexec', '--offline-mode'))
         and Path(launch['argv'][-1]).name == 'ipc_client.py', 'pinned trusted native entry point')
    need(launch['argv'][-1].replace('\\', '/').endswith('/8-9-hh3d-3/' +
         (package / 'source/studio/blender-addon/ipc_client.py').relative_to(ROOT).as_posix()),
         'GUI executed exact frozen IPC entry point')
    for lane in ('control', 'data'):
        hello = read(gui / (lane + '-hello.json'))
        need(hello['pid'] == report['native_pid'] and hello['public_ack'] is False
             and hello['background'] is False and hello['main_thread'] is True
             and hello['python_threads'] == 1, 'authenticated hello native process identity')
    for name in ('stdout.txt', 'stderr.txt'):
        text = raw(gui / name).lower()
        need(not any(word in text for word in (b'traceback', b'fatal', b'error:', b'warning:', b'leaked')),
             'no unexplained GUI diagnostic')
    secret_shape(report)
    return capture, report, gui, launch, runtime


def closed_journal(gui, relative, filename, inventory):
    original = gui / relative
    target = HERE / filename
    data = raw(target) if target.exists() else raw(original, inventory=False)
    record = inventory[original.relative_to(gui.parent).as_posix()]
    need(record == {'bytes': len(data), 'sha256': 'sha256:' + sha(data)}, 'closed journal inventory binding')
    if original.exists():
        need(raw(original, inventory=False) == data, 'copy equals original closed journal bytes')
    COPIES[target] = data
    return data


def audit_deadline(report, runner, canonical_bytes, queue):
    events = report['events']
    need([row['kind'] for row in events] == ['inspect', 'deadline-denial', 'deadline-denial',
        'deadline-denial', 'inspect', 'valid-create', 'future-retry', 'past-retry', 'inspect', 'stop'],
        'deadline trace complete and ordered')
    observations = {}
    for event in events[:-1]:
        need(event['command_id'] == event['command']['command_id']
             and event['command_sha256'] == 'sha256:' + sha(queue.c.canonical(event['command']))
             and event['result_sha256'] == 'sha256:' + sha(canonical_bytes(event['result']))
             and event['result_hash_domain'] == 'jcs-received-result-v1'
             and event['native_revision_recomputed'] is False, 'deadline raw command and response hashes')
        if event['kind'] == 'deadline-denial':
            need(event['result']['rejected'] is True and 0 <= event['result']['elapsed_ms'] < 2500,
                 'bounded deadline rejection trace')
        else:
            observations[event['command_id']] = runner.checked_observation(event['command'], event['result'])
    need(events[1]['deadline_ms'] < int(datetime.fromisoformat(events[1]['recorded_at']).timestamp() * 1000)
         and events[1]['raw_ipc'] is False and events[2]['deadline_ms'] is None
         and events[3]['deadline_ms'] is True and events[2]['raw_ipc'] is events[3]['raw_ipc'] is True,
         'expired null and boolean deadline cases')
    before = observations['deadline-initial']
    after = observations['deadline-create']
    need(before['snapshot']['objects'] == [] and observations['deadline-after-denials'] == before,
         'deadline denials have unchanged native readback')
    obj, = after['snapshot']['objects']
    need(obj['object_id'] == 'deadline_box' and len(obj['vertices']) == 8 and len(obj['faces']) == 6
         and [max(v[i] for v in obj['vertices']) - min(v[i] for v in obj['vertices']) for i in range(3)] == [1, 2, 3]
         and obj['location'] == obj['rotation'] == [0, 0, 0] and obj['scale'] == [1, 1, 1]
         and after['context'] == before['context'], 'deadline valid create actual geometry and context')
    for event in events[6:8]:
        need(event['command'] == events[5]['command'] and event['result'] == events[5]['result']
             and event['original_deadline_ms'] == events[5]['deadline_ms']
             and event['observed_after_original_ms'] > event['original_deadline_ms'],
             'deadline retries retain exact receipt after original expiry')
    need(events[6]['deadline_ms'] > events[6]['observed_after_original_ms']
         and events[7]['deadline_ms'] == events[5]['deadline_ms']
         and observations['deadline-after-retries'] == after, 'retry cannot add second object')
    need(events[-1]['result'] == {'stopped': True, 'public_ack': False}
         and 0 <= events[-1]['elapsed_ms'] < 2000, 'bounded native Stop trace')


def audit_writer(report, gui, launch, runtime, inventory, ledger, catalog, core, Journal, runner):
    client = read(WRITER / 'client.json')
    need(runner.client_report(raw(WRITER / 'client-stdout.txt')) == client
         and raw(WRITER / 'client-stderr.txt') == b'', 'raw CLI completion exact saved trace')
    exited = read(WRITER / 'client-exit.json')
    need(exited == report['client_cleanup'] and type(exited['exit_code']) is int and exited['exit_code'] == 0
         and exited['pid'] == client['pid'] and exited['pid'] not in (report['probe_pid'], report['native_pid'])
         and exited['timed_out'] is False, 'separate CLI actual exit')
    zero_job(exited['job'])
    secret_shape(client)
    calls = client['calls']
    need(len(calls) == 23, 'exact bounded HTTP trace count')
    responses = []
    for call in calls:
        wire = call['response_wire'].encode('utf-8')
        need(call['request_sha256'] == 'sha256:' + sha(core.canonical_bytes(call['request']))
             and call['response_sha256'] == 'sha256:' + sha(wire), 'HTTP exact request and response hashes')
        value = core.parse_json(wire)
        need(core.canonical_bytes(value) == wire and call['role'] in ('writer', 'reader', 'foreign'),
             'HTTP canonical bytes and explicit role')
        responses.append(value)
    need({v['operation'] for v in responses[0]['capabilities']} == catalog.EDIT_OPERATIONS | {catalog.READ}
         and [v['operation'] for v in responses[1]['capabilities']] == [catalog.READ]
         and responses[21]['capabilities'] == [], 'truthful connected discovery before and after Stop')
    need(responses[0]['schema_digest'] == catalog.CATALOG_DIGEST
         and responses[0]['build'] == 'sha256:' + sha(core.canonical_bytes(runtime)), 'discovery source and catalog binding')
    expected_denials = {2: 'BLENDER_WRITER_GRANT_REQUIRED', 8: 'BLENDER_LEDGER_COMMAND_CONFLICT',
        10: 'BLENDER_LEDGER_COMMAND_NOT_FOUND', 11: 'BLENDER_LEDGER_COMMAND_OWNER',
        12: 'BLENDER_OPERATION_FORBIDDEN', 13: 'BLENDER_DEADLINE_EXPIRED', 19: 'UNSUPPORTED_ROUTE'}
    for index, code in expected_denials.items():
        need(responses[index]['status'] == 'REJECTED' and responses[index]['code'] == code
             and 'observation' not in responses[index].get('postconditions', {}), 'HTTP known denial has no observation')
    need(calls[19]['listener'] == calls[20]['listener'] == 'stop'
         and calls[19]['http_status'] == 400 and calls[20]['route'] == '/v1/stop'
         and responses[20]['status'] == 'COMMITTED' and responses[20]['postconditions']['stopped'] is True,
         'isolated canonical Stop listener trace')
    for index in (7, 9, 22):
        need(calls[index]['response_wire'] == calls[6]['response_wire'], 'duplicate lookup and post-Stop exact wire')
    decoder = object.__new__(Journal)
    decoder.profile = ledger.DEFAULT_LIMITS
    data = closed_journal(gui, 'client-ledger/client-commands.jsonl', 'client-commands.jsonl', inventory)
    records = [decoder._decode_record(line) for line in data.splitlines(keepends=True)]
    secret_shape(records)
    binding = ledger.LedgerBinding(**records[0]['receipt']['binding'])
    need(binding.generation == launch['session'] and binding.catalog_digest == catalog.CATALOG_DIGEST
         and binding.source_sha256 == 'sha256:' + sha(core.canonical_bytes(runtime))
         and binding.owner_pin_sha256 == 'sha256:' + sha(core.canonical_bytes({
             'pid': report['native_pid'], 'generation': launch['session'], 'binary_sha256': launch['binary_sha256']})),
         'common ledger exact native owner binding')
    history = ledger.validate_history(records, binding)
    need(len(records) == 15 and len(history) == 7 and all(entry['response'] is not None for entry in history.values()),
         'seven common INTENT and terminal pairs plus config')
    order = [5, 6, 14, 15, 16, 17, 18]
    names = ['initial_inspect', 'create', 'transform', 'material', 'undo', 'redo', 'final_inspect']
    need([entry['intent']['command_id'] for entry in history.values()] == [calls[i]['request']['command_id'] for i in order],
         'HTTP successful order equals complete ledger order')
    previous = None
    requests = []
    for position, (index, name) in enumerate(zip(order, names)):
        request = core.Request.from_dict(calls[index]['request'])
        entry = list(history.values())[position]
        intent = entry['intent']
        translated = catalog.translate(request, binding=binding, session_id=intent['session_id'])
        need(entry['request'] == request and ledger.make_intent(binding, intent['session_id'], request,
             core.parse_json(translated)) == intent and translated == ledger.unchunk(intent['native_chunks'], ledger.queue.c.MAX_BYTES),
             'HTTP Request and exact native command bind to admitted intent')
        response = core.Response.from_dict(responses[index])
        need(entry['response'] == calls[index]['response_wire'].encode('utf-8')
             and response.status is core.Status.COMMITTED and response.command_id == request.command_id,
             'common terminal bytes equal actual HTTP wire')
        details = response.postconditions
        observation = details['observation']
        scene = observation['scene']
        need(response.result_hash == 'sha256:' + sha(core.canonical_bytes(observation))
             and response.result_revision == observation['native_revision'] == scene['revision']
             and observation['pid'] == report['native_pid'] and observation['generation'] == binding.generation
             and observation['source_sha256'] == binding.source_sha256
             and scene == client['observed'][name] and details['before_revision'] == request.expected_revision,
             'terminal observation hash native identity and declared scene')
        need(details['public_ack'] is False and details['ledger_receipt_only'] is True
             and details['scene_state_durable'] is False and details['durable_publication'] is False
             and details['hash_domain'] == 'jcs-observation-v1'
             and details['read_only'] is (request.operation == catalog.READ), 'terminal claim limits')
        if previous is not None:
            need(request.expected_revision == previous['revision'] and scene['context'] == previous['context'],
                 'native revision chain and restored context')
        if request.operation != catalog.READ:
            need(request.payload['expected_context'] == scene['context']
                 and request.lease_id == responses[3]['lease_id']
                 and request.fencing_epoch == responses[3]['fencing_epoch']
                 and entry['row']['created_ms'] < request.deadline_ms <= responses[3]['expires_ms'],
                 'admitted write has original lease context and unexpired deadline')
        previous = scene
        requests.append(request)
    observed = client['observed']
    need(observed['initial_inspect']['snapshot']['objects'] == [], 'writer begins with observed empty scene')
    box, = observed['create']['snapshot']['objects']
    need(box['object_id'] == requests[1].payload['arguments']['object_id']
         and len(box['vertices']) == 8 and len(box['faces']) == 6
         and [max(v[i] for v in box['vertices']) - min(v[i] for v in box['vertices']) for i in range(3)]
             == requests[1].payload['arguments']['size'], 'actual native created geometry matches request')
    rounded = lambda value: struct.unpack('f', struct.pack('f', value))[0]
    transformed, = observed['transform']['snapshot']['objects']
    for field in ('location', 'rotation', 'scale'):
        need(transformed[field] == [rounded(v) for v in requests[2].payload['arguments'][field]],
             'actual transform matches binary32 native readback')
    material = observed['material']['snapshot']['objects'][0]['material']
    planned = requests[3].payload['arguments']
    need(material['material_id'] == planned['material_id']
         and material['base_color'] == [rounded(v) for v in planned['base_color']] + [1]
         and all(material[name] == rounded(planned[name]) for name in ('metallic', 'roughness')),
         'actual native material matches typed request')
    need(observed['undo'] == observed['transform'] and observed['redo'] == observed['material']
         and observed['final_inspect'] == observed['redo'], 'real history Undo Redo and final inspect chain')
    lease_data = closed_journal(gui, 'journal/blender-journal.jsonl', 'writer-leases.jsonl', inventory)
    lease_rows = [decoder._decode_record(line) for line in lease_data.splitlines(keepends=True)]
    secret_shape(lease_rows)
    need(len(lease_rows) == 3 and lease_rows[0]['receipt'] == {'generation': binding.generation, 'public_ack': False}
         and lease_rows[1]['kind'] == 'lease' and lease_rows[1]['project_id'] == binding.project_id
         and lease_rows[1]['target'] == catalog.TARGET
         and lease_rows[1]['fencing_epoch'] == responses[3]['fencing_epoch']
         and lease_rows[1]['expires_ms'] >= responses[3]['expires_ms']
         and responses[3]['lease_id'] == 'write.' + lease_rows[1]['owner'].removeprefix('client-writer-')
         and lease_rows[2]['command_id'] == 'writer-stop' and lease_rows[2]['status'] == 'COMMITTED'
         and lease_rows[2]['receipt'] == {'stopped': True, 'public_ack': False}, 'native lease and durable Stop bind public writer')
    return {'http_calls': len(calls), 'http_checks': len(client['checks']), 'common_commands': len(history),
            'common_journal_records': len(records), 'native_lease_records': len(lease_rows)}


def main():
    a, b = snapshot(DEADLINE), snapshot(WRITER)
    need(a['files'] == b['files'], 'both packages use identical complete snapshots')
    sys.path[:0] = [str(SOURCE.parent), str(SOURCE / 'tests/blender')]
    from studio.host.blender import client_ledger as ledger, client_write_catalog as catalog
    from studio.host.core.journal import Journal
    from studio.protocol import core
    deadline_runner = importlib.import_module('run_absolute_deadline_probe')
    writer_runner = importlib.import_module('run_writer_client_probe')
    need(Path(ledger.__file__).resolve() == SOURCE / 'host/blender/client_ledger.py'
         and Path(deadline_runner.__file__).resolve() == SOURCE / 'tests/blender/run_absolute_deadline_probe.py'
         and Path(writer_runner.__file__).resolve() == SOURCE / 'tests/blender/run_writer_client_probe.py',
         'frozen modules only')
    first = package_facts(DEADLINE, a, deadline_runner, 440, 'absolute-deadline-native.json')
    second = package_facts(WRITER, b, writer_runner, 174, 'writer-native.json')
    inventories = {}
    for package in (DEADLINE, WRITER):
        inventories[package] = read(package / 'evidence-inventory.json')
    audit_deadline(first[1], deadline_runner, core.canonical_bytes, ledger.queue)
    writer_summary = audit_writer(second[1], second[2], second[3], second[4], inventories[WRITER],
        ledger, catalog, core, Journal, writer_runner)
    for package in (DEADLINE, WRITER):
        prefix = package.relative_to(ROOT).as_posix() + '/'
        for path, digest in list(FILES.items()):
            if path.startswith(prefix):
                relative = path[len(prefix):]
                if not relative.startswith('source/') and relative != 'evidence-inventory.json':
                    expected = inventories[package][relative]
                    need(expected['sha256'] == 'sha256:' + digest
                         and expected['bytes'] == (ROOT / path).stat().st_size, 'consumed artifact original inventory')
    # These two closed, decoded, credential-free streams are the only copied
    # private-root artifacts. Existing copies must match; nothing is overwritten.
    for path, value in COPIES.items():
        if not path.exists():
            with path.open('xb') as stream:
                stream.write(value)
        need(raw(path) == value, 'portable closed journal copy verified')
    return {'passed': True, 'scope': 'GT04_S56_COMPONENT_FILE_AUDIT', 'formal_acceptance': False,
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'source_closure_sha256': CLOSURE,
        'source_files_per_snapshot': len(a['files']), 'unit_tests': {'deadline_all': 440, 'writer_focused': 174},
        'native_checks': {'deadline': len(first[1]['checks']), 'writer_parent': len(second[1]['checks'])},
        **writer_summary, 'assertions': len(CHECKS), 'native_handles_opened': 0, 'engines_launched': 0,
        'journal_constructors_called': 0, 'public_ack': False, 'scene_state_durable': False,
        'limitations': ['Component evidence only; GT04 remains unaccepted.',
            'Seven native submission counter checks are captured harness observations; no raw IPC packet log is claimed.',
            'Known-secret byte comparison is captured by the frozen harness; this audit also rejects credential-shaped fields.',
            'Historical native revisions are opaque float-preserving tokens; only declared JCS observation hashes are recomputed.']}


if __name__ == '__main__':
    try:
        result = main()
    except Exception as error:
        result = {'passed': False, 'formal_acceptance': False, 'failure': str(error),
                  'exception_type': type(error).__name__, 'assertions_before_failure': len(CHECKS)}
    (HERE / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (HERE / 'portable-artifacts.json').write_text(json.dumps(dict(sorted(FILES.items())), indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 1)
