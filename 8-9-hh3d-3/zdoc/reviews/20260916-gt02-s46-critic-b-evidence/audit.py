"""Independent source/artifact inventory plus reviewed outcome verifier.

No source edits, no plan tick, no writes into coordinator evidence.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[2]
STUDIO = PRODUCT/'studio'
REVIEWS = PRODUCT/'zdoc/reviews'
PACK = REVIEWS/'20260916-gt02-s46-01'
CLOSURE = 'f28056d8ff705a60d48a54f9dee80f16554494fa976bd0bfabee84bb51fecbbf'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            assert key not in result, ('duplicate key', key)
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique)

def digest_map(files):
    rows = []
    for relative, digest in sorted(files.items()):
        assert not relative.startswith('/') and '\\' not in relative
        assert not set(relative.split('/')) & {'', '.', '..'}
        assert re.fullmatch('[0-9a-f]{64}', digest)
        rows.append('8-9-hh3d-3/studio/'+relative+'\0'+digest+'\n')
    return hashlib.sha256(''.join(rows).encode()).hexdigest()

candidate = read(PACK/'candidate.json')
frozen = read(PACK/'source-closure.json')
files = frozen['files']
assert len(files) == 106 and digest_map(files) == CLOSURE
inventory = {'toolchain.lock.json'}
for directory in ('protocol','host/core','tests/protocol','tests/bootstrap','build/bootstrap','fixtures'):
    inventory.update(p.relative_to(STUDIO).as_posix() for p in (STUDIO/directory).rglob('*')
        if p.is_file() and not set(p.relative_to(STUDIO).parts) & {'__pycache__','.godot','.local','evidence'})
assert inventory == set(files)
for relative, digest in files.items():
    target = STUDIO/relative
    assert not target.is_symlink() and not getattr(target.stat(), 'st_file_attributes', 0) & 0x400
    assert sha(target) == digest
artifact_hashes = {p.relative_to(PACK).as_posix():sha(p) for p in PACK.rglob('*')
                   if p.is_file() and p.name != 'candidate.json'}
assert artifact_hashes == candidate['artifacts'] and len(artifact_hashes) == 9

lanes = []
for lane in candidate['lanes']:
    host = lane['host']
    raw_host = read(PACK/host['host'])
    assert raw_host['target_pid'] == host['target_pid']
    assert raw_host['exit_code'] == host['exit_code'] == host['wrapper_exit_code'] == 0
    assert host['tree_verified'] is True and host['timed_out'] is False
    raw_stdout = (PACK/host['stdout']).read_text(encoding='utf-8')
    raw_stderr = (PACK/host['stderr']).read_text(encoding='utf-8')
    rows = [json.loads(line[len('HH_GT02_TEST_RESULT '):]) for line in raw_stdout.split('\n')
            if line.startswith('HH_GT02_TEST_RESULT ')]
    assert rows == [lane['summary']]
    summary = rows[0]
    assert summary['tests_run'] == len(set(summary['test_ids'])) == len(summary['test_ids'])
    assert summary['failures'] == summary['errors'] == 0
    assert re.search(r'Ran '+str(summary['tests_run'])+r' tests in [0-9.]+s',raw_stderr)
    assert '\nFAILED ' not in raw_stderr and '\nTraceback ' not in raw_stderr
    assert re.search(r'\nOK(?: \(skipped='+str(summary['skips'])+r'\))?\s*$',raw_stderr)
    lanes.append({'suite':lane['suite'],'run':summary['tests_run'],'skips':summary['skips']})

native = []
for name, label in (
    ('20260916-gt02-s46-native','managed-native'),
    ('20260916-gt02-s46-boundary','native'),
    ('20260916-gt02-s46-registry-native','registry-native'),
):
    directory = REVIEWS/name/'run-01'
    capture = read(directory/'capture.json')
    host = capture['host']
    raw_host = read(directory/(label+'-host.json'))
    record = read(directory/(label+'-stdout.txt'))
    binding = record['runtime_closure']
    assert binding['files'] == files and digest_map(binding['files']) == CLOSURE
    assert binding['source_closure_sha256'] == CLOSURE
    assert raw_host['exit_code'] == host['exit_code'] == host['wrapper_exit_code'] == 0
    assert raw_host['target_pid'] == host['target_pid']
    assert host['tree_verified'] and not host['timed_out']
    assert capture['job_samples'][-1]['active'] == 0 and capture['job_samples'][-1]['pids'] == []
    assert (directory/(label+'-stderr.txt')).read_bytes() == b''
    native.append({'name':name,'same_map':True,'files':len(files),
        'capture_sha256':sha(directory/'capture.json'),'stdout_sha256':sha(directory/(label+'-stdout.txt')),
        'host_sha256':sha(directory/(label+'-host.json'))})

# Reviewed source checks native reply hex independently, actual FileIDs, retry
# identity, compiler/child/Job exits, private denied+positive-control outcomes,
# diagnostic hashes, 2396 golden rows and source-map coverage.
verifier = REVIEWS/'20260916-gt02-s46-audit/verify_evidence.py'
spec = importlib.util.spec_from_file_location('critic_readonly_coordinator_verifier',verifier)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
coordinator = module.verify()  # function has no output mutation; __main__ is not used
index_proof_path = REVIEWS/'20260916-gt02-s46-audit/git-byte-verification-index.json'
index_proof = read(index_proof_path)
assert index_proof['source_closure_sha256'] == CLOSURE and index_proof['source_files'] == 106
git_paths = ['studio/'+relative for relative in files] + index_proof['evidence_files']
assert len(index_proof['evidence_files']) == 138
batch = subprocess.run(['git','cat-file','--batch'], cwd=PRODUCT,
    input=''.join(':8-9-hh3d-3/'+relative+'\n' for relative in git_paths).encode(),
    capture_output=True, timeout=20, check=True).stdout
offset = 0
for relative in git_paths:
    end = batch.index(b'\n', offset)
    header = batch[offset:end].split()
    assert len(header) == 3 and header[1] == b'blob'
    size = int(header[2])
    offset = end+1
    assert batch[offset:offset+size] == (PRODUCT/relative).read_bytes(), relative
    offset += size
    assert batch[offset:offset+1] == b'\n'
    offset += 1
assert offset == len(batch)
record = {'schema':'hh-s46-critic-b-integrity-v1','timestamp_utc':datetime.now(timezone.utc).isoformat(),
    'status':'PASS','source_closure_sha256':CLOSURE,'source_files':len(files),
    'candidate_sha256':sha(PACK/'candidate.json'),'source_manifest_sha256':sha(PACK/'source-closure.json'),
    'independent_exact_inventory_and_hashes':True,'artifacts':artifact_hashes,'lanes':lanes,
    'native':native,'reviewed_verifier_sha256':sha(verifier),'coordinator_verification':coordinator,
    'independent_git_index_bytes':{'source_files':106,'evidence_files':138,'proof_sha256':sha(index_proof_path)}}
(HERE/'integrity.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','source_files':len(files),'candidate_artifacts':len(artifact_hashes),
    'native_exact_maps':len(native),'lanes':lanes,'source_closure_sha256':CLOSURE}))
