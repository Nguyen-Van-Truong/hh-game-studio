# S71 Output capacity comparison — existing native evidence

Both existing native diagnostics completed **3 batches x50 cycles =150 cycles
per arm**, with actual native target and helper exits0, natural empty-tree
exit, closed untainted Jobs and released wrapper process handles. Offline
verification of the captured records and all300 cycle rows passed. No engine,
diagnostic collector, test suite or task was started for this collection.

This is **supplemental native diagnostic evidence only**. It is not the
10x35x100 benchmark, host/API performance, OS RSS/handle measurement, complete
dependency-closure acceptance, or GT06 acceptance.

| Project-local Output cap | Batch0 objects | Batch1 objects | Batch2 objects | Resources in all batches | Native PID / actual exit | Owner elapsed |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| 10,000 | 71,110 | 71,182 | 71,254 | 6 / 6 / 6 | 6052 / 0 | 38.609s |
| 100 | 71,109 | 71,131 | 71,131 | 6 / 6 / 6 | 23420 / 0 | 38.359s |

The10,000-line arm grew+72 objects between each observed batch; the100-line
arm grew+22 then0. This is consistent with bounding the editor Output display
removing that late diagnostic growth. Three short native batches do not prove
that later full-workload samples, host counters or RSS will pass. Both runs
explicitly leave native RSS and OS-held-handle sample values unavailable.
Released owner handles at termination are separately verified cleanup facts.

## Preserved and independently checked

`inventory.json` binds **148 copied files / 1,455,163 bytes** by original path,
size and SHA256. Copies used exclusive writes, byte readback and rehashing of
the originals. Complete import/editor stdout and stderr, actual process-start/
process-exit files, captures, invocations, cleanup, native index and all six
batch shards are retained. Both lanes' stderr are empty; full stdout files
contain no checked WARNING/ERROR/leak/failure markers. Nothing was truncated
or substituted with a tail. `.gitattributes` preserves exact copied bytes.

`comparison.json` records the offline results. Checks include:

- Each captured Output-cap readback marker equals its project override10000
  or100. Native limits remain the recorded owner profile.
- Exact owner capture/artifact/invocation hashes, expected engine binary hash,
  actual target/helper exits0, natural-tree exit, active_before_cleanup0,
  Jobclosed/zero/untainted/unretained and wrapper-handle closed/unretained.
- Import actual exits0 (PID17216 for cap10000; PID36464 for cap100), clean
  captured streams and matching source/binary invocation bindings.
- Three native batch references match their size/hash, index, run ID and PID;
  native completion stdout binds the exact index bytes. Index scope remains
  diagnostic, `host_integrated=false`, `benchmark_complete=false`.
- Every cycle has create/undo/save/reload effect count1, positive correctly
  derived timings, bounded ordered clocks, save-signal and reload-frame proof,
  changed root identity with cross-cycle continuity, and generation1→151.
  Created semantic hashes differ; undo/reload recover the baseline; saved-file
  hashes match the final scene. Each batch has50 cycles and zero dropped
  commands/telemetry, with the recorded quiescent frame/time boundaries.
- Native index source hashes agree with the recorded initial project map and
  post-run immutable project bytes. Nine native source paths are checked in
  that before/after binding; the intentionally mutable scene is checked by
  per-cycle saved hashes instead.

Both arms have the same38-file base source map and closure
`6f7940c4dec1387eaf4a3ca6b3d1e1152fb81fc2bf6ca1b1d03635f13a5c2aef`.
Each owner has a52-file map including its exact diagnostic project copies.
`cap-*/verification-source/studio/` reconstructs that namespace from the
arm's frozen `source/studio` and recorded project files. Verification never
compares those old maps with changed live production source. Initial bindings,
runtime maps and current copied-project hashes agree for immutable files.

**Dependency limitation:** the diagnostic base maps omitted the non-Python
`contracts/perf-collector.schema.json`. That omission remains explicit and is
not repaired by fetching today's bytes. The whole frozen native driver import
would read that absent dependency, so `collect_verify.py` selects only its
exact hash-bound pure validation definitions by AST, plus the frozen profile
definitions and complete frozen owner verifier. These selected definitions do
not read the perf schema or launch processes. The initial import attempt failed
on the missing schema before validation; it launched no engine and changed no
original evidence. The successful offline verification uses no live schema.
This therefore cannot claim complete diagnostic dependency provenance. The
coordinator's separate full-campaign49-file closure includes that schema and
must be assessed on its own evidence.

## First collector error is retained

The first arm's original `failure.json` remains
`KeyError("batch_index")`. Its preserved v1 collector reached the report
comprehension after `owner.finish()`, owner verification, log checks and native
batch reads. Native batch records name the field `index`. The original first
arm still has no `result.json`; it was not created retrospectively.

`cap-10000/recovered-result.json` is a **new, labeled read-only reconstruction**
using the existing native `index` fields and independently checked artifacts.
It retains the original collector-failure flag and does not convert the
collector invocation to exit0. Native success and collector failure coexist.
The second arm's original result was compared with the reconstructed values
and matches. Its v2 collector fixed that field and used an explicit single-arm
CLI; neither preserved collector was executed during this work.

| Record | SHA256 |
| --- | --- |
| v1 collector, cap10000 | `8feeefcadf612d2302d94bb343a0e4c2f5665fbbcdc9661c7ce370741c0f6407` |
| v2 collector, cap100 | `f4ad52c2d14d1b8d25612d01340adfa646919c53fd18c28210565ab681f4da38` |
| cap10000 owner capture | `4122fff36efea530390766cdfba0ba253428441bba204c190e5c9a0ad769be6b` |
| cap100 owner capture | `1c014a00c4b23f6fc948e9e29eaf76ca9a51b02eeb8800aadab3d4ac695e1b04` |
| cap10000 native index | `e319ce5a1f341fbd26c706ab8ff3462f534a38ee2330cff5df2d26962a9b9085` |
| cap100 native index | `cd79c8f42cb9842e35c0a15521a45bb4cb76cdeca61eae1d5dd18ffddb5c4f92` |
| comparison.json | `70b8c7f92d9bf3bf8aba1e736912028d62e2901aed647e760adb9a11e2c95b2d` |
| inventory.json | `212cf805c09d1953a431c9a7d447645949b92c31598fe547c9e04bf2b29241e1` |
| collect_verify.py | `cda365f69b4338985cacb2609316b245349cd95183a44400f03c5fdef0cd585e` |

The original roots remain unchanged:
`studio/.local/reviews/gt06-s71-output-cap-10000-01/` and
`studio/.local/reviews/gt06-s71-output-cap-100-01/`.
No engine rerun, source fix, task action, staging or commit belongs to this
collection. Integration and subsequent full-workload verification remain with
the coordinator.
