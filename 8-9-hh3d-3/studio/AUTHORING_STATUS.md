# O2 authoring state — 2026-10-12 (O14/S303; GT-11 under O15/S304)
AUTHORITY=0; GT09=ACCEPTED; GT10_PC=ACCEPTED_O14_SHORT_CHECKS (owner waived the 10×35 soak at 14:05).
Progress authority: `zdoc/8-9-godot-blender-agent-studio-plan.txt`; no checkbox changed here.
Accepted package: rehearsal gt10pc-rehearsal-20261012-c3h, P1–P11 through Scheduled Task, exit 0 in 1276 s.
Verify-only RAW_VERIFIED (coordinator rerun 14:25, 45 s); source 744a9f61, studio closure 86dc9f1c, package a6280d76.
Windows 0.1.0 manifest 3bb561df; archives in `.local/reviews/gt10pc-rehearsal-20261012-c3h/artifacts/`.
P11 is one real Godot cycle, not a soak: memory, handle and object growth over long sessions is unmeasured.
P12: two independent grok-4.7-xhigh critics gave TICK=yes on the same package (O14.7).
Verifier gaps G1/G2 fixed in code by GT-11 W11 (8a9d5407); proven only at the next packaging run. c3h raw predates G2.
Finals f1–f4 are VOID (f4 stopped at P7 under O14); their raw stays in `.local/reviews`.
Usage guide for game agents: `zdoc/12-10-huong-dan-dung-cong-cu-godot-blender.txt`.
Tool bugs found while making games: fix in `studio/` with the short related tests (O14.5), no long soak.
GT08B Android deferred; full GT10 waits for it. GT11 IN_PROGRESS under owner O15 (opened 12-10 15:16). No complete-game claim.

## P1–P12 acceptance matrix (GT-10-PC, O14)

| P | State | Evidence |
|---|---|---|
| P1 | ACCEPTED | Four archives (Windows, Linux-headless × 0.1.0, 0.1.1) rescanned: 809 members, no monetization, 0 armed failpoints. |
| P2 | ACCEPTED | Eight archive attacks and four native attacks rejected before unpack; install, project and state ledgers unchanged. |
| P3 | ACCEPTED | Install into clean copies of both fixtures on Windows and Linux headless; roundtrip and Play read back. |
| P4 | ACCEPTED | Upgrade and rollback; incompatible schema and untrusted rollback refused (recomputed, no per-case host receipt). |
| P5 | ACCEPTED | Uninstall keeps art, game, source and save; reinstall works. |
| P6 | ACCEPTED | Profile hh-godot-gameplay-source-1 kept across install, upgrade and rollback; other projects do not see it. |
| P7 | ACCEPTED | Eight native kill/Stop cases with killer and victim receipts; retry unchanged; last-good trees match signed manifests. |
| P8 | ACCEPTED | Five host cases (dependency, template, addon version, archive, closure) give actionable errors; no latest. |
| P9 | ACCEPTED | Independent consumer child installed release.hhpkg and ran smoke, exit 0; known limits carry the P2/P9 terms. |
| P10 | ACCEPTED | Installed copies pass GT-08A W01–W03, L01–L02 and K8/K10 on both fixtures (three producers, exit 0). |
| P11 | ACCEPTED_SHORT | One real Godot cycle gt06-p11-short-ad57e858 (import 37680, editor 20620, exit 0); 10×35 waived by O14. |
| P12 | ACCEPTED | `zdoc/reviews/20261012-gt10pc-c6-c3h/critic-a-grok.md` and `critic-b-grok.md`, TICK=yes, same package. |

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

## GT-11 gamekit (O15, quick checks)

`studio/gamekit/` is a host CLI (`hh`) that edits real Godot 4.7 projects, 2D and 3D, without the addon or CR-1.
Contract: host validation, command_id journal (replay/CONFLICT), one project lock, EDITOR_OPEN refusal, checkpoint,
temp save + atomic replace, fresh-process readback with auto-restore, per-set immediate readback (silent clamps refused).
Not inside the signed .hhpkg yet; the GT-09 fixture route is unchanged. Usage: guide section 13.

| W | State | Evidence |
|---|---|---|
| W1 | DONE | a0833df7; selftest w1 29/29, unit 12/12; hh.cmd real run 12-10 16:05 (add, new, apply, replay, inspect, check). |
| W2 | DONE_PART | 9eae7686, 2d129056; w2 19/19 (2D arena, two rejects keep bytes, 60 frames clean); image check waits for W5. |
| W3 | DONE_PART | 9b742f6d, 2d129056; w3 14/14 (3D room, method track, 60 frames clean); image check waits for W5. |
| W4–W10 | IN_PROGRESS | input/play/bot, shot/vcheck, perf, asset, blender, kit, export. |
| W11 | DONE | 8a9d5407; G1 P11 exits bound to host process-exit.json (c3h row reads pids 37680, 20620; tampered copy refused); G2 per-case P4 child receipts (missing dir → P4_NEG_RECEIPTS_ABSENT); test_gt10pc_g1_g2 8/8, test_gt10pc* 43 ok, package 9/9. |
| W12 | PLANNED | guide, this file, one Grok read-only critic, close ACCEPTED_O15_QUICK. |

## Next

GT-11 W4–W12 under O15 (above). Game agents use the guide now and each `hh` command once its W is DONE.
Requests for gamekit go to `zdoc/12-10-gt11-yeu-cau-tu-agent-game.txt` (append-only).

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
- GT10PC P10 11-10: focused IDs 01–03 exposed invocation/import and runtime-snapshot argument
  defects; ID04 exposed the installed Blender producer's missing `host` path. ID05 was invalidated
  by source drift because verifier edits were made during the run. Freeze first, then run a new ID;
  a live matrix must never be edited or reused.
- GT10PC P10 11-10: p10a proved GT08A and Blender native output, then the registered probe
  rejected the publication parent instead of its protected `published_root`; p10b confirmed that
  wiring repair but reproduced WinError 5 while atomically renaming a staged release. A bounded
  Windows sharing-lock retry was added and covered by a focused test; other errors still fail closed.
- GT10PC INFRA 11-10: r09 stopped before rows because the Windows P3–P6 producer requested a
  900-second child timeout while the shared launcher caps every child at 600 seconds. The raw
  task exit was 2 with no worker left; the matrix now binds that producer to the 600-second cap.
- GT10PC INFRA/VERIFIER 11-10: r10 reached P2 after P1 and P3–P6, then the native rejection
  worker hit its 180-second bound before writing `p2.json`. The last-good install and addon were
  intact; profiling showed `tree_ledger()` passed every file through `safe_path()` twice, causing
  repeated Windows ancestor `lstat` walks. The repair hashes the already-validated path once with
  streaming `hashlib.file_digest`; it does not relax archive, link, ledger, native, or timeout gates.
- GT10PC INFRA 11-10: r11 confirmed the P2 repair and completed P7 group A, but the four-case
  P7 group B exceeded the 600-second shared child limit while entering its fourth native case.
  No leftover process remained and the worker receipts are retained. The producer is partitioned
  into first/second/third groups of 3/3/2; all eight cases and their exact native checks remain
  required, and each child stays within the existing 600-second launcher contract.
- GT10PC INFRA 11-10: r12 reached exit 0 for all six Windows lifecycle drivers and Godot
  processes, then timed out only while finalizing the sequential producer before its manifest.
  This is a producer wall-clock issue, not a product PASS or acceptance. Hash only after the
  existing `safe_path()` validation and keep the 600-second bound; never raise the launcher cap.
