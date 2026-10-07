"""Bounded native PC gameplay-source adapter diagnostic (AUTHORITY=0).

Two byte-distinct source jobs use the private adapter and the pinned executor
sequentially. A competing source request is rejected while the first runner
callback is active; this is not parallel native or full MCP conformance.
The launcher must capture this Python process's actual exit independently.
New raw evidence is exclusive below studio/.local/reviews; retries never run
an engine. Use --dry-run before native execution outside the formal window.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import threading

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.godot import run_gameplay_publication_probe as publication

FIXTURE = 'gameplay_source_multifile'
FIXTURES = (FIXTURE, publication.ARENA_FIXTURE, 'gameplay_source_room_3d_native')
COMMANDS = ('command.adapter.1', 'command.adapter.2')
CONTENDER_TIMEOUT_SECONDS = 5
_RUN_ID = re.compile(r'o2-adapter-[a-z0-9-]{1,48}\Z')
need, save = publication.need, publication.save


def source_cases(case):
    """Keep the existing runtime oracle and dependency graph for both inputs."""
    need(case.get('mode') == 'gameplay-source'
         and type(case.get('script')) is str, 'ADAPTER_FIXTURE_REQUIRED')
    first = dict(case)
    if 'extra_files' in case:
        first['extra_files'] = dict(case['extra_files'])
    second = {**first, 'script': first['script'] + '\n# Adapter source revision two.\n'}
    return first, second


def native_exit_observation(result):
    """Copy actual executor returns; booleans cannot impersonate exit codes."""
    hosts = [result[key] for key in ('command_host', 'commandhost') if key in result]
    states = [result[key] for key in ('container_state', 'state') if key in result]
    need(hosts and states and all(type(row) is dict for row in hosts + states),
         'ADAPTER_NATIVE_EXIT_MISSING')
    need(all(row == hosts[0] for row in hosts) and all(row == states[0] for row in states),
         'ADAPTER_NATIVE_EXIT_ALIASES')
    need(all(type(row.get('exit_code')) is int and row['exit_code'] == 0
             and row.get('timed_out') is False for row in hosts)
         and all(type(row.get('ExitCode')) is int and row['ExitCode'] == 0
                 and row.get('Running') is False for row in states)
         and type(result.get('docker_wait_exit')) is int and result['docker_wait_exit'] == 0,
         'ADAPTER_NATIVE_EXIT_INVALID')
    return {'command_host_exit': hosts[0]['exit_code'],
            'container_exit': states[0]['ExitCode'],
            'docker_wait_exit': result['docker_wait_exit'],
            'timed_out': hosts[0]['timed_out']}


def busy_contender(effect):
    """Bound the overlapping source request without starting another engine."""
    observed = {}

    def contend():
        try:
            effect()
            observed['status'] = 'UNEXPECTED_ACK'
        except Exception as error:
            observed['error_class'] = type(error).__name__
            code = getattr(error, 'code', None)
            if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
                observed['error_code'] = code

    worker = threading.Thread(target=contend, name='adapter-source-contender', daemon=True)
    worker.start()
    worker.join(CONTENDER_TIMEOUT_SECONDS)
    need(not worker.is_alive(), 'ADAPTER_CONTENDER_TIMEOUT')
    need(observed.get('error_code') == 'GAMEPLAY_OWNER_BUSY', 'ADAPTER_CONTENDER_NOT_BUSY')
    return {**observed, 'source_job_overlap_observed': True,
            'native_overlap_observed': False, 'authority': 0,
            'scope': 'First publication runner callback active; contender rejected before native dispatch.'}


def _publication_args(args):
    need(type(args.run_id) is str and _RUN_ID.fullmatch(args.run_id), 'ADAPTER_RUN_ID_INVALID')
    fixture = getattr(args, 'fixture', FIXTURE)
    saved_arena = getattr(args, 'saved_arena', None)
    blender_published = getattr(args, 'blender_published', None)
    need(fixture in FIXTURES, 'ADAPTER_FIXTURE_REQUIRED')
    need(saved_arena is None or fixture == publication.ARENA_FIXTURE,
         'SAVED_ARENA_FIXTURE_REQUIRED')
    need(blender_published is None or fixture != FIXTURE, 'ADAPTER_ASSET_FIXTURE_REQUIRED')
    return argparse.Namespace(run_id=args.run_id, fixture=fixture,
                              saved_arena=saved_arena, blender_published=blender_published)


def _modules():
    owner = publication.load('o2_adapter_probe_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    adapter = publication.load('o2_adapter_probe_client', STUDIO / 'godot-addon/gameplay_source_adapter.py')
    fixtures = publication.load('o2_adapter_probe_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    probe = publication.load('o2_adapter_probe_linux', STUDIO / 'tests/godot/run_linux_probe.py')
    return owner, adapter, fixtures, probe


def _sources(owner, args):
    files, closure = publication._probe_sources(owner, _publication_args(args))
    for name in ('godot-addon/gameplay_source_adapter.py',
                 'tests/godot/run_gameplay_adapter_probe.py'):
        files[name] = hashlib.sha256((STUDIO / name).read_bytes()).hexdigest()
    return files, closure


def _inputs(owner, fixtures, probe, args):
    options = _publication_args(args)
    saved_raw = glb = None
    if options.saved_arena is not None:
        builder = publication.load('o2_adapter_saved_builder', STUDIO / 'tests/godot/run_saved_arena_builder.py')
        saved_raw = builder.verify_saved_arena(options.saved_arena, require_current_source=False)
    if options.blender_published is not None:
        glb, _, _ = publication.read_blender_handoff(options.blender_published)
    case = publication._publication_case(options, owner, fixtures,
                                         saved_arena_raw=saved_raw, glb=glb)
    cases = source_cases(case)
    candidates = []
    for item in cases:
        candidate = probe.case_files(item)
        candidate.pop('project.godot')
        owner._copy_source_bundle(owner._load('gameplay_source_profile'), candidate,
                                  entrypoint=owner.ENTRYPOINT)
        candidates.append(candidate)
    need(candidates[0] != candidates[1], 'ADAPTER_SOURCE_JOBS_NOT_DISTINCT')
    return cases, tuple(candidates)


def dry_run(args):
    """Reuse publication admission and the executor's default _binary policy."""
    admitted = publication.dry_run(_publication_args(args))
    owner, adapter, fixtures, probe = _modules()
    files, closure = _sources(owner, args)
    _, candidates = _inputs(owner, fixtures, probe, args)
    hashes = [{name: hashlib.sha256(raw).hexdigest() for name, raw in candidate.items()}
              for candidate in candidates]
    need(admitted['source_closure_sha256'] == closure
         and admitted['candidate_sha256'] == hashes[0]
         and all(files.get(name) == digest for name, digest in admitted['files'].items()),
         'ADAPTER_ADMISSION_CHANGED')
    return {**admitted, 'files': files, 'candidate_sha256': hashes,
            'authenticated': getattr(args, 'authenticated', False),
            'client_version': adapter.SUPPORTED_CLIENT_VERSION,
            'commands': list(COMMANDS), 'native_run_limit': 2,
            'authority': 0, 'public_ack': False,
            'full_mcp_conformance': False, 'parallel_native_conformance': False,
            'scope': 'Private PC adapter diagnostic; two sequential native source jobs.'}


def _execute(args, admission):
    output = STUDIO / '.local/reviews' / args.run_id
    output.mkdir(exist_ok=False)
    save(output / 'admission.json', admission)
    owner_mod, adapter_mod, fixtures, probe = _modules()
    files, closure = _sources(owner_mod, args)
    need(files == admission['files'] and closure == admission['source_closure_sha256'],
         'ADAPTER_ADMISSION_CHANGED')
    options = _publication_args(args)
    builder = saved_binding = handoff_binding = None
    if options.saved_arena is not None:
        builder = publication.load('o2_adapter_saved_builder', STUDIO / 'tests/godot/run_saved_arena_builder.py')
        _, saved_binding = publication.freeze_saved_arena(
            options.fixture, options.saved_arena, output / 'saved-arena', builder)
    if options.blender_published is not None:
        _, handoff_binding = publication.freeze_blender_handoff(
            options.blender_published, output / 'blender-handoff')
        need(handoff_binding == admission['blender_handoff'], 'BLENDER_HANDOFF_CHANGED')
    binding = {'run_id': args.run_id, 'files': files, 'source_closure_sha256': closure,
               'authority': 0, 'public_ack': False,
               'scope': 'Declared owner runtime closure plus private adapter and diagnostic harness.'}
    if saved_binding is not None:
        binding['saved_arena'] = saved_binding
    if handoff_binding is not None:
        binding['blender_handoff'] = handoff_binding
    save(output / 'binding.json', binding)
    for name, digest in files.items():
        raw = (STUDIO / name).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == digest, 'ADAPTER_SOURCE_CHANGED_BEFORE_FREEZE')
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(raw)
    cases, candidates = _inputs(owner_mod, fixtures, probe, args)
    need([{name: hashlib.sha256(raw).hexdigest() for name, raw in candidate.items()}
          for candidate in candidates] == admission['candidate_sha256'], 'ADAPTER_ADMISSION_CHANGED')
    initial = dict(candidates[0])
    initial[owner_mod.ENTRYPOINT] += b'\n# Initial unpublished adapter revision.\n'
    calls, exits, observations = [], [], []
    owner = reopened = client = contender = None
    contender_observation = None
    active = threading.Lock()
    result = {'run_id': args.run_id, 'fixture': options.fixture, 'authority': 0, 'public_ack': False,
              'sandbox_acceptance': False, 'full_mcp_conformance': False,
              'parallel_native_conformance': False,
              'source_closure_sha256': closure, 'status': 'INCOMPLETE'}

    def unchanged():
        need(all(probe.sha(STUDIO / name) == digest
                 and probe.sha(output / 'source' / name) == digest
                 for name, digest in files.items()), 'ADAPTER_SOURCE_CHANGED')
        publication.verify_fixture_sources(options.fixture, cases[0], candidates[0], files,
                                           source_root=STUDIO, frozen_root=output / 'source')
        if saved_binding is not None:
            publication.verify_saved_arena_binding(options.saved_arena, output / 'saved-arena',
                                                   saved_binding, builder, candidates[0])
        if handoff_binding is not None:
            publication.verify_blender_handoff(options.blender_published, output / 'blender-handoff',
                                               handoff_binding, candidates[0])

    def publish(target, index, expected, grant, lease):
        return target.publish_source(command_id=COMMANDS[index], source_files=candidates[index],
            expected_project_revision=expected, grant=grant, lease=lease, deadline_ms=lease.expires_ms)

    def durable_state(root):
        return {name: (root / name).read_bytes() for name in ('CURRENT', 'journal.jsonl')}

    def native_inventory(root):
        return {path.relative_to(root).as_posix(): probe.sha(path)
                for path in sorted((root / 'runs').rglob('*')) if path.is_file()}

    try:
        def run_native(project, **kwargs):
            nonlocal contender_observation
            publication.idle_window()
            unchanged()
            need(active.acquire(blocking=False), 'ADAPTER_PARALLEL_NATIVE_FORBIDDEN')
            try:
                index = len(calls)
                need(index < 2 and kwargs['output'].name == COMMANDS[index],
                     'ADAPTER_UNEXPECTED_NATIVE_DISPATCH')
                calls.append(str(kwargs['output'].relative_to(output)))
                if index == 0:
                    contender_observation = busy_contender(
                        lambda: publish(contender, 1, initial_readback['project_revision'], grant, lease))
                    need(len(calls) == 1, 'ADAPTER_CONTENDER_DISPATCHED')
                # Return exactly the native executor result, never fabricated exits.
                observed = owner_mod._load('linux_executor').run(
                    project, **kwargs, authenticated=admission['authenticated'])
                exits.append(native_exit_observation(observed))
                unchanged()
                return observed
            finally:
                active.release()

        policy = publication.publication_dependency_policy(options.fixture, cases[0],
                                                          saved_arena=saved_binding is not None)
        owner = owner_mod.GameplaySourcePublicationOwner.create(output,
            project_id='project.adapter', source_files=initial, entrypoint=owner_mod.ENTRYPOINT,
            source_closure_sha256=closure, runner=run_native, **policy)
        client = adapter_mod.GameplaySourceAdapter(owner)
        contender = adapter_mod.GameplaySourceAdapter(owner)
        need(client.discovery().capabilities == (), 'ADAPTER_PUBLIC_DISCOVERY_FORBIDDEN')
        try:
            adapter_mod.GameplaySourceAdapter(owner, client_version='unsupported-native-probe')
        except adapter_mod.GameplaySourceAdapterError as error:
            need(error.code == 'UNSUPPORTED_CLIENT_VERSION', 'ADAPTER_VERSION_WRONG_REJECTION')
        else:
            raise RuntimeError('ADAPTER_VERSION_ACCEPTED')
        initial_readback = client.inspect()
        credential = owner.issue()
        grant = owner.authorize('Bearer ' + credential.bearer, 'scene.save')
        lease = owner.lease(grant)
        first = publish(client, 0, initial_readback['project_revision'], grant, lease)
        after_first = client.inspect()
        need(first['status'] == 'READBACK_ACK' and first['readback_ack'] is True
             and first['public_ack'] is False and after_first['generation'] == 2,
             'ADAPTER_FIRST_PUBLICATION_FAILED')
        second = publish(contender, 1, after_first['project_revision'], grant, lease)
        selected = contender.inspect()
        need(second['status'] == 'READBACK_ACK' and second['readback_ack'] is True
             and second['public_ack'] is False and selected['generation'] == 3
             and first['project_revision'] != second['project_revision'] and len(calls) == 2,
             'ADAPTER_SECOND_PUBLICATION_FAILED')
        for index, case in enumerate(cases):
            directory = owner._root / 'runs' / COMMANDS[index]
            observation = probe.case_observation(directory, case, name=options.fixture, binding=binding)
            save(output / ('native-observation-' + str(index + 1) + '.json'), observation)
            publication.verify_fixture_observation(options.fixture, observation,
                                                   saved_arena=saved_binding is not None)
            observations.append(observation)
        root = owner._root
        state, raw = durable_state(root), native_inventory(root)
        client.context_reset()
        need(client.lookup(COMMANDS[0], grant=grant, lease=lease,
                           deadline_ms=lease.expires_ms) == first, 'ADAPTER_RESET_LOOKUP_CHANGED')
        client = client.reconnect()
        need(client.lookup(COMMANDS[1], grant=grant, lease=lease,
                           deadline_ms=lease.expires_ms) == second, 'ADAPTER_RECONNECT_LOOKUP_CHANGED')
        need(publish(client, 0, initial_readback['project_revision'], grant, lease) == first,
             'ADAPTER_HISTORICAL_RETRY_CHANGED')
        need(client.inspect() == selected and durable_state(root) == state
             and native_inventory(root) == raw and len(calls) == 2, 'ADAPTER_LIVE_RETRY_MUTATED')
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(root,
            project_id='project.adapter', source_closure_sha256=closure, runner=run_native, **policy)
        client.close()
        client = adapter_mod.GameplaySourceAdapter(reopened)
        credential = reopened.issue()
        grant = reopened.authorize('Bearer ' + credential.bearer, 'scene.save')
        lease = reopened.lease(grant)
        need(client.inspect() == selected, 'ADAPTER_REOPEN_READBACK_CHANGED')
        for index, receipt, expected in ((0, first, initial_readback['project_revision']),
                                         (1, second, after_first['project_revision'])):
            need(client.lookup(COMMANDS[index], grant=grant, lease=lease,
                               deadline_ms=lease.expires_ms) == receipt, 'ADAPTER_REOPEN_LOOKUP_CHANGED')
            need(publish(client, index, expected, grant, lease) == receipt,
                 'ADAPTER_REOPEN_RETRY_CHANGED')
        need(client.inspect() == selected and durable_state(root) == state
             and native_inventory(root) == raw and len(calls) == 2, 'ADAPTER_REOPEN_RETRY_MUTATED')
        # Intentional edit only in this diagnostic owner's selected local source.
        edited = reopened._safe_revision(selected['project_revision']) / 'project' / owner_mod.ENTRYPOINT
        original_bytes = edited.read_bytes()
        need(original_bytes.count(b'Adapter source revision two.') == 1, 'ADAPTER_OWNER_EDIT_TEMPLATE')
        edited_bytes = original_bytes.replace(b'Adapter source revision two.',
                                              b'Edited! source revision two.', 1)
        need(edited_bytes != original_bytes and len(edited_bytes) == len(original_bytes),
             'ADAPTER_OWNER_EDIT_TEMPLATE')
        with edited.open('wb') as stream:
            stream.write(edited_bytes)
        edit_conflicts = []
        for effect in (lambda: client.lookup(COMMANDS[0], grant=grant, lease=lease,
                                            deadline_ms=lease.expires_ms),
                       lambda: publish(client, 0, initial_readback['project_revision'], grant, lease)):
            try:
                effect()
            except adapter_mod.GameplaySourceAdapterError as error:
                need(error.code == 'GAMEPLAY_OWNER_READBACK_HASH', 'ADAPTER_OWNER_EDIT_WRONG_REJECTION')
                edit_conflicts.append(error.code)
            else:
                raise RuntimeError('ADAPTER_OWNER_EDIT_ACCEPTED')
        need(edited.read_bytes() == edited_bytes and durable_state(root) == state
             and native_inventory(root) == raw and len(calls) == 2, 'ADAPTER_OWNER_EDIT_OVERWRITTEN')
        unchanged()
        result.update(status='DIAGNOSTIC_PASS', initial=initial_readback, selected=selected,
            receipts=[first, second], native_exits=exits, contender=contender_observation,
            native_fixture_observed=all(row['fixture_observed'] for row in observations),
            context_reset_lookup_only=True, reconnect_lookup_only=True,
            historical_retry_preserved_current=True, reopened_retry_preserved_current=True,
            durable_state_unchanged=True, native_raw_unchanged=True, source_unchanged=True,
            unsupported_client_rejected=True, public_discovery_empty=client.discovery().capabilities == (),
            owner_edit_preserved=True, owner_edit_sha256=hashlib.sha256(edited_bytes).hexdigest(),
            owner_edit_path=str(edited.relative_to(output)), owner_edit_conflicts=edit_conflicts)
        if saved_binding is not None:
            result.update(saved_arena_scene_sha256=saved_binding['scene_sha256'],
                          saved_arena_provenance_unchanged=True)
        if handoff_binding is not None:
            result.update(blender_handoff=handoff_binding, blender_handoff_verified=True)
    except Exception as error:
        result.update(status='DIAGNOSTIC_FAIL', error_class=type(error).__name__,
                      native_exits=exits, contender=contender_observation)
        code = getattr(error, 'code', str(error))
        if type(code) is str and re.fullmatch(r'[A-Z][A-Z0-9_]{0,95}', code):
            result['error_code'] = code
    finally:
        for item in (client, contender, reopened, owner):
            if item is not None:
                item.close()
    result.update(native_paths=calls, native_run_count=len(calls))
    save(output / 'result.json', result)
    print(json.dumps({'run_id': args.run_id, 'status': result['status'],
                      'native_run_count': len(calls), 'authority': 0}), flush=True)
    return 0 if result['status'] == 'DIAGNOSTIC_PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--fixture', choices=FIXTURES, default=FIXTURE)
    parser.add_argument('--saved-arena', type=Path)
    parser.add_argument('--blender-published', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--authenticated', action='store_true',
                        help='use the private parent-attributed driver; no public capability grant')
    args = parser.parse_args()
    if not _RUN_ID.fullmatch(args.run_id):
        parser.error('use a fresh o2-adapter-<id>')
    admission = dry_run(args)
    if args.dry_run:
        print(json.dumps(admission, sort_keys=True))
        return 0
    from studio.tests.jobs.run_gt07_scenarios import _native_measure_guard
    with _native_measure_guard():
        need(dry_run(args) == admission, 'ADAPTER_ADMISSION_CHANGED')
        return _execute(args, admission)


if __name__ == '__main__':
    raise SystemExit(main())
