# GT-06 formal07 — dispatch checkpoint, 2026-09-29

`AUTHORITY=0`; GT-06 remains `IN_PROGRESS` with zero accepted pairs. Formal06
is retained as a separate PRODUCT_FAIL closeout and was not resumed.

Fresh campaign `gt06-o4-formal-07` was registered and started through the
demand-only Task Scheduler task `\HHStudio.GT06.gt06-o4-formal-07` at
05:19:58 Asia/Saigon. The scheduler returned instance
`{A7B7036D-77E6-4C00-A3B3-2EDDFD5FA3E4}` and supervisor PID 2292. This is a
new two-pair campaign with 35 batches per pair and one attempt per pair; O1/O4,
timeouts and all acceptance thresholds are unchanged.

The source was verified and frozen before dispatch: 54 files,
`d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`, with
profile `9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`.
No GT06 task was live and no foreign Godot/Blender process existed. The local
date's INFRA_ABORT count is 0/2 because formal06 was a product failure.

The scheduling window observed CPU for 60 seconds: maximum 39.1576%, mean
23.2002%, minimum available RAM 6.3342 GiB, maximum commit 61.4317%, and zero
foreign engines. The campaign will perform its own O4.1 preflight/watchdog for
each pair. While live, do not run another engine/heavy suite, modify measured
source, or compress growing raw evidence. On terminal state, verify actual
exits, Job/tree/handle cleanup, source/profile hashes and complete dataset.

If both pairs complete and pass, prepare the O4.3 CRITIC_PACKAGE for the owner;
do not self-call critics or sign acceptance. If it fails, preserve raw and
classify strictly under O1/O4; never restart or relabel the run. GT-07 remains
unopened.
