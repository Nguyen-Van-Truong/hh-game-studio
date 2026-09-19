"""Copy-only, <=30 second streaming SHA-512 reader diagnostic. No acceptance."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys
import time

HERE = Path(__file__).resolve().parent
HH3D = HERE.parents[3]
SOURCE = HH3D / 'studio/.local/reviews/gt06-s98-campaign-01/run-00-attempt-01/commands/commands.jsonl'
COPY = HERE / 'commands.copy.jsonl'
ARMS = [('read64k', 'read', 65_536), ('read256k', 'read', 262_144),
        ('read1m', 'read', 1_048_576), ('readinto256k', 'readinto', 262_144),
        ('readinto1m', 'readinto', 1_048_576)]


def digest_file(path):
    sha256, sha512 = hashlib.sha256(), hashlib.sha512()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(262_144):
            size += len(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return {'size': size, 'sha256': sha256.hexdigest(), 'sha512': sha512.hexdigest()}


def sample(name, method, capacity, repetition, ordinal, expected, deadline):
    # Buffer lives only for this full snapshot, matching a bounded local
    # implementation; no full-history bytes or state survive an operation.
    buffer = bytearray(capacity) if method == 'readinto' else None
    view = memoryview(buffer) if buffer is not None else None
    digest, size, chunks = hashlib.sha512(), 0, 0
    started = time.perf_counter_ns()
    with COPY.open('r+b') as stream:
        before = os.fstat(stream.fileno())
        while True:
            if time.perf_counter() >= deadline:
                raise TimeoutError('PROBE_30_SECOND_BOUND')
            if method == 'read':
                chunk = stream.read(min(capacity, before.st_size - size + 1))
                if not chunk:
                    break
                size += len(chunk)
                digest.update(chunk)
            else:
                count = stream.readinto(view[:min(capacity, before.st_size - size + 1)])
                if not count:
                    break
                size += count
                digest.update(view[:count])
            chunks += 1
        after = os.fstat(stream.fileno())
        hash_ended = time.perf_counter_ns()
        assert size == before.st_size == after.st_size == expected['size']
        assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
        assert digest.hexdigest() == expected['sha512']
        sync_started = time.perf_counter_ns()
        stream.flush()
        os.fsync(stream.fileno())
        sync_ended = time.perf_counter_ns()
    ended = time.perf_counter_ns()
    return {'arm': name, 'repetition': repetition, 'ordinal': ordinal,
            'buffer_bytes': capacity, 'bytes': size, 'chunks': chunks,
            'sha512': digest.hexdigest(), 'hash_read_ms': (hash_ended-started)/1e6,
            'flush_fsync_ms': (sync_ended-sync_started)/1e6,
            'total_ms': (ended-started)/1e6}


def stats(values):
    ordered = sorted(values)
    return {'median_ms': statistics.median(values),
            'p95_nearest_rank_ms': ordered[math.ceil(len(ordered)*.95)-1],
            'max_ms': max(values), 'min_ms': min(values)}


def main():
    started = time.perf_counter()
    deadline = started + 30
    original_before = digest_file(SOURCE)
    if COPY.exists():
        raise RuntimeError('COPY_ALREADY_EXISTS')
    # Stream copy into an exclusive new owned file; never open original writable.
    with SOURCE.open('rb') as source, COPY.open('xb') as destination:
        shutil.copyfileobj(source, destination, length=262_144)
        destination.flush()
        os.fsync(destination.fileno())
    copy_before = digest_file(COPY)
    assert original_before == copy_before
    rows = []
    for repetition in range(5):
        # Latin-square rotations distribute each arm across all five positions.
        order = ARMS[repetition:] + ARMS[:repetition]
        for arm in order:
            rows.append(sample(*arm, repetition, len(rows), copy_before, deadline))
    original_after, copy_after = digest_file(SOURCE), digest_file(COPY)
    assert original_before == original_after == copy_before == copy_after
    summaries = {}
    for name, method, capacity in ARMS:
        own = [row for row in rows if row['arm'] == name]
        summaries[name] = {'method': method, 'buffer_bytes': capacity, 'samples': len(own),
            **{key: stats([row[key] for row in own]) for key in ('hash_read_ms', 'flush_fsync_ms', 'total_ms')}}
    report = {'schema_id': 'hh-studio.hash-reader-diagnostic', 'schema_version': '1.0.0',
        'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'diagnostic_only': True,
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'scope': 'single-process warm-OS-cache copied-history reader microbenchmark; no engine, transport, lock contention, acceptance or root-cause claim',
        'method': '5 arms x 5 interleaved Latin-square rotations; exact full-file SHA-512 verified per arm; no byte cache/full-file loading/mmap; flush+fsync each sample timed separately',
        'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
        'source': str(SOURCE), 'copy': str(COPY), 'original_before': original_before,
        'original_after': original_after, 'copy_before': copy_before, 'copy_after': copy_after,
        'duration_seconds': time.perf_counter()-started, 'summaries': summaries, 'rows': rows}
    assert report['duration_seconds'] <= 30
    result = HERE / 'result.json'
    with result.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'result': str(result), 'duration_seconds': report['duration_seconds'],
        'original_sha256': original_before['sha256'], 'summaries': summaries}, indent=2))


if __name__ == '__main__':
    main()
