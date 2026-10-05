# GT-06 formal06 — dispatch checkpoint, 2026-09-29

`AUTHORITY=0`; GT-06 remains `IN_PROGRESS`, with zero accepted formal pairs.
This records a live launch, not a terminal result or acceptance verdict.

Demand task `\HHStudio.GT06.gt06-o4-formal-06` dispatched at 04:58:40
Asia/Saigon on 29 September. At 05:01 the scheduler had one running instance
`{9D73596F-D2ED-4627-965A-21A30BD9D0C2}` and its supervisor PID 1432,
host PID 23576 and Godot PID 12112 were live. Pair 1 had completed batch 0.
The interrupted tool observation did not stop the campaign and must not
trigger a restart. Always recheck live process/task state before acting.

The source closure is unchanged:
`d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`.
All 54 current and freshly frozen source files were checked byte-for-byte.
Profile SHA-256 is
`9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`.
The campaign remains two fresh pairs, 35 batches each, one attempt per pair;
O1/O4, timeouts and acceptance thresholds are unchanged. No unchanged test
suite was rerun for dispatch.

Preflight observed 60 seconds before dispatch: minimum available RAM 11.8237
GiB, maximum commit 46.5761%, maximum system CPU 23.5632%, and no foreign
Godot/Blender. App names remained inventory only. There were zero recorded
INFRA_ABORT attempts for local date 2026-09-29; formal04/05 exhausted the
previous day's budget only. The campaign enforces a fresh O4.1 preflight for
each pair and keeps its watchdog active.

Raw stays under `studio/.local/reviews/`:

- `gt06-o4-formal-06/` and `gt06-o4-formal-06-supervisor/` are live evidence.
- `gt06-formal06-preflight-20260929-045828.json`, SHA-256
  `23e64a660d129819e02633c10c62117eab7e10153c820c18ab9c8afcd05df86b`.
- `gt06-formal06-dispatch-checkpoint-20260929.json`, SHA-256
  `b0f551428859f62f5359a3131273b29512b83579a14511d02caa44216d5624cf`;
  binds campaign, profile, request, scheduler dispatch and supervisor start.

While live, only observe; do not run another engine/heavy suite, compress the
growing raw directory, or alter measured source. On terminal state, verify
actual exits, Job/tree/handle cleanup, source/profile and complete dataset.
Package immutable raw only then. A fully valid 2x35 PASS leads to an O4.3
CRITIC_PACKAGE for the owner; two independent same-hash reviews are still
required. Failed or terminal runs are never resumed. GT-07 remains unopened.
