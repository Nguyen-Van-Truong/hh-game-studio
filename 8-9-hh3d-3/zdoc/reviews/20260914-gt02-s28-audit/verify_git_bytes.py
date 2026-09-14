"""Rebuild the candidate from index or HEAD blobs, then verify its evidence.

Only an integrity/reproduction check, not a test rerun or independent review.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[4]
PREFIX = '8-9-hh3d-3/'
PACK = 'zdoc/reviews/20260914-gt02-s28-03/'
AUDIT = 'zdoc/reviews/20260914-gt02-s28-audit/'
ARCHIVE = 'zdoc/reviews/20260914-plan-history-s27/tools-plan-s27.txt'
ARCHIVE_HASH = 'e66c5e2f9837623f2388c7a96e54b7c0623deed243a4981934b6990a26daa4f0'


def main():
    source = sys.argv[1] if len(sys.argv) == 2 else 'index'
    if source not in ('index', 'HEAD'):
        raise SystemExit('usage: verify_git_bytes.py [index|HEAD]')

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=REPO, timeout=15)

    # Bind HEAD once; the index is read-only throughout this solo verification.
    commit = git('rev-parse', 'HEAD').decode('ascii').strip()
    revision = '' if source == 'index' else commit

    def blob(relative):
        parts = relative.split('/')
        if not relative or any(p in ('', '.', '..') for p in parts) or '\\' in relative or ':' in relative:
            raise ValueError('UNSAFE_MANIFEST_PATH')
        return git('show', revision + ':' + PREFIX + relative)

    candidate_bytes = blob(PACK + 'candidate.json')
    candidate = json.loads(candidate_bytes)
    manifest = json.loads(blob(PACK + 'source-closure.json'))
    expected = {'studio/' + name: digest for name, digest in manifest['files'].items()}
    expected.update({PACK + name: digest for name, digest in candidate['artifacts'].items()})
    expected[PACK + 'candidate.json'] = hashlib.sha256(candidate_bytes).hexdigest()
    expected[ARCHIVE] = ARCHIVE_HASH
    files = {}
    for relative, digest in expected.items():
        data = blob(relative)
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('GIT_BLOB_HASH_MISMATCH: ' + relative)
        if (REPO / PREFIX / relative).read_bytes() != data:
            raise ValueError('WORKTREE_BLOB_BYTES_DIFFER: ' + relative)
        files[relative] = data

    if source == 'index':
        names = git('ls-files', '-z', '--', PREFIX + 'studio/').decode('utf-8').split('\0')
    else:
        names = git('ls-tree', '-r', '--name-only', '-z', commit, '--', PREFIX + 'studio/').decode('utf-8').split('\0')
    closure_roots = ('protocol/', 'host/core/', 'tests/protocol/', 'tests/bootstrap/', 'build/bootstrap/', 'fixtures/')
    selected = {name[len(PREFIX + 'studio/'):] for name in names if name}
    selected = {name for name in selected if name == 'toolchain.lock.json' or name.startswith(closure_roots)}
    if selected != set(manifest['files']):
        raise ValueError('GIT_SOURCE_CLOSURE_MEMBERSHIP_MISMATCH')

    verifier = AUDIT + 'verify_evidence.py'
    files[verifier] = blob(verifier)
    # Materialize exact Git blobs: checkout filters, caches and the local source
    # tree cannot mask a mismatch. Cleanup is confined to this owned directory.
    with tempfile.TemporaryDirectory(prefix='hh-gt02-git-proof-') as temporary:
        root = Path(temporary) / '8-9-hh3d-3'
        for relative, data in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        run = subprocess.run([sys.executable, '-I', str(root / verifier)],
                             cwd=root, capture_output=True, text=True, timeout=30)
        if run.returncode != 0 or run.stderr:
            raise RuntimeError('GIT_RECONSTRUCTION_VERIFY_FAILED: ' + str(run.returncode))
        check = json.loads(run.stdout)
        if check['status'] != 'COORDINATOR_LOGIC_VERIFIED':
            raise ValueError('GIT_RECONSTRUCTION_MISSING_COMPLETION')
        verified = json.loads((root / AUDIT / 'verification.json').read_bytes())
    result = {
        'schema': 'hh-gt02-git-bytes-verification-v1',
        'status': 'GIT_BYTES_VERIFIED',
        'verified_utc': datetime.now(timezone.utc).isoformat(),
        'git_source': source,
        'head_at_verification': commit,
        'source_closure_sha256': candidate['source_closure_sha256'],
        'source_files': len(manifest['files']),
        'artifact_files': len(candidate['artifacts']),
        'candidate_sha256': expected[PACK + 'candidate.json'],
        'historical_plan_sha256': ARCHIVE_HASH,
        'verifier_sha256': hashlib.sha256(files[verifier]).hexdigest(),
        'reconstructed_verification_sha256': hashlib.sha256(json.dumps(verified, sort_keys=True).encode()).hexdigest(),
        'isolated_python_exit': run.returncode,
        'counts': verified['counts'],
        'scope': 'Git byte integrity and stored evidence verification; no engine or suite rerun',
        'formal_acceptance': False,
        'independent_critic_signatures': 0,
    }
    output = Path(__file__).with_name('git-byte-verification-' + source.lower() + '.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
