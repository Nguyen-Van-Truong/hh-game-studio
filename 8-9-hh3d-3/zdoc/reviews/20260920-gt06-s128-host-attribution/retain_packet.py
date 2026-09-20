"""Retain selected S128 raw bytes and verify references; never launch a process."""
import hashlib
import json
from pathlib import Path
import shutil

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s128-host-attribution-01'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name, value):
    (PACKET / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    selected = ['owned/invocation.json', 'owned/process-start.json',
                'attempt/editor-host/invocation.json', 'attempt/editor-snapshot.json',
                'attempt/import-observation.json',
                'attempt/project/benchmark/out/ready-05.json']
    checked = []
    for i in range(5):
        capture = RAW / f'attempt/batch-capture-{i:02}.json'
        doc = json.loads(capture.read_text(encoding='utf-8'))
        assert doc['index'] == i
        selected.append(capture.relative_to(RAW).as_posix())
        for role in ('ack', 'command', 'joint', 'native', 'ready', 'start'):
            ref = doc[role]
            target = (RAW / 'attempt' / ref['file']).resolve()
            assert target.is_relative_to(RAW.resolve()) and target.is_file()
            assert digest(target) == ref['sha256'] and target.stat().st_size == ref['size_bytes']
            checked.append({'batch': i, 'role': role, 'raw_file': target.relative_to(RAW).as_posix(),
                            'sha256': ref['sha256'], 'size_bytes': ref['size_bytes']})
            # Large command logs remain in immutable local raw; hashes explicitly retain their domain.
            if role != 'command':
                selected.append(target.relative_to(RAW).as_posix())
    missing_terminal = []
    for relative in ('result.json', 'attempt/child-failure.json', 'attempt/child-result.json',
                     'attempt/child-terminal-cleanup.json', 'owned/process-exit.json',
                     'owned/capture.json', 'attempt/editor-host/process-exit.json',
                     'attempt/editor-host/capture.json'):
        assert not (RAW / relative).exists(), f'NEW_TERMINAL_EVIDENCE:{relative}'
        missing_terminal.append(relative)
    copies = []
    for relative in sorted(set(selected)):
        source, target = RAW / relative, PACKET / relative
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            assert target.read_bytes() == source.read_bytes(), f'COPY_DRIFT:{relative}'
        else:
            shutil.copyfile(source, target)
        copies.append({'file': relative, 'sha256': digest(source), 'size': source.stat().st_size})
    write('raw-inventory.json', {'authority': 0, 'status': 'INCOMPLETE_UNKNOWN',
          'formal_acceptance': False, 'eligible_for_dataset': False,
          'raw_root_relative': RAW.relative_to(ROOT).as_posix(),
          'verified_batch_reference_count': len(checked), 'batch_references': checked,
          'selected_copies': copies, 'absent_terminal_paths': missing_terminal,
          'import_exit': json.loads((RAW / 'attempt/import-host/process-exit.json').read_text()),
          'limitations': ['NO_HOST_EDITOR_SUPERVISOR_EXIT', 'IMPORT_EXIT_IS_SEPARATE',
                         'RAW_COMMAND_LOGS_HASHED_NOT_COPIED', 'NOT_AN_ACCEPTANCE_PACKET']})
    old = json.loads((PACKET / 'manifest.json').read_text())
    paths = set(old['files']) | {v['file'] for v in copies} | {
        's127-plan.snapshot', 'helper-audit.md', 'raw-inventory.json',
        'liveness-observation.json', 'retain_packet.py'}
    files = {}
    for rel in sorted(paths):
        target = PACKET / rel
        files[rel] = {'sha256': digest(target), 'size': target.stat().st_size}
    old['files'] = files
    write('manifest.json', old)
    for rel, meta in files.items():
        assert digest(PACKET / rel) == meta['sha256']
    print(json.dumps({'packet_files': len(files), 'verified_references': len(checked),
                      'manifest_sha256': digest(PACKET / 'manifest.json')}))


if __name__ == '__main__':
    main()
