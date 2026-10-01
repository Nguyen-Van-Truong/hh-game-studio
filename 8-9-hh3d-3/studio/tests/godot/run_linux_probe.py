"""Frozen, resumable diagnostic fixtures for the confined Linux Godot process.

Observed child markers prove only that a fixture ran. They cannot prove the
truth of a publication validation report emitted from the same process.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
SUPERVISOR_SHA256 = '5ef0eaaaa4220593add7716aad74da927ca3bb10605e964330de64fecc3ef15e'
SUPERVISOR_BOOTSTRAP_SHA256 = '0194f9d31f6f8abaa8a33cc8c412075efa198546c2f187599ee023bd6be5c377'
DOCKER_CONTEXT = 'desktop-linux'
DOCKER_ENDPOINT = 'npipe:////./pipe/dockerDesktopLinuxEngine'
_POLICY_SPEC = importlib.util.spec_from_file_location('gt03_gameplay_log_policy',
    STUDIO / 'godot-addon/gameplay_log_policy.py')
log_policy = importlib.util.module_from_spec(_POLICY_SPEC)
_POLICY_SPEC.loader.exec_module(log_policy)
GUARD_MARKER = log_policy.GUARD_MARKER
GUARDED_STARTUP_ERROR = log_policy.GUARDED_STARTUP_ERROR
# Exact diagnostics for these pinned fixtures only. The guard denies socket()
# before editor import (two TCP listeners) and the spawn/network fixture calls.
# These remain errors in raw; explaining them does not make a clean/public PASS.
GUARDED_SOCKET_ERROR = log_policy.GUARDED_SOCKET_ERROR
GUARDED_LISTEN_ERROR = log_policy.GUARDED_LISTEN_ERROR
GAMEPLAY_STARTUP_ERRORS = log_policy.GAMEPLAY_STARTUP_ERRORS
GAMEPLAY_PHASE_EVENTS = log_policy.GAMEPLAY_PHASE_EVENTS


def gameplay_transcript(case: dict, stdout: str, stderr: str) -> bool:
    """Recognize the full fixture transcript, never attest untrusted gameplay."""
    kind = case['expect']
    primary = 'scripts/fixture_actor.gd'
    scripts = [primary] + sorted(name for name in case.get('extra_files', {})
                                if name.startswith('scripts/') and name.endswith('.gd'))
    if kind in ('gameplay_source', 'fixture_state'):
        try:
            return log_policy.classify(stdout.encode('utf-8'), stderr.encode('utf-8'), scripts)['accepted']
        except UnicodeEncodeError:
            return False
    rejected_path = case.get('parse_error_path', primary) if kind == 'engine_rejection' else None
    if rejected_path is not None and rejected_path not in scripts:
        return False
    expected = ['HH_GAMEPLAY_PHASE_BEGIN parse']
    parsed = 0
    for script in scripts:
        code = 1 if script == rejected_path else 0
        if script != primary:
            expected.append('HH_GAMEPLAY_MODULE_BEGIN ' + script)
        expected.append(GUARD_MARKER)
        if script != primary:
            expected.append('HH_GAMEPLAY_MODULE_END ' + script + ' ' + str(code))
        parsed += 1
        if code:
            break
    expected.append('HH_GAMEPLAY_PHASE_END parse ' + ('1' if rejected_path else '0'))
    if rejected_path is None:
        expected.extend(GAMEPLAY_PHASE_EVENTS[3:-1] if kind == 'watchdog' else GAMEPLAY_PHASE_EVENTS[3:])
    events = tuple(line for line in stdout.splitlines()
                   if line.startswith(('HH_GAMEPLAY_PHASE_', 'HH_GAMEPLAY_OS_GUARD', 'HH_GAMEPLAY_MODULE_')))
    if events != tuple(expected) or re.search(r'ERROR|WARNING|leaked', stdout, re.IGNORECASE):
        return False
    if kind == 'engine_rejection':
        reasons = case.get('parse_errors')
        if (type(reasons) is not tuple or not reasons
                or any(type(reason) is not str or not reason for reason in reasons)
                or any(line.startswith('HH_PROBE_') for line in stdout.splitlines())):
            return False
        errors = GUARDED_STARTUP_ERROR * parsed + ''.join(
            'SCRIPT ERROR: Parse Error: ' + reason + '\n'
            '          at: GDScript::reload (res://' + rejected_path + ':2)\n'
            for reason in reasons)
        errors += ('ERROR: Failed to load script "res://' + rejected_path + '" with error "Parse error".\n'
                   '   at: load (modules/gdscript/gdscript_resource_format.cpp:46)\n')
        return stderr.replace('\r\n', '\n') == errors
    # A watchdog fixture must reach play, so all three startups and the import
    # listener denials precede its loop. Two startup errors alone mean import
    # was interrupted; they cannot prove hostile play-loop termination.
    errors = GUARDED_STARTUP_ERROR * (parsed - 1) + GAMEPLAY_STARTUP_ERRORS
    if kind == 'spawn_observation':
        errors += ('ERROR: Cannot create pipe from command: "/usr/bin/printf" "HH_UNEXPECTED_CHILD" 2>&1.\n'
                   '   at: execute (drivers/unix/os_unix.cpp:899)\n'
                   '   GDScript backtrace (most recent call first):\n'
                   '       [0] _ready (res://scripts/fixture_actor.gd:4)\n')
    elif kind == 'boundary_observation':
        errors += (GUARDED_SOCKET_ERROR + '   GDScript backtrace (most recent call first):\n'
                   '       [0] _ready (res://scripts/fixture_actor.gd:7)\n')
    elif kind not in ('gameplay_source', 'fixture_state', 'watchdog'):
        return False
    return stderr.replace('\r\n', '\n') == errors


def _object(value) -> dict:
    return value if type(value) is dict else {}


def _integer(value, expected: int) -> bool:
    return type(value) is int and value == expected


def supervisor_binding(case: dict, result: dict) -> bool:
    """Bind recorded configuration; native inspect remains a separate audit."""
    timeout = case.get('timeout')
    if type(timeout) is not int or not 1 <= timeout <= 20:
        return False
    host = _object(result.get('command_host'))
    supervisor = _object(result.get('supervisor'))
    toolchain = _object(result.get('toolchain'))
    container_id = result.get('container_id')
    scope = supervisor.get('requires_yama_scope')
    return (supervisor.get('path') == '/usr/bin/timeout'
        and supervisor.get('sha256') == SUPERVISOR_SHA256
        and _integer(supervisor.get('term_after_seconds'), max(1, timeout - 1))
        and _integer(supervisor.get('kill_after_seconds'), 1)
        and _integer(supervisor.get('total_deadline_seconds'), max(2, timeout))
        and _integer(supervisor.get('pid'), 1)
        and type(scope) is list and all(type(value) is int for value in scope) and scope == [1, 2, 3]
        and supervisor.get('host_death_acceptance') is False
        and toolchain.get('supervisor_path') == '/usr/bin/timeout'
        and toolchain.get('supervisor_sha256') == SUPERVISOR_SHA256
        and toolchain.get('supervisor_bootstrap_sha256') == SUPERVISOR_BOOTSTRAP_SHA256
        and toolchain.get('docker_context') == DOCKER_CONTEXT
        and toolchain.get('docker_endpoint') == DOCKER_ENDPOINT
        and _integer(host.get('timeout_seconds'), timeout + 2)
        and type(container_id) is str and re.fullmatch(r'[0-9a-f]{64}', container_id) is not None
        and host.get('argv') == ['docker.exe', '--context', DOCKER_CONTEXT, 'start', '--attach', container_id])


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def marker(text: str, prefix: str) -> dict | None:
    rows = [line[len(prefix):] for line in text.split('\n') if line.startswith(prefix)]
    if len(rows) != 1:
        return None
    try:
        value = json.loads(rows[0])
    except ValueError:
        return None
    return value if type(value) is dict else None


def typed_equal(actual, expected) -> bool:
    """JSON bools cannot substitute for integer counts, including zero/one."""
    if type(actual) is not type(expected):
        return False
    if type(expected) is dict:
        return (actual.keys() == expected.keys()
                and all(typed_equal(actual[key], value) for key, value in expected.items()))
    return actual == expected


def physics_trace(case: dict, stdout: str) -> bool:
    """Cross-check bounded native telemetry for the fixed arena fixture only."""
    if case.get('fixture_kind') != 'arena_physics':
        return True
    def rows(prefix):
        return [json.loads(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
    try:
        inputs = rows('HH_FIXTURE_INPUT ')
        events = rows('HH_FIXTURE_EVENT ')
        expected_inputs = [{'tick': t, 'key': k, 'pressed': p} for t, k, p in case['input_trace']]
        if len(inputs) != len(expected_inputs) or any(not typed_equal(a, b) for a, b in zip(inputs, expected_inputs)):
            return False
        if len(events) != len(case['event_trace']):
            return False
        if tuple(row['event'] for row in events) != case['event_trace']:
            return False
        for row in events:
            if (type(row) is not dict or set(row) != {'event', 'tick', 'x', 'y', 'health', 'bot_health', 'hits', 'wall_contacts'}
                    or any(type(row[key]) is not int for key in ('tick', 'health', 'bot_health', 'hits', 'wall_contacts'))
                    or any(type(row[key]) not in (int, float) or not math.isfinite(row[key]) for key in ('x', 'y'))):
                return False
        if not all(a['tick'] < b['tick'] for a, b in zip(events, events[1:])):
            return False
        boot, pickup, bullet, jump, bot, landed, wall, finish = events
        return (boot['tick'] == 0 and boot['health'] == 3 and boot['x'] == 32.0
            and 2 <= pickup['tick'] < 25 and pickup['health'] == 4 and 45 <= pickup['x'] <= 90
            # Input.parse_input_event is called during the fixture's physics
            # callback. Godot's just-pressed physics state is consumed on the
            # following tick, not retroactively in the current callback.
            and bullet['tick'] == 26 and jump['tick'] == 29
            and bot['bot_health'] == 0 and bot['hits'] == 1
            and landed['y'] >= 173.0 and wall['wall_contacts'] == 1
            and 281.0 <= wall['x'] <= 282.1
            and finish['tick'] == 150 and finish['wall_contacts'] >= 3
            and abs(finish['x'] - wall['x']) < 0.01 and finish['y'] >= 173.0
            and finish['health'] == 4 and finish['bot_health'] == 0 and finish['hits'] == 1)
    except (ValueError, KeyError, TypeError):
        return False


def evaluate(case: dict, result: dict, stdout: str, stderr: str) -> dict:
    """Diagnostic assertions, deliberately not a publication PASS predicate."""
    host = _object(result.get('command_host'))
    state = _object(result.get('container_state'))
    job = _object(host.get('job_owner'))
    admission = _object(result.get('admission'))
    eof = host.get('stream_reader_eof')
    errors = result.get('errors')
    bound = supervisor_binding(case, result)
    controlled = (bound and result.get('schema') == 'hh-gt03-linux-diagnostic-1'
        and result.get('public_ack') is False
        and result.get('sandbox_acceptance') is False
        and result.get('owned_removed') is True
        and result.get('input_unchanged') is True
        and result.get('snapshot_unchanged') is True
        and result.get('binary_unchanged') is True
        and state.get('Running') is False and _integer(state.get('Pid'), 0)
        and state.get('OOMKilled') is False and type(state.get('ExitCode')) is int
        and _integer(result.get('docker_wait_exit'), state['ExitCode'])
        and type(host.get('exit_code')) is int
        and type(host.get('timed_out')) is bool and type(host.get('stream_cap_exceeded')) is bool
        and type(result.get('diagnostic_process_clean')) is bool
        and host.get('readers_stopped') is True
        and type(eof) is list and len(eof) == 2 and all(value is True for value in eof)
        and host.get('stream_reader_errors') == [None, None]
        and host.get('host_error') is None and host.get('evidence_write_error') is None
        and _integer(host.get('job_active_count'), 0)
        and all(job.get(key) is True for key in ('configured', 'assigned', 'closed', 'zero_observed'))
        and all(job.get(key) is False for key in ('tainted', 'handle_retained'))
        and _integer(job.get('active_count'), 0)
        and type(job.get('failed_operations')) is list and job['failed_operations'] == []
        and 'native_error' in job and job['native_error'] is None
        and admission.get('acquired') is True and admission.get('released') is True
        and _integer(admission.get('maximum_active'), 1)
        and result.get('owner_record_retained') is False
        and type(errors) is list and errors in ([], ['EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN']))
    completed = (type(state.get('ExitCode')) is int and state['ExitCode'] == 0
        and type(host.get('exit_code')) is int and host['exit_code'] == 0
        and host.get('timed_out') is False and host.get('stream_cap_exceeded') is False)
    kind = case['expect']
    details = None
    busy_entered = stdout.splitlines().count('HH_PROBE_BUSY_ENTERED') == 1
    supervisor_watchdog = (busy_entered and host.get('timed_out') is False
        and host.get('stream_cap_exceeded') is False
        and type(state.get('ExitCode')) is int and state['ExitCode'] in (124, 137)
        and _integer(host.get('exit_code'), state['ExitCode'])
        and result.get('diagnostic_process_clean') is False)
    host_watchdog = (busy_entered and host.get('timed_out') is True
        and host.get('stream_cap_exceeded') is False
        and type(state.get('ExitCode')) is int and state['ExitCode'] != 0
        and result.get('diagnostic_process_clean') is False)
    if kind == 'clean_process':
        observed = result.get('diagnostic_process_clean') is True and completed
    elif kind == 'engine_rejection':
        observed = (result.get('diagnostic_process_clean') is False
            and type(state.get('ExitCode')) is int and state['ExitCode'] not in (0, 124, 137)
            and _integer(host.get('exit_code'), state['ExitCode'])
            and host.get('timed_out') is False and host.get('stream_cap_exceeded') is False
            and bool(re.search(r'Parse Error|SCRIPT ERROR', stdout + stderr)))
    elif kind == 'tool_callback':
        observed = completed and stdout.splitlines().count('HH_PROBE_TOOL_ENTERED') == 1
    elif kind == 'static_callback':
        observed = completed and stdout.splitlines().count('HH_PROBE_STATIC_ENTERED') == 1
    elif kind == 'boundary_observation':
        details = marker(stdout, 'HH_PROBE_BOUNDARY ')
        observed = (completed and details is not None and details.get('source_denied') is True
            and details.get('root_denied') is True and details.get('docker_socket_absent') is True
            and type(details.get('external_connect_status')) is int
            and details['external_connect_status'] != 0)
    elif kind == 'disk_observation':
        details = marker(stdout, 'HH_PROBE_TMPFS ')
        observed = (completed and details is not None and details.get('write_rejected') is True
            and type(details.get('full_files')) is int and 0 < details['full_files'] <= 16)
    elif kind == 'spawn_observation':
        details = marker(stdout, 'HH_PROBE_SPAWN ')
        observed = (completed and details is not None and _integer(details.get('exit'), -1)
            and details.get('output') == ['']
            and 'Cannot create pipe from command: "/usr/bin/printf" "HH_UNEXPECTED_CHILD"' in stderr)
    elif kind == 'guarded_play':
        details = marker(stdout, 'HH_PROBE_PLAY ')
        observed = (completed and details is not None and _integer(details.get('ticks'), 12)
            and type(details.get('x')) in (int, float) and details['x'] == 12.0
            and stderr.replace('\r\n', '\n') == GUARDED_STARTUP_ERROR)
    elif kind == 'gameplay_source':
        details = marker(stdout, 'HH_PROBE_PLAY ')
        observed = (completed and details is not None and _integer(details.get('ticks'), 12)
            and type(details.get('x')) in (int, float) and details['x'] == 12.0)
        asset_details = marker(stdout, 'HH_PROBE_ASSET_READBACK ')
        asset_import_observed = (not case.get('asset_readback')
            or (type(asset_details) is dict
                and asset_details.get('avatar_loaded') is True
                and asset_details.get('sprite_loaded') is True))
        observed = observed and asset_import_observed
    elif kind == 'fixture_state':
        details = marker(stdout, 'HH_PROBE_FIXTURE ')
        observed = (completed and type(details) is dict and bool(case.get('expected_state'))
                    and typed_equal(details, case.get('expected_state'))
                    and type(case.get('fixture_kind')) is str and physics_trace(case, stdout))
    elif kind == 'watchdog':
        observed = supervisor_watchdog
    elif kind == 'stream_cap':
        observed = (host.get('stream_cap_exceeded') is True
            and type(state.get('ExitCode')) is int and state['ExitCode'] != 0
            and result.get('diagnostic_process_clean') is False)
    elif kind == 'untrusted_marker':
        details = marker(stdout, 'HH_ENGINE_VALIDATED ')
        observed = completed and details is not None and details.get('public_ack') is True
    else:
        raise ValueError('unknown fixture expectation')
    guarded = str(case.get('mode', '')).startswith('guarded-')
    if guarded:
        observed = (observed and result.get('mode') == case.get('mode')
            and result.get('sandbox_harness_unchanged') is True
            and stdout.splitlines().count(GUARD_MARKER) == 1
            and stdout.startswith(GUARD_MARKER + '\n'))
    transcript_ok = True
    if case.get('mode') == 'gameplay-source':
        transcript_ok = gameplay_transcript(case, stdout, stderr)
        if kind == 'engine_rejection':
            # The trusted parent returns 45 only after a nonzero phase exit.
            # A crash, watchdog or banner must not impersonate this rejection.
            observed = (observed and _integer(state.get('ExitCode'), 45)
                        and _integer(host.get('exit_code'), 45))
        observed = (observed and transcript_ok
                    and result.get('mode') == 'gameplay-source'
                    and result.get('sandbox_harness_unchanged') is True
                    and result.get('gameplay_source_envelope_checked') is True
                    and result.get('gameplay_profile') == 'hh-godot-gameplay-source-1'
                    and result.get('gameplay_profile_unchanged') is True)
    return {'fixture_observed': controlled and observed, 'confinement_lifecycle_observed': controlled,
        'supervisor_binding_verified': bound,
        'supervisor_watchdog_observed': controlled and transcript_ok and kind == 'watchdog' and supervisor_watchdog,
        'host_watchdog_observed': controlled and transcript_ok and kind == 'watchdog' and host_watchdog,
        'expectation': kind, 'untrusted_child_observation': details,
        'asset_import_observed': (not case.get('asset_readback')
            or (type(marker(stdout, 'HH_PROBE_ASSET_READBACK ')) is dict
                and marker(stdout, 'HH_PROBE_ASSET_READBACK ').get('avatar_loaded') is True
                and marker(stdout, 'HH_PROBE_ASSET_READBACK ').get('sprite_loaded') is True)),
        'authority': 0,
        'public_ack': False, 'sandbox_acceptance': False,
        'validation_attribution_proven': False}


def sandbox_binding(destination: Path, case: dict, result: dict, binding: dict) -> None:
    """Recheck native command/mount against hash-bound trusted local source.

    Never execute a Python file supplied by the evidence package. Historical
    evidence stays attached to its old verifier; resume needs unchanged source.
    """
    paths = ['godot-addon/linux_executor.py', 'godot-addon/gameplay_sandbox.py']
    if case['mode'] == 'gameplay-source':
        paths.append('godot-addon/gameplay_source_profile.py')
    files = _object(binding.get('files'))
    for path in paths:
        if files.get(path) != sha(STUDIO / path):
            raise ValueError('sandbox evidence requires the matching trusted source')
    expected_guard = files['godot-addon/gameplay_sandbox.py']
    if (sha(destination / 'harness/gameplay_sandbox.py') != expected_guard
            or result.get('sandbox_bootstrap_sha256') != expected_guard):
        raise ValueError('guarded bootstrap source changed')
    executor = load('gt03_probe_bound_executor', STUDIO / 'godot-addon/linux_executor.py')
    if case['mode'] == 'gameplay-source':
        expected_profile = files['godot-addon/gameplay_source_profile.py']
        if (expected_profile != executor.GAMEPLAY_PROFILE_SHA256
                or result.get('gameplay_profile_sha256') != expected_profile
                or _object(result.get('toolchain')).get('gameplay_profile_sha256') != expected_profile):
            raise ValueError('gameplay profile source changed')
    rows = json.loads((destination / 'created-inspect-stdout.txt').read_bytes())
    if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        raise ValueError('guarded container inspect shape')
    inspected = rows[0]
    config = _object(inspected.get('Config'))
    assets = tuple(sorted(path for path in case.get('extra_binary_files', {})
                          if path in executor.ASSET_PATHS))
    host = _object(inspected.get('HostConfig'))
    expected_tmpfs = dict(executor.TMPFS)
    if assets:
        expected_tmpfs.update(executor.ASSET_TMPFS)
    mounts = inspected.get('Mounts')
    harness = ([row for row in mounts if type(row) is dict and row.get('Destination') == '/harness']
               if type(mounts) is list else [])
    mount_map = ({row.get('Destination'): row for row in mounts}
                 if type(mounts) is list and all(type(row) is dict for row in mounts) else {})
    expected_destinations = {'/tool', '/project', '/harness'} | {
        '/project/' + path for path in assets}
    expected_tool = result.get('tool_mount_source')
    if (inspected.get('Id') != result['container_id']
            or config.get('Entrypoint') != ['/usr/local/bin/python3']
            or config.get('Cmd') != executor._supervised_command(case['mode'], case['timeout'])
            or host.get('Tmpfs') != expected_tmpfs
            or type(expected_tool) is not str
            or type(mounts) is not list
            or len(mounts) != len(expected_destinations)
            or set(mount_map) != expected_destinations
            or mount_map.get('/tool', {}).get('Source') != expected_tool
            or mount_map.get('/project', {}).get('Source') != str(destination / 'snapshot')
            or any(mount_map.get(destination, {}).get('Type') != 'bind'
                   or mount_map.get(destination, {}).get('RW') is not False
                   or mount_map.get(destination, {}).get('Propagation') != 'rprivate'
                   for destination in expected_destinations)
            or len(harness) != 1
            or harness[0].get('Type') != 'bind' or harness[0].get('RW') is not False
            or harness[0].get('Propagation') != 'rprivate'
            or harness[0].get('Source') != str(destination / 'harness')
            or any('/project/' + path not in mount_map
                   or mount_map['/project/' + path].get('Type') != 'bind'
                   or mount_map['/project/' + path].get('Source') != str(destination / 'snapshot' / path)
                   or mount_map['/project/' + path].get('RW') is not False
                   or mount_map['/project/' + path].get('Propagation') != 'rprivate'
                   for path in assets)):
        raise ValueError('guarded container command/mount mismatch')


def case_files(case: dict) -> dict[str, bytes]:
    values = {path: case[key].encode('utf-8')
        for path, key in (('project.godot', 'project'), ('scenes/fixture.tscn', 'scene'),
                          ('scripts/fixture_actor.gd', 'script'))}
    extras = case.get('extra_files', {})
    if type(extras) is not dict:
        raise ValueError('fixture extra files must be a mapping')
    for path, content in extras.items():
        if (type(path) is not str or type(content) is not str or path in values
                or not re.fullmatch(r'(scenes|scripts)/[A-Za-z0-9_-]+\.(tscn|gd)', path)):
            raise ValueError('invalid fixture extra file')
        values[path] = content.encode('utf-8')
    binary_extras = case.get('extra_binary_files', {})
    if type(binary_extras) is not dict:
        raise ValueError('fixture binary files must be a mapping')
    for path, content in binary_extras.items():
        if (type(path) is not str or type(content) is not bytes or path in values
                or path not in ('assets/avatar.glb', 'assets/sprite_sheet.png')):
            raise ValueError('invalid fixture binary file')
        values[path] = content
    return values


def case_observation(destination: Path, case: dict, *, name: str, binding: dict) -> dict:
    result = json.loads((destination / 'result.json').read_text(encoding='utf-8'))
    expected = {path: hashlib.sha256(raw).hexdigest() for path, raw in case_files(case).items()}
    actual = {path: sha(destination / 'snapshot' / path) for path in expected}
    if (actual != expected or result.get('input_hashes_before') != expected
            or result.get('input_hashes_after') != expected or result.get('snapshot_hashes_after') != expected
            or result.get('mode') != case['mode']
            or not supervisor_binding(case, result)):
        raise ValueError('raw case evidence does not bind the requested input/mode/supervisor/deadline')
    if case['mode'].startswith('guarded-') or case['mode'] == 'gameplay-source':
        sandbox_binding(destination, case, result, binding)
    stdout = (destination / 'engine-stdout.txt').read_text(encoding='utf-8', errors='replace')
    stderr = (destination / 'engine-stderr.txt').read_text(encoding='utf-8', errors='replace')
    row = evaluate(case, result, stdout, stderr)
    row.update(case_name=name, run_id=binding['run_id'],
        source_closure_sha256=binding['source_closure_sha256'],
        fixture_script_sha256=hashlib.sha256(case['script'].encode('utf-8')).hexdigest(),
        mode=case['mode'], timeout_seconds=case['timeout'])
    row['artifacts'] = {p.relative_to(destination).as_posix(): sha(p)
        for p in sorted(destination.rglob('*')) if p.is_file()}
    return row


def resume_case(destination: Path, observation: Path, case: dict, *, name: str, binding: dict) -> dict:
    previous = json.loads(observation.read_text(encoding='utf-8'))
    actual = case_observation(destination, case, name=name, binding=binding)
    if previous != actual:
        raise ValueError('existing case evidence changed')
    return actual


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--cases', nargs='+')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_id):
        parser.error('invalid run ID')
    output = args.output.resolve()
    # New raw belongs in .local. Historical evidence may still be replayed in
    # its original location, without rewriting it.
    allowed = [STUDIO / '.local/reviews']
    if args.resume:
        allowed.append(STUDIO.parent / 'zdoc/reviews')
    if not any(output.is_relative_to(root) for root in allowed):
        parser.error('new evidence must be below studio/.local/reviews')
    freezer = load('gt03_linux_freezer', STUDIO / 'tests/godot/run_editor_probe.py')
    current = freezer.inputs()
    owned = load('gt03_linux_owned', STUDIO / 'build/bootstrap/run_fixture.py')
    closure = owned.source_closure_sha256(current)
    if args.resume:
        binding = json.loads((output / 'source-closure.json').read_text(encoding='utf-8'))
        if (binding['files'] != current or binding['run_id'] != args.run_id
                or binding['source_closure_sha256'] != closure):
            raise ValueError('resume requires identical source and run ID')
    else:
        output.mkdir(parents=True, exist_ok=False)
        for name, digest in current.items():
            path = output / 'source/studio' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((STUDIO / name).read_bytes())
            if sha(path) != digest:
                raise ValueError('source changed during freeze')
        binding = {'run_id': args.run_id, 'files': current,
            'source_closure_sha256': closure}
        save(output / 'source-closure.json', binding)
    source = output / 'source/studio'
    if any(sha(source / name) != digest for name, digest in current.items()):
        raise ValueError('frozen source changed')
    # The environment supplies only an installation location. The executor must
    # verify the exact pinned binary hash before and after every invocation.
    os.environ.setdefault('HH_STUDIO_LINUX_GODOT', str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64'))
    sys.path.insert(0, str(source.parent))
    fixtures = load('gt03_linux_fixtures', source / 'tests/godot/linux_probe_fixtures.py')
    executor = load('gt03_linux_executor', source / 'godot-addon/linux_executor.py')
    cases = list(fixtures.FIXTURES) if args.cases is None else args.cases
    if len(set(cases)) != len(cases) or not set(cases) <= set(fixtures.FIXTURES):
        parser.error('duplicate or unknown case')
    results = {}
    for name in cases:
        project_template = (executor._gameplay_profile().PROJECT_TEMPLATE
                            if fixtures.FIXTURES[name]['mode'] == 'gameplay-source'
                            else executor.PROJECT_TEMPLATE)
        case = {**fixtures.FIXTURES[name], 'scene': fixtures.SCENE, 'project': project_template}
        destination = output / name
        observation = output / (name + '-observation.json')
        if observation.exists():
            # Never trust saved booleans or a caller-shortened artifact map.
            # Re-evaluate raw host observations, bind this exact fixture/source,
            # and require the complete current artifact inventory byte-for-byte.
            results[name] = resume_case(destination, observation, case, name=name, binding=binding)
            continue
        if destination.exists():
            raise ValueError('incomplete run retained; inspect owned container before a new attempt')
        project = output / 'inputs' / name
        (project / 'scenes').mkdir(parents=True, exist_ok=False)
        (project / 'scripts').mkdir()
        (project / '.godot').mkdir()
        for path, raw in case_files(case).items():
            (project / path).write_bytes(raw)
        result = executor.run(project, mode=case['mode'], output=destination, timeout_seconds=case['timeout'])
        row = case_observation(destination, case, name=name, binding=binding)
        save(observation, row)
        results[name] = row
        print(json.dumps({'case': name, 'fixture_observed': row['fixture_observed']}), flush=True)
    unchanged = current == freezer.inputs() and all(sha(source / n) == h for n, h in current.items())
    summary = {'run_id': args.run_id, 'source_closure_sha256': binding['source_closure_sha256'],
        'cases': results, 'source_unchanged': unchanged, 'sandbox_acceptance': False, 'public_ack': False,
        'authority': 0, 'validation_attribution_proven': False,
        'selected_fixtures_observed': unchanged and all(row['fixture_observed'] for row in results.values())}
    save(output / 'capture.json', summary)
    return 0 if summary['selected_fixtures_observed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
