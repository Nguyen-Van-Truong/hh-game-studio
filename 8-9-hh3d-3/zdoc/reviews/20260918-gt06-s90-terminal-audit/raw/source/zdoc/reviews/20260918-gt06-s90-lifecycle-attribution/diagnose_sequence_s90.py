"""One disposable low-overhead ACK lifecycle diagnostic.

No runtime file or gate is changed. The base campaign child and screen_sample
execute unchanged. Only prepare() decorates the copied native plugin, sampling
scalar ObjectDB counters around ACK FileAccess close/null and writing a small
diagnostic receipt. This adds overhead: the run is diagnostic, NEVER an eligible
campaign sample or final critic proof.
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
RUN_ID = 'gt06-s90-lifecycle-attribution-01'
PREFLIGHT_ID = 'gt06-s90-lifecycle-attribution-preflight-06'
EXPECTED_SOURCE = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
EXPECTED_PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'


def modules():
    from studio.tests.replay import run_benchmark_campaign as c
    c.load_fixture()
    files = c.source_files()
    c.require(len(files) == 51 and c.closure(files) == EXPECTED_SOURCE,
              'S90_BASE_SOURCE')
    c.require(c.profile.PROFILE_SHA256 == EXPECTED_PROFILE, 'S90_PROFILE')
    return c, files


def helpers():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), BASE / 'lifecycle_probe_s90.gd')}


def patch_native(raw, probe):
    script = raw.decode('utf-8')
    write_start = script.index('func _write_batch()')
    close_anchor = '    var raw: PackedByteArray = file.get_buffer(size)\n    file.close()\n'
    wait_start = script.index('func _wait_host_ack()')
    write_part = script[write_start:wait_start]
    batch_anchor = '    var memory: Dictionary = {"phase": "post_batch_quiescent",'
    if write_part.count(batch_anchor) != 1:
        raise ValueError('S90_BATCH_COUNTER_PATCH_POINT')
    write_part = write_part.replace(batch_anchor,
        '    _s90_batch_objects = int(objects)\n'
        '    _s90_batch_resources = int(resources)\n'
        '    _s90_batch_mono_us = ended\n' + batch_anchor, 1)
    wait_part = script[wait_start:]
    if wait_part.count(close_anchor) != 1:
        raise ValueError('S90_ACK_FILE_PATCH_POINT')
    preopen_anchor = '    if not FileAccess.file_exists(path):\n        return\n'
    if wait_part.count(preopen_anchor) != 1:
        raise ValueError('S90_ACK_PREOPEN_PATCH_POINT')
    wait_part = wait_part.replace(preopen_anchor, preopen_anchor +
        '    var s90_ack_preopen: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))\n', 1)
    patched_wait = wait_part.replace(close_anchor, close_anchor +
        '    var s90_after_close: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))\n'
        '    file = null\n'
        '    var s90_after_release: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))\n', 1)
    script = script[:write_start] + write_part + patched_wait
    fresh_anchor = '    _heartbeat(true)\n    _barrier_receipts.append({'
    if script.count(fresh_anchor) != 1:
        raise ValueError('S90_RECEIPT_PATCH_POINT')
    script = script.replace(fresh_anchor,
        '    _s90_write_lifecycle(_batch, s90_ack_preopen, s90_after_close, s90_after_release, _s90_batch_objects, _s90_batch_resources, int(objects), int(resources), _s90_batch_mono_us, process_frame)\n'
        '    if _failed:\n        return\n' + fresh_anchor, 1)
    # The disposable helper begins at byte zero, so anchor the marker without
    # requiring a leading newline.  Keep this exact boundary so only the
    # helper body is appended to the copied native script.
    marker = '# S90_LIFECYCLE_HELPER_BOUNDARY\n'
    if probe.count(marker) != 1:
        raise ValueError('S90_HELPER_BOUNDARY')
    script += '\n' + probe.split(marker, 1)[1]
    return script.encode('utf-8')

def install_prepare(c, output):
    original = c.prepare

    def prepared(project, factory, trusted, binding):
        original(project, factory, trusted, binding)
        native = project / 'addons/hh_benchmark/benchmark_native.gd'
        before = native.read_bytes()
        probe = (BASE / 'lifecycle_probe_s90.gd').read_text(encoding='utf-8-sig')
        after = patch_native(before, probe)
        native.write_bytes(after)  # Disposable project before import only.
        c.require(native.read_bytes() == after, 'S90_COPY_READBACK')
        c.write(output / 'native-overlay.json', {
            'base_sha256': c.sha(before), 'effective_sha256': c.sha(after),
            'probe_sha256': c.sha((BASE / 'lifecycle_probe_s90.gd').read_bytes()),
            'patch': 'low-overhead ACK FileAccess close/null lifecycle counters; no object census and no threshold changes',
            'runtime_source_modified': False, 'thresholds_modified': False,
            'formal_acceptance': False, 'eligible_for_dataset': False,
            'scope': 'ACK FileAccess after-close versus after-null counters plus fresh batch counter; diagnostic only; no identity census'})
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
        c.require(c.sha(raw) == digest, 'S90_FREEZE_CHANGED')
        c.write(output / 'source' / relative, raw)
    return meta


def preflight():
    c, files = modules()
    output = STUDIO / '.local/reviews' / PREFLIGHT_ID
    write_inputs(c, files, output, PREFLIGHT_ID)
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
    c.require(not (output / 'import-host/stderr.txt').read_bytes().strip(), 'S90_PREFLIGHT_STDERR')
    c.require(not list((project / 'benchmark/out').iterdir()), 'S90_IMPORT_ACTIVATED')
    c.require(all(c.project_files(project).get(k) == v for k, v in initial.items()), 'S90_IMPORT_DRIFT')
    c.verify_sources(files)
    c.write(output / 'preflight.json', {'verified_import': True,
        'helper_files': helpers(), 'base_source_closure_sha256': c.closure(files),
        'overlay': json.loads((output / 'native-overlay.json').read_bytes()),
        'formal_acceptance': False, 'runtime_lifecycle_not_yet_exercised': True})
    return 0


def child():
    c, files = modules()
    output = STUDIO / '.local/reviews' / RUN_ID
    meta = json.loads((output / 'diagnostic.json').read_bytes())
    c.require(meta['helper_files'] == helpers() and meta['base_source_files'] == files,
        'S90_CHILD_BINDING')
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
        'S90_PREFLIGHT_BINDING')
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
            # Bind a successful diagnostic to the real nested target/helper
            # exits and cleanup receipts.  This is deliberately a diagnostic
            # manifest, never the GT-06 acceptance assembly manifest.
            required = [
                output / 'child-result.json',
                output / 'child-terminal-cleanup.json',
                output / 'host-owner/capture.json',
                output / 'host-owner/process-exit.json',
                output / 'editor-host/capture.json',
                output / 'editor-host/process-exit.json',
                output / 'import-host/capture.json',
                output / 'import-host/process-exit.json',
            ]
            c.require(all(path.is_file() for path in required), 'S90_TERMINAL_RECEIPTS')
            child = json.loads(c.read_regular(output / 'child-result.json'))
            cleanup = json.loads(c.read_regular(output / 'child-terminal-cleanup.json'))
            host = json.loads(c.read_regular(output / 'host-owner/capture.json'))
            editor = json.loads(c.read_regular(output / 'editor-host/capture.json'))
            imported = json.loads(c.read_regular(output / 'import-host/capture.json'))
            c.require(child.get('completed') is True and child.get('formal_acceptance') is False,
                      'S90_CHILD_COMPLETE')
            for name, capture in (('host', host), ('editor', editor), ('import', imported)):
                actual = capture.get('actual_process_exit')
                c.require(capture.get('completed') is True and capture.get('natural_tree_exit') is True
                          and capture.get('wrapper_exit_code') == 0
                          and isinstance(actual, dict) and actual.get('exit_code') == 0
                          and capture.get('job', {}).get('closed') is True
                          and capture.get('job', {}).get('zero_observed') is True
                          and capture.get('job', {}).get('tainted') is False,
                          'S90_TERMINAL_' + name.upper())
            c.write(output / 'diagnostic-manifest.json', {
                'schema_id': 'hh-studio.gt06.s90-diagnostic-manifest',
                'schema_version': '1.0.0', 'run_id': RUN_ID,
                'source_closure_sha256': c.closure(files),
                'profile_sha256': c.profile.PROFILE_SHA256,
                'formal_acceptance': False, 'eligible_for_dataset': False,
                'assembly_manifest': None,
                'cleanup_schema_id': cleanup.get('schema_id'),
                'artifacts': {str(path.relative_to(output)).replace('\\', '/'): c.sha(c.read_regular(path))
                              for path in required},
                'native_lifecycle_receipts': sorted(
                    str(path.relative_to(output)).replace('\\', '/')
                    for path in (output / 'project/benchmark/out').glob('lifecycle-*.json')),
            })
            c.verify_sources(files)
            c.require(helpers() == meta['helper_files'], 'S90_HELPER_CHANGED')
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
