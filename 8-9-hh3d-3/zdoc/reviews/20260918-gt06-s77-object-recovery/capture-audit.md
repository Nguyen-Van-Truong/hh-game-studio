# S77 counter capture and handoff audit

Independent bounded static audit, 2026-09-18, Asia/Saigon. Diagnostic guidance only; no acceptance verdict or critic signature. GT-06 remains IN_PROGRESS and the S76 launch2 attempt remains FAILED. Only this report was authored. No engine, test, full-closure hash scan, runtime mutation, plan mutation or commit was performed.

The actual nested directory is `8-9-hh3d-3/`. Its AGENTS.md and the tools plan S76 were read. Initial repository HEAD was `398de65ca4f98cede6646df4b5f1809c4e28de5b`; the tracked-status query was clean and the process query returned no Godot/Blender processes. These are initial observations, not continuing ownership assertions. Engine source references below are pinned to the declared stock 4.7.2 commit `ed1daf0bf001b61586d9930840f2f1394092c079`.

The high-confidence result is that **next-batch allocation cannot explain the recorded batch05 increase**. The ACK sampler does count one locally retained FileAccess, but the same offset occurs in every available batch. The additional two objects already exist in the earlier batch publication sample. Their classes and lifetimes remain unknown; the failed evidence does not establish either a leak or a harmless transient.

## Exact samples

Raw root `R` is `studio/.local/reviews/gt06-s76-campaign-01/run-00-attempt-02/`, relative to `8-9-hh3d-3/`. Values were read directly from `R/project/benchmark/out/batch-XX.json` and `R/joint-XX.json`, without running collectors.

| Batch | Publication objects | ACK objects | Publication frame | ACK frame | Publication→ACK, µs |
|---:|---:|---:|---:|---:|---:|
| 00 | 71123 | 71124 | 7502 | 7506 | 57957 |
| 01 | 71127 | 71128 | 18526 | 18533 | 80216 |
| 02 | 71127 | 71128 | 28573 | 28581 | 82580 |
| 03 | 71127 | 71128 | 41157 | 41167 | 90036 |
| 04 | 71127 | 71128 | 53234 | 53248 | 125035 |
| 05 | 71129 | 71130 | 67748 | 67764 | 129681 |

Resources are 6 throughout. At 04→05 editor handles decrease 560→556 and editor RSS decreases 148873216→142139392 bytes; host handles stay194, host RSS rises19091456→20480000 bytes, within10%. Batch05 max status gap is656.642ms. These observations isolate the reported non-RSS increase to editor objects for this sample; they do not clear any other future sample or gate.

Batch05 publication time is640115481µs; ACK is640245162µs. READY06 is issued at640252059µs. The +2 exists at both earlier observations, before READY06. Publication follows1111722µs and161process frames of the existing batch settle interval.

## Boundary and temporary-object lifecycle

1. `studio/tests/replay/benchmark_native.gd:592–608` enters BATCH_SETTLE after100cycles and waits the fixed minimum4frames/1100000µs, then checks the scene revision. `:611–644` reads counters before batch serialization; `:650–651` switches to HOST_BARRIER.
2. `studio/tests/replay/run_benchmark_campaign.py:627–644` reads that batch, checks its binding/timings, samples the host and editor OS counters, then publishes the bound ACK. No next host command batch has begun.
3. `benchmark_native.gd:658–709` validates the ACK and rereads scene/file postconditions. `:712–730` records fresh native counters. `:731` prints the immutable receipt, then `:732` advances. Only `:735–740` begins the next READY state. `:346–382` prepares READY but does not perform create/undo/save/reload without a later start permit.
4. The host receives ACK at `run_benchmark_campaign.py:645`, copies its counter values at`:647–649`, writes/assembles the evidence, then screens at`:670`. Native READY06 can therefore precede the Python exception even though its allocations occurred after the sampled counter. There is no causally backward alias: the receipt holds integers, not a lazy query into native state.

The ACK path opens `var file: FileAccess` at`:669`, closes the OS file at`:679`, and still holds its GDScript reference when it queries ObjectDB at`:712`. FileAccess inherits RefCounted; closing its file is distinct from releasing the Object. The observed ACK-minus-publication value is exactly1 in all six batches, consistent with that lifecycle. This is an instrumentation offset, not an identified explanation of the04→05 +2. Source: [FileAccess lifecycle documentation](https://docs.godotengine.org/en/stable/classes/class_fileaccess.html).

An exact hygiene correction is `file = null` immediately after the successful close, before ACK counter sampling, or an ACK-read helper whose FileAccess scope has ended before the counters are read. Keep every byte-length, JSON, binding, hash, deadline and scene postcondition check. Do not subtract1 from evidence or rewrite existing counters. This change would require a fresh source and run; reducing both baseline and measured readings by the same offset does not cure the +2.

`_bytes_sha256()` (`:865–869`) owns a temporary HashingContext that has returned before the counter query. `_write_new()` (`:821–841`) runs after publication counters, and returns before later main-thread callbacks. JSON parse results, dictionaries, arrays, strings and packed bytes are Variant/container values, not one ObjectDB object per row. No variable-length object-owning collection is directly appended between ACK counter read and receipt construction. The sampled root is an existing Node.

The measured fixture is generated by `run_native_benchmark.py:128–138` from `fixture_profile.py:19–23`: one scripted Node3D with one exported integer. It has no viewport screenshot coroutine, timer or gameplay observer. `godot-addon/observe/capture.gd` is not this editor fixture's producer. A screenshot Image/ViewportTexture pair in the separate Play collector cannot simply be assigned to this editor ObjectDB increase.

## Pinned Output and file-system investigation

Output is a possible contributor to the editor total, but **plain cap100 overflow is not demonstrated**. In pinned `editor/editor_node.cpp:7912–7930`, main-thread print executes the Output handler synchronously. In `editor/editor_log.cpp:457–468`, add_newline is followed by a loop removing paragraphs until count≤line_limit+1, before returning. In `scene/gui/rich_text_label.cpp:4662–4717`, removal stops the shaping task and removes the Line synchronously; `rich_text_label.h:178–195` shows a TextParagraph owned by each Line. This weakens a theory where our synchronous heartbeat leaves two ordinary excess paragraphs alive at the following counter read. [Pinned EditorLog](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_log.cpp#L389), [pinned RichTextLabel](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/rich_text_label.cpp#L4662).

It does not rule out all asynchronous text work. The Output RichTextLabel is threaded (`editor_log.cpp:516`), and its shaping worker schedules a deferred end callback (`rich_text_label.cpp:3995–3998`). The display-buffer duplication path at`:775–778` requires nonnegative visible-character clipping; this is not an automatic extra paragraph for every normal log line. A bounded diagnostic should record the Output RichTextLabel's paragraph count, pending paragraphs, finished/updating state and visible-character policy before/after the ordinary sample. Do not change the cap or hide/clear Output to make counters pass. [Pinned RichTextLabel shaping](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/rich_text_label.cpp#L3995).

A concurrent scanner is a concrete transient-allocation candidate. The stock editor creates a0.5s scan timer (`editor/editor_node.cpp:8829–8833`), conditional on its import-resources-when-unfocused setting, and also scans on focus-in (`:1056`). `EditorFileSystem::scan_changes()` runs a low-priority source thread (`editor/file_system/editor_file_system.cpp:1710–1744`). `_scan_fs_changes()` can hold a DirAccess (`:1432–1458`); nested existence checks create an actual FileAccess Object (`core/io/file_access.cpp:54–61`), including ignored-directory checks (`editor_file_system.cpp:3488–3504`). Thus a DirAccess/FileAccess pair can coexist with an unrelated main-thread counter read. The thread flags are finalized by a later main-thread notification, and `is_scanning()` includes full/source/first scan (`:1788–1839`). [Pinned scan lifecycle](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp#L1432), [pinned FileAccess existence implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/file_access.cpp#L54).

The benchmark's present settle check proves elapsed time, frames and scene semantics, **not** scanner inactivity. Neither BATCH nor ACK records scan state. Existing samples therefore cannot confirm this candidate. The same +2 at publication and ACK129681µs apart does not prove uninterrupted identity; two scans or another lifetime pattern could produce equal totals.

If a controlled diagnostic identifies scanner work at these boundaries, strengthen the quiescence precondition using scanner state and a fixed completed-frame boundary, with all existing deadlines, status heartbeats and Stop behavior retained. This must be state-based, applied identically to warmup and measurement, and fixed before a new run. Never wait until an object total falls, choose a minimum, skip a failing sample, move baseline04, or exclude scanner classes from OBJECT_COUNT. A scanning observation at the already-selected sample should first be preserved as diagnostic evidence; there is no justification yet to deploy this as a claimed root-cause fix.

## S76 retention diagnostic limitations

`zdoc/reviews/20260918-gt06-s76-handles/diagnose_retention.py:22–52` reads its point counters before opening its output FileAccess, then awaits a host PSS ACK. Its outer coroutine at`:54–65` is instrumented differently from the full campaign. The final idle point follows `await get_tree().create_timer(60.0).timeout` at`:60`; the timer/suspended coroutine lifecycle can affect ObjectDB near signal delivery. The native-only evidence has a temporary71125→71127→71125 at batch02→03, and an idle71127 after workload71125. Those are real observations of this instrumented run, not attribution of the current full campaign's two objects. There is no identity/class census tying the pairs together. The earlier independent review already makes this limitation explicit.

## Stock-engine inspection route

The pinned implementation reads OBJECT_COUNT directly from ObjectDB and resource count from ResourceCache. ResourceCache=6 is not proof that every uncached Resource or RefCounted allocation is constant. [Pinned Performance implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/performance.cpp#L246).

The safe built-in global census is the **ObjectDB profiler snapshot protocol**, available since4.6. It lists classes/instances and references, but the ordinary Debugger UI targets its connected debuggee, not its own editor process. An editor PID must be the debuggee for this investigation; taking a Play snapshot would inspect the wrong process. [Official profiler guide](https://docs.godotengine.org/en/stable/tutorials/scripting/debug/objectdb_profiler.html).

Pinned `modules/objectdb_profiler/snapshot_collector.cpp` registers the `snapshot` message capture; prepare requests collect ObjectIDs/classes while ObjectDB is locked, then look up still-live objects before serialization. The wire messages are `snapshot:request_prepare_snapshot` with request ID/editor-version arguments, then `snapshot:request_snapshot_chunk`; replies are `snapshot:snapshot_prepared` and `snapshot:snapshot_chunk`. Drain every declared chunk: the producer keeps a pending compressed snapshot until the last chunk request. The UI pauses its debuggee for capture and handles6MiB chunks. [Pinned collector](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/modules/objectdb_profiler/snapshot_collector.cpp), [pinned profiler client](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/modules/objectdb_profiler/editor/objectdb_profiler_panel.cpp#L61).

This is a stock capability candidate for a separate disposable diagnostic launched with a loopback remote-debug endpoint. Pinned `main/main.cpp:2300` initializes the debugger independently of the later editor branch. This audit did not launch that route or prove its behavior on this installed binary. Its protocol availability, target PID, debugger handshake, bounded snapshot size/time, completion and cleanup must be proven before relying on it. Full snapshots allocate and pause; keep them outside any acceptance timing dataset, and compare object IDs/classes from fixed diagnostic points without retaining live Object references in the target.

There is no public `ObjectDB.get_all_instances()`/`debug_objects()` GDScript binding in the inspected API; `ObjectDB::debug_objects` is C++ infrastructure. `EngineDebugger.send_message()` sends to the debugger; it does not directly invoke a local incoming capture. Use the verified stock protocol or a bounded Node/TreeItem/Tween/known-owner census, not guessed IDs, raw-process-memory walks, injected DLLs, engine forks or GDExtensions. A Node-only census cannot rule out TextParagraph/FileAccess/DirAccess objects. [EngineDebugger API](https://docs.godotengine.org/en/stable/classes/class_enginedebugger.html), [EditorDebuggerSession API](https://docs.godotengine.org/en/stable/classes/class_editordebuggersession.html).

## Scoped re-audit hashes

Only the listed files were hashed; this is not a closure verification.

| File, relative to8-9-hh3d-3 | SHA256 |
|---|---|
| `studio/tests/replay/benchmark_native.gd` | `61ca9916f9b8cf758e702b59bf05d316f7f12c6c491d54f788054761da385ea1` |
| `studio/tests/replay/run_benchmark_campaign.py` | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| `studio/tests/replay/run_native_benchmark.py` | `6919f07d0e148d03dd15a4804f42b5bf1aba427610af3533d87c5f3a691a3788` |
| `studio/godot-addon/fixture_profile.py` | `25e1667dd930dcf0746b071fc29ea3460bc18d5fb9f3f83e806c1793028f21ae` |
| `R/project/benchmark/out/batch-04.json` | `23e5e2c5bcf8fabdf05f27bbb1f0732c4872ac60d1ade846cc58754d25a19c53` |
| `R/project/benchmark/out/batch-05.json` | `fa545f74a8280f1f2aa3a421bfde0e2776b3564c91d6de8f09ac5ff235c3a027` |
| `R/joint-04.json` | `8b854007e9d2fa3f1cab8408801cde40bc1d04436cae2e756a9e7111b020a330` |
| `R/joint-05.json` | `83b5d197dc9dd07e4b4d8e2d040431ad4b5f37a051010224402610ec2574d231` |

Recommended next evidence is a fixed, bounded current-source diagnostic with raw normal sample plus scanner/Output/known-owner census around the same phase. Preserve the existing failure. A FileAccess release is a precise instrumentation cleanup; it is not the missing root-cause proof and does not authorize accepting this attempt.
