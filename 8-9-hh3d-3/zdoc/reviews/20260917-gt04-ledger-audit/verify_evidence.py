"""File-only verification of the bounded S55 Blender ledger native probe."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PACKAGE = HERE.parent / '20260917-gt04-ledger-native-01'
SOURCE = PACKAGE / 'source/studio'
CLOSURE = 'a18e6de9563e770fe7258242c369abdef04f2af692995360ff3f5402b488d9b7'


def need(value, label):
    if not value:
        raise ValueError(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def verify(overrides=None):
    overrides = overrides or {}
    files = {}

    def raw(path):
        relative = path.relative_to(ROOT).as_posix()
        need(not path.is_symlink(), 'artifact symlink')
        value = overrides[relative] if relative in overrides else path.read_bytes()
        need(len(value) <= 8 * 1024 * 1024, 'artifact size')
        files[relative] = sha(value)
        return value

    def read(path):
        return strict_json(raw(path))

    source = read(PACKAGE / 'source-closure.json')
    mapping = source['files']
    observed = {p.relative_to(SOURCE).as_posix(): sha(raw(p))
                for p in SOURCE.rglob('*') if p.is_file()}
    need(observed == mapping, 'complete snapshot inventory')
    closure = sha(''.join('8-9-hh3d-3/studio/' + name + '\0' + value + '\n'
                         for name, value in sorted(mapping.items())).encode())
    need(closure == source['source_closure_sha256'] == CLOSURE, 'source closure')
    # Import the verified snapshot only. These calls decode bytes and reduce
    # captured records; no Journal constructor, handles or engine is invoked.
    sys.path.insert(0, str(SOURCE.parent))
    from studio.host.blender import client_ledger as ledger
    from studio.host.core.journal import Journal
    from studio.protocol.core import Request, Response, canonical_bytes, parse_json
    need(Path(ledger.__file__).resolve() == SOURCE / 'host/blender/client_ledger.py', 'frozen reducer import')

    capture = read(PACKAGE / 'capture.json')
    need(capture['source_closure_sha256'] == CLOSURE and capture['passed'] is True
         and capture['source_unchanged'] is True and capture['snapshot_unchanged'] is True
         and capture['public_ack'] is False and capture['public_write_facade'] is False
         and capture['formal_acceptance'] is False, 'candidate scope and source')

    def host(value, label):
        fact = read(PACKAGE / value['host'])
        need(type(value['exit_code']) is int and value['exit_code'] == 0
             and type(fact['exit_code']) is int and fact['exit_code'] == 0
             and type(value['wrapper_exit_code']) is int and value['wrapper_exit_code'] == 0
             and type(fact['target_pid']) is int and fact['target_pid'] > 0
             and fact['target_pid'] == value['target_pid'] and value['tree_verified'] is True
             and value['timed_out'] is False and value['ownership'] == 'gated_job_kill_on_close', label)
        return raw(PACKAGE / value['stdout']).decode('utf-8'), raw(PACKAGE / value['stderr'])

    unit_out, unit_err = host(capture['unit'], 'unit actual exit')
    native_out, native_err = host(capture['host'], 'native actual exit')
    need(native_err == b'', 'native stderr')
    ids = [strict_json(line.split(' ', 1)[1]) for line in unit_out.splitlines()
           if line.startswith('GT04_LEDGER_UNIT_INVENTORY ')]
    counts = [strict_json(line.split(' ', 1)[1]) for line in unit_out.splitlines()
              if line.startswith('GT04_LEDGER_UNIT_COMPLETE ')]
    need(len(ids) == 1 and len(ids[0]) == len(set(ids[0])) == 42
         and all(name.startswith(('test_client_ledger.', 'test_client_ledger_probe.')) for name in ids[0])
         and counts == [{'run': 42, 'failures': 0, 'errors': 0, 'skips': 0}]
         and capture['unit_counts'] == counts and capture['unit_completion'] is True
         and b'\nOK' in unit_err, 'unit completion')
    report = read(PACKAGE / 'ledger-native.json')
    checks = report['checks']
    markers = [strict_json(line.split(' ', 1)[1]) for line in native_out.splitlines()
               if line.startswith('GT04_LEDGER_NATIVE_COMPLETE ')]
    need(report['passed'] is True and len(checks) == len({r['label'] for r in checks}) == 25
         and all(row['passed'] is True for row in checks)
         and markers == [{'passed': True, 'checks': 25}]
         and report['probe_pid'] == capture['host']['target_pid']
         and report['failure'] is None and report['cleanup_errors'] == [], 'native completion')
    directory = report['gui_directory']
    need(Path(directory).name == directory and directory.startswith('blender-'), 'owned GUI directory')
    gui = PACKAGE / directory
    cleanup = read(gui / 'close.json')
    exit_fact = read(gui / 'process-exit.json')
    start = read(gui / 'process-start.json')
    job = cleanup['job']
    need(cleanup == report['cleanup'] and cleanup['closed'] is True
         and cleanup['held'] is False and cleanup['logs_overflow'] is False
         and type(cleanup['wrapper_exit_code']) is int and cleanup['wrapper_exit_code'] == 0
         and type(exit_fact['exit_code']) is int and exit_fact['exit_code'] == 0
         and type(start['pid']) is int and start['pid'] > 0
         and start['pid'] == exit_fact['pid'] == report['native_pid']
         and exit_fact == cleanup['actual_process_exit'] and job['closed'] is True
         and job['zero_observed'] is True and type(job['active_count']) is int and job['active_count'] == 0
         and job['handle_retained'] is False and job['tainted'] is False
         and job['failed_operations'] == [] and job['native_error'] is None, 'GUI actual exit and owned Job')
    launch = read(gui / 'launch.json')
    native_source = {name: value for name, value in mapping.items()
        if (name.endswith('.py') and name.split('/')[0] in ('blender-addon', 'host', 'protocol')
            and not name.startswith('tests/'))
        or name in ('blender-addon/exporter.lock.json', 'godot-addon/cli_job.py', 'toolchain.lock.json')}
    need(launch['source_files'] == native_source, 'native complete runtime source')
    need(launch['binary_sha256'] == read(SOURCE / 'toolchain.lock.json')['blender']['executable_sha256']
         and all(flag in launch['argv'] for flag in ('--factory-startup', '--disable-autoexec', '--offline-mode')),
         'Blender pin and execution profile')
    facts = report['artifacts']
    binding = ledger.LedgerBinding(**facts['ledger_binding'])
    need(binding.generation == launch['session']
         and binding.source_sha256 == 'sha256:' + sha(canonical_bytes(native_source)), 'owner source binding')
    need(binding.owner_pin_sha256 == 'sha256:' + sha(canonical_bytes({'pid': report['native_pid'],
         'generation': binding.generation, 'binary_sha256': launch['binary_sha256']})), 'exact owner identity pin')
    decoder = object.__new__(Journal)
    decoder.profile = ledger.DEFAULT_LIMITS
    histories = []
    for name, count in (('intent-before-native', 2), ('terminal-readback', 3), ('unresolved-readback', 4)):
        data = raw(PACKAGE / (name + '.jsonl'))
        need(facts[name] == {'sha256': 'sha256:' + sha(data), 'bytes': len(data), 'records': count}, 'journal artifact hash')
        records = [decoder._decode_record(line) for line in data.splitlines(keepends=True)]
        need(len(records) == count, 'journal record count')
        histories.append((records, ledger.validate_history(records, binding)))
    need(histories[1][0][:2] == histories[0][0] and histories[2][0][:3] == histories[1][0], 'immutable history prefixes')
    request = Request.from_dict(facts['request'])
    original = next(iter(histories[0][1].values()))
    intent = original['intent']
    need(ledger.make_intent(binding, intent['session_id'], request, facts['private_command']) == intent,
         'public to private original binding')
    terminal_raw = facts['terminal_wire'].encode()
    terminal = Response.from_dict(parse_json(terminal_raw))
    need(histories[1][1][intent['private_id']]['response'] == terminal_raw
         and histories[2][1][intent['private_id']]['response'] == terminal_raw
         and canonical_bytes(terminal.as_dict()) == terminal_raw, 'exact terminal persistence')
    observation = terminal.postconditions['observation']
    native = facts['native_result']
    need(terminal.status.value == 'COMMITTED' and terminal.command_id == request.command_id
         and terminal.result_hash == 'sha256:' + sha(canonical_bytes(observation))
         and observation['pid'] == report['native_pid'] and observation['generation'] == binding.generation
         and observation['source_sha256'] == binding.source_sha256
         and observation['scene'] == native['result'] and native['state'] == 'COMPLETED'
         and native['command_id'] == intent['private_id'] and native['command_digest'] == intent['native_digest']
         and terminal.result_revision == request.expected_revision == native['result']['revision'], 'native observation binding')
    pending = [entry for entry in histories[2][1].values() if entry['response'] is None]
    need(len(pending) == 1 and ledger.unknown_response(pending[0]['intent']) == facts['unresolved_wire'].encode()
         and facts['native_submissions_after'] == facts['native_submissions_before'] + 1, 'unresolved no redispatch')
    need(facts['stop']['status'] == 'COMMITTED' and facts['stop']['code'] == 'BLENDER_STOP_OBSERVED'
         and report['public_ack'] is False and report['public_write_facade'] is False
         and report['live_state_durable'] is False, 'Stop and claim limits')
    for name in ('stdout.txt', 'stderr.txt'):
        data = raw(gui / name)
        need(not any(word in data.lower() for word in (b'traceback', b'fatal', b'error:', b'warning:', b'leaked')),
             'unexplained Blender diagnostics')
    return {'passed': True, 'source_closure_sha256': CLOSURE, 'source_files': len(mapping),
        'unit_checks': 42, 'native_checks': 25, 'native_handles_opened': 0,
        'public_write_facade': False, 'formal_acceptance': False}, files


if __name__ == '__main__':
    summary, mapping = verify()
    for name, value in (('verification.json', summary), ('portable-artifacts.json', mapping)):
        (HERE / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(summary))
