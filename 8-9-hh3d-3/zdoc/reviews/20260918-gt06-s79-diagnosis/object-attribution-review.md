# S79 object attribution and diagnostic preflight

2026-09-18, Asia/Saigon. Read-only diagnostic review; no final critic verdict, acceptance, engine launch, tests, runtime/plan edit or commit. Only this report was written. Nested `AGENTS.md` and current tools plan S78 were read. Initial HEAD: `4fcdb0c9a2452a9aa52a5a483d6bdfd4e52c46fd`; status showed existing untracked evidence, no tracked changes, and no Godot/Blender processes were returned by the initial process query. These are point-in-time observations.

## What S77 actually identifies

All 19 raw `studio/.local/reviews/gt06-s77-object-diagnostic-03/project/benchmark/out/object-*.json` SHA256 values match `object-analysis-03.json`. The analysis file's actual SHA256 is `144c159a70d3307e38f8ff63e6f807d30474af5878c86b615e99a335ab0ec78f`; its `analyzer_sha256` field is a different hash, of the analyzer.

The growth first appears at `object-0016.json`, `mono_us=222267786`, batch 5, idle. Previous point 15 at `216693175` has 71123 objects; point 16 has 71127. The reachable census increases 27399→27401 and TreeItems 4491→4493. Exactly two descriptors enter:

| Added TreeItem | Owning Tree ID from relation | Last observed |
|---|---|---|
| `4918324827579` | `737509681388` | Point 18, `237515022` µs |
| `4917821504835` | `646795269124` | Point 18, `237515022` µs |

Neither item is removed or changed in points 17–18. Their owner Tree descriptors are absent from every raw point and analysis: the first census omitted initial identities, and those Trees never emitted a changed descriptor. Consequently their named UI owner/path, column count, text and parent item cannot be recovered from these artifacts. IDs from another process must not be used as an identity join.

Earlier batch boundaries replace 17 TreeItems under Trees `443941938432` and `491169804277` plus one Fixture Node3D, with zero net count change; the idle-growth owners are different. All points retain 104 Trees, 42 RichTextLabels, 496 PopupMenuItems, 21482 nodes, 313 orphan nodes and 6 cached resources. All sampled scan flags are false. Those facts do not establish continuous scanner inactivity or the lifetime of every ObjectDB entry. Only the Output RichTextLabel descriptor was known in S77; its 101 paragraphs do not describe all 42 labels.

## Stronger, still unproven ownership hypothesis

Pinned Godot `TreeItem::Cell` owns a private `Ref<TextParagraph>` and instantiates it in its constructor. Item creation sizes cells to the owning Tree's column count. Thus **two new one-column TreeItems would themselves bring two private TextParagraphs**, naturally matching the observed +4 total/+2 reachable split. This is an inference to check using S79 owner/column data, not a proven identity attribution or explanation of the S78 campaign. Sources: [pinned tree.h](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L59), [pinned item creation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.cpp#L858).

## Smallest useful capture improvements

- Preserve each TreeItem's owning Tree ID/path/visibility, parent-item ID, actual column count and bounded cell text with length/hash/truncation. Emit the initial Tree descriptors even when the rest of the 27k identities are omitted. S79 already implements these fields.
- Also capture bounded parent-item column-0 text/length/hash inline. A parent ID alone can remain unresolved because initial TreeItem descriptors are omitted. Include item ancestry only to a fixed small depth if its text does not distinguish the entry.
- Initial RichTextLabel descriptors allow whole-reachable-label paragraph totals; S79 includes them. Keep the distinction between reachable labels and the full ObjectDB.
- Popup text is a secondary follow-up if the identified Tree path points into a dialog/popup or the residual remains unexplained. Use a bounded descriptor of that owner Window title/visibility or PopupMenu item count and `get_item_text(index)`; do not dump arbitrary metadata/properties or expand all 494 popup menus by default. [Pinned PopupMenu API](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/PopupMenu.xml#L339).
- Emit idle-start and idle-deadline monotonic timestamps to bind the intended 120 seconds directly. Preserve raw normal counters and fail-closed limits; no object subtraction, sample selection, threshold relaxation or asserted leak clearance follows from this review.

## S79 static preflight

Reviewed `diagnose_objects.py`, `object_probe.gd` and `object_task.ps1`. Python AST and PowerShell parser reported no syntax errors without executing either script. All three Python replacement anchors occur exactly once in the current benchmark source. No Godot parser/import/runtime was invoked, so native parse success remains unproven.

The new native APIs and properties are present in the pin: `TreeItem.get_tree/get_parent/get_text` and `Tree.columns/hide_root`. Attached-item traversal is synchronous and uses primitive descriptors; it introduces no retained Object references, timers or awaits. Cell text is capped at 8 columns ×512 characters, preserving real column count/length/hash. Per-cell hash work adds diagnostic overhead; do not use its timing for acceptance. [Pinned TreeItem API](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/TreeItem.xml#L317), [pinned Tree API](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/doc/classes/Tree.xml#L377).

Run/task/output identifiers consistently use S79 diagnostic01 with exclusive output creation. Six batches ×100 cycles plus120 seconds quiet idle are fixed. Native660s < outer720s < scheduler840s; 512 snapshots, 8MiB per point and128MiB total remain fail-closed. During idle the hook bypasses ordinary heartbeat/phase-timeout handling, so the host deadline remains material. Actual native exits, source/binary bindings and cleanup are checked through the existing owner; scheduler status alone is not success. Only the coordinator launches.

**Required analysis adaptation:** S77 `analyze_objects.py` cannot be reused unchanged. It explicitly requires no initial descriptors and hardcodes60/540/600-second contracts. S79 analysis must accept exactly the initial Tree/RichTextLabel allowlist, subtract these initial known IDs from the omitted population before reconstruction, preserve class/count checks, and use120/660/720-second contracts. Initial descriptors are baseline observations, not object births. The probe's new boolean does not itself perform that reconstruction.

Reviewed helper hashes (subsequent edits require a new binding):

| File | SHA256 |
|---|---|
| `diagnose_objects.py` | `feca45738d0ca316332db90c7a90065a2cd9471e3d8a3d170b0b6846afe455ac` |
| `object_probe.gd` | `2647d3044331948ec3cdbed303dc27b84cf1d96d7039e13df4e496c846a1a21b` |
| `object_task.ps1` | `1d34e21d9925038dbae578a508b7c2b9750deb584a6c825e0c3ddadb363b379a` |

No static native-API blocker was found in this reviewed snapshot. GT-06 and S78 acceptance status are unchanged; S77 ownership remains partial until new diagnostic evidence names the two Trees and verifies the residual hypothesis.
