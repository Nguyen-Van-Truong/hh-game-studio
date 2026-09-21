"""Controlled whole-snapshot comparison; no engine and no runtime edits."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from snapshot_probe import HH3D, BASE, SOURCE, FREEZE, Calls, sha, write

OUT = HH3D / "studio/.local/reviews/gt06-s142-snapshot-contention-01"
SHA512 = hashlib.sha512


class BoundedDigest:
    def __init__(self):
        self.inner = SHA512()

    def update(self, data):
        view = memoryview(data)
        for offset in range(0, len(view), 2047):
            self.inner.update(view[offset:offset+2047])

    def digest(self):
        return self.inner.digest()


def main():
    freeze = json.loads(FREEZE.read_bytes())
    assert all(sha(HH3D/name) == digest for name, digest in freeze["files"].items())
    OUT.mkdir(exist_ok=False)
    shutil.copyfile(SOURCE, OUT/"commands.jsonl")
    expected = sha(SOURCE)
    assert sha(OUT/"commands.jsonl") == expected
    sys.path.insert(0, str(HH3D))
    from studio.host.replay import verified_journal
    journal = verified_journal.VerifiedJournal(OUT/"commands.jsonl")
    rows = []
    try:
        for contended in (False, True):
            stop, ready = threading.Event(), threading.Event()
            counts = [0]

            def compete():
                limit = time.monotonic()+50
                ready.set()
                value = 0
                while not stop.is_set() and time.monotonic() < limit:
                    for _ in range(1000):
                        value += 1
                    counts[0] = value

            worker = threading.Thread(target=compete, name="S142-snapshot-competitor") if contended else None
            try:
                if worker:
                    worker.start()
                    assert ready.wait(2)
                for trial in range(2):
                    for bounded in ((False, True) if trial == 0 else (True, False)):
                        calls = Calls()
                        factory = BoundedDigest if bounded else SHA512
                        # Only generated diagnostic module binding is patched;
                        # stock snapshot implementation and every I/O unchanged.
                        with patch.object(verified_journal, "hashlib", SimpleNamespace(sha512=factory)):
                            with journal._writer_lock():
                                before, cpu = time.perf_counter_ns(), time.thread_time_ns()
                                try:
                                    sys.setprofile(calls.profile)
                                    digest, size, identity = journal._snapshot(synchronize=True)
                                finally:
                                    sys.setprofile(None)
                                elapsed = time.perf_counter_ns()-before
                                cpu_elapsed = time.thread_time_ns()-cpu
                                assert journal._matches(digest, size, identity) and not calls.stack
                                rows.append({"trial": trial, "bounded_hash": bounded,
                                    "synthetic_contention": contended, "wall_ms": elapsed/1e6,
                                    "cpu_ms": cpu_elapsed/1e6, "calls": calls.rows,
                                    "matched": True, "competitor_progress": counts[0]})
            finally:
                stop.set()
                if worker:
                    worker.join(2)
                    assert not worker.is_alive()
    finally:
        sys.setprofile(None)
        journal.close()
    assert sha(SOURCE) == sha(OUT/"commands.jsonl") == expected
    assert all(sha(HH3D/name) == digest for name, digest in freeze["files"].items())
    result = {"authority": 0, "formal_acceptance": False, "engine_runs": 0,
        "history_sha256": expected, "helper_sha256": sha(Path(__file__)),
        "profile_helper_sha256": sha(BASE/"snapshot_probe.py"), "rows": rows,
        "owned_threads_stopped": True, "journal_closed": journal._cache_closed and journal._index_store is None,
        "history_unchanged": True, "source_unchanged": True, "ended_utc": datetime.now(timezone.utc).isoformat(),
        "limits": "Synthetic contention and profiled copied history. Not S141 replay, full workload or acceptance. No timing subtraction."}
    write(OUT/"result.json", result)
    for row in rows:
        print(json.dumps({k:v for k,v in row.items() if k != "calls"}))


if __name__ == "__main__":
    main()
