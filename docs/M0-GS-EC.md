# M0 GS-EC matrix (WP-M0-6)

Checklist for MASTER T0.6 / 12.1. Every M0-group `test_id` appears once.
Status is `pass` only when a real automated test exists. Crash tests use
`Session::inject_crash` (simulated 5.5 points) — **not** a real `kill -9`.

Kind: **U** unit, **I** integration, **F** fault, **M/T** manual/tooling.

| test_id | case | test location | kind | status |
|---|---|---|---|---|
| GS-EC-01 | Transform NaN/Inf rejected | `gs-scene::invariants::nan_transform_rejected` | U | pass |
| GS-EC-02 | scale 0 / \|s\|>1000 rejected | `gs-scene::invariants::scale_zero_and_name_too_long_rejected` | U | pass |
| GS-EC-03 | id not found → E_NOT_FOUND; txn rollback | `m0::gs_ec::id_not_found_is_e_not_found_and_txn_rolls_back` | U | pass |
| GS-EC-04 | Name 10MB rejected early | `gs-scene::invariants::scale_zero_and_name_too_long_rejected` | U | pass |
| GS-EC-07 | reparent cycle rejected | `gs-scene::invariants::reparent_cycle_rejected` | U | pass |
| GS-EC-10 | git conflict marker rejected | `gs-scene::invariants::git_conflict_marker_rejected` | U | pass |
| GS-EC-11 | unknown fields round-trip (I5) | `gs-scene::invariants::unknown_fields_round_trip_nested` | U | pass |
| GS-EC-13 | 2 agents / expected_revision conflict | `m0::gs_ec::two_agents_same_field_expected_revision_conflicts` | I | pass |
| GS-EC-14 | mutating budget 200 cmds/min → E_BUDGET | `m0::gs_ec::mutating_budget_200_per_minute` | I | pass |
| GS-EC-15 | duplicate client_name, distinct actor_id | `gs-editor::wp_m0_4::duplicate_client_name_gets_distinct_actor_ids` | U | pass |
| GS-EC-16 | txn atomic (no open txn between requests) | `m0::gs_ec::transaction_is_atomic_failing_command_applies_nothing` | U | pass |
| GS-EC-17 | pause: mutating E_PAUSED, ping OK | `gs-editor::wp_m0_4::pause_blocks_mutating_but_ping_still_works` | I | pass |
| GS-EC-18 | editor quit while agent in-flight → shutting_down | — | F | **manual** — no `shutting_down` app_code or graceful in-flight drain; `BusHandle` drop stops accept only |
| GS-EC-19 | retry command_id after drop / no dup entity | `gs-scene::invariants::command_id_retry_does_not_duplicate_entity`; `gs-editor::wp_m0_4::retry_same_command_id_does_not_duplicate_entity`; `m0::conformance::retry_same_command_id_after_spawn_is_idempotent` | I,F | pass |
| GS-EC-20 | confirmation reuse / changed params invalid | `gs-editor::wp_m0_4::confirmation_reuse_and_changed_params_are_invalid`; `m0::conformance::txn_with_d_destroy_waits_for_ui_confirmation` | U | pass |
| GS-EC-21 | salami: destroy 16–19 ids >3×/min → D | `m0::gs_ec::salami_destroy_elevates_to_destructive` | I | pass |
| GS-EC-38 | crash (a)(b)(c)(d) recover to last ACK | `gs-scene::invariants::crash_a_mid_record_write` / `crash_b_after_flush_before_apply` / `crash_c_mid_tmp_rename_autosave` / `crash_d_between_two_records`; harness `m0::fault::crash_a_*` … `crash_d_*` (simulated `inject_crash`, not kill -9) | F | pass |
| GS-EC-39 | disk full / fsync fail → fail-stop mutating | `gs-scene::invariants::disk_full_fsync_fail_rejects_mutating`; `m0::fault::disk_full_fsync_fail_rejects_mutating` | F | pass |
| GS-EC-40 | path traversal escapes project root | `m0::gs_ec::path_jail_rejects_escape` | U | pass |
| GS-EC-41 | Windows reserved file names | `m0::gs_ec::windows_reserved_name_rejected` | U | pass |
| GS-EC-42 | OneDrive/Dropbox holds file; rename retry | — | M/T | **manual** — needs a real sync-tool lock on the dest; cannot simulate OneDrive in CI |
| GS-EC-43 | second exclusive editor open fails | `gs-scene::invariants::second_exclusive_open_fails` | I | pass |
| GS-EC-44 | stale endpoint pid rejected | `gs-cli::wp_m0_5::stale_pid_is_rejected_without_hang` | I | pass |
| GS-EC-45 | bus token not in feed/events/logs | `gs-editor::wp_m0_4::token_does_not_appear_in_feed_or_event_fixture`; `gs-cli::wp_m0_5::token_absent_from_hello_debug_and_result` | U | pass |
| GS-EC-57 | command_id retry survives autosave restart | `gs-scene::invariants::command_id_retry_survives_autosave_restart` | F | pass |
| GS-EC-58 | NDJSON line >4MB → E_PROTO; other clients live | `gs-protocol::line_over_4mb_is_proto_error`; `m0::conformance::ndjson_line_over_4mb_is_e_proto`; `m0::conformance::ndjson_line_over_4mb_via_tcp_other_agent_lives` | U,I | pass |

## Conformance extras (12.1, not a GS-EC id)

| case | test location |
|---|---|
| agent TCP × every registry UiOnly method → `-32001` | `m0::conformance::agent_cannot_call_any_ui_only_method` |
| missing required fields → `-32602` / E_VALIDATION | `m0::conformance::invalid_params_missing_required_fields` |
| expected_revision mismatch → E_CONFLICT / `-32002` | `m0::conformance::expected_revision_mismatch_is_conflict` |
| txn containing D (21-id destroy) held until UI approve | `m0::conformance::txn_with_d_destroy_waits_for_ui_confirmation` |
| property undo: 20 varied spawns in one txn, undo_last + human_ui undo.perform, bytes/count match | `m0::gs_ec::property_undo_n_spawns_restores_canonical_bytes` |

## Manual reasons (only these)

- **GS-EC-18**: editor has no `shutting_down` path for in-flight agent RPCs.
- **GS-EC-42**: OneDrive/Dropbox file lock is an external OS/sync-tool condition.
