"""Exercise the enabled dependency gate through publication and recovery.

Only the executor is a shaped fake; parser, policy, disk evidence and owner
lifecycle are real. These tests do not claim native Godot observation.
"""
import json
from pathlib import Path
import tempfile
import unittest

from studio.tests.godot.test_gameplay_source_owner import owner_mod, bound_native_result


class OwnerDependencyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='hh-owner-dependencies-')
        self.addCleanup(temporary.cleanup)
        self.parent = Path(temporary.name)
        self.source = {'scripts/fixture_actor.gd': b'extends Node3D\n',
                       'scenes/fixture.tscn': b'[gd_scene format=3]\n'}
        # Intentionally not sorted, matching the native fixture declaration.
        self.paths = tuple(self.source)
        self.calls = []
        self.raw_results = []
        self.access = {}
        self.transform = lambda graph: graph
        self.dirty = False

    def runner(self, project, **kw):
        self.calls.append(kw['output'])
        result = bound_native_result(project, output=kw['output'])
        graph = {'schema': 'hh-gameplay-dependency-observation-1', 'version': 1,
                 'entrypoint': owner_mod.ENTRYPOINT, 'nodes': []}
        for name in self.paths:
            raw = (project / name).read_bytes()
            graph['nodes'].append({'path': name, 'kind': 'script' if name.endswith('.gd') else 'scene',
                                   'size_bytes': len(raw), 'sha256': owner_mod._sha(raw),
                                   'edges': []})
        graph = self.transform(graph)
        stdout = b'' if graph is None else b'HH_PROBE_DEPENDENCY ' + json.dumps(graph).encode() + b'\n'
        (kw['output'] / 'engine-stdout.txt').write_bytes(stdout)
        if self.dirty:
            result.update(errors=['EXECUTOR_UNRECORDED_CONTAINER'], diagnostic_process_clean=False)
            (kw['output'] / 'result.json').write_bytes(owner_mod.canonical_bytes(result))
        self.raw_results.append((kw['output'] / 'result.json').read_bytes())
        return result

    def create(self):
        owner = owner_mod.GameplaySourcePublicationOwner.create(
            self.parent, project_id='project.dependencies', source_files=self.source,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=owner_mod.runtime_source_closure()[1],
            runner=self.runner, dependency_observation_required=True,
            dependency_observation_files=self.paths)
        self.addCleanup(owner.close)
        return owner

    def request(self, owner):
        files = {**self.source, owner_mod.ENTRYPOINT: self.source[owner_mod.ENTRYPOINT] + b'# new\n'}
        request = {'command_id': 'command.dependencies.1', 'source_files': files,
                   'entrypoint': owner_mod.ENTRYPOINT,
                   'expected_project_revision': owner.inspect()['project_revision']}
        request['digest'] = owner_mod.request_digest(project_id=owner.project_id, **request)
        return request

    def publish(self, owner, request):
        if owner not in self.access:
            token = owner.issue()
            grant = owner.authorize('Bearer ' + token.bearer, 'scene.save')
            self.access[owner] = grant, owner.lease(grant)
        grant, lease = self.access[owner]
        return owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)

    def reopen(self, owner, **kwargs):
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            owner._root, project_id=owner.project_id, source_closure_sha256=owner.source_closure_sha256,
            runner=lambda *a, **kw: self.fail('recovery must not redispatch'), **kwargs)
        self.addCleanup(reopened.close)
        return reopened

    def test_enabled_publish_retry_reopen_binds_bytes_and_preserves_raw(self):
        owner = self.create()
        request = self.request(owner)
        receipt = self.publish(owner, request)
        run = self.calls[0]
        self.assertEqual((run / 'result.json').read_bytes(), self.raw_results[0])
        evidence = json.loads((run / 'dependency-observation.json').read_bytes())
        self.assertEqual(evidence['native_result_sha256'], owner_mod._sha(self.raw_results[0]))
        self.assertEqual(evidence['report']['authority'], 0)
        self.assertFalse(evidence['report']['dependency_closure_verified'])
        self.assertFalse(evidence['report']['public_ack'])
        durable = owner._selector.read_bytes(), owner._journal.read_bytes()
        self.assertEqual(self.publish(owner, request), receipt)
        owner.close()
        reopened = self.reopen(owner, dependency_observation_required=True,
                               dependency_observation_files=self.paths)
        self.assertEqual(self.publish(reopened, request), receipt)
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), durable)
        self.assertEqual(len(self.calls), 1)

    def test_missing_and_stale_markers_preserve_last_good(self):
        def stale(graph):
            graph['nodes'][0]['sha256'] = '0' * 64
            return graph
        for transform in (lambda graph: None, stale):
            with self.subTest(transform=transform):
                self.transform = transform
                owner = self.create()
                request = self.request(owner)
                durable = owner._selector.read_bytes(), owner._journal.read_bytes()
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_OBSERVATION'):
                    self.publish(owner, request)
                self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), durable)
                self.assertFalse((self.calls[-1] / 'dependency-observation.json').exists())

    def test_executor_failure_is_not_masked_by_absent_marker(self):
        self.dirty = True
        self.transform = lambda graph: None
        owner = self.create()
        request = self.request(owner)
        durable = owner._selector.read_bytes(), owner._journal.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_NOT_CLEAN'):
            self.publish(owner, request)
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), durable)
        self.assertEqual((self.calls[0] / 'result.json').read_bytes(), self.raw_results[0])

    def test_missing_changed_evidence_blocks_reopen_before_selector_repair(self):
        for change in ('missing', 'graph', 'stdout', 'native_result'):
            with self.subTest(change=change):
                owner = self.create()
                old_selector = owner._selector.read_bytes()
                self.publish(owner, self.request(owner))
                owner.close()
                run = self.calls[-1]
                path = run / 'dependency-observation.json'
                if change == 'missing':
                    path.unlink()
                elif change == 'graph':
                    report = json.loads(path.read_bytes())
                    report['report']['graph_sha256'] = '0' * 64
                    path.write_bytes(owner_mod.canonical_bytes(report))
                elif change == 'stdout':
                    (run / 'engine-stdout.txt').write_bytes((run / 'engine-stdout.txt').read_bytes() + b'# changed\n')
                else:
                    (run / 'result.json').write_bytes((run / 'result.json').read_bytes() + b'\n')
                owner._selector.write_bytes(old_selector)
                journal = owner._journal.read_bytes()
                with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_'):
                    self.reopen(owner)
                self.assertEqual(owner._selector.read_bytes(), old_selector)
                self.assertEqual(owner._journal.read_bytes(), journal)

    def test_policy_downgrade_rejects_even_without_caller_override(self):
        owner = self.create()
        self.publish(owner, self.request(owner))
        owner.close()
        policy = owner._root / owner_mod.DEPENDENCY_POLICY_FILE
        policy.write_bytes(owner_mod._dependency_policy_payload(False, ()))
        durable = owner._selector.read_bytes(), owner._journal.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_POLICY'):
            self.reopen(owner)
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), durable)

    def test_lost_dependency_evidence_blocks_cached_ack(self):
        owner = self.create()
        request = self.request(owner)
        self.publish(owner, request)
        (self.calls[-1] / 'dependency-observation.json').unlink()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_BINDING'):
            self.publish(owner, request)
        self.assertEqual(len(self.calls), 1)

    def test_lost_dependency_evidence_between_stage_and_adopt_preserves_selector(self):
        owner = self.create()
        request = self.request(owner)
        original = owner._adopt
        def adopt(*args):
            (self.calls[-1] / 'dependency-observation.json').unlink()
            return original(*args)
        owner._adopt = adopt
        before = owner._selector.read_bytes(), owner._journal.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_BINDING'):
            self.publish(owner, request)
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)

    def test_live_policy_edit_rejects_before_dispatch(self):
        owner = self.create()
        request = self.request(owner)
        (owner._root / owner_mod.DEPENDENCY_POLICY_FILE).write_bytes(
            owner_mod._dependency_policy_payload(False, ()))
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_POLICY'):
            self.publish(owner, request)
        self.assertEqual(self.calls, [])

    def test_changed_result_before_persistence_is_retained_and_rejected(self):
        owner = self.create()
        original = owner._persist_dependency_observation
        def diverge(result, output, expected_files):
            changed = {**result, 'run_id': 'changed-run-id'}
            (output / 'result.json').write_bytes(owner_mod.canonical_bytes(changed))
            return original(result, output, expected_files)
        owner._persist_dependency_observation = diverge
        request = self.request(owner)
        before = owner._selector.read_bytes(), owner._journal.read_bytes()
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'NATIVE_RESULT_BINDING'):
            self.publish(owner, request)
        self.assertEqual(json.loads((self.calls[-1] / 'result.json').read_bytes())['run_id'], 'changed-run-id')
        self.assertFalse((self.calls[-1] / 'dependency-observation.json').exists())
        self.assertEqual((owner._selector.read_bytes(), owner._journal.read_bytes()), before)

    def test_declared_dependency_missing_in_candidate_rejects_before_dispatch(self):
        source = 'scripts/shared_motion.gd'
        self.source[source] = b'extends RefCounted\n'
        self.paths = tuple(self.source)
        owner = self.create()
        request = self.request(owner)
        del request['source_files'][source]
        request['digest'] = owner_mod.request_digest(project_id=owner.project_id,
                                                    **{k: v for k, v in request.items() if k != 'digest'})
        with self.assertRaisesRegex(owner_mod.GameplaySourceOwnerError, 'DEPENDENCY_FILES'):
            self.publish(owner, request)
        self.assertEqual(self.calls, [])


if __name__ == '__main__':
    unittest.main()
