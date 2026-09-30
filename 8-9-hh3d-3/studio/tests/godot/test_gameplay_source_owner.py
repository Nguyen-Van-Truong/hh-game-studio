"""Pure adapter lifecycle tests; native result is an explicitly shaped fixture."""
import importlib.util
import hashlib
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
        "source_closure_sha256": owner_mod.runtime_source_closure()[1],
        "source_closure_unchanged": True,
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


def bound_native_result(project, run_id="fake-run-1", output=None):
    result = native_result(run_id)
    manifest = {path.relative_to(project).as_posix():
                hashlib.sha256(path.read_bytes()).hexdigest()
                for path in sorted(project.rglob('*')) if path.is_file()}
    result.update(input_hashes_before=manifest, input_hashes_after=dict(manifest),
                  snapshot_hashes_after=dict(manifest))
    if output is not None:
        output.mkdir()
        (output / 'result.json').write_bytes(owner_mod.canonical_bytes(result))
    return result


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
            self.assertEqual(kwargs['source_closure_sha256'], self.owner.source_closure_sha256)
            return bound_native_result(project, "fake-run-%d" % len(self.runs), kwargs['output'])

        self.owner = owner_mod.GameplaySourcePublicationOwner.create(
            self.parent, project_id="project.gameplay", source_files=self.source,
            entrypoint=owner_mod.ENTRYPOINT,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=runner)
        self.credential = self.owner.issue()
        self.grant = self.owner.authorize("Bearer " + self.credential.bearer, "scene.save")
        self.lease = self.owner.lease(self.grant)
        self.addCleanup(self.owner.close)

    def fresh_owner(self, runner):
        owner = owner_mod.GameplaySourcePublicationOwner.create(
            self.parent, project_id="project.gameplay", source_files=self.source,
            entrypoint=owner_mod.ENTRYPOINT,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=runner)
        self.addCleanup(owner.close)
        credential = owner.issue()
        grant = owner.authorize("Bearer " + credential.bearer, "scene.save")
        lease = owner.lease(grant)
        return owner, grant, lease

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

    def test_reopen_requires_committed_native_result_before_repairing_selector(self):
        request = self.request(dict(self.source))
        receipt = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                     deadline_ms=self.lease.expires_ms)
        root = self.owner._root
        self.owner.close()
        initial = json.loads(self.owner._journal.read_bytes().splitlines()[0])
        selector_before = owner_mod.canonical_bytes({"schema": "hh-gameplay-selector-1",
            "revision": initial["project_revision"], "generation": initial["generation"]})
        self.owner._selector.write_bytes(selector_before)
        result_path = self.owner._runs / request["command_id"] / "result.json"
        good = result_path.read_bytes()
        mutations = (
            ("missing", None, "NATIVE_RESULT_MISSING"),
            ("other-run", {"run_id": "other-run"}, "NATIVE_RUN_BINDING"),
            ("missing-closure", False, "NATIVE_SOURCE_CLOSURE"),
            ("other-closure", {"source_closure_sha256": "0" * 64}, "NATIVE_SOURCE_CLOSURE"),
            ("changed-closure", {"source_closure_unchanged": False}, "NATIVE_SOURCE_CLOSURE"),
            ("dirty", {"log_clean": False}, "NATIVE_NOT_CLEAN"),
            ("other-input", {"input_hashes_after": {}}, "NATIVE_INPUT_BINDING"),
        )
        for name, change, code in mutations:
            with self.subTest(name=name):
                if change is None:
                    result_path.unlink()
                elif change is False:
                    value = json.loads(good)
                    value.pop("source_closure_sha256", None)
                    result_path.write_bytes(owner_mod.canonical_bytes(value))
                else:
                    result_path.write_bytes(owner_mod.canonical_bytes(
                        {**json.loads(good), **change}))
                journal_before = self.owner._journal.read_bytes()
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, code):
                    owner_mod.GameplaySourcePublicationOwner.reopen(
                        root, project_id=self.owner.project_id,
                        source_closure_sha256=owner_mod.runtime_source_closure()[1],
                        runner=lambda *args, **kw: self.fail("recovery must not dispatch"))
                self.assertEqual(self.owner._selector.read_bytes(), selector_before)
                self.assertEqual(self.owner._journal.read_bytes(), journal_before)
                result_path.write_bytes(good)
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(root,
            project_id=self.owner.project_id,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kw: self.fail("recovery must not dispatch"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.inspect()["generation"], receipt["generation"])

    def test_live_journal_edits_block_new_work_and_cached_ack(self):
        request = self.request(dict(self.source))
        self.owner.publish(request, grant=self.grant, lease=self.lease,
                           deadline_ms=self.lease.expires_ms)
        next_request = self.request(dict(self.source), command="command.second")
        good = self.owner._journal.read_bytes()
        cases = (good.rstrip(b'\n'), b' ' + good, good.splitlines()[0] + b'\n')
        selected = self.owner._selector.read_bytes()
        calls = len(self.runs)
        for corrupt in cases:
            self.owner._journal.write_bytes(corrupt)
            for candidate in (request, next_request):
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                            "JOURNAL_CHANGED"):
                    self.owner.publish(candidate, grant=self.grant, lease=self.lease,
                                       deadline_ms=self.lease.expires_ms)
                self.assertEqual(self.owner._journal.read_bytes(), corrupt)
                self.assertEqual(self.owner._selector.read_bytes(), selected)
                self.assertEqual(len(self.runs), calls)
        self.owner._journal.write_bytes(good)

    def test_manual_edit_during_native_run_preserved_before_adoption(self):
        for target in ("journal", "selector"):
            with self.subTest(target=target):
                owner, grant, lease = self.fresh_owner(lambda *args, **kw: None)
                request = self.request(dict(self.source), command="command.racing." + target)
                before_selector, before_journal = owner._selector.read_bytes(), owner._journal.read_bytes()
                changed = b"manual-edit-preserved"
                path = owner._journal if target == "journal" else owner._selector
                def runner(project, **kw):
                    result = bound_native_result(project, output=kw["output"])
                    path.write_bytes(changed)
                    return result
                owner._runner = runner
                with self.assertRaises((owner_mod.GameplaySourceOwnerError, ValueError)):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertTrue(owner._held)
                self.assertTrue(owner._session.status()["held"])
                self.assertEqual(path.read_bytes(), changed)
                if target == "journal":
                    self.assertEqual(owner._selector.read_bytes(), before_selector)
                else:
                    self.assertEqual(owner._journal.read_bytes(), before_journal)

    def test_interrupted_journal_append_keeps_owner_held_without_ack(self):
        request = self.request(dict(self.source))
        real_fsync = owner_mod.os.fsync
        calls = 0
        def cut(fd):
            nonlocal calls
            calls += 1
            if calls == 2:  # selector succeeds, journal flush fails
                raise OSError("injected journal durability cut")
            return real_fsync(fd)
        with patch.object(owner_mod.os, 'fsync', side_effect=cut):
            with self.assertRaises(OSError):
                self.owner.publish(request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
        self.assertTrue(self.owner._held)
        self.assertNotIn(request["command_id"], self.owner._jobs)
        self.owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(self.owner._root,
            project_id=self.owner.project_id,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kw: self.fail("do not repeat validated effect"))
        self.addCleanup(reopened.close)
        credential = reopened.issue()
        grant = reopened.authorize("Bearer " + credential.bearer, "scene.save")
        lease = reopened.lease(grant)
        ack = reopened.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        self.assertEqual(ack["generation"], 2)

    def test_none_runner_return_cannot_borrow_persisted_success(self):
        def runner(project, **kw):
            bound_native_result(project, output=kw["output"])
            return None
        self.owner._runner = runner
        selected = self.owner._selector.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_RESULT_BINDING"):
            self.owner.publish(self.request(dict(self.source)), grant=self.grant,
                               lease=self.lease, deadline_ms=self.lease.expires_ms)
        self.assertTrue(self.owner._held)
        self.assertEqual(self.owner._selector.read_bytes(), selected)

    def test_reopen_reconciles_selector_against_durable_journal(self):
        request = self.request(dict(self.source))
        receipt = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                     deadline_ms=self.lease.expires_ms)
        root = self.owner._root
        initial = json.loads((root / 'journal.jsonl').read_bytes().splitlines()[0])
        self.owner.close()
        selector = root / 'CURRENT'

        # Selector behind the terminal journal: journal wins and CURRENT is
        # restored to the committed revision.
        selector.write_bytes((json.dumps({"schema": "hh-gameplay-selector-1",
            "revision": initial['project_revision'], "generation": initial['generation']},
            sort_keys=True, separators=(',', ':')) + '\n').encode())
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id='project.gameplay',
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kwargs: native_result('unused-run'))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.inspect()['project_revision'], receipt['project_revision'])
        self.assertEqual(json.loads(selector.read_bytes()), {
            'schema': 'hh-gameplay-selector-1', 'revision': receipt['project_revision'],
            'generation': receipt['generation']})

        # Selector ahead of the terminal journal: remove the terminal receipt
        # and prove reopen rolls back to the last durable row.
        reopened.close()
        rows = [json.loads(line) for line in (root / 'journal.jsonl').read_bytes().splitlines()]
        (root / 'journal.jsonl').write_bytes(
            b''.join(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                     for row in rows[:-1]))
        rolled_back = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id='project.gameplay',
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kwargs: native_result('unused-run'))
        self.addCleanup(rolled_back.close)
        self.assertEqual(rolled_back.inspect()['project_revision'], initial['project_revision'])
        self.assertEqual(json.loads(selector.read_bytes()), {
            'schema': 'hh-gameplay-selector-1', 'revision': initial['project_revision'],
            'generation': initial['generation']})

    def test_reopen_removes_only_empty_stage_marker_for_exact_retry(self):
        request = self.request(dict(self.source), command='command.crashed.stage')
        marker = self.owner._runs / (request['command_id'] + '.stage')
        marker.mkdir()
        root = self.owner._root
        self.owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id='project.gameplay',
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda project, **kwargs: bound_native_result(project, output=kwargs['output']))
        self.addCleanup(reopened.close)
        self.assertFalse(marker.exists())
        credential = reopened.issue()
        grant = reopened.authorize('Bearer ' + credential.bearer, 'scene.save')
        lease = reopened.lease(grant)
        receipt = reopened.publish(request, grant=grant, lease=lease,
                                   deadline_ms=lease.expires_ms)
        self.assertEqual(receipt['status'], 'READBACK_ACK')

    def test_reopen_preserves_partial_stage_evidence_and_fails_closed(self):
        marker = self.owner._runs / 'command.partial.stage'
        marker.mkdir()
        evidence = marker / 'runner.log'
        evidence.write_bytes(b'runner started\n')
        root = self.owner._root
        self.owner.close()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'GAMEPLAY_OWNER_STAGE_DIRTY'):
            owner_mod.GameplaySourcePublicationOwner.reopen(
                root, project_id='project.gameplay',
                source_closure_sha256=owner_mod.runtime_source_closure()[1],
                runner=lambda *args, **kwargs: native_result('unused-run'))
        self.assertTrue(marker.is_dir())
        self.assertEqual(evidence.read_bytes(), b'runner started\n')

    def test_reopen_rejects_stage_marker_file_without_touching_evidence(self):
        marker = self.owner._runs / 'command.marker-file.stage'
        marker.write_bytes(b'partial marker')
        root = self.owner._root
        self.owner.close()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'GAMEPLAY_OWNER_STAGE_MARKER'):
            owner_mod.GameplaySourcePublicationOwner.reopen(
                root, project_id='project.gameplay',
                source_closure_sha256=owner_mod.runtime_source_closure()[1],
                runner=lambda *args, **kwargs: native_result('unused-run'))
        self.assertEqual(marker.read_bytes(), b'partial marker')

    def test_existing_candidate_revision_is_verified_before_native_run(self):
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# existing candidate\n'
        request = self.request(files, command='command.tampered.revision')
        revision = owner_mod.GameplaySourcePublicationOwner._revision(files)
        self.owner._materialize(revision, files)
        target = self.owner._safe_revision(revision) / 'project' / owner_mod.ENTRYPOINT
        target.write_bytes(b'extends Node3D\n# tampered\n')
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'READBACK_HASH'):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(self.runs, [])

    def test_concurrent_publication_is_rejected_without_poisoning_active_writer(self):
        entered, release = threading.Event(), threading.Event()
        completed, failures = [], []
        calls = []
        before = self.durable_state()
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# first writer\n'
        first = self.request(files)
        second = self.request(dict(self.source), command='command.concurrent.2')

        def runner(project, **kwargs):
            calls.append(1)
            entered.set()
            if not release.wait(5):
                raise RuntimeError('TEST_RELEASE_TIMEOUT')
            return bound_native_result(project, output=kwargs['output'])

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

        def runner(project, **kwargs):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('TEST_RELEASE_TIMEOUT')
            return bound_native_result(project, output=kwargs['output'])

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
                manifest = {"project.godot": hashlib.sha256(
                    self.owner._profile.PROJECT_TEMPLATE.encode()).hexdigest(),
                    **{name: hashlib.sha256(raw).hexdigest()
                       for name, raw in sorted(files.items())}}
                result.update(input_hashes_before=manifest,
                              input_hashes_after=dict(manifest),
                              snapshot_hashes_after=dict(manifest))
                result[field] = dirty
                def dirty_runner(project, *, _result=result, **kwargs):
                    kwargs['output'].mkdir()
                    kwargs['output'].joinpath('result.json').write_bytes(
                        owner_mod.canonical_bytes(_result))
                    return _result
                owner, grant, lease = self.fresh_owner(dirty_runner)
                before = owner.inspect()
                request = self.request(files, command="command.dirty." + field)
                request["expected_project_revision"] = before["project_revision"]
                request["digest"] = owner_mod.request_digest(project_id=owner.project_id,
                    command_id=request["command_id"], entrypoint=request["entrypoint"],
                    expected_project_revision=request["expected_project_revision"],
                    source_files=files)
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                            "GAMEPLAY_OWNER_NATIVE_NOT_CLEAN"):
                    owner.publish(request, grant=grant, lease=lease,
                                  deadline_ms=lease.expires_ms)
                self.assertTrue(owner._held)
                self.assertTrue(owner._session.status()["held"])
                self.assertEqual(owner._selector.read_bytes(),
                                 json.dumps({"schema": "hh-gameplay-selector-1",
                                     "revision": before["project_revision"],
                                     "generation": before["generation"]},
                                     sort_keys=True, separators=(',', ':')).encode())

    def test_native_result_must_bind_all_published_source_hashes(self):
        before_selector = self.owner._selector.read_bytes()
        before_journal = self.owner._journal.read_bytes()
        files = dict(self.source)
        request = self.request(files, command="command.native-binding")

        def dirty_runner(project, **kwargs):
            result = bound_native_result(project, output=kwargs['output'])
            result["input_hashes_after"][owner_mod.ENTRYPOINT] = "0" * 64
            kwargs['output'].joinpath('result.json').write_bytes(owner_mod.canonical_bytes(result))
            return result

        self.owner._runner = dirty_runner
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    "GAMEPLAY_OWNER_NATIVE_INPUT_BINDING"):
            self.owner.publish(request,
                               grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertTrue(self.owner._held)
        self.assertEqual(self.owner._session.status(),
                         {'stopped': True, 'held': True, 'draining': False,
                          'public_ack': False})
        self.assertEqual(self.owner._selector.read_bytes(), before_selector)
        self.assertEqual(self.owner._journal.read_bytes(), before_journal)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'GAMEPLAY_OWNER_CLOSED'):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)

    def test_native_result_requires_unchanged_runtime_source_closure_before_selection(self):
        for name, change in (("missing", None), ("other", "0" * 64), ("changed", False)):
            with self.subTest(name=name):
                def runner(project, **kwargs):
                    result = bound_native_result(project, output=kwargs['output'])
                    if change is None:
                        result.pop('source_closure_sha256')
                    elif change is False:
                        result['source_closure_unchanged'] = False
                    else:
                        result['source_closure_sha256'] = change
                    kwargs['output'].joinpath('result.json').write_bytes(owner_mod.canonical_bytes(result))
                    return result

                owner, grant, lease = self.fresh_owner(runner)
                selector_before = owner._selector.read_bytes()
                journal_before = owner._journal.read_bytes()
                request = self.request(dict(self.source), command='command.closure.' + name)
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                            'GAMEPLAY_OWNER_NATIVE_SOURCE_CLOSURE'):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertTrue(owner._held)
                self.assertTrue(owner._session.status()['held'])
                self.assertEqual(owner._selector.read_bytes(), selector_before)
                self.assertEqual(owner._journal.read_bytes(), journal_before)

    def test_native_result_readback_failure_latches_owner_and_session(self):
        before_selector = self.owner._selector.read_bytes()
        before_journal = self.owner._journal.read_bytes()
        request = self.request(dict(self.source), command='command.missing-result')

        def missing_result_runner(project, **kwargs):
            kwargs['output'].mkdir()
            return native_result('missing-result')

        self.owner._runner = missing_result_runner
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'GAMEPLAY_OWNER_NATIVE_RESULT_MISSING'):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertTrue(self.owner._held)
        self.assertEqual(self.owner._session.status(),
                         {'stopped': True, 'held': True, 'draining': False,
                          'public_ack': False})
        self.assertEqual(self.owner._selector.read_bytes(), before_selector)
        self.assertEqual(self.owner._journal.read_bytes(), before_journal)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError,
                                    'GAMEPLAY_OWNER_CLOSED'):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)


if __name__ == "__main__":
    unittest.main()
