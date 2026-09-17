# GT06 final requirement → test → evidence matrix — DRAFT

Preparation only; **not an acceptance review or verdict**. Authoritative source:
`zdoc/8-9-godot-blender-agent-studio-plan.txt`, revision S70,
`CURRENT_VALID_WP=GT-06`. Observed HEAD:
`a007b21f5b7f630644d45b95be7a4e83cb63e678`, 2026-09-18 Asia/Saigon.
Only this report was written. No tests, engines, source changes, commits or large
raw-tree scan were performed. Paths below are relative to `8-9-hh3d-3/`.

```text
FINAL_CANDIDATE_MANIFEST=PENDING
FINAL_CANDIDATE_SHA256=PENDING
BENCHMARK_ACCEPTANCE=PENDING
INDEPENDENT_CRITIC_A=PENDING
INDEPENDENT_CRITIC_B=PENDING
COORDINATOR_ACCEPTANCE=PENDING
```

`AVAILABLE` below means recorded evidence exists for review under its own hashes,
not that this draft accepts the requirement. Unit methods identify regression
coverage; actual native artifacts supply runtime proof. Final packaging must
resolve each entry to its invoked test/source inventory and raw artifact hashes.

## Current benchmark status

Coordinator addendum after the draft inspection: checkpoint `9bc28b6` corrects
the entrypoint/schema source inventory; `-s70-units-03` records75/75 affected
tests with actual exits0 and stable source. The active candidate is now
`studio/.local/reviews/gt06-s70-campaign-02/` and its sibling `-supervisor/`,
dispatched at2026-09-17T18:25:28Z. Its49-file closure is
`21a17b2a350160efb17950979adada0a2b3e12dbd95e12158833acbe9f233aa0`.
Use those exact completed artifacts for EBENCH if the campaign passes; the
campaign01 references below preserve the originally inspected failed attempt.
Final dataset, package and both acceptance critics remain PENDING.

Scheduler launch1 for `gt06-s70-campaign-01` was requested at
`2026-09-17T18:21:53.1400514Z`. During lightweight inspection, its supervisor had
already written `failure.json` with `BENCHMARK_WRAPPER_EXIT`; `return.json`
reported returned code1 after1.422s and explicitly required scheduler terminal
status/actual exit. These are under
`studio/.local/reviews/gt06-s70-campaign-01-supervisor/`. Dispatch is not a
completion or benchmark result. The coordinator was notified; no launcher or
process action was taken by this reviewer. Later attempts must retain their own
source/task/launch bindings. Do not describe this launch as still running based
only on `task-start.json`.

## Evidence catalog and hash rules

| ID | Exact existing evidence location | Binding required in final package |
|---|---|---|
| E05 | `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`; `zdoc/reviews/20260917-gt05-s64-acceptance/acceptance.json` | Accepted GT05 reference `808d8ba`; manifest hash below. Join producer/edit/import artifacts and actual consumed GLB bytes; do not transfer GT05 signatures to new GT06 source. |
| E65 | `studio/.local/reviews/gt06-s65-native-04/`; `studio/.local/reviews/gt06-s65-repair-02/`; `studio/.local/reviews/gt06-s65-native-05/` | Fault/repair/replay capture anchors below; each `source-files.json`, actual host logs/exits, selected script bytes and `repair-replay.json`. Progress index: `zdoc/reviews/20260917-gt06-s65-progress/runs.json`. |
| E68GUI | `studio/.local/reviews/gt06-s68-reviewer-complete-02/`; `studio/.local/reviews/gt06-s68-reviewer-stop-02/` | Runtime `source-files.json` plus `reviewer-probe/source.json`; actual driver captures copied under `zdoc/reviews/20260917-gt06-s68-progress/captures/`. Native source closure and five-file reviewer closure below. Retain original driver/host logs, not only copied results. |
| E69A | `studio/.local/reviews/gt06-s69-saturated-stop-01/`, `gt06-s69-revoked-result-01/`, `gt06-s69-stale-capture-01/` and each sibling `-outer/` directory | Each `http-adversary/result.json`, checks, source map, import/runtime captures, outer capture/logs and mutation witness. Full file hashes are in E69INDEX. Stale-capture's intentionally mutated PNG must remain identified as negative-test evidence. |
| E69R | `studio/.local/reviews/gt06-s69-managed-replay-01/`; sibling `gt06-s69-managed-replay-01-driver/` | `capture.json`, `repair-replay.json`, runtime snapshot, source map, raw report, seven captures, host exits/Job proof; verified original repair02 receipt and selected-config hash. Managed replay source closure below. |
| E69OWNER | `studio/.local/reviews/gt06-s69-owner-smoke-01/` | Natural/Stop/setup-failure records, capture-v2 wrapper-handle evidence, actual exits and source inventory. This precedes later benchmark/launcher changes; scope reuse to unchanged owner paths. |
| E69INDEX | `zdoc/reviews/20260918-gt06-s69-progress/native-progress.json` | 1124 raw file hashes/sizes across ten roots. Previously independently checked in S69, not rescanned here. Final sealing must preserve/access those raw bytes. `captures/` is a selected copy, not the complete evidence closure. |
| U69 | `zdoc/reviews/20260918-gt06-s69-units-01/`; `zdoc/reviews/20260918-gt06-s69-stop-units-01/` | Each `invocation.json`, `capture.json`, `units-host.json`, stdout/stderr. 434/434 baseline and later66/66 affected coverage have different source inventories; do not sum overlapping tests or relabel the baseline. |
| E70 | `zdoc/reviews/20260918-gt06-s70-resume/evidence-inventory.json` and its `captures/`; complete raw roots named by that inventory | Exact source/request/XML/task hashes; nested legacy/composed diagnostics, scheduler natural/Stop/launch2 probes; actual child/helper/Job/wrapper proof plus terminal scheduler status. Historical probe source is in `probe-source-01/`; do not relabel it after launcher edits. |
| U70 | `zdoc/reviews/20260918-gt06-s70-units-01/` | `invocation.json` with `source_files` and `runner_sha256`, `capture.json`, `units-host.json`, stdout/stderr. Recorded73/73 affected tests, no skips, actual target/helper exits0 and stable listed source. |
| EBENCH | `studio/.local/reviews/gt06-s70-campaign-01/` and its explicitly numbered supervisor directories | **PENDING complete measurements.** Exact final artifact set specified below. An incomplete or failed attempt is preserved but cannot supply partial samples to another run. |

## Requirement matrix

Test paths in this table are under `studio/tests/`. A module reference includes
its exact recorded invocation/source binding from U69/U70 or the earlier linked
package; it does not imply every module was rerun at HEAD.

| ID / plan requirement | Test / actual probe | Evidence and current disposition |
|---|---|---|
| F01 / GT06 vertical slice; accepted dependency | `studio/host/replay/native_runner.py:accepted_inputs`; accepted GT05 producer/consumer checks; `replay/test_repair_replay.py` | E05 + E65 + E69R, **AVAILABLE**. Final join must follow actual Blender edit → validated GLB → Godot import/readback → Play → repair/replay. Existing accepted-input hash checks do not alone substitute for that artifact linkage. |
| F02 / TQ06 fixed60Hz, seed, pressed/held/released and actual menu/input callbacks | `replay/test_trace.py:test_schema_version_and_fps_are_exact`, `test_uint32_seed_edges_and_bool_are_distinct`, `test_default_intent_exercises_ordered_real_key_edges_and_pause_probe`; `replay/test_observation.py:test_input_event_callback_and_real_menu_button_are_required` | E68GUI complete02 `observation-checks.json` and E69R `repair-replay.json`/`project/out/report.json`, **AVAILABLE**. Bind raw authored trace bytes, seed, runtime source/snapshot, command/run IDs and native process identity. |
| F03 / movement/outfit/emote/prop/pause/resume/quit | `replay/test_observation.py:test_interaction_needs_native_hit_and_changed_outfit_emote`, `test_pause_body_animation_and_simulation_changes_rejected`, `test_ui_must_advance_during_pause`, `test_resume_must_advance_simulation`, `test_quit_must_drain_releases_and_captures` | E68GUI complete02 and E69R, **AVAILABLE**: actual1.50000023841858m movement, native interaction, simulation frozen/UI advancing, resume and drained quit. Final transition proof must use post-destination state, not direct state injection. |
| F04 / inspect scene/property/runtime, bounded pages and historical state | `replay/test_inspector.py:test_filter_and_pagination_cover_each_matching_tick_once`, `test_unknown_paths_properties_and_fields_reject_closed`, `test_page_filter_and_cursor_caps_reject_before_output`, `test_cursor_cannot_cross_registered_views_even_for_same_report` | E68GUI `reviewer-probe/result.json`, retained inspection artifacts and U69, **AVAILABLE**. Preserve historical labeling; no claim of arbitrary live runtime mutation/debugging. |
| F05 / bookmarks/camera/capture freshness; TX13 source/PID/window/time | `replay/test_observation.py:test_stale_native_pid_window_or_source_binding_rejected`, `test_capture_request_tick_frame_fence_and_native_frame_binding`, `test_camera_and_png_bytes_not_only_metadata_are_checked`, `test_resealed_late_menu_capture_still_rejects_phase_drift`; stale-capture native adversary | E68GUI/E69R seven named PNGs and report; E69A stale-capture original copy/mutation witness/result, **AVAILABLE**. Hash actual PNG bytes and camera/raw state string; bind native frame/time/identity and report anchor. |
| F06 / actual seeded fault → typed repair → replay | `replay/test_repair_replay.py`; `studio/host/replay/repair.py:verified_fault`; `repair_replay.py:verified_repair`; managed native replay driver | E65 zero-speed fault and authenticated `script_text.replace` receipt; E69R current-runtime replay, **AVAILABLE**. Preserve selected-config SHA and both causal capture anchors. Do not repeat the already-valid repair mutation merely for benchmark-only changes. |
| F07 / perf schema/raw frames/p50/p95/p99/1% low/counters | `replay/test_perf.py` schema identity/missing1%low rejection; `replay/test_perf_export.py:test_missing_readiness_remains_gap`, `test_unavailable_measured_counter_not_filled`, `test_closed_native_counter_semantics`; native export | E65 native04/native05 `perf-export-v1.json`, raw reports/process metrics and corresponding tests, **AVAILABLE diagnostic**. Schema id/version and actual raw-frame/counter definitions required. Screenshot overhead and startup unavailable values remain explicit; this is not EBENCH. |
| F08 / authenticated admission/ACK readback/dedupe/UNKNOWN | `replay/test_service.py:test_start_is_pending_then_commits_only_after_bound_result_and_dedupes_once`, `test_changed_payload_same_pending_id_cannot_poison_original_receipt`, `test_completion_persistence_failure_lookup_is_unknown_without_durable_success`, `test_durable_terminal_wins_if_finish_raises_after_commit`; `test_verified_journal.py`, `test_journal_index.py` | E68GUI plus E69A revoked-result and U69; journal contract `zdoc/reviews/20260917-gt06-s68-journal-contract-03/`, **AVAILABLE**. Retain exact command/lease/grant/source bindings and durable receipts/tombstones; no mock effect presented as native. |
| F09 / section2.6 reviewer UX, keyboard/error/UNKNOWN next action and no hidden resume | `reviewer/test_model.py:test_unknown_and_rejected_keep_safe_next_action_without_automatic_replay`, `test_reconnect_only_lookup_and_server_ready_cannot_reenable_play`; `test_app.py`, `test_client.py`, `test_client_adversarial.py:test_late_committed_play_cannot_overwrite_stop_latch`; real Tk probe | E68GUI complete02/stop02 + U69, **AVAILABLE**. Actual Ctrl+P/Inspect/Capture/Esc and cleanup are native GUI evidence; edge-state unit coverage must remain labeled as such. Telemetry-drop counters do not excuse lost command receipts. |
| F10 / TX02 stale identity/context and reload | `replay/test_inspector.py:test_all_expected_context_components_reject_stale_values`; `test_native_benchmark.py`; actual create/undo/save/reload diagnostic/campaign | E68GUI/E69A + E70 composed native cycle, **AVAILABLE bounded correctness**; full repeated lifecycle measurement in EBENCH **PENDING**. Require same editor PID per run, fresh root/generation, save-signal/disk hash and reload observation; do not clear private state to hide leakage. |
| F11 / TX05 timeout/Stop/PID ownership/cleanup, including owner exceptions | `replay/test_backend.py:test_start_timeout_retains_owner_until_actual_drain`, `test_runtime_exit_pid_must_match_sampler_identity`, `test_log_error_rejects_even_with_clean_captured_exit`; `test_process_probe.py`; `test_benchmark_job_owner.py`; `test_benchmark_stop.py` | E69A saturated-stop, E69OWNER, E70 nested/scheduler probes + U69/U70, **AVAILABLE bounded cases**. Preserve separate natural/forced Stop outcomes and actual Job/handle closure. Link applicable reused accepted runner fault coverage for OOM/disk-full; do not claim every fault was independently injected into the GT06 GUI. Final benchmark ownership remains **PENDING**. |
| F12 / TX18 quotas/congestion/fairness/retention/Stop priority; TX13 isolated Play | `replay/test_transport.py:test_stop_listener_works_with_work_and_control_partial_headers`, `test_stop_isolated_from_blocked_owner_work_lookup_and_slow_control`, `test_body_cap_precedes_auth_body_read_and_owner`; `test_backend.py`; reviewer deadline/retention regressions | E69A saturated-stop/revoked-result/stale-capture + E68GUI + U69, **AVAILABLE for the declared GT06 fixture scope**. Native saturation uses two real held HTTP connections; lookup/Stop stay responsive and reconnect cannot resume. Full multi-project scheduling/cross-app recovery belongs GT07; no new capability claim from this reuse. |
| F13 / tools UX benchmark exact counts, latency/heartbeat/memory/effect limits | `replay/test_benchmark_profile.py`, `test_benchmark_commands.py`, `test_benchmark_assembly.py`, `test_benchmark_campaign.py`; actual complete campaign | EBENCH **PENDING**. Ten process pairs ×35 batches, five warm-up excluded and30 measured each; each batch1000commands at50/30/20 mix plus100 real cycles. Inspect/Stop receipt p95≤500ms; status gap≤2s; RAM growth≤10% against declared warm baseline after10 repetitions; no duplicate/lost effects or steady leaks. Require raw distributions and actual exits/cleanup. |
| F14 / sustained execution and stop-safe final publication | `replay/test_campaign_task.py`; `test_benchmark_campaign_stop_completion.py`; nested-owner A/B; scheduler natural/Stop/launch2 probes | E70 + U70, **AVAILABLE diagnostics**; complete scheduler-launched campaign **PENDING**. Require source/request/XML/principal/launch identity, bounded no-restart configuration, native owner proofs, and terminal scheduler observation. `return.json` alone explicitly cannot prove supervisor process exit. |
| F15 / TQ00 final closure, no orphan requirement, clean logs, source-specific critics | Coverage map and final frozen manifest verification; actual evidence validators; two independent final reviews | **PENDING**. Bind every row to raw evidence and tested dependencies; report any unresolved gap rather than changing acceptance. Two final critics must review the same candidate hash; implementation reviews, unit totals and scheduler dispatch do not count. |

## Exact anchors available for the final manifest

These are small metadata/capture hashes read during this preparation, or retained
causal anchors already recorded by the source-bound packages. They identify
evidence, not acceptance. Complete raw file inventories remain necessary.

```text
S70 plan raw SHA256=c013f6202e3933333f0cc980fc57406797d2d0be4727474e184f05dc908ddb5a
perf-collector.schema.json SHA256=394d1df03bdfd736ea3fe9f260e9d718d35f3820cde35d1c45ccab65fbc24834
E05 manifest SHA256=fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b
consumed GLB SHA256=e85e536137208ba84adbc875b6fb647b5a4e49156344e03e2e8947a7ae91e377
authored trace SHA256=c7d3d949e1aed9e1fc40a458c940640f3f88db9fbb965d669654ba5b58be8fbe
S65 fault capture SHA256=d3469bee92f7decad37d1f937631cff467548c8751f03ca99eac029c7547b7a1
S65 repair02 capture SHA256=514a1f3a01ebab7f6f327a49170e4e9260a55310ee5c84b20c28f6bcf6a0ea14
selected repaired config SHA256=4fe3141b9afe6b411b585b203cebae77e851a406c291ac26620eb8cd7c018d90
E68GUI / E69A declared native-source closure=153926756107745108aa0df1941b6a189a77dd0a814f2424cd24c3a489abed7b
E68GUI reviewer-source closure=7665621f1090836c2bc711ccc7f6857c3961b99be5b077292baaadc933b712fb
E69R capture.json SHA256=d2f4985f75d6017e8ce13078d69973b9c7294a2719748cc978ba0977c0e6d0e5
E69R source-files.json SHA256=b0091dc3e16801af4c8bb39f39da9bb4bfd8b71be66f0ade7dac1e9b522ed11c
E69R declared source closure=491b65875f8246e7606c7b860d9c61d6a85657fc0077075fa6dc7209128dca2b
E69INDEX SHA256=b91aeca785fea3a6397087f1190648fcf7577392bb3c7db2192fcae4f8dca1b1
E70 evidence-inventory.json SHA256=236f25976d39f8121b0bdfbe9e375344591c2d407e5df441860985f39007b034
U70 invocation.json SHA256=40875e3b4a697e9b2699b38e3f0adce290804e6ae6271bd763d160b7c193b1fc
U70 capture.json SHA256=395c33e291175f53ccb52a82a9b62e3db1222e31d4063c927c0d910a53e4bdee
S70 campaign01 campaign.json SHA256=cdba8d953ef4b69fbc26c0e0270ad4ddf1111a309501869e21bff4da7e057584
S70 campaign01 declared source closure (47 files)=55d7a85f2fb43d1ba8b4aa719f89c96c571b5e278c0da4c76df6e5045a1aae1d
S70 campaign01 profile SHA256=0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85
```

Do not mix hash domains: raw file SHA, repository source-closure encoding,
canonical profile bytes and declared runtime snapshot hashes are distinct.
Use each producer/verifier's exact encoding. Do not reserialize native float
values or add a newline to canonical profile bytes when checking a digest.

## Benchmark and review artifacts still required

The following are producer path templates, **not claims that successful files
already exist**. Under `studio/.local/reviews/<accepted-campaign-id>/`, retain
`campaign.json`, `benchmark-profile.json`, frozen `source/`, and every selected
`run-NN-attempt-MM/` with:

- `context.json`, `source-files.json`, `toolchain.lock.json`,
  `benchmark-profile.json` and immutable source/native input snapshots;
- all command/native batch shards, readiness/start/joint/ACK observations and
  their references; preserve full warm-up rows while excluding them from metrics;
- `import-host/capture.json`, `host-owner/capture.json`,
  `editor-host/capture.json`, their raw logs/process-start/process-exit/cleanup
  artifacts, `child-result.json`, `cleanup.json`, `assembly-manifest.json` and
  `run-capture.json`;
- top-level `campaign-capture.json`, strictly assembled `dataset.json` and
  `summary.json`, with one source/toolchain/profile across all ten bound runs;
- exact supervisor launch/request/XML/registration/start/return records and a
  terminal scheduler status bound to that task/instance. A returned code or
  completion banner does not replace real owner exits and released handles.

After successful measurement, seal a final GT06 manifest containing this map's
resolved rows, complete runtime/test/driver/verifier/schema/tool dependencies,
raw artifact references/hashes, limits, source projections and reproducible
commands. Its file path/hash and the two critic report paths remain **PENDING**.
Do not invent signatures or call this draft the final freeze.

The `c5e56c7`→`a007b21` studio changes inspected here are confined to benchmark
owner/assembly/campaign/launcher/diagnostic files and their tests. Functional
replay, observer, fixture, reviewer, schema and repair sources are unchanged by
that commit range. Reuse E68GUI/E69A/E69R on their listed dependencies; do not
rerun them merely because the broad repository/benchmark manifest changed.
Future edits must be checked against the affected lane before reuse.

Final reviewers must keep coverage honest: F11's runner fault cases and F12's
unit/fixture boundaries need explicit existing test links, not blanket claims
that every TX fault was exercised natively. Any truly orphan requirement is a
GAP under TQ00. This draft adds no new native workload and waives none.

GT07–10 remain closed to implementation until their predecessors are accepted.
Physical Android is the later GT08 hard gate; it neither supplies missing GT06
benchmark proof nor requires repeating desktop functional evidence. Public
signing/publication and HH World claims are outside this preparation.
