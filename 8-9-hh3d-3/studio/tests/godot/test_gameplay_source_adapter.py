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
        credential = self.owner.issue()
        self.grant = self.owner.authorize("Bearer " + credential.bearer, "scene.save")
        self.lease = self.owner.lease(self.grant)
        self.initial_revision = self.owner.inspect()["project_revision"]
        self.adapter = adapter_mod.GameplaySourceAdapter(self.owner)

    def evidence(self, **changes):
        value = dict(
            client_version=adapter_mod.SUPPORTED_CLIENT_VERSION,
            protocol_version=adapter_mod.PROTOCOL_VERSION,
            schema_version=adapter_mod.SCHEMA_VERSION,
            profile=adapter_mod.PROFILE,
            source_closure_sha256=self.owner.source_closure_sha256,
            source_job_ids=("source.job.1", "source.job.2"),
            readback_ack=True, reconnect_lookup_only=True,
            context_reset_lookup_only=True, owner_edit_preserved=True,
            no_duplicate_mutation=True, public_ack=False, authority=0,
        )
        value.update(changes)
        return adapter_mod.CapabilityEvidence(**value)

    def measured(self):
        return self.adapter.measure_capability(self.evidence())

    def publish(self, *, command="source.job.1", files=None, expected=None):
        self.measured()
        files = self.source if files is None else files
        expected = self.owner.inspect()["project_revision"] if expected is None else expected
        return self.adapter.publish_source(
            command_id=command, source_files=files,
            expected_project_revision=expected, grant=self.grant,
            lease=self.lease, deadline_ms=self.lease.expires_ms)

    def test_discovery_stays_empty_until_measured(self):
        self.assertEqual(self.adapter.discovery().capabilities, ())
        self.assertFalse(self.adapter.measured)
        self.measured()
        discovered = self.adapter.discovery()
        self.assertTrue(discovered.supports(adapter_mod.PUBLISH_OPERATION))
        self.assertTrue(discovered.supports(adapter_mod.READ_OPERATION))
        self.assertEqual(discovered.schema_digest, adapter_mod.SCHEMA_DIGEST)

    def test_unsupported_client_version_rejected_before_owner_use(self):
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "UNSUPPORTED_CLIENT_VERSION"):
            adapter_mod.GameplaySourceAdapter(self.owner, client_version="android-godot-4.7.2")
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "UNSUPPORTED_CLIENT_VERSION"):
            adapter_mod.GameplaySourceAdapter.check_client_version("future")
        self.assertEqual(self.runs, [])

    def test_measurement_requires_two_distinct_source_jobs_and_matching_closure(self):
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "SOURCE_JOBS_INCOMPLETE"):
            self.adapter.measure_capability(self.evidence(source_job_ids=("source.job.1",)))
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "SOURCE_JOB_DUPLICATE"):
            self.adapter.measure_capability(self.evidence(
                source_job_ids=("source.job.1", "source.job.1")))
        with self.assertRaisesRegex(adapter_mod.GameplaySourceAdapterError,
                                    "SOURCE_CLOSURE_MISMATCH"):
            self.adapter.measure_capability(self.evidence(source_closure_sha256="0" * 64))
        self.assertFalse(self.adapter.measured)

    def test_publish_ack_is_bound_to_owner_readback(self):
        receipt = self.publish()
        self.assertEqual(receipt["status"], "READBACK_ACK")
        self.assertFalse(receipt["public_ack"])
        self.assertEqual(self.adapter.lookup("source.job.1"), receipt)
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
        self.assertEqual(replacement.lookup("source.job.1"), receipt)
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
                                    "OWNER_EDIT_CONFLICT"):
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


if __name__ == "__main__":
    unittest.main()
