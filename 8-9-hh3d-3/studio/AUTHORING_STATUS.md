# O2 authoring state — 2026-10-11 (O13/S290)

AUTHORITY=0; GT09=ACCEPTED; GT10_PC=IN_PROGRESS_NATIVE_DIAGNOSTIC.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
GT09 final -74 accepted: K1–K15, actual Scheduled Task exit0, two critics same hash.
GT10-PC P1–P12 remain unaccepted; no checkbox or acceptance claim is changed here.
Current source includes immutable Ed25519 package trust, compatibility lock, WAL selector/addon recovery, raw evidence verifier, native P2 worker and task-bound rehearsal rows. Fresh Scheduled Task `gt10pc-rehearsal-20261011-p2c` passed P1/P2 on the current source (authority=0; native Windows rejection + Godot readback captured).
Diagnostic Linux `gt10pc-linux-current-20261011-08` and Windows `gt10pc-win-current-20261011-09` are historical because their source closure predates the current P2/P8/P9/task changes.
Fresh rehearsal `gt10pc-rehearsal-20261011-r03` is historical authority-zero. Current `gt10pc-rehearsal-20261011-p2c` is authority-zero and passed selected P1/P2, including native Windows rejection and Godot readback with actual Scheduled Task exit 0. Fresh P7 host diagnostic `gt10pc-p7-host-20261011-09` passed all 8/8 crash/Stop cuts; it is not native acceptance evidence. P10/P11/P12 were not requested; P9 native smoke remains pending.
Focused validation: package/lifecycle/P2 tests pass after the compatibility-lock changes; P7 host diagnostic 09 is 8/8; a fresh rehearsal is required before any row is treated as current evidence. P9 native consumer smoke and P7 native producer are now wired into the rehearsal runner.
Remaining: P3–P7/P9–P10 native matrix (P7 host diagnostic is not a substitute), current P8/P9 rehearsal, formal25 10×35, two final critics.
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

Freeze current writers, run one fresh Scheduled Task rehearsal with selected P1/P2/P8/P9 first, then integrate the P7 native lifecycle producer and P3–P6/P10 regression before a whole-matrix rehearsal. P7 host diagnostic 09 is retained as the recovery-boundary baseline.
P2 native rejection must retain independent worker/host/Godot receipts and unchanged install/project/state ledgers. P9 consumer helper is host smoke only until a native installed fixture is captured.
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
- GT10PC INFRA 11-10: rehearsal r04 stopped before P7 because the child launcher rejects
  timeouts above 600s; raw is retained and the task was deleted after its actual exit. Keep
  Scheduled Task timeout within the launcher contract; do not reuse a failed run id.
