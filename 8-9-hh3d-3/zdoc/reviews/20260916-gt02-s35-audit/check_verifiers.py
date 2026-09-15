"""Bounded portable evidence checks; no engine/native process execution."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
PACK = 'zdoc/reviews/20260916-gt02-s35-01/'
NATIVE = 'zdoc/reviews/20260916-gt02-s35-native/'
AUDIT = 'zdoc/reviews/20260916-gt02-s35-audit/'


def main():
    manifest = json.loads((ROOT / (PACK + 'source-closure.json')).read_bytes())
    candidate = json.loads((ROOT / (PACK + 'candidate.json')).read_bytes())
    native = json.loads((ROOT / (NATIVE + 'manifest.json')).read_bytes())
    names = {'studio/' + name for name in manifest['files']}
    names.update(PACK + name for name in candidate['artifacts'])
    names.update(NATIVE + name for name in native['files'])
    names.update(native['dependencies'])
    names.update((PACK + 'candidate.json', NATIVE + 'manifest.json',
                  NATIVE + 'verify_package.py', AUDIT + 'verify_evidence.py'))
    results = []
    with tempfile.TemporaryDirectory(prefix='hh-s35-verifier-check-') as temporary:
        copied = Path(temporary) / '8-9-hh3d-3'
        for name in names:
            target = copied / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())

        def run(label, script, optimized=False, expected=None):
            args = [sys.executable, '-I'] + (['-O'] if optimized else [])
            result = subprocess.run(args + [str(copied / script)], cwd=copied,
                                    capture_output=True, text=True, timeout=30)
            if expected:
                if result.returncode == 0 or expected not in result.stderr:
                    raise ValueError('MISSING_EXPECTED_REJECTION: ' + label)
            else:
                if result.returncode != 0 or result.stderr:
                    raise ValueError('VERIFICATION_FAILED: ' + label)
                value = json.loads(result.stdout)
                if script.startswith(NATIVE) and value['raw_available'] is not False:
                    raise ValueError('PORTABLE_COPY_CLAIMED_LOCAL_RAW')
            results.append({'case': label, 'exit': result.returncode,
                            'expected_rejection': expected, 'passed': True})

        run('portable_native', NATIVE + 'verify_package.py')
        run('portable_native_optimized', NATIVE + 'verify_package.py', True)
        run('portable_integrated', AUDIT + 'verify_evidence.py')
        run('coordinator_optimized_refused', AUDIT + 'verify_evidence.py', True,
            'OPTIMIZED_VERIFICATION_FORBIDDEN')
        mutations = [
            ('native_artifact_changed', NATIVE + 'run-03.stdout.json', b' ', 'ARTIFACT_HASH_MISMATCH'),
            ('native_manifest_changed', NATIVE + 'manifest.json', b' ', 'MANIFEST_HASH_MISMATCH'),
            ('runtime_source_changed', 'studio/host/core/fixture_pipe.py', b'\n# altered\n', 'RUNTIME_SOURCE_HASH'),
            ('native_artifact_missing', NATIVE + 'run-03.host.json', None, 'FileNotFoundError'),
        ]
        for label, name, addition, rejection in mutations:
            target = copied / name
            original = target.read_bytes()
            try:
                if addition is None:
                    target.unlink()
                else:
                    target.write_bytes(original + addition)
                run(label, NATIVE + 'verify_package.py', True, rejection)
            finally:
                target.write_bytes(original)
        run('restored_portable_integrated', AUDIT + 'verify_evidence.py')
    output = {'status': 'PORTABLE_VERIFIER_CHECKS_PASSED', 'cases': results,
              'source_closure_sha256': manifest['source_closure_sha256'],
              'verifier_hashes': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                                  for name in (NATIVE+'verify_package.py', AUDIT+'verify_evidence.py')},
              'formal_acceptance': False, 'scope': 'Artifact integrity checks; no runtime suite rerun'}
    Path(__file__).with_name('verifier-checks.json').write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': output['status'], 'cases': len(results)}))


if __name__ == '__main__':
    main()
