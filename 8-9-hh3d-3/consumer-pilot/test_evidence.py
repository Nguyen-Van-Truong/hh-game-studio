"""Negative evidence-contract tests; no engine, network, or original raw writes."""
import copy
import json
from pathlib import Path
import tempfile
import types
import unittest

from authoring import close_editor_owner
from collect_existing import safe, sha
from run_runtime import CHECKS, verify_report, verify_terminal, host_ok


def report_fixture():
    state = {'schema': 1, 'tick': 60, 'position': [1.75, .5, 0], 'collected': True}
    replay = {'sha256': 'a' * 64, 'frames': 60, 'final': state}
    report = {'run_id': 'test', 'pid': 42, 'authority': 0, 'gt06_acceptance': False,
        'map_sha256': 'map', 'pickup_glb_sha256': 'glb', 'passed': True,
        'checks': {name: True for name in CHECKS},
        'observations': {'pause': {'before': state, 'after': copy.deepcopy(state), 'frames_advanced': 12},
                         'replays': [replay, copy.deepcopy(replay), {**replay, 'sha256': 'b' * 64}]}}
    manifest = {'run_id': 'test', 'runtime_sources': {},
                'inputs': {'map.json': {'sha256': 'map'}, 'pickup.glb': {'sha256': 'glb'}}}
    return report, manifest, {'target_pid': 42}


class EvidenceTests(unittest.TestCase):
    def test_valid_report(self):
        verify_report(*report_fixture())

    def test_reject_false_or_omitted_checks(self):
        for name in CHECKS:
            for mutation in ('false', 'omit', 'integer'):
                with self.subTest(name=name, mutation=mutation):
                    report, manifest, host = report_fixture()
                    if mutation == 'omit': del report['checks'][name]
                    else: report['checks'][name] = False if mutation == 'false' else 1
                    with self.assertRaises(ValueError): verify_report(report, manifest, host)

    def test_reject_cross_run_pid_inputs_and_acceptance(self):
        for key, value in [('run_id', 'other'), ('pid', 43), ('map_sha256', 'wrong'),
                           ('pickup_glb_sha256', 'wrong'), ('authority', 1), ('gt06_acceptance', True)]:
            with self.subTest(key=key):
                report, manifest, host = report_fixture()
                report[key] = value
                with self.assertRaises(ValueError): verify_report(report, manifest, host)

    def test_reject_pause_without_running_frames_or_with_movement(self):
        for kind in ('no_frames', 'simulation_moved'):
            report, manifest, host = report_fixture()
            if kind == 'no_frames': report['observations']['pause']['frames_advanced'] = 0
            else: report['observations']['pause']['after']['tick'] += 1
            with self.assertRaises(ValueError): verify_report(report, manifest, host)

    def test_reject_replay_arithmetic_only_or_nondeterminism(self):
        for kind in ('same_control', 'different_repeat', 'no_pickup'):
            report, manifest, host = report_fixture()
            replays = report['observations']['replays']
            if kind == 'same_control': replays[2] = copy.deepcopy(replays[0])
            elif kind == 'different_repeat': replays[1]['sha256'] = 'c' * 64
            else: replays[0]['final']['collected'] = replays[1]['final']['collected'] = False
            with self.assertRaises(ValueError): verify_report(report, manifest, host)

    def test_host_exit_pid_tree_and_stderr_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'host.json').write_text(json.dumps({'exit_code': 0, 'target_pid': 42}))
            (root / 'stderr.txt').write_text('')
            host = {'exit_code': 0, 'target_pid': 42, 'wrapper_exit_code': 0,
                'tree_verified': True, 'timed_out': False, 'host': 'host.json', 'stderr': 'stderr.txt'}
            self.assertTrue(host_ok(root, host))
            for key, value in [('exit_code', 1), ('target_pid', 43), ('wrapper_exit_code', 1),
                               ('tree_verified', False), ('timed_out', True)]:
                self.assertFalse(host_ok(root, {**host, key: value}))
            (root / 'stderr.txt').write_text('SCRIPT ERROR')
            self.assertFalse(host_ok(root, host))

    def test_artifact_paths_cannot_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(safe(root, 'a.json'), root / 'a.json')
            for bad in ('../escape', str(root / 'absolute'), ''):
                with self.subTest(path=bad), self.assertRaises(ValueError): safe(root, bad)

    def test_cleanup_must_be_observed_after_close(self):
        owner = types.SimpleNamespace(_editor=types.SimpleNamespace(_cleanup=None))
        def close(): owner._editor._cleanup = {'closed': True}
        owner.close = close
        self.assertEqual(close_editor_owner(owner), {'closed': True})
        owner._editor._cleanup = None
        owner.close = lambda: None
        with self.assertRaises(RuntimeError): close_editor_owner(owner)

    def test_gui_log_marker_and_hash_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report, manifest, host = report_fixture()
            (root / 'project/input').mkdir(parents=True)
            (root / 'project/out').mkdir()
            for name, report_key in [('map.json', 'map_sha256'), ('pickup.glb', 'pickup_glb_sha256')]:
                path = root / 'project/input' / name
                path.write_bytes(name.encode())
                manifest['inputs'][name]['sha256'] = report[report_key] = sha(path)
            (root / 'project/out/report.json').write_text(json.dumps(report))
            (root / 'host.json').write_text(json.dumps({'exit_code': 0, 'target_pid': 42}))
            (root / 'stderr.txt').write_text('')
            host.update(exit_code=0, wrapper_exit_code=0, tree_verified=True, timed_out=False,
                        host='host.json', stderr='stderr.txt')
            hosts = {'parse': host, 'runtime': host}
            log = root / 'godot-user/Roaming/Godot/app_userdata/HH Consumer Pilot/logs/godot.log'
            log.parent.mkdir(parents=True)
            log.write_text('HH_CONSUMER_PILOT_PASS\n')
            verify_terminal(root, manifest, hosts)
            for bad in ('', 'HH_CONSUMER_PILOT_PASS\nERROR\n', 'HH_CONSUMER_PILOT_PASS\n' * 2):
                log.write_text(bad)
                with self.assertRaises(ValueError): verify_terminal(root, manifest, hosts)
            log.write_text('HH_CONSUMER_PILOT_PASS\n')
            (root / 'project/input/pickup.glb').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_terminal(root, manifest, hosts)


if __name__ == '__main__':
    unittest.main()
