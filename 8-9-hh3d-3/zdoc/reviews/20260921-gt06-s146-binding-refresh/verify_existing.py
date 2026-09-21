"""Verify retained S146 metadata and current generation; never install or launch."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.host.replay import native_runner as native
from studio.host.replay import execution_installed as installed


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify():
    receipt = json.loads((BASE / 'refresh-receipt.json').read_bytes())
    for generation in ('old', 'new'):
        for name, digest in receipt[generation + '_metadata_sha256'].items():
            assert sha((BASE / generation / Path(name).name).read_bytes()) == digest
    old = json.loads((BASE / 'old/execution-source.json').read_bytes())
    new = json.loads((BASE / 'new/execution-source.json').read_bytes())
    assert old.keys() == new.keys()
    assert old['schema'] == new['schema']
    assert old['accepted_gt05_manifest_sha256'] == new['accepted_gt05_manifest_sha256']
    old_files, new_files = old['source_files'], new['source_files']
    assert set(old_files) == set(new_files)
    delta = [p for p in sorted(old_files) if old_files[p] != new_files[p]]
    assert delta == receipt['source_delta'] == ['host/replay/verified_journal.py']
    for name, digest in receipt['new_metadata_sha256'].items():
        assert sha((native.STUDIO / name).read_bytes()) == digest
    # Preserve original GT05 payload validation, not just its manifest label.
    inputs, accepted = native.accepted_inputs()
    verified = native.sources(accepted)
    assert verified == dict(sorted({**new_files, **receipt['new_metadata_sha256']}.items()))
    assert len(new_files) == 215 and len(verified) == 217
    return {'authority': 0, 'formal_acceptance': False, 'engine_runs': 0,
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'pid': os.getpid(), 'python': sys.executable,
        'operation': 'READ_ONLY_POSTCHECK', 'delta': delta,
        'source_count': len(new_files), 'execution_count': len(verified),
        'source215_canonical_closure': native.closure(new_files),
        'execution217_canonical_closure': native.closure(verified),
        'gt05_inputs_sha256': {p: sha(raw) for p, raw in inputs.items()},
        'metadata': installed.selection_identity(native.STUDIO),
        'execution_files': verified,
        'receipt_source_closure_domain': 'sha256(pretty JSON source map + newline), not native.closure'}


if __name__ == '__main__':
    result = verify()
    output = BASE / 'postcheck-01.json'
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'execution_files'}))
