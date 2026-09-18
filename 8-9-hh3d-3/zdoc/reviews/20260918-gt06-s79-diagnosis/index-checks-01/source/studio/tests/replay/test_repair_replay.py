"""Adversarial synthetic repair receipts; these tests never launch an engine.

Rehashed negative captures deliberately bypass the outer artifact digest check
to exercise semantic admission. The composition tests mock native execution;
their success is not evidence of a native managed repair.
"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from studio.host.replay import repair_replay as replay
from studio.host.replay.trace import default_trace


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def configuration(speed):
    return ("extends Node3D\n@export var fixture_value: int = 1\n"
            "@export var move_speed: float = " + speed + "\n").encode()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if type(value) is bytes else encoded(value))


def synthetic_capture(root):
    config = configuration("3.0")
    source = b"# Synthetic unit source witness; not native implementation.\n"
    source_map = {"host/replay/repair.py": sha(source)}
    closure = replay.native.closure(source_map)
    response = {"status": "COMMITTED", "code": "GODOT_MANAGED_SCRIPT_REPLACED",
                "postconditions": {"public_ack": True}}
    report = {"schema": "HH-GT06-MANAGED-REPAIR-1", "managed_script_repaired": True,
        "runtime_repair_proven": False, "formal_acceptance": False,
        "fault_capture_sha256": "1"*64, "fault_binding": {"run_id": "gt06-unit-fault"},
        "before_config_sha256": sha(configuration("0.0")), "selected_config_sha256": sha(config),
        "response_sha256": sha(encoded(response)), "selected_project_revision": "sha256:"+"2"*64,
        "source_closure_sha256": closure}
    files = {"repair.json": report, "selected-config.gd": config,
        "selected-manifest.json": {"synthetic_unit_fixture": True},
        "native-readback.json": {"script": {"source_sha256": sha(config), "disk_sha256": sha(config),
            "defaults": {"move_speed": {"value": 3.0}}}},
        "response-wire.json": response, "request.json": {"synthetic_unit_fixture": True},
        "events.json": [], "before-script.json": {"synthetic_unit_fixture": True},
        "after.json": {"synthetic_unit_fixture": True},
        "editor-close-0.json": {"synthetic_unit_fixture": True},
        "editor-close-1.json": {"synthetic_unit_fixture": True},
        "repair-host.json": {"exit_code": 0, "target_pid": 1234}, "source-files.json": source_map,
        "repair-stdout.txt": b"Synthetic unit capture\nHH_GT06_REPAIR_COMPLETE " + encoded(report),
        "repair-stderr.txt": b""}
    for name, value in files.items():
        write(root/name, value)
    write(root/"source/0.py", source)
    capture = {"schema": "HH-GT06-REPAIR-CAPTURE-1", "completed": True, "source_unchanged": True,
        "source_closure_sha256": closure, "formal_acceptance": False,
        "host": {"target_pid": 1234, "exit_code": 0, "wrapper_exit_code": 0,
                 "timed_out": False, "tree_verified": True},
        "artifacts": {name: sha((root/name).read_bytes()) for name in files if (root/name).stat().st_size}}
    write(root/"capture.json", capture)
    return sha((root/"capture.json").read_bytes())


class RepairAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hh-gt06-repair-unit-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.anchor = synthetic_capture(self.root)

    def read(self, name):
        return json.loads((self.root/name).read_bytes())

    def reseal(self, name, value):
        """Rebind the altered artifact to a new capture anchor, without excuses."""
        write(self.root/name, value)
        capture = self.read("capture.json")
        raw = (self.root/name).read_bytes()
        if raw:
            capture["artifacts"][name] = sha(raw)
        else:
            capture["artifacts"].pop(name, None)
        self.set_capture(capture)

    def set_capture(self, capture):
        write(self.root/"capture.json", capture)
        self.anchor = sha((self.root/"capture.json").read_bytes())

    def reseal_report(self, report):
        self.reseal("repair.json", report)
        self.reseal("repair-stdout.txt", b"HH_GT06_REPAIR_COMPLETE " + encoded(report))

    def reject(self, code):
        with self.assertRaises(replay.native.ReplayError) as error:
            replay.verified_repair(self.root, self.anchor)
        self.assertEqual(str(error.exception), code)

    def test_bound_completed_receipt_returns_selected_bytes_without_runtime_claim(self):
        config, report = replay.verified_repair(self.root, self.anchor)
        self.assertEqual(config, configuration("3.0"))
        self.assertTrue(report["managed_script_repaired"])
        self.assertFalse(report["runtime_repair_proven"] or report["formal_acceptance"])

    def test_wrong_external_anchor_is_rejected(self):
        self.anchor = "0"*64
        self.reject("REPLAY_REPAIR_CAPTURE_HASH")

    def test_unsealed_selected_byte_tampering_is_rejected(self):
        write(self.root/"selected-config.gd", configuration("0.0"))
        self.reject("REPLAY_REPAIR_ARTIFACT_HASH")

    def test_rehashed_selected_config_still_requires_fixed_repaired_value(self):
        self.reseal("selected-config.gd", configuration("0.0"))
        self.reject("REPLAY_REPAIR_SELECTED_BYTES")

    def test_source_copy_tampering_cannot_hide_behind_unchanged_flag(self):
        write(self.root/"source/0.py", b"# altered source copy\n")
        self.reject("REPLAY_REPAIR_SOURCE_BYTES")

    def test_rehashed_host_record_requires_same_real_child_pid(self):
        self.reseal("repair-host.json", {"exit_code": 0, "target_pid": 4321})
        self.reject("REPLAY_REPAIR_HOST")

    def test_rehashed_host_failure_is_not_repaired_by_success_banner(self):
        self.reseal("repair-host.json", {"exit_code": 26, "target_pid": 1234})
        self.reject("REPLAY_REPAIR_HOST")

    def test_repaired_flag_does_not_replace_committed_public_ack(self):
        response = self.read("response-wire.json")
        response["status"] = "FAILED"
        self.reseal("response-wire.json", response)
        report = self.read("repair.json")
        report["response_sha256"] = sha((self.root/"response-wire.json").read_bytes())
        self.reseal_report(report)
        self.reject("REPLAY_REPAIR_COMMITTED")

    def test_native_default_must_match_selected_script_bytes(self):
        readback = self.read("native-readback.json")
        readback["script"]["defaults"]["move_speed"]["value"] = 0.0
        self.reseal("native-readback.json", readback)
        self.reject("REPLAY_REPAIR_NATIVE_CONFIG")

    def test_duplicate_completion_marker_rejected_after_log_and_capture_rehash(self):
        self.reseal("repair-stdout.txt", (self.root/"repair-stdout.txt").read_bytes()*2)
        self.reject("REPLAY_REPAIR_MARKER")

    def test_missing_completion_marker_rejected_after_log_and_capture_rehash(self):
        self.reseal("repair-stdout.txt", b"ordinary successful-looking log\n")
        self.reject("REPLAY_REPAIR_MARKER")

    def test_completion_marker_must_equal_entire_bound_report(self):
        marker = self.read("repair.json")
        marker["selected_config_sha256"] = "0"*64
        self.reseal("repair-stdout.txt", b"HH_GT06_REPAIR_COMPLETE " + encoded(marker))
        self.reject("REPLAY_REPAIR_MARKER")

    def test_nonempty_stderr_rejected_even_with_new_artifact_anchor(self):
        self.reseal("repair-stderr.txt", b"unexpected diagnostic\n")
        self.reject("REPLAY_REPAIR_LOG_ERROR")

    def test_log_errors_rejected_even_with_valid_completion_and_new_anchor(self):
        original = (self.root/"repair-stdout.txt").read_bytes()
        for diagnostic in (b"WARNING: bad state\n", b"ERROR: failed operation\n", b"Error: unhandled native failure\n"):
            with self.subTest(diagnostic=diagnostic):
                self.reseal("repair-stdout.txt", original + diagnostic)
                self.reject("REPLAY_REPAIR_LOG_ERROR")

    def test_stdout_cannot_be_omitted_from_artifact_map(self):
        capture = self.read("capture.json")
        del capture["artifacts"]["repair-stdout.txt"]
        self.set_capture(capture)
        self.reject("REPLAY_REPAIR_ARTIFACT_SET")

    def test_artifact_path_cannot_escape_capture_root(self):
        capture = self.read("capture.json")
        capture["artifacts"]["../outside.json"] = "0"*64
        self.set_capture(capture)
        self.reject("REPLAY_REPAIR_ARTIFACT_PATH")


class RepairCompositionTests(unittest.TestCase):
    """Native boundary is mocked. Check composition decisions and proof writes."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="hh-gt06-compose-unit-")
        self.addCleanup(temporary.cleanup)
        self.studio = Path(temporary.name)
        self.trace = default_trace(23)
        self.repair_id, self.fault_id, self.run_id = "gt06-unit-repair", "gt06-unit-fault", "gt06-unit-replay"
        self.output = self.studio/".local/reviews"/self.run_id
        write(self.studio/".local/reviews"/self.fault_id/"project/input/trace.json", self.trace.raw)
        for name in ("repair_replay.py", "repair.py", "observation.py", "trace.py"):
            write(self.studio/"host/replay"/name, ("# synthetic " + name + "\n").encode())
        self.addCleanup(patch.stopall)
        patch.object(replay, "STUDIO", self.studio).start()
        self.source_before = replay.verifier_sources()
        self.receipt = {"fault_binding": {"run_id": self.fault_id}, "fault_capture_sha256": "1"*64}
        self.fault_capture = {"binding": {"trace_sha256": self.trace.raw_sha256, "glb_sha256": "2"*64}}
        self.checks = {"all_postconditions": True, "movement_fault_observed": False}
        patch.object(replay, "verified_repair", return_value=(configuration("3.0"), self.receipt)).start()
        patch.object(replay, "verified_fault", return_value=(configuration("0.0"), self.fault_capture,
            {"all_postconditions": False, "movement_fault_observed": True})).start()
        self.validate = patch.object(replay, "validate_observation", return_value=self.checks).start()
        self.native_run = patch.object(replay.native, "run", side_effect=self.fake_native).start()
        self.stdout = patch("sys.stdout", new=io.StringIO()).start()

    def fake_native(self, run_id, **kwargs):
        self.assertEqual(run_id, self.run_id)
        self.assertEqual(kwargs["speed"], "3.0")
        self.assertEqual(kwargs["seed"], 23)
        self.assertEqual(kwargs["config_bytes"], configuration("3.0"))
        self.assertEqual(kwargs["repair_binding"]["selected_config_sha256"], sha(configuration("3.0")))
        write(self.output/"project/out/report.json", {"mocked_native_boundary": True})
        write(self.output/"process-metrics.json", {"mocked_native_boundary": True})
        write(self.output/"capture.json", {"mocked_native_boundary": True})
        return copy.deepcopy(self.fault_capture)

    def invoke(self):
        return replay.run(self.run_id, self.repair_id, "3"*64)

    def test_unchanged_verifier_sources_record_original_hashes_in_mocked_composition(self):
        proof = self.invoke()
        self.assertEqual(proof["verifier_sources"], self.source_before)
        self.assertTrue(proof["managed_repair_proven"])
        self.assertFalse(proof["formal_acceptance"])
        self.assertEqual(json.loads((self.output/"repair-replay.json").read_bytes()), proof)
        self.native_run.assert_called_once()
        self.validate.assert_called_once()

    def test_verifier_changed_during_run_cannot_receive_repair_proof(self):
        def changed(run_id, **kwargs):
            result = self.fake_native(run_id, **kwargs)
            write(self.studio/"host/replay/observation.py", b"# changed while native process was active\n")
            return result
        self.native_run.side_effect = changed
        with self.assertRaisesRegex(replay.native.ReplayError, "^REPLAY_REPAIR_VERIFIER_CHANGED$"):
            self.invoke()
        self.assertFalse((self.output/"repair-replay.json").exists())

    def test_same_seed_does_not_excuse_changed_trace_or_asset(self):
        def changed(run_id, **kwargs):
            result = self.fake_native(run_id, **kwargs)
            result["binding"]["trace_sha256"] = "0"*64
            return result
        self.native_run.side_effect = changed
        with self.assertRaisesRegex(replay.native.ReplayError, "^REPLAY_REPAIR_INPUT_CHANGED$"):
            self.invoke()
        self.validate.assert_not_called()
        self.assertFalse((self.output/"repair-replay.json").exists())

    def test_completed_replay_with_remaining_fault_cannot_receive_repair_proof(self):
        self.checks.update(all_postconditions=False, movement_fault_observed=True)
        with self.assertRaisesRegex(replay.native.ReplayError, "^REPLAY_REPAIR_POSTCONDITION$"):
            self.invoke()
        self.assertFalse((self.output/"repair-replay.json").exists())


if __name__ == "__main__":
    unittest.main()
