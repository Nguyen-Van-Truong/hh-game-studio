"""Self-contained retained-view tests. Synthetic fixture is not native evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import inspector
from studio.host.replay.observation import ObservationRejected
from studio.protocol.core import parse_json, MAX_ARRAY_ITEMS
from studio.tests.replay.test_observation import fixture, encoded, sha


class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="hh-gt06-inspector-unit-")
        cls.addClassCleanup(cls.directory.cleanup)
        cls.project = Path(cls.directory.name)
        cls.trace, cls.binding, cls.process, cls.report = fixture(cls.project)
        cls.report_raw, cls.process_raw = encoded(cls.report), encoded(cls.process)
        cls.capture = {"schema": "HH-GT06-NATIVE-CAPTURE-1", "run_id": cls.binding["run_id"],
            "completed_native": True, "formal_acceptance": False, "public_ack": False,
            "binding": cls.binding, "process": cls.process["identity"], "report_sha256": sha(cls.report_raw),
            "source_unchanged": True, "import_capture_sha256": "1"*64, "runtime_capture_sha256": "2"*64,
            "process_metrics_sha256": sha(cls.process_raw)}
        cls.capture_raw = encoded(cls.capture)
        cls.expected = {key: cls.binding[key] for key in ("runtime_instance_id", "generation",
            "source_closure_sha256", "runtime_snapshot_sha256")}
        cls.expected.update(report_sha256=sha(cls.report_raw), **cls.process["identity"])

    def setUp(self):
        self.view = self.admit()
        self.payload = {"expected": copy.deepcopy(self.expected), "properties": ["phase", "body_position"]}

    def admit(self, **changes):
        values = {"native_capture_raw": self.capture_raw, "native_capture_sha256": sha(self.capture_raw),
            "trace": self.trace, "binding": copy.deepcopy(self.binding), "process_raw": self.process_raw,
            "project": self.project, "config_speed": 3.0}
        raw = changes.pop("report_raw", self.report_raw)
        values.update(changes)
        view = inspector.register_view(raw, **values)
        self.addCleanup(inspector.close_view, view)
        return view

    def query(self, **changes):
        return inspector.query_view(self.view, {**self.payload, **changes})

    def reject_query(self, code, **changes):
        with self.assertRaises(inspector.InspectorRejected) as error:
            self.query(**changes)
        self.assertEqual(error.exception.code, code)

    def test_query_is_explicitly_historical_completed_and_schema_bounded(self):
        result = self.query(properties=sorted(inspector.PROPERTIES))
        self.assertTrue(result["historical"] and result["completed"])
        self.assertFalse(result["live"] or result["formal_acceptance"])
        self.assertEqual(result["returned_count"], 8)
        self.assertEqual(result["total_matches"], 360)
        self.assertEqual(result["rows"][0]["tick"], 0)
        self.assertEqual(set(result["rows"][0]["properties"]), inspector.PROPERTIES)
        self.assertEqual(parse_json(encoded(result)), result)
        self.assertLess(len(encoded(result)), inspector.MAX_RESULT_BYTES)
        self.assertEqual(MAX_ARRAY_ITEMS, 256)
        self.assertEqual(inspector.MAX_RESULT_BYTES, 262144)

    def test_filter_and_pagination_cover_each_matching_tick_once(self):
        payload = {**self.payload, "phase": "PAUSED", "tick_min": 145, "tick_max": 205}
        ticks = []
        while True:
            result = inspector.query_view(self.view, payload)
            self.assertEqual(result["total_matches"], 50)
            self.assertLessEqual(len(result["rows"]), 8)
            ticks.extend(row["tick"] for row in result["rows"])
            if result["next_cursor"] is None:
                break
            payload["cursor"] = result["next_cursor"]
        self.assertEqual(ticks, list(range(150, 200)))

    def test_empty_filter_returns_empty_page_without_cursor(self):
        result = self.query(phase="MENU", tick_min=100, tick_max=200)
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["returned_count"], 0)
        self.assertEqual(result["total_matches"], 0)
        self.assertIsNone(result["next_cursor"])

    def test_deep_mutation_of_result_cannot_change_registered_view(self):
        first = self.query(properties=["animation", "camera"])
        first["rows"][0]["properties"]["camera"]["position"][0] = 999
        first["rows"][0]["properties"]["animation"]["clip"] = "forged"
        first["provenance"]["binding"]["source_closure_sha256"] = "0"*64
        first["semantics"]["all_postconditions"] = False
        second = self.query(properties=["animation", "camera"])
        self.assertEqual(second["rows"][0]["properties"]["camera"]["position"][0], 5.2)
        self.assertEqual(second["rows"][0]["properties"]["animation"]["clip"], "idle")
        self.assertEqual(second["provenance"]["binding"], self.binding)
        self.assertTrue(second["semantics"]["all_postconditions"])

    def test_admission_validates_observation_once_queries_have_no_file_access(self):
        with patch.object(inspector, "validate_observation", wraps=inspector.validate_observation) as validate:
            view = self.admit()
            self.assertEqual(validate.call_count, 1)
            with patch.object(Path, "open", side_effect=AssertionError("query attempted file I/O")):
                one = inspector.query_view(view, self.payload)
                inspector.query_view(view, {**self.payload, "cursor": one["next_cursor"]})
            self.assertEqual(validate.call_count, 1)

    def test_all_expected_context_components_reject_stale_values(self):
        replacements = {"runtime_instance_id": "another.runtime", "generation": 2,
            "source_closure_sha256": "0"*64, "runtime_snapshot_sha256": "0"*64,
            "report_sha256": "0"*64, "pid": 1235, "process_start": "windows:123456790"}
        for key, value in replacements.items():
            with self.subTest(key=key):
                self.reject_query("INSPECT_STALE_CONTEXT", expected={**self.expected, key: value})

    def test_boolean_and_oversized_process_identity_cannot_alias_valid_context(self):
        for key, value in (("generation", True), ("pid", True), ("process_start", "windows:18446744073709551616")):
            with self.subTest(key=key):
                self.reject_query("INSPECT_EXPECTED_TYPE", expected={**self.expected, key: value})

    def test_unknown_paths_properties_and_fields_reject_closed(self):
        for properties in (["camera.position"], ["../config/fixture_actor.gd"], ["body_position/0"], [], ["phase", "phase"]):
            with self.subTest(properties=properties):
                self.reject_query("INSPECT_PROPERTIES", properties=properties)
        self.reject_query("INSPECT_QUERY_FIELDS", path="out/report.json")
        self.reject_query("INSPECT_EXPECTED_FIELDS", expected={**self.expected, "path": "ignored"})

    def test_page_filter_and_cursor_caps_reject_before_output(self):
        for size in (0, 9, True, 1.5):
            self.reject_query("INSPECT_PAGE_SIZE", page_size=size)
        for change in ({"phase": "LIVE"}, {"tick_min": -1}, {"tick_max": 600}, {"tick_min": 5, "tick_max": 4}):
            self.reject_query("INSPECT_FILTER", **change)
        self.reject_query("INSPECT_CURSOR", cursor="x"*(inspector.MAX_CURSOR_CHARS+1))
        with patch.object(inspector, "MAX_RESULT_BYTES", 16):
            self.reject_query("INSPECT_RESULT_BYTES")

    def test_cursor_tampering_filter_or_property_switch_cannot_change_page_meaning(self):
        cursor = self.query()["next_cursor"]
        changed = cursor[:-1] + ("0" if cursor[-1] != "0" else "1")
        self.reject_query("INSPECT_CURSOR", cursor=changed)
        for change in ({"phase": "PLAY"}, {"tick_min": 1}, {"tick_max": 300},
                       {"page_size": 4}, {"properties": ["sim_tick"]}):
            self.reject_query("INSPECT_CURSOR", cursor=cursor, **change)

    def test_cursor_cannot_cross_registered_views_even_for_same_report(self):
        cursor = self.query()["next_cursor"]
        other = self.admit()
        with self.assertRaisesRegex(inspector.InspectorRejected, "^INSPECT_CURSOR$"):
            inspector.query_view(other, {**self.payload, "cursor": cursor})

    def test_opaque_factory_forgery_and_token_tampering_rejected(self):
        with self.assertRaisesRegex(inspector.InspectorRejected, "^INSPECT_VIEW_FACTORY$"):
            inspector.RetainedView()
        forged = object.__new__(inspector.RetainedView)
        object.__setattr__(forged, "_token", self.view._token)
        with self.assertRaisesRegex(inspector.InspectorRejected, "^INSPECT_VIEW$"):
            inspector.query_view(forged, self.payload)
        with self.assertRaises(AttributeError):
            self.view._token = "tampered"
        object.__setattr__(self.view, "_token", "tampered")
        self.reject_query("INSPECT_VIEW")

    def test_closed_view_cannot_be_queried_and_repeat_close_is_safe(self):
        inspector.close_view(self.view)
        inspector.close_view(self.view)
        self.reject_query("INSPECT_VIEW")

    def test_registry_cap_is_enforced_before_expensive_validation(self):
        with patch.object(inspector, "MAX_REGISTERED_VIEWS", 1), patch.object(inspector, "validate_observation") as validate:
            with self.assertRaisesRegex(inspector.InspectorRejected, "^INSPECT_VIEW_CAP$"):
                self.admit()
            validate.assert_not_called()

    def test_capture_anchor_report_bytes_and_process_bytes_are_independently_bound(self):
        for change, code in (({"native_capture_sha256": "0"*64}, "INSPECT_CAPTURE_ANCHOR"),
                             ({"report_raw": self.report_raw+b" "}, "INSPECT_REPORT_HASH"),
                             ({"process_raw": self.process_raw+b" "}, "INSPECT_PROCESS_HASH")):
            with self.subTest(code=code), self.assertRaisesRegex(inspector.InspectorRejected, "^"+code+"$"):
                self.admit(**change)

    def test_rehashed_capture_cannot_claim_incomplete_run_or_different_pid(self):
        for field, value, code in (("completed_native", False, "INSPECT_CAPTURE_COMPLETION"),
                                   ("source_unchanged", False, "INSPECT_CAPTURE_COMPLETION"),
                                   ("process", {"pid": 4321, "process_start": "windows:123456789"}, "INSPECT_CAPTURE_BINDING")):
            capture = {**self.capture, field: value}; raw = encoded(capture)
            with self.subTest(field=field), self.assertRaisesRegex(inspector.InspectorRejected, "^"+code+"$"):
                self.admit(native_capture_raw=raw, native_capture_sha256=sha(raw))

    def test_resealed_bad_native_semantics_cannot_register(self):
        report = copy.deepcopy(self.report)
        row = report["observations"][40]
        row["state"]["body_position"][0] = 0
        row["state_json"] = encoded(row["state"]).decode()
        row["snapshot_sha256"] = sha(row["state_json"].encode())
        raw = encoded(report); capture = {**self.capture, "report_sha256": sha(raw)}; capture_raw = encoded(capture)
        with self.assertRaisesRegex(ObservationRejected, "^OBS_MOVEMENT$"):
            self.admit(report_raw=raw, native_capture_raw=capture_raw, native_capture_sha256=sha(capture_raw))

    def test_artifact_byte_caps_are_admitted_before_hash_or_parser_work(self):
        for change, code in (({"native_capture_raw": b"x"*16385}, "INSPECT_CAPTURE_BYTES"),
                             ({"process_raw": b"x"*1048577}, "INSPECT_PROCESS_BYTES"),
                             ({"report_raw": b"x"*(inspector.MAX_REPORT_BYTES+1)}, "INSPECT_REPORT_BYTES")):
            with self.subTest(code=code), self.assertRaisesRegex(inspector.InspectorRejected, "^"+code+"$"):
                self.admit(**change)

    def test_fault_view_retains_explicit_failure_even_though_completed(self):
        with tempfile.TemporaryDirectory(prefix="hh-gt06-inspector-fault-unit-") as directory:
            project = Path(directory)
            trace, binding, process, report = fixture(project, 0.0)
            report_raw, process_raw = encoded(report), encoded(process)
            capture = {**self.capture, "binding": binding, "process": process["identity"],
                "report_sha256": sha(report_raw), "process_metrics_sha256": sha(process_raw)}
            capture_raw = encoded(capture)
            view = self.admit(report_raw=report_raw, native_capture_raw=capture_raw,
                native_capture_sha256=sha(capture_raw), trace=trace, binding=binding,
                process_raw=process_raw, project=project, config_speed=0.0)
            result = inspector.query_view(view, {**self.payload, "expected": {**self.expected, "report_sha256": sha(report_raw)}})
            self.assertTrue(result["completed"] and result["semantics"]["complete"])
            self.assertTrue(result["semantics"]["movement_fault_observed"])
            self.assertFalse(result["semantics"]["all_postconditions"])


if __name__ == "__main__":
    unittest.main()
