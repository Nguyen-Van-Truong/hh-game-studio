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
spec = importlib.util.spec_from_file_location(
    "hh_gameplay_source_owner_test", STUDIO / "godot-addon/gameplay_source_owner.py")
owner_mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = owner_mod
spec.loader.exec_module(owner_mod)
SafetyViolation = owner_mod.SafetyViolation


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
        (output / 'engine-stdout.txt').write_bytes(b'')
        (output / 'engine-stderr.txt').write_bytes(b'')
        (output / 'result.json').write_bytes(owner_mod.canonical_bytes(result))
    return result


def invalid_native_host_aliases():
    host = native_result()["commandhost"]
    cases = []
    for alias in ("commandhost", "command_host"):
        for name, value in (("empty", {}), ("null", None), ("boolean", False), ("list", [])):
            cases.append((alias + "-" + name,
                          {"commandhost": host, "command_host": host, alias: value}))
    cases.append(("conflicting-exit", {"commandhost": host,
                                      "command_host": {**host, "exit_code": 1}}))
    for name, value in (("boolean", False), ("float", 0.0)):
        cases.append(("secondary-exit-" + name, {"commandhost": host,
                      "command_host": {**host, "exit_code": value}}))
        cases.append(("secondary-count-" + name, {"commandhost": host,
                      "command_host": {**host, "job_active_count": value}}))
        cases.append(("secondary-job-" + name, {"commandhost": host,
                      "command_host": {**host, "job_owner": {
                          **host["job_owner"], "active_count": value}}}))
    cases.append(("secondary-boolean-as-int", {"commandhost": host,
                  "command_host": {**host, "readers_stopped": 1}}))
    cases.append(("missing-both", {}))
    return cases


def explained_native_result(project, output):
    policy = owner_mod._load('gameplay_log_policy')
    stdout = ('\n'.join(policy.GAMEPLAY_PHASE_EVENTS) + '\n').encode()
    stderr = policy.GAMEPLAY_STARTUP_ERRORS.encode()
    result = bound_native_result(project, output=output)
    result.update(diagnostic_process_clean=False, diagnostic_execution_complete=True,
                  log_clean=False, log_policy=policy.classify(
                      stdout, stderr, [owner_mod.ENTRYPOINT]))
    (output / 'engine-stdout.txt').write_bytes(stdout)
    (output / 'engine-stderr.txt').write_bytes(stderr)
    (output / 'result.json').write_bytes(owner_mod.canonical_bytes(result))
    return result


def damage_native_evidence(output, damage):
    if damage in ('missing-result', 'missing-stdout'):
        (output / ('result.json' if damage == 'missing-result' else 'engine-stdout.txt')).unlink()
    elif damage == 'warning':
        (output / 'engine-stderr.txt').write_bytes(b'WARNING: unproven native result\n')
    else:
        result = json.loads((output / 'result.json').read_bytes())
        if damage == 'exit':
            result['commandhost']['exit_code'] = 124
        elif damage == 'run-id':
            result['run_id'] = 'different-native-run'
        else:
            raise AssertionError(damage)
        (output / 'result.json').write_bytes(owner_mod.canonical_bytes(result))


def evidence_bytes(output):
    return {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}


class GameplaySourceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="hh-gameplay-owner-")
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.proof = self.parent / 'native-proof'
        self.proof.mkdir()
        (self.proof / 'engine-stdout.txt').write_bytes(b'')
        (self.proof / 'engine-stderr.txt').write_bytes(b'')
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

    def test_cached_ack_rechecks_native_evidence_without_dependency_policy(self):
        for damage in ('missing-result', 'missing-stdout', 'warning', 'exit', 'run-id'):
            with self.subTest(damage=damage):
                calls = []
                def runner(project, **kwargs):
                    calls.append(kwargs['output'])
                    return bound_native_result(project, output=kwargs['output'])
                owner, grant, lease = self.fresh_owner(runner)
                self.assertFalse(owner._dependency_observation_required)
                request = self.request(dict(self.source), command='command.raw.retry')
                owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                before = owner._selector.read_bytes(), owner._journal.read_bytes()
                damage_native_evidence(calls[0], damage)
                raw = evidence_bytes(calls[0])
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_'):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertEqual(len(calls), 1)
                self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)
                self.assertEqual(evidence_bytes(calls[0]), raw)

    def test_pre_adopt_rechecks_native_evidence_without_dependency_policy(self):
        for damage in ('missing-result', 'missing-stdout', 'warning', 'exit', 'run-id'):
            with self.subTest(damage=damage):
                calls = []
                def runner(project, **kwargs):
                    calls.append(kwargs['output'])
                    return bound_native_result(project, output=kwargs['output'])
                owner, grant, lease = self.fresh_owner(runner)
                original = owner._adopt
                retained = []
                def adopt(*args):
                    damage_native_evidence(calls[0], damage)
                    retained.append(evidence_bytes(calls[0]))
                    return original(*args)
                owner._adopt = adopt
                files = dict(self.source)
                files[owner_mod.ENTRYPOINT] += b'\n# candidate must not be selected\n'
                request = self.request(files, command='command.raw.adopt')
                before = owner._selector.read_bytes(), owner._journal.read_bytes()
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_'):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertEqual(len(calls), 1)
                self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)
                self.assertEqual(evidence_bytes(calls[0]), retained[0])
                self.assertTrue(owner._held)
                self.assertTrue(owner._session.status()['held'])

    def test_older_receipt_retry_after_later_publication_keeps_current(self):
        first_request = self.request(dict(self.source), command='command.history.1')
        first = self.owner.publish(first_request, grant=self.grant, lease=self.lease,
                                   deadline_ms=self.lease.expires_ms)
        files = dict(self.source)
        files[owner_mod.ENTRYPOINT] += b'\n# next revision\n'
        second_request = self.request(files, command='command.history.2')
        second = self.owner.publish(second_request, grant=self.grant, lease=self.lease,
                                    deadline_ms=self.lease.expires_ms)
        current = self.durable_state()
        self.assertNotEqual(first['project_revision'], second['project_revision'])
        self.assertEqual(self.owner.publish(first_request, grant=self.grant, lease=self.lease,
                                           deadline_ms=self.lease.expires_ms), first)
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(self.durable_state(), current)
        old_output = self.runs[0][1]['output']
        damage_native_evidence(old_output, 'run-id')
        damaged = evidence_bytes(old_output)
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_RUN_BINDING'):
            self.owner.publish(first_request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(len(self.runs), 2)
        self.assertEqual(self.durable_state(), current)
        self.assertEqual(evidence_bytes(old_output), damaged)

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

    def test_native_exit_and_process_counts_require_integer_zero(self):
        paths = (("state", "Pid"), ("state", "ExitCode"), ("docker_wait_exit",),
                 ("commandhost", "exit_code"), ("commandhost", "job_active_count"),
                 ("commandhost", "job_owner", "active_count"))
        for path in paths:
            for value in (False, 0.0, None, "0", 1, -1):
                with self.subTest(path=path, value=value, kind=type(value).__name__):
                    result = native_result()
                    for field in ("input_hashes_before", "input_hashes_after", "snapshot_hashes_after"):
                        result[field] = {}
                    target = result
                    for key in path[:-1]:
                        target = target[key]
                    target[path[-1]] = value
                    with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_(EXIT|HOST|JOB)"):
                        owner_mod.GameplaySourcePublicationOwner._validate_native(
                            result, expected_input_hashes={},
                            expected_source_closure_sha256=owner_mod.runtime_source_closure()[1],
                            evidence_directory=self.proof)

    def test_boolean_exit_cannot_publish_or_restore_cached_ack(self):
        request = self.request(dict(self.source), command="command.boolean-exit")
        selected, journal = self.owner._selector.read_bytes(), self.owner._journal.read_bytes()

        def runner(project, **kwargs):
            result = bound_native_result(project, output=kwargs['output'])
            result['state']['ExitCode'] = False
            kwargs['output'].joinpath('result.json').write_bytes(owner_mod.canonical_bytes(result))
            return result

        self.owner._runner = runner
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_EXIT"):
            self.owner.publish(request, grant=self.grant, lease=self.lease,
                               deadline_ms=self.lease.expires_ms)
        self.assertEqual(self.owner._selector.read_bytes(), selected)
        self.assertEqual(self.owner._journal.read_bytes(), journal)
        self.assertTrue(self.owner._held)
        self.assertTrue(self.owner._session.status()['held'])
        self.assertTrue((self.owner._runs / request['command_id'] / 'result.json').is_file())

        owner, grant, lease = self.fresh_owner(
            lambda project, **kw: bound_native_result(project, output=kw['output']))
        owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        owner.close()
        result_path = owner._runs / request['command_id'] / 'result.json'
        result = json.loads(result_path.read_bytes())
        result['docker_wait_exit'] = False
        result_path.write_bytes(owner_mod.canonical_bytes(result))
        selected, journal = owner._selector.read_bytes(), owner._journal.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_EXIT"):
            owner_mod.GameplaySourcePublicationOwner.reopen(
                owner._root, project_id=owner.project_id,
                source_closure_sha256=owner_mod.runtime_source_closure()[1],
                runner=lambda *args, **kw: self.fail("recovery must not dispatch"))
        self.assertEqual(owner._selector.read_bytes(), selected)
        self.assertEqual(owner._journal.read_bytes(), journal)

    def test_native_host_aliases_preserve_single_alias_compatibility(self):
        for aliases in (("commandhost",), ("command_host",), ("commandhost", "command_host")):
            with self.subTest(aliases=aliases):
                result = native_result()
                host = result.pop("commandhost")
                for alias in aliases:
                    result[alias] = json.loads(json.dumps(host))
                for field in ("input_hashes_before", "input_hashes_after", "snapshot_hashes_after"):
                    result[field] = {}
                owner_mod.GameplaySourcePublicationOwner._validate_native(
                    result, expected_input_hashes={},
                    expected_source_closure_sha256=owner_mod.runtime_source_closure()[1],
                    evidence_directory=self.proof)

    def test_malformed_native_host_alias_cannot_publish_or_ack(self):
        request = self.request(dict(self.source), command="command.host-alias")
        for name, aliases in invalid_native_host_aliases():
            with self.subTest(name=name):
                def runner(project, **kwargs):
                    result = bound_native_result(project, output=kwargs['output'])
                    result.pop('commandhost')
                    result.update(aliases)
                    # Preserve 0.0 in the retained JSON; JCS normalizes it to 0.
                    kwargs['output'].joinpath('result.json').write_bytes(
                        json.dumps(result, sort_keys=True, separators=(',', ':')).encode())
                    return result

                owner, grant, lease = self.fresh_owner(runner)
                selected, journal = owner._selector.read_bytes(), owner._journal.read_bytes()
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_(HOST|JOB)"):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertEqual(owner._selector.read_bytes(), selected)
                self.assertEqual(owner._journal.read_bytes(), journal)
                self.assertTrue(owner._held)
                self.assertTrue(owner._session.status()['held'])
                self.assertTrue((owner._runs / request['command_id'] / 'result.json').is_file())

    def test_malformed_native_host_alias_cannot_restore_ack_or_repair_selector(self):
        request = self.request(dict(self.source), command="command.host-alias")
        receipt = self.owner.publish(request, grant=self.grant, lease=self.lease,
                                     deadline_ms=self.lease.expires_ms)
        self.owner.close()
        initial = json.loads(self.owner._journal.read_bytes().splitlines()[0])
        selected = owner_mod.canonical_bytes({"schema": "hh-gameplay-selector-1",
            "revision": initial["project_revision"], "generation": initial["generation"]})
        self.owner._selector.write_bytes(selected)
        journal = self.owner._journal.read_bytes()
        result_path = self.owner._runs / request['command_id'] / 'result.json'
        good = result_path.read_bytes()
        for name, aliases in invalid_native_host_aliases():
            with self.subTest(name=name):
                result = json.loads(good)
                result.pop('commandhost')
                result.update(aliases)
                result_path.write_bytes(
                    json.dumps(result, sort_keys=True, separators=(',', ':')).encode())
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, "NATIVE_(HOST|JOB)"):
                    owner_mod.GameplaySourcePublicationOwner.reopen(
                        self.owner._root, project_id=self.owner.project_id,
                        source_closure_sha256=owner_mod.runtime_source_closure()[1],
                        runner=lambda *args, **kw: self.fail("recovery must not dispatch"))
                self.assertEqual(self.owner._selector.read_bytes(), selected)
                self.assertEqual(self.owner._journal.read_bytes(), journal)
        result_path.write_bytes(good)
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            self.owner._root, project_id=self.owner.project_id,
            source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=lambda *args, **kw: self.fail("recovery must not dispatch"))
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.inspect()['generation'], receipt['generation'])

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


    def test_exact_startup_policy_is_rechecked_for_publish_and_recovered_ack(self):
        calls = []
        def runner(project, **kwargs):
            calls.append(kwargs['output'])
            return explained_native_result(project, kwargs['output'])
        owner, grant, lease = self.fresh_owner(runner)
        request = self.request(dict(self.source), expected=owner.inspect()['project_revision'])
        receipt = owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        raw_result = json.loads((calls[0] / 'result.json').read_bytes())
        self.assertIs(raw_result['log_clean'], False)
        self.assertIs(raw_result['diagnostic_process_clean'], False)
        self.assertIs(receipt['public_ack'], False)
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(owner._root,
            project_id=owner.project_id, source_closure_sha256=owner.source_closure_sha256,
            runner=lambda *a, **kw: self.fail('recovery must not dispatch'))
        self.addCleanup(reopened.close)
        fresh = reopened.issue()
        grant = reopened.authorize('Bearer ' + fresh.bearer, 'scene.save')
        lease = reopened.lease(grant)
        self.assertEqual(reopened.publish(request, grant=grant, lease=lease,
                                         deadline_ms=lease.expires_ms), receipt)
        self.assertEqual(len(calls), 1)

    def test_explained_policy_cannot_hide_changed_missing_or_unproven_raw(self):
        for case in ('missing', 'warning', 'extra_stdout', 'forged_hash',
                     'forged_policy', 'incomplete', 'false_clean', 'both_flags_clean'):
            with self.subTest(case=case):
                def runner(project, **kwargs):
                    output = kwargs['output']
                    result = explained_native_result(project, output)
                    if case == 'missing':
                        (output / 'engine-stderr.txt').unlink()
                    elif case == 'warning':
                        with (output / 'engine-stderr.txt').open('ab') as stream:
                            stream.write(b'WARNING: unexpected\n')
                    elif case == 'extra_stdout':
                        with (output / 'engine-stdout.txt').open('ab') as stream:
                            stream.write(b'SCRIPT ERROR: unexpected\n')
                    elif case == 'forged_hash':
                        result['log_policy']['stderr_sha256'] = '0' * 64
                    elif case == 'forged_policy':
                        result['log_policy']['policy'] = 'accept-anything'
                    elif case == 'incomplete':
                        result['diagnostic_execution_complete'] = False
                    elif case == 'false_clean':
                        result['diagnostic_process_clean'] = True
                    else:
                        result.update(diagnostic_process_clean=True, log_clean=True)
                    (output / 'result.json').write_bytes(owner_mod.canonical_bytes(result))
                    return result
                owner, grant, lease = self.fresh_owner(runner)
                before = owner._selector.read_bytes(), owner._journal.read_bytes()
                request = self.request(dict(self.source), expected=owner.inspect()['project_revision'])
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_NOT_CLEAN'):
                    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)
                self.assertTrue(owner._held)

    def test_reopen_does_not_trust_prior_startup_policy_after_log_tampering(self):
        outputs = []
        def runner(project, **kwargs):
            outputs.append(kwargs['output'])
            return explained_native_result(project, kwargs['output'])
        owner, grant, lease = self.fresh_owner(runner)
        request = self.request(dict(self.source), expected=owner.inspect()['project_revision'])
        owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        owner.close()
        before = owner._selector.read_bytes(), owner._journal.read_bytes()
        with (outputs[0] / 'engine-stderr.txt').open('ab') as stream:
            stream.write(b'ERROR: new failure\n')
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_NOT_CLEAN'):
            owner_mod.GameplaySourcePublicationOwner.reopen(owner._root,
                project_id=owner.project_id, source_closure_sha256=owner.source_closure_sha256,
                runner=lambda *a, **kw: self.fail('recovery must not dispatch'))
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)

    def test_clean_flags_do_not_bypass_raw_checks_on_publish_or_reopen(self):
        for phase in ('publish', 'reopen'):
            for missing in (False, True):
                with self.subTest(phase=phase, missing=missing):
                    outputs = []
                    def corrupt(output):
                        path = output / 'engine-stderr.txt'
                        if missing:
                            path.unlink()
                        else:
                            path.write_bytes(b'WARNING: not a clean log\n')
                    def runner(project, **kwargs):
                        output = kwargs['output']
                        outputs.append(output)
                        result = bound_native_result(project, output=output)
                        if phase == 'publish':
                            corrupt(output)
                        return result
                    owner, grant, lease = self.fresh_owner(runner)
                    request = self.request(dict(self.source), expected=owner.inspect()['project_revision'])
                    if phase == 'publish':
                        before = owner._selector.read_bytes(), owner._journal.read_bytes()
                        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_NOT_CLEAN'):
                            owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                    else:
                        owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
                        owner.close()
                        before = owner._selector.read_bytes(), owner._journal.read_bytes()
                        corrupt(outputs[0])
                        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_NOT_CLEAN'):
                            owner_mod.GameplaySourcePublicationOwner.reopen(owner._root,
                                project_id=owner.project_id, source_closure_sha256=owner.source_closure_sha256,
                                runner=lambda *a, **kw: self.fail('recovery must not dispatch'))
                    self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)


    def test_unsupported_sources_reject_before_creation_digest_or_native_stage(self):
        cases = (
            ('scripts/fixture_actor.gd', b'@tool\nextends Node3D\n', 'TOOL_SCRIPT'),
            ('scripts/secondary.gd', b'@tool\nextends RefCounted\n', 'TOOL_SCRIPT'),
            ('scenes/secondary.tscn', b'[gd_scene format=3]\n[sub_resource type="GDScript" id="s"]\n',
             'EXECUTABLE_RESOURCE'),
            ('scripts/extension.gdextension', b'[configuration]\n', 'FILE_KIND'),
        )
        for name, raw, code in cases:
            with self.subTest(name=name):
                files = {**self.source, name: raw}
                before = self.durable_state()
                inventory = sorted(path.relative_to(self.parent).as_posix()
                                   for path in self.parent.rglob('*'))
                with self.assertRaisesRegex(ValueError, code):
                    owner_mod.GameplaySourcePublicationOwner.create(self.parent,
                        project_id='project.rejected', source_files=files,
                        entrypoint=owner_mod.ENTRYPOINT,
                        source_closure_sha256=self.owner.source_closure_sha256)
                with self.assertRaisesRegex(ValueError, code):
                    self.request(files)
                # A caller need not use request_digest(). Admission must still
                # reject a correctly hashed unsupported request before staging.
                request = {'command_id': 'command.rejected', 'entrypoint': owner_mod.ENTRYPOINT,
                    'expected_project_revision': before[0]['project_revision'], 'source_files': files}
                request['digest'] = owner_mod._request_digest(project_id=self.owner.project_id, **request)
                with self.assertRaisesRegex(ValueError, code):
                    self.owner.publish(request, grant=self.grant, lease=self.lease,
                                       deadline_ms=self.lease.expires_ms)
                self.assertEqual(self.runs, [])
                self.assertEqual(self.durable_state(), before)
                self.assertEqual(sorted(path.relative_to(self.parent).as_posix()
                                        for path in self.parent.rglob('*')), inventory)

    def test_reopen_rechecks_eligibility_before_repairing_selector(self):
        # Simulate a coherent durable candidate written by the pre-fix owner.
        # Hash consistency must not replace the current eligibility policy.
        files = {**self.source, 'scripts/secondary.gd': b'@tool\nextends RefCounted\n'}
        revision = self.owner._revision(files)
        self.owner._materialize(revision, files)
        row = json.loads(self.owner._journal.read_bytes())
        row.update(project_revision=revision, source_sha256=self.owner._source_hash(files))
        self.owner._journal.write_bytes(owner_mod.canonical_bytes(row) + b'\n')
        self.owner.close()
        before = self.owner._selector.read_bytes(), self.owner._journal.read_bytes()
        with self.assertRaisesRegex(ValueError, 'TOOL_SCRIPT'):
            owner_mod.GameplaySourcePublicationOwner.reopen(self.owner._root,
                project_id=self.owner.project_id, source_closure_sha256=self.owner.source_closure_sha256,
                runner=lambda *a, **kw: self.fail('reopen must not dispatch'))
        self.assertEqual((self.owner._selector.read_bytes(), self.owner._journal.read_bytes()), before)

    def test_allowlisted_assets_survive_publish_reopen_and_retry(self):
        files = {**self.source,
                 'assets/avatar.glb': b'glTF' + (2).to_bytes(4, 'little') + (12).to_bytes(4, 'little'),
                 'assets/sprite_sheet.png': b'\x89PNG\r\n\x1a\nfixture'}
        owner, grant, lease = self.fresh_owner(lambda project, **kwargs:
            bound_native_result(project, 'asset-run', kwargs['output']))
        request = self.request(files, expected=owner.inspect()['project_revision'])
        first = owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        root = owner._root
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id=owner.project_id,
            source_closure_sha256=owner.source_closure_sha256,
            runner=lambda *a, **kw: self.fail('retry must not dispatch'))
        self.addCleanup(reopened.close)
        second = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id=owner.project_id,
            source_closure_sha256=owner.source_closure_sha256,
            runner=lambda *a, **kw: self.fail('second reopen must not dispatch'))
        self.addCleanup(second.close)
        self.assertEqual(reopened.inspect(), second.inspect())
        fresh = reopened.issue()
        grant2 = reopened.authorize('Bearer ' + fresh.bearer, 'scene.save')
        lease2 = reopened.lease(grant2)
        self.assertEqual(reopened.publish(request, grant=grant2, lease=lease2,
                                          deadline_ms=lease2.expires_ms), first)


if __name__ == "__main__":
    unittest.main()
