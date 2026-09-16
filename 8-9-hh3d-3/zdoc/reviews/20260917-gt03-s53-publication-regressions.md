# S53 scene save and Stop regressions

AUTHORITY=0. Native implementation evidence, not an independent acceptance
review. No runtime or runner source was changed during these regressions.

Both runs use frozen closure
`31a66517322bc57665aa316c53a88686ee27037a38ff055b1744327ad2464cec`, matching
the S53 script publication run. Origin and snapshot source remained unchanged.

| Run | Checks | Actual child/wrapper | Native editor |
| --- | --- | --- | --- |
| `20260917-gt03-s53-publication-01` | 17/17 | PID37520/PID16308, exit0/0 | PID17200 exit0, Job closed/zero |
| `20260917-gt03-s53-stop-01` | 19/19 | PID25164/PID13944, exit0/0 | PID5140 exit0, Job closed/zero |

Both owned runs finished without timeout and verified their process tree.
Native editor Jobs had no retained handles, taint, uncertain closure or failed
operations. The scene-only save still captures the dirty scene, validates it,
selects the complete bundle, reloads within the same editor, commits durably,
deduplicates replies and reopens v4 storage read-only.

The Stop run independently observed the exact owned Linux validator container
`hh-gt03-fc9298c1f5e047868695ba0c7c2d5db6` running before sending the control
request. Native execution lasted from `2026-09-16T20:50:32.944276236Z` through
`2026-09-16T20:50:41.918384451Z`. Stop completed inside that interval and before
the registered validator method returned. Epoch timestamps show 3 ms elapsed;
the monotonic metric rounded to 0.0 ms, which is not a zero-latency guarantee.

Validation subsequently exited cleanly and its owned container was removed.
The command retained durable `UNKNOWN`/`public_ack=false` before any native
stage, selector or adoption event. Exact selected bytes/identity, native content
names and the dirty editor root/semantic state remained unchanged. Authenticated
lookup returned the original UNKNOWN response. Read-only v4 reopen preserved
that outcome and the original selected bundle.

Linux lanes ran sequentially. This lane released its serialized slot after
actual host completion; no new baseline was needed because runtime bytes did
not change.
