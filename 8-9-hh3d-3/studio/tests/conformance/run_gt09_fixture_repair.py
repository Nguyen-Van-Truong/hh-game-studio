"""K9 on the actual K8 publications: observe Play, catalog repair, reopen/replay.

The committed recipe is the authored batch template. The host fills its lease,
revision and full source payload only after reading the seeded native result.
Verification reconstructs every input and observation from retained raw files.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.conformance import run_gt09_registered_script as route_runner
from studio.tests.godot.run_delegated_playtest import _publication_project

OWNER = route_runner._OWNER
REGISTERED = route_runner._REGISTERED
ADAPTER = route_runner._ADAPTER
PROBE = route_runner._PROBE
RECIPE = Path(__file__).with_name('gt09_repair_recipe.json')
SCHEMA = 'hh-gt09-fixture-repair-1'


def need(value, code):
    if not value:
        raise ValueError(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def inputs(publication, fixture):
    project, provenance = _publication_project(publication, fixture)
    need(provenance['selected_matches_executed_snapshot'], 'K9_PUBLICATION_SELECTOR')
    files = {name: (project / name).read_bytes()
             for name in provenance['executed_snapshot_files'] if name != 'project.godot'}
    expected = read(publication / 'native-observation.json')['untrusted_child_observation']
    return files, expected, provenance


def case_for(files, fixture, expected):
    return {'mode': 'gameplay-source', 'timeout': 30, 'authenticated_timeout': True,
            'expect': 'fixture_state', 'fixture_kind': 'k9_' + fixture,
            'project': OWNER._load('gameplay_source_profile').PROJECT_TEMPLATE,
            'scene': files['scenes/fixture.tscn'].decode(),
            'script': files['scripts/fixture_actor.gd'].decode(),
            'extra_files': {name: raw.decode() for name, raw in files.items()
                            if name not in ('scenes/fixture.tscn', 'scripts/fixture_actor.gd')
                            and name.endswith(('.gd', '.tscn'))},
            'extra_binary_files': {name: raw for name, raw in files.items()
                                   if not name.endswith(('.gd', '.tscn'))},
            'expected_state': expected}


def changed(files, recipe, *, seed):
    values = dict(files)
    old, new = (recipe['good'], recipe['seeded']) if seed else (recipe['seeded'], recipe['good'])
    raw = values[recipe['target']]
    need(raw.count(old.encode()) == 1, 'K9_REPAIR_PRECONDITION')
    values[recipe['target']] = raw.replace(old.encode(), new.encode(), 1)
    return values


def observe(root, case, fixture, closure, *, seeded=False, play_exit=0):
    """Bind real input hashes, confinement, attributed phases and gameplay state."""
    result = read(root / 'result.json')
    need(result.get('source_closure_sha256') == closure, 'K9_NATIVE_CLOSURE')
    observation = PROBE.case_observation(root, case, name='k9_' + fixture,
        binding={'run_id': root.name, 'source_closure_sha256': closure,
                 'files': OWNER.runtime_source_closure()[0]})
    need(observation['confinement_lifecycle_observed'], 'K9_NATIVE_CONFINEMENT')
    executor = OWNER._load('linux_executor')
    attributed = executor.read_attribution(root, result)
    phases = attributed['phase_results']
    need(phases and phases[-1]['phase'] == 'play' and
         phases[-1]['returncode'] == play_exit and
         all(row['returncode'] == 0 for row in phases[:-1]), 'K9_PLAY_PHASE_EXIT')
    need(result['command_host']['exit_code'] == (45 if play_exit else 0)
         and result['command_host']['timed_out'] is False, 'K9_ACTUAL_EXIT')
    stdout = attributed['child_stdout'].decode()
    stderr = attributed['child_stderr'].decode()
    state = PROBE.marker(stdout, 'HH_PROBE_FIXTURE ')
    need(PROBE.typed_equal(state, case['expected_state']), 'K9_PLAY_STATE')
    # A known gameplay assertion exit is not a syntax/runtime/log failure.
    # Pin the stderr policy from the successful base run, apart from the exit.
    scripts = ['scripts/fixture_actor.gd'] + sorted(
        name for name in files_from_case(case) if name.startswith('scripts/')
        and name.endswith('.gd') and name != 'scripts/fixture_actor.gd')
    if not seeded or play_exit == 0:
        need(observation['fixture_observed'], 'K9_NATIVE_OBSERVATION')
    else:
        need(not re.search(r'ERROR|WARNING|leaked', stdout, re.I), 'K9_PLAY_LOG')
        need(stderr.replace('\r\n', '\n') == PROBE.GUARDED_STARTUP_ERROR * (len(scripts) + 4),
             'K9_SEEDED_LOG_POLICY')
    need(state.get('checkpoint_reload_observed') is True, 'K9_CHECKPOINT_READBACK')
    return {'state': state, 'actual_exit': result['command_host']['exit_code'],
            'play_exit': play_exit, 'observation': observation,
            'result_sha256': sha(root / 'result.json'),
            'stdout_sha256': sha(root / 'engine-stdout.txt'),
            'stderr_sha256': sha(root / 'engine-stderr.txt')}


def files_from_case(case):
    return {name: raw for name, raw in PROBE.case_files(case).items() if name != 'project.godot'}


def execute_native(files, case, root, closure):
    # Diagnostic resume may reuse a completed native step only after observe()
    # reconstructs all input hashes and raw receipts. Incomplete steps fail.
    if root.exists():
        need((root / 'result.json').is_file(), 'K9_INCOMPLETE_NATIVE_STEP')
        return
    project = root.with_name(root.name + '-project')
    project.mkdir(parents=True)
    for name, raw in {'project.godot': case['project'].encode(), **files}.items():
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    OWNER._load('linux_executor').run(project, mode='gameplay-source', output=root,
        timeout_seconds=30, authenticated=True, source_closure_sha256=closure)


def fixture_run(publication, fixture, output, closure):
    if (output / 'result.json').is_file():
        return read(output / 'result.json')  # top-level verify revalidates raw
    recipe = read(RECIPE)['fixtures'][fixture]
    files, expected, provenance = inputs(publication, fixture)
    seeded_files = changed(files, recipe, seed=True)
    seed_case = case_for(seeded_files, fixture, {**expected, **recipe['symptom']})
    execute_native(seeded_files, seed_case, output / 'seed', closure)
    seed = observe(output / 'seed', seed_case, fixture, closure,
                   seeded=True, play_exit=recipe['play_exit'])
    # Author diagnosis is committed; bind this execution to the observed raw.
    repaired_files = changed(seeded_files, recipe, seed=False)
    need(repaired_files == files, 'K9_REPAIR_SCOPE')
    # Match K8's proven shallow layout. On this Docker Desktop host, individual
    # file binds at two extra directory levels return EIO even with short paths;
    # a long single-level path reads correctly (k9-bind-71 diagnostic).
    parent = output
    longest = parent / ('gameplay-owner-' + 'f' * 32) / 'runs' / recipe['command_id'] / 'snapshot/assets/sprite_sheet.png'
    need(len(str(longest)) < 248, 'K9_WINDOWS_BIND_PATH_TOO_LONG')
    parent.mkdir(exist_ok=True)
    project_id = 'project.registered.' + fixture
    retained = list(parent.glob('gameplay-owner-*'))
    if retained:
        need(len(retained) == 1 and retained[0].is_dir(), 'K9_RESUME_OWNER_AMBIGUOUS')
        owner = OWNER.GameplaySourcePublicationOwner.reopen(retained[0],
            project_id=project_id, source_closure_sha256=closure)
    else:
        owner = OWNER.GameplaySourcePublicationOwner.create(parent,
            project_id=project_id, source_files=seeded_files,
            entrypoint=OWNER.ENTRYPOINT, source_closure_sha256=closure,
            dependency_observation_required=True,
            dependency_observation_files=tuple(sorted(seeded_files)))
    registered_owner = None
    try:
        grant = owner.authorize('Bearer ' + owner.issue().bearer, 'scene.save')
        lease = owner.lease(grant)
        profile = REGISTERED.load_fixture_host_profile(project_id)
        before = owner.inspect()
        admission = REGISTERED.make_admission(project_id=project_id,
            revision='sha256:' + 'a' * 64, project_revision=before['project_revision'],
            lease_id=lease.lease_id, fencing_epoch=lease.fencing_epoch)
        handoff = REGISTERED.BlenderHandoff('registered://k9', '0' * 64,
            '0' * 64, 'DIAGNOSTIC', recipe['command_id'])
        registered_owner = REGISTERED.RegisteredAuthoringOwner(admission=admission,
            blender=handoff, native_apply=lambda *_: (_ for _ in ()).throw(ValueError('K9_SCENE_ROUTE')))
        route = REGISTERED.RegisteredScriptRoute(registered_owner,
            adapter=ADAPTER.GameplaySourceAdapter(owner, host_profile=profile),
            grant=grant, lease=lease, host_profile=profile)
        command_path = output / 'repair-command.json'
        prior = read(command_path) if command_path.exists() else None
        expected_revision = prior['expected_revision'] if prior else before['project_revision']
        request = route_runner._request(command_id=recipe['command_id'],
            expected=expected_revision, profile=profile, source=repaired_files, lease=lease)
        request['project_id'] = project_id
        # Contains no bearer token. This is the exact command dispatched after
        # observe, including bounded lease metadata and source payload hash.
        write(output / 'repair-command.json', request)
        receipt = route.execute(request)
        need(route.execute(request) == receipt, 'K9_RETRY_DIFFERENT')
        selected = owner.inspect()
        root = owner._root
        command_root = root / 'runs' / recipe['command_id']
        good_case = case_for(files, fixture, expected)
        applied = observe(command_root, good_case, fixture, closure)
        owner.close()
        owner = OWNER.GameplaySourcePublicationOwner.reopen(root,
            project_id=project_id, source_closure_sha256=closure)
        reopened = owner.inspect()
        need(reopened == selected, 'K9_REOPEN_REVISION')
        persisted_files = owner._read_revision(reopened['project_revision'])
        need(persisted_files == files, 'K9_REOPEN_SOURCE')
        execute_native(persisted_files, good_case, output / 'replay', closure)
        replay = observe(output / 'replay', good_case, fixture, closure)
        need(applied['state'] == replay['state'], 'K9_REPLAY_MISMATCH')
        result = {'fixture': fixture, 'publication': str(publication.resolve()),
            'publication_sha256': sha(publication / 'result.json'),
            'publication_provenance': provenance, 'seed': seed, 'applied': applied,
            'repair_route': receipt, 'command_sha256': sha(output / 'repair-command.json'),
            'applied_root': str(command_root), 'replay': replay,
            'selected': selected, 'reopened': reopened,
            'recipe_sha256': sha(RECIPE), 'source_closure_sha256': closure}
        write(output / 'result.json', result)
        return result
    finally:
        owner.close()
        if registered_owner is not None:
            registered_owner.close()


def verify(root):
    doc = read(root / 'result.json')
    need(doc['schema'] == SCHEMA and doc['authority'] == 0 and
         doc['acceptance'] is False and doc['status'] == 'DIAGNOSTIC_PASS', 'K9_RESULT')
    need(set(doc['fixtures']) == {'arena', 'room'}, 'K9_BOTH_FIXTURES_REQUIRED')
    need(doc['recipe_sha256'] == sha(RECIPE), 'K9_RECIPE_CHANGED')
    closure = doc['source_closure_sha256']
    for fixture, value in doc['fixtures'].items():
        need(value.get('source_closure_sha256') == closure, 'K9_FIXTURE_CLOSURE')
        folder = root.with_name(root.name + '-' + fixture)
        need(read(folder / 'result.json') == value, 'K9_FIXTURE_RESULT')
        publication = Path(value['publication'])
        need(value['publication_sha256'] == sha(publication / 'result.json'), 'K9_PUBLICATION_HASH')
        files, expected, provenance = inputs(publication, fixture)
        need(provenance == value['publication_provenance'], 'K9_PUBLICATION_CHANGED')
        recipe = read(RECIPE)['fixtures'][fixture]
        bad = changed(files, recipe, seed=True)
        cases = [('seed', case_for(bad, fixture, {**expected, **recipe['symptom']}),
                  folder / 'seed', True, recipe['play_exit']),
                 ('applied', case_for(files, fixture, expected), Path(value['applied_root']), False, 0),
                 ('replay', case_for(files, fixture, expected), folder / 'replay', False, 0)]
        for label, case, native, seeded, code in cases:
            need(native.resolve().is_relative_to(folder.resolve()), 'K9_NATIVE_PATH')
            need(observe(native, case, fixture, closure, seeded=seeded, play_exit=code)
                 == value[label], 'K9_RAW_OBSERVATION')
        command_path = folder / 'repair-command.json'
        need(value['command_sha256'] == sha(command_path), 'K9_COMMAND_HASH')
        command = read(command_path)
        from studio.protocol.core import Request, canonical_bytes
        Request.from_dict(command)  # schema, bounded encoding and payload hash
        decoded = {name: b''.join(base64.b64decode(chunk, validate=True)
                    for chunk in (encoded if isinstance(encoded, list) else [encoded]))
                   for name, encoded in command['payload']['source_files'].items()}
        need(decoded == files, 'K9_COMMAND_SOURCE')
        need(command['command_id'] == recipe['command_id'] and
             command['operation'] == recipe['operation'] and
             command['project_id'] == 'project.registered.' + fixture, 'K9_COMMAND_BINDING')
        need(value['selected'] == value['reopened'] and value['applied']['state'] == value['replay']['state'],
             'K9_REPLAY_CHECKPOINT')
        receipt = value['repair_route']
        need(receipt['command_id'] == command['command_id'] and receipt['receipt']['readback_ack'] is True,
             'K9_CATALOG_READBACK')
        need(receipt['receipt']['request_digest'] == OWNER.request_digest(
            project_id=command['project_id'], command_id=command['command_id'],
            entrypoint=OWNER.ENTRYPOINT, expected_project_revision=command['expected_revision'],
            source_files=decoded), 'K9_COMMAND_RECEIPT_DIGEST')
        # Verification is read-only: no owner/session construction, lease,
        # credential, selector reconciliation or engine launch is permitted.
        owner_root = Path(value['applied_root']).parent.parent
        journal = [json.loads(line) for line in (owner_root / 'journal.jsonl').read_text().splitlines()]
        need(len(journal) == 2 and journal[0]['kind'] == 'INITIAL'
             and journal[1]['kind'] == 'COMMITTED', 'K9_DURABLE_JOURNAL')
        committed = journal[1]
        need(all(committed.get(key) == val for key, val in receipt['receipt'].items()
                 if key != 'status') and committed['source_closure_sha256'] == closure
             and committed['project_id'] == command['project_id'], 'K9_DURABLE_RECEIPT')
        selected = value['reopened']
        need(read(owner_root / 'CURRENT') == {'schema': 'hh-gameplay-selector-1',
             'generation': selected['generation'], 'revision': selected['project_revision']},
             'K9_DURABLE_SELECTOR')
        project = owner_root / 'revisions' / selected['project_revision'].removeprefix('sha256:') / 'project'
        need({name: sha(project / name) for name in files} == selected['files']
             == {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()},
             'K9_DURABLE_SOURCE')
        need(hashlib.sha256(canonical_bytes(selected)).hexdigest() == receipt['receipt']['readback_sha256'],
             'K9_DURABLE_READBACK')
    return doc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arena', type=Path)
    parser.add_argument('--room', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--verify-only', action='store_true')
    parser.add_argument('--resume-diagnostic', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify_only:
            verify(args.output.resolve())
        elif args.dry_run:
            for fixture in ('arena', 'room'):
                files, _, _ = inputs(getattr(args, fixture), fixture)
                changed(files, read(RECIPE)['fixtures'][fixture], seed=True)
        else:
            need(not args.output.exists() or args.resume_diagnostic, 'K9_OUTPUT_EXISTS')
            need(args.resume_diagnostic or all(not args.output.with_name(
                 args.output.name + '-' + fixture).exists() for fixture in ('arena', 'room')),
                 'K9_FIXTURE_OUTPUT_EXISTS')
            args.output.mkdir(parents=True, exist_ok=args.resume_diagnostic)
            closure = OWNER.runtime_source_closure()[1]
            fixtures = {fixture: fixture_run(getattr(args, fixture).resolve(), fixture,
                         args.output.resolve().with_name(args.output.name + '-' + fixture), closure)
                        for fixture in ('arena', 'room')}
            write(args.output / 'result.json', {'schema': SCHEMA, 'run_id': args.run_id,
                'authority': 0, 'public_ack': False, 'acceptance': False, 'status': 'DIAGNOSTIC_PASS',
                'source_closure_sha256': closure, 'recipe_sha256': sha(RECIPE), 'fixtures': fixtures})
            verify(args.output.resolve())
        print(json.dumps({'status': 'DIAGNOSTIC_PASS', 'authority': 0, 'run_id': args.run_id}))
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'DIAGNOSTIC_FAIL', 'authority': 0, 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
