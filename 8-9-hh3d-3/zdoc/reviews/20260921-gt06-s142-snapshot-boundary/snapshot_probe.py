"""Bounded no-engine timing of the unchanged snapshot on a copied S141 journal.

The stock parser/index initialization runs first. CPython's profiling hook then
times fixed C-call names during 20 locked snapshots; no journal method, I/O
operation, digest, durability barrier, limit or timeout is replaced. This is
attribution on historical bytes, not reproduction of S141's live interleaving.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

BASE = Path(__file__).resolve().parent
HH3D = BASE.parents[2]
SOURCE = HH3D / "studio/.local/reviews/gt06-s141-formal-01/run-00-attempt-01/commands/commands.jsonl"
OUT = HH3D / "studio/.local/reviews/gt06-s142-snapshot-01"
FREEZE = HH3D / "zdoc/reviews/20260921-gt06-s141-stock-campaign/freeze.json"
NAMES = frozenset({"open", "read", "update", "fstat", "fsync", "flush", "close"})


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


class Calls:
    def __init__(self):
        self.stack = []
        self.rows = {}

    def profile(self, frame, event, value):
        if event not in ("c_call", "c_return", "c_exception"):
            return
        label = getattr(value, "__name__", "")
        if label not in NAMES:
            return
        if event == "c_call":
            self.stack.append((label, time.perf_counter_ns(), time.thread_time_ns()))
        else:
            name, started, cpu = self.stack.pop()
            if name != label:
                raise RuntimeError("S142_PROFILE_PAIR_MISMATCH")
            duration = (time.perf_counter_ns() - started) / 1e6
            cpu_ms = (time.thread_time_ns() - cpu) / 1e6
            row = self.rows.setdefault(label, {"count": 0, "wall_ms": 0, "cpu_ms": 0, "max_ms": 0})
            row["count"] += 1
            row["wall_ms"] += duration
            row["cpu_ms"] += cpu_ms
            row["max_ms"] = max(row["max_ms"], duration)


def main():
    freeze = json.loads(FREEZE.read_bytes())
    if any(sha(HH3D/name) != digest for name, digest in freeze["files"].items()):
        raise RuntimeError("S142_SOURCE_INPUT_DRIFT")
    source_hash = sha(SOURCE)
    if sys.argv[1:] != ["--run"]:
        print(json.dumps({"checked": True, "engine_launched": False,
                          "source_files": len(freeze["files"]), "history_sha256": source_hash}))
        return 0
    if sys.getprofile() is not None:
        raise RuntimeError("S142_EXISTING_PROFILER")
    OUT.mkdir(exist_ok=False)
    history = OUT / "commands.jsonl"
    shutil.copyfile(SOURCE, history)
    assert sha(history) == source_hash == sha(SOURCE)
    write(OUT/"freeze.json", {"authority": 0, "source_files": freeze["files"],
          "helper_sha256": sha(Path(__file__)), "history_sha256": source_hash,
          "history_size": history.stat().st_size, "formal_acceptance": False,
          "started_utc": datetime.now(timezone.utc).isoformat()})
    sys.path.insert(0, str(HH3D))
    from studio.host.replay.verified_journal import VerifiedJournal
    started = time.perf_counter()
    journal = None
    rows = []
    try:
        journal = VerifiedJournal(history)
        initialization = time.perf_counter() - started
        for index in range(20):
            if time.perf_counter() - started > 120:
                raise RuntimeError("S142_BOUNDED_DURATION")
            calls = Calls()
            # Guard acquisition is separately outside the snapshot timing.
            with journal._writer_lock():
                before, cpu = time.perf_counter_ns(), time.thread_time_ns()
                try:
                    sys.setprofile(calls.profile)
                    digest, size, identity = journal._snapshot(synchronize=True)
                finally:
                    sys.setprofile(None)
                elapsed, cpu_elapsed = time.perf_counter_ns() - before, time.thread_time_ns() - cpu
                assert journal._matches(digest, size, identity) and not calls.stack
                rows.append({"index": index, "wall_ms": elapsed/1e6, "cpu_ms": cpu_elapsed/1e6,
                             "bytes_verified": size, "calls": calls.rows})
    finally:
        sys.setprofile(None)
        if journal is not None:
            journal.close()
    assert sha(history) == source_hash == sha(SOURCE)
    assert all(sha(HH3D/name) == digest for name, digest in freeze["files"].items())
    result = {"authority": 0, "formal_acceptance": False, "engine_runs": 0,
              "initialization_seconds": initialization, "elapsed_seconds": time.perf_counter()-started,
              "rows": rows, "history_unchanged": True, "source_unchanged": True,
              "closed": journal._cache_closed and journal._index_store is None,
              "ended_utc": datetime.now(timezone.utc).isoformat(),
              "limits": ["No HTTP/native workload, OS pressure or original interleaving reproduced.",
                         "Profiler overhead is present, never subtracted; thread CPU clock may be coarse.",
                         "No performance gate, root cause, no-leak or formal acceptance inference."]}
    write(OUT/"result.json", result)
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "limits")}))
    print(json.dumps({"snapshot_max_ms": max(row["wall_ms"] for row in rows),
                      "snapshot_count": len(rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
