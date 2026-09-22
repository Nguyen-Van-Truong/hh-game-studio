# GT07–GT10 read-only order (S163)

`AUTHORITY=0` · `FORMAL_ACCEPTANCE=false` · `ENGINE_RUNS=0`

This memo is planning-only. It does not open a work package, create runtime
evidence, or replace the GT06 gate.

## Boundaries

- Plan: `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt`
- Plan revision: `S163`
- Plan SHA256 at memo creation: `89E3AC3A3675624B9C87DB0D00BEDD1E4439CA72E09EF14E3EA7CCB2DE97CC03`
- GT06 source closure: `fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde`
- Profile SHA256: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`

GT06 remains the first open dependency. It still requires debugger attribution,
10 fresh host/editor pairs × 35 original batches, complete raw/hash/schema/
counter/exit/tree/job/handle evidence, a frozen requirement→test→evidence
manifest, and two new independent critics with `PASS/TICK=yes` on that same
final hash. S161–S163 fixture and debugger attempts remain diagnostic only.

## Safe order after GT06 acceptance

1. **GT07** — scheduling/concurrency, leases/fencing, recovery, and cross-app
   activation. Prepare only schemas, lease/recovery fixtures, and failure-case
   checklists now; do not run activation or mutate source while GT06 is open.
2. **GT08** — clean Windows/Linux/Android import/export and CI/cache matrix.
   Record the physical Android device prerequisite; an emulator or PATH lookup
   cannot satisfy the Android hard gate.
3. **GT09** — client conformance and the pinned MCP compatibility spike on the
   sample fixture. Keep the spike read-only until GT08 is accepted.
4. **GT10** — package, install, upgrade, rollback, uninstall, and handoff. This
   is the first tool handoff point for a separate game vertical slice.

The only useful work before GT06 closes is static review/checklist preparation
and preserving failed evidence. Do not retry the engine, installer, debugger,
or formal campaign merely to advance this memo; do not alter timeout, baseline,
RSS policy, priority, source, or profile.

## Separate vertical-slice handoff

The first game slice is a separate deliverable after the tool handoff: Godot
owns runtime/gameplay and Blender owns source asset/export. Its minimum scope
is one original map, combat, pickup, pause, save/load, and a deterministic
seeded test. This memo is not implementation or acceptance evidence for that
slice, and it does not touch the game plans.

## Current blocker and next action

`BLOCKER=SUPPORTED_DEBUGGER_BOUNDARY_MISSING`. `wpr/tracerpt` and `dbgeng.dll`
are present, but no runnable CDB/WinDbg `!htrace` integration is available and
S162/S163 did not expose a usable current process/event. The next admissible
step is one bounded attribution run after a supported debugger environment is
provided. Until then, keep GT06 and GT07–GT10 unopened.
