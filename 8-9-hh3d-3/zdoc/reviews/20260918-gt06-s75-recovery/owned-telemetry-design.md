# S75 owned-process telemetry — supplemental diagnostic

Prepared 2026-09-18, Asia/Saigon. This helper belongs to the GT-06 investigation, not the production runtime or acceptance tests. Baseline repository HEAD at start: `1dda560c2eb46739cbe5aff69293ec1c6056be6c`. The active tools plan was revision S74 / GT-06. Coordinator reports that S73 launch2 has now terminated with `CAMPAIGN_RETAINED_COUNTER_GROWTH` at batch9; launch1 RSS and status-gap causation remain unproven. This work does not independently audit those campaign results, change their failure state, or authorize another campaign.

The exclusive changes are `owned_telemetry.py` and this document. No engine, production source, test, launch policy, process setting, tracing session, or acceptance gate was changed. No commit or plan tick was made; integration belongs to the coordinator.

## Contract and usage

The helper reads 1–8 explicitly supplied owned processes. Every target requires its PID, **exact creation FILETIME integer** (100 ns ticks since 1601-01-01 UTC), and expected fully qualified executable path. The coordinator must obtain these from trusted ownership/launch records and confirm scope; knowing an identity is not proof of ownership. Rounded CIM/ISO creation timestamps are insufficient. Duplicate PIDs, missing identity values, non-finite timing values and invalid bounds are rejected before process opens.

Run from the workspace root; the example placeholders must be replaced by the coordinator's actual owned identity. Repeat `--target` for each predetermined target, without discovering or expanding descendants during sampling:

```powershell
python -B '8-9-hh3d-3/zdoc/reviews/20260918-gt06-s75-recovery/owned_telemetry.py' --run-id '<unique-diagnostic-run-id>' --target '<owned-pid>' '<exact-creation-filetime>' '<absolute-owned-exe-path>' --duration 60 --interval 1
```

Stdout is JSONL only; the caller captures it to a fresh evidence path and captures the helper's actual exit separately. The helper opens no output files. Do not overwrite earlier evidence. It emits `start`, one `identity` per target, `sample`, and `end`; failure can add `fatal` or `interrupted`. A missing `end`, nonzero actual exit, API failure, or unsuccessful close is incomplete diagnostic evidence. An `end.result_code` is a self-report, not independent host-exit evidence.

Duration is 0–120 seconds (default 60), interval 0.5–10 seconds (default 1). Duration zero means exactly one sample after identity checks. The deadline starts before initialization/opening, and the initial sample is attempted even if setup consumed that budget. Subsequent samples wait a full interval after completing the prior sample; there are no catch-up bursts. State retained between samples is bounded by the target count, with one prior fault count/time per target. Samples are streamed rather than accumulated.

This is a cooperative sampling deadline, not a hard watchdog: API calls, stdout backpressure, OS suspension or starvation can delay return. Use the established separately bounded host wrapper for any actual owned run and collect its actual exit/cleanup. This helper does not create that wrapper or spawn/kill any process. A full owned-workload run has **not** been performed by this worker.

## Identity, handles and read-only API scope

Each target is opened once with `PROCESS_QUERY_LIMITED_INFORMATION | PROCESS_VM_READ` (`0x1010`), non-inheritable. No broader-rights fallback or privilege adjustment exists. The retained original handle is registered for cleanup before identity querying. Creation ticks and executable path must both match; path comparison only normalizes separators/dot components and Win32 case. It does not resolve filesystem links or accept alternate executable aliases. Any mismatch or failure to establish identity aborts before collecting any target samples. [OpenProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess), [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes), [QueryFullProcessImageNameW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew).

Every sample uses those same original handles; the helper never reopens by PID, so reuse cannot redirect sampling to another process. It tries to close all original handles in `finally`, including after partial-open or identity failure, before emitting cleanup output. Failed closes are explicit and make the exit nonzero; no successful-close claim is invented. Retaining a process handle can prolong retention of its terminated kernel object until close. Closing that handle does not terminate the process. [CloseHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-closehandle).

`GetExitCodeProcess` is included only as a limited-query observation. A value other than 259 triggers `owned_target_exited` and stops sampling. Value 259 is explicitly named `still_active_or_application_exit_259`, since an application can itself return 259. No SYNCHRONIZE right or wait call is requested. The undefined exit FILETIME of a running process is never used as a liveness test. Therefore this helper is **not** the owned-tree/actual-exit verifier. [GetExitCodeProcess](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getexitcodeprocess), [GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes).

The native bindings declare argument/return types explicitly, use DWORD/ULONG as 32-bit values and SIZE_T/pointers at Python's native width, and verify memory-structure sizes before opening targets: EX 80 / performance 104 bytes on x64; 44 / 56 on x86. x86 was not executed here. The helper calls the documented modern `K32` exports in kernel32; missing exports are recorded, not replaced with inferred zeros or elevated requests. It never reads target memory contents despite requesting the specified VM_READ right. [GetProcessMemoryInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo).

## Measurements and errors

| JSON group | API / interpretation |
| --- | --- |
| `cpu_priority` | `GetPriorityClass`, raw class and known name. Process priority class is separate from individual thread priority and memory priority. [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getpriorityclass). |
| `memory_priority` | `GetProcessInformation(ProcessMemoryPriority=0)`, exact returned priority. Normal/default is 5; lower values are a trimming hint, not proof of an observed trim. [GetProcessInformation](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocessinformation), [MEMORY_PRIORITY_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-memory_priority_information). |
| `power_throttling` | `GetProcessInformation(ProcessPowerThrottling=4)`, version 1 request and raw returned version/control/state masks. Masks are preserved without claiming an effective clock, scheduler behavior, or window state. [PROCESS_POWER_THROTTLING_STATE](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/ns-processthreadsapi-process_power_throttling_state), [Microsoft SDK header constants](https://raw.githubusercontent.com/microsoft/win32metadata/main/generation/WinSDK/RecompiledIdlHeaders/um/processthreadsapi.h). |
| `memory` | `K32GetProcessMemoryInfo` + `PROCESS_MEMORY_COUNTERS_EX`: current RSS = `WorkingSetSize`, private commit = `PrivateUsage`, fault count = unsigned `PageFaultCount`. Bytes are preserved; private commit is never substituted for RSS. Fault counts do not isolate hard faults or disk I/O. [Structure](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex), [Working Set](https://learn.microsoft.com/en-us/windows/win32/memory/working-set). |
| `handle_count` | `GetProcessHandleCount` on the retained owned handle. [Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesshandlecount). |
| `system_memory` | `K32GetPerformanceInfo` once per sample: physical available/total, commit total/limit in both raw pages and bytes, plus page size. Byte conversion is pages × actual PageSize. Available includes standby/free/zero pages; commit above physical total is not proof of current pressure. No individual unrelated process is inspected. [GetPerformanceInfo](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getperformanceinfo), [PERFORMANCE_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-performance_information). |

Fault deltas compare successive successful memory reads of the same retained handle; `delta_interval_ns` discloses that interval, including skipped/error samples. The first delta is null with `no_previous_sample`. A decreasing 32-bit count produces null with `counter_decreased_or_wrapped`; there is no guessed rollover correction. The helper retains original absolute counts.

Each API group has `status=ok`, `status=unavailable` with the missing export, or `status=error` with the API and immediate `GetLastError` code/message. Failed groups have no numeric counter values. A legitimate zero appears only after a successful API call. A failure without an extended error explicitly says so. Individual metric failures are collected through the bounded window and make completion code 1; identity/open/lifecycle failures abort with code 2. Close failure is code 3, interruption 130. Argument errors use argparse exit 2. All nonzero outcomes are diagnostic failures/incompleteness, never benchmark failures repaired or benchmark PASS.

UTC and monotonic timestamps appear on every event. The monotonic clock uses `time.perf_counter_ns` for high-resolution Windows timings; its reported resolution is included in `start`. Each sample and process group records collection boundaries. Calls are sequential, not an atomic cross-process/system snapshot, and an individual counter's timestamp is bounded by those collection times. Normal sleep/scheduling can delay samples. Source SHA256, observer PID, Windows build, pointer width, requested timing, expected identities and exported-API availability are emitted once at start.

## Validation performed

`ast.parse` passed without generating bytecode. The final helper was run on itself only with:

```powershell
python -B '8-9-hh3d-3/zdoc/reviews/20260918-gt06-s75-recovery/owned_telemetry.py' --run-id gt06-s75-owned-telemetry-self-02 --self-test
```

Actual shell exit was 0. At `2026-09-17T22:21:27.739510+00:00` (05:21 on September 18 Asia/Saigon), Python 3.11.9 x64 / Windows build 26200 sampled exactly one helper PID, 35400, creation FILETIME `134341572874805730`; all API groups succeeded, cleanup recorded the one original handle closed, and elapsed helper time was approximately 4.285 ms. The native reads returned CPU NORMAL (32), memory priority 5, power version 1/control 0/state 0, current RSS 19,734,528 B, private commit 11,501,568 B, faults 4,947, handles 158. These values describe that self-test instant, not any campaign process.

Final helper SHA256: `2fe8051e5e3a50ebdddfefb34aaa3fed5ee4e20341ca1f8ccb37ae05da12b0ef`. A prior self-only single sample validated the API layout, after which the coarse Python 3.11 `monotonic` clock was replaced with `perf_counter`; the final `-02` validation covers that change. No external target, multi-sample duration, PID mismatch, target exit, missing export, access denial, broken stdout or CloseHandle failure has been runtime fault-injected. The success path was checked; failure handling remains subject to coordinator review.

## Interpretation limits

This is supplementary telemetry, with real observer CPU/memory/IO cost. The self-test is not an overhead benchmark on the campaign. Do not silently add this observer to an official campaign or reuse its self-sample as launch-policy evidence. A bounded coordinator-owned diagnostic can correlate RSS/private commit/faults/availability and inspect actual priority settings before deciding whether a justified correction or further measurement is needed. System-wide values and process values are not simultaneous, and the helper samples no native ObjectDB/resource inventories, window state, thread priorities, per-page residency, hard-fault attribution, ETW or trimmer identity.

Stable private commit with falling/recovering RSS and rising faults would be consistent with residency churn, but would not prove its cause, absolve retained-object growth, or explain the complete status-gap path. No snapshot can reconstruct missing launch1/launch2 telemetry. Keep all failed attempts, current-RSS baseline/growth gates, timing limits, prescribed warmups, native workload, source freeze, actual exits and independent critic requirements unchanged. The coordinator must authorize and serialize any next owned run; no setting change or rerun is initiated by this helper.
