# S103 read-only attribution of the S102 status-gap failure

Scope: `gt06-s102-campaign-01.r00.a01`, batch 6, frozen source closure `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`, source checkpoint `56bfd448e83aa2512c0c2561e8e1a29f12134360`. Read-only diagnosis; no engine/test/retry, source change, gate change, or final critic verdict. Raw paths below are relative to `studio/.local/reviews/gt06-s102-campaign-01/run-00-attempt-01/`.

## Finding

The observed failure is the native/editor heartbeat at cycle 74, not an HTTP LOOKUP transport failure. `http-phases-final.json` has `first_failure=null`, `transport_failures_observed=0`, and zero failure counts for every route. All command batches 0–6 and their cancel lookup attempts also contain zero non-null transport failures. The first-failure copy was never triggered; it was not lost through event-ring eviction.

The full campaign is still failed. Its primary `CAMPAIGN_STATUS_GAP` follows from a genuine 2,109.351 ms native heartbeat interval, 109.351 ms over the unchanged 2,000 ms gate. The command lane's maximum is 1,936.8697 ms. Seven complete batch artifacts, including the failing batch, do not make a completed pair or acceptance dataset.

## Native evidence chain

1. `editor-host/stdout.txt:1312` records PID 14312, batch 6, cycle 74, phase `SAVE`, native monotonic time `651389903` us. Line 1313 records the same identity/cycle, phase `SAVE_WAIT`, time `653499254` us. Their exact difference is `2109351` us. This is the only adjacent native heartbeat pair over 2 seconds in the preserved log.
2. `project/benchmark/out/batch-06.json`, `raw_timings[74]`, records save start `651390132`, save signal `652296856`, save end `653519351`, then reload start `653520537` us. Save latency is 2,129.219 ms. The heartbeat interval starts 229 us before save begins and ends 20.097 ms before save readback completes. The signal arrives 906.724 ms after save start, 1,202.398 ms before the next heartbeat.
3. `batch-06.json.max_status_gap_ms=2109.351`; its start-permit gap is only `548.256`. The same maximum reaches `joint-06.json.barrier_receipt.max_status_gap_ms` and then `sample-preview-06.json.max_status_gap_ms`.
4. Frozen `benchmark_assembly.py:581` selects the maximum of command, native ACK, and native start-permit gaps. Frozen `run_benchmark_campaign.py:275` rejects above 2000. `child-failure.json` reports batch 6 / `joint_observation` because this is where the assembled sample is checked; that label is not the phase during which the heartbeat delay occurred.
5. Frozen `benchmark_native.gd:281` emits the heartbeat before executing the phase action. Lines 690–707 mark save start, set `SAVE_WAIT`, call `EditorInterface.save_scene()`, and timestamp the save signal. Lines 710–721 later perform readback. Thus the raw interval attributes to the native save lifecycle, but cannot separate time inside `save_scene()` from editor/frame scheduling after the call. A save-return timestamp is not recorded.

## Separate, sub-threshold HTTP slowdown

The longest host response-progress interval is QPC-derived host time `678891963052` → `678893899921` us: 1,936.869 ms using the exported integer microseconds (the original nanosecond maximum is 1,936.8697 ms). It spans the terminal response of `b6.inspect.452` to the admission receipt of `b6.inspect.453` (ordinal 903). The latter is a successful command admission, followed by a successful lookup, with no transport failure.

The retained HTTP ring includes the complete client/server lifecycle for this admission. Numeric socket identity is **server 54937 / client 56455**. Client root/span `218905`; server root `218909`. Event IDs 484945–484988 retain entry, socket binding, send/read, response, and exits:

| Phase | Span | QPC start ns | QPC end ns | Duration ms |
| --- | ---: | ---: | ---: | ---: |
| client.call | 218905 | 678892002202800 | 678893899848000 | 1897.6452 |
| client.connect | 218907 | 678892002464000 | 678892003935800 | 1.4718 |
| client.headers | 218908 | 678892004292900 | 678893898867900 | 1894.5750 |
| server.handle | 218909 | 678892104948800 | 678893904742200 | 1799.7934 |
| server.dispatch | 218911 | 678892105417600 | 678893898258500 | 1792.8409 |
| server.lookup, route=commands | 218912 | 678892105969200 | 678893842703700 | 1736.7345 |
| journal.guard_wait | 218913 | 678892105994600 | 678892222988000 | 116.9934 |
| journal.snapshot | 218916 | 678892223374600 | 678893842384000 | 1619.0094 |
| client.body | 218923 | 678893898890200 | 678893899748200 | 0.8580 |

These are nested/overlapping spans and must not be summed. The client/header wait contains server processing and therefore is not evidence of a network-only delay. The 1,619 ms snapshot span is an observed wall-time location, not proof of disk, hashing, antivirus, CPU contention, or any other underlying cause. `server.lookup` and its guard end with `raised`, while dispatch/client end with `returned`; frozen `host/core/transport.py:598–604` catches `COMMAND_NOT_FOUND` during admission. A raised internal span must not be mislabeled a LOOKUP-route transport failure.

The preceding successful lookup for `b6.inspect.452` uses server 54938 / client 49786, client span 218887, QPC `678890418816000` → `678891962950100` ns (1,544.1341 ms). It is also sub-threshold and distinct from the campaign's native failure.

## Retention and cross-clock limits

The final observer has 8,192 events, IDs 483527–491718, with 483,526 earlier events evicted. Timestamp coverage is QPC `678886264757600` → `678903850501100` ns; snapshot capture is `678975986862700` ns. It has zero unfinished spans, zero dropped spans, and zero missing socket identities. It preserves the HTTP slowdown above, but is not the full historical HTTP event trace.

The last retained HTTP client call ends at `678903850501100` ns and command batch 6 ends at `678903852398` us. The native batch start permit is published only after this command batch is complete (`run_benchmark_campaign.py:916–922`), and the native failure is cycle 74 after start. Therefore this HTTP slowdown precedes the native failure. There is no recorded HTTP activity during the offending native interval. Godot `Time.get_ticks_usec()` and Python `perf_counter_ns()` have different reported epochs; this packet provides no exact shared clock-offset calibration. Do not subtract their raw values or invent an exact QPC coordinate for the native heartbeat gap.

## Smallest next step

Keep this campaign failed and preserved. The raw data already identifies the failing native save lifecycle, so another full campaign is not a diagnostic prerequisite. Audit the save-call/next-frame boundary and, if runtime evidence is needed, add a bounded observation of save entry, save return, save signal, and the next native process/heartbeat callback under the same save workload. Those four boundaries distinguish synchronous save cost from time after the return. Keep observer cost in timings, source/freeze identity fresh, and the 2-second gate/workload unchanged. The separate HTTP snapshot slowdown can be investigated independently; repairing it alone would not explain or fix this failure.

## Byte bindings

| Raw artifact | SHA-256 |
| --- | --- |
| http-phases-final.json | 910257f1e7588ebf3d803cba10abf4096acb4bf29e8b9c5e866781555d440078 |
| command-06.json | 5d248a2ab3758a69a4671f0b64cfe51242fb1545f86891f3987390f735360e00 |
| project/benchmark/out/batch-06.json | 8a950e0d9628b4033fc346eff02384eace33e942dc58148b65d6cf0aba77bc26 |
| joint-06.json | b5d86b91c87eb88999cee6d66da7f5ff40d42ca9c2dc44b18bc7954446be1a19 |
| sample-preview-06.json | 959e311ff022b6cbe74d2805d9fcde41b2d336e55cb286a4a2fb11590a8bafe4 |
| editor-host/stdout.txt | 076d719a7f6326e2965cc097e6ce03ead80a0cc687ae8b8458ef491215c56a96 |

No raw or executable source files were modified by this diagnosis.
