"""S51 frozen components evidence check. AUTHORITY=0; no native operations.

verify(root) takes the components package, not the repository. Receipts and
selector effects are historical facts from the pinned owned producer. This
auditor never mints registered receipts, reopens native roots or runs engines.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
AUDIT = Path(__file__).resolve().parent
S50_PATH = AUDIT.parent / '20260917-gt03-s50-audit/verify_evidence.py'
S50_SHA256 = '56e4877f7c611af2f55bfdc2117fec0cbc97d566bf6a53c9321026d2a540ef6d'
EXPECTED_CLOSURE = '55f15f2a431b8b065565143d456bd4cafbc59bca78a99492e3674ef93a97007c'
RUN_ID = 'GT03-S51-COMPONENTS-01'
EXPECTED_CODE = ('import importlib.util,sys;from pathlib import Path;'
    'p=Path("tests/godot/run_components_probe.py").resolve();'
    's=importlib.util.spec_from_file_location("frozen_components",p);'
    'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
    'sys.exit(m.frozen_run(Path(sys.argv[1])))')


def _dependency():
    raw = S50_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != S50_SHA256:
        raise ValueError('S50 components auditor dependency changed')
    spec = importlib.util.spec_from_file_location('s51_components_pinned_s50', S50_PATH)
    result = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = result
    exec(compile(raw, str(S50_PATH), 'exec'), result.__dict__)
    return result


S50 = _dependency()
H = S50.H  # S50 in turn verifies the exact S49 helper hash before loading it.


def shape(value, keys, message):
    H.need(type(value) is dict and set(value) == set(keys), message)


def closure_digest(files):
    """Independent fixed closure algorithm; execute no unverified producer."""
    H.hash_map(files)
    return H.digest(''.join(sorted('8-9-hh3d-3/studio/' + name + '\0' + digest + '\n'
                                  for name, digest in files.items())).encode('utf-8'))


def _namespace(files):
    """Allow identical verified editor/component snapshots, never live studio."""
    verified = set()
    for name, loaded in tuple(sys.modules.items()):
        if name != 'studio' and not name.startswith('studio.'):
            continue
        location = getattr(loaded, '__file__', None)
        locations = [location] if location else list(getattr(loaded, '__path__', ()))
        for item in locations:
            path = Path(item).resolve()
            source = next((p for p in (path, *path.parents)
                           if p.name == 'studio' and p.parent.name == 'source'), None)
            H.need(source is not None and source.parent.parent.name in (
                '20260917-gt03-s51-components-01', '20260917-gt03-s51-editor-01'),
                'loaded studio dependency escaped frozen S51 source: ' + name)
            if source not in verified:
                H.source_copy(source.parent.parent, files, EXPECTED_CLOSURE)
                verified.add(source)
            if location:
                relative = path.relative_to(source).as_posix()
                H.need(relative in files and H.sha(path) == files[relative],
                       'loaded studio dependency hash mismatch: ' + name)


def epoch_ms(value):
    H.need(type(value) is str and re.fullmatch(
        r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?(?:Z|\+00:00)', value),
        'missing or non-UTC actual process time')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    delta = parsed - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000


def interval(value, result, host_started):
    start, end = value.get('validation_started_ms'), value.get('validation_completed_ms')
    H.need(H.integer(start) and H.integer(end) and 0 <= start <= end <= 9007199254740991,
           'semantic validation interval type/order')
    state = result['container_state']
    actual_start, actual_end = epoch_ms(state['StartedAt']), epoch_ms(state['FinishedAt'])
    H.need(host_started <= start <= actual_start <= actual_end <= end,
           'semantic validation interval does not enclose actual native execution')
    return start, end


def component_summary(value):
    H.need(H.exact(value, {'passed': True, 'components': 2, 'readonly_reopen_verified': True,
        'temporary_removed': True, 'public_ack': False, 'selected_state_verified': False,
        'live_editor_adoption_verified': False, 'selector_bytes_verified': True,
        'candidate_semantic_revision_verified': True}), 'component final native/reopen summary')


def _row(row, command):
    shape(row, ('command_id', 'project_revision', 'final_manifest', 'descriptor',
        'validation_receipt', 'semantic_receipt', 'semantic_observation', 'selector', 'observation',
        'namespace_barrier_readback', 'public_ack', 'selected_state_verified', 'selector_bytes_verified',
        'candidate_semantic_revision_verified', 'live_editor_adoption_verified'), 'component row shape')
    H.need(row['command_id'] == command, 'component command changed')
    for key in ('namespace_barrier_readback', 'selector_bytes_verified', 'candidate_semantic_revision_verified'):
        H.need(row[key] is True, 'component missing native/semantic fact: ' + key)
    for key in ('public_ack', 'selected_state_verified', 'live_editor_adoption_verified'):
        H.need(row[key] is False, 'component authority overclaim: ' + key)


def verify(root: Path) -> dict:
    root = Path(root).resolve()
    manifest = H.read(root / 'source-closure.json')
    shape(manifest, ('files', 'source_closure_sha256'), 'component source closure shape')
    files = H.hash_map(manifest['files'])
    H.need(manifest['source_closure_sha256'] == EXPECTED_CLOSURE
           and closure_digest(files) == EXPECTED_CLOSURE, 'component wrong independent source closure')
    source, _ = H.source_copy(root, files, EXPECTED_CLOSURE)
    package_inventory = H.inventory(root)
    capture = H.read(root / 'capture.json')
    shape(capture, ('run_id', 'source_closure_sha256', 'host', 'result', 'source_unchanged',
                    'snapshot_unchanged', 'public_ack', 'passed'), 'component capture shape')
    H.need(capture['run_id'] == RUN_ID and capture['source_closure_sha256'] == EXPECTED_CLOSURE
           and capture['public_ack'] is False, 'component source/run/authority binding')
    for flag in ('passed', 'source_unchanged', 'snapshot_unchanged'):
        H.need(capture[flag] is True, 'component capture missing ' + flag)
    component_summary(capture['result'])
    H.need(H.exact(capture['result'], H.read(root / 'components.json')), 'component raw final summary differs')
    host = capture['host']
    H.need(host.get('stdout') == 'components-stdout.txt' and host.get('stderr') == 'components-stderr.txt'
           and host.get('host') == 'components-host.json', 'component host path substitution')
    stdout, stderr = H.host(root, host)
    H.need(host.get('argv') == ['python.exe', '-B', '-c', EXPECTED_CODE, root.name],
           'component actual owned invocation changed')
    H.need(not H.BAD_LOG.search(stdout + '\n' + stderr) and not stderr.strip(), 'unclean component owned host')
    target_host = H.read(root / 'components-host.json')
    host_started = epoch_ms(target_host['started_at'])
    H.need(epoch_ms(host['started_at']) <= host_started, 'component wrapper/target start order')

    _namespace(files)
    sys.path.insert(0, str(source.parent))
    key = H.digest(str(source).encode('utf-8'))[:16]
    validate = H.module('s51_frozen_components_validation_' + key, source / 'godot-addon/validation_owner.py')
    linux_probe = H.module('s51_frozen_components_linux_' + key, source / 'tests/godot/run_linux_probe.py')
    _namespace(files)
    factory, codec, executor = validate.factory, validate.bundle_codec, validate.executor
    canonical = validate.canonical_bytes
    source_files, source_release = validate.source_release()
    H.need(all(files.get(name) == digest for name, digest in source_files.items()),
           'component validation release escaped full closure')
    H.need(source_release == H.digest(canonical(source_files)), 'component source release digest')
    first = factory.compose(factory.DEFAULT_SCENE, factory.DEFAULT_SCRIPT,
        scene_revision='sha256:' + H.digest(factory.DEFAULT_SCENE), engine_sha256=executor.BINARY_SHA256)
    second = codec.replace_script(first, b'extends Node3D\n@export var fixture_value: int = 11\n',
        expected_project_revision=first.project_revision, expected_script_sha256=first.script_sha256,
        expected_uid_sha256=first.uid_sha256)
    directories = sorted(H.inside(root, 'validation').iterdir())
    H.need(len(directories) == 2 and all(path.is_dir() and re.fullmatch(r'validate-[0-9a-f]{32}', path.name)
                                       for path in directories), 'component validation attempt inventory')
    captured = {}
    for directory in directories:
        raw_files = {name: H.inside(directory / 'input', name).read_bytes() for name in codec.PATHS}
        H.need(H.inventory(directory / 'input') == {name: H.digest(raw) for name, raw in raw_files.items()},
               'component extra/missing original input')
        bundle = codec.decode_bundle(H.inside(directory, 'manifest.json').read_bytes(), raw_files)
        factory.qualify(bundle)
        H.need(bundle.project_revision not in captured, 'duplicate original candidate revision')
        captured[bundle.project_revision] = directory, bundle

    roots, all_names, all_ids, rows, markers, intervals, run_ids = [], set(), set(), [], [], [], set()
    for index, expected in enumerate((first, second)):
        H.need(expected.project_revision in captured, 'missing exact original component candidate')
        directory, bundle = captured[expected.project_revision]
        H.need(bundle.manifest_bytes == expected.manifest_bytes and dict(bundle.files) == dict(expected.files),
               'component original candidate bytes differ')
        row = H.read(root / ('component-' + str(index) + '.json'))
        command = 'component.' + str(index)
        _row(row, command)
        result = H.verify_executor(directory / 'executor', executor, linux_probe,
                                   mode='profile-validate', timeout=20, inputs=dict(bundle.files))
        H.need(type(result['run_id']) is str and re.fullmatch(r'hh-gt03-[0-9a-f]{32}', result['run_id'])
               and result['run_id'] not in run_ids, 'component native run identity duplicate/invalid')
        run_ids.add(result['run_id'])
        observation, comparison = validate.evaluate_run(result,
            H.inside(directory, 'executor/engine-stdout.txt').read_text(encoding='utf-8'),
            H.inside(directory, 'executor/engine-stderr.txt').read_text(encoding='utf-8'), bundle)
        observation = validate.parse_json(canonical(observation))
        H.need(H.exact(row['observation'], observation) and comparison.get('semantic_observed') is True,
               'component raw full semantic observation differs/missing')
        receipt = {'command_id': command, 'project_revision': bundle.project_revision,
            'manifest_sha256': H.digest(bundle.manifest_bytes), 'source_release_sha256': source_release,
            'engine_sha256': executor.BINARY_SHA256, 'observation_sha256': H.digest(canonical(observation)),
            'evidence_sha256': H.digest(canonical(H.inventory(directory))), 'run_id': result['run_id'],
            'status': 'OWNED_PROFILE_VALIDATED', 'public_ack': False, 'selected_state_verified': False}
        H.need(H.exact(row['validation_receipt'], receipt), 'original issued receipt differs from independent raw facts')

        # Compute from the entire native state, not its supplied revision label.
        state_bytes = canonical(observation['semantic']['state'])
        semantic_revision = 'sha256:' + H.digest(state_bytes)
        H.need(semantic_revision == observation['semantic']['revision'] == comparison['semantic_revision'],
               'component full semantic JCS revision differs')
        final = codec.create_bundle(dict(bundle.files), scene_revision=semantic_revision,
                                    engine_sha256=executor.BINARY_SHA256)
        H.need(dict(final.files) == dict(bundle.files) and final.manifest_bytes != bundle.manifest_bytes,
               'component semantic binding did not preserve inputs/remanifest')
        H.need(H.exact(row['final_manifest'], validate.parse_json(final.manifest_bytes))
               and row['project_revision'] == final.project_revision,
               'component final manifest is not exact semantic remanifest')
        intervals.append(interval(row['semantic_receipt'], result, host_started))
        start, end = intervals[-1]
        semantic_receipt = {'command_id': command, 'project_revision': final.project_revision,
            'scene_revision': semantic_revision, 'manifest_sha256': H.digest(final.manifest_bytes),
            'input_files_sha256': H.digest(canonical(validate.parse_json(final.manifest_bytes)['files'])),
            'source_release_sha256': source_release, 'validator_engine_sha256': executor.BINARY_SHA256,
            'observation_sha256': receipt['observation_sha256'], 'evidence_sha256': receipt['evidence_sha256'],
            'run_id': result['run_id'], 'validation_started_ms': start, 'validation_completed_ms': end,
            'context_kind': 'isolated_candidate', 'public_ack': False,
            'selected_state_verified': False, 'live_editor_adoption_verified': False}
        H.need(H.exact(row['semantic_receipt'], semantic_receipt), 'component semantic issued receipt differs')
        semantic_observation = {'context_kind': 'isolated_candidate', 'command_id': command,
            'run_id': result['run_id'], 'validation_started_ms': start, 'validation_completed_ms': end,
            'project_revision': final.project_revision, 'manifest_sha256': H.digest(final.manifest_bytes),
            'validator_engine_sha256': executor.BINARY_SHA256, 'source_release_sha256': source_release,
            'semantic': observation['semantic'], 'public_ack': False, 'selected_state_verified': False,
            'live_editor_adoption_verified': False}
        H.need(H.exact(row['semantic_observation'], semantic_observation), 'component bound observation differs')
        native_root, names, identities = S50.descriptor(row['descriptor'], final)
        H.need(not names.intersection(all_names) and not identities.intersection(all_ids),
               'cross-component native identity/name alias')
        roots.append(native_root); all_names.update(names); all_ids.update(identities)
        expected_selector = {'schema': 'hh-godot-active-selection-1', 'command_id': command,
            'parent_selection': None if index == 0 else rows[-1]['selector']['selection'],
            'selection': {'generation': index, 'identity': 'sha256:' + H.digest(final.manifest_bytes)},
            'descriptor_sha256': H.digest(canonical(row['descriptor'])), 'descriptor': row['descriptor']}
        H.need(H.exact(row['selector'], expected_selector) and len(canonical(row['selector'])) <= 16384,
               'component selector bytes/parent/generation/descriptor chain differs')
        rows.append(row)
        markers.append({'command_id': command, 'project_revision': final.project_revision})

    H.need(roots[0] == roots[1] and len(all_names) == len(all_ids) == 24, 'component same-root complete namespace')
    H.need(intervals[0][1] <= intervals[1][0], 'component validation intervals overlap/out of order')
    H.need(rows[0]['observation']['script']['source_sha256'] != rows[1]['observation']['script']['source_sha256'],
           'script replacement not actually observed')
    H.need(H.exact(H.markers(stdout, 'HH_COMPONENT_VERIFIED '), markers), 'component actual host markers differ')
    H.need(H.inventory(root) == package_inventory, 'component evidence changed during audit')
    _namespace(files)
    return {'components': 2, 'native_descriptor_files': 24, 'source_closure_sha256': EXPECTED_CLOSURE,
        'source_release_sha256': source_release, 'original_validation_raw_facts_verified': True,
        'full_semantic_jcs_binding_verified': True, 'historical_native_readback_bound': True,
        'selector_chain_host_verified': True, 'readonly_reopen_host_verified': True,
        'validation_interval_available_bounds_verified': True, 'final_host_completion_upper_bound_available': False,
        'selector_native_versions_persisted': False, 'independent_live_root_verification': False,
        'public_ack': False, 'selected_state_verified': False, 'live_editor_adoption_verified': False,
        'authenticated_publication_verified': False}


if __name__ == '__main__':
    H.need(len(sys.argv) == 2, 'usage: components_check.py COMPONENTS_PACKAGE')
    print(H.json.dumps(verify(Path(sys.argv[1])), indent=2))
