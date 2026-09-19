"""Retain selected terminal S106 preflight evidence; no engine or cache scan."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
HH3D = HERE.parents[2]
RUN = 'gt06-s106-handles-preflight-01'
RAW = HH3D / 'studio/.local/reviews' / RUN
OUT = HERE / 'preflight-01'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def closure(files):
    return sha(''.join(k + '\0' + files[k] + '\n' for k in sorted(files)).encode())


def main():
    if OUT.exists():
        raise RuntimeError('RETAINED_OUTPUT_EXISTS')
    spec = importlib.util.spec_from_file_location('_s105_retention_rules', HERE.parent / '20260919-gt06-s105-result/build_packet.py')
    sys.path.insert(0, str(Path(spec.origin).parent))
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    result = json.loads((RAW / 'diagnostic-result.json').read_bytes())
    context = json.loads((RAW / 'context.json').read_bytes())
    assert result['status'] == 'BOUNDARY_CAPTURED' and result['errors'] == []
    assert result['batches']['count'] == 1 and result['capture_status'] == 'COMPLETE'
    selected = [(p, 'raw/' + p.relative_to(RAW).as_posix()) for p in RAW.glob('*.json')]
    for name in ('host-owner', 'editor-host', 'import-host', 'gates', 'pss', 'project/benchmark/input', 'project/benchmark/out'):
        base = RAW / name
        selected.extend((p, 'raw/' + p.relative_to(RAW).as_posix()) for p in base.iterdir()
                        if p.is_file() and (p.suffix == '.json' or p.name in ('stdout.txt', 'stderr.txt')))
    input_path = RAW / 'project/benchmark/input.json'
    selected.append((input_path, 'raw/project/benchmark/input.json'))
    outer = RAW.with_name(RUN + '-outer')
    selected.extend((p, 'outer/' + p.name) for p in outer.iterdir() if p.is_file())
    for name, expected in context['diagnostic_files'].items():
        source = HH3D / name
        assert sha(source.read_bytes()) == expected
        selected.append((source, 'frozen-helper/' + source.name))
    destinations = [relative for source, relative in selected]
    assert len(destinations) == len(set(destinations))
    rows = []
    for source, relative in sorted(selected, key=lambda pair: pair[1]):
        assert source.is_file() and not source.is_symlink()
        raw = source.read_bytes()
        helper.secret_screen(raw, source.relative_to(HH3D).as_posix())
        target = OUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
        assert target.read_bytes() == raw
        rows.append({'source': source.relative_to(HH3D).as_posix(), 'path': relative,
                     'sha256': sha(raw), 'size_bytes': len(raw)})
    packet = {'schema': 'gt06-s106-preflight-retention-v1', 'authority': 0,
              'formal_acceptance': False, 'eligible_for_dataset': False,
              'run_id': RUN, 'files': rows,
              'raw_selected_domain_sha256': closure({r['source']: r['sha256'] for r in rows}),
              'portable_domain_sha256': closure({r['path']: r['sha256'] for r in rows}),
              'exclusions': ['cache/private environments', 'journals/commandstore', 'unselected project source/assets/binaries'],
              'limitations': ['editor natural exit UNKNOWN', 'import wrapper native handle close UNKNOWN',
                              'outer managed Dispose does not observe native CloseHandle return',
                              'one diagnostic batch cannot establish formal performance/memory acceptance']}
    with (OUT / 'manifest.json').open('xb') as stream:
        stream.write((json.dumps(packet, sort_keys=True, indent=2) + '\n').encode())
    for row in rows:
        b = (OUT / row['path']).read_bytes()
        assert sha(b) == row['sha256'] and len(b) == row['size_bytes']
    print(json.dumps({'files': len(rows), 'bytes': sum(r['size_bytes'] for r in rows),
                      'manifest_sha256': sha((OUT / 'manifest.json').read_bytes())}))


if __name__ == '__main__':
    main()
