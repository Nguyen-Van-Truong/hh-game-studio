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
import stat
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
BLENDER_HANDOFF_ROOT = STUDIO / '.local' / 'reviews'
BLENDER_GLTF_NAME = 'scene.glb'


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
            'expected_state': {**case['expected_state'], 'saved_world_instantiated': True,
                'saved_actors_resolved': True, 'saved_hud_resolved': True,
                'saved_world_path': 'res://scenes/arena.tscn',
                'saved_actor_paths': {'pickup': 'Pickup', 'bot': 'Bot', 'camera': 'Camera'}},
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


def _handoff_path(root, name):
    """Check lexical paths before resolving; reject Windows junctions too."""
    need(isinstance(root, Path) and root.is_absolute() and root.is_dir(),
         'BLENDER_HANDOFF_ROOT')
    need(type(name) is str and name and '/' not in name and '\\' not in name and ':' not in name
         and name not in ('.', '..'), 'BLENDER_HANDOFF_PATH')
    path = root / name
    for part in (path, *path.parents):
        info = part.lstat()
        need(not stat.S_ISLNK(info.st_mode)
             and not getattr(info, 'st_file_attributes', 0) & 0x400,
             'BLENDER_HANDOFF_PATH')
    info = path.stat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'BLENDER_HANDOFF_PATH')
    return path


def _handoff_bytes(root, name, limit):
    path = _handoff_path(root, name)
    need(0 < path.stat().st_size <= limit, 'BLENDER_HANDOFF_SIZE')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    need(0 < len(raw) <= limit, 'BLENDER_HANDOFF_SIZE')
    return raw


def read_blender_handoff(directory):
    """Read the actual protected publication, with its captured producer exits.

    No source in the evidence directory is executed. Historical producer code
    keeps its original hash; this read-only check grants no current GT07 tick.
    """
    from studio.host.blender.publication_owner import BlenderPublicationOwner
    from studio.host.blender.publication_state import blob, SCHEMA
    directory = Path(directory).absolute()
    trusted_root = BLENDER_HANDOFF_ROOT.absolute()
    producer_root = directory.parent
    need(directory.is_dir() and directory.name == 'published'
         and producer_root.parent == trusted_root
         and re.fullmatch(r'gt07-native-queue-[0-9]{8}-[0-9]{2}', producer_root.name),
         'BLENDER_HANDOFF_ROOT')
    manifest_raw = _handoff_bytes(directory, 'manifest.json', 1_048_576)
    manifest = json.loads(manifest_raw)
    need(type(manifest) is dict and manifest.get('schema') == SCHEMA
         and manifest.get('publication_profile') == 'export.publish'
         and type(manifest.get('artifacts')) is dict
         and set(manifest['artifacts']) == {'scene.glb', 'checkpoint.blend'},
         'BLENDER_HANDOFF_MANIFEST')
    artifact = blob(manifest['artifacts'][BLENDER_GLTF_NAME])
    raw = _handoff_bytes(directory, BLENDER_GLTF_NAME, 32 * 1024 * 1024)
    need(len(raw) == artifact.identity.size and hashlib.sha256(raw).hexdigest() == artifact.sha256,
         'BLENDER_HANDOFF_HASH')
    receipts = {name: _handoff_bytes(producer_root, name, 1_048_576)
                for name in ('queue-native.json', 'native-child.json', 'native-host.json')}
    wrapper, child, host = (json.loads(receipts[name]) for name in receipts)
    need(type(wrapper) is dict and type(child) is dict and type(host) is dict,
         'BLENDER_HANDOFF_RECEIPT')
    captured = wrapper.get('host', {})
    publication = child.get('publication', {})
    need(wrapper.get('child') == child and wrapper.get('run_id') == producer_root.name
         and child.get('run_id') == producer_root.name and wrapper.get('passed') is True
         and child.get('passed') is True and child.get('operation') == 'export.publish'
         and child.get('queue_state') == 'COMMITTED' and not child.get('errors')
         and wrapper.get('source_unchanged') is True and wrapper.get('snapshot_unchanged') is True
         and type(host.get('exit_code')) is int and host['exit_code'] == 0
         and type(host.get('target_pid')) is int and host['target_pid'] > 0
         and captured.get('target_pid') == host['target_pid']
         and captured.get('exit_code') == 0 and captured.get('wrapper_exit_code') == 0
         and captured.get('tree_verified') is True and captured.get('timed_out') is False
         and publication.get('manifest_sha256') == hashlib.sha256(manifest_raw).hexdigest(),
         'BLENDER_HANDOFF_RECEIPT')
    owner = BlenderPublicationOwner.reopen(publication['storage_id'])
    try:
        selected, artifacts = owner.read_selected()
        need(owner.files.root.parent == producer_root
             and selected == manifest and artifacts.get(BLENDER_GLTF_NAME) == raw,
             'BLENDER_HANDOFF_PROTECTED_READBACK')
    finally:
        owner.close()
    binding = {
        'schema': 'hh-blender-godot-handoff-1',
        'producer_run_id': producer_root.name,
        'storage_id': publication['storage_id'],
        'producer_receipts': {name: hashlib.sha256(value).hexdigest()
                              for name, value in receipts.items()},
        'manifest_sha256': hashlib.sha256(manifest_raw).hexdigest(),
        'artifact': {'path': BLENDER_GLTF_NAME, 'sha256': artifact.sha256,
                     'bytes': artifact.identity.size},
        'authority': 0, 'public_ack': False,
    }
    return raw, manifest_raw, binding


def freeze_blender_handoff(directory, frozen_root):
    raw, manifest_raw, binding = read_blender_handoff(directory)
    frozen_root.mkdir(exist_ok=False)
    for name, data in ((BLENDER_GLTF_NAME, raw), ('manifest.json', manifest_raw)):
        with (frozen_root / name).open('xb') as stream:
            stream.write(data)
    save(frozen_root / 'binding.json', binding)
    return raw, binding


def verify_blender_handoff(directory, frozen_root, binding, candidate):
    """Recheck producer bytes and the exact candidate input before each dispatch."""
    raw, manifest_raw, current = read_blender_handoff(directory)
    need(current == binding, 'BLENDER_HANDOFF_CHANGED')
    need(_handoff_bytes(frozen_root, BLENDER_GLTF_NAME, 32 * 1024 * 1024) == raw
         and _handoff_bytes(frozen_root, 'manifest.json', 1_048_576) == manifest_raw
         and json.loads(_handoff_bytes(frozen_root, 'binding.json', 16_384)) == binding
         and candidate.get('assets/avatar.glb') == raw,
         'BLENDER_HANDOFF_CANDIDATE_CHANGED')
    return raw


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


def _probe_sources(owner_mod, args):
    files, closure = owner_mod.runtime_source_closure()
    names = ['tests/godot/run_gameplay_publication_probe.py',
             'tests/godot/run_linux_probe.py', 'tests/godot/linux_probe_fixtures.py',
             'godot-addon/gameplay_dependency_observation.py',
             'tests/jobs/run_gt07_scenarios.py', 'tests/replay/measure_window.py',
             'tests/replay/benchmark_job.py', 'host/core/gt07_failpoints.py']
    if args.fixture == ARENA_FIXTURE:
        names.extend(ARENA_SOURCE_FILES.values())
    if args.saved_arena is not None:
        names.append('tests/godot/run_saved_arena_builder.py')
    if args.blender_published is not None:
        for folder in ('host/blender', 'host/core', 'blender-addon'):
            names.extend(path.relative_to(STUDIO).as_posix()
                         for path in (STUDIO / folder).rglob('*.py'))
    for name in names:
        files[name] = hashlib.sha256((STUDIO / name).read_bytes()).hexdigest()
    return files, closure


def _publication_case(args, owner_mod, fixtures, *, saved_arena_raw=None, glb=None):
    need(publication_fixture_allowed(args.fixture, fixtures.FIXTURES), 'PUBLICATION_FIXTURE_REQUIRED')
    case = {**fixtures.FIXTURES[args.fixture], 'scene': fixtures.SCENE,
            'project': owner_mod._load('gameplay_source_profile').PROJECT_TEMPLATE}
    if saved_arena_raw is not None:
        case = saved_arena_case(args.fixture, case, saved_arena_raw)
    if glb is not None:
        case = {**case, 'extra_binary_files': {**case.get('extra_binary_files', {}),
                                             'assets/avatar.glb': glb}}
    return case


def dry_run(args):
    """Validate the actual bytes, profile, pin and source without starting Docker."""
    idle_window()
    from studio.tests.replay.measure_window import plain
    output = STUDIO / '.local/reviews' / args.run_id
    plain(output)
    need(not output.exists(), 'PUBLICATION_RUN_ID_USED')
    owner_mod = load('o2_admission_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    fixtures = load('o2_admission_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    probe = load('o2_admission_probe', STUDIO / 'tests/godot/run_linux_probe.py')
    files, closure = _probe_sources(owner_mod, args)
    saved_raw = glb = handoff = None
    if args.saved_arena is not None:
        builder = load('o2_admission_builder', STUDIO / 'tests/godot/run_saved_arena_builder.py')
        saved_raw = builder.verify_saved_arena(args.saved_arena)
    if args.blender_published is not None:
        glb, _, handoff = read_blender_handoff(args.blender_published)
    case = _publication_case(args, owner_mod, fixtures, saved_arena_raw=saved_raw, glb=glb)
    candidate = probe.case_files(case)
    candidate.pop('project.godot')
    owner_mod._copy_source_bundle(owner_mod._load('gameplay_source_profile'), candidate,
                                 entrypoint=owner_mod.ENTRYPOINT)
    publication_dependency_policy(args.fixture, case, saved_arena=saved_raw is not None)
    executor = owner_mod._load('linux_executor')
    executor._lock()
    binary = executor._binary()
    executor._supervised_command(case['mode'], case['timeout'])
    return {'dry_run': True, 'engine_started': False, 'run_id': args.run_id,
            'fixture': args.fixture, 'source_closure_sha256': closure,
            'files': files, 'binary': str(binary), 'binary_sha256': executor.BINARY_SHA256,
            'candidate_sha256': {name: hashlib.sha256(raw).hexdigest() for name, raw in candidate.items()},
            'blender_handoff': handoff}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--fixture', default='gameplay_source_multifile')
    parser.add_argument('--saved-arena', type=Path,
                        help='verified native saved-arena builder run directory; arena fixture only')
    parser.add_argument('--blender-published', type=Path,
                        help='completed native Blender export/published directory; assets fixture only')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'o2-publication-[a-z0-9-]{1,48}', args.run_id):
        parser.error('use a fresh o2-publication-<id>')
    if args.saved_arena is not None and args.fixture != ARENA_FIXTURE:
        parser.error('--saved-arena requires --fixture gameplay_arena_physics')
    if args.blender_published is not None and args.fixture != 'gameplay_source_assets':
        parser.error('--blender-published requires --fixture gameplay_source_assets')
    if args.saved_arena is not None and args.blender_published is not None:
        parser.error('--saved-arena and --blender-published are mutually exclusive')
    admission = dry_run(args)
    if args.dry_run:
        print(json.dumps(admission, sort_keys=True))
        return 0
    # The Linux executor rejects a formal marker. Hold the same kernel guard
    # as GT07 without creating that marker; all native dispatches stay serialized.
    from studio.tests.jobs.run_gt07_scenarios import _native_measure_guard
    with _native_measure_guard():
        need(dry_run(args) == admission, 'PUBLICATION_ADMISSION_CHANGED')
        return _execute(args, admission)


def _execute(args, admission):
    output = STUDIO / '.local/reviews' / args.run_id
    output.mkdir(exist_ok=False)
    save(output / 'admission.json', admission)
    owner_mod = load('o2_native_gameplay_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    probe = load('o2_native_linux_probe', STUDIO / 'tests/godot/run_linux_probe.py')
    fixtures = load('o2_native_gameplay_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    files, closure = _probe_sources(owner_mod, args)
    need(files == admission['files'] and closure == admission['source_closure_sha256'],
         'PUBLICATION_ADMISSION_CHANGED')
    builder = None
    saved_arena_binding = None
    saved_arena_raw = None
    blender_handoff_binding = None
    blender_handoff_raw = None
    if args.saved_arena is not None:
        builder_name = 'tests/godot/run_saved_arena_builder.py'
        files[builder_name] = probe.sha(STUDIO / builder_name)
        builder = load('o2_publication_saved_arena_builder', STUDIO / builder_name)
        saved_arena_raw, saved_arena_binding = freeze_saved_arena(
            args.fixture, args.saved_arena, output / 'saved-arena', builder)
    if args.blender_published is not None:
        blender_handoff_raw, blender_handoff_binding = freeze_blender_handoff(
            args.blender_published, output / 'blender-handoff')
        need(blender_handoff_binding == admission['blender_handoff'], 'BLENDER_HANDOFF_CHANGED')
    binding = {'run_id': args.run_id, 'source_closure_sha256': closure,
               'files': files, 'authority': 0, 'public_ack': False,
               'scope': 'Declared adapter closure plus diagnostic harness; not arbitrary dependencies.'}
    if saved_arena_binding is not None:
        binding['saved_arena'] = saved_arena_binding
    if blender_handoff_binding is not None:
        binding['blender_handoff'] = blender_handoff_binding
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
    fixture_name = args.fixture
    case = _publication_case(args, owner_mod, fixtures,
                            saved_arena_raw=saved_arena_raw, glb=blender_handoff_raw)
    candidate = probe.case_files(case)
    candidate.pop('project.godot')
    need({name: hashlib.sha256(raw).hexdigest() for name, raw in candidate.items()}
         == admission['candidate_sha256'], 'PUBLICATION_ADMISSION_CHANGED')
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
            if blender_handoff_binding is not None:
                verify_blender_handoff(args.blender_published,
                                       output / 'blender-handoff',
                                       blender_handoff_binding, candidate)
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
        if blender_handoff_binding is not None:
            verify_blender_handoff(args.blender_published,
                                   output / 'blender-handoff',
                                   blender_handoff_binding, candidate)
        result.update(status='DIAGNOSTIC_PASS', initial=initial_readback,
            selected=selected, receipt=ack, native_run_count=len(calls), native_paths=calls,
            live_retry_equal=True, reopened_retry_equal=True, durable_state_unchanged=True,
            source_unchanged=True, native_fixture_observed=True)
        if saved_arena_binding is not None:
            result.update(saved_arena_scene_sha256=saved_arena_binding['scene_sha256'],
                          saved_arena_provenance_unchanged=True,
                          saved_arena_instantiation_observed=True,
                          saved_arena_scope='Player/Floor/Wall/Pickup/Bot and shapes plus Camera/HUD/Status; input/signals remain runtime')
        if blender_handoff_binding is not None:
            result.update(blender_handoff=blender_handoff_binding,
                          blender_handoff_verified=True,
                          blender_handoff_scope='Blender scene.glb bytes loaded by the Godot gameplay-source fixture; queue/editor reload remains separate')
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
