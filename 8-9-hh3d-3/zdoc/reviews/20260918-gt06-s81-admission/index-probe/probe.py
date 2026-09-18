"""Bounded copied-history SQLite sync comparison; diagnostic, no engine."""
from pathlib import Path
from contextlib import contextmanager
import collections
import hashlib
import json
import math
import os
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
RAW = ROOT / 'studio/.local/reviews/gt06-s80-campaign-01/run-00-attempt-01'
OUT = Path(__file__).resolve().parent
SOURCE = RAW / 'source'
sys.path.insert(0, str(SOURCE))
from studio.host.replay import verified_journal, disk_journal_index


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    return {str(p.relative_to(SOURCE)).replace('\\', '/'): sha(p)
            for p in sorted(SOURCE.rglob('*.py'))}


def stats(values):
    values = sorted(values)
    return {'count': len(values), 'sum_ms': sum(values),
            'p50_ms': values[math.ceil(len(values) * .50) - 1],
            'p95_ms': values[math.ceil(len(values) * .95) - 1],
            'max_ms': values[-1]}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


ORIGINAL_FSYNC = os.fsync
ORIGINAL_INDEX = verified_journal.DiskJournalIndex
ORIGINAL_SNAPSHOT = verified_journal.VerifiedJournal._snapshot
ACTIVE = None


def add(name, elapsed):
    if ACTIVE is not None:
        ACTIVE[name + '_ms'] = ACTIVE.get(name + '_ms', 0.0) + elapsed
        ACTIVE[name + '_calls'] = ACTIVE.get(name + '_calls', 0) + 1


def timed_fsync(fd):
    start = time.perf_counter_ns()
    try:
        return ORIGINAL_FSYNC(fd)
    finally:
        add('canonical_fsync', (time.perf_counter_ns() - start) / 1e6)


def timed_snapshot(self, *, synchronize):
    start = time.perf_counter_ns()
    try:
        return ORIGINAL_SNAPSHOT(self, synchronize=synchronize)
    finally:
        add('snapshot_including_fsync', (time.perf_counter_ns() - start) / 1e6)


def main():
    global ACTIVE
    original_journal = RAW / 'commands/commands.jsonl'
    initial_hash = sha(original_journal)
    initial_sources = source_hashes()
    lines = original_journal.read_bytes().splitlines()
    last = json.loads(lines[-1])['record']
    now = max(json.loads(line)['record'].get('created_ms', 0) for line in lines) + 1000
    del lines
    records = []
    initial_dirs = sorted(str(p.relative_to(RAW)) for p in RAW.rglob('.hh-index-*'))
    os.fsync = timed_fsync
    verified_journal.VerifiedJournal._snapshot = timed_snapshot
    try:
        for ordinal, sync in enumerate([2, 0, 0, 2]):
            arm_dir = OUT / ('arm-%02d-sync%d' % (ordinal, sync))
            arm_dir.mkdir(exist_ok=False)
            journal_path = arm_dir / 'commands.jsonl'
            shutil.copyfile(original_journal, journal_path)
            assert sha(journal_path) == initial_hash
            owners = []

            class PolicyIndex(ORIGINAL_INDEX):
                def __init__(self, parent):
                    super().__init__(parent)
                    # Only the derived, never-reopened index changes policy.
                    self._execute('PRAGMA synchronous=%d' % sync)
                    assert self._one('PRAGMA synchronous')[0] == sync
                    assert self._one('PRAGMA journal_mode')[0] == 'delete'
                    assert self._one('PRAGMA cache_size')[0] == -256
                    assert self._one('PRAGMA mmap_size')[0] == 0
                    assert self._one('PRAGMA temp_store')[0] == 1
                    owners.append(self)

                def _execute(self, sql, args=(), *, fetch=False):
                    start = time.perf_counter_ns()
                    try:
                        return super()._execute(sql, args, fetch=fetch)
                    finally:
                        elapsed = (time.perf_counter_ns() - start) / 1e6
                        add('sqlite_execute_including_commit', elapsed)
                        if sql == 'COMMIT':
                            add('sqlite_commit', elapsed)

            verified_journal.DiskJournalIndex = PolicyIndex
            ACTIVE = {'name': 'initial_full_replay'}
            start = time.perf_counter_ns()
            journal = verified_journal.VerifiedJournal(journal_path)
            init = ACTIVE
            init['total_ms'] = (time.perf_counter_ns() - start) / 1e6
            ACTIVE = None
            ops = []

            def operation(kind, fn):
                global ACTIVE
                ACTIVE = {'kind': kind, 'ordinal': len(ops)}
                begin = time.perf_counter_ns()
                try:
                    result = fn()
                finally:
                    ACTIVE['total_ms'] = (time.perf_counter_ns() - begin) / 1e6
                    ops.append(ACTIVE)
                    ACTIVE = None
                return result

            try:
                for i in range(20):
                    name = 's81.index.probe.%02d' % i
                    digest = 'sha256:' + hashlib.sha256(name.encode()).hexdigest()
                    pending = {'phase': 'pending', 'value': i}
                    terminal = {'phase': 'terminal', 'value': i}
                    args = dict(project_id='s81.index.probe', command_id=name, now_ms=now)
                    existing = operation('lookup_original', lambda: journal.lookup(
                        project_id=last['project_id'], command_id=last['command_id'], now_ms=now))
                    assert existing['receipt'] == last['receipt']
                    result = operation('append_pending', lambda: journal.append_command(
                        **args, digest=digest, receipt=pending, pending=True))
                    assert result['status'] == 'ACCEPTED_PENDING' and not result['replayed']
                    result = operation('lookup_pending', lambda: journal.lookup(**args))
                    assert result['receipt'] == pending
                    result = operation('finish', lambda: journal.finish_command(
                        **args, status='COMMITTED', receipt=terminal))
                    assert result['status'] == 'COMMITTED'
                    result = operation('lookup_terminal', lambda: journal.lookup(**args))
                    assert result['receipt'] == terminal
                    result = operation('duplicate_append', lambda: journal.append_command(
                        **args, digest=digest, receipt=pending, pending=True))
                    assert result['replayed'] and result['receipt'] == terminal
                assert len(journal._records) == 22210
                assert len(journal._pending) == 0
            finally:
                journal.close()
            assert not list(arm_dir.glob('.hh-index-*'))
            assert all(index._db is None and index._dir is None for index in owners)
            kinds = sorted({row['kind'] for row in ops})
            result = {'ordinal': ordinal, 'synchronous': sync, 'journal_mode': 'delete',
                      'initial_journal_sha256': initial_hash, 'initial_full_replay': init,
                      'operations': ops, 'operation_statistics': stats([x['total_ms'] for x in ops]),
                      'by_kind': {k: stats([x['total_ms'] for x in ops if x['kind'] == k]) for k in kinds},
                      'phase_sums_ms': {key: sum(x.get(key, 0) for x in ops) for key in
                          ['snapshot_including_fsync_ms', 'canonical_fsync_ms',
                           'sqlite_execute_including_commit_ms', 'sqlite_commit_ms']},
                      'canonical_fsync_calls': sum(x.get('canonical_fsync_calls', 0) for x in ops),
                      'sqlite_commit_calls': sum(x.get('sqlite_commit_calls', 0) for x in ops),
                      'final_journal_sha256': sha(journal_path), 'final_record_count': 22210,
                      'all_receipt_assertions_passed': True, 'owned_index_closed_and_removed': True}
            write(arm_dir / 'result.json', result)
            records.append(result)
            print(json.dumps({'arm': ordinal, 'sync': sync, 'init_ms': init['total_ms'],
                              'total_operation_ms': result['operation_statistics']['sum_ms'],
                              'max_operation_ms': result['operation_statistics']['max_ms']}), flush=True)
    finally:
        ACTIVE = None
        os.fsync = ORIGINAL_FSYNC
        verified_journal.DiskJournalIndex = ORIGINAL_INDEX
        verified_journal.VerifiedJournal._snapshot = ORIGINAL_SNAPSHOT
    final_hash = sha(original_journal)
    final_sources = source_hashes()
    assert final_hash == initial_hash
    assert final_sources == initial_sources
    assert sorted(str(p.relative_to(RAW)) for p in RAW.rglob('.hh-index-*')) == initial_dirs
    assert len({row['final_journal_sha256'] for row in records}) == 1
    write(OUT / 'result.json', {'kind': 'copied_history_diagnostic_not_benchmark_acceptance',
          'source_files_sha256': initial_sources, 'source_files_unchanged': True,
          'original_journal_sha256_before': initial_hash, 'original_journal_sha256_after': final_hash,
          'original_journal_unchanged': True, 'original_index_inventory_unchanged': True,
          'arms': records, 'final_journal_bytes_equal_all_arms': True,
          'full_history_hash_and_canonical_fsync_preserved': True,
          'sync0_selection': 'after_index_constructor_before_complete_canonical_replay',
          'units_per_arm': 20, 'operations_per_unit': 6, 'engine_runs': 0,
          'scope_limit': 'Uncontended journal-only diagnostic; no HTTP/editor/campaign or S80 causal proof.'})


if __name__ == '__main__':
    main()
