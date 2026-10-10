# O2 authoring state — 2026-10-10 (O13/S284)

AUTHORITY=0; GT09=IN_PROGRESS; no public gameplay-source or acceptance claim.
Source-of-truth plan: `zdoc/8-9-godot-blender-agent-studio-plan.txt` S284.
Current WIP is the runner/process-boundary repair plus the K13 native adapter
receipt hardening; the 12-CPU Docker quota repair is already measured. Commit
`8d50949c` pins the final runner to measured K13 v3. Commit `69da19c3`
repairs verify-only's K5/K7 fixture-envelope reconstruction. Rehearsal
`gt09-rehearsal-20261010-27` passed K3 on closure
`sha256:3fb5fb70a0cca863f36895cee0940c6f8958094d58cf684250bd3dd33b02bc3b`.
Final -52 stopped at K3 on a Docker attach timeout (raw preserved); exact
reproducer `gt09-registered-script-k3-repro-20261010-53` passed. Final -54
passed K1–K15 with host exit 0, then verify-only found only the K5/K7 validator
gap now repaired; it is historical because the source hash changed.
Final closure is computed by `run_gt09_matrix.py` and excludes `.local` and caches.
GT08A remains accepted; GT08B Android remains deferred by owner.
K1–K9 and K11–K14 have diagnostic implementations/evidence, but no final row
is accepted until one frozen K1–K15 run and two independent critics share its hash.
Earlier final attempts are historical; -04 had source drift, -05 had
watchdog parser failures, and -06 was stopped after schema/closure failures.
Human playtest remains NOT_PERFORMED and authority stays 0. Next action is a
fresh K3 rehearsal on the repaired verifier, then one final through the
demand-only Scheduled Task with no writers running.
A delegated room
probe `gt09-playtest-20261009-03` passed on its own frozen publication with
901.003 seconds, actual Godot exit 0, lifecycle_complete=true, all scripted
transitions and freeze_errors=0; it is diagnostic until a fresh final matrix.
Final `gt09-matrix-final-20261009-22` stopped at K7 because the wall probe child
exited before writing `result.json`; raw evidence has no hostile result and is
invalid. Fresh `o2-auth05-native-k7wall-repro-20261009-01` passed with two
native calls and unchanged source, so this is retained as a transient Docker/
CLI boundary; no deadline or hostile acceptance rule was changed.
Final `gt09-matrix-final-20261009-23` reported PASS K1–K15, but the required
verify-only self-check rejected K6 because its persisted row contained only a
unit step. This was a runner/verifier gap, not acceptance; K6 now records a
native durable-publication step and `_write_row` serializes evidence types
before hashing. Fresh `-24` reached K1–K14 and its room native Godot capture
exited 0 with Job/tree zero, but the outer room host ended 1 without
`host-result.json`; it is retained as INFRA and cannot be combined. A
demand-only GT09 Scheduled Task launcher now pins source closure and records
task/supervisor start, terminal and delete receipts; fresh final is required.

Final `gt09-matrix-final-20261009-27` stopped at K1 with
`CONTENT_DEADLINE_OR_LOG_CAP`; the native Blender output had valid partial
artifacts but no process-exit receipt. Sixteen sequential diagnostic content
runs measured one cold timeout and successful host walls up to 23.596 s, so
the bounded producer watchdog is now 30 s (p95 plus margin); raw measurement
is under `.local/reviews/gt09-content-deadline-measure-20261009`.

Final `gt09-matrix-final-20261009-30` stopped at K1 with the same content
deadline shape after Blender had written durable partial artifacts but before
the transcript/process-exit. A controlled comparison now has ten sequential
cap-15 passes and ten cap-60 passes, so the content route keeps the generic
15 s CPU cap; `-30` remains an INFRA diagnostic and its raw evidence is not
acceptance evidence.

Final `gt09-matrix-final-20261009-31` passed the content producer and arena
catalog probe, then the room catalog probe returned `CATALOG_RESULT` with
actual exit 1. Its exact room repro
`o2-registered-authoring-k1room-repro-20261009-01` passed on the same frozen
published content, so `-31` is retained as a room host transient and cannot be
combined with later evidence. The `-31` task was observed and deleted with
terminal receipts.

Final `gt09-matrix-final-20261009-32` stopped at K3 in the registered-script
native child after the inner Docker/Godot deadline; its host Job/tree cleanup
was eventually reconciled and it is retained as INFRA. Rehearsal
`gt09-rehearsal-20261009-35` then passed K3 unit plus native replay on the new
closure using the gated outer process runner. It is rehearsal-only. Controlled
quota rehearsals `-42` (2 CPUs) and `-43` (4 CPUs) reproduced the same inner
Docker boundary. With the host reporting 12 logical CPUs, the isolated GT-03
worker quota was raised to 8 CPUs while retaining the 1 GiB, 64-PID, network
none and watchdog limits. `gt09-rehearsal-20261009-44` then passed K3 unit plus
native replay on closure `sha256:0d45ffec5c5544444f9885a4543e7353acfd23979f4a98159285ab3785c37478`;
it remains rehearsal-only, and its raw baseline still records the diagnostic
log/process-clean distinction explicitly.

Final `gt09-matrix-final-20261010-45` reached K3 with the native K3 child
exiting 0, then the registered script's seeded K9 fault behaved as expected
but its repair play child stopped at the authenticated inner supervisor
boundary (`ExitCode=124`, host attach exit 124, 21.094 seconds). The outer
Scheduled Task captured exit 2, the process tree was clean, and the task was
deleted with a terminal receipt. Exact repro
`gt09-registered-script-k3-k9-repro-20261010-45` on the unchanged source
passed with K3 exit 0, expected seed exit 45, repair exit 0 and replay/readback
PASS; `-45` is therefore retained as INFRA and cannot be combined with a later
final.

Final `gt09-matrix-final-20261010-46` passed K1–K6 and all K7 cases through
boundary and spawn, then the busy hostile fixture returned
`BAD_FIXTURE_NOT_OBSERVED` after the host watchdog while retaining clean
ownership/tree receipts. Exact repro
`o2-auth05-native-k7busy-repro-20261010-46` passed on the unchanged source;
`-46` is retained as INFRA and its rows are not combined with another final.

Final `gt09-matrix-final-20261010-47` passed K1–K6, then K7 stopped on the
boundary hostile case with `GAMEPLAY_OWNER_NATIVE_NOT_CLEAN` after the first
good publication. Exact repro
`o2-auth05-native-k7boundary-repro-20261010-47` passed with native run count 2;
`-47` is retained as a second K7 scheduling INFRA run and cannot be combined.

Sequential K7 boundary diagnostics `o2-auth05-native-k7seq-20261010-48` then
ran boundary, spawn, busy and wall in one worker, in that order; all four
returned `DIAGNOSTIC_PASS` with native run count 2 and authority 0. This adds
evidence that the `-46/-47` observations are cumulative scheduling transients,
not a reproducible fixture or acceptance gap. No deadline, watchdog or
acceptance rule was widened at that point; the subsequent -49 attach boundary
provided the new evidence for the separate 12-CPU quota repair below.

Final `gt09-matrix-final-20261010-49` reached K1–K2, then K3's registered
script route hit the authenticated Docker `start --attach` boundary with
actual inner exit 124 after 22 seconds; Scheduler observed outer exit 2 and a
clean process tree. Exact repro
`gt09-registered-script-k3-boundary-repro-20261010-49` passed on the unchanged
8-CPU source, so `-49` is INFRA and its rows are not combined. The controlled
repair raises only the measured worker CPU quota from 8 to 12 (the host's 12
logical CPUs); memory, PID, network, per-process CPU and wall watchdogs remain
unchanged. Executor/guarded/matrix tests pass, and fresh
`gt09-registered-script-k3-cpu12-repro-20261010-50` passes on the changed
source.

Final `gt09-matrix-final-20261009-28` reached K1–K4, then stopped at K5 after
the syntax fixture's Linux/Docker native publication returned actual container
`ExitCode=124` at the authenticated `/usr/bin/timeout 29s` boundary during the
play phase. The container was removed cleanly and the source closure was
unchanged, so this is an INFRA boundary, not a product acceptance result. An
independent exact-fixture repro `o2-auth03-native-k5syntax-repro-20261009-01`
passed with two native calls, durable bad rejection, retry equality and source
unchanged. The `-28` Scheduled Task was observed and deleted with terminal
receipts; its raw matrix remains preserved.

## K1–K15 acceptance matrix (current)

| K | State | Evidence / next boundary |
|---|---|---|
| K1 | IMPLEMENTED | Trusted fixture registration and discovery tests; final native row pending. |
| K2 | IMPLEMENTED | Allowlist, identity, root/revision, idempotency/conflict and readback tests; final native row pending. |
| K3 | DIAGNOSTIC_PASS | Fresh registered script route changes controller behavior and replay reads it back; final closure row pending. |
| K4 | DIAGNOSTIC_PASS | Static dependency, UID/import and lifecycle admission tests; final closure row pending. |
| K5 | DIAGNOSTIC_PASS | Fresh syntax/type failure probes retain raw rejection and prior revision; final closure row pending. |
| K6 | DIAGNOSTIC_PASS | Publication retry/reopen and owner recovery evidence; -23 was verifier-rejected for unit-only row, runner fixed with native step; final closure row pending. |
| K7 | DIAGNOSTIC_PASS | Fresh boundary/spawn/busy/wall probes and executor tests; `-22` had a transient wall child-exit boundary, independent repro passed; final closure row pending. |
| K8 | DIAGNOSTIC_PASS | Catalog-authored room/arena publication and Blender handoff candidate pass; final in-run producers required. |
| K9 | DIAGNOSTIC_PASS | Seeded defect, durable reopen, typed repair and native replay/checkpoint route; final closure row pending. |
| K10 | DIAGNOSTIC_PASS | Native conformance and lifecycle fixtures; final publication-bound matrix row pending. |
| K11 | IMPLEMENTED | Adapter reconnect/retry/context reset tests; final in-run two-source concurrency evidence pending. |
| K12 | IMPLEMENTED | Attribution and scope rejection tests; final in-run hostile metadata evidence pending. |
| K13 | MEASURED_LIMIT | Both pinned native receipts verify as INCOMPATIBLE with native readback and measured cleanup/lease limits; final client/model row must be bound. |
| K14 | DIAGNOSTIC_PASS | GT08A 18/18 diagnostic matrix and focused regression tests; final validator must bind real schema. |
| K15 | REUSE_ONLY | Delegated runner and fail-closed packer exist; two 15-minute runs only in final matrix. |

## Next (O13.5/S283)

B6a/B6b: runner contract and K6 verifier repair plus K13 native receipt
hardening are ready to commit; fresh toolkit `gt09-mcp-native-toolkit-20261010-25`
and hybrid `gt09-mcp-native-hybrid-20261010-25` both verify as measured native
limits. The K13 matrix is `gt09-mcp-capability-matrix-20261010-k13-v3.json`;
it is authority 0 and not a final matrix row until the client is run in the
same final closure. `-23` is
rejected by verify-only and `-24` is INFRA because its outer room host had no
receipt. `-27` is a separate INFRA K1 deadline boundary; `-28` is a K5
Docker exit-124 boundary with an exact independent repro PASS; `-30` remains
an unproven content CPU-boundary diagnostic; `-31` is a room catalog host
transient with an exact repro PASS; `-32` is the K3 inner deadline boundary;
`-35` is a K3 rehearsal PASS only. The 2-CPU and 4-CPU K3 rehearsals (`-42`,
`-43`) reproduced the inner Docker boundary; the 8-CPU rehearsal `-44` passed
K3 on its own frozen closure. Final `-45` is an INFRA K9 repair exit-124 with
an exact registered-script repro PASS on unchanged source. The new `--rows`
rehearsal, measured quota and gated process-tree receipts are ready for the
next final.
Final `-46` is an INFRA K7 busy-observation boundary with an exact repro PASS;
the next final must use a fresh closure and ID.
Final `-47` is an INFRA K7 boundary-publication observation with an exact repro
PASS; the required sequential K7 diagnostic `-48` passed boundary, spawn, busy
and wall on one worker. Final `-49` is an INFRA K3 authenticated attach
boundary with exact repro PASS. The source repair is committed at the 12-CPU
quota and the next action is a fresh Scheduled Task final.
B7: freeze the source, prepare one new Scheduled Task final, start it with
`start-run`, wait for independent Scheduler/return/matrix receipts, then run
verify-only. Only after self-check, dispatch two different-model read-only
critics on the same manifest hash. Do not tick GT09 or open GT10-PC before
both TICK=yes.

## Milestone run log (raw under .local/reviews)

- `gt09-matrix-final-20261009-01`: historical incomplete; multiple rows failed but later playtests ran.
- `gt09-matrix-final-20261009-02`: historical invalid; static/stale evidence and overwritten playtest provenance.
- `gt09-matrix-final-20261009-04`: stopped after source drift during the run.
- `gt09-matrix-final-20261009-05`: stopped after watchdog test failures in K9/K10; raw retained.
- `gt09-matrix-final-20261009-06`: stopped after K10/K14 failures; raw retained and not evidence.
- `gt09-matrix-final-20261009-07`: stopped at K1; Blender wrapper relative import failed, fixed in `b667474c`.
- `gt09-matrix-final-20261009-08`: stopped at K1; stale dead measurement-window marker was recovered, raw retained.
- `gt09-registered-script-20261009-routefix`: diagnostic native K3/K9 route pass, authority 0.
- `gt09-fixture-conformance-20261009-finalprep`: candidate pass, authority 0.
- `gt09-playtest-20261009-03`: room lifecycle diagnostic pass; not final matrix evidence.
- `gt09-matrix-final-20261009-22`: stopped at K7; wall child exited before result.json, invalid and retained.
- `o2-auth05-native-k7wall-repro-20261009-01`: diagnostic PASS after the K7 boundary; no source or deadline change.
- `gt09-matrix-final-20261009-23`: runner PASS K1–K15 but verify-only rejected K6 unit-only evidence; not critic-ready.
- `gt09-matrix-final-20261009-24`: K1–K14 PASS; K15 arena ran, room native Godot exited 0 with clean Job/tree, but host exited 1 without host-result; INFRA raw retained, no rows combined.
- `gt09-matrix-final-20261009-27`: stopped at K1; Blender content hit the measured 20-second watchdog boundary before process-exit receipt; INFRA raw retained, no later rows ran.
- `gt09-matrix-final-20261009-28`: reached K1–K4; K5 syntax native Docker returned exit 124 at the authenticated 29-second boundary; INFRA raw retained, task terminal/delete receipts captured.
- `o2-auth03-native-k5syntax-repro-20261009-01`: exact K5 syntax repro PASS with two native calls, durable rejection and unchanged source.
- `gt09-matrix-final-20261009-30`: stopped at K1; content producer hit the shared 15-second Job CPU cap before transcript/process-exit; INFRA raw retained, task terminal/delete receipts captured.
- `gt09-content-debug-30`: content-only CPU-cap repair diagnostic PASS with native Blender exit, Job cleanup and publication readback.
- `gt09-matrix-final-20261009-31`: K1 content and arena passed; room catalog returned `CATALOG_RESULT`/exit 1; INFRA raw retained, task terminal/delete receipts captured.
- `o2-registered-authoring-k1room-repro-20261009-01`: exact room catalog repro PASS on the same publication root.
- `o2-publication-gt09-k6-repro-20261009-01`: native AUTH-04 publication diagnostic PASS used to validate the K6 repair.
- `gt09-rehearsal-20261009-35`: K3 unit/native/replay PASS on the current closure; rehearsal-only.
- `gt09-rehearsal-20261009-42`: 2-CPU K3 rehearsal; native baseline hit the same inner Docker boundary; rehearsal-only.
- `gt09-rehearsal-20261009-43`: 4-CPU K3 rehearsal; native baseline hit the same inner Docker boundary; rehearsal-only.
- `gt09-rehearsal-20261009-44`: 8-CPU K3 unit/native/replay PASS on closure `0d45ffec…`; rehearsal-only.
- `gt09-matrix-final-20261010-45`: K3 native passed, then K9 repair hit inner Docker exit 124; outer exit 2, clean tree, INFRA only.
- `gt09-registered-script-k3-k9-repro-20261010-45`: exact registered-script repro PASS; seed exit 45 expected, repair exit 0, replay/readback PASS.
- `gt09-matrix-final-20261010-46`: K1–K6 PASS; K7 busy returned `BAD_FIXTURE_NOT_OBSERVED`; outer exit 2, clean tree, INFRA only.
- `o2-auth05-native-k7busy-repro-20261010-46`: exact busy hostile repro PASS; native run count 2, authority 0.
- `gt09-matrix-final-20261010-47`: K1–K6 PASS; K7 boundary returned `GAMEPLAY_OWNER_NATIVE_NOT_CLEAN`; outer exit 2, clean tree, INFRA only.
- `o2-auth05-native-k7boundary-repro-20261010-47`: exact boundary hostile repro PASS; native run count 2.
- `o2-auth05-native-k7seq-20261010-48`: sequential boundary/spawn/busy/wall diagnostic; all four PASS, native run count 2, authority 0.
- `gt09-matrix-final-20261010-49`: K1–K2 PASS; K3 registered route hit authenticated Docker exit 124, outer exit 2, clean tree; INFRA only.
- `gt09-registered-script-k3-boundary-repro-20261010-49`: exact K3 registered-route repro PASS on unchanged 8-CPU source.
- `gt09-registered-script-k3-cpu12-repro-20261010-50`: exact K3 registered-route repro PASS after controlled 12-CPU quota repair.
- `gt09-content-cap60-series-20261009-37`: ten sequential cap-60 content runs PASS; diagnostic only.
- `gt09-content-cap15-series-20261009-38`: ten sequential cap-15 content runs PASS; supports retaining the generic cap.

## Lessons carried forward

- Freeze source, verifier, plan and status before every long run; any source change invalidates closure-bound evidence.
- Final producers must run inside the matrix; evidence from older publication, attribution or adapter directories cannot satisfy a final row.
- A validator must run on real raw output before the final run and must match the producer schema exactly; a child banner never supplies a host exit.
- Stop at the first failed row; do not spend the long playtest budget on an already invalid matrix.
- Keep one coordinator and one writer per file, no audit subagents, one Godot/Blender worker per path, and preserve actual exits/tree cleanup.
- Native, host and unit steps are labeled separately; a unit-only row cannot pass.
- Final preflight now recovers a marker only after the recorded PID is proven dead; a live or uncertain lock fails closed.
- K12 uses a real host subprocess and adapter scope rejection; K13 hashes exact in-run K8/K9 receipts plus the external incompatibility measurement.
- Authority remains zero until two independent critics explicitly accept the same frozen manifest.
- Treat a native timeout as a host boundary only after the raw exit, cleanup/tree state and an exact independent repro agree; never relax the fixture or acceptance rule to make one final run pass.
- Keep resource caps scoped to the producer that measured the boundary; do not widen the generic Blender export cap to make the content fixture pass.
- A cap change needs a controlled comparison: ten sequential cap-15 and cap-60 content runs passed, so the generic 15 s cap remains sufficient for this source.
- Keep catalog fixture probes independently reproducible; a single room host exit cannot be promoted to a source defect without the same publication failing an exact rerun.
- Treat the Docker CPU quota as a bounded scheduling repair: compare fixed short
  rehearsals before raising it, keep memory/PID/network/watchdog limits fixed,
  and record the selected quota in source, docs and the next closure. The
  8-CPU quota is the measured choice on this 12-CPU host; do not widen it again
  without new raw boundary evidence.
- Room publication now reuses the shared native controller and opts into lifecycle only for the
  delegated trace; the short tick-60 probe remains bounded. Any source change invalidates this run.
