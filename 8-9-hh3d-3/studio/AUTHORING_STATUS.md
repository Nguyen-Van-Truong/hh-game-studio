# O2 authoring state — 2026-10-02

AUTHORITY=0. Branch `codex/o2-authoring-contract`; no merge before GT-06 ACCEPTED.
Tools-plan O1–O8 governs; test counts/native diagnostics do not close AUTH or a WP.

## Current state

- Typed nodes/resources, scene instances, signals/InputMap, animation and six-effect gameplay
  shortcut have candidate validation/native readback; generic typed gameplay uses gameplay-source.
- Blender template armature/action, geometry/material/UV, GLB export and 2D sprite import have
  separate diagnostics; neither asset presence nor a marker proves complete authored gameplay.
- Publication owner supports readback ACK, lease/revision checks, idempotent retry and reopen.
  Dependency-enabled lifecycle has pure proof; native dependency run20261002-03 stopped at
  Docker CLI inventory5s before container creation. Old failure remains unchanged.
- O8.3b repair verified by 71 focused pure tests, exit0: exact-label/all-container bounded named-pipe inventory replaces only that
  admission CLI call, preserving5s and fail-closed ownership. Test/confirmation details below.
- AUTH-03 native type rejection preserves last-good CURRENT/journal and avoids third dispatch.
  Source binding is historical; do not combine different runs' runtime or probe hashes.
- AUTH-05 hostile boundary/spawn/network/timeout observations remain separate cases.
  Adapter boundary run20261002-01 preserves last-good but predates the later run-ID harness
  validation; keep it as historical diagnostic, not a run of today's harness or AUTH acceptance.
- O8.3a physics repair re-evaluated44 raw artifacts from20260929-03: corrected trace/lifecycle
  check true; original verifier FAIL unchanged. Supplemental below; fresh native confirmation open.
- GT-06 formal10 is terminal; no measured workload active at last check. Recheck process/lock
  before engine/Docker work; when formal runs, static work only and one writer per file.

## Next actions

1. Review/test O8.3b repair, then one fresh dependency publication confirmation when host allows.
2. One physics native confirmation after the offline repair; preserve raw and actual exit/cleanup.
3. Complete fixture-specific adapter AUTH-02..05 evidence, then authored2D arena and3D room E2E.
4. Keep GT09/GT10 acceptance, human playtest and two independent critics separate from diagnostics.

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
