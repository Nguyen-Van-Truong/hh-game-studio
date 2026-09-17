# S71 campaign failure preserved for S73 recovery

This is a failure-forensics package, not a critic verdict or GT-06 acceptance.
Preserved on 2026-09-18 at 03:58 Asia/Saigon (2026-09-17 20:58 UTC).
Repository HEAD at preservation: `a15cd42c5fcfa8d7c07faabd9c0247a7ab5040ac`.

Campaign `gt06-s71-campaign-01`, launch 1, attempted only
`gt06-s71-campaign-01.r00.a01`. Its child failed with `ADMISSION_UNKNOWN`
in the command phase of zero-based batch 33. It completed batches 00–32:
5 warmup and 28 measured batches, short of the required 5+30 for even one
run. There is no completed run or complete ten-run dataset.

## Exact failure and exit boundaries

- `raw/campaign/run-00-attempt-01/child-failure.json` preserves the full
  original 729,944 bytes, including the partial command report. Its last
  row is ordinal 631, `gt06-s71-campaign-01.r00.a01.b33.inspect.316`, with
  receipt `UNKNOWN / CONNECTION_LOST_LOOKUP`, `receipt_ms=2013.8505`, and
  no lookup attempts. The preceding inspect command has a committed
  readback. The failed receipt is an uncertain outcome, not proof that the
  command was never admitted. Root cause and repair belong to the coordinator.
- `host-owner/stderr.txt` records the child's `CommandError: ADMISSION_UNKNOWN`.
  The child's actual process receipt is `host-owner/process-exit.json`:
  target PID 46256 exited 1. The host-owner cleanup separately records
  wrapper exit 1. These are two evidence fields with separate meanings.
- The measured Godot editor target started as PID 11064. Its
  `editor-host/process-exit.json` is absent. Editor cleanup records wrapper
  exit 2 and `BENCHMARK_CLOSED_BEFORE_FINISH`; **2 is not a proven native
  Godot exit code**. An empty editor stderr cannot fill this gap.
- Both owner cleanup receipts record `active_count=0`, `zero_observed=true`,
  `closed=true`, no taint/native errors/failed operations, no retained Job
  handle, and a closed wrapper-process handle with no close uncertainty.
  The parent failure repeats `owned_tree_zero=true`, `owner_closed=true`,
  and `cleanup_error=null`. Cleanup is evidenced despite the missing editor
  target exit receipt; natural native completion is not established.
- Import PID 13880 has its own actual exit 0, wrapper exit 0, and completed
  capture. This proves the initial import, not the later editor run.
- Parent failure and supervisor failure report `BENCHMARK_WRAPPER_EXIT`.
  Supervisor `return.json` records intended return 1 after 6200.516 seconds
  and explicitly says its actual exit was not yet observed. The fresh
  launcher status observation supplies scheduler state 3, last result 1,
  and zero instances. Scheduler status is separate from target exits and
  native Job ownership evidence.

## Completion, Stop, and recovery eligibility

The package retains all 33 batch capture and joint records. The complete
hash inventory locates their command/native/ready/start/ACK inputs. The last
native batch (32) and its boundary artifacts are copied; ready-33 exists,
but start-33, ACK-33, native batches 33 and 34, and the native final index
are absent. `terminal-facts.json` lists the observed absences, including
child-result, assembled-run, run-capture, campaign-capture, dataset, and summary.
Partial records must not be combined with another attempt to claim a full run.

All 30 fixed attempt slots were checked with `os.path.lexists` for
`stop-request.json`; every latch was absent. Only run-00-attempt-01 exists.
The command-lane `cancel` recorded inside the partial report is a benchmark
test operation, not an operator Stop latch. No latch was created, cleared,
or bypassed during preservation.

At this observation, the prior-attempt cleanup preconditions for an unchanged
campaign's fresh attempt 2 are present: the task is terminal, owner closure
and Job zero are recorded, no Stop latch is present, and two attempt slots
remain for run 00. This is structural eligibility only; preservation did not
launch, test, or authorize a retry and did not prove the failure is repaired.
The missing native exit prevents accepting attempt 1 as a successful native
run. If the coordinator changes source, the campaign's source/machine binding
must remain enforced: preserve S71 and mint a new campaign/closure rather than
append changed source to this campaign. No success or accepted benchmark data
can be recovered from this attempt.

## Scope and byte integrity

`raw/` contains 111 selected files (3,802,277 bytes) copied without
normalization or redaction. `preserved-byte-manifest.json` binds each copy
to its original relative locator, size, and SHA-256. It includes failure,
context, source maps, owner starts/exits/cleanup/invocations/stdout/stderr,
supervisor receipts/logs/task definitions, and selected completion boundaries.

`raw-locator-hashmaps.json` inventories **all 455 files, 92,194,747 bytes**
under exactly these two raw roots, including caches and the command journal:

- `studio/.local/reviews/gt06-s71-campaign-01`
- `studio/.local/reviews/gt06-s71-campaign-01-supervisor`

The raw roots remain in place. The 33 MB journal, bulk command/native sample
data, frozen source trees, and caches are not copied into this package. The
inventory is a locator/hash map, not a portable replacement for those bytes.

`source-map-verification.json` verifies all 49 files against both frozen
source copies and checks the campaign/context/attempt maps agree. Source closure:
`38a0848b68c4d6b34f1a03839008d54aa9e99a33458abaa88a939c8d2a744d86`.
All 49 live files also matched at 03:58; later coordinator edits do not alter
the preserved S71 evidence or transfer its claims to a new source closure.

`observations/` contains host-captured read-only commands, raw output bytes,
actual observer return codes, and timestamps. The first scheduler query used
Windows PowerShell and failed because `Get-FileHash` was unavailable in that
environment. That failed observation remains intact. The `-retry-02` query
used the installed PowerShell 7 executable and completed successfully. The
task was neither run nor deleted by either query. The process-name snapshot
observed no Godot/Blender process; it does not manufacture a native exit code.

`preserve.py` documents the collection procedure. It writes only this failure
directory and invokes no engines/tests/process control. `verification.json`
records an independent rehash of copied and raw inputs and checks every
completed batch reference against the raw inventory. `package-manifest.json`
seals this package's files except itself and its detached checksum. No source,
plan, task registration, Stop control, or unrelated process was changed.
