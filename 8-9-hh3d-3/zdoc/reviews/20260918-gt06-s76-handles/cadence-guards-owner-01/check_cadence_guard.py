"""Fresh copied native fixture: invalid cadence configuration must reject before cycles."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as n

parser = argparse.ArgumentParser()
parser.add_argument('variant', choices=['old-key', 'slow', 'float', 'bool', 'missing'])
variant = parser.parse_args().variant
factory, trusted = n.load_fixture()
source = n.source_files()
lock = json.loads(n.read_regular(n.STUDIO / 'toolchain.lock.json'))['godot']
executable = n.STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
root = n.STUDIO / ('.local/reviews/gt06-s76-cadence-' + variant + '-01')
root.mkdir(exist_ok=False)
project = root / 'project'
binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
    'run_id': root.name, 'mode': 'diagnostic', 'source_closure_sha256': n.closure(source),
    'profile_sha256': n.benchmark_profile.PROFILE_SHA256,
    'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
n.prepare(project, factory, trusted, binding)
config = project / 'project.godot'
raw = config.read_bytes()
changes = {
    'old-key': (b'interface/editor/timers/low_processor_mode_sleep_usec=6900', b'interface/editor/low_processor_mode_sleep_usec=6900'),
    'slow': (b'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=6900', b'interface/editor/timers/unfocused_low_processor_mode_sleep_usec=100000'),
    'float': (b'interface/editor/timers/low_processor_mode_sleep_usec=6900', b'interface/editor/timers/low_processor_mode_sleep_usec=6900.0'),
    'bool': (b'interface/editor/display/update_continuously=false', b'interface/editor/display/update_continuously=0'),
    'missing': (b'interface/editor/timers/low_processor_mode_sleep_usec=6900\n', b''),
}
needle, replacement = changes[variant]
assert raw.count(needle) == 1
config.write_bytes(raw.replace(needle, replacement))
initial = n.project_files(project)
for name, digest in source.items():
    data = n.read_regular(n.STUDIO / name)
    assert n.sha(data) == digest
    n.write(root / 'source/studio' / name, data)
n.write(root / 'diagnostic.json', {'source_files': source, 'initial_project_files': initial,
    'binding': binding, 'runner_sha256': n.sha(Path(__file__).read_bytes()),
    'formal_acceptance': False, 'expected_failure': 'BENCHMARK_EDITOR_CADENCE'})
n.native_job.run_trusted_stage([str(executable), '--headless', '--editor', '--path', str(project), '--import'],
    cwd=project, output=root / 'import-host', source_files=source, source_root=n.STUDIO,
    binary_sha256=lock['gui_sha256'])
snapshot = n.project_files(project)
assert all(snapshot.get(k) == v for k, v in initial.items())
runtime = dict(source)
runtime.update({(project / name).relative_to(n.STUDIO).as_posix(): value
    for name, value in snapshot.items() if name != n.MUTABLE_SCENE})
try:
    n.native_job.run_trusted_stage([str(executable), '--editor', '--path', str(project),
        'res://scenes/fixture.tscn', '--', '--hh-benchmark-mode=diagnostic'], cwd=project,
        output=root / 'editor-host', source_files=runtime, source_root=n.STUDIO, binary_sha256=lock['gui_sha256'])
    raise AssertionError('Invalid cadence was not rejected')
except n.native_job.StageFailed as error:
    assert str(error) == 'STAGE_NATIVE_EXIT', str(error)
report = json.loads((root / 'editor-host/capture.json').read_bytes())
exited = json.loads((root / 'editor-host/process-exit.json').read_bytes())
started = json.loads((root / 'editor-host/process-start.json').read_bytes())
assert exited == {'pid': started['pid'], 'exit_code': 86}
assert report['wrapper_exit_code'] == 86 and report['natural_tree_exit'] is True
assert report['active_before_cleanup'] == 0 and report['completed'] is False
job = report['job']
assert job['closed'] and job['zero_observed'] and not job['tainted'] and not job['handle_retained']
stdout = (root / 'editor-host/stdout.txt').read_bytes()
failed = n.markers(stdout, 'HH_GT06_BENCHMARK_FAILED ')
assert len(failed) == 1 and failed[0]['code'] == 'BENCHMARK_EDITOR_CADENCE'
assert not list((project / 'benchmark/out').iterdir())
for marker in ['HH_GT06_BENCHMARK_CYCLE ', 'HH_GT06_BENCHMARK_READY ', 'HH_GT06_BENCHMARK_START ', 'HH_GT06_BENCHMARK_BATCH ', 'HH_GT06_BENCHMARK_CADENCE ']:
    assert not n.markers(stdout, marker)
assert not (root / 'editor-host/stderr.txt').read_bytes().strip()
assert (project / n.MUTABLE_SCENE).read_bytes() == factory.DEFAULT_SCENE
assert n.source_files() == source
n.write(root / 'result.json', {'guard_rejected': True, 'formal_acceptance': False,
    'failure_marker': failed[0], 'actual_exit': exited, 'wrapper_exit': report['wrapper_exit_code'],
    'job': job, 'scene_unchanged': True, 'no_batch': True,
    'capture_sha256': n.sha((root / 'editor-host/capture.json').read_bytes())})
print('CADENCE_GUARD_REJECTED_NATIVE_86_CLEAN_TREE ' + variant, flush=True)
