"""S49 diagnostic evidence consistency audit. AUTHORITY=0; acceptance is false.

No engine/daemon calls. Raw host captures remain host evidence, not authenticated
public receipts. Recompute semantic readback from the complete frozen comparator.
"""
from __future__ import annotations

import hashlib
import datetime
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
STUDIO = ROOT / 'studio'
PACKAGE = AUDIT.parent / '20260917-gt03-s49-editor-01'
LINUX = AUDIT.parent / '20260917-gt03-s49-linux-01'
PROFILE = AUDIT.parent / '20260917-gt03-s49-profile-02'
HOST_DEATH = AUDIT.parent / '20260917-gt03-s49-host-death-01'
# Filled only after the coordinator supplies actual captured counts.
EXPECTED_TESTS = 321
EXPECTED_ENGINE_CHECKS = {'edit': 103, 'reopen': 10, 'contract': 31}
PROFILE_CASES = ('defaults_override', 'transformed_box', 'typed_scene_override',
                 'tiny_export', 'nested_node')
HEX = re.compile(r'[0-9a-f]{64}\Z')
BAD_LOG = re.compile(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, expected=None):
    return type(value) is int and (expected is None or value == expected)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return digest(path.read_bytes())


def pairs(rows):
    value = {}
    for key, item in rows:
        need(key not in value, 'duplicate JSON key: ' + key)
        value[key] = item
    return value


def parse(raw):
    def invalid(value):
        raise ValueError('nonfinite JSON: ' + value)
    def finite(value):
        number = float(value)
        need(math.isfinite(number), 'nonfinite JSON number')
        return number
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)


def read(path):
    return parse(path.read_text(encoding='utf-8', errors='strict'))


def exact(left, right):
    """Unlike Python ==, retain bool/int and int/float distinctions in JSON."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def relative(name):
    need(type(name) is str and name and '\\' not in name and ':' not in name
         and '\n' not in name and '\r' not in name, 'invalid relative evidence name')
    path = PurePosixPath(name)
    need(not path.is_absolute() and path.as_posix() == name
         and all(part not in ('.', '..') and not part.endswith((' ', '.')) for part in path.parts),
         'aliased relative evidence name: ' + name)
    return name


def inside(base, name):
    path = base / relative(name)
    need(path.resolve().is_relative_to(base.resolve()), 'evidence escaped root')
    current = path
    while current != base:
        info = current.stat(follow_symlinks=False)
        need(not current.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'evidence reparse path: ' + str(current))
        current = current.parent
    return path


def inventory(directory):
    need(directory.is_dir(), 'missing evidence directory: ' + str(directory))
    result = {}
    for path in sorted(directory.rglob('*')):
        name = path.relative_to(directory).as_posix()
        inside(directory, name)
        if path.is_file():
            result[name] = sha(path)
    return result


def hash_map(value):
    need(type(value) is dict and value, 'empty or invalid hash map')
    folded = set()
    for name, value_ in value.items():
        relative(name)
        need(name.casefold() not in folded, 'case-aliased file path')
        folded.add(name.casefold())
        need(type(value_) is str and HEX.fullmatch(value_), 'invalid file digest: ' + name)
    return value


def module(name, path):
    # Compile the verified bytes directly: an unrelated .pyc must not override it.
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    exec(compile(path.read_bytes(), str(path), 'exec'), value.__dict__)
    return value


def markers(text, prefix):
    return [parse(line[len(prefix):]) for line in text.splitlines() if line.startswith(prefix)]


def host(base, value):
    captured = read(inside(base, value['host']))
    need(integer(captured.get('target_pid')) and captured['target_pid'] > 0, 'missing actual child PID')
    need(all(integer(row, 0) for row in (captured.get('exit_code'), value.get('exit_code'),
                                       value.get('wrapper_exit_code'))), 'actual host exit mismatch')
    need(integer(value.get('target_pid'), captured['target_pid'])
         and integer(value.get('wrapper_pid')) and value['wrapper_pid'] > 0, 'host PID mismatch')
    need(value.get('timed_out') is False and value.get('tree_verified') is True
         and value.get('ownership') == 'gated_job_kill_on_close', 'unclean Windows process ownership')
    need(type(captured.get('started_at')) is str and captured['started_at'], 'missing target start time')
    return tuple(inside(base, value[key]).read_text(encoding='utf-8', errors='strict')
                 for key in ('stdout', 'stderr'))


def source_copy(package, files, closure):
    manifest = read(package / 'source-closure.json')
    need(exact(manifest.get('files'), files) and manifest.get('source_closure_sha256') == closure,
         'complete source closures differ: ' + package.name)
    source = package / 'source/studio'
    need(inventory(source) == files, 'frozen source inventory/bytes differ: ' + package.name)
    return source, manifest


def cli(base, label, executor, *, args=None, exit_code=0, engine=False):
    row = read(base / (label + '-host.json'))
    need(row.get('stdout') == label + '-stdout.txt' and row.get('stderr') == label + '-stderr.txt',
         'CLI stream path substitution: ' + label)
    if args is not None:
        need(row.get('argv') == ['docker.exe', '--context', 'desktop-linux', *args], 'CLI argv: ' + label)
    counts, cap = row.get('stream_byte_counts'), row.get('stream_cap_bytes_each')
    need(integer(cap) and 0 < cap <= 262144 and type(counts) is list and len(counts) == 2
         and all(integer(item) and item >= 0 for item in counts), 'CLI byte counters: ' + label)
    for index, key in enumerate(('stdout', 'stderr')):
        need(inside(base, row[key]).stat().st_size == min(counts[index], cap), 'CLI captured length: ' + label)
    need(row.get('stream_cap_exceeded') is any(item > cap for item in counts), 'CLI cap flag mismatch')
    # A deliberate flood can exceed the capture cap. It still must release the
    # checked Job and readers; only exit/cap/timeout vary for the engine call.
    normalized = dict(row)
    if engine:
        need(integer(row.get('exit_code')) and type(row.get('timed_out')) is bool, 'missing engine actual exit')
        normalized.update(exit_code=0, timed_out=False, stream_cap_exceeded=False)
    need(executor._cli_done(normalized, 0 if engine else exit_code), 'CLI lifecycle/checked CloseHandle: ' + label)
    return row


def one_inspect(base, label):
    rows = read(base / (label + '-stdout.txt'))
    need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, 'invalid raw inspect: ' + label)
    return rows[0]


def verify_executor(base, executor, probe, *, mode, timeout, inputs):
    result = read(base / 'result.json')
    need(result.get('schema') == 'hh-gt03-linux-diagnostic-1' and result.get('mode') == mode, 'wrong executor mode')
    for key in ('public_ack', 'sandbox_acceptance', 'owner_record_retained'):
        need(result.get(key) is False, 'executor overclaim/owner retained: ' + key)
    for key in ('owned_removed', 'input_unchanged', 'snapshot_unchanged', 'binary_unchanged'):
        need(result.get(key) is True, 'executor missing fact: ' + key)
    admission = result.get('admission', {})
    need(admission.get('acquired') is True and admission.get('released') is True
         and integer(admission.get('maximum_active'), 1), 'admission lifecycle')
    expected = {name: digest(raw) for name, raw in inputs.items()}
    need(read(base / 'input-manifest.json') == expected, 'raw executor input manifest')
    for key in ('input_hashes_before', 'input_hashes_after', 'snapshot_hashes_after'):
        need(result.get(key) == expected, 'executor candidate hashes: ' + key)
    need(inventory(base / 'snapshot') == expected, 'executor full readonly snapshot bytes')
    need(probe.supervisor_binding({'timeout': timeout}, result), 'missing exact PID1 supervisor binding')
    lock = read(Path(executor.__file__).with_name('validator-toolchain.lock.json'))
    need(exact(result.get('toolchain'), lock), 'executor toolchain does not equal frozen lock')
    tool = STUDIO / '.local/tooling/godot-4.7.2-stable-linux'
    need(inventory(tool) == {lock['binary_name']: lock['binary_sha256']}, 'tool mount is not exact pinned binary')
    cid, name = result['container_id'], result['run_id']
    args = executor._create_args(name, mode, tool, base / 'snapshot', timeout)
    need(read(base / 'create-argv.json') == args, 'raw create argv differs from fixed policy')
    cli(base, 'context', executor, args=['context', 'inspect', 'desktop-linux', '--format', '{{json .Endpoints.docker.Host}}'])
    need(read(base / 'context-stdout.txt') == lock['docker_endpoint'], 'wrong daemon endpoint')
    cli(base, 'image', executor, args=['image', 'inspect', lock['image_id']])
    image = one_inspect(base, 'image')
    need(image.get('Id') == lock['image_id'] and image.get('Os') == 'linux'
         and image.get('Architecture') == 'amd64' and not image.get('Config', {}).get('Volumes'), 'raw image identity')
    env = image['Config']['Env']
    need(len(env) == 5 and {item.split('=', 1)[0] for item in env}
         == {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256'}, 'image environment')
    cli(base, 'create', executor, args=args)
    need((base / 'create-stdout.txt').read_text(encoding='ascii').strip() == cid, 'raw created ID')
    cli(base, 'created-inspect', executor, args=['inspect', cid])
    created = one_inspect(base, 'created-inspect')
    executor._validate_inspect(created, name=name, container_id=cid, mode=mode,
        tool=tool, snapshot=base / 'snapshot', image_environment=env, timeout_seconds=timeout)
    # Initial and final daemon states are distinct evidence, not result aliases.
    need(created['State'].get('Running') is False and integer(created['State'].get('Pid'), 0), 'container was already running at create')
    raw_host = cli(base, 'engine', executor, args=['start', '--attach', cid], engine=True)
    need(exact(raw_host, result.get('command_host')) and exact(raw_host, result.get('commandhost')), 'raw engine host differs')
    need(result.get('stdout') == raw_host['stdout'] and result.get('stderr') == raw_host['stderr'], 'engine stream alias')
    for label in ('after-command-inspect', 'exited-inspect', 'cleanup-inspect'):
        cli(base, label, executor, args=['inspect', cid])
        need(executor._owned_identity(one_inspect(base, label), name, cid), 'native identity changed: ' + label)
    final_label = 'cleanup-exited-inspect' if (base / 'cleanup-exited-inspect-host.json').exists() else 'cleanup-inspect'
    if final_label != 'cleanup-inspect':
        cli(base, final_label, executor, args=['inspect', cid])
    final = one_inspect(base, final_label)
    need(executor._owned_identity(final, name, cid), 'final native identity')
    state = final['State']
    need(exact(state, result.get('state')) and exact(state, result.get('container_state')), 'actual final state differs')
    need(state.get('Running') is False and integer(state.get('Pid'), 0)
         and state.get('OOMKilled') is False and integer(state.get('ExitCode')), 'native container not cleanly stopped')
    cli(base, 'wait', executor, args=['wait', cid])
    wait_text = (base / 'wait-stdout.txt').read_text(encoding='ascii').strip()
    need(re.fullmatch(r'\d+', wait_text) and integer(result.get('docker_wait_exit'), int(wait_text))
         and int(wait_text) == state['ExitCode'], 'raw native wait/exit mismatch')
    cli(base, 'owned-remove', executor, args=['rm', cid])
    cli(base, 'removed-inspect', executor, args=['inspect', cid], exit_code=1)
    gone = (base / 'removed-inspect-stderr.txt').read_text(encoding='utf-8').lower()
    need('no such object: ' + cid in gone, 'no exact removed-ID observation')
    # Validate every auxiliary CLI cleanup/admission record, including optional
    # kills/reconciliation; unexpected unfinished native owners cannot disappear.
    for path in base.glob('*-host.json'):
        label = path.name.removesuffix('-host.json')
        if label == 'engine':
            continue
        row = read(path)
        allowed_exit = 1 if label in ('removed-inspect', 'admission-owner-missing') else 0
        if label == 'admission-owner-inspect':
            allowed_exit = row.get('exit_code')
            need(integer(allowed_exit) and allowed_exit in (0, 1), 'admission inspect exit')
        cli(base, label, executor, exit_code=allowed_exit)
    if mode == 'profile-validate':
        helper_hash = sha(Path(executor.__file__).with_name('validation_bootstrap.gd'))
        need(inventory(base / 'harness') == {'validation_bootstrap.gd': helper_hash}
             and result.get('profile_harness_sha256') == helper_hash
             and result.get('profile_harness_unchanged') is True
             and result.get('profile_eligible') is True, 'readonly fixed helper bytes')
    return result


def verify_linux(files, closure):
    source, manifest = source_copy(LINUX, files, closure)
    probe = module('s49_frozen_linux_probe', source / 'tests/godot/run_linux_probe.py')
    fixtures = module('s49_frozen_linux_fixtures', source / 'tests/godot/linux_probe_fixtures.py')
    executor = module('s49_frozen_linux_executor', source / 'godot-addon/linux_executor.py')
    capture = read(LINUX / 'capture.json')
    need(capture.get('source_closure_sha256') == closure and capture.get('source_unchanged') is True,
         'Linux capture source mismatch')
    need(set(capture['cases']) == set(fixtures.FIXTURES) and len(capture['cases']) == 11, 'Linux fixture omitted')
    need(capture.get('selected_fixtures_observed') is True, 'Linux fixture summary failed')
    for flag in ('sandbox_acceptance', 'public_ack', 'validation_attribution_proven'):
        need(capture.get(flag) is False, 'Linux diagnostic overclaims acceptance')
    for name, fixture in fixtures.FIXTURES.items():
        case = {**fixture, 'scene': fixtures.SCENE, 'project': executor.PROJECT_TEMPLATE}
        inputs = {'project.godot': case['project'], 'scenes/fixture.tscn': case['scene'],
                  'scripts/fixture_actor.gd': case['script']}
        inputs = {key: value.encode('utf-8') if type(value) is str else value for key, value in inputs.items()}
        need(inventory(LINUX / 'inputs' / name) == {key: digest(value) for key, value in inputs.items()}, 'Linux raw input bytes')
        verify_executor(LINUX / name, executor, probe, mode=case['mode'], timeout=case['timeout'], inputs=inputs)
        observed = probe.resume_case(LINUX / name, LINUX / (name + '-observation.json'), case, name=name, binding=manifest)
        need(exact(observed, capture['cases'][name]) and observed.get('fixture_observed') is True,
             'Linux raw diagnostic expectation failed: ' + name)
    return {'fixtures': 11, 'public_ack': False, 'sandbox_acceptance': False,
            'validation_attribution_proven': False}


def verify_profile(files, closure):
    source, _ = source_copy(PROFILE, files, closure)
    probe = module('s49_frozen_profile_probe', source / 'tests/godot/run_profile_probe.py')
    comparator = module('s49_frozen_profile_comparator', source / 'godot-addon/profile_readback.py')
    executor = module('s49_frozen_profile_executor', source / 'godot-addon/linux_executor.py')
    linux_probe = module('s49_profile_linux_binding', source / 'tests/godot/run_linux_probe.py')
    factory = comparator.factory
    capture = read(PROFILE / 'capture.json')
    need(capture.get('source_closure_sha256') == closure, 'profile capture source mismatch')
    for flag in ('passed', 'source_unchanged', 'snapshot_unchanged'):
        need(capture.get(flag) is True, 'profile capture missing fact: ' + flag)
    for flag in ('public_ack', 'sandbox_acceptance', 'production_save_verified'):
        need(capture.get(flag) is False, 'profile diagnostic overclaim')
    stdout, stderr = host(PROFILE, capture['host'])
    need(not BAD_LOG.search(stdout + '\n' + stderr), 'unclean profile host streams')
    cases = probe.cases(factory)
    need(tuple(row[0] for row in cases) == PROFILE_CASES, 'profile coverage changed')
    rows = []
    for name, scene, script in cases:
        destination = PROFILE / name
        raw_files = {path: inside(destination / 'input', path).read_bytes() for path in factory.bundle_codec.PATHS}
        need(inventory(destination / 'input') == {key: digest(value) for key, value in raw_files.items()}, 'profile extra input file')
        bundle = factory.bundle_codec.decode_bundle((destination / 'manifest.json').read_bytes(), raw_files)
        factory.qualify(bundle)
        expected = factory.compose(scene, script, scene_revision='sha256:' + digest(scene), engine_sha256=executor.BINARY_SHA256)
        need(bundle.manifest_bytes == expected.manifest_bytes and dict(bundle.files) == dict(expected.files),
             'profile candidate differs from exact frozen case: ' + name)
        result = verify_executor(destination / 'executor', executor, linux_probe,
                                 mode='profile-validate', timeout=20, inputs=raw_files)
        raw_stdout = (destination / 'executor/engine-stdout.txt').read_text(encoding='utf-8', errors='strict')
        raw_stderr = (destination / 'executor/engine-stderr.txt').read_text(encoding='utf-8', errors='strict')
        verdict = probe.evaluate(result, raw_stdout, raw_stderr, bundle, comparator)
        need(verdict.get('passed') is True and exact(verdict, read(destination / 'comparison.json')),
             'raw phase/UID/hash/native full-state comparison failed: ' + name)
        rows.append({'case': name, 'passed': True, 'project_revision': bundle.project_revision})
    expected_summary = {'passed': True, 'cases': rows, 'public_ack': False, 'sandbox_acceptance': False}
    need(exact(read(PROFILE / 'profile-cases.json'), expected_summary)
         and exact(capture.get('cases'), expected_summary), 'profile summary differs from recomputation')
    need(exact(markers(stdout, 'HH_PROFILE_CASE '), rows), 'actual profile host markers differ')
    return {'cases': rows, 'public_ack': False, 'sandbox_acceptance': False}


def verify_host_death(files, closure, source):
    capture = read(HOST_DEATH / 'capture.json')
    invocation = read(HOST_DEATH / 'invocation.json')
    for value in (capture, invocation):
        need(value.get('source_closure_sha256') == closure and value.get('source_files') == files,
             'host-death complete source binding')
    for key, path in (('probe_sha256', AUDIT / 'probe_host_death.py'),
                      ('capture_script_sha256', AUDIT / 'run_host_death.py'),
                      ('runner_sha256', source / 'build/bootstrap/run_fixture.py')):
        need(invocation.get(key) == sha(path), 'host-death probe source changed: ' + key)
    for key in ('passed', 'snapshot_unchanged', 'source_unchanged'):
        need(capture.get(key) is True, 'host-death missing capture fact: ' + key)
    need(capture.get('public_ack') is False and capture.get('sandbox_acceptance') is False, 'host-death overclaim')
    stdout, stderr = host(HOST_DEATH, capture['host'])
    need(not stderr.strip(), 'host-death wrapper stderr')
    base = HOST_DEATH / 'probe'
    result = read(base / 'probe-result.json')
    need(exact(capture.get('result'), result) and result.get('observed') is True, 'host-death raw report mismatch')
    need(result.get('public_ack') is False and result.get('sandbox_acceptance') is False, 'host-death result overclaim')
    for key, name in (('source_executor_sha256', 'godot-addon/linux_executor.py'),
                      ('source_cli_job_sha256', 'godot-addon/cli_job.py')):
        need(result.get(key) == files[name], 'host-death executed source hash')
    executor = module('s49_death_executor', source / 'godot-addon/linux_executor.py')
    probe = module('s49_death_linux_probe', source / 'tests/godot/run_linux_probe.py')
    owner = result['owner_before_death']; cid, name = owner['container_id'], owner['name']
    need(owner.get('schema') == 'hh-linux-owner-1' and owner.get('context') == executor.EXECUTOR_CONTEXT
         and owner.get('image') == executor.IMAGE_ID and owner.get('phase') == 'start_pending'
         and integer(owner.get('host_pid')) and owner['host_pid'] > 0, 'host-death owner identity')
    need(integer(result.get('host_actual_exit'), 2) and integer(result.get('host_job_active_count'), 0), 'host was not terminated/zero')
    job = result.get('host_job_owner', {})
    need(all(job.get(key) is True for key in ('configured', 'assigned', 'closed', 'zero_observed'))
         and all(job.get(key) is False for key in ('tainted', 'handle_retained'))
         and integer(job.get('active_count'), 0) and job.get('failed_operations') == []
         and 'native_error' in job and job['native_error'] is None, 'killed host Job not checked closed')
    initial = []
    for path in sorted(base.glob('running-inspect-*-stdout.txt')):
        label = path.name.removesuffix('-stdout.txt')
        cli(base, label, executor, args=['inspect', cid])
        value = one_inspect(base, label)
        need(executor._owned_identity(value, name, cid), 'initial host-death native identity')
        initial.append(value['State'])
    need(initial and exact(initial[-1], result.get('initial_state')), 'initial running state lacks raw inspect')
    for key, label in (('after_host_death_state', 'after-host-death-inspect'), ('orphan_state', 'orphan-exited-inspect')):
        cli(base, label, executor, args=['inspect', cid])
        value = one_inspect(base, label)
        need(executor._owned_identity(value, name, cid) and exact(value['State'], result.get(key)), 'raw orphan identity/state mismatch')
    for state in (initial[-1], result['after_host_death_state']):
        need(state.get('Running') is True and integer(state.get('Pid')) and state['Pid'] > 0
             and state.get('OOMKilled') is False, 'orphan not observed running')
    state = result['orphan_state']; native_exit = state.get('ExitCode')
    need(integer(native_exit) and native_exit in (124, 137) and state.get('Running') is False
         and integer(state.get('Pid'), 0) and state.get('OOMKilled') is False, 'orphan PID1 timeout not observed')
    observed = cli(base, 'orphan-attach', executor, args=['attach', '--no-stdin', '--sig-proxy=false', cid], exit_code=native_exit)
    need(exact(observed, result.get('observer_host')), 'orphan observer raw host differs')
    marker = 'S49_IDLE_BODY_AFTER_HOST_DEATH'
    body = (base / 'orphan-attach-stdout.txt').read_text(encoding='utf-8')
    need(body.splitlines().count(marker) == 1 and result.get('child_body_observed') is True, 'orphan child body missing/duplicated')
    stamp = lambda text: datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))
    started, finished, killed = map(stamp, (state['StartedAt'], state['FinishedAt'], result['host_killed_at_utc']))
    lifetime = (finished - started).total_seconds()
    need(started < killed < finished and 0 < lifetime <= 10
         and type(result.get('container_lifetime_seconds')) is float
         and lifetime == result['container_lifetime_seconds'], 'host-death raw deadline timestamps')
    # Bind the killed invocation's actual readonly policy and the exact idle body.
    original = base / 'host-run'
    idle_script = ('extends Node3D\nstatic func _static_init() -> void:\n\tOS.delay_msec(3000)\n'
                   '\tprint("S49_IDLE_BODY_AFTER_HOST_DEATH")\n\twhile true:\n\t\tOS.delay_msec(100)\n').replace('\n', '\r\n').encode()
    scene = '[gd_scene format=3]\n[node name="Fixture" type="Node3D"]\n'.replace('\n', '\r\n').encode()
    idle = {'project.godot': executor.PROJECT_TEMPLATE.encode(), 'scenes/fixture.tscn': scene,
            'scripts/fixture_actor.gd': idle_script}
    expected_idle = {key: digest(raw) for key, raw in idle.items()}
    need(inventory(base / 'idle') == inventory(original / 'snapshot') == expected_idle
         and read(original / 'input-manifest.json') == expected_idle, 'host-death idle input bytes')
    tool = STUDIO / '.local/tooling/godot-4.7.2-stable-linux'
    args = executor._create_args(name, 'parse', tool, original / 'snapshot', 8)
    need(read(original / 'create-argv.json') == args, 'host-death supervisor create argv')
    cli(original, 'create', executor, args=args)
    need((original / 'create-stdout.txt').read_text().strip() == cid, 'host-death created ID')
    cli(original, 'created-inspect', executor, args=['inspect', cid])
    executor._validate_inspect(one_inspect(original, 'created-inspect'), name=name, container_id=cid,
        mode='parse', tool=tool, snapshot=original / 'snapshot', timeout_seconds=8,
        image_environment=one_inspect(original, 'image')['Config']['Env'])
    concurrent = read(base / 'concurrent-run/result.json')
    need(exact(concurrent, result.get('concurrent_result')) and concurrent.get('errors') == ['EXECUTOR_ADMISSION_BUSY']
         and concurrent.get('container_id') is None and concurrent.get('command_host') is None
         and concurrent.get('admission', {}).get('acquired') is False, 'concurrent request was not denied before effect')
    need(not list((base / 'concurrent-run').glob('*-host.json')), 'concurrent busy request invoked native CLI')
    valid = dict(idle); valid['scripts/fixture_actor.gd'] = b'extends Node3D\r\n'
    expected_valid = {key: digest(raw) for key, raw in valid.items()}
    need(inventory(base / 'valid') == inventory(base / 'concurrent-run/snapshot') == expected_valid, 'concurrent input bytes')
    recovery = verify_executor(base / 'recovery-run', executor, probe, mode='parse', timeout=8, inputs=valid)
    need(exact(recovery, result.get('recovery_result')) and recovery.get('diagnostic_process_clean') is True, 'host-death recovery raw run differs')
    recovered = recovery['admission']['recovery']
    need(exact(recovered.get('previous_owner'), owner) and recovered.get('removed') is True
         and recovered.get('reconciled') is True and exact(recovered.get('state'), state), 'wrong orphan recovered')
    for label, args_, code in (('admission-owner-inspect', ['inspect', cid], 0),
                               ('admission-owner-remove', ['rm', cid], 0),
                               ('admission-owner-missing', ['inspect', cid], 1)):
        cli(base / 'recovery-run', label, executor, args=args_, exit_code=code)
    need('no such object: ' + cid in (base / 'recovery-run/admission-owner-missing-stderr.txt').read_text().lower(), 'old orphan removal unproven')
    expected_marker = {'observed': True, 'container_lifetime_seconds': lifetime,
                       'child_body_observed': True, 'host_job_active_count': 0}
    need(exact([parse(line) for line in stdout.splitlines() if line.strip()], [expected_marker]), 'host-death outer actual marker')
    return {'observed': True, 'native_exit': native_exit, 'container_lifetime_seconds': lifetime,
            'public_ack': False, 'sandbox_acceptance': False}


def verify_editor(source, files, closure):
    checks = module('s49_frozen_checks', source / 'tests/godot/evidence_checks.py')
    capture = read(PACKAGE / 'capture.json')
    need(capture.get('source_closure_sha256') == closure, 'editor capture closure mismatch')
    for flag in ('passed', 'source_unchanged', 'snapshot_unchanged', 'binary_unchanged', 'temporary_removed'):
        need(capture.get(flag) is True, 'editor flag not true: ' + flag)
    for flag in ('production_save_verified', 'hostile_script_sandbox_verified'):
        need(capture.get(flag) is False, 'unsupported editor scope: ' + flag)
    lock = read(source / 'toolchain.lock.json')['godot']
    need(capture.get('godot_sha256') == lock['gui_sha256'], 'unlocked Windows engine')
    unit = capture['unit']
    need(unit.get('passed') is True, 'unit summary did not pass')
    stdout, stderr = host(PACKAGE, unit['host'])
    counts = unit['counts']
    need(exact(markers(stdout, 'GT03_UNIT_COMPLETE '), [counts]), 'unit raw marker differs')
    need(integer(EXPECTED_TESTS) and EXPECTED_TESTS > 0 and integer(counts.get('run'), EXPECTED_TESTS)
         and all(integer(counts.get(key), 0) for key in ('failures', 'errors', 'skips')), 'actual expected unit counts not established/mismatch')
    need(re.findall(r'Ran (\d+) tests? in ', stderr) == [str(EXPECTED_TESTS)] and stderr.rstrip().endswith('OK'), 'unittest raw completion')
    need([lane['mode'] for lane in capture['lanes']] == ['edit', 'reopen', 'contract'], 'engine lane missing')
    # Rebuild every executable byte from the frozen runner's documented fixture.
    # The diagnostic plugin.cfg replacement is deliberate and also bound here.
    expected = {}
    addon = source / 'godot-addon/addons/hh_studio'
    for path in addon.rglob('*'):
        if path.is_file() and path.suffix in ('.gd', '.cfg', '.godot'):
            raw = path.read_bytes()
            if path.name == 'plugin.cfg':
                raw = path.read_text(encoding='utf-8').replace('script="plugin.gd"', 'script="diagnostic_plugin.gd"').replace('\n', '\r\n').encode('utf-8')
            expected['addons/hh_studio/' + path.relative_to(addon).as_posix()] = digest(raw)
    for runtime, frozen in {'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
                            'addons/hh_studio/diagnostic_plugin.gd': 'tests/godot/diagnostic_plugin.gd',
                            'tests/editor_probe.gd': 'tests/godot/editor_probe.gd'}.items():
        expected[runtime] = files[frozen]
    script = b'extends Node3D\n@export var fixture_value: int = 7\n'
    project = (b'config_version=5\n[application]\nconfig/name="HH GT03 trusted editor fixture"\n'
               b'[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
               b'[editor_plugins]\nenabled=PackedStringArray("res://addons/hh_studio/plugin.cfg")\n')
    expected.update({'scripts/fixture_actor.gd': digest(script.replace(b'\n', b'\r\n')),
                     'project.godot': digest(project.replace(b'\n', b'\r\n'))})
    need(read(PACKAGE / 'executed-inputs.json') == expected, 'all executed editor inputs must match frozen fixture')
    fixture = read(PACKAGE / 'fixture-inputs.json')
    need(all(fixture.get(name) == value for name, value in expected.items()), 'initial fixture input differs')
    results = {}
    for lane in capture['lanes']:
        mode = lane['mode']
        streams = host(PACKAGE, lane['host'])
        need(lane['host'].get('argv') == [lock['gui_executable'], '--headless', '--editor', '--path', '$SNAPSHOT/.',
             '--log-file', '$SNAPSHOT/' + mode + '-engine.log', 'res://scenes/fixture.tscn', '--',
             '--hh-studio-editor-probe', '--probe-mode=' + mode], 'actual editor argv differs')
        for flag in ('passed', 'clean_log', 'result_valid', 'execution_unchanged', 'exact_reopen_revision'):
            need(lane.get(flag) is True, mode + ' invalid fact: ' + flag)
        need(lane.get('result_validation_error') is None and lane['execution_before'] == lane['execution_after'] == expected, 'executed editor input changed')
        result = read(PACKAGE / (mode + '-result.json'))
        progress = [parse(line) for line in (PACKAGE / (mode + '-progress.jsonl')).read_text(encoding='utf-8').splitlines()]
        need(checks.validate_result(mode, result, progress) is True, 'invalid engine result/progress')
        need(type(EXPECTED_ENGINE_CHECKS) is dict and integer(EXPECTED_ENGINE_CHECKS.get(mode), len(result['checks'])), 'actual expected engine count not established/mismatch')
        for text in (*streams, (PACKAGE / (mode + '-engine.log')).read_text(encoding='utf-8')):
            need(BAD_LOG.search(text) is None, 'unclean editor stream')
        results[mode] = result
    need(results['edit']['saved_revision'] == results['reopen']['saved_revision'], 'reopened complete-state revision differs')
    vectors = read(PACKAGE / 'contract-vectors.json')
    need(vectors.get('snapshot_mode') == 'SUPPLIED_NATIVE_OBSERVATION' and vectors.get('file_hashes_observed') is True, 'synthetic contract vectors')
    need(vectors.get('runtime_authorized') is False and vectors.get('acceptance') is False, 'contract vector overclaim')
    need(len(vectors['rejected']) == 14 and all(row['engine_projection'] is None for row in vectors['rejected']), 'rejected host wire reached engine')
    need(vectors.get('schema') == 'hh-gt03-contract-vectors-2', 'legacy vectors')
    need(vectors['context']['project_revision'] == read(PACKAGE / 'contract-base-bundle.json')['project_revision'], 'wire complete-project revision differs')
    return counts, {name: len(value['checks']) for name, value in results.items()}


def verify_artifacts():
    artifacts = hash_map(read(AUDIT / 'artifact-manifest.json')['files'])
    for name, expected in artifacts.items():
        need(sha(inside(ROOT, name)) == expected, 'artifact bytes differ: ' + name)
    roots = {PACKAGE, LINUX, PROFILE, HOST_DEATH}
    # A standalone review Markdown file is one artifact, not authority to scan
    # the complete reviews parent. Directory roots are its third path component.
    for name in artifacts:
        parts = PurePosixPath(name).parts
        need(parts[:2] == ('zdoc', 'reviews'), 'artifact outside review scope')
        if len(parts) >= 4:
            roots.add(ROOT.joinpath(*parts[:3]))
    for package in roots:
        prefix = package.relative_to(ROOT).as_posix() + '/'
        listed = {name[len(prefix):]: value for name, value in artifacts.items() if name.startswith(prefix)}
        actual = inventory(package)
        if package == AUDIT:
            exclusions = {'artifact-manifest.json', 'verification.json',
                          'git-byte-verification-index.json', 'git-byte-verification-HEAD.json'}
            need(not exclusions.intersection(listed), 'recursive audit output listed as input')
            actual = {key: value for key, value in actual.items() if key not in exclusions}
        need(listed == actual, 'artifact inventory omitted/added package files: ' + package.name)
    return artifacts


def verify():
    manifest = read(PACKAGE / 'source-closure.json')
    files = hash_map(manifest['files'])
    closure = manifest['source_closure_sha256']
    need(type(closure) is str and HEX.fullmatch(closure), 'invalid source closure digest')
    source, _ = source_copy(PACKAGE, files, closure)
    # Verify the current tree without importing it. Use the frozen enumeration
    # implementation against an explicit current STUDIO root.
    enumerator = module('s49_frozen_enumerator', source / 'tests/godot/run_editor_probe.py')
    enumerator.STUDIO = STUDIO
    need(enumerator.inputs() == files, 'current source is not this frozen checkpoint')
    owned = module('s49_frozen_owned_runner', source / 'build/bootstrap/run_fixture.py')
    need(owned.source_closure_sha256(files) == closure, 'source closure digest mismatch')
    for name in tuple(sys.modules):
        need(name != 'studio' and not name.startswith('studio.'), 'run audit in a fresh process; studio was already imported')
    sys.path.insert(0, str(source.parent))
    counts, engine_checks = verify_editor(source, files, closure)
    linux = verify_linux(files, closure)
    profile = verify_profile(files, closure)
    host_death = verify_host_death(files, closure, source)
    # Every imported studio dependency must belong to the verified complete copy.
    for name, loaded in tuple(sys.modules.items()):
        if name == 'studio' or name.startswith('studio.'):
            location = getattr(loaded, '__file__', None)
            if location:
                path = Path(location).resolve()
                need(path.is_relative_to(source.resolve()), 'import escaped frozen source: ' + name)
                relative_name = path.relative_to(source.resolve()).as_posix()
                need(relative_name in files and sha(path) == files[relative_name], 'unbound imported dependency: ' + name)
    artifacts = verify_artifacts()
    return {'status': 'S49_DIAGNOSTIC_CHECKPOINT_VERIFIED', 'authority': 0, 'acceptance': False,
            'formal_acceptance': False, 'public_ack': False, 'source_closure_sha256': closure,
            'source_files': len(files), 'artifacts': len(artifacts), 'unit': counts,
            'engine_checks': engine_checks, 'linux': linux, 'profile': profile, 'host_death': host_death}


def git_bytes(summary, ref):
    need(ref in ('index', 'HEAD'), 'expected index or HEAD')
    repo = ROOT.parent
    names = {ROOT.name + '/studio/' + relative(name) for name in read(PACKAGE / 'source-closure.json')['files']}
    names.update(ROOT.name + '/' + relative(name) for name in read(AUDIT / 'artifact-manifest.json')['files'])
    names = sorted(names)
    selectors = [':' + name if ref == 'index' else 'HEAD:' + name for name in names]
    completed = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo,
        input=('\n'.join(selectors) + '\n').encode('utf-8'), capture_output=True, timeout=60, check=True)
    raw, offset = completed.stdout, 0
    for name in names:
        end = raw.find(b'\n', offset)
        need(end >= offset, 'missing Git blob header')
        fields = raw[offset:end].split()
        need(len(fields) == 3 and fields[1] == b'blob' and fields[2].isdigit(), 'invalid Git blob header')
        size = int(fields[2]); offset = end + 1
        blob = raw[offset:offset + size]
        need(len(blob) == size and raw[offset + size:offset + size + 1] == b'\n', 'truncated Git blob')
        need(blob == (repo / name).read_bytes(), 'Git byte mismatch: ' + name)
        offset += size + 1
    need(offset == len(raw), 'extra Git batch bytes')
    summary.update(git_bytes=ref, verified_files=len(names))
    if ref == 'HEAD':
        summary['git_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True, timeout=10).strip()


if __name__ == '__main__':
    need(len(sys.argv) <= 2, 'usage: verify_evidence.py [index|HEAD]')
    summary = verify()
    if len(sys.argv) == 2:
        git_bytes(summary, sys.argv[1])
    destination = AUDIT / ('verification.json' if len(sys.argv) == 1 else 'git-byte-verification-' + sys.argv[1] + '.json')
    destination.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))
