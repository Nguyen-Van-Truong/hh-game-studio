"""Synthetic receipt negatives only; never native evidence."""
from copy import deepcopy
import unittest

from studio.tests.replay import benchmark_readiness as subject


def readiness_fixture(*, binding=None, pid=202, source_files=None, scene_file_sha256='c' * 64,
                      baseline_revision='sha256:' + 'a' * 64, first_cycle_root_before=1000):
    binding = binding or {'run_id': 'gt06-readiness-unit', 'source_closure_sha256': 'd' * 64}
    source_files = source_files or {'res://addons/hh_benchmark/benchmark_native.gd': 'e' * 64}
    owners = {}
    for number, (role, (owner_class, method)) in enumerate(subject.OWNERS.items()):
        owners[role] = {'dialog_id': str(10 + number * 10), 'tree_id': str(11 + number * 10),
                       'callback_target_id': str(12 + number * 10),
                       'callback_target_class': owner_class, 'callback_method': method}
    points = {}
    for phase, mono, frame in (('before', 10, 1), ('immediate', 20, 1), ('settled', 1100020, 5)):
        points[phase] = {'mono_us': mono, 'frame': frame, 'scene_root_id': str(first_cycle_root_before),
            'scene_revision': baseline_revision, 'scene_file_sha256': scene_file_sha256,
            'source_files': deepcopy(source_files), 'roots': {role: {
                'root_id': '' if phase == 'before' else str(100 + number), 'columns': 1,
                'child_count': 0, 'text': '', 'dialog_visible': False}
                for number, role in enumerate(subject.OWNERS)}}
    return {'schema_id': 'hh-studio.native-startup-readiness', 'schema_version': '1.0.0',
            'run_id': binding['run_id'], 'source_closure_sha256': binding['source_closure_sha256'],
            'pid': pid, 'synthetic': True, 'notification': 2016, 'operation': subject.OPERATION,
            'dispatch_count': 1, 'observed_dispatch_count': 1, 'minimum_settle_frames': 4,
            'minimum_settle_us': 1100000, 'owners': owners, **points}


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.receipt = readiness_fixture()
        self.kwargs = {'binding': {'run_id': 'gt06-readiness-unit', 'source_closure_sha256': 'd' * 64},
            'pid': 202, 'source_files': deepcopy(self.receipt['before']['source_files']),
            'baseline_revision': 'sha256:' + 'a' * 64, 'scene_file_sha256': 'c' * 64,
            'first_batch_started_mono_us': 2001000, 'first_cycle_root_before': 1000,
            'run_started_mono_us': 1, 'first_ready_mono_us': 2000100, 'first_ready_frame': 101}

    def validate(self):
        return subject.validate_startup_readiness(self.receipt, **self.kwargs)

    def test_bound_full_and_diagnostic_receipt_with_blank_roots(self):
        self.assertIs(self.validate(), self.receipt)
        self.kwargs.pop('first_ready_mono_us')
        self.kwargs.pop('first_ready_frame')
        self.validate()
        # A real focus before explicit setup may have already initialized roots.
        self.receipt['before']['roots']['editor_disk_changes']['root_id'] = '98'
        self.receipt['before']['roots']['script_disk_changes']['root_id'] = '99'
        self.validate()

    def test_closed_shapes_reject_missing_and_unknown_fields(self):
        targets = ((), ('owners', 'editor_disk_changes'), ('before',), ('immediate', 'roots', 'editor_disk_changes'))
        original = deepcopy(self.receipt)
        for keys in targets:
            for missing in (True, False):
                with self.subTest(keys=keys, missing=missing):
                    self.receipt = deepcopy(original)
                    target = self.receipt
                    for key in keys:
                        target = target[key]
                    if missing:
                        target.pop(next(iter(target)))
                    else:
                        target['invented'] = True
                    with self.assertRaisesRegex(subject.ReadinessError, 'FIELDS'):
                        self.validate()
        for value in (None, [], True, {}):
            self.receipt = value
            with self.assertRaisesRegex(subject.ReadinessError, 'FIELDS'):
                self.validate()

    def test_operation_dispatch_and_settle_contract_not_relaxed(self):
        original = deepcopy(self.receipt)
        for field, value in (('schema_version', '0.9.0'), ('synthetic', 1), ('notification', 2015),
                             ('operation', 'emit_signal'), ('dispatch_count', 2), ('dispatch_count', True),
                             ('observed_dispatch_count', 0), ('minimum_settle_frames', 3),
                             ('minimum_settle_us', 1099999), ('run_id', 'another-run'),
                             ('pid', 203), ('pid', True), ('source_closure_sha256', 'f' * 64)):
            with self.subTest(field=field, value=value):
                self.receipt = deepcopy(original)
                self.receipt[field] = value
                with self.assertRaises(subject.ReadinessError):
                    self.validate()

    def test_owner_callback_identity_and_positive_unique_native_ids(self):
        original = deepcopy(self.receipt)
        changes = [lambda r: r['owners'].pop('script_disk_changes'),
                   lambda r: r['owners']['editor_disk_changes'].update(callback_method='reload_scripts'),
                   lambda r: r['owners']['editor_disk_changes'].update(callback_target_class='Node'),
                   lambda r: r['owners']['editor_disk_changes'].update(tree_id='10')]
        changes.extend(lambda r, value=value: r['owners']['editor_disk_changes'].update(tree_id=value)
                       for value in (0, '0', '-1', '01', '1.0', True, '18446744073709551616'))
        for change in changes:
            self.receipt = deepcopy(original)
            change(self.receipt)
            with self.assertRaises(subject.ReadinessError):
                self.validate()

    def test_missing_dirty_visible_or_aliased_root_is_rejected(self):
        original = deepcopy(self.receipt)
        for field, value in (('root_id', ''), ('root_id', '10'), ('root_id', '101'), ('root_id', '1000'),
                             ('columns', True), ('columns', 2), ('child_count', 1), ('text', 'dirty scene'),
                             ('dialog_visible', True), ('dialog_visible', 0)):
            with self.subTest(field=field, value=value):
                self.receipt = deepcopy(original)
                self.receipt['immediate']['roots']['editor_disk_changes'][field] = value
                with self.assertRaises(subject.ReadinessError):
                    self.validate()
        self.receipt = deepcopy(original)
        self.receipt['settled']['roots']['editor_disk_changes']['root_id'] = '104'
        with self.assertRaisesRegex(subject.ReadinessError, 'ROOT_DRIFT'):
            self.validate()

    def test_source_scene_root_revision_or_bytes_drift_rejected_at_each_point(self):
        original = deepcopy(self.receipt)
        for phase in ('before', 'immediate', 'settled'):
            for field, value in (('scene_root_id', '1001'), ('scene_revision', 'sha256:' + 'b' * 64),
                                 ('scene_file_sha256', 'b' * 64), ('source_files', {})):
                with self.subTest(phase=phase, field=field):
                    self.receipt = deepcopy(original)
                    self.receipt[phase][field] = value
                    with self.assertRaises(subject.ReadinessError):
                        self.validate()

    def test_setup_after_batch_or_ready_and_short_settle_rejected(self):
        original = deepcopy(self.receipt)
        for phase, field, value in (('before', 'mono_us', 0), ('immediate', 'mono_us', 9),
                                    ('immediate', 'frame', 2), ('settled', 'mono_us', 1100019),
                                    ('settled', 'frame', 4), ('settled', 'mono_us', 2001001),
                                    ('settled', 'frame', 102), ('settled', 'mono_us', 2000500)):
            with self.subTest(phase=phase, field=field, value=value):
                self.receipt = deepcopy(original)
                self.receipt[phase][field] = value
                with self.assertRaises(subject.ReadinessError):
                    self.validate()

    def test_caller_bindings_and_optional_ready_pair_fail_closed(self):
        original = deepcopy(self.kwargs)
        for field, value in (('scene_file_sha256', None), ('baseline_revision', 'bad'),
                             ('first_cycle_root_before', True), ('run_started_mono_us', 11),
                             ('first_batch_started_mono_us', 1000), ('pid', 0),
                             ('first_ready_mono_us', None), ('first_ready_frame', None)):
            with self.subTest(field=field):
                self.kwargs = deepcopy(original)
                self.kwargs[field] = value
                with self.assertRaises(subject.ReadinessError):
                    self.validate()


if __name__ == '__main__':
    unittest.main()
