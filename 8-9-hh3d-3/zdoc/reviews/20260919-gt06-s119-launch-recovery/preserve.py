"""Retain interrupted S117-03 bytes without inventing terminal evidence."""
import hashlib
import json
from pathlib import Path
import shutil

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    packet = BASE / 'interrupted-s117-03'
    packet.mkdir(exist_ok=False)
    sources = {
        'raw': ROOT / 'studio/.local/reviews/gt06-s117-lookup-boundary-03',
        'launch': ROOT / 'zdoc/reviews/20260919-gt06-s117-lookup-boundary/launch-03',
        'helpers': ROOT / 'zdoc/reviews/20260919-gt06-s117-lookup-boundary/owned/gt06-s117-lookup-boundary-03',
    }
    files, excluded = {}, {}
    for domain, source in sources.items():
        for path in sorted(source.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(source)
            key = domain + '/' + relative.as_posix()
            record = {'source': path.relative_to(ROOT).as_posix(),
                      'sha256': digest(path), 'bytes': path.stat().st_size}
            if any(part.lower() in {'.godot', 'commands', 'localappdata', 'appdata', '__pycache__'}
                   for part in relative.parts):
                excluded[key] = record
                continue
            target = packet / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            assert digest(target) == record['sha256'] == digest(path)
            files[key] = record
    missing = [name for name in ('result.json', 'timing-summary.json',
        'owned/process-exit.json', 'owned/capture.json', 'attempt/child-failure.json',
        'attempt/child-terminal-cleanup.json', 'attempt/http-phases-final.json',
        'attempt/editor-host/process-exit.json') if not (sources['raw'] / name).exists()]
    manifest = {'AUTHORITY': 0, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'run_id': 'gt06-s117-lookup-boundary-03', 'disposition': 'INTERRUPTED_WITHOUT_TERMINAL_RECORD',
        'files': files, 'local_excluded': excluded, 'missing_terminal_records': missing,
        'limits': 'Absence of live targets is not actual exit or Job/handle cleanup evidence. No retroactive raw.'}
    (packet / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'copied': len(files), 'local_excluded': len(excluded),
        'manifest_sha256': digest(packet / 'manifest.json'), 'missing': missing}))


if __name__ == '__main__':
    main()
