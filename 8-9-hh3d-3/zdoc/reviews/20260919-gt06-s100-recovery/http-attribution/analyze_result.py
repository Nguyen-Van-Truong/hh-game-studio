"""Read retained probe evidence and exclusively create derived analysis files."""
from pathlib import Path
from collections import Counter
import hashlib
import json

BASE = Path(__file__).resolve().parent
RUN = BASE / 'run-01'


def read(relative):
    return json.loads((RUN / relative).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    inputs = ['freeze.json', 'child/report.json', 'child/phases.json',
        'owned/capture.json', 'owned/http-host.json', 'owned/http-stdout.txt', 'owned/http-stderr.txt']
    inputs += [f'child/command-{index:02d}.json' for index in range(20)]
    hashes = {name: sha(RUN / name) for name in inputs}
    report, phases, capture = read('child/report.json'), read('child/phases.json'), read('owned/capture.json')
    freeze, target = read('freeze.json'), read('owned/http-host.json')
    commands = [read(f'child/command-{index:02d}.json') for index in range(20)]
    lookups = [(command['index'], row.get('ordinal', 'cancel'), attempt)
        for command in commands for row in [*command['commands'], command['cancel']]
        for attempt in row['lookup_attempts']]
    longest_lookup = max(lookups, key=lambda row: row[2]['ended_mono_us']-row[2]['started_mono_us'])
    gaps = [(end-start, start, end, command['index']) for command in commands
        for start, end in zip(command['host_response_mono_us'], command['host_response_mono_us'][1:])]
    largest_gap = max(gaps)
    gap_start, gap_end = largest_gap[1]*1000, largest_gap[2]*1000
    gap_spans = [{key: event[key] for key in ('span_id', 'parent_id', 'root_id', 'thread_id',
            'phase', 'route', 'started_ns', 'timestamp_ns', 'outcome', 'server_port', 'client_port')}
        | {'elapsed_ms': (event['timestamp_ns']-event['started_ns'])/1e6}
        for event in phases['events'] if event['kind'] == 'exit'
        and event['timestamp_ns'] >= gap_start and event['started_ns'] <= gap_end]
    gap_spans.sort(key=lambda row: row['elapsed_ms'], reverse=True)
    http = report['snapshot_subphases']['rows']['http']
    denominator = http['snapshots']['total_ns']
    subphases = {name: dict(row, total_ms=row['total_ns']/1e6,
        percent_of_http_snapshot_duration=row['total_ns']/denominator*100)
        for name, row in http['operations'].items()}
    residual = denominator-sum(row['total_ns'] for row in http['operations'].values())
    assert residual >= 0
    assert report['groups_completed'] == 20 and all(command['status'] == 'DIAGNOSTIC' for command in commands)
    assert len(lookups) == 160 and all(row[2]['transport_failure'] is None for row in lookups)
    assert phases['first_failure'] is None and phases['transport_failures_observed'] == 0
    assert phases['events_evicted'] == 9418 and len(phases['events']) == 8192
    assert phases['spans_dropped'] == phases['identity_missing'] == 0 and phases['unfinished'] == []
    assert capture['target_pid'] == target['target_pid'] == 37560
    assert capture['exit_code'] == target['exit_code'] == capture['wrapper_exit_code'] == 0
    assert capture['tree_verified'] is True and capture['timed_out'] is False
    assert report['source_before'] == report['source_after'] == freeze['source_files']
    result = {'schema': 'HH-S100-HTTP-RESULT-ANALYSIS-1', 'formal_acceptance': False,
        'eligible_for_dataset': False, 'root_cause_established': False, 'engine_runs': 0,
        'analysis_scope': 'Derived solely from retained copied-history HTTP probe; no new runtime/test execution',
        'input_hashes': hashes, 'analyzer_sha256': sha(Path(__file__)),
        'source_closure_sha256': freeze['current_source_closure_sha256'],
        'source_count': len(freeze['source_files']), 'source_and_helpers_unchanged': all(
            capture[key] for key in ('source_original_unchanged', 'source_copy_unchanged', 'helpers_unchanged')),
        'history': {'sha256': freeze['history_sha256'], 'bytes': freeze['history_bytes'],
            'original_and_copy_unchanged': capture['history_unchanged'],
            'kind': 'Exact S98 postterminal journal; not pre-failure batch17 or restored residency'},
        'workload': {'groups': 20, 'commands': sum(len(command['commands']) for command in commands),
            'mix': dict(Counter(row['kind'] for command in commands for row in command['commands'])),
            'cancel_commands': 20, 'cancel_no_effect': all(command['cancel']['no_effect'] for command in commands),
            'lookup_attempts': len(lookups), 'effects': commands[-1]['effect_count_after'],
            'lookup_statuses': dict(Counter(row[2]['status'] for row in lookups))},
        'duration': {'initial_load_ms': report['timings']['journal.load']['total_ns']/1e6,
            'http_group_sum_ms': sum(command['ended_mono_us']-command['started_mono_us'] for command in commands)/1000,
            'http_group_envelope_ms': (commands[-1]['ended_mono_us']-commands[0]['started_mono_us'])/1000,
            'scope': 'Initialization excluded from HTTP response windows; no invented process-wall duration'},
        'max_status_gap_ms': max(command['max_status_gap_ms'] for command in commands),
        'max_status_gap_group': largest_gap[3],
        'longest_lookup': {'group': longest_lookup[0], 'ordinal': longest_lookup[1],
            'elapsed_ms': (longest_lookup[2]['ended_mono_us']-longest_lookup[2]['started_mono_us'])/1000,
            'status': longest_lookup[2]['status'], 'transport_failure': longest_lookup[2]['transport_failure']},
        'snapshot_composition': {'http_snapshots': http['snapshots'], 'operations': subphases,
            'residual_ns': residual, 'residual_percent': residual/denominator*100,
            'denominator': 'Sum of 780 measured HTTP _snapshot context durations only',
            'validity': 'The three delegated suboperations are sequential inside each snapshot. Their composition is not an end-to-end HTTP share or CPU profile. Outer snapshot/reload/guard/dispatch spans overlap.',
            'residual_scope': 'Other snapshot operations, scheduling and observer overhead; no isolated overhead attribution',
            'fsync_scope': 'Snapshot durability barrier only; append/parser/SQLite/fsync internals unmeasured'},
        'operation_timings': {name: {key: row[key] for key in ('count', 'returned_count', 'total_ns', 'max_ns')}
            for name, row in report['timings'].items()},
        'largest_gap_retained_span_chain': {'group': 12, 'command_ordinal': 9, 'kind': 'admitted',
            'raw_interval_mono_us': [largest_gap[1], largest_gap[2]], 'largest_overlapping_spans': gap_spans[:18],
            'interpretation': 'Same socket pair and nested spans locate a 297.7172ms append inside 366.8098ms guard-held/444.0249ms commands dispatch. Append internal cost remains unsplit; this is not the S98 lookup timeout.'},
        'trace': {key: phases[key] for key in ('event_capacity', 'active_capacity', 'events_evicted',
            'spans_dropped', 'identity_missing', 'transport_failures_observed', 'transport_failures_by_route',
            'unfinished', 'first_failure')},
        'cleanup': {'target_pid': target['target_pid'], 'target_exit': target['exit_code'],
            'helper_pid': capture['wrapper_pid'], 'helper_exit': capture['wrapper_exit_code'],
            'owned_tree_verified_zero': capture['tree_verified'], 'timed_out': capture['timed_out'],
            'producer_closed': report['closed'], 'threads_alive': report['threads_alive'],
            'host': report['host_cleanup'], 'journal': report['journal_cleanup'], 'observer': report['observer_cleanup'],
            'stdout_bytes': (RUN/'owned/http-stdout.txt').stat().st_size,
            'stderr_bytes': (RUN/'owned/http-stderr.txt').stat().st_size,
            'limitation': 'run_fixture owned Job/actual-exit evidence; no independent retained-process-handle observer'},
        'limitations': ['No 2000ms gap occurred; absence in this short copied-history run neither clears nor diagnoses S98.',
            '9418 older events were evicted; zero dropped active spans does not mean a complete lifetime trace.',
            'Read/hash/fsync times are wall-clock call durations and can include descheduling; hash share is not CPU utilization.',
            'Expected rejected/missing-command control paths unwind wrappers; returned_count is not a wire failure count.',
            'No native/editor/ACK/residency/no-leak/F13/F14 evidence is produced.',
            'Fake wrapper overhead check is not representative of I/O/concurrency and was not subtracted.']}
    assert hashes == {name: sha(RUN / name) for name in inputs}
    with (BASE/'result-analysis.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    md = f'''# S100 copied-history HTTP result

AUTHORITY=0; formal_acceptance=false; eligible_for_dataset=false.

The probe completed 20 groups/200 commands/160 lookup attempts with 40 mock effects
and 20 cancellations confirmed without effect. Maximum host status gap was 446.3703 ms
(group 12); longest lookup was 382.548 ms (group 4). No transport failure occurred and
first_failure is null. This does not establish the cause or repair of S98's 2-second
lookup timeout.

The unchanged source51 closure is `{result['source_closure_sha256']}`. It loaded
17,761,123 exact S98 postterminal history bytes, then used a fresh project/producer.
This reconstructs neither the pre-failure batch17 history nor coupled residency.
Initial journal load took 12.6688604 s, outside HTTP response windows. The 20 HTTP group
windows totalled 37.318641 s (first-to-last envelope 37.351543 s).

Within the 780 HTTP snapshot contexts (28.7525402 s total), sequential suboperations
accounted for:

| Snapshot suboperation | Total | Share of snapshot time |
|---|---:|---:|
| Hash update |20.272694 s|70.5075%|
| Read |5.0855682 s|17.6874%|
| Snapshot fsync |0.4030053 s|1.4016%|
| Residual |2.9912727 s|10.4035%|

Read and hash each processed 13,943,550,521 bytes across these snapshots. These are
wall-clock call durations, potentially including descheduling. Shares use only
snapshot time; they are not an HTTP/CPU profile or a cause allocation for S98.
Residual includes other snapshot work and instrumentation. Snapshot fsync excludes
append/parser/SQLite durability work. Nested reload/guard/dispatch totals overlap
and must not be added to this table.

The retained trace covers the largest observed gap: group 12 admitted command 9,
client/server socket pair 53341/61540. A 444.0249 ms commands dispatch contains a
366.8098 ms guard-held span, including a 297.7172 ms append. This locates the large
cost inside append in this observation, without identifying append's internal
I/O/SQLite/fsync/scheduling component or explaining S98's lookup timeout.

The ring retains 8192 events and evicted 9418 earlier events. It reports 0 dropped active
spans, 0 missing identities and 0 unfinished spans at completion. These counters do
not establish a complete lifetime trace. first_failure remains null.

Target 37560 and helper 36872 exited 0; owned tree verification succeeded, no timeout,
stderr/stdout empty. Producer threads/sockets/index/observer handles closed according
to the retained cleanup record. Source, helper and original/copied history checks
remain unchanged. This runner supplies its owned Job/actual-exit evidence; it does
not add the separate retained-handle observer's proof.

The JSON analysis records hashes for every input, operation totals, the retained
span chain and limitations. Reproduce by running `analyze_result.py` against an
unchanged retained run in a fresh analysis location; exclusive outputs prevent
overwriting this analysis. No runtime or engine was launched by analysis.
'''
    with (BASE/'result-analysis.md').open('x', encoding='utf-8') as stream:
        stream.write(md)
    print(json.dumps({'analysis_sha256': sha(BASE/'result-analysis.json'),
        'markdown_sha256': sha(BASE/'result-analysis.md'), 'raw_unchanged': True}, sort_keys=True))


if __name__ == '__main__':
    main()
