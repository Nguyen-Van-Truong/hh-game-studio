"""Disposable S91 targeted identity diagnostic; no campaign acceptance.

Run the original 51-file campaign child with only a copied native pre-batch
probe. No ACK, workload, timing or threshold is weakened. The external observer
owns and records process exits; failures retain a separate partial manifest.
"""
from pathlib import Path
from dataclasses import asdict
import hashlib
import json
import os
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
RUN_ID = 'gt06-s91-sparse-attribution-01'
PREFLIGHT_ID = 'gt06-s91-sparse-attribution-preflight-01'
EXPECTED_SOURCE = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
EXPECTED_PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'


def modules():
    from studio.tests.replay import run_benchmark_campaign as c
    c.load_fixture()
    files = c.source_files()
    c.require(len(files) == 51 and c.closure(files) == EXPECTED_SOURCE,
              'S91_BASE_SOURCE')
    c.require(c.profile.PROFILE_SHA256 == EXPECTED_PROFILE, 'S91_PROFILE')
    return c, files


def helpers():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), BASE / 'object_probe_s91.gd', BASE / 'patch_native_s91.py', BASE / 'launch_observer.py', BASE / 'register_task.ps1', BASE / 'test_launch_observer.py')}


from patch_native_s91 import patch_native


def install_prepare(c, output):
    original = c.prepare

    def prepared(project, factory, trusted, binding):
        original(project, factory, trusted, binding)
        native = project / 'addons/hh_benchmark/benchmark_native.gd'
        before = native.read_bytes()
        probe = (BASE / 'object_probe_s91.gd').read_text(encoding='utf-8-sig')
        after = patch_native(before, probe)
        native.write_bytes(after)  # Disposable project before import only.
        c.require(native.read_bytes() == after, 'S91_COPY_READBACK')
        c.write(output / 'native-overlay.json', {
            'base_sha256': c.sha(before), 'effective_sha256': c.sha(after),
            'probe_sha256': c.sha((BASE / 'object_probe_s91.gd').read_bytes()),
            'patch': 'targeted TreeItem/Node3D primitive identity census at baseline and first same-phase growth; no threshold changes',
            'runtime_source_modified': False, 'thresholds_modified': False,
            'formal_acceptance': False, 'eligible_for_dataset': False,
            'scope': 'pre-batch targeted partial inventory before host baseline sample; ACK schema/code unchanged'})
        return c.project_files(project)

    c.prepare = prepared


def write_inputs(c, files, output, run_id):
    output.mkdir(exist_ok=False)
    helper_map = helpers()
    meta = {'run_id': run_id, 'base_source_files': files,
        'base_source_closure_sha256': c.closure(files), 'helper_files': helper_map,
        'profile_sha256': c.profile.PROFILE_SHA256, 'workstation': c.workstation_profile(),
        'sequence': c.SEQUENCE, 'run_count': 1, 'maximum_batches': 35,
        'http_commands_per_batch': 1000, 'native_cycles_per_batch': 100,
        'wall_limit_seconds': 7410, 'formal_acceptance': False,
        'eligible_for_dataset': False, 'full_benchmark': False,
        'scope': 'instrumented diagnostic; native full mode retains original scheduling and gates'}
    c.write(output / 'diagnostic.json', meta)
    c.write(output / 'context.json', {'run_id': run_id, 'index': 0, 'attempt': 1,
        'source_files': files, 'source_closure_sha256': c.closure(files),
        'profile_sha256': c.profile.PROFILE_SHA256,
        'campaign_sha256': c.sha(c.read_regular(output / 'diagnostic.json'))})
    c.write(output / 'source-files.json', files)
    c.write(output / 'toolchain.lock.json', c.read_regular(STUDIO / 'toolchain.lock.json'))
    c.write(output / 'benchmark-profile.json', json.dumps(asdict(c.profile.PROFILE),
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
    for relative, digest in {**{'studio/' + k: v for k, v in files.items()}, **helper_map}.items():
        raw = (ROOT / relative).read_bytes()
        c.require(c.sha(raw) == digest, 'S91_FREEZE_CHANGED')
        c.write(output / 'source' / relative, raw)
    return meta


def preflight():
    c, files = modules()
    output = STUDIO / '.local/reviews' / PREFLIGHT_ID
    meta = write_inputs(c, files, output, PREFLIGHT_ID)
    install_prepare(c, output)
    factory, trusted = c.load_fixture()
    binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
        'run_id': PREFLIGHT_ID, 'mode': 'full', 'source_closure_sha256': c.closure(files),
        'profile_sha256': c.profile.PROFILE_SHA256,
        'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}
    project = output / 'project'
    initial = c.prepare(project, factory, trusted, binding)
    (project / 'benchmark/input').mkdir()
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    import_sources = {**files, **{
        (project / name).relative_to(STUDIO).as_posix(): value for name, value in initial.items()}}
    c.native_job.run_trusted_stage([str(executable), '--headless', '--editor', '--path', str(project), '--import'],
        cwd=project, output=output / 'import-host', source_files=import_sources,
        source_root=STUDIO, binary_sha256=lock['gui_sha256'])
    c.native_job.verify_captured_stage(output / 'import-host',
        c.sha(c.read_regular(output / 'import-host/capture.json')))
    c.require(not (output / 'import-host/stderr.txt').read_bytes().strip(), 'S91_PREFLIGHT_STDERR')
    c.require(not list((project / 'benchmark/out').iterdir()), 'S91_IMPORT_ACTIVATED')
    c.require(all(c.project_files(project).get(k) == v for k, v in initial.items()), 'S91_IMPORT_DRIFT')
    c.verify_sources(files)
    c.require(helpers() == meta['helper_files'], 'S91_PREFLIGHT_HELPER_DRIFT')
    c.write(output / 'preflight.json', {'verified_import': True,
        'helper_files': meta['helper_files'], 'base_source_closure_sha256': c.closure(files),
        'overlay': json.loads((output / 'native-overlay.json').read_bytes()),
        'formal_acceptance': False, 'runtime_attribution_not_yet_exercised': True})
    return 0


def child():
    c, files = modules()
    output = STUDIO / '.local/reviews' / RUN_ID
    meta = json.loads((output / 'diagnostic.json').read_bytes())
    c.require(meta['helper_files'] == helpers() and meta['base_source_files'] == files,
        'S91_CHILD_BINDING')
    install_prepare(c, output)
    c.run_child(output)
    # A completed base child still cannot enter a campaign dataset: this run has
    # no campaign.json/assembly manifest and the explicit diagnostic overlay.
    return 0


def parent():
    c, files = modules()
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    pre = STUDIO / '.local/reviews' / PREFLIGHT_ID
    checked = json.loads((pre / 'preflight.json').read_bytes())
    c.require(checked['verified_import'] is True and checked['helper_files'] == helpers(),
        'S91_PREFLIGHT_BINDING')
    output = STUDIO / '.local/reviews' / RUN_ID
    meta = write_inputs(c, files, output, RUN_ID)
    # Exclusive creation above prevents duplicate starts. Parent only owns the
    # child and descendants it creates; it does not stop unrelated processes.
    with (output / 'supervisor-stdout.txt').open('x', encoding='utf-8', buffering=1) as stdout, \
         (output / 'supervisor-stderr.txt').open('x', encoding='utf-8', buffering=1) as stderr:
        sys.stdout, sys.stderr = stdout, stderr
        c.write(output / 'supervisor-start.json', {'pid': os.getpid(),
            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'formal_acceptance': False})
        owner = primary = cleanup_error = None
        code = 1
        try:
            owner = BenchmarkProcess([sys.executable, '-B', str(Path(__file__)), '--owned-child'],
                cwd=output, output=output / 'host-owner', source_root=ROOT,
                source_files={**{'studio/' + k: v for k, v in files.items()}, **meta['helper_files']},
                binary_sha256=c.sha(Path(sys.executable).read_bytes()), campaign_host=True)
            context = json.loads((output / 'context.json').read_bytes())
            c.wait_owned_run(owner, output, run_id=RUN_ID,
                source_closure_sha256=c.closure(files), campaign_sha256=context['campaign_sha256'])
            owner.finish()
            child_result = json.loads(c.read_regular(output / 'child-result.json'))
            c.verify_child_terminal_cleanup(output, context, child_result)
            c.verify_capture(output / 'host-owner', c.sha(c.read_regular(output / 'host-owner/capture.json')),
                source_root=ROOT, expected_source_files={**{'studio/' + k: v for k, v in files.items()}, **meta['helper_files']},
                expected_binary_sha256=c.sha(Path(sys.executable).read_bytes()), expected_campaign_host=True)
            snapshot = json.loads(c.read_regular(output / 'editor-snapshot.json'))
            runtime = {**files, **{(output / 'project' / name).relative_to(STUDIO).as_posix(): value
                for name, value in snapshot.items() if name != c.MUTABLE_SCENE}}
            lock = json.loads(c.read_regular(output / 'toolchain.lock.json'))['godot']
            c.verify_capture(output / 'editor-host', c.sha(c.read_regular(output / 'editor-host/capture.json')),
                source_root=STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
            c.native_job.verify_captured_stage(output / 'import-host',
                c.sha(c.read_regular(output / 'import-host/capture.json')))
            c.verify_sources(files)
            c.require(helpers() == meta['helper_files'], 'S91_HELPER_CHANGED')
            code = 0
        except BaseException as error:
            primary = error
            owner = owner or getattr(error, 'cleanup_owner', None)
            traceback.print_exc()
        finally:
            if owner is not None:
                try:
                    owner.close()
                except BaseException as error:
                    cleanup_error = error
                    code = 1
                    traceback.print_exc()
            c.write(output / 'supervisor-return.json', {'returned_exit_code': code,
                'primary_error': getattr(primary, 'code', type(primary).__name__) if primary else None,
                'cleanup_error': getattr(cleanup_error, 'code', type(cleanup_error).__name__) if cleanup_error else None,
                'owner_closed': owner.closed if owner else None,
                'owned_tree_zero': owner.job.zero_observed if owner and owner.job else None,
                'own_actual_exit_not_yet_observed': True,
                'eligible_for_dataset': False, 'formal_acceptance': False})
        # Subprocess logs are closed by owner.close(). Freeze only emitted
        # evidence; a missing exit stays missing and the external observer adds
        # its retained-handle record in a separate hash domain after this exit.
        sys.stdout.flush()
        sys.stderr.flush()
        selected = sorted(set(output.glob('*.json')) | set(output.glob('*.txt')) | set(output.glob('*/process-*.json'))
            | set(output.glob('*/capture.json')) | set(output.glob('*/cleanup*.json')) | set(output.glob('*/invocation.json'))
            | set(output.glob('*/stdout.txt')) | set(output.glob('*/stderr.txt'))
            | set((output / 'project/benchmark/out').glob('*.json'))
            | set((output / 'project/benchmark/input').glob('*.json')))
        missing = [name for name in ('child-result.json', 'child-terminal-cleanup.json',
            'host-owner/process-exit.json', 'editor-host/process-exit.json', 'import-host/process-exit.json')
            if not (output / name).is_file()]
        c.write(output / 'diagnostic-manifest.json', {
            'schema_id': 'hh-studio.gt06.s91-diagnostic-manifest', 'schema_version': '1.0.0',
            'run_id': RUN_ID, 'returned_exit_code': code,
            'outcome': 'DIAGNOSTIC_COMPLETE' if code == 0 else 'DIAGNOSTIC_FAILED',
            'formal_acceptance': False, 'eligible_for_dataset': False,
            'source_closure_sha256': c.closure(files), 'helper_files': meta['helper_files'],
            'profile_sha256': c.profile.PROFILE_SHA256,
            'missing_terminal_artifacts': missing, 'supervisor_actual_exit_not_yet_observed': True,
            'artifacts': {path.relative_to(output).as_posix():
                {'sha256': c.sha(c.artifact_bytes(path)), 'size_bytes': path.stat().st_size}
                for path in selected}})
        return code


if __name__ == '__main__':
    # Windowless supervisor uses the console companion only inside owned Jobs.
    sys.executable = str(Path(sys.executable).with_name('python.exe'))
    mode = sys.argv[1:]
    if mode == ['--preflight']:
        raise SystemExit(preflight())
    if mode == ['--owned-child']:
        raise SystemExit(child())
    if mode == ['--supervisor']:
        raise SystemExit(parent())
    raise SystemExit('Expected fixed --preflight, --supervisor or --owned-child mode.')
