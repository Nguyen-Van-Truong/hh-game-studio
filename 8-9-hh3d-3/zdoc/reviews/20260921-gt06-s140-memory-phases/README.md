# S140 — phase-resolved host memory diagnostic

Authority: 0. Diagnostic only; no F13/F14 samples, no GT06 acceptance.

The unresolved S131 gate is host RSS growth from 40,861,696 to 45,395,968 B
at batch 5. S132's host-only result does not cover the native/ACK/assembly
interval. This diagnostic reads private commit, working set, page faults and
current-process allocated blocks at ten bounded phase boundaries. It does not
change runtime sources, native workload, profile, baseline, timers or gates.
`native_validated_before_editor` includes parsing, validation and the stock host
observation; it is not a timing attribution to JSON parsing alone. The telemetry
has its own cost, is bounded to 200 rows and is never subtracted from a gate.

## Attempts and corrections

| Run suffix | Evidence | Disposition |
|---|---|---|
| p01 | AttributeError at wrapper installation; zero rows; no engine startup | Helper composition failure, retained |
| p02 | 1 original batch, 1,000 HTTP + 100 native, all ten phase rows | BOUNDARY_CAPTURED after the original gate and post-assembly GC |
| p03 | Import started/completed; log last seen at batch 0 commands; no terminal/phase/exit receipts, no remaining run processes at follow-up | INCOMPLETE/UNKNOWN; interruption coincided with turn cancellation, causal exit code unavailable |
| p04 | Seven batches, 70 rows, original gates returned; ended 06:52:12Z with recorded owner cleanup | BOUNDARY_CAPTURED; retained launcher exit 0; editor natural exit UNKNOWN; task retired |

P01's outer GateObserver replaced `CampaignProducer` with a factory function
before the phase hook accessed the class method. The replacement runner directly
wraps stock class methods and keeps the stock screen gate. Composition tests now
import the actual campaign class without launching Godot.

Additional prelaunch fixes: use an independent ctypes function signature for
PROCESS_MEMORY_COUNTERS_EX (the stock probe expects its own smaller structure);
never label the current Python allocated-block count as an editor count; reject
identity mismatch/rebinding; record the original post-assembly GC before the
bounded stop. Nine unittest cases, including a retained self-process native
counter check, passed before p02. Stock source pin check passed.

P02 host/helper actual exits are 1 for deliberate bounded termination. Import
target exit is 0. Editor target natural exit is UNKNOWN, while its owner/helper
exit 2 and Job zero/closed, released probes/handles, stopped threads and sockets
are recorded in `child-terminal-cleanup.json`. Do not describe UNKNOWN as an
observed editor exit. The unsupervised p02 top launcher has only the shell's exit
observation, not the later p04 passive handle receipt.

P02 private commit rose from 34,824,192 B at command completion to 39,129,088 B
at screen and fell to 36,470,784 B after assembly GC. Working set and allocated
blocks are separate fields. One warm-up batch cannot prove retention, a leak,
or the cause of S131. P04 obtains the still-missing batch 4→5 comparison.

## Run and ownership

Helper: `run_s140_memory_diagnostic.py`; prepare is inert and IDs are exclusive.
`--run-existing` consumes `dispatch-once.json` before any process launch. Child
and parent use the current `BenchmarkProcess` Job implementation. Parent limit
is 300s for prefix 1 or 1230s for prefix 7; original engine/profile limits are
unchanged. Bounded child exit is deliberately nonzero and never passed to the
formal success capture verifier as a success.

P04 task: `HHStudio.GT06.gt06-s129-s140-memory-p04-supervisor`.
The unchanged S129 observer retains the launcher's actual process handle and
records native wait/exit/CloseHandle. Its bound is 1290s; the demand-only task
has 1380s, no restart and no repeat trigger. Scheduler return alone is not PASS.
Request: `../20260920-gt06-s129-supervision/request-gt06-s129-s140-memory-p04-supervisor.json`.
Observer output: `../20260920-gt06-s129-supervision/runs/gt06-s129-s140-memory-p04-supervisor/`.
Raw: `../../../studio/.local/reviews/gt06-s140-memory-phase-p04/`.

Query `prepare_task.ps1 -Command status -RunId gt06-s129-s140-memory-p04-supervisor`
and short tail; check current PID/start/executable. Leave helper/source/profile
and workstation unchanged during measurement. Do not run another engine/test
or heavy audit beside it. On terminal inspect phase/summary/result, child cleanup,
actual exits, Job/handle state, Stop and source pins, observer terminal and task
terminal before sealing. Missing receipts stay UNKNOWN. Retire only this task
after preserving terminal metadata and verifying there is no active instance.

## Work retained and next action

S138 managed repair and replay already completed. S139 bound the 53 benchmark
and 217 installed source projections (union 231) and GT05 inputs. Those are
distinct scopes; neither can supply the missing 10 fresh pairs × 35 batch
performance dataset. Reuse functional evidence only by exact dependencies.

S140 requested three Astra xhigh worker audits; all three failed model capacity.
The earlier completed S140 readiness audit identified duplicate artifact decode
as a hypothesis. Coordinator implemented and tested this diagnostic; no worker
or coordinator implementation review substitutes for the two final critics.

P04 analysis and lifecycle decision are in `coordinator-terminal.md` and
`analysis-p04.json`; the selected 174-file packet has zero hash mismatches.
No batch 4→5 retention discontinuity justified a runtime repair. S141 proceeds
to fresh stock evidence with all original gates, retaining S131 as unresolved.
Preserve failures and
all partial attempts; do not resume a dead process, reuse its ID, or join partial
samples. Frozen full GT06 DoD and two fresh same-hash critics remain required.
