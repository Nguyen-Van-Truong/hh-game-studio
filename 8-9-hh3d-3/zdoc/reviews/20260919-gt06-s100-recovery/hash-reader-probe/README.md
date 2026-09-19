# Streaming journal reader diagnostic

This packet is diagnostic only: `formal_acceptance=false`, `eligible_for_dataset=false`.
No engine, runtime edits, acceptance changes, full-file byte loading, memory mapping,
or retained history byte cache was used. The original S98 journal was opened read-only.
Each measured arm opened only `commands.copy.jsonl` with `r+b`, streamed the complete
file through SHA-512, checked full size and identity, then called the unchanged
`flush()` and `os.fsync()` separately. Original and copy SHA-256/SHA-512 matched before
and after each run.

Input: 17,761,123 bytes. SHA-256:
`91e593b3df4fae95efceebf47ff9e629004a4a6f9e21aed459b3cf48cff9ca19`.

Both runs use five arms, five repetitions each, and rotations that put each arm in
every ordinal position. The confirmation reverses arm order and includes buffer
allocation in timing. Five observations are too few for a tail estimate: reported
nearest-rank p95 is the maximum of five, not a production percentile.

| Arm | First hash/read median / max, ms | Allocation-inclusive median / max, ms |
| --- | ---: | ---: |
| read 64 KiB (existing) | 29.3483 / 30.3498 | 29.6714 / 31.0990 |
| read 256 KiB | 33.0581 / 34.6258 | 30.2738 / 33.7769 |
| read 1 MiB | 32.2736 / 33.7671 | 31.8191 / 32.6572 |
| readinto 256 KiB | 27.7440 / 35.3496 | 27.3760 / 28.9375 |
| readinto 1 MiB | 27.2058 / 28.3514 | 27.3801 / 28.6888 |

The narrowly supported candidate is a bounded local 1 MiB bytearray/memoryview
used repeatedly with `readinto` inside `_snapshot`. Its hash/read median improved
7.30% in the first run and 7.72% when allocation was included. Both maxima also
improved. Increasing ordinary `read` buffers was slower here. The 256 KiB readinto
arm had an adverse first-run maximum. Fsync was still performed on every sample;
first-run fsync max was 1.1468 ms, confirmation max was 0.1985 ms.

This is a warm-OS-cache single-process measurement. It excludes host locks,
SQLite transactions, transport, concurrent worker scheduling and coupled native
load. It does not reproduce the S98 two-second timeout, explain that event, or
justify a claim that a buffer change fixes it. Expected benefit is only roughly
2.2 ms per full verification of this 17.8 MB history; asymptotic scaling remains.

Recommendation: keep runtime unchanged while the instrumented HTTP baseline and
the separate import probe establish where time is spent. A roughly 2 ms snapshot
gain alone does not justify invalidating the frozen closure and reminting a full
campaign to chase a two-second outlier. The source change becomes better justified
if phase evidence shows that repeated hash scans materially dominate the affected
critical section or sustained workload cost. No campaign-ready claim follows here.

Memory consideration: a local 1 MiB buffer is bounded and contains only scratch
bytes, but it is larger than the current 64 KiB chunks. Python/CRT allocators may
retain released pages; leaving local scope does not guarantee RSS returns to its
initial value. An owner-retained buffer makes an explicit additional 1 MiB live
allocation. The probe did not measure RSS and cannot establish neutrality under
the existing baseline/plateau gate. Keep the existing RSS limits and sampling
points unchanged; validate the chosen buffer lifetime on the actual host before
promotion. Per-snapshot allocation was included in the second timing run only.

## Static mechanism

- `studio/tests/replay/benchmark_commands.py:39` selects `VerifiedJournal`.
- `studio/host/core/journal.py:271` reloads before every decorated operation.
- `studio/host/replay/verified_journal.py:166` invokes full `_snapshot` even for
  unchanged history. Lines 112–127 read/hash every byte and retain recovery fsync.
- `studio/host/core/transport.py:551` serializes dispatch through the host RLock.
  Worker apply/readback at lines 754 and 803 uses the same lock. A lookup can wait
  for worker verification and durable finish, then perform its own verification.
- An ordinary admitted command performs at least six full snapshots: existing-ID
  lookup, lease validation, pending append, lease guard, terminal append and
  terminal lookup. Inspect performs at least four; polling adds more. Rejected
  invalid-payload commands fail before journal access. These per-command scans
  make total work grow approximately quadratically with retained command history.
- `studio/host/replay/disk_journal_index.py:79` uses synchronous FULL and line 87
  uses DELETE journaling. Each local authoritative append wraps one index
  transaction (`verified_journal.py:189`); no ordinary whole-table scan appears in
  indexed command lookup. Changing this durability setting was not evaluated.
- `studio/host/core/transport.py:858` fixes the normal client timeout at two seconds.
  `studio/tests/replay/benchmark_transport.py:74` waits for the response headers;
  a timeout at this stage does not identify which server phase was delayed.

## Candidate boundary and required verification

Only replace the `_snapshot` streaming loop. Allocate a local fixed bytearray and
memoryview; repeatedly `readinto(view[:min(capacity, max_bytes - size + 1)])`, hash
only `view[:count]`, preserve the existing size increment and limit failure, and
leave fstat identity checks, SHA-512 matching, SHA-256 record validation, cache
poisoning, parsing precedence and `flush/fsync` unchanged. No skipping snapshots,
mtime trust, dedupe changes, receipt changes, timeout changes or larger limits.

If implemented, verify at least:

1. Existing `test_verified_journal.py`, disk-index tests and relevant protocol
   journal corruption/durability tests, preserving exact responses and errors.
2. Digest parity for empty, sub-buffer, exactly-buffer, buffer-plus-one and
   multi-buffer histories; include partial/short `readinto` returns.
3. Same-length same-mtime corruption at the beginning, middle and final chunk;
   external append/replacement/truncation; max-bytes boundary and growth past it.
4. Read failure and fsync failure retain existing error code, UNKNOWN provenance
   and poisoned-cache behavior; no fsync moves or skips.
5. A bounded host diagnostic after source freeze, then fresh required coupled
   evidence and two independent critics before any GT-06 acceptance claim.

## Reproduction and host observation

Using the installed `C:/Users/truon/AppData/Local/Programs/Python/Python311/python.exe`:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/hash-reader-probe/probe.py
python -B 8-9-hh3d-3/zdoc/reviews/20260919-gt06-s100-recovery/hash-reader-probe/probe_allocation_inclusive.py
```

Scripts create exclusive output files and intentionally refuse overwriting.
First run: exec_command chunk `3ecad6`, actual exit 0, internal duration
1.4154174 seconds. Confirmation: chunk `05d387`, actual exit 0, internal duration
1.0262209 seconds. These are diagnostic tool observations, not formal benchmark
owner receipts. Raw rows and all digests are in the two result JSON files.

The copied 17.8 MB journal is a disposable diagnostic artifact, not runtime source.
