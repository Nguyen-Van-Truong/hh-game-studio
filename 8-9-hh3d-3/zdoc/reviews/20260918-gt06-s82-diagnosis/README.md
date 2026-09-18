# S82 ObjectDB owner diagnosis

`AUTHORITY=0`; diagnostic only, no GT-06 acceptance and no campaign retry
permission. This probe ran the frozen benchmark fixture in a disposable copy,
with 6 batches × 100 native cycles and 120 seconds of idle owner sampling.
It used source closure computed by the runner and did not edit production source,
profile, thresholds, or transport.

The result reported native exit 0, wrapper exit 0, Job zero/closed, no retained
handles, and `source_unchanged=true`. All 25 snapshots held the same ObjectDB
count after the initial inventory; no added/removed objects appeared during the
cycles or idle window. This isolates the create→undo→save→reload cycle from the
persistent +2 observed in S81 full campaign batch 15.

It does not reproduce the host-commands-before-native sequence, so it cannot
identify the S81 owner yet. A second bounded 16-batch native-only probe is
running in `gt06-s82-object-diagnostic-long-01`; its output remains raw until
terminal cleanup and hashes are verified. Do not subtract counters, relax the
gate, or use this diagnostic as a PASS.

Files copied here are exact summaries only; the complete disposable raw tree
remains under `studio/.local/reviews/gt06-s82-object-diagnostic-01`.
