# GT-06 S76 critical-path preparation

2026-09-18, Asia/Saigon. Preparation only; no acceptance or critic verdict.

**Prioritize a fixed editor cadence before another long campaign.** S75's native lane settles near exactly 10 process frames/second and 13 frames/cycle. Its saved unfocused-editor sleep is exactly 100 ms. This is a much stronger lead than a generic “Windows is slow” explanation. Preserve the native save/reload/readback work and the full profile; investigate and fix the cadence, then measure again. This does not resolve the separate retained-handle or host-response failures.

Scope was read-only source/raw analysis plus this one new report. No engine, host service, test suite, benchmark, process-control operation, source edit, plan edit, commit or subagent was used. Initial HEAD was `95a0cb97aace5853790c6ffe92ad85dc781645f5`; status contained existing untracked reviews. Initial process inventory found no Godot/HH engine name match. The frozen S75 input is checkpoint `979f98ef`, closure `638304f54851366ac2a79a792a8009406fc927c3c6c410ad8f65cc2dd9b14995`, profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

## Evidence and measured decomposition

Raw base `R` below means `studio/.local/reviews/gt06-s75-campaign-01/run-00-attempt-01/`, relative to `8-9-hh3d-3/`. Analysis parsed existing JSON using `python -B` without importing studio modules. All **54** references in `R/batch-capture-00.json` through `08.json` matched their recorded size and SHA256 (six references per batch: command/native/joint/ready/start/ack). This is a bounded reference check, not full capture or acceptance validation.

Durations use end minus start within each artifact's own clock. “Other” is joint duration minus command and native durations; no host/native absolute clocks were subtracted. Frame count is native batch memory frame minus native start-permit frame.

| Batch | HTTP commands, s | Native 100 cycles, s | Joint, s | Other, s | Native frames |
| --- | ---: | ---: | ---: | ---: | ---: |
| 00 warmup | 37.942 | 29.339 | 67.458 | 0.178 | 1463 |
| 04 baseline | 77.802 | 111.933 | 190.011 | 0.275 | 1313 |
| 05 | 86.649 | 131.449 | 218.338 | 0.240 | 1313 |
| 06 | 80.915 | 131.455 | 212.588 | 0.219 | 1313 |
| 07 | 102.314 | 132.793 | 235.454 | 0.347 | 1312 |
| 08 failed screen | 134.126 | 132.261 | 266.642 | 0.255 | 1313 |

The old roughly 66-second warmup claim described a combined host/native window, not a required delay. S75 batch00 was 67.458 seconds, of which only 29.339 seconds was native. S73 launch1 batch00 was 60.583 seconds joint and 26.693 seconds native. Its batch03–05 native durations were 131.368, 133.910 and 131.759 seconds, each 1313 frames. S73 launch2 batch05–09 likewise ran about 131 seconds at 1312–1313 frames. These are historical comparisons, not pooled acceptance samples.

Native batch05's 131.449 seconds breaks down as follows, derived from its 100 `raw_timings` rows:

| Segment | Seconds |
| --- | ---: |
| Timed create + undo, including their readbacks | 10.438 |
| Timed save through observed save signal and disk/scene readback | 60.425 |
| Timed reload through changed-root/generation/readback | 10.912 |
| Time outside those four operation intervals | 49.675 |

Of the save interval, 8.527 seconds occurs after the actual save signal and before its observing phase completes. This is not all disk time. The remaining 49.675 seconds includes phase scheduling, baseline/post-reload checks and final quiescence; it is not all removable idle time. Median gaps per cycle were create-end→undo-start 60.888 ms, undo-end→save-start 43.450 ms, save-end→reload-start 95.965 ms, and reload-end→next-create-start 291.891 ms. Median create-to-next-create was 1300.048 ms; median reload-observation frame difference was 13. Batch06–08 median cycle times stayed 1300.127, 1300.159 and 1299.998 ms.

`benchmark_native.gd:224–267` advances one phase per `_process`. `:428–544` separates baseline/create/undo/save/save-observation/reload/reload-observation; `:547–575` retains one frame after reload and the batch quiescence requirement. `SETTLE_US=1100000` is applied at startup and once per batch, not once per cycle. Reducing that wait cannot explain or reclaim the approximately 100-second native difference.

## Exact cadence setting and proposed bounded change

The local S75 import artifact `R/import-host/appdata/Godot/editor_settings-4.7.tres:37–41` contains:

```text
interface/editor/timers/low_processor_mode_sleep_usec = 6900
interface/editor/timers/unfocused_low_processor_mode_sleep_usec = 100000
interface/editor/display/update_continuously = false
```

The `timers/` segment matters. The pinned Godot commit is `ed1daf0bf001b61586d9930840f2f1394092c079`, from `studio/toolchain.lock.json`. Read-only verification of the exact official source confirms `editor/editor_node.cpp:966–988` applies focused/unfocused sleep on focus notifications; `:1099–1100` enables low-processor mode when continuous update is false. `editor/settings/editor_settings.cpp:510` declares the unfocused setting as integer, default 100000, restart-required; `:1193–1194` migrates old names without `timers/`. `:1427–1432` makes `get_setting()` resolve project overrides. Sources: [pinned editor node](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp), [pinned editor settings](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/editor/settings/editor_settings.cpp).

The setting plus exact cadence is strong evidence of background throttling, but S75 did not record runtime focus, effective OS sleep or low-processor mode. The saved settings alone do not prove which branch was active at every instant. Scheduler task XML has `<Priority>6</Priority>`; that does not prove the native process's actual priority or exclude other scheduling pressure.

Recommended coordinator A/B diagnostic: prepare two disposable copies before launch, default unfocused 100000 versus **integer 6900**, retaining focused 6900, continuous-update false, ordinary VSync, identical semantic cycle/settle/readback work, and separately frozen provenance. Pin the responsive variant in the generated `[editor_overrides]` block rather than changing user/global settings, stealing focus, calling OS priority setters, or editing a live run. Observe `EditorSettings.get_setting()` values plus `OS.low_processor_usage_mode`, `OS.low_processor_usage_mode_sleep_usec`, focus and native frame/time deltas in the diagnostic. The workload may run below the theoretical cap; 6900 is a sleep configuration, not a promised frame rate. Keep the full benchmark counts, 500 ms p95, 2-second progress gate, RSS/handle/object/resource rules and 7410-second limit unchanged.

This follows the existing maintainable path: `run_native_benchmark.py:145–183` generates fixture configuration before import/freeze; line177 installs `run/output/max_lines=100`. `benchmark_native.gd:157–163` calls `get_setting()` and rejects any type/value except integer100 before effects. Preserve that cap and guard. A cadence implementation should add both exact sleep keys and continuous-update false to the same generated block, validate exact types/values before any mutation, and record effective values. Do not use `Object.get()` for override checks. Imported project hashes, frozen source manifest and runtime postcondition must agree; a restart-required setting should not be patched into an already-started editor.

Meaningful maintenance checks: import round-trip leaves generated config bytes unchanged; wrong key/type/value fails before cycle effects; runtime reads both overridden values; changing window focus does not change configured sleep; every cycle still proves save signal/disk hash, changed root, generation increment and semantic equality; actual process exits and complete owned cleanup are captured. The diagnostic remains supplemental even if faster and clean. Any adopted configuration/source requires fresh campaign provenance; S73/S75 samples cannot be relabeled or resumed into its acceptance package.

Do not first refactor phase transitions into an eager loop. That could reduce approximately five frame gaps per cycle, but changes interleaving with editor callbacks and deferred deletion and may hide retained-state faults. The exact responsive-cadence override is smaller, isolated and easier to reason about. Keep scene preview/save behavior and required postcondition waits intact.

## Host command cost and next optimization order

The host is also material and grows with history. S75 journal sizes after batch04/08 were 4,916,197/8,861,577 bytes. Sequential command row spans accounted for 74.586/129.187 seconds of their 77.802/134.126-second batches, respectively. Across batch04–08 only 3, 1, 2, 4 and 7 extra terminal lookup attempts occurred among the main 1000-command mix. The explicit 1 ms lookup retry sleep therefore contributes only milliseconds of requested delay, not the tens of seconds at issue.

Do not estimate total command work by summing `latency_ms` alone: admitted latency records its admission receipt, while execution also waits for terminal lookup/readback (`benchmark_commands.py:206–234`). For batch08, the published class sums are inspect84.271 + admitted19.752 + reject1.292 = 105.315 seconds; the remaining time largely includes admitted terminal waits, not unexplained sleep.

`VerifiedJournal._snapshot` still reads/hashes all bytes and preserves recovery fsync under the accepted writer guard for each operation. The S71 performance report's lower bound of 3207 full-history scans and 1403 appended records per complete batch remains structurally relevant after S73's SHA512 factory change. A batch at around 8 MiB history entails tens of GiB of logical scan traffic; actual wall-time attribution is absent. S73's paired 32 MiB study measured 76.177→56.900 ms median scan cost, not a 25% campaign speedup. It found little buffer-only gain, so reopening buffer tuning has lower priority than native cadence.

Additional harness overhead exists: `CampaignProducer._received` calls `NativeLog.poll` on each response; this calls owner watchdog, stats stderr and opens/seeks stdout. The stdout reader advances an offset (`run_benchmark_campaign.py:99–163`), so it is not a full-log rescan. The owner traverses its bounded workspace at most once per second (`benchmark_job.py:317–339`). Base response handling also rechecks a bounded diagnostic ring. Preserve fail-fast warning/error/Stop/watchdog detection; there is no evidence that disabling these checks will solve the dominant cost. If host time remains high after cadence isolation, collect aggregate time/count for journal refresh/hash/fsync, receipt submit/lookup and watchdog polling on a bounded diagnostic. This can distinguish scanning from lock/scheduler/I/O cost before a larger change.

After such attribution, a compound admission transaction is a possible maintainable larger optimization: reconcile ID, lease/revision and pending append under one existing writer-guard interval rather than multiple independent full refreshes. The S71 design estimates 900 fewer refreshes per batch, about 28% of its minimum main-mix scans, not 28% of total wall time. It crosses accepted core/transport boundaries and requires an explicit source scope, preserved validation precedence/durability/uncertainty semantics and adversarial equivalence evidence. No metadata-only/tail-only trust, receipt eviction, journal reset, skipped fsync, enlarged deadlines or removed lookup is justified.

## Separate failures and scope limits

S75 remains failed. Batch04–07 joint editor handles were577 and batch08 was579; host handles194, editor objects71130 and resources6 stayed flat. `child-failure.json` records `CAMPAIGN_RETAINED_COUNTER_GROWTH` at batch08 after9 captures. Batch08 also has command progress gap2016.221 ms: inspect226 received pending, then `CONNECTION_LOST_LOOKUP` after2013.940 ms, then committed; terminal span3519.3582 ms. This additional failure remains even if a cadence change fixes total duration. Neither a speedup nor correlation with focus can waive retained handles, relabel UNKNOWN as ACK or supply missing native exit evidence.

Local scope answer: GT-01–05 establish pinned bootstrap, protocol/safety, bounded Godot editor mutation, Blender jobs, and validated Blender→GLB→Godot fixture pipeline. They do not mean a complete arbitrary 2D/3D game authoring surface. Current `scene_commands.gd:48,448` explicitly restricts scene nodes to `Node3D`/`MeshInstance3D`, with BoxMesh restrictions; it does not establish Sprite2D, CharacterBody2D, TileMap or combat-authoring support. A Superfighters-like 2D game would need its own approved 2D node/resource/physics/input/gameplay operations, original assets and actual game E2E/quality evidence. This tools gate does not open or accept the separate Vault Fighters route.

GT-06 adds actual Play/input/observe/capture/repair on the fixture; the tools plan explicitly excludes HH World source and gameplay/network acceptance (`:788–811`). GT-07–10 still cover publication/recovery, target/CI including physical Android, conformance and package delivery. The HH World plan keeps `H2-P0-01` dependent on accepted GT-10 and re-verifies real 3D game workloads; the tool command benchmark is not evidence of avatar, multiplayer/server, map, gameplay or shipping quality. No product gate was opened here.

## Input fingerprints for this analysis

Use each retained batch-capture JSON for the complete six-artifact reference set. Selected independently checked fingerprints:

| Raw input | SHA256 |
| --- | --- |
| `R/command-04.json` | `735caedcf0297d55c210d50c4cb58fa7196d22ca3f70946d9e497580a54c0f7a` |
| `R/command-08.json` | `43daf97dcda536688c4687d00f71c284b24a0312e9a877a4c310a9f73aede2ed` |
| `R/project/benchmark/out/batch-05.json` | `eef5b5402efe9d98ff30eed3d3585a6fec3ca2d0f1655b3d4aaeadb15da35176` |
| `R/project/benchmark/out/batch-08.json` | `31d8d9607cf77e21fb460381180690de93b03767744e042e7cd879347a94b8de` |
| `R/import-host/appdata/Godot/editor_settings-4.7.tres` | `6adc3cb2b75a15e88cb2fbf05baafe16bf3dd6f3c75dd09b69fd4ee103593335` |
| `R/child-failure.json` | `7d10c71ebd64fe589109835f8a9e9fbeb0cc7f01d3685abc899411bee69124d5` |

Prior local analyses read: `reviews/20260918-gt06-s71-next/performance-path.md`, `reviews/20260918-gt06-s73-recovery/performance/recommendation.md`, `reviews/20260918-gt06-s73-next/warmup-watchpoint.json`, and `reviews/20260918-gt06-s75-recovery/next/telemetry-plan.md`. These paths are under `zdoc/`; none grants acceptance.
