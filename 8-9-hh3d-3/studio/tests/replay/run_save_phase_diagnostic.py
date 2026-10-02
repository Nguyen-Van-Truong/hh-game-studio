"""Tier D / AUTHORITY=0: one copied GUI fixture, 100 native save/reload cycles.

Only the disposable driver is patched. Raw timing schemas, tracked driver and
formal gates stay unchanged. Import retains its 20 s native_job budget; editor
uses unchanged BenchmarkProcess limits plus this diagnostic's 180 s deadline.
No automatic retry; existing run directories and failed raw evidence survive.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.run_stock_editor_control import observe_preflight
from studio.tests.replay.benchmark_job import BenchmarkProcess, HELD_OWNERS, require, verify_capture
from studio.tests.replay.measure_window import measurement_window
from studio.host.replay.process_probe import ProcessProbe, HELD_PROBES

CYCLES = 100
DEADLINE_SECONDS = 180
MARKER = 'HH_GT06_SAVE_PHASE '
SCOPE = {'authority': 0, 'tier': 'D', 'formal_acceptance': False, 'full_benchmark': False}


def patched_driver(raw):
    text = raw.decode('utf-8')
    replacements = [
        ('        _cycle_limit = 1\n', '        _cycle_limit = 100\n'),
        ('    var result: Error = EditorInterface.save_scene()\n',
         '    var diagnostic_batch: int = _batch\n'
         '    var diagnostic_cycle: int = _cycle\n'
         '    var diagnostic_start_us: int = int(_timing.save.start_us)\n'
         '    var result: Error = EditorInterface.save_scene()\n'
         '    var diagnostic_return_us: int = Time.get_ticks_usec()\n'
         '    _diagnostic_save_phase("return", diagnostic_return_us, result, diagnostic_batch, diagnostic_cycle, diagnostic_start_us)\n'),
        ('    _save_signal_us = Time.get_ticks_usec()\n',
         '    _save_signal_us = Time.get_ticks_usec()\n'
         '    _diagnostic_save_phase("signal", _save_signal_us)\n'),
    ]
    for old, new in replacements:
        require(text.count(old) == 1, 'SAVE_DIAGNOSTIC_PATCH_ANCHOR')
        text = text.replace(old, new)
    text += '''

func _diagnostic_save_phase(event: String, observed_us: int, result: int = -1, call_batch: int = -1, call_cycle: int = -1, call_start_us: int = -1) -> void:
    print("HH_GT06_SAVE_PHASE " + JSON.stringify({"event": event, "result": result,
        "run_id": _input.run_id, "pid": OS.get_process_id(),
        "batch": _batch if call_batch < 0 else call_batch,
        "cycle": _cycle if call_cycle < 0 else call_cycle,
        "source_closure_sha256": _input.source_closure_sha256, "profile_sha256": _input.profile_sha256,
        "start_us": int(_timing.save.start_us) if call_start_us < 0 else call_start_us,
        "live_batch": _batch, "live_cycle": _cycle, "live_phase": int(_phase),
        "monotonic_us": observed_us}))
'''
    return text.encode('utf-8')


def summarize(raw, batch, binding, pid, cycles=CYCLES):
    """Join supplemental markers to unchanged native timings; allow sync signal."""
    require(batch['run_id'] == binding['run_id'] and batch['pid'] == pid
            and batch['index'] == 0 and len(batch['raw_timings']) == cycles,
            'SAVE_DIAGNOSTIC_BATCH_BINDING')
    rows = {}
    for marker in native.markers(raw, MARKER):
        require(all(marker.get(key) == binding[key] for key in
                    ('run_id', 'source_closure_sha256', 'profile_sha256'))
                and marker.get('pid') == pid and marker.get('batch') == 0,
                'SAVE_DIAGNOSTIC_MARKER_BINDING')
        cycle, event = marker.get('cycle'), marker.get('event')
        require(native.integer(cycle) and cycle < cycles and event in ('return', 'signal'),
                'SAVE_DIAGNOSTIC_MARKER_POSITION')
        require(event not in rows.setdefault(cycle, {}), 'SAVE_DIAGNOSTIC_DUPLICATE_MARKER')
        rows[cycle][event] = marker
    result = []
    for cycle, timing in enumerate(batch['raw_timings']):
        require(timing['index'] == cycle and set(rows.get(cycle, {})) == {'return', 'signal'},
                'SAVE_DIAGNOSTIC_MISSING_MARKER')
        returned, signal = rows[cycle]['return'], rows[cycle]['signal']
        require(all(row.get('live_batch') == 0 and row.get('live_cycle') == cycle
                    for row in (returned, signal)), 'SAVE_DIAGNOSTIC_CALL_IDENTITY_DRIFT')
        start, end = timing['save']['start_us'], timing['save']['end_us']
        ret, sig = returned['monotonic_us'], signal['monotonic_us']
        require(native.integer(start, 1) and native.integer(end, start + 1)
                and all(row['start_us'] == start for row in (returned, signal))
                and all(native.integer(value, start) and value <= end for value in (ret, sig))
                and sig == timing['save_signal_mono_us'] and returned['result'] == 0
                and signal['result'] == -1, 'SAVE_DIAGNOSTIC_MARKER_CLOCK')
        result.append({'cycle': cycle, 'start_us': start, 'return_us': ret, 'signal_us': sig,
            'end_us': end, 'call_ms': (ret - start) / 1000,
            'signal_minus_return_ms': (sig - ret) / 1000,
            'after_return_to_signal_ms': max(0, sig - ret) / 1000,
            'after_both_to_end_ms': (end - max(ret, sig)) / 1000,
            'total_save_ms': (end - start) / 1000})
    beats = native.markers(raw, 'HH_GT06_BENCHMARK_HEARTBEAT ')
    require(len(beats) >= 2 and all(row['run_id'] == binding['run_id'] and row['pid'] == pid
            and native.integer(row['monotonic_us'], 1) for row in beats), 'SAVE_DIAGNOSTIC_HEARTBEAT')
    gaps = [{'gap_ms': (b['monotonic_us'] - a['monotonic_us']) / 1000, 'before': a, 'after': b}
            for a, b in zip(beats, beats[1:])]
    require(all(row['gap_ms'] >= 0 for row in gaps), 'SAVE_DIAGNOSTIC_HEARTBEAT_CLOCK')
    return {'saves': result, 'slowest_save': max(result, key=lambda row: row['total_save_ms']),
            'largest_heartbeat_gap': max(gaps, key=lambda row: row['gap_ms']),
            'native_batch_max_status_gap_ms': batch['max_status_gap_ms'],
            'formula': 'total = call + max(0, signal-return) + end-max(return,signal); all ms',
            'signal_minus_return_is_signed': True, 'root_cause_claim': False}


def project_sources(project, host, *, runtime=False):
    return {**host, **{(project / name).relative_to(STUDIO).as_posix(): digest
        for name, digest in native.project_files(project).items()
        if not runtime or name != native.MUTABLE_SCENE}}


def verify_sources(files):
    require(all(native.sha(native.read_regular(STUDIO / name)) == digest
                for name, digest in files.items()), 'SAVE_DIAGNOSTIC_SOURCE_CHANGED')


def verify_log(directory):
    require(not (directory / 'stderr.txt').read_bytes().strip()
            and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked',
                              (directory / 'stdout.txt').read_bytes()), 'SAVE_DIAGNOSTIC_NATIVE_LOG')


def run_locked(root, run_id):
    owner = probe = watchdog = import_owner = None
    host = frozen = runtime = snapshot = None
    failure = report = None
    cleanup_errors = []
    try:
        factory, trusted = native.load_fixture()
        observe_preflight(root)
        # Apply the existing dispatch timing choice (not all intervals >95%).
        rows = [json.loads(line) for line in (root / 'dispatch-environment.jsonl').read_bytes().splitlines()]
        cpu = [100 * (1 - (b['cpu_idle_100ns'] - a['cpu_idle_100ns']) /
               (b['cpu_total_100ns'] - a['cpu_total_100ns'])) for a, b in zip(rows, rows[1:])]
        require(cpu and not all(value > 95 for value in cpu), 'CAMPAIGN_PREFLIGHT_CPU_BUSY')
        host = native.source_files()  # After imports/preflight, include actual Python closure.
        project = root / 'project'
        driver = patched_driver(native.read_regular(STUDIO / 'tests/replay/benchmark_native.gd'))
        files = {**trusted, 'project.godot': native.benchmark_project_config(trusted['project.godot']),
            native.MUTABLE_SCENE: factory.DEFAULT_SCENE, 'scripts/fixture_actor.gd': factory.DEFAULT_SCRIPT,
            'addons/hh_benchmark/benchmark_native.gd': driver,
            'addons/hh_benchmark/plugin.cfg': native.read_regular(STUDIO / 'tests/replay/benchmark_plugin.cfg'),
            'benchmark/.gdignore': b'# HH Studio benchmark evidence is not a Godot asset.\n'}
        for name, raw in files.items():
            native.write(project / name, raw)
        (project / 'benchmark/out').mkdir()
        # Input excludes itself from its closure to avoid a self-referential hash.
        binding_sources = project_sources(project, host)
        binding = {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
            'run_id': run_id, 'mode': 'diagnostic', 'source_closure_sha256': native.closure(binding_sources),
            'profile_sha256': native.benchmark_profile.PROFILE_SHA256,
            'batch_barrier': 'diagnostic_none', 'batch_start': 'diagnostic_immediate'}
        native.write(project / 'benchmark/input.json', binding)
        frozen = project_sources(project, host)
        lock = json.loads(native.read_regular(STUDIO / 'toolchain.lock.json'))['godot']
        exe = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
        require(native.sha(native.read_regular(exe, 256 * 1024**2)) == lock['gui_sha256'], 'SAVE_DIAGNOSTIC_BINARY_PIN')
        native.write(root / 'freeze.json', {**SCOPE, 'binding': binding, 'source_files': frozen,
            'source_closure_sha256': native.closure(frozen), 'binding_excludes': ['benchmark/input.json'],
            'diagnostic_driver_sha256': native.sha(driver), 'cycles': CYCLES,
            'tracked_driver_sha256': host['tests/replay/benchmark_native.gd'],
            'runner_sha256': host['tests/replay/run_save_phase_diagnostic.py'],
            'editor_deadline_seconds': DEADLINE_SECONDS, 'import_wall_seconds': native.native_job.WALL_SECONDS,
            'benchmark_job_limits_unchanged': True, 'raw_timing_schema_unchanged': True})
        verify_sources(frozen)
        native.native_job.run_trusted_stage([str(exe), '--headless', '--editor', '--path', str(project), '--import'],
            cwd=project, output=root / 'import-host', source_root=STUDIO, source_files=frozen,
            binary_sha256=lock['gui_sha256'])
        imported = native.native_job.verify_captured_stage(root / 'import-host',
            native.sha(native.read_regular(root / 'import-host/capture.json')))
        verify_log(root / 'import-host')
        verify_sources(frozen)
        require(not list((project / 'benchmark/out').iterdir()), 'SAVE_DIAGNOSTIC_IMPORT_ACTIVATED')
        snapshot = native.project_files(project)
        runtime = project_sources(project, host, runtime=True)
        native.write(root / 'runtime-freeze.json', {**SCOPE, 'source_files': runtime,
            'source_closure_sha256': native.closure(runtime), 'mutable_project_paths': [native.MUTABLE_SCENE]})
        fresh = campaign.environment_preflight()
        native.write(root / 'environment-preflight-before.json', fresh)
        campaign.require_environment_preflight(fresh)
        owner = BenchmarkProcess([str(exe), '--editor', '--path', str(project), 'res://scenes/fixture.tscn',
            '--', '--hh-benchmark-mode=diagnostic'], cwd=project, output=root / 'editor-host',
            source_root=STUDIO, source_files=runtime, binary_sha256=lock['gui_sha256'])
        context = {'run_id': run_id, 'source_closure_sha256': binding['source_closure_sha256'],
                   'campaign_sha256': native.sha(native.encoded(binding))}
        watchdog = campaign.environment.Watchdog(root,
            lambda: campaign.environment_snapshot(job_handle=owner.job._handle), context, native.write)
        seen_window = False
        while owner.tick(stop=campaign.stop_requested(root, **context)) is None:
            watchdog.poll()
            require(time.monotonic() - owner.started < DEADLINE_SECONDS, 'SAVE_DIAGNOSTIC_EDITOR_DEADLINE')
            if probe is None and (owner.output / 'process-start.json').is_file():
                probe = ProcessProbe(json.loads((owner.output / 'process-start.json').read_bytes())['pid'], exe)
            if probe is not None:
                sample = probe.sample()
                seen_window |= bool(sample and sample['visible_window_handles'])
            time.sleep(.1)
        exit_observation = probe.exit_observation() if probe else None
        captured = owner.finish()
        verify_capture(owner.output, native.sha(native.read_regular(owner.output / 'capture.json')),
            source_root=STUDIO, expected_source_files=runtime, expected_binary_sha256=lock['gui_sha256'])
        require(seen_window and exit_observation and exit_observation['exit_code'] == 0,
                'SAVE_DIAGNOSTIC_GUI_OR_EXIT')
        watchdog.close()
        campaign.environment.verify_watchdog(root, native.read_regular,
            expected_binding=context, elapsed_seconds=captured['elapsed_seconds'])
        raw = native.read_regular(owner.output / 'stdout.txt')
        batch = json.loads(native.read_regular(project / 'benchmark/out/batch-00.json'))
        index_raw = native.read_regular(project / 'benchmark/out/index.json')
        index = json.loads(index_raw)
        require(index['input'] == binding and index['cycles_per_batch'] == CYCLES
                and index['completed'] is True and index['formal_acceptance'] is False
                and index['benchmark_complete'] is False, 'SAVE_DIAGNOSTIC_INDEX')
        complete = native.markers(raw, 'HH_GT06_BENCHMARK_COMPLETE ')
        require(len(complete) == 1 and complete[0]['run_id'] == run_id
                and complete[0]['pid'] == captured['actual_process_exit']['pid']
                and complete[0]['index_sha256'] == native.sha(index_raw)
                and not native.markers(raw, 'HH_GT06_BENCHMARK_FAILED '), 'SAVE_DIAGNOSTIC_COMPLETE')
        require(len(batch['cycles']) == CYCLES, 'SAVE_DIAGNOSTIC_CYCLES')
        for timing, cycle in zip(batch['raw_timings'], batch['cycles']):
            native.validate_cycle_timing(timing, cycle, batch['memory'], batch)
        report = {**SCOPE, 'run_id': run_id, 'binding': binding,
            **summarize(raw, batch, binding, captured['actual_process_exit']['pid']),
            'actual_exits': {'import': imported['actual_process_exit'], 'editor': captured['actual_process_exit']},
            'jobs': {'import': imported['job'], 'editor': captured['job']},
            'wrapper_process_handle': captured['wrapper_process_handle'],
            'retained_exit': exit_observation, 'index_sha256': native.sha(index_raw),
            'diagnostic_driver_sha256': native.sha(driver), 'completed_diagnostic': True}
        verify_log(root / 'editor-host')
    except BaseException as error:
        failure = error
        retained = getattr(error, 'cleanup_owner', None)
        if isinstance(retained, BenchmarkProcess):
            owner = owner or retained
        else:
            import_owner = retained
    finally:
        for name, resource in (('watchdog', watchdog), ('probe', probe), ('owner', owner), ('import_owner', import_owner)):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    cleanup_errors.append({'stage': name, 'code': getattr(error, 'code', str(error))})
        try:
            if host is not None:
                require(native.source_files() == host, 'SAVE_DIAGNOSTIC_HOST_SOURCE_CHANGED')
            if runtime is not None:
                verify_sources(runtime)
                after = native.project_files(root / 'project')
                require({k: v for k, v in after.items() if k != native.MUTABLE_SCENE} ==
                        {k: v for k, v in snapshot.items() if k != native.MUTABLE_SCENE}, 'SAVE_DIAGNOSTIC_PROJECT_CHANGED')
            elif frozen is not None:
                verify_sources(frozen)
            require(not HELD_OWNERS and not HELD_PROBES and not native.native_job.cli_job.HOLDS,
                    'SAVE_DIAGNOSTIC_RETAINED_OWNERS')
            native.write(root / 'environment-preflight-after.json', campaign.environment_preflight())
        except BaseException as error:
            cleanup_errors.append({'stage': 'source_or_inventory', 'code': getattr(error, 'code', str(error))})
    native.write(root / 'terminal.json', {**SCOPE, 'run_id': run_id,
        'failure': getattr(failure, 'code', str(failure)) if failure else None, 'cleanup_errors': cleanup_errors,
        'owner_closed': owner.closed if owner else None, 'job': owner.job.snapshot() if owner and owner.job else None,
        'wrapper_process_handle': owner.process_handle_snapshot() if owner else None,
        'probe_released': probe is None or probe.handle is None, 'source_unchanged': host is not None and not cleanup_errors,
        'actual_process_exit': json.loads((root / 'editor-host/process-exit.json').read_bytes())
            if (root / 'editor-host/process-exit.json').is_file() else None})
    if report is not None:
        native.write(root / 'save-phase-report.json', {**report, 'diagnostic_checks_pass': failure is None and not cleanup_errors})
    if failure is not None:
        raise failure
    require(not cleanup_errors, 'SAVE_DIAGNOSTIC_CLEANUP_FAILED')
    return 0


def run(run_id):
    require(os.name == 'nt' and re.fullmatch(r'gt06-[a-z0-9-]{1,59}', run_id), 'SAVE_DIAGNOSTIC_ID_OR_PLATFORM')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    with measurement_window(run_id, 'tier-D save phase diagnostic; AUTHORITY=0',
            safe_to_release=lambda: not HELD_OWNERS and not HELD_PROBES and not native.native_job.cli_job.HOLDS):
        with campaign.environment.KeepAwake():
            return run_locked(root, run_id)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    raise SystemExit(run(parser.parse_args().run_id))
