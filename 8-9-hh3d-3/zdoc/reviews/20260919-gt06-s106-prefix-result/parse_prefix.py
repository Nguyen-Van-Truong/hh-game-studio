"""Derive the bounded S106 prefix result from retained bytes only."""
from __future__ import annotations
import ast
import hashlib
import json
import ntpath
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = 'gt06-s106-handles-prefix-01'
SOURCE_SHA = '7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467'
PROFILE_SHA = '0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85'


def need(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def closure(values):
    return sha(''.join(k + '\0' + values[k] + '\n' for k in sorted(values)).encode())


def read(path):
    def unique(items):
        out = {}
        for key, value in items:
            need(key not in out, 'DUPLICATE_JSON_KEY')
            out[key] = value
        return out
    return json.loads(path.read_bytes(), object_pairs_hook=unique)


def job_clean(value):
    return (value['closed'] and value['zero_observed'] and value['active_count'] == 0
            and not value['handle_retained'] and not value['tainted']
            and not value['create_uncertain'] and not value['close_uncertain']
            and value['failed_operations'] == [])


def derive(root=HERE):
    raw, outer = root / 'raw', root / 'outer'
    ctx, original = read(raw / 'context.json'), read(raw / 'diagnostic-result.json')
    need(ctx['run_id'] == RUN_ID and ctx['limit_batches'] == 6 and ctx['capture_boundaries'] == [4, 5], 'CONTEXT_SCOPE')
    need(ctx['source_closure_sha256'] == SOURCE_SHA and len(ctx['source_files']) == 53
         and closure(ctx['source_files']) == SOURCE_SHA, 'SOURCE_CLOSURE')
    need(read(raw / 'source-files.json') == ctx['source_files'], 'SOURCE_MANIFEST')
    need(ctx['profile_sha256'] == PROFILE_SHA and not ctx['formal_acceptance'] and not ctx['eligible_for_dataset'], 'PROFILE_SCOPE')
    need(sha(canonical({k: v for k, v in ctx.items() if k != 'campaign_sha256'}) + b'\n') == ctx['campaign_sha256'], 'CAMPAIGN_BINDING')
    need(closure(ctx['diagnostic_files']) == ctx['diagnostic_closure_sha256'], 'DIAGNOSTIC_CLOSURE')
    for path, digest in ctx['diagnostic_files'].items():
        need(sha((root / 'frozen' / Path(path).name).read_bytes()) == digest, 'FROZEN_HELPER:' + path)
    for path, digest in ctx['helper_original_pins'].items():
        need(sha((root / 'frozen' / Path(path).name).read_bytes()) == digest, 'ORIGINAL_HELPER:' + path)
    need(sha((root / 'frozen/overlay.gd').read_bytes()) == ctx['generated_overlay_sha256'], 'OVERLAY')
    for name in ('run_benchmark_campaign.py', 'benchmark_profile.py'):
        need(sha((root / 'supporting-source' / name).read_bytes()) == ctx['source_files']['tests/replay/' + name], 'SUPPORTING_SOURCE')
    tree = ast.parse((root / 'supporting-source/benchmark_profile.py').read_text())
    profile_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'BenchmarkProfile')
    profile_values = {n.target.id: ast.literal_eval(n.value) for n in profile_class.body if isinstance(n, ast.AnnAssign)}
    need(sha(canonical(profile_values)) == PROFILE_SHA, 'PROFILE_LITERAL_HASH')
    audit = read(root / 'source-audit.json')
    need(audit['source_files'] == ctx['source_files'] and audit['diagnostic_files'] == ctx['diagnostic_files']
         and audit['helper_original_pins'] == ctx['helper_original_pins']
         and audit['all_selected_live_hashes_matched'] is True, 'RETAINED_LIVE_AUDIT')

    reference_files, reference_occurrences = {}, 0
    def refs(value):
        nonlocal reference_occurrences
        if isinstance(value, dict):
            if {'file', 'sha256', 'size_bytes'} <= value.keys():
                p = (raw / value['file']).resolve()
                need(p.is_relative_to(raw.resolve()), 'REFERENCE_TRAVERSAL')
                b = p.read_bytes()
                need(sha(b) == value['sha256'] and len(b) == value['size_bytes'], 'REFERENCE:' + value['file'])
                reference_files[value['file']] = value['sha256']
                reference_occurrences += 1
            for v in value.values():
                refs(v)
        elif isinstance(value, list):
            for v in value:
                refs(v)
    refs(original)
    samples, commands, natives, batch_rows = [], [], [], []
    need(sorted(p.name for p in raw.glob('batch-capture-*.json')) == [f'batch-capture-{i:02}.json' for i in range(6)], 'BATCH_SET')
    for index in range(6):
        cap = read(raw / f'batch-capture-{index:02}.json')
        need(set(cap) == {'index', 'command', 'native', 'joint', 'ack', 'ready', 'start'} and cap['index'] == index, 'CAPTURE_SHAPE')
        refs(cap)
        sample = read(raw / f'sample-preview-{index:02}.json')
        command, native, joint = [read(raw / cap[k]['file']) for k in ('command', 'native', 'joint')]
        refs(joint)
        need(sample['index'] == index and command['index'] == index and joint['index'] == index, 'BATCH_INDEX')
        need(joint['run_id'] == RUN_ID and command['run_id'] == RUN_ID, 'BATCH_RUN')
        need(joint['source_closure_sha256'] == SOURCE_SHA and joint['profile_sha256'] == PROFILE_SHA, 'JOINT_PINS')
        need(sample['processes'] == joint['processes'] == original['batches']['processes'], 'PROCESS_IDENTITIES')
        need(len(command['commands']) == 1000 and len(native['cycles']) == 100, 'WORKLOAD_COUNTS')
        need(sample['dropped_commands'] == sample['dropped_telemetry'] == 0, 'DROPPED_ROWS')
        need(sample['max_status_gap_ms'] == max(command['max_status_gap_ms'], native['max_status_gap_ms']), 'STATUS_GAP_REDUCTION')
        samples.append(sample); commands.append(command); natives.append(native)
        batch_rows.append({'index': index, 'warmup': sample['warmup'], 'editor': {k: v['value'] for k, v in sample['memory']['editor'].items()},
                           'host': {k: v['value'] for k, v in sample['memory']['host'].items()},
                           'http_status_gap_ms': command['max_status_gap_ms'], 'native_status_gap_ms': native['max_status_gap_ms'],
                           'combined_status_gap_ms': sample['max_status_gap_ms']})
    snapshots = []
    for index in (4, 5):
        gate, snapshot = read(raw / f'gates/batch-{index:02}.json'), read(raw / f'pss/batch-{index:02}.json')
        refs(gate); refs(snapshot)
        need(gate['run_id'] == snapshot['run_id'] == RUN_ID and gate['index'] == snapshot['index'] == index, 'SNAPSHOT_SCOPE')
        need(gate['result'] == 'PASSED' and gate['error'] is None, 'ORIGINAL_GATE')
        need(snapshot['source_closure_sha256'] == SOURCE_SHA and snapshot['profile_sha256'] == PROFILE_SHA
             and snapshot['diagnostic_closure_sha256'] == ctx['diagnostic_closure_sha256'], 'SNAPSHOT_PINS')
        need(gate['sample'] == snapshot['sample'] and gate['context'] == snapshot['context'], 'SNAPSHOT_REFS')
        need(gate['baseline'] == snapshot['baseline'], 'BASELINE_REFS')
        if index == 4:
            need(gate['baseline'] is None, 'BASELINE4')
        else:
            need(gate['baseline']['file'] == 'sample-preview-04.json', 'EXACT_BATCH4_BASELINE')
        c = snapshot['capture']
        need(gate['recorded_perf_ns'] <= snapshot['capture_started_perf_ns'] <= c['timing']['started_perf_ns'], 'GATE_BEFORE_PSS')
        need(c['status'] == 'OBSERVED' and c['binding_verified'] and c['errors'] == []
             and c['cleanup']['all_released'] and c['cleanup']['held_resources'] == [], 'PSS_VALID')
        need(c['identity']['pid'] == samples[index]['processes']['editor']['pid']
             and c['identity']['process_start'] == samples[index]['processes']['editor']['process_start']
             and ntpath.normcase(c['identity']['executable']) == ntpath.normcase(ctx['godot_executable']), 'PSS_IDENTITY')
        count = c['handles_captured']
        need(count == len(c['entries']) == sum(c['type_counts'].values()), 'PSS_ENTRY_COUNT')
        need(count == c['target_handle_count_before'] == c['target_handle_count_after']
             == samples[index]['memory']['editor']['held_handles']['value'], 'PSS_SAMPLE_COUNT')
        snapshots.append({'index': index, 'status': c['status'], 'identity': c['identity'], 'handles_captured': count,
                          'target_before': c['target_handle_count_before'], 'target_after': c['target_handle_count_after'],
                          'observer_before': c['observer_handle_count_before'], 'observer_after': c['observer_handle_count_after'],
                          'timing': c['timing'], 'type_counts': c['type_counts'], 'cleanup': c['cleanup'],
                          'errors': c['errors'], 'limitations': c['limitations'],
                          'gate_recorded_perf_ns': gate['recorded_perf_ns'], 'capture_started_perf_ns': snapshot['capture_started_perf_ns']})
    need(snapshots[0]['identity'] == snapshots[1]['identity'], 'SNAPSHOT_PROCESS_CHANGED')
    types = sorted(set(snapshots[0]['type_counts']) | set(snapshots[1]['type_counts']))
    deltas = [{'type': t, 'batch4': snapshots[0]['type_counts'].get(t, 0), 'batch5': snapshots[1]['type_counts'].get(t, 0),
               'delta': snapshots[1]['type_counts'].get(t, 0) - snapshots[0]['type_counts'].get(t, 0)} for t in types]
    comparisons = []
    for role in ('host', 'editor'):
        for name, row in samples[5]['memory'][role].items():
            if row['value'] is None:
                need(role == 'host' and name in ('objects', 'resources'), 'UNAVAILABLE_COUNTER')
                continue
            before, after = samples[4]['memory'][role][name]['value'], row['value']
            passed = after * 100 <= before * 110 if name == 'rss_bytes' else after <= before
            need(passed, 'ORIGINAL_COUNTER_GATE')
            comparisons.append({'role': role, 'metric': name, 'batch4': before, 'batch5': after, 'delta': after - before,
                                'unchanged_gate': 'max_10_percent_growth' if name == 'rss_bytes' else 'no_growth', 'passed': passed})
    need(samples[5]['max_status_gap_ms'] <= 2000, 'ORIGINAL_STATUS_GATE')

    terminal = read(raw / 'child-terminal-cleanup.json'); refs(terminal)
    need(terminal['errors'] == [] and terminal['completed_batches'] == 6, 'TERMINAL')
    failure = read(raw / 'child-failure.json')
    need(failure['code'] == 'S106_PREFIX_BOUNDARY' and failure['completed_batches'] == 6, 'EXPECTED_BOUNDARY')
    need(original['status'] == 'BOUNDARY_CAPTURED' and original['capture_status'] == 'COMPLETE'
         and original['errors'] == [] and original['owner']['cleanup_errors'] == []
         and original['owner']['primary_error'] is None and not original['owner']['timed_out'], 'ORIGINAL_RESULT')
    observations = terminal['observations']
    lifecycle = {}
    for role, helper_exit, actual_exit in (('host-owner', 1, 1), ('editor-host', 2, None), ('import-host', 0, 0)):
        start = read(raw / role / 'process-start.json')
        endpath = raw / role / 'process-exit.json'
        end = read(endpath) if endpath.exists() else None
        clean = read(raw / role / ('capture.json' if role == 'import-host' else 'cleanup-001.json'))
        need(clean['wrapper_exit_code'] == helper_exit and job_clean(clean['job']), 'JOB_CLEANUP:' + role)
        if actual_exit is None:
            need(end is None, 'EDITOR_EXIT_LIMIT_CHANGED')
        else:
            need(end['pid'] == start['pid'] and end['exit_code'] == actual_exit, 'ACTUAL_EXIT:' + role)
        if role in ('host-owner', 'editor-host'):
            sample_role = 'host' if role == 'host-owner' else 'editor'
            need(start['pid'] == samples[0]['processes'][sample_role]['pid'], 'TARGET_SAMPLE_PID:' + role)
        if role == 'import-host':
            need(clean['actual_process_exit'] == end, 'IMPORT_CAPTURE_EXIT')
            for filename, digest in clean['artifacts'].items():
                need(sha((raw / role / filename).read_bytes()) == digest, 'IMPORT_ARTIFACT:' + filename)
        if role != 'import-host':
            need(clean['wrapper_process_handle']['closed'] and not clean['wrapper_process_handle']['handle_retained']
                 and not clean['wrapper_process_handle']['close_uncertain'], 'WRAPPER_HANDLE:' + role)
        lifecycle[role] = {'pid': start['pid'], 'actual_exit': end['exit_code'] if end else None, 'helper_exit': helper_exit,
                           'job_zero_closed': True, 'native_wrapper_handle_close': 'UNKNOWN' if role == 'import-host' else 'RECORDED_RELEASE'}
    need(not observations['heartbeat_alive'] and not any(observations['editor_owner']['drain_threads_alive']), 'TERMINAL_THREADS')
    for key in ('editor_probe',):
        need(not observations[key]['handle_retained'] and not observations[key]['close_uncertain'], 'PROBE')
    observer = observations['import_observer']
    need(observer['closed'] and observer['probe_handles_released'] and not observer['thread_alive']
         and not observer['handle_retained'] and not observer['handle_close_uncertain']
         and observer['error_count'] == 0 and observer['global_held_probe_count'] == 0, 'IMPORT_OBSERVER')
    producer = observations['producer']
    need(producer['closed'] and producer['host']['stopped'] and producer['host']['main_socket_closed']
         and producer['host']['control_socket_closed'] and not any(producer['host']['threads_alive'])
         and not producer['observer_probe']['handle_retained'] and not producer['observer_probe']['close_uncertain'], 'PRODUCER_CLEANUP')
    need(producer['journal']['cache_closed'] and not producer['journal']['database_retained']
         and not producer['journal']['directory_retained'] and not producer['journal']['index_retained'], 'JOURNAL_CLEANUP')
    request, start, end, close = [read(outer / name) for name in ('request.json', 'process-start.json', 'process-exit.json', 'observer-close.json')]
    need(all(v['run_id'] == RUN_ID for v in (request, start, end, close)), 'OUTER_RUN')
    need(start['pid'] == end['pid'] and start['start_utc'] == end['start_utc'] and start['handle_retained']
         and start['executable'] == request['python'] and end['exit_code'] == 0
         and not end['forced_by_outer_observer'], 'OUTER_ACTUAL_EXIT')
    need(close['managed_process_disposed'] and not close['native_close_bool_observed'], 'OUTER_DISPOSE_SCOPE')
    need(request['helper_sha256'] == sha((root / 'frozen/owned_handles.py').read_bytes())
         and request['observer_sha256'] == sha((root / 'observer/observe_runner.ps1').read_bytes())
         and request['python_sha256'] == ctx['python_sha256'] == audit['python_sha256_observed'], 'OUTER_PINS')
    need(not (outer / 'stderr.txt').read_bytes() and not (outer / 'observer-error.json').exists(), 'OUTER_ERRORS')
    need(audit['stop_request_present'] is False and not (raw / 'stop-request.json').exists(), 'STOP_NOT_EXERCISED')
    http = read(raw / 'http-phases-final.json')['observation']
    need(http['transport_failures_observed'] == 0 and http['first_failure'] is None, 'HTTP_FAILURE')
    return {'schema': 'gt06-s106-prefix-comparison-v1', 'authority': 0, 'formal_acceptance': False,
            'eligible_for_dataset': False, 'final_critic': False, 'run_id': RUN_ID,
            'classification': 'NON_REPRODUCED', 'identical_prefix_branch': 'CLOSED_NO_IDENTICAL_RETRY',
            'root_cause_established': False, 'runtime_repair_justified': False, 'object_identity_delta_available': False,
            'original_result_status': original['status'], 'completed_batches': 6, 'http_commands': 6000, 'native_cycles': 600,
            'batch_capture_references_verified': 36, 'all_exact_reference_occurrences': reference_occurrences,
            'unique_exact_reference_files': len(reference_files), 'source_files_audited': 53, 'frozen_diagnostic_files_verified': 6,
            'profile_literal_hash_verified': PROFILE_SHA, 'source_closure_sha256': SOURCE_SHA,
            'diagnostic_closure_sha256': ctx['diagnostic_closure_sha256'], 'campaign_sha256': ctx['campaign_sha256'],
            'processes': samples[0]['processes'], 'batches': batch_rows, 'snapshots': snapshots,
            'type_count_deltas': deltas, 'changed_type_count_deltas': [v for v in deltas if v['delta']],
            'net_pss_handle_count_delta': snapshots[1]['handles_captured'] - snapshots[0]['handles_captured'],
            'batch5_original_counter_comparisons': comparisons, 'batch5_status_gate_passed': True,
            'max_http_gap_ms': max(c['max_status_gap_ms'] for c in commands),
            'max_native_gap_ms': max(n['max_status_gap_ms'] for n in natives),
            'http_transport_failures': 0, 'lifecycle': lifecycle, 'outer_actual_exit': end,
            'outer_native_close_return_observed': False, 'cleanup': 'RECORDED_JOBS_PROBES_THREADS_RELEASED',
            'stop': {'request_present': False, 'runtime_stop_exercised': False,
                     'binding': {'schema': 'HH-GT06-CAMPAIGN-STOP-1', 'run_id': RUN_ID,
                                 'source_closure_sha256': SOURCE_SHA, 'campaign_sha256': ctx['campaign_sha256'], 'reason': 'OPERATOR_STOP'},
                     'static_path': 'Frozen own_run/wait_owner check before launch, each tick and after exit; original stop_requested enforces exact binding.'},
            'limitations': ['COUNTS_AND_TYPES_ARE_NOT_PERSISTENT_OBJECT_IDENTITIES', '192_UNAVAILABLE_TYPE_ENTRIES_IN_EACH_SNAPSHOT',
                            'PSS_OBSERVER_EFFECT_UNKNOWN_NO_TIMING_SUBTRACTION', 'NO_POST_IDLE_SERIES',
                            'EDITOR_ACTUAL_NATURAL_EXIT_UNKNOWN', 'IMPORT_WRAPPER_NATIVE_HANDLE_CLOSE_UNKNOWN',
                            'OUTER_MANAGED_DISPOSE_NOT_NATIVE_CLOSE_RETURN', 'NO_F13_F14_OR_FULL_CAMPAIGN_PASS',
                            'S102_NATIVE_LATENCY_CAUSE_REMAINS_UNRESOLVED']}


if __name__ == '__main__':
    print(json.dumps(derive(), sort_keys=True, indent=2))
