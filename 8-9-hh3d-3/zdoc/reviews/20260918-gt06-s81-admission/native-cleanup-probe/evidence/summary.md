# Completed supplemental native cleanup smoke

AUTHORITY=0. This packet preserves one real cleanup smoke, not a benchmark PASS, GT-06 acceptance, critic verdict, command-effect proof or campaign completion.

The real child reached native READY at batch 0, then its first command-batch call deliberately raised `CommandError(S81_EXPECTED_CLEANUP_SMOKE)` from the original `RuntimeError("fixed synthetic cleanup stimulus")`. Zero command batches, native batches and effects are claimed. The original `child-failure.json` remains failed with zero completed batches; no child success or batch result exists. The hash-bound driver checked original exception/cause identity in process before reporting `CLEANUP_SMOKE_VERIFIED` and returning 0. Offline collection verified its preserved bytes, receipts, bindings and recorded outcome; it does not independently recreate historical object identity.

| Process | Actual target result | Separate helper result |
| --- | --- | --- |
| Outer diagnostic observer | PID 14112, exit 0 | exit 0; PID not recorded |
| Pinned import | PID 34944, exit 0 | exit 0; PID not recorded |
| Real editor | PID 18744; actual/natural exit **null**, no exit receipt | PID 33296, exit 2 after forced cleanup |

The coordinator reported root shell exit 0; this raw directory contains no independent shell receipt. That reported value is not substituted for any target or helper exit. The child terminal record leaves its own host/supervisor exits null because those were unobservable from inside the child; the outer target exit is independently present in `probe-owner/process-exit.json`.

The outer observer and import captures show natural tree termination. Outer/editor/import Jobs each recorded active count 0, zero observed and closed, without retained/tainted/uncertain state. Outer/editor wrapper handles were recorded released. Import capture has no separate wrapper-handle receipt, so that observation remains unavailable. Editor cleanup remains `completed=false`, `BENCHMARK_CLOSED_BEFORE_FINISH`; the outer post-close cleanup receipt also uses `completed=false`, while its independently bound capture records actual observer completion.

The persisted terminal artifact matches the retained-object observations after original cleanup: heartbeat and editor drain threads stopped; three host threads stopped; both listeners at fileno -1; producer closed/failed; host/editor probe handles released without uncertainty; journal cache closed and index detached; retained SQLite index object's DB and directory handles released; held owner/probe counts zero. Terminal cleanup errors are empty. The PID presence snapshot found 0 of the four known target/helper PIDs present at collection. Absence does not synthesize missing exit bytes.

Raw inventory: **132 files / 10,056,822 bytes**, streamed twice with matching content/size/mtime and unchanged membership. Portable exact copies: **99 files / 949,428 bytes**. Inventory includes all generated cache bytes; copies exclude `.godot`, isolated-user generated caches, binaries and the generated benchmark UID. Initial project file hashes all remain equal because no command or native batch ran. **21 artifact references** were independently checked against bytes; stderr is empty for all three logged lanes, with no warning/error/leak/failure marker in their stdout.

Runtime source: **51 files**, closure `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`. Execution source plus probe driver: **52 files**, closure `ff0246d4629395aefe7962c624d2bb51140ecf1a6658db72ad1c034a79f7b840`. All frozen source copies, request/context/capture maps and current execution files agree before/after collection. Profile SHA-256 is `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. The observed interval was 13.797s under the 120s supplemental watchdog.

No unexpected collection mismatch was found. Missing target/helper identity details and the absent import wrapper-handle receipt above are explicit evidence limits. No source/raw files, engine processes, tests or scheduled tasks were changed by this collector.

See `raw-inventory.json`, `selected-manifest.json`, `verification.json`, `known-process-observation.json` and the byte-for-byte `copies/` tree. `package-manifest.json` seals all packet files except itself.
