# O2 authoring state — 2026-10-10 (O13/S282)

AUTHORITY=0; GT09=IN_PROGRESS; no public gameplay-source or acceptance claim.
Source-of-truth plan: `zdoc/8-9-godot-blender-agent-studio-plan.txt` S282.
Current WIP is the runner/process-boundary repair plus a measured Docker CPU
quota repair; commit it before the next long run. Final closure is computed by `run_gt09_matrix.py` and excludes
`.local` and caches.
GT08A remains accepted; GT08B Android remains deferred by owner.
K1–K9 and K11–K14 have diagnostic implementations/evidence, but no final row
is accepted until one frozen K1–K15 run and two independent critics share its hash.
Earlier final attempts are historical; -04 had source drift, -05 had
watchdog parser failures, and -06 was stopped after schema/closure failures.
Human playtest remains NOT_PERFORMED and authority stays 0. A delegated room
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
| K13 | MEASURED_LIMIT | External native route is INCOMPATIBLE with measured cleanup/lease limits; final client/model row must be bound. |
| K14 | DIAGNOSTIC_PASS | GT08A 18/18 diagnostic matrix and focused regression tests; final validator must bind real schema. |
| K15 | REUSE_ONLY | Delegated runner and fail-closed packer exist; two 15-minute runs only in final matrix. |

## Next (O13.5/S282)

B6a/B6b: runner contract and K6 verifier repair are committed; `-23` is
rejected by verify-only and `-24` is INFRA because its outer room host had no
receipt. `-27` is a separate INFRA K1 deadline boundary; `-28` is a K5
Docker exit-124 boundary with an exact independent repro PASS; `-30` remains
an unproven content CPU-boundary diagnostic; `-31` is a room catalog host
transient with an exact repro PASS; `-32` is the K3 inner deadline boundary;
`-35` is a K3 rehearsal PASS only. The 2-CPU and 4-CPU K3 rehearsals (`-42`,
`-43`) reproduced the inner Docker boundary; the 8-CPU rehearsal `-44` passed
K3 on its own frozen closure. The new `--rows` rehearsal, measured quota and
gated process-tree receipts are ready for the next final.
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
