"""Prepare immutable inputs and run one explicitly requested owned diagnostic."""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import shutil
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
ORIGINAL = ROOT / 'studio/.local/reviews/gt06-s93-sparse-attribution-01'
TIMEOUT_SECONDS = 105  # Target wall cap; leave room below 120s for owner cleanup.
KNOWN_FAILURE_CODES = frozenset({
    'SOURCE_PATH_INVALID', 'CURRENT_SOURCE_CHANGED_DURING_FREEZE',
    'SOURCE_COPY_MISMATCH', 'HISTORY_COPY_MISMATCH', 'RUNNER_COPY_MISMATCH',
    'CURRENT_CLOSURE_CHANGED_DURING_FREEZE',
})


class ProbeFailure(ValueError):
    def __init__(self, code, source_relative=None):
        super().__init__(code)
        self.source_relative = source_relative


def safe_relative(value):
    if (type(value) is str and len(value) <= 256
            and re.fullmatch(r'[A-Za-z0-9_./-]+', value)
            and not Path(value).is_absolute() and '..' not in Path(value).parts):
        return value
    return None


def sanitized_error(error):
    rows, seen = [], set()
    while error is not None and id(error) not in seen and len(rows) < 3:
        seen.add(id(error))
        kind = type(error).__name__
        row = {'exception_class': kind if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', kind) else 'Exception',
               'frames': []}
        trace = error.__traceback__
        while trace is not None:
            name = Path(trace.tb_frame.f_code.co_filename).name
            row['frames'].append({'file': name if re.fullmatch(r'[A-Za-z0-9_.-]{1,96}', name) else 'nonstandard_filename',
                                  'line': trace.tb_lineno})
            trace = trace.tb_next
        row['frames'] = row['frames'][-16:]
        if len(error.args) == 1 and type(error.args[0]) is str and error.args[0] in KNOWN_FAILURE_CODES:
            row['known_code'] = error.args[0]
        if isinstance(error, ProbeFailure) and safe_relative(error.source_relative) is not None:
            row['source_relative'] = safe_relative(error.source_relative)
        rows.append(row)
        error = error.__cause__ or error.__context__
    return {'exception_chain': rows}


def mismatch_locations(expected, actual):
    return [safe_relative(name) for name in sorted(set(expected) | set(actual))
            if expected.get(name) != actual.get(name) and safe_relative(name) is not None][:8]


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(65536):
            value.update(chunk)
    return value.hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def main():
    if sys.argv[1:] != ['--launch']:
        print('Prepared probe only. Coordinator must explicitly invoke --launch.')
        return 2
    run = BASE / 'run-01'
    run.mkdir(exist_ok=False)
    source = run / 'source'
    source.mkdir()
    # Freeze current code only after coordinator has finished the source repair.
    # Importing this collector starts no worker, engine or test.
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_benchmark_campaign as campaign
    originals = campaign.source_files()
    frozen = {}
    for name, expected in originals.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ProbeFailure('SOURCE_PATH_INVALID')
        old = ROOT / 'studio' / relative
        if sha(old) != expected:
            raise ProbeFailure('CURRENT_SOURCE_CHANGED_DURING_FREEZE', relative.as_posix())
        target = source / 'studio' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, target)
        frozen['studio/' + relative.as_posix()] = sha(target)
        if frozen['studio/' + relative.as_posix()] != expected:
            raise ProbeFailure('SOURCE_COPY_MISMATCH', relative.as_posix())
    original_history = ORIGINAL / 'commands' / 'commands.jsonl'
    history_before = sha(original_history)
    shutil.copyfile(original_history, run / 'history.jsonl')
    if sha(run / 'history.jsonl') != history_before:
        raise ValueError('HISTORY_COPY_MISMATCH')
    runner_original = ROOT / 'studio/build/bootstrap/run_fixture.py'
    runner = run / 'owned-runner.py'
    shutil.copyfile(runner_original, runner)
    runner_before = sha(runner_original)
    if sha(runner) != runner_before:
        raise ValueError('RUNNER_COPY_MISMATCH')
    after_freeze = campaign.source_files()
    if after_freeze != originals:
        locations = mismatch_locations(originals, after_freeze)
        raise ProbeFailure('CURRENT_CLOSURE_CHANGED_DURING_FREEZE', locations[0] if locations else None)
    freeze = {'source_files': frozen, 'current_studio_source_files': originals,
              'current_source_closure_sha256': campaign.closure(originals),
              'source_kind': 'current repaired code frozen at launch; S93 supplies history only',
              's93_history_provenance_manifest_sha256': sha(ORIGINAL / 'source-files.json'),
              'history_sha256': history_before, 'history_bytes': original_history.stat().st_size,
              'runner_sha256': runner_before, 'probe_sha256': sha(BASE / 'probe.py'),
              'launcher_sha256': sha(Path(__file__)), 'python_sha256': sha(Path(sys.executable)),
              'formal_acceptance': False, 'eligible_for_dataset': False}
    write(run / 'freeze.json', freeze)
    spec = importlib.util.spec_from_file_location('s95_owned_runner', runner)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    capture = run / 'owned'
    capture.mkdir()
    argv = [sys.executable, '-B', str(BASE / 'probe.py'), str(run)]
    write(capture / 'invocation.json', {'argv': argv, 'timeout_seconds': TIMEOUT_SECONDS,
          'formal_acceptance': False, 'engine_runs': 0, 'freeze_sha256': sha(run / 'freeze.json')})
    result = owned.run_process(argv, cwd=source, output=capture,
                               timeout=TIMEOUT_SECONDS, label='http')
    current_after = campaign.source_files()
    result.update(formal_acceptance=False, eligible_for_dataset=False, engine_runs=0,
        source_original_unchanged=current_after == originals,
        source_original_mismatch_locations=mismatch_locations(originals, current_after),
        source_copy_unchanged=all(sha(source / name) == digest for name, digest in frozen.items()),
        history_original_after_sha256=sha(original_history),
        history_copy_after_sha256=sha(run / 'history.jsonl'),
        runner_original_unchanged=sha(runner_original) == runner_before,
        runner_copy_unchanged=sha(runner) == runner_before,
        probe_unchanged=sha(BASE / 'probe.py') == freeze['probe_sha256'])
    result['history_unchanged'] = result['history_original_after_sha256'] == result['history_copy_after_sha256'] == history_before
    result['actual_target_exit_missing'] = result.get('exit_code') is None
    result['cleanup_scope'] = 'run_fixture owned Job tree; target exit from helper wait, helper exit from parent wait; missing target receipt after timeout remains GAP'
    write(capture / 'capture.json', result)
    ok = (result.get('exit_code') == 0 and result.get('wrapper_exit_code') == 0
          and result.get('tree_verified') is True and result.get('timed_out') is False
          and all(result[key] for key in ('source_original_unchanged', 'source_copy_unchanged',
                  'history_unchanged', 'runner_original_unchanged', 'runner_copy_unchanged', 'probe_unchanged')))
    print(json.dumps({key: result.get(key) for key in
          ('exit_code', 'wrapper_exit_code', 'tree_verified', 'timed_out', 'actual_target_exit_missing')}), flush=True)
    return 0 if ok else 1


if __name__ == '__main__':
    try:
        code = main()
    except BaseException as error:
        diagnostic = {'status': 'HTTP_ATTRIBUTION_OWNER_INCOMPLETE', **sanitized_error(error)}
        try:
            write(BASE / 'launcher-error.json', diagnostic)
        except OSError:
            pass
        print(json.dumps(diagnostic, sort_keys=True), flush=True)
        code = 1
    raise SystemExit(code)
