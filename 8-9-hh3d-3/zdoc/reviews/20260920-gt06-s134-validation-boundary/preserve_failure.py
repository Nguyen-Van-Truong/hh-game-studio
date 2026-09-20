"""Preserve S134 exact evidence and decode its existing journal without reopening it."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
RAW = ROOT / 'studio/.local/reviews/gt06-s134-managed-repair-01'
PACKET = BASE / 'terminal-packet-01'
EXCLUDED = {'.godot', '__pycache__', 'appdata', 'localappdata'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def write(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def decode_events(raw):
    """Validate framing/checksum/sequence/previous; no custody or acceptance claim."""
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('EVENT_SIZE')
    offset, previous, events = 0, '0' * 64, []
    while offset < len(raw):
        if len(raw) - offset < 36 or len(events) >= 512:
            raise ValueError('EVENT_TRUNCATED')
        size = int.from_bytes(raw[offset:offset + 4], 'little')
        if not 1 <= size <= 16384 or offset + size + 36 > len(raw):
            raise ValueError('EVENT_FRAME')
        body = raw[offset + 4:offset + 4 + size]
        digest = raw[offset + 4 + size:offset + 36 + size]
        value = json.loads(body)
        if (hashlib.sha256(body).digest() != digest
                or set(value) != {'format', 'sequence', 'previous', 'event'}
                or value['format'] != 'hh-private-events-1'
                or type(value['sequence']) is not int
                or value['sequence'] != len(events) + 1
                or value['previous'] != previous or type(value['event']) is not dict):
            raise ValueError('EVENT_CHAIN')
        events.append(value['event'])
        previous = digest.hex()
        offset += size + 36
    if not events:
        raise ValueError('EVENT_EMPTY')
    return events


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def create():
    PACKET.mkdir(exist_ok=False)
    roots = [('managed', RAW), ('outer', BASE / 'managed-refresh-02'),
             ('profile01', BASE / 'gt06-s134-profile-boundary-01'),
             ('profile02', BASE / 'gt06-s134-profile-boundary-02'),
             ('profile03', BASE / 'gt06-s134-profile-boundary-03'),
             ('script_probe', BASE / 'script-lane-probe-01')]
    records, excluded = [], []
    for label, source in roots:
        for path in sorted(source.rglob('*')):
            if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise ValueError('REPARSE')
            if not path.is_file():
                continue
            rel = path.relative_to(source)
            if EXCLUDED.intersection(rel.parts) or path.name == '.writer':
                excluded.append({'source': path.relative_to(ROOT).as_posix(), 'reason': 'cache_or_empty_guard'})
                continue
            raw = path.read_bytes()
            dest = Path(label) / rel
            write(PACKET / dest, raw)
            records.append({'file': dest.as_posix(), 'source': path.relative_to(ROOT).as_posix(),
                            'sha256': sha(raw), 'size': len(raw)})
    logs = list(RAW.glob('owned/storage/*/.events'))
    if len(logs) != 1:
        raise ValueError('JOURNAL_COUNT')
    events = decode_events(logs[0].read_bytes())
    timeline = []
    for event in events:
        if 'observed_ms' in event:
            timeline.append({'kind': event['kind'], 'observed_ms': event['observed_ms'],
                             'utc': utc(event['observed_ms'])})
    request = json.loads((RAW / 'request.json').read_bytes())
    generation_path, = RAW.glob('owned/editor/*/generation-*.json')
    generation = json.loads(generation_path.read_bytes())
    capture = json.loads((RAW / 'capture.json').read_bytes())
    validations = []
    for path in RAW.glob('owned/validation/*/executor/after-command-inspect-stdout.txt'):
        inspected = json.loads(path.read_bytes())[0]['State']
        validations.append({'path': path.relative_to(RAW).as_posix(), 'state': inspected})
    summary = {'schema': 'HH-S134-TERMINAL-ANALYSIS-1', 'authority': 0,
        'formal_acceptance': False, 'accepted_full_runs': 0, 'outcome': 'FAILED_UNKNOWN_COMMAND',
        'primary': 'HTTP_GETRESPONSE_TIMEOUT', 'secondary': 'GODOT_TRANSPORT_DRAIN_REQUIRED',
        'root_cause': 'UNKNOWN', 'command_deadline_ms': request['deadline_ms'],
        'generation_receipt': generation_path.relative_to(RAW).as_posix(),
        'generation_observed_ms': generation['observed_ms'],
        'generation_after_deadline_ms': generation['observed_ms'] - request['deadline_ms'],
        'journal_timeline': timeline, 'journal_kinds': [e.get('kind') for e in events],
        'validation_container_states': validations, 'host': capture['host'],
        'source_unchanged': capture['source_unchanged'],
        'execution_source_closure': capture['source_closure_sha256'],
        'successor_close': 'MISSING', 'successor_natural_exit': 'UNKNOWN',
        'limits': ['Frame chain integrity is not registry custody verification.',
                   'Event observed_ms is not method completion time.',
                   'Generation effect receipt is not public ACK or durable commit.',
                   'Outer tree_verified does not supply missing successor exit/handle records.',
                   'Validation container StartedAt/FinishedAt establish chronology, not directory order.']}
    write(PACKET / 'analysis.json', encode(summary))
    records.append({'file': 'analysis.json', 'source': None,
                    'sha256': sha((PACKET / 'analysis.json').read_bytes()),
                    'size': (PACKET / 'analysis.json').stat().st_size})
    write(PACKET / 'manifest.json', encode({'authority': 0, 'formal_acceptance': False,
        'files': records, 'exclusions': excluded, 'raw_preserved': True}))
    return verify()


def verify():
    manifest = json.loads((PACKET / 'manifest.json').read_bytes())
    for row in manifest['files']:
        raw = (PACKET / row['file']).read_bytes()
        if sha(raw) != row['sha256'] or len(raw) != row['size']:
            raise ValueError('COPY_MISMATCH')
        if row['source'] and (ROOT / row['source']).read_bytes() != raw:
            raise ValueError('RAW_CHANGED')
    return {'verified': len(manifest['files']), 'manifest_sha256': sha((PACKET / 'manifest.json').read_bytes()),
            'formal_acceptance': False}


if __name__ == '__main__':
    print(json.dumps(verify() if '--verify' in sys.argv else create()))
