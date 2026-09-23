"""Derive a bounded S181 failure report from immutable retained raw."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RAW = ROOT / 'studio/.local/reviews/gt06-s181-formal-01/run-00-attempt-01'


def read(name):
    return json.loads((RAW / name).read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    failure = read('child-failure.json')
    partial = failure['partial_command']
    row = partial['commands'][-1]
    phase = read('http-phases-final.json')['observation']
    attempts = row['lookup_attempts']
    start = row['started_mono_us'] * 1000
    relevant = [event for event in phase['events'] if event['timestamp_ns'] >= start
                and event['kind'] == 'exit' and (event['phase'].startswith('journal.')
                                               or event['phase'] == 'host.finish')]
    spans = [{'phase': e['phase'], 'thread_id': e['thread_id'], 'root_id': e['root_id'],
              'start_relative_ms': (e['started_ns']-start)/1e6,
              'duration_ms': (e['timestamp_ns']-e['started_ns'])/1e6,
              'outcome': e['outcome']} for e in relevant]
    durable = []
    with (RAW / 'commands/commands.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            value = json.loads(line)
            if value['record'].get('command_id') == row['command_id']:
                durable.append(value)
    assert [entry['record']['status'] for entry in durable] == ['ACCEPTED_PENDING', 'COMMITTED']
    assert all(entry['record']['digest'] == row['request_digest'] for entry in durable)
    pins = read('source-files.json')
    drift = [name for name, digest in pins.items() if sha(ROOT/'studio'/name) != digest]
    assert not drift, drift
    summary = {
        'run_id': 'gt06-s181-formal-01', 'audit_id': 'gt06-s182-terminal-attribution-01',
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'authority': 0,
        'formal_acceptance': False, 'accepted_full_runs': 0, 'completed_batches': 22,
        'failure_code': failure['code'], 'phase': failure['phase'],
        'partial_command_count': len(partial['commands']), 'failed_command_id': row['command_id'],
        'lookup_attempts': len(attempts), 'lookup_transport_failures': sum(bool(a['transport_failure']) for a in attempts),
        'lookup_window_ms': (attempts[-1]['ended_mono_us']-attempts[0]['started_mono_us'])/1000,
        'admission_to_last_response_ms': row['terminal_ms'],
        'deadline_note': '5s terminal budget starts in _terminal, after admission; admission-to-response is not the budget',
        'last_lookup_status': attempts[-1]['status'], 'last_lookup_code': attempts[-1]['code'],
        'partial_max_status_gap_ms': partial['max_status_gap_ms'],
        'durable_rows': durable, 'phase_spans': spans,
        'first_transport_failure_before_last_admission_ms': (start-phase['first_failure']['captured_ns'])/1e6,
        'total_transport_failures': phase['transport_failures_observed'],
        'transport_failures_by_route': phase['transport_failures_by_route'],
        'host_actual_exit': read('host-owner/process-exit.json'),
        'import_actual_exit': read('import-host/process-exit.json'),
        'editor_actual_exit': None, 'editor_helper_exit': 2, 'supervisor_actual_exit': None,
        'cleanup_errors': read('child-terminal-cleanup.json')['errors'],
        'source_pins_checked': len(pins), 'source_drift': drift,
        'inputs': {name: sha(RAW/name) for name in ['child-failure.json','http-phases-final.json',
                   'commands/commands.jsonl','child-terminal-cleanup.json','source-files.json']},
        'conclusion': 'Terminal journal work returned after last queued lookup; late durable COMMITTED is not an in-deadline ACK.',
        'unproven': ['Cause of long snapshot/append wall time', 'CPU scheduling versus I/O wait',
                     'Leak or handle ownership', 'Full GT06 acceptance'],
        'next_hypothesis': 'Bounded Python-only differential: retained-history verifier with and without concurrent pending HTTP polling.',
    }
    with (OUT/'failure-analysis.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({key: summary[key] for key in ['completed_batches','failure_code','partial_command_count',
          'lookup_attempts','lookup_transport_failures','lookup_window_ms','source_pins_checked','source_drift']}))


if __name__ == '__main__':
    main()
