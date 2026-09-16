"""Read-only artifact timing audit; mtimes are not per-phase runtime telemetry."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re

REVIEWS = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument('--quiet', action='store_true')
args = parser.parse_args()
FAILED = REVIEWS / ('20260917-gt03-s54-recovery-cuts-resume-02/scene-cas' if args.quiet
                    else '20260917-gt03-s54-recovery-cuts-resume-01/scene-cas')
PRIOR = REVIEWS / '20260917-gt03-s54-recovery-publication-01'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def record(path):
    return {'path': path.relative_to(REVIEWS).as_posix(), 'sha256': sha(path),
        'mtime_ns': path.stat().st_mtime_ns,
        'mtime_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()}

def artifact_delta(left, right):
    return round((right.stat().st_mtime_ns - left.stat().st_mtime_ns) / 1e9, 3)

request_path = FAILED / 'recovery-request.json'
request = json.loads(request_path.read_bytes())
editor = next((FAILED / 'recovery/recovery-editor').iterdir())
timing_files = [request_path, FAILED / 'before-reconcile-snapshot.json',
    editor / 'process-start.json', editor / 'hello.json', FAILED / 'response.json',
    editor / 'close.json', editor / 'process-exit.json', FAILED / 'result.json',
    FAILED / 'recovery-cut-host.json']
events = json.loads((PRIOR / 'recovery-events.json').read_bytes())
prior_events = [e for e in events if e.get('schema') == 'hh-godot-publication-recovery-1'
                and e.get('kind') in ('ADMITTED', 'READBACK', 'TERMINAL')]
logs = [p for p in FAILED.rglob('*.txt') if p.name in ('stdout.txt', 'stderr.txt')]
report = {
    'candidate_only': True, 'gt03_acceptance': False,
    'measurement_scope': 'read-only artifact mtimes plus existing recorded event timestamps; no new engine or recovery open',
    'failed_runtime_closure': 'c354c978062dc9987f98eae28d5af158bed5256ba25126457be44d43a720150f',
    'failure': 'GODOT_DEADLINE_EXPIRED before commit phase; HTTP UNKNOWN and public_ack=false',
    'quiet_retry': args.quiet,
    'deadline_utc': datetime.fromtimestamp(request['deadline_ms'] / 1000, timezone.utc).isoformat(),
    'file_records': [record(p) for p in timing_files],
    'artifact_deltas_seconds': {
        'request_written_to_editor_process_start': artifact_delta(request_path, editor / 'process-start.json'),
        'editor_process_start_to_hello': artifact_delta(editor / 'process-start.json', editor / 'hello.json'),
        'request_written_to_unknown_response': artifact_delta(request_path, FAILED / 'response.json'),
        'hello_before_request_deadline': round(request['deadline_ms'] / 1000 - (editor / 'hello.json').stat().st_mtime, 3),
    },
    'native_logs': [{'artifact': record(p), 'clean': re.search(rb'(?i)\b(warning|error|fatal|traceback)\b', p.read_bytes()) is None}
                    for p in logs],
    'editor_cleanup': json.loads((editor / 'close.json').read_bytes()),
    'case_raw_exit': json.loads((FAILED / 'recovery-cut-host.json').read_bytes()),
    'earlier_success_different_closure': {
        'package': PRIOR.name,
        'source_closure_sha256': json.loads((PRIOR / 'source-closure.json').read_bytes())['source_closure_sha256'],
        'events': [{'kind': e['kind'], 'observed_ms': e['observed_ms'],
            'admission': e.get('admission'), 'readback_started_ms': e.get('observation', {}).get('started_ms'),
            'readback_observed_ms': e.get('observation', {}).get('observed_ms')} for e in prior_events],
    },
    'interpretation': [
        ('Coordinator ended native storage/Registry unit lanes and transferred the exclusive native slot before this quiet retry; it still exhausted the unchanged deadline.' if args.quiet else
         'Root native storage/Registry unit lanes launched at 21:57:43 UTC, inside this recovery attempt, according to their invocation.json. This demonstrates temporal overlap, not causation.'),
        'Most of the request budget elapsed before editor process start; the editor hello left only a few seconds for protected readback and terminal work.',
        'The earlier successful recovery is a different closure and shorter original journal, so it cannot establish a timing baseline for this scene-CAS route.',
        ('The quiet failure shows the route cannot finish within its current budget even without the concurrent unit load. The registered selected storage is unchanged but includes the previous failed recovery suffix. Runtime-owner consolidation/profiling is required; the 30-second contract remains unchanged.' if args.quiet else
         'A later authorized quiet retry or profiling is needed to separate fsync contention from journal-length/algorithm cost. The 30-second contract remains unchanged.'),
    ],
}
if args.quiet:
    suffix = json.loads((FAILED / 'failure-recovery-events.json').read_bytes())
    report['failed_recovery_events'] = [{'kind': e['kind'], 'observed_ms': e['observed_ms'],
        'admission': e.get('admission'), 'reason': e.get('reason')}
        for e in suffix if e.get('schema') == 'hh-godot-publication-recovery-1']
    snapshot = json.loads((FAILED / 'failure-journal-snapshot.json').read_bytes())
    report['final_attempt_phases'] = [a['phase'] for a in snapshot['recovery']['attempts']]
(OUT / ('quiet-timing-report.json' if args.quiet else 'timing-report.json')).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report['artifact_deltas_seconds'], indent=2))
