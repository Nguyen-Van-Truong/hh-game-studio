"""Pure adapter lifecycle tests; native result is an explicitly shaped fixture."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.core.limits import SafetyViolation
spec = importlib.util.spec_from_file_location(
    "hh_gameplay_source_owner_test", STUDIO / "godot-addon/gameplay_source_owner.py")
owner_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner_mod
spec.loader.exec_module(owner_mod)


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
        request = {
            "command_id": command,
            "expected_project_revision": expected or self.owner.inspect()["project_revision"],
            "source_files": files, "entrypoint": owner_mod.ENTRYPOINT,
        }
        request["digest"] = owner_mod.request_digest(project_id=self.owner.project_id, **request)
        return request

    def durable_state(self):
        return (self.owner.inspect(), self.owner._selector.read_bytes(),
                self.owner._journal.read_bytes())

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
        files["scripts/fixture_actor.gd"] += b"\nfunc _ready() -> void:\n\tpass\n"
        request = self.request(files)
        first = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
        self.assertNotEqual(request["expected_project_revision"], first["project_revision"])
        after = self.durable_state()
        self.assertEqual(first, self.owner.publish(request, grant=self.grant,
                                                   lease=self.lease, deadline_ms=self.lease.expires_ms))
        changed = dict(files)
        changed["scripts/fixture_actor.gd"] += b"\n# changed source request\n"
        conflict = self.request(changed, expected=request["expected_project_revision"])
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "COMMAND_CONFLICT"):
            self.owner.publish(conflict, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.durable_state(), after)

    def test_cached_ack_rejects_changed_request_with_original_digest(self):
        files = dict(self.source)
        files["scripts/fixture_actor.gd"] += b"\n# published bytes\n"
        request = self.request(files)
        self.owner.publish(request, grant=self.grant, lease=self.lease,
                           deadline_ms=self.lease.expires_ms)
        after = self.durable_state()
        changed = dict(files)
        changed["scripts/fixture_actor.gd"] += b"\n# different request bytes\n"
        cases = (
            dict(request, source_files=changed),
            dict(request, entrypoint="scenes/fixture.tscn"),
            dict(request, expected_project_revision="sha256:" + "c" * 64),
        )
        for altered in cases:
            with self.subTest(field=next(key for key in request if request[key] != altered[key])):
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "DIGEST_MISMATCH"):
                    self.owner.publish(altered, grant=self.grant, lease=self.lease,
                                       deadline_ms=self.lease.expires_ms)
                self.assertEqual(len(self.runs), 1)
                self.assertEqual(self.durable_state(), after)

    def test_reordered_source_mapping_has_same_digest_and_cached_ack(self):
        request = self.request(dict(self.source))
        first = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
        after = self.durable_state()
        reordered = self.request(dict(reversed(list(self.source.items()))),
                                 expected=request["expected_project_revision"])
        self.assertEqual(reordered["digest"], request["digest"])
        self.assertEqual(self.owner.publish(reordered, grant=self.grant, lease=self.lease,
                                           deadline_ms=self.lease.expires_ms), first)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual(self.durable_state(), after)

    def test_cached_ack_requires_live_grant_lease_deadline_and_owner(self):
        request = self.request(dict(self.source))
        self.owner.publish(request, grant=self.grant, lease=self.lease,
                           deadline_ms=self.lease.expires_ms)
        after = (self.owner._selector.read_bytes(), self.owner._journal.read_bytes())
        for changes, code in (({'grant': object()}, 'GRANT'),
                              ({'lease': object()}, 'STALE_LEASE'),
                              ({'deadline_ms': 0}, 'DEADLINE_EXPIRED')):
            args = dict(grant=self.grant, lease=self.lease, deadline_ms=self.lease.expires_ms)
            args.update(changes)
            with self.subTest(code=code), self.assertRaisesRegex(SafetyViolation, code):
                self.owner.publish(request, **args)
        self.owner._session.revoke(self.credential)
        with self.assertRaises(SafetyViolation):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.owner.close()
        with self.assertRaisesRegex(SafetyViolation, 'GAMEPLAY_OWNER_CLOSED'):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 1)
        self.assertEqual((self.owner._selector.read_bytes(), self.owner._journal.read_bytes()), after)

    def test_digest_mismatch_rejects_new_request_before_native_or_durable_changes(self):
        request = self.request(dict(self.source))
        request["digest"] = "sha256:" + "b" * 64
        before = self.durable_state()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "DIGEST_MISMATCH"):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(self.runs, [])
        self.assertEqual(self.durable_state(), before)

    def test_validated_copy_binds_digest_and_published_bytes_after_caller_mutation(self):
        files = dict(self.source)
        files["scripts/fixture_actor.gd"] += b"\n# immutable candidate\n"
        expected = dict(files)
        request = self.request(files)
        validate = self.owner._profile.validate_source_bundle

        def mutate_after_validation(candidate, *, entrypoint):
            checked = validate(candidate, entrypoint=entrypoint)
            files["scripts/fixture_actor.gd"] += b"\n# caller mutation\n"
            return checked

        with patch.object(self.owner._profile, "validate_source_bundle", mutate_after_validation):
            receipt = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                         deadline_ms=self.lease.expires_ms)
        self.assertNotEqual(files, expected)
        self.assertEqual(receipt["request_digest"], request["digest"])
        self.assertEqual(self.owner._files, expected)
        project = self.runs[0][0]
        self.assertEqual({name: (project / name).read_bytes() for name in expected}, expected)

    def test_reopen_reads_selected_revision_without_reusing_old_lease(self):
        files = dict(self.source)
        request = self.request(files)
        receipt = self.owner.publish(request, grant=self.grant,
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
        credential = reopened.issue()
        grant = reopened.authorize("Bearer " + credential.bearer, "scene.save")
        lease = reopened.lease(grant)
        calls_before = len(self.runs)
        self.assertEqual(reopened.publish(request, grant=grant, lease=lease,
                                          deadline_ms=lease.expires_ms), receipt)
        self.assertEqual(len(self.runs), calls_before)
        with self.assertRaisesRegex(SafetyViolation, "AUTH_REQUIRED"):
            reopened.authorize("Bearer " + self.credential.bearer, "scene.save")

    def test_stale_project_is_rejected_before_native_runner(self):
        files = dict(self.source)
        request = self.request(files, expected="sha256:" + "c" * 64)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "STALE_PROJECT"):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(self.runs, [])

    def test_reopen_rejects_tampered_committed_receipt(self):
        request = self.request(dict(self.source))
        self.owner.publish(request, grant=self.grant, lease=self.lease,
                           deadline_ms=self.lease.expires_ms)
        root = self.owner._root
        self.owner.close()
        rows = [json.loads(line) for line in (root / 'journal.jsonl').read_bytes().splitlines()]
        rows[-1].pop('readback_sha256')
        (root / 'journal.jsonl').write_bytes(
            b''.join(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                     for row in rows))
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'JOURNAL_COMMITTED_SHAPE'):
            owner_mod.GameplaySourcePublicationOwner.reopen(
                root, project_id='project.gameplay',
                source_closure_sha256=owner_mod.runtime_source_closure()[1],
                runner=lambda *args, **kwargs: native_result('unused-run'))

    def test_concurrent_publication_is_rejected_without_poisoning_active_writer(self):
        entered, release = threading.Event(), threading.Event()
        completed, failures = [], []
        calls = []
        before = self.durable_state()
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# first writer\n'
        first = self.request(files)
        second = self.request(dict(self.source), command='command.concurrent.2')

        def runner(*args, **kwargs):
            calls.append(1)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('TEST_RELEASE_TIMEOUT')
            return native_result()

        def publish_first():
            try:
                completed.append(self.owner.publish(first, grant=self.grant, lease=self.lease,
                                                     deadline_ms=self.lease.expires_ms))
            except BaseException as error:
                failures.append(error)

        self.owner._runner = runner
        worker = threading.Thread(target=publish_first)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            with self.assertRaisesRegex(SafetyViolation, 'GAMEPLAY_OWNER_BUSY'):
                self.owner.publish(second, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
            self.assertEqual(self.durable_state(), before)
            self.assertFalse(self.owner._held)
            self.assertEqual(len(calls), 1)
        finally:
            release.set()
            worker.join(5)
        self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(len(completed), 1)
        self.assertEqual(self.owner.inspect()['generation'], before[0]['generation'] + 1)
        self.assertEqual(self.owner.publish(first, grant=self.grant, lease=self.lease,
                                           deadline_ms=self.lease.expires_ms), completed[0])
        self.assertEqual(len(calls), 1)

    def test_close_remains_available_while_native_writer_is_blocked(self):
        entered, release, closed = threading.Event(), threading.Event(), threading.Event()
        failures = []
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# never selected\n'
        request = self.request(files)
        before = (self.owner._selector.read_bytes(), self.owner._journal.read_bytes())

        def runner(*args, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('TEST_RELEASE_TIMEOUT')
            return native_result()

        def publish():
            try:
                self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
            except BaseException as error:
                failures.append(error)

        def close():
            self.owner.close()
            closed.set()

        self.owner._runner = runner
        worker = threading.Thread(target=publish)
        closer = threading.Thread(target=close)
        worker.start()
        try:
            self.assertTrue(entered.wait(5))
            closer.start()
            self.assertTrue(closed.wait(2), 'close must not wait on publication lock')
        finally:
            release.set()
            worker.join(5)
            if closer.ident is not None:
                closer.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], SafetyViolation)
        self.assertEqual((self.owner._selector.read_bytes(), self.owner._journal.read_bytes()), before)
        self.assertFalse(self.owner._work.locked())

    def test_close_waits_for_selector_adoption_and_reopen_sees_committed_revision(self):
        selected, release, close_started, closed = (
            threading.Event(), threading.Event(), threading.Event(), threading.Event())
        failures = []
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# selector barrier\n'
        request = self.request(files)
        original_select = self.owner._atomic_select

        def select(revision, generation):
            original_select(revision, generation)
            selected.set()
            if not release.wait(5):
                raise RuntimeError('TEST_RELEASE_TIMEOUT')

        def publish():
            try:
                self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
            except BaseException as error:
                failures.append(error)

        def close():
            close_started.set()
            self.owner.close()
            closed.set()

        self.owner._atomic_select = select
        worker = threading.Thread(target=publish)
        closer = threading.Thread(target=close)
        worker.start()
        try:
            self.assertTrue(selected.wait(5))
            closer.start()
            self.assertTrue(close_started.wait(2))
            self.assertFalse(closed.wait(0.1), 'close must wait for adopt/commit boundary')
        finally:
            release.set()
            worker.join(5)
            if closer.ident is not None:
                closer.join(5)
        self.assertFalse(worker.is_alive())
        self.assertFalse(closer.is_alive())
        self.assertEqual(failures, [])
        self.assertTrue(closed.is_set())
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            self.owner._root, project_id='project.gameplay',
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kwargs: native_result('unused-run'))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.inspect()['project_revision'],
                         self.owner._project_revision)
        self.assertEqual(reopened.inspect()['generation'], self.owner._generation)

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
