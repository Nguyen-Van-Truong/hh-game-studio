"""Private cache fingerprint alternatives; no studio imports or mutations.

Every sample reads all 32 MiB and performs the same open/fstat/flush/fsync.
No wire, journal record, or evidence checksum algorithm is changed here.
"""
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
SIZE, CAP = 32 * 1024 * 1024, 64 * 1024 * 1024
FACTORIES = {
    "sha256_read64k": (hashlib.sha256, "read", 64 * 1024),
    "sha256_readinto256k": (hashlib.sha256, "readinto", 256 * 1024),
    "sha512_readinto256k": (hashlib.sha512, "readinto", 256 * 1024),
    "blake2b256_readinto256k": (lambda: hashlib.blake2b(digest_size=32), "readinto", 256 * 1024),
    "blake2s256_readinto256k": (hashlib.blake2s, "readinto", 256 * 1024),
}


def scan(path, factory, method, block_size):
    digest, size = factory(), 0
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
            view = memoryview(bytearray(block_size))
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


def main():
    started = time.perf_counter()
    watchdog = threading.Timer(12, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    fixture = None
    try:
        with tempfile.NamedTemporaryFile(prefix="fingerprint-32mib-", suffix=".bin", dir=OUT, delete=False) as stream:
            fixture = Path(stream.name)
            chunk = bytes(range(256)) * 4096
            expected = {name: factory() for name, (factory, _, _) in FACTORIES.items()}
            for _ in range(SIZE // len(chunk)):
                stream.write(chunk)
                for digest in expected.values():
                    digest.update(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        expected = {key: value.hexdigest() for key, value in expected.items()}
        for name, (factory, _, _) in FACTORIES.items():
            digest = factory()
            digest.update(b"verified-prefix")
            fork = digest.copy()
            fork.update(b"-append")
            reference = factory()
            reference.update(b"verified-prefix-append")
            assert fork.digest() == reference.digest()
            assert digest.digest() != fork.digest()
        warmups = {}
        for name, arguments in FACTORIES.items():
            before = time.perf_counter()
            assert scan(fixture, *arguments) == expected[name]
            warmups[name] = (time.perf_counter() - before) * 1000
        rng = random.Random(7307)
        samples = {name: [] for name in FACTORIES}
        order = []
        completed_rounds = 0
        for round_index in range(9):
            names = list(FACTORIES)
            rng.shuffle(names)
            for name in names:
                if time.perf_counter() - started > 8:
                    break
                before = time.perf_counter()
                result = scan(fixture, *FACTORIES[name])
                elapsed = (time.perf_counter() - before) * 1000
                assert result == expected[name]
                samples[name].append(elapsed)
                order.append({"round": round_index, "method": name, "ms": elapsed})
            else:
                completed_rounds += 1
                continue
            break
        info = fixture.stat()
        with fixture.open("r+b") as stream:
            stream.write(b"\xff")
            stream.flush()
            os.fsync(stream.fileno())
        os.utime(fixture, ns=(info.st_atime_ns, info.st_mtime_ns))
        assert fixture.stat().st_size == info.st_size
        assert fixture.stat().st_mtime_ns == info.st_mtime_ns
        assert all(scan(fixture, *arguments) != expected[name] for name, arguments in FACTORIES.items())
        result = {
            "kind": "isolated_private_fingerprint_microbenchmark_not_native_or_acceptance",
            "utc_completed": dt.datetime.now(dt.timezone.utc).isoformat(),
            "python": sys.version, "platform": platform.platform(),
            "dataset_bytes": SIZE, "dataset_digests": expected,
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "fsync_every_scan": True, "warm_file_cache_only": True,
            "completed_rounds": completed_rounds, "requested_rounds": 9,
            "warmups_ms": warmups, "samples_ms": samples, "sample_order": order,
            "summary": {name: {"n": len(values), "median_ms": statistics.median(values),
                "min_ms": min(values), "max_ms": max(values)} for name, values in samples.items() if values},
            "copy_then_append_sanity": True,
            "same_size_mtime_mutation_detected_all_algorithms": True,
            "wall_seconds_before_report": time.perf_counter() - started,
            "scope": "private cache fingerprint candidates only; no record/wire/source-hash change",
        }
        target = OUT / "fingerprint-results.json"
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": str(target), "summary": result["summary"], "wall_seconds": time.perf_counter() - started}))
        return 0
    finally:
        if fixture is not None:
            assert fixture.parent.resolve() == OUT
            fixture.unlink(missing_ok=True)
        watchdog.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
