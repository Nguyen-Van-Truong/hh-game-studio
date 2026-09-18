"""Prepared owner; requires a coordinator-approved frozen source tree."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    source = args.source_root.resolve(strict=True)
    args.output.mkdir(parents=False, exist_ok=False)
    output = args.output.resolve(strict=True)
    manifest = {p.relative_to(source).as_posix(): sha(p) for p in sorted((source / 'studio').rglob('*.py'))}
    if not manifest or any(p.is_symlink() for p in (source / 'studio').rglob('*.py')):
        raise RuntimeError('INVALID_FROZEN_SOURCE_TREE')
    write(output / 'source-files.json', manifest)
    shutil.copyfile(Path(__file__).with_name('probe.py'), output / 'probe.py')
    shutil.copyfile(Path(__file__), output / 'owner-source.py')
    spec = importlib.util.spec_from_file_location('_s81_owned_process', source / 'studio/build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    argv = [sys.executable, '-B', str(output / 'probe.py'), '--source-root', str(source),
            '--manifest', str(output / 'source-files.json'), '--journal', str(args.journal.resolve(strict=True)),
            '--output', str(output / 'child'), '--run-id', args.run_id]
    write(output / 'invocation.json', {'argv': argv, 'timeout_seconds': 240,
          'coordinator_freeze_required': True, 'formal_acceptance': False,
          'python_sha256': sha(Path(sys.executable)), 'driver_sha256': sha(output / 'probe.py'),
          'owner_sha256': sha(Path(__file__)),
          'owned_runner_sha256': sha(source / 'studio/build/bootstrap/run_fixture.py'),
          'source_manifest_sha256': sha(output / 'source-files.json')})
    capture = runner.run_process(argv, cwd=source, output=output, timeout=240, label='http-probe',
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    capture['source_files_unchanged'] = all(sha(source / name) == expected for name, expected in manifest.items())
    capture['engine_runs'] = 0
    capture['formal_acceptance'] = False
    capture['evidence_hashes'] = {p.relative_to(output).as_posix(): sha(p) for p in sorted(output.rglob('*'))
                                  if p.is_file()}
    write(output / 'capture.json', capture)
    print(json.dumps(capture, indent=2))
    return 0 if (capture['exit_code'] == 0 and capture['wrapper_exit_code'] == 0
                 and capture['tree_verified'] and not capture['timed_out']
                 and capture['source_files_unchanged']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
