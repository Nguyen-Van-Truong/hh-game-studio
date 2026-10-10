# O2 authoring state — 2026-10-10 (O13/S285)

AUTHORITY=0; GT09=IN_PROGRESS; public gameplay-source remains disabled.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
Final -54 completed K1–K15, host exit0; post-run self-check exposed K5/K7
fixture reconstruction gaps, repaired in `69da19c3`. It is historical after source changes.
Final -55 and rehearsal -30 hit the Docker deadline; authenticated 30s alone is insufficient.
Diagnostic -58 locates timeout inside import, before play; failed raw remains intact.
Its removal confirmation timed out, but owner recovery -59 proved the container absent.
Current repair stages the unchanged pinned Godot binary in a read-only Linux image layer.
Scheduled Task now supports K3 rehearsal; every row self-checks persisted raw before continuing.
K13 v3 measures both pinned external adapters as INCOMPATIBLE with native readback.
GT08A remains accepted; GT08B Android deferred. Human playtest NOT_PERFORMED.
No final acceptance or GT10-PC opening until a current final and two different-model critics.
Rehearsal `gt09-matrix-rehearsal-20261010-59` PASS via Scheduled Task: actual exit 0, 171.969s, K3 native+unit, closure `sha256:531bfbd1…`; task terminal/delete receipts retained.
Final `gt09-matrix-final-20261010-59` stopped at K1 with Blender `CONTENT_DEADLINE_OR_LOG_CAP`; actual task exit 2 after 34.625s, raw/task receipts retained. Exact content repro `gt09-content-repro-20261010-61` then PASS (exit 0), so no producer/limit change was justified.

## K1–K15 acceptance matrix

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

## Next

Finish and verify the pinned image build; validate confinement/receipt regressions.
Commit source and this status together, then run Scheduled Task K3 rehearsal on
that closure. If clean, run one new Scheduled Task final, `--verify-only`, then
B7 critics on the same frozen hash. No source writers during final.

## Retained evidence and lessons

- Detailed earlier run history: Git `d76ee98e` version of this file; raw stays in `.local/reviews`.
- -54 raw validators K1–K14 pass after the K5/K7 repair; K15 correctly rejects current source drift.
- -57/-58 startup-retry experiment was removed: timeout alone cannot classify a transient;
  renaming evidence/project directories breaks absolute-path provenance. No failure becomes PASS.
- The 12-CPU cap equals the host's 12 logical CPUs; it is a ceiling, not reserved capacity.
  Concurrent user services and Docker backend compete for CPU. Never stop unrelated services.
- Reconcile a retained owner with its original image pin before migrating runtime images.
- Keep exact raw exits, immutable paths, cleanup receipts and source hashes. Do not combine finals.
- Run persisted-row validators before the next row, especially before the 30-minute playtest.
- Rehearsals/finals use Scheduled Task receipts. A shell-child rehearsal cannot survive session loss.
- Update status only with a meaningful source milestone; metadata-only commits invalidate the
  matrix closure and trigger unnecessary rehearsals. Preserve limits and stop at first FAIL.
