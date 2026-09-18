"""No-engine draft checks; synthetic JSON is not native evidence."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('focus_probe_draft', BASE / 'diagnose_focus.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
sys.path.insert(0, str(probe.ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture  # Freeze dependencies, never instantiate.


def text(value):
    return {'text': value, 'length': len(value), 'sha256': native.sha(value.encode()), 'truncated': False}


def fixture():
    labels = ['natural_after_cycle', 'before_first_stimulus', 'after_first_return',
              'after_first_settle_before_second', 'after_second_return', 'after_second_settle']
    times = [100, 1600200, 1600300, 3200400, 3200500, 4800600]
    files = {f'res://{name}': {'sha256': 'a' * 64, 'size_bytes': 1, 'modified_time': 100}
             for name in ('addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd',
                          'addons/hh_studio/jcs_godot.gd', 'addons/hh_studio/plugin.cfg',
                          'scripts/fixture_actor.gd', 'addons/hh_benchmark/benchmark_native.gd',
                          'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json',
                          'benchmark/.gdignore', 'scenes/fixture.tscn')}
    counters = dict(objects=71123, cached_resources=10, tree_nodes=200, orphan_nodes=0,
                    filesystem_scanning_before=False, filesystem_scanning_after=False)
    rows = []
    for index, label in enumerate(labels):
        owners = {}
        for offset, role in enumerate(('editor_disk_changes', 'script_disk_changes')):
            root_id = '' if index < 2 else str(1000 + offset + (10 if index >= 4 else 0))
            previous = rows[-1]['owners'][role]['root_item_id'] if rows else ''
            owners[role] = {
                'dialog_id': str(100 + offset), 'tree_id': str(200 + offset),
                'confirmed_callbacks': [{'target_id': str(300 + offset),
                    'target_class': 'EditorNode' if offset == 0 else 'ScriptEditor',
                    'target_path': '/root/EditorNode',
                    'method': '_reload_modified_scenes' if offset == 0 else 'reload_scripts'}],
                'dialog_title': text('Files have been modified on disk'), 'columns': 1,
                'root_present': bool(root_id), 'root_item_id': root_id,
                'previous_root_item_id': previous,
                'previous_root_still_valid': (previous == root_id) if previous else None,
                'item_count': int(bool(root_id)), 'items': ([{
                    'id': root_id, 'owner_tree_id': str(200 + offset), 'columns': 1,
                    'parent_item_id': '', 'cell_texts': [text('')]}] if root_id else [])}
        rows.append({'schema_id': 'hh-studio.focus-causal-diagnostic-point', 'schema_version': '1.0.0',
            'run_id': probe.RUN_ID, 'pid': 123, 'sequence': index, 'label': label,
            'formal_acceptance': False, 'full_benchmark': False, 'full_objectdb_attribution': False,
            'batch': 0, 'cycle': 1, 'phase': 'BATCH_WRITE', 'focus_probe_stage': [0, 1, 1, 2, 2, 3][index],
            'event_count': (int(index >= 2) + int(index >= 4)), 'mono_us': times[index],
            'main_window_title': text('HH managed fixture - Godot Engine'),
            'collection_end_us': times[index] + 10, 'frame': [10, 20, 20, 30, 30, 40][index],
            'files': copy.deepcopy(files), 'counters_before': counters.copy(),
            'counters_after': counters.copy(), 'counters_equal_across_collection': True, 'owners': owners})
    report = {'schema_id': 'hh-studio.focus-causal-diagnostic', 'schema_version': '1.0.0',
        'run_id': probe.RUN_ID, 'pid': 123, 'completed_diagnostic': True, 'formal_acceptance': False,
        'full_benchmark': False, 'root_cause_proven': False, 'stimulus_is_synthetic_not_os_focus': True,
        'private_tree_mutation': False, 'settle_minimum_us': 1500000, 'settle_minimum_frames': 8,
        'points': [], 'stimuli': [], 'events': []}
    for index, before in enumerate((1, 3)):
        report['stimuli'].append({'ordinal': index + 1, 'synthetic': True, 'notification': 2016,
            'operation': 'SceneTree.root.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)',
            'before_point_sequence': before, 'begin_mono_us': times[before] + 20,
            'end_mono_us': times[before] + 30, 'event_start_index': index, 'event_end_index': index + 1})
        report['events'].append({'ordinal': index, 'notification': 2016, 'pid': 123,
            'probe_synthetic_dispatch': index + 1, 'origin': 'probe_synthetic', 'mono_us': times[before] + 25})
    return rows, report


class ProbeDraftTests(unittest.TestCase):
    def verify(self, mutate=None):
        rows, report = fixture()
        if mutate:
            mutate(rows, report)
        with tempfile.TemporaryDirectory(prefix='probe-test-', dir=BASE) as directory:
            out = Path(directory).resolve()
            self.assertTrue(out.is_relative_to(BASE))
            for index, row in enumerate(rows):
                raw = native.encoded(row)
                name = f'focus-{index:02d}.json'
                (out / name).write_bytes(raw)
                report['points'].append({'file': name, 'sha256': native.sha(raw), 'size_bytes': len(raw),
                                         'sequence': index, 'label': row['label']})
            self.assertEqual(len(probe.verify_focus(out, report, 123, native)), 6)

    def test_valid_synthetic_report(self):
        self.verify()

    def test_rejects_same_hash_manifest_with_wrong_pid(self):
        with self.assertRaises(AssertionError):
            self.verify(lambda rows, _: rows[3].update(pid=124))

    def test_rejects_file_timestamp_change(self):
        with self.assertRaises(AssertionError):
            self.verify(lambda rows, _: rows[2]['files']['res://project.godot'].update(modified_time=101))

    def test_rejects_wrong_callback_target(self):
        with self.assertRaises(AssertionError):
            self.verify(lambda rows, _: rows[0]['owners']['editor_disk_changes']['confirmed_callbacks'][0].update(target_class='Control'))

    def test_rejects_wrong_root_readback(self):
        with self.assertRaises(AssertionError):
            self.verify(lambda rows, _: rows[3]['owners']['editor_disk_changes'].update(previous_root_still_valid=False))

    def test_rejects_synthetic_event_misattribution(self):
        with self.assertRaises(AssertionError):
            self.verify(lambda _, report: report['events'][0].update(probe_synthetic_dispatch=0))

    def test_real_dependencies_and_fixed_instrumentation(self):
        native.load_fixture()
        source = native.source_files()
        for name in ('tests/replay/benchmark_job.py', 'pipeline/native_job.py', 'host/blender/ui_host.py',
                     'godot-addon/cli_job.py', 'godot-addon/fixture_profile.py'):
            self.assertIn(name, source)
        base = (native.STUDIO / 'tests/replay/benchmark_native.gd').read_text(encoding='utf-8')
        extra = (BASE / 'focus_probe.gd').read_text(encoding='utf-8')
        combined = probe.instrument_driver(base, extra)
        self.assertEqual(combined.count('func _notification('), 1)
        self.assertEqual(combined.count('get_tree().root.propagate_notification('), 1)
        self.assertNotIn('.clear(', extra)
        self.assertEqual(native.native_job.WALL_SECONDS, 20)
        self.assertLess(probe.INNER_WALL_SECONDS, probe.OUTER_WALL_SECONDS)
        self.assertLessEqual(probe.OUTER_WALL_SECONDS, 600)
        with self.assertRaises(AssertionError):
            probe.instrument_driver(combined, extra)


if __name__ == '__main__':
    unittest.main()
