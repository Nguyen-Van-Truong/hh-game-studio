"""Closed startup focus receipt validation; no engine calls or acceptance policy.

The explicit setup notification precedes the existing startup settle and batch0.
It does not discount objects or alter warmup/measurement boundaries.
"""
from __future__ import annotations

import re

SAFE_INTEGER = (1 << 53) - 1
OWNERS = {
    'editor_disk_changes': ('EditorNode', '_reload_modified_scenes'),
    'script_disk_changes': ('ScriptEditor', 'reload_scripts'),
}
OPERATION = 'SceneTree.root.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_IN)'


class ReadinessError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _need(condition, code):
    if not condition:
        raise ReadinessError('STARTUP_READINESS_' + code)


def _shape(value, fields):
    _need(type(value) is dict and set(value) == set(fields.split()), 'FIELDS')


def _integer(value, low=0):
    _need(type(value) is int and low <= value <= SAFE_INTEGER, 'INTEGER')


def _id(value):
    _need(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value) is not None
          and int(value) < 1 << 64, 'OBJECT_ID')
    return value


def _digest(value):
    _need(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'HASH')


def validate_startup_readiness(receipt, *, binding, pid, source_files, baseline_revision,
                               scene_file_sha256, first_batch_started_mono_us,
                               first_cycle_root_before, run_started_mono_us,
                               first_ready_mono_us=None, first_ready_frame=None):
    """Bind one closed receipt to its native index, batch0 and precycle scene.

    In full mode, pass the first READY time/frame and its scene_file_sha256.
    The diagnostic passes the frozen pre-runtime scene hash instead. Scene
    bytes saved by a later native cycle cannot establish the startup bytes.
    """
    _shape(receipt, 'schema_id schema_version run_id source_closure_sha256 pid synthetic notification operation dispatch_count observed_dispatch_count minimum_settle_frames minimum_settle_us owners before immediate settled')
    _need(receipt['schema_id'] == 'hh-studio.native-startup-readiness'
          and receipt['schema_version'] == '1.0.0', 'SCHEMA')
    _need(type(binding) is dict and type(binding.get('run_id')) is str
          and 1 <= len(binding['run_id']) <= 80 and receipt['run_id'] == binding['run_id'], 'RUN_BINDING')
    _digest(binding.get('source_closure_sha256'))
    _need(receipt['source_closure_sha256'] == binding['source_closure_sha256'], 'SOURCE_BINDING')
    _integer(pid, 1)
    _integer(receipt['pid'], 1)
    _need(receipt['pid'] == pid, 'PID_BINDING')
    _need(receipt['synthetic'] is True and receipt['operation'] == OPERATION, 'OPERATION')
    for field, expected in (('notification', 2016), ('dispatch_count', 1), ('observed_dispatch_count', 1),
                            ('minimum_settle_frames', 4), ('minimum_settle_us', 1100000)):
        _integer(receipt[field], 1)
        _need(receipt[field] == expected, 'SETUP_CONTRACT')
    _need(type(source_files) is dict and source_files, 'SOURCE_FILES')
    for path, digest in source_files.items():
        _need(type(path) is str and path.startswith('res://') and len(path) <= 240
              and '..' not in path.split('/'), 'SOURCE_FILES')
        _digest(digest)
    _digest(scene_file_sha256)
    _need(type(baseline_revision) is str and baseline_revision.startswith('sha256:'), 'SCENE_REVISION')
    _digest(baseline_revision[7:])
    _integer(first_cycle_root_before, 1)
    _integer(run_started_mono_us, 1)
    _integer(first_batch_started_mono_us, run_started_mono_us)
    _need((first_ready_mono_us is None) == (first_ready_frame is None), 'READY_BINDING')
    if first_ready_mono_us is not None:
        _integer(first_ready_mono_us, run_started_mono_us)
        _integer(first_ready_frame, 1)
        _need(first_ready_mono_us <= first_batch_started_mono_us, 'READY_BINDING')
    _need(type(receipt['owners']) is dict and set(receipt['owners']) == set(OWNERS), 'OWNERS')
    owner_ids = []
    for role, expected in OWNERS.items():
        owner = receipt['owners'][role]
        _shape(owner, 'dialog_id tree_id callback_target_id callback_target_class callback_method')
        _need((owner['callback_target_class'], owner['callback_method']) == expected, 'CALLBACK')
        owner_ids.extend(_id(owner[field]) for field in ('dialog_id', 'tree_id', 'callback_target_id'))
    _need(len(set(owner_ids)) == len(owner_ids), 'OWNER_ALIAS')
    previous = None
    for phase in ('before', 'immediate', 'settled'):
        point = receipt[phase]
        _shape(point, 'mono_us frame scene_root_id scene_revision scene_file_sha256 source_files roots')
        _integer(point['mono_us'], run_started_mono_us)
        _integer(point['frame'], 1)
        _need(point['mono_us'] <= first_batch_started_mono_us, 'AFTER_BATCH')
        if previous is not None:
            _need(point['mono_us'] > previous['mono_us'] and point['frame'] >= previous['frame'], 'CLOCK_ORDER')
        _need(_id(point['scene_root_id']) == str(first_cycle_root_before)
              and point['scene_revision'] == baseline_revision
              and point['scene_file_sha256'] == scene_file_sha256, 'SCENE_DRIFT')
        _need(type(point['source_files']) is dict and point['source_files'] == source_files, 'SOURCE_DRIFT')
        _need(type(point['roots']) is dict and set(point['roots']) == set(OWNERS), 'ROOTS')
        root_ids = []
        for root in point['roots'].values():
            _shape(root, 'root_id columns child_count text dialog_visible')
            _need(type(root['columns']) is int and root['columns'] == 1
                  and type(root['child_count']) is int and root['child_count'] == 0
                  and root['text'] == '' and type(root['text']) is str
                  and root['dialog_visible'] is False, 'ROOT_CONTENT')
            if root['root_id'] != '' or phase != 'before':
                root_ids.append(_id(root['root_id']))
        all_ids = owner_ids + root_ids + [point['scene_root_id']]
        _need(len(set(all_ids)) == len(all_ids), 'ROOT_ALIAS')
        previous = point
    before, immediate, settled = (receipt[name] for name in ('before', 'immediate', 'settled'))
    _need(immediate['frame'] == before['frame'], 'DISPATCH_FRAME')
    _need(settled['frame'] - immediate['frame'] >= 4
          and settled['mono_us'] - immediate['mono_us'] >= 1100000, 'SETTLE')
    _need(settled['roots'] == immediate['roots'], 'ROOT_DRIFT')
    if first_ready_mono_us is not None:
        _need(settled['mono_us'] <= first_ready_mono_us and settled['frame'] <= first_ready_frame, 'AFTER_READY')
    return receipt
