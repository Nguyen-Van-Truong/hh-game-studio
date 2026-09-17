# S73 launch 2 failure preserved for S75 recovery

This package preserves a failed attempt. It is not a benchmark PASS, critic
verdict, or GT-06 acceptance. The preservation worker did not launch an
engine/test, control a process, delete a task, edit source/plan, or commit.

Observed on 2026-09-18 at 05:20:49 Asia/Saigon (2026-09-17 22:20:49 UTC).
HEAD at collection: `1dda560c2eb46739cbe5aff69293ec1c6056be6c`.
Source checkpoint: `cb4d1f6f633e6824a30a45873f05024c3bf7cd58`.
Frozen campaign closure:
`6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`.

## Recorded failure and limits

Campaign `gt06-s73-campaign-01`, launch 2, failed in
`gt06-s73-campaign-01.r00.a02`. The child reports
`CAMPAIGN_RETAINED_COUNTER_GROWTH`, zero-based batch 9, phase
`joint_observation`, `completed_batches=10`, and `partial_command=null`.
The original 222-byte child record, parent failure, all ten
joint/capture/sample-preview records, and owner logs are exact copies.

Ten captured batches mean five warmups and five measured sample artifacts.
Measured batches 5–8 pass the frozen prefix screen; batch 9 fails it. The
runner writes capture/sample artifacts before screening. These counts are
not ten accepted batches, five accepted measured samples, a completed
35-batch run, or a ten-run dataset. No partial attempt may be joined to a
different process pair to claim a full run.

| Counter | Warmup baseline, batch 4 | Batch 9 |
|---|---:|---:|
| Host RSS bytes | 30,543,872 | 9,490,432 |
| Editor RSS bytes | 258,248,704 | 119,283,712 |
| Host handles | 194 | 194 |
| Editor handles | 566 | 568 |
| Editor objects | 71,175 | 71,213 |
| Editor resources | 6 | 6 |
| Maximum status gap, ms | 682.691 | 748.668 |

The frozen assembler creates editor counters in RSS, handles, objects,
resources order. The runner screens that in-memory order. Handles +2 is the
first failing comparison. Objects +38 is an additional observed exceedance
that would also fail the unchanged retained-counter limit, but no second
exception was emitted. Sorted JSON keys do not preserve the in-memory
screening order; the two relevant frozen Python sources are copied here.
This identifies the failing comparisons, not the cause of the growth or
whether it represents a leak.

Neither RSS counter exceeds its unchanged baseline plus 10% at batch 9.
The measured status gaps are below 2,000 ms. Warmup batch 3 records
2,004.0029 ms; the frozen screen applies that threshold only to measured
batches. The warmup observation is retained and is not a separately emitted
failure. `completeness-and-screen.json` contains all ten counter rows.

## Exits and owned resources

- Host target PID 27508 has a real `process-exit.json` with exit 1, matching
  its start receipt and the fixed host identity in all ten samples. Host
  cleanup separately reports wrapper exit 1.
- Editor target PID 8776 has its start receipt and fixed sample identity,
  but no native exit receipt. Editor cleanup reports wrapper exit 2 and
  `BENCHMARK_CLOSED_BEFORE_FINISH`. **Wrapper exit 2 is not a proven Godot
  target exit code.** Empty native stderr and later process absence do not
  supply the missing code.
- Both owner cleanup records show Job active count 0, zero observed,
  ownership closed, no retained Job handle, taint, failed operation, native
  error, create uncertainty, or close uncertainty. Both wrapper-process
  handles are closed without retention or uncertainty. Parent failure
  reports owner closed, owned tree zero, and no cleanup error. These are
  verified terminal ownership receipts, not a new live inspection of already
  closed Job handles.
- Import target PID 35564 has its own native exit 0 receipt and matching
  import capture, wrapper exit 0, natural tree exit, and Job zero/closed.
  The import capture has no wrapper-process-handle object; the two later
  owner receipts are the source of the explicit wrapper-handle claims.
- Parent/supervisor report `BENCHMARK_WRAPPER_EXIT`. Supervisor return reports
  exit 1 after 2,133.782 seconds and explicitly says its actual process exit
  was not yet observed. Fresh read-only task status shows state 3, result 1,
  and no instances for `\HHStudio.GT06.gt06-s73-campaign-01-launch-02`.
  Scheduler result is distinct from host/native exit and Job receipts.
  A process-name snapshot found no Godot/Blender processes or the three
  recorded target PIDs among the observed Python/Godot/Blender processes.

## Completeness and Stop

Native ready-10 exists. Start-10, ACK-10, native batches 10–34, final native
index, child result, run assembly/capture, campaign capture, dataset, and
summary are absent. No complete run exists.

All 30 fixed attempt slots were checked with `os.path.lexists`; every Stop
latch is absent. Only run-00-attempt-01 and run-00-attempt-02 exist. No Stop
was created, cleared, or bypassed. Benchmark Stop/cancel operations inside
a sample are distinct from the operator Stop latch. Structural cleanup does
not establish that the counter failure is repaired or authorize a blind retry.

## Preservation and verification

`raw/` contains **77 exact copies, 1,902,821 bytes**. The selected set contains
campaign and attempt bindings, all owner top-level receipts/logs, every
launch-2 supervisor top-level file, ten joint/capture/sample-preview sets,
final batch boundary artifacts, and the two frozen sources needed to
interpret screening. `preserved-byte-manifest.json` binds every copy to its
original locator, size, and SHA-256.

`raw-locator-hashmaps.json` inventories **447 files, 60,708,808 bytes**:

- Campaign root: 435 files, 60,700,371 bytes, including prior attempt 1.
- Launch-2 supervisor root: 12 files, 8,437 bytes.

The exact roots are `studio/.local/reviews/gt06-s73-campaign-01` and its
sibling `gt06-s73-campaign-01-supervisor-launch-02`. Full journals, command
data, other native batch data, unselected frozen source, and caches remain
at raw locators. An inventory is not a portable copy of those bytes.

`source-map-verification.json` binds all 49 files against campaign and
attempt frozen copies and byte hashes read from Git checkpoint `cb4d1f6f`.
Both frozen maps and the context map agree, and closure is independently
recomputed. All 49 live files matched at collection time. Later source
changes cannot inherit this attempt's evidence.

`observations/` records exact read-only observer stdout/stderr, commands,
timestamps, and actual observer exits. `preserve.py` collected the package
with exclusive writes; it performed no engine/test launch. `verification.json`
records a second hash pass over all 447 raw files, 77 exact copies, and all
60 references in ten batch captures. `verify.py` independently rechecks
bytes, source identities, receipt boundaries, sample identities, and Stop
slots before writing `verification-independent.json` and the package seal.

`package-manifest.json` seals every package file except itself and its
detached SHA-256 file. Verification PASS means preservation/static consistency
only; missing native exit and incomplete workload remain acceptance gaps.
