"""One coordinator-scheduled native lane using the unchanged shared S55 source.

--describe and --dry-run never spawn a child. Execution needs the coordinator's
exclusive native/Linux slot. Each fresh output contains its own controller,
invocation, source reference, raw process exit, result checks and typed log audit.
No runtime copy, production acceptance or source mutation is performed.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REVIEWS = HERE.parent
PACKAGE = REVIEWS / '20260917-gt03-s55-source-01'
SOURCE = PACKAGE / 'source/studio'
LIVE_STUDIO = REVIEWS.parent.parent / 'studio'
CLOSURE = '3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e'
FILE_COUNT = 176
# Timeouts are the fixed values in the corresponding frozen outer wrappers.
LANES = {
    'save': ('run_publication_probe.py', 180, 'publication.json', 'passed', 'HH_PUBLICATION_COMPLETE'),
    'script': ('run_script_publication_probe.py', 240, 'publication.json', 'passed', 'HH_SCRIPT_PUBLICATION_COMPLETE'),
    'edit': ('run_edit_publication_probe.py', 360, 'publication.json', 'passed', 'HH_EDIT_PUBLICATION_COMPLETE'),
    'stop': ('run_publication_stop_probe.py', 180, 'publication-stop.json', 'passed', 'HH_PUBLICATION_STOP_COMPLETE'),
    'fifo': ('run_fifo_publication_probe.py', 210, 'fifo-publication.json', 'passed', 'HH_FIFO_PUBLICATION_COMPLETE'),
    'recovery-publication': ('run_recovery_publication_probe.py', 240, 'recovery.json', 'passed', 'HH_AUTHENTICATED_RECOVERY_COMPLETE'),
}
CRASH_EXITS = {'scene-cas': 93, 'script-committed': 94, 'script-retired': 96,
               'edit-applied': 98, 'script-unwitnessed': 95}
for _case in CRASH_EXITS:
    LANES[_case] = ('run_recovery_cut_matrix.py', 240, 'result.json', 'ok', 'HH_RECOVERY_CUT_COMPLETE')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def save(path, value):
    need(not path.exists(), 'evidence file already exists: ' + path.name)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def regular(path):
    for part in (path, *path.parents):
        if part.exists():
            need(not part.is_symlink() and not (getattr(part.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400),
                 'reparse/symlink input forbidden: ' + str(part))


def inventory():
    regular(SOURCE)
    values = {}
    for path in sorted(SOURCE.rglob('*')):
        regular(path)
        if path.is_file():
            name = path.relative_to(SOURCE).as_posix()
            need('__pycache__' not in path.parts and path.suffix not in ('.pyc', '.pyo'), 'untracked bytecode in immutable source')
            values[name] = digest(path)
    return values


def constants(path, names):
    values = {}
    for node in ast.parse(path.read_bytes()).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in names:
                    values[target.id] = ast.literal_eval(node.value)
    need(set(values) == set(names), 'frozen executable pin constants missing')
    return values


def preflight():
    need(os.name == 'nt', 'native lanes require the pinned Windows host')
    record_path = PACKAGE / 'source-closure.json'
    regular(record_path)
    record = read(record_path)
    need(record.get('source_closure_sha256') == CLOSURE and len(record.get('files', {})) == FILE_COUNT,
         'shared source package identity/count mismatch')
    before = inventory()
    need(before == record['files'], 'shared source inventory/hash mismatch')
    runner = load('s55_native_lane_owned_runner', SOURCE / 'build/bootstrap/run_fixture.py')
    need(runner.source_closure_sha256(before) == CLOSURE, 'shared source canonical closure mismatch')
    lock = read(SOURCE / 'toolchain.lock.json')['godot']
    local = read(LIVE_STUDIO / '.local/toolchain.local.json')
    binary = Path(local['godot_console']).with_name(lock['gui_executable'])
    linux = constants(SOURCE / 'godot-addon/linux_executor.py', ('BINARY_NAME', 'BINARY_SHA256'))
    linux_binary = LIVE_STUDIO / '.local/tooling/godot-4.7.2-stable-linux' / linux['BINARY_NAME']
    regular(binary)
    regular(linux_binary)
    need(binary.is_absolute() and binary.is_file() and digest(binary) == lock['gui_sha256'], 'Windows GUI binary pin mismatch')
    need(linux_binary.is_file() and digest(linux_binary) == linux['BINARY_SHA256'], 'Linux binary pin mismatch')
    pins = {'windows_gui': {'path': str(binary), 'sha256': lock['gui_sha256']},
            'linux': {'path': str(linux_binary), 'sha256': linux['BINARY_SHA256']}}
    return runner, before, digest(record_path), binary, linux_binary, pins


def clean_exit(output, host, expected):
    raw = read(output / host['host'])
    return (type(raw.get('exit_code')) is int and raw['exit_code'] == expected == host.get('exit_code')
        and type(raw.get('target_pid')) is int and raw['target_pid'] > 0 and raw['target_pid'] == host.get('target_pid')
        and type(host.get('wrapper_exit_code')) is int and host['wrapper_exit_code'] == 0
        and host.get('tree_verified') is True and host.get('timed_out') is False
        and host.get('ownership') == 'gated_job_kill_on_close')


def typed_logs(output):
    # This source-pinned scanner already binds expected executor removal probes
    # to exact container IDs, successful rm exits and empty owned Jobs.
    scanner = load('s55_frozen_typed_log_scanner', SOURCE / 'tests/godot/run_recovery_cut_matrix.py')
    report = scanner.audit_logs([output])
    for row in report['logs']:
        path = Path(row['path'])
        raw = path.read_bytes()
        # Stop has an extra read-only running-container observation outside
        # the executor directory. Permit only its exact inspect JSON/host pair.
        if not row['clean'] and re.fullmatch(r'running-[1-9][0-9]*-stdout\.txt', path.name):
            try:
                label = path.name.removesuffix('-stdout.txt')
                native = read(path)
                host = read(path.with_name(label + '-host.json'))
                job = host['job_owner']
                need(type(native) is list and len(native) == 1, 'running inspect shape')
                container = native[0]
                container_id = container['Id']
                need(re.fullmatch('[0-9a-f]{64}', container_id) is not None and container['State']['Error'] == '', 'running inspect identity/error')
                need(type(host['exit_code']) is int and host['exit_code'] == 0 and host['timed_out'] is False
                    and host['stream_cap_exceeded'] is False and host['readers_stopped'] is True
                    and type(host['job_active_count']) is int and host['job_active_count'] == 0
                    and host['stream_reader_errors'] == [None, None]
                    and type(host['stream_reader_eof']) is list and len(host['stream_reader_eof']) == 2
                    and all(value is True for value in host['stream_reader_eof'])
                    and job['closed'] is True and job['zero_observed'] is True and job['tainted'] is False
                    and job['handle_retained'] is False and type(job['active_count']) is int and job['active_count'] == 0
                    and job['failed_operations'] == [] and job['native_error'] is None
                    and host['argv'][-2:] == ['inspect', container_id]
                    and host['stdout'] == path.name and host['stderr'] == label + '-stderr.txt'
                    and path.with_name(host['stderr']).read_bytes() == b'', 'running inspect host')
                observations = read(output / 'running-observations.json')
                need(any(item['host'] == host and item['owner']['container_id'] == container_id for item in observations),
                     'running inspect not bound to observed owned record')
                del container['State']['Error']
                need(re.search(rb'(?i)\b(warning|error|fatal|traceback)\b', json.dumps(native).encode()) is None,
                     'unexplained running inspect diagnostic')
                row.update(clean=True, reason='typed_owned_running_inspect_empty_state_error')
            except (ValueError, KeyError, TypeError, OSError):
                row.update(clean=False, reason='invalid_running_inspect_evidence')
        if re.search(rb'(?i)\bleaked\b', raw):
            row.update(clean=False, reason='unexplained_leak_diagnostic')
    report['clean'] = bool(report['logs']) and all(row['clean'] is True for row in report['logs'])
    report['scanner_source_sha256'] = digest(SOURCE / 'tests/godot/run_recovery_cut_matrix.py')
    return report


def validate_result(output, lane, host):
    _, _, filename, success_key, marker = LANES[lane]
    report = read(output / filename)
    checks = report.get('checks')
    need(type(checks) is list and checks and all(type(row) is dict and row.get('passed') is True for row in checks),
         'missing or failed lane checks')
    need(report.get(success_key) is True and report.get('source_closure_sha256') == CLOSURE,
         'lane success/source mismatch')
    lines = (output / host['stdout']).read_text(encoding='utf-8').splitlines()
    markers = [json.loads(line[len(marker) + 1:]) for line in lines if line.startswith(marker + ' ')]
    need(len(markers) == 1 and markers[0].get(success_key) is True
        and type(markers[0].get('checks')) is int and markers[0]['checks'] == len(checks), 'completion marker/result mismatch')
    original = None
    if lane in CRASH_EXITS or lane == 'recovery-publication':
        original = read(output / 'original-host.json')
        need(clean_exit(output / 'original', original, CRASH_EXITS.get(lane, 92)), 'original crash raw exit/owned Job mismatch')
    if lane in CRASH_EXITS:
        need(report.get('case') == lane and markers[0].get('case') == lane, 'cut identity mismatch')
    return {'file': filename, 'sha256': digest(output / filename), 'check_count': len(checks),
            'completion_marker': markers[0], 'original_host': original}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lane', choices=tuple(LANES))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--run-id')
    parser.add_argument('--describe', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='validate inputs and show argv; never create output or spawn')
    args = parser.parse_args()
    if args.describe:
        print(json.dumps({'source_package': str(PACKAGE), 'source_closure_sha256': CLOSURE,
            'file_count': FILE_COUNT, 'lanes': {name: {'script': value[0], 'timeout_seconds': value[1],
                'result': value[2]} for name, value in LANES.items()}, 'engines_started': 0}, indent=2))
        return 0
    need(args.lane in LANES and args.output is not None and type(args.run_id) is str
         and re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id), 'lane/output/valid run-id required')
    output = args.output.resolve()
    need(output.parent == REVIEWS.resolve() and not output.exists(), 'output must be a fresh direct child of reviews')
    regular(output.parent)
    runner, before, manifest_hash, binary, linux_binary, pins = preflight()
    script, timeout, _, _, _ = LANES[args.lane]
    argv = [sys.executable, '-B', str(SOURCE / 'tests/godot' / script), '--frozen', '--output', str(output),
            '--run-id', args.run_id, '--binary', str(binary), '--closure', CLOSURE]
    if args.lane in CRASH_EXITS:
        argv += ['--case', args.lane]
    controller = Path(__file__).resolve()
    controller_hash = digest(controller)
    invocation = {'lane': args.lane, 'run_id': args.run_id, 'argv': argv, 'cwd': str(SOURCE),
        'timeout_seconds': timeout, 'source_closure_sha256': CLOSURE,
        'controller_sha256': controller_hash, 'runtime_entrypoint_sha256': before['tests/godot/' + script],
        'python': {'path': sys.executable, 'version': sys.version, 'sha256': digest(Path(sys.executable))},
        'pins': pins, 'environment_overrides': {'HH_STUDIO_LINUX_GODOT': str(linux_binary), 'PYTHONDONTWRITEBYTECODE': '1'},
        'one_lane_only': True, 'requires_coordinator_native_slot': True}
    if args.dry_run:
        print(json.dumps({'dry_run': True, 'engines_started': 0, 'output_created': False, 'invocation': invocation}, indent=2))
        return 0
    output.mkdir()
    (output / 'controller.py').write_bytes(controller.read_bytes())
    need(digest(output / 'controller.py') == controller_hash, 'controller changed during copy')
    save(output / 'invocation.json', invocation)
    save(output / 'source-reference.json', {'source_package': str(PACKAGE), 'source_root': str(SOURCE),
        'source_closure_sha256': CLOSURE, 'file_count': FILE_COUNT, 'source_manifest_sha256': manifest_hash,
        'runtime_copied': False, 'controller_sha256': controller_hash})
    capture = {'run_id': args.run_id, 'lane': args.lane, 'passed': False,
        'started_at_utc': datetime.now(timezone.utc).isoformat(), 'source_closure_sha256': CLOSURE,
        'controller_sha256': controller_hash, 'candidate_only': True, 'gt03_acceptance': False}
    try:
        environment = dict(os.environ)
        environment.update(invocation['environment_overrides'])
        host = runner.run_process(argv, cwd=SOURCE, output=output, timeout=timeout,
                                  label='native-' + args.lane, env=environment)
        capture['host'] = host
        save(output / 'host-report.json', host)
        need(clean_exit(output, host, 0), 'native lane raw exit/wrapper/owned Job mismatch')
        capture['result'] = validate_result(output, args.lane, host)
        logs = typed_logs(output)
        save(output / 'log-audit.json', logs)
        need(logs['clean'] is True, 'unexplained or unproven log diagnostics')
        capture['native_logs_clean'] = True
        capture['passed'] = True
    except BaseException as error:
        capture['failure'] = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            after = inventory()
            source_unchanged = after == before and digest(PACKAGE / 'source-closure.json') == manifest_hash
            controller_unchanged = digest(controller) == controller_hash == digest(output / 'controller.py')
            pins_unchanged = digest(binary) == pins['windows_gui']['sha256'] and digest(linux_binary) == pins['linux']['sha256']
            capture.update(source_inventory_unchanged=source_unchanged, controller_unchanged=controller_unchanged,
                           executable_pins_unchanged=pins_unchanged)
            capture['passed'] = capture['passed'] and source_unchanged and controller_unchanged and pins_unchanged
            save(output / 'source-check-after.json', {'unchanged': source_unchanged, 'file_count': len(after),
                'changed': sorted(name for name in before.keys() & after.keys() if before[name] != after[name]),
                'missing': sorted(before.keys() - after.keys()), 'extra': sorted(after.keys() - before.keys())})
        except BaseException as error:
            capture['passed'] = False
            capture['final_verification_failure'] = type(error).__name__ + ': ' + str(error)
        capture['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
        save(output / 'capture.json', capture)
    print(json.dumps({'lane': args.lane, 'passed': capture['passed'], 'source_closure_sha256': CLOSURE,
        'checks': capture.get('result', {}).get('check_count'), 'failure': capture.get('failure')}, indent=2), flush=True)
    return 0 if capture['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
