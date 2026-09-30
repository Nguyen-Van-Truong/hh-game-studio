"""Short session-rotation allocation diagnostic; never benchmark acceptance.

Uses the real session issuer and checks all retained credentials' redaction.
Outputs only aggregate allocation statistics, never credentials or patterns.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import tracemalloc

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.transport import SessionAuthority, TransportLimits
from studio.tests.replay.benchmark_commands import NativeObserver


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def run(root):
    root.mkdir(parents=True, exist_ok=False)
    paths = {Path(__file__).resolve()}
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name is not None:
            path = Path(name).absolute()
            if path.suffix == '.py' and path.is_relative_to(STUDIO):
                paths.add(path)
    source = {path.relative_to(STUDIO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(paths)}
    write(root / 'source-files.json', source)
    observer = NativeObserver()
    marks = []
    started = time.monotonic()
    try:
        write(root / 'context.json', {'run_id': root.name, 'authority': 0,
            'started_utc': datetime.now(timezone.utc).isoformat(), 'process': observer.identity,
            'python_version': platform.python_version(), 'platform': sys.platform,
            'python_sha256': hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),
            'private_bytes_provider': observer.kind, 'pid': os.getpid(),
            'source_closure_sha256': hashlib.sha256(''.join(
                name + '\0' + source[name] + '\n' for name in sorted(source)).encode()).hexdigest()})
        tracemalloc.start(1)
        authority = SessionAuthority('allocation.probe', root, TransportLimits())
        credential = None
        for index in range(35):
            credential = authority.issue() if credential is None else authority.rotate(credential)
            # Expired/rotated credentials remain private; do not trade security
            # history for a smaller allocation count.
            for prior in authority._issued:
                if prior in authority.redact_output('message ' + prior):
                    raise RuntimeError('PRIOR_CREDENTIAL_NOT_REDACTED')
            gc.collect()
            current, peak = tracemalloc.get_traced_memory()
            private = observer.sample()['counters']['private_commit_bytes']
            if type(private['value']) is not int or private['value'] <= 0 or private['unavailable_reason'] is not None:
                raise RuntimeError('PRIVATE_COMMIT_UNAVAILABLE')
            marks.append({'index': index, 'issued_count': len(authority._issued),
                'traced_current': current, 'traced_peak': peak,
                'private_bytes': private['value']})
        snapshot = tracemalloc.take_snapshot()
        allocations = [{'file': str(row.traceback[0].filename), 'line': row.traceback[0].lineno,
                        'bytes': row.size, 'count': row.count}
                       for row in snapshot.statistics('lineno')]
        write(root / 'allocations.json', allocations)
        del snapshot, allocations
        write(root / 'result.json', {'authority': 0, 'acceptance': False, 'completed': True,
            'marks': marks, 'elapsed_seconds': time.monotonic() - started,
            'source_unchanged': all(hashlib.sha256((STUDIO / name).read_bytes()).hexdigest() == digest
                                    for name, digest in source.items()),
            'scope': '35 credential generations (issue + 34 rotations), no commands, no journal or native editor; tracemalloc affects memory'})
    finally:
        tracemalloc.stop()
        observer.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
