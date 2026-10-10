# O2 authoring state — 2026-10-10 (O13/S286)

AUTHORITY=0; GT09=IN_PROGRESS; public gameplay-source remains disabled.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
Final -60: K1–K15 PASS, verify-only exit0, Scheduled Task exit0 (2613.844s).
B7: Sol TICK=yes, Astra TICK=no: K9 only covered room; no acceptance.
Current repair uses both actual K8 publications, native Play faults and catalog commands.
K9 `k9-real-72` diagnostic PASS; read-only raw verifier and K13 four-event binding pass.
Arena health 3→4 and room switch false→true, native replay, durable reopen/checkpoint observed.
K3 keeps controller-change proof; removed its misleading synthetic K9/checkpoint claims.
Protocol uses existing bounded base64 chunks for GLB/PNG; no limit or sandbox relaxation.
K9 shallow raw layout avoids reproduced Docker Desktop per-file bind EIO in deeper paths.
46 focused tests PASS, including raw replay, missing-fixture and false-symptom rejects.
GT08A accepted; GT08B Android deferred; human playtest NOT_PERFORMED.
Next: Scheduled Task K9 rehearsal with fresh producers, then final and two critics.

## K1–K15 acceptance matrix

| K | State | Evidence / next boundary |
|---|---|---|
| K1 | HISTORICAL_PASS | -60 registered discovery + Blender native; refresh on final closure. |
| K2 | HISTORICAL_PASS | -60 allowlist/idempotency/readback; refresh on final closure. |
| K3 | UPDATED | Controller change retained; synthetic K9 removed; rehearsal covers new runner. |
| K4 | HISTORICAL_PASS | -60 native dependency/UID/import; refresh on final closure. |
| K5 | HISTORICAL_PASS | -60 native parse/type failure and revision preservation. |
| K6 | HISTORICAL_PASS | -60 native publish/reopen/recovery, not unit-only. |
| K7 | HISTORICAL_PASS | -60 attributed hostile execution/confinement. |
| K8 | HISTORICAL_PASS | -60 two catalog publications plus native Blender assets. |
| K9 | DIAGNOSTIC_PASS | `k9-real-72`: both actual mini-games, Play symptom→catalog repair→native replay→durable reopen. Fresh final required. |
| K10 | HISTORICAL_PASS | -60 lifecycle/replay/performance on catalog publications. |
| K11 | HISTORICAL_PASS | -60 two-source concurrency + retry/owner edit. |
| K12 | HISTORICAL_PASS | -60 hostile metadata and scope rejection. |
| K13 | UPDATED | Native adapters remain measured INCOMPATIBLE; client now binds committed recipe and both exact repair commands/raw. |
| K14 | HISTORICAL_PASS | -60 GT08A 18/18 and focused regression. |
| K15 | HISTORICAL_PASS | -60 delegated arena/room each >900s with exit0; rerun only in new final. |

## Next

Freeze this source, run Scheduled Task `--rows K9` with its fresh K1–K8 producers.
After rehearsal PASS, run one new Scheduled Task final, `--verify-only`, then
B7 critics on that same closure. GT10-PC remains closed until both TICK=yes.

## Retained evidence and lessons

- Final -60 manifest `1c6419dc…`, closure `4e7534af…`; original critic reports retained
  in `.local/reviews/gt09-matrix-final-20261010-60` and `zdoc/reviews/20261010-gt09-b7-60/`.
- VERIFIER: K9 room-only proof was insufficient despite all matrix rows being green.
  Validate explicit per-fixture DoD; syntax rejection belongs to K5, not gameplay repair.
- Diagnostic -62 failed parent setup; -63 expected the wrong arena health; -64 was
  toy-fixture proof only and was discarded as an implementation route, raw preserved.
- VERIFIER -65: seeded assertion exit needed its exact attributed startup-log policy.
  Then request encoding exposed the 16 KiB string ceiling; reuse supported chunks.
- INFRA -65/-66: asset bytes matched on host but per-file Docker binds returned EIO.
  Repro -68/-69 separated directory bind (readable) from file bind (EIO); -71 showed
  extra path depth fails while a longer shallow path works. Use K8's shallow layout;
  do not shorten timeouts, relax permissions, or mark asset failure as expected.
- `k9-real-72` proves repair on real 2D/3D physics scenes and Blender assets, not old
  arithmetic fixtures. Its raw verifier is read-only and rechecks command/source/journal.
- Earlier history stays in Git `144c007c`; failure raw remains in `.local/reviews`.
- The 12-CPU cap already equals host logical CPUs; it is a ceiling, not reserved capacity.
- Final/rehearsal/soak use Scheduled Task. Freeze all writers, run persisted-row checks
  before later rows, and retain actual exits. Never combine finals or reuse old signatures.
