"""Bind S60 Git/source/view files separately from retained exact local raw."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
REPO = ROOT.parent
EXCLUDE = {'review-closure.json', 'files.json', 'paths.nul', 'git-index.json', 'git-HEAD.json'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def inventory():
    from verify_views import PACKAGES, verify
    assert verify(local=True)['passed']
    files, local = {}, {}
    def add(path, expected=None):
        path = path.absolute()
        path.relative_to(ROOT)
        assert not path.is_symlink() and path.is_file()
        hashed = sha(path.read_bytes())
        assert expected is None or expected == hashed, path.relative_to(ROOT)
        files[path.relative_to(REPO).as_posix()] = hashed
    source = json.loads((HERE/'source-closure.json').read_bytes())
    for name, hashed in source['files'].items():
        add(ROOT/'studio'/name, hashed)
    for name in ('.gitattributes', 'AGENTS.md', 'zdoc/8-9-godot-blender-agent-studio-plan.txt',
                 'zdoc/reviews/20260917-gt04-s56-audit/verify_evidence.py',
                 'zdoc/reviews/20260917-gt03-s55-audit/checkpoint.py',
                 'zdoc/reviews/20260917-gt04-s60-review-interruption.json',
                 'zdoc/reviews/20260917-gt04-s60-repro-before.json',
                 'zdoc/reviews/20260917-gt04-s60-review-request.json',
                 'zdoc/reviews/20260917-plan-history-s59/README.md',
                 'zdoc/reviews/20260917-plan-history-s59/tools-plan-s59.snapshot'):
        add(ROOT/name)
    for path in HERE.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and not (path.parent == HERE and path.name in EXCLUDE):
            add(path)
    for label, folder in PACKAGES.items():
        manifest = json.loads((HERE/'portable'/label/'manifest.json').read_bytes())
        for name, row in manifest['files'].items():
            path = ROOT/'studio/.local/reviews'/folder/name
            assert sha(path.read_bytes()) == row['raw_sha256']
            local[path.relative_to(REPO).as_posix()] = row['raw_sha256']
    review = {'git_files': dict(sorted(files.items())), 'local_raw_files': dict(sorted(local.items()))}
    review['review_closure_sha256'] = digest(review)
    review['source_closure_sha256'] = source['source_closure_sha256']
    review['formal_acceptance'] = False
    write(HERE/'review-closure.json', review)
    add(HERE/'review-closure.json')
    files = dict(sorted(files.items()))
    write(HERE/'files.json', {'files': files, 'files_sha256': digest(files), 'formal_acceptance': False})
    (HERE/'paths.nul').write_bytes(b''.join(name.encode() + b'\0' for name in files))
    return review


def check(local=True):
    saved = json.loads((HERE/'review-closure.json').read_bytes())
    assert saved['review_closure_sha256'] == digest({key: saved[key] for key in ('git_files','local_raw_files')})
    for key in ('git_files','local_raw_files') if local else ('git_files',):
        for name, hashed in saved[key].items():
            assert sha((REPO/name).read_bytes()) == hashed, name
    return saved


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inventory','check','index','HEAD'))
    mode = parser.parse_args().mode
    if mode == 'inventory':
        result = inventory()
    else:
        result = check(local=(mode == 'check'))
        if mode in ('index','HEAD'):
            spec = importlib.util.spec_from_file_location('git_bytes', ROOT/'zdoc/reviews/20260917-gt03-s55-audit/checkpoint.py')
            helper = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(helper)
            saved = json.loads((HERE/'files.json').read_bytes())
            assert digest(saved['files']) == saved['files_sha256']
            helper.verify_git(saved['files'], mode)
            write(HERE/('git-'+mode+'.json'), {'passed': True, 'files': len(saved['files']),
                'files_sha256': saved['files_sha256'], 'ref': mode,
                'head': subprocess.check_output(['git','rev-parse','HEAD'], cwd=REPO).decode().strip(),
                'local_raw_bytes_in_git': False, 'formal_acceptance': False})
    print(json.dumps({'mode': mode, 'review_closure_sha256': result['review_closure_sha256'],
                      'git_files': len(result['git_files']), 'local_raw_files': len(result['local_raw_files'])}))
