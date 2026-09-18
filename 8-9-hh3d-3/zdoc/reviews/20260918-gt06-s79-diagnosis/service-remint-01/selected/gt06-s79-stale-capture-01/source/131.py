"""Internal reproducible GT05 producer diagnostic, not a publication command.

One named attempt owns a new private directory. Failed attempts stay intact.
Only the fixed original fixture producer is executable through this entry point.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(STUDIO.parent))
from studio.pipeline.native_job import run_trusted_stage


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def source_map(extra):
    """Bind loaded supervisor modules plus the explicitly declared child source."""
    paths = {Path(__file__).resolve(), *extra}
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(STUDIO) and path.suffix == '.py':
                paths.add(path)
    return {p.relative_to(STUDIO).as_posix(): sha(p.read_bytes()) for p in sorted(paths)}


def producer_warnings(stdout: bytes, stderr: bytes):
    """Only the two documented pinned-exporter cases; no log suppression."""
    expected = {
        b'Armature must be the parent of skinned meshArmature is selected by its name, but may be false in case of instances': 4,
        b'More than one shader node tex image used for a texture. The resulting glTF sampler will behave like the first shader node tex image.': 1,
    }
    if stderr.strip():
        raise ValueError('PRODUCER_STDERR_REQUIRES_REVIEW')
    found = []
    for line in stdout.splitlines():
        if any(word in line for word in (b'WARNING', b'ERROR', b'Error:')):
            match = re.fullmatch(rb'\d{2}:\d{2}:\d{2} \| WARNING: (.+)', line)
            if match is None:
                raise ValueError('PRODUCER_UNEXPLAINED_LOG')
            found.append(match[1])
    if Counter(found) != expected:
        raise ValueError('PRODUCER_WARNING_SET_CHANGED')
    return {'root_skin_single_rig_fallback': 4, 'shared_orm_sampler_traversal': 1}


def producer(run_id, variant):
    if not re.fullmatch(r'gt05-[a-z0-9-]{1,90}', run_id) or variant not in ('baseline', 'edited'):
        raise ValueError('DIAGNOSTIC_ARGUMENTS')
    root = STUDIO / '.local/reviews' / run_id
    root.mkdir(exist_ok=False)
    fixture = root / 'fixture'
    fixture.mkdir()
    script = STUDIO / 'pipeline/producer/run_blender.py'
    extra = list(script.parent.glob('*.py')) + [STUDIO / name for name in (
        'fixtures/assets-src/fixture-source.json', 'tests/asset-profile.json',
        'contracts/naming-convention-v1.md', 'pipeline/naming.py',
        'toolchain.lock.json', 'blender-addon/exporter.lock.json')]
    files = source_map(extra)
    write(root / 'source-files.json', files)
    for name in files:
        target = root / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((STUDIO / name).read_bytes())
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())
    binary = STUDIO / '.local/tooling/blender-5.2.1-windows-x64/blender.exe'
    argv = [str(binary), '--background', '--factory-startup', '--disable-autoexec',
            '--offline-mode', '--threads', '1', '--python-exit-code', '17',
            '--python', str(script), '--', str(fixture), variant]
    host = run_trusted_stage(argv, cwd=fixture, output=root / 'host',
        source_root=STUDIO, source_files=files,
        binary_sha256=lock['blender']['executable_sha256'])
    explained_warnings = producer_warnings((root / 'host/stdout.txt').read_bytes(),
                                          (root / 'host/stderr.txt').read_bytes())
    raw = (fixture / 'producer-report.json').read_bytes()
    report = json.loads(raw)
    if (report['variant'] != variant or report['formal_acceptance'] is not False
            or not report['source_reopened_exact'] or not report['export_preserved_source']):
        raise ValueError('PRODUCER_REPORT_CONTRACT')
    for name, item in report['artifacts'].items():
        if name not in ('fixture.blend', 'fixture.glb'):
            raise ValueError('PRODUCER_ARTIFACT_SLOT')
        value = (fixture / name).read_bytes()
        if item != {'sha256': sha(value), 'bytes': len(value)}:
            raise ValueError('PRODUCER_ARTIFACT_BINDING')
    pins = report['pins']['source_files']
    if not pins or any(files.get(name) != digest for name, digest in pins.items()):
        raise ValueError('PRODUCER_SOURCE_BINDING')
    lines = (root / 'host/stdout.txt').read_bytes().splitlines()
    markers = [json.loads(line[len(b'GT05_PRODUCER_COMPLETE '):]) for line in lines
               if line.startswith(b'GT05_PRODUCER_COMPLETE ')]
    if len(markers) != 1 or markers[0]['report_sha256'] != sha(raw):
        raise ValueError('PRODUCER_COMPLETION_BINDING')
    summary = {'run_id': run_id, 'variant': variant, 'producer_completed': True,
        'source_files': files, 'report_sha256': sha(raw), 'host_capture_sha256':
        sha((root / 'host/capture.json').read_bytes()), 'artifacts': report['artifacts'],
        'explained_exporter_warnings': explained_warnings,
        'formal_acceptance': False, 'public_ack': False}
    write(root / 'diagnostic.json', summary)
    print(json.dumps({'run_id': run_id, 'artifacts': report['artifacts'],
                      'completed': host['completed'], 'formal_acceptance': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--variant', choices=('baseline', 'edited'), default='baseline')
    args = parser.parse_args()
    producer(args.run_id, args.variant)
