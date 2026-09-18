# S82: sparse attribution during the real campaign sequence

AUTHORITY=0. Design/preflight only; not an acceptance critic, execution result,
GT-06 verdict, or authorization to retry the acceptance campaign. No engine or
test was launched for this review. Only this new document was written.

## Recommendation

Run **one disposable, instrumented host/editor pair**, using the unchanged
`run_benchmark_campaign.run_child` sequence and its original strict
`screen_sample`. Wrap `prepare` only to instrument the copied benchmark plugin.
Take a reachable-object census at the original ACK counter observation for
batch 4 and at the first later ACK whose object count exceeds that baseline.
Flush/read back the growth census **before printing the ACK marker**. The
existing host failure then retains the attribution instead of killing the
editor before it can be collected.

Do not start the ten-run campaign controller, change thresholds, reduce the
1000/100 work, accelerate HTTP with fixtures, reset the editor between batches,
or replace elapsed time with an accelerated clock. If growth does not recur,
finish this one 35-batch pair and report `NOT_REPRODUCED_IN_ONE_PAIR`; that is
not benchmark acceptance and does not justify a blind acceptance rerun.

This is the fastest useful next diagnostic. A new state machine, extra debugger
connection, or comprehensive all-object serializer is unnecessary before trying
these two sparse observations. If reachable ownership cannot account for the
growth, keep that gap explicit and stop rather than guessing the owner.

## What the inspected evidence establishes

- The S82 plan retains S81 failure at joint-15: 71,128 to 71,130 objects,
  ResourceCache 6, after approximately 31 minutes. Current WP remains GT-06.
- `benchmark_commands.py` implements real loopback HTTP and journal activity,
  but its effects are explicitly in-process mock effects. HTTP does not invoke
  the Godot adapter. Its significance here is the complete sequence, editor
  lifetime/idle time, host activity, and possible scheduling/I/O contention.
- `run_child` keeps one producer and editor alive across 35 repetitions of
  READY -> HTTP1000 -> bound START -> native100 -> joint sample -> bound ACK.
  Its ACK contains fresh native counters. The editor immediately advances after
  printing ACK; the host applies `screen_sample` afterwards.
- The 6/16-batch native-only probes do not establish behavior over the original
  elapsed time and HTTP sequence. Stable total counts and replacement identities
  do not rule out the S81 problem.
- Read-only aggregation of the retained probe JSON found full census durations
  of 0.593-0.934 seconds across the first probe's 25 records and 0.585-0.990
  seconds across the long probe's 45 records. The long probe's mean was 0.707
  seconds. These are past observations, not a timing guarantee under HTTP load.
  The helper's older 1.1-1.6 second comment is conservative relative to these
  files. The first probe's largest recorded previous write was 43,305 us.
- The long probe's inventory covered 27,401 of 71,127 objects: 104 Tree nodes,
  4,493 TreeItems, 42 RichTextLabels, and other reachable classes. Its residual
  was **43,726 objects**. The probe is not a complete ObjectDB census.

The different native-only and ACK totals must not be subtracted or normalized
into acceptance. In `_wait_host_ack`, a closed FileAccess local still exists at
the counter read. Baseline and growth must be observed at the *same lexical
point*, with the same surrounding locals, to avoid probe-created differences.

## Exact patch points in the disposable copy

Source line references below identify the inspected frozen files, not changes
to those files.

1. **Python `prepare` adapter**, corresponding to
   `run_benchmark_campaign.py:763` and `run_native_benchmark.py:129`.
   Call the original prepare, verify the original copied driver hash, patch
   only `project/addons/hh_benchmark/benchmark_native.gd`, and return a freshly
   computed `project_files(project)` manifest. Returning the old prepare
   manifest would fail the subsequent import-drift check. Preserve
   `benchmark/.gdignore`; put probe output below `benchmark/out`.
2. **One GDScript insertion**, in `_wait_host_ack`, immediately after
   `_barrier_receipts.append(...)` and immediately before the existing
   `print("HH_GT06_BENCHMARK_ACK " ...)` near lines 889-898. Call a synchronous
   helper with `_barrier_receipts[-1]`. It uses that receipt's already-recorded
   object/resource counts; it never overwrites them. If the helper calls
   `_fail`, return before emitting ACK. Assert the replacement target occurs
   exactly once and append the helper exactly once.
3. **Sparse selection in that helper**: capture batch 4 unconditionally as
   `baseline_ack`; on later ACKs capture once when
   `receipt.objects.value > baseline_ack_objects`. Store a primitive baseline
   and boolean trigger latch. Do not sample at `_process`, BATCH_SETTLE, or
   every 10 seconds. Do not add await, Timer, coroutine, or retained Object
   references. A compact per-ACK primitive count/timestamp record is optional;
   the original ACK stdout already supplies the necessary boundary series.
4. **Leave functional control intact**: original `_advance_batch`, original
   `screen_sample` (`run_benchmark_campaign.py:259,868`), original HTTP mix,
   START/ACK binding, native cycles, profile, settling, timeouts, source checks,
   and failure cleanup stay unchanged. There is no diagnostic soft-PASS.
   At first growth the host should fail exactly as before, with an attribution
   file already present. This captures ownership at the *same failing ACK
   boundary*, not the exact instruction or wall-clock instant of allocation.

Prefer this explicit two-hook adapter over patching `run_child` source text or
duplicating its entire control/cleanup loop. The wrapper itself is diagnostic
code and must have its own immutable hash and exact invocation record.

The coordinator's initial `20260918-gt06-s82-attribution/diagnose_sequence.py`
uses a closely related insertion immediately **before** the original fresh
counter block. That is also workable and avoids aging the ACK's observation
timestamp during a census. In that variant, read the same monitors before the
probe and after `_object_probe_sample` returns, including its write/readback,
and reject or explicitly invalidate attribution if they differ. The existing
`counters_equal_across_collection` check covers collection only, not subsequent
serialization/publication. Without this extra comparison, the helper's
pre-probe baseline can differ from the host's later ACK baseline. Never fix a
discrepancy by overwriting or subtracting from the original ACK counters.

## Census contents and timing budget

Reuse the existing `_object_probe_collect` traversal initially. Its demonstrated
cost is reasonable for two calls, and silently narrowing to just TreeItem would
miss a different reachable owner. Remove the old probe's phase/idle hooks and
its periodic selection; do not change its normal gameplay methods.

For both snapshots record original ACK receipt, PID/start binding, run ID,
batch, cycle, phase, process frame, monotonic time, scanning/focus state,
counter reads before/after collection, census duration, serialization/write
duration, class counts, inventory count, and residual count. Collect first;
open output FileAccess and HashingContext only after the counter comparison.
Keep data as strings/numbers/booleans/arrays/dictionaries; never retain a Node,
TreeItem, Resource, Signal, or Callable in the previous inventory.

Add **per-owner summaries** to make normal replacement understandable:

- For each Tree: ID, path, visibility, item count, and a multiset fingerprint
  of bounded cell text hashes and parent/column structure. Keep item IDs for
  identity diff separately. Preserve counts even if payload text is truncated.
- For each RichTextLabel: ID/path, paragraph count and character count. These
  are ownership clues; they do not directly enumerate its internal paragraphs.
- For Node changes: class, ID, parent ID, path/scene file when applicable,
  inside-tree and queued-for-deletion state. Include orphan and processed-tween
  observations already supported by the probe.
- Persist a compact baseline ID/class inventory, not only the old helper's
  `initial_inventory_ids_omitted=true` summary. Full descriptions need only be
  written for ownership summaries and added/changed/removed objects. This lets
  another reviewer check the diff without the probe's vanished in-memory map.

Report added minus removed counts by class and Tree owner, together with
removed-ID validity. A rebuilt 30-item Tree is churn if 30 items disappear and
30 replace them; an owner whose item count rises by two is a much better lead
than two arbitrary IDs appearing among replacements. Neither correlation nor
net +2 alone proves retention cause.

Keep existing bounded, no-overwrite temp/write/flush/rename/readback output.
Set finite caps before launch (for example, two snapshots, 8 MiB per artifact,
64 MiB aggregate); stop on overflow rather than truncate owner evidence. Any
manifested extra baseline chunks count toward the same caps. Do not print
large inventories into Godot Output, since that can itself allocate objects.
Do not serialize arbitrary editor properties or connection-bound arguments,
which may expose credentials or invoke property getters.

Use a **diagnostic census time guard**, including serialization and publication,
with an explicit failure code if the first baseline instrumentation consumes
the 2-second status budget or cannot finish inside a conservative smaller
budget (e.g. 1.5 seconds). A traversal time budget must be checked during work,
not only after an unlimited recursion; its partial output must be labeled
incomplete. Do not raise the production status threshold. The existing guard
may still trip because of scheduling: retain that result as probe interference.

If baseline cost actually blocks progress, the next *separate* diagnostic may
use a faster collector that traverses all nodes with only ID/class/parent/name,
builds detailed paths only for changed nodes and Tree/RichText owners, and
omits all-node incoming-signal enumeration. This should be cheaper, but no
sub-2-second claim is justified without measurement. Its reduced coverage must
be declared. Do not spend another long full run assuming it is faster.

## Source provenance and bounded ownership

Before launch verify the original 51-file S81 manifest byte-for-byte against
the retained freeze. Keep the original closure and the **instrumented execution
closure** distinct: the latter includes diagnostic Python/GDScript helpers,
exact transformation or patch, prepared project, imported project snapshot,
actual imported Python modules, toolchain lock and binary digest. Do not label
the instrumented driver with the unmodified S81 digest. Collect the dynamic
Python closure only after fixture/campaign imports are loaded; otherwise it
will omit modules loaded by `run_child` and fail equality later.

Record helper hashes before/after, initial/copied/patched driver hashes,
complete project manifests, exact argv/cwd, UTC time, engine pin, host/editor
PID and start identity, fixed wall bound, limits, expected sequence, and
`formal_acceptance=false`, `full_benchmark=false`, `AUTHORITY=0`. Even if the
unchanged inner driver emits `benchmark_complete=true` after 35 batches, the
outer diagnostic record must explain that this means one instrumented native
run completed, not the required ten-run acceptance campaign. Do not feed this
output to the acceptance dataset/sealer.

Use a fresh no-overwrite run root and the existing checked ownership primitive:
the outer Python process must be owned with `campaign_host=True` so its process
budget includes the nested editor helper/editor/transient RD probe. Retain
original 7,410-second limits, one editor per copied project path, original
import ownership, and the original cooperative Stop binding through the owned
parent. Do not use a 600-second `run_fixture.py` wrapper copied from the short
native probe for a roughly 31-minute reproduction. Do not start a second engine
lane or delete any S80/S81/probe evidence.

On error or Stop, preserve the original exception and independently close the
producer, observer, editor owner and any retained constructor owner. Preserve
`child-terminal-cleanup.json`, raw stdout/stderr, exact target start/exit files,
helper exits, Job zero/closed state and handle/thread/socket observations.
Independently observe the host child's exit from its parent. Do not infer a
native exit from helper exit 2 or Job zero: the existing forced cleanup can
terminate the helper before it writes `process-exit.json`. A sparse attribution
run can succeed at identifying a candidate owner while still leaving the
native-exit diagnostic gap open. Do not claim that this design fixes that gap.

## Why the stock ObjectDB profiler is not the first lane

At the exact 4.7.2 source tag, the object counter reads ObjectDB and the resource
counter reads ResourceCache, so cached resources are not a census of all
RefCounted objects. [Pinned Performance implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/main/performance.cpp#L246)

Godot's profiler can compare snapshots and expose reference information, but
the documented workflow targets a running project/debugger session and excludes
some native classes. [Godot 4.7 profiler documentation](https://docs.godotengine.org/en/4.7/tutorials/scripting/debug/objectdb_profiler.html)

The pinned panel pauses the current debuggee and sends
`snapshot:request_prepare_snapshot`; it does not directly snapshot its own
editor process. The collector gathers IDs via `ObjectDB::debug_objects` and
serializes them through the engine debugger; its class is C++-only and the
module registration does not bind a public GDScript snapshot method.
[Panel implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/objectdb_profiler/editor/objectdb_profiler_panel.cpp#L56),
[collector implementation](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/objectdb_profiler/snapshot_collector.cpp#L48),
[collector declaration](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/objectdb_profiler/snapshot_collector.h#L41),
[module registration](https://github.com/godotengine/godot/blob/4.7.2-stable/modules/objectdb_profiler/register_types.cpp#L36)

Therefore do not use a guessed GDScript `ObjectDB.get_objects` API, brute-force
instance IDs, click a profiler for the wrong process, or rebuild/fork the engine
for this attempt. If growth falls entirely in the residual, a separate bounded
preflight may investigate debugging the *editor as debuggee* with the stock
collector and an owned transport. Editor activation, capture support, side
effects, sensitive property serialization, and actual cost must be demonstrated
before promising that route. This review did not verify it by execution.

## Stop and interpretation

- **Growth captured, owner delta present:** retain exact baseline/growth bytes
  and owner/class deltas; write a narrow causal hypothesis and next targeted
  check. No production counter subtraction or threshold adjustment follows.
- **Growth captured, residual unexplained or counters change during census:**
  mark attribution unresolved/unstable, retain evidence, stop. Do not claim a
  complete ObjectDB diagnosis.
- **No growth after one complete pair:** `NOT_REPRODUCED_IN_ONE_PAIR`; preserve
  the actual duration and sequence. No automatic repeat or ten-run launch.
- **Census overhead, HTTP failure, source drift, warnings/errors, cap/timeout,
  Stop, or uncertain cleanup:** terminate via the existing bounded owner and
  report that exact diagnostic limitation; retain all artifacts.

The recommendation intentionally preserves the original growth failure. It
adds an owner observation before teardown; it does not redefine acceptance.

## Follow-up static read of the coordinator adapter

At the coordinator's request, the initial new `diagnose_sequence.py` and copied
probe were read without execution or edits. No concrete launch/Job nesting/
source-root defect was found: `ROOT = BASE.parents[2]` resolves to HH3D-3,
the parent owner uses `campaign_host=True`, its source root binds the 51 base
files plus two helpers, prepared-project hashes are recomputed after patching,
and the original `run_child`/`screen_sample` remain unchanged. The preflight
import is a separate owned stage and must remain serialized with other engines.

The two actionable diagnostic limitations were sent to the coordinator:
counter equality must include probe publication as explained above, and the
copied helper still omitted baseline identities/per-Tree item counts. The
latter does not prevent launch, but limits independent owner-net-change audit.
Neither static reading nor a successful import proves the runtime hook or
native exit capture. The parent's strict wrapper-exit failure on growth must
be interpreted with the retained child's original failure/cleanup artifacts.

## Review baseline

Read-only HEAD: `d1254bf8fbc18585a19cb41153581ec832280425`.
Tracked `git status --short --untracked-files=no` was clean at inspection; many
pre-existing untracked review artifacts were present. The process query found
no Godot/Blender or matching benchmark/diagnostic Python worker at that moment;
the coordinator must recheck immediately before launch.

Plan's frozen S81 closure:
`e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`.
This review read that closure from the plan; it did not recalculate all 51 files.

Inspected individual SHA-256 values:

| File | SHA-256 |
| --- | --- |
| `studio/tests/replay/run_benchmark_campaign.py` | `bb43ecc04c2de4872177a440eb071d533efdaa9e8194f62b4e0907bad8d4b252` |
| `studio/tests/replay/benchmark_native.gd` | `52fbd9af5c6191ada5baf1d7195a75685ed5e27a95f4d244af8b4d679f8c00f2` |
| `zdoc/reviews/20260918-gt06-s82-diagnosis/diagnose_objects.py` | `4fdcc8961d6f69f469c09c255bf20f63cd504fa6cd999af67b0ae7357ffa8a36` |
| `zdoc/reviews/20260918-gt06-s82-diagnosis/object_probe.gd` | `d43bd09033b50dd4c93ace5ad160513c2f064aa36ff5496135048e474e87f2f8` |

## 2026-09-18 09:40 UTC / 16:40 Asia-Saigon: revised helper preflight note

Static re-review of the coordinator's revised helpers found **no concrete
blocker to this diagnostic**. This is not a final critic verdict or acceptance.
The two earlier findings are resolved in the reviewed version:

- `_attribution_ack` now reads ObjectDB again after `_object_probe_sample`
  returns from publication/readback, writes `attribution-<batch>.json`, and
  fails with `ATTRIBUTION_SELF_DRIFT` on count mismatch or receipt-write failure.
  The original fresh ACK counter read and strict `screen_sample` remain intact.
- The probe now persists `initial_id_classes` for the baseline and
  `owner_tree_item_counts` for owner-level comparison, retaining the original
  detailed added/changed/removed rows and explicit incomplete-ObjectDB label.

Read-only hash verification at `2026-09-18T09:40:48Z` matched both current
helper files to `gt06-s82-attribution-preflight-02/preflight.json`, matched the
effective prepared driver to its overlay digest, and matched all four import
artifacts to `import-host/capture.json`. All 51 current base-source files also
matched the preflight's stored source-file manifest. No helper, engine, or test
was executed by this reviewer.

The retained import receipt reports native PID 28016 with actual exit 0 and
wrapper exit 0, zero active processes, Job closed/zero-observed, no retained
Job handle, no taint, and 4.703 seconds elapsed. The independently rehashed
stderr is empty; the retained stdout shows ordinary 4.7.2 import progress with
no warning/error. This supports the recorded import preflight only: it does
not exercise ACK4, the growth hook, the full HTTP/native sequence, or the
failure-path native-exit issue.

| Reviewed artifact | SHA-256 |
| --- | --- |
| `zdoc/reviews/20260918-gt06-s82-attribution/diagnose_sequence.py` | `bb9f288a3df30dce8f3442896a94e8fb31505bd7a6e8e0ef769a9ea24037e095` |
| `zdoc/reviews/20260918-gt06-s82-attribution/object_probe.gd` | `6221092c70591d89b42aa8c00298198299a716edc7c25b8b4813db5d771fe556` |
| preflight-02 effective `addons/hh_benchmark/benchmark_native.gd` | `a24e69f0e3275cc37c5e57e7ba9279f4bdda2553fbf1d1e155bc86575e6f5b00` |
| preflight-02 `preflight.json` | `90952e2d84d471753d7cd9ae78e2494251c88ef05d283721ae5323ab4020e8fc` |
| preflight-02 `import-host/capture.json` | `90fa682e2f2d05e31d0da7e62422536d5020185be525f88d3b0534af2bdf1f55` |

Remaining limits are unchanged: count equality does not prove atomic inventory
identity under background work, the reachable census has a large residual,
instrumentation can affect timing/RSS, and only the original strict failure
plus actual run evidence can establish what happens at growth. The current
second snapshot's own write duration is not persisted in that snapshot (the
field records the previous write); use the surrounding native/host timing to
bound the total hook cost and avoid claiming a directly measured final write
duration. None of these limits authorize a threshold change or acceptance use.
