"""Retain exact short-probe inventories; never copy journals or caches into Git."""
from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parent
LANES = ('hash-reader-probe', 'http-attribution', 'import-attribution')


def main():
    raw, portable, excluded = {}, {}, {}
    for lane in LANES:
        for path in sorted((BASE / lane).rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            relative = path.relative_to(BASE).as_posix()
            info = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size_bytes': path.stat().st_size}
            raw[relative] = info
            reason = None
            if path.suffix == '.jsonl':
                reason = 'LOCAL_JOURNAL_COPY'
            elif any(part in path.parts for part in ('source', 'project', 'commands')):
                reason = 'LOCAL_SOURCE_OR_GENERATED_FIXTURE_COPY'
            elif path.suffix not in ('.py', '.md', '.json', '.txt'):
                reason = 'LOCAL_GENERATED_FILE'
            if reason is not None:
                excluded[relative] = dict(info, reason=reason)
            else:
                portable[relative] = info
    value = {'schema': 'HH-S100-SHORT-PROBE-INVENTORY-1', 'formal_acceptance': False,
        'eligible_for_dataset': False, 'authority': 0, 'raw_files': raw,
        'portable_files': portable, 'local_excluded': excluded,
        'scope': 'Three completed short probes; local raw and portable Git domains are distinct.'}
    with (BASE / 'short-probes-inventory.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'raw': len(raw), 'portable': len(portable), 'excluded': len(excluded),
                      'sha256': hashlib.sha256((BASE / 'short-probes-inventory.json').read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
