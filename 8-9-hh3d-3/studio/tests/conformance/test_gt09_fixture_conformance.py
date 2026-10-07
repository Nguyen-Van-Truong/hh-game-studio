from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from gt09_fixture_conformance import ARENA_REQUIRED, build_report


def write_row(root: Path, name: str, *, room: bool, closure: str = 'same') -> Path:
    path = root / name
    path.mkdir()
    source = 'closure-shared' if closure == 'same' else closure
    details = {
        'ticks': 60, 'movement_observed': True, 'camera_follow': True,
        'switch_used': True, 'pickup_collected': True, 'ui_visible': True,
        'input_trace_ok': True, 'replay_hash_equal': True,
        'avatar_asset_loaded': True, 'sprite_asset_loaded': True,
        'perf_samples': 60, 'perf_budget_ms': 33.333,
        'perf_budget_ok': True, 'topology_ok': True,
        'topology_components': {
            'avatar_shape': True, 'trigger_shape': True, 'pickup_shape': True,
            'camera': True, 'hud': True,
        },
    }
    if not room:
        details = dict(ARENA_REQUIRED)
    (path / 'result.json').write_text(json.dumps({
        'run_id': name, 'status': 'DIAGNOSTIC_PASS', 'authority': 0,
        'public_ack': False, 'source_closure_sha256': source,
        'blender_handoff_verified': True,
        'blender_handoff': {
            'schema': 'hh-blender-godot-handoff-1',
            'producer_run_id': 'gt07-native-queue-test',
            'manifest_sha256': 'manifest-sha',
            'artifact': {'path': 'scene.glb', 'sha256': 'glb-sha', 'bytes': 12},
            'producer_receipts': {
                'queue-native.json': 'q', 'native-child.json': 'c',
                'native-host.json': 'h'},
            'authority': 0, 'public_ack': False,
        },
        'native_run_count': 1, 'native_fixture_observed': True,
        'live_retry_equal': True, 'reopened_retry_equal': True,
        'durable_state_unchanged': True, 'source_unchanged': True,
    }), encoding='utf-8')
    (path / 'native-observation.json').write_text(json.dumps({
        'fixture_observed': True, 'confinement_lifecycle_observed': True,
        'supervisor_binding_verified': True,
        'asset_import_observed': True,
        'untrusted_child_observation': details,
    }), encoding='utf-8')
    return path


class Gt09ConformanceTests(unittest.TestCase):
    def test_room_requirements_and_shared_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build_report(write_row(root, 'arena', room=False),
                                  write_row(root, 'room', room=True))
            self.assertEqual(report['status'], 'CANDIDATE_PASS')
            self.assertEqual(report['acceptance'], False)

    def test_closure_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = build_report(write_row(root, 'arena', room=False),
                                  write_row(root, 'room', room=True, closure='different'))
            self.assertEqual(report['status'], 'INCOMPLETE')
            self.assertIn('source_closure_mismatch', report['errors'])


if __name__ == '__main__':
    unittest.main()
