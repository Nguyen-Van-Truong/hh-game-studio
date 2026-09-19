# S102 terminal lifecycle and Stop review

AUTHORITY=0. Implementation review only; not a final critic verdict or acceptance.
Reviewer lane: independent `s103_cleanup_review`. Observed 2026-09-19 UTC.
Campaign: `gt06-s102-campaign-01`, launch 1, run `gt06-s102-campaign-01.r00.a01`.
Declared source checkpoint: `56bfd448e83aa2512c0c2561e8e1a29f12134360`.
Declared 53-file closure: `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`.
Profile: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

## Conclusion

The campaign failed at the batch 6 joint-observation screen. Seven batches
were captured, including the failing sample; this is zero completed 35-batch
runs and cannot contribute a successful run to the ten-pair dataset.
`child-failure.json` preserves `CAMPAIGN_STATUS_GAP`, and sample 6 records
2109.351 ms against the unchanged 2000 ms limit. Parent
`BENCHMARK_WRAPPER_EXIT` is the consequence of the child failure, not a new
attributed cause.

The packet supports checked failed-run cleanup for the owned host/editor
Jobs and recorded resources. It does not support a complete successful or
natural-exit cleanup claim. The editor's actual target exit and supervisor's
actual process exit are missing. No acceptance, no no-leak conclusion, and
no inference of a successful run follows from scheduler completion.

## Actual exits and resource evidence

Raw root is `studio/.local/reviews/gt06-s102-campaign-01/`;
attempt-relative paths below refer to `run-00-attempt-01/`.
The supervisor root is the sibling `gt06-s102-campaign-01-supervisor/`.

| Role | Direct record | Supported conclusion / remaining gap |
| --- | --- | --- |
| Import target | `import-host/process-exit.json`: PID 10368, code 0 | Actual target exit recorded. Import observer binds start `windows:134342536660867488`. |
| Import helper and Job | `import-host/capture.json`: wrapper code 0; active-at-wrapper-exit 0; active-before-cleanup 0; natural-tree-exit true; Job zero/closed, no retained Job handle or taint | Import completed in 5.391 s. Its stage receipt supports natural tree exit. Observer's own `natural_target_exit_status=UNKNOWN` does not override that independent stage receipt. |
| Import observer | `import-observation.json` and child terminal record | 55 samples; closed, no live thread, no retained/uncertain target-probe handle, global held-probe count 0, no observer errors. |
| Host target | `host-owner/process-exit.json`: PID 32404, code 1; matching process-start; traceback reports `CAMPAIGN_STATUS_GAP` | Actual failed target exit recorded by helper after `p.wait()`. The child terminal record's null self-exit is expected because it precedes process exit. No successful natural-tree capture was produced. |
| Host helper / outer Job | `host-owner/cleanup-001.json`: wrapper code 1; Job zero/closed; no taint or uncertain/retained Job handle; wrapper process handle checked closed | Checked cleanup completed. `parent-failure.json` corroborates owner-closed/tree-zero and no cleanup error. Parent helper PID is not recorded in this cleanup JSON. |
| Editor target | `editor-host/process-start.json`: PID 14312; joint observations bind start `windows:134342536722446194`; no `process-exit.json` | Actual editor exit code is UNKNOWN. No natural exit may be inferred. Native stdout ends while waiting at batch 7 `HOST_START`. |
| Editor helper / inner Job | `editor-host/cleanup-001.json` plus terminal observation: helper PID 29916/code 2; `BENCHMARK_CLOSED_BEFORE_FINISH`; Job zero/closed; wrapper handle checked closed; two drain threads false | Failure cleanup took the owner-close path. Code 2 is consistent with the source's `TerminateJobObject(..., 2)` path. It is the helper's code, not an observed editor-target code. The record does not preserve a separate termination-event flag. |
| Producer / probes | `child-terminal-cleanup.json`, observed 01:19:26Z | Producer closed/failed; main/control sockets closed; all three host threads false; journal cache closed with no retained index/database/directory; editor/producer probe handles released without uncertainty; heartbeat false; errors empty. |
| Supervisor | `start.json`: PID 37044/start `windows:134342536631741011`; `return.json`: returned code 1, 705.906 s | Return record explicitly says actual process exit has not been observed. Scheduler result and later absence cannot replace a retained-handle exit receipt. |

Import stage capture does not contain a checked import-helper
`wrapper_process_handle` snapshot. `native_job.run_stage` waits for that
helper and closes streams; its local Python process-object lifetime is not
separately evidenced with the explicit native-handle close receipt used by
`BenchmarkProcess`. This is an evidence detail still unrecorded, not proof
that a handle remains live. The import observer only proves its own target
probe was released.

The terminal record's context/start/import-exit references were independently
checked against file size and SHA-256. All four references matched. The four
import capture artifact hashes (start, exit, stdout, stderr) also matched.
The coordinator owns the comprehensive source/raw preservation check; this
lane did not duplicate the full closure hash scan. A scoped tracked-source
diff was empty during inspection.

## Live identity check and Stop

Read-only scheduler COM and exact-PID CIM queries at
`2026-09-19T01:22:25.5250695Z` found task
`\\HHStudio.GT06.gt06-s102-campaign-01` in state 3, last result 1, with no
instances. PIDs 37044, 14312, 29916, and 10368 were absent.

**PID 32404 had already been reused by unrelated Chrome**, executable
`C:\Program Files\Google\Chrome\Application\chrome.exe`, created
`2026-09-19T01:21:58.0958810Z`. The owned Python host was created at
`2026-09-19T01:07:45.0056822Z`. This is not a remaining owned host. Do not
signal or terminate this numeric PID. Absence/reuse is liveness evidence,
not an actual-exit receipt.

All 30 bounded campaign Stop slots (`run-00` through `run-09`, attempts
01 through 03) were checked at `2026-09-19T01:21:43.6560433Z`; none contained
`stop-request.json`. This failure was not an observed campaign operator
Stop. Source `run_benchmark_campaign.py` validates active Stop payloads and
uses `lexists` for the cross-attempt latch; it checks the latch around wait,
completion, assembly, and publication. Existing slots must remain immutable.

Per-batch cancel records for batches 0–6 are a different scope: each records
`CANCELED`, `CANCELED_BEFORE_APPLY`, and `no_effect=true`; receipt times are
29.53, 32.3034, 43.8038, 58.8121, 42.7626, 92.2462, and 52.752 ms. These
preserve the completed prefix's cancel observations; they do not establish
the full campaign Stop gate or ten-run benchmark acceptance.

## Continuation constraints

1. Preserve this failure, original sidecars, and all attempts byte-for-byte.
   Do not retry over launch 1, relabel its source, or splice its partial
   batches into a later successful run.
2. Analyze the original HTTP/native timing evidence before claiming a cause
   or fix for the 2.109351 s gap. Clean Jobs and an empty stderr do not explain
   that gap; the host stderr correctly records the failure traceback.
3. Keep the workload, 2 s limit, source/profile/workstation discipline, and
   acceptance requirements unchanged. A changed runtime requires a fresh
   source binding and affected verification before a new bounded run.
4. Treat editor actual-exit and supervisor actual-exit as missing unless an
   already-retained independent observation exists. A postmortem PID query
   cannot manufacture those receipts. A future lifecycle observation should
   bind process start/executable while the owned handle is alive.
5. Any further cleanup or scheduler change belongs to the coordinator's
   owned-identity workflow. This lane did not start engines/tests, terminate
   processes, delete data, mutate tasks, or edit runtime/plan files.
6. GT-06 remains IN_PROGRESS. This implementation review provides no final
   critic signature and cannot open GT-07 or substitute for two new critics
   on a complete final evidence closure.
