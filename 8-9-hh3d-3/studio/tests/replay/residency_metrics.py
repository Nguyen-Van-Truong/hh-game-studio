"""Offline residency diagnostics; never process proof or formal acceptance.

Latency windows follow logical commands (batches 0..4 versus 30..34), not
the first/last 5,000 journal operations or averages of batch percentiles.
The default O6.3 policy preserves historical p95 verdicts. O7 must be selected
explicitly with a bound interleaved probe and its unchanged original seeds.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median
import sys

STUDIO = Path(__file__).resolve().parents[2]
LEGACY_POLICY = 'O6.3'
O7_POLICY = 'O7'
POLICIES = (LEGACY_POLICY, O7_POLICY)


def need(condition, code):
    if not condition:
        raise ValueError(code)


def number(value):
    if type(value) is int:
        return value >= 0
    return type(value) is float and math.isfinite(value) and value >= 0


def p95(values):
    need(values and all(number(v) for v in values), 'TIMING_VALUES')
    ordered = sorted(values)
    position = (len(ordered) - 1) * .95
    lower = int(position)
    return ordered[lower] + (ordered[min(lower + 1, len(ordered) - 1)]
                             - ordered[lower]) * (position - lower)


def _calculate(summaries, timings, recoveries, *, policy, journal_scaling=None):
    need(policy in POLICIES, 'UNKNOWN_POLICY')
    need(policy != O7_POLICY or journal_scaling is not None, 'INTERLEAVED_PROBE_REQUIRED')
    need(len(summaries) == len(timings) == len(recoveries) == 35, 'FULL_35_REQUIRED')
    private, handles, gaps = [], [], []
    identity = summaries[0]['host_process']
    need(type(identity) is dict and type(identity.get('pid')) is int
         and identity['pid'] > 0 and type(identity.get('process_start')) is str
         and identity['process_start'], 'PROCESS_IDENTITY')
    previous_counts = {'lookup': 0, 'append': 0}
    previous_events = 0
    for index, (row, timing, recovery) in enumerate(zip(summaries, timings, recoveries)):
        need(type(row['index']) is int and row['index'] == index
             and type(row['commands']) is int and row['commands'] == 1000, 'BATCH_SHAPE')
        observation = row['memory_after_release']
        need(row['host_process'] == observation['process'] == identity, 'PROCESS_IDENTITY')
        for name, series in (('private_commit_bytes', private), ('held_handles', handles)):
            counter = observation['counters'][name]
            minimum = 1 if name == 'private_commit_bytes' else 0
            need(counter['unavailable_reason'] is None and type(counter['value']) is int
                 and counter['value'] >= minimum, 'COUNTER_UNAVAILABLE')
            series.append(counter['value'])
        need(number(row['max_status_gap_ms']), 'STATUS_GAP_SHAPE')
        gaps.append(row['max_status_gap_ms'])
        need(type(timing['counts']['load']) is int and timing['counts']['load'] == 1,
             'FULL_RELOAD')
        for operation in previous_counts:
            count = timing['counts'][operation]
            values = timing['latency_ms'][operation]
            need(type(count) is int and type(values) is list
                 and count > previous_counts[operation]
                 and len(values) == count - previous_counts[operation]
                 and type(timing['dropped'][operation]) is int
                 and timing['dropped'][operation] == 0
                 and all(number(v) for v in values), 'TIMING_COVERAGE')
            previous_counts[operation] = count
        before, after = recovery['event_count_before'], recovery['event_count_after']
        need(type(before) is int and type(after) is int and before == previous_events
             and after >= before and type(recovery['events']) is list
             and all(type(event) is dict for event in recovery['events'])
             and len(recovery['events']) == after - before, 'TRANSPORT_COVERAGE')
        need(recovery['all_reconciled'] is True, 'TRANSPORT_UNRECONCILED')
        previous_events = after
    baseline = median(private[2:5])
    need(baseline > 0 and max(private[5:20]) > 0, 'PRIVATE_BASELINE')
    growth = max(private[5:35]) / baseline
    trend = max(private[20:35]) / max(private[5:20])
    host_baseline = median(handles[2:5])
    checks = {'private_growth': max(private[5:35]) * 100 <= baseline * 110,
              'private_trend': max(private[20:35]) * 100 <= max(private[5:20]) * 105,
              'host_handles_growth': max(handles[5:35]) <= host_baseline + 4,
              'host_handles_trend': max(handles[20:35]) <= max(handles[5:20]) + 2,
              'status_gap_all_batches': max(gaps) <= 2000}
    latency = {}
    for operation in ('lookup', 'append'):
        first = [v for row in timings[:5] for v in row['latency_ms'][operation]]
        last = [v for row in timings[30:35] for v in row['latency_ms'][operation]]
        first_p95, last_p95 = p95(first), p95(last)
        need(first_p95 > 0, 'TIMING_BASELINE')
        if policy == LEGACY_POLICY:
            checks[operation + '_p95'] = last_p95 <= 1.2 * first_p95
        else:
            checks[operation + '_interleaved_median'] = journal_scaling['checks'][operation]
        first_median, last_median = median(first), median(last)
        latency[operation] = {'first_operations': len(first), 'last_operations': len(last),
                              'first_median_ms': first_median, 'last_median_ms': last_median,
                              'median_last_over_first_percent': (100 * last_median / first_median
                                                                 if first_median > 0 else None),
                              'first_p95_ms': first_p95, 'last_p95_ms': last_p95,
                              'last_over_first_percent': 100 * last_p95 / first_p95,
                              'p95_report_only': policy == O7_POLICY}
    passed = all(checks.values())
    variation_triggered = max(private[5:35]) * 100 > baseline * 107
    report = {'authority': 0, 'formal_acceptance': False, 'metric_checks_only': True,
            'policy': policy,
            'metrics_pass': passed, 'failed_checks': [k for k, v in checks.items() if not v],
            'variation_triggered': variation_triggered,
            # O6.3 makes the >107% variation check an independent next-run
            # trigger.  A failing timing/counter check still blocks formal;
            # callers must review both flags before dispatching another ID.
            'additional_soak_required': variation_triggered,
            'private_commit': {'baseline_bytes': baseline, 'max_bytes': max(private[5:35]),
                               'growth_percent': growth * 100, 'late_over_early_percent': trend * 100},
            'host_handles': {'baseline': host_baseline, 'min': min(handles), 'max': max(handles)},
            'status_gap_max_ms': max(gaps), 'journal_latency': latency,
            'load': 1, 'recovery_event_count': previous_events,
            'scope': 'O6.3 metrics only; verify raw commands, actual exits, ownership, watchdog and source separately'}
    if policy == O7_POLICY:
        report['interleaved_journal'] = journal_scaling
        report['scope'] = ('O7 finite-workload diagnostic metrics only; no complexity proof or native editor '
                           'coverage; verify raw commands, actual exits, ownership and watchdog separately')
    return report


def calculate(summaries, timings, recoveries, *, policy=LEGACY_POLICY):
    """Pure historical calculation. O7 requires file/source/seed binding in from_run."""
    need(policy in POLICIES, 'UNKNOWN_POLICY')
    need(policy == LEGACY_POLICY, 'INTERLEAVED_PROBE_REQUIRED')
    return _calculate(summaries, timings, recoveries, policy=policy)


def read_json(path, limit):
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(len(raw) <= limit, 'ARTIFACT_SIZE')
    return json.loads(raw)


def from_run(root, *, policy=LEGACY_POLICY, interleaved_probe=None,
             seed_directory=None, source_root=STUDIO):
    need(policy in POLICIES, 'UNKNOWN_POLICY')
    if policy == O7_POLICY:
        need(interleaved_probe is not None and seed_directory is not None,
             'INTERLEAVED_PROBE_REQUIRED')
    else:
        need(interleaved_probe is None and seed_directory is None, 'PROBE_REQUIRES_O7_POLICY')
    summaries, timings, recoveries = [], [], []
    for index in range(35):
        summaries.append(read_json(root / f'summary-{index:02}.json', 65536))
        timings.append(read_json(root / f'journal-timing-{index:02}.json', 512 * 1024))
        batch = read_json(root / f'batch-{index:02}.json', 8 * 1024 * 1024)
        need(type(batch['index']) is int and batch['index'] == index
             and batch['run_id'] == root.name
             and batch['host_process'] == summaries[-1]['host_process']
             and type(batch['commands']) is list
             and len(batch['commands']) == summaries[-1]['commands']
             and number(batch['max_status_gap_ms'])
             and batch['max_status_gap_ms'] == summaries[-1]['max_status_gap_ms'],
             'BATCH_BINDING')
        recoveries.append(batch['transport_recovery'])
    legacy = calculate(summaries, timings, recoveries)
    if policy == LEGACY_POLICY:
        return {'run_id': root.name, **legacy}
    # This verifier stays outside the formal/runtime closure. Importing this
    # offline reader never starts a producer, engine, counter or live probe.
    sys.path.insert(0, str(STUDIO.parent))
    from studio.tests.replay.journal_scaling_metrics import read_bound_probe
    scaling = read_bound_probe(Path(interleaved_probe), Path(seed_directory),
                               source_root=Path(source_root), soak_root=root)
    report = _calculate(summaries, timings, recoveries, policy=policy, journal_scaling=scaling)
    report['legacy_policy_result'] = {'policy': LEGACY_POLICY,
                                     'metrics_pass': legacy['metrics_pass'],
                                     'failed_checks': legacy['failed_checks']}
    return {'run_id': root.name, **report}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-directory', type=Path, required=True)
    parser.add_argument('--policy', choices=POLICIES, default=LEGACY_POLICY)
    parser.add_argument('--interleaved-probe', type=Path,
                        help='O7 retained probe03 result.json (adjacent inspected probe.py)')
    parser.add_argument('--seed-directory', type=Path,
                        help='O7 probe01 directory containing unchanged early/late.jsonl originals')
    args = parser.parse_args()
    try:
        report = from_run(args.run_directory, policy=args.policy,
                          interleaved_probe=args.interleaved_probe,
                          seed_directory=args.seed_directory)
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({'authority': 0, 'formal_acceptance': False,
                          'policy': args.policy, 'metrics_pass': False,
                          'evidence_invalid': type(error).__name__,
                          'reason': str(error) if type(error) is ValueError else 'INVALID_EVIDENCE'}))
        return 2
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['metrics_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
