"""Engine-free verification of the sealed S227 cleanup diagnostic."""
from pathlib import Path
import hashlib, json, sys

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / 'studio/.local/reviews/gt06-s227-terminal-exit-01'
MANIFEST_SHA = '9e4df4c1ea7ddfa82f2dc0c931435f7679bee64966dcf65d13debf34b865c8ff'

def main():
    manifest = RAW / 'raw-manifest.json'
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == MANIFEST_SHA
    data = json.loads(manifest.read_bytes())
    assert data['authority'] == 0 and data['formal_acceptance'] is False
    rows = {row['path']: row for row in data['files']}
    for rel, row in rows.items():
        p = RAW / rel
        assert p.is_file() and p.stat().st_size == row['bytes']
        assert hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256']
    result = json.loads((RAW / 'result.json').read_bytes())
    target = result['target_observation']
    assert result['engine_started'] is False and result['passed'] is True
    assert result['formal_acceptance'] is False and result['authority'] == 0
    assert result['helper_exit'] == 2 and target['exit_code'] == 2
    assert target['natural_exit_not_inferred'] is True
    assert result['job']['closed'] is True and result['job']['zero_observed'] is True
    assert result['wrapper_handle']['handle_retained'] is False
    assert result['probe_handle_released'] is True and result['source_unchanged'] is True
    terminal = json.loads((RAW / 'child-terminal-cleanup.json').read_bytes())
    assert terminal['errors'] == [] and terminal['primary_error']['code'] == 'EXIT_PROBE_INJECTED_FAILURE'
    assert terminal['observations']['editor_exit_after_cleanup'] == target
    assert terminal['observations']['editor_target']['actual_target_exit'] is None
    print(json.dumps({'authority': 0, 'formal_acceptance': False,
                      'engine_started': False, 'verified_files': len(rows),
                      'target_exit': target['exit_code']}))

if __name__ == '__main__':
    main()
