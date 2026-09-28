# GT-06 status-gap journal diagnostic — 2026-09-28

`AUTHORITY=0`; this is a controlled diagnosis, not a formal campaign and not
acceptance evidence.

The retained batch-17 journal from `gt06-o4-formal-03` was copied to a separate
diagnostic directory. The original raw evidence and the source tree were not
modified. The copied journal was loaded through the production
`VerifiedJournal` path, then exercised with twelve lookups and six appends under
`cProfile`.

Observed measurements:

- journal SHA256: `42badf40e013ecdae171b22ae31210bd079ed60d39506856e4f74e75a57ffb01`
- size: 17,609,707 bytes
- full load and verification: 11,148.87 ms
- later lookups: approximately 38–48 ms each
- appends: approximately 43–45 ms each
- profile: reload/snapshot/read-verify dominated; 155,000 hash updates were
  recorded across the exercised operations
- copied journal closed cleanly and the original journal remained unchanged

The full load cost is a plausible contributor to the 6,432.487 ms native
status gap in formal03, especially if a reload or cache invalidation occurred
inside the batch. It does **not** prove that the journal caused the gap: the
diagnostic did not run Godot, did not reproduce the barrier, and did not
attribute host CPU pressure. The formal03 verdict therefore remains
`PRODUCT_FAIL`, with O1 thresholds and timeouts unchanged.

Diagnostic outputs are retained under
`studio/.local/reviews/gt06-formal03-journal-probe-01/`:
`result.json`, `profile.txt`, and `outer-exit.json` (actual exit 0). No raw
formal evidence was overwritten and no campaign was resumed.

Next action is a command-only residency measurement with a fresh diagnostic ID
to separate command-lane/journal cost from the native editor heartbeat. A fresh
O4.1 preflight is still required before any new formal campaign; no formal
campaign is dispatched from this diagnosis.
