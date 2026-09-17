"""Isolated, bounded 32 MiB scan study. Never imports or runs studio code.

This is a hashing microbenchmark, not GT-06 or journal acceptance evidence.
Each measured scan includes open/fstat/full SHA-256/fstat/flush/fsync/close.
All bytes, caps, and identity checks are identical across scan variants.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import stat
import statistics
import sys
import tempfile
import threading
import time


OUT = Path(__file__).resolve().parent
RESULT = OUT / "hash-scan-results.json"
SIZE = 32 * 1024 * 1024
CAP = 64 * 1024 * 1024
METHODS = [("read", 64 * 1024), ("read", 1024 * 1024)] + [
    ("readinto", size * 1024) for size in (64, 256, 1024, 4096)
]


def scan(path: Path, method: str, block_size: int) -> str:
    digest, size = hashlib.sha256(), 0
    with path.open("r+b") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise RuntimeError("JOURNAL_PATH_UNSAFE")
        if info.st_size > CAP:
            raise RuntimeError("JOURNAL_FULL")
        if method == "read":
            while chunk := stream.read(min(block_size, CAP - size + 1)):
                size += len(chunk)
                if size > CAP:
                    raise RuntimeError("JOURNAL_FULL")
                digest.update(chunk)
        else:
            buffer = bytearray(block_size)
            view = memoryview(buffer)
            while count := stream.readinto(view[:min(block_size, CAP - size + 1)]):
                size += count
                if size > CAP:
                    raise RuntimeError("JOURNAL_FULL")
                digest.update(view[:count])
        final = os.fstat(stream.fileno())
        if (size != info.st_size or final.st_size != size
                or (info.st_dev, info.st_ino) != (final.st_dev, final.st_ino)):
            raise RuntimeError("JOURNAL_HISTORY_CHANGED")
        stream.flush()
        os.fsync(stream.fileno())
    return digest.hexdigest()


def main() -> int:
    started = time.perf_counter()
    utc = dt.datetime.now(dt.timezone.utc).isoformat()
    # Hard stop independently of the between-scan measurement deadline.
    watchdog = threading.Timer(18, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    fixture: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix="synthetic-32mib-", suffix=".bin", dir=OUT, delete=False) as stream:
            fixture = Path(stream.name)
            chunk = bytes(range(256)) * 4096
            expected = hashlib.sha256()
            for _ in range(SIZE // len(chunk)):
                stream.write(chunk)
                expected.update(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        expected_digest = expected.hexdigest()
        samples: dict[str, list[float]] = {
            f"{method}_{block // 1024}k": [] for method, block in METHODS
        }
        warmups = []
        for method, block in METHODS:
            before = time.perf_counter()
            assert scan(fixture, method, block) == expected_digest
            warmups.append({"method": f"{method}_{block // 1024}k", "ms": (time.perf_counter() - before) * 1000})
        order = []
        rng = random.Random(7306)
        completed_rounds = 0
        for round_index in range(11):
            methods = METHODS.copy()
            rng.shuffle(methods)
            for method, block in methods:
                if time.perf_counter() - started >= 14:
                    break
                label = f"{method}_{block // 1024}k"
                before = time.perf_counter()
                actual = scan(fixture, method, block)
                elapsed = (time.perf_counter() - before) * 1000
                assert actual == expected_digest
                samples[label].append(elapsed)
                order.append({"round": round_index, "method": label, "ms": elapsed})
            else:
                completed_rounds += 1
                continue
            break
        # A changed byte with exactly restored mtime is still part of every scan.
        before_mutation = fixture.stat()
        with fixture.open("r+b") as stream:
            stream.seek(0)
            stream.write(b"\xff")
            stream.flush()
            os.fsync(stream.fileno())
        os.utime(fixture, ns=(before_mutation.st_atime_ns, before_mutation.st_mtime_ns))
        mutation_info = fixture.stat()
        assert mutation_info.st_size == before_mutation.st_size
        assert mutation_info.st_mtime_ns == before_mutation.st_mtime_ns
        mutation_digests = {f"{method}_{block // 1024}k": scan(fixture, method, block) for method, block in METHODS}
        assert all(value != expected_digest for value in mutation_digests.values())
        assert len(set(mutation_digests.values())) == 1
        root = OUT.parents[3]
        source_paths = [
            root / "studio/host/replay/verified_journal.py",
            root / "studio/host/core/journal.py",
            root / "studio/host/core/transport.py",
        ]
        result = {
            "kind": "isolated_hash_microbenchmark_not_native_or_acceptance",
            "utc_started": utc,
            "python": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
            "source_sha256": {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "dataset_bytes": SIZE,
            "dataset_sha256": expected_digest,
            "read_cap_bytes": CAP,
            "fsync_every_scan": True,
            "includes": ["open", "before_fstat", "buffer_allocation", "all_byte_SHA256", "after_fstat", "flush", "fsync", "close"],
            "excludes": ["writer_lock", "JSON_parser", "index_lookup", "append", "HTTP", "engine", "native_benchmark"],
            "warmups": warmups,
            "completed_rounds": completed_rounds,
            "requested_rounds": 11,
            "samples_ms": samples,
            "sample_order": order,
            "summary": {key: {
                "n": len(values), "median_ms": statistics.median(values),
                "min_ms": min(values), "max_ms": max(values),
                "median_MiB_per_second": (SIZE / (1024 ** 2)) / (statistics.median(values) / 1000),
            } for key, values in samples.items() if values},
            "same_size_mtime_changed_byte_digest_detected": True,
            "mutated_digest": next(iter(mutation_digests.values())),
            "wall_seconds_before_report": time.perf_counter() - started,
            "warm_file_cache_only": True,
            "fixed_seed": 7306,
        }
        RESULT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": str(RESULT), "wall_seconds": time.perf_counter() - started, "summary": result["summary"]}))
        return 0
    finally:
        if fixture is not None:
            assert fixture.parent.resolve() == OUT
            fixture.unlink(missing_ok=True)
        watchdog.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
