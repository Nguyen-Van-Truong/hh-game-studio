"""Offline S119 reader: exact identities, retained lifecycles, temporal containment.

Never opens an engine, edits input evidence, or supplies an acceptance verdict.
"""
import hashlib
import json
from pathlib import Path
import sys


def need(value, code):
    if not value:
        raise ValueError(code)


def merged_events(first, final):
    events = {}
    for window in (first, final):
        for row in window['events']:
            key = row['event_id']
            need(key not in events or events[key] == row, 'EVENT_CONFLICT')
            events[key] = row
    return sorted(events.values(), key=lambda r: r['event_id'])


def lifecycles(events):
    groups = {}
    for row in events:
        groups.setdefault(row['span_id'], []).append(row)
    complete = {}
    for key, rows in groups.items():
        starts = [r for r in rows if r['kind'] == 'enter']
        ends = [r for r in rows if r['kind'] == 'exit']
        need(len(starts) <= 1 and len(ends) <= 1, 'DUPLICATE_LIFECYCLE')
        if not starts or not ends:
            continue  # Evicted/missing boundaries cannot acquire a fabricated extent.
        start, end = starts[0], ends[0]
        for field in ('span_id', 'parent_id', 'root_id', 'phase', 'thread_id', 'started_ns'):
            need(start[field] == end[field], 'LIFECYCLE_IDENTITY')
        need(start['timestamp_ns'] == start['started_ns'] <= end['timestamp_ns'], 'LIFECYCLE_TIME')
        complete[key] = {**end, 'enter_event_id': start['event_id']}
    return complete


def correlate(first, final, timings):
    unknown = lambda reason: {'status': 'UNKNOWN', 'reason': reason}
    if any(w['spans_dropped'] or w['identity_missing'] for w in (first, final)):
        return unknown('DROPPED_SPANS_OR_IDENTITIES')
    events = merged_events(first, final)
    spans = lifecycles(events)
    call = first['failed_call_id']
    headers = [r for r in first['events'] if r['kind'] == 'exit'
               and r['phase'] == 'client.headers' and r['root_id'] == call
               and r['route'] == 'lookup' and r['outcome'] == 'raised']
    if len(headers) != 1 or headers[0]['span_id'] not in spans or call not in spans:
        return unknown('MISSING_CLIENT_LIFECYCLE')
    header = headers[0]
    begin, end = header['started_ns'], header['timestamp_ns']
    pair = (header['server_port'], header['client_port'])
    if not all(type(p) is int and 0 < p < 65536 for p in pair):
        return unknown('MISSING_PORT_PAIR')
    handles = {e['span_id'] for e in events if e['phase'] == 'server.handle'
               and (e['server_port'], e['client_port']) == pair
               and e['span_id'] in spans and e['started_ns'] <= end
               and spans[e['span_id']]['timestamp_ns'] >= begin}
    if len(handles) != 1:
        return unknown('AMBIGUOUS_SERVER_LIFECYCLE')
    root = next(iter(handles))
    dispatch = [e for e in first['unfinished'] if e['phase'] == 'server.dispatch'
                and e['root_id'] == root and e['parent_id'] == root
                and e['route'] == 'lookup' and e['span_id'] in spans]
    if len(dispatch) != 1:
        return unknown('MISSING_DISPATCH_LIFECYCLE')
    dispatch = dispatch[0]
    lookup = [s for s in spans.values() if s['phase'] == 'server.lookup'
              and s['root_id'] == root and s['parent_id'] == dispatch['span_id']]
    if len(lookup) != 1:
        return unknown('MISSING_LOOKUP_LIFECYCLE')
    lookup = lookup[0]
    need(lookup['thread_id'] == dispatch['thread_id'], 'LOOKUP_THREAD')
    finish = [s for s in spans.values() if s['phase'] == 'host.finish'
              and s['started_ns'] <= end and s['timestamp_ns'] >= begin]
    if len(finish) != 1:
        return unknown('AMBIGUOUS_FINISH_LIFECYCLE')
    finish = finish[0]
    held = [s for s in spans.values() if s['phase'] == 'journal.guard_held'
            and s['root_id'] == finish['span_id'] and s['parent_id'] == finish['span_id']
            and s['thread_id'] == finish['thread_id']]
    if len(held) != 1:
        return unknown('MISSING_GUARD_LIFECYCLE')
    held = held[0]
    phase_map = {'coupled.reload': ('journal.reload', 'none'),
                 'coupled.snapshot_true': ('journal.snapshot', 'reload'),
                 'coupled.append': ('journal.append', 'none'),
                 'coupled.sqlite_commit': ('journal.append', 'append')}
    matches = []
    for label, (phase, scope) in phase_map.items():
        for row in timings.get(label, {}).get('slowest', []):
            need(row['start_ns'] <= row['end_ns'], 'TIMING_RANGE')
            if not (row['start_ns'] < end and row['end_ns'] > begin):
                continue
            candidates = [s for s in spans.values() if s['phase'] == phase
                and s['root_id'] == finish['span_id'] and s['thread_id'] == row['thread_id']
                and row['enclosing_scope'] == scope
                and s['started_ns'] <= row['start_ns'] <= row['end_ns'] <= s['timestamp_ns']]
            if len(candidates) != 1:
                continue
            span = candidates[0]
            parent = spans.get(span['parent_id'])
            expected_parent = 'journal.reload' if phase == 'journal.snapshot' else 'journal.guard_held'
            if not parent or parent['phase'] != expected_parent or parent['root_id'] != finish['span_id']:
                continue
            matches.append({'label': label, 'phase': phase, 'span_id': span['span_id'],
                'root_id': span['root_id'], 'parent_id': span['parent_id'], **row,
                'overlap_ms': (min(end, row['end_ns']) - max(begin, row['start_ns'])) / 1e6})
    return {'status': 'OBSERVED_BOUNDARY' if matches else 'UNKNOWN',
        'reason': 'EXACT_LIFECYCLES_AND_CONTAINMENT' if matches else 'NO_RETAINED_TIMING_MATCH',
        'failed_call_id': call, 'server_root': root, 'lookup_headers_ms': (end-begin)/1e6,
        'dispatch_before_lookup_ms': (lookup['started_ns']-dispatch['started_ns'])/1e6,
        'lookup_started_after_client_timeout': lookup['started_ns'] > end,
        'finish_span': finish, 'guard_span': held, 'matched_timings': matches,
        'claim_limit': 'Host lock wait is inferred from pinned code, not directly timed; no OS/disk/scheduler cause.'}


def summarize(root):
    refs = {}
    def read(name, required=True):
        path = root / name
        if not path.is_file():
            need(not required, 'MISSING_REQUIRED_' + name)
            return None
        raw = path.read_bytes()
        refs[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
        return json.loads(raw)
    result, freeze = read('result.json'), read('freeze.json')
    context = read('attempt/context.json')
    exit_record = read('owned/process-exit.json')
    timing, http = read('timing-summary.json', False), read('attempt/http-phases-final.json', False)
    run = result['run_id']
    need(result.get('formal_acceptance') is False and freeze.get('formal_acceptance') is False, 'DIAGNOSTIC_REQUIRED')
    need(run == freeze['run_id'] and context['run_id'] == run + '.r00.a01'
         and context['source_closure_sha256'] == freeze['source_closure']
         and context['profile_sha256'] == freeze['profile_sha256'], 'RUN_SOURCE_PROFILE_BINDING')
    target = result['observations']['target']
    need(target['actual_target_exit'] == exit_record
         and target['exit']['sha256'] == refs['owned/process-exit.json']['sha256'], 'TARGET_EXIT_BINDING')
    pid = exit_record['pid']
    if timing is not None:
        need(timing['run_id'] == run and timing['pid'] == pid, 'TIMING_BINDING')
    if http is not None:
        need(http['run_id'] == context['run_id']
             and http['source_closure_sha256'] == freeze['source_closure']
             and http['profile_sha256'] == freeze['profile_sha256']
             and http['context']['sha256'] == refs['attempt/context.json']['sha256'], 'HTTP_BINDING')
    report = {'AUTHORITY': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'run_id': run, 'references': refs, 'cleanup_and_exits': result['observations'],
        'correlation': {'status': 'UNKNOWN', 'reason': 'MISSING_HTTP_OR_TIMING'},
        'limits': ['Timing top-three is incomplete; missing match is UNKNOWN.',
                   'Nested durations cannot be added or subtracted from acceptance.',
                   'Numeric Windows thread identity is corroborated by phase and QPC containment.',
                   'No root-cause, repaired-runtime, no-leak, or formal PASS claim.']}
    if timing is None or http is None or not http.get('available'):
        return report
    observation = http['observation']
    need(observation['pid'] == pid and observation['clock'] == 'perf_counter_ns', 'OBSERVATION_IDENTITY')
    first = observation.get('first_failure')
    if first is None:
        report['correlation'] = {'status': 'NOT_REPRODUCED', 'reason': 'NO_RETAINED_LOOKUP_FAILURE'}
        return report
    need(first['pid'] == pid and first['clock'] == observation['clock']
         and first['captured_ns'] <= observation['captured_ns'], 'FAILURE_IDENTITY')
    report['correlation'] = correlate(first, observation, timing['timings'])
    report['transport_failures_by_route'] = observation['transport_failures_by_route']
    report['original_gates_passed'] = len(timing['gates'])
    return report


if __name__ == '__main__':
    print(json.dumps(summarize(Path(sys.argv[1])), indent=2, allow_nan=False))
