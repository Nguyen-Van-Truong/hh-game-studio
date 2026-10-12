"""Unit checks for P10 host receipts and the K10 smoke trace."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from studio.tests.conformance.gt10pc_p10 import verify_engine_host, verify_k10_trace
from studio.tests.godot.fixture_lifecycle_manifest import parse_log

FIXTURE = Path(__file__).resolve().parent / "data" / "k10-smoke-stdout.txt"


def _lines(text: str) -> tuple[dict, list, list]:
    return parse_log(text)


def _render(summary: dict, states: list, inputs: list) -> str:
    rows = ["HH_FIXTURE_LIFECYCLE_INPUT " + json.dumps(edge, sort_keys=True) for edge in inputs]
    rows.extend("HH_FIXTURE_LIFECYCLE_STATE " + json.dumps(state, sort_keys=True) for state in states)
    rows.append("HH_FIXTURE_LIFECYCLE_SUMMARY " + json.dumps(summary, sort_keys=True))
    return "\n".join(rows) + "\n"


class K10TraceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = FIXTURE.read_text(encoding="utf-8")
        self.summary, self.states, self.inputs = _lines(self.raw)

    def test_recorded_smoke_stdout_passes(self) -> None:
        verify_k10_trace(self.raw)

    def test_wrong_seed_is_rejected(self) -> None:
        summary = dict(self.summary)
        summary["seed"] = 11111
        with self.assertRaises(ValueError) as caught:
            verify_k10_trace(_render(summary, self.states, self.inputs))
        self.assertIn("GT10PC_P10_K10_SEED", str(caught.exception))

    def test_missing_release_edge_is_rejected(self) -> None:
        # Keep a single KEY_D press and drop its release (and any later D press).
        seen_press = False
        inputs = []
        for edge in self.inputs:
            if edge.get("key") == 68:
                if edge.get("state") == "released" or seen_press:
                    continue
                seen_press = True
            inputs.append(edge)
        with self.assertRaises(ValueError) as caught:
            verify_k10_trace(_render(self.summary, self.states, inputs))
        self.assertIn("GT10PC_P10_K10_HELD_EDGE", str(caught.exception))

    def test_pause_world_change_is_rejected(self) -> None:
        states = []
        for state in self.states:
            if state.get("event") == "resume":
                changed = dict(state)
                changed["world"] = dict(state["world"])
                changed["world"]["tick"] = state["world"]["tick"] + 1
                states.append(changed)
            else:
                states.append(state)
        with self.assertRaises(ValueError) as caught:
            verify_k10_trace(_render(self.summary, states, self.inputs))
        self.assertIn("GT10PC_P10_K10_PAUSE_WORLD", str(caught.exception))

    def test_key_d_not_held_between_edges_is_rejected(self) -> None:
        states = []
        for state in self.states:
            if state.get("event") == "pause":
                changed = dict(state)
                changed["held_keys"] = []
                states.append(changed)
            else:
                states.append(state)
        with self.assertRaises(ValueError) as caught:
            verify_k10_trace(_render(self.summary, states, self.inputs))
        self.assertIn("GT10PC_P10_K10_HELD_KEYS", str(caught.exception))


class EngineHostReceiptTests(unittest.TestCase):
    def _write(self, root: Path, *, pid: int = 42, exit_code: int = 0, stdout: bytes = b"ok\n",
               stderr: bytes = b"") -> None:
        (root / "w02-stdout.txt").write_bytes(stdout)
        (root / "w02-stderr.txt").write_bytes(stderr)
        (root / "w02-host.json").write_text(json.dumps({
            "target_pid": pid, "exit_code": exit_code, "started_at": "t"}), encoding="utf-8")
        (root / "w02-receipt.json").write_text(json.dumps({
            "target_pid": pid, "exit_code": exit_code, "wrapper_exit_code": 0,
            "timed_out": False, "tree_verified": True,
            "stdout": "w02-stdout.txt", "stderr": "w02-stderr.txt",
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest()}), encoding="utf-8")

    def test_receipt_matches_raw_streams(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root)
            host = verify_engine_host(root, "w02")
            self.assertEqual(host["target_pid"], 42)

    def test_stream_hash_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root)
            (root / "w02-stdout.txt").write_bytes(b"tampered\n")
            with self.assertRaises(ValueError) as caught:
                verify_engine_host(root, "w02")
            self.assertIn("GT10PC_P10_ENGINE_HOST", str(caught.exception))

    def test_non_positive_pid_and_failed_exit_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root, pid=0, exit_code=1)
            with self.assertRaises(ValueError):
                verify_engine_host(root, "w02")


if __name__ == "__main__":
    unittest.main()
