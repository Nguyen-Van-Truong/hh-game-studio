"""Offline derived reader. Never changes a run or promotes diagnostic results."""
import hashlib
import json
from pathlib import Path
import sys


def read(root, name, refs):
    path = root / name
    if not path.is_file():
        return None
    raw = path.read_bytes()
    refs[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return json.loads(raw)


def summarize(root):
    refs = {}
    result = read(root, 'result.json', refs)
    if result is None:
        raise ValueError('TERMINAL_REQUIRED')
    freeze = read(root, 'freeze.json', refs)
    timing = read(root, 'timing-summary.json', refs)
    http = read(root, 'attempt/http-phases-final.json', refs)
    report = {'AUTHORITY': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'run_id': result['run_id'], 'references': refs,
        'disposition': timing.get('disposition') if timing else 'MISSING_TIMING',
        'original_gates_passed': len(timing.get('gates', [])) if timing else 0,
        'source_unchanged': result.get('observations', {}).get('source_unchanged'),
        'cleanup_and_exits': result.get('observations'),
        'correlation': {'status': 'UNKNOWN', 'reason': 'MISSING_HTTP_OR_TIMING'},
        'limits': ['Top-three timing samples are incomplete; absence is not absence of waiting.',
                   'Same-PID QPC and numeric Windows thread identity correlate observations only.',
                   'Nested spans overlap; never add or subtract them from acceptance latency.',
                   'No disk/RAM/scheduler/root-cause or no-leak inference.']}
    if timing is None or http is None or not http.get('available'):
        return report
    observation = http['observation']
    actual = result.get('observations', {}).get('target', {}).get('actual_target_exit')
    if (timing['run_id'] != result['run_id'] or freeze['run_id'] != result['run_id']
            or http['run_id'] != result['run_id'] + '.r00.a01'
            or http['source_closure_sha256'] != freeze['source_closure']
            or http['profile_sha256'] != freeze['profile_sha256']
            or not actual or timing['pid'] != actual['pid'] or observation['pid'] != actual['pid']):
        raise ValueError('RUN_PID_SOURCE_BINDING')
    report['timing_aggregates'] = {label: {k: value[k] for k in
        ('count','wall_max_ms','wall_sum_ms','cpu_sum_ms')}
        for label,value in timing['timings'].items()}
    report['transport_failures_by_route'] = observation['transport_failures_by_route']
    failure = observation.get('first_failure')
    if failure is None:
        report['correlation'] = {'status':'NOT_REPRODUCED', 'reason':'NO_LOOKUP_FAILURE_WINDOW'}
        return report
    if failure['pid'] != actual['pid'] or failure['clock'] != 'perf_counter_ns':
        raise ValueError('FAILURE_CLOCK_PID')
    call = failure.get('failed_call_id')
    events = failure['events']
    headers = [r for r in events if r['root_id']==call and r['phase']=='client.headers'
        and r['kind']=='exit' and r['outcome']=='raised' and r['route']=='lookup']
    if len(headers)!=1 or failure['spans_dropped'] or failure['identity_missing']:
        report['correlation']={'status':'UNKNOWN','reason':'MISSING_OR_AMBIGUOUS_CLIENT_OR_IDENTITIES'}
        return report
    header=headers[0]; begin,end=header['started_ns'],header['timestamp_ns']
    pair=(header['server_port'],header['client_port'])
    if not all(type(v) is int and v>0 for v in pair):
        report['correlation']={'status':'UNKNOWN','reason':'MISSING_PORT_PAIR'}
        return report
    handles={r['root_id'] for r in events if r['phase']=='server.handle'
        and (r['server_port'],r['client_port'])==pair and r['started_ns']<=end
        and r['timestamp_ns']>=begin}
    dispatch=[r for r in failure['unfinished'] if r['phase']=='server.dispatch'
        and r['root_id'] in handles and r['route']=='lookup']
    if len(handles)!=1 or len(dispatch)!=1:
        report['correlation']={'status':'UNKNOWN','reason':'AMBIGUOUS_SERVER_LIFECYCLE'}
        return report
    appends=[r for r in failure['unfinished'] if r['phase']=='journal.append']
    matches=[]
    for span in appends:
        for label,aggregate in timing['timings'].items():
            for row in aggregate['slowest']:
                if (row['thread_id']==span['thread_id'] and row['start_ns']<=end
                        and row['end_ns']>=begin):
                    matches.append({'label':label,'journal_span':span['span_id'],
                        'wall_ms':row['wall_ms'],'thread_cpu_ms':row['thread_cpu_ms'],
                        'start_ns':row['start_ns'],'end_ns':row['end_ns'],
                        'overlap_ms':max(0,min(end,row['end_ns'])-max(begin,row['start_ns']))/1e6})
    report['correlation']={'status':'OBSERVED_OVERLAP' if matches else 'UNKNOWN',
        'reason':'BOUNDED_RETAINED_TIMINGS' if matches else 'TOP_THREE_DID_NOT_RETAIN_MATCH',
        'failed_call_id':call,'server_root':next(iter(handles)),
        'lookup_headers_ms':(end-begin)/1e6,'journal_appends_at_failure':appends,
        'overlapping_original_calls':matches}
    return report


if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('Use read_lookup_terminal.py <terminal-run-directory>')
    print(json.dumps(summarize(Path(sys.argv[1]).resolve()),indent=2,allow_nan=False))
