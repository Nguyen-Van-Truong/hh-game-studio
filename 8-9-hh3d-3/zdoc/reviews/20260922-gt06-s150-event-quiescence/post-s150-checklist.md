# Post-S150 GT-06 checklist

Read-only checklist against the S150 plan state. S150 is an `AUTHORITY=0`
host-only attribution follow-up; it cannot close GT-06 or count toward F13/F14.

## Required when S150 reaches terminal

- [ ] Seal the fresh supervisor/child packet before interpretation. Preserve the
  terminal receipt, raw commands, batch-9 failure row, immediate checkpoint,
  `09-quiet` checkpoint, both PSS censuses, phase output, stdout/stderr, and
  all-attempts history under the new IDs. Verify a canonical relative-path
  manifest and per-file hashes; do not overwrite S149 or repair raw files.
- [ ] Bind both PSS observations to the same target PID, process start, and
  executable. Require `OBSERVED`, complete type counts/entries, released
  marker/snapshot/process resources, and no identity or cleanup uncertainty.
- [ ] Read actual target, helper, and wrapper exits separately. Verify Job
  active count zero/closed/untainted, owned tree zero, retained probe/wrapper
  handles released, child producer/journal closed, no live threads, and source
  unchanged. A clean failure is still a diagnostic failure.
- [ ] Compare immediate versus 250 ms quiet samples at the same batch-9
  boundary. Record Event aggregate and redacted row deltas, phase/unfinished
  spans, sample timestamps, and the effect of the zero-duration scheduler
  yield. Keep the original retained-counter gate and status/RSS samples.
- [ ] Treat `Event` persistence as descriptor-class evidence only. Numeric slot
  reuse, unavailable names, or `object_identity=UNKNOWN` do not establish
  ownership or a leak. The host-only run omits native/ACK/idle/assembly and is
  therefore not formal coverage.

## Decision gate after the comparison

- [ ] If the Event disappears after quieting, record deferred thread/sync
  cleanup and preserve S149's failure; do not edit runtime source or loop
  diagnostics.
- [ ] If the Event persists, require new ownership evidence before preparing a
  repair candidate. Any repair must be narrow, keep all gates/profile/timeouts
  unchanged, and have focused regressions plus a fresh source freeze/hash.
- [ ] If either census is `UNKNOWN`, exits are missing, identity is mismatched,
  or cleanup is uncertain, stop interpretation and retain the raw gap.
- [ ] In all branches, keep S149/S150 outside F13/F14 and do not launch a blind
  formal retry. A scheduler state or PASS field cannot replace terminal exits.

## GT-06 remains open until the formal campaign

- [ ] Freeze the exact post-decision source/runtime/profile/binary closure and
  mint fresh formal IDs. Do not reuse diagnostic or failed formal evidence.
- [ ] Run the unchanged requirement: ten fresh host/editor pairs × 35 batches
  (0–4 warmup, 5–34 measured), 1000 HTTP commands + 100 native cycles per
  batch, same PID, original ready/start/joint/ACK/Stop path.
- [ ] Verify every measured sample against the locked batch-4 baseline without
  rebaseline or subtracting observer cost; any over-baseline required counter,
  missing counter, unknown exit, or partial attempt fails the dataset.
- [ ] Seal complete raw/hash/schema/limits/actual-exit/cleanup evidence and a
  requirement→test→artifact map, then obtain two independent critics with
  `PASS` and `TICK=yes` on the same final frozen hash. Only coordinator
  acceptance after those signatures can open GT-07.

## Current concrete gaps

As of the S150 dispatch, the plan still reports zero accepted full GT-06 runs,
formal RSS/freeze/dataset closure open, and no final critics. The plan's prose
also contains an older “S148” progress line beneath the S150 header; it should
be reconciled from the sealed S150 raw packet after terminal, without changing
the acceptance gate.
