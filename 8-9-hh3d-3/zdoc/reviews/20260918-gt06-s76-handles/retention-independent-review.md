# S76 retention: independent diagnostic review

Reviewed 2026-09-18 00:02:39 UTC (07:02:39 Asia/Saigon). This is a bounded diagnostic review, not a gate critic or an acceptance signature. GT-06 remains IN_PROGRESS. No runtime, plan, acceptance rule, raw artifact, test, engine process or other agent was changed/launched. The only authored file is this report.

The observed repository HEAD was `dfbed1621a831abd9cc005f2b1ee01de9fec2702`; tracked status was clean at the initial check, with existing untracked review material. No Godot/Blender process appeared in that check. The coordinator is separately preserving evidence and checking ownership.

The nested AGENTS.md and tools plan S76 route this review to GT-06. `R` below means `studio/.local/reviews/gt06-s76-retention-01/`; `D` means this report's directory, both relative to `8-9-hh3d-3/`.

The key result is **a stable final handle plateau, with one newly observed Event + IoCompletion pair still present after the final idle**. This run does not establish that every +2 increase is transient. It also does not demonstrate increasing retention across the last three 100-cycle blocks. Neither statement clears the S75 failed benchmark.

## Evidence integrity and execution scope

The completed diagnostic has eight batches of 100 semantic create/undo/save/reload cycles, followed by a fixed 60-second idle. All 800 cycle rows contain one effect per operation, main-thread=true and matching before/undo/reload semantic hashes. All eight batch file hashes match their index. The source map contains 39 files, closure `aa58e8ee7fc4f8399766c8d6beca9dfc1bf10b5247ab7f2aba5cb0d40c259b6f`; all 39 frozen copies and current corresponding files match their recorded hashes. The runtime map contains 54 files. The diagnostic and PSS helper hashes match their current files. This smaller source closure is not the plan's 49-file full-campaign closure.

All nine PSS files match `R/result.json`. Entries recount to the recorded type totals and captured totals. At every point, before count = captured count = after count; PID is 25368, and snapshot/marker cleanup is recorded true. Capture flags are 0x3c. Exactly 192 entries per snapshot lack valid type information; their count stays constant, but their meaning remains unknown.

Import PID34140 and editor PID25368 both have separate actual exit-0 records. Their capture artifact hashes match the process-start/process-exit/stdout/stderr bytes. Both captures record natural tree exit, zero active processes and closed/untainted Jobs. Editor cleanup additionally records wrapper exit0 and its wrapper-process handle released. Native stderr files are empty. Editor stdout terminates with COMPLETE, explicitly `benchmark_complete=false`, `host_integrated=false`. Editor elapsed time is 331.594s. `D/retention-owner-01/capture.json` separately reports target37480/wrapper30776 exit0, no timeout, verified tree and unchanged helper sources; it is supporting owner summary, not a substitute for the target-native exit files.

The fixture uses the current guarded configuration: focused/unfocused sleep6900µs, continuous updates false. All nine sampled points were focused. There is no HTTP command mix, joint host sample, Stop workload or host barrier. Native output explicitly identifies this as direct semantic fixture coverage. `warmup=false` in all eight diagnostic batches; discussion of batch4 below is only comparison with the full profile's fixed baseline position.

## Exact counter sequence

Objects below are from both the original batch memory record and its subsequent diagnostic point; they agree for all eight workload points. Idle has only the diagnostic point. Resources are6 throughout. Handles are the externally observed PSS counts, not a native memory field: native batch `held_handles` and RSS are explicitly unavailable.

| Point | Cycles completed | Native time, s | Handles | Objects | Resources | Handle type delta from previous point |
|---|---:|---:|---:|---:|---:|---|
| batch00 | 100 | 42.512133 | 573 | 71125 | 6 | Initial observation |
| batch01 | 200 | 74.652719 | 565 | 71125 | 6 | Event−2, ALPC Port−4, Thread−1, Timer−1 |
| batch02 | 300 | 107.499935 | 565 | 71127 | 6 | None |
| batch03 | 400 | 139.879596 | 557 | 71125 | 6 | Event−4, IoCompletion−1, Thread−2, Timer−1 |
| batch04 | 500 | 173.137265 | 559 | 71125 | 6 | Event+1, IoCompletion+1 |
| batch05 | 600 | 205.312184 | 559 | 71125 | 6 | None |
| batch06 | 700 | 238.154186 | 559 | 71125 | 6 | None |
| batch07 | 800 | 268.583262 | 559 | 71125 | 6 | None |
| idle | 800 | 328.704932 | 559 | 71127 | 6 | None |

The end-to-end difference from the first observed point to idle is handles−14: Event−5, ALPC Port−4, Thread−3, Timer−2; IoCompletion has zero net change. This aggregate does not imply that each later addition was released.

At the final plateau the complete type census is: unavailable192, Event116, Thread45, Key37, Semaphore29, WaitCompletionPacket28, File26, ALPC Port17, Mutant16, Section15, IRTimer12, IoCompletion12, TpWorkerFactory6, Directory2, WindowStation2, IoCompletionReserve2, SchedulerSharedData1, Desktop1. Sum559.

## Retained observations versus transient observations

* **Event/IoCompletion additions remain observed.** Between batch03 and04, new slots2628 (IoCompletion) and2820 (Event) appear. Their entries, type and flags are unchanged at every later sampled point, through idle155.567667s after the first observation and60.121670s after batch07. There are also three subsequent 100-cycle blocks in that interval. It is correct to say that the additional typed slots remain observed through idle. Snapshot equality does not prove uninterrupted lifetime or kernel-object identity: slots may close and be reused between observations. Names are unavailable, and no allocation/close caller is recorded. Therefore neither leak, legitimate persistent initialization nor a particular library/caller has been identified.
* **Other handles disappear.** Eight handles net disappear between00→01 and another eight between02→03. These are count/type decreases within this diagnostic. They are evidence that some activity is temporary, not evidence that the later pair is temporary.
* **One File slot changes every workload batch with no File-count growth.** The observed sequence is2476→2356→1944→1844→2976→2888→2300→2672; each step removes the former slot and adds the latter. Final2672 remains observed at idle. These entries have no name digest. Their path, caller and identity are not known. A closed GDScript FileAccess or scene-save path cannot be assigned as the cause from this data.
* **Object count has a demonstrated transient increase at batch02.** Both native and diagnostic counts rise71125→71127, then return71125 at03 and stay there through07. The exact object classes/owners are absent. ResourceCache count remains6.
* **The idle Object+2 is unresolved.** The diagnostic creates a SceneTreeTimer and awaits its timeout while a coroutine is active before publishing idle. That is an instrumentation-specific state, and the source makes instrumentation a plausible contributor. The raw evidence does not identify those two objects and has no later post-coroutine object census; it is not valid to assert that both are proven timer/coroutine objects, or that they leaked. The native resource monitor remains6.
* **Process exit is separate.** Clean exit/Job release verifies the owned process lifecycle. It cannot establish absence of undesirable retained resources while the editor was alive.

Sampling is not simultaneous across APIs. Native quiescent memory is read before serializing/publishing the batch; diagnostic point timestamps are19.372–27.450ms later, in the same recorded process frame. PSS happens after point publication while the coroutine yields. Before/captured/after count equality is useful, but does not make the native counters, diagnostic point and PSS snapshot one atomic sample. PSS itself took5.771–60.715ms; timings are supplemental.

## What the earlier comparison does and does not show

All13 stock and16 responsive references listed in `D/comparison.json` were rehashed successfully. Those arms use source closure `b52204d79923644a6d0102357e05db03dd124090c1d911d2d0c5b78498eb2235`. The current retention source differs in the native driver and project-preparation script. Both earlier arms use6×50 cycles, while this run uses8×100. Counts or speed cannot be pooled into one acceptance run.

* Earlier responsive handles are574,566,566,566,559,561, then558 idle. The net final workload increase is Event+1/IoCompletion+1. **Idle does not remove those newly added slots.** Batch04→05 adds IoCompletion2196 and Event2352; both are still present at idle. The three removed idle entries are Event1716, Event2888 and IoCompletion2936, which were already present at batch04. Thus561→558 is an aggregate decrease caused by other slots disappearing; it is not evidence that the new pair was released. Handle-slot identity caveats still apply.
* Earlier stock handles are566,558,560,560,560,562. Its final net+2 is Event+1/Thread+1, with additional slot churn. There is no completed stock idle/native-exit proof. It cannot establish eventual release.
* Workload objects71123/resources6 were flat in the earlier arms; responsive idle objects71125. The absolute object-level difference between different instrumented sources is not an identified leak or an identified guard-allocation cost.

The S75 full campaign remains separately failed at batch08 with577→579 editor handles and a2016.2214ms host status gap. S75 has no typed handle census for that failing sample. The recurring type pattern in these diagnostics cannot retroactively identify its two handles. Native retention's maximum recorded status gap578.721ms excludes the HTTP path and does not repair that second failure.

## Fastest justified next step under the existing rules

Use **one bounded combined diagnostic on the current frozen cadence**, with the exact first nine full-mix batches (five existing warmups plus four measured-position batches,1000 HTTP commands and100 native cycles each). This directly revisits the first known S75 failure position and the missing host/editor interaction. It is more informative now than another native-only idle extension or another30-inspect-only lane. It remains a diagnostic, and its partial samples must never be promoted or spliced into a full campaign.

Keep baseline at batch04, all status/counter limits, the normal joint observation/ACK order, source binding and declared deadlines. Add fixed PSS observations after the ordinary joint counter observation, at predeclared boundaries; do not wait/resample until a count falls. Record native time, host time/phase and creation-bound PID so work count and elapsed-time correlation can be distinguished. PSS overhead makes this instrumented lane supplemental. The existing S75 path already reconciles a lost lookup successfully; preserve that behavior while recording the concrete lookup exception/timing and bounded journal/transport/watchdog attribution. Any diagnostic failure must still capture actual target exits and complete owned cleanup.

If the pair or another increase recurs beyond the fixed baseline, use that captured type/phase to select a process-scoped allocation/close attribution experiment. PSS census alone cannot reveal the responsible caller, and generic thread-start-module data is insufficient. Do not invent a cleanup fix, close target handles from the observer, or suppress the counted types. If this bounded combined lane is clean, it supports attempting a newly frozen full campaign, not accepting GT-06.

An operational alternative avoids a separate pilot: start one fresh S76 full campaign and let its existing fail-fast checks govern the first integrated run. This is defensible as verification of the changed cadence after the completed diagnostics, with both S75 issues explicitly unresolved. It does not need another permission or a claim that a root cause was fixed. Keep PSS or other added attribution outside valid timed samples; if in-band instrumentation is added, identify that attempt as diagnostic. On a new failure, preserve the original counter/status failure and collect only bounded supplemental evidence before verified cleanup. Do not repeatedly relaunch an unchanged failing campaign. This route saves the duplicated prefix when the fresh run succeeds; the instrumented nine-batch route provides stronger immediate attribution if it fails.

The existing gate checks every post-warmup required non-RSS counter against the exact batch04 value; any higher value fails, whether later shown temporary or not. RSS allows the existing10% bound. Therefore the current native diagnostic's559 plateau at04–07 is favorable but only three later native-only observations. The pre-baseline557→559 increase is not a reason to move/inflate baseline. The extra idle sample is not a substitute for the actual joint sampling phase. Acceptance still requires10 fresh process pairs×35 complete batches, unchanged mix/profile,500ms p95 gates,≤2s status gap, actual exits/cleanup and two independent final reviews on the same closure.

## Re-audit anchors

SHA256 values, exact bytes as read:

| File | SHA256 |
|---|---|
| `R/diagnostic.json` | `e8fa96e5432741559a4176596416553ec364736bf177856f6c8d5a5ef748e1d5` |
| `R/result.json` | `d719d811e21498e4453c0e960082ba0fba665aa10fd42e1369f9e8303a2dbd1d` |
| `R/runtime-source-files.json` | `dbea327fd9ca08ed44cc270a2dc79b493a3a4ece9e7f22c202b0eab206a27609` |
| `R/project/benchmark/out/index.json` | `6efe0783811c2d28a977f42ee6505421dc9c48fa48917449fabaa62056ff2abe` |
| `R/editor-host/capture.json` | `d46f0a0a0b26cdfe22b8ef208f2f137685f6e29916b3ffa2506ecf1a97afb537` |
| `R/editor-host/process-exit.json` | `594a25f641e5eaf496daf3ff3784716cda035a5173b29de96d2f1f5659505f42` |
| `R/editor-host/cleanup-001.json` | `379d7a25b4032e6cb243e100aa8a5ebcd3d82a94e45b71e0f18e47fe7e569534` |
| `R/handles/batch-03.json` | `6ed8b5bf402acbbef9293a0c8aba027eeacf6a019dc10e2d8ac0b0e35ebbb3d3` |
| `R/handles/batch-04.json` | `2423cd1f05a3e842202c9b5b83738705be7d52531175ff79a269fbed69895a4d` |
| `R/handles/idle.json` | `d27db48737d44f1968fd39c7c162788eebf53f3da5629fb32a4d00cc4902f65b` |
| `D/comparison.json` | `39d4aecf67db4482ac05f871f971c07c422932760d0aa7489c13c512adc38274` |
| `D/diagnose_retention.py` | `800491f1512078863cff009aef98e464e7af1a0eef22bdb382608ed5a5458134` |
| `D/pss_handles.py` | `020970b27fd1bd8106b1a398dc06abeb4b3cc732bafa02d211658928e89afa7e` |

Reproduction is read-only JSON parsing: recount `handles/*/entries` by `type` (null→`<unavailable>`), compare consecutive maps keyed by numeric `handle`, join labels with `points/` and `project/benchmark/out/`, and verify the hashes listed by result/index/comparison. Do not execute the diagnostic scripts to reproduce this analysis: doing so launches new work and is unnecessary for these findings.
