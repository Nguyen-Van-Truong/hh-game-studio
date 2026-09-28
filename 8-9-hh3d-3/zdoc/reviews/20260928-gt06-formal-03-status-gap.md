# GT-06 formal campaign 03 — status-gap failure — 2026-09-28

`AUTHORITY=0`; `FORMAL_ACCEPTANCE=false`; no critic package was created.

Campaign `gt06-o4-formal-03` used source closure
`9d373d2ef4b18aab43473f3e4de0e92efa88b97a038f976b44e17526b0037954` and the
unchanged profile
`9dfa0ae003577e8607e28e722089328933d60e6cdb5b1ae1c5e978b3ad9d335e`.
The first pair completed batches 0–17 (18 captures) and stopped at batch 17,
phase `joint_observation`, with `CAMPAIGN_STATUS_GAP`. The native barrier
reported `max_status_gap_ms=6432.487`, over the unchanged O1 limit of 2000 ms.
The command lane also reached 2059.8072 ms; this is a real product-gate
failure in the captured run, not a pass or an infrastructure abort.

The batch-17 raw evidence shows a long editor heartbeat gap between
`HOST_START` events and slow `save` operations. The retained HTTP phase window
shows command dispatch/header spans above 1.6 seconds and journal guard/append
spans above 1.1 seconds. These observations identify where to investigate, but
do not authorize changing the gate or claiming causation. Host CPU samples also
include high intervals; O4 watchdog attribution is not retroactively applied.

The child wrote `child-failure.json` and `child-terminal-cleanup.json`. The
parent wrote `parent-failure.json` with `classification=PRODUCT_FAIL`,
`owned_tree_zero=true`, and `cleanup_error=null`. Both Job owners closed with
zero active handles. `host-owner/process-exit.json` records child exit 1;
the editor target's natural exit was not recorded, so no target exit is
inferred. Scheduler status ended with result 1 and no instance. Raw files stay
under `studio/.local/reviews/gt06-o4-formal-03/`; nothing was overwritten.

This campaign is terminal and must not be resumed or rebound. GT-06 remains
the current WP with zero accepted full pairs. Before any fresh formal pair,
repair and verify the status-gap path or capture a controlled diagnosis using a
new ID, after a new O4.1 preflight and within the daily INFRA_ABORT budget.
Do not change O1 thresholds/timeouts, open GT-07, or sign critics from this
failure.

Evidence paths:

- `studio/.local/reviews/gt06-o4-formal-03/run-00-attempt-01/child-failure.json`
- `studio/.local/reviews/gt06-o4-formal-03/run-00-attempt-01/parent-failure.json`
- `studio/.local/reviews/gt06-o4-formal-03/run-00-attempt-01/joint-17.json`
- `studio/.local/reviews/gt06-o4-formal-03/run-00-attempt-01/sample-preview-17.json`
- `studio/.local/reviews/gt06-o4-formal-03/run-00-attempt-01/http-phases-final.json`
