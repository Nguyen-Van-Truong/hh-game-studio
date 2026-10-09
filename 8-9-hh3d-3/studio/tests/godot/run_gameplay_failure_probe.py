"""Native AUTH-03 failure/last-good diagnostic; never public acceptance.

Publishes one valid gameplay fixture, rejects a second fixture through the
real bounded Docker/Godot executor, then proves durable reopen and idempotent
retry without a third native dispatch. Run only outside GT06's measurement
window. The caller must capture this process's actual exit.
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

AUTH05_FAILURE_FIXTURES = {
    'boundary': 'gameplay_source_boundary',
    'spawn': 'gameplay_source_spawn',
    'busy': 'gameplay_source_busy',
    'wall': 'gameplay_source_wall_wait',
}
AUTH03_FAILURE_FIXTURES = {
    'syntax': 'gameplay_secondary_syntax_error',
    'type': 'gameplay_secondary_type_error',
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


def failure_case_name(failure_fixture):
    if failure_fixture in AUTH05_FAILURE_FIXTURES:
        return AUTH05_FAILURE_FIXTURES[failure_fixture]
    if failure_fixture in AUTH03_FAILURE_FIXTURES:
        return AUTH03_FAILURE_FIXTURES[failure_fixture]
    raise ValueError('UNKNOWN_FAILURE_FIXTURE')


def is_auth05_failure(failure_fixture):
    return failure_fixture in AUTH05_FAILURE_FIXTURES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--failure-fixture', choices=('syntax', 'type', 'boundary', 'spawn', 'busy', 'wall'), default='syntax')
    args = parser.parse_args()
    if not re.fullmatch(r'o2-auth0[35]-native-[a-z0-9-]{1,40}', args.run_id):
        parser.error('use a fresh o2-auth03-native-<id> or o2-auth05-native-<id>')
    auth05 = is_auth05_failure(args.failure_fixture)
    if auth05 != args.run_id.startswith('o2-auth05-native-'):
        parser.error('boundary/spawn/busy/wall require o2-auth05-native-<id>; syntax/type require o2-auth03-native-<id>')
    idle_window()
    output = STUDIO / '.local/reviews' / args.run_id
    output.mkdir(exist_ok=False)
    owner_mod = load('o2_auth03_gameplay_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    probe = load('o2_auth03_linux_probe', STUDIO / 'tests/godot/run_linux_probe.py')
    fixtures = load('o2_auth03_gameplay_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    good_case_name = 'gameplay_source'
    bad_case_name = failure_case_name(args.failure_fixture)
    good_case = {**fixtures.FIXTURES[good_case_name], 'scene': fixtures.SCENE,
                 'project': owner_mod._load('gameplay_source_profile').PROJECT_TEMPLATE}
    bad_case = {**fixtures.FIXTURES[bad_case_name], 'scene': fixtures.SCENE,
                'project': good_case['project']}
    # AUTH-03 uses the authenticated extended deadline because its dependency
    # readback can drain a secondary parse failure.  AUTH-05 intentionally
    # remains on the legacy 20 s hostile-fixture contract; applying the
    # attribution driver there changes its watchdog boundary and transcript.
    if not auth05:
        bad_case['timeout'] = 30
        bad_case['authenticated_timeout'] = True
    files, closure = owner_mod.runtime_source_closure()
    for name in ('tests/godot/run_gameplay_failure_probe.py', 'tests/godot/run_linux_probe.py',
                 'tests/godot/linux_probe_fixtures.py', 'godot-addon/gameplay_dependency_observation.py'):
        files[name] = probe.sha(STUDIO / name)
    binding = {'run_id': args.run_id, 'source_closure_sha256': closure, 'files': files,
               'authority': 0, 'public_ack': False,
               'scope': ('AUTH-05 hostile boundary/spawn/watchdog rejection after a good publication; '
                         'not public acceptance.' if auth05
                         else 'AUTH-03 good publication then native rejection; not public acceptance.')}
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
    good = probe.case_files(good_case)
    good.pop('project.godot')
    initial = dict(good)
    initial[owner_mod.ENTRYPOINT] += b'\n# Initial unpublished fixture revision.\n'
    candidate = dict(good)
    candidate[owner_mod.ENTRYPOINT] += b'\n# Known good published fixture.\n'
    bad = probe.case_files(bad_case)
    bad.pop('project.godot')
    calls = []
    owner = reopened = None
    result = {'run_id': args.run_id, 'authority': 0, 'public_ack': False,
              'sandbox_acceptance': False, 'source_closure_sha256': closure,
              'status': 'INCOMPLETE'}
    try:
        def run_native(project, **kwargs):
            idle_window()
            need(len(calls) < 2, 'UNEXPECTED_NATIVE_REDISPATCH')
            calls.append(str(kwargs['output'].relative_to(output)))
            # The owner uses this wrapper to retain the per-run call ledger,
            # so the owner cannot identity-compare it with executor.run when
            # forwarding the authenticated gameplay deadline. AUTH-03 uses it
            # for both calls. AUTH-05 keeps the hostile fixture at its legacy
            # 20 s boundary, while its good baseline may use the authenticated
            # 30 s envelope so three Godot startup phases do not flake before
            # the hostile behavior is dispatched.
            good_baseline = str(kwargs['output']).endswith('command.publication.good')
            kwargs['authenticated'] = (not auth05) or good_baseline
            if auth05 and good_baseline:
                kwargs['timeout_seconds'] = 30
            return owner_mod._load('linux_executor').run(project, **kwargs)

        # AUTH-03 is a source bundle parse gate.  Keep the dependency observer
        # enabled so the secondary type failure gets the authenticated 30 s
        # gameplay deadline; the previous 20 s legacy deadline could expire
        # while Godot was draining the parse error, losing the raw rejection
        # postcondition even though the engine had already emitted it.
        dependency_files = tuple(sorted(name for name in initial
                                        if name in ('scenes/fixture.tscn',
                                                    'scripts/fixture_actor.gd',
                                                    'scripts/unused.gd')))
        owner = owner_mod.GameplaySourcePublicationOwner.create(
            output, project_id='project.publication', source_files=initial,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=closure,
            runner=run_native, dependency_observation_required=not auth05,
            dependency_observation_files=dependency_files if not auth05 else ())
        initial_readback = owner.inspect()
        credential = owner.issue()
        grant = owner.authorize('Bearer ' + credential.bearer, 'scene.save')
        lease = owner.lease(grant)
        good_request = {'command_id': 'command.publication.good',
                        'expected_project_revision': initial_readback['project_revision'],
                        'source_files': candidate, 'entrypoint': owner_mod.ENTRYPOINT}
        good_request['digest'] = owner_mod.request_digest(project_id=owner.project_id, **good_request)
        good_ack = owner.publish(good_request, grant=grant, lease=lease,
                                 deadline_ms=lease.expires_ms)
        selected = owner.inspect()
        need(good_ack['status'] == 'READBACK_ACK' and good_ack['public_ack'] is False,
             'GOOD_PUBLICATION_POSTCONDITION')
        selected_bytes = (owner._root / 'CURRENT').read_bytes()
        journal_bytes = (owner._root / 'journal.jsonl').read_bytes()
        bad_request = {'command_id': 'command.publication.bad',
                       'expected_project_revision': selected['project_revision'],
                       'source_files': bad, 'entrypoint': owner_mod.ENTRYPOINT}
        bad_request['digest'] = owner_mod.request_digest(project_id=owner.project_id, **bad_request)
        bad_error = None
        try:
            owner.publish(bad_request, grant=grant, lease=lease, deadline_ms=lease.expires_ms)
        except Exception as error:
            bad_error = error
        need(isinstance(bad_error, owner_mod.GameplaySourceOwnerError)
             and str(bad_error) == 'GAMEPLAY_OWNER_NATIVE_NOT_CLEAN', 'BAD_FIXTURE_NOT_REJECTED')
        need((owner._root / 'CURRENT').read_bytes() == selected_bytes
             and (owner._root / 'journal.jsonl').read_bytes() == journal_bytes,
             'LAST_GOOD_MUTATED')
        bad_dir = owner._root / 'runs' / bad_request['command_id']
        observation = probe.case_observation(bad_dir, bad_case, name=bad_case_name, binding=binding)
        save(output / 'native-rejection-observation.json', observation)
        need(observation['fixture_observed'] is True and observation['mode'] == 'gameplay-source',
             'BAD_FIXTURE_NOT_OBSERVED')
        root = owner._root
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(
            root, project_id='project.publication', source_closure_sha256=closure,
            runner=run_native, dependency_observation_required=not auth05,
            dependency_observation_files=dependency_files if not auth05 else ())
        need(reopened.inspect() == selected, 'REOPEN_LAST_GOOD_CHANGED')
        fresh = reopened.issue()
        grant = reopened.authorize('Bearer ' + fresh.bearer, 'scene.save')
        lease = reopened.lease(grant)
        need(reopened.publish(good_request, grant=grant, lease=lease,
                              deadline_ms=lease.expires_ms) == good_ack, 'GOOD_RETRY_CHANGED')
        need(len(calls) == 2, 'UNEXPECTED_NATIVE_REDISPATCH')
        need((root / 'CURRENT').read_bytes() == selected_bytes
             and (root / 'journal.jsonl').read_bytes() == journal_bytes,
             'RECOVERY_DURABLE_STATE_CHANGED')
        need(all(probe.sha(STUDIO / name) == digest for name, digest in files.items()),
             'SOURCE_CHANGED_DURING_PROBE')
        result.update(status='DIAGNOSTIC_PASS', initial=initial_readback, selected=selected,
            good_receipt=good_ack, bad_error_code=str(bad_error), bad_observation=observation,
            native_run_count=len(calls), native_paths=calls, bad_rejected=True,
            failure_fixture=args.failure_fixture,
            last_good_current_sha256=hashlib.sha256(selected_bytes).hexdigest(),
            last_good_journal_sha256=hashlib.sha256(journal_bytes).hexdigest(),
            reopen_readback_equal=True, retry_equal=True, retry_no_redispatch=True,
            durable_state_unchanged=True, source_unchanged=True)
    except Exception as error:
        result.update(status='DIAGNOSTIC_FAIL', error_class=type(error).__name__,
                      error_message=str(error), native_paths=calls,
                      native_run_count=len(calls))
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
