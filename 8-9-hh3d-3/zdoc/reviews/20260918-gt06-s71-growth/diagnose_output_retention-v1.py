"""Owned A/B diagnostic only: stock Output capacity, 3x50 native cycles.

Does not alter production source, workload acceptance, or global editor settings.
Both copied projects use identical diagnostic dimensions and an explicit cap.
Full external logs are retained. This is not the 10x35x100 benchmark.
"""
from pathlib import Path
import hashlib
import json
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as n
from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture


def run(cap):
    factory, trusted = n.load_fixture()
    source = n.source_files()
    lock = json.loads(n.read_regular(n.STUDIO / 'toolchain.lock.json'))['godot']
    executable = n.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    run_id = f'gt06-s71-output-cap-{cap}-01'
    root = n.STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = root / 'project'
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'diagnostic', 'source_closure_sha256': n.closure(source),
        'profile_sha256': n.benchmark_profile.PROFILE_SHA256,
        'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
    n.prepare(project, factory, trusted, binding)
    config = project / 'project.godot'
    raw = config.read_bytes()
    assert raw.count(b'[editor_plugins]') == 1
    config.write_bytes(raw.replace(b'[editor_plugins]',
        f'[editor_overrides]\n\nrun/output/max_lines={cap}\n\n[editor_plugins]'.encode()))
    driver = project / 'addons/hh_benchmark/benchmark_native.gd'
    raw = driver.read_bytes()
    old = b'        _batch_limit = 1\n        _cycle_limit = 1'
    assert raw.count(old) == 1
    raw = raw.replace(old, b'        _batch_limit = 3\n        _cycle_limit = 50')
    old = b'    var input_file: FileAccess = FileAccess.open(INPUT, FileAccess.READ)'
    assert raw.count(old) == 1
    readback = (f'    var diagnostic_cap: int = int(EditorInterface.get_editor_settings().get_setting("run/output/max_lines"))\n'
        f'    if diagnostic_cap != {cap}:\n'
        '        _fail("DIAGNOSTIC_OUTPUT_CAP_READBACK")\n        return\n'
        '    print("HH_S71_OUTPUT_CAP " + str(diagnostic_cap))\n').encode()
    driver.write_bytes(raw.replace(old, readback + old))
    initial = n.project_files(project)
    for name, digest in source.items():
        data = n.read_regular(n.STUDIO / name)
        assert n.sha(data) == digest
        n.write(root / 'source/studio' / name, data)
    n.write(root / 'diagnostic.json', {'full_benchmark': False, 'formal_acceptance': False,
        'run_id': run_id, 'output_max_lines': cap, 'batches': 3, 'cycles_per_batch': 50,
        'outer_wall_seconds': 180, 'native_owner_limits_unchanged': True,
        'source_files': source, 'initial_project_files': initial,
        'runner_sha256': n.sha(Path(__file__).read_bytes()), 'binding': binding})
    owner = None
    try:
        imported = n.native_job.run_trusted_stage(
            [str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=source, source_root=n.STUDIO,
            binary_sha256=lock['gui_sha256'])
        n.native_job.verify_captured_stage(root / 'import-host', n.sha(n.read_regular(root / 'import-host/capture.json')))
        snapshot = n.project_files(project)
        assert all(snapshot.get(k) == v for k, v in initial.items()), 'import source drift'
        runtime = dict(source)
        runtime.update({(project / name).relative_to(n.STUDIO).as_posix(): value
            for name, value in snapshot.items() if name != n.MUTABLE_SCENE})
        n.write(root / 'runtime-source-files.json', runtime)
        owner = BenchmarkProcess([str(executable), '--editor', '--path', str(project),
            'res://scenes/fixture.tscn', '--', '--hh-benchmark-mode=diagnostic'],
            cwd=project, output=root / 'editor-host', source_root=n.STUDIO,
            source_files=runtime, binary_sha256=lock['gui_sha256'])
        deadline = time.monotonic() + 180
        while owner.tick(stop=time.monotonic() >= deadline) is None:
            time.sleep(.1)
        capture = owner.finish()
        verify_capture(root / 'editor-host', n.sha(n.read_regular(root / 'editor-host/capture.json')),
            source_root=n.STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        for lane in ('import-host', 'editor-host'):
            assert not (root / lane / 'stderr.txt').read_bytes().strip(), lane + ' stderr'
            stdout = (root / lane / 'stdout.txt').read_bytes()
            assert not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED', stdout), lane
        assert n.source_files() == source, 'source changed'
        batches = [json.loads(path.read_bytes()) for path in sorted((project / 'benchmark/out').glob('batch-*.json'))]
        assert len(batches) == 3 and all(len(row['cycles']) == 50 for row in batches)
        result = {'formal_acceptance': False, 'full_benchmark': False,
            'completed_diagnostic': True, 'output_max_lines': cap,
            'batches': [{'index': row['batch_index'], 'memory': row['memory']} for row in batches],
            'actual_process_exit': capture['actual_process_exit'], 'job': capture['job'],
            'capture_sha256': n.sha(n.read_regular(root / 'editor-host/capture.json'))}
        n.write(root / 'result.json', result)
        print(json.dumps(result), flush=True)
        return result
    except BaseException as exc:
        n.write(root / 'failure.json', {'type': type(exc).__name__, 'detail': str(exc), 'formal_acceptance': False})
        raise
    finally:
        if owner is not None:
            owner.close()


if __name__ == '__main__':
    for cap in (10000, 100):
        run(cap)
