# O2 authoring state — 2026-10-11 (O13/S290)

AUTHORITY=0; GT09=ACCEPTED; GT10_PC=IN_PROGRESS_NATIVE_DIAGNOSTIC.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
GT09 final -74 accepted: K1–K15, actual Scheduled Task exit0, two critics same hash.
GT10-PC prototype 6b3e0f77 claims remain VOID_DIAGNOSTIC; no P row accepted.
Checkpoint 51ce380e: external Ed25519 trust, immutable releases and native lane.
Diagnostic 20261011-04: arena+room exit0; sched01 exited0 in 60.032s (older source).
Current source adds addon dependency/layout repair, WAL recovery and strict raw verifier.
Five host tests passed, including four actual addon worker kills (118.408s).
Current-source Scheduled Task native parse/lifecycle verification is NEXT; prior runs are historical.
Remaining: P1/P2 adversarial receipts, Linux/P4/P6–P10, formal25 10×35, two final critics.
GT08B Android deferred; full GT10 blocked; GT11 unopened. No complete-game claim.

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

Run Scheduled Task diagnostic with schema-3 producer and external trust arguments.
Then extend native P4/P6/P7 and Linux; P7 host kill tests alone do not satisfy the native row.
Final is explicitly disabled until all row producers and raw verifiers are complete.

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

- GT10PC VERIFIER 11-10: compare Play to the post-install ledger, not pre-install;
  installation intentionally adds addon files. Keep distinct receipt names for each phase.
- GT10PC PRODUCT: addon source is godot-addon/addons/hh_studio plus protocol/jcs_godot.gd;
  a lifecycle Play that never parses the addon cannot prove addon installation. Parse it explicitly.
- GT10PC PRODUCT: preserve unowned collisions by rejecting before mutation; repair only journal-owned
  paths. Ownership is per project. Intent precedes directory replacement; recover forward from WAL
  after process death. Retain backup outside project rather than deleting during commit.
- GT10PC VERIFIER: schema-3 requires external trust, signed artifact binding, every evidence hash,
  independent host exit/PID receipt, complete fixture ledger and exact lifecycle transitions.
