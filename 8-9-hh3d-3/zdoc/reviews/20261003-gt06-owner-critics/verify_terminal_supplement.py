"""Read-only verification of Formal25's recovered original Scheduler receipt.

The original final package remains immutable. This verifier checks an additive
review manifest, exact original tool-record slices, and task/request/time joins.
It never queries Scheduler, starts an engine, or writes a receipt.
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone
import hashlib
import json
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'studio/.local/reviews/gt06-f25-final-review-20261003-01/manifest.json'
BASE_SHA = 'fb5770aaaa30aeec4c481947a185c28e2f0bb4a10dae34c05f9b7610215100e0'
RAW = ROOT/'studio/.local/reviews/gt06-f25-terminal-supplement-20261003-01'
FINAL = ROOT/'studio/.local/reviews/gt06-f25-final-review-20261003-02/manifest.json'
SUPERVISOR = ROOT/'studio/.local/reviews/gt06-o4-formal-25-supervisor'

def need(value, code):
    if not value:
        raise ValueError(code)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))

def decoded_result(record):
    payload = record['payload']
    need(record['type'] == 'response_item' and payload['type'] == 'custom_tool_call_output', 'RESULT_RECORD_KIND')
    texts = [row['text'] for row in payload['output'] if row.get('type') == 'input_text']
    candidates = []
    for text in texts:
        try:
            candidate = json.loads(text)
        except json.JSONDecodeError:
            continue
        if type(candidate) is dict and 'exit_code' in candidate and 'output' in candidate:
            candidates.append(candidate)
    need(len(candidates) == 1, 'RESULT_COUNT')
    result = candidates[0]
    need(type(result['exit_code']) is int and result['exit_code'] == 0, 'STATUS_QUERY_EXIT')
    status = json.loads(result['output'])
    return status

def validate(call, result, request, started, task_start, deleted, request_sha):
    payload = call['payload']
    need(call['type'] == 'response_item' and payload['type'] == 'custom_tool_call'
         and payload['name'] == 'exec', 'CALL_RECORD_KIND')
    need(payload['call_id'] == result['payload']['call_id'], 'CALL_ID_BINDING')
    command = payload['input']
    need("$script='8-9-hh3d-3/studio/tests/replay/campaign_task.ps1'" in command
         and '-Command status -CampaignId gt06-o4-formal-25 -Mode campaign' in command,
         'STATUS_COMMAND_BINDING')
    status = decoded_result(result)
    need(status.get('schema') == 'HH-GT06-TASK-STATUS-1', 'STATUS_SCHEMA')
    campaign = 'gt06-o4-formal-25'
    task = '\\HHStudio.GT06.' + campaign
    need(status['campaign_id'] == request['campaign_id'] == started['campaign_id']
         == task_start['campaign_id'] == deleted['campaign_id'] == campaign, 'CAMPAIGN_BINDING')
    need(status['task_path'] == task_start['task_path'] == deleted['task_path'] == task,
         'TASK_BINDING')
    need(status['mode'] == request['mode'] == task_start['mode'] == 'campaign', 'MODE_BINDING')
    need(type(status['state']) is int and status['state'] == 3
         and type(status['last_task_result']) is int and status['last_task_result'] == 0
         and status['instances'] == [], 'TERMINAL_RESULT')
    need(status['launch_number'] == task_start['launch_number'] == deleted['launch_number'] == 1,
         'LAUNCH_BINDING')
    need(Path(status['output_directory']) == SUPERVISOR
         and status['output_directory'] == task_start['output_directory'], 'OUTPUT_BINDING')
    need(started['pid'] == task_start['scheduler_engine_pid'] == 51568
         and started['request_sha256'] == task_start['request_sha256'] == request_sha, 'START_BINDING')
    need(task_start['task_definition_sha256'] == deleted['task_definition_sha256'], 'DEFINITION_BINDING')
    begin = stamp(started['started_at'])
    need(begin < stamp(call['timestamp']) <= stamp(result['timestamp']) < stamp(deleted['deleted_utc']),
         'TERMINAL_TIME_BINDING')
    # Scheduler's recorded naive time is local Asia/Saigon; never treat as UTC.
    last_run = datetime.fromisoformat(status['last_run_time']).replace(tzinfo=timezone(timedelta(hours=7)))
    need(abs((last_run - stamp(task_start['requested_utc'])).total_seconds()) < 2,
         'LAST_RUN_BINDING')
    return status

def verify():
    manifest = read(FINAL)
    need(manifest['schema'] == 'hh-gt06-additive-review-1'
         and manifest['base_manifest_sha256'] == sha(BASE) == BASE_SHA, 'BASE_BINDING')
    files = manifest['files']
    required = {p.relative_to(ROOT).as_posix() for p in (
        Path(__file__).resolve(), Path(__file__).with_name('terminal-supplement.md'),
        Path(__file__).with_name('test_terminal_supplement.py'),
        Path(__file__).with_name('critic-astra.md'), Path(__file__).with_name('critic-sol.md'),
        Path(__file__).with_name('dispatch.md'),
        RAW/'tool-call.json', RAW/'tool-result.json', RAW/'provenance.json', RAW/'terminal-status.json',
        RAW/'test-command.json', RAW/'test-stdout.txt', RAW/'test-stderr.txt',
        SUPERVISOR/'request.json', SUPERVISOR/'start.json', SUPERVISOR/'task-start.json',
        SUPERVISOR/'task-deleted.json', SUPERVISOR/'task-definition.xml',
        SUPERVISOR/'task-definition.expected.xml')}
    need(set(files) == required, 'SUPPLEMENT_MEMBERSHIP')
    for name, digest in files.items():
        path = ROOT/name
        need(path.is_relative_to(ROOT) and '..' not in Path(name).parts and sha(path) == digest,
             'SUPPLEMENT_BYTES')
    archive = manifest['archive']
    archive_path = FINAL.parent/'supplement.zip'
    need(archive['sha256'] == sha(archive_path) and set(archive['members']) == required,
         'ARCHIVE_BINDING')
    with zipfile.ZipFile(archive_path) as bundle:
        need(set(bundle.namelist()) == set(archive['members'].values())
             and len(bundle.namelist()) == len(required) and bundle.testzip() is None,
             'ARCHIVE_MEMBERSHIP')
        for name, member in archive['members'].items():
            need(len(member) <= 180 and hashlib.sha256(bundle.read(member)).hexdigest() == files[name],
                 'ARCHIVE_BYTES')
    need(sha(FINAL) == FINAL.with_suffix('.sha256').read_text().strip(), 'FINAL_HASH')
    provenance = read(RAW/'provenance.json')
    need(provenance['schema'] == 'hh-original-tool-record-slices-1', 'PROVENANCE_SCHEMA')
    need([row['role'] for row in provenance['records']] == ['tool-call', 'tool-result'], 'PROVENANCE_ROLES')
    with Path(provenance['source_log']).open('rb') as source:
        for row in provenance['records']:
            raw = (RAW/(row['role']+'.json')).read_bytes()
            source.seek(row['offset'])
            need(len(raw) == row['length'] and hashlib.sha256(raw).hexdigest() == row['sha256']
                 and source.read(row['length']) == raw, 'ORIGINAL_SLICE_BINDING')
    status = validate(read(RAW/'tool-call.json'), read(RAW/'tool-result.json'),
                      read(SUPERVISOR/'request.json'), read(SUPERVISOR/'start.json'),
                      read(SUPERVISOR/'task-start.json'), read(SUPERVISOR/'task-deleted.json'),
                      sha(SUPERVISOR/'request.json'))
    derived = read(RAW/'terminal-status.json')
    need(derived['scheduler'] == status and derived['command_exit'] == 0
         and derived['source_records'] == provenance['records'], 'DERIVED_RECEIPT_BINDING')
    definition = read(SUPERVISOR/'task-start.json')['task_definition_sha256']
    need(definition == sha(SUPERVISOR/'task-definition.xml'), 'DEFINITION_BYTES')
    test = read(RAW/'test-command.json')
    need(test['actual_exit'] == 0 and test['stdout_sha256'] == sha(RAW/'test-stdout.txt')
         and test['stderr_sha256'] == sha(RAW/'test-stderr.txt'), 'TEST_RECEIPT')
    base = subprocess.run([sys.executable, '-B', str(ROOT/'zdoc/reviews/20261003-gt06-functional-refresh/build_review.py'),
                           '--verify'], capture_output=True, text=True)
    need(base.returncode == 0, 'BASE_VERIFICATION: ' + base.stderr[-1000:])
    return {'manifest_sha256': sha(FINAL), 'base_manifest_sha256': BASE_SHA,
            'scheduler_task': status['task_path'], 'scheduler_result': status['last_task_result'],
            'original_tool_call': read(RAW/'tool-call.json')['payload']['call_id'],
            'base_verifier_actual_exit': base.returncode, 'formal_acceptance': False}

if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
