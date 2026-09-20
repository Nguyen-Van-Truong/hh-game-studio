"""One-use S135 installation; exact old generation and exactly two changed files."""
from pathlib import Path
import hashlib
import json
import os
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
from studio.host.replay import execution_binding as binding, execution_installed as installed


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    target = BASE / 'binding-install-01'
    assert not target.exists(), 'one use only'
    selector_path, binding_path = (STUDIO / installed.SELECTOR_PATH, STUDIO / installed.BINDING_PATH)
    old_selector, old_binding = selector_path.read_bytes(), binding_path.read_bytes()
    assert sha(old_binding) == 'b0ec25dc6ed1d757f468375052db5170b0305c134ffcc8d5b4740d6eccf3286f'
    assert json.loads(old_selector)['binding_sha256'] == sha(old_binding)
    document = json.loads(old_binding)
    sources = document['source_files']
    new_sources = {name: sha(binding._read(STUDIO / name, binding.MAX_SOURCE_BYTES)) for name in sources}
    changed = {name for name in sources if sources[name] != new_sources[name]}
    assert changed == {'host/replay/repair.py', 'host/replay/repair_replay.py'}, changed
    assert installed._required_sources(STUDIO) <= sources.keys()
    manifest_raw = (ROOT / 'zdoc/reviews/20260917-gt05-s63-audit/manifest.json').read_bytes()
    assert sha(manifest_raw) == binding.GT05_MANIFEST_SHA256
    target.mkdir()
    (target / 'prior-binding.json').write_bytes(old_binding)
    (target / 'prior-selector.json').write_bytes(old_selector)
    new_binding = encode({**document, 'source_files': new_sources})
    new_selector = encode({'schema': installed.SELECTOR_SCHEMA, 'binding_sha256': sha(new_binding)})
    for path, raw in ((binding_path, new_binding), (selector_path, new_selector)):
        temporary = path.with_suffix('.s135.tmp')
        with temporary.open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    verified = installed.load_installed(STUDIO, json.loads(manifest_raw)['source_files'])
    closure = sha(''.join(name + '\0' + verified[name] + '\n' for name in sorted(verified)).encode())
    receipt = {'authority': 0, 'formal_acceptance': False, 'changed': sorted(changed),
        'before': {name: sources[name] for name in sorted(changed)},
        'after': {name: new_sources[name] for name in sorted(changed)},
        'execution_files': verified, 'execution_closure': closure,
        'metadata': installed.selection_identity(STUDIO), 'fresh_interpreter_required': True}
    (target / 'receipt.json').write_bytes(encode(receipt))
    print(json.dumps({'execution_files': len(verified), 'closure': closure, 'changed': sorted(changed)}))


if __name__ == '__main__':
    main()
