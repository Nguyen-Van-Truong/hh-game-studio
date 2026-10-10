# O2 authoring state — 2026-10-10 (O13/S287)

AUTHORITY=0; GT09=ACCEPTED; GT10_PC=OPEN; public gameplay-source remains disabled.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
Final `gt09-matrix-final-20261010-74`: K1–K15 PASS, manifest `8d9a2ec6…`, closure `6b7b5231…`.
Scheduled Task actual exit0, 2487.203s, zero remaining instances; verify-only `DIAGNOSTIC_OK` exit0.
Critics: Astra xhigh `TICK=yes`; Sol ultra `TICK=yes`, same manifest and closure.
Coordinator acceptance: `zdoc/reviews/20261010-gt09-b7-74/coordinator-acceptance.md`.
K9: arena health 3→4 and room switch false→true through native Play, catalog repair, replay and reopen/checkpoint.
K13 remains measured `INCOMPATIBLE` with reason; no external compatibility claim.
GT08A accepted; GT08B Android deferred; human playtest NOT_PERFORMED.
Next gate: GT-10-PC P1–P12; write `run_gt10pc_matrix.py` matrix/DoD before implementation.
Full GT-10 remains blocked by deferred GT08B; GT-11 opens only after GT-10-PC acceptance.

## K1–K15 acceptance matrix

| K | State | Evidence |
|---|---|---|
| K1 | ACCEPTED | Final -74 registered discovery, profile isolation and Blender native producer. |
| K2 | ACCEPTED | Final -74 allowlist, identity, idempotency, conflict and readback. |
| K3 | ACCEPTED | Final -74 controller change and native replay. |
| K4 | ACCEPTED | Final -74 dependency, UID/import and rejection checks. |
| K5 | ACCEPTED | Final -74 native syntax/type failure and revision preservation. |
| K6 | ACCEPTED | Final -74 durable publish/reopen/recovery and owner edit. |
| K7 | ACCEPTED | Final -74 attributed hostile execution and confinement. |
| K8 | ACCEPTED | Final -74 two catalog publications with native Blender assets and readback. |
| K9 | ACCEPTED | Final -74 arena and room seeded defects repaired through catalog commands and replayed natively. |
| K10 | ACCEPTED | Final -74 input/pause/save/reload/performance conformance on both publications. |
| K11 | ACCEPTED | Final -74 reconnect/retry/context reset, owner edit and two-source concurrency. |
| K12 | ACCEPTED | Final -74 hostile metadata and out-of-scope command rejection. |
| K13 | ACCEPTED | Final -74 measured adapter matrix, four provenance events and explicit INCOMPATIBLE result. |
| K14 | ACCEPTED | Final -74 GT08A regression and focused suite. |
| K15 | ACCEPTED | Final -74 delegated arena/room playtests, each over 900s with exit0. |

## Next

GT-09 is accepted by two independent critics on the same frozen manifest/closure.
Open GT-10-PC: define P1–P12 and evidence classes in `run_gt10pc_matrix.py`, then run
its dry-run/rehearsal before any final Scheduled Task. Keep GT08B deferred and do not
claim full GT-10 or Android support.

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
