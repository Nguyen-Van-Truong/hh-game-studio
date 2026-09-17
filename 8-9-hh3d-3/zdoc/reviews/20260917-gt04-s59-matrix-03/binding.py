"""Read-only binding for S59 supplement and every recursively launched child."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
STUDIO = HERE.parent/'20260917-gt04-s59-scene-01/source/studio'
BINARY = ROOT/'studio/.local/tooling/blender-5.2.1-windows-x64/blender.exe'
CLOSURE = '943cff74f23a61427765071f7fd6661acbdad23c0e8386364f5615a2a0016134'


def sha(raw): return hashlib.sha256(raw).hexdigest()


def verify():
    manifest = json.loads((HERE/'execution-closure.json').read_bytes())
    assert manifest['source_closure_sha256'] == CLOSURE
    files = manifest['files']
    assert sha(json.dumps(files, sort_keys=True, separators=(',',':')).encode()) == manifest['execution_closure_sha256']
    for name, digest in files.items():
        path = (ROOT/name).resolve()
        path.relative_to(ROOT)
        assert path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == digest, name
    source = json.loads((STUDIO.parent.parent/'source-closure.json').read_bytes())
    assert source['source_closure_sha256'] == CLOSURE
    prefix = STUDIO.relative_to(ROOT).as_posix()+'/'
    assert {name[len(prefix):]:digest for name,digest in files.items() if name.startswith(prefix)} == source['files']
    assert sha(BINARY.read_bytes()) == manifest['binary_sha256']
    return manifest
