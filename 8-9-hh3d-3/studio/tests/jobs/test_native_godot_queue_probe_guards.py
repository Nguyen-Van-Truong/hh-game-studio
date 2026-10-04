"""Pure guards for GT07 native probe closeout and receipt-loss evidence."""
from __future__ import annotations

import importlib.util
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
_spec = importlib.util.spec_from_file_location(
    "gt07_queue_probe_guard_module", STUDIO / "tests/jobs/run_native_godot_queue_probe.py")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)


class NativeGodotQueueProbeGuardTests(unittest.TestCase):
    def test_crash_snapshot_reads_response_only_at_durable_terminal(self):
        # Real reducer histories reproduce run25: RELOAD is SELECTED, where
        # lookup_response must raise rather than return an absent receipt.
        spec = importlib.util.spec_from_file_location(
            'gt07_cut_state_fixtures', STUDIO / 'tests/godot/test_publication_state_v4.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        from studio.protocol.core import ValidationError
        for operation in ('scene.save', 'script_text.replace'):
            for phase in ('PREPARED', 'VALIDATED', 'ACTIVATING', 'SELECTED', 'COMMITTED'):
                with self.subTest(operation=operation, phase=phase):
                    state = fixture.state.replay(fixture.history(operation, until=phase))
                    journal = SimpleNamespace(
                        lookup=lambda *args: fixture.state.lookup(state, *args),
                        lookup_response=lambda *args: fixture.state.lookup_response(state, *args))
                    args = ('command.one', fixture.rev('command.one'))
                    if phase == 'COMMITTED':
                        self.assertEqual(_module._durable_response(journal, *args),
                                         journal.lookup_response(*args))
                    else:
                        with self.assertRaisesRegex(ValidationError, 'RESPONSE_NOT_DURABLE'):
                            journal.lookup_response(*args)
                        self.assertIsNone(_module._durable_response(journal, *args))

    def test_crash_snapshot_does_not_hide_corrupt_terminal_or_missing_command(self):
        journal = SimpleNamespace(lookup=lambda *_: {'phase': 'COMMITTED'},
                                  lookup_response=lambda *_: (_ for _ in ()).throw(
                                      ValueError('RESPONSE_NOT_DURABLE')))
        with self.assertRaisesRegex(ValueError, 'RESPONSE_NOT_DURABLE'):
            _module._durable_response(journal, 'command.one', 'digest')
        journal.lookup = lambda *_: None
        with self.assertRaisesRegex(RuntimeError, 'COMMAND_MISSING'):
            _module._durable_response(journal, 'command.one', 'digest')

    def test_close_proof_requires_actual_pid_exit_and_clean_job(self):
        identity = {"pid": 1234, "session_id": "editor.fixture"}
        clean = {
            "closed": True, "held": False, "logs_overflow": False,
            "actual_process_exit": {"pid": 1234, "exit_code": 0},
            "wrapper_exit_code": 0,
            "job": {"configured": True, "assigned": True, "closed": True,
                    "zero_observed": True, "tainted": False,
                    "handle_retained": False, "close_uncertain": False,
                    "create_uncertain": False, "active_count": 0,
                    "failed_operations": [], "native_error": None},
        }
        self.assertTrue(_module._editor_close_proof(clean, identity)["valid"])
        clean["actual_process_exit"]["pid"] = 9999
        self.assertFalse(_module._editor_close_proof(clean, identity)["valid"])

    def test_recovery_guard_requires_fence_and_unchanged_heads(self):
        proof = {
            "receipt_boundary": "record_owner_result",
            "injection_count": 1, "reconciled_status": "COMMITTED",
            "response_before": {"status": "COMMITTED"},
            "response_after": {"status": "COMMITTED"},
            "submit_calls_before": 1, "submit_calls_after": 1,
            "fence_before": {"stream_id": "stream.fixture", "generation": 1},
            "fence_after": {"stream_id": "stream.fixture", "generation": 1},
            "queue_before_loss": {"sequence": 3},
            "queue_after_loss": {"sequence": 3},
            "queue_reopened": {"sequence": 3},
            "queue_after_reconcile": {"sequence": 4},
            "queue_result_event": {"kind": "OWNER_RESULT"},
            "expected_queue_result_event": {"kind": "OWNER_RESULT"},
            "journal_before_loss": {"sequence": 3},
            "journal_after_loss": {"sequence": 14},
            "journal_after_reconcile": {"sequence": 14},
            "native_before_reconcile": {"generation": 2},
            "native_after_reconcile": {"generation": 2},
        }
        self.assertTrue(_module._recovery_evidence_complete(True, proof))
        for key, value in (("fence_after", {"stream_id": "stream.fixture", "generation": 2}),
                           ("submit_calls_after", 2), ("queue_after_reconcile", {"sequence": 3}),
                           ("journal_after_reconcile", {"sequence": 15}),
                           ("queue_result_event", {"kind": "ENQUEUE"}),
                           ("native_after_reconcile", {"generation": 3})):
            with self.subTest(key=key):
                bad = copy.deepcopy(proof)
                bad[key] = value
                self.assertFalse(_module._recovery_evidence_complete(True, bad))
        self.assertFalse(_module._recovery_evidence_complete(True, {"no_native_replay": True}))

    def test_non_recovery_run_has_no_extra_recovery_claim(self):
        self.assertTrue(_module._recovery_evidence_complete(False, None))

    def test_public_route_and_deadlines_dry_run_never_launch_engine(self):
        with patch("subprocess.Popen", side_effect=AssertionError("unexpected engine")):
            for operation in ("scene.node.update", "scene.save", "script_text.replace"):
                proof = _module.dry_run_contract(operation)
                self.assertEqual(proof["operation"], operation)
                self.assertTrue(proof["public_lease_route_validated"])
                self.assertTrue(proof["deadline_lower_bound_rejected"])
                self.assertTrue(proof["deadline_upper_bound_rejected"])
                self.assertFalse(proof["native_effect"])

    def test_recovery_cannot_target_an_edit(self):
        with self.assertRaisesRegex(ValueError, "RECOVERY_PROBE_REQUIRES_SCRIPT"):
            _module.dry_run_contract("scene.node.update", True)


if __name__ == "__main__":
    unittest.main()
