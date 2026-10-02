"""Native fixture publication/reopen/retry diagnostic; never public acceptance.

Uses the real bounded Docker executor once, then proves durable recovery and
deduplication without a second native dispatch. Run only outside GT06's
measurement window. The caller must capture this process's actual exit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
ARENA_FIXTURE = 'gameplay_arena_physics'
ARENA_DEPENDENCY_FILES = ('scenes/fixture.tscn', 'scripts/fixture_actor.gd',
                          'scenes/projectile.tscn')
SAVED_ARENA_PATH = 'scenes/arena.tscn'
SAVED_ARENA_DEPENDENCY_FILES = ARENA_DEPENDENCY_FILES + (SAVED_ARENA_PATH,)
ARENA_SOURCE_FILES = {
    'scripts/fixture_actor.gd': 'tests/godot/gameplay_fixture/arena_physics.gd',
    'scenes/projectile.tscn': 'tests/godot/gameplay_fixture/projectile.tscn',
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def need(value, message):
    if not value:
        raise RuntimeError(message)


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')


def idle_window():
    base = os.environ.get('LOCALAPPDATA')
    need(base, 'LOCALAPPDATA_REQUIRED')
    need(not (Path(base) / 'HHGodotAgent/measure-window.lock').exists(),
         'MEASUREMENT_WINDOW_HELD')


def publication_fixture_allowed(name, catalog):
    return name in catalog and (name.startswith('gameplay_source_') or name == ARENA_FIXTURE)


def publication_dependency_policy(name, case, *, saved_arena=False):
    need(not saved_arena or name == ARENA_FIXTURE, 'SAVED_ARENA_FIXTURE_REQUIRED')
    if name == ARENA_FIXTURE:
        expected = SAVED_ARENA_DEPENDENCY_FILES if saved_arena else ARENA_DEPENDENCY_FILES
        need(case.get('dependency_observation') is True
             and case.get('dependency_files') == expected,
             'ARENA_DEPENDENCY_POLICY_REQUIRED')
    return {'dependency_observation_required': case.get('dependency_observation') is True,
            'dependency_observation_files': tuple(case.get('dependency_files', ()))}


def saved_arena_case(name, case, raw):
    """Attach native-builder bytes; never synthesize the saved arena scene."""
    need(name == ARENA_FIXTURE, 'SAVED_ARENA_FIXTURE_REQUIRED')
    need(type(raw) is bytes and 0 < len(raw) <= 1_048_576, 'SAVED_ARENA_BYTES_REQUIRED')
    scene = case['scene']
    replacements = (
        ('[gd_scene load_steps=2 format=3]', '[gd_scene load_steps=3 format=3]'),
        ('[node name="Fixture" type="Node3D"]',
         '[ext_resource type="PackedScene" path="res://scenes/arena.tscn" id="2_world"]\n\n'
         '[node name="Fixture" type="Node3D"]'),
        ('script = ExtResource("1_script")',
         'script = ExtResource("1_script")\nsaved_world = ExtResource("2_world")'),
    )
    for old, new in replacements:
        need(scene.count(old) == 1, 'SAVED_ARENA_FIXTURE_TEMPLATE')
        scene = scene.replace(old, new, 1)
    need(SAVED_ARENA_PATH not in case.get('extra_files', {}), 'SAVED_ARENA_INPUT_COLLISION')
    return {**case, 'scene': scene,
            'extra_files': {**case.get('extra_files', {}), SAVED_ARENA_PATH: raw.decode('utf-8')},
            'expected_state': {**case['expected_state'], 'saved_world_instantiated': True},
            'dependency_files': SAVED_ARENA_DEPENDENCY_FILES}


def _provenance_file(root, name):
    need(type(name) is str and name and '\\' not in name and ':' not in name
         and not name.startswith('/') and all(part not in ('', '.', '..') for part in name.split('/')),
         'SAVED_ARENA_PROVENANCE_PATH')
    path = root / name
    need(path.resolve().is_relative_to(root.resolve()) and path.is_file()
         and not any(part.is_symlink() for part in (path, *path.parents) if part != root.parent),
         'SAVED_ARENA_PROVENANCE_PATH')
    return path


def freeze_saved_arena(name, directory, frozen_root, builder):
    need(name == ARENA_FIXTURE, 'SAVED_ARENA_FIXTURE_REQUIRED')
    raw = builder.verify_saved_arena(directory)
    need(type(raw) is bytes and 0 < len(raw) <= 1_048_576, 'SAVED_ARENA_BYTES_REQUIRED')
    provenance = builder.saved_arena_provenance(directory)
    need(type(provenance) is dict and type(provenance.get('files')) is dict
         and provenance['files'], 'SAVED_ARENA_PROVENANCE_REQUIRED')
    binding = {'scene_sha256': hashlib.sha256(raw).hexdigest(), 'scene_size_bytes': len(raw),
               'provenance': provenance}
    frozen_root.mkdir(exist_ok=False)
    with (frozen_root / 'arena.tscn').open('xb') as stream:
        stream.write(raw)
    for name, digest in provenance['files'].items():
        content = _provenance_file(directory, name).read_bytes()
        need(hashlib.sha256(content).hexdigest() == digest, 'SAVED_ARENA_PROVENANCE_CHANGED')
        target = frozen_root / 'provenance' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(content)
    save(frozen_root / 'binding.json', binding)
    return raw, binding


def verify_saved_arena_binding(directory, frozen_root, binding, builder, candidate):
    """Recheck trusted native proof and every frozen byte immediately before use."""
    raw = builder.verify_saved_arena(directory)
    need(builder.saved_arena_provenance(directory) == binding['provenance'],
         'SAVED_ARENA_PROVENANCE_CHANGED')
    need(json.loads((frozen_root / 'binding.json').read_text(encoding='utf-8')) == binding,
         'SAVED_ARENA_BINDING_CHANGED')
    frozen = (frozen_root / 'arena.tscn').read_bytes()
    need(type(raw) is bytes and raw == frozen == candidate.get(SAVED_ARENA_PATH)
         and len(raw) == binding['scene_size_bytes']
         and hashlib.sha256(raw).hexdigest() == binding['scene_sha256'], 'SAVED_ARENA_SOURCE_CHANGED')
    for name, digest in binding['provenance']['files'].items():
        need(all(hashlib.sha256(_provenance_file(root, name).read_bytes()).hexdigest() == digest
                 for root in (directory, frozen_root / 'provenance')),
             'SAVED_ARENA_PROVENANCE_CHANGED')


def verify_fixture_sources(name, case, candidate, hashes, *, source_root, frozen_root):
    """Bind imported arena templates to frozen raw bytes and current disk bytes.

    read_text uses universal newlines on Windows. Preserve raw hashes while
    comparing the loaded template to the same normalized text from the freeze.
    """
    if name != ARENA_FIXTURE:
        return
    for target, source in ARENA_SOURCE_FILES.items():
        need(source in hashes, 'ARENA_SOURCE_BINDING_MISSING')
        frozen = (frozen_root / source).read_bytes()
        current = (source_root / source).read_bytes()
        need(hashlib.sha256(frozen).hexdigest() == hashes[source]
             and hashlib.sha256(current).hexdigest() == hashes[source],
             'ARENA_SOURCE_CHANGED')
        expected = frozen.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
        loaded = case.get('script') if target.endswith('.gd') else case.get('extra_files', {}).get(target)
        need(type(loaded) is str and loaded.encode('utf-8') == expected
             and candidate.get(target) == expected, 'ARENA_TEMPLATE_FREEZE_MISMATCH')


def verify_fixture_observation(name, observation, *, saved_arena=False):
    need(observation['fixture_observed'] is True, 'NATIVE_FIXTURE_NOT_OBSERVED')
    if name != ARENA_FIXTURE:
        return
    graph = observation.get('dependency_observation', {}).get('observation', {})
    nodes = graph.get('nodes', [])
    expected = {
        'scenes/fixture.tscn': [{'kind': 'scene_ext_resource', 'target': 'scripts/fixture_actor.gd'}],
        'scripts/fixture_actor.gd': [{'kind': 'script_preload', 'target': 'scenes/projectile.tscn'}],
        'scenes/projectile.tscn': [],
    }
    if saved_arena:
        expected['scenes/fixture.tscn'].append({'kind': 'scene_ext_resource', 'target': SAVED_ARENA_PATH})
        expected[SAVED_ARENA_PATH] = []
    # Dependency order is not semantic; the bound graph parser rejects duplicates.
    normalize = lambda rows: sorted((row['kind'], row['target']) for row in rows)
    need(graph.get('entrypoint') == 'scenes/fixture.tscn' and len(nodes) == len(expected)
         and {row.get('path'): normalize(row.get('edges', [])) for row in nodes}
             == {path: normalize(edges) for path, edges in expected.items()},
         'ARENA_DEPENDENCY_GRAPH_MISMATCH')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--fixture', default='gameplay_source_multifile')
    parser.add_argument('--saved-arena', type=Path,
                        help='verified native saved-arena builder run directory; arena fixture only')
    args = parser.parse_args()
    if not re.fullmatch(r'o2-publication-[a-z0-9-]{1,48}', args.run_id):
        parser.error('use a fresh o2-publication-<id>')
    if args.saved_arena is not None and args.fixture != ARENA_FIXTURE:
        parser.error('--saved-arena requires --fixture gameplay_arena_physics')
    idle_window()
    output = STUDIO / '.local/reviews' / args.run_id
    output.mkdir(exist_ok=False)
    owner_mod = load('o2_native_gameplay_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    probe = load('o2_native_linux_probe', STUDIO / 'tests/godot/run_linux_probe.py')
    fixtures = load('o2_native_gameplay_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    if not publication_fixture_allowed(args.fixture, fixtures.FIXTURES):
        parser.error('fixture must be a gameplay_source_* case or gameplay_arena_physics')
    files, closure = owner_mod.runtime_source_closure()
    for name in ('tests/godot/run_gameplay_publication_probe.py',
                 'tests/godot/run_linux_probe.py', 'tests/godot/linux_probe_fixtures.py',
                 'godot-addon/gameplay_dependency_observation.py'):
        files[name] = probe.sha(STUDIO / name)
    if args.fixture == ARENA_FIXTURE:
        for name in ARENA_SOURCE_FILES.values():
            files[name] = probe.sha(STUDIO / name)
    builder = None
    saved_arena_binding = None
    saved_arena_raw = None
    if args.saved_arena is not None:
        builder_name = 'tests/godot/run_saved_arena_builder.py'
        files[builder_name] = probe.sha(STUDIO / builder_name)
        builder = load('o2_publication_saved_arena_builder', STUDIO / builder_name)
        saved_arena_raw, saved_arena_binding = freeze_saved_arena(
            args.fixture, args.saved_arena, output / 'saved-arena', builder)
    binding = {'run_id': args.run_id, 'source_closure_sha256': closure,
               'files': files, 'authority': 0, 'public_ack': False,
               'scope': 'Declared adapter closure plus diagnostic harness; not arbitrary dependencies.'}
    if saved_arena_binding is not None:
        binding['saved_arena'] = saved_arena_binding
    save(output / 'binding.json', binding)
    for name, digest in files.items():
        raw = (STUDIO / name).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == digest, 'SOURCE_CHANGED_BEFORE_FREEZE')
        copy = output / 'source' / name
        copy.parent.mkdir(parents=True, exist_ok=True)
        with copy.open('xb') as stream:
            stream.write(raw)
    os.environ.setdefault('HH_STUDIO_LINUX_GODOT', str(STUDIO /
        '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64'))
    profile = owner_mod._load('gameplay_source_profile')
    fixture_name = args.fixture
    case = {**fixtures.FIXTURES[fixture_name],
            'scene': fixtures.SCENE, 'project': profile.PROJECT_TEMPLATE}
    if saved_arena_raw is not None:
        case = saved_arena_case(fixture_name, case, saved_arena_raw)
    candidate = probe.case_files(case)
    candidate.pop('project.godot')
    dependency_policy = publication_dependency_policy(fixture_name, case,
                                                     saved_arena=saved_arena_binding is not None)
    verify_fixture_sources(fixture_name, case, candidate, files,
                           source_root=STUDIO, frozen_root=output / 'source')
    if saved_arena_binding is not None:
        verify_saved_arena_binding(args.saved_arena, output / 'saved-arena',
                                  saved_arena_binding, builder, candidate)
    initial = dict(candidate)
    initial[owner_mod.ENTRYPOINT] += b'\n# Initial unpublished fixture revision.\n'
    calls = []
    owner = reopened = None
    result = {'run_id': args.run_id, 'authority': 0, 'public_ack': False,
              'sandbox_acceptance': False, 'source_closure_sha256': closure,
              'status': 'INCOMPLETE'}
    try:
        def run_native(project, **kwargs):
            idle_window()
            need(not calls, 'UNEXPECTED_SECOND_NATIVE_DISPATCH')
            verify_fixture_sources(fixture_name, case, candidate, files,
                                   source_root=STUDIO, frozen_root=output / 'source')
            need(all(probe.sha(STUDIO / name) == digest for name, digest in files.items()),
                 'SOURCE_CHANGED_BEFORE_DISPATCH')
            if saved_arena_binding is not None:
                verify_saved_arena_binding(args.saved_arena, output / 'saved-arena',
                                          saved_arena_binding, builder, candidate)
            calls.append(str(kwargs['output'].relative_to(output)))
            return owner_mod._load('linux_executor').run(project, **kwargs)

        owner = owner_mod.GameplaySourcePublicationOwner.create(output,
            project_id='project.publication', source_files=initial,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=closure, runner=run_native,
            **dependency_policy)
        initial_readback = owner.inspect()
        credential = owner.issue()
        grant = owner.authorize('Bearer ' + credential.bearer, 'scene.save')
        lease = owner.lease(grant)
        request = {'command_id': 'command.publication.1',
                   'expected_project_revision': initial_readback['project_revision'],
                   'source_files': candidate, 'entrypoint': owner_mod.ENTRYPOINT}
        request['digest'] = owner_mod.request_digest(project_id=owner.project_id, **request)
        ack = owner.publish(request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        selected = owner.inspect()
        need(ack['status'] == 'READBACK_ACK' and ack['public_ack'] is False
             and selected['generation'] == initial_readback['generation'] + 1,
             'PUBLICATION_POSTCONDITION')
        selected_bytes = (owner._root / 'CURRENT').read_bytes()
        journal_bytes = (owner._root / 'journal.jsonl').read_bytes()
        need(ack == owner.publish(request, grant=grant, lease=lease,
                                  deadline_ms=lease.expires_ms), 'LIVE_RETRY_CHANGED')
        need((owner._root / 'CURRENT').read_bytes() == selected_bytes
             and (owner._root / 'journal.jsonl').read_bytes() == journal_bytes,
             'LIVE_RETRY_MUTATED_STATE')
        native_dir = owner._root / 'runs' / request['command_id']
        observation = probe.case_observation(native_dir, case,
            name=fixture_name, binding=binding)
        save(output / 'native-observation.json', observation)
        verify_fixture_observation(fixture_name, observation,
                                   saved_arena=saved_arena_binding is not None)
        root = owner._root
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(root,
            project_id='project.publication', source_closure_sha256=closure, runner=run_native,
            **dependency_policy)
        need(reopened.inspect() == selected, 'REOPEN_READBACK_CHANGED')
        fresh = reopened.issue()
        grant = reopened.authorize('Bearer ' + fresh.bearer, 'scene.save')
        lease = reopened.lease(grant)
        need(reopened.publish(request, grant=grant, lease=lease,
                              deadline_ms=lease.expires_ms) == ack, 'RECOVERED_RETRY_CHANGED')
        need(len(calls) == 1, 'NATIVE_DISPATCH_COUNT')
        need((root / 'CURRENT').read_bytes() == selected_bytes
             and (root / 'journal.jsonl').read_bytes() == journal_bytes, 'RETRY_MUTATED_STATE')
        need(all(probe.sha(STUDIO / name) == digest for name, digest in files.items()),
             'SOURCE_CHANGED_DURING_PROBE')
        if saved_arena_binding is not None:
            verify_saved_arena_binding(args.saved_arena, output / 'saved-arena',
                                      saved_arena_binding, builder, candidate)
        result.update(status='DIAGNOSTIC_PASS', initial=initial_readback,
            selected=selected, receipt=ack, native_run_count=len(calls), native_paths=calls,
            live_retry_equal=True, reopened_retry_equal=True, durable_state_unchanged=True,
            source_unchanged=True, native_fixture_observed=True)
        if saved_arena_binding is not None:
            result.update(saved_arena_scene_sha256=saved_arena_binding['scene_sha256'],
                          saved_arena_provenance_unchanged=True,
                          saved_arena_instantiation_observed=True,
                          saved_arena_scope='Player/Floor/Wall and shapes; other fixture actors remain runtime')
    except Exception as error:
        # Native raw remains at its original location; never log credentials or
        # arbitrary exception text. The class and phase evidence locate failure.
        result.update(status='DIAGNOSTIC_FAIL', error_class=type(error).__name__,
                      native_paths=calls, native_run_count=len(calls))
        code = str(error)
        if re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            result['error_code'] = code
    finally:
        for item in (reopened, owner):
            if item is not None:
                item.close()
    save(output / 'result.json', result)
    print(json.dumps({'run_id': args.run_id, 'status': result['status'],
                      'native_run_count': len(calls), 'authority': 0}), flush=True)
    return 0 if result['status'] == 'DIAGNOSTIC_PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
