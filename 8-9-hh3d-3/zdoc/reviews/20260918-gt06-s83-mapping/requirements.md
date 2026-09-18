# S83 GT-06 full F01–F15 requirement → test → evidence mapping

AUTHORITY=0. PREPARATION_ONLY=1. FORMAL_ACCEPTANCE=false. Paths are relative to `8-9-hh3d-3/`. This expands the generic five-row S81 draft; it is not the final seal or an independent critic.

**Current target:** source `b3862a10`, benchmark runtime51 / `e010180a1bf85b7f565e9aa39734f8551caf170a85b36c50598be556b723ce7f`; profile `0cd5b53055853b592d4376a6b8a89d69c70ea5facc40dfc25ebd6fcd6dbf4d85`. GT-06 remains IN_PROGRESS. Current identities are declared metadata; no source/raw package rehash or engine/test was performed.

**Boundary:** current-source reuse means exact declared lane dependencies according to DEP81. It does not mean historical artifacts were produced on this benchmark closure, nor that broad S79-453/U69/U79 snapshots equal current source. All raw IDs/hashes and causal anchors stay original.

**Measured outcome:** S81 campaign01 FAILED at batch15 with ObjectDB71128→71130,16 captures and zero complete runs. Preserve its failure packet. Fresh full campaign, final source/artifact seal and two new same-manifest critics remain open.

## F01 — First tool vertical slice: Blender edit to GLB/import to real Play and repair/replay

Plan: `GT-06 BUILD`, `TQ00`. **AVAILABLE_SCOPED_FINAL_CHAIN_JOIN_OPEN**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/host/replay/native_runner.py:accepted_inputs`
- `studio/tests/replay/test_repair_replay.py`

Concrete evidence paths:

- `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`
- `zdoc/reviews/20260917-gt05-s64-acceptance/acceptance.json`
- `studio/.local/reviews/gt06-s65-native-04/capture.json`
- `studio/.local/reviews/gt06-s65-repair-02/capture.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/repair-replay.json`
- `studio/.local/reviews/gt05-validation-s62-01/fixture.glb`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/input/fixture.glb`
- `studio/.local/reviews/gt06-s69-managed-replay-01/runtime-snapshot.json`


Catalog/source scopes: E05, E65, E69R, DEP81. Reuse accepted asset and original repair/replay chain. Final seal must resolve Blender edit/producer->consumed GLB->import/readback->Play->repair02->S69 replay with exact original artifacts/IDs. No rerun absent changed dependencies.

## F02 — 60Hz real menu/play/input with pressed/held/released and seed

Plan: `GT-06 VERIFY`, `TQ06`. **AVAILABLE_DEPENDENCY_SCOPED**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_trace.py:test_default_intent_exercises_ordered_real_key_edges_and_pause_probe`
- `studio/tests/replay/test_observation.py:test_input_event_callback_and_real_menu_button_are_required`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s69-managed-replay-01/repair-replay.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/report.json`
- `studio/.local/reviews/gt06-s79-reviewer-complete-01/reviewer-probe/result.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/input/trace.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/invocation.json`


Catalog/source scopes: E69R, E79, U69, DEP81. Reuse original native reports/traces and real callback checks; bind seed17/60Hz/key edges and source/PID/run IDs in final seal. No affected source delta shown for these lanes.

## F03 — Move, outfit/emote/prop, pause/resume/quit; frozen simulation with responsive UI

Plan: `GT-06 BUILD/VERIFY`, `TQ06`, `TX13`. **AVAILABLE_DEPENDENCY_SCOPED**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_observation.py:test_pause_body_animation_and_simulation_changes_rejected`
- `studio/tests/replay/test_observation.py:test_ui_must_advance_during_pause`
- `studio/tests/replay/test_observation.py:test_quit_must_drain_releases_and_captures`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/report.json`
- `studio/.local/reviews/gt06-s79-reviewer-complete-01/reviewer-probe/result.json`
- `studio/.local/reviews/gt06-s79-http-complete-01/capture.json`

Catalog/source scopes: E69R, E79, U69, DEP81. Reuse post-phase native movement/interaction/pause/resume/quit evidence. Final join retains simulation tick/body freeze and advancing UI; fixture-only, no HH World claim.

## F04 — Bounded scene/property/runtime inspection and historical pages

Plan: `GT-06 BUILD`, `section2.6`. **AVAILABLE_DEPENDENCY_SCOPED**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_inspector.py:test_filter_and_pagination_cover_each_matching_tick_once`
- `studio/tests/replay/test_inspector.py:test_page_filter_and_cursor_caps_reject_before_output`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s79-reviewer-complete-01/reviewer-probe/result.json`
- `zdoc/reviews/20260918-gt06-s69-units-01/units-stderr.txt`

Catalog/source scopes: E79, U69, DEP81. Reuse S79 real Inspect/Capture plus U69 bounded view/pagination negatives. Historical state inspection remains labeled historical; no arbitrary runtime mutation/debugger claim.

## F05 — Bookmarks/camera/capture bind actual source, PID/window, frame and time

Plan: `GT-06 VERIFY`, `TQ06`, `TX13`. **AVAILABLE_DEPENDENCY_SCOPED**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_observation.py:test_stale_native_pid_window_or_source_binding_rejected`
- `studio/tests/replay/test_observation.py:test_capture_request_tick_frame_fence_and_native_frame_binding`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/report.json`
- `studio/.local/reviews/gt06-s79-stale-capture-01/http-adversary/result.json`
- `zdoc/reviews/20260918-gt06-s79-diagnosis/service-remint-01/verification.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/menu.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/moved.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/interact.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/paused_a.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/paused_b.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/resumed.png`
- `studio/.local/reviews/gt06-s69-managed-replay-01/project/out/camera.png`


Catalog/source scopes: E69R, E79, U69, DEP81. Resolve seven original PNGs through report/inventory, native frame/time/camera/PID/source binding, and stale-capture original/mutation witness/rejection. Preserve deliberately corrupted PNG; do not reinterpret it as positive output.

## F06 — Seeded fault observed, typed authenticated repair, fault absent on replay

Plan: `GT-06 BUILD`, `TQ06`. **AVAILABLE_CAUSAL_HISTORICAL_PLUS_DEPENDENCY_EXACT_REPLAY**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_repair_replay.py`
- `studio/host/replay/repair_replay.py:verified_repair`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s65-native-04/capture.json`
- `studio/.local/reviews/gt06-s65-repair-02/capture.json`
- `studio/.local/reviews/gt06-s69-managed-replay-01/repair-replay.json`
- `studio/.local/reviews/gt06-s65-repair-02/fault-binding.json`
- `studio/.local/reviews/gt06-s65-repair-02/request.json`
- `studio/.local/reviews/gt06-s65-repair-02/response.json`
- `studio/.local/reviews/gt06-s65-repair-02/native-readback.json`
- `studio/.local/reviews/gt06-s65-repair-02/repair.json`
- `studio/.local/reviews/gt06-s65-repair-02/selected-config.gd`
- `studio/.local/reviews/gt06-s65-repair-02/selected-manifest.json`


Catalog/source scopes: E65, E69R, DEP, DEP81. Keep S65 zero-speed fault/typed script_text.replace repair02 receipt and selected-config hash, then dependency-exact S69 managed replay. S65 is not current-native; no need to repeat valid repair merely for changed benchmark files.

## F07 — Versioned raw frame-ms/perf counters, p50/p95/p99 and exact1%low

Plan: `GT-06 perf contract/VERIFY`, `TQ06`. **AVAILABLE_HISTORICAL_NATIVE_CURRENT_COLLECTOR**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_perf.py:test_type7_and_one_percent_goldens`
- `studio/tests/replay/test_perf.py:test_required_identity_and_low_fields`
- `studio/tests/replay/test_perf_export.py:test_closed_native_counter_semantics`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s65-native-04/perf-export-v1.json`
- `studio/.local/reviews/gt06-s65-native-05/perf-export-v1.json`
- `zdoc/reviews/20260918-gt06-s79-diagnosis/s80-dependency-bridge.json`

Catalog/source scopes: E65, DEP, U69, SRC81. Reuse historical S65 native/perf exports only within original runtime. Three collector files matched in DEP; schema stays current in SRC81. Resolve export raw frames/schema/counter unavailable markers; performance campaign still open.

## F08 — Admission/readback/dedupe and durable UNKNOWN; no fabricated ACK

Plan: `section2.2`, `section2.6`, `TQ00`. **AVAILABLE_SERVICE_DEPENDENCY_SCOPED_BENCHMARK_SUPPLEMENTAL**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_service.py:test_start_is_pending_then_commits_only_after_bound_result_and_dedupes_once`
- `studio/tests/replay/test_service.py:test_completion_persistence_failure_lookup_is_unknown_without_durable_success`
- `studio/tests/replay/test_index_faults.py`
- `studio/tests/protocol/test_transport_observation.py:test_copied_call_preserves_accepted_wire_and_error_behavior`
- `studio/tests/protocol/test_transport_fault_lock.py:test_durable_pending_ack_arrives_while_terminal_persistence_holds_host_lock`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s79-revoked-result-01/http-adversary/result.json`
- `zdoc/reviews/20260918-gt06-s79-diagnosis/index-checks-01/invocation.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/unit-stderr.txt`
- `zdoc/reviews/20260918-gt06-s81-admission/http-probe/result-02/capture.json`

Catalog/source scopes: E79, U79, U81, H81, DEP81. S79 is current dependency-exact service evidence; U79/U81 replace changed U69 service/index coverage. H81 isolates new benchmark transport and proves only one instrumented HTTP batch. Full benchmark consumers need fresh complete campaign.

## F09 — Reviewer keyboard/error/UNKNOWN next action; human Stop survives reconnect

Plan: `GT-06 CONTRACT/VERIFY`, `section2.6`. **AVAILABLE_DEPENDENCY_SCOPED**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/reviewer/test_model.py:test_unknown_and_rejected_keep_safe_next_action_without_automatic_replay`
- `studio/tests/reviewer/test_client_adversarial.py:test_late_committed_play_cannot_overwrite_stop_latch`
- `studio/tests/reviewer/run_reviewer_probe.py`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s79-reviewer-complete-01/reviewer-probe/result.json`
- `studio/.local/reviews/gt06-s79-reviewer-stop-01/reviewer-probe/result.json`
- `zdoc/reviews/20260918-gt06-s69-units-01/units-stderr.txt`

Catalog/source scopes: E79, U69, DEP81. Reuse S79 UI5/backend174 actual keyboard/buttons plus unit edge states. Preserve Stop latch/UNKNOWN next action/reconnect denial; no unit outcome promoted to native fault proof.

## F10 — Resolve native identity after reload; source-bound startup receipt before measured work

Plan: `TX02`, `TQ00`, `GT-06 schema compatibility`. **AVAILABLE_READINESS_SCOPED_FULL_REPEATED_LIFECYCLE_OPEN**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_native_benchmark.py:test_missing_old_or_late_startup_receipt_rejected`
- `studio/tests/replay/test_benchmark_readiness.py:test_source_scene_root_revision_or_bytes_drift_rejected_at_each_point`
- `studio/tests/replay/test_benchmark_readiness.py:test_setup_after_batch_or_ready_and_short_settle_rejected`

Concrete evidence paths:

- `zdoc/reviews/20260918-gt06-s80-readiness/verification.json`
- `zdoc/reviews/20260918-gt06-s80-readiness/campaign-closure-binding.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/invocation.json`
- `zdoc/reviews/20260918-gt06-s81-admission/native-cleanup-probe/evidence/verification.json`

Catalog/source scopes: U80, E80N, U81, C81, SRC81, FAIL81. Reuse bounded readiness behavior at original bindings; C81 reaches READY but has zero native cycles. Fresh complete campaign must supply source-bound index1.3.0 startup and every cycle/reload/identity/postcondition over10x35; no OS-focus or private-state-reset claim.

## F11 — Timeout/OOM/disk failures/Stop/PID identity preserve diagnostics and exact owned cleanup

Plan: `TX05`, `TQ00`. **AVAILABLE_SCOPED_FAULTS_CURRENT_CLEANUP_SUPPLEMENT_FULL_SUCCESS_OPEN**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/pipeline/test_native_job.py:test_actual_short_deadline_kills_only_owned_job`
- `studio/tests/replay/test_backend.py:test_runtime_exit_pid_must_match_sampler_identity`
- `studio/tests/replay/test_service.py:test_stop_persistence_failure_still_latches_runtime_and_work_admission`
- `studio/tests/replay/test_campaign_terminal_cleanup.py`
- `studio/tests/replay/test_campaign_terminal_cleanup.py:test_actual_exit_receipt_is_pid_bound_and_not_a_helper_exit`

Concrete evidence paths:

- `studio/.local/reviews/20260917-gt04-s60-matrix/ipc/oom.json`
- `studio/.local/reviews/gt05-units-s64-02/unit-stderr.txt`
- `studio/.local/reviews/gt06-s79-http-stop-01/runtime-host/capture.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/unit-stderr.txt`
- `zdoc/reviews/20260918-gt06-s81-admission/native-cleanup-probe/evidence/verification.json`
- `zdoc/reviews/20260918-gt06-s82-failure/terminal-facts.json`

Catalog/source scopes: FAULT, U69, U79, E79, U81, C81, FAIL81. Reuse shared accepted S60/S64 and current S79 consumers; U81/C81 cover new terminal-cleanup path with explicit forced-path/missing-receipt limits. Fresh successful campaign must prove actual natural target/helper exits and released ownership. Never substitute helper/scheduler code for missing exit.

## F12 — Bounded queues/results/memory, Stop priority, no retry amplification/UI starvation

Plan: `GT-06 CONTRACT/VERIFY`, `TX18`, `section2.6`. **AVAILABLE_SINGLE_RUNTIME_SCOPE_FULL_METRICS_OPEN**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_transport.py:test_stop_isolated_from_blocked_owner_work_lookup_and_slow_control`
- `studio/tests/replay/test_session.py:test_budget_is_finite_without_eviction_and_stop_still_works`
- `studio/tests/reviewer/test_app.py:test_receipts_are_retained_until_taken_and_work_cannot_flood_mailbox`
- `studio/tests/protocol/test_transport_observation.py:test_copied_call_preserves_accepted_wire_and_error_behavior`

Concrete evidence paths:

- `studio/.local/reviews/gt06-s79-saturated-stop-01/http-adversary/result.json`
- `zdoc/reviews/20260918-gt06-s70-resume/fault-coverage-links.md`
- `zdoc/reviews/20260918-gt06-s79-diagnosis/index-checks-01/invocation.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/invocation.json`

Catalog/source scopes: FAULT, U69, U79, E79, U81, H81. Reuse native saturated Stop and bounded quota/retry/UI tests. Full metrics remain F13. General multi-project fairness and recovery remain GT07; physical wire cuts and disk exhaustion are not invented new gates.

## F13 — Fixed UX/performance workload and latency/status/memory/effect limits

Plan: `section4 UX benchmark contract`. **OPEN_FAILED_CAMPAIGN_REQUIRES_FRESH_COMPLETE_MEASUREMENT**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_benchmark_profile.py`
- `studio/tests/replay/test_benchmark_assembly.py`
- `studio/tests/replay/test_benchmark_campaign.py`
- `studio/tests/protocol/test_transport_observation.py:test_copied_call_preserves_accepted_wire_and_error_behavior`

Concrete evidence paths:

- `zdoc/reviews/20260918-gt06-s81-admission/repair-source.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/capture.json`
- `zdoc/reviews/20260918-gt06-s82-failure/completeness-and-screen.json`
- `zdoc/reviews/20260918-gt06-s82-failure/package-manifest.json`

Catalog/source scopes: U80, SRC81, U81, H81, C81, FAIL81, BENCH. Resolve ObjectDB growth on measured source without relaxed gates; freeze any repair and remint10 fresh pairs x35 batches. S81 has16 captures and zero completed runs. H81/C81/S82 attribution/native-only probes and S80/S81 prefixes are excluded from dataset.

## F14 — Sustained campaign ownership, Stop and terminal publication retain actual exits

Plan: `TQ00`, `TX05`, `TX13`, `section4 UX benchmark contract`. **OPEN_SUCCESSFUL_CAMPAIGN_TERMINAL_PROOF**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/test_campaign_task.py`
- `studio/tests/replay/test_benchmark_campaign_stop_completion.py`
- `studio/tests/replay/test_campaign_terminal_cleanup.py`

Concrete evidence paths:

- `zdoc/reviews/20260918-gt06-s70-resume/evidence-inventory.json`
- `zdoc/reviews/20260918-gt06-s81-admission/checks-02/invocation.json`
- `zdoc/reviews/20260918-gt06-s82-failure/terminal-facts.json`
- `zdoc/reviews/20260918-gt06-s82-failure/package-manifest.json`

Catalog/source scopes: U80, E70, U81, C81, FAIL81, BENCH. Historical scheduler probes remain scoped. A fresh completed campaign needs exact source/request/XML/launch/principal, actual host/editor/helper exits, post-finally terminal cleanup and terminal scheduler observation. Missing supervisor natural-exit evidence stays explicit; return.json is not that receipt.

## F15 — Complete requirement/artifact/source closure and two independent same-manifest critics

Plan: `TQ00`, `GT-06 DoD`. **OPEN_FINAL_SEAL_TWO_CRITICS_COORDINATOR**.

Tests / producer-verifier links (recorded scopes, not tests rerun here):

- `studio/tests/replay/benchmark_assembly.py`
- `final scoped seal verifier (coordinator/seal-owner output pending)`

Concrete evidence paths:

- `zdoc/reviews/20260918-gt06-s81-admission/dependency-impact.md`
- `zdoc/reviews/20260918-gt06-s81-admission/repair-source.json`
- `zdoc/reviews/20260918-gt06-s83-mapping/requirements.json`
- `zdoc/reviews/20260918-gt06-s83-mapping/seal-checklist.md`

Catalog/source scopes: E05, DEP, DEP81, SRC81, FAIL81, BENCH. After full measurement, finalize all15 requirement/artifact/source/test/driver/verifier/schema joins and raw bytes, then two new independent PASS/TICK=yes against one final manifest and coordinator decision. No signature or final-manifest hash exists here.

## Evidence and provenance catalog

Historically recorded metadata digests in JSON are attributed to the S80 mapping and were not rehashed here. Current source/digest equality is based on the named recorded dependency reports, not guessed from Git HEAD.

- **E05** — `zdoc/reviews/20260917-gt05-s63-audit/manifest.json`. Accepted GT05 producer/edit/validated GLB/import/reimport provenance; acceptance S64, no transferred GT06 verdict.
- **E65** — `zdoc/reviews/20260917-gt06-s65-progress/runs.json`. Historical native04 fault, repair02 and native05/perf. Native154 maps are not current; preserve original causal anchors.
- **E69R** — `studio/.local/reviews/gt06-s69-managed-replay-01/repair-replay.json`. Current-matching scoped runtime159 and four verifier sources; seed17; original S65 fault/repair02 bound to native replay.
- **E79** — `zdoc/reviews/20260918-gt06-s79-diagnosis/service-remint-01/verification.json`. Seven native service/adversary/reviewer runs; runtime174 and GUI5 projections match. Stop natural exit remains null, not fabricated zero.
- **DEP** — `zdoc/reviews/20260918-gt06-s79-diagnosis/s80-dependency-bridge.json`. S80 per-lane dependency comparison and S65/S68 limits; use DEP81 for restored transport/current scope. REPORT distinguishes source checkpoint24efe967 and frozen Git HEAD e4bbc1fe.
- **U69** — `zdoc/reviews/20260918-gt06-s69-units-01/invocation.json`. Original434-test package. Reuse unaffected scoped fault/observer/UI paths; service.py changed and is supplemented by U79/E79.
- **U79** — `zdoc/reviews/20260918-gt06-s79-diagnosis/index-checks-01/invocation.json`. 95 recorded index/service/journal regressions, including current service/index fault cases; no whole407 snapshot current claim.
- **U80** — `zdoc/reviews/20260918-gt06-s80-readiness/verification.json`. Historical96+11 tests (98 distinct), current readiness source subset only; changed benchmark consumers use U81. Not a current50/51-file execution claim.
- **CB80** — `zdoc/reviews/20260918-gt06-s80-readiness/campaign-closure-binding.json`. Historical actual50 campaign closure and diagnostic source correction; superseded for current campaign by SRC81 51. Keep provenance, never rename it.
- **E80N** — `zdoc/reviews/20260918-gt06-s80-readiness/README.md`. Historical native positive37788 exit0 and no-focus19752 exit86; source-scoped readiness behavior only, not S81 full-runtime performance.
- **FAULT** — `zdoc/reviews/20260918-gt06-s70-resume/fault-coverage-links.md`. Exact F11/F12 test/artifact links; native S60 OOM, S64 shared-runner bounds, scoped S69 consumer coverage. Current service supplement U79/E79.
- **E70** — `zdoc/reviews/20260918-gt06-s70-resume/evidence-inventory.json`. Historical scheduler/nested-owner natural/Stop/failure examples at original source bindings. They do not prove successful termination of current or future campaign; S80 and S81 campaigns failed.
- **BENCH** — `studio/.local/reviews/gt06-s81-campaign-01`. FAILED at batch15; 16 captures including5warmup/11measured; ObjectDB71128 to71130, zero complete runs. Retain failed raw/supervisor; no sample pooling. Future successful campaign ID unassigned here.
- **DEP81** — `zdoc/reviews/20260918-gt06-s81-admission/dependency-impact.md`. After accepted transport restoration, recorded exact joins: acceptedGT05 143; S79 backend174 and UI5 with same collector membership; S69 runtime159/verifier4. Benchmark-only paths absent from those maps. No native remint needed solely for this isolated source delta.
- **SRC81** — `zdoc/reviews/20260918-gt06-s81-admission/repair-source.json`. Current declared51-file e010180a closure, profile and per-file map. Includes new benchmark_transport and terminal cleanup consumer. Not independently rehashed here.
- **U81** — `zdoc/reviews/20260918-gt06-s81-admission/checks-02/invocation.json`. 204/204 affected checks, zero skips/failures/errors; actual target10500 exit0/helper36760 exit0, tree verified; 414 captured sources unchanged. Broad414 is a test snapshot, not campaign closure.
- **H81** — `zdoc/reviews/20260918-gt06-s81-admission/http-probe/result-02/capture.json`. Instrumented isolated-benchmark HTTP02, target7060 exit0/helper53616 exit0; complete1000-command batch. Removes observed fault-hook contention, not demonstrated total throughput gain, native workload or timeout-cause proof.
- **C81** — `zdoc/reviews/20260918-gt06-s81-admission/native-cleanup-probe/evidence/verification.json`. Supplemental same51 runtime, execution52 with driver: ff0246d4629395aefe7962c624d2bb51140ecf1a6658db72ad1c034a79f7b840. Actual READY then injected failure, zero batches/effects. Observer14112/import34944 exit0; editor natural exit null/helper33296 exit2. Import wrapper receipt/outer shell receipt/helper PID gaps remain.
- **FAIL81** — `zdoc/reviews/20260918-gt06-s82-failure/package-manifest.json`. Failure preservation only, recorded seal15990322afe5cfdcf8f95a5274493bbd2b72b7ccca323cf7f7c2b9c2aeef1a48. 325raw/172copies; host4132 exit1, editor48332 actual exit missing/helper22376 exit2; closed zero Jobs. Scheduler state3/result1/no instances; supervisor actual exit/import wrapper/helper inventory gaps.
- **DIAG82** — `zdoc/reviews/20260918-gt06-s82-attribution/README.md`. Attribution design/overlay and coordinator-controlled disposable run; no runtime claim or live/raw inspection by this preparation. Native-only short/long probes and full-sequence attribution have separate instrumentation/durations. All excluded from accepted campaign samples.

## Exact reuse and limits

- S79 backend174 closure `644b90abfe769bf1a3654ba506cef50f8a38393f05f0be5ca7aae8050aaaa527`; GUI5 `7665621f1090836c2bc711ccc7f6857c3961b99be5b077292baaadc933b712fb`. Original source checkpoint24efe967/frozen Git HEAD e4bbc1fe remain distinct. Seven original run IDs are in JSON; actual Stop natural exits remain null.
- S69 managed159 closure `491b65875f8246e7606c7b860d9c61d6a85657fc0077075fa6dc7209128dca2b` and four verifier pins match according to DEP81. Preserve S65 repair02 causal authority and original IDs.
- S65 native154 differs in fixture/observer bytes and is historical; collector3 is a separate matching scope. S68 integrated service/journal maps are historical; S79 supersedes their integration claim.
- U69 service.py is not current; U79 and affected U81 supplement it. Do not sum434/95/98/204 overlapping tests or call broad snapshots exact-current.
- S81 checks02/HTTP02/cleanup probe are current scoped supplements; checks01/HTTP01 remain previous diagnostic implementation. C81 forced cleanup has no editor natural exit/import wrapper receipt/outer shell receipt and no completed batch.
- S82 native-only nonreproduction does not rule out a leak; attribution adds overhead/overlay and is excluded from measurement. This preparation made no live-status read or result claim.

## Remaining gates

1. G1: resolve measured failure, freeze any changed source and obtain10 fresh complete process pairs x35batches at unchanged profile, with terminal ownership/cleanup and all metrics.
2. G2: final requirement/raw/source/test/driver/verifier/schema seal and accepted asset→Play→fault/repair/replay joins; retain failed prefixes and missing-proof limits.
3. G3: two new independent PASS/TICK=yes on one final manifest hash, then coordinator acceptance. All final manifest/critic fields remain null.

Accepted shared fault coverage does not certify physical disk exhaustion, power loss or forced OS PID recycling. Single-runtime quota/Stop scope does not close GT07 multi-project scheduling. No additional functional native orphan was identified in this bounded prep; final reviewers may identify an actual gap. See `seal-checklist.md` for terminal packaging details.
