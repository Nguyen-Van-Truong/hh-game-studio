# Failed diagnostic02: no new TreeItem owner lead

2026-09-18, Asia/Saigon. Supplemental metadata inspection only; no acceptance or causal finding. No engine, process, test or code was run/changed. Only this report was written.

Read exactly the 26 existing `object-*.json` files under `studio/.local/reviews/gt06-s79-object-diagnostic-02/project/benchmark/out/`, rejecting any file larger than 8MiB, and filtered for `label` equal to `idle` or `idle_end`. No other raw files were read in this follow-up.

There are 14 matching points, `object-0012.json` through `object-0025.json`, all `idle`, batch 5. There is no `idle_end` point. **None contains an added TreeItem**, so this failed run supplies no new owner path/cell text for the S77 idle-growth TreeItems.

| Points | `counters_before.objects` | Added descriptor classes |
|---|---:|---|
| 0012–0022 | 71123 | None |
| 0023 | 71125 | SceneTreeTimer |
| 0024 | 71127 | SceneTreeTimer |
| 0025 | 71125 | None |

These metadata values come from a run contaminated by repeated hashing errors and terminated for `BENCHMARK_LOG_LIMIT_OR_IO`. The timer observations are not a demonstrated cause of S77/S78 growth, and the absence of added TreeItems here does not clear that issue. Object IDs from this process cannot identify owners in another process.

No useful new TreeItem allocation-trigger lead was found. No pinned-source allocation research was pursued because there is no newly observed TreeItem owner to match; diagnostic03 remains necessary for a clean attribution attempt.

## After diagnostic03: focus-triggered external-change lists are a concrete hypothesis

Coordinator reports diagnostic03 completed cleanly with 25 verified points at constant71125. This follow-up did not re-audit that result or run an engine/test. It researches a next hypothesis only, against official Godot commit `ed1daf0bf001b61586d9930840f2f1394092c079`.

The supplied diagnostic03 Tree paths are compatible with two external-change lists: one under ScriptEditor/ConfirmationDialog/VBoxContainer, initially `hide_root=true`, and one under EditorNode/Panel/ConfirmationDialog/VBoxContainer, initially `hide_root=false`. Auto-generated numeric node names are not semantic identifiers. The numeric Tree IDs matching S77 in another process do **not** establish identity, and these paths do not retroactively attribute S77 objects.

**EditorNode candidate.** Its constructor creates a ConfirmationDialog containing a VBoxContainer and Tree, without setting hide_root there. The dialog's confirmed handlers reload modified scenes and project settings. Application-focus-in invokes `_scan_external_changes()`, which unconditionally clears the Tree, creates a root item, and sets hide_root=true. Only afterward does it compare scene/project timestamps. Child items and a visible dialog require changed files; the empty root does not. This matches the main-editor hierarchy and initial root-hiding difference as a hypothesis. [Constructor](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L8597), [focus handler](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L966), [unconditional root creation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L1430).

**ScriptEditor candidate.** Its constructor creates the same dialog/VBoxContainer/Tree shape beneath ScriptEditor, explicitly setting hide_root=true. Confirmed invokes `reload_scripts`. Application-focus-in calls `_test_script_times_on_disk()`, which clears and creates its root before iterating editor tabs, even when no tabs/files require action. Script editing, save-related paths and `reload_open_files()` also invoke this test, so focus is not its sole possible trigger. [Constructor](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/script/script_editor_plugin.cpp#L3787), [focus handler](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/script/script_editor_plugin.cpp#L1445), [unconditional root creation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/script/script_editor_plugin.cpp#L747), [additional calls](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/script/script_editor_plugin.cpp#L2200).

**Predicted allocation pattern, not observed causation:** if both candidate Trees are initially empty, the first qualifying focus-in can leave two root TreeItems. Tree defaults to one column; each cell instantiates a private TextParagraph. That predicts two reachable TreeItems plus two unenumerated TextParagraphs, even with unchanged files and invisible dialogs. Subsequent checks clear/free the old roots before replacement, so this mechanism predicts initial retained growth followed by identity replacement, not an additional four objects on every focus event. [Tree defaults](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.cpp#L6898), [private cell paragraph](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L59), [root replacement lifecycle](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.cpp#L5335).

For a future same-run proof, use the following bounded observations:

1. Resolve each candidate from its live ancestor classes, dialog title, and existing `confirmed` callback target/method descriptors; the callbacks distinguish the two same-titled dialogs. Record actual Tree/dialog IDs and paths under that run's PID. Read connections through `get_signal_connection_list`, storing only primitive IDs/method names. Do not call, emit or replace those handlers. [Signal inspection API](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Object.xml#L680).
2. At baseline and each relevant observation, capture `Tree.get_root()` identity or explicit null, root parent ID, column count, hide_root, bounded root/child text, and dialog visibility. A persistent blank root with no children is different evidence from a new filename child. The present initial Tree-only descriptors do not record whether a root already exists.
3. Record OS application-focus-in/out notifications (2016/2017) with monotonic time, process frame and event ordinal in a bounded primitive log. Application focus includes any window of the instance; a later main-window `has_focus=false` sample can miss a brief intervening event. Window focus signals may supplement this but should not substitute for the application notification. [Application focus semantics](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Node.xml#L1318), [Window focus signals](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Window.xml#L837).
4. Keep a pre-event baseline and capture after notification propagation at a subsequent process boundary. Then join the added root IDs to those same-run Tree descriptors, preserve raw before/after counters and file-state evidence, and check old-root invalidation on later replacements. A handler observer can run before or after sibling handlers, so its timestamp alone is not a completed postcondition. No focus manipulation, internal-method invocation or benchmark warmup change was performed or authorized by this report.

This is a specific, falsifiable lead. It does not prove S77/S78 attribution, identify private TextParagraph IDs, clear leaks, or justify accepting a changed object-count threshold. A clean run without the transition also does not establish its cause.
