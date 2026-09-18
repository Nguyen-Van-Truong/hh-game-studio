# S77 native ObjectDB attribution handoff

2026-09-18, Asia/Saigon. AUTHORITY=0. GT-06 remains IN_PROGRESS; no acceptance verdict or gate change. This worker inspected source and existing evidence only. It did not run an engine, parser, test, campaign, or broad hash audit. Initial inspected Git HEAD was `398de65ca4f98cede6646df4b5f1809c4e28de5b`.

The failed campaign cannot yet be called an object leak or explained as two identified transient editor objects. Both claims require attribution that current aggregate counters lack. The evidence does establish a previously observed +2/-2 fluctuation in the same native PID. The existing retained-counter gate remains binding.

## Observations and exclusions

| Evidence | Exact observation | Meaning |
|---|---|---|
| Coordinator's current campaign observation: `gt06-s76-campaign-01`, launch2, `run-00-attempt-02` | Batch4 baseline71128 → batch5 71130; resources6; handles560 →556; RSS within10%; `CAMPAIGN_RETAINED_COUNTER_GROWTH` | This worker did not independently re-read the newly preserved package. It accepts these as coordinator-reported failure facts, not a class attribution. |
| `20260918-gt06-s76-handles/retention-analysis.json`, PID25368 | b0/b1 71125; b2 71127; b3–b7 71125; final idle71127. Resources6 throughout; handles565 at b1/b2 and559 at b7/idle. Native exit0;800 cycles. | Net object count can return to its earlier value. This does not prove the same two IDs were freed, or rule out a masked leak. |
| `retention-evidence/project/benchmark/out/batch-02.json` | Objects71127 at107472485µs, frame4585, settle1112524µs/163frames | The +2 existed in the native batch sample before the old diagnostic's asynchronous PSS wait. |
| Corresponding `batch-03.json` | Objects71125 at139855509µs, frame6053, settle1108189µs/162frames | Return occurred while continuing the same semantic create/undo/save/reload workload. |
| `studio/tests/replay/benchmark_native.gd:580`–`636` | Clears per-cycle dictionaries, waits≥4frames and≥1.1s, validates semantic revision, samples ObjectDB | Semantic quiescence is checked; arbitrary editor/background object quiescence is not. More settle time alone does not identify the cause. |
| `benchmark_native.gd:668`–`712` | ACK reader keeps a local `FileAccess` reference through fresh counters, even after `close()` | A stable ACK-versus-batch +1 can have a separate measurement-scope explanation. It cannot explain a +2 already present at batch publication. No counter subtraction is authorized. |

Pinned `Performance.OBJECT_RESOURCE_COUNT` counts ResourceCache entries, not all live resources/refcounted editor objects. Thus resources6 does not eliminate UI text, timers, or file/directory access objects. Node and orphan monitors are distinct from total ObjectDB. [Pinned monitor implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/performance.cpp#L229).

## Hypotheses to discriminate

1. **Periodic filesystem work overlaps the scalar sample.** Pinned EditorNode creates a Timer with wait_time0.5 connected to `EditorFileSystem.scan_changes`. The filesystem implementation can perform changes scanning on its worker thread; `is_scanning()` includes both normal scanning and changes scanning. This is a concrete source-supported mechanism for concurrent temporary objects, but not proof that this campaign's exact two objects were DirAccess/FileAccess. [Editor timer](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L8132), [filesystem scanning](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp#L1553), [scan-state implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp#L1713).
2. **Editor UI/text or TreeItem churn.** `_write_batch()` forces a heartbeat immediately before its counters; `_heartbeat()` prints every500ms. The project already limits displayed output to100 lines, but a limit does not establish a constant paragraph count or identical live text-object lifetimes. Record RichTextLabel paragraph/character counts and a TreeItem census, and compare a quiet idle period without new heartbeat lines. No claim that paragraph count is a complete TextParagraph census.
3. **Retained semantic objects or orphan nodes.** Create/undo/reload could leave objects outside the edited tree even when its semantic hash returns to baseline. Track exact Node/orphan IDs and their later validity; distinguish expected replacement of the edited root from persistent objects outside it. This remains possible until excluded by actual observations.
4. **Other transient editor objects.** Signal-connected SceneTreeTimer/resources, processed Tween objects, tooltips, and deferred editor work may appear without cached-resource growth. Record existing accessible IDs; do not create timers or use `await` in the new sampler. The old idle helper did use both, so its absolute idle count is not a clean object census.

## Runnable isolated probe

From repository root, after the coordinator confirms all prior owned process trees/handles are clean:

```powershell
python -B '8-9-hh3d-3/zdoc/reviews/20260918-gt06-s77-object-recovery/diagnose_objects.py'
```

This fixed no-argument entry point uses existing `run_fixture.run_process` as a600s outer owner. Its child uses unchanged trusted import ownership and `BenchmarkProcess` for one disposable editor, with a540s child wall bound. It creates fresh `studio/.local/reviews/gt06-s77-object-diagnostic-01` and `object-owner-01` beside the helper. It refuses reuse through exclusive creation. A failure is preserved; do not rerun under the same ID.

The diagnostic uses six batches of100 accepted semantic cycles, then60s of frame-polled idle. It changes only the disposable clone's diagnostic count, observation hook, and final idle state. It does not change source runtime, cadence settings, full campaign profile, thresholds, or ownership limits. It does not launch the HTTP mix or a full campaign. Final idle intentionally does not emit heartbeats; its timing is not performance acceptance evidence.

`object_probe.gd` is appended to the disposable driver. It samples cheap counters each frame during BATCH_SETTLE and final idle, and inventories on count/scan-state changes, at one-second intervals, and after batch publication. No inventory is requested during each mutation. It records:

- ObjectDB, cached-resource, tree-node and orphan-node counts, with `EditorFileSystem.is_scanning()` immediately before and after the reads. Both scan-state values are in the change signature.
- Every traversed Node, including internal children; orphan Node IDs; each Tree's TreeItem IDs; existing inbound signal-source objects; processed Tween IDs. Timer rows include wait_time, stopped state and timeout target ID/method, without stopping the timer.
- Instance IDs serialized as decimal strings; class, tree path/parent, scene path, queued-delete state and later ID validity. No object references remain in stored inventories.
- RichTextLabel paragraph and total-character counts, focus, frame/time, phase/batch, last heartbeat time, class counts, and added/changed/removed ID descriptors.
- Counters again after collection; collection duration separately from the previous snapshot's serialization/write/hash duration. A changing before/after count invalidates an atomic-census interpretation.

Counters and class collection happen before opening the local evidence FileAccess. Snapshots use temp+rename and exact readback hash. Output is under the existing `benchmark/.gdignore` boundary. Caps are512 snapshots,8MiB per snapshot and128MiB combined; cap overflow is a diagnostic failure. The first record contains the initial accessible inventory, later records contain deltas. The final record is `idle_end`.

The outer owner saves exact copies and hashes of both helper files before starting; the child saves its source subset, initial project map, transformed driver hash and runtime manifest. The result must contain real native exit/Job proof, all600 cycles, final idle record and clean captured logs. A scheduler or helper exit alone is insufficient. The probe is ready for coordinator execution but has not been syntax/engine-tested by this worker.

Frozen handoff hashes:

| File | SHA256 |
|---|---|
| `diagnose_objects.py` | `e6d07a658d378a85e3859dcfb7432051ee1002fa2b37c10848b0bd9f37a50a60` |
| `object_probe.gd` | `54352825dc7860a233d70cfd34bb38c0797abe00b7d766f5fa14ba896388e5e0` |
| inspected unchanged `studio/tests/replay/benchmark_native.gd` | `61ca9916f9b8cf758e702b59bf05d316f7f12c6c491d54f788054761da385ea1` |

Further helper edits and execution ownership were handed to the coordinator after these hashes. A later parser fix requires a new frozen helper hash; the worker does not claim these initial bytes have run successfully.

## Interpretation boundaries

This is an **accessible-object inventory**, not full ObjectDB enumeration. Pinned GDScript exposes orphan Node IDs but not the C++ `ObjectDB::debug_objects` iterator; arbitrary unconnected RefCounted objects and internal text helpers can remain unenumerated. The probe explicitly reports `inventory_complete_objectdb=false` and the residual count. [Node orphan binding](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/main/node.cpp#L3220), [ObjectDB interface](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/object/object.h#L813).

Two identified editor objects are transient only if their appearance explains the count change and those same IDs subsequently become invalid while the edited scene/other inventories stay accounted for. A count drop alone is weaker evidence. Stable Nodes/TreeItems with +2 correlated to scanning supports the background-scanner hypothesis but still does not identify two unexposed classes. Stable UI paragraph counts help exclude output growth; changing counts only establish correlation unless identities/lifetimes are also captured. If attribution remains residual, report that gap and design a narrowly targeted follow-up; do not retry the campaign blindly, subtract two objects, accept a minimum sample, or increase tolerances.

No conclusions from this diagnostic can repair the failed S76 campaign retroactively. Any eventual runtime remedy must preserve current gates and receive its own source-bound verification and independent reviews.
