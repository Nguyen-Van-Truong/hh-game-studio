"""Exact scoped S56 checkpoint; never enumerate or stage private fixture trees."""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REVIEWS = HERE.parent
ROOT = REVIEWS.parent.parent
REPO = ROOT.parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory():
    files = {}

    def add(path, expected=None):
        path = path.resolve()
        path.relative_to(ROOT)
        assert path.is_file() and not path.is_symlink() and path.name != '.writer'
        data = path.read_bytes()
        digest = sha(data)
        assert expected is None or expected == digest, str(path)
        files[path.relative_to(REPO).as_posix()] = digest

    manifest = json.loads((HERE / 'portable-artifacts.json').read_bytes())
    for name, digest in manifest.get('files', manifest).items():
        add(ROOT / name, digest)
    # Exact tested live bytes, independently of historical source snapshots.
    frozen = REVIEWS / '20260917-gt04-s56-writer-01'
    source = json.loads((frozen / 'source-closure.json').read_bytes())['files']
    for name, digest in source.items():
        add(ROOT / 'studio' / name, digest)
    # Preserve the failed first probe without its private working directory.
    failed = REVIEWS / '20260917-gt04-s56-deadline-01'
    for name, digest in json.loads((failed / 'source-closure.json').read_bytes())['files'].items():
        add(failed / 'source/studio' / name, digest)
    for name in ('source-closure.json', 'capture.json', 'absolute-deadline-native.json',
                 'unit-host.json', 'unit-stdout.txt', 'unit-stderr.txt',
                 'native-host.json', 'native-stdout.txt', 'native-stderr.txt'):
        add(failed / name)
    report = json.loads((failed / 'absolute-deadline-native.json').read_bytes())
    directory = report['gui_directory']
    assert Path(directory).name == directory and directory.startswith('blender-')
    for name in ('launch.json', 'process-start.json', 'process-exit.json', 'close.json', 'stdout.txt', 'stderr.txt'):
        add(failed / directory / name)
    for name in ('.gitattributes', 'AGENTS.md', 'zdoc/8-9-godot-blender-agent-studio-plan.txt'):
        add(ROOT / name)
    for name in ('20260917-gt04-deadline-review.md', '20260917-gt04-writer-owner-review.md',
                 '20260917-gt04-s56-next.md'):
        add(REVIEWS / name)
    for path in (REVIEWS / '20260917-plan-history-s55').iterdir():
        if path.is_file():
            add(path)
    for path in HERE.iterdir():
        if path.is_file() and path.name not in ('files.json', 'paths.nul', 'git-index.json', 'git-HEAD.json'):
            add(path)
    return dict(sorted(files.items()))


def main():
    mode = sys.argv[1]
    if mode == 'inventory':
        files = inventory()
        saved = {'files': files, 'files_sha256': sha(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())}
        (HERE / 'files.json').write_text(json.dumps(saved, indent=2) + '\n', encoding='utf-8', newline='\n')
        (HERE / 'paths.nul').write_bytes(b''.join(name.encode() + b'\0' for name in files))
    else:
        assert mode in ('index', 'HEAD')
        saved = json.loads((HERE / 'files.json').read_bytes())
        for name, digest in saved['files'].items():
            assert sha((REPO / name).read_bytes()) == digest, name
        helper = REVIEWS / '20260917-gt03-s55-audit/checkpoint.py'
        spec = importlib.util.spec_from_file_location('s55_git_bytes', helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.verify_git(saved['files'], mode)
        result = {'passed': True, 'files': len(saved['files']), 'files_sha256': saved['files_sha256'],
                  'ref': mode, 'head_commit': subprocess.check_output(
                      ['git', 'rev-parse', 'HEAD'], cwd=REPO).decode().strip(), 'formal_acceptance': False}
        (HERE / ('git-' + mode + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'mode': mode, 'files': len(saved['files']), 'files_sha256': saved['files_sha256']}))


if __name__ == '__main__':
    main()
