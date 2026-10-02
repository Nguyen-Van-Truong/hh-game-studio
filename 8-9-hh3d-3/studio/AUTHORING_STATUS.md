# O2 authoring state — 2026-10-02

AUTHORITY=0. Branch `codex/o2-authoring-contract`; no merge before GT-06 ACCEPTED.
Tools-plan O1–O8 governs; test counts/native diagnostics do not close AUTH or a WP.

- Added an authority-zero asset handoff plan for both fixture lanes (`tests/godot/asset_handoff_plan.py`). The room GLB row now records explicit Blender geometry/material/UV/axis/export/import-readback steps, while the arena row records the separate pose-render/sprite-sheet/texture-readback path. Hashes and profile labels are shape-checked, paths are confined to `assets/`, and every import/native flag remains false. Four focused pure tests exit0; this is a static handoff contract only and does not verify a Blender export, Godot import, texture readback, or gameplay.

## Current state

- Saved-arena candidate composition now has a pure owner-admission binding seam:
  `bind_recipe_to_owner_admission` rehydrates each existing node/resource projection
  with a supplied owner project/revision/generation/lease observation, revalidates
  through the existing typed candidate contracts, and returns detached request
  envelopes plus projection hashes. The repeated observed revision/lease is
  provenance only: the result is explicitly `DETACHED_PLAN_ONLY`, not a
  sequential executable stream; an owner must re-admit before every effect.
  It performs no owner submit, native edit, save, ACK, or runtime claim.
  Focused recipe/builder tests: **16**, exit0.
  AUTHORITY remains0; native editor proof is open and the raw `o2-authoring-update-20261002-04`
  `EDITOR_IPC_TIMEOUT` verdict is unchanged.

- Saved-room 3D fixture now has a separate pure recipe seam. It validates a
  parent-before-child `Node3D` room with `CharacterBody3D`, `MeshInstance3D`,
  `Camera3D`, `Area3D` triggers and `CollisionShape3D` nodes, plus typed
  `CapsuleShape3D`/`BoxShape3D` resources. The mesh is bound to a detached
  Blender `assets/avatar.glb` and `assets/manifest.json` hash reference;
  import/readback remains explicitly pending. Owner-admission binding returns
  `DETACHED_PLAN_ONLY` envelopes and requires fresh admission per effect; it
  performs no editor submit, save, ACK or native claim. Focused pure recipe
  tests: **7**, exit0. The resource candidate allowlist now includes the
  necessary 3D ancestor node types and rejects broken hierarchy/dimensions.
  AUTHORITY remains0; this does not open GT-06 or prove Blender/Godot native
  import.

- The 2D arena fixture now has a pure composition plan over the existing
  TileMapLayer, signal/group/InputMap edge and typed gameplay validators. It
  binds nine deterministic platform cells, pickup/bot/lifecycle edges and
  typed player/pickup/bot source references into a canonical
  `DETACHED_PLAN_ONLY` document. Its offline verifier rejects unknown fields,
  stale admission, altered projection hashes and validator-invalid rows;
  eight focused tests exit0. This remains authority0: no Godot mutation,
  native readback, save, ACK, or complete-game claim.

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
- Duplicate-key hardening retains strict hostile-marker parsing; diagnostics do not grant AUTH05.
- Saved-arena builder06 persists fourteen nodes (five collision shapes, Camera and HUD/Status)
  through validated candidate proposals and native UndoRedo/save/reload. Publication-saved-arena03
  loads those exact scene bytes and proves physics, saved HUD, dependencies and ACK/reopen/retry.
  InputMap/signals remain runtime; generic registered authoring, complete arena and3D remain open.
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

## 2026-10-02 — Private registered update bridge and native confirmation closeout

- Added a private `scene.node.update` bridge into the existing registered publication
  owner. It reuses the owner’s current inspected context, grant, lease/fencing,
  idempotent journal and accepted projection; it admits only `position`/`scale` on
  existing Node3D/MeshInstance3D nodes. It does not expose HTTP, enable an AUTH
  profile, save, or claim 2D/gameplay authoring. Source/catalog drift and forged
  projections fail closed. Focused pure bridge/owner/session tests: **67**, exit0.
- The independent Windows run `o2-authoring-update-20261002-02` was interrupted
  before terminal closeout and remains non-PASS. Its raw evidence is retained; no
  effect or exit is inferred from the missing receipt.
- Run `o2-authoring-update-20261002-03` initially failed before owner creation because
  the scheduler worker lacked the trusted registry parents. The exact task was
  removed after tree/Job cleanup. The probe now calls the existing
  `RegistryCustody.provision_base()` before loading the owner, without changing ACLs
  or making normal create/reopen provision implicitly; setup-failure regression test
  exits0. Run03 remains `HARNESS_SETUP_FAIL`, authority0.
- Fresh run `o2-authoring-update-20261002-04` used a new frozen closure
  `8c2b257d833815a284d7d376576dcd3d57310fe713f4378309e7de663199cd70` and created
  the three trusted parents. Validation container exited0 and was cleaned, but the
  first registered `scene.node.create` then timed out waiting for the editor IPC
  response (`EDITOR_IPC_TIMEOUT` → `EDITOR_EDIT_UNKNOWN`); outer tree was verified
  and the editor Job was closed/zero/unretained, but the editor natural exit receipt
  is absent. The candidate bridge was not reached. Classify as
  `NATIVE_EDITOR_TIMEOUT_UNKNOWN_EFFECT`, authority0; no timeout increase, replay,
  or PASS claim. Exact task/XML/deletion receipt and raw closeout remain under
  `studio/.local/reviews/`.
- The native failure does not prove a bridge or Godot root cause. Existing source has
  no per-command breadcrumbs to distinguish apply, post-snapshot, or reply flush;
  adding markers or another native run needs a distinct reviewed reproducer. Continue
  static bridge/fixture work and keep GT-06/O1 gates unchanged.

## 2026-10-02 — Saved HUD composed with the native arena and publication owner

- Candidate catalog/resource context now admits `CanvasLayer` and `Label`; the saved-arena
  recipe persists a fourteen-node scene: the twelve physical nodes plus `HUD/Status`.
  The label is validated as a typed candidate (`text`, position, visibility and mouse filter),
  and the builder still verifies one atomic UndoRedo transaction, save, cache-ignore reload,
  ownership, distinct resources and exact snapshots. Authority remains0.
- Focused pure authoring/recipe/builder/publication/owner tests: **104**, actual exit0.
- Builder preflight passed (available memory12.41GiB, commit54.50%, no foreign engines).
  Publication used a second fresh O4.1 check:10.64GiB,58.14%, no foreign engines. `o2-saved-arena-20261002-06` used the pinned Windows Godot editor:
  actual editor/target/wrapper exit0, natural tree exit, Job closed/zero, no retained handles;
  builder verifier observed 202 native checks, 14 nodes and scene SHA256
  `563f773d8b30025baf859f1d967489abdbdb3a35943c67ecfe60174b645fff30`.
- `o2-publication-saved-arena-20261002-03` then used that exact scene through the real
  gameplay publication owner and Docker executor. Outer/host/container actual exit0, one
  native dispatch, READBACK_ACK generation2, live/reopened retry equal, CURRENT/journal
  unchanged, owned cleanup verified. The 150-tick physics oracle passed and
  `saved_hud_resolved=true` proves the loaded `HUD/Status` label drove the final HUD state.
  Raw evidence is under `studio/.local/reviews/`; `authority=0`, `public_ack=false`.
- InputMap and signal wiring remain runtime fixture logic. TileMap, audio, pause/restart,
  respawn and the real3D/Blender fixture remain open; candidate authoring is not yet a
  registered public adapter/profile and must not be described as a complete game or GT09 proof.

## 2026-10-02 — Saved physical world composed with native gameplay publication

- Added a private planned recipe: eleven node and five resource requests validated before
  native mutation; StaticBody2D/Area2D, body collision layer/mask and truthful collider ancestry
  fill only the fixture's catalog gaps. Fixed script-free Arena root is bootstrap, not
  a claimed public create command. Planned revisions/lease placeholders grant no runtime
  authority. Candidate profile stays disabled; accepted adapter unchanged.
- Builder prepares actual Node2D/CharacterBody2D/StaticBody2D/CollisionShape2D objects,
  reads ClassDB properties, attaches one UndoRedo transaction, verifies do/undo/redo,
  packs via PackedScene, saves via ResourceSaver and cache-ignore reloads exact semantics.
  Twelve nodes, five distinct RectangleShape2D resources, owner identities and no gameplay
  script in the Windows editor. Proof verifies exact project input set, plugin/frozen-source,
  recipe/scene bytes, pinned invocation and actual process receipts; a PASS field alone fails.
- Focused recipe/contract/resource/publication/builder suites:57 pure tests exit0. After
  numeric-comparison repair, builder verifier5 tests exit0. Run01 stopped before engine:
  Windows binary is in main tooling, not O2's Linux-only tooling. Run02 actual editor43,
  clean Job, rejected prepared snapshot because Godot Dictionary equality distinguishes
  JSON floats from native ints. Repair compares JSON numbers recursively while preserving
  bool/string types, exact keys/order/value. Native regression checks1==1.0,true!=1,1!=2.
  Run03 was interrupted during launch by the user turn; no terminal receipt/capture,
  no inferred natural exit. Raw preserved; no engine remained on resume.
- Fresh O4.1 then `python -B -X utf8 studio/tests/godot/run_saved_arena_builder.py
  --run-id o2-saved-arena-20261002-05 --godot <main pinned Windows GUI binary>`.
  21:59 Asia/Saigon:188 native checks (corrected from the earlier seven-node run count), actual outer/target/wrapper0, natural tree0,
  Job zero/closed/unretained, clean logs.24 frozen/current source files verified.
  Builder native scene binding was rederived before publication.
- Fresh O4.1 then `python -B -X utf8 studio/tests/godot/run_gameplay_publication_probe.py
  --run-id o2-publication-saved-arena-20261002-02 --fixture gameplay_arena_physics
  --saved-arena <absolute builder05 directory>`.22:00, actual outer/host/container0,
  one native dispatch, host attach11.875s. Required saved_world_instantiated=true;
  saved_actors_resolved=true with paths Pickup/Bot/Camera; 150-tick oracle observed jump/apex/
  landing, wall, pickup, shot/hit, input release, stop, camera/HUD win. Four-file native graph:
  fixture -> actor+arena, actor -> projectile.
  READBACK_ACK generation2; live/reopened retry keeps CURRENT/journal and no second dispatch.
  31 current/frozen probe sources and44 native artifact hashes verified; builder provenance
  copied/hash-bound/rechecked. Owned container removed, Job zero/closed/handles released,
  admission released. Raw log_clean=false remains; exact startup-log policy accepted=true.
- Runtime closure80300fb2f4dd699c4d01b982855ffa7334d756608eb90a4cefdfb07404c30cb4;
  actor SHA2560a509590f82eecb16a352d87d7c9d91e23702f4aa7f5c3ce30ca68e013da7f51.
  Raw under studio/.local/reviews/<run-id>/. AUTHORITY0/public_ack=false, not AUTH/GT09.
  Saved nodes are Player/Floor/Wall/Pickup/Bot/Camera and five colliders; HUD/InputMap/signals
  remain runtime. Next: bind remaining required arena content to candidate authoring; integrate
  registered transaction/adoption path and complete fixture gaps. No O2 merge or GT07 yet.

## 2026-10-02 — Real arena physics composed with publication and durable recovery

- Publication probe explicitly admits `gameplay_arena_physics`; requires native
  dependency observation for exactly fixture.tscn -> fixture_actor.gd -> projectile.tscn.
  The original input/physics/event oracle is unchanged. Both external templates
  arena_physics.gd and projectile.tscn are now in the frozen probe source inventory;
  loaded bytes must match the raw-hash-verified snapshot before native dispatch.
  Current/frozen drift, stale/missing projectile and disabled dependency policy
  reject.33 focused pure tests passed, actual exit0. First suite invocation had a
  Python import-path error; reran with studio on sys.path without a source workaround.
- Fresh O4.1 passed, then `python -B -X utf8 studio/tests/godot/run_gameplay_publication_probe.py
  --run-id o2-publication-arena-20261002-01 --fixture gameplay_arena_physics`.
  21:24 Asia/Saigon; actual outer/host/container exit0, one native dispatch.
  Runtime closure `80300fb2f4dd699c4d01b982855ffa7334d756608eb90a4cefdfb07404c30cb4`;
  actor SHA256 `6efd556e135935c350ed61f3e3f42015c13651f553c3a6e4a663b788ca0a53c9`;
  observed graph SHA256 `fb46d8cc6317a1d1a3f21f597ef74cd8642dd3d7bc9b801ad2b384cf4037072c`.
- Existing oracle observed150 physics ticks: pickup, projectile hit, jump/apex/
  landing, wall collision, released input and stop, camera/HUD win. Exact native
  three-file graph is byte-bound; arbitrary closure verification remains false.
  READBACK_ACK generation2 selected the matching source; live and reopened retries
  preserved CURRENT/journal and caused no second native dispatch. Reopen is durable
  owner/evidence readback, not a second Godot load of the selected directory.
- Host attach16.406s, no timeout; owned container removed, Job zero/closed, handles
  released and admission released.30 current/frozen source files and43 retained
  artifact hashes independently verified. Stderr contains only the exact expected
  guarded startup noise accepted by hh-gameplay-startup-log-1; raw log_clean=false
  is preserved, policy accepted=true and diagnostic_execution_complete=true.
- Raw: `studio/.local/reviews/o2-publication-arena-20261002-01/`. AUTHORITY0,
  public_ack=false; no AUTH/GT09 acceptance or full-game claim. This fixture still
  constructs the arena in typed GDScript at runtime; catalog-authored saved scene,
  TileMap/art/audio/pause/respawn and a real3D avatar/interactions remain unfinished.

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

1. Connect candidate scene/node/resource commands to the registered adapter boundary. The fixed
   fourteen-node saved scene already has native UndoRedo/save/reload and gameplay publication proof,
   but its builder is private diagnostic tooling. Preserve the existing lease/fencing, command
   identity, checkpoint, effect-time guards, native readback and durable recovery while integrating.
   Then complete2D TileMap/audio/pause/restart/respawn and3D avatar/camera/interactions through that path.
   Do not repeat completed sandbox/HUD confirmations solely to refresh hashes.
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
