# GT06 S71 — campaign02 retained Object growth

Read-only diagnosis, 2026-09-18. No engine, test, or production source was run or changed by this reviewer. This is an implementation diagnosis, not acceptance. The accompanying patch is a draft for coordinator integration and fresh native verification.

## Finding

The failure is the native editor **ObjectDB count**, not handles, cached resources, or RSS. In the last three batch transitions, its entire net increase is explained exactly by Output-dock text paragraphs: one per captured stdout line, plus one editor-only action message per create commit. The evidence does not demonstrate a retained scene/mesh/custody object leak in those transitions.

The measured source is campaign `gt06-s70-campaign-02`, attempt `run-00-attempt-01`, closure `21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`. All paths below are relative to `studio/.local/reviews/gt06-s70-campaign-02/run-00-attempt-01/`; code line references refer to its immutable `source/studio/` copy. The captured Godot is 4.7.2 stable, commit `ed1daf0bf001b61586d9930840f2f1394092c079`, binary SHA256 `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`.

| Counter | Batch 3, warmup | Batch 4, baseline | Batch 5, first measured |
|---|---:|---:|---:|
| Editor objects at native batch publication | 72,398 | 72,864 | 73,340 |
| Editor objects in ACK/sample | 72,400 | 72,866 | 73,342 |
| Editor handles | 555 | 555 | 555 |
| Editor cached resources | 6 | 6 | 6 |
| Editor RSS, bytes | 305,446,912 | 223,989,760 | 181,624,832 |
| Host handles | 194 | 194 | 194 |
| Host RSS, bytes | 27,377,664 | 26,693,632 | 27,267,072 |

All three contain 100 completed native create/undo/save/reload cycles and approximately 1.297 seconds of final quiescence. Batch 5 exceeds baseline by 476 editor objects. `run_benchmark_campaign.py:256–268` correctly rejects any non-RSS counter increase; its baseline is assigned from batch 4 at lines 670–672. No threshold change is proposed. Host RSS remains within the existing 10% allowance.

## Exact attribution method

Read `editor-host/stdout.txt` as UTF-8 lines. Locate each `HH_GT06_BENCHMARK_BATCH` marker by its JSON `index`. Count the interval starting at the previous batch marker and ending immediately before the current batch marker. This corresponds to the new log lines between the two native pre-publication ObjectDB readings: `_write_batch()` reads the counter at `benchmark_native.gd:578`, then prints its batch marker at line 605. Add `len(native_batch['cycles'])`, because each cycle commits one create action. Compare this sum to the native ObjectDB delta. ACK deltas match the same calculation.

| Transition | Previous/current BATCH stdout line, 1-based | New stdout lines | Create commits | Object delta | Residual |
|---|---|---:|---:|---:|---:|
| 0→1 | 126 / 262 | 136 | 100 | 236 | 0 |
| 1→2 | 262 / 608 | 346 | 100 | 448 | 2 |
| 2→3 | 608 / 963 | 355 | 100 | 455 | 0 |
| 3→4 | 963 / 1329 | 366 | 100 | 466 | 0 |
| 4→5 | 1329 / 1705 | 376 | 100 | 476 | 0 |

The last interval contains 372 heartbeats and one each of BATCH, ACK, READY, START. `line-attribution.json` records the arithmetic for all six batches. The earlier warmup transition 1→2 has two additional objects; this review does not assign those two objects to a class. The raw/ACK readings also have a constant +2 offset; no conclusion here depends on attributing that offset. Aggregate accounting cannot independently identify every individual live object, but it exactly explains the observed mature-batch net growth and provides a concrete native mechanism.

## Pinned stock source mechanism

- GDScript `print()` calls `print_line`; ordinary output goes to the OS and registered print handlers. The editor handler sends it to `EditorLog`. See [variant utility, line 960](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/variant/variant_utility.cpp#L960), [print handler dispatch, line 97](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/string/print_string.cpp#L97), and [EditorNode, line 7912](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L7912).
- `scene_commands.gd:353–361` creates an unmerged action and commits once. Every editor UndoRedo history registers the log callback; commit calls that callback once; the callback adds an editor-only message. See [history registration, line 45](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_undo_redo_manager.cpp#L45), [commit callback, line 343](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/object/undo_redo.cpp#L343), and [EditorLog callback, line 301](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_log.cpp#L301).
- EditorLog appends a newline for each displayed message. A RichTextLabel paragraph constructs a `TextParagraph` object. The default display cap is 10,000 lines, so these samples are still filling it. See [newline and oldest-paragraph removal, lines 457–467](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_log.cpp#L457), [paragraph constructor, line 194](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/rich_text_label.h#L194), and [default/range, line 1122](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/settings/editor_settings.cpp#L1122).

## Scene and UndoRedo ownership check

`plugin.gd:36–49` drops the old command adapter when the edited root changes. `scene_commands.gd:255–264` uses `DetachedNodeCustody`, whose final release frees a detached created node; lines 357 and 463 bind that custody to the action. The benchmark clears transient row dictionaries after each cycle and checks generation/root replacement (`benchmark_native.gd:513–553`).

Stock reload removes the old scene, deletes its root, discards its UndoRedo history, and clears the new history. Discarding the old history deletes its UndoRedo object, whose destructor clears its action storage. See [reload, lines 7143–7151](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L7143), [scene deletion, lines 674–701](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_data.cpp#L674), [history disposal, lines 495–505](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_undo_redo_manager.cpp#L495), and [UndoRedo cleanup, lines 458–464 and destructor](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/object/undo_redo.cpp#L458).

No additional scene ownership defect was demonstrated in this bounded read. The stable resource counter alone cannot prove all resources were freed: its pinned implementation counts `ResourceCache` entries, whereas the object counter counts all ObjectDB objects. See [Performance, lines 257–260](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/performance.cpp#L257).

## Minimal proposed correction

`bounded-output-log.patch.draft` changes only the generated benchmark project configuration and native bootstrap readback:

```ini
[editor_overrides]
run/output/max_lines=100
```

This is the lowest supported stock value, declared before import/launch and included in the existing immutable project/source binding. It retains a rolling 100 visible Output lines; the first 100-cycle warmup fills that display. Full externally captured stdout/stderr and native command/cycle evidence remain unchanged. All original counters, barriers, quiescence, profile schema/hash, 5+30 batches, and 10-run requirements remain unchanged. There is no object subtraction, counter reset, Output clearing, hidden filter, or memory-threshold increase.

The API path is verified against the pinned engine, including the distinction raised during review: `EditorInterface.get_editor_settings()` returns the singleton ([line 102](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_interface.cpp#L102)); **`EditorSettings.get_setting()` explicitly resolves project overrides before raw `get()`** ([lines 1574–1579](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/settings/editor_settings.cpp#L1574)). The override prefix is `editor_overrides/` ([ProjectSettings header, line 58](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/config/project_settings.h#L58)); EditorLog reads the effective setting in its constructor ([lines 502–503](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_log.cpp#L502)). The draft fails bootstrap unless effective readback is exactly 100. It does not mutate global editor preferences.

Using `printraw()` alone would still leave the 100 editor action paragraphs per batch, so it is not included. The stock cap limits displayed paragraph objects; EditorLog still keeps message strings internally (`editor_log.cpp:276`). Original host/editor RSS checks must remain active. A fresh native comparison is required to confirm the effective setting and stable post-warmup total counts; this draft is not a demonstrated fix or PASS. Root owns that verification and remint.

## Reviewed file digests

| File | SHA256 |
|---|---|
| source/studio/tests/replay/benchmark_native.gd | `da0bb949ebaf3bc3881a1e9ad325d98ac6496fc3a0454b825a28655fdbc37515` |
| source/studio/tests/replay/run_native_benchmark.py | `f61e031920232f5476a3f5f6850f5217765b9058d4474a678d6e09f103f29392` |
| source/studio/godot-addon/addons/hh_studio/scene_commands.gd | `8da8495197b3d5358ea681321765c388618aadc63459c3eda18f69957f623069` |
| source/studio/godot-addon/addons/hh_studio/plugin.gd | `13dc29df8b673358c40af96220b8d8c29e999eb9f9a2618b224a1e9d983b6036` |
| editor-host/stdout.txt | `ba0aad8543c6a4a878f507ed3bdc3019ca6751b3d13957d27db627f497bc9cc4` |
| sample-preview-03.json | `20f50ed3883bb2184582b88090eed106f4900b7b574cebf9aa31a5fea7f5705d` |
| sample-preview-04.json | `593307e15fb49b3695baea64c36ef6c9eb46b0c4cf87fcb3e005890f84d91e14` |
| sample-preview-05.json | `2f5a7039b99f390dd678734fa148509ed79709522c2330ab00f6286b98d6a2da` |
| source-files.json | `4ce35b98d4f850ba1fdf8aa9d86058cabc4ac45f72e1ef661626149235da2ebf` |

The draft patch SHA256 is `81c7790c0cadb11f7afd0aab5e957fa4bdbacf0add543c403f87f3c360142d28`; the arithmetic artifact SHA256 is `37ca564f280fec43870febd77126e4ee005ffacac4cecc9c79d601392a1d3b2f`.
