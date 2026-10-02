"""Subprocess generation regressions over temporary copies; no native dispatch."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

STUDIO = Path(__file__).resolve().parents[2]

BOOTSTRAP = r'''
import importlib.util, json, sys
from pathlib import Path
root = Path.cwd()
studio = root / 'studio'
def load_owner():
    spec = importlib.util.spec_from_file_location('runtime_binding_owner',
        studio / 'godot-addon/gameplay_source_owner.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
def forbidden_runner(*args, **kwargs):
    raise AssertionError('generation regression must not dispatch native work')
def create_owner(module, parent, closure):
    return module.GameplaySourcePublicationOwner.create(parent,
        project_id='project.generation',
        source_files={'scripts/fixture_actor.gd': b'extends Node3D\n',
                      'scenes/fixture.tscn': b'[gd_scene format=3]\n'},
        entrypoint=module.ENTRYPOINT, source_closure_sha256=closure,
        runner=forbidden_runner)
def error_code(error):
    return getattr(error, 'code', str(error).split(':', 1)[0])
def publication_fixture():
    # Reuse the pure shaped-result fixture, not a native executor or security
    # validator replacement. Its module and sources also live in this copy.
    spec = importlib.util.spec_from_file_location('runtime_binding_fixture',
        studio / 'tests/godot/test_gameplay_source_owner.py')
    fixture = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = fixture
    spec.loader.exec_module(fixture)
    module = fixture.owner_mod
    source = {'scripts/fixture_actor.gd': b'extends Node3D\n@export var speed: float = 2.0\n',
              'scenes/fixture.tscn': b'[gd_scene format=3]\n'}
    parent = root / 'owners'
    parent.mkdir()
    runs = []
    def runner(project, **kwargs):
        runs.append((project, kwargs))
        return fixture.bound_native_result(project, 'fake-run-%d' % len(runs), kwargs['output'])
    owner = module.GameplaySourcePublicationOwner.create(parent,
        project_id='project.gameplay', source_files=source, entrypoint=module.ENTRYPOINT,
        source_closure_sha256=module.runtime_source_closure()[1], runner=runner)
    credential = owner.issue()
    grant = owner.authorize('Bearer ' + credential.bearer, 'scene.save')
    lease = owner.lease(grant)
    candidate = dict(source)
    candidate['scripts/fixture_actor.gd'] = source['scripts/fixture_actor.gd'].replace(b'2.0', b'3.0')
    request = {'command_id':'command.generation.1',
               'expected_project_revision':owner.inspect()['project_revision'],
               'source_files':candidate, 'entrypoint':module.ENTRYPOINT}
    request['digest'] = module.request_digest(project_id=owner.project_id, **request)
    return fixture, owner, grant, lease, request, runs
def mutate_dependency():
    path = studio / 'protocol/core.py'
    path.write_bytes(path.read_bytes() + b'\nHH_RUNTIME_BINDING_MARKER = "changed"\n')
'''


class GameplayRuntimeBindingTests(unittest.TestCase):
    def test_dependency_parser_uses_captured_validator_before_drift_rejection(self):
        observation = self.run_copy(r'''
owner_mod = load_owner()
path = studio / 'godot-addon/gameplay_dependency_evidence.py'
path.write_bytes(path.read_bytes() + b'\nraise AssertionError("new disk validator executed")\n')
marker = owner_mod._load('gameplay_dependency_observation')
assert marker._VALIDATOR is owner_mod._load('gameplay_dependency_evidence')
assert marker.VALIDATOR_SHA256 == marker._VALIDATOR._gameplay_source
try:
    marker.parse_dependency_observation('', {})
except marker.DependencyObservationMarkerError as error:
    assert str(error) == 'DEPENDENCY_VALIDATOR_SOURCE_CHANGED', str(error)
else:
    raise AssertionError('changed validator accepted')
print(json.dumps({'captured_validator_used':True, 'disk_drift_rejected':True}))
''')
        self.assertEqual(observation, {'captured_validator_used': True, 'disk_drift_rejected': True})

    def run_copy(self, code):
        tree = ast.parse((STUDIO / 'godot-addon/linux_executor.py').read_bytes())
        inventory = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                and target.id == 'GAMEPLAY_RUNTIME_FILES' for target in node.targets))
        paths = set(inventory) | {'godot-addon/gameplay_runtime.py',
                                  'tests/godot/test_gameplay_source_owner.py'}
        for package in ('__init__.py', 'host/__init__.py', 'host/core/__init__.py'):
            if (STUDIO / package).is_file():
                paths.add(package)
        original = {name: (STUDIO / name).read_bytes() for name in paths}
        with tempfile.TemporaryDirectory(prefix='hh-o2-runtime-binding-') as temporary:
            copy_root = Path(temporary).resolve()
            copy_studio = copy_root / 'studio'
            for name, raw in original.items():
                destination = copy_studio / name
                self.assertTrue(destination.is_relative_to(copy_studio))
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(raw)
            env = os.environ.copy()
            env['PYTHONPATH'] = str(copy_root)
            process = subprocess.run([sys.executable, '-B', '-c', BOOTSTRAP + code],
                cwd=copy_root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=30)
            self.assertEqual(process.returncode, 0,
                process.stdout.decode('utf-8', 'replace') + '\n' +
                process.stderr.decode('utf-8', 'replace'))
            observation = json.loads(process.stdout)
        self.assertEqual(original, {name: (STUDIO / name).read_bytes() for name in paths})
        return observation

    def test_preloaded_shared_core_is_preserved_while_owner_uses_fresh_private_bytes(self):
        observation = self.run_copy(r'''
import studio.protocol.core as shared
assert Path(shared.__file__).is_relative_to(studio)
shared_function = shared.canonical_bytes
assert not hasattr(shared, 'HH_RUNTIME_BINDING_MARKER')
path = studio / 'protocol/core.py'
path.write_bytes(path.read_bytes() + b'\nHH_RUNTIME_BINDING_MARKER = "fresh-private-generation"\n')
owner_mod = load_owner()
assert owner_mod.canonical_bytes is not shared_function
assert owner_mod.canonical_bytes.__globals__['HH_RUNTIME_BINDING_MARKER'] == 'fresh-private-generation'
assert sys.modules['studio.protocol.core'] is shared
assert shared.canonical_bytes is shared_function and not hasattr(shared, 'HH_RUNTIME_BINDING_MARKER')
files, closure = owner_mod.runtime_source_closure()
parent = root / 'owners'
parent.mkdir()
owner = create_owner(owner_mod, parent, closure)
assert owner.source_closure_sha256 == closure
owner.close()
print(json.dumps({'private_fresh':True, 'shared_unchanged':True, 'new_owner_created':True}))
''')
        self.assertEqual(observation, {'private_fresh': True, 'shared_unchanged': True,
                                      'new_owner_created': True})

    def test_postimport_source_drift_rejects_closure_and_create_before_writes(self):
        for target in ('protocol/core.py', 'godot-addon/cli_job.py',
                       'godot-addon/gameplay_source_owner.py',
                       'godot-addon/publication_session.py', 'godot-addon/operations.json'):
            with self.subTest(target=target):
                code = 'target = ' + repr(target) + '\n' + r'''
owner_mod = load_owner()
_, closure = owner_mod.runtime_source_closure()
path = studio / target
suffix = b'\n' if path.suffix == '.json' else b'\nHH_RUNTIME_BINDING_MARKER = "changed"\n'
path.write_bytes(path.read_bytes() + suffix)
try:
    owner_mod.runtime_source_closure()
except owner_mod.GameplaySourceOwnerError as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('stale process accepted a new on-disk closure')
parent = root / 'owners'
parent.mkdir()
try:
    create_owner(owner_mod, parent, closure)
except owner_mod.GameplaySourceOwnerError as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('stale process created an owner after source drift')
assert list(parent.iterdir()) == []
print(json.dumps({'target':target, 'closure_rejected':True,
                  'create_rejected':True, 'no_owner_writes':True}))
'''
                observation = self.run_copy(code)
                self.assertEqual(observation, {'target': target, 'closure_rejected': True,
                    'create_rejected': True, 'no_owner_writes': True})

    def test_same_timestamp_size_and_stale_pyc_cannot_supply_private_generation(self):
        observation = self.run_copy(r'''
import os, py_compile
path = studio / 'protocol/core.py'
raw = path.read_bytes()
old = b'PROTOCOL_VERSION = "1.0"'
new = b'PROTOCOL_VERSION = "1.1"'
assert raw.count(old) == 1 and len(old) == len(new)
stamp = path.stat()
py_compile.compile(str(path), doraise=True,
    invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
path.write_bytes(raw.replace(old, new, 1))
os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
assert path.stat().st_size == stamp.st_size and path.stat().st_mtime_ns == stamp.st_mtime_ns
import studio.protocol.core as shared
assert Path(shared.__file__).is_relative_to(studio)
assert shared.PROTOCOL_VERSION == '1.0', 'test did not exercise the stale timestamp pyc'
try:
    owner_mod = load_owner()
except Exception as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
    outcome = 'FAIL_CLOSED'
else:
    assert owner_mod.canonical_bytes is not shared.canonical_bytes
    assert owner_mod.canonical_bytes.__globals__['PROTOCOL_VERSION'] == '1.1'
    owner_mod.runtime_source_closure()
    outcome = 'FRESH_PRIVATE_BYTES'
assert shared.PROTOCOL_VERSION == '1.0'
print(json.dumps({'outcome':outcome, 'stale_shared_pyc_observed':True,
                  'shared_unchanged':True}))
''')
        self.assertIn(observation['outcome'], ('FRESH_PRIVATE_BYTES', 'FAIL_CLOSED'))
        self.assertIs(observation['stale_shared_pyc_observed'], True)
        self.assertIs(observation['shared_unchanged'], True)

    def test_source_drift_blocks_cached_ack_without_new_dispatch_or_writes(self):
        observation = self.run_copy(r'''
fixture, owner, grant, lease, request, runs = publication_fixture()
owner_mod = fixture.owner_mod
ack = owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
assert ack['status'] == 'READBACK_ACK' and len(runs) == 1
assert owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms) == ack
before_selector, before_journal = owner._selector.read_bytes(), owner._journal.read_bytes()
native_raw = (owner._runs / request['command_id'] / 'result.json').read_bytes()
mutate_dependency()
try:
    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
except owner_mod.GameplaySourceOwnerError as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('stale generation returned a cached ACK')
assert len(runs) == 1
assert owner._selector.read_bytes() == before_selector
assert owner._journal.read_bytes() == before_journal
assert (owner._runs / request['command_id'] / 'result.json').read_bytes() == native_raw
owner.close()
print(json.dumps({'cached_ack_rejected':True, 'runner_calls':len(runs), 'durable_unchanged':True}))
''')
        self.assertEqual(observation, {'cached_ack_rejected': True, 'runner_calls': 1,
                                      'durable_unchanged': True})

    def test_source_drift_during_native_return_preserves_last_good_selector(self):
        observation = self.run_copy(r'''
fixture, owner, grant, lease, request, runs = publication_fixture()
owner_mod = fixture.owner_mod
before_selector, before_journal = owner._selector.read_bytes(), owner._journal.read_bytes()
proof = []
def drifting_runner(project, **kwargs):
    runs.append((project, kwargs))
    result = fixture.bound_native_result(project, 'fake-run-1', kwargs['output'])
    proof.append((kwargs['output'] / 'result.json').read_bytes())
    # The result is genuinely persisted for the admitted old generation.
    # Change real copied disk bytes only after producing that fixture result.
    mutate_dependency()
    return result
owner._runner = drifting_runner
try:
    owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
except owner_mod.GameplaySourceOwnerError as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('native return adopted under a changed runtime generation')
assert len(runs) == 1 and len(proof) == 1
assert owner._selector.read_bytes() == before_selector
assert owner._journal.read_bytes() == before_journal
assert (owner._runs / request['command_id'] / 'result.json').read_bytes() == proof[0]
assert owner._held and owner._session.status()['held']
assert request['command_id'] not in owner._jobs
owner.close()
print(json.dumps({'adopt_rejected':True, 'runner_calls':len(runs),
                  'last_good_unchanged':True, 'raw_retained':True, 'held':True}))
''')
        self.assertEqual(observation, {'adopt_rejected': True, 'runner_calls': 1,
            'last_good_unchanged': True, 'raw_retained': True, 'held': True})

    def test_reopen_source_drift_after_receipt_validation_blocks_selector_repair(self):
        observation = self.run_copy(r'''
fixture, owner, grant, lease, request, runs = publication_fixture()
owner_mod = fixture.owner_mod
ack = owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
owner_root, closure = owner._root, owner.source_closure_sha256
initial = json.loads(owner._journal.read_bytes().splitlines()[0])
owner.close()
selector, journal = owner_root / 'CURRENT', owner_root / 'journal.jsonl'
selector.write_bytes(owner_mod.canonical_bytes({'schema':'hh-gameplay-selector-1',
    'revision':initial['project_revision'], 'generation':initial['generation']}) + b'\n')
assert json.loads(selector.read_bytes())['revision'] != ack['project_revision']
before_selector, before_journal = selector.read_bytes(), journal.read_bytes()
raw_path = owner_root / 'runs' / request['command_id'] / 'result.json'
before_raw = raw_path.read_bytes()
validated = []
class DriftingRecoveryOwner(owner_mod.GameplaySourcePublicationOwner):
    @staticmethod
    def _validate_native(result, **kwargs):
        # Run the production validator fully, then inject an actual copied
        # disk update while recovery is still rebuilding its receipt loop.
        owner_mod.GameplaySourcePublicationOwner._validate_native(result, **kwargs)
        validated.append(result['run_id'])
        mutate_dependency()
try:
    DriftingRecoveryOwner.reopen(owner_root, project_id='project.gameplay',
        source_closure_sha256=closure, runner=forbidden_runner)
except owner_mod.GameplaySourceOwnerError as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('changed generation repaired CURRENT after receipt validation')
assert validated == [ack['native_run_id']] and len(runs) == 1
assert selector.read_bytes() == before_selector and journal.read_bytes() == before_journal
assert raw_path.read_bytes() == before_raw
print(json.dumps({'receipt_validated':True, 'repair_rejected':True,
                  'durable_unchanged':True, 'raw_retained':True}))
''')
        self.assertEqual(observation, {'receipt_validated': True, 'repair_rejected': True,
                                      'durable_unchanged': True, 'raw_retained': True})

    def test_stale_owner_timestamp_pyc_fails_closed_before_owner_writes(self):
        observation = self.run_copy(r'''
import os, py_compile
path = studio / 'godot-addon/gameplay_source_owner.py'
raw = path.read_bytes()
old, new = b'MAX_JOURNAL_BYTES = 512 * 1024', b'MAX_JOURNAL_BYTES = 513 * 1024'
assert raw.count(old) == 1 and len(old) == len(new)
stamp = path.stat()
py_compile.compile(str(path), doraise=True,
    invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
path.write_bytes(raw.replace(old, new, 1))
os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
assert path.stat().st_size == stamp.st_size and path.stat().st_mtime_ns == stamp.st_mtime_ns
spec = importlib.util.spec_from_file_location('runtime_binding_owner', path)
code = spec.loader.get_code(spec.name)
assert any('MAX_JOURNAL_BYTES' == instruction.argval for instruction in __import__('dis').get_instructions(code))
# The loader really supplied the stale compiled body. The runtime frame check
# must reject it even though its disk timestamp and size still match the pyc.
assert code != compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
parent = root / 'owners'
parent.mkdir()
try:
    load_owner()
except Exception as error:
    assert error_code(error) == 'GAMEPLAY_OWNER_IMPORT_RELEASE_CHANGED', error_code(error)
else:
    raise AssertionError('owner imported an old pyc under a fresh disk closure')
assert list(parent.iterdir()) == []
print(json.dumps({'stale_owner_pyc_observed':True, 'import_rejected':True, 'no_owner_writes':True}))
''')
        self.assertEqual(observation, {'stale_owner_pyc_observed': True, 'import_rejected': True,
                                      'no_owner_writes': True})


if __name__ == '__main__':
    unittest.main()
