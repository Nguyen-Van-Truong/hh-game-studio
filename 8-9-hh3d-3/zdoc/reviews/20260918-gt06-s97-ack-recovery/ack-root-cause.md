# S97 ACK-read failure audit and narrow repair proposal

AUTHORITY=0. Read-only diagnostic audit; no acceptance verdict, source repair,
engine/test execution or process control. S96 failure remains immutable.
The parent tools plan is still GT-06 IN_PROGRESS. Its live S96 status lines are
historical relative to the terminal records inspected here.

## What the retained evidence establishes

Paths below use `R=studio/.local/reviews/gt06-s96-coupled-phases-01` relative
to `8-9-hh3d-3/`; `F=R/source/studio/tests/replay` is the executed frozen source.

- Native `R/project/benchmark/out/failure.json` reports
  `BENCHMARK_HOST_ACK_READ`, PID 50100, batch 17, cycle 100, HOST_BARRIER.
  Native time is 2114247696us, 55.117ms after barrier issue 2114192579us and
  29944.883ms before its deadline 2144192579us. This was not ACK timeout.
- `R/child-failure.json` says 17 completed batches and failure during batch 17
  joint observation. Frozen `run_benchmark_campaign.py:842` finishes `publish`
  before line 843 waits for ACK; the retained host stderr traceback reaches
  line 843. Thus host rename and subsequent exact-byte readback returned.
  This does not prove that they returned before the earlier native read attempt.
- `ack-17.json` is now 423 bytes, SHA256
  `ed082013ff329c80205d253bfe630f125978c5326797aa04e97c711c5e7c95bd`;
  this matches the emitted diagnostic manifest. It is complete JSON with the
  expected run, batch 17, source/profile, deadline and native batch digest
  `ba30ed708117e7f9bb526f49f416a4e52dbf25822dc0ad23b9562d069ad3fa11`.
  Its `.tmp` is absent. Current bytes prove retained completeness, not what a
  native open/read returned at the failure instant. File creation/write times
  describe the file, not the internal rename-handle close interval.
- Native batch 17 completed 100 cycles, with pre-ACK objects 71127/resources 6.
  There is no ACK17 receipt or joint17. Those earlier counters cannot fill the
  missing ACK-phase sample or establish absence of later growth. The S96 census
  hook is downstream of both possible failing reads and was not reached for ACK17.
- HTTP command17 completed under schema 1.3.0 with max status gap 418.1515ms,
  zero dropped commands/telemetry and cumulative 3600 effects. The final HTTP
  phase record has zero transport failures and no first-lookup-failure window.
  It does not measure native filesystem reads.

The scoped source reads were joined to retained digests (no full closure scan):

| Frozen file | SHA256 |
|---|---|
| `F/run_benchmark_campaign.py` | `bb43ecc04c2de4872177a440eb071d533efdaa9e8194f62b4e0907bad8d4b252` |
| `F/benchmark_native.gd` | `52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2` |
| `F/run_native_benchmark.py` | `e6b0f8e9711ac881cfa65b4537232c685ff577af0a13778a51cc54999b1c1fc7` |
| `R/effective-benchmark-native.gd` | `de1838cf836e7dfd9a80fa05c7636774e43da0121dc3d7b551e02b90f5f746b1` |

Root separately sealed failure manifest
`46ad1f9701c5e3bd000b7fb58e7c7d638a1c1bc580d376ea4c2df1f182b126f2`.
This audit does not substitute for that seal or its exit/cleanup verification.

## Publication is already staged; the read branch is ambiguous

`F/run_benchmark_campaign.py:87–99` writes exclusively to a sibling `.tmp`,
flushes, fsyncs, exits the with-block (closing the writer), performs no-overwrite
rename, reads the final path back and returns an actual clock sample. No direct
write to the visible ACK path occurs. `F/run_native_benchmark.py:71–79` verifies
path/size and reads bytes; that readback does not reopen the file for writing.

`F/benchmark_native.gd:833–849` checks existence, opens READ, obtains length and
reads that many bytes. **Both a null `FileAccess.open` (line 838) and a short
`get_buffer` (line 848) emit the same failure code.** Size, JSON, fields, binding,
hash and postcondition failures have different codes. `failure.json` contains
neither the branch nor `get_open_error`, read error, expected length or actual
length. A partial publication conclusion is therefore unsupported.

The start-permit reader at `F/benchmark_native.gd:552–576` repeats the same
exists/open/short-read pattern. Any justified reader correction applies narrowly
to both fixed-slot input readers. Static input loading is a different lifecycle.

## Leading hypothesis and alternatives

The pinned Godot commit is `ed1daf0bf001b61586d9930840f2f1394092c079`.
Its Windows FileAccess implementation checks existence with file attributes,
opens READ using `_wfsopen`, maps most open failures to `ERR_FILE_CANT_OPEN`,
and reads with `fread`. Its CRT sharing flags do not request delete sharing.
The engine source therefore supports an existing-but-temporarily-unopenable
file; it does not tell us which S96 branch occurred.
[Pinned Godot Windows implementation](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/windows/file_access_windows.cpp)

CPython 3.11.9 implements Windows rename with `MoveFileExW`, without replace
flags for `os.rename`. Microsoft documents a real interval in which the new
name is visible while the rename still holds DELETE access; a reader lacking
delete sharing can fail, then succeed once that handle closes. That is the
leading causal hypothesis, **not a captured S96 OS error**.
[CPython rename implementation](https://raw.githubusercontent.com/python/cpython/v3.11.9/Modules/posixmodule.c),
[Microsoft rename/sharing explanation](https://devblogs.microsoft.com/oldnewthing/20211022-00/?p=105822)

| Explanation | Evidence and remaining uncertainty |
|---|---|
| Rename's DELETE handle overlaps the native open | Matches documented Windows semantics and immediate first-read failure; S96 has no rename interval or Win32 error capture to establish the overlap. |
| Host post-publication readback itself blocks native READ | Both operations request read access; this is not an evident writer conflict. Test the read-only overlap as a negative control. |
| Antivirus/filter or another transient conflicting handle | Compatible with null-open; no handle/OS telemetry identifies an actor. Do not blame or alter unrelated software. |
| Short read due to an I/O error or external mutation | Still possible because the failure code conflates branches. Retained valid bytes do not exclude an earlier read error. No evidence identifies mutation. |
| Empty/partial JSON, malformed binding, ACK timeout or census error | The corresponding fail sites/codes and failure ordering do not support these as the recorded branch. A general partial-write story is especially weak because the writer closes before rename. |

## Smallest causal probe before editing the reader

Prepare a fresh diagnostic directory and one bounded owned pinned Godot process;
no campaign, HTTP workload or production edit is needed. Keep a DELETE-access
handle open across an actual same-directory rename. Then compare:

1. Godot READ on a normal file while Python holds a read-only handle: success.
2. Target existence and exact Win32 read with `FILE_SHARE_DELETE` while the
   rename's retained DELETE-access handle is open: complete expected bytes.
3. Godot `FileAccess.open(..., READ)` in that same held-handle state: capture
   `get_open_error` immediately, before any subsequent FileAccess operation.
4. Close the DELETE handle explicitly, signal release, then read/hash the same
   unchanged target with the same Godot process: success and exact bytes.

This deliberately holds the Windows sharing state long enough to observe it.
It is a deterministic mechanism probe, not replay of S96's missing timing.
Record source/binary/fixture identities, actual target/helper exits and all
owned-handle closure; deadline/exception cleanup must release the holder too.
No process-name kills or filesystem/security setting changes. The sibling
`rename-probe/` contains preparation only until root records execution.

## Proposed narrow repair if the mechanism probe supports it

- Preserve publisher temp/write/flush/fsync/close/no-overwrite rename/readback.
  A second ready file, delay, replacement overwrite, relaxed fsync or engine
  fork is unnecessary for the identified reader assumption.
- At the two fixed-slot READ-open null branches, immediately retain a bounded
  diagnostic containing stage (`start`/`ack`), batch, error enum, attempt count
  and first/last actual times. Treat `ERR_FILE_CANT_OPEN`/`ERR_FILE_NOT_FOUND`
  as pending availability and return to the next normal process frame under
  the **existing absolute** start/ACK deadline. Do not sleep/block the editor,
  restart a deadline, synthesize a receipt/status or change heartbeat cadence.
  Godot's coarse open enum does not distinguish a permanent permission problem;
  continued inability must still fail at that original deadline with diagnostics.
- Keep short reads, invalid size/JSON/schema/identity/hash and postcondition
  changes fail-closed; split the short-read diagnostic from open failure, with
  actual requested/read lengths and read error captured before close. No
  retry of malformed/changed content is justified by the rename hypothesis.
- Retain the original second post-read deadline check, source/semantic readback,
  counters and real receipt timestamp. No ACK/native effect advances before all
  checks. Do not relabel historical failure records or missing ACK17.

Regression should exercise behavior rather than textual presence: a real pinned
native reader stays pending through the controlled open conflict, succeeds
exactly once after release with the unchanged bytes/identity, and remains
responsive to actual heartbeat/owned Stop. A held conflict through the original
deadline must fail without advancement; malformed/zero-size/stale binding and
short-read injection must still reject. Engine-free publisher tests should
assert close-before-rename, existing-destination refusal and exact readback.
Keep injected controls separately labeled; run one bounded full ACK sequence
after the repair before any fresh coupled campaign. New source requires a new
freeze/run ID and affected dependency/remint checks, not acceptance from this audit.
