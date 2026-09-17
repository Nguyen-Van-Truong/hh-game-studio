"""Supplemental attribution over unchanged real HTTP/journal code, never a gate.

Wrap existing methods and stream calls; delegate every argument and result.
No sampling omission, skipped fsync, cached bytes, deadline or journal changes.
The trusted S73 driver verifies the original 33MB history and private copy.
"""
from pathlib import Path
from collections import defaultdict
import importlib.util
import json
import os
import sys
import threading
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
sys.path.insert(0, str(ROOT))
from studio.host.replay.verified_journal import VerifiedJournal
from studio.host.core.transport import FixtureClient

local = threading.local()
totals = defaultdict(lambda: {'calls': 0, 'inclusive_ns': 0, 'max_ns': 0})
stats_lock = threading.Lock()


def timed(label, call, *args, **kwargs):
    start = time.perf_counter_ns()
    try:
        return call(*args, **kwargs)
    finally:
        elapsed = time.perf_counter_ns() - start
        with stats_lock:
            row = totals[label]
            row['calls'] += 1
            row['inclusive_ns'] += elapsed
            row['max_ns'] = max(row['max_ns'], elapsed)


class Stream:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        self.raw.__enter__()
        return self

    def __exit__(self, *args):
        return self.raw.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.raw, name)

    def read(self, *args, **kwargs):
        return timed('snapshot.stream.read', self.raw.read, *args, **kwargs)

    def flush(self, *args, **kwargs):
        return timed('snapshot.stream.flush', self.raw.flush, *args, **kwargs)


def main():
    original_open, original_sync = Path.open, os.fsync
    originals = {}
    def opened(path, *args, **kwargs):
        if getattr(local, 'snapshot', False):
            return Stream(timed('snapshot.open', original_open, path, *args, **kwargs))
        return original_open(path, *args, **kwargs)
    def synced(fd):
        if getattr(local, 'snapshot', False):
            return timed('snapshot.fsync', original_sync, fd)
        return original_sync(fd)
    def wrap(cls, method, label):
        original = getattr(cls, method)
        originals[(cls, method)] = (original, method in cls.__dict__)
        def wrapped(self, *args, **kwargs):
            was = getattr(local, 'snapshot', False)
            if method == '_snapshot':
                local.snapshot = True
            try:
                return timed(label, original, self, *args, **kwargs)
            finally:
                local.snapshot = was
        setattr(cls, method, wrapped)
    Path.open, os.fsync = opened, synced
    for name in ('_snapshot', '_reload', '_load', '_append'):
        wrap(VerifiedJournal, name, 'journal.' + name)
    for name in ('submit', 'lookup'):
        wrap(FixtureClient, name, 'http.' + name)
    driver = ROOT / 'zdoc/reviews/20260918-gt06-s73-recovery/large-history/large_history_http.py'
    spec = importlib.util.spec_from_file_location('history_http_owned', driver)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = BASE / 'http-attribution-01'
    try:
        return module.main(['--source-root', str(ROOT),
                     '--journal', str(ROOT / 'studio/.local/reviews/gt06-s71-campaign-01/run-00-attempt-01/commands/commands.jsonl'),
                     '--source-map', str(ROOT / 'studio/.local/reviews/gt06-s71-campaign-01/run-00-attempt-01/source-files.json'),
                     '--output', str(output), '--run-id', 'gt06-s76-attribution-01',
                     '--commands', '30', '--deadline-seconds', '100'])
    finally:
        Path.open, os.fsync = original_open, original_sync
        for (cls, name), (original, own) in originals.items():
            if own:
                setattr(cls, name, original)
            else:
                delattr(cls, name)
        result = {'formal_acceptance': False, 'instrumentation_adds_overhead': True,
                  'durations_are_inclusive_do_not_sum_parent_and_child': True,
                  'snapshot_residual_includes_hash_metadata_scheduling_and_wrapper_overhead': True,
                  'counts': dict(totals)}
        (BASE / 'http-attribution-timing.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
