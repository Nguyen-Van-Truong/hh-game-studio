"""Offline contract checks for the registered K5/K7 scenario interface."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tests.conformance import run_gt09_registered_failures as verifier


class GT09RegisteredFailureTests(unittest.TestCase):
    def test_profile_is_bound_but_current_route_is_private_and_scriptless(self):
        profile = verifier.registered_profile()
        self.assertEqual(profile["authority"], 0)
        self.assertFalse(profile["runtime_enabled"])
        self.assertFalse(profile["script_enabled"])
        self.assertRegex(profile["catalog_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("script.create", profile["operations"])

    def test_hostile_markers_are_source_bound_and_not_native_observations(self):
        report = verifier.verify_hostile_markers()
        self.assertTrue(report["verified"])
        self.assertFalse(report["native_observed"])
        self.assertEqual(len(report["rows"]), 7)
        for row in report["rows"]:
            self.assertEqual(row["behaviour_line"], row["marker_line"] + 1)

    def test_empty_report_is_open_and_never_launches_native(self):
        with tempfile.TemporaryDirectory() as temp:
            report = verifier.build_report(evidence_root=Path(temp))
        self.assertEqual(report["k5"]["status"], "OPEN")
        self.assertEqual(report["k7"]["status"], "OPEN")
        self.assertEqual(report["k5"]["route_reason"], "REGISTERED_SCRIPT_ROUTE_DISABLED")
        self.assertFalse(report["native_launch_performed"])
        self.assertFalse(report["acceptance"])
        self.assertFalse(report["package_ready"])

    def test_static_claim_cannot_become_k5_native_evidence(self):
        profile = verifier.registered_profile()
        closure = verifier.source_binding()["source_closure_sha256"]
        receipt = {
            "schema": verifier.RECEIPT_SCHEMA,
            "kind": "k5-failure",
            "run_id": "unit-static-k5",
            "source_closure_sha256": closure,
            "authority": 0,
            "public_ack": False,
            "registered_profile": profile["profile"],
            "profile_catalog_digest": profile["catalog_digest"],
            "registered_discovery": {
                "fixture_enabled": True,
                "public_runtime_enabled": False,
                "authority": 0,
                "public_ack": False,
                "profile": profile,
            },
            "failure_case": "syntax",
            "failure": {
                "observed": True,
                "last_good_preserved": True,
                "reopen_readback_equal": True,
                "retry_equal": True,
                "retry_no_redispatch": True,
                "exit_preserved": True,
            },
            "process": {
                "host_exit": 45,
                "container_exit": 45,
                "timed_out": False,
                "stream_cap_exceeded": False,
                "owned_tree_zero": True,
            },
            # A unit dictionary has no independently captured native receipt.
            "native_observed": False,
            "evidence_origin": "unit-test",
        }
        result = verifier.verify_k5_receipt(receipt, profile=profile, source_closure=closure)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "OPEN")
        self.assertIn("REGISTERED_SCRIPT_ROUTE_DISABLED", result["errors"])
        self.assertIn("RECEIPT_NATIVE_OBSERVATION", result["errors"])
        self.assertIn("RECEIPT_EVIDENCE_ORIGIN", result["errors"])

    def test_exit_mismatch_is_rejected_even_when_claimed_fields_look_good(self):
        profile = verifier.registered_profile()
        closure = verifier.source_binding()["source_closure_sha256"]
        receipt = {
            "schema": verifier.RECEIPT_SCHEMA,
            "kind": "k7-hostile",
            "run_id": "native-boundary",
            "source_closure_sha256": closure,
            "authority": 0,
            "public_ack": False,
            "registered_profile": profile["profile"],
            "profile_catalog_digest": profile["catalog_digest"],
            "registered_discovery": {"fixture_enabled": True,
                "public_runtime_enabled": False, "authority": 0,
                "public_ack": False, "profile": profile},
            "hostile_case": "boundary",
            "marker_observation": {"name": "source_write", "count": 1, "source_bound": True},
            "sandbox": {"source_write_denied": True, "root_write_denied": True,
                "docker_socket_absent": True, "network_denied": True,
                "acceptance": False},
            "process": {"host_exit": 0, "container_exit": 1, "timed_out": False,
                "stream_cap_exceeded": False, "owned_tree_zero": True},
            "native_observed": True,
            "evidence_origin": "registered-native",
        }
        result = verifier.verify_k7_receipt(receipt, profile=profile, source_closure=closure)
        self.assertFalse(result["valid"])
        self.assertIn("PROCESS_EXIT_MISMATCH", result["errors"])


if __name__ == "__main__":
    unittest.main()

