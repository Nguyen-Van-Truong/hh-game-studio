"""Retain interrupted S90 evidence without manufacturing terminal success."""
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s90-lifecycle-attribution-01'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    destination = BASE / 'raw'
    destination.mkdir(exist_ok=False)
    inventory, copies = {}, {}
    for path in sorted(RAW.rglob('*')):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise ValueError('S90_REPARSE')
        relative = path.relative_to(RAW).as_posix()
        raw = path.read_bytes()
        inventory[relative] = {'sha256': sha(raw), 'size_bytes': len(raw)}
        # Retain metadata/logs/source snapshots and phase evidence. Internal
        # journal/cache/workspace binaries remain in their original raw domain.
        selected = (path.parent == RAW or relative.startswith('source/')
                    or relative.startswith('project/benchmark/')
                    or (path.parent.name in ('host-owner', 'editor-host', 'import-host')
                        and path.suffix in ('.json', '.txt')))
        if selected:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
            if target.read_bytes() != raw or path.read_bytes() != raw:
                raise ValueError('S90_COPY_DRIFT')
            copies[relative] = inventory[relative]
    manifest = {'schema': 'HH-GT06-S90-INTERRUPTED-PACKET-1',
                'raw_relative_to_root': RAW.relative_to(ROOT).as_posix(),
                'raw_files': inventory, 'exact_copies': copies,
                'outcome': 'INTERRUPTED_UNKNOWN_CAUSE',
                'actual_exit_or_job_cleanup_proven': False,
                'formal_acceptance': False, 'eligible_for_dataset': False}
    encoded = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    with (BASE / 'manifest.json').open('xb') as stream:
        stream.write(encoded)
    print(json.dumps({'raw_files': len(inventory), 'exact_copies': len(copies),
                      'manifest_sha256': sha(encoded)}))


if __name__ == '__main__':
    main()
