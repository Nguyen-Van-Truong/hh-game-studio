# S241 terminal preservation (S242 packet)

Campaign `gt06-s241-formal-01` was a fresh formal attempt after the post-power recovery preflight. It terminated at batch 16 during `joint_observation` with `CAMPAIGN_STATUS_GAP`; `joint-00` through `joint-16` were captured (`completed_batches=17`). This is a partial diagnostic only and is not an accepted GT06 run.

The measured failure is in the host command-lane status-gap screen: command 16 reached 1000 completed HTTP commands, but its maximum adjacent host response gap was 2055.5275 ms (the 2000 ms gate), with additional gaps 2017.529 ms and 1891.190 ms. The native batch and command report were complete before the parent aborted; this does not prove editor or host process exit. The raw status-gap rows are retained without merging them into the formal dataset.

Raw run and supervisor directories remain immutable under `studio/.local/reviews/gt06-s241-formal-01*`. Source closure is `d7c78724ed827c8182af62c3f7bc1489d8dd35d29abe1f70216736a896e66bb3`; profile is `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. The parent wrapper exit was 1 and the import target exited 0. The editor target, host, and supervisor actual exits were not recorded; `owned_tree_zero=true`, `owner_closed=true`, Jobs were closed and handles released. Scheduler deletion is not used as exit proof.

Packet hashes:

- raw manifest SHA256: `cc739e6ea4655c88b5f4b58ee9bd6235bb50144b6dc057ea2efcc7995b2ff5cc`
- archive: `studio/.local/archives/gt06-s241-formal-01-s242-status-gap.zip`
- archive SHA256: `794f68ed014d9fc3980a6632dbf218f64eb085e26646d54e58e605d2d8365b1c`
- packet authority: `0`; formal acceptance: `false`

`verify.py` checks the raw manifest, archive member set, and every member hash. No source or gate change is implied. The next action is a bounded source/harness boundary review; do not reuse this campaign ID, merge partial batches, or retry unchanged.
