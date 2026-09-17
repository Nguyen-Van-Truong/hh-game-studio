"""Curate hash-bound S55/Blender read-client WIP; never an acceptance verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPO = ROOT.parent
REVIEWS = ROOT / 'zdoc/reviews'
DENIED = {'__pycache__', '.godot', 'storage', 'appdata', 'localappdata', 'temp'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def inventory(manifests, extra_packages=()):
    files = {}

    def add(path, expected=None):
        path = path.resolve()
        relative = path.relative_to(ROOT)
        assert not set(relative.parts) & DENIED and path.name != '.writer', relative
        assert not path.is_symlink(), relative
        value = sha(path.read_bytes())
        assert expected is None or expected == value, 'hash mismatch: ' + str(relative)
        name = path.relative_to(REPO).as_posix()
        assert name not in files or files[name] == value, name
        files[name] = value

    # Exact tested live bytes; a later untested module is not silently included.
    for package in ('20260917-gt03-s55-source-01', '20260917-gt04-client-04', *extra_packages):
        folder = (REVIEWS / package).resolve()
        assert folder.parent == REVIEWS.resolve(), 'source package must be a direct review child'
        mapping = json.loads((folder / 'source-closure.json').read_bytes())['files']
        for name, digest in mapping.items():
            add(folder / 'source/studio' / name, digest)
            add(ROOT / 'studio' / name, digest)
        add(folder / 'source-closure.json')
    for name in ('.gitattributes', 'AGENTS.md', 'zdoc/8-9-godot-blender-agent-studio-plan.txt',
                 'zdoc/reviews/.gitignore'):
        add(ROOT / name)
    for manifest in manifests:
        manifest = manifest.resolve()
        manifest.relative_to(REVIEWS)
        record = json.loads(manifest.read_bytes())
        mapping = record.get('files', record)
        for name, digest in mapping.items():
            add(ROOT / name, digest)
        add(manifest)
        for path in manifest.parent.iterdir():
            if path.is_file() and path.suffix in ('.py', '.md', '.json', '.txt'):
                add(path)
    # Owned audit controllers/docs and bounded results; never enumerate private
    # native fixture storage or arbitrary untracked review roots.
    for folder in (HERE, REVIEWS / '20260917-gt03-s54-audit',
                   REVIEWS / '20260917-gt03-s54-gap-audit',
                   REVIEWS / '20260917-gt03-s54-recovery-cuts-audit',
                   REVIEWS / '20260917-gt04-client-next',
                   REVIEWS / '20260917-plan-history-s54-final',
                   REVIEWS / '20260917-mcp-adapter-preflight'):
        for path in folder.iterdir():
            if path.is_file() and path.suffix in ('.py', '.md', '.json', '.txt'):
                add(path)
    return dict(sorted(files.items()))


def verify_git(files, ref):
    prefix = ':' if ref == 'index' else 'HEAD:'
    result = subprocess.run(['git', 'cat-file', '--batch'], cwd=REPO,
        input=''.join(prefix + name + '\n' for name in files).encode(),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=True)
    cursor = 0
    for name, digest in files.items():
        end = result.stdout.index(b'\n', cursor)
        header = result.stdout[cursor:end].split()
        assert len(header) == 3 and header[1] == b'blob', 'missing Git blob: ' + name
        size = int(header[2]); cursor = end + 1
        raw = result.stdout[cursor:cursor + size]; cursor += size
        assert result.stdout[cursor:cursor + 1] == b'\n', 'Git batch framing'
        cursor += 1
        assert sha(raw) == digest, 'Git byte mismatch: ' + name
    assert cursor == len(result.stdout), 'unexpected Git output'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, action='append', default=[])
    parser.add_argument('--source-package', action='append', default=[],
                        help='additional completed source package, checked against live bytes')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--git-ref', choices=('index', 'HEAD'))
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.parent == HERE, 'checkpoint output must be one direct audit child'
    if args.git_ref:
        saved = json.loads((output / 'files.json').read_bytes())
        files = saved['files']
        for name, digest in files.items():
            assert sha((REPO / name).read_bytes()) == digest, 'working byte changed: ' + name
        verify_git(files, args.git_ref)
        report = {'passed': True, 'files': len(files), 'ref': args.git_ref,
                  'files_sha256': saved['files_sha256'], 'formal_acceptance': False}
        with (output / ('git-' + args.git_ref + '.json')).open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, indent=2); stream.write('\n')
    else:
        assert args.manifest, 'at least one verified portable manifest required'
        files = inventory(args.manifest, args.source_package)
        output.mkdir(exist_ok=False)
        digest = sha(json.dumps(files, sort_keys=True, separators=(',', ':')).encode())
        (output / 'files.json').write_text(json.dumps({'files': files, 'files_sha256': digest,
            'formal_acceptance': False}, indent=2) + '\n', encoding='utf-8', newline='\n')
        (output / 'paths.nul').write_bytes(b''.join(name.encode() + b'\0' for name in files))
        report = {'files': len(files), 'files_sha256': digest, 'formal_acceptance': False}
    print(json.dumps(report))


if __name__ == '__main__':
    main()
