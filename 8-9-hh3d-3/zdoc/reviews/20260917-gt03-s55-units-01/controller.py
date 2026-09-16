"""Bounded GT03 unit partitions; resume only verified complete frozen-source lanes."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / 'studio'
LABELS = tuple(['test_publication_journal'] +
               ['test_publication_journal_v' + str(v) for v in range(2, 6)] + ['other'])
TIMEOUTS = {label: 600 if label == 'other' else 360 for label in LABELS}
CODE = """import unittest,json,sys
suite=unittest.defaultTestLoader.discover('tests/godot',pattern='test_*.py')
def flatten(suite):
    for item in suite:
        if isinstance(item,unittest.TestSuite):yield from flatten(item)
        else:yield item
all_tests=list(flatten(suite));ids=[case.id() for case in all_tests]
assert len(ids)==len(set(ids))
label=sys.argv[1]
chosen=[case for case in all_tests if (not case.id().startswith('test_publication_journal')
    if label=='other' else case.id().split('.')[0]==label)]
print('GT03_UNIT_INVENTORY '+json.dumps({'all':sorted(ids),'chosen':sorted(case.id() for case in chosen)}),flush=True)
result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(chosen))
print('GT03_UNIT_COMPLETE '+json.dumps({'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skips':len(result.skipped)}),flush=True)
sys.exit(not result.wasSuccessful())
"""


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, *, replace=False):
    data = json.dumps(value, indent=2, sort_keys=True) + '\n'
    if replace:
        temporary = path.with_name(path.name + '.pending')
        with temporary.open('w', encoding='utf-8', newline='\n') as handle:
            handle.write(data)
        os.replace(temporary, path)
    else:
        with path.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(data)


def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def regular(path):
    need(not path.is_symlink() and not
         getattr(path.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400,
         'REPARSE_FORBIDDEN')


def closure_hash(files):
    need(type(files) is dict and bool(files), 'INVALID_SOURCE_MAP')
    rows = []
    for name, digest in files.items():
        need(type(name) is str and name and '\\' not in name and ':' not in name and
             all(part not in ('', '.', '..') for part in name.split('/')),
             'INVALID_SOURCE_PATH')
        need(type(digest) is str and re.fullmatch('[0-9a-f]{64}', digest), 'INVALID_SOURCE_HASH')
        rows.append(f'8-9-hh3d-3/studio/{name}\0{digest}\n')
    return hashlib.sha256(''.join(sorted(rows)).encode('utf-8')).hexdigest()


def verify_runtime(package):
    regular(package)
    manifest = package / 'source-closure.json'
    regular(manifest)
    document = read(manifest)
    files = document['files']
    need(closure_hash(files) == document['source_closure_sha256'], 'SOURCE_CLOSURE_MISMATCH')
    source = package / 'source/studio'
    regular(package / 'source')
    regular(source)
    actual = {}
    for path in source.rglob('*'):
        regular(path)
        if path.is_file():
            actual[path.relative_to(source).as_posix()] = sha(path)
    need(actual == files, 'SOURCE_FILES_MISMATCH')
    return source, document


def live_inputs():
    return load('s54_unit_inventory', STUDIO / 'tests/godot/run_editor_probe.py').inputs()


def prepare(output, *, resume=False, runtime_package=None, controller=None):
    """Validate before importing runtime code. A legacy non-resumable output is rejected."""
    controller = Path(controller or __file__).resolve()
    output = output.resolve()
    runtime_package = runtime_package.resolve() if runtime_package is not None else None
    if resume:
        invocation = read(output / 'invocation.json')
        need(invocation.get('schema') == 'hh-gt03-unit-matrix-2', 'UNSUPPORTED_RESUME_PACKAGE')
        package = (output / invocation['runtime_package']).resolve()
        need(runtime_package is None or runtime_package == package, 'RUNTIME_REFERENCE_MISMATCH')
        need(sha(controller) == invocation['controller_sha256'] == sha(output / 'controller.py'),
             'CONTROLLER_MISMATCH')
    else:
        output.mkdir(parents=True, exist_ok=False)
        package = runtime_package or output
        if runtime_package is None:
            files = live_inputs()
            for name, digest in files.items():
                target = output / 'source/studio' / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((STUDIO / name).read_bytes())
                need(sha(target) == digest, 'SOURCE_CHANGED_DURING_FREEZE')
            save(output / 'source-closure.json',
                 {'files': files, 'source_closure_sha256': closure_hash(files)})
        (output / 'controller.py').write_bytes(controller.read_bytes())
    source, document = verify_runtime(package)
    expected = {'schema': 'hh-gt03-unit-matrix-2', 'code': CODE, 'partitions': list(LABELS),
                'timeouts': TIMEOUTS, 'controller_sha256': sha(controller),
                'runner_sha256': sha(source / 'build/bootstrap/run_fixture.py'),
                'source_closure_sha256': document['source_closure_sha256'],
                'source_manifest_sha256': sha(package / 'source-closure.json'),
                'runtime_package': Path(os.path.relpath(package, output)).as_posix()}
    if resume:
        need(invocation == expected, 'INVOCATION_OR_SOURCE_MISMATCH')
    else:
        save(output / 'invocation.json', expected)
        save(output / 'runtime-source-reference.json',
             {key: expected[key] for key in ('runtime_package', 'source_closure_sha256',
              'source_manifest_sha256', 'controller_sha256')})
    need(read(output / 'runtime-source-reference.json') ==
         {key: expected[key] for key in ('runtime_package', 'source_closure_sha256',
          'source_manifest_sha256', 'controller_sha256')}, 'RUNTIME_REFERENCE_MISMATCH')
    return source, document, expected


@contextmanager
def exclusive(output):
    """OS-held lock releases on controller death; no stale PID lock to remove."""
    with (output / 'controller.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def next_directory(parent):
    parent.mkdir(parents=True, exist_ok=True)
    numbers = [int(path.name) for path in parent.iterdir() if re.fullmatch(r'[0-9]{4,}', path.name)]
    path = parent / f'{max(numbers, default=0) + 1:04d}'
    path.mkdir(exist_ok=False)
    return path


def binding(invocation, label):
    return {'schema': 'hh-gt03-unit-attempt-2', 'label': label,
            'source_closure_sha256': invocation['source_closure_sha256'],
            'controller_sha256': invocation['controller_sha256'],
            'invocation_sha256': hashlib.sha256(json.dumps(invocation, sort_keys=True).encode()).hexdigest()}


def partition_ids(ids, label):
    return [name for name in ids if (not name.startswith('test_publication_journal')
            if label == 'other' else name.split('.')[0] == label)]


def markers(stdout, prefix):
    values = [json.loads(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
    need(len(values) == 1, 'MISSING_OR_DUPLICATE_MARKER')
    return values[0]


def inspect_attempt(path, invocation, label):
    """Never trust saved passed/count fields; rebuild them from sealed raw files."""
    try:
        regular(path)
        regular(path / 'attempt.json')
        record = read(path / 'attempt.json')
        need({key: record.get(key) for key in binding(invocation, label)} == binding(invocation, label),
             'ATTEMPT_BINDING_MISMATCH')
        expected_names = {'process.json', 'run-stdout.txt', 'run-stderr.txt', 'run-host.json'}
        need(set(record['artifacts']) == expected_names, 'INCOMPLETE_ARTIFACT_SET')
        need({p.name for p in path.iterdir()} == expected_names | {'attempt.json'}, 'ARTIFACT_SET_MISMATCH')
        for name, digest in record['artifacts'].items():
            regular(path / name)
            need(sha(path / name) == digest, 'ARTIFACT_HASH_MISMATCH')
        host = read(path / 'process.json')
        raw = read(path / 'run-host.json')
        need(type(host.get('exit_code')) is int and host['exit_code'] == 0 and
             type(host.get('wrapper_exit_code')) is int and host['wrapper_exit_code'] == 0 and
             host.get('tree_verified') is True and host.get('timed_out') is False,
             'HOST_NOT_SUCCESSFUL')
        need(type(host.get('target_pid')) is int and host['target_pid'] > 0 and
             type(host.get('wrapper_pid')) is int and host['wrapper_pid'] > 0 and
             type(raw.get('target_pid')) is int and raw['target_pid'] == host['target_pid'] and
             type(raw.get('exit_code')) is int and raw['exit_code'] == 0 and
             type(raw.get('started_at')) is str and bool(raw['started_at']), 'RAW_EXIT_MISMATCH')
        need(host.get('ownership') in ('gated_job_kill_on_close', 'process_group') and
             host.get('argv') == [Path(sys.executable).name, '-B', '-c', CODE, label] and
             [host.get(key) for key in ('stdout', 'stderr', 'host')] ==
             ['run-stdout.txt', 'run-stderr.txt', 'run-host.json'], 'HOST_INVOCATION_MISMATCH')
        stdout = (path / 'run-stdout.txt').read_text(encoding='utf-8')
        inventory = markers(stdout, 'GT03_UNIT_INVENTORY ')
        counts = markers(stdout, 'GT03_UNIT_COMPLETE ')
        need(type(inventory) is dict and set(inventory) == {'all', 'chosen'}, 'INVALID_INVENTORY')
        for ids in inventory.values():
            need(type(ids) is list and bool(ids) and all(type(x) is str and x for x in ids) and
                 ids == sorted(set(ids)), 'INVALID_INVENTORY')
        need(inventory['chosen'] == partition_ids(inventory['all'], label), 'PARTITION_MISMATCH')
        need(type(counts) is dict and set(counts) == {'run', 'failures', 'errors', 'skips'} and
             all(type(value) is int for value in counts.values()) and
             counts == {'run': len(inventory['chosen']), 'failures': 0, 'errors': 0, 'skips': 0},
             'INCOMPLETE_OR_FAILED_TESTS')
        return {'passed': True, 'counts': counts, 'inventory': inventory,
                'attempt_sha256': sha(path / 'attempt.json'), 'host': host}
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        return {'passed': False, 'reason': str(error) if isinstance(error, ValueError) else type(error).__name__}


def run_attempt(path, invocation, label, source, runner):
    try:
        host = runner.run_process([sys.executable, '-B', '-c', CODE, label], cwd=source,
                                  output=path, timeout=TIMEOUTS[label], label='run')
        save(path / 'process.json', host)
    except Exception as error:
        # Preserve incomplete raw output. It cannot be reused, and a new attempt
        # receives a fresh directory on resume even if the controller died here.
        save(path / 'process.json', {'controller_error': type(error).__name__})
    record = binding(invocation, label)
    record['artifacts'] = {p.name: sha(p) for p in path.iterdir() if p.is_file()}
    save(path / 'attempt.json', record)
    return inspect_attempt(path, invocation, label)


def runtime_stable(output, package, document, invocation):
    return (verify_runtime(package)[1] == document and
            sha(package / 'source-closure.json') == invocation['source_manifest_sha256'] and
            sha(output / 'controller.py') == invocation['controller_sha256'] and
            read(output / 'invocation.json') == invocation and
            read(output / 'runtime-source-reference.json') ==
            {key: invocation[key] for key in ('runtime_package', 'source_closure_sha256',
             'source_manifest_sha256', 'controller_sha256')})


def run_matrix(output, source, document, invocation, runner, *, workers=1, origin_files=None,
               origin_probe=None):
    need(workers in (1, 2), 'INVALID_WORKERS')
    package = (output / invocation['runtime_package']).resolve()
    need(runtime_stable(output, package, document, invocation), 'SOURCE_OR_CONTROLLER_CHANGED')
    round_path = next_directory(output / 'rounds')
    running = {'passed': False, 'state': 'RUNNING', 'formal_acceptance': False,
               'round': round_path.relative_to(output).as_posix(),
               'source_closure_sha256': invocation['source_closure_sha256']}
    save(output / 'capture.json', running, replace=True)
    selection, pending, rejected = {}, [], {}
    for label in LABELS:
        parent = output / 'attempts' / label
        previous = sorted((p for p in parent.glob('*') if p.is_dir()), key=lambda p: p.name)
        if previous:
            result = inspect_attempt(previous[-1], invocation, label)
            if result['passed']:
                selection[label] = previous[-1]
                continue
            rejected[label] = {'attempt': previous[-1].relative_to(output).as_posix(),
                               'reason': result['reason']}
        path = next_directory(parent)
        selection[label] = path
        pending.append((label, path))
    def execute(pair):
        label, path = pair
        result = run_attempt(path, invocation, label, source, runner)
        print(json.dumps({'lane': label, 'attempt': path.relative_to(output).as_posix(),
                          'passed': result['passed'], 'counts': result.get('counts'),
                          'reason': result.get('reason')}), flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(execute, pending))
    lanes = {label: {**inspect_attempt(path, invocation, label),
                    'attempt': path.relative_to(output).as_posix(),
                    'reused': label not in {item[0] for item in pending}}
             for label, path in selection.items()}
    inventories = [row['inventory'] for row in lanes.values() if row['passed']]
    selected = [name for row in inventories for name in row['chosen']]
    complete = bool(len(inventories) == len(LABELS) and
                    all(row['all'] == inventories[0]['all'] for row in inventories) and
                    len(selected) == len(set(selected)) and set(selected) == set(inventories[0]['all']))
    try:
        snapshot = runtime_stable(output, package, document, invocation)
    except (ValueError, OSError, KeyError, TypeError):
        snapshot = False
    origin_before = origin_files == document['files'] if origin_files is not None else None
    origin_after = origin_probe() == document['files'] if origin_probe is not None else origin_before
    result = {**running, 'state': 'COMPLETE' if complete and snapshot else 'INCOMPLETE',
              'passed': complete and snapshot, 'snapshot_unchanged': snapshot,
              'partitions_disjoint_complete': complete, 'controller_sha256': invocation['controller_sha256'],
              'runtime_package': invocation['runtime_package'], 'workers': workers,
              'origin_source_unchanged': (origin_before and origin_after) if origin_before is not None else None,
              'origin_source_unchanged_before': origin_before, 'origin_source_unchanged_after': origin_after,
              'counts': ({key: sum(row['counts'][key] for row in lanes.values())
                         for key in ('run', 'failures', 'errors', 'skips')} if complete else None),
              'rejected_previous_attempts': rejected, 'lanes': lanes}
    save(round_path / 'capture.json', result)
    save(output / 'capture.json', result, replace=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--runtime-package', type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to(ROOT / 'zdoc/reviews')
    source, document, invocation = prepare(output, resume=args.resume, runtime_package=args.runtime_package)
    with exclusive(output):
        # Recheck under the exclusive controller lock before starting any lane.
        prepare(output, resume=True, runtime_package=args.runtime_package)
        runner = load('s54_unit_runner', source / 'build/bootstrap/run_fixture.py')
        result = run_matrix(output, source, document, invocation, runner, workers=args.workers,
                            origin_files=live_inputs(), origin_probe=live_inputs)
        print(json.dumps({key: value for key, value in result.items() if key != 'lanes'}), flush=True)
        return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
