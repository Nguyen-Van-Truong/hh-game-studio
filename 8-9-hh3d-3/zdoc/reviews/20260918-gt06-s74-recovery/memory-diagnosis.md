S74 memory diagnosis — 2026-09-18, read-only production review

The S73 run failed the unchanged RSS gate correctly. The available observations
do not establish a host memory leak, a sampler defect, or the cause of the
large working-set reductions. They also reveal a separate measured-batch
status-gap failure. Changing the RSS metric, warmup baseline, threshold, or
workload to obtain a pass would not repair this result.

Scope: `studio/.local/reviews/gt06-s73-campaign-01/run-00-attempt-01`;
`joint-00.json` through `joint-05.json`, `command-00.json` through
`command-05.json`, and native `project/benchmark/out/batch-04.json` and
`batch-05.json`. Relevant sampler, producer, assembly, profile, campaign and
derived journal-index source was read. No raw-tree sweep or hash scan was
performed. This worker launched no test, engine or benchmark, made
no source/plan/setting/process-control change, and wrote only this report.
The coordinator supplied the terminal campaign outcome
`FAILED / CAMPAIGN_RSS_GROWTH`, duration 1131.563 seconds. This report is not a
critic verdict or acceptance evidence.

**Observed memory.** All six joint artifacts identify the same host PID 38244
with start identity `windows:134341530873608923` and editor PID 2984 with start
identity `windows:134341530936030303`.

| Batch | Host RSS bytes | Editor RSS bytes | Host handles | Editor handles | Editor objects |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0, warmup | 36,495,360 | 753,053,696 | 194 | 565 | 71,135 |
| 1, warmup | 38,830,080 | 753,352,704 | 194 | 557 | 71,135 |
| 2, warmup | 38,952,960 | 753,618,944 | 194 | 558 | 71,159 |
| 3, warmup | 36,208,640 | 616,329,216 | 194 | 561 | 71,161 |
| 4, fixed baseline | 18,939,904 | 359,473,152 | 194 | 555 | 71,161 |
| 5, first measured | 23,056,384 | 93,556,736 | 194 | 555 | 71,161 |

Editor resources remained 6. Batch 5 host RSS increased by 4,116,480 bytes,
or about 21.73%, from the required batch-4 baseline. The 10% upper bound is
20,833,894.4 bytes, so the observation exceeds it by about 2.12 MiB. Batch 5
host RSS is nevertheless about 36.82% below its batch-0 observation. The
editor's batch-5 working set is about 73.97% below batch 4 while its object,
resource and handle counters remain unchanged. Neither direction by itself
proves allocation ownership, retained heap growth or successful freeing.

Command-phase observations locate additional changes within the same process:

| Batch | Host RSS before commands | Host RSS after commands | Host RSS at later joint sample |
| --- | ---: | ---: | ---: |
| 4 | 37,130,240 | 35,909,632 | 18,939,904 |
| 5 | 19,451,904 | 18,137,088 | 23,056,384 |

The required baseline was sampled after the host became substantially less
resident during batch 4's native interval. During batch 5, the host command
phase ended below that baseline, then its later joint sample rose above it.
This is not a simple monotonically increasing sequence. The RSS comparisons
are phase-specific; command-before/after values cannot replace the prescribed
joint samples.

**Sampler and gate review.** No static implementation error was found in the
inspected path:

- `ProcessProbe.Memory` lays out `PROCESS_MEMORY_COUNTERS` with two DWORDs
  followed by native-width SIZE_T fields. `working_set` follows
  `peak_working_set`; the sampler returns `int(memory.working_set)`, not the
  peak, pagefile/commit field, a truncated 32-bit number or a fabricated zero.
  It initializes `cb` from the structure size and checks the BOOL result of
  `GetProcessMemoryInfo`.
- The probe retains an opened process handle and binds PID, creation time and
  executable. Sampling checks that handle remains live. The artifacts retain
  consistent process identities. This rules out an obvious PID-reuse mix-up
  in the inspected evidence; it is not a new native ABI test.
- `NativeObserver` samples the actual Python host PID. `sample_editor` uses
  the retained editor probe. `assemble_sample` takes RSS from the joint
  host/editor observations; it does not substitute command-phase memory or
  engine object counts for RSS.
- The campaign takes `baseline_memory` from batch 4 exactly. Beginning with
  batch 5, `screen_sample` uses integer comparison
  `value * 100 <= baseline * 110`. The complete profile uses the same 10%
  rule. Neither path accidentally uses batch 0, a peak, rolling baseline,
  rounded percentages or a selected lower sample.
- Native quiescence is required before joint sampling. Host report objects
  are written and released before native execution; native report parsing
  occurs before the joint host sample. The same observation phase is applied
  to every batch. That instrumentation has real memory costs, but this review
  found no evidence that a changed sampling phase manufactured batch 5's
  delta. The probe timestamp is obtained after window enumeration, so it is
  a close observation timestamp, not an atomic snapshot of every counter.

The RSS source is the process working-set field. These artifacts do not
include private committed bytes, allocation/heap snapshots, page-fault deltas,
working-set residency events, or the identity of any actor requesting memory
trimming. A fall in working set followed by residency recovery is compatible
with these values; so are changes in live allocations and allocator behavior.
The data do not identify which occurred. Stable handles and editor object
counts do not measure the Python heap or every native allocation. Conversely,
RSS recovery above an unusually low baseline does not by itself demonstrate
a leak. Root's separate workstation inspection and Windows-source research
must establish any external cause before it is named as the cause here.

The journal intentionally retains exact command-key and offset indexes while
receipts remain on disk. Those indexes grow with accepted history; that is
real retained state, not automatically a leak. No allocation trace in this
package attributes the 4.12 MB joint RSS increase to those indexes, to
temporary reports, or to leaked objects. Dropping dedupe entries, receipts or
tombstones would violate the contract and is not a remedy.

**Independent failure hidden by first-error reporting.**
`command-05.json.max_status_gap_ms` is 2010.742, exceeding the fixed 2000 ms
limit. The native batch-5 value is 735.018 ms and its start-permit value is
700.373 ms. Assembly takes the maximum including the host value. The campaign
checks memory before checking status gap, so RSS was the first reported error;
removing that error alone would not make this measured prefix conformant.

Batch-5 command time was 341.782 seconds versus 57.274 seconds at batch 4,
about 5.97 times longer. The journal grew only from 4,916,197 to 5,902,542 bytes,
about 20.06%. Native time remained close, 133.910 versus 131.759 seconds. This
large additional host slowdown is not quantitatively explained by history-size
growth alone. It does not establish paging, external interference, fsync stalls
or a particular scheduling cause without corresponding telemetry.

**Minimal maintainable recovery consistent with the fixed gate.** There is no
evidenced sampler or RSS-calculation fix to apply from this package. Keep
`ProcessProbe`, exact RSS, batch-4 baseline, five warmups plus thirty measured
batches, ten fresh process runs, identity continuity and all limits unchanged.
Preserve the failed S73 package as failed; do not splice its prefix into a new
run.

The smallest justified next step is operational diagnosis and isolation before
a fresh campaign: correlate the observed timeline with the coordinator's
independently identified system activity. If an external trimming/maintenance
job or competing workload is actually demonstrated, arrange the fresh run so
that activity does not interfere, within existing authorization. This report
does not authorize killing unrelated processes or changing global settings.
If no external cause is demonstrated, treat the cause as unresolved and obtain
allocation/residency evidence before changing product memory ownership.

For diagnosis, supplemental time-aligned private-commit and page-fault
observations can help distinguish new committed allocation from a working-set
change; the current sampler structure already receives a page-fault field,
but does not preserve it. Such telemetry should be a separate diagnostic
artifact and must not replace, subtract from or become an exception to the
required RSS measurements. This is a proposed diagnostic addition, not evidence
already collected. A leak finding would require a retained-allocation trend
and ownership attribution across repeated work, followed by an actual release
or bounded-storage fix and fresh unchanged acceptance runs.

Do not raise or select a different baseline, add warmups, preload/touch dummy
memory, pin or repeatedly touch pages solely to hold RSS up, replace current
RSS with peak/private-commit values, truncate history, force a pre-sample trim,
subtract instrumentation memory, or relax the 10%/2000 ms limits. A later run
must satisfy the existing gate with its actual observations; the present
failure cannot be converted into a pass by explaining a possible cause.
