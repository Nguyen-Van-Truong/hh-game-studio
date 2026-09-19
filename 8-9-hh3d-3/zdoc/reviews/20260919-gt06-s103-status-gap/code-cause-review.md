# S103 code-cause review — S102 status-gap failure

AUTHORITY=0. Read-only diagnosis, no acceptance or critic verdict. Reviewed 2026-09-19. No engine, campaign, or tests run by this worker; no runtime source changed.

Frozen runtime under review: checkpoint `56bfd448e83aa2512c0c2561e8e1a29f12134360`, formal 53-file closure `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`. Current Git HEAD observed `d3693ddb741c618b0487bc2504ac19e4dbaaf406`; the seven runtime files listed below were compared byte-for-byte with the S102 raw run's `source/studio/...` copies and all match.

## Finding

The failed `CAMPAIGN_STATUS_GAP` is a native editor interval, not a failed HTTP lookup. The smallest supported localization is **batch 6 / cycle 74, save dispatch through the next benchmark `_process` heartbeat**. Evidence does not yet distinguish synchronous `save_scene()` duration from subsequent Godot frame work or process scheduling. No production repair is causally established.

The native maximum is 2109.351 ms. The command maximum is 1936.8697 ms, below the unchanged 2000 ms gate. Native start-permit gap is 548.256 ms; the native batch and ACK both retain 2109.351 ms. The maximum is already present before the ACK, so the ACK receipt is not proof the delay occurred while waiting for that ACK.

Raw root: `studio/.local/reviews/gt06-s102-campaign-01/run-00-attempt-01/`.

| Observation | Native microseconds | Meaning |
|---|---:|---|
| stdout line 1312 | 651389903 | b6/c74 heartbeat, phase SAVE |
| raw_timings[74].save.start_us | 651390132 | 229 us later, `_save` starts |
| save_signal_mono_us | 652296856 | `scene_saved` callback, 906.724 ms after save start |
| stdout line 1313 | 653499254 | b6/c74 heartbeat, phase SAVE_WAIT; 2109.351 ms after prior heartbeat |
| raw_timings[74].save.end_us | 653519351 | readback complete, 2129.219 ms total save measurement |

There are 1202.398 ms from the scene-saved signal to the next heartbeat. The callback proves the main thread ran inside the overall heartbeat interval; this is not evidence of one uninterrupted 2109 ms CPU stall. The missing boundary is the return from `EditorInterface.save_scene()`.

## Code path and exclusions

- `studio/tests/replay/benchmark_native.gd:274` calls `_heartbeat()` at `_process` entry, before dispatching one phase. `_save` at line 690 sets `SAVE_WAIT` and calls `EditorInterface.save_scene()`; the signal handler at line 700 only records count/time. The next `_process` entry supplies the later heartbeat. `_wait_save` at line 710 performs scene inspection and file hashing after that later heartbeat. Therefore its roughly 20.097 ms of final readback is outside the failed heartbeat interval and cannot explain it.
- `_heartbeat` at line 1028 uses a 500000 us cadence, with the unchanged gap based on consecutive emitted native timestamps. The 2109.351 ms is independently recoverable from original adjacent stdout markers. There is no subtraction of command latency, save work, or observer overhead.
- `studio/tests/replay/run_benchmark_campaign.py:909` completes `producer.run_batch`, writes its command report, collects Python garbage, and only then publishes the start permit at line 920. It waits for native batch completion at line 922. Native b6 begins at 621451115 us and the failed interval is approximately 29.939 s later. The host is waiting for the native batch at that time, not issuing the b6 command mix.
- `CampaignProducer._received` polls native logs after host responses. `NativeLog.wait` continues polling the owned process and reading stdout while native work runs. Its current evidence has no per-poll timing, so shared-machine contention or polling cost cannot be ruled out merely because the command mix is sequential. It does not invoke journal lookup during that native wait.
- `VerifiedJournal._writer_lock/_reload/_snapshot` still serialize, fully read/hash, and fsync unchanged durable history. The disposable SQLite index retains `synchronous=2`. Accepted journal `lookup` remains decorated with the writer-lock/reload wrapper. These operations can contribute to command-lane latency, but no call chain puts them inside the failed native interval. Keep the existing journal/index implementation; the prior 2.3 ms hash-reader result is not a remedy for this new failure.
- The accepted adapter IPC remains disabled for this benchmark. Native `save_scene()` goes directly through `EditorInterface`, not the Python HTTP/journal path.

## Broader pattern

Native b0–b5 take 23.432–29.901 s each. Native b6 takes 66.479 s. The saved scene remains 295 bytes, and all required cycle baseline/readback hashes remain equal. Within b6, latency grows across multiple operations:

| Median latency | cycles 0–19 | cycles 80–99 |
|---|---:|---:|
| create | 50.4875 ms | 251.7985 ms |
| undo | 36.6275 ms | 105.9815 ms |
| save including signal/readback | 65.7100 ms | 636.9240 ms |
| reload | 18.6315 ms | 40.7580 ms |
| save signal to readback end | 15.4275 ms | 397.6800 ms |

This supports investigating a broader native/frame or scheduling slowdown rather than treating one tiny file hash as the cause. It does not identify disk, renderer, thermal/power state, external activity, or editor internals as the root cause. The startup cadence readback is unchanged: low-processor mode true, sleep 6900 us, unfocused sleep 6900 us, continuous update false, output cap 100. None of those startup values establishes later scheduling behavior.

## One bounded next experiment

Before another full campaign, add **supplemental observation only** to the benchmark-owned native fixture: `_process` entry/exit timestamp and frame number, save-call entry/return, scene-saved callback, and first next-process entry. Retain fixed-size primitive records and the first threshold-crossing window; write them only after work/quiescence or failure. Bind the sidecar to run/source/profile/PID and retain all original heartbeat/gate calculations unchanged. Do not add forced heartbeats inside `scene_saved` or exempt save duration: either would make this failure disappear without demonstrating responsiveness improved.

Use exactly one diagnostic prefix retaining the original sequence and workload: at most batches 0–6, one host/editor pair, no retry, a 15-minute outer ceiling, and the existing per-phase/Stop/cleanup limits. Stop after a captured >2000 ms interval or completion of b6, whichever happens first. Label the prefix ineligible for acceptance; do not change the formal 35-batch profile, baseline, timeout, thresholds, or public core pins. If it does not reproduce, report that outcome and the bounded timing distributions; do not automatically extend or launch a second probe.

The experiment has a concrete branch decision:

1. Long save-call entry→return: investigate stock editor save path and save-associated callbacks; do not alter accepted journal durability.
2. Short save call but long `_process` exit→next entry: investigate engine remainder/frame scheduling, using an owned bounded OS sampling trace only if this branch is observed.
3. Long GDScript phase body outside save: the measured phase boundary identifies the next narrow code path.

If implementation budget permits only one added datum, save-call-return timestamp is the highest-value missing boundary. A fresh one-cycle native smoke test cannot settle a failure observed after six full batches of residency.

## Source checks and raw hashes

All seven files match the S102 frozen source copies: `verified_journal.py`, `disk_journal_index.py`, `core/journal.py`, `benchmark_transport.py`, `benchmark_commands.py`, `benchmark_native.gd`, `run_benchmark_campaign.py`.

| Raw evidence | SHA-256 |
|---|---|
| editor-host/stdout.txt | 076d719a7f6326e2965cc097e6ce03ead80a0cc687ae8b8458ef491215c56a96 |
| project/benchmark/out/batch-06.json | 8a950e0d9628b4033fc346eff02384eace33e942dc58148b65d6cf0aba77bc26 |
| joint-06.json | b5d86b91c87eb88999cee6d66da7f5ff40d42ca9c2dc44b18bc7954446be1a19 |
| command-06.json | 5d248a2ab3758a69a4671f0b64cfe51242fb1545f86891f3987390f735360e00 |

Raw preservation, source closure verification beyond these seven files, target/helper exit adjudication, and cleanup remain coordinator-owned. This memo cannot convert the failed S102 campaign into acceptance.
