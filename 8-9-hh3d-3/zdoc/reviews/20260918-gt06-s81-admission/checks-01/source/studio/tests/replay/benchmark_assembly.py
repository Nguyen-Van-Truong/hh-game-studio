"""Offline, hash-bound assembly of GT06 benchmark measurements.

read_artifact(root, {file, sha256, size_bytes}) -> BoundArtifact.
assemble_sample(native, command, joint, *, run_id, index, processes,
                source_closure_sha256, barrier_receipt, ack, ready, start)
                -> profile sample.
All six artifacts must be BoundArtifact instances. The receipt must come from
the independently bound native index. Fresh ACK frame/object/resource fields
are mandatory; pre-barrier counters cannot substitute for joint observations.
Host times use QPC/perf_counter; Godot times are checked only against Godot
times. Reported millisecond timings are checked against their own clock with
at most one microsecond of host timestamp truncation.

assemble_run(root, manifest) verifies 35 batches and frozen source copies,
then returns a BoundRun with exact source/toolchain/profile provenance.
assemble_dataset(provenance, runs) requires matching BoundRun envelopes,
then applies the unchanged profile v2 validator to their existing run values.
Hashes and recorded process evidence do not independently attest execution;
the coordinator must bind manifests to its captured child/Job lifecycle.
No engines, writes, repairs, retries, or acceptance decisions occur here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re

from studio.protocol.core import Response, ValidationError, canonical_bytes
from studio.tests.replay import benchmark_profile as profile
from studio.tests.replay.benchmark_readiness import ReadinessError, validate_startup_readiness

MAX_RAW_BYTES = 8 * 1024 * 1024
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_NAME = re.compile(r'[A-Za-z0-9._/-]{1,240}\Z')
_STEPS = ('create', 'undo', 'save', 'reload')
_COUNTERS = ('rss_bytes', 'objects', 'resources', 'held_handles')
_HOST_NA = profile.HOST_NOT_APPLICABLE


class AssemblyError(ValueError):
    def __init__(self, code, path='$'):
        self.code, self.path = code, path
        super().__init__(f'{code}: {path}')


def _need(condition, code, path='$'):
    if not condition:
        raise AssemblyError(code, path)


def _shape(value, fields, path='$'):
    _need(type(value) is dict and set(value) == set(fields.split()), 'FIELDS', path)


def _integer(value, low=0, high=profile.SAFE_INTEGER, path='$'):
    _need(type(value) is int and low <= value <= high, 'INTEGER', path)


def _number(value, low=0, high=600000, path='$'):
    _need(type(value) in (int, float) and low <= value <= high and math.isfinite(value), 'NUMBER', path)


def _digest(value, prefix=False):
    _need(type(value) is str and (not prefix or value.startswith('sha256:'))
          and _HASH.fullmatch(value[7:] if prefix else value), 'HASH')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, RecursionError, UnicodeError) as error:
        raise AssemblyError('INVALID_JSON') from error


def _parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, 'DUPLICATE_KEY')
            result[key] = value
        return result
    def bad(_):
        raise AssemblyError('NONFINITE_JSON')
    try:
        value = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs, parse_constant=bad)
        pending = [value]
        while pending:
            row = pending.pop()
            if type(row) is float:
                _need(math.isfinite(row), 'NONFINITE_JSON')
            elif type(row) is dict:
                pending.extend(row.values())
            elif type(row) is list:
                pending.extend(row)
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, AssemblyError):
            raise
        raise AssemblyError('INVALID_JSON') from error


@dataclass(frozen=True)
class BoundArtifact:
    file: str
    sha256: str
    raw: bytes

    @property
    def value(self):
        _need(type(self.raw) is bytes and 0 < len(self.raw) <= MAX_RAW_BYTES
              and _sha(self.raw) == self.sha256, 'ARTIFACT_BINDING')
        return _parse(self.raw)


@dataclass(frozen=True)
class BoundRun:
    """Immutable run bytes bound together with their verified provenance.

    value contains source_closure_sha256, toolchain_sha256, profile_sha256,
    and run. Only run is serialized into the strict profile dataset. Like
    BoundArtifact, this is a checked data container, not execution attestation.
    """
    sha256: str
    raw: bytes

    @property
    def value(self):
        _need(type(self.raw) is bytes and 0 < len(self.raw) <= profile.MAX_BYTES
              and _sha(self.raw) == self.sha256, 'RUN_BINDING')
        value = _parse(self.raw)
        _shape(value, 'source_closure_sha256 toolchain_sha256 profile_sha256 run')
        for name in ('source_closure_sha256', 'toolchain_sha256', 'profile_sha256'):
            _digest(value[name])
        _need(type(value['run']) is dict, 'RUN_BINDING')
        return value


def read_artifact(root: Path, reference: dict) -> BoundArtifact:
    """Read an exact, bounded regular file; reject traversal and reparse paths."""
    _shape(reference, 'file sha256 size_bytes')
    name = reference['file']
    _need(type(name) is str and _NAME.fullmatch(name) and '\\' not in name, 'ARTIFACT_PATH')
    relative = PurePosixPath(name)
    _need(not relative.is_absolute() and relative.as_posix() == name
          and all(part not in ('.', '..') for part in relative.parts), 'ARTIFACT_PATH')
    _digest(reference['sha256'])
    _integer(reference['size_bytes'], 0, MAX_RAW_BYTES)
    root = Path(root).absolute()
    path = root.joinpath(*relative.parts)
    for component in (root, *path.parents[:len(relative.parts) - 1], path):
        try:
            info = component.lstat()
        except OSError as error:
            raise AssemblyError('ARTIFACT_MISSING') from error
        _need(not component.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'ARTIFACT_REPARSE')
    _need(path.is_file() and path.stat().st_size == reference['size_bytes'], 'ARTIFACT_SIZE')
    with path.open('rb') as stream:
        raw = stream.read(MAX_RAW_BYTES + 1)
    _need(len(raw) == reference['size_bytes'] and _sha(raw) == reference['sha256'], 'ARTIFACT_HASH')
    return BoundArtifact(name, reference['sha256'], raw)


def _identity(value):
    _shape(value, 'pid process_start')
    _integer(value['pid'], 1, 0xffffffff)
    _need(type(value['process_start']) is str
          and re.fullmatch(r'windows:[1-9][0-9]{0,19}', value['process_start']), 'PROCESS_IDENTITY')


def _counter(value, *, positive=False, required=False):
    _shape(value, 'value unavailable_reason')
    if value['value'] is None:
        reason = value['unavailable_reason']
        _need(not required and type(reason) is str and 1 <= len(reason) <= 160
              and all(32 <= ord(c) < 127 for c in reason), 'COUNTER_UNAVAILABLE')
    else:
        _integer(value['value'], 1 if positive else 0)
        _need(value['unavailable_reason'] is None, 'COUNTER_AVAILABILITY')


def _host_observation(value, identity):
    _shape(value, 'process monotonic_us counters')
    _need(value['process'] == identity, 'HOST_PROCESS_CHANGED')
    _integer(value['monotonic_us'], 1)
    _shape(value['counters'], ' '.join(_COUNTERS))
    for name, counter in value['counters'].items():
        _counter(counter, positive=name == 'rss_bytes')
        if name in ('objects', 'resources'):
            _need(counter == {'value': None, 'unavailable_reason': _HOST_NA}, 'HOST_COUNTER_APPLICABILITY')
        else:
            _need(counter['unavailable_reason'] != _HOST_NA, 'COUNTER_APPLICABILITY')


def _timing(start, end, ms, *, host=False):
    _integer(start, 1)
    _integer(end, start + 1)
    _number(ms, .000000001)
    _need(abs(ms - (end - start) / 1000) <= (.001001 if host else 1e-9), 'TIMING_MISMATCH')


def _lookup_trace(row, *, canceled=False):
    """Reconcile the original ID only; every attempt remains measurable."""
    attempts = row['lookup_attempts']
    _need(type(attempts) is list and 1 <= len(attempts) <= 5001, 'LOOKUP_ATTEMPTS')
    response = row['terminal_response']
    fields = 'status code command_id result_revision result_hash postconditions'
    _shape(response, fields + (' retry_after_ms' if type(response) is dict and 'retry_after_ms' in response else ''))
    try:
        _need(Response.from_dict(response).as_dict() == response, 'TERMINAL_RESPONSE')
    except ValidationError as error:
        raise AssemblyError('TERMINAL_RESPONSE') from error
    expected_status = 'CANCELED' if canceled else 'COMMITTED'
    expected_code = 'CANCELED_BEFORE_APPLY' if canceled else row['terminal_code']
    _need(response['status'] == expected_status and response['code'] == expected_code
          and response['command_id'] == row['command_id'], 'TERMINAL_RESPONSE_IDENTITY')
    if canceled:
        _need(response['result_revision'] is None and response['result_hash'] is None
              and _encode(response['postconditions']) == _encode({'request_digest': row['request_digest'], 'no_effect': True}),
              'CANCEL_RESPONSE')
    else:
        _need(response['result_revision'] == row['snapshot']['revision']
              and response['result_hash'] == row['result_hash']
              and _encode(response['postconditions']) == _encode({'request_digest': row['request_digest'], 'snapshot': row['snapshot']}),
              'TERMINAL_RESPONSE_READBACK')
    previous, first_start, ends = row['receipt_mono_us'], None, []
    for index, attempt in enumerate(attempts):
        _shape(attempt, 'status code command_id request_digest started_mono_us ended_mono_us')
        _integer(attempt['started_mono_us'], previous)
        if first_start is None:
            first_start = attempt['started_mono_us']
        _integer(attempt['ended_mono_us'], attempt['started_mono_us'], first_start + 5000000)
        _need(attempt['command_id'] == row['command_id'], 'LOOKUP_IDENTITY')
        _need(type(attempt['code']) is str and 1 <= len(attempt['code']) <= 160, 'LOOKUP_CODE')
        uncertain = attempt['status'] == 'UNKNOWN' and attempt['code'] == 'CONNECTION_LOST_LOOKUP'
        _need(attempt['request_digest'] == row['request_digest']
              or (uncertain and attempt['request_digest'] is None), 'LOOKUP_DIGEST')
        if index == len(attempts) - 1:
            _need(attempt['status'] == response['status'] and attempt['code'] == response['code']
                  and attempt['ended_mono_us'] == row['terminal_mono_us'], 'LOOKUP_TERMINAL')
        else:
            _need(uncertain or attempt['status'] == 'ACCEPTED_PENDING', 'LOOKUP_RETRY_SCOPE')
        previous = attempt['ended_mono_us']
        ends.append(previous)
    return ends


def validate_command_batch(value, *, run_id, index, host_identity):
    """Verify all 1000 rows, aggregates, effect chain and separate Cancel."""
    _shape(value, 'schema_id schema_version run_id index mode complete_command_mix native_acceptance effects_kind transport_kind observation_kind host_process warmup commands latency_ms effects_per_admission cancel status started_mono_us memory_before memory_after effect_count_before effect_count_after dropped_commands dropped_telemetry journal_bytes diagnostic_retention ended_mono_us host_response_mono_us max_status_gap_ms status_gap_scope')
    _identity(host_identity)
    _need(value['schema_id'] == 'hh-studio.benchmark-command-batch' and value['schema_version'] == '1.1.0', 'COMMAND_SCHEMA')
    _need(value['mode'] == 'benchmark' and value['status'] == 'COMPLETE'
          and value['complete_command_mix'] is True and value['native_acceptance'] is False, 'COMMAND_INCOMPLETE_OR_DIAGNOSTIC')
    _need(value['effects_kind'] == 'in_process_mock_fixture'
          and value['transport_kind'] == 'accepted_loopback_fixture_http'
          and value['observation_kind'] == 'native_windows_process_probe', 'COMMAND_ORIGIN')
    _need(value['run_id'] == run_id and value['host_process'] == host_identity, 'COMMAND_BINDING')
    _integer(value['index'], index, index)
    _need(type(value['warmup']) is bool and value['warmup'] == (index < 5), 'WARMUP')
    _integer(value['started_mono_us'], 1)
    _integer(value['ended_mono_us'], value['started_mono_us'] + 1)
    for name in ('dropped_commands', 'dropped_telemetry'):
        _integer(value[name], 0, 0)
    _integer(value['journal_bytes'], 1, 64 * 1024 * 1024)
    for name in ('memory_before', 'memory_after'):
        _host_observation(value[name], host_identity)
        _need(value['started_mono_us'] <= value[name]['monotonic_us'] <= value['ended_mono_us'], 'COMMAND_MEMORY_TIME')
    _need(value['memory_before']['monotonic_us'] <= value['memory_after']['monotonic_us'], 'COMMAND_MEMORY_TIME')
    _need(type(value['commands']) is list and len(value['commands']) == 1000, 'COMMAND_COUNT')
    _shape(value['latency_ms'], 'inspect rejected admitted')
    latencies = {kind: [] for kind in ('inspect', 'rejected', 'admitted')}
    effects, lookup_ends = [], []
    count, previous = index * 200, value['started_mono_us']
    _integer(value['effect_count_before'], count, count)
    base = 'ordinal group kind command_id started_mono_us receipt_mono_us receipt_ms receipt_status receipt_code request_digest latency_ms terminal_status effect_count_before effect_count_after lookup_attempts'
    extra = ' terminal_mono_us terminal_ms terminal_code result_hash snapshot terminal_response'
    for ordinal, row in enumerate(value['commands']):
        kind = ('inspect',) * 5 + ('rejected',) * 3 + ('admitted',) * 2
        kind = kind[ordinal % 10]
        _shape(row, base + ('' if kind == 'rejected' else extra))
        _integer(row['ordinal'], ordinal, ordinal)
        _integer(row['group'], ordinal // 10, ordinal // 10)
        _need(row['kind'] == kind and row['command_id'] == f'{run_id}.b{index}.{kind}.{len(latencies[kind])}', 'COMMAND_ORDER_OR_ID')
        _digest(row['request_digest'], True)
        _need(row['started_mono_us'] >= previous, 'COMMAND_CLOCK_ORDER')
        _timing(row['started_mono_us'], row['receipt_mono_us'], row['receipt_ms'], host=True)
        _integer(row['effect_count_before'], count, count)
        if kind == 'rejected':
            _need(row['receipt_status'] == row['terminal_status'] == 'REJECTED'
                  and row['receipt_code'] == 'INVALID_FIXTURE_PAYLOAD', 'REJECTION_KIND')
            _need(row['lookup_attempts'] == [], 'REJECTED_LOOKUP')
            previous = row['receipt_mono_us']
            expected_latency = row['receipt_ms']
        else:
            _need(row['receipt_status'] == 'ACCEPTED_PENDING' and row['receipt_code'] == 'QUEUED'
                  and row['terminal_status'] == 'COMMITTED' and row['terminal_code'] == 'READBACK_CONFIRMED', 'COMMAND_TERMINAL')
            _timing(row['started_mono_us'], row['terminal_mono_us'], row['terminal_ms'], host=True)
            _need(row['terminal_mono_us'] >= row['receipt_mono_us'], 'COMMAND_CLOCK_ORDER')
            count += int(kind == 'admitted')
            _shape(row['snapshot'], 'effect_count revision value')
            for key in ('effect_count', 'value'):
                _integer(row['snapshot'][key], count, count)
            _need(row['snapshot']['revision'] == 'rev-' + str(count)
                  and row['result_hash'] == 'sha256:' + _sha(canonical_bytes(row['snapshot'])), 'COMMAND_READBACK')
            lookup_ends.extend(_lookup_trace(row))
            previous = row['terminal_mono_us']
            expected_latency = row['receipt_ms'] if kind == 'admitted' else row['terminal_ms']
        _integer(row['effect_count_after'], count, count)
        _number(row['latency_ms'], .000000001)
        _need(row['latency_ms'] == expected_latency and previous <= value['ended_mono_us'], 'COMMAND_LATENCY')
        latencies[kind].append(row['latency_ms'])
        if kind == 'admitted':
            effects.append(row['effect_count_after'] - row['effect_count_before'])
    _need(value['latency_ms'] == latencies and value['effects_per_admission'] == effects
          and all(type(n) is int and n == 1 for n in value['effects_per_admission']), 'COMMAND_AGGREGATES')
    for values in value['latency_ms'].values():
        _need(type(values) is list, 'COMMAND_AGGREGATES')
        for latency in values:
            _number(latency, .000000001)
    _integer(value['effect_count_after'], count, count)
    cancel = value['cancel']
    _shape(cancel, 'command_id kind separate_from_mix delay_ms started_mono_us receipt_mono_us receipt_ms status terminal_status request_digest no_effect lookup_attempts terminal_response terminal_mono_us terminal_ms')
    _need(cancel['command_id'] == f'{run_id}.b{index}.cancel' and cancel['kind'] == 'cancel'
          and cancel['separate_from_mix'] is True and cancel['no_effect'] is True
          and cancel['status'] == cancel['terminal_status'] == 'CANCELED', 'CANCEL_BINDING')
    _integer(cancel['delay_ms'], 1000, 1000)
    _digest(cancel['request_digest'], True)
    _timing(cancel['started_mono_us'], cancel['receipt_mono_us'], cancel['receipt_ms'], host=True)
    _timing(cancel['started_mono_us'], cancel['terminal_mono_us'], cancel['terminal_ms'], host=True)
    lookup_ends.extend(_lookup_trace(cancel, canceled=True))
    _need(value['commands'][499]['terminal_mono_us'] <= cancel['started_mono_us']
          and cancel['terminal_mono_us'] <= value['commands'][500]['started_mono_us'], 'CANCEL_SCHEDULE')
    stamps = value['host_response_mono_us']
    _need(type(stamps) is list and 1705 <= len(stamps) <= 100000, 'STATUS_SAMPLES')
    for stamp in stamps:
        _integer(stamp, value['started_mono_us'], value['ended_mono_us'])
    _need(stamps[0] == value['started_mono_us'] and stamps[-1] == value['ended_mono_us']
          and all(a <= b for a, b in zip(stamps, stamps[1:])), 'STATUS_CLOCK')
    _number(value['max_status_gap_ms'], .000000001)
    _need(abs(value['max_status_gap_ms'] - max(b - a for a, b in zip(stamps, stamps[1:])) / 1000) <= .001001,
          'STATUS_GAP_MISMATCH')
    stamp_set = set(stamps)
    _need(all(row['receipt_mono_us'] in stamp_set for row in value['commands'])
          and cancel['receipt_mono_us'] in stamps, 'STATUS_RECEIPT_MISSING')
    _need(all(stamp in stamp_set for stamp in lookup_ends), 'STATUS_LOOKUP_MISSING')
    _need(value['status_gap_scope'] == 'host command-lane response progress; not editor UI heartbeat', 'STATUS_SCOPE')
    return value


def validate_native_batch(value, *, run_id, index, editor_identity):
    """Reject diagnostics and recompute every native operation duration."""
    _shape(value, 'schema_id schema_version run_id mode pid index warmup started_mono_us ended_mono_us cycles raw_timings memory barrier start_permit max_status_gap_ms dropped_commands dropped_telemetry')
    _identity(editor_identity)
    _need(value['schema_id'] == 'hh-studio.native-cycle-batch' and value['schema_version'] == '1.2.0', 'NATIVE_SCHEMA')
    _need(value['mode'] == 'full', 'NATIVE_DIAGNOSTIC')
    _need(value['run_id'] == run_id and value['pid'] == editor_identity['pid'], 'NATIVE_BINDING')
    _integer(value['pid'], 1, 0xffffffff)
    _integer(value['index'], index, index)
    _need(type(value['warmup']) is bool and value['warmup'] == (index < 5), 'WARMUP')
    _integer(value['started_mono_us'], 1)
    _integer(value['ended_mono_us'], value['started_mono_us'] + 1)
    _need(type(value['cycles']) is list and len(value['cycles']) == 100
          and type(value['raw_timings']) is list and len(value['raw_timings']) == 100, 'NATIVE_CYCLE_COUNT')
    previous_time, previous_root, previous_generation, baseline, previous_frame = value['started_mono_us'], None, None, None, 0
    for number, (cycle, timing) in enumerate(zip(value['cycles'], value['raw_timings'])):
        _shape(cycle, 'index root_before root_after before_sha256 created_sha256 undone_sha256 saved_file_sha256 reloaded_sha256 latency_ms effects main_thread')
        _shape(timing, 'index generation_before generation_after create undo save reload save_signal_mono_us reload_observed_process_frame')
        _integer(cycle['index'], number, number)
        _integer(timing['index'], number, number)
        for name in ('root_before', 'root_after'):
            _integer(cycle[name], 1)
        _need(cycle['root_before'] != cycle['root_after'] and (previous_root is None or cycle['root_before'] == previous_root), 'NATIVE_ROOT_CHAIN')
        for name in ('before_sha256', 'created_sha256', 'undone_sha256', 'saved_file_sha256', 'reloaded_sha256'):
            _digest(cycle[name])
        baseline = baseline or cycle['before_sha256']
        _need(cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256'] == baseline
              and cycle['created_sha256'] != baseline and cycle['main_thread'] is True, 'NATIVE_READBACK')
        _integer(timing['generation_before'], 1)
        _integer(timing['generation_after'], timing['generation_before'] + 1, timing['generation_before'] + 1)
        _need(previous_generation is None or timing['generation_before'] == previous_generation, 'NATIVE_GENERATION_CHAIN')
        _shape(cycle['latency_ms'], ' '.join(_STEPS))
        _shape(cycle['effects'], ' '.join(_STEPS))
        for step in _STEPS:
            _shape(timing[step], 'start_us end_us')
            record = timing[step]
            _timing(record['start_us'], record['end_us'], cycle['latency_ms'][step])
            _need(previous_time <= record['start_us'] < record['end_us'] <= value['ended_mono_us'], 'NATIVE_CLOCK_ORDER')
            _integer(cycle['effects'][step], 1, 1)
            previous_time = record['end_us']
        _integer(timing['save_signal_mono_us'], timing['save']['start_us'], timing['save']['end_us'])
        _integer(timing['reload_observed_process_frame'], previous_frame + 1)
        previous_frame, previous_root, previous_generation = timing['reload_observed_process_frame'], cycle['root_after'], timing['generation_after']
    memory = value['memory']
    _shape(memory, 'phase monotonic_us process_frame settle_frames settle_us editor')
    _need(memory['phase'] == 'post_batch_quiescent' and memory['monotonic_us'] == value['ended_mono_us'], 'NATIVE_MEMORY_TIME')
    _integer(memory['process_frame'], previous_frame + 4)
    _integer(memory['settle_frames'], 4)
    _integer(memory['settle_us'], 1100000)
    _need(memory['settle_frames'] <= memory['process_frame'] - previous_frame
          and memory['settle_us'] <= value['ended_mono_us'] - previous_time, 'NATIVE_QUIESCENCE')
    _shape(memory['editor'], ' '.join(_COUNTERS))
    for name, row in memory['editor'].items():
        _counter(row, positive=name in ('rss_bytes', 'objects'), required=name in ('objects', 'resources'))
    barrier = value['barrier']
    _shape(barrier, 'mode required ack_file issued_mono_us deadline_mono_us root_instance_id generation baseline_sha256')
    _need(barrier['mode'] == 'host_ack_v1' and barrier['required'] is True
          and barrier['ack_file'] == f'benchmark/input/ack-{index:02d}.json'
          and barrier['issued_mono_us'] == value['ended_mono_us']
          and barrier['root_instance_id'] == previous_root and barrier['generation'] == previous_generation
          and barrier['baseline_sha256'] == baseline, 'NATIVE_BARRIER')
    _integer(barrier['deadline_mono_us'], barrier['issued_mono_us'] + 30000000, barrier['issued_mono_us'] + 30000000)
    _number(value['max_status_gap_ms'], .000000001)
    for name in ('dropped_commands', 'dropped_telemetry'):
        _integer(value[name], 0, 0)
    return value


def _artifact(value):
    _need(type(value) is BoundArtifact, 'BOUND_ARTIFACT_REQUIRED')
    return value.value


def _start_permit(native, command_artifact, ready_artifact, start_artifact, run_id, index, source_hash):
    ready, start = _artifact(ready_artifact), _artifact(start_artifact)
    _shape(ready, 'schema_id schema_version run_id pid batch_index source_closure_sha256 profile_sha256 start_file issued_mono_us deadline_mono_us root_instance_id generation baseline_sha256 scene_file_sha256 process_frame')
    _shape(start, 'schema_id schema_version run_id batch_index source_closure_sha256 profile_sha256 command_batch_sha256 ready_sha256 deadline_mono_us')
    _need(ready['schema_id'] == 'hh-studio.native-cycle-batch-ready' and start['schema_id'] == 'hh-studio.native-cycle-batch-start'
          and ready['schema_version'] == start['schema_version'] == '1.0.0', 'START_SCHEMA')
    for row in (ready, start):
        _need(row['run_id'] == run_id and row['source_closure_sha256'] == source_hash
              and row['profile_sha256'] == profile.PROFILE_SHA256, 'START_BINDING')
        _integer(row['batch_index'], index, index)
    _integer(ready['pid'], native['pid'], native['pid'])
    _integer(ready['issued_mono_us'], 1)
    _integer(ready['deadline_mono_us'], ready['issued_mono_us'] + 600000000, ready['issued_mono_us'] + 600000000)
    _integer(ready['process_frame'], 1, native['raw_timings'][0]['reload_observed_process_frame'] - 1)
    _integer(ready['root_instance_id'], 1)
    _integer(ready['generation'], 1)
    _digest(ready['scene_file_sha256'])
    _need(ready['start_file'] == f'benchmark/input/start-{index:02d}.json'
          and ready['root_instance_id'] == native['cycles'][0]['root_before']
          and ready['generation'] == native['raw_timings'][0]['generation_before']
          and ready['baseline_sha256'] == native['cycles'][0]['before_sha256'], 'READY_STATE')
    _need(start['ready_sha256'] == ready_artifact.sha256 and start['command_batch_sha256'] == command_artifact.sha256
          and start['deadline_mono_us'] == ready['deadline_mono_us'], 'START_HASH_BINDING')
    receipt = native['start_permit']
    _shape(receipt, 'batch_index start_file start_sha256 start_size_bytes ready_file ready_sha256 command_batch_sha256 issued_mono_us deadline_mono_us start_observed_mono_us process_frame root_instance_id generation semantic_sha256 max_status_gap_ms')
    expected = {'batch_index': index, 'start_file': ready['start_file'], 'start_sha256': start_artifact.sha256,
                'start_size_bytes': len(start_artifact.raw), 'ready_file': f'benchmark/out/ready-{index:02d}.json',
                'ready_sha256': ready_artifact.sha256, 'command_batch_sha256': command_artifact.sha256,
                'issued_mono_us': ready['issued_mono_us'], 'deadline_mono_us': ready['deadline_mono_us'],
                'root_instance_id': ready['root_instance_id'], 'generation': ready['generation'],
                'semantic_sha256': ready['baseline_sha256']}
    _need(all(receipt[key] == value and type(receipt[key]) is type(value) for key, value in expected.items()), 'START_RECEIPT_BINDING')
    _integer(receipt['start_observed_mono_us'], ready['issued_mono_us'], min(ready['deadline_mono_us'], native['started_mono_us']))
    _integer(receipt['process_frame'], ready['process_frame'], native['raw_timings'][0]['reload_observed_process_frame'] - 1)
    _number(receipt['max_status_gap_ms'], .000000001)
    return receipt


def assemble_sample(native, command, joint, *, run_id, index, processes,
                    source_closure_sha256, barrier_receipt, ack, ready, start):
    """Build one exact profile sample, retaining source evidence in its hash."""
    _integer(index, 0, 34)
    _digest(source_closure_sha256)
    _shape(processes, 'host editor')
    for identity in processes.values():
        _identity(identity)
    _need(processes['host']['pid'] != processes['editor']['pid'], 'PROCESS_ROLES')
    n = validate_native_batch(_artifact(native), run_id=run_id, index=index, editor_identity=processes['editor'])
    c = validate_command_batch(_artifact(command), run_id=run_id, index=index, host_identity=processes['host'])
    permit = _start_permit(n, command, ready, start, run_id, index, source_closure_sha256)
    j, a = _artifact(joint), _artifact(ack)
    _shape(a, 'schema_id schema_version run_id batch_index native_batch_sha256 source_closure_sha256 profile_sha256 deadline_mono_us')
    _need(a['schema_id'] == 'hh-studio.native-cycle-batch-ack' and a['schema_version'] == '1.0.0'
          and a['run_id'] == run_id and a['native_batch_sha256'] == native.sha256
          and a['source_closure_sha256'] == source_closure_sha256 and a['profile_sha256'] == profile.PROFILE_SHA256,
          'ACK_BINDING')
    _integer(a['batch_index'], index, index)
    _integer(a['deadline_mono_us'], n['barrier']['deadline_mono_us'], n['barrier']['deadline_mono_us'])
    receipt = barrier_receipt
    _shape(receipt, 'batch_index ack_file ack_sha256 ack_size_bytes native_batch_sha256 issued_mono_us deadline_mono_us ack_observed_mono_us root_instance_id generation semantic_sha256 max_status_gap_ms process_frame objects resources')
    expected = {'batch_index': index, 'ack_file': n['barrier']['ack_file'], 'ack_sha256': ack.sha256,
                'ack_size_bytes': len(ack.raw), 'native_batch_sha256': native.sha256,
                'issued_mono_us': n['barrier']['issued_mono_us'], 'deadline_mono_us': n['barrier']['deadline_mono_us'],
                'root_instance_id': n['barrier']['root_instance_id'], 'generation': n['barrier']['generation'],
                'semantic_sha256': n['barrier']['baseline_sha256']}
    _need(all(receipt[key] == value and type(receipt[key]) is type(value) for key, value in expected.items()), 'ACK_RECEIPT_BINDING')
    _integer(receipt['ack_observed_mono_us'], n['ended_mono_us'] + 1, n['barrier']['deadline_mono_us'])
    _integer(receipt['process_frame'], n['memory']['process_frame'] + 1)
    _counter(receipt['objects'], positive=True, required=True)
    _counter(receipt['resources'], required=True)
    _number(receipt['max_status_gap_ms'], .000000001)
    _need(receipt['max_status_gap_ms'] >= n['max_status_gap_ms'], 'ACK_STATUS_GAP')
    _shape(j, 'schema_id schema_version run_id index profile_sha256 source_closure_sha256 native_batch_sha256 command_batch_sha256 processes phase host_window host editor host_effect_count barrier_receipt ack_ref')
    _need(j['schema_id'] == 'hh-studio.benchmark-joint-observation' and j['schema_version'] == '1.0.0'
          and j['run_id'] == run_id and j['profile_sha256'] == profile.PROFILE_SHA256
          and j['source_closure_sha256'] == source_closure_sha256 and j['native_batch_sha256'] == native.sha256
          and j['command_batch_sha256'] == command.sha256 and j['processes'] == processes
          and j['phase'] == 'post_batch_quiescent' and j['barrier_receipt'] == receipt, 'JOINT_BINDING')
    _integer(j['index'], index, index)
    _integer(j['host_effect_count'], c['effect_count_after'], c['effect_count_after'])
    _need(j['ack_ref'] == {'file': ack.file, 'sha256': ack.sha256, 'size_bytes': len(ack.raw)}, 'JOINT_ACK_REFERENCE')
    window = j['host_window']
    _shape(window, 'started_mono_us ended_mono_us ack_written_mono_us')
    _integer(window['started_mono_us'], 1, c['started_mono_us'])
    _integer(window['ended_mono_us'], c['ended_mono_us'] + 1)
    _integer(window['ack_written_mono_us'], c['ended_mono_us'], window['ended_mono_us'])
    _shape(j['host'], 'monotonic_us counters')
    _host_observation({'process': processes['host'], **j['host']}, processes['host'])
    _integer(j['host']['monotonic_us'], c['ended_mono_us'], window['ack_written_mono_us'])
    editor = j['editor']
    _shape(editor, 'host_mono_us rss_bytes held_handles visible_window_handles native_observation')
    _integer(editor['host_mono_us'], c['ended_mono_us'], window['ack_written_mono_us'])
    _counter(editor['rss_bytes'], positive=True)
    _counter(editor['held_handles'])
    handles = editor['visible_window_handles']
    _need(type(handles) is list and 1 <= len(handles) <= 64 and len(set(handles)) == len(handles)
          and all(type(handle) is str and re.fullmatch(r'[1-9][0-9]{0,19}', handle) for handle in handles), 'EDITOR_GUI_WINDOW')
    observation = editor['native_observation']
    _shape(observation, 'source native_mono_us process_frame objects resources')
    _need(observation == {'source': 'native_ack', 'native_mono_us': receipt['ack_observed_mono_us'],
          'process_frame': receipt['process_frame'], 'objects': receipt['objects'], 'resources': receipt['resources']}, 'STALE_NATIVE_OBSERVATION')
    memory = {'phase': 'post_batch_quiescent', 'host': j['host']['counters'],
              'editor': {'rss_bytes': editor['rss_bytes'], 'held_handles': editor['held_handles'],
                         'objects': observation['objects'], 'resources': observation['resources']}}
    profile._memory(memory, '$.assembled.memory')
    evidence = {'profile_sha256': profile.PROFILE_SHA256, 'source_closure_sha256': source_closure_sha256,
                'run_id': run_id, 'index': index, 'processes': processes,
                'artifacts': {label: {'file': item.file, 'sha256': item.sha256, 'size_bytes': len(item.raw)}
                              for label, item in (('native', native), ('command', command), ('joint', joint),
                                                  ('ack', ack), ('ready', ready), ('start', start))},
                'barrier_receipt': receipt}
    return {'index': index, 'warmup': index < 5, 'processes': processes,
            'started_mono_us': window['started_mono_us'], 'ended_mono_us': window['ended_mono_us'],
            'latency_ms': c['latency_ms'], 'effects_per_admission': c['effects_per_admission'],
            'stop_target_instance_id': c['cancel']['command_id'], 'stop_receipt_ms': c['cancel']['receipt_ms'],
            'max_status_gap_ms': max(c['max_status_gap_ms'], receipt['max_status_gap_ms'], permit['max_status_gap_ms']),
            'cycles': n['cycles'], 'memory': memory, 'evidence_sha256': _sha(_encode(evidence)),
            'dropped_commands': 0, 'dropped_telemetry': 0}


def assemble_run(root, manifest):
    """Return a BoundRun; the parent must already have captured the host exit.

Manifest fields: schema_id/schema_version ('hh-studio.benchmark-run-assembly',
'1.0.0'), run_id,index,profile_sha256,source_closure_sha256,processes,refs,
native_batches,command_batches,joint_observations,ready_artifacts,
start_artifacts,ack_artifacts. Each artifact array has 35 reference objects.
refs contains native_index,source_manifest,toolchain,profile,native_stdout,
native_stderr,cleanup. Frozen studio files live under source/studio; runtime
native res:// files under project. cleanup is hh-studio.benchmark-cleanup/1.0.0
with run_id,processes,host_exit_code,editor_exit_code,owned_tree_zero,held_handles.
"""
    _shape(manifest, 'schema_id schema_version run_id index profile_sha256 source_closure_sha256 processes refs native_batches command_batches joint_observations ready_artifacts start_artifacts ack_artifacts')
    _need(manifest['schema_id'] == 'hh-studio.benchmark-run-assembly' and manifest['schema_version'] == '1.0.0'
          and manifest['profile_sha256'] == profile.PROFILE_SHA256, 'MANIFEST_SCHEMA')
    _integer(manifest['index'], 0, 9)
    _digest(manifest['source_closure_sha256'])
    _shape(manifest['refs'], 'native_index source_manifest toolchain profile native_stdout native_stderr cleanup')
    artifacts = {name: read_artifact(root, ref) for name, ref in manifest['refs'].items()}
    _need(artifacts['profile'].raw == _encode(asdict(profile.PROFILE)), 'PROFILE_BYTES')
    files = artifacts['source_manifest'].value
    _need(type(files) is dict and 1 <= len(files) <= 512, 'SOURCE_MANIFEST')
    _need(len({name.casefold() for name in files}) == len(files), 'SOURCE_PATH_ALIAS')
    for name, digest in files.items():
        _digest(digest)
        _need(type(name) is str and _NAME.fullmatch(name) and PurePosixPath(name).as_posix() == name
              and not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts, 'SOURCE_PATH')
        path = Path(root) / 'source/studio' / name
        read_artifact(root, {'file': 'source/studio/' + name, 'sha256': digest, 'size_bytes': path.stat().st_size})
    closure = _sha(''.join(name + '\0' + files[name] + '\n' for name in sorted(files)).encode())
    _need(closure == manifest['source_closure_sha256'] and files.get('toolchain.lock.json') == artifacts['toolchain'].sha256, 'SOURCE_CLOSURE')
    native_index = artifacts['native_index'].value
    _shape(native_index, 'schema_id schema_version input pid engine display_server editor_hint main_thread started_mono_us ended_mono_us started_unix source_files batches batches_completed host_barriers host_integrated cycles_per_batch baseline_revision max_status_gap_ms heartbeat_target_met quiescence host_barrier_timeout_us counter_definitions scope benchmark_complete completed formal_acceptance start_permits host_start_timeout_us batch_order startup_readiness')
    _need(native_index.get('schema_id') == 'hh-studio.native-cycle-benchmark' and native_index.get('schema_version') == '1.3.0'
          and native_index.get('completed') is True and native_index.get('benchmark_complete') is True
          and native_index.get('host_integrated') is True and native_index.get('formal_acceptance') is False
          and native_index.get('editor_hint') is True and native_index.get('main_thread') is True
          and native_index.get('batch_order') == 'host_commands_then_native_cycles_then_joint_ack', 'NATIVE_INDEX_SCOPE')
    _integer(native_index.get('pid'), manifest['processes']['editor']['pid'], manifest['processes']['editor']['pid'])
    _integer(native_index['started_mono_us'], 1)
    _integer(native_index['ended_mono_us'], native_index['started_mono_us'] + 1)
    _number(native_index['max_status_gap_ms'], .000000001)
    _need(type(native_index['heartbeat_target_met']) is bool
          and native_index['heartbeat_target_met'] == (native_index['max_status_gap_ms'] <= 2000)
          and native_index['quiescence'] == {'minimum_frames': 4, 'minimum_us': 1100000}, 'NATIVE_TIMING_DEFINITION')
    # The index also covers startup and inter-batch waits. Those intervals must
    # not disappear when the measured batch rows are projected into a dataset.
    _need(native_index['heartbeat_target_met'] is True, 'NATIVE_HEARTBEAT')
    _need(native_index['counter_definitions'] == {
        'objects': 'Performance.OBJECT_COUNT -> ObjectDB::get_object_count',
        'resources': 'Performance.OBJECT_RESOURCE_COUNT -> ResourceCache::get_cached_resource_count'}, 'NATIVE_COUNTER_DEFINITION')
    for field, count in (('batches_completed', 35), ('cycles_per_batch', 100), ('host_start_timeout_us', 600000000), ('host_barrier_timeout_us', 30000000)):
        _integer(native_index.get(field), count, count)
    binding = native_index['input']
    _need(binding == {'schema_id': 'hh-studio.native-cycle-benchmark-run', 'schema_version': '1.2.0',
          'run_id': manifest['run_id'], 'mode': 'full', 'source_closure_sha256': closure,
          'profile_sha256': profile.PROFILE_SHA256, 'batch_barrier': 'host_ack_v1', 'batch_start': 'host_permit_v1'}, 'NATIVE_INPUT')
    lock = artifacts['toolchain'].value['godot']
    _need(native_index.get('engine', {}).get('hash') == lock['source_commit']
          and native_index.get('display_server') == 'Windows', 'NATIVE_ENGINE')
    required = ('addons/hh_studio/plugin.gd', 'addons/hh_studio/scene_commands.gd', 'addons/hh_studio/jcs_godot.gd',
                'addons/hh_studio/plugin.cfg', 'scripts/fixture_actor.gd', 'addons/hh_benchmark/benchmark_native.gd',
                'addons/hh_benchmark/plugin.cfg', 'project.godot', 'benchmark/input.json', 'benchmark/.gdignore')
    _need(type(native_index.get('source_files')) is dict and set(native_index['source_files']) == {'res://' + name for name in required}, 'NATIVE_SOURCE_SET')
    for name in required:
        path = Path(root) / 'project' / name
        artifact = read_artifact(root, {'file': 'project/' + name, 'sha256': native_index['source_files']['res://' + name], 'size_bytes': path.stat().st_size})
        if name == 'benchmark/.gdignore':
            _need(artifact.raw == b'# HH Studio benchmark evidence is not a Godot asset.\n', 'NATIVE_EVIDENCE_IGNORE')
    source_mapping = {'addons/hh_studio/plugin.gd': 'godot-addon/addons/hh_studio/plugin.gd',
                      'addons/hh_studio/scene_commands.gd': 'godot-addon/addons/hh_studio/scene_commands.gd',
                      'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
                      'addons/hh_benchmark/benchmark_native.gd': 'tests/replay/benchmark_native.gd',
                      'addons/hh_benchmark/plugin.cfg': 'tests/replay/benchmark_plugin.cfg'}
    _need(all(files.get(source) == native_index['source_files']['res://' + destination]
              for destination, source in source_mapping.items()), 'NATIVE_SOURCE_CLOSURE')
    for name in ('tests/replay/benchmark_profile.py', 'tests/replay/benchmark_commands.py',
                 'tests/replay/benchmark_assembly.py', 'tests/replay/benchmark_readiness.py', 'host/core/transport.py',
                 'host/replay/verified_journal.py', 'protocol/core.py'):
        _need(name in files, 'SOURCE_CLOSURE_INCOMPLETE')
    input_path = Path(root) / 'project/benchmark/input.json'
    actual_input = read_artifact(root, {'file': 'project/benchmark/input.json',
        'sha256': native_index['source_files']['res://benchmark/input.json'], 'size_bytes': input_path.stat().st_size}).value
    _need(actual_input == binding, 'NATIVE_INPUT_BYTES')
    for field in ('native_batches', 'command_batches', 'joint_observations', 'ready_artifacts', 'start_artifacts', 'ack_artifacts'):
        _need(type(manifest[field]) is list and len(manifest[field]) == 35, 'RUN_INCOMPLETE')
    for field in ('batches', 'host_barriers', 'start_permits'):
        _need(type(native_index.get(field)) is list and len(native_index[field]) == 35, 'NATIVE_INDEX_INCOMPLETE')
    samples, previous_native, previous_ack = [], None, None
    for index in range(35):
        n, c, j, r, s, a = [read_artifact(root, manifest[field][index]) for field in
                            ('native_batches', 'command_batches', 'joint_observations', 'ready_artifacts', 'start_artifacts', 'ack_artifacts')]
        _need(native_index['batches'][index] == {'index': index, 'file': f'batch-{index:02d}.json', 'sha256': n.sha256, 'size_bytes': len(n.raw)}
              and native_index['start_permits'][index] == n.value['start_permit'], 'INDEX_BATCH_BINDING')
        sample = assemble_sample(n, c, j, run_id=manifest['run_id'], index=index, processes=manifest['processes'],
            source_closure_sha256=closure, barrier_receipt=native_index['host_barriers'][index], ack=a, ready=r, start=s)
        if index == 0:
            try:
                validate_startup_readiness(native_index['startup_readiness'], binding=binding,
                    pid=manifest['processes']['editor']['pid'], source_files=native_index['source_files'],
                    baseline_revision=native_index['baseline_revision'], scene_file_sha256=r.value['scene_file_sha256'],
                    first_batch_started_mono_us=n.value['started_mono_us'],
                    first_cycle_root_before=n.value['cycles'][0]['root_before'],
                    run_started_mono_us=native_index['started_mono_us'],
                    first_ready_mono_us=r.value['issued_mono_us'], first_ready_frame=r.value['process_frame'])
            except ReadinessError as error:
                raise AssemblyError(error.code) from error
        if samples:
            _need(sample['started_mono_us'] >= samples[-1]['ended_mono_us']
                  and sample['cycles'][0]['root_before'] == samples[-1]['cycles'][-1]['root_after']
                  and sample['cycles'][0]['before_sha256'] == samples[-1]['cycles'][-1]['reloaded_sha256'], 'RUN_CONTINUITY')
            _need(n.value['raw_timings'][0]['generation_before'] == previous_native['raw_timings'][-1]['generation_after']
                  and r.value['issued_mono_us'] >= previous_ack['ack_observed_mono_us']
                  and r.value['scene_file_sha256'] == previous_native['cycles'][-1]['saved_file_sha256'], 'NATIVE_RUN_CONTINUITY')
        _need(native_index['started_mono_us'] <= r.value['issued_mono_us']
              and native_index['host_barriers'][index]['ack_observed_mono_us'] <= native_index['ended_mono_us']
              and native_index['max_status_gap_ms'] >= max(n.value['max_status_gap_ms'],
                    n.value['start_permit']['max_status_gap_ms'], native_index['host_barriers'][index]['max_status_gap_ms']),
              'NATIVE_RUN_CLOCK')
        samples.append(sample)
        previous_native, previous_ack = n.value, native_index['host_barriers'][index]
    _need(native_index['baseline_revision'] == 'sha256:' + samples[0]['cycles'][0]['before_sha256'], 'NATIVE_BASELINE')
    scene = Path(root) / 'project/scenes/fixture.tscn'
    read_artifact(root, {'file': 'project/scenes/fixture.tscn', 'sha256': samples[-1]['cycles'][-1]['saved_file_sha256'],
                         'size_bytes': scene.stat().st_size})
    stdout, stderr = artifacts['native_stdout'].raw, artifacts['native_stderr'].raw
    _need(not stderr.strip() and not re.search(rb'\b(?:WARNING|ERROR)\b|ObjectDB instances leaked|HH_GT06_BENCHMARK_FAILED', stdout), 'NATIVE_LOG')
    prefix = b'HH_GT06_BENCHMARK_COMPLETE '
    complete = [_parse(line[len(prefix):]) for line in stdout.splitlines() if line.startswith(prefix)]
    _need(complete == [{'run_id': manifest['run_id'], 'pid': manifest['processes']['editor']['pid'],
          'mode': 'full', 'batches': 35, 'index_sha256': artifacts['native_index'].sha256,
          'benchmark_complete': True, 'host_integrated': True}], 'NATIVE_COMPLETE_MARKER')
    cleanup = artifacts['cleanup'].value
    _shape(cleanup, 'schema_id schema_version run_id processes host_exit_code editor_exit_code owned_tree_zero held_handles')
    _need(cleanup['schema_id'] == 'hh-studio.benchmark-cleanup' and cleanup['schema_version'] == '1.0.0'
          and cleanup['run_id'] == manifest['run_id'] and cleanup['processes'] == manifest['processes']
          and cleanup['owned_tree_zero'] is True, 'CLEANUP_BINDING')
    for key in ('host_exit_code', 'editor_exit_code', 'held_handles'):
        _integer(cleanup[key], 0, 0)
    run = {'run_id': manifest['run_id'], 'index': manifest['index'], 'processes': manifest['processes'],
           'baseline': {'after_batch_index': 4, 'memory': samples[4]['memory']}, 'samples': samples,
           'cleanup': {key: cleanup[key] for key in ('host_exit_code', 'editor_exit_code', 'owned_tree_zero', 'held_handles')}}
    raw = _encode({'source_closure_sha256': closure, 'toolchain_sha256': artifacts['toolchain'].sha256,
                   'profile_sha256': profile.PROFILE_SHA256, 'run': run})
    return BoundRun(sha256=_sha(raw), raw=raw)


def assemble_dataset(provenance, runs):
    """Require ten bound runs with one source/toolchain/profile; never promote diagnostics."""
    _shape(provenance, 'source_closure_sha256 toolchain_sha256 workstation_profile_sha256 driver_sha256 capture_manifest_sha256',
           '$.provenance')
    for digest in provenance.values():
        _digest(digest)
    _need(type(runs) is list, 'BOUND_RUNS_REQUIRED')
    expected = {'source_closure_sha256': provenance['source_closure_sha256'],
                'toolchain_sha256': provenance['toolchain_sha256'], 'profile_sha256': profile.PROFILE_SHA256}
    values = []
    for index, bound in enumerate(runs):
        path = f'$.runs[{index}]'
        _need(type(bound) is BoundRun, 'BOUND_RUN_REQUIRED', path)
        value = bound.value
        _need(all(value[name] == digest for name, digest in expected.items()), 'RUN_PROVENANCE_MISMATCH', path)
        values.append(value['run'])
    return profile.validate_dataset({'schema_id': 'hh-studio.tools-ux-benchmark', 'schema_version': '1.1.0',
        'profile_sha256': profile.PROFILE_SHA256, 'evidence_kind': 'native', 'provenance': provenance, 'runs': values})
