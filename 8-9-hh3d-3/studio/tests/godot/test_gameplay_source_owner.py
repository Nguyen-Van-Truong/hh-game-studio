"""Pure adapter lifecycle tests; native result is an explicitly shaped fixture."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.limits import SafetyViolation
spec = importlib.util.spec_from_file_location(
    "hh_gameplay_source_owner_test", STUDIO / "godot-addon/gameplay_source_owner.py")
owner_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner_mod
spec.loader.exec_module(owner_mod)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def native_result(run_id="fake-run-1"):
    job = {"configured": True, "assigned": True, "closed": True,
           "zero_observed": True, "active_count": 0, "tainted": False,
           "handle_retained": False, "failed_operations": []}
    host = {"exit_code": 0, "timed_out": False, "stream_cap_exceeded": False,
            "readers_stopped": True, "job_active_count": 0, "job_owner": job}
    return {
        "schema": "hh-gt03-linux-diagnostic-1", "mode": "gameplay-source",
        "run_id": run_id, "public_ack": False,
        "gameplay_source_envelope_checked": True,
        "gameplay_profile": owner_mod.PROFILE,
        "gameplay_profile_unchanged": True, "diagnostic_process_clean": True,
        "errors": [], "owned_removed": True, "owner_record_retained": False,
        "input_unchanged": True, "snapshot_unchanged": True,
        "binary_unchanged": True, "log_clean": True, "docker_wait_exit": 0,
        "commandhost": host,
        "state": {"Running": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False},
    }


class GameplaySourceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-gameplay-owner-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.source = {
            "scripts/fixture_actor.gd": b"extends Node3D\n@export var speed: float = 2.0\n",
            "scenes/fixture.tscn": b"[gd_scene format=3]\n",
        }
        self.runs = []

        def runner(project, **kwargs):
            self.runs.append((project, kwargs))
            return native_result("fake-run-%d" % len(self.runs))

        self.owner = owner_mod.GameplaySourcePublicationOwner.create(
            self.parent, project_id="project.gameplay", source_files=self.source,
            entrypoint=owner_mod.ENTRYPOINT,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=runner)
        self.credential = self.owner.issue()
        self.grant = self.owner.authorize("Bearer " + self.credential.bearer, "scene.save")
        self.lease = self.owner.lease(self.grant)
        self.addCleanup(self.owner.close)

    def request(self, files, expected=None, command="command.gameplay.1"):
        raw_digest = digest(b"request-" + command.encode())
        return {
            "command_id": command, "digest": "sha256:" + raw_digest,
            "expected_project_revision": expected or self.owner.inspect()["project_revision"],
            "source_files": files, "entrypoint": owner_mod.ENTRYPOINT,
        }

    def test_native_validation_precedes_atomic_selection_and_readback_ack(self):
        before = self.owner.inspect()
        files = dict(self.source)
        files["scripts/fixture_actor.gd"] += b"\nfunc _ready() -> void:\n\tpass\n"
        receipt = self.owner.publish(self.request(files), grant=self.grant,
                                      lease=self.lease, deadline_ms=self.lease.expires_ms)
        self.assertEqual(receipt["status"], "READBACK_ACK")
        self.assertTrue(receipt["readback_ack"])
        self.assertFalse(receipt["public_ack"])
        self.assertEqual(receipt["generation"], before["generation"] + 1)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.runs[0][0].parent.name, receipt["project_revision"][7:])
        self.assertEqual(self.owner.inspect()["project_revision"], receipt["project_revision"])

    def test_exact_command_retry_is_idempotent_and_digest_conflict_is_rejected(self):
        files = dict(self.source)
        request = self.request(files)
        first = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
        self.assertEqual(first, self.owner.publish(request, grant=self.grant,
                                                   lease=self.lease, deadline_ms=self.lease.expires_ms))
        conflict = dict(request, digest="sha256:" + "b" * 64)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "COMMAND_CONFLICT"):
            self.owner.publish(conflict, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 1)

    def test_reopen_reads_selected_revision_without_reusing_old_lease(self):
        files = dict(self.source)
        receipt = self.owner.publish(self.request(files), grant=self.grant,
                                     lease=self.lease, deadline_ms=self.lease.expires_ms)
        root = self.owner._root
        self.owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id="project.gameplay",
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kwargs: native_result("unused-run"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.inspect()["project_revision"], receipt["project_revision"])
        self.assertEqual(reopened.inspect()["generation"], receipt["generation"])
        with self.assertRaisesRegex(SafetyViolation, "AUTH_REQUIRED"):
            reopened.authorize("Bearer " + self.credential.bearer, "scene.save")

    def test_stale_project_is_rejected_before_native_runner(self):
        files = dict(self.source)
        request = self.request(files, expected="sha256:" + "c" * 64)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "STALE_PROJECT"):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(self.runs, [])

    def test_dirty_native_observation_cannot_publish_or_ack(self):
        before = self.owner.inspect()
        files = dict(self.source)
        fields = (
            ("diagnostic_process_clean", False),
            ("log_clean", False),
            ("owner_record_retained", True),
            ("gameplay_profile_unchanged", False),
            ("errors", ["EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN"]),
        )
        for field, dirty in fields:
            with self.subTest(field=field):
                result = native_result("dirty-" + field)
                result[field] = dirty
                self.owner._runner = lambda *args, _result=result, **kwargs: _result
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                            "GAMEPLAY_OWNER_NATIVE_NOT_CLEAN"):
                    self.owner.publish(self.request(files, command="command.dirty." + field),
                                       grant=self.grant, lease=self.lease,
                                       deadline_ms=self.lease.expires_ms)
                self.assertEqual(self.owner.inspect()["generation"], before["generation"])
                self.assertEqual(self.owner.inspect()["project_revision"], before["project_revision"])


if __name__ == "__main__":
    unittest.main()
