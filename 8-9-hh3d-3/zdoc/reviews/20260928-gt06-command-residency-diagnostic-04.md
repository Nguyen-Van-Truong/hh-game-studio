# GT-06 command-residency diagnostic 04 — repair verification — 2026-09-28

`AUTHORITY=0`; this is a command-only diagnosis, not formal GT-06 acceptance.
It used the repaired source closure
`10e705b3574cb34cd360db81d8e87047e521e193ecc9404cfa9de622f36468e3` after
commit `a746a3a6` (`HH3D: remove duplicate journal reload on submit`).

The demand-only Scheduler run `gt06-status-gap-diagnostic-04` completed all 35
1,000-command batches on one resident host process. Independent verification
validated every batch schema, source copy, host identity and summary, for
35,000 commands and 7,000 mock-fixture effects. The maximum command-lane
status gap was `1013.0454 ms`, below the unchanged O1 `2000 ms` boundary. The
measured inspect p95 was `289.38225 ms`; the largest per-batch diagnostic p95
was `583.1046249999997 ms`.

The actual child exit and wrapper exit were both 0. Scheduler status was Ready,
`LastTaskResult=0`, with no instances. The captured Job was configured,
assigned, closed, untainted, zero-active and zero-observed; the process handle
was closed and not retained; the process tree exited naturally. The source
freeze remained unchanged throughout. Raw evidence is retained under
`studio/.local/reviews/gt06-status-gap-diagnostic-04/` and its supervisor
directory; the machine-verifiable closeout is under
`studio/.local/reviews/gt06-residency04-closeout-20260928/verification.json`.

This result supports the journal-submit repair as the cause of the earlier
command-only status-gap reproduction, but it does not prove the Godot/editor
pair, counters, memory, native ACK, or the two-pair formal gate. It does not
authorize a tick, reuse any terminal campaign ID, or change O1/O4 thresholds.
The next action is a fresh O4.1 preflight followed by a new formal campaign ID.
