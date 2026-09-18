"""One disposable S84 compact HTTP/native sequence with sparse object attribution.

No runtime file or gate is changed. The base campaign child and screen_sample
execute unchanged. Only prepare() decorates the copied native plugin, sampling
reachable identities at ACK4 and positive ObjectDB growth. This adds overhead:
the run is diagnostic, NEVER an eligible campaign sample or final critic proof.
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
RUN_ID = 'gt06-s84-attribution-01'
PREFLIGHT_ID = 'gt06-s84-attribution-preflight-01'
EXPECTED_SOURCE = 'e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f'
EXPECTED_PROFILE = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'


def modules():
    from studio.tests.replay import run_benchmark_campaign as c
    c.load_fixture()
    files = c.source_files()
    c.require(len(files) == 51 and c.closure(files) == EXPECTED_SOURCE,
              'ATTRIBUTION_BASE_SOURCE')
    c.require(c.profile.PROFILE_SHA256 == EXPECTED_PROFILE, 'ATTRIBUTION_PROFILE')
    return c, files


def helpers():
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), BASE / 'object_probe.gd')}


def patch_native(raw, probe):
    script = raw.decode('utf-8')
    anchor = '    # Fresh counters after host joint sampling and validated ACK. Never reuse\n'
    if script.count(anchor) != 1:
        raise ValueError('ATTRIBUTION_ACK_PATCH_POINT')
    script = script.replace(anchor,
        '    _attribution_ack()\n    if _failed:\n        return\n' + anchor)
    # Keep only collection/sample helpers, not native-only probe scheduling.
    marker = '\n\nfunc _object_probe_after_batch() -> void:'
    if probe.count(marker) != 1:
        raise ValueError('ATTRIBUTION_PROBE_BOUNDARY')
    script += '\n' + probe.split(marker)[0] + '''

var _attribution_baseline_objects: int = -1


func _attribution_ack() -> void:
    var current: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
    var sampled: bool = false
    if _batch == 4:
        _attribution_baseline_objects = current
        _object_probe_sample("joint_baseline", true)
        sampled = true
    elif _batch > 4 and _attribution_baseline_objects >= 0 and current > _attribution_baseline_objects:
        _object_probe_sample("joint_growth", true)
        sampled = true
    if sampled and not _failed:
        var after_publication: int = int(Performance.get_monitor(Performance.OBJECT_COUNT))
        var receipt: Dictionary = _write_new("attribution-%02d.json" % _batch,
            {"run_id": _input.run_id, "batch": _batch, "objects_before": current,
            "objects_after_publication": after_publication,
            "baseline_objects": _attribution_baseline_objects, "formal_acceptance": false})
        if receipt.is_empty() or after_publication != current:
            _fail("ATTRIBUTION_SELF_DRIFT")
'''
    return script.encode('utf-8')


def install_prepare(c, output):
    original = c.prepare

    def prepared(project, factory, trusted, binding):
        original(project, factory, trusted, binding)
        native = project / 'addons/hh_benchmark/benchmark_native.gd'
        before = native.read_bytes()
        probe = (BASE / 'object_probe.gd').read_text(encoding='utf-8-sig')
        after = patch_native(before, probe)
        native.write_bytes(after)  # Disposable project before import only.
        c.require(native.read_bytes() == after, 'ATTRIBUTION_COPY_READBACK')
        c.write(output / 'native-overlay.json', {
            'base_sha256': c.sha(before), 'effective_sha256': c.sha(after),
            'probe_sha256': c.sha((BASE / 'object_probe.gd').read_bytes()),
            'patch': 'sparse ACK4 baseline and positive ObjectDB growth before fresh ACK counters',
            'runtime_source_modified': False, 'thresholds_modified': False,
            'formal_acceptance': False, 'eligible_for_dataset': False,
            'scope': 'compact ID/class and Tree/RichText summaries; ordinary baseline content unknown; residual ObjectDB unobserved; overhead affects timing and RSS'})
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
        c.require(c.sha(raw) == digest, 'ATTRIBUTION_FREEZE_CHANGED')
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
    c.require(not (output / 'import-host/stderr.txt').read_bytes().strip(), 'ATTRIBUTION_PREFLIGHT_STDERR')
    c.require(not list((project / 'benchmark/out').iterdir()), 'ATTRIBUTION_IMPORT_ACTIVATED')
    c.require(all(c.project_files(project).get(k) == v for k, v in initial.items()), 'ATTRIBUTION_IMPORT_DRIFT')
    c.verify_sources(files)
    c.write(output / 'preflight.json', {'verified_import': True,
        'helper_files': helpers(), 'base_source_closure_sha256': c.closure(files),
        'overlay': json.loads((output / 'native-overlay.json').read_bytes()),
        'formal_acceptance': False, 'runtime_attribution_not_yet_exercised': True})
    return 0


def child():
    c, files = modules()
    output = STUDIO / '.local/reviews' / RUN_ID
    meta = json.loads((output / 'diagnostic.json').read_bytes())
    c.require(meta['helper_files'] == helpers() and meta['base_source_files'] == files,
        'ATTRIBUTION_CHILD_BINDING')
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
        'ATTRIBUTION_PREFLIGHT_BINDING')
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
            c.verify_sources(files)
            c.require(helpers() == meta['helper_files'], 'ATTRIBUTION_HELPER_CHANGED')
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
