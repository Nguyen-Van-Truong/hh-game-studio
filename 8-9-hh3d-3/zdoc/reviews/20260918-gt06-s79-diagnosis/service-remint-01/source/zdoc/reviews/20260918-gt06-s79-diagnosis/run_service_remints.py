"""Fixed S79 seven-lane remint using the existing bounded owners; not acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
import subprocess
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
OUTPUT = BASE / 'service-remint-01'
sys.path.insert(0, str(ROOT))
from studio.host.replay import native_runner as native
from studio.pipeline.native_job import verify_captured_stage

LANES = [
    ('http-complete', 'replay/run_service_probe.py', 'complete', 150),
    ('http-stop', 'replay/run_service_probe.py', 'stop', 150),
    ('saturated-stop', 'replay/run_service_adversary.py', 'saturated-stop', 180),
    ('revoked-result', 'replay/run_service_adversary.py', 'revoked-result', 180),
    ('stale-capture', 'replay/run_service_adversary.py', 'stale-capture', 180),
    ('reviewer-complete', 'reviewer/run_reviewer_probe.py', 'complete', 150),
    ('reviewer-stop', 'reviewer/run_reviewer_probe.py', 'stop', 150),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def need(value, code):
    if not value:
        raise RuntimeError(code)


def verify_outer(folder, host):
    actual = read(folder / host['host'])
    need(host['exit_code'] == host['wrapper_exit_code'] == actual['exit_code'] == 0,
         'OUTER_ACTUAL_EXIT')
    need(actual['target_pid'] == host['target_pid'] and actual['started_at'], 'OUTER_IDENTITY')
    need(host['tree_verified'] is True and host['timed_out'] is False, 'OUTER_TREE')
    need((folder / host['stderr']).stat().st_size == 0, 'OUTER_STDERR')
    need(not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', (folder / host['stdout']).read_bytes()), 'OUTER_LOG')
    return {'actual_target': actual, 'helper_pid': host['wrapper_pid'],
            'helper_exit': host['wrapper_exit_code'], 'tree_verified': host['tree_verified']}


def verify_stage(folder, stopped=False):
    capture = read(folder / 'capture.json')
    for name, digest in capture['artifacts'].items():
        need(sha(folder / name) == digest, 'NATIVE_ARTIFACT_HASH')
    job = capture['job']
    need(job['closed'] is True and job['zero_observed'] is True and job['active_count'] == 0
         and job['handle_retained'] is False and job['tainted'] is False
         and job['create_uncertain'] is False and job['close_uncertain'] is False
         and not job['failed_operations'], 'NATIVE_JOB')
    need((folder / 'stderr.txt').stat().st_size == 0, 'NATIVE_STDERR')
    need(not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', (folder / 'stdout.txt').read_bytes()), 'NATIVE_LOG')
    start = read(folder / 'process-start.json')
    if stopped:
        need(capture['completed'] is False and capture['failure'] == 'STAGE_STOPPED', 'STOP_SEMANTICS')
        # Missing natural exit remains missing. Do not infer it from wrapper exit.
        actual = read(folder / 'process-exit.json') if (folder / 'process-exit.json').exists() else None
        if actual is not None:
            need(actual['pid'] == start['pid'], 'STOP_EXIT_IDENTITY')
    else:
        verify_captured_stage(folder, sha(folder / 'capture.json'))
        actual = read(folder / 'process-exit.json')
    return {'pid': start['pid'], 'actual_native_exit': actual,
            'completed': capture['completed'], 'wrapper_exit': capture['wrapper_exit_code'], 'job': job}


def verify_lane(label, driver, mode, source, frozen):
    run_id = 'gt06-s79-' + label + '-01'
    raw = STUDIO / '.local/reviews' / run_id
    folder = OUTPUT / label
    outer = verify_outer(folder, read(folder / 'capture.json')['host'])
    raw_roots = [raw]
    inner = None
    if 'adversary' in driver or 'reviewer' in driver:
        inner_root = STUDIO / '.local/reviews' / (run_id + ('-outer' if 'adversary' in driver else '-driver'))
        inner_capture = read(inner_root / 'capture.json')
        need(inner_capture['completed'] is True, 'INNER_COMPLETE')
        inner = verify_outer(inner_root, inner_capture['host'])
        need(inner_capture['driver_sha256'] == sha(STUDIO / 'tests' / driver), 'INNER_DRIVER')
        raw_roots.append(inner_root)
    need(read(raw / 'source-files.json') == source, 'EXACT_BACKEND_SOURCE')
    for index, (name, digest) in enumerate(source.items()):
        need(sha(raw / 'source' / (str(index) + Path(name).suffix)) == digest, 'SOURCE_COPY')
    imported = verify_stage(raw / 'import-host')
    runtime = verify_stage(raw / 'runtime-host', mode in ('stop', 'saturated-stop'))
    domain = 'reviewer-probe' if 'reviewer' in driver else 'http-adversary' if 'adversary' in driver else 'http-probe'
    result = read(raw / domain / 'result.json')
    need(result['run_id'] == run_id and result['mode'] == mode and result['formal_acceptance'] is False, 'RESULT_IDENTITY')
    need(result['binding']['source_closure_sha256'] == native.closure(source), 'RESULT_SOURCE')
    if domain == 'reviewer-probe':
        observations = read(raw / domain / 'observations.json')
        need(result['closed'] is True and result['source_unchanged'] is True and not observations['errors']
             and observations['closed'] is True and observations['window_closed'] is True, 'GUI_CLOSE')
        flags = result['flags']
        need(flags['play_key'] and (flags['stop_key'] if mode == 'stop' else flags['inspect_button'] and flags['capture_button']), 'GUI_INPUT')
        checks = []
    else:
        checks = result['checks']
        need(checks and all(row['passed'] is True for row in checks), 'CHECKS')
        old = ROOT / 'zdoc/reviews/20260918-gt06-s73-recovery/service-remint/selected' / run_id.replace('s79', 's73') / domain / 'result.json'
        need({row['label'] for row in read(old)['checks']} <= {row['label'] for row in checks}, 'MISSING_NAMED_INVARIANT')
        need(result['driver_sha256'] == sha(STUDIO / 'tests' / driver), 'DRIVER_HASH')
    if inner is not None:
        need(inner_capture['result_sha256'] == sha(raw / domain / 'result.json'), 'INNER_RESULT_HASH')
    if mode == 'stale-capture':
        mutation = read(raw / domain / 'intentional-capture-mutation.json')
        need(sha(raw / mutation['original_copy']) == mutation['original_sha256']
             and sha(raw / mutation['generated_relative_path']) == mutation['mutated_sha256']
             and mutation['original_sha256'] != mutation['mutated_sha256'] and mutation['restored'] is False, 'MUTATION_WITNESS')
    need(all(sha(ROOT / name) == digest for name, digest in frozen.items()), 'FROZEN_SOURCE_CHANGED')
    inventory = {}
    for raw_root in raw_roots:
        for path in sorted(raw_root.rglob('*')):
            if path.is_file():
                relative = path.relative_to(ROOT).as_posix()
                inventory[relative] = {'sha256': sha(path), 'size_bytes': path.stat().st_size}
                # Preserve portable review records and source bytes, leaving generated caches in raw.
                parts = path.relative_to(raw_root).parts
                if not any(p in ('.godot', 'appdata', 'localappdata', 'temp') for p in parts):
                    target = OUTPUT / 'selected' / raw_root.name / path.relative_to(raw_root)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as stream:
                        stream.write(path.read_bytes())
    write(folder / 'raw-files.json', inventory)
    summary = {'run_id': run_id, 'checks': len(checks), 'all_checks_passed': True,
               'source_files': len(source), 'source_sha256': native.closure(source), 'source_unchanged': True,
               'outer': outer, 'inner': inner, 'import': imported, 'runtime': runtime,
               'raw_file_count': len(inventory), 'raw_bytes': sum(v['size_bytes'] for v in inventory.values()),
               'formal_acceptance': False}
    write(folder / 'verification.json', summary)
    return summary


def main():
    need(not sys.argv[1:], 'FIXED_INVOCATION')
    OUTPUT.mkdir(exist_ok=False)
    _, accepted = native.accepted_inputs()
    source = native.sources(accepted)
    source.update({p.relative_to(STUDIO).as_posix(): sha(p) for p in (STUDIO / 'host/replay').glob('*.py')})
    source['contracts/perf-collector.schema.json'] = sha(STUDIO / 'contracts/perf-collector.schema.json')
    source = dict(sorted(source.items()))
    paths = subprocess.check_output(['git', 'ls-files', '-z', '--', 'studio'], cwd=ROOT).decode().split('\0')
    paths += [Path(__file__).relative_to(ROOT).as_posix()]
    paths = sorted({p for p in paths if p and (ROOT / p).is_file() and Path(p).suffix in {'.py', '.json', '.gd', '.cfg', '.tscn', '.tres', '.godot', '.uid'}})
    paths = sorted(set(paths) | {'studio/' + p for p in source})
    frozen = {p: sha(ROOT / p) for p in paths}
    for name in frozen:
        target = OUTPUT / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    write(OUTPUT / 'freeze.json', {'created_at': datetime.now(timezone.utc).isoformat(), 'source_files': frozen,
          'backend_source_files': source, 'backend_source_sha256': native.closure(source),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
          'formal_acceptance': False})
    runner = STUDIO / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('s79_service_owned', runner)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    results = []
    for label, driver, mode, timeout in LANES:
        run_id = 'gt06-s79-' + label + '-01'
        for suffix in ('', '-outer', '-driver'):
            need(not (STUDIO / '.local/reviews' / (run_id + suffix)).exists(), 'RUN_ID_REUSE')
        need(all(sha(ROOT / name) == digest for name, digest in frozen.items()), 'PRELAUNCH_SOURCE_CHANGED')
        folder = OUTPUT / label
        folder.mkdir(exist_ok=False)
        argv = [sys.executable, '-B', str(STUDIO / 'tests' / driver), '--run-id', run_id, '--mode', mode]
        write(folder / 'invocation.json', {'argv': argv, 'cwd': str(ROOT), 'run_id': run_id, 'mode': mode,
              'timeout_seconds': timeout, 'runner_sha256': sha(runner), 'formal_acceptance': False})
        print('S79_START ' + run_id, flush=True)
        host = owned.run_process(argv, cwd=ROOT, output=folder, timeout=timeout, label='owner')
        write(folder / 'capture.json', {'host': host})
        results.append(verify_lane(label, driver, mode, source, frozen))
        print('S79_VERIFIED ' + json.dumps(results[-1]), flush=True)
    write(OUTPUT / 'verification.json', {'schema': 'HH-GT06-S79-SERVICE-REMINT-1', 'lanes': results,
          'source_unchanged': True, 'frozen_files': len(frozen), 'formal_acceptance': False})
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        if OUTPUT.is_dir() and not (OUTPUT / 'failure.json').exists():
            write(OUTPUT / 'failure.json', {'error_type': type(error).__name__, 'message': str(error), 'formal_acceptance': False})
        raise
