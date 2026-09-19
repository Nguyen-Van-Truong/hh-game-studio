# S106 native latency: finite next choice

AUTHORITY=0. Recommendations only; not a critic verdict or acceptance evidence.
Reviewed 2026-09-19, Asia/Saigon. No engine, benchmark, test suite, full-closure
hash sweep, runtime edit, gate edit, or commit was performed for this memo.
Only this new file is worker-owned. Git HEAD observed at inspection was
`1c6cbbf3cb4f07ccb8b5841c1b9686768ce6c96d`; the working tree already contained
coordinator/review changes. The process-name check found no Godot/Blender.

## Decision

There is **no proven causal repair for S102's native status gap**. There is a
specific, testable cost in the benchmark: its `EditorInterface.save_scene()`
invokes the stock editor's preview-producing save. A tiny paired experiment can
isolate that cost. It must not silently replace the formal save operation, claim
that public `scene.save` became faster, or unlock formal launch 2.

Do not run another unchanged six-batch prefix. S105 did not reproduce the counter
excursion, and six batches do not reach the S102 failure at batch 6. Do not
manufacture memory pressure to make a failure appear.

## Evidence and remaining boundary

The frozen runtime/profile bindings below are those recorded in the existing
packets, not a newly verified complete closure:

- Source checkpoint: `56bfd448e83aa2512c0c2561e8e1a29f12134360`.
- 53-file source closure: `7635a470cef554c1a60e1d9427f59998737d3bb829c3a1f134e426cdf9275467`.
- Profile: `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.
- S102 and S105 stdout identify `4.7.2.stable.official.ed1daf0bf`.

`20260919-gt06-s103-status-gap/code-cause-review.md` and its batch summary
localize S102 to b6/c74: heartbeat SAVE at 651389903 us, save start at
651390132, scene-saved callback at 652296856, next heartbeat SAVE_WAIT at
653499254, final readback at 653519351. Thus the native gap is 2109.351 ms;
the signal occurs 906.724 ms after save start, then 1202.398 ms precede the
next heartbeat. HTTP's maximum is 1936.8697 ms with zero transport failures.
The missing S102 datum is save-call return, not another scene-file hash.

In `benchmark_native.gd:274,690,710`, the heartbeat runs before phase dispatch;
the save callback only checks/counts/stamps the signal. Scene inspection and
file hashing in `_wait_save` happen after the later heartbeat. Their final
20.097 ms cannot explain the preceding failed gap. The host's command batch
finished before native start; accepted HTTP/journal work has no demonstrated
call chain inside this native interval.

S102 b6 slowed across create, undo, save and reload, while the scene stayed
295 bytes and ObjectDB/resources stayed 71128/6. That supports a broader
slowdown hypothesis, but does not prove memory pressure, disk contention,
GPU delay, scheduling delay, or a leak. The inspected benchmark has fixed
100-cycle arrays reset at batch start and a 35-batch bound; no newly introduced
unbounded save loop or explicit memory-stress allocator was found in this path.

S104 reader-v104 accepted the same 100 preflight and 600 prefix boundary rows
after correcting frame order. No interval crossed 2 s. S105 `handles-03`
completed six batches and stopped at intentional `S105_PREFIX_BOUNDARY`:
handles 565,559,555,555,559,555; objects/resources 71130/6 throughout; maximum
status gap 779.422 ms. Its single PSS baseline has no comparison snapshot.
Neither observation resolves the earlier latency failure.

## What stock 4.7.2 actually does

The [pinned version file](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/version.py)
confirms 4.7.2 stable. `save_scene()` delegates to `save_scene_as()`; the latter
defaults `with_preview` to true. [Implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_interface.cpp#L695),
[default argument](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_interface.h#L170).

The preview branch reads the 3D viewport image, crops/resizes it, writes a PNG,
uses a progress dialog, and then calls the common scene save. The common path
also saves editor state. `scene_saved` is emitted before external-resource and
plugin external-data saving, folding/title/tab updates, and post-save work.
Therefore signal-to-next-heartbeat can still contain synchronous save work;
the signal is not the save-call-return boundary. This is a source-backed
candidate, not measured attribution of S102. [Pinned save implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L2087).

The preview switch chooses `_save_scene_with_preview` versus `_save_scene`.
[Pinned dispatch](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.h#L901).
The progress dialog processes events and calls `Main::iteration()` when updating
its UI. This provides a concrete mechanism for process-frame advancement during
one synchronous save invocation, consistent with S104's corrected predicate;
it does not prove reentrant benchmark dispatch or a scheduling fault.
[Pinned progress dialog](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/gui/progress_dialog.cpp#L138).

## Public save and benchmark coverage are different

The actual publication path is `publication_owner.py:448`: native capture,
Linux validation, protected staging, selector CAS, editor adoption/readback,
then durable commit. Its EditorPlugin capture at `plugin.gd:402` packs the
bound root and uses `ResourceSaver.save` to an owned scratch path; it does not
call `EditorInterface.save_scene()`. See also `PUBLICATION_OWNER.md:39` and
`publication_owner.py:471-496,539-556`. The native benchmark explicitly grants
no publication ACK (`benchmark_native.gd:2-5`); it tests direct semantic
create/undo followed by the stock editor save/reload route. Improving a
benchmark thumbnail cost is not a demonstrated public-save optimization.

The authoritative plan's performance contract (lines 953-980 at inspection)
requires 100 create/undo/save/reload cycles, fixed mix/device/profile, original
status/counter gates and no overhead subtraction. `BenchmarkProfile` fixes
`native_editor_direct_semantic_test_fixture`; its v2 validator rejects altered
profile fields. The prose does not explicitly require a thumbnail, but the
frozen source does produce one. Removing it changes executed editor/UI/cache
coverage even if scene bytes and reload semantics match. **Treat a formal
switch as a proposed workload/coverage change requiring explicit contract
review and new source/profile binding, not as an automatically equivalent fix.**
This memo does not propose that switch for acceptance.

## One finite mechanism experiment, if pursued

Use one fresh disposable owned editor on the pinned binary, no other engine,
no PSS, no artificial load, and no full HTTP campaign. Define a new diagnostic
recipe/source binding, explicitly outside the formal v2 dataset. After existing
startup/readiness checks, execute exactly ten groups of A,B,B,A: 40 native
create/undo/save/reload cycles total, 20 saves per arm. A is the unchanged
`save_scene()`; B is `save_scene_as(SCENE, false)` on that same existing path.
Keep all rows and their order; do not discard inconvenient first observations.
Use one 180-second outer ceiling, existing bounded per-phase/owned Stop rules,
and stop immediately on a semantic/error/binding failure. No automatic retry.

Record each call entry/return, signal time/count, phase entry/exit, frame
numbers, next-dispatch time and unchanged heartbeat timestamps. Require exact
scene-file bytes/hash, unchanged script bytes, matching semantic baseline after
undo and reload, and the expected new root/generation after reload for both
arms. Record preview cache effects separately: thumbnail equivalence is neither
expected nor claimed. Buffer only the fixed 40 records and flush after the
measurement, retaining actual process exits and owned cleanup.

B returns void, unlike A. Its collector must record the method and a nullable
return-error field; do not invent `save_result=0` or feed B into reader-v104's
unchanged success predicate. Completion requires the actual matching signal,
file readback and semantic reload. This is a versioned diagnostic reader/recipe,
not a reinterpretation of any old raw record.

Report paired call-duration and between-dispatch distributions, all outliers,
and whether A's cost differs consistently across the ten groups. A clear
difference establishes avoidable *preview-path cost in this microexperiment*;
it does not reproduce residency b6 or establish the cause of S102. Overlap or
missing boundaries means `NO_DISCRIMINATING_RESULT`/`UNKNOWN`; stop this branch,
do not enlarge or repeat it. Even a favorable result requires contract review
before any formal workload change. The short experiment is useful precisely
because it tests a source-defined contrast rather than waiting for a rare gap.

If preservation of the full stock save path is required, the unresolved
boundary remains the original S102 call-return/frame interval. A future
latency-specific attempt would need that boundary and CPU/wait attribution
through b6, not another six-batch PSS probe. Do not launch it merely because
this memo exists, and do not claim an external machine blocker without an
observed wait or resource-pressure measurement.

## Handle limits remain separate

Windows thread pools include worker factories, worker/waiter threads and
waitable objects; Windows may add workers for blocked work and controls their
lifetime. This makes pool-related fluctuations plausible, not proven for this
Godot process. [Microsoft thread-pool documentation](https://learn.microsoft.com/en-us/windows/win32/procthread/thread-pools).
S105's one baseline shows 45 Thread and 6 TpWorkerFactory entries, but 192/559
entries have flags 0 and unavailable type. There is no before/after typed
delta, and numeric handles are not stable object identity. Neither these types
nor the non-monotonic total explain S102 latency or excuse S103's valid gate
failure. Keep all existing gates and failures unchanged.
