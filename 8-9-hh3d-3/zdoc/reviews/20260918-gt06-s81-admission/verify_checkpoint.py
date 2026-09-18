"""Verify S81 runtime bytes and explicitly staged checkpoint bytes, not acceptance."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
REPO = ROOT.parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('revision', choices=['index', 'HEAD'])
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    binding = json.loads((BASE / 'repair-source.json').read_bytes())
    mapping = binding['files']
    closure = sha(b''.join(name.encode() + b'\0' + digest.encode() + b'\n'
                          for name, digest in sorted(mapping.items())))
    assert len(mapping) == binding['file_count'] == 51
    assert closure == binding['source_closure_sha256']
    assert git('rev-parse', '--show-object-format').strip() == b'sha1'
    for name, digest in mapping.items():
        path = '8-9-hh3d-3/studio/' + name
        spec = ':' + path if args.revision == 'index' else 'HEAD:' + path
        raw = git('show', spec)
        assert sha(raw) == digest == sha((REPO / path).read_bytes()), path
    # Inventory only this checkpoint's explicit files, not unrelated untracked work.
    inventory = json.loads((BASE / 'checkpoint-paths.json').read_bytes())
    paths = inventory['paths']
    expected = {item['path']: item for item in inventory['files']}
    if args.revision == 'index':
        entries = git('ls-files', '-s', '-z').split(b'\0')
        index = {}
        for entry in entries:
            if not entry:
                continue
            meta, path = entry.split(b'\t', 1)
            mode, blob, stage = meta.split()
            assert stage == b'0', path
            index[path.decode()] = (mode, blob.decode())
    checks = {}
    for path in paths:
        assert path.startswith('8-9-hh3d-3/') and '..' not in Path(path).parts
        raw = (REPO / path).read_bytes()
        if path != inventory['inventory_self']['path']:
            assert expected[path]['sha256'] == sha(raw), path
            assert expected[path]['bytes'] == len(raw), path
        if args.revision == 'index':
            mode, blob = index[path]
            assert mode in (b'100644', b'100755'), path
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == blob, path
        else:
            assert git('show', 'HEAD:' + path) == raw, path
        checks[path] = {'sha256': sha(raw), 'bytes': len(raw)}
    report = {'formal_acceptance': False, 'revision': args.revision,
              'head': git('rev-parse', 'HEAD').decode().strip(),
              'runtime_files': len(mapping), 'runtime_closure': closure,
              'checkpoint_files': len(checks), 'exact_git_bytes': True, 'files': checks}
    with Path(args.output).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'files'}))


if __name__ == '__main__':
    main()
