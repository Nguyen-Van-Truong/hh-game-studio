# O2 authoring state — 2026-10-11 (O13/S290)

AUTHORITY=0; GT09=ACCEPTED; GT10_PC=IN_PROGRESS_NATIVE_DIAGNOSTIC.
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`.
GT09 final -74 accepted: K1–K15, actual Scheduled Task exit0, two critics same hash.
GT10-PC P1–P12 remain unaccepted; no checkbox or acceptance claim is changed here.
Current source includes immutable Ed25519 package trust, compatibility lock, WAL selector/addon recovery, raw evidence verifier, native P2/P7/P9 workers and task-bound rehearsal rows. Fresh Scheduled Task `gt10pc-rehearsal-20261011-r08` passed selected P1/P2/P7/P8/P9 on the frozen source (authority=0; actual task exit 0; P7 native 8/8 cuts; P9 archive-backed independent consumer).
Diagnostic Linux `gt10pc-linux-current-20261011-08` and Windows `gt10pc-win-current-20261011-09` are historical because their source closure predates the current P2/P8/P9/task changes.
Fresh rehearsal `gt10pc-rehearsal-20261011-r08` is current but authority-zero: P1/P2/P7/P8/P9 are `REHEARSAL_PASS`, with independent child receipts and a captured Scheduled Task return receipt. P7 is split into two bounded 4-case producers to respect the 600-second launcher limit; both groups pass and combine to 8/8. P10/P11/P12 remain unaccepted.
Focused validation: package/lifecycle/P2 tests pass after the compatibility-lock changes; P7 host diagnostic 09 and native diagnostic `gt10pc-p7-native-20261011-01` are 8/8; r08 is the current scheduled rehearsal. P9 now has an archive-backed native consumer producer/verifier, and P7 native producer is protected from stale pending overwrite.
Remaining: P3–P6 and P10 native producers/verifiers, then formal25 10×35 and two final critics. No row is accepted or ticked by this status file.
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

Freeze current writers, integrate P3–P6 and P10 native producers/verifiers, then run a fresh whole-matrix rehearsal from one frozen source closure. P7 host diagnostic 09 remains the recovery-boundary baseline; r08 supplies the current native rehearsal.
P2 native rejection must retain independent worker/host/Godot receipts and unchanged install/project/state ledgers. P9 r08 now captures an installed fixture through an independent archive-backed consumer, but remains rehearsal-only until final manifest/critic gates.
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
- GT10PC INFRA 11-10: rehearsal r05 stopped at the first native P7 kill because the nested
  worker job was sampled immediately after wait(); no process remained, but the receipt was
  correctly rejected. P7 now polls the independent job count for a bounded 3s before failing.
- GT10PC PRODUCT/INFRA 11-10: rehearsal r06 proved the worker/tree fix, then P7 native launch
  hit WinError 267 while using a mutable installed-release parent as cwd. The direct probe on
  the same snapshot succeeds; native launchers now use the stable consumer project cwd with
  explicit installed-payload PYTHONPATH, preserving the source binding.
- GT10PC INFRA 11-10: rehearsal r07 ran clean through six P7 cases but the single 8-case
  producer exceeded the launcher’s 600s child limit; actual task exit was 2 with no leftover
  process. P7 rehearsal is split into two 4-case producers and the matrix requires both reports.
- GT10PC REHEARSAL 11-10: rehearsal r08 completed with actual Scheduled Task exit 0 on the
  frozen source closure. P1/P2/P7/P8/P9 were `REHEARSAL_PASS`; P7 had two native 4-case
  producers (8/8 total), and P9 used the independent archive-backed consumer. Authority remains
  zero; do not treat this as acceptance or reuse its identifiers after any source change.
