# S76 launch1 import: independent bounded review

2026-09-18, Asia/Saigon. Static source/raw comparison only. No engine, tests, campaign validator, process control, limit change, runtime/plan edit or acceptance verdict. Only this report was written. Observed HEAD remained `dfbed1621a831abd9cc005f2b1ee01de9fec2702`; the tools plan had an existing coordinator modification.

**No concrete source, configuration or path mismatch explaining this timeout was found.** One explicitly bounded same-source/profile/workstation retry with a fresh owned pair is reasonable after cleanup verification, preserving this failed attempt. An identical throwaway20-second import adds little unless it tests a new discriminating hypothesis. If the next import repeats this failure, stop blind retries and collect phase/time/ownership evidence on a separately labeled diagnostic; do not enlarge the accepted shared limit to obtain a pass.

## Observed failure and comparison

Raw failure root: `studio/.local/reviews/gt06-s76-campaign-01/run-00-attempt-01/`.

`child-failure.json` records `StageFailed`, `phase=import`, `batch=-1`, `completed_batches=0`, `partial_command=null`. No warmup or measured batch exists. The import capture records `STAGE_WALL_LIMIT`, elapsed20.188s, effective wall20s, wrapper exit2, Job configured/assigned/closed/zero, active0 and no retained Job handle. `process-start.json` records native PID26944. There is no `process-exit.json` and no captured native exit in this failure. Cleanup zero does not become native exit0.

Stdout stops after Godot4.7.2's `Loading global class names...` at16% of project initialization. Stderr is empty. There is no emitted syntax warning/error, but the last buffered progress line alone does not prove which function was running throughout the remaining time or exclude an unreached parser error. The failed project cache currently contains only `.godot/.gdignore`; no generated editor settings file exists in this import's isolated appdata. These support an early initialization interruption, not a diagnosed cause.

The following values are parsed from the existing import captures, without executing their verifiers:

| Import | Elapsed seconds | Native exit | Source-map count | Project absolute path length |
| --- | ---: | --- | ---: | ---: |
| S76 campaign r00.a01 |20.188|missing; timeout cleanup|49|151|
| S76 retention01 |7.953|PID34140,0|39|134|
| S75 campaign r00.a01 |7.406|PID35452,0|49|151|
| S73 campaign r00.a01 |4.782|PID44056,0|49|151|
| S73 campaign r00.a02 |9.171|PID35564,0|49|151|

All listed successful imports report completion under20s. These are historical observations, not a controlled timing experiment or samples to pool into S76 acceptance. The earlier49-file campaigns at the same151-character project depth weaken “49 source files” or “longer campaign path” as sufficient explanations for this single failure.

## Source, project and environment comparison

The S76 failed campaign and successful retention import invocations bind the same Godot executable and binary SHA256 `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`. Both use `--headless --editor --path <fresh project> --import` and the same `studio.pipeline.native_job.run_trusted_stage` implementation/default limits.

All39 source entries shared by the two invocation maps have identical hashes. The campaign's ten extra entries are host journal/redaction/transport, replay journal-index/verified-journal, and benchmark assembly/commands/campaign/task launchers. These are host provenance dependencies, not ten extra Godot scene scripts copied into the project. The larger map cannot be treated as a larger Godot import workload without further evidence.

Both declared initial project manifests contain15 files and differ at exactly two entries:

- `addons/hh_benchmark/benchmark_native.gd`: retention uses the disclosed supplemental eight-batch/100-cycle/point-observer patch; campaign uses the frozen production driver.
- `benchmark/input.json`: correct differences in run ID, source closure, full versus diagnostic mode, and host barriers versus diagnostic immediate mode. The `benchmark/.gdignore` bytes are identical.

The original scene, `project.godot`, actor, production plugin/JCS/scene-command scripts and UID files are byte-identical. Project settings match: both editor sleep values6900µs, continuous updatesfalse, Output limit100, compatibility renderer, worker pool4 and both declared plugins. The retention scene's current on-disk bytes differ after its800 edit/save/reload cycles, but **its initial scene hash equals the failed campaign's initial hash**; post-run scene normalization is not a construction mismatch.

Import command lines contain no `--hh-benchmark-mode` user argument. `isolated_env()` strips `HH_` variables, and the benchmark `_enter_tree()` returns inactive when no activation is supplied (`benchmark_native.gd:118–134`). Thus the full/diagnostic input modes are not evidence that the import was executing3500 versus800 semantic cycles. The diagnostic GDScript body remains a parser/source difference, but this comparison supplies no evidence it caused the campaign's early failure.

Environment isolation is performed by the same code (`native_job.py:38–49`): it removes named Python/Blender/HH/Godot/Node/npm variable prefixes and uses fresh output-local APPDATA/LOCALAPPDATA/TEMP/TMP/Blender directories. Actual complete inherited environment values are not recorded in `invocation.json`. Therefore the two imports are not proven to have identical inherited PATH/OS state, scheduler ancestry, priority, filesystem contention, cache residency or memory pressure. No such difference is established as causal. Do not attribute this event to antivirus, RAM trimming, background throttling or a thread deadlock from these files alone.

The stage timer starts before wrapper creation, Job setup and a second source recheck (`native_job.py:176–195`); it is not an engine-only20-second timer. Initial source checking and binary hashing occur before that timer. The10 extra source files can add some in-budget recheck work, but the successful49-file historical imports and lack of phase timings do not support blaming that work for the timeout. Workspace polling also contributes host overhead; none of the raw records measures its contribution.

## Origin and authority of the20-second bound

The normative GT06/performance text does **not** specify a numeric20-second Godot import deadline. It requires declared bounded jobs, enforced timeout/owned cleanup, locked workload/device metrics, and the benchmark's7410s/run. The20-second import ceiling is an inherited shared implementation safety bound:

1. `studio/host/blender/export_job.py:20–25` declares2GiB memory,15s Job CPU,20s wall,32MiB workspace,262144-byte logs and4-process cap.
2. `studio/pipeline/native_job.py:20–23` imports those production limits. `run_trusted_stage(... timeout_seconds=WALL_SECONDS)` at107–123 defaults to20s and rejects any larger requested timeout.
3. `run_benchmark_campaign.py:582–586` calls that shared runner for import without an override, then verifies the captured stage. The retention and earlier campaign imports use the same path.
4. `studio/tests/replay/benchmark_job.py:1–5` explicitly distinguishes the separate long benchmark budget from the accepted20-second native stage and states that the latter's production limits are unchanged.

Consequently20s is not a GT06 UX latency metric, but it is still part of the frozen runner's enforced safety contract. Its inherited origin does not authorize weakening it, moving import to an unrestricted launcher, or relabeling this timed-out stage as success. The long-run7410s limit does not supersede this import bound.

## Immediate next step and limits

After independently checking the original host/import cleanup and scheduler terminal state, use the existing next fresh attempt mechanism under unchanged source/profile/machine and20-second import bound. Preserve launch1 raw/source/capture and its absent native-exit limitation. No partial measurements need recycling: none were collected. Do not reuse the killed project's generated cache as an undocumented “fresh” import, and do not claim the retention import as the missing campaign import.

If the second import succeeds, continue that exact campaign pair and keep the failure visible; this does not prove the initial delay's cause. If it repeats, record the repeated failure and stop additional blind attempts. The next diagnostic should distinguish startup scheduling/host overhead from Godot initialization work using owned-process observations and separately frozen provenance, while keeping production limits and benchmark thresholds unchanged. This review does not require another identical throwaway import before that one bounded retry.

Source facts, raw observations and inferred hypotheses are deliberately separate. The coordinator supplied broader host/scheduler cleanup status in its message; this review directly inspected the import and child-failure artifacts and does not independently certify the entire outer launch closure. GT06 remains in progress.

All paths are relative to `8-9-hh3d-3/`.
