"""Bounded diagnostic of census retained memory, never benchmark evidence.

Each arm is a fresh copied native fixture with one semantic cycle. The host
samples retained-handle RSS before census, after census, and after clear.
Godot allocator memory is supplemental and is not used instead of RSS.
"""
from pathlib import Path
import importlib.util
import json
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
EXPECTED = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'


def child(arm, ordinal):
    from studio.tests.replay import run_benchmark_campaign as c
    from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture
    c.load_fixture()
    source = c.source_files()
    assert len(source) == 51 and c.closure(source) == EXPECTED
    original = ROOT / 'zdoc/reviews/20260918-gt06-s82-attribution/object_probe.gd'
    compact = ROOT / 'zdoc/reviews/20260918-gt06-s84-compact-probe/object_probe.gd'
    helper = compact if arm in ('compact', 'compact-growth') else original
    phases_path = BASE / ('cost_growth.gd' if arm == 'compact-growth' else 'cost_phases.gd')
    helper_raw = helper.read_bytes()
    probe_script = helper_raw.decode('utf-8-sig')
    marker = '\n\nfunc _object_probe_after_batch() -> void:'
    if marker in probe_script:
        probe_script = probe_script.split(marker)[0]
    if arm not in ('compact', 'compact-growth'):
        probe_script += '\n\nfunc _object_probe_clear_retained() -> void:\n    _object_probe_previous.clear()\n    _object_probe_signature.clear()\n'
    assert 'func _object_probe_clear_retained()' in probe_script
    run_id = f'gt06-s84-cost-{arm}-{ordinal:02d}'
    root = c.STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = root / 'project'
    factory, trusted = c.load_fixture()
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': run_id, 'mode': 'diagnostic', 'source_closure_sha256': EXPECTED,
        'profile_sha256': c.profile.PROFILE_SHA256, 'batch_barrier': 'diagnostic_none',
        'batch_start': 'diagnostic_immediate'}
    c.prepare(project, factory, trusted, binding)
    (project / 'benchmark/input').mkdir()
    native = project / 'addons/hh_benchmark/benchmark_native.gd'
    script = native.read_text(encoding='utf-8')
    for old, new in [
        ('    if _mode != "full":\n        _advance_batch()', '    if _mode != "full":\n        _cost_begin()'),
        ('    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n', '    if _cost_tick():\n        return\n    var now: int = Time.get_ticks_usec()\n    _heartbeat()\n'),
    ]:
        assert script.count(old) == 1, old
        script = script.replace(old, new)
    phases = phases_path.read_text(encoding='utf-8')
    if arm == 'sham':
        phases = phases.replace('_object_probe_sample("cost_baseline", true)', 'pass')
    script += '\n' + probe_script + '\n' + phases
    native.write_text(script, encoding='utf-8', newline='\n')
    initial = c.project_files(project)
    helpers = {p.relative_to(ROOT).as_posix(): c.sha(p.read_bytes())
               for p in (Path(__file__), phases_path, helper)}
    lock = json.loads((c.STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    executable = c.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    c.write(root / 'invocation.json', {'binding': binding, 'source_files': source,
        'helper_files': helpers, 'initial_project_files': initial, 'arm': arm,
        'formal_acceptance': False, 'wall_limit_seconds': 180})
    for name, digest in {**{'studio/' + k: v for k, v in source.items()}, **helpers}.items():
        raw = (ROOT / name).read_bytes()
        assert c.sha(raw) == digest
        c.write(root / 'source' / name, raw)
    owner = probe = None
    observations = []
    started = time.monotonic()
    try:
        c.native_job.run_trusted_stage([str(executable), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_files=source,
            source_root=c.STUDIO, binary_sha256=lock['gui_sha256'])
        c.native_job.verify_captured_stage(root / 'import-host', c.sha((root / 'import-host/capture.json').read_bytes()))
        assert not (root / 'import-host/stderr.txt').read_bytes().strip()
        assert not list((project / 'benchmark/out').iterdir())
        snapshot = c.project_files(project)
        assert all(snapshot.get(k) == v for k, v in initial.items())
        runtime = {**source, **{(project / k).relative_to(c.STUDIO).as_posix(): v
                   for k, v in snapshot.items() if k != c.MUTABLE_SCENE}}
        c.write(root / 'runtime-source-files.json', runtime)
        owner = BenchmarkProcess([str(executable), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
            '--', '--hh-benchmark-mode=diagnostic'], cwd=project, output=root / 'editor-host',
            source_root=c.STUDIO, source_files=runtime, binary_sha256=lock['gui_sha256'])
        probe = c.open_probe(owner, executable)
        for phase in range(4 if arm == 'compact-growth' else 3):
            path = project / f'benchmark/out/cost-{phase:02d}.json'
            while not path.exists():
                assert owner.tick(stop=time.monotonic() - started > 180) is None, 'COST_EARLY_EXIT'
                time.sleep(.02)
            raw = path.read_bytes()
            point = json.loads(raw)
            assert point['run_id'] == run_id and point['pid'] == probe.pid and point['phase'] == phase
            observed = c.sample_editor(probe)
            row = {'native': point, 'native_sha256': c.sha(raw), 'os': observed}
            c.write(root / f'observation-{phase:02d}.json', row)
            observations.append(row)
            c.write(project / f'benchmark/input/cost-{phase:02d}.ack', run_id.encode())
        while owner.tick(stop=time.monotonic() - started > 180) is None:
            time.sleep(.02)
        captured = owner.finish()
        verify_capture(root / 'editor-host', c.sha((root / 'editor-host/capture.json').read_bytes()),
            source_root=c.STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        assert not (root / 'editor-host/stderr.txt').read_bytes().strip()
        assert len(list((project / 'benchmark/out').glob('batch-*.json'))) == 1
        # Counts may drift during editor startup; record that fact, never make
        # a no-leak claim from these short diagnostic allocation observations.
        c.verify_sources(source)
        assert all(c.sha((ROOT / k).read_bytes()) == v for k, v in helpers.items())
        probe.close()
        probe = None
        owner.close()
        owner = None
        c.write(root / 'result.json', {'completed_cost_diagnostic': True, 'formal_acceptance': False,
            'actual_process_exit': captured['actual_process_exit'], 'job': captured['job'],
            'observations': observations, 'elapsed_seconds': time.monotonic() - started})
    except BaseException as error:
        owner = owner or getattr(error, 'cleanup_owner', None)
        c.write(root / 'failure.json', {'type': type(error).__name__, 'detail': str(error)})
        raise
    finally:
        errors = []
        for name, resource in [('probe', probe), ('owner', owner)]:
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append({'resource': name, 'type': type(error).__name__, 'detail': str(error)})
        c.write(root / 'cleanup.json', {'errors': errors, 'probe_handle_retained': probe.handle is not None if probe else False,
            'owner_closed': owner.closed if owner else True, 'formal_acceptance': False})
        if errors:
            raise RuntimeError('COST_CLEANUP_FAILED')


def outer(arm, ordinal):
    output = BASE / f'{arm}-{ordinal:02d}'
    output.mkdir(exist_ok=False)
    runner = ROOT / 'studio/build/bootstrap/run_fixture.py'
    spec = importlib.util.spec_from_file_location('cost_owned', runner)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import hashlib
    invocation = {'runner_sha256': hashlib.sha256(runner.read_bytes()).hexdigest(),
        'helper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'arm': arm, 'ordinal': ordinal, 'formal_acceptance': False, 'timeout_seconds': 240}
    (output / 'invocation.json').write_text(json.dumps(invocation, indent=2) + '\n', encoding='utf-8')
    result = module.run_process([sys.executable, '-B', str(Path(__file__)), arm, str(ordinal), '--child'],
        cwd=ROOT, output=output, timeout=240, label='cost')
    (output / 'capture.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result), flush=True)
    return 0 if result.get('exit_code') == result.get('wrapper_exit_code') == 0 and result.get('tree_verified') is True and result.get('timed_out') is False else 1


if __name__ == '__main__':
    arm, ordinal, *mode = sys.argv[1:]
    assert arm in ('original', 'compact', 'compact-growth', 'sham') and ordinal.isdigit() and 1 <= int(ordinal) <= 4
    if mode == ['--child']:
        child(arm, int(ordinal))
    else:
        assert not mode
        raise SystemExit(outer(arm, int(ordinal)))
