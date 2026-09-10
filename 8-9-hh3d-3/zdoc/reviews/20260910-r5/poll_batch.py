"""Bounded local status inspection, never reads streaming model output."""
from pathlib import Path
import argparse
import datetime
import json

parser = argparse.ArgumentParser()
parser.add_argument('--batch', type=Path, default=Path(__file__).with_name('active-batch.local.json'))
args = parser.parse_args()
record = json.loads(args.batch.read_text(encoding='utf-8-sig'))
if record['polls_used'] >= record['poll_budget']:
    raise SystemExit('Poll budget used. Completion remains in per-attempt metadata/Windows notification; resume on owner message.')
record['polls_used'] += 1
record['last_polled_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
args.batch.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
print('POLL', record['polls_used'], '/', record['poll_budget'])
for job in record['jobs']:
    attempt = Path(job['attempt_dir'])
    meta_path = attempt / 'runner-meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8-sig')) if meta_path.exists() else None
    native_path = attempt / 'native.json'
    native = json.loads(native_path.read_text(encoding='utf-8-sig')) if native_path.exists() else None
    work = Path(job['workspace'])
    reports = {name: (work / name).exists() for name in ['REPORT.md', 'evidence.json']}
    print(json.dumps({'role': job['role'], 'terminal': meta, 'native': native, 'reports': reports,
                      'notice_recorded': (attempt / 'notice-result.json').exists(),
                      'supervisor_stderr': (attempt / 'supervisor.stderr.txt').read_text(encoding='utf-8-sig')[:1000]}, ensure_ascii=True))
