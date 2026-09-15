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
PACK = 'zdoc/reviews/20260916-gt02-s36-01/'
AUDIT = 'zdoc/reviews/20260916-gt02-s36-audit/'
NATIVE = 'zdoc/reviews/20260916-gt02-s35-native/'
NATIVE_MANIFEST_HASH = '3f5a5d5b26b199897161048a8c70bf4a98cef46595b00e3d08d5c33f8b903363'
ARCHIVE = 'zdoc/reviews/20260915-plan-history-s29/tools-plan-s29.txt'
ARCHIVE_HASH = 'f299a73fe9f699a0a7943a6b9ef74bbd7bcc3821a66a32075588d39a482dc189'


def main():
    source = sys.argv[1] if len(sys.argv) == 2 else 'index'
    if source not in ('index', 'HEAD'):
        raise SystemExit('usage: verify_git_bytes.py [index|HEAD]')

    def git(*args):
        return subprocess.check_output(['git', *args], cwd=REPO, timeout=15)

    # Bind HEAD once; the index is read-only throughout this coordinator verification.
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
    expected['zdoc/reviews/20260916-plan-history-s33/tools-plan-s33.txt'] = '1eb33e360f2c6f712768e453e0bb751e6d539eefb922347614b5e4a613a192f0'
    native_manifest_bytes = blob(NATIVE + 'manifest.json')
    if hashlib.sha256(native_manifest_bytes).hexdigest() != NATIVE_MANIFEST_HASH:
        raise ValueError('NATIVE_MANIFEST_HASH_MISMATCH')
    native_manifest = json.loads(native_manifest_bytes)
    expected[NATIVE + 'manifest.json'] = NATIVE_MANIFEST_HASH
    expected.update({NATIVE + name: digest for name, digest in native_manifest['files'].items()})
    expected.update(native_manifest['dependencies'])
    diagnostic_manifest = blob(AUDIT + 'diagnostic-manifest.json')
    diagnostic_hash = '609149bd9bc2508b1680b27221d89c52da14e07600726fbcb4b5efa7f50de82e'
    if hashlib.sha256(diagnostic_manifest).hexdigest() != diagnostic_hash:
        raise ValueError('DIAGNOSTIC_MANIFEST_HASH_MISMATCH')
    expected[AUDIT + 'diagnostic-manifest.json'] = diagnostic_hash
    expected.update(json.loads(diagnostic_manifest)['files'])
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
    native_verifier = NATIVE + 'verify_package.py'
    files[native_verifier] = blob(native_verifier)
    for relative in (verifier, native_verifier):
        if (REPO / PREFIX / relative).read_bytes() != files[relative]:
            raise ValueError('VERIFIER_WORKTREE_BYTES_DIFFER: ' + relative)
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
        'prior_native_counter': verified['prior_native_counter'],
        'native_verifier_sha256': hashlib.sha256(files[native_verifier]).hexdigest(),
        'scope': 'Git byte integrity and stored evidence verification; no engine or suite rerun',
        'formal_acceptance': False,
        'independent_critic_signatures': 0,
    }
    output = Path(__file__).with_name('git-byte-verification-' + source.lower() + '.json')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
