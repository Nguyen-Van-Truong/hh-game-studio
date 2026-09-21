"""No-engine controlled SHA-512 scheduling mechanism probe, not acceptance.

Tests exactly the same historical bytes with a synthetic competing Python
thread. No application, process priority, switch interval, source or profile
setting changes. All threads owned here stop at a bounded deadline.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
HISTORY = HH3D / "studio/.local/reviews/gt06-s141-formal-01/run-00-attempt-01/commands/commands.jsonl"
OUTPUT = BASE / "hash-contention-01.json"


def main():
    if OUTPUT.exists():
        raise RuntimeError("S142_FRESH_OUTPUT_REQUIRED")
    raw = HISTORY.read_bytes()
    expected = hashlib.sha512(raw).digest()
    view = memoryview(raw)
    rows = []
    for contention in (False, True):
        stop, ready = threading.Event(), threading.Event()
        progress = [0]

        def compete():
            limit = time.monotonic() + 40
            ready.set()
            counter = 0
            while not stop.is_set() and time.monotonic() < limit:
                for _ in range(1000):
                    counter += 1
                progress[0] = counter

        worker = threading.Thread(target=compete, name="S142-owned-synthetic-competitor") if contention else None
        try:
            if worker:
                worker.start()
                if not ready.wait(2):
                    raise RuntimeError("S142_COMPETITOR_START")
            for trial in range(4):
                # Alternate order; <=2047 avoids hashlib's per-update GIL release.
                for chunk_size in ((65536, 2047) if trial % 2 == 0 else (2047, 65536)):
                    before, cpu = time.perf_counter_ns(), time.thread_time_ns()
                    digest = hashlib.sha512()
                    for offset in range(0, len(view), chunk_size):
                        digest.update(view[offset:offset+chunk_size])
                    elapsed = time.perf_counter_ns()-before
                    assert digest.digest() == expected
                    rows.append({"contention": contention, "trial": trial, "chunk_size": chunk_size,
                                 "wall_ms": elapsed/1e6, "cpu_ms": (time.thread_time_ns()-cpu)/1e6,
                                 "digest_matches": True, "competitor_progress": progress[0]})
        finally:
            stop.set()
            if worker:
                worker.join(2)
                if worker.is_alive():
                    raise RuntimeError("S142_COMPETITOR_DID_NOT_EXIT")
    result = {"authority": 0, "formal_acceptance": False, "engine_runs": 0,
              "history_sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
              "helper_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "python": sys.version, "switch_interval": sys.getswitchinterval(), "rows": rows,
              "owned_threads_stopped": True, "ended_utc": datetime.now(timezone.utc).isoformat(),
              "limits": "Synthetic in-memory hashing only; no file I/O/fsync/native/HTTP or S141 scheduling reproduced."}
    with OUTPUT.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    for contention in (False, True):
        for chunk_size in (65536, 2047):
            values = [r["wall_ms"] for r in rows if r["contention"] == contention and r["chunk_size"] == chunk_size]
            print(json.dumps({"contention": contention, "chunk_size": chunk_size, "wall_ms": values}))


if __name__ == "__main__":
    main()
