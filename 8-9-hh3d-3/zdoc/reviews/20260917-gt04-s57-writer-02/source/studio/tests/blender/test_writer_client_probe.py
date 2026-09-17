"""Pure writer probe parsing/evidence checks; no HTTP, native engine, or Journal."""
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_writer_client_probe as probe


def rows(required):
    return [{"label": label, "passed": True} for label in sorted(required)]


def job():
    return {"zero_observed": True, "active_count": 0, "closed": True, "handle_retained": False}


def client_cleanup():
    return {"pid": 303, "exit_code": 0, "timed_out": False, "job": job()}


def native_cleanup():
    return {"closed": True, "actual_process_exit": {"pid": 202, "exit_code": 0},
            "wrapper_exit_code": 0, "logs_overflow": False, "job": job()}


def host():
    return {"exit_code": 0, "wrapper_exit_code": 0, "timed_out": False, "tree_verified": True,
            "target_pid": 101, "wrapper_pid": 100, "host": "native-host.json"}


def child():
    return {"passed": True, "pid": 303, "checks": rows(probe.CLIENT_CHECKS), "public_ack": False,
            "scene_state_durable": False, "formal_acceptance": False}


def client_wire(value):
    return (probe.CLIENT_COMPLETE + json.dumps(value) + "\n").encode()


class PureBoundaries(unittest.TestCase):
    def test_help_and_missing_arguments_cannot_start_bootstrap(self):
        with patch.object(probe, "load", side_effect=AssertionError("no native bootstrap")):
            with redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as raised:
                probe.main(["--help"])
            self.assertEqual(raised.exception.code, 0)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                probe.main(["--output", "unused"])

    def test_complete_checks_require_exact_labels_true_flags_and_no_duplicates(self):
        required = {"one", "two"}
        self.assertTrue(probe.checks_complete(rows(required), required))
        invalid = [rows({"one"}), rows(required) + rows({"one"}),
                   [{"label": "one", "passed": True}, {"label": "other", "passed": True}],
                   [{"label": "one", "passed": True}, {"label": "two", "passed": 1}],
                   [{"label": "one", "passed": True, "extra": True}, {"label": "two", "passed": True}]]
        for value in invalid:
            with self.subTest(value=value):
                self.assertFalse(probe.checks_complete(value, required))

    def test_client_marker_caps_and_claim_scope_fail_closed(self):
        self.assertEqual(probe.client_report(client_wire(child())), child())
        for raw in (b"", b"x" * (probe.MAX_CLIENT_BYTES + 1), client_wire(child()) * 2,
                    b"not a completion\n", (probe.CLIENT_COMPLETE + "[]").encode()):
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                probe.client_report(raw)
        for changes in ({"pid": True}, {"public_ack": True}, {"scene_state_durable": True},
                        {"formal_acceptance": True}, {"checks": rows(probe.CLIENT_CHECKS)[:-1]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                probe.client_report(client_wire({**child(), **changes}))

    def test_cli_requires_actual_exit_zero_and_empty_closed_owned_job(self):
        self.assertTrue(probe.cli_cleanup_passed(client_cleanup()))
        for key, value in (("pid", True), ("exit_code", False), ("exit_code", None), ("timed_out", True)):
            with self.subTest(key=key):
                self.assertFalse(probe.cli_cleanup_passed({**client_cleanup(), key: value}))
        for key, value in (("active_count", 1), ("active_count", False), ("handle_retained", True), ("closed", False)):
            value = {**client_cleanup(), "job": {**job(), key: value}}
            self.assertFalse(probe.cli_cleanup_passed(value))

    def test_malformed_client_configuration_never_exposes_ephemeral_credentials(self):
        private = "ephemeral-bearer-not-for-evidence"
        configuration = json.dumps({"writer": private, "reader": private}).encode()
        stdin = SimpleNamespace(buffer=io.BytesIO(configuration))
        captured = io.StringIO()
        with patch.object(sys, "stdin", stdin), patch.object(probe.http.client, "HTTPConnection",
                side_effect=AssertionError("unexpected HTTP")), redirect_stdout(captured):
            self.assertEqual(probe.client(), 1)
        text = captured.getvalue()
        self.assertNotIn(private, text)
        failure = json.loads(text.removeprefix(probe.CLIENT_COMPLETE))
        self.assertFalse(failure["passed"])
        self.assertEqual(failure["failure"], {"type": "KeyError", "code": None})

    def test_unit_program_uses_writer_markers_and_preserves_strict_inventory_gate(self):
        source = probe.unit_program(["test_writer_client_probe.py"])
        compile(source, "<writer-units>", "exec")
        self.assertIn(probe.UNIT_INVENTORY, source)
        self.assertNotIn(probe.BASE_INVENTORY, source)
        inventory = probe.UNIT_INVENTORY + '["one.test"]'
        counts = {"run": 1, "failures": 0, "errors": 0, "skips": 0}
        completed = probe.UNIT_COMPLETE + json.dumps(counts)
        self.assertEqual(probe.unit_completion(inventory + "\n" + completed), (True, [counts]))
        self.assertFalse(probe.unit_completion(completed)[0])
        self.assertFalse(probe.unit_completion(inventory + "\n" + completed.replace('"skips": 0', '"skips": false'))[0])

    def test_focused_suite_refuses_missing_writer_owner_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(probe.unit_patterns(root, "all"), ["test_*.py"])
            with self.assertRaisesRegex(ValueError, "required writer"):
                probe.unit_patterns(root, "focused")


class NativeArtifacts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.directory = self.output / ("blender-" + "a" * 32)
        self.directory.mkdir()
        self.manifest = {"run_id": "writer-test", "source_closure_sha256": "b" * 64}
        self.report = {
            **self.manifest, "passed": True, "probe_pid": 101, "native_pid": 202,
            "gui_directory": self.directory.name, "checks": rows(probe.NATIVE_CHECKS),
            "cleanup": native_cleanup(), "client_cleanup": client_cleanup(),
            "client_checks": len(probe.CLIENT_CHECKS), "public_ack": False,
            "scene_state_durable": False, "formal_acceptance": False,
        }
        self.child = child()
        self.persist()

    def persist(self):
        for name, value in (("source-closure.json", self.manifest), ("writer-native.json", self.report),
                            ("native-host.json", {"target_pid": 101, "exit_code": 0}),
                            ("client-exit.json", self.report["client_cleanup"]), ("client.json", self.child)):
            (self.output / name).write_text(json.dumps(value), encoding="utf-8")
        (self.output / "client-stdout.txt").write_bytes(client_wire(self.child))
        (self.output / "client-stderr.txt").write_bytes(b"")
        (self.output / "native-stdout.txt").write_text(probe.NATIVE_COMPLETE + json.dumps({
            "passed": True, "checks": len(self.report["checks"]), "client_checks": len(self.child["checks"])}), encoding="utf-8")
        (self.directory / "process-exit.json").write_text(json.dumps(
            self.report["cleanup"]["actual_process_exit"]), encoding="utf-8")
        (self.directory / "close.json").write_text(json.dumps(self.report["cleanup"]), encoding="utf-8")

    def test_complete_cli_gui_and_outer_actual_process_proof(self):
        self.assertTrue(probe.native_completion(self.output, host()))
        self.assertFalse(probe.native_completion(self.output, {**host(), "target_pid": 999}))
        self.assertFalse(probe.native_completion(self.output, {**host(), "tree_verified": False}))

    def test_client_exit_or_tree_mismatch_cannot_be_replaced_by_pass_banner(self):
        for key, value in (("exit_code", 1), ("timed_out", True), ("pid", 101)):
            self.report["client_cleanup"] = {**client_cleanup(), key: value}
            self.persist()
            with self.subTest(key=key):
                self.assertFalse(probe.native_completion(self.output, host()))
        self.report["client_cleanup"] = {**client_cleanup(), "job": {**job(), "handle_retained": True}}
        self.persist()
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_raw_gui_exit_job_and_report_must_agree(self):
        (self.directory / "process-exit.json").write_text('{"pid":202,"exit_code":false}', encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        close = copy.deepcopy(native_cleanup())
        close["job"]["active_count"] = 1
        (self.directory / "close.json").write_text(json.dumps(close), encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_native_and_cli_checks_cannot_be_omitted_or_duplicated(self):
        self.report["checks"].pop()
        self.persist()
        self.assertFalse(probe.native_completion(self.output, host()))
        self.report["checks"] = rows(probe.NATIVE_CHECKS)
        self.child["checks"] = self.child["checks"][:-1] + self.child["checks"][:1]
        self.persist()
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_client_stdout_must_match_saved_client_and_be_error_free(self):
        changed = {**self.child, "pid": 404}
        (self.output / "client.json").write_text(json.dumps(changed), encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))
        self.persist()
        (self.output / "client-stderr.txt").write_bytes(b"unexpected diagnostic")
        self.assertFalse(probe.native_completion(self.output, host()))

    def test_wrong_source_claims_path_or_duplicate_native_completion_rejected(self):
        baseline = copy.deepcopy(self.report)
        for changes in ({"source_closure_sha256": "c" * 64}, {"run_id": "other-run"},
                        {"public_ack": True}, {"scene_state_durable": True},
                        {"formal_acceptance": True}, {"gui_directory": "../outside"},
                        {"client_checks": True}, {"client_checks": 1}):
            self.report = {**baseline, **changes}
            self.persist()
            with self.subTest(changes=changes):
                self.assertFalse(probe.native_completion(self.output, host()))
        self.report = baseline
        self.persist()
        path = self.output / "native-stdout.txt"
        text = path.read_text(encoding="utf-8")
        path.write_text(text + "\n" + text, encoding="utf-8")
        self.assertFalse(probe.native_completion(self.output, host()))


if __name__ == "__main__":
    unittest.main()
