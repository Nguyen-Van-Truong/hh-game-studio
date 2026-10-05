# GT-06 command-residency diagnostic 01 — 2026-09-28

`AUTHORITY=0`; this is a command-only scaling diagnosis, not a formal
campaign and not acceptance evidence. It used source closure
`e1602694a55e617ec5e9e27d9c659c813759514b90c4f9e9a4d960cb874f0dbd`.

The resident loop completed three full 1,000-command batches and failed during
batch 3. The completed command-only batch gaps were 681.30 ms, 931.00 ms, and
808.41 ms. In the partial fourth batch the command lane reached
`max_status_gap_ms=2015.6922` and a lookup timed out at 2002.7916 ms during
`getresponse`. The wrapper classified the failure as `HOST_DIAGNOSTICS` after
that lookup timeout. The partial command row records `CONNECTION_LOST_LOOKUP`,
`getresponse`, and 2002.7916 ms; the subsequent diagnostic guard saw an
unexpected host diagnostic. This old run did not persist the host diagnostic
ring, so its exact code is unavailable and must not be guessed as
`INVALID_FIXTURE_PAYLOAD`.

The wrapper recorded actual child exit 1, closed its Job, observed zero active
handles/tree entries, and retained the partial raw batch. No Godot or Blender
process ran. Because this run predates the failure-artifact repair, it has no
phase-window artifact; the raw command rows, `failure.json`, `owner-failure.json`
and cleanup records remain unchanged under
`studio/.local/reviews/gt06-status-gap-diagnostic-01/`.

This independently reproduces the O1 two-second command-lane boundary without
the native editor. It strengthens the status-gap diagnosis, but does not prove
whether journal verification, loopback scheduling, fixture worker contention,
or host pressure is the root cause. It does not authorize changing O1 or
starting formal03 again. Diagnostic-02 uses a fresh source closure and the
repaired runner, which persists bounded phase and diagnostic artifacts on both
success and failure.
