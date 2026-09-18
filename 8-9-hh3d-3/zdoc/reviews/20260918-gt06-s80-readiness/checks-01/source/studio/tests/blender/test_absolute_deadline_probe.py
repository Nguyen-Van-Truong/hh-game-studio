"""Pure deadline-runner parsing and evidence gates, with no native launch."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_absolute_deadline_probe as probe


def host():
    return {"exit_code": 0, "wrapper_exit_code": 0, "timed_out": False,
            "tree_verified": True, "target_pid": 101, "wrapper_pid": 100, "host": "native-host.json"}


def cleanup():
    return {"closed": True, "actual_process_exit": {"pid": 202, "exit_code": 0},
            "wrapper_exit_code": 0, "logs_overflow": False,
            "job": {"zero_observed": True, "active_count": 0, "closed": True, "handle_retained": False}}


class ParserAndWaitTests(unittest.TestCase):
    def test_post_jcs_integral_float_normalization_preserves_opaque_native_revision(self):
        from studio.host.blender.durable_session import queue
        from studio.protocol.core import canonical_bytes, parse_json

        snapshot = {"schema": "HH-BLENDER-FIXTURE-SCENE-1", "objects": [],
                    "units": {"system": "METRIC", "scale_length": 1.0}}
        native_revision = queue.c.digest(snapshot)
        observation = {"snapshot": snapshot, "revision": native_revision,
                       "context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
                       "public_ack": False, "undo_supported": True}
        request = probe.command("float-inspect", "scene.inspect")
        receipt = {"command_id": request["command_id"], "command_digest": queue.c.digest(request),
                   "state": "COMPLETED", "public_ack": False, "result": observation}
        received = parse_json(canonical_bytes(receipt))
        self.assertIs(type(received["result"]["snapshot"]["units"]["scale_length"]), int)
        self.assertNotEqual(queue.c.digest(received["result"]["snapshot"]), native_revision)
        checked = probe.checked_observation(request, received)
        self.assertEqual(checked["revision"], native_revision)
        self.assertEqual(checked, received["result"])
        # The received JCS result hash is a separate, reproducible domain.
        self.assertEqual(probe.sha(canonical_bytes(received)), probe.sha(canonical_bytes(receipt)))

    def test_observation_requires_matching_completed_command_and_create_postconditions(self):
        from studio.host.blender.durable_session import queue
        from studio.protocol.core import canonical_bytes, parse_json

        before = {"snapshot": {"objects": []}, "revision": "sha256:" + "a" * 64,
                  "context": {"mode": "OBJECT", "active_id": None, "selected_ids": []},
                  "public_ack": False, "undo_supported": True}
        request = probe.command("bound-create", "mesh.create_box", before,
                                {"object_id": "box", "size": [1, 2, 3]})
        after = {**before, "revision": "sha256:" + "b" * 64}
        result = {"operation": "mesh.create_box", "before_revision": before["revision"],
                  "after": after, "native_operator_finished": True, "status": "INTERNAL_UI_READBACK",
                  "public_ack": False}
        receipt = {"command_id": request["command_id"], "command_digest": queue.c.digest(request),
                   "state": "COMPLETED", "public_ack": False, "result": result}
        self.assertEqual(probe.checked_observation(request, receipt), after)
        for changes in ({"command_id": "other"}, {"command_digest": "sha256:" + "0" * 64},
                        {"state": "REJECTED"}, {"public_ack": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                probe.checked_observation(request, {**receipt, **changes})
        for changes in ({"before_revision": "sha256:" + "c" * 64}, {"native_operator_finished": False},
                        {"operation": "history.undo"}, {"public_ack": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                probe.checked_observation(request, {**receipt, "result": {**result, **changes}})
        normalized = parse_json(canonical_bytes(receipt))
        normalized["result"]["after"]["revision"] = "not-a-native-revision"
        with self.assertRaises(ValueError):
            probe.checked_observation(request, normalized)

    def test_help_does_not_load_bootstrap_or_launch_native(self):
        with patch.object(probe, "load", side_effect=AssertionError("bootstrap must not load")):
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
                probe.main(["--help"])
        self.assertEqual(raised.exception.code, 0)

    def test_required_run_identity_and_unit_mode_are_bounded(self):
        parsed = probe.parser().parse_args(["--output", "unused", "--run-id", "GT04-Deadline-01"])
        self.assertEqual(parsed.unit_suite, "focused")
        for args in (["--output", "unused"], ["--output", "unused", "--run-id", "../escape"],
                     ["--output", "unused", "--run-id", "valid", "--unit-suite", "partial"]):
            with self.subTest(args=args), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                probe.parser().parse_args(args)

    def test_wait_observes_elapsed_wall_deadline(self):
        clock = [0.0]
        wall = [1000]

        def pause(seconds):
            clock[0] += seconds
            wall[0] += int(seconds * 1000)

        observed = probe.wait_past_deadline(1020, wall=lambda: wall[0], clock=lambda: clock[0], pause=pause)
        self.assertGreater(observed, 1020)
        self.assertLess(clock[0], .1)

    def test_wait_stays_bounded_during_wall_clock_rollback(self):
        clock = [0.0]
        sleeps = []

        def pause(seconds):
            sleeps.append(seconds)
            clock[0] += seconds

        with self.assertRaisesRegex(TimeoutError, "WAIT_BOUND"):
            probe.wait_past_deadline(1000, wall=lambda: 1, clock=lambda: clock[0], pause=pause, timeout=.05)
        self.assertAlmostEqual(clock[0], .05)
        self.assertEqual(len(sleeps), 3)

    def test_unit_inventory_rejects_false_exit_like_counts_duplicates_and_omissions(self):
        counts = {"run": 2, "failures": 0, "errors": 0, "skips": 0}
        inventory = probe.UNIT_INVENTORY + json.dumps(["a.test", "b.test"])
        complete = probe.UNIT_COMPLETE + json.dumps(counts)
        self.assertEqual(probe.unit_completion(inventory + "\n" + complete), (True, [counts]))
        bad = [inventory, complete, inventory + "\n" + complete + "\n" + complete,
               probe.UNIT_INVENTORY + '["a.test","a.test"]\n' + complete,
               inventory + "\n" + complete.replace('"run": 2', '"run": 1'),
               inventory + "\n" + complete.replace('"skips": 0', '"skips": false'),
               inventory + "\n" + complete.replace('"errors": 0', '"errors": 1'),
               probe.UNIT_INVENTORY + "broken json"]
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(probe.unit_completion(value)[0])

    def test_focused_unit_patterns_require_sources_and_include_writer_when_present(self):
        with tempfile.TemporaryDirectory() as name:
            snapshot = Path(name)
            tests = snapshot / "tests/blender"
            tests.mkdir(parents=True)
            self.assertEqual(probe.unit_patterns(snapshot, "all"), ["test_*.py"])
            with self.assertRaisesRegex(ValueError, "required focused"):
                probe.unit_patterns(snapshot, "focused")
            expected = ["test_absolute_deadline.py", "test_absolute_deadline_probe.py",
                        "test_ui_queue.py", "test_client_write_catalog.py"]
            for item in expected:
                (tests / item).write_bytes(b"")
            self.assertEqual(probe.unit_patterns(snapshot, "focused"), expected)
            (tests / "test_client_writer_session.py").write_bytes(b"")
            self.assertEqual(probe.unit_patterns(snapshot, "focused"), expected + ["test_client_writer_session.py"])

    def test_unit_program_compiles_without_executing_tests(self):
        source = probe.unit_program(["test_absolute_deadline.py"])
        compile(source, "<deadline-unit-program>", "exec")
        self.assertIn(repr(probe.UNIT_INVENTORY), source)
        self.assertIn(repr(probe.UNIT_COMPLETE), source)

    def test_invalid_json_is_encoded_before_artifact_open(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            with self.assertRaises(ValueError):
                probe.write_json(output, "invalid.json", {"value": float("nan")})
            self.assertFalse((output / "invalid.json").exists())

    def test_inventory_hash_and_size_come_from_same_bytes_and_exclude_source(self):
        with tempfile.TemporaryDirectory() as name:
            output = Path(name)
            (output / "source").mkdir()
            (output / "source/ignored.py").write_bytes(b"source")
            raw = b"observed\n"
            (output / "receipt.txt").write_bytes(raw)
            self.assertEqual(probe.evidence_inventory(output), {
                "receipt.txt": {"bytes": len(raw), "sha256": probe.sha(raw)}})


class NativeArtifactGates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.directory = self.output / ("blender-" + "a" * 32)
        self.directory.mkdir()
        self.manifest = {"run_id": "deadline-test", "source_closure_sha256": "b" * 64}
        self.report = {
            **self.manifest, "passed": True, "probe_pid": 101, "native_pid": 202,
            "gui_directory": self.directory.name, "cleanup": cleanup(),
            "checks": [{"label": label, "passed": True} for label in sorted(probe.REQUIRED_CHECKS)],
            "public_ack": False, "public_write_facade": False,
            "private_fixture_lease_only": True, "formal_acceptance": False,
        }
        self.persist()

    def persist(self):
        (self.output / "source-closure.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        (self.output / "native-host.json").write_text('{"target_pid":101,"exit_code":0}', encoding="utf-8")
        (self.output / probe.REPORT).write_text(json.dumps(self.report), encoding="utf-8")
        (self.output / "native-stdout.txt").write_text(probe.NATIVE_COMPLETE + json.dumps({
            "passed": True, "checks": len(self.report["checks"])}), encoding="utf-8")
        (self.directory / "process-exit.json").write_text(json.dumps(
            self.report["cleanup"]["actual_process_exit"]), encoding="utf-8")
        (self.directory / "close.json").write_text(json.dumps(self.report["cleanup"]), encoding="utf-8")

    def test_matching_raw_process_and_job_artifacts_required(self):
        self.assertTrue(probe.native_completion(self.output, host()))
        for key, value in (("target_pid", 999), ("exit_code", False), ("tree_verified", False), ("timed_out", True)):
            with self.subTest(key=key):
                self.assertFalse(probe.native_completion(self.output, {**host(), key: value}))

    def test_missing_or_falsified_raw_exit_and_retained_job_reject_success_banner(self):
        (self.directory / "process-exit.json").unlink()
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        (self.directory / "process-exit.json").write_text('{"pid":202,"exit_code":false}', encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        raw = copy.deepcopy(self.report["cleanup"])
        raw["job"]["handle_retained"] = True
        (self.directory / "close.json").write_text(json.dumps(raw), encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_omitted_duplicate_or_unknown_semantic_checks_are_rejected(self):
        original = copy.deepcopy(self.report["checks"])
        variants = [original[:-1], original + [original[0]],
                    original[:-1] + [{"label": "invented-check", "passed": True}]]
        for rows in variants:
            self.report["checks"] = rows
            self.persist()
            with self.subTest(rows=len(rows)):
                self.assertFalse(probe.native_completion(self.output, host()))

    def test_duplicate_completion_marker_and_malformed_artifact_fail_closed(self):
        path = self.output / "native-stdout.txt"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\n" + text, encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        (self.output / probe.REPORT).write_text("[]", encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_native_proof_cannot_claim_public_grant_ack_acceptance_or_another_source(self):
        changes = (("public_ack", True), ("public_write_facade", True),
                   ("private_fixture_lease_only", False), ("formal_acceptance", True),
                   ("run_id", "other-run"), ("source_closure_sha256", "c" * 64),
                   ("gui_directory", "../outside"), ("probe_pid", True))
        baseline = copy.deepcopy(self.report)
        for key, value in changes:
            self.report = {**baseline, key: value}
            self.persist()
            with self.subTest(key=key):
                self.assertFalse(probe.native_completion(self.output, host()))


if __name__ == "__main__":
    unittest.main()
