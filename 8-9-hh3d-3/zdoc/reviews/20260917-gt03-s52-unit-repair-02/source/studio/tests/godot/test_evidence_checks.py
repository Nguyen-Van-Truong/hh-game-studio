"""Corruption tests for probe evidence; these synthetic rows do not run Godot."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location(
    "gt03_evidence_checks", Path(__file__).with_name("evidence_checks.py"))
evidence_checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence_checks)

# Independent fixtures transcribed from the successful editor_probe.gd paths.
# Never construct positive evidence from the validator's own required-label set.
_COMMON = ("actual_editor_initialized main_thread root_stable_id "
    "initial_script_attached initial_script_exact_source_hash initial_script_export_preserved")
_LABELS = {
    "edit": (_COMMON + """
        thread_started off_thread_rejected_before_scene_access preview_valid
        preview_has_no_effect create_applied create_actual_owner create_actual_box_resource
        create_position create_invalidated_revision pagination_is_bounded update_applied
        updated_position updated_resource updated_ownership undo_applied undo_restored_position
        redo_applied redo_exact_revision remove_applied remove_actual_detach remove_undo_applied
        remove_undo_exact_revision remove_undo_position remove_undo_resource remove_undo_ownership
        after_undo_script_attached after_undo_script_exact_source_hash after_undo_script_export_preserved
        invalid_0_rejected invalid_0_no_effect invalid_1_rejected invalid_1_no_effect
        invalid_2_rejected invalid_2_no_effect invalid_3_rejected invalid_3_no_effect
        invalid_4_rejected invalid_4_no_effect invalid_5_rejected invalid_5_no_effect
        invalid_6_rejected invalid_6_no_effect invalid_7_rejected invalid_7_no_effect
        fixture_pack fixture_save fixture_load pack_has_stable_id pack_has_owner
        external_resource_setup_save external_resource_setup_path external_resource_link_rejected
        external_resource_update_rejected external_resource_link_preserved
        external_resource_restore_exact_revision shared_resource_setup shared_resource_alias_rejected
        shared_resource_restored shared_resource_cleanup shared_resource_cleanup_exact_revision
        manual_edit_changes_revision manual_edit_stale_request_rejected actual_editor_history_exists
        direct_undo_guard_rejected direct_undo_preserves_manual_edit history_clear_preserves_live_node
        reload_binds_new_generation reload_resolves_root_stable_id old_projection_rejected_after_reload
        detached_group_setup detached_group_undo detached_group_rejected_before_attach
        detached_group_unchanged_scene detached_group_no_signal detached_group_reload
        detached_persistent_connection_setup detached_persistent_connection_undo
        detached_persistent_connection_rejected_before_attach detached_persistent_connection_unchanged_scene
        detached_persistent_connection_no_signal detached_persistent_connection_reload
        detached_queued_delete_setup detached_queued_delete_undo detached_queued_delete_rejected_before_attach
        detached_queued_delete_unchanged_scene detached_queued_delete_no_signal detached_queued_delete_reload
        parent_identity_setup parent_identity_child_setup parent_identity_undo_setup
        identical_parent_replacement_same_revision retained_parent_identity_rejected stale_parent_not_mutated
        replacement_parent_not_mutated parent_guard_preserves_revision parent_custody_freed_detached_original
        parent_custody_preserves_replacement
    """).split(),
    "reopen": (_COMMON + """
        reopened_saved_scene_position reopened_saved_scene_resource
        reopened_saved_scene_ownership reopen_exact_node_count
    """).split(),
    "contract": (_COMMON + """
        contract_vectors_present_bounded contract_actual_observation_matches
        contract_negative_cases_host_rejected contract_decode_inspect contract_engine_inspect
        contract_preview_unchanged_inspect contract_decode_create contract_engine_create
        contract_preview_unchanged_create contract_decode_update contract_engine_update
        contract_preview_unchanged_update contract_decode_preview contract_engine_preview
        contract_preview_unchanged_preview contract_create_available contract_actual_apply
        contract_postcondition_box_size contract_postcondition_owner_id contract_postcondition_parent_id
        contract_postcondition_position contract_postcondition_stable_id contract_revision_changed
        contract_fractional_generation_rejected contract_boolean_generation_rejected
    """).split(),
}


def fixture(mode):
    result = {
        "mode": mode, "actual_editor": True, "ok": True, "failures": [],
        "checks": [{"label": label, "passed": True, "detail": {}} for label in _LABELS[mode]],
        "saved_revision": "sha256:" + "a" * 64 if mode != "contract" else "",
        "production_save_verified": False, "hostile_script_sandbox_verified": False,
    }
    progress = [{"label": row["label"], "passed": row["passed"]} for row in result["checks"]]
    return result, progress


class EvidenceChecksTests(unittest.TestCase):
    def test_accepts_complete_modes_without_mutating_records(self):
        for mode, count in (("edit", 103), ("reopen", 10), ("contract", 31)):
            with self.subTest(mode=mode):
                result, progress = fixture(mode)
                before = deepcopy((result, progress))
                self.assertEqual(len(result["checks"]), count)
                self.assertIs(evidence_checks.validate_result(mode, result, progress), True)
                self.assertEqual((result, progress), before)

    def test_rejects_unknown_requested_mode(self):
        result, progress = fixture("edit")
        for mode in ("", "EDIT", "play", None, [], 1):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                evidence_checks.validate_result(mode, result, progress)

    def test_rejects_wrong_or_missing_result_mode(self):
        for mode in _LABELS:
            for reported in (None, "", "play", 1, *[other for other in _LABELS if other != mode]):
                with self.subTest(mode=mode, reported=reported):
                    result, progress = fixture(mode)
                    result["mode"] = reported
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result(mode, result, progress)
            result, progress = fixture(mode)
            del result["mode"]
            with self.assertRaises(ValueError):
                evidence_checks.validate_result(mode, result, progress)

    def test_rejects_noneditor_and_truthy_nonboolean_flags(self):
        for field in ("actual_editor", "ok"):
            for value in (False, None, 0, 1, "true", "false", [], {}):
                with self.subTest(field=field, value=value):
                    result, progress = fixture("edit")
                    result[field] = value
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)
            result, progress = fixture("edit")
            del result[field]
            with self.assertRaises(ValueError):
                evidence_checks.validate_result("edit", result, progress)

    def test_rejects_failures_despite_success_header(self):
        for failures in (["create_applied"], [False], None, {}, (), "", False):
            with self.subTest(failures=failures):
                result, progress = fixture("edit")
                result["failures"] = failures
                with self.assertRaises(ValueError):
                    evidence_checks.validate_result("edit", result, progress)
        result, progress = fixture("edit")
        del result["failures"]
        with self.assertRaises(ValueError):
            evidence_checks.validate_result("edit", result, progress)

    def test_rejects_each_omitted_check_even_when_progress_matches(self):
        for mode, labels in _LABELS.items():
            for index, label in enumerate(labels):
                with self.subTest(mode=mode, omitted=label):
                    result, progress = fixture(mode)
                    result["checks"].pop(index)
                    progress.pop(index)
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result(mode, result, progress)

    def test_rejects_each_false_check_even_when_header_and_progress_agree(self):
        for mode, labels in _LABELS.items():
            for index, label in enumerate(labels):
                with self.subTest(mode=mode, failed=label):
                    result, progress = fixture(mode)
                    result["checks"][index]["passed"] = False
                    progress[index]["passed"] = False
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result(mode, result, progress)

    def test_rejects_duplicate_rows_even_when_progress_matches(self):
        for mode in _LABELS:
            with self.subTest(mode=mode):
                result, progress = fixture(mode)
                result["checks"].append(deepcopy(result["checks"][0]))
                progress.append(deepcopy(progress[0]))
                with self.assertRaises(ValueError):
                    evidence_checks.validate_result(mode, result, progress)

    def test_rejects_blank_missing_or_nonstrings_labels(self):
        for source in ("checks", "progress"):
            for label in (None, "", " ", "\t", 1, [], {}, " padded "):
                with self.subTest(source=source, label=label):
                    result, progress = fixture("edit")
                    rows = result["checks"] if source == "checks" else progress
                    rows.append({"label": label, "passed": True})
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)
            result, progress = fixture("edit")
            rows = result["checks"] if source == "checks" else progress
            rows.append({"passed": True})
            with self.assertRaises(ValueError):
                evidence_checks.validate_result("edit", result, progress)

    def test_rejects_nonboolean_or_missing_row_pass_flags(self):
        for source in ("checks", "progress"):
            for value in (1, 0, None, "true", [], {}):
                with self.subTest(source=source, value=value):
                    result, progress = fixture("edit")
                    rows = result["checks"] if source == "checks" else progress
                    rows[0]["passed"] = value
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)
            result, progress = fixture("edit")
            rows = result["checks"] if source == "checks" else progress
            del rows[0]["passed"]
            with self.assertRaises(ValueError):
                evidence_checks.validate_result("edit", result, progress)

    def test_rejects_malformed_result_and_row_containers(self):
        result, progress = fixture("edit")
        for bad_result in (None, [], "", True):
            with self.subTest(result=bad_result), self.assertRaises(ValueError):
                evidence_checks.validate_result("edit", bad_result, progress)
        for bad_rows in (None, {}, (), "", [], True):
            for source in ("checks", "progress"):
                with self.subTest(source=source, rows=bad_rows):
                    result, progress = fixture("edit")
                    if source == "checks":
                        result["checks"] = bad_rows
                    else:
                        progress = bad_rows
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)
        for row in (None, [], "", 1):
            for source in ("checks", "progress"):
                with self.subTest(source=source, row=row):
                    result, progress = fixture("edit")
                    rows = result["checks"] if source == "checks" else progress
                    rows.append(row)
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)

    def test_rejects_missing_checks_array(self):
        result, progress = fixture("edit")
        del result["checks"]
        with self.assertRaises(ValueError):
            evidence_checks.validate_result("edit", result, progress)

    def test_rejects_progress_missing_added_reordered_or_replaced_row(self):
        for mode in _LABELS:
            for mutation in ("missing", "added", "reordered", "replaced", "duplicate", "false"):
                with self.subTest(mode=mode, mutation=mutation):
                    result, progress = fixture(mode)
                    if mutation == "missing":
                        progress.pop()
                    elif mutation == "added":
                        progress.append({"label": "unreported_check", "passed": True})
                    elif mutation == "reordered":
                        progress[0], progress[1] = progress[1], progress[0]
                    elif mutation == "replaced":
                        progress[-1]["label"] = "unreported_check"
                    elif mutation == "duplicate":
                        progress.append(deepcopy(progress[0]))
                    else:
                        progress[-1]["passed"] = False
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result(mode, result, progress)

    def test_requires_valid_saved_revision_for_edit_and_reopen(self):
        invalid = (None, "", " ", False, 1, [], {}, "a" * 64,
                   "sha256:" + "a" * 63, "sha256:" + "a" * 65,
                   "sha256:" + "A" * 64, "sha256:" + "g" * 64,
                   "sha256:" + "a" * 64 + "\n")
        for mode in ("edit", "reopen"):
            for revision in invalid:
                with self.subTest(mode=mode, revision=revision):
                    result, progress = fixture(mode)
                    result["saved_revision"] = revision
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result(mode, result, progress)
            result, progress = fixture(mode)
            del result["saved_revision"]
            with self.assertRaises(ValueError):
                evidence_checks.validate_result(mode, result, progress)

    def test_contract_does_not_claim_a_saved_revision(self):
        result, progress = fixture("contract")
        self.assertIs(evidence_checks.validate_result("contract", result, progress), True)
        del result["saved_revision"]
        self.assertIs(evidence_checks.validate_result("contract", result, progress), True)

    def test_additional_checks_must_pass_and_match_progress(self):
        for passed in (True, False, 1):
            with self.subTest(passed=passed):
                result, progress = fixture("edit")
                extra = {"label": "additional_probe_check", "passed": passed}
                result["checks"].append(deepcopy(extra))
                progress.append(deepcopy(extra))
                if passed is True:
                    self.assertIs(evidence_checks.validate_result("edit", result, progress), True)
                else:
                    with self.assertRaises(ValueError):
                        evidence_checks.validate_result("edit", result, progress)

    def test_progress_compares_labels_and_passes_without_result_detail(self):
        result, progress = fixture("edit")
        result["checks"][0]["detail"] = {"snapshot": {"revision": "observed"}}
        self.assertIs(evidence_checks.validate_result("edit", result, progress), True)


if __name__ == "__main__":
    unittest.main()
