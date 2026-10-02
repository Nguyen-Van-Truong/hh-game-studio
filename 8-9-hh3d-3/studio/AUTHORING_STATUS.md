# O2 authoring state — 2026-10-02

AUTHORITY=0. Branch `codex/o2-authoring-contract`; no merge before GT-06 ACCEPTED.
Tools-plan O1–O8 governs; test counts/native diagnostics do not close AUTH or a WP.

## Current state

- Typed nodes/resources, scene instances, signals/InputMap, animation and six-effect gameplay
  shortcut have candidate validation/native readback; generic typed gameplay uses gameplay-source.
- Blender template armature/action, geometry/material/UV, GLB export and 2D sprite import have
  separate diagnostics; neither asset presence nor a marker proves complete authored gameplay.
- Publication owner supports readback ACK, lease/revision checks, idempotent retry and reopen.
  Dependency-enabled lifecycle has pure proof; the old native dependency run20261002-03 stopped at
  Docker CLI inventory5s before container creation and remains unchanged. Fresh native confirmation
  run20261002-04 completed with one container dispatch and actual outer/host/container exit0.
- O8.3b repair verified by 71 focused pure tests, exit0: exact-label/all-container bounded named-pipe inventory replaces only that
  admission CLI call, preserving5s and fail-closed ownership. Test/confirmation details below.
- AUTH-03 native type rejection preserves last-good CURRENT/journal and avoids third dispatch.
  Source binding is historical; do not combine different runs' runtime or probe hashes.
- AUTH-05 hostile boundary/spawn/network/timeout observations remain separate cases.
  Adapter boundary run20261002-01 preserves last-good but predates the later run-ID harness
  validation; keep it as historical diagnostic, not a run of today's harness or AUTH acceptance.
- AUTH-05 static hardening commit `55433374ee03de50d0837d549b8cd3d8b03f4bd9` now rejects
  duplicate JSON keys recursively in hostile boundary/spawn markers. Focused pure suites
  passed46 and43 tests, both actual exit0; no native engine, Docker or network probe was run.
- AUTH-05 publication-owner hostile runs now include native spawn and a distinct wall-wait
  confirmation. Wall20261002-01 actual outer0, good host/container0 then bad124;
  supervisor/cleanup/last-good/reopen/retry checked with exactly2 dispatches.
  Busy01 import failure and busy02 CPU/wall mismatch remain FAIL; bounded resource
  telemetry is advisory. Distinct source bindings below; AUTHORITY stays0.
- Publication recovery now uses a marker namespace disjoint from valid command IDs.
  IDs ending `.stage` previously broke reopen after success or rejection; six focused
  pure tests now pass. Old-source roots retain their binding; no implicit migration.
- O8.3a physics repair re-evaluated44 raw artifacts from20260929-03: corrected trace/lifecycle
  check true; original verifier FAIL unchanged. Fresh native confirmation below observed the repaired
  fixture in a real container with actual exit0 and clean owned lifecycle; authority remains0.
- GT-06 formal14 is terminal PRODUCT_FAIL; no measured workload active at last check. Recheck process/lock
  before engine/Docker work; when formal runs, static work only and one writer per file.

## 2026-10-02 — Native wall-watchdog rejection and last-good recovery verified

- Fixed the test design without changing the guard: new `gameplay_source_wall_wait`
  enters a real nonterminating `OS.delay_msec(1000)` loop. Original busy loop/raw
  kept. The same20s total cap,10 CPU-second cap and strict124/137 wall oracle apply;
  no acceptance of exit45 or advisory metrics as watchdog proof. Mapping/evidence
  focused suites:20 pure tests passed, actual exit0.
- Fresh O4.1 passed, then `python -B -X utf8 studio/tests/godot/run_gameplay_failure_probe.py
  --run-id o2-auth05-native-wall-20261002-01 --failure-fixture wall`.
  21:10–21:11 Asia/Saigon, actual outerexit0 / DIAGNOSTIC_PASS. Runtime closure
  `80300fb2f4dd699c4d01b982855ffa7334d756608eb90a4cefdfb07404c30cb4`;
  fixture script SHA256 `6f831737af67fd1e1847c991c6b6ac340d28f2f7bf6ac89cc4328bd6db1ba621`.
- Good publish host/container0 then real loop entry; bad host/container124 after
  ~19.765s host duration, timed_out=false. Pinned in-container PID1 supervisor
  termination at19s / kill-after1s, binding verified and watchdog observed.
  No claim that the killed engine naturally exited0. Negative publication rejected;
  CURRENT/journal unchanged, reopen equal and idempotent good retry caused no third
  dispatch. Both owned containers removed, Jobs zero/closed, handles released,
  admissions released. All28 current/frozen source files and41 bad artifact hashes
  independently matched after terminal. No engine left running.
- Raw: `studio/.local/reviews/o2-auth05-native-wall-20261002-01/`. Diagnostic
  AUTHORITY0/public_ack=false/sandbox_acceptance=false; this closes that pending
  native observation, not AUTH05/GT09 acceptance. Busy01/02 verdicts untouched.

## 2026-10-02 — Child resource telemetry; CPU/wall fixture race localized

- Trusted phase parent now emits bounded advisory child-resource records after
  wait: actual child returncode, elapsed time, inherited CPU limits, per-child
  user/system CPU deltas and bounded cgroup-v2 memory.events. Missing readings
  remain null. These transcript records carry authority0 and never grant PASS,
  change a child exit, replace lifecycle proof or relax log policy. Long-uptime
  clocks preserve elapsed nanoseconds and use bounded absolute microseconds.
  Profile16 + log policy9 + integrity-pin1 focused tests passed, actual exits0.
- Profile SHA256 `aa01428ff26dc56fc20f19f7093bd025685fe9ca509843826ee02fe7acb6485c`;
  runtime closure `80300fb2f4dd699c4d01b982855ffa7334d756608eb90a4cefdfb07404c30cb4`.
  Fresh O4.1 then `python -B -X utf8 studio/tests/godot/run_gameplay_failure_probe.py
  --run-id o2-auth05-native-busy-20261002-02 --failure-fixture busy`.
- Actual outerexit1 / BAD_FIXTURE_NOT_OBSERVED remains FAIL. Good host/container0;
  bad parse0/import0, real BUSY_ENTERED, play child-9, host/container45. Play used
  9.918739 user +0.079925 system CPU seconds (~9.998664), with soft/hard CPU10s;
  cgroup OOM counters stayed0. This is consistent with CPU-limit termination,
  not independent proof of the signal's cause. It does not explain busy01's
  earlier import kill retroactively. No wall watchdog was observed in busy02.
- Static review found the fixture's timing assumption wrong: a tight loop races
  its CPU limit against the shared wall deadline. The existing verifier correctly
  refuses exit45/play-9 as evidence of supervisor124/137; do not weaken that rule
  or promote advisory resource markers into trusted acceptance.
- Both containers removed, Jobs zero/closed/handles released, admissions released;
 28 frozen/current source files and41 bad artifact hashes verified. Offline
  reopen performed0 dispatches and preserved CURRENT/journal byte-for-byte.
  Raw and original result stay under `studio/.local/reviews/o2-auth05-native-busy-20261002-02/`.
- Add a distinct low-CPU wall-wait fixture, retaining the old busy loop and raw:
  real script enters a nonterminating delay loop; same20s cap, same wall-only
  exit/transcript/lifecycle oracle. One native confirmation after focused tests;
  no executor timeout/resource change and no claim that all AUTH05 is accepted.

## 2026-10-02 — Recovery marker collision repair; busy confirmation incomplete

- A valid command ID ending `.stage` was confused with a temporary directory on
  reopen. Both successful and rejected native runs reproduced STAGE_DIRTY before
  repair. Markers now use `.stage.<command_id>`; valid IDs cannot start with a dot.
  Six focused lifecycle tests passed, actual exit0 (2.821s): committed retry,
  rejected45/watchdog124 retry, dirty/file/paired markers, and old-root preservation.
  Rejected retry never redispatches; no failed raw is removed. Old runtime closures
  are rejected before reconciliation, not silently migrated/rebound.
- New runtime closure (25 files):
  `be82d6e85d4577842bd0ef852e472fa3576aacabe39a7f49ef8395866a3d9a8f`.
  Command: `python -B -X utf8 studio/tests/godot/run_gameplay_failure_probe.py
  --run-id o2-auth05-native-busy-20261002-01 --failure-fixture busy`.
  Fresh O4.1 preflight passed; outer actual exit1 / BAD_FIXTURE_NOT_OBSERVED.
  Good publish host/container exit0; bad host/container exit45, transcript
  PHASE_END import -9. No BUSY_ENTERED or runtime phase, and no watchdog observation.
  Container OOMKilled=false does not establish why the import child was killed.
  Do not retry blindly or claim the infinite loop was bounded by this run.
- Both containers removed, Jobs zero/closed/handles released, admissions released;
  source28 files and41 negative artifact references matched. Offline recovery from
  the retained owner succeeded with0 native dispatches and byte-identical CURRENT/
  journal (`offline-reopen-closeout.json`). Original DIAGNOSTIC_FAIL is unchanged;
  this supplements recovery evidence only. First offline helper attempts stopped
  before reopen (missing module registration, then relative root); corrected those
  invocation errors without restarting engines or rewriting raw.
- Raw: `studio/.local/reviews/o2-auth05-native-busy-20261002-01/`. AUTHORITY=0.
  Next: identify the import-child termination boundary before another busy attempt;
  keep the existing executor resource and wall limits. This is not GT06 acceptance.

## 2026-10-02 — AUTH-05 native spawn rejection and recovery

- Command: `python -B -X utf8 studio/tests/godot/run_gameplay_failure_probe.py
  --run-id o2-auth05-native-spawn-20261002-01 --failure-fixture spawn`.
  Fresh O4.1 snapshot passed before launch; outer actual exit0 is in outer-exit.json.
  Runtime closure `f9e295de500888e4c1d3f721d2675e3dacaa96af7c4cec641b5eeac949284a91`;
  all28 frozen/current source files and all bad-observation artifact hashes matched.
- Good publish returned READBACK_ACK, then OS.execute returned-1/output[""] with
  the expected OS pipe-denial log. Publication rejected GAMEPLAY_OWNER_NATIVE_NOT_CLEAN;
  CURRENT/journal unchanged, reopen/readback/retry equal, exactly2 native dispatches.
  Each host/container actually exited0, owned Jobs zero/closed/handles released,
  containers removed and admission released. The negative fixture's expected error
  is rejection evidence, not a clean gameplay log or general sandbox acceptance.
- Raw: `studio/.local/reviews/o2-auth05-native-spawn-20261002-01/`. AUTHORITY=0,
  public_ack=false, sandbox_acceptance=false. This run predates any following
  stage-marker namespace repair; retain its original closure and verdict.

## 2026-10-02 — O8.3b native dependency confirmation

- Fresh run `o2-publication-20261002-04` used the repaired named-pipe inventory
  with source closure `f9e295de500888e4c1d3f721d2675e3dacaa96af7c4cec641b5eeac949284a91`.
  Wrapper actual exit was `0`; the native container actual exit was `0`, state
  `exited`, `OOMKilled=false`, and the owned Job was closed with active count
  `0`, retained handle `false`, and no failed operations.
- The real dependency fixture observed four nodes and its dependency edges;
  publication returned `READBACK_ACK`, live retry and reopened retry were equal,
  durable `CURRENT`/journal state stayed unchanged, and source hashes were
  unchanged. Native dispatch count was exactly one. Raw evidence is under
  `studio/.local/reviews/o2-publication-20261002-04/`.
- This remains a diagnostic confirmation (`AUTHORITY=0`, `public_ack=false`,
  `sandbox_acceptance=false`); it does not accept GT06 or authorize an O2 merge.
  The earlier `o2-publication-20261002-03` timeout remains historical.

## 2026-10-02 — O8.3a native physics confirmation

- Fresh run `o2-physics-native-20261002-01` used the repaired arena fixture. The wrapper,
  host supervisor and container each reported actual exit0; the owned Job was closed,
  retained handles were false, and owned resources were removed. Raw evidence is under
  `studio/.local/reviews/o2-physics-native-20261002-01/`.
- The observed trace covered boot, pickup, projectile, jump, bot defeat, landing, wall,
  input release and finish at 150 ticks; fixture and lifecycle observations were true.
  This is a bounded native fixture diagnostic, not complete authored-game E2E evidence:
  `AUTHORITY=0`, `sandbox_acceptance=false`, and `validation_attribution_proven=false`.
- The retained `o2-arena-physics-20260929-03` original outer FAIL and its offline correction
  remain unchanged; the fresh run does not rewrite either verdict.

## Next actions

1. Complete fixture-specific adapter AUTH-02..05 evidence, then authored2D arena and3D room E2E.
2. Keep GT09/GT10 acceptance, human playtest and two independent critics separate from diagnostics.
3. Do not repeat the completed native confirmations without a new reproducer; retain raw evidence and
   keep the candidate authority0 until the formal GT06 and later gates are accepted.

The duplicate-key repair only hardens evidence parsing. Boundary/network, spawn and
wall-timeout observations above are separate diagnostics on recorded closures;
do not repeat them just to update hashes or combine them into acceptance. Remaining
work is the fixture-specific adapter path and authored2D/3D end-to-end coverage.
Native work requires an absent measurement lock and a fresh host preflight.

Historical entries (including obsolete next actions): [history](AUTHORING_STATUS_HISTORY_20261002.md).
History preserves the previous status file byte-for-byte; SHA256 `48fc9e191150cebd2c546f360cc75f3cd3ae2b5c0e77844bd316712a36407b9a`.
Read this current section first; O8.3 permits one confirmation after a demonstrated repair and
supersedes the historical “wait for owner after3/3” notes. No raw evidence or verdict was edited.

## 2026-10-02 — Physics offline correction (O8.3a)

`studio/.local/reviews/o2-physics-offline-20261002-01/supplemental.json` re-evaluates the retained
`o2-arena-physics-20260929-03` transcript using the corrected next-physics-tick expectation.
All44 recorded artifact hashes and unchanged fixture-script hash match. Physics trace and
lifecycle evaluation are true; recorded host/container exits0. No native dispatch occurred.
Original outer verifier exit1/FAIL remains. This supplemental is not current sandbox/source
acceptance: current native confirmation remains required. Verifier/script hashes are in receipt.

## 2026-10-02 — Bounded inventory repair (O8.3b)

Repair replaces only admission inventory; known-owner inspect/kill/wait/remove remain unchanged.
Fixed local pipe request uses all=1 and exact hh.gt03.executor label, validates unique full IDs
including stopped/created containers, and uses one five-second deadline with no CLI fallback.
Inventory errors cannot become an empty set. `admission-inventory.json` records this transport
honestly without fabricated process exits. Runtime closure includes inventory and pipe helpers.
Focused pure verification: 71 tests, actual exit0, 15.201s. Command from tools root:
`python -B -m unittest studio.tests.godot.test_docker_inventory studio.tests.godot.test_linux_executor
studio.tests.protocol.test_pipe_io studio.tests.godot.test_gameplay_runtime_binding
studio.tests.godot.test_gameplay_owner_dependencies`.
Runtime closure: 25 files / `f9e295de500888e4c1d3f721d2675e3dacaa96af7c4cec641b5eeac949284a91`.
Tests cover parser/deadline/cleanup negatives, executor rejection/no-create and captured-generation
drift. New native confirmation pending; last host check14:16 had2.694GiB available/89.122% commit,
so no engine run was started. Previous failures stay unchanged. Native verification must check
actual host/container exits, dependency binding, retry/reopen and owned cleanup.
