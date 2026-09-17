# GT06 S75 — review of indexed/ignored diagnostic v1

Read-only supplemental review, 2026-09-18 Asia/Saigon. No engine/test/task action, production edit, old-raw modification or commit by this reviewer. This is an implementation investigation, **not an acceptance critic or TICK verdict**. Only this review file is written for this follow-up.

## Assessment

The paired experiment directly demonstrates the proposed FileSystem-dock mechanism in the disposable fixture. Thirty-eight newly indexed JSON files produce exactly38 new file TreeItems and76 whole-editor Objects; putting the benchmark evidence directory behind a predeclared `.gdignore` removes both increases. All live Node IDs/paths and all RichTextLabel paragraph counts remain unchanged within each arm. The experiment supports a minimal fixture correction in `prepare()` that writes a nonempty, hash-bound `benchmark/.gdignore` before import and verifies it in native bootstrap. It does **not** establish that the original campaign's extra38 Objects were exactly19 discovered files, explain its two extra kernel handles, or prove the corrected complete campaign will pass.

## Inputs and independently checked results

All paths here are relative to `8-9-hh3d-3/`:

- Preserved driver: `zdoc/reviews/20260918-gt06-s75-recovery/diagnose_editor_files-v1.py`, SHA256 `353b7b2b6b2eafd7ac51df25f1760aea6fb602c7dac96d4f496b280202a2fe59`. It matches both original `diagnostic.json` runner hashes. The working `diagnose_editor_files.py` has since changed; its new bytes are not assigned to these old runs.
- Raw roots: `studio/.local/reviews/gt06-s75-editor-files-indexed-01/` and `studio/.local/reviews/gt06-s75-editor-files-ignored-01/`.

| Observed property | Indexed01 | Ignored01 |
|---|---:|---:|
| New synthetic JSON files, independently counted | 38 | 38 |
| ObjectDB before → after | 71056 → 71132 | 71042 → 71042 |
| Total TreeItems before → after | 4497 → 4535 | 4491 → 4491 |
| FileSystem main tree before → after | 22 → 60 | unchanged |
| Nodes before → after | 21482 → 21482 | 21482 → 21482 |
| Node ID sets / paths | identical | identical |
| RichTextLabel paragraph-count changes | none | none |
| Cached resources | 6 → 6 | 6 → 6 |
| Scan generation | 1 → 2 | 1 → 2 |
| Native editor PID / captured exit | 2892 / 0 | 32092 / 0 |
| Import PID / captured exit | 46552 / 0 | 16676 / 0 |
| Job closed / zero / retained handle | true / true / false | true / true / false |

The sole tree with a net item-count increase is the FileSystem dock's main `Tree@6430`. Its metadata additions are precisely ten `benchmark/out/ready-00..09.json`, ten `benchmark/input/start-00..09.json`, nine `benchmark/input/ack-00..08.json`, and nine `benchmark/out/batch-01..09.json`. They match all38 actual files containing `{"diagnostic_only":true}`. There is no growth elsewhere in the captured TreeItem totals. The unchanged Node identity set is stronger than a merely equal Node count.

This matches the pinned source mechanism: FileSystemDock creates each file item, and a one-column TreeItem includes one TextParagraph object through its cell constructor. See [FileSystem tree creation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/docks/filesystem_dock.cpp#L315), [TreeItem/cell declarations](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L48), and [cell construction](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/gui/tree.h#L131). The census does not directly enumerate every RefCounted object, but the measured +38 items/+76 Objects agrees with this independently read implementation.

I checked all38 preserved base-source hashes and all52 indexed/53 ignored declared runtime hashes against the corresponding preserved files: no mismatch. Both arms share declared base closure `0b44219e1e5b09e471b835bcc76df0ea2cbf024ebc85e3ead32677644c48bdd9`; the generated runtime maps correctly differ. Exact hashes of each capture's declared log/process artifacts also match. Captured stderr is empty, and full stdout has no tested WARNING/ERROR/leak/failure markers. Editor wrapper process handles are recorded closed/unretained.

## Experiment and evidence limits

1. **Dependency closure is incomplete in v1.** The38-file base map contains `host/replay/perf.py` but no schema. That module reads `contracts/perf-collector.schema.json` at import. The v1 driver conditionally probes nonexistent `host/blender/cli-protocol.schema.json`; it does not bind the actual schema. Matching all declared hashes therefore does not mean complete dependency provenance. Preserve v1, add the actual schema unconditionally with an existence/read/hash check, and use fresh run IDs. Do not repair old manifests with today's bytes.
2. **Full scan is a deliberate intervention.** V1 uses `EditorFileSystem.scan()`, not the `scan_sources()` API bound to `scan_changes()` used by application focus-in. The experiment proves indexing can create this retention; it does not reproduce the exact original trigger. A fresh `scan_sources()` pair is the useful next check. Never relabel full-scan evidence as a focus-event test. [Pinned focus path](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/editor_node.cpp#L1049).
3. **One semantic cycle and synthetic payloads.** The native driver completes one diagnostic create/undo/save/reload cycle before the probe. The38 additional files have real campaign naming/topology but deliberately do not have valid command/barrier payloads. This establishes the indexing mechanism, not full ready/start/joint/ACK behavior,100-cycle batches,35-batch runs, or10 fresh-process runs. The native index/COMPLETE marker precedes the separate probe and remains diagnostic-only.
4. **No OS measurement in v1.** Process exits and released owner handles show successful cleanup; they are not in-run editor handle-count/RSS samples. Nothing here explains or exempts original566→568 kernel handles or previous RSS failures. Supplemental owned-editor telemetry must be bound to PID/start/source and its own exact implementation/dependencies; preserve the original gate and sampling rule.
5. **Census sealing is separate.** Owner capture artifacts bind stdout/stderr/process records, not `census/before.json` or `census/after.json`. The native completion marker says only38. The current raw census is inspectable and hashed below, but its bytes require a supplemental inventory for a sealed review package. A new diagnostic can emit exact census size/SHA256 from native readback and bind those markers; do not fabricate such receipts retroactively.
6. **Bounded observation, not stabilization.** V1 waits for a changed generation, `is_scanning()==false`, and a fixed settling interval with an8-second scan deadline. It does not loop until counters fall to baseline. This is appropriate causal probing. Node/TreeItem rows retain primitive values rather than persistent object references, and census writes are outside `res://`, avoiding recursive asset-index growth. Census extraction records only column0 and does not provide a whole ObjectDB class census; retain those scope limits.

## Proposed minimal production change

Adding exactly one nonempty `benchmark/.gdignore` through `run_native_benchmark.prepare()` before import is reasonable. That subtree contains the benchmark's fixed binding/control/evidence JSON, not fixture scripts/scenes/assets. The stock scanner skips a directory containing `.gdignore`; direct native FileAccess remains the access path for these JSONs. [Pinned scanner rule](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp#L3502).

Keep this narrowly scoped and explicit:

- Pin exact file bytes/hash in the generator and include it in initial project, import snapshot, runtime source and native `SOURCE_PATHS`/finish checks. Verify its exact expected bytes/hash before the first semantic effect; missing or changed bytes should fail bootstrap. Mere presence is weaker than the existing freeze contract.
- Preserve every original JSON publication/readback, size/hash/schema check, command count, native cycle, barrier, complete stdout/stderr, cap100, counter value, baseline04,5+30 batch structure,10-process requirement and deadline. Do not subtract TreeItems or suppress logs, reset histories or add new sampling delays.
- Verify the ignored subtree still permits a real normal benchmark binding to load and a fresh host/native ready/start/ACK exchange. V1's one-cycle diagnostic does not exercise those full-mode barriers. Verify missing/altered ignore guards separately before effect.
- Freeze a new source/configuration closure. The old failed attempt stays failed and is not reinterpreted as a PASS. The original S73 implementation and its signatures/evidence must not be assigned to new configuration bytes. Affected evidence needs new identities; unchanged dependencies may retain their existing provenance mapping.
- Run the entire unchanged acceptance workload after targeted verification. Any kernel-handle, ObjectDB or RSS increase remains a failure requiring explanation/fix. The targeted mechanism fix cannot provide a counter exemption or acceptance itself.

## Exact census/result hashes

SHA256 of original bytes; `indexed/` and `ignored/` denote the raw roots above.

| File | SHA256 |
|---|---|
| indexed/diagnostic.json | `3929a45d712e170d4c1b0e47b5269e456458a608b9e758ae0181eb9d593be755` |
| indexed/result.json | `948457a19e3720dc7c203cdae823e6cc6b03b4eacbe0ddca65d2aacfa7a80588` |
| indexed/census/before.json | `bb1ccbb276a719e740811cdc11a9692179a0120909c12563d9e2e2cd70ea9923` |
| indexed/census/after.json | `553e74dcebe59ef0962f0556a9414bef7784c32977eccae5e858ca44dd356dce` |
| indexed/editor-host/capture.json | `b45dd58215fdb587b3d2e6f509e00ad5416eaa245b481d6ffc8ca591201c68b2` |
| ignored/diagnostic.json | `39c62239d72c8d856a43137889a30220b0420e6ce66fd4c71b2b9bafff603a65` |
| ignored/result.json | `d7696b529b84f463358c24d6ab44582586e88038c65dfb1460dafb2feb74df82` |
| ignored/census/before.json | `24b02dd243a715b867135577f83030cc177b585f32ad95e33d75784ac7cc62fc` |
| ignored/census/after.json | `b80423fa55e905a573105f6a8e03f31fa23fd0da207b1415f027c88be9220a91` |
| ignored/editor-host/capture.json | `372ca46fb50ecf202482450975507c3e9bec0e9cc24c08b04d0ce4898fece19c` |
