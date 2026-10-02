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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--fixture', default='gameplay_source_multifile')
    args = parser.parse_args()
    if not re.fullmatch(r'o2-publication-[a-z0-9-]{1,48}', args.run_id):
        parser.error('use a fresh o2-publication-<id>')
    idle_window()
    output = STUDIO / '.local/reviews' / args.run_id
    output.mkdir(exist_ok=False)
    owner_mod = load('o2_native_gameplay_owner', STUDIO / 'godot-addon/gameplay_source_owner.py')
    probe = load('o2_native_linux_probe', STUDIO / 'tests/godot/run_linux_probe.py')
    fixtures = load('o2_native_gameplay_fixtures', STUDIO / 'tests/godot/linux_probe_fixtures.py')
    if args.fixture not in fixtures.FIXTURES or not args.fixture.startswith('gameplay_source_'):
        parser.error('fixture must be a gameplay_source_* case')
    files, closure = owner_mod.runtime_source_closure()
    for name in ('tests/godot/run_gameplay_publication_probe.py',
                 'tests/godot/run_linux_probe.py', 'tests/godot/linux_probe_fixtures.py',
                 'godot-addon/gameplay_dependency_observation.py'):
        files[name] = probe.sha(STUDIO / name)
    binding = {'run_id': args.run_id, 'source_closure_sha256': closure,
               'files': files, 'authority': 0, 'public_ack': False,
               'scope': 'Declared adapter closure plus diagnostic harness; not arbitrary dependencies.'}
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
    candidate = probe.case_files(case)
    candidate.pop('project.godot')
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
            calls.append(str(kwargs['output'].relative_to(output)))
            return owner_mod._load('linux_executor').run(project, **kwargs)

        owner = owner_mod.GameplaySourcePublicationOwner.create(output,
            project_id='project.publication', source_files=initial,
            entrypoint=owner_mod.ENTRYPOINT, source_closure_sha256=closure, runner=run_native,
            dependency_observation_required=case.get('dependency_observation') is True,
            dependency_observation_files=tuple(case.get('dependency_files', ())))
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
        need(observation['fixture_observed'] is True, 'NATIVE_FIXTURE_NOT_OBSERVED')
        root = owner._root
        owner.close()
        reopened = owner_mod.GameplaySourcePublicationOwner.reopen(root,
            project_id='project.publication', source_closure_sha256=closure, runner=run_native,
            dependency_observation_required=case.get('dependency_observation') is True,
            dependency_observation_files=tuple(case.get('dependency_files', ())))
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
        result.update(status='DIAGNOSTIC_PASS', initial=initial_readback,
            selected=selected, receipt=ack, native_run_count=len(calls), native_paths=calls,
            live_retry_equal=True, reopened_retry_equal=True, durable_state_unchanged=True,
            source_unchanged=True, native_fixture_observed=True)
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
