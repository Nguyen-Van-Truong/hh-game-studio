# GT06 S75 — attempt02 retained-counter investigation

Read-only diagnosis, 2026-09-18 Asia/Saigon. This is not critic acceptance or a verified fix. No engine, test, scheduler, production-source mutation or commit was performed. This report is the investigator's only written file. Initial workspace HEAD was `1dda560c2eb46739cbe5aff69293ec1c6056be6c`; the measured source remains checkpoint `cb4d1f6f633e6824a30a45873f05024c3bf7cd58`.

## Finding

The first rejection is **editor held handles, 566 → 568**. The same sample independently fails **editor ObjectDB count, 71,175 → 71,213**. A single `CAMPAIGN_RETAINED_COUNTER_GROWTH` code hides which field failed first. This is not an RSS rejection and must not be described as only an object-counter failure.

The leading object-growth hypothesis is the stock FileSystem dock indexing benchmark JSON evidence under `res://`, adding `TreeItem` and `TextParagraph` objects. The source mechanism and even-sized progression fit; the failed attempt does not contain a live per-class/TreeItem census or focus/scan events, so causality is **not proven**. The two additional OS handles remain separately unexplained. There is no justified production fix yet; a bounded explicit-scan census experiment can test this much faster than another campaign.

## Binding and exact progression

Raw root, relative to `8-9-hh3d-3/`:

`studio/.local/reviews/gt06-s73-campaign-01/run-00-attempt-02/`

Run ID is `gt06-s73-campaign-01.r00.a02`; editor PID 8776/start `windows:134341548516419558`; host PID 27508/start `windows:134341548391087746`. I independently hashed every preserved source file: **49/49 match**, closure `6f5d4c8a14ef8476c4cff6afb06ab161b17905f8593f9a685cd235593d7ee913`. The profile remains `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`.

| Batch | Native pre-publication Objects | ACK Objects | Editor handles | Host handles | Editor RSS bytes | Host RSS bytes |
|---:|---:|---:|---:|---:|---:|---:|
| 0 warmup | 71134 | 71135 | 576 | 194 | 757526528 | 36659200 |
| 1 warmup | 71150 | 71151 | 568 | 194 | 757448704 | 39055360 |
| 2 warmup | 71150 | 71151 | 568 | 194 | 567410688 | 38146048 |
| 3 warmup | 71166 | 71167 | 569 | 194 | 345481216 | 30445568 |
| 4 baseline | 71174 | 71175 | 566 | 194 | 258248704 | 30543872 |
| 5 measured | 71174 | 71175 | 566 | 194 | 217059328 | 27275264 |
| 6 measured | 71174 | 71175 | 566 | 194 | 160325632 | 26902528 |
| 7 measured | 71174 | 71175 | 566 | 194 | 123879424 | 26476544 |
| 8 measured | 71174 | 71175 | 566 | 194 | 110637056 | 27066368 |
| 9 rejected | 71212 | 71213 | 568 | 194 | 119283712 | 9490432 |

Every row has cached-resource count **6**, one identical visible top-level window handle **9048600**, and 100 native create/undo/save/reload cycles. Batch09 records 13 settling frames and 1,296,582 microseconds; batch08 records 12 frames and 1,194,335 microseconds. Batch09 maximum combined status gap is 748.668 ms. Four measured samples passed screening before batch09; they are an incomplete prefix, not a complete accepted run.

The source `benchmark_assembly.py:530–532` constructs editor counters in insertion order `rss_bytes`, `held_handles`, `objects`, `resources`. `run_benchmark_campaign.py:256–268` checks that order against the batch04 baseline; editor RSS is below baseline, so handles trigger first. Independently, Objects exceed baseline by 38. The on-disk JSON is sorted alphabetically and must not be mistaken for runtime insertion order.

`sample_editor()` at `run_benchmark_campaign.py:166–177` calls Windows `GetProcessHandleCount` against the retained **editor process** handle. This is a process handle-table count, distinct from the separate visible-window list. Creating the host's sampler handle does not itself add two handles to the target editor. Constant visible windows do not prove constant kernel handles, child windows or GDScript Objects.

## What sampling does and does not explain

`benchmark_native.gd:588` reads the pre-publication ObjectDB count; `:675` reads again after the validated host ACK. The +38 increase already exists in the native batch JSON, before host joint observation and before ACK. Every ACK count is exactly one above its own batch count. The ACK path keeps a local `FileAccess` reference until function return even after `close()`, a plausible explanation for that constant one-object offset; no conclusion depends on assigning it. It does not explain the new +38.

The whole-editor Object count includes UI/helper objects, not just fixture nodes. The cached-resource monitor counts ResourceCache entries, so unchanged 6 does not demonstrate that all uncached resources or UI buffers are unchanged. [Pinned performance implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/main/performance.cpp).

Full native stdout contains only the engine/banner lines and benchmark markers; stderr is empty. There is no class census, background-scan state, focus event record or handle-type inventory. The terminal owner record shows wrapper exit2, Job zero/closed and wrapper handle released; that wrapper status is not a captured native target exit or evidence that the retained counts were harmless.

## Comparison with S71 and likely mechanism

The frozen generated project still contains `[editor_overrides] run/output/max_lines=100`, and native bootstrap rejects a missing, differently typed or non-100 effective setting before workload. S71's default-cap failure grew almost one Object per printed/action line. Its A/B showed 71110→71182→71254 at10000 and 71109→71131→71131 at100 over three short 50-cycle batches. Those old diagnostics did not establish long-run stability.

Here the late plateau 71175 across batches04–08 despite hundreds of additional log lines is unlike the prior unbounded Output-fill mechanism. Stock EditorLog removes oldest displayed paragraphs above `line_limit+1`, but retains its message vector and uses threaded RichTextLabel shaping. It remains a diagnostic candidate; neither count subtraction nor a lower unsupported cap is justified. [Pinned EditorLog](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_log.cpp#L429).

The stronger alternative is concrete:

- `project/.godot/editor/filesystem_cache10` already identifies `res://benchmark/input.json` as a JSON resource and includes the `benchmark/input/` and `benchmark/out/` directories. There is no `.gdignore`. Each full batch adds ready, start, batch and ACK JSON files in that asset namespace.
- The saved editor layout has FileSystem selected, `display_mode=0`, and root selected. Stock FileSystemDock recursively builds directory items and, in tree-only mode, every file item, even under collapsed directories. It also queues previews. [Pinned FileSystemDock, lines230–341](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/docks/filesystem_dock.cpp#L230).
- A `TreeItem` is an Object; each cell constructs a `TextParagraph`. For a one-column file tree, one added file therefore has a direct two-Object mechanism. [Pinned TreeItem declaration/cell constructor](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L48), [Tree item creation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.cpp#L917).
- Warmup increments +16,0,+16,+8 are arithmetically compatible with 8,0,8,4 newly indexed files. Late +38 is compatible with19 entries. These are **candidate explanations, not an observed census**; the failed run does not record which files were indexed at those moments.
- EditorNode requests `scan_changes()` on application focus-in, which can make accumulated file discovery intermittent. [Pinned focus handler](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L1049). Whether a focus event occurred here is unknown.

The cache thumbnail last rewritten near failure, `resthumb-b3d3202c5330c331f3de7d29300eb5c5`, maps exactly to the absolute `project/scenes/fixture.tscn` path via MD5. Its timestamp is consistent with routine repeated scene saves, not proof of a new resource or cause. The stock preview cache is keyed by path and invalidates on modification time; that timestamp alone cannot identify retained objects. [Pinned preview cache/path handling](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/inspector/editor_resource_preview.cpp#L149).

## Minimal next diagnostic and conditional fix

Run a separately identified disposable native diagnostic, with its own frozen source/evidence and no acceptance claim. Keep cap100, unchanged semantic operations and original counters. Do not start another campaign to find this blindly.

1. Record primitive-only census snapshots before/after fixed batches (e.g.3×50), including all Node IDs/class/paths using `get_children(true)`, TreeItem IDs plus per-column text and resource-path metadata, RichTextLabel paragraph counts/pending paragraphs, Node/orphan/object/resource monitors, Window visibility/focus, and filesystem scan state. Do not retain Node/Resource objects inside stored census dictionaries. Write census records outside the indexed `res://` namespace or to a predeclared fixed non-indexed sink.
2. After a fixed normal evidence topology exists, take a census and explicitly request `EditorInterface.get_resource_filesystem().scan_sources()`. Pinned ClassDB maps that public API to the same `scan_changes()` used on focus-in; prefer it to a broader full `scan()` rebuild. Observe `filesystem_changed`, `is_scanning()==false`, and the ordinary settling interval before another census. This is a labeled **causal probe**, not a change to official workload. Bound scan completion by a fixed deadline; never wait until totals happen to match.
3. Compare file-path TreeItem deltas and whole Object deltas. If each discovered JSON contributes the predicted two Objects, repeat a fresh paired diagnostic with `.gdignore` predeclared in the evidence-only directory before import. Stock scanning recognizes that file ([implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp#L3502)); direct FileAccess and the normal batch/ACK hash checks must still succeed. This configuration would separate runtime evidence from assets; it must not ignore actual fixture resources or bypass evidence validation.
4. Diagnose the two handles independently. Record owned-editor process handle count and thread count alongside scan state at fixed points. A thread/file-handle transient is plausible but unproven. If the original quiescent sample still rises, retain the failure; a filesystem-ignore result cannot exempt an unexplained handle increase.

Only after attribution and an unchanged-gate native check should the coordinator integrate a narrowly scoped generator/configuration change, freeze a new source closure and remint affected evidence. Preserve all original failed attempts. No warmup padding, counter exemptions, Object subtraction, sample retries until lower, history resets, threshold relaxation, or acceptance claim is proposed.

## Re-audit hashes

Hashes are SHA256 of exact bytes under the raw root above.

| File | SHA256 |
|---|---|
| child-failure.json | `bd42882a706c60960a55fbec19537c0b7bc879879b821a6ce1aaa5682d215381` |
| joint-04.json | `71b04306e5fe06d749c7e80f6c637c1df655e03d2977df0203118e4f039df835` |
| joint-09.json | `292dd919f675d6a2ada2d30504352a3a449c4c5da46619f090b04849f3bb7250` |
| sample-preview-09.json | `36440b0c3f01d8c2d23d6fb937f2828529beecdecbd508362812373ba4e77c8b` |
| project/benchmark/out/batch-09.json | `0fa42d9f89371b537582ffa3834a4ecbe2142c4f00f40625f9e21fe984f0cda1` |
| editor-host/stdout.txt | `9309735b3bfe944b5df8f5464890f03aacf2cd334a825843d718bdcef99977b2` |
| source/studio/tests/replay/benchmark_native.gd | `be16dc41c6eb1654521dfbb38e91853bb6067cf07adc28579ddb9bdf95de75a5` |
| source/studio/tests/replay/run_benchmark_campaign.py | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| source/studio/tests/replay/benchmark_assembly.py | `16ba15ea1961d78c89d5ea2b8c389e89b960a4df25e6a2783e4cc8a6d0c1111a` |

Reproduce the progression with read-only JSON parsing of `joint-00.json`…`joint-09.json` and corresponding `project/benchmark/out/batch-*.json`; compare `editor.native_observation.objects`, `editor.held_handles`, `host.counters`, and native `memory.editor.objects`. Source closure is SHA256 of sorted `path + NUL + declared_sha256 + LF`; verify each preserved source byte hash before using code line references.
