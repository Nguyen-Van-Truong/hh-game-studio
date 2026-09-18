# S84: isolate census cost before another full-sequence diagnostic

AUTHORITY=0. DESIGN_ONLY=1. FORMAL_ACCEPTANCE=false. Read-only investigation,
2026-09-18, of terminal `gt06-s82-attribution-01`. Only this document was written.
No engine, test, runtime/helper/raw edit, process control or commit was performed.
Paths below are relative to `8-9-hh3d-3/`.

**Recommendation:** first run a short, explicitly ineligible probe-cost
experiment with a sham window, the executed census, and release of only the
probe's retained graph. Then compare a compact ID-only census in a fresh editor.
Do not immediately retry 35 batches. Existing evidence shows a concrete probe
allocation mechanism and an incorrectly comparable before/after RSS boundary;
it does not yet prove how many bytes of the 117.16 MiB increase came from it.
The original S81 +2 ObjectDB failure and the separate S82 host-response delay
remain unresolved.

## Executed identity and raw observations

Base checkpoint remains `b3862a10`, 51 files,
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.
Profile remains
`0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
The raw run root, abbreviated `R` below, is
`studio/.local/reviews/gt06-s82-attribution-01/`.

The following three small executed files were read and hashed in this review;
this was not a full source/raw-package rehash:

| Executed path below R | SHA256 |
| --- | --- |
| `source/zdoc/reviews/20260918-gt06-s82-attribution/diagnose_sequence.py` | `bb9f288a3df30dce8f3442896a94e8fb31505bd7a6e8e0ef769a9ea24037e095` |
| `source/zdoc/reviews/20260918-gt06-s82-attribution/object_probe.gd` | `6221092c70591d89b42aa8c00298198299a716edc7c25b8b4813db5d771fe556` |
| `project/addons/hh_benchmark/benchmark_native.gd` | `a24e69f0e3275cc37c5e57e7ba9279f4bdda2553fbf1d1e155bc86575e6f5b00` |

Both executed helper copies also match the live helper bytes read here exactly.

`R/native-overlay.json` binds the effective plugin to base native file
`52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2` and
explicitly excludes the diagnostic from a campaign dataset. Import parsing
success did not exercise the later collection cost.

| Batch | Editor working set / RSS bytes | ObjectDB | Native ACK maximum gap ms |
| --- | ---: | ---: | ---: |
| 0 | 757010432 | 71128 | 677.655 |
| 1 | 757055488 | 71128 | 574.592 |
| 2 | 757530624 | 71128 | 585.052 |
| 3 | 758038528 | 71128 | 610.961 |
| 4 | 758169600 | 71128 | 1046.246 |
| 5 | 881020928 | 71128 | 605.229 |

These values are from `R/joint-00.json` through `joint-05.json`. RSS rises
122851328 bytes, **117.16015625 MiB / 16.20367369%**, from the batch4 baseline
to batch5. This is the measured delta, not an estimate of census allocations.
Resources stay6. `R/child-failure.json` records `CAMPAIGN_RSS_GROWTH`, six
completed captures, phase `joint_observation`, batch5. `screen_sample` checks
memory before status, explaining why RSS is the terminal error even though
the status sample also exceeds its limit.

Only `R/project/benchmark/out/object-0000.json` exists for the census observed
here. It is842623 bytes and records:

- baseline batch4, cycle100, frame47440, native time406668395us;
- 27401 reachable identities, including4493 TreeItems and1778 Timers;
- 43727 ObjectDB entries outside this partial inventory;
- collection820390us, unchanged before/after counters71128 objects,
  21482 tree nodes,313 orphans,6 cached resources; filesystem scan false;
- initial ID/class map27401 entries,146 detailed added Tree/RichTextLabel
  descriptors, zero changed/removed rows.

`R/project/benchmark/out/attribution-04.json` records ObjectDB71128 before and
after publication. It verifies only that particular ObjectDB counter; it is
not an allocation/RSS-neutrality test.

## Proven ordering: OS baseline precedes expensive census

The executed `R/source/studio/tests/replay/run_benchmark_campaign.py`, around
lines834–875, first samples host and editor OS counters, publishes the ACK,
waits for its native receipt, constructs the sample, screens it, then saves
batch4 `sample['memory']` as the warm baseline. The copied plugin's
`_wait_host_ack`, lines877–900, validates the ACK and scene, then runs
`_attribution_ack()` **before** fresh native counters and the ACK print.

Consequently batch4's sample combines **pre-census OS RSS** with
**post-census native ObjectDB**. Batch5's OS RSS includes the retained census
graph. This ordering is demonstrated by code and receipts, without assuming
the census caused the entire later rise:

- host RSS read:623101738282us; ACK written:623101793576us;
- native census starts406668395us and collects for820390us;
- native ACK observed407606716us; host wait ends623102755824us.

Host and native monotonic origins differ. Compare intervals within each clock;
do not subtract a native timestamp directly from a host timestamp. Native
census start→ACK is938321us, of which117931us follows the recorded collection
duration. That residual includes aggregation/serialization/publication and
remaining ACK work; it is **not** a measured serialization-only duration.
The first census's `previous_snapshot_write_us=0` supplies no current write
duration; there was no later census exposing that field.

## The 2044ms violation is a separate host-response observation

`R/command-05.json` declares
`status_gap_scope="host command-lane response progress; not editor UI heartbeat"`.
Its maximum gap2044.2252ms is the first interval in `host_response_mono_us`:
batch start623102920435→first inspect receipt623104964661, or2044.226ms from
the rounded integer timestamps. The first submit starts623103633248, giving
approximately712.813ms before submit and1331.4124ms submit receipt latency.
The earlier interval includes `_connect_batch()` and initial `_observe()`;
the raw rows do not split their individual costs.

The native batch5 maximum and ACK maximum are605.229ms. The assembled sample
takes the maximum of command, ACK and start-permit gaps. The census had
finished before batch5 began. Memory/page-pressure effects on that later host
work are a hypothesis, not a demonstrated causal explanation. Keep this
status breach even if a corrected probe later reduces RSS. Do not subtract
census time from the command metric or relabel it as native UI blocking.

## Allocation mechanism and what remains uncertain

The executed probe builds a string-keyed dictionary containing one descriptor
dictionary per reachable object. Nodes add names, paths, parent IDs and other
strings. TreeItems add column arrays, text dictionaries, bounded text and
digests. Incoming-signal lists and child arrays also create temporary
containers. `_object_probe_previous = rows` retains the entire descriptor
graph across subsequent batches so that fields can be compared.

The separate27401-entry `initial_id_classes` map is temporary: it is reachable
through local `point` until serialization/function return, not a second global
map intentionally retained afterward. JSON/string/UTF-8 buffers and the
aggregation maps also contribute temporary allocation. The retained graph and
temporary allocation/page-residency effects must be measured separately.

Godot dictionaries are reference-shared. The pinned engine source implements
their private storage as a refcount plus a Variant hash map, allocated by
`memnew`; it is not an Object-derived instance for each dictionary. Thus
stable ObjectDB does not establish stable container/string heap use.
[Dictionary documentation](https://docs.godotengine.org/en/stable/classes/class_dictionary.html)
and [pinned dictionary.cpp](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/variant/dictionary.cpp).

The existing `ProcessProbe.sample()` reports Windows `WorkingSetSize`, the
resident pageable pages of the process. `PrivateUsage`/commit is a different
quantity. Releasing the dictionary graph must not be interpreted as a promise
that the working set immediately returns to its earlier value; the metrics
answer different questions. Record both as diagnostic observations while
retaining RSS as the actual gate metric. Do not trim the process working set.
[Windows working set](https://learn.microsoft.com/en-us/windows/win32/memory/working-set)
and [PROCESS_MEMORY_COUNTERS_EX](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex).

Optional Godot `Performance.MEMORY_STATIC` is useful for the allocation
intervention only if supported by this exact editor build. The documentation
says it is unavailable in release builds; zero must be labeled unavailable
when support cannot be established. It cannot replace OS RSS or recover an
absent allocation trace. [Performance monitors](https://docs.godotengine.org/en/stable/classes/class_performance.html).

This establishes a credible, explicit instrumentation mechanism. It does not
yet prove that all117.16MiB is live descriptors, that allocator retention is
the residual, or that the probe caused the separate host-response delay.

## Cheapest discriminating experiment

Use a **new disposable copied project and fresh owned process**, frozen base
and helper/overlay hashes, `eligible_for_dataset=false`. Do not modify the
executed S82 helper or raw files. Give the short diagnostic its own bounded
watchdog and explicit stop reason; this is not a shortened successful campaign.
No full35-batch run is needed to measure one census's cost.

1. **Establish a comparable editor state cheaply.** Use the existing startup/
   readiness sequence, then one real native100-cycle batch and its unchanged
   settle. Record scalar counters first; obtain reachable cardinality from
   the intervention itself, never pre-run the full census to establish it.
   If that editor state is materially unlike the S82 baseline, use five native-only batches
   to reach the500-cycle point. Do not spend five1000-command HTTP batches
   merely to measure census allocation. This microprobe does not test the
   original HTTP/native interaction failure.
2. **Bracket a sham, then one exact executed census.** A diagnostic phase
   pauses further native workload while editor frames continue; all Stop/
   deadline/ownership controls remain active. The observer uses a retained,
   identity-checked process handle and samples working set/commit/page-fault
   counters at a fixed modest cadence, for example100ms in a bounded window.
   Native markers delimit a small no-op function with the same marker I/O,
   then an invocation of the unchanged census body. Observe several seconds
   before and after each; do not clear editor logs/trees, run HTTP, change
   priority, force collection or trim memory. Capture helper/native start/end
   times and thread/heartbeat gaps without merging clock origins.
3. **Separate retained from transient allocations.** After the full-census
   function returns and the first post window is captured, a new main-thread
   diagnostic callback releases only `_object_probe_previous` and any probe
   locals/caches. The no-op and release callbacks have their own markers.
   Sample again after return,1s,5s and15s. Record retained descriptor count,
   static-memory observation when available, RSS/commit and ObjectDB. Do not
   free any editor/game objects. The existing full census should not run a
   second time unless the first result is ambiguous.
4. **Fresh compact arm.** Launch a second fresh owned editor with the same
   initialization and sham windows, but the compact census below. Do not run
   it after the legacy census in the same editor: allocator/working-set
   carryover would contaminate its incremental cost. Preserve actual exits,
   Job/handle cleanup and original raw measurements for both arms.

The intervention contrast is
`(post-census − pre-census) − (post-sham − pre-sham)` for each diagnostic
metric, plus the separate post-release observation. These are explanatory
differences, not corrected benchmark samples. Report distributions/ranges and
raw timestamps, not one favorable RSS point. If the legacy census introduces
a large immediate step absent in the sham, the mechanism is reproduced without
another long campaign. If supported static allocation falls after releasing
the probe graph while RSS remains elevated, that distinguishes live-reference
release from resident-memory behavior; it does not identify a particular heap
implementation. If control drift or effects are ambiguous, repeat the short
arms in reversed order; do not claim causality from one noisy long prefix.

A separate tiny copy of the recorded host batch5 history can subsequently
bracket connect/initial-observe/first submit if the host2s gap still needs
diagnosis. Do not add that workload concurrently to the census-cost experiment.
The present data already localizes its interval, but does not identify its
I/O/scheduling cause.

## Minimal diagnostic-only collector correction

The required distinction for the original failure is **new/removed IDs**, not
every string field of every unchanged editor object. Replace the retained
full-row baseline with compact numeric identities:

- Traverse the same reachable categories: scene nodes including internal
  children, TreeItems, incoming-signal source objects, orphans and processed
  tweens. Collect numeric instance IDs in `PackedInt64Array`; sort and dedupe
  numeric IDs. Do not construct per-object descriptors, stringified IDs,
  paths, cell text/digests or a27401-entry JSON ID/class map at baseline.
  Avoid retaining objects or connection arrays. Child-index iteration can
  avoid allocating a child array at each node; incoming-connection APIs still
  have temporary cost, which the short experiment must include.
- Retain only the packed baseline IDs and small scalar/class summaries needed
  for interpretation.27401 IDs contain219208 raw bytes before array/header/
  temporary costs, not117MiB; this is a payload-size calculation, not an RSS
  prediction. Packed arrays use less memory than ordinary arrays according
  to [Godot's packed-array documentation](https://docs.godotengine.org/en/stable/classes/class_packedint64array.html).
- If baseline ID/class provenance is necessary, stream compact numeric
  records to the diagnostic file with a small versioned class table, or write
  the packed bytes plus declared encoding and counts. Do not rebuild the old
  large Dictionary solely to serialize it. Publish exclusively via temporary
  file/flush/rename and record its hash/readback; details stay outside official
  campaign artifacts. Godot exposes integer64 and buffer file writes in
  [FileAccess](https://docs.godotengine.org/en/stable/classes/class_fileaccess.html).
- At a positive ObjectDB trigger, collect another compact ID set and compute
  sorted added/removed IDs. Describe only added/current candidates, using
  nonrecursive per-item descriptors with explicit detail/byte caps. Preserve
  removed IDs and their baseline class lookup if captured. Invalidated objects
  remain unavailable, not fabricated. Record counts even if detail is capped.
  Do not recursively dump an entire owner Tree for one changed TreeItem.
- Preserve before/after ObjectDB and declared reachable coverage. A matching
  count with ID churn is not unchanged identity. A new count outside the
  reachable inventory remains unattributed; the43727 unobserved objects are
  not silently considered absent. Changing from field-level diffs to ID-only
  detection is an explicit diagnostic scope change.
- Keep sparse timing at ACK4 and the first positive count, and save diagnostic
  evidence before the original failure path can tear down the editor. Keep
  original `screen_sample`, profile, warm baseline, quiescence, counters and
  deadlines. Additional OS samples immediately before/after the diagnostic
  call are diagnostic sidecars; never overwrite the canonical batch4 sample.

Simply clearing `rows` after the old census is insufficient: it removes the
baseline needed for the delta and still incurs large temporary allocations.
Simply moving that census before the official baseline absorbs its overhead
into the denominator and supplies no mechanism proof. Neither is the proposed
fix. The compact collector still allocates and takes time; qualify its actual
cost instead of declaring it free from a data-structure estimate.

## When a longer run becomes justified

The next immediate step is the short cost experiment, not a full35 retry.
If it demonstrates a material reduction and preserves usable ID coverage,
one new copied-project HTTP→native→joint-ACK diagnostic is justified to seek
the **original** S81 ObjectDB71128→71130 event around batch15. Keep the
35-batch maximum and original gate; stop when failure/attribution is captured.
Passing batch15 or completing35 without the event is nonreproduction, not
proof that the old +2 was fixed. No second blind full35 attempt follows solely
because the event did not recur.

S82's baseline census was added after S81 failed, so it cannot explain S81's
original +2. S82 failed earlier at batch5 with ObjectDB still71128, so it did
not exercise the original failure time. Native-only stable-count probes also
lack the complete HTTP/native interaction and do not disprove that failure.

After a justified product/benchmark correction, GT-06 still requires the
unchanged official workload: **ten fresh complete host/editor pairs ×35
batches**, all limits/actual exits/cleanup, final source/artifact seal and two
new independent same-manifest critics. Every experiment proposed here is
diagnostic and ineligible for those350 batch records. There is no gate
relaxation, replacement memory baseline or acceptance conclusion in this note.
