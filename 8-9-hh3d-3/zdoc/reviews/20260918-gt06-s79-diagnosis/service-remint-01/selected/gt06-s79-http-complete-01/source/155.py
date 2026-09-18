"""Freeze GT05 unit sources, run in an owned child, and keep exact raw evidence.

No engine is launched by this driver. Tests that deliberately exercise a native
ownership primitive still run inside the bootstrap runner's bounded process tree.
This is component verification, never gate acceptance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
DIRECTORIES = ('pipeline', 'tests/pipeline', 'host/core', 'host/blender',
               'protocol', 'blender-addon', 'fixtures/assets-src', 'contracts')
SUFFIXES = {'.py', '.json', '.md', '.txt', '.cjs', '.gd', '.uid', '.godot', '.tscn', '.tres'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_files(studio):
    paths = {studio / name for name in ('build/bootstrap/run_fixture.py',
        'godot-addon/cli_job.py', 'tests/asset-profile.json', 'toolchain.lock.json')}
    for directory in DIRECTORIES:
        paths.update(path for path in (studio / directory).rglob('*')
            if path.is_file() and path.suffix in SUFFIXES and '__pycache__' not in path.parts)
    result = {}
    for path in sorted(paths):
        info = path.stat(follow_symlinks=False)
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('UNIT_SOURCE_REPARSE')
        result[path.relative_to(studio).as_posix()] = sha(path.read_bytes())
    return result


def write(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write('\n')


def run(run_id, pattern='test_*.py'):
    if not re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run_id):
        raise ValueError('UNIT_RUN_ID')
    if pattern != 'test_*.py' and not re.fullmatch(r'test_[a-z0-9_]+\.py', pattern):
        raise ValueError('UNIT_PATTERN')
    output = STUDIO / '.local/reviews' / run_id
    output.mkdir(exist_ok=False)
    before = source_files(STUDIO)
    snapshot = output / 'source/studio'
    for name, digest in before.items():
        raw = (STUDIO / name).read_bytes()
        if sha(raw) != digest:
            raise ValueError('UNIT_SOURCE_CHANGED_DURING_FREEZE')
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    if source_files(snapshot) != before:
        raise ValueError('UNIT_SNAPSHOT_COPY_MISMATCH')
    # The three native validator tests need their own writable scratch parent
    # and exact pinned offline package inside the disposable snapshot. Neither
    # a PATH check nor omitting this cache is a reason to skip those tests.
    (snapshot / '.local/reviews').mkdir(parents=True)
    lock = json.loads((snapshot / 'pipeline/dependencies/gltf-validator.lock.json').read_bytes())
    cache = Path('.local/tooling/gt05') / ('gltf-validator-' + lock['version'])
    dependencies = {}
    for name, digest in lock['files'].items():
        if not name.startswith('package/') or any(part in ('', '.', '..') for part in name.split('/')) or '\\' in name:
            raise ValueError('UNIT_DEPENDENCY_PATH')
        raw = (STUDIO / cache / name).read_bytes()
        if sha(raw) != digest:
            raise ValueError('UNIT_DEPENDENCY_PIN')
        target = snapshot / cache / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        dependencies[(cache / name).as_posix()] = digest
    write(output / 'dependency-files.json', dependencies)
    path = snapshot / 'build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('gt05_owned_unit_runner', path)
    runner = importlib.util.module_from_spec(spec)
    exec(compile(path.read_bytes(), str(path), 'exec'), runner.__dict__)
    closure = runner.source_closure_sha256(before)
    write(output / 'source-closure.json', {'schema': 'HH-GT05-UNIT-SOURCE-1',
        'source_closure_sha256': closure, 'files': before})
    code = "\n".join((
        'import json,sys,unittest',
        "suite=unittest.defaultTestLoader.discover('tests/pipeline',pattern=sys.argv[1])",
        'def ids(item):',
        ' return [item.id()] if isinstance(item,unittest.TestCase) else [key for child in item for key in ids(child)]',
        'tests=ids(suite)',
        'r=unittest.TextTestRunner(verbosity=2).run(suite)',
        "summary={'run':r.testsRun,'ids':tests,'failures':len(r.failures),'errors':len(r.errors),'skips':[{'id':test.id(),'reason':reason} for test,reason in r.skipped]}",
        "print('GT05_UNIT_COMPLETE '+json.dumps(summary),flush=True)",
        'sys.exit(0 if r.wasSuccessful() else 1)',
    ))
    started = datetime.now(timezone.utc).isoformat()
    write(output / 'invocation.json', {'code': code, 'pattern': pattern,
        'python_sha256': sha(Path(sys.executable).read_bytes()), 'source_closure_sha256': closure})
    host = runner.run_process([sys.executable, '-B', '-c', code, pattern], cwd=snapshot,
                              output=output, timeout=120, label='unit')
    markers = [json.loads(line[len('GT05_UNIT_COMPLETE '):])
        for line in (output / host['stdout']).read_text(encoding='utf-8').splitlines()
        if line.startswith('GT05_UNIT_COMPLETE ')]
    summary = markers[0] if len(markers) == 1 else None
    stable = (source_files(STUDIO) == before and source_files(snapshot) == before
        and all(sha((snapshot / name).read_bytes()) == digest for name, digest in dependencies.items()))
    passed = (stable and host['exit_code'] == host['wrapper_exit_code'] == 0
        and host['tree_verified'] and not host['timed_out'] and summary is not None
        and summary['run'] > len(summary['skips']) and summary['failures'] == summary['errors'] == 0
        and len(set(summary['ids'])) == len(summary['ids']) == summary['run'])
    # Skips remain explicit evidence. A component pass does not waive required
    # capabilities or allow its coordinator to turn an environment gap into PASS.
    result = {'schema': 'HH-GT05-UNIT-CAPTURE-1', 'run_id': run_id,
        'started_utc': started, 'completed_utc': datetime.now(timezone.utc).isoformat(),
        'host': host, 'summary': summary, 'source_closure_sha256': closure,
        'source_unchanged': stable, 'passed': passed, 'formal_acceptance': False,
        'artifacts': {name: sha((output / name).read_bytes()) for name in
                      (host['stdout'], host['stderr'], host['host'], 'invocation.json', 'source-closure.json', 'dependency-files.json')}}
    write(output / 'capture.json', result)
    print(json.dumps({'run_id': run_id, 'passed': passed, 'source_unchanged': stable,
        'run': summary['run'] if summary else None, 'skips': summary['skips'] if summary else None}))
    return 0 if passed else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--pattern', default='test_*.py')
    args = parser.parse_args()
    raise SystemExit(run(args.run_id, args.pattern))
