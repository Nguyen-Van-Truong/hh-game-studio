# Current state for independent agent review — 2026-09-27

## Scope and authority

The authoritative execution plan is `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt`.
It currently reports `CURRENT_VALID_WP=GT-06`, with GT-01 through GT-05 accepted,
GT-06 in progress, and GT-07 through GT-10 unopened. This report is an audit
summary for an independent reviewer; it does not change a checkbox, gate, or
acceptance decision.

## What has been completed and accepted

- GT-01: pin/scope/reuse/bootstrap baseline accepted.
- GT-02: command protocol, capability, journal, and minimum safety accepted.
- GT-03: Godot EditorPlugin mutation, UndoRedo, save/readback accepted.
- GT-04: Blender adapter/UI and background-job safety accepted.
- GT-05: `.blend -> GLB -> Godot` pipeline and asset manifest accepted.

These are historical plan acceptances. They do not mean the O2 authoring
candidate or a complete game is already accepted.

## GT-06 status and hard gate

GT-06 has **zero accepted formal full runs**. The current O1 gate requires:

- two fresh host/editor pairs;
- 35 batches per pair (5 warmup and 30 measured);
- fresh campaign IDs; S258 must never be resumed;
- the frozen source/profile closure, actual process exits, owned-tree/job/handle
  cleanup, required counters, status-gap and duplicate/lost-effect checks;
- two independent read-only critics signing the same final source hash.

The latest recorded plan preflight is `2026-09-27T08:04:28Z`: 7.14 GiB free,
73.31% commit, and heavy Chrome/Firefox/Edge/Telegram/Zalo/WSL processes;
result `CAMPAIGN_PREFLIGHT_HEAVY_APPS`, `PASS=false`. A later direct snapshot at
08:13:28Z still failed the same latch (6.83 GiB free, 73.65% commit, the same
heavy-process set). It was not recorded as a second plan snapshot because the
plan explicitly records an unchanged blocker once. No formal campaign was
started from either failed preflight.

## O2 authoring lane retained in isolation

O2 remains on branch `codex/o2-authoring-contract`, separate from the formal
GT-06 source. The latest branch commit is `8eb2c039`; no O2 source is merged
before GT-06 acceptance.

Implemented candidate areas include typed scene/resource/TileMap authoring,
2D/3D animation playback, declarative gameplay effects and native dispatch,
and a closed declarative script-profile parse/attach/readback boundary. The
latest combined static regression has **151 passing tests**. The latest native
Godot diagnostic is `o2-native-20260927-33`: **396 checks**, host and wrapper
exit 0, owned process tree verified clean, clean log, unchanged source/project
snapshots, and a frozen 20-file closure. These are `AUTHORITY=0` diagnostics.
They do not prove public authorization, OS sandbox/AUTH-05, atomic
save/reload, multi-agent lease/recovery, or product acceptance.

The retained failed attempts (`-30` gameplay compile and `-32` script-profile
compile) remain raw historical evidence and were repaired by source changes;
they were not relabeled as PASS.

## Blender evidence and limits

The available native Blender evidence is `o2-blender-native-20260926-16`,
`AUTHORITY=0`, with 18 checks for armature/template geometry, action/keyframe
creation, native UI undo/redo, and reopen. It does not prove full geometry,
materials, UVs, export/import, or a game-authoring workflow. The pinned
Blender 5.2.1 archive exists locally and its SHA256 matches `toolchain.lock.json`;
a verified extracted executable and a fresh native probe are still pending in
this checkpoint. No system PATH or global toolchain mutation is allowed.

## What the earlier agent assessment got right

- Formal progress is slow because O1.8 preflight is blocking the only current
  acceptance lane.
- S258 is sealed and must not be resumed.
- O2 is isolated and useful for bounded capability work, but it is not GT-06
  evidence.
- AUTH-05/sandbox, integration, save/reload, publication, and complete
  gameplay authoring remain unproven.
- A full game with quality comparable to a commercial/Y8 title is not shown by
  GT-01..GT-05 or the current O2 diagnostics.

## What was stale or unsupported in that assessment

- Its RAM/commit/process numbers were older than the latest preflight and must
  not be quoted as current.
- The claim that warmup removed required status-gap/counter checks is false for
  the current verifier; warmup only skips growth-baseline checks.
- Relaxing O1.8 or opening GT-07 in parallel was not authorized by the current
  plan and was correctly rejected.
- Static code quality and candidate tests do not justify claims of a complete
  Godot+Blender game, public ACK semantics, or secure sandboxing.

## Issues the independent reviewer should assess in the plan

1. **Formal environment dependency:** GT-06 cannot progress until unnecessary
   heavy applications are closed and a fresh full preflight passes. The plan
   should keep this visible without duplicating unchanged snapshots.
2. **Evidence authority boundaries:** O2 native probes are strong diagnostics,
   but the plan must continue to label them authority 0 and prevent accidental
   promotion to GT acceptance.
3. **Blender coverage gap:** geometry/material/UV/export/import and an actual
   Blender-to-Godot content loop still need pinned native evidence before GT-09.
4. **AUTH-05 and mutation security:** validated schemas, UndoRedo and temporary
   probes do not establish an OS sandbox, path isolation, symlink/traversal
   defense under hostile inputs, or public profile authorization.
5. **Product conformance gap:** no mini-game conformance package yet proves
   input, physics/combat, UI, audio, save/reload, export, or human/product
   acceptance. Do not claim Super Fighter 2D/HH World parity from tooling work.
6. **Plan hygiene:** keep GT-07..GT-10 read-only until GT-06 is accepted;
   preserve one-WP/one-commit discipline and fresh IDs after every source
   change; retain failed raw evidence instead of rewriting it.
7. **Critic independence:** coordinator or implementer summaries cannot replace
   two independent same-hash critics. A read-only audit agent may report gaps,
   but cannot sign acceptance.

## Reviewer decision requested

Please review the source plan, this summary, the cited commits/evidence, and
return: (a) any factual error, (b) any gate or authority ambiguity, (c) any
missing acceptance condition, and (d) the smallest safe improvement that can
be made without opening GT-07 or weakening GT-06.

