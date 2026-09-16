"""S50 diagnostic audit adapter. AUTHORITY=0; no publication acceptance.

Reuse the hash-pinned S49 auditor with explicit package/count/marker bindings.
Additional component checks are historical host-evidence checks, not live root
reopening or receipt registration. No native process is launched by this file.
"""
from __future__ import annotations
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
LEGACY = AUDIT.parent / '20260917-gt03-s49-audit/verify_evidence.py'
LEGACY_SHA256 = 'ad040b4512fbdfd865131a7d281ca958fad853cee36b1c21e3e0b2870338271f'
EXPECTED_CLOSURE = 'e6fcee30d7000aef5a5781e7cebe04c08e2be9a961c033fae3f0926d1e44bc3d'
EXPECTED_TESTS = 421  # Actual completed raw marker/stderr: 421, no failures/skips.
COMPONENTS = AUDIT.parent / '20260917-gt03-s50-components-01'
OLD_MARKER, MARKER = 'S49_IDLE_BODY_AFTER_HOST_DEATH', 'S50_IDLE_BODY_AFTER_HOST_DEATH'


def load_legacy(path=LEGACY):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA256:
        raise ValueError('S49 auditor dependency hash changed')
    # This single named run marker appears in the expected log and idle source.
    # Require the exact pinned source and occurrence count before substitution.
    if raw.count(OLD_MARKER.encode()) != 2:
        raise ValueError('S49 auditor marker binding changed')
    adapted = raw.replace(OLD_MARKER.encode(), MARKER.encode())
    spec = importlib.util.spec_from_file_location('s50_pinned_audit_helpers', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile(adapted, str(path), 'exec'), module.__dict__)
    module.AUDIT = AUDIT
    module.PACKAGE = AUDIT.parent / '20260917-gt03-s50-editor-01'
    module.LINUX = AUDIT.parent / '20260917-gt03-s50-linux-01'
    module.PROFILE = AUDIT.parent / '20260917-gt03-s50-profile-01'
    module.HOST_DEATH = AUDIT.parent / '20260917-gt03-s50-host-death-01'
    module.EXPECTED_TESTS = EXPECTED_TESTS
    module.EXPECTED_ENGINE_CHECKS = {'edit': 103, 'reopen': 10, 'contract': 31}
    return module


H = load_legacy()


def shape(value, keys, message):
    H.need(type(value) is dict and set(value) == set(keys), message)


def descriptor(value, bundle):
    """Strict descriptor/actual candidate bytes binding; no native owner call."""
    shape(value, ('root_identity', 'project_revision', 'files', 'manifest'), 'component descriptor shape')
    root = value['root_identity']
    shape(root, ('volume', 'file_id'), 'component root shape')
    H.need(type(root['volume']) is str and re.fullmatch(r'0|[1-9][0-9]{0,19}', root['volume'])
           and int(root['volume']) < 2**64 and type(root['file_id']) is str
           and re.fullmatch(r'[0-9a-f]{32}', root['file_id']), 'component native root identity')
    H.need(value['project_revision'] == bundle.project_revision, 'component descriptor project revision')
    shape(value['files'], bundle.files, 'component eleven-file descriptor')
    rows = {**value['files'], '@manifest': value['manifest']}
    names, identities = set(), set()
    for logical, row in rows.items():
        shape(row, ('name', 'volume', 'file_id', 'size_bytes', 'sha256'), 'component native FileVersion shape')
        H.need(type(row['name']) is str and re.fullmatch(r'obj-[0-9a-f]{32}', row['name'])
               and row['name'] not in names, 'component aliased native name')
        H.need(row['volume'] == root['volume'] and type(row['file_id']) is str
               and re.fullmatch(r'[0-9a-f]{32}', row['file_id'])
               and row['file_id'] not in identities and row['file_id'] != root['file_id'], 'component native identity alias/volume')
        raw = bundle.manifest_bytes if logical == '@manifest' else bundle.files[logical]
        H.need(H.integer(row['size_bytes'], len(raw)) and row['sha256'] == H.digest(raw), 'component descriptor bytes mismatch')
        names.add(row['name']); identities.add(row['file_id'])
    H.need(len(names) == len(identities) == 12, 'incomplete component native namespace')
    return root, names, identities


def component_summary(value):
    expected = {'passed': True, 'components': 2, 'readonly_reopen_verified': True,
                'temporary_removed': True, 'public_ack': False, 'selected_state_verified': False,
                'semantic_scene_revision_verified': False}
    H.need(H.exact(value, expected), 'component final native/reopen summary')


def verify_components(files, closure):
    source, _ = H.source_copy(COMPONENTS, files, closure)
    capture = H.read(COMPONENTS / 'capture.json')
    H.need(capture.get('source_closure_sha256') == closure and capture.get('public_ack') is False,
           'component source/authority binding')
    for flag in ('passed', 'source_unchanged', 'snapshot_unchanged'):
        H.need(capture.get(flag) is True, 'component capture missing ' + flag)
    component_summary(capture['result'])
    H.need(H.exact(capture['result'], H.read(COMPONENTS / 'components.json')), 'component raw final summary differs')
    stdout, stderr = H.host(COMPONENTS, capture['host'])
    H.need(not H.BAD_LOG.search(stdout + '\n' + stderr) and not stderr.strip(), 'unclean component owned host')
    expected_code = ('import importlib.util,sys;from pathlib import Path;'
        'p=Path("tests/godot/run_components_probe.py").resolve();'
        's=importlib.util.spec_from_file_location("frozen_components",p);'
        'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
        'sys.exit(m.frozen_run(Path(sys.argv[1])))')
    H.need(capture['host'].get('argv') == ['python.exe', '-B', '-c', expected_code, COMPONENTS.name],
           'component actual host invocation differs')
    # Import only from the already verified component copy. The global studio
    # namespace has been bound by the reused verifier to identical editor bytes.
    validate = H.module('s50_frozen_component_validation', source / 'godot-addon/validation_owner.py')
    linux_probe = H.module('s50_component_linux_binding', source / 'tests/godot/run_linux_probe.py')
    factory, codec, executor = validate.factory, validate.bundle_codec, validate.executor
    source_files, source_release = validate.source_release()
    H.need(all(files.get(name) == digest for name, digest in source_files.items()), 'component validation release escaped full closure')
    canonical = validate.canonical_bytes
    first = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + H.digest(factory.DEFAULT_SCENE), engine_sha256=executor.BINARY_SHA256)
    second = codec.replace_script(first, b'extends Node3D\n@export var fixture_value: int = 11\n',
        expected_project_revision=first.project_revision, expected_script_sha256=first.script_sha256,
        expected_uid_sha256=first.uid_sha256)
    directories = sorted((COMPONENTS / 'validation').iterdir())
    H.need(len(directories) == 2 and all(path.is_dir() and re.fullmatch(r'validate-[0-9a-f]{32}', path.name)
                                       for path in directories), 'component validation attempt inventory')
    captured = {}
    for directory in directories:
        raw_files = {name: H.inside(directory / 'input', name).read_bytes() for name in codec.PATHS}
        H.need(H.inventory(directory / 'input') == {name: H.digest(raw) for name, raw in raw_files.items()}, 'component input extra file')
        bundle = codec.decode_bundle((directory / 'manifest.json').read_bytes(), raw_files)
        factory.qualify(bundle)
        H.need(bundle.project_revision not in captured, 'duplicate component candidate revision')
        captured[bundle.project_revision] = (directory, bundle)
    roots, all_names, all_ids, rows, markers = [], set(), set(), [], []
    for index, expected in enumerate((first, second)):
        H.need(expected.project_revision in captured, 'missing exact component candidate')
        directory, bundle = captured[expected.project_revision]
        H.need(bundle.manifest_bytes == expected.manifest_bytes and dict(bundle.files) == dict(expected.files), 'component candidate bytes differ')
        row = H.read(COMPONENTS / ('component-' + str(index) + '.json'))
        shape(row, ('command_id', 'project_revision', 'descriptor', 'validation_receipt', 'observation',
                    'namespace_barrier_readback', 'public_ack', 'selected_state_verified',
                    'semantic_scene_revision_verified'), 'component row shape')
        command = 'component.' + str(index)
        H.need(row['command_id'] == command and row['project_revision'] == bundle.project_revision
               and row['namespace_barrier_readback'] is True, 'component historical native readback fact')
        H.need(all(row[key] is False for key in ('public_ack', 'selected_state_verified', 'semantic_scene_revision_verified')),
               'component scope overclaim')
        root, names, identities = descriptor(row['descriptor'], bundle)
        H.need(not names.intersection(all_names) and not identities.intersection(all_ids), 'cross-component native alias')
        roots.append(root); all_names.update(names); all_ids.update(identities)
        result = H.verify_executor(directory / 'executor', executor, linux_probe,
                                   mode='profile-validate', timeout=20, inputs=dict(bundle.files))
        raw_stdout = (directory / 'executor/engine-stdout.txt').read_text(encoding='utf-8')
        raw_stderr = (directory / 'executor/engine-stderr.txt').read_text(encoding='utf-8')
        observation, _ = validate.evaluate_run(result, raw_stdout, raw_stderr, bundle)
        # The actual issuer stores canonical bytes, then observation() parses
        # those bytes. JCS renders integral float values as JSON integers.
        observation = validate.parse_json(canonical(observation))
        H.need(H.exact(row['observation'], observation), 'component raw engine observation differs')
        receipt = {'command_id': command, 'project_revision': bundle.project_revision,
            'manifest_sha256': H.digest(bundle.manifest_bytes), 'source_release_sha256': source_release,
            'engine_sha256': executor.BINARY_SHA256, 'observation_sha256': H.digest(canonical(observation)),
            'evidence_sha256': H.digest(canonical(H.inventory(directory))), 'run_id': result['run_id'],
            'status': 'OWNED_PROFILE_VALIDATED', 'public_ack': False, 'selected_state_verified': False}
        H.need(H.exact(row['validation_receipt'], receipt), 'component registered receipt data differs from raw evidence')
        rows.append(row)
        markers.append({'command_id': command, 'project_revision': bundle.project_revision})
    H.need(roots[0] == roots[1] and len(all_names) == len(all_ids) == 24, 'component same-root complete namespace')
    H.need(rows[0]['observation']['script']['source_sha256'] != rows[1]['observation']['script']['source_sha256'], 'script replacement not observed')
    H.need(H.exact(H.markers(stdout, 'HH_COMPONENT_VERIFIED '), markers), 'component actual host markers differ')
    return {'components': 2, 'native_descriptor_files': 24, 'historical_native_readback_bound': True,
            'readonly_reopen_host_verified': True, 'independent_live_root_verification': False,
            'public_ack': False, 'selected_state_verified': False, 'semantic_scene_revision_verified': False}


def verify():
    H.need(H.integer(EXPECTED_TESTS), 'actual completed unit count has not been bound')
    H.EXPECTED_TESTS = EXPECTED_TESTS
    manifest = H.read(H.PACKAGE / 'source-closure.json')
    H.need(manifest.get('source_closure_sha256') == EXPECTED_CLOSURE, 'wrong S50 frozen closure')
    summary = H.verify()
    summary['components'] = verify_components(manifest['files'], EXPECTED_CLOSURE)
    # Components are a mandatory principal package, not merely optional entries.
    artifacts = H.read(AUDIT / 'artifact-manifest.json')['files']
    prefix = COMPONENTS.relative_to(H.ROOT).as_posix() + '/'
    H.need({name[len(prefix):]: digest for name, digest in artifacts.items() if name.startswith(prefix)}
           == H.inventory(COMPONENTS), 'component artifact inventory omitted/added files')
    summary.update(status='S50_DIAGNOSTIC_CHECKPOINT_VERIFIED', authority=0, acceptance=False,
                   formal_acceptance=False, public_ack=False, reused_auditor_sha256=LEGACY_SHA256,
                   host_death_marker=MARKER)
    return summary


if __name__ == '__main__':
    H.need(len(sys.argv) <= 2, 'usage: verify_evidence.py [index|HEAD]')
    summary = verify()
    if len(sys.argv) == 2:
        H.git_bytes(summary, sys.argv[1])
    destination = AUDIT / ('verification.json' if len(sys.argv) == 1 else 'git-byte-verification-' + sys.argv[1] + '.json')
    destination.write_text(H.json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(H.json.dumps(summary))
