# GT06 progress review — S149 host handles

**Review scope.** Read-only audit of the S148 plan state, S147 terminal packet, the
S148 attribution, and the S149 host-handles packet. No source, runtime, plan, gate,
tick, or engine changes were made. The current runtime closure remains
`fce149cd3a62e102aaba225794b9a5078cd84d7647cb359f6bbcacb8895ddcde`; the S146
installed execution closure remains
`78ffef60682f596313aac8aca69a06e0a23808c546202effdebc481bdb845b58`.

## Current product state

- The authoritative tool plan is still **GT-06 / IN_PROGRESS**. GT-01 through
  GT-05 are accepted; GT-07 through GT-10 remain blocked behind GT-06.
- GT-06 has **zero accepted full runs**. Its required campaign is still
  10 fresh host/editor pairs × 35 batches (5 warmup + 30 measured), with the
  original gates, actual target/helper exits, complete raw/hash/schema/counter
  evidence, and two new independent critic PASS/TICK=yes reviews on one frozen
  final closure.
- S147 formal campaign `gt06-s147-formal-01` is a retained failure:
  `accepted_full_runs=0`, `completed_batches=11`, `engine_runs=1`, and
  `CAMPAIGN_RETAINED_COUNTER_GROWTH` at batch 10 / `joint_observation`.
  The actual host exit is 1; import exit is 0; editor target exit is UNKNOWN.
  Cleanup reports no retained wrapper/job/thread resources, but this does not
  convert the failed run into a pass.
- S148 attribution correctly preserves the failure and gives no source repair:
  host held handles are 204 for batches 0–9 and 205 at batch 10, while editor
  handles, RSS, ObjectDB, and resources do not show the same growth. A process
  handle count does not identify the descriptor class or prove a leak/root cause.
  S143/S144/S145 are separate workloads and cannot establish causality for S147.

## S147 packet and claim hygiene

The terminal manifest has **17 exact packet entries**, but
`attribution-01.json` is explicitly a derived read-only file assembled from
raw command/joint rows. Therefore “17 exact files” is not “17 independent raw
observations.” The packet remains AUTHORITY=0, outside F13/F14 and the dataset.
The S147 liveness prefix is historical only and cannot override the batch-10
terminal failure. Do not infer a natural editor exit from the missing editor
exit record, and do not infer descriptor identity from the 204→205 count.

## S149 status

The prerequisite smoke `gt06-s149-handles-smoke-01` completed with actual target
exit 0, helper exit 0, verified capture, released probe, closed Job, no live
threads, and unchanged source. It exercised one bounded host batch and one
external census checkpoint. Its summary is AUTHORITY=0,
`formal_acceptance=false`, `eligible_for_dataset=false`, and explicitly
omits native/ACK/idle/assembly coverage. The observed smoke host count (173
handles, RSS 32,440,320 bytes) belongs to a fresh smoke process and cannot be
compared as a campaign result with S147’s 204/205 sequence.

The smoke is a prerequisite, not the requested 11-batch diagnostic and not a
boundary result. The owner process-start receipt records the PID; the checkpoint
and retained ProcessProbe carry the start identity used by the binding check.
Do not describe the standalone receipt as a complete creation-time proof.

## Stale or redundant state

- The S148 plan header still says
  `EXECUTION_MODE=COORDINATOR_SOLO_OWNER_20260921_S148`,
  `SUBAGENTS_ENABLED=NO_OWNER_REQUEST`, and `GT06_ACTIVE_DIAGNOSTIC=NONE`.
  Those fields predate the owner’s current authorization for three Astra
  extra-high workers and the S149 smoke. They are stale routing metadata, not
  evidence that workers or a full diagnostic are absent. Coordinator should
  refresh the authoritative header before dispatching new work.
- S148’s “do not launch a new diagnostic/formal run until a separately evidenced
  boundary or repair hypothesis exists” remains valid for the S147 failure, but
  S149 now supplies a separately scoped host-only hypothesis probe. It does not
  authorize a blind formal retry or change the GT06 DoD.
- Existing S133–S148 worker/coordinator material is historical evidence already
  integrated into the plan. Do not rerun accepted lanes, reuse their signatures
  against a changed closure, or treat Astra capacity/dispatch messages as
  completed evidence. No new critic PASS exists.

## Critical path and safe parallel work

1. Finish the single fresh S149 host-only run after the smoke prerequisite,
   using unchanged `CommandProducer.run_batch`, fresh IDs, the original
   host RSS/handle/status gates, five warmups, and a stop at the first original
   gate failure or the final boundary. Keep the PSS census externally owned and
   bound to the helper PID plus process start. Preserve actual exits and cleanup
   even on failure.
2. At terminal, compare only descriptor-class observations and redacted entry
   fields. If the handle growth does not recur, record non-reproduction and do
   not loop retries. If a concrete class is measured, prepare one narrow repair
   hypothesis and focused affected regressions; do not alter a gate, timeout,
   baseline, profile, or workstation.
3. Only after a concrete repair and its focused verification may coordinator
   mint a fresh formal campaign. A new formal run must still be the unchanged
   10×35 campaign and must produce a complete accepted dataset before GT-06 can
   move.
4. While the host-only run occupies the engine/benchmark lane, Astra workers can
   safely perform read-only work in separate files: raw/manifest cross-checks,
   requirement→evidence mapping, stale-status reconciliation, and critic-ready
   closure checklists. They must not mutate shared runtime source, run a second
   engine/campaign, or manufacture verdicts.
5. The final GT-06 gate remains: complete raw and hash closure, actual target and
   helper exits, Job/handle/thread cleanup, source freeze, then two independent
   critics reading that same final hash with explicit PASS/TICK=yes. GT-07
   cannot open before that coordinator acceptance.

**Disposition:** retain S147 as failed AUTHORITY=0 evidence; retain S149 smoke as
a successful but non-acceptance prerequisite; keep GT-06 open and do not claim a
root cause, no-leak result, formal pass, or GT-07 readiness.

