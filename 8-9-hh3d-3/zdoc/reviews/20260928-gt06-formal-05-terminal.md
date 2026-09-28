# GT-06 formal05 — terminal INFRA_ABORT, 2026-09-28

`AUTHORITY=0`; GT-06 remains `IN_PROGRESS` with zero accepted formal pairs.
Formal05 used the second and final O4.1 infrastructure attempt for local date
2026-09-28. Pair `run-00-attempt-01` completed 16 batches (0–15), then the
watchdog stopped the run. Pair 2 never started.

The raw watchdog replay reproduces `CAMPAIGN_WATCHDOG_CPU_PRESSURE` after more
than 60 seconds of system CPU pressure. The classification is `INFRA_ABORT`
and does not waive any product gate or prove a pass. Scheduler is Ready with
zero live instances and LastTaskResult 1. Cleanup proves wrapper exit 2, a
closed Job, zero active children, zero retained handles, and no cleanup error;
it does not prove natural host/editor exit 0.

All 54 campaign source files match the frozen closure
`d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`. The 16
complete batch captures contain 96 referenced artifacts whose size and SHA-256
were read back successfully. The largest observed status gap in the completed
prefix was 1084.837 ms. There is no dataset and no formal acceptance.

Raw evidence remains at `studio/.local/reviews/gt06-o4-formal-05/` and
`gt06-o4-formal-05-supervisor/`. The verified closeout is
`studio/.local/reviews/gt06-formal05-closeout-20260928/`:

- manifest SHA-256: `d1cb3a0ac4820b6703548b552b8fb4ce68da6d4adace7183afa582f7035a9eaf`
- raw archive SHA-256: `d2d60d00e3f8c66eb72748bb8eb7c194372742fd7e14895b086dad2920f2c4d1`
- scheduler terminal receipt: `scheduler-terminal.json` (Ready, zero instances,
  LastTaskResult 1, no remaining Godot/Blender process).

Both formal04 and formal05 consumed the two permitted infrastructure aborts on
2026-09-28. Do not launch another GT06 campaign today, resume either run, or
change O1/O4 thresholds. The next safe action is O2 static work in its separate
worktree, followed by a fresh O4.1 preflight and a new campaign ID on a later
local date. Owner critics are still required after a complete formal dataset.
