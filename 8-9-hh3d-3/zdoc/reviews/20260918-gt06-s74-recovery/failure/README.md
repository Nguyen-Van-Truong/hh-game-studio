# S73 campaign failure preserved for S74 recovery

This package preserves a failed attempt. It is not a benchmark PASS, critic
verdict, or GT-06 acceptance. No engine, test, process control, task deletion,
source edit, plan edit, or commit was performed by the preservation worker.

Observed on 2026-09-18 at 04:33:55 Asia/Saigon (2026-09-17 21:33:55 UTC).
HEAD: `115297d3bd9decf1ad79c5fd0332c771fa014e8c`.
Coordinator-designated source checkpoint: `cb4d1f6f633e6824a30a45873f05024c3bf7cd58`.
Frozen campaign closure:
`6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`.

## Recorded failure

Campaign `gt06-s73-campaign-01`, launch 1, attempted only
`gt06-s73-campaign-01.r00.a01`. The child reports `CAMPAIGN_RSS_GROWTH`
at zero-based batch 5, phase `joint_observation`, `completed_batches=6`,
and `partial_command=null`. The exact 208-byte child failure, parent failure,
all six joint/capture/sample-preview records, and original logs are preserved.

The six captured batches are five warmups and one measured batch whose
screening failed. They are not six accepted batches or one accepted measured
sample. The frozen runner writes the batch/sample artifacts before screening,
which explains the child counter. It did not complete a 35-batch run or a
ten-run dataset.

| Sample counter | Warmup baseline, batch 4 | Batch 5 |
|---|---:|---:|
| Host RSS bytes | 18,939,904 | 23,056,384 |
| Editor RSS bytes | 359,473,152 | 93,556,736 |
| Host handles | 194 | 194 |
| Editor handles | 555 | 555 |
| Editor objects | 71,161 | 71,161 |
| Editor resources | 6 | 6 |
| Maximum status gap, ms | 1,142.063 | 2,010.742 |

The host RSS increased by 4,116,480 bytes, about 21.73%, exceeding the
unchanged 10% limit. The frozen `screen_sample` checks host counters first;
host RSS explains the recorded primary failure. Batch 5 also records a
2,010.742 ms status gap above 2,000 ms, but the RSS exception occurred before
that subsequent check. This additional observed limit exceedance is not a
second emitted failure. These facts identify the failing comparison, not the
cause of memory or timing variation. Root-cause work belongs to the coordinator.

## Exit and ownership boundaries

- Host target PID 38244 has an actual `process-exit.json` with exit 1.
  Host-owner cleanup separately records wrapper exit 1.
- Editor target PID 2984 has a start receipt but no native exit receipt.
  Editor cleanup records wrapper exit 2 and `BENCHMARK_CLOSED_BEFORE_FINISH`.
  **Wrapper exit 2 is not a proven Godot target exit code.** Empty editor
  stderr and process disappearance cannot supply the missing code.
- Both owner cleanup receipts record Job active count zero, observed zero,
  closed ownership, no taint, native error, failed operation, uncertainty,
  or retained Job handle. Both wrapper-process handles are closed without
  retained handles or close uncertainty. Parent failure records owner closed,
  owned tree zero, and no cleanup error.
- Import target PID 44056 exited 0 with its own successful import capture,
  wrapper exit 0, and Job zero. This is separate from the later editor failure.
- Parent and supervisor failures report `BENCHMARK_WRAPPER_EXIT`. Supervisor
  return says exit 1 after 1131.563 seconds and explicitly marks its actual
  exit as not yet observed. The fresh read-only launcher status establishes
  scheduler state 3, result 1, and no instances. It is not a substitute for
  target exit or Job receipts. The process-name snapshot observed no Godot
  or Blender process.

## Completion, Stop, and recovery limits

Native ready-06 exists, but start-06, ACK-06, native batches 06–34, final native
index, child result, run assembly/capture, campaign capture, dataset, and
summary are absent. `completeness-and-screen.json` records these bounded
checks. No completed run can be reused, and these partial samples must not
be combined with another process pair to claim a full run.

All 30 fixed attempt slots were checked with `os.path.lexists` for Stop
requests. Every Stop latch is absent, and only run-00-attempt-01 exists.
No Stop was created, cleared, or bypassed. Benchmark Stop/cancel operations
inside a sample are distinct from an operator Stop latch.

Prior cleanup and terminal scheduler evidence satisfy the structural cleanup
preconditions for a fresh attempt 2 under unchanged campaign bindings. This
does not show that either observed limit exceedance is repaired. A source
change requires a new campaign/closure; the S73 records retain their original
source identity. Missing native exit and incomplete data prevent acceptance
of this attempt, despite verified process-tree cleanup.

## Preservation scope and verification

`raw/` contains 64 exact copies, 1,130,974 bytes: key campaign/attempt metadata,
source maps, every top-level owner receipt and log, all supervisor receipts
and task definitions, all six joint/capture/sample-preview records, final
batch boundaries, and the frozen runner used to interpret screening order.
`preserved-byte-manifest.json` binds copies to original locators and hashes.

`raw-locator-hashmaps.json` inventories all 239 files, 25,861,512 bytes,
under exactly these roots, including caches, without copying the full trees:

- `studio/.local/reviews/gt06-s73-campaign-01`
- `studio/.local/reviews/gt06-s73-campaign-01-supervisor`

The journal, bulk command/native data, remaining frozen source files, and
caches stay in their raw locations. Hash inventories are not portable copies
of those bytes. `source-map-verification.json` confirms both frozen copies
of all 49 source files and agreement of campaign/context/attempt maps. All
49 live files also matched at collection time; later edits do not inherit
S73's evidence.

`observations/` retains exact stdout/stderr, observer exit codes, timestamps,
and commands for read-only Git, scheduler, and process observations.
`preserve.py` documents collection and writes only this failure directory.
`verification.json` records a second rehash of all raw inputs and copies,
all 36 completed batch references, and the recomputed frozen source closure.
`package-manifest.json` seals this package except itself and its detached
checksum. Verification PASS means byte preservation only, not runtime success.
