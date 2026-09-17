# GT06 S75 correction — read-only source preflight

2026-09-18, Asia/Saigon. Initial HEAD: `1dda560c2eb46739cbe5aff69293ec1c6056be6c`. Read `8-9-hh3d-3/AGENTS.md`, the S75 tools-plan summary, GT-06 scope and referenced evidence/benchmark requirements. GT-06 remains IN_PROGRESS. This is a preflight investigation, **not an acceptance critic or TICK verdict**. This reviewer launched no engine or tests, edited no production/test/plan source, and wrote only this report. The coordinator owns the corrections and verification runs described below.

## Result and findings

The original two-file change was appropriately narrow but had two actionable integration defects. Both were reported to the coordinator and are **resolved in the current source by static re-audit**. No further blocker was found in the reviewed diff. This does not establish campaign success or GT-06 acceptance.

1. **Full-run source-set mismatch (original P1).** Native `SOURCE_PATHS` gained `res://benchmark/.gdignore`, while `benchmark_assembly.py:609-612` still required exactly the previous nine entries. A completed corrected campaign would consequently fail `NATIVE_SOURCE_SET` during `assemble_run()`. Updating diagnostic `validate_native()` alone did not update this independent consumer. The coordinator now requires all ten entries in the assembler, binds the marker through `read_artifact()`, and requires its exact raw bytes. The complete synthetic fixture includes the marker; the added negative test rejects a missing index entry and coherently rehashed altered/BOM/CRLF marker bytes. No source entries were made optional.

2. **Decoded text was weaker than the promised byte guard (original P2).** The first implementation compared `FileAccess.get_file_as_string()` with expected text. The pinned engine decodes this with `String::append_utf8()`, which skips a leading UTF-8 BOM; therefore BOM-prefixed marker bytes could pass that native bootstrap check. Existing generator/import drift checks still protected the normal generated baseline, so this was a native exact-configuration check defect, not evidence of a workload bypass. The coordinator replaced it with `get_file_as_bytes()` versus the expected UTF-8 byte array before input parsing or semantic effects. [Pinned FileAccess implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/io/file_access.cpp#L854), [pinned UTF-8 decoder](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/string/ustring.cpp#L1656).

## Scope and invariant checks

- `prepare()` creates one fixed, nonempty 53-byte `benchmark/.gdignore` before import. Its SHA256 is `3d078ee3c08af2f64daca29255d23d366dc0a9bdbef8a872442d5642bfb84cf8`. Only benchmark binding/control/output JSON lives in that subtree. Fixture scene, actor script, installed addon and benchmark plugin remain outside it. There is no asset/resource filtering or engine modification in this diff.
- The marker is included in the generated initial manifest, `project_files()` import snapshot, native `SOURCE_PATHS`, native completion rehash and host immutable/runtime source map. `project_files()` excludes `.godot` and benchmark output as before; it does not exclude the marker. Campaign final project-drift verification retains it. The new assembler independently reads its exact bytes and recorded hash.
- Missing, empty, truncated, BOM-prefixed, CRLF-modified and other changed marker bytes fail the current native byte comparison. Missing/extra native source keys fail the diagnostic/assembly exact-set checks. Mutation after bootstrap is caught by native completion rehash and the host project/source comparisons before completion can be accepted. These are source-path conclusions; this reviewer did not run a native negative matrix.
- `source_files()` now unconditionally binds the actual non-Python `contracts/perf-collector.schema.json` dependency. `host/replay/perf.py` reads that file at import. The full campaign already included it in `CAMPAIGN_FIXED_SOURCES`; adding it to the shared collector fixes diagnostic closure without removing other dependencies.
- Searches of the current replay producer/verifier sources found the two exact native source-set consumers: diagnostic `validate_native()` and full-run `assemble_run()`. Both now agree. Campaign initial/import/runtime/final maps are dynamic and carry the marker without another hard-coded set. Ready/start/joint/ACK paths remain direct file I/O; no loader/import dependency was introduced for ignored JSON.
- The reviewed diffs do not change 10 fresh process pairs, 35 batches, 5 warmups, 30 measured batches, 1,000 HTTP commands, 100 native cycles, PID continuity, ready/start/joint/ACK exchange, semantic readbacks, cap100, source/scene ownership, baseline04, counter/RSS thresholds, 2-second status target, deadlines, Stop handling, full logs, process exits or cleanup gates. `run_benchmark_campaign.py` and `benchmark_profile.py` are unchanged.

## Evidence checked independently

The supplemental `indexed-03` / `ignored-03` arms use `scan_sources`, share base closure `d287a384ec1f65ec7b2e657274eeff3c907cb795c73efd943d2529cf82abf3b9`, and include the actual schema. I rehashed 39/39 preserved base files and 53/53 versus 54/54 declared runtime files: all match. Their preserved runner hash matches `diagnose_editor_files.py`. Indexed objects grow 71056→71132 with 38 new file metadata entries; ignored objects stay 71039→71039 with no added entries. Node identities and paths are unchanged, and both scan generations advance 1→2. Import/editor actual exits are zero, Jobs closed/zero/unretained, and stderr is empty. These are causal supplemental scans with synthetic JSON, not full barrier/workload evidence, and do not explain or exempt the original two extra kernel handles or earlier RSS failures.

`gt06-s75-native-01` preserves the original text-guard source. Its 38/38 preserved source files match closure `7005f0a129688846777e146b85e04a010c8048b11e280171ee6db20f52aa9913`; marker, index, batch and stage-capture hashes match. Editor PID47456/import PID29772 have actual exit0 and clean closed Jobs. Keep this evidence attached to its original hash.

After the guard correction, I independently checked `gt06-s75-native-02`: 38/38 source files match closure `8c5860756d7288714c5d696677d30ddef01ad2bd24b0f6175dc50b8ca5ec1f2e`, including current native source hash below. Capture SHA256 is `44f78186b430040c94a5173ead4857a65cce70160dca3d747cd7b976c420ee74`. Editor PID36144/import PID49440 actual-exit records match their bound captures and report exit0; both stderr files are empty, Jobs closed/zero with no retained handles. Its `host_integrated=false` and `full_benchmark=false` are correct and must remain so. Native02 covers the changed native bootstrap, not full campaign assembly.

## Source snapshot and remaining verification

Final static re-audit observed these SHA256 byte hashes:

| Path under `studio/` | SHA256 |
|---|---|
| `tests/replay/run_native_benchmark.py` | `de46a8bdbd90f83961844f76c5d6a667451d042c3bb19a5e9b6858495ef023e1` |
| `tests/replay/benchmark_native.gd` | `4f78fd09c70de45faf9cfa23fb25b86dc1bb5ab2e461e72b74e0483b172135b5` |
| `tests/replay/benchmark_assembly.py` | `c1c6f67734e5e7feebae109ed7ce7d960fa578a8e1504ec5390c3620c6a65003` |
| `tests/replay/test_benchmark_assembly.py` | `56f39cc9d2a77288fbad10081182cc3f1e364b611224ebbd66fc772bdd254cda` |
| `tests/replay/run_benchmark_campaign.py` (unchanged) | `09f9d6a24c6281193f21c9aa89c48602ac5d70dfe86882fbaf76e8366c66dd6c` |
| `tests/replay/benchmark_profile.py` (unchanged) | `ddbd98583060f791226fca83e275cf01204b37112627383198dcef4ec6f6f233` |

The coordinator is responsible for affected unit results and native negative guard evidence; those runs were not executed or certified by this reviewer. A scan warning on intentional early failure must remain explicitly classified in its raw negative evidence. Native01 cannot be relabeled as the corrected byte-guard source, and neither one-cycle diagnostic establishes ready/start/ACK behavior. Before acceptance, freeze the corrected complete campaign closure, preserve fresh identities, obtain the unchanged full workload and actual exits/cleanup, and commission the required two independent acceptance critics on the same final hash. The earlier failed campaigns remain failed.
