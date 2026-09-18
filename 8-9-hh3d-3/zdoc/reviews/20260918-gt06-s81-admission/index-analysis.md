# S81 journal/index investigation — diagnostic only

AUTHORITY=0; GT-06 remains open. No runtime source, limit, timeout, original
evidence, plan, or acceptance marker was changed by this lane. This report does
not identify the exact S80 latency source and does not claim benchmark PASS.

## Finding

The retained evidence demonstrates a client response timeout, not a configured
journal/index capacity boundary. The disposable SQLite index has no surviving
file to inspect: normal cleanup removed all `.hh-index-*`/`*.sqlite*` entries in
the S80 run root. No original database was opened, repaired, or rebuilt.

The smallest safety-justifiable index optimization is changing only its
`synchronous=2` to `synchronous=0`, keeping `journal_mode=DELETE`, transaction
rollback, cache/page limits, canonical journal fsync, and never reopening an old
index. The copied-history A/B did **not** establish an overall latency gain, so
this is not a supported standalone S80 fix. Keep it a candidate until a
coordinator decision; preserve UNKNOWN and do not extend response timeouts.

## Raw evidence

Run: `gt06-s80-campaign-01.r00.a01`, frozen source checkpoint `f75a5d08`.
Workspace HEAD when inspection began: `d8da8a21d22d415e097bef884d6056942a0fe719`.

- `child-failure.json`: `ADMISSION_UNKNOWN`, batch 15 after 15 complete batches.
  Last command `gt06-s80-campaign-01.r00.a01.b15.inspect.400` returned
  `UNKNOWN/CONNECTION_LOST_LOOKUP` in 2003.3888 ms; no lookup attempt follows.
- `commands/commands.jsonl`: 15,586,409 bytes, 22,170 records, 11,077 unique
  command IDs, 16 leases. Pure JSON parsing independently matched all 22,170
  record SHA-256 checksums. This is not a replacement for the accepted parser.
- Command rows: 11,077 ACCEPTED_PENDING, 11,060 COMMITTED, 17 CANCELED.
  Maximum pending cardinality reconstructed from the history is 1; final is 0.
- The failed command is line 22,169, offset 15,585,123, pending row 635 bytes;
  line 22,170 at offset 15,585,758 is its 651-byte CANCELED_BEFORE_APPLY row.
  Raw pending/cleanup evidence cannot allocate the original latency among locks,
  hashing, filesystem synchronization, scheduler delay, or SQLite.
- Journal SHA-256 before and after inspection/probe:
  `4d8ecb5bacd76a57d3137e9f812c36c3a6a759d4d51d41008627e9114ee1377a`.
- Failure JSON SHA-256:
  `9ea461e39d74924e3a3f42044e7c00fd2525220ec7b3ae277648ceb6f79aad25`.

`JournalLimits` caps are 64 MiB, 100,000 records, and 1,024 pending commands;
reserved terminal capacity remains 256 KiB per pending command. At the failed
admission, the pending row plus its reservation totals 15,847,902 bytes and
22,170 reserved record slots, both comfortably below their caps. No evidence
supports raising them. Each completed batch adds 1,403 rows; the same mix over
35 batches projects 49,105 rows. At the largest observed line size (778 bytes),
that shape would use at most 38,203,690 bytes before terminal reservation. The
projection assumes the same record shape and is not a guarantee for other jobs.

Pure parsing of the 15 completed batch artifacts shows accepted-command receipt
medians increasing from 16.94 ms (batch 0) to 33.61 (batch 4), 52.06 (batch 9),
and 72.51 (batch 14). Host command batch duration increases 40.72 s to 124.68 s.
This is consistent with growing verification work, but the original artifacts
contain no journal-phase spans sufficient to prove the timeout's cause.

## Exact code boundaries

All four live files matched their frozen S80 copies at initial inspection:
`host/core/journal.py`, `host/core/limits.py`, `host/replay/verified_journal.py`,
and `host/replay/disk_journal_index.py`. Exact hashes are in the JSON companion.

- `disk_journal_index.py:74–96` creates a new random private SQLite database,
  sets synchronous FULL (2), DELETE rollback journal, 256 KiB page cache,
  mmap=0 and temp_store=FILE. The old index is never reopened (`:57`).
- `disk_journal_index.py:140–162` preserves BEGIN/COMMIT/ROLLBACK and poisons
  the index if rollback cannot be confirmed. Do not use journal_mode=OFF.
- `verified_journal.py:102–134` reads and SHA-512 hashes the complete regular,
  single-link JSONL file for every operation, and performs the recovery fsync
  before trusting a matching fingerprint. This protects same-length/mtime
  corruption, replacement and external append; it must remain effective.
- `verified_journal.py:180–210` wraps the authoritative append in a disposable
  index transaction. An index failure after the JSONL fsync remains UNKNOWN;
  the poisoned fingerprint forces accepted replay on the next operation.
- `journal.py:399–423` reserves terminal capacity, appends and fsyncs JSONL,
  then updates derived state. Those durability and refusal rules are unchanged.
- The measured caller is `LoopbackFixtureHost`, not `ReplayService`.
  `transport.py:630–679` may verify history for existing-command lookup,
  lease check on mutation, and pending append. Their costs are cumulative
  within a request; this probe isolates journal work without HTTP/lock contention.

## Authorized copied-history A/B

Files: `index-probe/probe.py`, `run_probe.py`, `host.json`, `result.json`, and
four `arm-*/result.json` files. The four copied JSONL files are local diagnostic
inputs/outputs, not new authority and not runtime source.

Coordinator authorized this diagnostic only after original host/editor cleanup
was confirmed. Child PID 26932 exited 0 in 65.33 s, within its 180 s bound;
stderr is empty. No engine, full campaign, or unit test suite was launched.
The child has no descendants and was observed exited through its retained
process handle.

The probe imported frozen S80 modules, then substituted an owned diagnostic
index subclass. It selected synchronous 2,0,0,2 after each brand-new index
constructor but before complete replay. DELETE, cache=256 KiB, mmap=0,
temp_store=FILE, full JSONL hashing and canonical fsync remained unchanged.
Each arm copied the identical 15.6 MB JSONL, reconstructed its own index, and
performed 20 identical units of six operations: original receipt lookup,
pending append, pending lookup, finish, terminal lookup, duplicate append.
Original IDs were not resubmitted for mutation. New IDs, timestamps and receipt
bodies matched across arms, within the existing retry horizon.

| Policy | Operations | Total | p50 / p95 / max per operation | Snapshot incl. recovery fsync | SQLite COMMIT |
|---|---:|---:|---:|---:|---:|
| FULL 2, two arms | 240 | 8732.02 ms | 33.649 / 54.514 / 87.784 ms | 7299.69 ms (83.60%) | 211.44 ms |
| OFF 0, two arms | 240 | 8874.82 ms | 33.666 / 59.711 / 120.629 ms | 7540.22 ms (84.96%) | 33.32 ms |

Both policies made 320 canonical fsync calls and 80 SQLite COMMIT calls.
COMMIT cost fell about 84%, but its original share was only 2.42% of overall
operation time. The total OFF arm time is 1.64% greater in this small sample;
this is not a statistically established regression or improvement. The
two-second S80 condition was not reproduced.

Phase totals overlap: snapshot includes recovery fsync; SQLite execution
includes COMMIT; total canonical fsync also includes append fsync. Do not add
these columns as mutually exclusive spans. Rebuild/init times were separately
11.32–12.02 s and excluded from steady operation totals.

All receipt, replay, pending and count assertions held. Each arm ended at 22,210
records with zero pending commands, and all four resulting JSONL files have
identical SHA-256 `7838da7671fe4fe34a73795440de698c15be1b7b69bfe61de7737894dcc56a5e`.
All four index owners closed and removed their private index directories.
Original journal bytes, original index inventory and frozen source hashes
were rechecked unchanged at completion. These are bounded diagnostic results,
not a conformance or acceptance verdict.

## Recommendation and regression obligations

Do not present an index-capacity fix or a confirmed root cause. Preserve the
failed campaign and the existing UNKNOWN receipt. Full-history verification
accounts for most uncontended work in this probe, so the next narrow diagnostic
should attribute complete LoopbackFixtureHost request spans, including its
repeated verifications and lock waits. Any future consolidation of verification
must keep one continuous accepted cross-process writer guard and exact-byte
validation; caching by mtime/size or bypassing recovery fsync would change the
accepted safety boundary.

If the coordinator independently chooses the small sync=0 optimization,
the justification is that this database is disposable and never reopens;
power-loss corruption can affect only an abandoned derived index. SQLite's
[synchronous documentation](https://www.sqlite.org/pragma.html#pragma_synchronous)
allows OFF for reproducible scratch databases while documenting its power-loss
risk. The [journal-mode documentation](https://www.sqlite.org/pragma.html#pragma_journal_mode)
explains why OFF is unsuitable when rollback is required. Preserve DELETE;
do not trade bounded cache memory for an unbounded in-memory database.

Required focused regressions before any source acceptance:

1. Read back sync=0 and DELETE with unchanged page/cache/mmap/temp settings;
   reject unsupported settings. Assert canonical JSONL fsync before receipt.
2. Keep existing index COMMIT-after-fsync, cursor-close, rebuild and cleanup
   failure tests: UNKNOWN, poisoned generation, exact replay and no duplicate
   effect/append. Failed close must retain its cleanup owner.
3. Exercise actual SQLite rollback of row and metadata changes, including
   nested transactions and failure before/after canonical append. Mode changes
   must not introduce partial derived state.
4. Leave a stale/corrupt scratch index after a bounded child crash and prove a
   new journal creates a fresh index, fully validates and fsyncs canonical
   history before exposing receipts; never reopen the stale index.
5. Retain same-length/mtime corruption, truncated tail, external writer,
   replacement, expiry/tombstone, dedupe and exact capacity/pending-reservation
   tests. No larger limits or altered refusal/outcome_unknown semantics.
6. Recheck the actual command host's uncertain-admission/no-effect/retry lookup
   behavior and owned shutdown. Journal-only timings cannot prove that path or
   substitute for the required full campaign and independent critics.

No commit was made: this worker owns analysis and diagnostic artifacts only;
the coordinator owns integration and acceptance decisions.
