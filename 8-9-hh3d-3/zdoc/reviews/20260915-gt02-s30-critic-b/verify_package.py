"""Independent read-only S30 source/artifact verifier. No engine or suite launch."""
from __future__ import annotations
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT.parent
PACKAGE = ROOT/'zdoc/reviews/20260915-gt02-s30-01'
EXPECTED = '60799065f406fbb3b13d2dc0df093477210927f86e84b54175dfd36351521a1a'

def digest(raw): return hashlib.sha256(raw).hexdigest()
def pairs(items):
    value={}
    for key,item in items:
        assert key not in value,'DUPLICATE_JSON_KEY'
        value[key]=item
    return value
def read(path): return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs)
def check_path(name):
    assert name and not name.startswith('/') and '\\' not in name
    assert all(part not in ('','.','..') for part in name.split('/'))

manifest=read(PACKAGE/'source-closure.json')
files=manifest['files']
assert len(files)==62
closure=digest(''.join(sorted(f'8-9-hh3d-3/studio/{name}\0{sha}\n' for name,sha in files.items())).encode())
assert closure==manifest['source_closure_sha256']==EXPECTED
source={}
for name,sha in files.items():
    check_path(name)
    path=ROOT/'studio'/name
    assert not path.is_symlink() and not getattr(path.lstat(),'st_file_attributes',0)&0x400
    source[name]=path.read_bytes()
    assert digest(source[name])==sha,name
    blob=hashlib.sha1(b'blob '+str(len(source[name])).encode()+b'\0'+source[name]).hexdigest()
    converted=subprocess.run(['git','hash-object','--stdin','--path=8-9-hh3d-3/studio/'+name],
        input=source[name],cwd=REPO,capture_output=True,check=True,timeout=5)
    assert converted.stdout.decode().strip()==blob,('GIT_WOULD_CHANGE_BYTES',name)
expected_inventory={'toolchain.lock.json'}
for folder in ('protocol','host/core','tests/protocol','tests/bootstrap','build/bootstrap','fixtures'):
    for path in (ROOT/'studio'/folder).rglob('*'):
        if path.is_file() and not set(path.relative_to(ROOT/'studio').parts)&{'__pycache__','.godot','.local','evidence'}:
            expected_inventory.add(path.relative_to(ROOT/'studio').as_posix())
assert expected_inventory==set(files),'SOURCE_INVENTORY_MISMATCH'

candidate=read(PACKAGE/'candidate.json')
assert candidate['source_closure_sha256']==EXPECTED and candidate['source_unchanged'] is True
assert candidate['run_id']=='GT02-S30-20260915-01' and candidate['command_id']=='cmd.GT02-S30-20260915-01'
assert candidate['status']=='CANDIDATE' and candidate['acceptance']=='NOT_REVIEWED'
assert candidate['acceptance_ready'] is False and candidate['seed']==8785
started=datetime.fromisoformat(candidate['started_utc'])
ended=datetime.fromisoformat(candidate['completed_utc'])
assert started<ended
for name,sha in candidate['artifacts'].items():
    check_path(name)
    assert digest((PACKAGE/name).read_bytes())==sha,name
inventory={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file()}
assert inventory==set(candidate['artifacts'])|{'candidate.json'},'ARTIFACT_INVENTORY_MISMATCH'
lanes=[]
for lane in candidate['lanes']:
    suite=lane['suite']; host=lane['host']; summary=lane['summary']
    real=read(PACKAGE/host['host'])
    assert real['exit_code']==host['exit_code']==host['wrapper_exit_code']==0
    assert real['target_pid']==host['target_pid'] and real['target_pid']>0 and host['wrapper_pid']>0
    assert started<=datetime.fromisoformat(real['started_at'])<=ended
    assert host['tree_verified'] is True and host['timed_out'] is False
    assert host['ownership']=='gated_job_kill_on_close'
    stdout=(PACKAGE/host['stdout']).read_text(encoding='utf-8')
    stderr=(PACKAGE/host['stderr']).read_text(encoding='utf-8')
    marker=[line.removeprefix('HH_GT02_TEST_RESULT ') for line in stdout.split('\n') if line.startswith('HH_GT02_TEST_RESULT ')]
    assert len(marker)==1 and json.loads(marker[0])==summary
    ids=set(summary['test_ids'])
    assert summary['failures']==summary['errors']==0 and len(ids)==len(summary['test_ids'])==summary['tests_run']
    assert re.search(r'Ran '+str(summary['tests_run'])+r' tests in [0-9.]+s',stderr)
    assert re.search(r'\nOK(?: \(skipped=\d+\))?\s*$',stderr)
    assert '\nFAIL:' not in stderr and '\nERROR:' not in stderr and 'Traceback (most recent call last)' not in stderr
    declared=set()
    for path in (ROOT/'studio/tests'/suite).glob('test_*.py'):
        tree=ast.parse(path.read_text(encoding='utf-8'))
        for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
            for method in cls.body:
                if isinstance(method,ast.FunctionDef) and method.name.startswith('test_'):
                    declared.add(path.stem+'.'+cls.name+'.'+method.name)
    assert declared==ids,('TEST_INVENTORY_MISMATCH',suite,declared^ids)
    skipped={x['id'] for x in summary['skipped']}
    assert len(skipped)==summary['skips'] and skipped<=ids
    assert all(not any(key in item for key in ('GoldenVectorTests','JournalCasTests','JournalDurabilityTests')) for item in skipped)
    for item in ids-skipped:
        module,cls,method=item.split('.')
        assert f'{method} ({module}.{cls}.{method})' in stderr or f'{method} ({module}.{cls})' in stderr,item
    lanes.append({'suite':suite,'tests':summary['tests_run'],'passed':summary['tests_run']-summary['skips'],
                  'skipped':summary['skipped'],'target_pid':real['target_pid'],'host_exit':real['exit_code'],'wrapper_exit':host['wrapper_exit_code']})

godot=read(next((PACKAGE/'golden').glob('*godot*.json')))
node=read(next((PACKAGE/'golden').glob('*node*.json')))
assert godot['host_exit']==node['host_exit']==0 and not godot['stderr'].strip() and not node['stderr'].strip()
assert godot['leftover_before']==godot['leftover_after']==[] and godot['source_unchanged'] is True
assert godot['scope']==node['scope']=='serializer_conformance_only' and godot['raw_wire_parser_conformance'] is False
assert godot['test_source_sha256']==node['test_source_sha256']==files['tests/protocol/test_golden_vectors.py']
pin=read(ROOT/'studio/toolchain.lock.json')['godot']
assert godot['console_sha256']==pin['console_sha256'] and godot['gui_sha256']==pin['gui_sha256']
markers=[line.removeprefix('HH_GT02_JCS ') for line in godot['stdout'].split('\n') if line.startswith('HH_GT02_JCS ')]
assert len(markers)==1
result=json.loads(markers[0],object_pairs_hook=pairs)
assert result['rows']==node['rows'] and len(node['rows'])==2396
assert len({row['id'] for row in node['rows']})==2396
for row in node['rows']:
    raw=row['canonical'].encode('utf-8')
    assert row['ok'] is True and raw.hex()==row['utf8_hex'] and 'sha256:'+digest(raw)==row['sha256']
sys.path[:0]=[str(ROOT),str(ROOT/'studio/tests/protocol')]
from test_golden_vectors import GoldenVectorTests
GoldenVectorTests.setUpClass()  # Pure expected-vector construction; no consumer launch.
assert result['rows']==GoldenVectorTests.expected
rejects={'nan':'INVALID_NUMBER','infinity':'INVALID_NUMBER','negative_infinity':'INVALID_NUMBER',
    'unsafe_integer':'INTEGER_REQUIRES_DECIMAL_STRING','surrogate':'INVALID_UNICODE','invalid_scalar':'INVALID_UNICODE',
    'invalid_key':'INVALID_KEY','invalid_type':'INVALID_TYPE','long_string':'STRING_LIMIT'}
assert result['rejected']=={key:{'ok':False,'error':value} for key,value in rejects.items()}
diagnostics='\n'.join(line for line in godot['stdout'].split('\n') if not line.startswith('HH_GT02_JCS '))+godot['stderr']
assert not re.search(r'\b(warning|error|leaked)\b',diagnostics,re.I)
assert all((ROOT/'studio'/name).read_bytes()==raw for name,raw in source.items())
report={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'reviewer':'independent-critic-b',
    'source_closure_sha256':closure,'source_files':len(files),'git_byte_identity':True,
    'candidate_sha256':digest((PACKAGE/'candidate.json').read_bytes()),'artifacts':len(candidate['artifacts']),
    'lanes':lanes,'canonical_rows':2396,'godot_negative_cases':9,'source_unchanged':True,'verification':'PASS'}
print(json.dumps(report,indent=2))
if __name__=='__main__':
    (Path(__file__).with_name('package-verification.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
