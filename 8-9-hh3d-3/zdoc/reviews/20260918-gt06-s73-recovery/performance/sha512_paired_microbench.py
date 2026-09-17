"""Paired unchanged-read-loop study; no production imports or mutations."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import random
import statistics
import tempfile
import threading
import time

from fingerprint_microbench import scan, OUT, SIZE


def main():
    started = time.perf_counter()
    watchdog = threading.Timer(6, lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    fixture = None
    try:
        methods = {
            "sha256_read64k": (hashlib.sha256, "read", 65536),
            "sha512_read64k": (hashlib.sha512, "read", 65536),
            "sha512_readinto256k": (hashlib.sha512, "readinto", 262144),
        }
        with tempfile.NamedTemporaryFile(prefix="sha512-paired-32mib-", suffix=".bin", dir=OUT, delete=False) as stream:
            fixture = Path(stream.name)
            chunk = bytes(range(256)) * 4096
            expected = {name: args[0]() for name, args in methods.items()}
            for _ in range(SIZE // len(chunk)):
                stream.write(chunk)
                for value in expected.values():
                    value.update(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        expected = {name: value.hexdigest() for name, value in expected.items()}
        for name, args in methods.items():
            assert scan(fixture, *args) == expected[name]
        samples, order = {name: [] for name in methods}, []
        rng = random.Random(7309)
        for round_index in range(9):
            names = list(methods)
            rng.shuffle(names)
            for name in names:
                assert time.perf_counter() - started < 4
                before = time.perf_counter()
                assert scan(fixture, *methods[name]) == expected[name]
                elapsed = (time.perf_counter() - before) * 1000
                samples[name].append(elapsed)
                order.append({"round": round_index, "method": name, "ms": elapsed})
        paired = [100 * (old - new) / old for old, new in zip(samples["sha256_read64k"], samples["sha512_read64k"])]
        result = {
            "kind": "paired_private_fingerprint_microbenchmark_not_native_or_acceptance",
            "utc_completed": dt.datetime.now(dt.timezone.utc).isoformat(),
            "dataset_bytes": SIZE, "dataset_digests": expected,
            "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "shared_scan_harness_sha256": hashlib.sha256((OUT / "fingerprint_microbench.py").read_bytes()).hexdigest(),
            "warm_file_cache_only": True, "fsync_every_scan": True,
            "samples_ms": samples, "sample_order": order,
            "summary": {name: {"n": len(values), "median_ms": statistics.median(values),
                "min_ms": min(values), "max_ms": max(values)} for name, values in samples.items()},
            "paired_sha512_read64k_reduction_percent": paired,
            "median_paired_reduction_percent": statistics.median(paired),
            "wall_seconds_before_report": time.perf_counter() - started,
            "scope": "same 65536-byte allocating read loop; private fingerprint factory only",
        }
        target = OUT / "sha512-paired-results.json"
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": str(target), "summary": result["summary"], "paired_reduction_percent": statistics.median(paired), "wall_seconds": time.perf_counter() - started}))
        return 0
    finally:
        if fixture is not None:
            assert fixture.parent.resolve() == OUT
            fixture.unlink(missing_ok=True)
        watchdog.cancel()


if __name__ == "__main__":
    raise SystemExit(main())
