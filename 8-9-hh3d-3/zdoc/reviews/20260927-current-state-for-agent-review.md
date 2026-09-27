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

O4 (owner-delegated commit b0802472) supersedes the previous app-closure
preflight. The latest old-rule snapshot (08:26:45Z) had 5.22 GiB available and
75.28% commit and was not launch permission. The implemented O4 preflight at
09:01:55Z reported 10.24 GiB available, 68.84% commit, no foreign engines and
PASS while 58 application entries remained. Every actual launch still needs a
fresh captured preflight. The new harness remains subject to final critics.

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

The latest native Blender diagnostic is o2-blender-native-20260927-17:
18/18 checks, native/reopen exits 0, verified tree, unchanged source/project,
AUTHORITY=0. Archive and executable match the Blender 5.2.1 lock. It proves
armature/template geometry, action/keyframe authoring, native UI undo/redo and
reopen only. General geometry/material/UV and authored game content loops
remain open. Details and fixture gaps now live in studio/AUTHORING_STATUS.md
on the isolated O2 branch (0faf7c44).

## What the earlier agent assessment got right

- The old O1.8 preflight blocked launch. O4.1 now permits normal apps under
  resource and engine-inventory limits; code correctness still needs formal proof.
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
- CORRECTION: the reviewer said the newer verifier TIGHTENED warmup checks,
  not that it removed them. Inspection of 87912523 confirms status-gap checking
  began at index >= 5 there. Current source checks warmup too; O4.2 explicitly
  approves this tightening. The previous coordinator assessment was wrong.
- App-closure relaxation was not authorized before O4; it is now authorized
  by O4.1. GT-07 remains sequential. The earlier restriction is historical.
- Static code quality and candidate tests do not justify claims of a complete
  Godot+Blender game, public ACK semantics, or secure sandboxing.

## Issues the independent reviewer should assess in the plan

1. **Formal environment dependency:** implement and verify O4.1 resource/engine
   preflight and watchdog. App closing is no longer required. No workload PASS
   follows from passing preflight; preserve product failures over infra stops.
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
   but this report is not an acceptance signature. O4.3 requires two independent
   final critics through the owner review route.

## Reviewer decision requested

Please review the source plan, this summary, the cited commits/evidence, and
return: (a) any factual error, (b) any gate or authority ambiguity, (c) any
missing acceptance condition, and (d) the smallest safe improvement that can
be made under O4 without opening GT-07 before GT-06 acceptance.
