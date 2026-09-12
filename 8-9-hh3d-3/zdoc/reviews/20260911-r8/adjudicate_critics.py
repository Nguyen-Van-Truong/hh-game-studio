"""Read terminal critics and verify frozen inputs, never accept the entire WP."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = []
    for role in ['critic-a', 'critic-b']:
        batch = json.loads((HERE/(role+'-batch.local.json')).read_text(encoding='utf-8-sig'))
        job = batch['jobs'][0]
        attempt, work = Path(job['attempt_dir']), Path(job['workspace'])
        meta = json.loads((attempt/'runner-meta.json').read_text(encoding='utf-8-sig'))
        row = {'role':role, 'session':job['session'], 'model':batch['model'], 'effort':batch['reasoning_effort'],
               'terminal':meta, 'status':'NO_VERDICT', 'GT01_ACCEPTED':False, 'events_sha256':sha(attempt/'events.jsonl')}
        manifest = json.loads((work/'input-manifest.json').read_text(encoding='utf-8'))
        row['frozen_inputs_unchanged'] = all(sha(work/p['path']) == p['sha256'] for p in manifest)
        events = [json.loads(line) for line in (attempt/'events.jsonl').read_text(encoding='utf-8-sig').splitlines() if line]
        row['files_read'] = [e.get('rawInput',{}).get('target_file') for e in events if e.get('type') == 'tool_call' and e.get('toolName') == 'read_file']
        row['files_read'] = [str(p).replace('\\','/').removeprefix(work.as_posix()+'/') for p in row['files_read']]
        if meta['exit_code'] == 0 and not meta['timed_out'] and not meta['launcher_error'] and row['frozen_inputs_unchanged']:
            raw = (work/'response.txt').read_text(encoding='utf-8')
            match = re.fullmatch(r'\s*```json\s*\n([\s\S]*?)\n```\s*', raw)
            data = json.loads(match.group(1) if match else raw)
            runner = sha(work/'studio/build/bootstrap/run_fixture.py')
            test = sha(work/'studio/tests/bootstrap/test_version_probe.py')
            if data.get('source_sha256') == runner and data.get('test_sha256') == test and data.get('GT01_ACCEPTED') is False:
                row.update(status='SMALL_CHANGE_'+data['change_verdict'], verdict=data, response_sha256=sha(work/'response.txt'))
        else:
            errors = [e.get('message','') for e in events if e.get('type') == 'error']
            row['provider_reason'] = '403 SAFETY_CHECK_TYPE_DATA_LEAKAGE' if any('SAFETY_CHECK_TYPE_DATA_LEAKAGE' in e for e in errors) else 'No valid terminal verdict'
        rows.append(row)
    report = {'scope':'_observed_version change only; not full GT01', 'critics':rows,
              'two_change_passes':sum(r['status']=='SMALL_CHANGE_PASS' for r in rows)==2, 'GT01_ACCEPTED':False}
    (HERE/'critic-adjudication.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
