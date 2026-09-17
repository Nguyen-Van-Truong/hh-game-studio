# S75 campaign failure preserved for S76

This package seals failed campaign `gt06-s75-campaign-01`, launch 1,
run `gt06-s75-campaign-01.r00.a01`. It is preservation and static consistency
evidence only: no benchmark PASS, independent critic verdict, or GT-06 acceptance.
The preservation worker did not launch an engine/test, control a process/task,
edit runtime source or plan, modify raw inputs, or commit.

Collection ran at 2026-09-17 23:19:44–23:20:06 UTC (2026-09-18
06:19:44–06:20:06 Asia/Saigon). HEAD was
`95a0cb97aace5853790c6ffe92ad85dc781645f5`.
Runtime checkpoint: `979f98ef27dbca1613c2382a917b4dd4f73fecb6`.
Source closure: `638304f54851366ac2a79a792a8009406fc927c3c6c410ad8f65cc2dd9b14995`.
Profile: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

## Failure and completeness

The exact child failure is `CAMPAIGN_RETAINED_COUNTER_GROWTH`, zero-based
batch 8, `joint_observation`, `completed_batches=9`, `partial_command=null`.
There are five warmup and four measured sample artifacts. Measured batches
5–7 pass the frozen prefix screen; batch 8 fails. Captures are written
before screening. These are neither four accepted measured samples nor a
completed 35-batch run or ten-run campaign. No attempt is combined with another.

| Measurement | Warmup baseline, batch 4 | Failed batch 8 |
|---|---:|---:|
| Host RSS bytes | 27,201,536 | 11,411,456 |
| Editor RSS bytes | 185,987,072 | 96,612,352 |
| Host handles | 194 | 194 |
| Editor handles | 577 | 579 |
| Editor objects | 71,130 | 71,130 |
| Editor resources | 6 | 6 |
| Maximum command-lane status gap, ms | 675.134 | 2,016.2214 |

The frozen assembler builds editor counters in RSS, handles, objects,
resources order. The runner screens that in-memory order, so editor handles
+2 is the first failing comparison. The same sample also exceeds the unchanged
2,000 ms status-gap threshold by 16.2214 ms. That check follows counters,
so it did not emit a separate exception. No other retained counter or RSS
comparison breaches its limit, and no earlier sample breaches the applicable
prefix screen. `completeness-and-screen.json` retains all nine counter rows.
The gap measures host command-lane response progress, not editor UI heartbeat.
These observations identify failures, not their cause or whether handles leak.

Every captured batch references 1,000 commands and 100 native cycles, with
500 inspect, 300 rejected, and 200 admitted latency observations. The recheck
also verifies 200 single effects, zero dropped commands/telemetry, and per-batch
descriptive inspect p95 values. This is incomplete-run evidence; it does not
replace final run/dataset latency gates.

Native ready-09 exists; start-09, ACK-09, batches 09–34, final native index,
child result, owner success captures, run assembly/capture, campaign capture,
dataset, and summary are absent. Complete runs: zero.

## Actual exits, cleanup, and Stop

- Host target PID 16220 has matching start and actual exit-1 receipts and
  matches the fixed host identity in every sample. Host wrapper exit is also 1.
- Editor target PID 13024 has its start and fixed sample identity, but no
  native exit receipt. Cleanup records wrapper exit 2 and
  `BENCHMARK_CLOSED_BEFORE_FINISH`. Wrapper 2 is not a proven Godot target exit.
- Host and editor owner receipts both show Job active count 0, zero observed,
  configured/assigned/closed ownership, no retained handle, taint, failed
  operation, native error, or create/close uncertainty. Both wrapper-process
  handles are closed without retention or uncertainty. Parent failure confirms
  owner closed, owned tree zero, and no cleanup error. These are terminal
  receipts, not new inspection of already closed Job handles.
- Import target PID 35452 has a native exit-0 receipt and matching import
  capture, wrapper 0, natural tree exit, and Job zero/closed. Its capture has
  no separate wrapper-process-handle object; no such field is inferred.
- Supervisor returned 1 after 1,709.938 seconds and explicitly marks its
  own actual process exit as not yet observed. Fresh read-only scheduler
  status shows state 3, result 1, and no instances. Scheduler and supervisor
  records do not substitute for native target exits.
- The collection snapshot found no Godot/Blender processes and none of the
  three recorded target PIDs among observed Python/Godot/Blender processes.
  This does not reconstruct a missing historical native exit code.
- All 30 fixed attempt slots were checked using `os.path.lexists`; all Stop
  latches and run captures are absent. Only `run-00-attempt-01` exists.
  No latch was created, cleared, or bypassed. In-sample benchmark cancellation
  exercises are distinct from the operator Stop latch.

No cleanup blocker is visible in the terminal ownership receipts. Acceptance
still lacks a native editor exit, complete workload, and passing measurements.
Cleanup does not establish a repaired failure or authorize a blind retry.

## Bytes, source, and reproduction

`raw/` contains **162 exact copies, 13,360,701 bytes**: campaign/attempt bindings,
all 49 frozen runtime source files, all 54 references from nine batch captures,
all nine joint/capture/sample sets, owner receipts/logs, final native boundary,
and every supervisor top-level file. `.gitattributes` preserves these bytes.

`raw-locator-hashmaps.json` inventories **264 files, 33,045,901 bytes**:

- Campaign: 252 files, 33,037,632 bytes.
- Supervisor: 12 files, 8,269 bytes.

The roots remain `studio/.local/reviews/gt06-s75-campaign-01` and sibling
`gt06-s75-campaign-01-supervisor`. Unselected journals, remaining attempt source
duplicates, and caches remain at raw locators; an inventory is not a copy.
Raw inputs were fully rehashed before collection completed. The manifest binds
every exact copy to its locator, byte count, and SHA-256. No broad cache is copied.

All 49 source entries match campaign and attempt frozen bytes, the context
and source-file maps, live files at collection, and exact Git blobs from both
checkpoint `979f98ef` and HEAD `95a0cb97`. Campaign/context and both profile
bindings match; source closure was independently recomputed. Later source
changes cannot inherit this failed attempt's evidence. `final-source-status.json`
records source status at sealing separately from collection.

`collect_failure.py` is the exclusive-write collection recipe. It reads raw
inputs and performs only read-only Git, scheduler-status, and process observations.
Their commands, timestamps, stdout/stderr hashes, and actual observer exits are
preserved under `observations/`. Collection was executed with `python -B` and
returned 0. Observer exits are not native target exits.

`verify.py` performs a separate static recheck of raw inventory, exact copies,
source bindings, import artifacts, actual/wrapper receipt boundaries, all 54
references, process identities and sample evidence hashes, workload dimensions,
Stop slots, and absences. It is not an independent critic. First invocation
creates the recheck report and seal. Repeat verification from the repository root:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260918-gt06-s76-handles/failure/verify.py --check
```

`package-manifest.json` seals all package files except itself and its detached
SHA-256 file. `--check` rehashes raw inputs and all sealed bytes without writing.
The raw locators must remain accessible for the complete check.
