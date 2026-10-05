"""O1.9 diagnostic: current fixture, stock editor with NO enabled plugins.

Only the owned editor receives WM_CLOSE after 720 seconds of external sampling.
The original 780-second diagnostic deadline and all benchmark Job limits stay
unchanged. No HTTP/native cycles, injected script or acceptance verdict.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as w
import hashlib
import json
from pathlib import Path
import re
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess, require, verify_capture
from studio.host.replay.process_probe import ProcessProbe
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage

IDLE_SECONDS = 720
DEADLINE_SECONDS = 780
SAMPLE_SECONDS = .25


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stock_files(factory, trusted):
    # Retain fixture and editor overrides, remove both installed hh_studio and
    # benchmark instrumentation. No observation plugin is added in their place.
    config = native.benchmark_project_config(trusted['project.godot'])
    sections = re.split(rb'(?=^\[)', config, flags=re.MULTILINE)
    config = b''.join(section for section in sections
                      if not section.startswith(b'[editor_plugins]'))
    files = {name: raw for name, raw in trusted.items() if not name.startswith('addons/')}
    files.update({'project.godot': config, 'scenes/fixture.tscn': factory.DEFAULT_SCENE,
                  'scripts/fixture_actor.gd': factory.DEFAULT_SCRIPT})
    return files


def source_files(project):
    files = campaign.source_files()
    path = Path(__file__).resolve()
    files[path.relative_to(STUDIO).as_posix()] = sha(path)
    files.update({(project / name).relative_to(STUDIO).as_posix(): digest
                  for name, digest in native.project_files(project).items()})
    return files


def verify_sources(files):
    for name, digest in files.items():
        require(sha(STUDIO / name) == digest, 'STOCK_SOURCE_CHANGED')


def observe_preflight(root):
    """Observe an actual minute; CPU timing is scheduling, never acceptance."""
    policy = campaign.environment.Policy()
    started = time.monotonic()
    rows = []
    with (root / 'dispatch-environment.jsonl').open('x', encoding='utf-8') as stream:
        while True:
            row = campaign.environment_preflight()
            stream.write(json.dumps(row, sort_keys=True) + '\n')
            stream.flush()
            rows.append(row)
            campaign.require_environment_preflight(row)
            require(policy.observe(row) is None, 'STOCK_DISPATCH_ENVIRONMENT_UNSTABLE')
            if time.monotonic() - started >= 60:
                break
            time.sleep(5)
    cpu = []
    for previous, current in zip(rows, rows[1:]):
        total = current['cpu_total_100ns'] - previous['cpu_total_100ns']
        idle = current['cpu_idle_100ns'] - previous['cpu_idle_100ns']
        require(total > 0 and 0 <= idle <= total, 'STOCK_DISPATCH_CPU_DELTA')
        cpu.append(100 * (total - idle) / total)
    campaign.write(root / 'dispatch-preflight.json', {
        'duration_seconds': time.monotonic() - started, 'samples': len(rows),
        'cpu_max_percent': max(cpu), 'cpu_mean_percent': sum(cpu) / len(cpu),
        'available_min_bytes': min(r['available_memory_bytes'] for r in rows),
        'commit_max_percent': max(r['commit_used_percent'] for r in rows),
        'all_preflights_pass': True, 'formal_acceptance': False})


def request_owned_close(probe):
    """Close only a visible window belonging to the retained live identity."""
    observed = probe.sample_with_handle_count()
    require(observed is not None, 'STOCK_EXIT_BEFORE_CLOSE')
    windows = observed['visible_window_handles']
    require(len(windows) == 1, 'STOCK_CLOSE_WINDOW_AMBIGUOUS')
    hwnd = int(windows[0])
    owner = w.DWORD()
    require(probe.u.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            and owner.value == probe.pid, 'STOCK_CLOSE_WINDOW_OWNER')
    require(probe.k.WaitForSingleObject(probe.handle, 0) == 258, 'STOCK_CLOSE_TARGET_EXITED')
    post = probe.u.PostMessageW
    post.argtypes, post.restype = [w.HWND, w.UINT, w.WPARAM, w.LPARAM], w.BOOL
    require(post(hwnd, 0x0010, 0, 0), 'STOCK_CLOSE_REQUEST')  # WM_CLOSE, not termination.
    return {'pid': probe.pid, 'process_start': probe.process_start,
            'hwnd': str(hwnd), 'message': 'WM_CLOSE', 'observation': observed}


def run(run_id):
    require(re.fullmatch(r'gt06-[a-z0-9-]{1,25}', run_id) is not None, 'STOCK_RUN_ID')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    project = root / 'project'
    owner = probe = watchdog = None
    failure = None
    cleanup_errors = []
    result = None
    try:
        factory, trusted = native.load_fixture()
        for name, raw in stock_files(factory, trusted).items():
            native.write(project / name, raw)
        lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
        exe = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
        require(sha(exe) == lock['gui_sha256'], 'STOCK_BINARY_PIN')
        before = source_files(project)
        binding = {'run_id': run_id, 'source_closure_sha256': native.closure(before),
                   'campaign_sha256': native.sha(native.encoded({'run_id': run_id, 'files': before}))}
        campaign.write(root / 'freeze.json', {**binding, 'source_files': before,
            'binary_sha256': lock['gui_sha256'], 'executable': str(exe),
            'idle_seconds': IDLE_SECONDS, 'deadline_seconds': DEADLINE_SECONDS,
            'sample_seconds': SAMPLE_SECONDS, 'authority': 0, 'formal_acceptance': False,
            'plugins_enabled': [], 'workload': 'stock_editor_idle_external_observer'})
        # Preserve exact source bytes, including the fixture snapshot, outside
        # the editor's project; import cannot turn evidence into assets.
        for name in before:
            native.write(root / 'source' / name, (STUDIO / name).read_bytes())
        verify_sources(before)
        with campaign.environment.KeepAwake():
            observe_preflight(root)
            out = root / 'import-host'
            run_trusted_stage([str(exe), '--headless', '--editor', '--path', str(project), '--import'],
                cwd=project, output=out, source_root=STUDIO, source_files=before,
                binary_sha256=lock['gui_sha256'])
            verify_captured_stage(out, sha(out / 'capture.json'))
            require(not (out / 'stderr.txt').read_bytes().strip(), 'STOCK_IMPORT_STDERR')
            verify_sources(before)
            runtime = source_files(project)  # Include generated UID files after import.
            campaign.write(root / 'runtime-freeze.json', {'files': runtime,
                'source_closure_sha256': native.closure(runtime), 'formal_acceptance': False})
            fresh = campaign.environment_preflight()
            campaign.write(root / 'environment-preflight-before.json', fresh)
            campaign.require_environment_preflight(fresh)
            owner = BenchmarkProcess([str(exe), '--editor', '--path', str(project),
                'res://scenes/fixture.tscn'], cwd=project, output=root / 'editor-host',
                source_root=STUDIO, source_files=runtime, binary_sha256=lock['gui_sha256'])
            launched = time.monotonic()
            watchdog = campaign.environment.Watchdog(root,
                lambda: campaign.environment_snapshot(job_handle=owner.job._handle, docker_inventory=[]), binding,
                campaign.write, docker_probe=campaign.environment.running_containers)
            while not (owner.output / 'process-start.json').is_file():
                watchdog.poll()
                require(owner.tick() is None and time.monotonic() - launched < 15, 'STOCK_START_FAILED')
                time.sleep(.05)
            pid = json.loads((owner.output / 'process-start.json').read_bytes())['pid']
            probe = ProcessProbe(pid, exe)
            samples = 0
            closed = False
            sample_start = time.monotonic()
            campaign.write(root / 'sampling-start.json', {'pid': pid, 'process_start': probe.process_start,
                'observer_pid': __import__('os').getpid(), 'formal_acceptance': False})
            with (root / 'samples.jsonl').open('x', encoding='utf-8') as stream:
                while owner.tick() is None:
                    watchdog.poll()
                    require(time.monotonic() - launched < DEADLINE_SECONDS, 'STOCK_EDITOR_DEADLINE')
                    observed = probe.sample_with_handle_count()
                    if observed is not None:
                        observed['elapsed_seconds'] = time.monotonic() - sample_start
                        stream.write(json.dumps(observed, separators=(',', ':')) + '\n')
                        samples += 1
                        if samples % 20 == 0:
                            stream.flush()
                    if not closed and time.monotonic() - sample_start >= IDLE_SECONDS:
                        campaign.write(root / 'close-request.json', request_owned_close(probe))
                        closed = True
                    time.sleep(SAMPLE_SECONDS)
            require(closed, 'STOCK_PREMATURE_EXIT')
            exit_observation = probe.exit_observation()
            capture = owner.finish()
            probe.close()
            watchdog.close()
            campaign.environment.verify_watchdog(root, campaign.read_regular, expected_binding=binding,
                elapsed_seconds=capture['elapsed_seconds'], require_docker_inventory=True)
            verify_capture(owner.output, sha(owner.output / 'capture.json'), source_root=STUDIO,
                expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
            require(not (owner.output / 'stderr.txt').read_bytes().strip(), 'STOCK_EDITOR_STDERR')
            require(exit_observation is not None and exit_observation['exit_code'] == 0, 'STOCK_EXIT_OBSERVATION')
            verify_sources(runtime)
            result = {**binding, 'authority': 0, 'formal_acceptance': False,
                'completed_idle_control': True, 'sample_count': samples,
                'actual_target_exit': capture['actual_process_exit'], 'retained_exit': exit_observation,
                'job': capture['job'], 'probe_released': probe.handle is None,
                'samples_sha256': sha(root / 'samples.jsonl'),
                'capture_sha256': sha(owner.output / 'capture.json')}
    except BaseException as error:
        failure = error
        owner = owner or getattr(error, 'cleanup_owner', None)
    finally:
        for stage, resource in (('watchdog', watchdog), ('probe', probe), ('owner', owner)):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    cleanup_errors.append({'stage': stage, 'type': type(error).__name__,
                                           'code': getattr(error, 'code', None)})
        try:
            campaign.write(root / 'environment-preflight-after.json', campaign.environment_preflight())
        except BaseException as error:
            cleanup_errors.append({'stage': 'inventory', 'type': type(error).__name__})
    if failure is not None or cleanup_errors:
        campaign.write(root / 'failure.json', {'code': getattr(failure, 'code', type(failure).__name__),
            'classification': getattr(failure, 'classification', 'DIAGNOSTIC_FAIL'),
            'cleanup_errors': cleanup_errors, 'formal_acceptance': False})
        if failure is not None:
            raise failure
        raise RuntimeError('STOCK_CLEANUP_FAILED')
    campaign.write(root / 'result.json', result)
    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.run_id))
