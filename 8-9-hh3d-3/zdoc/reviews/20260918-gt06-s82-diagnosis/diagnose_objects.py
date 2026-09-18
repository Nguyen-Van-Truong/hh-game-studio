"""One owned, disposable 6x100 native-cycle + 120s object-attribution probe.

Diagnostic only. No threshold changes, HTTP campaign, runtime source edits,
focus changes, timer/coroutine sampling, or full-ObjectDB census claim.
Run the no-argument entry point after coordinator verifies other lanes clean.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import re
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RUN_ID = 'gt06-s82-object-diagnostic-01'


def outer():
    output = BASE / 'result-01'
    output.mkdir(exist_ok=False)
    helper_files = ['diagnose_objects.py', 'object_probe.gd']
    before = {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in helper_files}
    for name in helper_files:
        (output / name).write_bytes((BASE / name).read_bytes())
    runner = ROOT / 'studio/build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('owned_object_probe', runner)
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    executable = Path(sys.executable).with_name('python.exe')
    assert executable.is_file()
    argv = [str(executable), '-B', str(BASE / 'diagnose_objects.py'), '--owned-child']
    (output / 'invocation.json').write_text(json.dumps({
        'argv': argv, 'helper_files': before, 'timeout_seconds': 600,
        'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
        'formal_acceptance': False, 'full_benchmark': False}, indent=2) + '\n', encoding='utf-8')
    result = owned.run_process(argv, cwd=ROOT, output=output, timeout=600, label='probe')
    after = {name: hashlib.sha256((BASE / name).read_bytes()).hexdigest() for name in helper_files}
    (output / 'capture.json').write_text(json.dumps({
        'host': result, 'helper_source_unchanged': before == after}, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    assert before == after
    code = result.get('exit_code')
    if (type(code) is not int or result.get('wrapper_exit_code') != 0
            or result.get('timed_out') is not False or result.get('tree_verified') is not True):
        return 1
    return code


def child():
    sys.path.insert(0, str(ROOT))
    from studio.tests.replay import run_native_benchmark as n
    from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture

    factory, trusted = n.load_fixture()
    source = n.source_files()
    lock = json.loads(n.read_regular(n.STUDIO / 'toolchain.lock.json'))['godot']
    executable = n.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    root = n.STUDIO / '.local/reviews' / RUN_ID
    root.mkdir(exist_ok=False)
    project = root / 'project'
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
               'run_id': RUN_ID, 'mode': 'diagnostic', 'source_closure_sha256': n.closure(source),
               'profile_sha256': n.benchmark_profile.PROFILE_SHA256,
               'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
    n.prepare(project, factory, trusted, binding)
    driver = project / 'addons/hh_benchmark/benchmark_native.gd'
    script = driver.read_text(encoding='utf-8')
    replacements = [
        ('        _batch_limit = 1\n        _cycle_limit = 1',
         '        _batch_limit = 6\n        _cycle_limit = 100'),
        ('    if _mode != "full":\n        _advance_batch()',
         '    if _mode != "full":\n        _object_probe_after_batch()'),
        ('    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n',
         '    if _object_probe_tick():\n        return\n    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n'),
    ]
    for old, new in replacements:
        assert script.count(old) == 1, old
        script = script.replace(old, new)
    script += '\n' + (BASE / 'object_probe.gd').read_text(encoding='utf-8')
    driver.write_text(script, encoding='utf-8', newline='\n')
    initial = n.project_files(project)
    for name, digest in source.items():
        raw = n.read_regular(n.STUDIO / name)
        assert n.sha(raw) == digest
        n.write(root / 'source/studio' / name, raw)
    n.write(root / 'diagnostic.json', {
        'formal_acceptance': False, 'full_benchmark': False, 'run_id': RUN_ID,
        'source_files': source, 'initial_project_files': initial, 'native_batches': 6,
        'cycles_each': 100, 'idle_seconds': 120, 'inner_wall_seconds': 540,
        'runner_sha256': n.sha(Path(__file__).read_bytes()),
        'probe_sha256': n.sha((BASE / 'object_probe.gd').read_bytes()),
        'inventory_complete_objectdb': False, 'binding': binding})
    owner = None
    started = time.monotonic()
    try:
        n.native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=source,
            source_root=n.STUDIO, binary_sha256=lock['gui_sha256'])
        n.native_job.verify_captured_stage(root / 'import-host',
            n.sha(n.read_regular(root / 'import-host/capture.json')))
        snapshot = n.project_files(project)
        assert all(snapshot.get(key) == value for key, value in initial.items())
        runtime = dict(source)
        runtime.update({(project / name).relative_to(n.STUDIO).as_posix(): value
                        for name, value in snapshot.items() if name != n.MUTABLE_SCENE})
        n.write(root / 'runtime-source-files.json', runtime)
        owner = BenchmarkProcess(
            [str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
             '--', '--hh-benchmark-mode=diagnostic'], cwd=project, output=root / 'editor-host',
            source_root=n.STUDIO, source_files=runtime, binary_sha256=lock['gui_sha256'])
        while owner.tick(stop=time.monotonic() - started >= 540) is None:
            time.sleep(.1)
        capture = owner.finish()
        verify_capture(root / 'editor-host', n.sha(n.read_regular(root / 'editor-host/capture.json')),
            source_root=n.STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        batches = sorted((project / 'benchmark/out').glob('batch-*.json'))
        assert len(batches) == 6
        for index, path in enumerate(batches):
            batch = json.loads(path.read_bytes())
            assert batch['index'] == index and len(batch['cycles']) == 100
        points = sorted((project / 'benchmark/out').glob('object-*.json'))
        assert points and json.loads(points[-1].read_bytes())['label'] == 'idle_end'
        for lane in ['import-host', 'editor-host']:
            assert not (root / lane / 'stderr.txt').read_bytes().strip()
            assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED',
                                 (root / lane / 'stdout.txt').read_bytes())
        assert n.source_files() == source
        owner.close()
        owner = None
        n.write(root / 'result.json', {
            'formal_acceptance': False, 'full_benchmark': False, 'completed_diagnostic': True,
            'actual_process_exit': capture['actual_process_exit'], 'job': capture['job'],
            'source_unchanged': True, 'point_count': len(points),
            'points': {path.name: n.sha(n.read_regular(path)) for path in points}})
        return 0
    except BaseException as exc:
        if owner is None:
            owner = getattr(exc, 'cleanup_owner', None)
        n.write(root / 'failure.json', {
            'type': type(exc).__name__, 'detail': str(exc), 'formal_acceptance': False})
        raise
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as cleanup_error:
                n.write(root / 'cleanup-failure.json', {
                    'type': type(cleanup_error).__name__, 'detail': str(cleanup_error),
                    'formal_acceptance': False})
                raise


if __name__ == '__main__':
    if sys.argv[1:] == ['--owned-child']:
        raise SystemExit(child())
    if sys.argv[1:]:
        raise SystemExit('No public arguments; use the fixed owned diagnostic entry point.')
    try:
        code = outer()
    except Exception as error:
        import traceback
        with (BASE / 'outer-failure-03.json').open('x', encoding='utf-8') as log:
            json.dump({'type': type(error).__name__, 'detail': str(error),
                       'traceback': traceback.format_exc(), 'formal_acceptance': False}, log, indent=2)
        code = 1
    raise SystemExit(code)

