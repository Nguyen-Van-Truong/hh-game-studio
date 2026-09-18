"""Fixed disposable fault injection; no live runtime source is modified."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN = 'gt06-s80-no-focus-01'


def child():
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_native_benchmark as n
    original = n.prepare

    def prepare(project, factory, trusted, binding):
        original(project, factory, trusted, binding)
        path = project / 'addons/hh_benchmark/benchmark_native.gd'
        data = path.read_bytes()
        needle = b'    get_tree().root.propagate_notification(NOTIFICATION_APPLICATION_FOCUS_IN)'
        assert data.count(needle) == 1
        modified = data.replace(needle, b'    # Injected skipped setup notification: expect fail before batch zero.')
        path.write_bytes(modified)
        n.write(project.parent / 'injection.json', {'scope': 'disposable generated driver only',
            'before_sha256': n.sha(data), 'after_sha256': n.sha(modified),
            'expected': 'BENCHMARK_STARTUP_NOTIFICATION_READBACK', 'formal_acceptance': False})
        return n.project_files(project)

    n.prepare = prepare
    try:
        n.run(RUN)
    except n.native_job.StageFailed:
        pass
    else:
        raise AssertionError('Skipped notification was accepted')
    return verify_negative(n)


def verify_negative(n):
    raw = n.STUDIO / '.local/reviews' / RUN
    capture = json.loads((raw / 'editor-host/capture.json').read_bytes())
    exited = json.loads((raw / 'editor-host/process-exit.json').read_bytes())
    started = json.loads((raw / 'editor-host/process-start.json').read_bytes())
    assert exited['pid'] == started['pid'] and exited['exit_code'] == 86
    assert capture['completed'] is False and capture['failure'] == 'STAGE_NATIVE_EXIT'
    assert capture['wrapper_exit_code'] == 86
    # On nonzero exit this native owner retains the actual exit in its hashed
    # process-exit artifact, not the success-only actual_process_exit field.
    assert capture['job']['zero_observed'] and capture['job']['closed']
    assert not capture['job']['handle_retained'] and not capture['job']['tainted']
    assert capture['active_at_wrapper_exit'] == 0 and capture['natural_tree_exit'] is True
    for name, digest in capture['artifacts'].items():
        assert n.sha((raw / 'editor-host' / name).read_bytes()) == digest
    failure = json.loads((raw / 'project/benchmark/out/failure.json').read_bytes())
    assert failure['code'] == 'BENCHMARK_STARTUP_NOTIFICATION_READBACK'
    assert failure['phase'] == 'INITIALIZE' and failure['batch'] == failure['cycle'] == 0
    assert failure['partial_cycle'] == failure['partial_timing'] == {}
    assert {p.name for p in (raw / 'project/benchmark/out').iterdir()} == {'failure.json'}
    assert (raw / 'initial-scene.tscn').read_bytes() == (raw / 'project' / n.MUTABLE_SCENE).read_bytes()
    sources = json.loads((raw / 'source-files.json').read_bytes())
    n.load_fixture()  # Match the original diagnostic's loaded fixture dependency.
    assert n.source_files() == sources
    assert all(n.sha((n.STUDIO / name).read_bytes()) == digest for name, digest in sources.items())
    assert not (raw / 'editor-host/stderr.txt').read_bytes().strip()
    n.write(raw / 'negative-verification-recovered.json', {'negative_verified': True,
        'formal_acceptance': False, 'full_benchmark': False, 'actual_process_exit': exited,
        'scene_unchanged': True, 'source_unchanged': True, 'job': capture['job'],
        'stderr_sha256': n.sha((raw / 'editor-host/stderr.txt').read_bytes()),
        'stdout_sha256': n.sha((raw / 'editor-host/stdout.txt').read_bytes())})
    return 0


def outer():
    output = BASE / 'negative-owner-01'
    output.mkdir(exist_ok=False)
    runner = ROOT / 'studio/build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('s80negativeowner', runner)
    owner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owner)
    argv = [sys.executable, '-B', str(Path(__file__).resolve()), '--owned-child']
    before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / 'invocation.json').write_text(json.dumps({'argv': argv, 'timeout_seconds': 90,
        'script_sha256': before, 'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
        'formal_acceptance': False}, indent=2) + '\n', encoding='utf-8')
    result = owner.run_process(argv, cwd=ROOT, output=output, timeout=90, label='negative')
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == before
    (output / 'capture.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    return int(not (result['exit_code'] == result['wrapper_exit_code'] == 0
                    and result['tree_verified'] and not result['timed_out']))


if __name__ == '__main__':
    if sys.argv[1:] == ['--verify-only']:
        sys.path.insert(0, str(ROOT))
        from studio.tests.replay import run_native_benchmark as n
        raise SystemExit(verify_negative(n))
    if sys.argv[1:] == ['--owned-child']:
        raise SystemExit(child())
    if sys.argv[1:]:
        raise SystemExit('Fixed invocation only')
    raise SystemExit(outer())
