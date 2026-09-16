"""Frozen, resumable diagnostic fixtures for the confined Linux Godot process.

Observed child markers prove only that a fixture ran. They cannot prove the
truth of a publication validation report emitted from the same process.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
SUPERVISOR_SHA256 = '5ef0eaaaa4220593add7716aad74da927ca3bb10605e964330de64fecc3ef15e'
SUPERVISOR_BOOTSTRAP_SHA256 = '0194f9d31f6f8abaa8a33cc8c412075efa198546c2f187599ee023bd6be5c377'
DOCKER_CONTEXT = 'desktop-linux'
DOCKER_ENDPOINT = 'npipe:////./pipe/dockerDesktopLinuxEngine'


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
    return {'fixture_observed': controlled and observed, 'confinement_lifecycle_observed': controlled,
        'supervisor_binding_verified': bound,
        'supervisor_watchdog_observed': controlled and kind == 'watchdog' and supervisor_watchdog,
        'host_watchdog_observed': controlled and kind == 'watchdog' and host_watchdog,
        'expectation': kind, 'untrusted_child_observation': details,
        'public_ack': False, 'sandbox_acceptance': False,
        'validation_attribution_proven': False}


def case_observation(destination: Path, case: dict, *, name: str, binding: dict) -> dict:
    result = json.loads((destination / 'result.json').read_text(encoding='utf-8'))
    expected = {path: hashlib.sha256(case[key].encode('utf-8')).hexdigest()
        for path, key in (('project.godot', 'project'), ('scenes/fixture.tscn', 'scene'),
                          ('scripts/fixture_actor.gd', 'script'))}
    actual = {path: sha(destination / 'snapshot' / path) for path in expected}
    if (actual != expected or result.get('input_hashes_before') != expected
            or result.get('input_hashes_after') != expected or result.get('snapshot_hashes_after') != expected
            or result.get('mode') != case['mode']
            or not supervisor_binding(case, result)):
        raise ValueError('raw case evidence does not bind the requested input/mode/supervisor/deadline')
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
    output.relative_to(STUDIO.parent / 'zdoc/reviews')
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
    os.environ['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    sys.path.insert(0, str(source.parent))
    fixtures = load('gt03_linux_fixtures', source / 'tests/godot/linux_probe_fixtures.py')
    executor = load('gt03_linux_executor', source / 'godot-addon/linux_executor.py')
    cases = list(fixtures.FIXTURES) if args.cases is None else args.cases
    if len(set(cases)) != len(cases) or not set(cases) <= set(fixtures.FIXTURES):
        parser.error('duplicate or unknown case')
    results = {}
    for name in cases:
        case = {**fixtures.FIXTURES[name], 'scene': fixtures.SCENE, 'project': executor.PROJECT_TEMPLATE}
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
        (project / 'project.godot').write_text(executor.PROJECT_TEMPLATE, encoding='utf-8', newline='\n')
        (project / 'scenes/fixture.tscn').write_text(fixtures.SCENE, encoding='utf-8', newline='\n')
        (project / 'scripts/fixture_actor.gd').write_text(case['script'], encoding='utf-8', newline='\n')
        result = executor.run(project, mode=case['mode'], output=destination, timeout_seconds=case['timeout'])
        row = case_observation(destination, case, name=name, binding=binding)
        save(observation, row)
        results[name] = row
        print(json.dumps({'case': name, 'fixture_observed': row['fixture_observed']}), flush=True)
    unchanged = current == freezer.inputs() and all(sha(source / n) == h for n, h in current.items())
    summary = {'run_id': args.run_id, 'source_closure_sha256': binding['source_closure_sha256'],
        'cases': results, 'source_unchanged': unchanged, 'sandbox_acceptance': False, 'public_ack': False,
        'validation_attribution_proven': False,
        'selected_fixtures_observed': unchanged and all(row['fixture_observed'] for row in results.values())}
    save(output / 'capture.json', summary)
    return 0 if summary['selected_fixtures_observed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
