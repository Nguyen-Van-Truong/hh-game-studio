# GT-06 command-residency diagnostic 03 — status-gap phase evidence — 2026-09-28

`AUTHORITY=0`; this is a bounded command-only diagnosis, not a formal GT-06
campaign and not acceptance evidence. It used the frozen diagnostic source
closure `d9159b2c1173d088b89665f196c82c99765953b15672c9a42e4bedbbb90ba3e6`.

The demand-only Scheduler run `gt06-status-gap-diagnostic-03` completed 14
full 1,000-command batches (indices 0–13) and failed in batch 14. The partial
batch reached `max_status_gap_ms=2018.9652` on
`gt06-status-gap-diagnostic-03.b14.admitted.158`; the lookup client timeout was
about 2010.68 ms. The wrapper recorded `HOST_DIAGNOSTICS`, actual child exit 1,
Scheduler `LastTaskResult=1`, a closed Job with zero owned tree/handles, and no
Godot or Blender process. Raw artifacts remain under
`studio/.local/reviews/gt06-status-gap-diagnostic-03/`.

The persisted phase window narrows the boundary to concurrent journal work:
`server.dispatch` peaked at 3501.358 ms, `server.handle` at 3507.2235 ms,
`journal.guard_held` at 2376.7469 ms, `journal.append` at 1525.1169 ms, and
the lookup snapshot phase at 2028.37 ms (lookup server phase 3419.97 ms).
There were no `journal.load` events in this window. Command submission and
lookup were contending for the journal writer lock while hashing/replaying the
history; before the repair, `_submit` performed a separate `_existing` lookup
and then `append_command`, duplicating that reload/hash path.

The repair is committed as `a746a3a6` (`HH3D: remove duplicate journal reload
on submit`). `append_command` now owns the authoritative dedupe/conflict check,
runs new-request preflight only after that check, and `_submit` does not enqueue
a replay. An orphan durable pending row is returned as
`UNKNOWN/RECOVERY_REQUIRED`; a published live pending job still returns its
original pending receipt. The focused 74-test suite and an additional 117-test
journal/recovery suite both pass. This repair does not change O1 thresholds,
timeouts, watchdog rules, or formal acceptance requirements.

The phase evidence supports testing this proven contention boundary with a
fresh residency ID, but it does not prove that no other host pressure exists.
Do not resume run03, reuse its ID, or call it a PASS.
