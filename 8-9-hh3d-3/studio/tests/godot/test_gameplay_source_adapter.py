"""Pure PC adapter conformance over the existing gameplay-source owner."""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


owner_mod = _load("hh_gameplay_source_owner_adapter_test",
                  STUDIO / "godot-addon/gameplay_source_owner.py")
adapter_mod = _load("hh_gameplay_source_adapter_test",
                    STUDIO / "godot-addon/gameplay_source_adapter.py")


def native_result(project: Path, output: Path, run_id: str) -> dict:
    job = {"configured": True, "assigned": True, "closed": True,
           "zero_observed": True, "active_count": 0, "tainted": False,
           "handle_retained": False, "failed_operations": []}
    host = {"exit_code": 0, "timed_out": False, "stream_cap_exceeded": False,
            "readers_stopped": True, "job_active_count": 0, "job_owner": job}
    manifest = {path.relative_to(project).as_posix():
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(project.rglob("*")) if path.is_file()}
    result = {
        "schema": "hh-gt03-linux-diagnostic-1", "mode": "gameplay-source",
        "source_closure_sha256": owner_mod.runtime_source_closure()[1],
        "source_closure_unchanged": True, "run_id": run_id, "public_ack": False,
        "gameplay_source_envelope_checked": True,
        "gameplay_profile": owner_mod.PROFILE, "gameplay_profile_unchanged": True,
        "diagnostic_process_clean": True, "errors": [], "owned_removed": True,
        "owner_record_retained": False, "input_unchanged": True,
        "snapshot_unchanged": True, "binary_unchanged": True, "log_clean": True,
        "docker_wait_exit": 0, "commandhost": host,
        "state": {"Running": False, "Pid": 0, "ExitCode": 0, "OOMKilled": False},
        "input_hashes_before": manifest, "input_hashes_after": dict(manifest),
        "snapshot_hashes_after": dict(manifest),
    }
    output.mkdir()
    (output / "engine-stdout.txt").write_bytes(b"")
    (output / "engine-stderr.txt").write_bytes(b"")
    (output / "result.json").write_bytes(owner_mod.canonical_bytes(result))
    return result


class GameplaySourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-gameplay-adapter-")
        self.addCleanup(self.temp.cleanup)
        parent = Path(self.temp.name)
        source = {
            "scripts/fixture_actor.gd": b"extends Node3D\n@export var speed: float = 2.0\n",
            "scenes/fixture.tscn": b"[gd_scene format=3]\n",
        }
        self.source = source
        self.runs: list[str] = []

        def runner(project, **kwargs):
            run_id = f"adapter-run-{len(self.runs) + 1}"
            self.runs.append(run_id)
            return native_result(project, kwargs["output"], run_id)

        self.owner = owner_mod.GameplaySourcePublicationOwner.create(
            parent, project_id="project.adapter", source_files=source,
            entrypoint=owner_mod.ENTRYPOINT,
            source_closure_sha256=owner_mod.runtime_source_closure()[1], runner=runner)
        self.addCleanup(self.owner.close)
        credential = self.credential = self.owner.issue()
        self.grant = self.owner.authorize("Bearer " + credential.bearer, "scene.save")
        self.lease = self.owner.lease(self.grant)
        self.initial_revision = self.owner.inspect()["project_revision"]
        self.adapter = adapter_mod.GameplaySourceAdapter(self.owner)

    def publish(self, *, command="source.job.1", files=None, expected=None):
        files = self.source if files is None else files
        expected = self.owner.inspect()["project_revision"] if expected is None else expected
        return self.adapter.publish_source(
            command_id=command, source_files=files,
            expected_project_revision=expected, grant=self.grant,
            lease=self.lease, deadline_ms=self.lease.expires_ms)

    def lookup(self, command="source.job.1", *, adapter=None):
        return (adapter or self.adapter).lookup(command, grant=self.grant,
                    lease=self.lease, deadline_ms=self.lease.expires_ms)

    def test_private_diagnostics_never_advertise_public_capabilities(self):
        self.assertEqual(self.adapter.discovery().capabilities, ())
        self.publish()
        discovered = self.adapter.discovery()
        self.assertFalse(discovered.supports(adapter_mod.PUBLISH_OPERATION))
        self.assertFalse(discovered.supports(adapter_mod.READ_OPERATION))
        self.assertEqual(discovered.schema_digest, adapter_mod.SCHEMA_DIGEST)

    def test_unsupported_client_version_rejected_before_owner_use(self):
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "UNSUPPORTED_CLIENT_VERSION"):
            adapter_mod.GameplaySourceAdapter(self.owner, client_version="android-godot-4.7.2")
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "UNSUPPORTED_CLIENT_VERSION"):
            adapter_mod.GameplaySourceAdapter.check_client_version("future")
        self.assertEqual(self.runs, [])

    def test_caller_measurement_cannot_enable_capability(self):
        with self.assertRaises(TypeError):
            adapter_mod.GameplaySourceAdapter(self.owner, measurement={"accepted": True})
        self.assertEqual(self.adapter.discovery().capabilities, ())
        self.assertEqual(self.runs, [])

    def test_publish_ack_is_bound_to_owner_readback(self):
        receipt = self.publish()
        self.assertEqual(receipt["status"], "READBACK_ACK")
        self.assertFalse(receipt["public_ack"])
        self.assertEqual(self.lookup(), receipt)
        self.assertEqual(len(self.runs), 1)

    def test_context_reset_and_reconnect_retry_do_not_duplicate_mutation(self):
        receipt = self.publish()
        self.adapter.context_reset()
        retried = self.adapter.publish_source(
            command_id="source.job.1", source_files=self.source,
            expected_project_revision=self.initial_revision,
            grant=self.grant, lease=self.lease, deadline_ms=self.lease.expires_ms)
        self.assertEqual(retried, receipt)
        replacement = self.adapter.reconnect()
        self.assertFalse(self.adapter._connected)
        self.assertTrue(replacement._connected)
        self.assertEqual(self.lookup(adapter=replacement), receipt)
        self.assertEqual(replacement.publish_source(
            command_id="source.job.1", source_files=self.source,
            expected_project_revision=receipt["project_revision"], grant=self.grant,
            lease=self.lease, deadline_ms=self.lease.expires_ms), receipt)
        self.assertEqual(len(self.runs), 1)

    def test_changed_same_id_is_conflict_without_second_source_job(self):
        receipt = self.publish()
        changed = dict(self.source)
        changed[owner_mod.ENTRYPOINT] += b"\n# changed request\n"
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "COMMAND_CONFLICT"):
            self.adapter.publish_source(
                command_id="source.job.1", source_files=changed,
                expected_project_revision=receipt["project_revision"],
                grant=self.grant, lease=self.lease, deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 1)

    def test_owner_edit_is_reported_and_preserved_before_retry(self):
        receipt = self.publish()
        selected = self.owner._safe_revision(receipt["project_revision"]) / "project" / owner_mod.ENTRYPOINT
        selected.write_bytes(selected.read_bytes() + b"\n# owner edit\n")
        replacement = self.adapter.reconnect()
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "EXECUTOR_FILE_SHAPE"):
            replacement.publish_source(
                command_id="source.job.1", source_files=self.source,
                expected_project_revision=receipt["project_revision"], grant=self.grant,
                lease=self.lease, deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.owner._generation, receipt["generation"])

    def test_two_source_jobs_publish_once_each(self):
        first = self.publish(command="source.job.1")
        second_files = dict(self.source)
        second_files[owner_mod.ENTRYPOINT] += b"\n# second source job\n"
        second = self.publish(command="source.job.2", files=second_files,
                              expected=first["project_revision"])
        self.assertNotEqual(first["project_revision"], second["project_revision"])
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(self.owner.inspect()["generation"], 3)

    def test_historical_retry_after_new_publish_preserves_current(self):
        first = self.publish()
        second_files = dict(self.source)
        second_files[owner_mod.ENTRYPOINT] += b"\n# newer revision\n"
        self.publish(command="source.job.2", files=second_files)
        before = self.owner.inspect()
        durable = ((self.owner._root / "CURRENT").read_bytes(),
                   (self.owner._root / "journal.jsonl").read_bytes())
        self.adapter = self.adapter.reconnect()
        retried = self.publish(expected=self.initial_revision)
        self.assertEqual(retried, first)
        self.assertEqual(self.lookup(), first)
        self.assertEqual(self.owner.inspect(), before)
        self.assertEqual(durable, ((self.owner._root / "CURRENT").read_bytes(),
                                  (self.owner._root / "journal.jsonl").read_bytes()))
        self.assertEqual(len(self.runs), 2)

    def test_lookup_does_not_return_cached_ack_after_evidence_tamper(self):
        self.publish()
        path = self.owner._root / "runs" / "source.job.1" / "result.json"
        path.write_bytes(b"{}")
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "GAMEPLAY_OWNER_NATIVE_SCHEMA"):
            self.lookup()
        self.assertEqual(len(self.runs), 1)

    def test_lookup_requires_current_writer_grant_and_lease(self):
        self.publish()
        self.owner._session.revoke(self.credential)
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "GODOT_GRANT_REQUIRED"):
            self.lookup()
        self.assertEqual(len(self.runs), 1)

    def test_closed_owner_lookup_is_not_an_ack_cache(self):
        self.publish()
        self.owner.close()
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "GAMEPLAY_OWNER_CLOSED"):
            self.lookup()

    def test_lookup_unknown_command_has_no_native_effect(self):
        self.assertIsNone(self.lookup("source.absent"))
        self.assertEqual(self.runs, [])

    def test_empty_client_context_still_uses_durable_identity(self):
        self.publish()
        self.adapter.context_reset()
        changed = dict(self.source)
        changed[owner_mod.ENTRYPOINT] += b"\n# conflicting bytes\n"
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "GAMEPLAY_OWNER_COMMAND_CONFLICT"):
            self.publish(files=changed, expected=self.initial_revision)
        self.assertEqual(len(self.runs), 1)


if __name__ == "__main__":
    unittest.main()
