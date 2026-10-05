"""Run actual GDScript phase logic with injected save callback/return ordering.

This short native regression does NOT call save_scene, reproduce formal14's
latency, or authorize formal acceptance. A copied driver has exactly one API
expression replaced; phase/readback/heartbeat/deadline logic stays unchanged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay.measure_window import measurement_window

EXPECTED_CHECKS = frozenset(
    [scenario + ':' + check for scenario in ('sync_ok', 'delayed_signal') for check in
     ('no_early_readback', 'no_early_reload', 'readback_after_return', 'disk_hash',
      'next_cycle_waits', 'next_cycle_completes')]
    + ['delayed:waits_for_signal', 'status_gap_not_hidden']
    + [scenario + ':' + check for scenario in ('sync_error', 'wrong_signal', 'duplicate_signal', 'phase_timeout')
       for check in ('no_early_readback', 'failure_preserved')]
    + [scenario + ':failure_no_readback' for scenario in ('sync_error', 'wrong_signal', 'phase_timeout')]
    + [scenario + ':no_early_reload' for scenario in ('sync_error', 'duplicate_signal')])


def owners_released():
    return not native.HELD_PROBES and not native.native_job.cli_job.HOLDS


def verify_fault_marker(rows, capture):
    native.need(len(rows) == 1, 'BOUNDARY_FAULT_MARKER')
    row = rows[0]
    checks = row.get('checks', [])
    native.need(row.get('pid') == capture['actual_process_exit']['pid'] and row.get('passed') is True
                and row.get('fault_injected') is True and row.get('real_save_exercised') is False
                and row.get('formal14_root_cause_proven') is False
                and len(checks) == len(EXPECTED_CHECKS)
                and {check.get('name') for check in checks} == EXPECTED_CHECKS
                and all(check.get('passed') is True for check in checks), 'BOUNDARY_FAULT_INCOMPLETE')
    return row


def verify_real_marker(rows, result):
    native.need(len(rows) == 1, 'BOUNDARY_REAL_MARKER')
    row = rows[0]
    before, after = row['before'], row['after']
    # Historical marker "recorded" means key presence, NOT a published hash.
    # _begin_cycle initializes that key to "". Premature _wait_save would
    # also set end_us and advance phase; require both to remain untouched.
    native.need(row['run_id'] == result['run_id'] and row['pid'] == result['actual_exits']['editor']['pid']
                and row['failed'] is False and before == after and before['phase'] == 7
                and before['returned'] is False and before['recorded'] is True
                and before['save_end_us'] == 0 and before['batch'] == before['cycle'] == 0
                and before['root_id'] > 0, 'BOUNDARY_REAL_ADVANCED')
    return row


def confirm_real_save(run_id):
    """One real preview-enabled save; force one process callback at its signal."""
    native.need(re.fullmatch(r'gt06-save-boundary-[a-z0-9-]{1,40}', run_id), 'BOUNDARY_RUN_ID')
    root = STUDIO / '.local/reviews' / run_id
    admission = root.with_name(root.name + '-admission')
    admission.mkdir(exist_ok=False)
    original_prepare = native.prepare

    def prepare(project, factory, trusted, binding):
        initial = original_prepare(project, factory, trusted, binding)
        path = project / 'addons/hh_benchmark/benchmark_native.gd'
        raw = native.read_regular(path)
        anchor = b'    _save_signal_us = Time.get_ticks_usec()\n'
        native.need(raw.count(anchor) == 1, 'BOUNDARY_SIGNAL_ANCHOR')
        injected = b'''    var boundary_before: Dictionary = {"phase": int(_phase), "returned": _save_call_completed,
        "recorded": _row.has("saved_file_sha256"), "save_end_us": int(_timing.save.end_us),
        "batch": _batch, "cycle": _cycle, "root_id": EditorInterface.get_edited_scene_root().get_instance_id()}
    _process(0.0)
    print("HH_REAL_SAVE_BOUNDARY " + JSON.stringify({"pid": OS.get_process_id(), "before": boundary_before,
        "after": {"phase": int(_phase), "returned": _save_call_completed,
        "recorded": _row.has("saved_file_sha256"), "save_end_us": int(_timing.save.end_us),
        "batch": _batch, "cycle": _cycle, "root_id": EditorInterface.get_edited_scene_root().get_instance_id()},
        "failed": _failed, "run_id": _input.run_id}))
'''
        path.write_bytes(raw.replace(anchor, anchor + injected))
        initial[path.relative_to(project).as_posix()] = native.sha(path.read_bytes())
        return initial

    released = True
    with measurement_window(run_id, 'one real save with forced callback reentry; no latency attribution',
                            safe_to_release=lambda: released and owners_released()):
        preflight = campaign.environment_preflight()
        native.write(admission / 'preflight.json', preflight)
        campaign.require_environment_preflight(preflight)
        try:
            released = False
            with patch.object(native, 'prepare', prepare):
                result = native.run(run_id)
            released = True
        except BaseException as exc:
            released = getattr(exc, 'cleanup_owner', None) is None and not native.HELD_PROBES
            raise
        rows = native.markers(native.read_regular(root / 'editor-host/stdout.txt'), 'HH_REAL_SAVE_BOUNDARY ')
        try:
            row = verify_real_marker(rows, result)
        except BaseException as exc:
            native.write(root / 'boundary-failure.json', {'run_id': run_id, 'authority': 0,
                'error': str(exc), 'passed': False, 'native_capture_preserved': True})
            raise
        native.write(root / 'boundary-confirmation.json', {'run_id': run_id, 'passed': True,
            'authority': 0, 'real_save_exercised': True, 'forced_reentry': True,
            'formal14_root_cause_proven': False, 'native': row,
            'capture_sha256': native.sha(native.read_regular(root / 'capture.json'))})
        print(json.dumps({'root': str(root), 'passed': True, 'actual_exits': result['actual_exits'],
                          'real_save_exercised': True, 'formal14_root_cause_proven': False}))
        return 0


def run(run_id):
    native.need(re.fullmatch(r'gt06-save-boundary-[a-z0-9-]{1,40}', run_id), 'BOUNDARY_RUN_ID')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    released = True
    with measurement_window(run_id, 'fault-injected save ordering; no latency claim',
                            safe_to_release=lambda: released and owners_released()):
        try:
            preflight = campaign.environment_preflight()
            native.write(root / 'preflight.json', preflight)
            campaign.require_environment_preflight(preflight)
            factory, trusted = native.load_fixture()
            original = native.read_regular(STUDIO / 'tests/replay/benchmark_native.gd')
            anchor = b'var result: Error = EditorInterface.save_scene()'
            native.need(original.count(anchor) == 1, 'BOUNDARY_API_ANCHOR')
            driver = original.replace(anchor, b'var result: Error = _test_save_scene()')
            # Base declaration enables typed override by the test subject.
            driver += b'\n\nfunc _test_save_scene() -> Error:\n    return FAILED\n'
            files = {**trusted,
                'project.godot': b'config_version=5\n[application]\nconfig/name="Save boundary regression"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n[editor_plugins]\nenabled=PackedStringArray("res://addons/test/plugin.cfg")\n',
                'scenes/fixture.tscn': factory.DEFAULT_SCENE,
                'scripts/fixture_actor.gd': factory.DEFAULT_SCRIPT,
                'addons/hh_benchmark/benchmark_native.gd': driver,
                'addons/test/test.gd': native.read_regular(STUDIO / 'tests/replay/save_boundary_test.gd'),
                'addons/test/plugin.cfg': b'[plugin]\nname="SaveBoundary"\ndescription="Fault injected ordering"\nauthor="HH"\nversion="1"\nscript="test.gd"\n'}
            project = root / 'project'
            for name, raw in files.items():
                native.write(project / name, raw)
            source = native.source_files()
            source['tests/replay/save_boundary_test.gd'] = native.sha(files['addons/test/test.gd'])
            source.update({(project / name).relative_to(STUDIO).as_posix(): native.sha(raw)
                           for name, raw in files.items()})
            lock = json.loads(native.read_regular(STUDIO / 'toolchain.lock.json'))['godot']
            exe = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
            native.need(native.sha(native.read_regular(exe, 256 * 1024**2)) == lock['gui_sha256'], 'BOUNDARY_PIN')
            native.write(root / 'freeze.json', {'run_id': run_id, 'authority': 0, 'source_files': source,
                'source_closure_sha256': native.closure(source), 'original_driver_sha256': native.sha(original),
                'injected_driver_sha256': native.sha(driver), 'binary_sha256': lock['gui_sha256'],
                'fault_injected': True, 'real_save_exercised': False, 'formal14_root_cause_proven': False})
            for name in source:
                native.write(root / 'source' / name, native.read_regular(STUDIO / name))
            error = None
            try:
                released = False
                native.native_job.run_trusted_stage(
                    [str(exe), '--headless', '--editor', '--path', str(project)], cwd=project,
                    output=root / 'editor', source_root=STUDIO, source_files=source,
                    binary_sha256=lock['gui_sha256'])
                released = True
            except native.native_job.StageFailed as exc:
                error = str(exc)
                native.need(exc.cleanup_owner is None, 'BOUNDARY_CLEANUP_HELD')
                released = True
            # A failing regression has a real nonzero exit; never forge a PASS.
            capture = json.loads((root / 'editor/capture.json').read_bytes())
            stdout = (root / 'editor/stdout.txt').read_bytes()
            stderr = (root / 'editor/stderr.txt').read_bytes()
            rows = native.markers(stdout, 'HH_SAVE_BOUNDARY ')
            intact = all(native.sha(native.read_regular(STUDIO / name)) == digest for name, digest in source.items())
            if error is None:
                native.native_job.verify_captured_stage(root / 'editor', native.sha((root / 'editor/capture.json').read_bytes()))
                verify_fault_marker(rows, capture)
            clean_log = not stderr.strip() and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked', stdout)
            passed = error is None and intact and clean_log and len(rows) == 1 and rows[0].get('passed') is True
            report = {'run_id': run_id, 'authority': 0, 'passed': passed, 'native': rows, 'stage_error': error,
                'source_intact': intact, 'clean_log': clean_log, 'capture': capture,
                'real_save_exercised': False, 'formal14_root_cause_proven': False}
            native.write(root / 'result.json', report)
            print(json.dumps({'root': str(root), 'passed': passed, 'stage_error': error,
                'checks': len(rows[0]['checks']) if len(rows) == 1 else 0,
                'failed_checks': [x['name'] for x in rows[0]['checks'] if not x['passed']] if len(rows) == 1 else []}))
            return 0 if passed else 1
        finally:
            # Keep the measurement marker if native ownership could not be released.
            if not released:
                print('BOUNDARY_CLEANUP_UNCERTAIN', file=sys.stderr)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--real-save', action='store_true')
    args = parser.parse_args()
    raise SystemExit(confirm_real_save(args.run_id) if args.real_save else run(args.run_id))
