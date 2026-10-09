# O2 authoring state — 2026-10-09 (O13/S272)

AUTHORITY=0; GT09=IN_PROGRESS; no public gameplay-source or acceptance claim.
Source-of-truth plan: `zdoc/8-9-godot-blender-agent-studio-plan.txt` S272.
WIP milestone is frozen for commit before the next long run; final closure is
computed by `run_gt09_matrix.py` and excludes `.local` and caches.
GT08A remains accepted; GT08B Android remains deferred by owner.
K1–K9 and K11–K14 have diagnostic implementations/evidence, but no final row
is accepted until one frozen K1–K15 run and two independent critics share its hash.
The five earlier final attempts are historical; -04 had source drift, -05 had
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

## K1–K15 acceptance matrix (current)

| K | State | Evidence / next boundary |
|---|---|---|
| K1 | IMPLEMENTED | Trusted fixture registration and discovery tests; final native row pending. |
| K2 | IMPLEMENTED | Allowlist, identity, root/revision, idempotency/conflict and readback tests; final native row pending. |
| K3 | DIAGNOSTIC_PASS | Fresh registered script route changes controller behavior and replay reads it back; final closure row pending. |
| K4 | DIAGNOSTIC_PASS | Static dependency, UID/import and lifecycle admission tests; final closure row pending. |
| K5 | DIAGNOSTIC_PASS | Fresh syntax/type failure probes retain raw rejection and prior revision; final closure row pending. |
| K6 | DIAGNOSTIC_PASS | Publication retry/reopen and owner recovery evidence; final closure row pending. |
| K7 | DIAGNOSTIC_PASS | Fresh boundary/spawn/busy/wall probes and executor tests; `-22` had a transient wall child-exit boundary, independent repro passed; final closure row pending. |
| K8 | DIAGNOSTIC_PASS | Catalog-authored room/arena publication and Blender handoff candidate pass; final in-run producers required. |
| K9 | DIAGNOSTIC_PASS | Seeded defect, durable reopen, typed repair and native replay/checkpoint route; final closure row pending. |
| K10 | DIAGNOSTIC_PASS | Native conformance and lifecycle fixtures; final publication-bound matrix row pending. |
| K11 | IMPLEMENTED | Adapter reconnect/retry/context reset tests; final in-run two-source concurrency evidence pending. |
| K12 | IMPLEMENTED | Attribution and scope rejection tests; final in-run hostile metadata evidence pending. |
| K13 | MEASURED_LIMIT | External native route is INCOMPATIBLE with measured cleanup/lease limits; final client/model row must be bound. |
| K14 | DIAGNOSTIC_PASS | GT08A 18/18 diagnostic matrix and focused regression tests; final validator must bind real schema. |
| K15 | REUSE_ONLY | Delegated runner and fail-closed packer exist; two 15-minute runs only in final matrix. |

## Next (O13.5/S271)

B6a: finish the final runner contract: in-run K8 producers, closure start/end,
native/host evidence labels, K1/K2/K11/K12/K13 client rows, verify-only and
fail-fast behavior. Run verify-only and changed-row checks on historical raw.
B6b: commit this WIP, dry-run, then one fresh final K1–K15 run with no writers.
B7: only after self-check, dispatch two different-model read-only critics on the
same manifest hash. Do not tick GT09 or open GT10-PC before both TICK=yes.

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
- Room publication now reuses the shared native controller and opts into lifecycle only for the
  delegated trace; the short tick-60 probe remains bounded. Any source change invalidates this run.
