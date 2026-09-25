# HH Studio tools handoff — S251

**Authority:** 0 (handoff/reference only; it does not accept a gate or change the plan)
**Workspace:** `8-9-hh3d-3`
**Plan:** `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt`
**Snapshot:** 2026-09-25 Asia/Saigon, coordinator branch `codex/hh3d-s14-bootstrap`, HEAD `4ee1000197e143be6b7c3d7ff2f90c85c34d2964`

## One-sentence state

GT01–GT05 are historically accepted; GT06 is still the only current work package, remains `IN_PROGRESS` with **zero accepted full benchmark runs**, and GT07–GT10 must stay unopened.

## What is already accepted

- **GT01:** official Godot 4.7.2 bootstrap and independent fixture (`a0fb247`, S21 evidence).
- **GT02:** protocol, leases, journal, validation and scoped safe-write baseline (`reviews/20260916-gt02-s46-audit/acceptance.json`, two critics).
- **GT03:** Godot typed EditorPlugin mutation, UndoRedo, staged save/readback (`323882b`, S55, two critics).
- **GT04:** Blender main-thread adapter and bounded background publication (`38f6b9a`, S60, two critics).
- **GT05:** staged Blender → GLB → Godot fixture pipeline, rig/clip intake and naming lint (`808d8ba`, S64, two critics).

Do not rerun or reinterpret these closures while their dependencies remain unchanged. Their scope is the published fixture/catalog; it does not prove arbitrary gameplay authoring, a complete game, Web/Y8 parity, or HH World.

## GT06 work that exists, but is not accepted

The functional fixture lanes have real Play/editor separation, 60 Hz input traces, menu/play/move/interaction/pause/resume/quit, capture/inspect/perf export, seeded repair/replay, HTTP/Stop, reviewer UI, and adversary lanes. S177 consumer-pilot evidence is provisional Authority0 and is not GT06 acceptance. Reuse it only after checking the exact dependency/source closure.

The formal gate is frozen:

1. Ten fresh host/editor pairs.
2. Thirty-five batches per pair: indices 0–4 warm-up, 5–34 measured.
3. Each batch has 1000 HTTP commands and 100 native create/undo/save/reload cycles.
4. Same PID/start identity through all 35 batches; post-batch-quiescent batch 4 is the baseline.
5. Every measured sample must satisfy the existing RSS, host-handle, editor-object/resource/OS-handle limits; one over-baseline sample fails. Status-gap, p95 and 7410-second run limits remain unchanged.
6. Final evidence must contain the complete dataset/schema/source hashes, real target/helper exits, owned-tree/Job/handle cleanup and two independent critics on the same final hash before the coordinator can accept GT06.

No counter attribution is an acceptance shortcut. The policy is diagnostic-only unless an owner ADR explicitly changes it.

## Latest formal result

`gt06-s246-formal-01` is sealed as Authority0:

- Packet: `zdoc/reviews/20260925-gt06-s246-counter-failure`
- Raw: `8-9-hh3d-3/studio/.local/reviews/gt06-s246-formal-01` and sibling `-supervisor`
- Raw manifest SHA256: `e3e4be50cde3e0fcbe43958efa9ed462eae6984999e06f2e7b71e4dca733ecbe`
- Archive: `8-9-hh3d-3/studio/.local/archives/gt06-s246-formal-01-s247-counter-failure.zip`
- Archive SHA256: `8c11df0104dd6da3bb404117cb2e01da672cc9d4e85db624726e88a8f5c02635`
- Source closure: 53 files, `1f6b7da7f48085b417e5d6d7f3388c75c0a8beadad3659b14057a2a6e71df625`
- Profile SHA256: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`
- Captured batches: 0–7; measured run failed at batch 7 because editor held handles went from baseline batch 4 `558` to `559`. Objects `71160`, resources `6`, host handles `204` stayed stable. This is a gate-row failure and diagnostic attribution only; it proves neither a leak nor ownership/root cause.
- Import target exit was observed as `0`. The editor target has no natural-success exit proof: the retained cleanup observation is exit `2` after forced cleanup and marks `natural_exit_not_inferred=true`; host/supervisor target exits remain unknown. Jobs/tree/owner/producer handles were closed/released.

The scheduler is not process evidence. The task `\\HHStudio.GT06.gt06-s246-formal-01` is still registered in Task Scheduler with state `3` (Ready), last result `1`, and no instances. Do not describe it as retired, running, or passed from that registration. Inspect actual PID/start/executable and raw evidence before any future decision.

## Power-recovery impact

S239 was interrupted after import and batch 0 became ready. S240 preserved and audited it; the machine reboot invalidated old PIDs and liveness. The audit recorded 22 Event 41 boot records across the outage window, bugcheck/WHEA boot error fields at zero, and a `volmgr` 46 crash-dump-initialization failure. These records do not prove the cause was absent and do not make the interrupted run resumable. The board/BIOS changed, so a new workstation preflight is required for any future formal campaign. Never reuse S239 PIDs, partial rows, or campaign IDs.

S250 is read-only GT07–GT10 preparation only: `adb` was not on PATH and physical Android device status is `UNKNOWN_NOT_TESTED`. That is a PATH/prerequisite gap, not proof that no SDK or device exists. GT08 remains unopened and physical Android remains a hard gate.

## Source and repair history that matters

S243 commit `a5dfb42` moved successful readback receipt persistence outside the host state lock and made the FINALIZING cancel path fail closed. Focused transport/recovery/drain/command tests were reported green, and a bounded 100-command probe was low-gap. This proves one response-serialization boundary only; it does not prove that all terminal persistence contention or the S246 counter row is repaired. Keep the 53-file formal closure and frozen gate unchanged.

S243/S245/S248/S249/S250 are preparation or diagnostics. Their evidence must remain separate from formal 53-file evidence. S248 compares the retained counter series and found no supported new boundary. S249 corrects one read-only catalog source drift. S250 only records environment prerequisites.

## First actions for the successor

1. Read `8-9-hh3d-3/AGENTS.md`, this handoff, and the first marker block of the plan. Do not use old heartbeat text as state.
2. Run `git status --short --branch`; inspect actual processes and the current workstation before touching a formal lane. Do not start Godot, Blender, CDB, or heavy tests merely to refresh metadata.
3. Verify the 53-file source map and frozen profile against the current checkout. A source or workstation change requires a fresh preflight and fresh campaign ID; never rebind old raw evidence.
4. Read S246 raw and packet verifier before proposing a new experiment. A new formal run needs either (a) an owner ADR or (b) a genuinely distinct, supported measurement/harness boundary with a bounded diagnostic proving what it distinguishes.
5. If a new campaign is authorized, verify source/profile/workstation/Stop latch, dispatch a fresh ID, and preserve raw before deriving metadata. On terminal, bind every PID to its recorded start time and executable, verify actual exits/trees/Jobs/handles/cleanup, then seal. Never merge partial rows, reuse IDs, infer exit from scheduler/wrapper disappearance, or alter timeout/baseline/profile/counter/RSS thresholds.
6. Only a complete 10×35 dataset can move GT06 to candidate. Then freeze the final manifest and obtain two independent critics on that exact hash. The coordinator alone cannot sign either critic verdict.
7. After GT06 is accepted, open GT07, then GT08 (including a physical Android device), GT09, and GT10 in order. GT10 must produce the local-trust package, install/upgrade/rollback/uninstall proof, support runbook and handoff manifest.

## Do not do these things

- Do not open GT07–GT10 early, build HH World/Vault Fighters/Superagent, or treat this fixture as a complete game.
- Do not change the 10×35 gate, timeout, RSS/counter baseline, priority, RAM, or sampling to make a run pass.
- Do not turn `UNKNOWN`, scheduler state, a banner, wrapper exit, or a killed process into a successful target exit.
- Do not delete raw failures, `.local` archives, old task registrations, caches needed for proof, or accepted evidence. Do not commit `.local`, secrets, `.godot`, build output, or tokens.
- Do not claim Blender plus these tools can automatically author a full game of Super Fighter 2D or HH World. Current public proof is limited to the declared fixture operations; general controller/combat/UI/audio/physics/gameplay-script authoring still needs a versioned consumer change request and evidence.

## Handoff prompt to paste to the next agent

> Continue only `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt` in the HH Studio repository. Read `8-9-hh3d-3/AGENTS.md` and `8-9-hh3d-3/zdoc/reviews/20260925-tools-handoff-s251/HANDOFF.md` first. Treat the S251 handoff and the plan’s top marker as current state: GT01–GT05 accepted, GT06 in progress with zero accepted full runs, GT07–GT10 unopened. Verify Git/process/workstation state before work. Keep the frozen 53-file formal source closure `1f6b7da7f48085b417e5d6d7f3388c75c0a8beadad3659b14057a2a6e71df625`, profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`, and all gate limits unchanged. S246 is a retained counter-row failure, not acceptance; raw and archive hashes are in the handoff. The Task Scheduler entry is Ready with no instances and is not process proof. Do not rerun S246 unchanged. Proceed only with a distinct supported measurement/harness boundary or an owner ADR; otherwise do read-only preparation and keep GT06 current. Preserve raw before metadata, use fresh IDs after any source/workstation change, and require two independent critics on the exact final 10×35 hash before accepting GT06 or opening GT07.

## Useful evidence locations

- Current plan: `8-9-hh3d-3/zdoc/8-9-godot-blender-agent-studio-plan.txt`
- S240 power audit: `8-9-hh3d-3/zdoc/reviews/20260925-gt06-s240-power-recovery`
- S241 status-gap seal: `8-9-hh3d-3/zdoc/reviews/20260925-gt06-s241-status-gap`
- S243 repair record: search the plan for `S243_SOURCE_REPAIR` and inspect commit `a5dfb42`
- S244 import-wall seal: `8-9-hh3d-3/zdoc/reviews/20260925-gt06-s243-import-wall`
- S245/S246 import diagnostic: `8-9-hh3d-3/zdoc/reviews/20260925-gt06-s245-import-diagnostic`
- S246 formal raw/packet: paths listed above
- S248 counter series: `8-9-hh3d-3/zdoc/reviews/20260925-gt06-s248-counter-series`
- S249 catalog correction: `8-9-hh3d-3/zdoc/reviews/20260925-gt07-10-catalog-correction-s249`
- S250 environment preflight: `8-9-hh3d-3/zdoc/reviews/20260925-gt07-10-environment-preflight-s250`

This document is a navigation aid for the next agent. It does not replace raw manifests, packet verifiers, the plan, or the two-critic acceptance gate.
