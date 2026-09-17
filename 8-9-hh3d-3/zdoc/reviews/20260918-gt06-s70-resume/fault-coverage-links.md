# GT06 F11/F12 fault and quota coverage links

Bounded read-only dependency mapping at HEAD
`14b8752b6bafe3ce6531188f02355881b9ffb1d1`, 2026-09-18 Asia/Saigon.
Only this report was written. No tests, engines, source edits, commits or raw-tree
scan; the measured campaign was not touched. This is implementation preparation,
not acceptance, a gate reopening or a claim that every fault was injected natively.
Paths are relative to `8-9-hh3d-3/`.

## Conclusion

F11/F12 have concrete existing coverage links. The missing links in
`requirements-final-draft.md` do not justify rerunning accepted GT03–05 or the
unchanged GT06 functional lanes. In particular, actual native memory exhaustion
exists in the accepted S60 dependency evidence; it is not merely a configured
memory limit. The S64 shared runner separately proves timeout/nonzero-exit/live
descendant rejection and bounded disk accounting. S69 recorded results cover the
GT06 persistence, ownership, quota, disconnect and priority-control consumers.

No additional concrete native functional orphan was identified within GT06's
declared fixed fixture/runtime scope. Full measured benchmark, final sealed
coverage/evidence closure and two independent critics remain pending. The scope
limits below must accompany reuse; this report does not mark all TX18 scheduling
requirements globally complete.

## F11: exact tests and source-bound results

| Behavior | Existing test/probe | Recorded evidence and precise scope |
|---|---|---|
| OOM / actual Job memory enforcement | `studio/tests/blender/export_fault_probe.py:run`, diagnostic `oom`; reused `studio/host/blender/export_job.py:configure_limits` and `studio/godot-addon/cli_job.py` | `studio/.local/reviews/20260917-gt04-s60-matrix/ipc/oom.json`: native over-limit allocation produced `MemoryError`, target PID42916 exit17 and wrapper exit17, queried Job memory2147483648 bytes, Job closed/zero/un-tainted, no retained handle/output GLB. Accepted by `zdoc/reviews/20260917-gt04-s60-acceptance/acceptance.json`, source ref38f6b9a. This proves the shared limit/ownership primitive on a Blender fixture, not a separate Godot OOM playthrough. |
| Correct owned termination on deadline | `studio/tests/pipeline/test_native_job.py:NativeJobTests.test_actual_short_deadline_kills_only_owned_job` | Exact ID is `... ok` in `studio/.local/reviews/gt05-units-s64-02/unit-stderr.txt:131`; the test launches a short owned Python process, reaches `STAGE_WALL_LIMIT`, and checks closed/zero Job. This is the same unchanged `pipeline/native_job.py` imported by GT06. |
| Nonzero exit or live descendants must not become PASS | Same module: `test_nonzero_child_is_not_promoted_to_success`, `test_successful_parent_with_live_child_is_rejected_before_cleanup` | Same recorded S64 log, lines134/139. Actual child exit7 is retained; a successful parent with a live child is rejected before checked cleanup. S64 `capture.json` binds233 tests,232 pass/one unrelated symlink skip, real target/helper exits0 and tree verification. Accepted GT05 manifest hashes these files. |
| Disk accounting, bounded logs and error handling | Same module: `test_disk_budget_combines_sibling_roots_without_double_count`, `test_disk_watchdog_tolerates_deleted_owned_scratch_only`, `test_stream_overflow_preserved_and_rejected` | Same S64 invocation/log/capture. Disk test writes two40-byte files and patches the cap to64/128 to exercise rejection/counting; scratch disappearance differs from access denial. Log overflow runs an actual child and rejects overflow while preserving bounded diagnostics. This is a disk watchdog, not filesystem reservation or physical disk exhaustion certification. |
| Journal/storage failure must retain UNKNOWN and Stop | `studio/tests/replay/test_service.py:ReplayServiceTests.test_completion_persistence_failure_lookup_is_unknown_without_durable_success`; `test_stop_persistence_failure_still_latches_runtime_and_work_admission`; `test_durable_terminal_wins_if_finish_raises_after_commit` | All executed in `zdoc/reviews/20260918-gt06-s69-units-01/units-stderr.txt`, under its invocation/source map. Injected `JOURNAL_WRITE_FAILED` leaves durable pending intent and blocks replay; Stop still latches; an actually durable terminal wins a later uncertainty overlay. These are explicit failure injection, not actual ENOSPC/power-loss tests. |
| Startup timeout / retained cleanup owner | `studio/tests/replay/test_backend.py:PreparedPlayTests.test_start_timeout_retains_owner_until_actual_drain`, `test_worker_start_uncertain_latches_stop_and_returns_cleanup_owner`, `test_cleanup_failure_retains_owner_and_retry_releases` | S69 unit package records the methods and source. Native supplements: S69 owner-smoke natural/Stop/setup-failure and S70 scheduler/nested-owner probes, already indexed in the final draft. Their later benchmark-owner changes stay bound to their own U70 evidence. |
| PID/process identity and uncertain native handle | `studio/tests/replay/test_backend.py:test_runtime_exit_pid_must_match_sampler_identity`, `test_bad_marker_pid_rejects_completion`; `test_process_probe.py:test_invalid_pid_never_opens`, `test_actual_retained_process_identity_and_memory`, `test_actual_foreign_image_expectation_rejected_and_closed`, `test_interrupted_close_never_reuses_uncertain_handle` | S69 unit invocation and log. Checks bind a retained Windows handle, process-start identity/image and matching captured PID; invalid/stale identity is rejected. Do not describe this as deliberately forcing OS PID recycling. E69A native records additionally bind process-start artifact and closed/zero Job. |
| Stop wins; forced Stop is not natural completion | `studio/tests/replay/test_backend.py:test_native_stage_stop_is_not_claimed_as_completed`; `test_service.py:test_stop_during_pending_runtime_records_canceled_without_relaunch`; real `run_service_adversary.py --mode saturated-stop` | S69 units plus `studio/.local/reviews/gt06-s69-saturated-stop-01/http-adversary/result.json` and runtime capture; outer driver/helper0, runtime `STAGE_STOPPED`, CANCELED and exact owned cleanup. No natural native exit0 is fabricated. |

The memory proof reaches GT06 through an explicit code dependency:
`pipeline/native_job.py` imports `configure_limits` from
`host/blender/export_job.py` and `cli_job` through `host/blender/ui_host.py`.
The unchanged shared runner's nonzero/deadline handling tests and GT06's
completion/ownership consumer tests bridge that primitive. They do not grant a
new GT06 acceptance signature to S60.

## F12: concrete quota/disconnect/priority links

All unit methods below are in the recorded **S69 full434-test package**,
`zdoc/reviews/20260918-gt06-s69-units-01/{invocation.json,capture.json,units-host.json,units-stderr.txt}`.
Target/helper exit0, zero skips and source stability are recorded there. This
review read the corresponding `... ok` lines for the main entries and checked
the19 selected production/test dependencies listed below against that invocation.

| Requirement part | Concrete recorded test IDs (under `studio/tests/`) | Native complement / limit |
|---|---|---|
| Finite command/session/credential budgets; no eviction that permits replay | `replay/test_session.py:test_budget_is_finite_without_eviction_and_stop_still_works`; `test_session_and_credential_history_budgets_fail_closed`; `test_exact_command_tombstones_survive_rotation_and_do_not_become_retry_authority` | The64-command owner budget preserves existing IDs; eight sessions/32 credential history are bounded. Lookup/Stop remain available at exhausted command budget. This is one prepared project/runtime owner, not a general multi-project scheduler. |
| Inspector/result/memory admission bounds | `replay/test_inspector.py:test_registry_cap_is_enforced_before_expensive_validation`; `test_artifact_byte_caps_are_admitted_before_hash_or_parser_work`; `test_page_filter_and_cursor_caps_reject_before_output` | Actual S68 GUI Inspect/Capture uses the bounded historical view. Native stale-capture adversary proves fresh artifact-byte revalidation. |
| Flooded/slow work cannot consume reserved Stop | `replay/test_transport.py:test_stop_listener_works_with_work_and_control_partial_headers`; `test_stop_isolated_from_blocked_owner_work_lookup_and_slow_control`; `test_body_cap_precedes_auth_body_read_and_owner` | S69 saturated-stop uses two actual incomplete work connections while Play is running; lookup and Stop succeed through reserved listeners and a reconnect cannot resume. Single observed latency is not benchmark p95. |
| No response loss → duplicate mutation amplification | `reviewer/test_client.py:test_response_loss_never_resubmits_play`; `replay/test_service.py:test_start_is_pending_then_commits_only_after_bound_result_and_dedupes_once` | The client test injects a timeout after simulated server processing and proves only one submit. Native service/GUI evidence supplies actual command→Play→readback, but this test is not labeled a native cable-loss event. |
| Disconnect/late results cannot clear human Stop | `reviewer/test_model.py:test_stop_latch_survives_disconnect_and_lookup_completion`; `reviewer/test_client_adversarial.py:test_late_committed_play_cannot_overwrite_stop_latch`; `reviewer/test_client.py:test_stop_latches_before_io_and_never_claims_owner_closed` | S68 actual Esc/Stop and S69 native reconnect denial complement the state-machine fault cases. |
| UI starvation / worker mailbox amplification / bounded telemetry | `reviewer/test_app.py:test_network_is_off_main_thread_with_independent_priority_stop`; `test_receipts_are_retained_until_taken_and_work_cannot_flood_mailbox`; `reviewer/test_model.py:test_work_slot_is_bounded_and_stop_has_independent_capacity`; `test_progress_numeric_limits_and_history_retention_are_bounded` | Actual Tk complete/Stop lanes already retained. All admitted receipts remain available; stale UI updates/history are bounded explicitly. Full workload UI/status/memory measurements remain in the pending benchmark. |
| Slow I/O still has absolute deadline | `reviewer/test_client_adversarial.py:test_dripping_headers_obey_whole_request_deadline`; `test_dripping_body_obeys_whole_request_deadline`; `test_complete_response_after_expiry_is_never_returned`; replay session deadline tests | Bounded fake-server/socket tests, not claims about arbitrary network failure coverage. No redefinition of the benchmark's≤2s status or≤500ms receipt thresholds. |

## Source and result anchors checked

Accepted S60 source map:
`zdoc/reviews/20260917-gt04-s60-audit/source-closure.json`, source closure
`f5ae5dfbb451d3204197c2b21486c586698089ac24d14d23641a9182b5e42673`.
Its `coverage.json` explicitly maps GT04/TX05 to the native IPC/deadline/cleanup
artifacts. The following current file bytes still match that source map:

```text
studio/host/blender/export_job.py=8eb0cc4a93361faf8cf09a3f11fd0278ec3fcdb2c9863e4b2ee98852c67ecdfe
studio/godot-addon/cli_job.py=5a0f37bc129bde409a2657054fb091d637d838e442d45a69e7adc1f1527d4c88
studio/tests/blender/export_fault_probe.py=b70d44f0d85fa80561d8d7170298366aabf45768d6f00d4d2dd772cdcceb5f2e
raw S60 ipc/oom.json=80f9d81a99c045356c53f9223c1d9bdd4c364751f4be17dade4bc882659a38a8
```

Accepted S64 manifest:
`zdoc/reviews/20260917-gt05-s63-audit/manifest.json`, SHA256
`fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b`.
Both current shared-runner files match its source entries:

```text
studio/pipeline/native_job.py=456bb70c315e38cf7a29354b7df51862e1ded4578f6b22d9110bf628547c20ca
studio/tests/pipeline/test_native_job.py=16d825addc32ea8dce04785fab8003853cc3cfc843597c64d40eb17c8059d01c
studio/.local/reviews/gt05-units-s64-02/capture.json=0b7ba63a43c7c0365524810ff478652b3f813e35c0413349e669accb1302fa11
studio/.local/reviews/gt05-units-s64-02/unit-stderr.txt=dc1fef9ffb2ee06c45ed7326cbbe0aeb6a85adcec22fe0fb211f647a01e16805
```

S69 unit anchors:

```text
zdoc/reviews/20260918-gt06-s69-units-01/invocation.json=951d3439e92747b658aee9dd9f60df1b0e2c9cca30944c9d2d00792427718ac1
zdoc/reviews/20260918-gt06-s69-units-01/capture.json=987b828553ccd82b59977b7a1fde9bf5ed4ac588baf2f9e7a80f129aef736e27
```

The19 selected current files all match the S69 invocation's per-file hashes:
`host/replay/{backend,process_probe,service,session,transport,inspector}.py`,
`reviewer/{app,client,model}.py`,
`tests/replay/test_{backend,process_probe,service,session,transport,inspector}.py`,
and `tests/reviewer/test_{app,client,client_adversarial,model}.py`.
This is targeted dependency reuse, not a fresh full-source or full-raw audit.

## Limits and actual remaining gaps

- No physical disk exhaustion, power-loss or antivirus certification is claimed;
  accepted GT04/GT05 explicitly retain those limits. Existing disk-budget and
  persistence-failure cases cover bounded failure handling. Do not convert these
  known limits into an invented new native certification requirement.
- No actual forced OS PID recycle is claimed; retained handle/start identity,
  mismatch rejection and exact-owner teardown are the existing proof.
- Single-owner admission/control fairness is linked above. General fairness
  across concurrent projects/sessions and cross-app activation remains GT07's
  explicit scheduling/transaction scope. Do not mark that broader TX18 obligation
  accepted from GT06's one-runtime tests; final reviewers must retain the scope
  boundary instead of using a blanket TX18 PASS.
- A real mid-job cable disconnect is not newly claimed. Recorded response-loss,
  absolute-deadline and Stop-state injection plus native congestion/reconnect
  evidence are the available bounded coverage; the plan does not require every
  failure to be demonstrated by physically severing a connection.
- Actual remaining GT06 gates are the declared full measured workload and its
  limits/clean ownership, final source-specific evidence seal, and two independent
  critics. Nothing in this bounded follow-up requires interrupting the running
  campaign or reopening already accepted gates.
