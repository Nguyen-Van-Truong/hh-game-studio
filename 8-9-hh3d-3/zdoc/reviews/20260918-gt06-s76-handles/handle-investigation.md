# S76: S75 editor handles and the next bounded diagnostic

Read-only investigation, 2026-09-18 Asia/Saigon. This is not an acceptance review. No engine, diagnostic workload, test suite, process kill, runtime edit, plan edit, gate change or commit was performed by this worker. The coordinator owns any experiment and helper implementation. The only worker-authored file is this report.

The active nested `AGENTS.md` routes this work to the tools plan, revision S75, `CURRENT_VALID_WP=GT-06`. The inspected campaign is `gt06-s75-campaign-01`, run `gt06-s75-campaign-01.r00.a01`, under `studio/.local/reviews/gt06-s75-campaign-01/run-00-attempt-01`. Its declared source checkpoint is `979f98ef`; closure is `638304f54851366ac2a79a792a8009406fc927c3c6c410ad8f65cc2dd9b14995`; profile is `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. All 49 preserved source files were independently hashed against this run's `source-files.json`, with zero mismatches. Repository HEAD observed during investigation was `95a0cb97aace5853790c6ffe92ad85dc781645f5`.

## Observed failure, with every counter retained

The editor's count first exceeds the final warmup baseline at batch8: 577 to 579 handles. ObjectDB stays 71130 and cached resources stay 6 throughout batches4–8. The Python host stays at 194 handles. This is a distinct unresolved Windows handle observation; the earlier `.gdignore` proof does not explain or repair it.

Values below come directly from the `joint-04.json` through `joint-08.json` files. RSS is bytes, not private commit.

| Batch | Role | Handles | Objects | Resources | RSS bytes |
|---|---|---:|---:|---:|---:|
| 4, baseline | Editor | 577 | 71130 | 6 | 185987072 |
| 5 | Editor | 577 | 71130 | 6 | 186888192 |
| 6 | Editor | 577 | 71130 | 6 | 159019008 |
| 7 | Editor | 577 | 71130 | 6 | 112214016 |
| 8 | Editor | 579 | 71130 | 6 | 96612352 |
| 4, baseline | Host | 194 | N/A | N/A | 27201536 |
| 5 | Host | 194 | N/A | N/A | 29204480 |
| 6 | Host | 194 | N/A | N/A | 29368320 |
| 7 | Host | 194 | N/A | N/A | 28995584 |
| 8 | Host | 194 | N/A | N/A | 11411456 |

Warmup editor handle values were 587,581,581,584,577. A later value below an earlier warmup value still fails the actual baseline gate. These totals do not identify which handles were created, destroyed, reused or retained. The run has no handle-type inventory, so neither leak nor harmless transient has been established as the cause.

`sample_editor()` reads `GetProcessHandleCount` through the already retained editor-process handle. It samples after the native batch publication and before writing that batch's ACK. Opening/retaining the observer's process handle does not by itself add a handle-table entry to the target editor. The stable visible-window ID `18548876` is separate from the kernel-handle count. PID and creation identity remain editor13024/`windows:134341583460096238`, host16220/`windows:134341583363370969`.

## A second gate violation is masked by the first exception

`screen_sample()` checks counters before status gaps. The batch8 counter exception prevents execution of the subsequent status-gap assertion, but the saved sample independently exceeds that gate.

| Batch | HTTP command phase, s | Native100 cycles, s | Command gap, ms | Native gap, ms | Journal bytes |
|---|---:|---:|---:|---:|---:|
| 4 | 77.802468 | 111.933219 | 365.3157 | 675.134 | 4916197 |
| 5 | 86.649167 | 131.448903 | 320.0123 | 681.402 | 5902542 |
| 6 | 80.914519 | 131.454623 | 678.7898 | 752.183 | 6888887 |
| 7 | 102.313546 | 132.793458 | 329.5035 | 929.787 | 7875232 |
| 8 | 134.125810 | 132.260961 | **2016.2214** | 1017.122 | 8861577 |

`b8.inspect.226` was admitted QUEUED in101.1921ms. Its second lookup returned `CONNECTION_LOST_LOOKUP`/UNKNOWN, from monotonic584440192013 to584442205953 (2013.940ms). The next lookup recovered `READBACK_CONFIRMED`/COMMITTED; overall terminal latency was3519.3582ms. The successful reconciliation preserves correctness, but does not change the 2016.2214ms status-gap violation. The raw record does not identify the socket exception subtype or attribute the delay to hashing, I/O or scheduling. A handle-only repair is insufficient for the next campaign.

`child-failure.json` correctly records nine captured batches, failure at batch8 joint observation, `CAMPAIGN_RETAINED_COUNTER_GROWTH`, `completed=false`. Supervisor return reports1709.938s and return1, explicitly requiring a separate scheduler result. The host actual exit record is PID16220/exit1. Editor cleanup reports wrapperexit2, Jobzero/closed, wrapper handle released, and `BENCHMARK_CLOSED_BEFORE_FINISH`; there is no editor actual process-exit file. Wrapperexit2 cannot substitute for a native target exit. The raw native stderr is empty and stdout reaches ACK8/READY9, without a COMPLETE record. No partial run is a benchmark pass.

## Source-supported limits on attribution

The benchmark's output writer closes its `FileAccess` before publishing/returning. ACK handling also closes the file, and the host handle sample occurs before the new ACK exists. The pinned stock `FileAccessWindows::_close()` calls `fclose` and clears its file pointer; both `close()` and the destructor invoke it. A retained GDScript `FileAccess` object after `close()` is therefore not itself proof of an open OS file handle. [Pinned implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/windows/file_access_windows.cpp#L223).

The stock Windows process launcher stores a process/thread handle pair for asynchronous children, making a +2 process/thread pair a concrete *conditional* candidate if the census actually finds those types. The benchmark GDScript has no explicit `OS.create_process`/`OS.execute` call. Static source does not establish that this path ran; do not label the pair a child-process leak without its typed entries and target IDs. [Pinned launcher](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/platform/windows/os_windows.cpp#L1448).

Flat objects/resources cannot exclude OS library, driver, thread, socket or file activity. Falling RSS cannot prove cleanup or disprove retained kernel handles. The previous telemetry's high commit/low available RAM is context, not causal proof or a threshold exemption.

## Preferred next measurement: documented PSS handle census

Use one disposable owned diagnostic fixture and its known PID, exact process-creation FILETIME, expected executable path and source hash. Keep S75 raw/source and official workload untouched. First qualify the helper on a disposable process with known handles; record helper source/hash, API return codes, actual observer exit and cleanup. No system-wide process/handle enumeration is needed.

For the native fixture, capture a small predetermined sequence around normal edit/undo/save/reload blocks and fixed idle points. Three50-cycle blocks with snapshots before and after each are a reasonable first classification probe, not proof that the late S75 failure is solved. If the pair does not recur, retain the negative result and design the next fixed elapsed-time/phase-specific probe from it; do not infer long-run stability or run another full campaign blindly. Never wait or resample until counts fall.

`PssCaptureSnapshot` followed by `PssWalkSnapshot(PSS_WALK_HANDLES)` is the documented Windows interface for this job. Start with handle metadata flags `HANDLES | HANDLE_NAME_INFORMATION | HANDLE_BASIC_INFORMATION | HANDLE_TYPE_SPECIFIC_INFORMATION` (`0x3c`) and `ThreadContextFlags=0`. Omit VA cloning, VA capture, thread context, handle tracing, breakaway and process-creation flags. This requests handle values and metadata; it is not a memory dump. Capture names only within this owned fixture and redact any sensitive namespace before portable publication. [Capture](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psscapturesnapshot), [flags](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_capture_flags).

The capture documentation does not state an exhaustive minimum-rights mapping for these flags. A narrow `QUERY_INFORMATION | DUP_HANDLE | VM_READ` mask (`0x450`) is a candidate to qualify empirically, not a claimed Microsoft requirement. Avoid `ALL_ACCESS`, privilege adjustment, VM_WRITE, VM_OPERATION, CREATE_PROCESS, CREATE_THREAD, SET_INFORMATION, SUSPEND_RESUME and TERMINATE in the observer. `DUP_HANDLE` is a powerful capability; scope enforcement must precede its use. It does not authorize closing/altering target handles. The observer must keep its original identity-verified handle rather than reopening by PID. [Documented rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights).

Implementation/review requirements:

- Copy entries to primitive data immediately, including raw handle value, validity flags, ObjectType, TypeName, ObjectName, attributes and supported type-specific process/thread IDs. Respect validity flags. Unknown/unavailable fields remain unknown. Decode names using their byte lengths divided by UTF-16 character size; strings need not be NULL-terminated. `CreationTime` is documented reserved and must not become an object-identity proof. Numeric handle values may be reused. [Entry contract](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_entry), [validity flags](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_handle_flags).
- `PSS_OBJECT_TYPE` covers a small set of supported kinds; UNKNOWN is not evidence of an invalid handle. Preserve TypeName and absence explicitly, including types outside the enum. [Object types](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ne-processsnapshot-pss_object_type).
- A walk is complete only at `ERROR_NO_MORE_ITEMS` (259). Other return codes fail the census. Compare enumerated entries against `PssQuerySnapshot(PSS_QUERY_HANDLE_INFORMATION).HandlesCaptured`. Pre/post `GetProcessHandleCount` are separate-time observations, so a difference is disclosed rather than fabricated away. [Walk](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalksnapshot), [captured count](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/ns-processsnapshot-pss_handle_information).
- Register snapshot and marker ownership immediately. Always attempt marker free, snapshot free and observer process-handle close on every path; preserve any failed-close state and return failure. A snapshot captured locally from a remote target belongs to the observer: use `PssFreeSnapshot(GetCurrentProcess(), snapshot)`, not the target handle. The remote-free VM_OPERATION requirement applies to a snapshot residing in a remote process, not this case. No concurrent walk/free or double-free. [Snapshot free](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-pssfreesnapshot), [marker free](https://learn.microsoft.com/en-us/windows/win32/api/processsnapshot/nf-processsnapshot-psswalkmarkerfree).
- Record monotonic begin/end, pre/post target counts, captured-count completeness, source hash and all cleanup returns for each census. Metadata-only is not a guarantee of zero latency, synchronization or object-reference lifetime effects. Microsoft does not promise those absences. Bound the observer externally and disclose it as supplemental; do not mix observed timing with official campaign timing.

Interpret the first recurring delta before editing runtime: File entries point to the exact path/lifetime; Thread entries provide IDs for an owned thread-lifetime check; Process+Thread suggests checking actual child ownership; Event/Semaphore/Mutant requires correlation with the specific background task. Capture at fixed phase boundaries and preserve all additions/removals, not only the net+2. A pair absent in a later snapshot is evidence of bounded lifetime in that diagnostic, not retroactive permission to waive S75.

## Why not start with NtQuery or arbitrary handle duplication

Microsoft warns that `NtQuerySystemInformation` and returned structures are internal and changeable; its supported documentation does not define `SystemExtendedHandleInformation` for this task. A system-wide native table adds ABI and scope complexity when PSS can target one owned process. `NtQueryObject` likewise has a weaker compatibility contract. Do not silently switch to these APIs if PSS fails: save the exact error and reassess the diagnostic. [System query contract](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntquerysysteminformation), [object query contract](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryobject).

`DuplicateHandle` is documented, but a duplicate references the same underlying object and can extend its lifetime; operating through it can affect shared state. It requires explicit ownership and cleanup. `DUPLICATE_CLOSE_SOURCE` closes the source even when errors occur and is forbidden for an observational diagnostic. No file reads, waits that consume semaphore state, or target-handle close is needed here. Prefer PSS metadata first. [DuplicateHandle](https://learn.microsoft.com/en-us/windows/win32/api/handleapi/nf-handleapi-duplicatehandle).

## Re-audit hashes

Exact-byte SHA256, relative to the S75 run root stated above:

| File | SHA256 |
|---|---|
| `joint-04.json` | `5d5ca7504b77f883f9cfffb573cc8be190a84f9bf163a64774e6dd68a230d400` |
| `joint-08.json` | `c86a7b4ac261908b893eba0354fb9f591a4c3b300efce2f903bc8169794c5c15` |
| `sample-preview-08.json` | `ba9529ded1adfb13db066a4e21b5668be56ac92348fdf0406f15c88ade8e337e` |
| `command-08.json` | `43daf97dcda536688c4687d00f71c284b24a0312e9a877a4c310a9f73aede2ed` |
| `project/benchmark/out/batch-08.json` | `31d8d9607cf77e21fb460381180690de93b03767744e042e7cd879347a94b8de` |
| `child-failure.json` | `7d10c71ebd64fe589109835f8a9e9fbeb0cc7f01d3685abc899411bee69124d5` |

No acceptance threshold, workload, warmup count, status deadline or source attribution changes follow from this report. GT-06 remains unresolved until both observed failures have evidence-backed treatment and the required unchanged-gate verification completes.
