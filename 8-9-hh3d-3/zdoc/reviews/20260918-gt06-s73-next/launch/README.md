# S73 campaign startup observation

Source checkpoint `cb4d1f6f`, campaign `gt06-s73-campaign-01`, launch 1.
The scheduler dispatched at `2026-09-17T21:11:26Z`. A separate live query
confirmed state 4 and one matching instance. The observation at
`2026-09-17T21:12:57Z` found host progress in batch 1 and native PID 2984
heartbeats for the same run, with empty host/editor stderr.

All 49 campaign source hashes equal the prior Git HEAD proof in
`../../20260918-gt06-s73-recovery/source-git-head.json`. Source closure:
`6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`.
The benchmark profile is unchanged. Static input copies retain exact bytes;
`observation.json` records raw paths, sizes and hashes. Startup is not a
completed benchmark or proof of final cleanup.

The first observation collector required a transient `commands` phase and
failed when the log advanced. Its successful scheduler/static captures are
retained. `startup-collector-note.json` explains the correction to matching
run/progress markers; the campaign was not relaunched and source was not
changed. Live scheduler and tail observations have separate timestamps.

The existing thread heartbeat was updated in place for this campaign at a
15-minute interval; `overnight-schedule.json` is its readback. Keep source
fixed and avoid other engines, tests and broad audits while measuring.
Query live task status and bounded tails on continuation. The full gate
remains 10 fresh process pairs with 5 warmup plus 30 measured batches each,
followed by final verification and two independent critics.
