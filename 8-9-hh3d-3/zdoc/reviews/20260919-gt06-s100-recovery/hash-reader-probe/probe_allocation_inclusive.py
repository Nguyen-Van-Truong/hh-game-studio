"""Fresh 5x5 copy-only confirmation counting each local buffer allocation."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time

from probe import ARMS, COPY, HERE, SOURCE, digest_file, stats


def sample(arm, repetition, ordinal, expected, deadline):
    name, method, capacity = arm
    started = time.perf_counter_ns()
    buffer = bytearray(capacity) if method == 'readinto' else None
    view = memoryview(buffer) if buffer is not None else None
    digest, size, chunks = hashlib.sha512(), 0, 0
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


def main():
    started = time.perf_counter()
    deadline = started + 30
    original_before, copy_before = digest_file(SOURCE), digest_file(COPY)
    assert original_before == copy_before
    rows = []
    for repetition in range(5):
        # Reverse traversal, rotating each arm through every position.
        order = list(reversed(ARMS))
        order = order[repetition:] + order[:repetition]
        for arm in order:
            rows.append(sample(arm, repetition, len(rows), copy_before, deadline))
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
        'method': 'Fresh 5 arms x 5 reverse interleaved rotations; each snapshot local buffer allocation included; exact full-file SHA-512 verified per arm; no byte cache/full-file loading/mmap; flush+fsync each sample separately',
        'python': sys.version, 'executable': sys.executable,
        'source': str(SOURCE), 'copy': str(COPY), 'original_before': original_before,
        'original_after': original_after, 'copy_before': copy_before, 'copy_after': copy_after,
        'duration_seconds': time.perf_counter()-started, 'summaries': summaries, 'rows': rows}
    assert report['duration_seconds'] <= 30
    result = HERE / 'result-allocation-inclusive.json'
    with result.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'result': str(result), 'duration_seconds': report['duration_seconds'],
        'original_sha256': original_before['sha256'], 'summaries': summaries}, indent=2))


if __name__ == '__main__':
    main()
