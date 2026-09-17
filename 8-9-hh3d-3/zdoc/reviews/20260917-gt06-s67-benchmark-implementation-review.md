# GT06 S67 benchmark implementation review

Review time: 2026-09-17 14:36:37 UTC / 21:36:37 Asia/Saigon.

This is a bounded implementation review, not an acceptance critic verdict. No TICK decision, plan change, source edit, or engine launch was performed. Authority is the S67 tools plan, `CURRENT_VALID_WP=GT-06`; GT01–05 remain accepted. The only authored file is this report. Workspace HEAD at inspection was `843e6816935958406b7439340fd81b9f37c89f63`.

## Findings

### P1 — Normalize the generated project configuration before freezing its runtime hash

Locations: `studio/tests/replay/run_native_benchmark.py:127–142, 314–327`; downstream checks at `224–226, 355–357`.

`prepare()` changes the accepted minimal fixture config only by adding the benchmark plugin. The GUI editor normalizes that config, including `config/features=PackedStringArray("4.7")`, before the benchmark's `_boot()` source snapshot. The host freezes the pre-GUI bytes in `editor-snapshot.json` and `runtime_source`, so a correct native cycle is rejected by the immutable-source guard.

Confirmed from the coordinator's existing diagnostic-01 artifacts (read only):

- Frozen `project.godot`: `7f1e2e42a4b480eff5450d312d39064198183d36e267ab351904277266e115da`.
- Native index and final config: `a1f2cfce445bedf4b6bc7709ca1d6d57616e2e1e9ffdc9f17132a4b172372fe9`.
- This was the only mismatch among the editor host's declared source files.
- PID 43252 produced the native completion marker, exited 0, and naturally drained its owned tree. `editor-host/capture.json` correctly records `completed=false`, `failure=STAGE_SOURCE_CHANGED`, and a closed, untainted Job with zero active processes.
- The native index already contains the normalized hash. Therefore the mutation occurred before native source capture, rather than being attributable solely to editor shutdown. Even if the stage guard were bypassed, `validate_native()` rejects the different index/snapshot source hashes with `DIAGNOSTIC_NATIVE_SOURCE`.

Prepare the exact canonical configuration for this pinned editor, or introduce a separately captured, bounded normalization stage before freezing measurement bytes. Keep the accepted fixture factory unchanged and keep `project.godot` immutable during measurement. Do not make the config an unchecked mutable path or remove the source guard. Preserve diagnostic-01 as failed and use a fresh run ID after the fix.

### P2 — Validate the save-signal and reload-observation fields in raw timing evidence

Locations: `studio/tests/replay/run_native_benchmark.py:246–256`; producer fields at `studio/tests/replay/benchmark_native.gd:364, 393`.

The native driver correctly waits for one `scene_saved` callback and fresh root/generation readback. Its raw timing row records `save_signal_mono_us` and `reload_observed_process_frame`, but the host validator never requires or reads either field. It also leaves the containing timing-row shape open. Consequently the exported timing evidence can omit the callback proof, or carry impossible callback ordering, while passing the semantic validator.

A read-only in-memory probe reused diagnostic-01's actual raw batch, process metrics, source snapshot and exit record. It adjusted only the known config hash mismatch in a detached snapshot to isolate this finding; no files were changed. It recomputed the detached batch reference for each case and called `validate_native()`:

| Detached case | Result |
|---|---|
| Original timing row after isolating the config mismatch | Accepted |
| Remove both `save_signal_mono_us` and `reload_observed_process_frame` | Accepted |
| Set `save_signal_mono_us = reload.end_us + 999999` | Accepted |

Require the exact timing-row field set, safe integer types, `save.start_us <= save_signal_mono_us <= save.end_us <= reload.start_us`, and a positive reload observation frame preceding the retained batch memory frame. Apply equivalent validation when integrating the full-mode raw shards. This finding concerns semantic evidence validation, not a claim that diagnostic-01 fabricated its actual signal; its original signal timestamp is consistent with the native implementation.

## Lifecycle and boundary observations

- `benchmark_plugin.cfg` points to the intended `@tool EditorPlugin`. The existing diagnostic's engine output demonstrates that these sources parsed and executed; no compile failure was observed.
- Create and undo call the unchanged accepted adapter's `apply_projection()` with unique run/batch/cycle command IDs, current generation/revision, and fixed payloads. The driver checks semantic readback after both operations.
- Reload uses `EditorInterface.reload_scene_from_path()`. The driver requires a different root instance, a later `adapter_ready`, exactly one generation increment, baseline semantic equality, and unchanged saved bytes. This matches accepted `plugin.gd:36–49`: a new root creates a new `SceneCommands` instance and increments generation. It does not reset generation or clear private receipt tables. Diagnostic-01 records generation 1→2 and distinct root IDs.
- Save is not accepted solely on `save_scene()==OK`: the driver enters `SAVE_WAIT` before the call and waits for the matching signal, then hashes disk bytes and verifies them after reload. Its host parser gap is described above.
- No benchmark calls were found that clear UndoRedo history, write the adapter's private generation/receipt/Stop state, invoke request-selected methods, or launch child processes. `_adapter.get("_generation")` in the host barrier is a private read, not a reset. Active accepted-adapter IPC is rejected at initialization, and the trusted stage isolates HH/Godot launch environment variables.
- Full-mode host barriers are fixed-path, hash/run/profile/deadline bound; the next batch waits for the current ACK, including the final batch. Root/generation are checked while waiting, semantic/disk state is checked before acceptance, and ACK bytes are rehashed immediately and again at finish. No host clock is compared to the native-clock deadline. These are static observations; diagnostic mode intentionally does not exercise host barriers.
- The Python entry point is explicitly a one-cycle diagnostic. Missing full campaign results are not a finding against this implementation review. Repeated lifecycle cleanup and full-mode barrier behavior still need their planned runtime validation; this review does not infer those outcomes from one cycle.

## Reviewed hashes and existing evidence

Paths are relative to `8-9-hh3d-3/`.

| File | SHA256 |
|---|---|
| `studio/tests/replay/benchmark_native.gd` | `826976c8ac94e82e618733eb781e6743809d1860c55253587b306a8e1ecce7f0` |
| `studio/tests/replay/benchmark_plugin.cfg` | `648d8821a36d0abc825ef1f380b4917639074302a619cb25a798df987a5a1092` |
| `studio/tests/replay/run_native_benchmark.py` | `43faa9f2b7bf207e2c6639d902e47509e349a3c734ebeb75fa2adf1bf6a85753` |
| `studio/.local/reviews/gt06-benchmark-diagnostic-01/source-files.json` | `3446080d6c053a563f32a40572e3712052ca686df5e5d2486acef0cfbde75530` |
| `studio/.local/reviews/gt06-benchmark-diagnostic-01/editor-host/capture.json` | `7d6f2e13f26a960699535ee81c95ae966006e78cb9ede14dbacc89c2950d7103` |
| `studio/.local/reviews/gt06-benchmark-diagnostic-01/project/benchmark/out/index.json` | `c9aa6550b24d955bce118f6cdb801c04814cc9b7d593ba6602922f394cc4294a` |

Inspection also covered the nested AGENTS, current GT06 plan/UX benchmark contract, accepted `fixture_profile.py` and source pins, accepted adapter lifecycle/semantic operations, trusted native Job source checks and cleanup, process sampler, and the benchmark profile's consumer shape. No accepted dependency was modified or reopened.
