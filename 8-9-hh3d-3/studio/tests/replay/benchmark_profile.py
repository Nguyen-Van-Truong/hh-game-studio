"""Exact tools-UX benchmark contract, without engine launch or acceptance.

PROFILE is frozen. validate_dataset(value) returns detached validated raw data;
summarize_dataset(value) derives PASS/FAIL/GAP, per-run and per-batch statistics.
PASS means the supplied complete measurements satisfy this profile, not that
their origin is authenticated. evidence_kind must explicitly be synthetic or
native. An external verifier must verify all source/profile/capture references.

Raw latency arrays preserve command ordinal within each class. Their IDs are
run_id/batch_index/class/ordinal; the fixed mix repeats 5 inspect, 3 rejected,
2 admitted entries 100 times. effects_per_admission has one native/mock-effect
readback per admitted ordinal. Each native cycle has all four timings, effect
counts, scene readback hashes and a changed root instance after reload.

Each run retains the same host/editor process identities throughout 35 batches.
baseline is the per-counter median of batches 2, 3 and 4's quiescent memory
observations. Counters are closed
{value, unavailable_reason} objects: unavailable applicable counters never mean
zero or PASS. Python host objects/resources are canonically not applicable;
host RSS/private commit/OS handles and all five editor counters remain mandatory.
Stop targets a separately bounded owned job; it must not restart the editor.
Large local series never enter a shared protocol envelope.

Direct CLI: python -B benchmark_profile.py --profile; or --input RAW.json.
The latter writes summary JSON to stdout: exit 0 PASS, 1 FAIL, 2 GAP/invalid.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys

if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from studio.host.replay.perf import summarize as frame_statistics

MAX_BYTES = 64 * 1024 * 1024
SAFE_INTEGER = (1 << 53) - 1
_HASH = re.compile(r'[0-9a-f]{64}\Z')
_ID = re.compile(r'[a-z][a-z0-9._-]{0,95}\Z')
_START = re.compile(r'(?:windows|linux):[1-9][0-9]{0,19}\Z')
_COUNTERS = ('rss_bytes', 'private_commit_bytes', 'objects', 'resources', 'held_handles')
_BASELINE_BATCHES = (2, 3, 4)
_STEPS = ('create', 'undo', 'save', 'reload')
HOST_NOT_APPLICABLE = 'NOT_APPLICABLE_PYTHON_HOST'


class BenchmarkError(ValueError):
    def __init__(self, code, path='$'):
        self.code, self.path = code, path
        super().__init__(f'{code}: {path}')


@dataclass(frozen=True, slots=True)
class BenchmarkProfile:
    profile_id: str = 'gt06-tools-ux-o1-v5'
    process_runs: int = 2
    warmup_batches: int = 5
    measured_batches: int = 30
    inspect_commands: int = 500
    rejected_commands: int = 300
    admitted_commands: int = 200
    native_cycles: int = 100
    stop_receipts_per_batch: int = 1
    inspect_p95_limit_ms: int = 500
    stop_p95_limit_ms: int = 500
    max_status_gap_ms: int = 2000
    rss_gate: str = 'diagnostic_only'
    memory_checkpoint_repetition: int = 10
    percentile_method: str = 'linear_type7'
    command_order: str = 'repeat_5inspect_3reject_2admitted'
    quiescent_phase: str = 'post_batch_quiescent'
    command_lane: str = 'host_api_50_30_20_mock_effect_allowed'
    cycle_lane: str = 'native_editor_direct_semantic_test_fixture'
    host_required_counters: str = 'rss_bytes private_commit_bytes held_handles'
    editor_required_counters: str = 'rss_bytes private_commit_bytes objects resources held_handles'
    baseline_batch_indices: str = '2,3,4'
    private_commit_baseline_percent: int = 110
    private_commit_trend_percent: int = 105
    early_handle_margin: int = 64
    early_object_margin: int = 256
    early_private_commit_percent: int = 150
    host_handles_tolerance: int = 4
    host_handles_trend: int = 2
    editor_handles_tolerance: int = 8
    editor_handles_trend: int = 2
    editor_objects_tolerance: int = 32
    editor_objects_trend: int = 8
    editor_resources_tolerance: int = 2
    editor_resources_trend: int = 1
    retained_handle_trend_min_increments: int = 3

    def __post_init__(self):
        # This version describes one workload, not a configurable smaller test.
        expected = ('gt06-tools-ux-o1-v5', 2, 5, 30, 500, 300, 200, 100, 1,
                    500, 500, 2000, 'diagnostic_only', 10, 'linear_type7',
                    'repeat_5inspect_3reject_2admitted', 'post_batch_quiescent',
                    'host_api_50_30_20_mock_effect_allowed', 'native_editor_direct_semantic_test_fixture',
                    'rss_bytes private_commit_bytes held_handles',
                    'rss_bytes private_commit_bytes objects resources held_handles',
                    '2,3,4', 110, 105, 64, 256, 150, 4, 2, 8, 2, 32, 8, 2, 1, 3)
        if any(type(a) is not type(b) or a != b for a, b in zip(asdict(self).values(), expected)):
            raise BenchmarkError('PROFILE_VERSION_REQUIRED')


PROFILE = BenchmarkProfile()


def counter_window(role, counter):
    """Return the frozen O1 T/G pair for an applicable retained counter."""
    values = {
        ('host', 'held_handles'): (PROFILE.host_handles_tolerance, PROFILE.host_handles_trend),
        ('editor', 'held_handles'): (PROFILE.editor_handles_tolerance, PROFILE.editor_handles_trend),
        ('editor', 'objects'): (PROFILE.editor_objects_tolerance, PROFILE.editor_objects_trend),
        ('editor', 'resources'): (PROFILE.editor_resources_tolerance, PROFILE.editor_resources_trend),
    }
    return values.get((role, counter))


def memory_gate_codes(role, counter, baseline, max_all, max_early, max_late):
    """Evaluate O1 limits, independently of dataset completeness/provenance.

    A historical prefix may have no late window; None leaves that check
    unevaluated. Formal callers first validate all 35 batches. This helper
    cannot issue an acceptance verdict or substitute missing observations.
    """
    if counter == 'rss_bytes':
        return []
    if counter == 'private_commit_bytes':
        codes = []
        if max_all * 100 > baseline * PROFILE.private_commit_baseline_percent:
            codes.append('PRIVATE_COMMIT_GROWTH')
        if max_late is not None and max_late * 100 > max_early * PROFILE.private_commit_trend_percent:
            codes.append('PRIVATE_COMMIT_TREND')
        return codes
    tolerance, trend = counter_window(role, counter)
    return ['RETAINED_COUNTER_GROWTH'] if (
        max_all > baseline + tolerance or
        (max_late is not None and max_late > max_early + trend)) else []


def retained_handle_trend_code(role, counter, values):
    """Owner-authorized supplemental rule; final critics still remain pending.

    O1's numerical windows remain authoritative. This supplemental rule only
    applies to retained handles and requires a nondecreasing 30-sample series,
    at least three positive steps, and a step in both measured halves. A single
    initialization step and non-monotonic noise remain outside this rule.
    """
    if role not in ('host', 'editor') or counter != 'held_handles' or len(values) != PROFILE.measured_batches:
        return None
    increases = [index for index in range(1, len(values)) if values[index] > values[index - 1]]
    early = any(index <= 14 for index in increases)
    # Both endpoints must lie within a half. The 19 -> 20 transition alone
    # does not establish growth inside the late (20..34) window.
    late = any(index >= 16 for index in increases)
    if (all(later >= earlier for earlier, later in zip(values, values[1:])) and
            len(increases) >= PROFILE.retained_handle_trend_min_increments and early and late):
        return 'RETAINED_COUNTER_TREND'
    return None


def _encoded(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (ValueError, TypeError, RecursionError, UnicodeError) as error:
        raise BenchmarkError('INVALID_JSON_VALUE') from error


PROFILE_SHA256 = hashlib.sha256(_encoded(asdict(PROFILE))).hexdigest()


def _need(value, code, path):
    if not value:
        raise BenchmarkError(code, path)


def _shape(value, names, path):
    _need(type(value) is dict and set(value) == set(names.split()), 'FIELDS', path)


def _int(value, low, high, path):
    _need(type(value) is int and low <= value <= high, 'INTEGER', path)


def _latency(value, path):
    _need(type(value) in (int, float) and 0 < value <= 600_000 and math.isfinite(value), 'LATENCY', path)


def _hash(value, path):
    _need(type(value) is str and _HASH.fullmatch(value), 'HASH', path)


def _id(value, path):
    _need(type(value) is str and _ID.fullmatch(value), 'IDENTIFIER', path)


def _array(value, count, path):
    _need(type(value) is list and len(value) == count, 'INCOMPLETE_ARRAY', path)


def _processes(value, path):
    _shape(value, 'host editor', path)
    for role, row in value.items():
        _shape(row, 'pid process_start', path + '.' + role)
        _int(row['pid'], 1, 0xffffffff, path)
        _need(type(row['process_start']) is str and _START.fullmatch(row['process_start']), 'PROCESS_START', path)
    _need(value['host'] != value['editor'], 'PROCESS_ROLES', path)


def _memory(value, path):
    _shape(value, 'phase host editor', path)
    _need(value['phase'] == PROFILE.quiescent_phase, 'MEMORY_PHASE', path)
    for role in ('host', 'editor'):
        _shape(value[role], ' '.join(_COUNTERS), path + '.' + role)
        for counter, observed in value[role].items():
            where = path + '.' + role + '.' + counter
            _shape(observed, 'value unavailable_reason', where)
            if role == 'host' and counter in ('objects', 'resources'):
                _need(observed['value'] is None and observed['unavailable_reason'] == HOST_NOT_APPLICABLE,
                      'HOST_COUNTER_APPLICABILITY', where)
                continue
            _need(observed['unavailable_reason'] != HOST_NOT_APPLICABLE, 'COUNTER_APPLICABILITY', where)
            if observed['value'] is None:
                reason = observed['unavailable_reason']
                _need(type(reason) is str and 1 <= len(reason) <= 160
                      and reason.isascii() and all(32 <= ord(c) < 127 for c in reason), 'COUNTER_REASON', where)
            else:
                _int(observed['value'], 1 if counter in ('rss_bytes', 'private_commit_bytes') else 0,
                     SAFE_INTEGER, where)
                _need(observed['unavailable_reason'] is None, 'COUNTER_AVAILABILITY', where)


def _median_memory(memories, path='$'):
    """Return the exact per-counter median for the frozen baseline window."""
    _need(type(memories) is list and len(memories) == len(_BASELINE_BATCHES),
          'BASELINE_WINDOW', path)
    for index, memory in zip(_BASELINE_BATCHES, memories):
        _memory(memory, f'{path}[batch={index}]')
    result = {'phase': PROFILE.quiescent_phase, 'host': {}, 'editor': {}}
    for role in ('host', 'editor'):
        for counter in _COUNTERS:
            rows = [memory[role][counter] for memory in memories]
            if role == 'host' and counter in ('objects', 'resources'):
                result[role][counter] = {'value': None, 'unavailable_reason': HOST_NOT_APPLICABLE}
                continue
            values = [row['value'] for row in rows]
            _need(all(type(value) is int for value in values), 'COUNTER_UNAVAILABLE', path)
            result[role][counter] = {'value': sorted(values)[1], 'unavailable_reason': None}
    return result


def baseline_memory(samples, path='$'):
    """Compute the baseline from sample memory rows 2, 3 and 4 only."""
    _need(type(samples) is list and len(samples) == 5, 'BASELINE_SAMPLES', path)
    rows = []
    for index in _BASELINE_BATCHES:
        row = samples[index]
        _need(type(row) is dict and row.get('index') == index, 'BASELINE_SAMPLE_INDEX', path)
        rows.append(row['memory'])
    return baseline_memory_rows(rows, path + '.memory')


def baseline_memory_rows(memories, path='$'):
    """Compute the same baseline from exactly three memory observations."""
    return _median_memory(memories, path)


def _validate(value):
    _shape(value, 'schema_id schema_version profile_sha256 evidence_kind provenance runs', '$')
    _need(value['schema_id'] == 'hh-studio.tools-ux-benchmark' and value['schema_version'] == '1.2.0'
          and value['profile_sha256'] == PROFILE_SHA256, 'PROFILE_BINDING', '$')
    _need(value['evidence_kind'] in ('synthetic', 'native'), 'EVIDENCE_KIND', '$')
    _shape(value['provenance'], 'source_closure_sha256 toolchain_sha256 workstation_profile_sha256 driver_sha256 capture_manifest_sha256', '$.provenance')
    for name, digest in value['provenance'].items():
        _hash(digest, '$.provenance.' + name)
    _array(value['runs'], PROFILE.process_runs, '$.runs')
    run_ids, process_ids, stop_ids = set(), set(), set()
    for index, run in enumerate(value['runs']):
        path = f'$.runs[{index}]'
        _shape(run, 'run_id index processes baseline samples cleanup', path)
        _int(run['index'], index, index, path)
        _id(run['run_id'], path)
        _need(run['run_id'] not in run_ids, 'DUPLICATE_RUN', path)
        run_ids.add(run['run_id'])
        _processes(run['processes'], path + '.processes')
        for process in run['processes'].values():
            identity = (process['pid'], process['process_start'])
            _need(identity not in process_ids, 'REUSED_PROCESS_RUN', path)
            process_ids.add(identity)
        _shape(run['baseline'], 'after_batch_indices memory', path + '.baseline')
        _need(run['baseline']['after_batch_indices'] == list(_BASELINE_BATCHES),
              'BASELINE_WINDOW', path)
        _memory(run['baseline']['memory'], path + '.baseline.memory')
        _array(run['samples'], 35, path + '.samples')
        previous_end, previous_root, previous_semantic = None, None, None
        for ordinal, sample in enumerate(run['samples']):
            at = path + f'.samples[{ordinal}]'
            _shape(sample, 'index warmup processes started_mono_us ended_mono_us latency_ms effects_per_admission stop_target_instance_id stop_receipt_ms max_status_gap_ms cycles memory evidence_sha256 dropped_commands dropped_telemetry', at)
            _int(sample['index'], ordinal, ordinal, at)
            _need(type(sample['warmup']) is bool and sample['warmup'] == (ordinal < 5), 'WARMUP_LABEL', at)
            _processes(sample['processes'], at + '.processes')
            _need(sample['processes'] == run['processes'], 'PROCESS_RESTART', at)
            _int(sample['started_mono_us'], 1, SAFE_INTEGER, at)
            _int(sample['ended_mono_us'], sample['started_mono_us'] + 1, SAFE_INTEGER, at)
            _need(previous_end is None or sample['started_mono_us'] >= previous_end, 'SAMPLE_CLOCK', at)
            previous_end = sample['ended_mono_us']
            _shape(sample['latency_ms'], 'inspect rejected admitted', at)
            for kind, count in (('inspect', PROFILE.inspect_commands),
                                ('rejected', PROFILE.rejected_commands),
                                ('admitted', PROFILE.admitted_commands)):
                _array(sample['latency_ms'][kind], count, at + '.' + kind)
                for latency in sample['latency_ms'][kind]:
                    _latency(latency, at + '.' + kind)
            _array(sample['effects_per_admission'], PROFILE.admitted_commands, at)
            _need(all(type(n) is int and n == 1 for n in sample['effects_per_admission']),
                  'DUPLICATE_OR_LOST_EFFECT', at)
            _id(sample['stop_target_instance_id'], at)
            _need(sample['stop_target_instance_id'] not in stop_ids, 'REUSED_STOP_SCOPE', at)
            stop_ids.add(sample['stop_target_instance_id'])
            _latency(sample['stop_receipt_ms'], at)
            _latency(sample['max_status_gap_ms'], at)
            _array(sample['cycles'], PROFILE.native_cycles, at + '.cycles')
            for number, cycle in enumerate(sample['cycles']):
                where = at + f'.cycles[{number}]'
                _shape(cycle, 'index root_before root_after before_sha256 created_sha256 undone_sha256 saved_file_sha256 reloaded_sha256 latency_ms effects main_thread', where)
                _int(cycle['index'], number, number, where)
                for name in ('root_before', 'root_after'):
                    _int(cycle[name], 1, SAFE_INTEGER, where)
                _need(cycle['root_before'] != cycle['root_after']
                      and (previous_root is None or cycle['root_before'] == previous_root), 'RELOAD_ROOT_CHAIN', where)
                previous_root = cycle['root_after']
                for name in ('before_sha256', 'created_sha256', 'undone_sha256', 'saved_file_sha256', 'reloaded_sha256'):
                    _hash(cycle[name], where)
                _need(cycle['before_sha256'] != cycle['created_sha256']
                      and cycle['before_sha256'] == cycle['undone_sha256'] == cycle['reloaded_sha256']
                      and (previous_semantic is None or cycle['before_sha256'] == previous_semantic), 'CYCLE_READBACK', where)
                previous_semantic = cycle['reloaded_sha256']
                _shape(cycle['latency_ms'], ' '.join(_STEPS), where)
                _shape(cycle['effects'], ' '.join(_STEPS), where)
                for step in _STEPS:
                    _latency(cycle['latency_ms'][step], where)
                    _int(cycle['effects'][step], 1, 1, where)
                _need(cycle['main_thread'] is True, 'EDITOR_MAIN_THREAD', where)
            _memory(sample['memory'], at + '.memory')
            _hash(sample['evidence_sha256'], at)
            _int(sample['dropped_commands'], 0, 0, at)
            _int(sample['dropped_telemetry'], 0, 0, at)
        _need(run['baseline']['memory'] == baseline_memory(run['samples'][:5], path + '.baseline'),
              'BASELINE_MEDIAN', path)
        _shape(run['cleanup'], 'host_exit_code editor_exit_code owned_tree_zero held_handles', path)
        _need(run['cleanup'] == {'host_exit_code': 0, 'editor_exit_code': 0, 'owned_tree_zero': True, 'held_handles': 0}
              and run['cleanup']['owned_tree_zero'] is True
              and all(type(run['cleanup'][key]) is int for key in ('host_exit_code', 'editor_exit_code', 'held_handles')),
              'UNCLEAN_RUN', path)


def validate_dataset(value):
    """Validate exact raw completeness; never infer absent counter values."""
    raw = _encoded(value)
    _need(len(raw) <= MAX_BYTES, 'DATASET_BYTE_CAP', '$')
    detached = json.loads(raw)
    _validate(detached)
    return detached


def parse_dataset(raw):
    """Strict bounded JSON; duplicates/nonfinite values cannot bypass checks."""
    _need(type(raw) is bytes and 0 < len(raw) <= MAX_BYTES, 'DATASET_BYTE_CAP', '$')
    def pairs(items):
        row = {}
        for key, value in items:
            _need(key not in row, 'DUPLICATE_KEY', '$')
            row[key] = value
        return row
    def nonfinite(_):
        raise BenchmarkError('NONFINITE_JSON')
    try:
        value = json.loads(raw.decode('utf-8', 'strict'), object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError) as error:
        if isinstance(error, BenchmarkError):
            raise
        raise BenchmarkError('INVALID_JSON') from error
    _validate(value)
    return value


def _stats(values):
    result = frame_statistics(values)
    return {'count': result['sample_count'], 'p50_ms': result['p50_frame_ms'],
            'p95_ms': result['p95_frame_ms'], 'p99_ms': result['p99_frame_ms'],
            'percentile_method': 'linear_type7'}


def summarize_dataset(value):
    """Derive results; failures/gaps retain run identity, never pooled away."""
    data = validate_dataset(value)
    runs, failures, gaps = [], [], []
    for run in data['runs']:
        run_id = run['run_id']
        measured = run['samples'][5:]
        metrics = {kind: _stats([n for row in measured for n in row['latency_ms'][kind]])
                   for kind in ('inspect', 'rejected', 'admitted')}
        metrics['stop_receipt'] = _stats([row['stop_receipt_ms'] for row in measured])
        for step in _STEPS:
            metrics[step] = _stats([cycle['latency_ms'][step] for row in measured for cycle in row['cycles']])
        for metric, limit in (('inspect', 500), ('stop_receipt', 500)):
            if metrics[metric]['p95_ms'] > limit:
                failures.append({'run_id': run_id, 'code': metric.upper() + '_P95', 'value': metrics[metric]['p95_ms']})
        # The fixed status-gap gate applies to every captured batch. A warmup
        # row over the limit is still a real protocol timing failure; warmup
        # is excluded only from percentile and memory growth samples.
        max_gap = max(row['max_status_gap_ms'] for row in run['samples'])
        if max_gap > 2000:
            failures.append({'run_id': run_id, 'code': 'STATUS_UPDATE_GAP', 'value': max_gap})
        memory = {}
        for role in ('host', 'editor'):
            memory[role] = {}
            for counter in _COUNTERS:
                if role == 'host' and counter in ('objects', 'resources'):
                    memory[role][counter] = {'applicable': False, 'reason': HOST_NOT_APPLICABLE}
                    continue
                observations = [run['baseline']['memory'][role][counter],
                                *[row['memory'][role][counter] for row in measured]]
                unavailable = [i for i, row in enumerate(observations) if row['value'] is None]
                if unavailable:
                    gaps.append({'run_id': run_id, 'code': 'COUNTER_UNAVAILABLE', 'role': role,
                                 'counter': counter, 'observation_indexes': unavailable})
                    memory[role][counter] = None
                    continue
                baseline, *values = [row['value'] for row in observations]
                growth = [100.0 * (n - baseline) / baseline for n in values] if counter in ('rss_bytes', 'private_commit_bytes') else None
                early, late = values[:15], values[15:]
                max_all, max_early, max_late = max(values), max(early), max(late)
                row = {'baseline': baseline, 'baseline_batches': list(_BASELINE_BATCHES),
                       'values': values, 'repetition_10': values[9],
                       'max_growth_percent': max(growth) if growth is not None else None,
                       'max_batch_5_34': max_all, 'max_batch_5_19': max_early,
                       'max_batch_20_34': max_late}
                memory[role][counter] = row
                codes = memory_gate_codes(role, counter, baseline, max_all, max_early, max_late)
                if counter == 'rss_bytes':
                    # Working set/RSS is retained for diagnosis and reports, but
                    # O1 deliberately removes it from the automatic gate.
                    continue
                if counter == 'private_commit_bytes':
                    if 'PRIVATE_COMMIT_GROWTH' in codes:
                        failures.append({'run_id': run_id, 'code': 'PRIVATE_COMMIT_GROWTH',
                                         'role': role, 'counter': counter, 'value': max_all,
                                         'baseline': baseline})
                    if 'PRIVATE_COMMIT_TREND' in codes:
                        failures.append({'run_id': run_id, 'code': 'PRIVATE_COMMIT_TREND',
                                         'role': role, 'counter': counter, 'value': max_late,
                                         'early_max': max_early})
                    continue
                window = counter_window(role, counter)
                tolerance, trend = window if window is not None else (None, None)
                if 'RETAINED_COUNTER_GROWTH' in codes:
                    failures.append({'run_id': run_id, 'code': 'RETAINED_COUNTER_GROWTH',
                                     'role': role, 'counter': counter, 'baseline': baseline,
                                     'max_batch_5_34': max_all, 'max_batch_5_19': max_early,
                                     'max_batch_20_34': max_late, 'tolerance': tolerance,
                                     'trend_tolerance': trend})
                trend_code = retained_handle_trend_code(role, counter, values)
                if trend_code is not None:
                    failures.append({'run_id': run_id, 'code': trend_code, 'role': role,
                                     'counter': counter, 'first_measured': values[0],
                                     'last_measured': values[-1],
                                     'minimum_increments': PROFILE.retained_handle_trend_min_increments})
        # Warm-up unavailability is retained as a gap too, never fabricated.
        for row in run['samples'][:5]:
            for role in ('host', 'editor'):
                for name in _COUNTERS:
                    if role == 'host' and name in ('objects', 'resources'):
                        continue
                    if row['memory'][role][name]['value'] is None:
                        gaps.append({'run_id': run_id, 'code': 'WARMUP_COUNTER_UNAVAILABLE',
                                     'batch': row['index'], 'role': role, 'counter': name})
        batches = [{'index': row['index'], 'metrics': {kind: _stats(values) for kind, values in row['latency_ms'].items()},
                    'stop_receipt_ms': row['stop_receipt_ms']} for row in measured]
        runs.append({'run_id': run_id, 'metrics': metrics, 'batches': batches, 'memory': memory,
                     'max_status_gap_ms': max_gap})
    return {'schema_id': 'hh-studio.tools-ux-benchmark-summary', 'schema_version': '1.3.0',
            'profile_sha256': PROFILE_SHA256, 'raw_sha256': hashlib.sha256(_encoded(data)).hexdigest(),
            'evidence_kind': data['evidence_kind'], 'native_acceptance': False,
            'command_lane': PROFILE.command_lane, 'cycle_lane': PROFILE.cycle_lane,
            'status': 'GAP' if gaps else 'FAIL' if failures else 'PASS',
            'scope': 'supplied raw measurement contract only; source/native origin requires independent verification',
            'measured_batches': PROFILE.process_runs * PROFILE.measured_batches,
            'measured_commands': PROFILE.process_runs * PROFILE.measured_batches *
            (PROFILE.inspect_commands + PROFILE.rejected_commands + PROFILE.admitted_commands),
            'measured_cycles': PROFILE.process_runs * PROFILE.measured_batches * PROFILE.native_cycles,
            'excluded_warmup_batches': PROFILE.process_runs * PROFILE.warmup_batches,
            'runs': runs, 'failures': failures, 'gaps': gaps}


def main(argv=None):
    """Read-only CLI; never launches an engine or writes source/artifacts."""
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--profile', action='store_true')
    mode.add_argument('--input', type=Path)
    args = parser.parse_args(argv)
    if args.profile:
        print(json.dumps({'profile': asdict(PROFILE), 'profile_sha256': PROFILE_SHA256}, indent=2))
        return 0
    try:
        with args.input.open('rb') as stream:
            raw = stream.read(MAX_BYTES + 1)
        result = summarize_dataset(parse_dataset(raw))
    except (BenchmarkError, OSError) as error:
        print(json.dumps({'status': 'INVALID', 'code': getattr(error, 'code', 'INPUT_IO'),
                          'path': getattr(error, 'path', '$')}))
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return {'PASS': 0, 'FAIL': 1, 'GAP': 2}[result['status']]


if __name__ == '__main__':
    raise SystemExit(main())
