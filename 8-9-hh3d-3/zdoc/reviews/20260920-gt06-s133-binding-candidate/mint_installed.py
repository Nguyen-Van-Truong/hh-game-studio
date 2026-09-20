"""Coordinator-only one-use installed binding mint; never automatic at runtime."""
from pathlib import Path
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
from studio.host.replay import execution_binding as reader
from studio.host.replay import execution_installed as installed


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def main():
    assert len(sys.argv) == 1
    anchor = ROOT / 'zdoc/reviews/20260917-gt05-s63-audit/manifest.json'
    raw = reader._read(anchor, reader.MAX_BINDING_BYTES)
    assert hashlib.sha256(raw).hexdigest() == reader.GT05_MANIFEST_SHA256
    accepted = json.loads(raw)['source_files']
    names = set(installed._required_sources(STUDIO))
    for name in accepted:
        assert name.startswith(reader.GT05_SOURCE_PREFIX)
        names.add(name[len(reader.GT05_SOURCE_PREFIX):])
    assert not names & installed.METADATA_PATHS
    files = {name: hashlib.sha256(reader._read(STUDIO / name, reader.MAX_SOURCE_BYTES)).hexdigest()
             for name in sorted(names)}
    binding = encoded({'schema': reader.SCHEMA,
        'accepted_gt05_manifest_sha256': reader.GT05_MANIFEST_SHA256, 'source_files': files})
    selector = encoded({'schema': installed.SELECTOR_SCHEMA,
                        'binding_sha256': hashlib.sha256(binding).hexdigest()})
    assert all(not (STUDIO / name).exists() for name in installed.METADATA_PATHS)
    with (STUDIO / installed.BINDING_PATH).open('xb') as stream:
        stream.write(binding)
    with (STUDIO / installed.SELECTOR_PATH).open('xb') as stream:
        stream.write(selector)
    verified = installed.load_installed(STUDIO, accepted)
    assert files.items() <= verified.items()
    receipt = {'authority': 0, 'formal_acceptance': False, 'source_files': files,
               'execution_files': verified, 'metadata': installed.selection_identity(STUDIO),
               'scope': 'Current execution source only; unchanged accepted GT05 assets retain historical provenance'}
    with (BASE / 'installed-mint-01.json').open('xb') as stream:
        stream.write(encoded(receipt))
    print(json.dumps({'dependency_files': len(files), 'execution_files': len(verified),
                      'metadata': receipt['metadata']}))


if __name__ == '__main__':
    main()
