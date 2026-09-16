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
    host = result.get('command_host') or {}
    state = result.get('container_state') or {}
    controlled = (result.get('public_ack') is False
        and result.get('sandbox_acceptance') is False
        and result.get('owned_removed') is True
        and result.get('input_unchanged') is True
        and result.get('snapshot_unchanged') is True
        and result.get('binary_unchanged') is True
        and state.get('Running') is False and type(state.get('Pid')) is int and state['Pid'] == 0
        and host.get('readers_stopped') is True
        and type(host.get('job_active_count')) is int and host['job_active_count'] == 0)
    completed = (type(state.get('ExitCode')) is int and state['ExitCode'] == 0
        and type(host.get('exit_code')) is int and host['exit_code'] == 0
        and host.get('timed_out') is False and host.get('stream_cap_exceeded') is False)
    kind = case['expect']
    details = None
    if kind == 'clean_process':
        observed = result.get('diagnostic_process_clean') is True and completed
    elif kind == 'engine_rejection':
        observed = (result.get('diagnostic_process_clean') is False
            and type(state.get('ExitCode')) is int and state['ExitCode'] != 0
            and host.get('timed_out') is False and host.get('stream_cap_exceeded') is False
            and bool(re.search(r'Parse Error|SCRIPT ERROR', stdout + stderr)))
    elif kind == 'tool_callback':
        observed = completed and stdout.splitlines().count('HH_PROBE_TOOL_ENTERED') == 1
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
        observed = (host.get('timed_out') is True and stdout.splitlines().count('HH_PROBE_BUSY_ENTERED') == 1
            and type(state.get('ExitCode')) is int and state['ExitCode'] != 0
            and result.get('diagnostic_process_clean') is False)
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
            or result.get('mode') != case['mode']
            or (result.get('command_host') or {}).get('timeout_seconds') != case['timeout']):
        raise ValueError('raw case evidence does not bind the requested input/mode/deadline')
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
