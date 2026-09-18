# S95 native isolation diagnostic

AUTHORITY=0. Diagnostic implementation with coordinator smoke evidence below. This folder does not
change studio runtime, the benchmark profile, the S93 helper, old raw evidence,
formal gates, or plan status. No engine or test was run by its implementation
author. Coordinator must review/check this new source before use.

The purpose is to ask whether the native editor create/undo/save/reload cycle
subset produces same-phase ObjectDB growth without the HTTP command lane.
Native-only completion is not a formal benchmark PASS. A negative observation
means **not reproduced in this isolated workload**, never "no leak".

## Fixed modes

| Mode | Native workload | Per-stage wall bound | Meaning |
|---|---|---:|---|
| preflight | Import only; overlays 35x100 but does not activate it | 180 s | Compile/import and immutable project check |
| smoke | 5 batches x 1 cycle | 180 s | Exercises startup, cycle/readback and sparse batch-4 baseline |
| isolation | 35 batches x 100 cycles | 1800 s | Native workload attribution, no HTTP producer |

The parent owns its Python child through `BenchmarkProcess`; the child owns
each sequential import/editor stage through the same bounded runner. Parent
wall bound is the mode's stage limit plus 240 seconds. Engine Job quotas and
the existing native phase limits remain unchanged. The copied driver is in
`diagnostic` mode, with no host start permit or ACK. It reports
`host_integrated=false`, `benchmark_complete=false`, `formal_acceptance=false`.
The outer records also state `full_benchmark=false` and
`eligible_for_dataset=false`. No campaign dataset is generated.

`prepare()` and `benchmark_project_config()` come from the current
`studio/tests/replay/run_native_benchmark.py`. They preserve the fixture,
Godot 4.7.2 pin, editor plugins, GL compatibility renderer, worker pool,
6900 us focused/unfocused sleep, update-continuously false, Output limit 100
and `benchmark/.gdignore`. The GUI editor performs the workload; only its
preceding import is headless.

The overlay changes only the disposable driver's diagnostic dimensions and
adds one call before its original batch counter publication. The copied S93
sparse helper is versioned as S95 and explicitly permits diagnostic mode. It
retains primitive IDs only, uses a 32768 target-ID cap and at most two snapshots
(batch-4 baseline and first later same-phase object growth), and fails on
incomplete target inventory or counter self-drift. The patch is reversible to
the exact frozen original bytes. No original helper/runtime file is written.

## Coordinator commands

Use the selected Python runtime from the repository root. The examples below
are commands to run later, not evidence that they have been executed. First
read the new source and perform the coordinator's static/unit checks. Freeze
only after the independently developed HTTP changes and this helper are final.

```powershell
$isolationHelper = '8-9-hh3d-3/zdoc/reviews/20260918-gt06-s95-native-isolation/native_isolation.py'
python -B $isolationHelper --describe
```

`--describe` launches no engine and writes nothing. It returns the current
`pins.source_closure_sha256` and `pins.helper_closure_sha256`, including the
explicit fixture pins/schema/driver and imported local launch/verifier modules.
This narrower native source closure is distinct from the coupled campaign
closure; do not substitute one for the other. Copy both digests into the two
variables below and record them in coordinator evidence:

```powershell
$nativeSourcePin = '<pins.source_closure_sha256>'
$nativeHelperPin = '<pins.helper_closure_sha256>'
python -B $isolationHelper --mode preflight --run-id gt06-s95-native-preflight-01 --source-sha256 $nativeSourcePin --helper-sha256 $nativeHelperPin
python -B $isolationHelper --mode smoke --run-id gt06-s95-native-smoke-01 --source-sha256 $nativeSourcePin --helper-sha256 $nativeHelperPin
python -B $isolationHelper --mode isolation --run-id gt06-s95-native-isolation-01 --source-sha256 $nativeSourcePin --helper-sha256 $nativeHelperPin
```

Run those modes sequentially under the coordinator's managed launcher with
captured actual outer Python exit. Do not run them beside the HTTP probe or
another engine. Each command exclusively creates a fresh
`studio/.local/reviews/<run-id>/`; repeated IDs are rejected. Do not reuse an
ID after source changes or a failed attempt. The wrapper itself owns/captures
its Python child and engine target exits; its final result explicitly says
`supervisor_own_actual_exit_not_yet_observed=true`, since only the external
launcher can prove that final exit.

For an authorized Stop, exclusively publish `stop-request.json` in that run's
output directory using temp-plus-no-overwrite rename. Its exact content is:

```json
{"schema":"HH-GT06-S95-NATIVE-STOP-1","run_id":"<exact-run-id>","source_closure_sha256":"<source-pin>","helper_closure_sha256":"<helper-pin>","reason":"OPERATOR_STOP"}
```

Both parent and child poll this fixed slot; stale/malformed requests fail
closed. Stop invokes the existing owned-runner cleanup and cannot become a
successful diagnostic. Do not remove the latch to resume a run.

## Evidence and interpretation

The output binds original source copies, helper copies, effective overlaid
driver, toolchain through the source map, invocation, project snapshot,
diagnostic dimensions and exact batch artifacts. Its dimensions-consistent
verifier checks all native cycles, root/generation/readback chains, startup
readiness, final saved scene, source drift, sparse baseline/first-growth
capture and self-drift. It checks actual engine/helper exits and owned cleanup,
and requires a visible matching editor process observation. Missing/failed
capture or cleanup cannot produce `completed_diagnostic=true`.

`child-result.json` reports native elapsed seconds, per-batch cycle durations,
counts, sparse identity deltas, native heartbeat values and its unchanged
2000 ms target result. Diagnostic completion means the bounded measurement
completed and its evidence passed structural verification; it does not mean
every performance criterion passed. Heartbeat failures remain visible. Object
growth is retained as an observation instead of being called a successful
formal memory test. `supervisor-result.json` and `output-manifest.json` retain
failed/unknown results and never invent missing process-exit receipts.

The native `warmup` field stays false in diagnostic mode. Only the diagnostic
analysis defines batch 4 as its same-phase baseline; it does not pretend these
are measured samples of the official 5+30 profile. Formal profile hashes in
the existing native binding identify the reused base contract, while the
separate diagnostic metadata explicitly declares this different workload.

The isolated workload omits HTTP producer load, host-start waits, ACK execution
and their elapsed time. Formal memory observations are post-ACK; these are
prepublication native observations and must be compared with their own
same-phase baseline. S93 batch 6, for example, had 71127 prepublication versus
71128 post-ACK objects. Do not compare those absolute counts as a leak.

Historical S82's 16x100 native-only diagnostic did not reproduce +2 and lasted
about 507 s including 120 s idle; its coupled failure was roughly 31 minutes.
Running 35x100 faster still may miss age-, idle-, ACK- or load-dependent growth.
Report actual walltime alongside that limitation. The sparse inventory covers
reachable Tree-owned TreeItems and Node3D-family instances, not full ObjectDB
or every owned TextParagraph. A match is an attribution lead; a negative is
not a root-cause elimination or acceptance verdict. S91/S93 failures remain
unchanged, and the full formal campaign must eventually pass its original gates.

## Coordinator verification, S95

Current native source40 closureebed9418490379bb902d2049e4a2f98a96e3378d09b369aef02684e16214c74e;
helper closure4448ab35a6e087c8756063e0d8a025f4dc60a44329fcf56c4b270e6d1474302b
is recorded in pins-03.json. It is distinct from the formal coupled51 map.
Eight focused tests unit-02 pass, actual50084/helper25420exit0/treeverified.
The final census hook runs after semantic inspect/root/barrier and immediately
before the original counters, refreshes ended from the actual clock, and emits
a real second heartbeat after capture. No fake progress or threshold change.

Smoke01 completed but preflight found a receipt publication race and timestamp
ordering gap. Smoke02 moved the census before semantic inspect and then exposed
a different-phase count:71062 versus71063, so its collector failed after native
exit0. Both exact packets remain preserved. Moving the hook back to the same
counter lifecycle, with timestamp/heartbeat coverage corrected, led to smoke03:
5x1 cycles completed, import33312/editor18096exit0; external supervisor1444/
helper31040exit0/treeverified. Native time8.274s, maxgap505.823ms; baseline only.
The process-start reader waits at most5s after partial publication is first
seen, continues Stop polling and rejects completed invalid records immediately.

Detached long run uses outer_owner.py/register_task.ps1: explicit registration
then start, same-PID gated target and checked7-slot outer Job including stock
Godot transient processes. A further BenchmarkProcess wrapper would consume
extra slots and was rejected in preflight; inner engine profiles remain intact.
Request pins the reused S93 ownership helper; S95 watchdog2160s, scheduler40min.
Scheduler observes outer owner completion separately. Commands status/delete
apply only to the fixed S95 task, and start includes hidden HHStudio.GT06 tasks
when checking for conflicts. Do not dispatch twice or overwrite launch/output.
