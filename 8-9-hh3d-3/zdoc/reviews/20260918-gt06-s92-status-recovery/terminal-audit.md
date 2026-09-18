# S91 terminal and closure audit

AUTHORITY=0. Read-only evidence audit; no benchmark, runtime acceptance, engine run, test, retry or Stop mutation. Only this report was written.

Run: gt06-s91-sparse-attribution-01. Raw root: studio/.local/reviews/gt06-s91-sparse-attribution-01. Observer: zdoc/reviews/20260918-gt06-s91-sparse-attribution/launch-02/observer.

## Closure binding

- All 51 declared runtime files match their SHA256 values in both current studio source and preserved source/studio. The manifest's canonical path+NUL+digest+newline closure independently recomputes to e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f.
- All six diagnostic helpers match diagnostic.json in current source and preserved source/zdoc. The observer's four launcher/helper bindings agree with that set. No source/helper drift found.
- benchmark-profile.json hashes to 0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85, matching context, diagnostic, native input, joint-16 and child terminal records. Child terminal's context hash and size match actual context.json.
- The native overlay is separately declared: base 52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2, effective a8a287c2b9c4d8c6a3a6030684db74aaaa7ee7f84e4e3fb0e0c6974f207b2efd. It is diagnostic instrumentation, not unchanged runtime/performance evidence.
- All 12 observer artifact hashes plus request.json and task.xml match observer/manifest.json. This audit did not independently repeat the root sealer's larger raw/copy audit.

## Terminal and cleanup

CAMPAIGN_STATUS_GAP stopped the child at batch index 16 / 17 recorded partial batches, phase joint_observation, 2026-09-18T14:25:58Z. completed=false; formal_acceptance=false; eligible_for_dataset=false.

| Process | PID | Retained-handle exit | Observation UTC |
| --- | ---: | ---: | --- |
| Editor | 22440 | 2 | 14:25:58Z |
| Editor helper | 45548 | 2 | 14:25:58Z |
| Host | 54540 | 1 | 14:25:59Z |
| Host helper | 17164 | 1 | 14:25:59Z |
| Supervisor | 51464 | 1 | 14:26:01Z |

These five exits are recorded through retained_handle_GetExitCodeProcess with signaled waits. Editor/helper exit 2 follows BENCHMARK_CLOSED_BEFORE_FINISH cleanup and is forced termination, not natural completion. The import stage is separate: PID 50660 exit 0, wrapper 0, natural_tree_exit=true.

Host-owner inner Job, editor-owner inner Job and observer outer Job all record active_count=0, zero_observed=true, closed=true, handle_retained=false, no failed operations, no close uncertainty or taint. Wrapper process handles and all five observer-retained handles are closed. The outer Job was already zero before observer cleanup; errors and unobserved_processes are empty. Child producer sockets/threads/journal/probes and heartbeat also report closed/stopped. No Godot/Blender process was present in the audit's read-only process snapshot.

Individual exit files show handle_closed=false at exit capture; terminal.json later records true after release. That is a staged observation, not a contradiction. Missing child-result.json and inner editor-host/process-exit.json remain truthfully listed. The external editor exit record supplies the actual forced exit without rewriting that missing inner record or claiming a natural exit.

## Scheduler and Stop

Scheduler readback at 2026-09-18T14:33:50.281Z: state=Ready (Ready/3), LastTaskResult=1, LastRunTime=2026-09-18T13:52:58Z, no next scheduled run, missed runs=0. Task-start binds scheduler engine PID 8536 to observer claim/request and the dispatched instance. Observer terminal reports its intended return 1 but explicitly cannot observe its own exit. Scheduler result 1 supplies scheduler-level completion evidence; it is not a retained native process-handle exit for observer PID 8536 and never proves diagnostic success.

No S91 stop-request.json is present; the recorded cause is CAMPAIGN_STATUS_GAP, not operator Stop. No Stop latch was removed or changed. Historical Stop files outside this S91 run were not used to infer its outcome.

## Disposition

Terminal/closure records inspected are mutually consistent with a failed diagnostic and cleaned owned process tree. They do not establish a complete 35-batch run or GT-06 acceptance. Preserve failed partial evidence and the distinct inner/outer exit provenance; no rerun is justified by a missing inner exit alone.