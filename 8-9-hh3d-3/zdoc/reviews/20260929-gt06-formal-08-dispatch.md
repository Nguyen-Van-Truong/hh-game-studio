# GT-06 formal08 dispatch — 2026-09-29

`AUTHORITY=0`; GT-06 remains `IN_PROGRESS` with zero accepted pairs. Formal07
was closed as `PRODUCT_FAIL/TERMINAL_TIMEOUT` at batch 31; its simultaneous
watchdog foreign-engine signal is retained and was reviewed under the existing
child-failure precedence rule. No terminal run was resumed.

Fresh campaign `gt06-o4-formal-08` was registered and started through the
demand-only Task Scheduler task `\\HHStudio.GT06.gt06-o4-formal-08` at
`2026-09-29T00:21:10.4576798Z` (07:21:10 Asia/Saigon). The scheduler returned
instance `{B4B71F93-2C4A-4324-873B-FA09A857F11E}` and scheduler engine PID
35860. This is a new two-pair campaign with 35 batches per pair and one
attempt per pair; O1/O4, timeouts and all acceptance thresholds are unchanged.

The measured source was revalidated and frozen before dispatch: 54 files,
source closure
`d64c4ce399f5a79153d8daea289ca087b4f07aed0622ac02788f0cbe666ca475`, profile
`9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`, and no
source edits were made after the formal07 review. The fresh one-minute choice
window sampled 13 points over 60.281 seconds: CPU maximum 32.2271%, mean
20.4490%, minimum available RAM 8.7695 GiB, maximum commit 66.6763%, and zero
foreign engines. The campaign performs its own O4.1 preflight and watchdog for
each pair.

While formal08 is live, do not run another Godot/Blender engine or heavy test,
change the measured source, or compress its growing raw directory. On terminal
state, verify actual exits, Job/tree/handle cleanup, dataset and source/profile
hashes. If both fresh pairs pass, prepare the O4.3 CRITIC_PACKAGE for the owner;
do not self-call critics or sign acceptance. If it fails, preserve raw and
classify strictly under O1/O4. GT-07 remains unopened.

