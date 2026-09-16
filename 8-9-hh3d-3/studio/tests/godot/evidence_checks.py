"""Fail-closed validation of one actual EditorPlugin probe result.

The host runner separately verifies process completion, executable/source
provenance, clean logs and equality of the edit/reopen saved revisions. This
module validates parsed result/progress records, without claiming those records
alone prove that an editor process ran.
"""
from __future__ import annotations

import re


_COMMON = ("actual_editor_initialized", "main_thread", "root_stable_id")
_EDIT = (
    "thread_started", "off_thread_rejected_before_scene_access",
    "preview_valid", "preview_has_no_effect", "create_applied",
    "create_actual_owner", "create_actual_box_resource", "create_position",
    "create_invalidated_revision", "pagination_is_bounded", "update_applied",
    "updated_position", "updated_resource", "updated_ownership", "undo_applied",
    "undo_restored_position", "redo_applied", "redo_exact_revision",
    "remove_applied", "remove_actual_detach", "remove_undo_applied",
    "remove_undo_exact_revision", "remove_undo_position", "remove_undo_resource",
    "remove_undo_ownership",
) + tuple(
    f"invalid_{index}_{suffix}"
    for index in range(8) for suffix in ("rejected", "no_effect")
) + (
    "fixture_pack", "fixture_save", "fixture_load", "pack_has_stable_id",
    "pack_has_owner", "external_resource_setup_save", "external_resource_setup_path",
    "external_resource_link_rejected", "external_resource_update_rejected",
    "external_resource_link_preserved", "external_resource_restore_exact_revision",
    "shared_resource_setup", "shared_resource_alias_rejected", "shared_resource_restored",
    "shared_resource_cleanup", "shared_resource_cleanup_exact_revision",
    "manual_edit_changes_revision", "manual_edit_stale_request_rejected",
    "actual_editor_history_exists", "direct_undo_guard_rejected",
    "direct_undo_preserves_manual_edit", "history_clear_preserves_live_node",
    "reload_binds_new_generation", "reload_resolves_root_stable_id",
    "old_projection_rejected_after_reload",
) + tuple(
    f"detached_{mutation}_{suffix}"
    for mutation in ("group", "persistent_connection", "queued_delete")
    for suffix in ("setup", "undo", "rejected_before_attach", "unchanged_scene", "no_signal", "reload")
) + (
    "parent_identity_setup", "parent_identity_child_setup", "parent_identity_undo_setup",
    "identical_parent_replacement_same_revision", "retained_parent_identity_rejected",
    "stale_parent_not_mutated", "replacement_parent_not_mutated", "parent_guard_preserves_revision",
    "parent_custody_freed_detached_original", "parent_custody_preserves_replacement",
)
_REOPEN = (
    "reopened_saved_scene_position", "reopened_saved_scene_resource",
    "reopened_saved_scene_ownership", "reopen_exact_node_count",
)
_CONTRACT = (
    "contract_vectors_present_bounded", "contract_actual_observation_matches",
    "contract_negative_cases_host_rejected",
) + tuple(
    f"contract_{stage}_{vector}"
    for vector in ("inspect", "create", "update", "preview")
    for stage in ("decode", "engine", "preview_unchanged")
) + (
    "contract_create_available", "contract_actual_apply",
    "contract_postcondition_box_size", "contract_postcondition_owner_id",
    "contract_postcondition_parent_id", "contract_postcondition_position",
    "contract_postcondition_stable_id", "contract_revision_changed",
    "contract_fractional_generation_rejected", "contract_boolean_generation_rejected",
)
# These are the complete successful paths in editor_probe.gd. Requiring each
# label catches an early return even if the producer incorrectly reports ok.
_REQUIRED = {
    "edit": frozenset(_COMMON + _EDIT),
    "reopen": frozenset(_COMMON + _REOPEN),
    "contract": frozenset(_COMMON + _CONTRACT),
}
_REVISION = re.compile(r"sha256:[0-9a-f]{64}")


def _sequence(rows: object, source: str) -> list[tuple[str, bool]]:
    if type(rows) is not list or not rows:
        raise ValueError(f"{source} must be a nonempty list")
    sequence = []
    labels = set()
    for index, row in enumerate(rows):
        if type(row) is not dict:
            raise ValueError(f"{source}[{index}] must be an object")
        label = row.get("label")
        if type(label) is not str or not label or label != label.strip():
            raise ValueError(f"{source}[{index}] must have a nonblank label")
        if label in labels:
            raise ValueError(f"{source} has duplicate label: {label}")
        if row.get("passed") is not True:
            raise ValueError(f"{source} check must pass with boolean true: {label}")
        labels.add(label)
        sequence.append((label, True))
    return sequence


def validate_result(mode: str, result: object, progress_rows: object) -> bool:
    """Return True for complete consistent evidence; otherwise raise ValueError.

    Inputs must be parsed JSON objects/lists. Unknown metadata and additional
    unique passing checks are allowed, but no required check may be omitted.
    The inputs are not modified.
    """
    if type(mode) is not str or mode not in _REQUIRED:
        raise ValueError("unsupported probe mode")
    if type(result) is not dict:
        raise ValueError("result must be an object")
    if type(result.get("mode")) is not str or result["mode"] != mode:
        raise ValueError("result mode does not match requested mode")
    if result.get("actual_editor") is not True:
        raise ValueError("result must report actual_editor as boolean true")
    if result.get("ok") is not True:
        raise ValueError("result must report ok as boolean true")
    if type(result.get("failures")) is not list or result["failures"]:
        raise ValueError("result failures must be an empty list")

    checks = _sequence(result.get("checks"), "result checks")
    missing = _REQUIRED[mode] - {label for label, _ in checks}
    if missing:
        raise ValueError("result is missing required checks: " + ", ".join(sorted(missing)))
    progress = _sequence(progress_rows, "progress rows")
    if progress != checks:
        raise ValueError("progress label/pass sequence does not match result checks")

    if mode in ("edit", "reopen"):
        revision = result.get("saved_revision")
        if type(revision) is not str or _REVISION.fullmatch(revision) is None:
            raise ValueError("saved_revision must be sha256 followed by 64 lowercase hexadecimal digits")
    return True
