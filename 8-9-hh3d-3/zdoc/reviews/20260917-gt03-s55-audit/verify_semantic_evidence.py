"""Read-only S55 shared-source and raw semantic audit; never acceptance.

No native API owner, Registry, private storage, or engine is opened. Optional
portable custody exports must be produced separately under coordinator control.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REVIEWS = HERE.parent
ROOT = REVIEWS.parent.parent
CLOSURE = '3a220b51105166274bad4bde950f4cc1d975e87b009b66e52428fad9dc27b02e'
SOURCE_PACKAGE = REVIEWS / '20260917-gt03-s55-source-01'
SOURCE = SOURCE_PACKAGE / 'source/studio'
CONTROLLER_PIN = '46d27dd3a3c188ad90abd8a951d6723314e989ebd642fae6be68dbe1232394da'
HELPER = REVIEWS / '20260917-gt03-s52-audit/verify_integration.py'
HELPER_PIN = 'a4500bf057cd0e7d50201453b427e7124db2c04efb99cc114f8d73606ff31c66'
PUBLICATION_HELPER = REVIEWS / '20260917-gt03-s53-audit/verify_publication.py'
PUBLICATION_HELPER_PIN = '28f03ad71a891569e472ae7c4c76880fd3026eca04fc37530efb71bd7a86add8'
UNIT_CONTROLLER_PIN = 'f285ddba8fe71bfc9fd7bbfedf0ba13f04fafb741cbb496d039d6e50380dfc7a'
EXPORTER_PIN = 'b2afbab8a7719cd191024676e92c891974ff86b9f6f70fdee203918da897f4fa'
FRAME_PARSER_PIN = '770135ab5f5b53ecec62369364c2c9e9dac925bf540a70cd18a7291727e2bb8f'
DRAIN_CONTROLLER_PIN = 'cf36f1c33fb7d76d18bdcac58b62b930913f05ded8f1f575fe8c4be68266e8e4'
EXCLUDED = {'.godot', '__pycache__', '.cache', '.writer', 'storage', 'appdata', 'localappdata', 'temp'}


def need(value, message):
    if value is not True:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    # Use the frozen JCS implementation, including ECMAScript number rendering.
    from studio.protocol.core import canonical_bytes
    return canonical_bytes(value)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


need(sha(HELPER.read_bytes()) == HELPER_PIN, 'pinned S52 raw auditor changed')
base = load('s55_semantic_raw_audit', HELPER)
need(sha((HERE / 'run_native_lane.py').read_bytes()) == CONTROLLER_PIN, 'controller changed')
controller = load('s55_semantic_controller', HERE / 'run_native_lane.py')
need(sha(PUBLICATION_HELPER.read_bytes()) == PUBLICATION_HELPER_PIN, 'pinned S53 publication auditor changed')
publication_helper = load('s55_publication_binding_helper', PUBLICATION_HELPER)


class Evidence:
    def __init__(self, overlay=None):
        self.files = {}
        self.overlay = overlay or {}

    def add(self, path):
        path = Path(path).resolve()
        relative = path.relative_to(ROOT.resolve()).as_posix()
        need(not any(part.lower() in EXCLUDED or part.startswith(('hh-private-', 'hh-files-'))
                     for part in path.parts), 'private storage/cache excluded from portable evidence')
        controller.regular(path)
        self.files[relative] = sha(path.read_bytes())
        return path

    def raw(self, path):
        path = self.add(path)
        return self.overlay.get(path, path.read_bytes())

    def read(self, path):
        return json.loads(self.raw(path))

    def text(self, path):
        return self.raw(path).decode('utf-8')

    def tree(self, path):
        for item in sorted(Path(path).rglob('*')):
            if item.is_file():
                self.add(item)


def source(ev):
    manifest = ev.read(SOURCE_PACKAGE / 'source-closure.json')
    actual = controller.inventory()
    need(len(actual) == 176 and actual == manifest['files'] and manifest['source_closure_sha256'] == CLOSURE
         and base.closure_digest(actual) == CLOSURE, 'shared full source inventory/closure mismatch')
    ev.tree(SOURCE)
    ev.add(HELPER)
    ev.add(base.HELPER)
    ev.add(PUBLICATION_HELPER)
    ev.add(HERE / 'run_native_lane.py')
    ev.add(Path(__file__))
    return actual


def modules():
    sys.path.insert(0, str(SOURCE.parent))
    return {name: base.H.module('s55_semantic_' + name, SOURCE / 'godot-addon' / (name + '.py'))
            for name in ('publication_state_v5', 'publication_recovery', 'validation_owner', 'editor_owner')}


def raw_host(ev, package, host, expected=0):
    raw = ev.read(package / host['host'])
    need(type(raw.get('exit_code')) is int and raw['exit_code'] == expected == host['exit_code']
         and type(raw.get('target_pid')) is int and raw['target_pid'] > 0 and raw['target_pid'] == host['target_pid']
         and type(host['wrapper_exit_code']) is int and host['wrapper_exit_code'] == 0
         and host['tree_verified'] is True and host['timed_out'] is False
         and host['ownership'] == 'gated_job_kill_on_close', 'raw process exit/PID/Job mismatch')
    ev.add(package / host['stderr'])
    return ev.text(package / host['stdout'])


def supporting_evidence(ev, files):
    """Bind already completed unit evidence; no discovery/test/native call."""
    package = REVIEWS / '20260917-gt03-s55-units-01'
    capture = ev.read(package / 'capture.json')
    invocation = ev.read(package / 'invocation.json')
    need(sha(ev.raw(package / 'controller.py')) == UNIT_CONTROLLER_PIN, 'unit controller pin')
    unit = load('s55_unit_audit_only', package / 'controller.py')
    need(invocation == {'schema': 'hh-gt03-unit-matrix-2', 'code': unit.CODE,
         'partitions': list(unit.LABELS), 'timeouts': unit.TIMEOUTS,
         'controller_sha256': UNIT_CONTROLLER_PIN,
         'runner_sha256': files['build/bootstrap/run_fixture.py'],
         'source_closure_sha256': CLOSURE,
         'source_manifest_sha256': sha(ev.raw(SOURCE_PACKAGE / 'source-closure.json')),
         'runtime_package': '../20260917-gt03-s55-source-01'}, 'unit invocation/source binding')
    need(ev.read(package / 'runtime-source-reference.json') == {key: invocation[key] for key in
         ('runtime_package', 'source_closure_sha256', 'source_manifest_sha256', 'controller_sha256')}, 'unit source reference')
    need(capture['state'] == 'COMPLETE' and capture['passed'] is True and capture['formal_acceptance'] is False
         and capture['snapshot_unchanged'] is True and capture['partitions_disjoint_complete'] is True
         and capture['source_closure_sha256'] == CLOSURE and capture['controller_sha256'] == UNIT_CONTROLLER_PIN
         and capture['runtime_package'] == invocation['runtime_package'] and set(capture['lanes']) == set(unit.LABELS),
         'unit complete capture/source')
    round_path = (package / capture['round']).resolve()
    need(round_path.parent == (package / 'rounds').resolve()
         and ev.raw(round_path / 'capture.json') == ev.raw(package / 'capture.json'), 'unit retained round differs')
    inventories, summaries = [], []
    for label in unit.LABELS:
        saved = capture['lanes'][label]
        attempt = (package / saved['attempt']).resolve()
        need(attempt.parent == (package / 'attempts' / label).resolve(), 'unit attempt path')
        ev.tree(attempt)
        rebuilt = unit.inspect_attempt(attempt, invocation, label)
        need(rebuilt['passed'] is True and all(saved.get(key) == value for key, value in rebuilt.items()),
             'unit raw attempt differs: ' + label)
        # The helper is pinned and reads only sealed raw files. Record those
        # same bytes in the portable inventory and independently parse host.
        raw_host(ev, attempt, rebuilt['host'])
        inventories.append(rebuilt['inventory'])
        summaries.append({'partition': label, 'attempt': saved['attempt'], 'run': rebuilt['counts']['run'],
                          'raw_exit': rebuilt['host']['exit_code'], 'wrapper_exit': rebuilt['host']['wrapper_exit_code']})
    full = inventories[0]['all']
    selected = [name for inventory in inventories for name in inventory['chosen']]
    need(all(inventory['all'] == full for inventory in inventories) and len(selected) == len(set(selected))
         and set(selected) == set(full) and len(full) == 699
         and capture['counts'] == {'run': len(full), 'failures': 0, 'errors': 0, 'skips': 0},
         'unit inventory is not disjoint complete 699')

    inspection = REVIEWS / '20260917-gt03-s55-recovery-inspection-native-01'
    inv = ev.read(inspection / 'invocation.json')
    cap = ev.read(inspection / 'capture.json')
    code = "import unittest,json,sys; suite=unittest.defaultTestLoader.discover('tests/godot',pattern='test_recovery_journal_native.py'); r=unittest.TextTestRunner(verbosity=2).run(suite);print('NATIVE_INSPECTION_COMPLETE '+json.dumps({'run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped)}),flush=True);sys.exit(not r.wasSuccessful())"
    counts = {'run': 4, 'failures': 0, 'errors': 0, 'skips': 0}
    need(inv['code'] == code and Path(inv['runtime_package']).resolve() == SOURCE_PACKAGE.resolve()
         and inv['source_closure_sha256'] == cap['source_closure_sha256'] == CLOSURE
         and inv['runner_sha256'] == files['build/bootstrap/run_fixture.py']
         and cap['host']['argv'] == ['python.exe', '-B', '-c', code]
         and cap['counts'] == counts and cap['snapshot_unchanged'] is True and cap['formal_acceptance'] is False,
         'recovery inspection source/invocation')
    stdout = raw_host(ev, inspection, cap['host'])
    need(base.H.markers(stdout, 'NATIVE_INSPECTION_COMPLETE ') == [counts], 'recovery inspection completion')
    stderr = ev.text(inspection / cap['host']['stderr'])
    expected = [name for name in full if name.startswith('test_recovery_journal_native.')]
    need(len(expected) == 4 and len([line for line in stderr.splitlines() if line.endswith(' ... ok')]) == 4
         and all('(' + name + ') ... ok' in stderr for name in expected)
         and stderr.splitlines()[-1] == 'OK', 'recovery inspection named results')
    return {'unit_matrix': {'verified': True, 'package': package.name, 'run': len(full),
            'partitions': summaries, 'source_closure_sha256': CLOSURE},
            'extended_recovery_inspection': {'verified': True, 'package': inspection.name, 'run': 4,
            'counts_overlap_unit_matrix': True, 'source_closure_sha256': CLOSURE,
            'limitation': 'Native storage with synthetic readback; embedded crash91 host line is a unit assertion, not separately retained raw crash evidence.'}}


def common(ev, package, files):
    reference = ev.read(package / 'source-reference.json')
    invocation = ev.read(package / 'invocation.json')
    capture = ev.read(package / 'capture.json')
    lane = invocation['lane']
    need(lane in controller.LANES and capture['lane'] == lane, 'unknown lane')
    script, timeout, result_name, success_key, marker = controller.LANES[lane]
    need(reference['source_closure_sha256'] == capture['source_closure_sha256'] == invocation['source_closure_sha256'] == CLOSURE
         and reference['file_count'] == 176 and reference['runtime_copied'] is False
         and Path(reference['source_package']).resolve() == SOURCE_PACKAGE.resolve()
         and Path(reference['source_root']).resolve() == SOURCE.resolve()
         and reference['source_manifest_sha256'] == sha(ev.raw(SOURCE_PACKAGE / 'source-closure.json')),
         'shared source reference mismatch')
    effective = invocation.get('effective_execution')
    entrypoint = SOURCE / 'tests/godot' / script
    expected_source_check = {'unchanged': True, 'file_count': 176, 'changed': [], 'missing': [], 'extra': []}
    controller_pin = CONTROLLER_PIN
    if effective is not None:
        controller_pin = DRAIN_CONTROLLER_PIN
        drain_path = HERE / 'run_drained_publication_lane.py'
        need(lane in ('script', 'save') and sha(ev.raw(drain_path)) == DRAIN_CONTROLLER_PIN,
             'unknown supplementary execution policy')
        drain = load('s55_drain_audit_only', drain_path)
        expected_driver = drain.build_driver(ev.raw(entrypoint), SOURCE)
        expected_effective = {'policy': 'cleanup-only-stop-drain-v1', 'runtime_closure_sha256': CLOSURE,
            'original_probe': 'tests/godot/' + script, 'original_probe_sha256': files['tests/godot/' + script],
            'executed_driver': 'driver.py', 'executed_driver_sha256': sha(expected_driver),
            'controller_sha256': DRAIN_CONTROLLER_PIN, 'base_controller_sha256': CONTROLLER_PIN,
            'runtime_modified': False, 'unit_dependencies_modified': False}
        need(effective == reference.get('effective_execution') == capture.get('effective_execution')
             == ev.read(package / 'effective-execution.json') == expected_effective
             and ev.raw(package / 'driver.py') == expected_driver and capture['driver_unchanged'] is True,
             'effective runtime/driver file map mismatch')
        entrypoint = package / 'driver.py'
        expected_source_check = {'unchanged': True, 'file_count': 176}
        stop = ev.read(package / 'stop-terminal.json')
        need(stop['http_status'] == 200 and stop['response']['stop_persistence'] == 'DURABLE'
             and stop['response']['stopped'] is True and 0 <= stop['drain_elapsed_ms'] < 30000,
             'supplementary durable Stop terminal missing')
    need(reference['controller_sha256'] == capture['controller_sha256'] == invocation['controller_sha256']
         == sha(ev.raw(package / 'controller.py')) == controller_pin, 'controller binding mismatch')
    need(capture['passed'] is True and all(capture[key] is True for key in
         ('source_inventory_unchanged', 'controller_unchanged', 'executable_pins_unchanged'))
         and capture['candidate_only'] is True and capture['gt03_acceptance'] is False, 'candidate capture failed')
    need(ev.read(package / 'source-check-after.json') == expected_source_check, 'source postcheck mismatch')
    lock = ev.read(SOURCE / 'toolchain.lock.json')['godot']
    linux_pin = controller.constants(SOURCE / 'godot-addon/linux_executor.py', ('BINARY_NAME', 'BINARY_SHA256'))
    need(invocation['timeout_seconds'] == timeout and invocation['runtime_entrypoint_sha256'] == files['tests/godot/' + script]
         and invocation['pins']['windows_gui']['sha256'] == lock['gui_sha256']
         and invocation['pins']['linux']['sha256'] == linux_pin['BINARY_SHA256'], 'invocation executable/deadline pin mismatch')
    expected_argv = [invocation['python']['path'], '-B', str(entrypoint), '--frozen', '--output',
                     str(package), '--run-id', capture['run_id'], '--binary', invocation['pins']['windows_gui']['path'], '--closure', CLOSURE]
    if lane in controller.CRASH_EXITS:
        expected_argv += ['--case', lane]
    need(invocation['argv'] == expected_argv and Path(invocation['cwd']).resolve() == SOURCE.resolve(), 'invocation argv/source mismatch')
    host = capture['host']
    need(ev.read(package / 'host-report.json') == host, 'wrapper report differs')
    stdout = raw_host(ev, package, host)
    result = ev.read(package / result_name)
    checks = result['checks']
    need(checks and all(row.get('passed') is True for row in checks)
         and len({row['label'] for row in checks}) == len(checks) and checks == ev.read(package / 'progress.json'), 'producer checks differ')
    need(result[success_key] is True and result['source_closure_sha256'] == CLOSURE
         and result['candidate_only'] is True and result['gt03_acceptance'] is False, 'result source/scope mismatch')
    markers = base.H.markers(stdout, marker + ' ')
    expected_marker = {success_key: True, 'checks': len(checks)}
    if lane in controller.CRASH_EXITS:
        expected_marker['case'] = lane
        need(result['case'] == lane, 'cut identity')
    need(markers == [expected_marker], 'raw completion marker mismatch')
    need(capture['result']['sha256'] == sha(ev.raw(package / result_name)), 'captured result digest differs')
    if lane in controller.CRASH_EXITS or lane == 'recovery-publication':
        raw_host(ev, package / 'original', ev.read(package / 'original-host.json'), controller.CRASH_EXITS.get(lane, 92))
    logs = controller.typed_logs(package)
    need(logs['clean'] is True and ev.read(package / 'log-audit.json') == logs, 'typed raw log audit differs')
    for row in logs['logs']:
        ev.add(row['path'])
    return lane, len(checks)


def journal(ev, package, lane, mods):
    recovery_lane = lane in controller.CRASH_EXITS or lane == 'recovery-publication'
    event_name = 'recovery-events.json' if recovery_lane else ('journal-events.json' if lane == 'edit' else 'events.json')
    snapshot_name = 'journal-snapshot.json' if recovery_lane or lane == 'edit' else ('reopened.json' if lane == 'stop' else 'journal.json')
    events = ev.read(package / event_name)
    snapshot = ev.read(package / snapshot_name)
    if (package / 'effective-execution.json').exists():
        need(snapshot['stopped'] is True and events[-1]['kind'] == 'STOP', 'supplementary final durable Stop events')
        if (package / 'before-stop-journal.json').exists():
            prior = ev.read(package / 'before-stop-events.json') if (package / 'before-stop-events.json').exists() else events[:-1]
            need(events[:-1] == prior, 'supplementary pre-Stop event preservation')
            previous_snapshot = ev.read(package / 'before-stop-journal.json')
            prior_fold = mods['publication_state_v5'].replay(prior).snapshot()
            need(all(previous_snapshot.get(key) == value for key, value in prior_fold.items())
                 and previous_snapshot['journal_event_sequence'] == len(prior) + 4
                 and previous_snapshot['bootstrap_bytes_verified'] is True, 'pre-Stop snapshot fold')
    cut = next((index for index, row in enumerate(events) if row['schema'] == mods['publication_recovery'].RECOVERY_SCHEMA), len(events))
    state = mods['publication_state_v5'].replay(events[:cut])
    replayed = state.snapshot()
    recovered = None
    if recovery_lane:
        recovered = mods['publication_recovery']._fold_recovery(state, tuple(canonical(row) for row in events[cut:]))
        expected = {**replayed, 'selected': recovered['selected'] or replayed['selected'], 'recovery': recovered,
                    'stopped': replayed['stopped'] or recovered['stopped']}
    else:
        expected = replayed
    need(all(snapshot.get(key) == value for key, value in expected.items()), 'pure event fold differs from captured snapshot')
    need(snapshot['source_closure_sha256'] == CLOSURE, 'journal source mismatch')
    selected = snapshot['selected']
    base.check_selection({'selector': selected['selector'], 'selector_version': selected['selector_version']}, canonical)
    manifest = selected['bundle_manifest']
    for name in ('selection.json', 'selection-before.json'):
        if (package / name).exists():
            receipt = ev.read(package / name)
            need(receipt['selector'] == selected['selector'] and receipt['selector_version'] == selected['selector_version'], 'selected receipt differs')
    responses = []
    if recovery_lane:
        attempt = recovered['attempts'][-1]
        need(attempt['phase'] == 'TERMINAL', 'missing terminal recovery')
        response = ev.read(package / 'response.json')
        need(canonical(response) == ev.raw(package / 'response-wire.json') == canonical(attempt['response']), 'recovered terminal response bytes differ')
        request_name = 'recovery-request.json' if (package / 'recovery-request.json').exists() else 'request.json'
        request = ev.read(package / request_name)
        need(request['command_id'] == attempt['command_id'] and request['digest'] == attempt['digest'], 'recovery request binding')
        responses.append({'command_id': attempt['command_id'], 'route': attempt['route'], 'response_sha256': sha(canonical(response))})
    else:
        requests = list(package.glob('*-request.json')) if lane in ('edit', 'fifo') else [package / 'request.json']
        from studio.protocol.core import Request
        for request_path in requests:
            request_value = ev.read(request_path)
            if request_value.get('operation', '').startswith('lease.'):
                continue
            request = Request.from_dict(request_value)
            if lane in ('edit', 'fifo'):
                response_path = request_path.with_name(request_path.name.replace('-request.json', '-response.json'))
            else:
                response_path = package / ('save-response.json' if lane == 'stop' else 'response.json')
            response = ev.read(response_path)
            if lane == 'stop':
                response = response['result']
            raw = mods['publication_state_v5'].lookup_response(state, request.command_id, request.digest)
            need(raw == canonical(response), 'original terminal response differs from pure replay')
            wire = response_path.with_name(response_path.name.replace('-response.json', '-wire.json'))
            if response_path.name == 'response.json':
                wire = package / 'response-wire.json'
            if wire != response_path and wire.exists():
                need(ev.raw(wire) == raw, 'original wire response differs')
            responses.append({'command_id': request.command_id, 'response_sha256': sha(raw),
                              'raw_http_response_wire_retained': wire != response_path and wire.exists()})
        for name in ('duplicate-response.json', 'lookup-response.json'):
            if (package / name).exists():
                need(canonical(ev.read(package / name)) == raw, 'original reply replay differs')
    return events, snapshot, responses


def editor_evidence(ev, package, lane, snapshot):
    roots = sorted((package / 'owned/editor').glob('editor-*'))
    need(bool(roots), 'fresh editor evidence missing')
    for root in roots:
        start, hello, exited, close = [ev.read(root / name) for name in ('process-start.json', 'hello.json', 'process-exit.json', 'close.json')]
        need(type(start['pid']) is int and start['pid'] == hello['pid'] == exited['pid'] and exited['exit_code'] == 0
             and close['actual_process_exit'] == exited and close['wrapper_exit_code'] == 0
             and close['closed'] is True and close['held'] is False and close['logs_overflow'] is False
             and hello['main_thread'] is True and hello['editor_hint'] is True, 'actual editor identity/exit mismatch')
        base.checked_job(close['job'])
    if lane in controller.CRASH_EXITS or lane == 'recovery-publication':
        actual = ev.read(package / 'actual-editor.json')
        actual = actual.get('snapshot', actual)
        identity = ev.read(package / 'actual-editor-identity.json')
        need(identity['pid'] == hello['pid'] and identity['session_id'] == hello['editor_session_id'], 'fresh recovery editor differs')
        attempt = snapshot['recovery']['attempts'][-1]
        observation = attempt['observation']
        need(actual['state'] and actual['revision'] == observation['semantic_revision']
             and observation['editor'] == identity and actual['generation'] == observation['generation'], 'actual recovered readback mismatch')
    else:
        actual = ev.read(package / ('after-save.json' if lane == 'edit' else 'after.json'))
    need(actual['revision'] == 'sha256:' + sha(canonical(actual['state'])), 'actual semantic readback revision differs')
    selected = snapshot['selected']
    manifest = selected['bundle_manifest']
    expected_files = {name: {key: value[key] for key in ('sha256', 'size_bytes')} for name, value in manifest['files'].items()}
    need(actual['working_files'] == expected_files, 'actual readback full selected files differ')
    matching = [root for root in roots if ev.read(root / 'hello.json')['editor_session_id'] == actual['editor_session_id']]
    need(len(matching) == 1, 'readback editor session not found')
    root = matching[0]
    for name, expected in expected_files.items():
        raw = ev.raw(root / 'project' / name)
        need(sha(raw) == expected['sha256'] and len(raw) == expected['size_bytes'], 'selected file bytes differ: ' + name)
    if lane in ('save', 'script', 'edit', *controller.CRASH_EXITS, 'recovery-publication'):
        need(actual['revision'] == manifest['caller_observations']['scene_revision'] and not actual['can_undo'] and not actual['can_redo'],
             'selected semantic/history boundary differs')
    if lane == 'stop':
        dirty = ev.read(package / 'dirty.json')
        need(all(dirty[key] == actual[key] for key in ('revision', 'generation', 'root_instance_id', 'working_files', 'state', 'project_revision')),
             'Stop changed dirty live state')
        need(snapshot['stopped'] is True and [e['phase'] for e in snapshot['commands']] == ['UNKNOWN'], 'Stop terminal journal differs')
    return actual


def edit_observations(ev, package, lane, snapshot, mods):
    if lane not in ('edit', 'fifo'):
        return
    roots = list((package / 'owned/editor').glob('editor-*'))
    need(len(roots) == 1, 'one edit editor required')
    root = roots[0]
    before = ev.read(package / 'before.json')
    state = mods['publication_state_v5']
    for command in snapshot['commands']:
        if 'edit_prepared' not in command:
            continue
        checkpoint = command['checkpoint']
        cap = ev.read(root / (checkpoint['capture']['observation_id'] + '.json'))
        observed = ev.read(root / (command['edit_observation']['observation_id'] + '.json'))
        need(state.capture_summary(cap, command['edit_prepared'], checkpoint['observed_ms']) == checkpoint['capture']
             and state.observation_summary(observed, command, snapshot['last_observed_ms']) == command['edit_observation'],
             'raw editor checkpoint/transition differs from typed event')
        scene = ev.raw(root / 'scratch' / command['edit_prepared']['scratch_name'])
        need(sha(scene) == cap['scene_sha256'] and len(scene) == cap['scene_size_bytes'], 'actual checkpoint scene bytes differ')
        actual = ev.read(package / (command['command_id'] + '-after.json'))
        need(actual['state'] == observed['semantic_state'] and actual['revision'] == observed['semantic_revision']
             and all(actual[key] == before[key] for key in ('working_files', 'generation', 'root_instance_id', 'history_id')),
             'actual edit readback/history differs')
        post = command['response']['postconditions']
        need(post['public_ack'] is True and post['effect_scope'] == 'editor_session'
             and post['files_saved'] is False and post['live_state_durable'] is False, 'edit receipt overstates durability')
    if lane == 'edit':
        need(ev.read(package / 'edit.undo-after.json')['state'] == ev.read(package / 'edit.create-after.json')['state']
             and ev.read(package / 'edit.redo-after.json')['state'] == ev.read(package / 'edit.update-after.json')['state']
             and ev.read(package / 'edit.restore-after.json')['state'] == ev.read(package / 'after-save.json')['state'],
             'undo/redo/remove restore differs')
        save = next(row for row in snapshot['commands'] if row['command_id'] == 'edit.save')
        need(save['phase'] == 'COMMITTED' and save['response'] == ev.read(package / 'save-response.json'), 'saved terminal response differs')


def linux_evidence(ev, package, mods):
    validation = mods['validation_owner']
    linux = base.H.module('s55_semantic_linux', SOURCE / 'tests/godot/run_linux_probe.py')
    directories = sorted(package.glob('**/owned/validation/validate-*'))
    need(bool(directories), 'native Linux validation missing')
    results = []
    for directory in directories:
        ev.tree(directory / 'input')
        inputs = {name: ev.raw(directory / 'input' / name) for name in validation.bundle_codec.PATHS}
        bundle = validation.bundle_codec.decode_bundle(ev.raw(directory / 'manifest.json'), inputs)
        validation.factory.qualify(bundle)
        executor = directory / 'executor'
        for path in executor.iterdir():
            if path.is_file():
                ev.add(path)
        ev.tree(executor / 'snapshot')
        ev.tree(executor / 'harness')
        native = base.H.verify_executor(executor, validation.executor, linux, mode='profile-validate', timeout=20, inputs=inputs)
        observation, comparison = validation.evaluate_run(native, ev.text(executor / 'engine-stdout.txt'), ev.text(executor / 'engine-stderr.txt'), bundle)
        need(comparison.get('semantic_observed') is True, 'missing actual Linux semantic readback')
        results.append((directory, bundle, native, observation))
    need(len({row[2]['run_id'] for row in results}) == len(results), 'duplicate Linux execution')
    return results


def publication_chain(ev, package, lane, events, runs, mods):
    roots = list(package.glob('**/owned/editor/editor-*'))
    captures = {}
    for event in events:
        if event['kind'] != 'CAPTURED':
            continue
        facts = event['capture']
        paths = [root / (facts['capture_id'] + '.json') for root in roots if (root / (facts['capture_id'] + '.json')).exists()]
        need(len(paths) == 1, 'exact native publication capture required')
        observation = ev.read(paths[0])
        base.bind_editor_event(facts, observation)
        need(observation['semantic_revision'] == 'sha256:' + sha(canonical(observation['semantic_state'])), 'capture semantic digest')
        prepared = next(row for row in events if row['kind'] == 'CAPTURE_PREPARED' and row['command_id'] == event['command_id'])
        raw = ev.raw(paths[0].parent / 'scratch' / prepared['scratch_name'])
        need(sha(raw) == facts['scene_sha256'] and len(raw) == facts['scene_size_bytes'], 'publication captured scene bytes')
        captures[event['command_id']] = observation
    for event in events:
        if event['kind'] != 'VALIDATED':
            continue
        captured = captures[event['command_id']]
        candidates = [row for row in runs if sha(row[1].files['scenes/fixture.tscn']) == captured['scene_sha256']
                      and row[2]['run_id'] == event['validation']['run_id']]
        need(len(candidates) == 1, 'exact captured Linux candidate required')
        directory, bundle, native, observation = candidates[0]
        publication_helper.validation_receipt(event['validation'], event['command_id'], mods['validation_owner'],
                                              directory, bundle, native, observation)
    for event in events:
        if event['kind'] != 'READBACK' or 'adoption' not in event:
            continue
        facts = dict(event['adoption'])
        if facts.get('mode') == 'same_editor':
            facts.pop('mode')
            paths = [root / (facts['adoption_id'] + '.json') for root in roots if (root / (facts['adoption_id'] + '.json')).exists()]
            need(len(paths) == 1, 'exact native same-editor adoption required')
            base.bind_editor_event(facts, ev.read(paths[0]), adoption=True)
    if lane == 'script':
        # Explicit adapter: only pure raw observation helpers are reused. The
        # old per-package source/capture assumptions and main() are never used.
        publication_helper.script_editors(ev, package, SOURCE, mods['editor_owner'], canonical)


def custody_export(ev, package, events, snapshot):
    exports = [path for path in HERE.glob('native-exports*') if (path / package.name / 'native-capture.json').exists()]
    if not exports:
        return {'verified': False, 'gap': 'portable native custody/event-stream/FileID export missing; no live storage opened'}
    need(len(exports) == 1, 'ambiguous native custody exports')
    export_root = exports[0]
    export = export_root / package.name
    # The old parser is pure, pinned through this evidence manifest.
    parser_path = REVIEWS / '20260917-gt03-s54-edit-audit/verify_edit.py'
    need(sha(ev.raw(parser_path)) == FRAME_PARSER_PIN, 'native frame parser changed')
    parser = load('s55_native_frame_parser', parser_path)
    raw = ev.raw(export / 'native-events.bin')
    records = parser.native_records(raw, canonical)
    custody = ev.read(export / 'native-custody.json')
    native = ev.read(export / 'native-capture.json')
    export_host = ev.read(export_root / 'export-host-report.json')
    stdout = raw_host(ev, export_root, export_host)
    invocation = ev.read(export_root / 'export-invocation.json')
    need(invocation['source_closure_sha256'] == CLOSURE
         and invocation['exporter_sha256'] == sha(ev.raw(export_root / 'exporter.py'))
         == EXPORTER_PIN == sha(ev.raw(HERE / 'export_native_evidence.py'))
         and invocation['source_manifest_sha256'] == sha(ev.raw(SOURCE_PACKAGE / 'source-closure.json')),
         'native exporter/source binding')
    exported = ev.read(export_root / 'export-results.json')
    package_names = [row['package'] for row in exported['packages']]
    need(package.name in package_names and len(package_names) == len(set(package_names))
         and exported['source_unchanged'] is True and exported['gt03_acceptance'] is False
         and invocation['timeout_seconds'] == 300 and invocation['requires_coordinator_native_slot'] is True
         and base.H.markers(stdout, 'HH_S55_NATIVE_EXPORT_COMPLETE ') == [{'packages': len(package_names), 'passed': True}]
         and not ev.raw(export_root / export_host['stderr']), 'native export actual completion')
    need(sha(canonical(custody['record'])) == custody['sha256'] and native['custody_sha256'] == sha(ev.raw(export / 'native-custody.json')), 'custody checksum')
    need([row['event'] for row in records[4:]] == events and records == native['native_records'], 'native event bytes differ from replay')
    need(records[-1]['head'] == custody['record']['events']['binding']['witnessed'] == native['native_binding']['witnessed']
         and sha(raw) == native['stream_sha256'] and len(raw) == native['stream_size_bytes'], 'native witnessed terminal differs')
    record = custody['record']
    recovery = snapshot.get('recovery') is not None
    storage_parent = package / ('original/owned/storage' if recovery else 'owned/storage')
    need(native['storage_id'] == record['storage_id'] and native['project_id'] == record['project_id'] == snapshot['project_id']
         and all(Path(record[name]['path']).parent.resolve() == storage_parent.resolve() for name in ('files', 'events', 'blobs'))
         and all(native['native_binding'][kind][key] == record['events']['binding'][kind][key]
                 for kind in ('root', 'stream') for key in ('volume', 'file_id'))
         and native['native_binding']['stream']['size'] == len(raw)
         and native['files_root'] == {key: record['files']['identity'][key] for key in ('volume', 'file_id')},
         'native Registry/project/storage/root binding')
    need(native['source_closure_sha256'] == CLOSURE and native['registry_unchanged'] is True and native['stream_unchanged'] is True
         and native['native_resources_closed'] is True and native['cleanup_errors'] == [] and native['passed'] is True
         and native['access_scope'] == 'non-publishing content verification with write-capable verification handles'
         and native['creates_appends_registry_updates_or_rearms'] is False, 'native export scope/cleanup')
    selected = snapshot['selected']
    genesis, prepared, selecting, initial = [row['event'] for row in records[:4]]
    need(genesis == {'kind': 'GENESIS', 'file_id': native['native_binding']['stream']['file_id'],
            'root_file_id': native['native_binding']['root']['file_id'],
            'store_id': Path(record['events']['path']).name, 'volume': native['native_binding']['root']['volume']}
         and prepared['kind'] == 'BOOTSTRAP_PREPARED'
         and prepared['config'] == {key: value for key, value in events[0].items() if key != 'initial'}
         and events[0]['initial'] == {'bundle_manifest': prepared['bundle_manifest'],
             'selector': selecting['selector'], 'selector_version': initial['selector_version']}
         and selecting['kind'] == 'BOOTSTRAP_SELECTING' and initial['kind'] == 'BOOTSTRAP_SELECTED'
         and sha(canonical(selecting['selector'])) == initial['selector_sha256']
         and selected['selector']['descriptor']['root_identity'] == native['files_root'],
         'native genesis/bootstrap/selected root binding')
    need(ev.raw(export / 'native-selector.json') == canonical(selected['selector'])
         and ev.raw(export / 'native-manifest.json') == canonical(selected['bundle_manifest'])
         and native['selector_version'] == selected['selector_version'], 'native selected bytes differ')
    need(native['selected_files_unchanged'] is True
         and native['manifest_version'] == {key: selected['selector']['descriptor']['manifest'][key]
             for key in ('volume', 'file_id', 'size_bytes', 'sha256')}, 'native selected manifest FileID differs')
    need(native['selected_files'] == {name: {key: value[key] for key in ('volume', 'file_id', 'size_bytes', 'sha256')}
         for name, value in selected['selector']['descriptor']['files'].items()}, 'native selected FileIDs differ')
    descriptions = {}
    for event in events:
        for field in ('scene_blob', 'capture_blob', 'observation_blob'):
            if field in event:
                desc = event[field]
                descriptions[desc['object_id']] = desc
    need(native['edit_blobs'] == descriptions, 'native edit blob inventory differs')
    for object_id, desc in descriptions.items():
        raw_blob = ev.raw(export / 'blobs' / object_id)
        need(sha(raw_blob) == desc['sha256'] and len(raw_blob) == desc['identity']['size'], 'native edit blob bytes differ')
    return {'verified': True, 'native_records': len(records), 'portable_custody_is_not_acl_authority': True}


def verify_lane(package, files, mods, overlay=None):
    ev = Evidence(overlay)
    lane, count = common(ev, package, files)
    events, snapshot, responses = journal(ev, package, lane, mods)
    actual = editor_evidence(ev, package, lane, snapshot)
    edit_observations(ev, package, lane, snapshot, mods)
    runs = linux_evidence(ev, package, mods)
    publication_chain(ev, package, lane, events, runs, mods)
    if lane != 'fifo':
        need(any(row[3]['semantic']['state'] == actual['state'] for row in runs), 'actual editor state has no matching raw Linux readback')
    if lane == 'stop':
        timing = ev.read(package / 'timing.json')
        need(timing['validation_returned_at_stop_response'] is False and 0 <= timing['stop_elapsed_ms'] < 500
             and timing['stop_started_ms'] <= timing['stop_completed_ms'] < timing['validation_returned_ms'], 'Stop response/drain deadline')
        need(sha(ev.raw(package / timing['native_result_relative'])) == timing['native_result_sha256'], 'Stop native result digest')
        capture = base.live_editor(ev, package, SOURCE, canonical, adoption=False,
                                  release=sha(canonical(mods['editor_owner']._release())))[0]
        capture_event = next(row['capture'] for row in events if row['kind'] == 'CAPTURED')
        base.bind_editor_event(capture_event, capture)
        candidates = [row for row in runs if sha(row[1].files['scenes/fixture.tscn']) == capture['scene_sha256']]
        need(len(candidates) == 1, 'Stop exact candidate input')
        directory, bundle, native, observation = candidates[0]
        base.bind_validation_receipt(timing['registered_validation_receipt'], mods['validation_owner'],
                                     directory, bundle, native, observation, semantic=False)
        running = ev.read(package / 'running.json')
        observer = package / 'stop-observer'
        ev.tree(observer)
        label = Path(running['host']['stdout']).name.removesuffix('-stdout.txt')
        need(base.H.cli(observer, label, mods['validation_owner'].executor, args=['inspect', native['container_id']]) == running['host']
             and base.H.one_inspect(observer, label) == running['native']
             and running['native']['Id'] == native['container_id'] and running['native']['State']['Running'] is True,
             'actual running Stop observation differs')
        need(base.milliseconds(native['container_state']['StartedAt']) <= timing['stop_started_ms']
             <= timing['stop_completed_ms'] < base.milliseconds(native['container_state']['FinishedAt']), 'Stop outside actual validator execution')
    custody = custody_export(ev, package, events, snapshot)
    stop_drain = None
    if (package / 'effective-execution.json').exists():
        first, terminal = ev.read(package / 'stop-response.json'), ev.read(package / 'stop-terminal.json')
        stop_drain = {'initial_persistence': first['stop_persistence'],
            'terminal_persistence': terminal['response']['stop_persistence'],
            'drain_elapsed_ms': terminal['drain_elapsed_ms'],
            'terminal_http_status_observed_by_poll': first['stop_persistence'] == 'PENDING'}
    return ev, {'lane': lane, 'package': package.name, 'available_evidence_verified': True,
                'source_closure_sha256': CLOSURE, 'harness_checks': count, 'typed_events': len(events),
                'effective_execution': ev.read(package / 'invocation.json').get('effective_execution'),
                'supplementary_stop_drain': stop_drain,
                'raw_linux_runs': len(runs), 'terminal_responses': responses, 'custody': custody,
                'gaps': ([] if custody['verified'] else [custody['gap']]), 'gt03_acceptance': False}


def failed_attempt(ev, package):
    """Retain a failed execution as a failure, never as functional proof."""
    capture = ev.read(package / 'capture.json')
    invocation = ev.read(package / 'invocation.json')
    reference = ev.read(package / 'source-reference.json')
    need(capture['passed'] is False and capture['candidate_only'] is True and capture['gt03_acceptance'] is False
         and capture['lane'] == invocation['lane'] and capture['source_inventory_unchanged'] is True
         and capture['source_closure_sha256'] == invocation['source_closure_sha256'] == reference['source_closure_sha256'] == CLOSURE
         and capture['controller_sha256'] == invocation['controller_sha256'] == reference['controller_sha256']
         == sha(ev.raw(package / 'controller.py')) == CONTROLLER_PIN, 'failed attempt binding')
    host = capture['host']
    need(ev.read(package / 'host-report.json') == host and type(host['exit_code']) is int and host['exit_code'] != 0,
         'failed attempt actual result')
    raw_host(ev, package, host, host['exit_code'])
    need(ev.read(package / 'source-check-after.json') == {'unchanged': True, 'file_count': 176,
         'changed': [], 'missing': [], 'extra': []}, 'failed attempt source check')
    if (package / 'stop-response.json').exists():
        ev.add(package / 'stop-response.json')
    return {'package': package.name, 'lane': invocation['lane'], 'available_evidence_verified': False,
            'failed_execution_retained': True, 'raw_exit': host['exit_code'], 'wrapper_exit': host['wrapper_exit_code'],
            'owned_tree_verified': host['tree_verified'], 'failure': capture['failure'],
            'functional_pass': False, 'gt03_acceptance': False}


def execution_manifest(ev, files, rows):
    """Separate immutable runtime closure from the complete executed driver map."""
    execution_files = {'runtime/studio/' + name: value for name, value in files.items()}
    paths = {'runtime/studio/' + name: (SOURCE / name).relative_to(ROOT).as_posix() for name in files}
    dependencies = list(sorted(execution_files))
    lanes = []
    verified = [row for row in rows if row.get('available_evidence_verified')]
    need(len({row['lane'] for row in verified}) == len(verified), 'ambiguous multiple successful lane packages')
    def external(path):
        name = path.relative_to(ROOT).as_posix()
        key = 'evidence/' + name
        execution_files[key] = sha(ev.raw(path))
        paths[key] = name
        return key
    base_key = external(HERE / 'run_native_lane.py')
    unit_key = external(REVIEWS / '20260917-gt03-s55-units-01/controller.py')
    lanes.append({'lane': 'unit-matrix', 'package': '20260917-gt03-s55-units-01',
                  'entrypoint': unit_key, 'dependencies': dependencies + [unit_key],
                  'external_cleanup_drivers_executed_by_units': False})
    inspection_key = external(REVIEWS / '20260917-gt03-s55-recovery-inspection-native-01/invocation.json')
    lanes.append({'lane': 'extended-recovery-inspection', 'package': '20260917-gt03-s55-recovery-inspection-native-01',
                  'inline_driver_in_invocation': inspection_key, 'entrypoint': 'runtime/studio/tests/godot/test_recovery_journal_native.py',
                  'dependencies': dependencies + [inspection_key], 'counts_overlap_unit_matrix': True})
    for row in verified:
        package = REVIEWS / row['package']
        invocation = ev.read(package / 'invocation.json')
        controller_key = external(package / 'controller.py')
        deps = dependencies + [base_key, controller_key]
        entrypoint = 'runtime/studio/tests/godot/' + controller.LANES[row['lane']][0]
        if invocation.get('effective_execution') is not None:
            deps.append(external(HERE / 'run_drained_publication_lane.py'))
            entrypoint = external(package / 'driver.py')
            deps.append(entrypoint)
        lanes.append({'lane': row['lane'], 'package': package.name, 'entrypoint': entrypoint,
                      'controller': controller_key, 'dependencies': sorted(set(deps)),
                      'argv': invocation['argv'], 'effective_execution': invocation.get('effective_execution')})
    manifest = {'schema': 'hh-s55-effective-execution-1', 'runtime_source_closure_sha256': CLOSURE,
            'runtime_source_file_count': len(files), 'files': execution_files, 'source_paths': paths,
            'files_sha256': sha(''.join(name + '\0' + value + '\n'
                 for name, value in sorted(execution_files.items())).encode()),
            'lanes': lanes, 'all_native_lane_maps_present': len(verified) == len(controller.LANES),
            'unit_matrix_scope': '699 tests ran the unchanged176-file runtime/unit snapshot; external cleanup drivers are separately executed native harnesses.',
            'gt03_acceptance': False}
    # Hash the dependency/entrypoint map as well as the file bytes. Two critics
    # bind this value only after all requested lane maps are present.
    manifest['effective_execution_closure_sha256'] = sha(canonical(manifest))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='fresh report directory under this audit')
    args = parser.parse_args()
    output = args.output.resolve()
    need(output.parent == HERE.resolve() and not output.exists(), 'fresh owned report directory required')
    ev = Evidence()
    files = source(ev)
    mods = modules()
    supporting = supporting_evidence(ev, files)
    rows = []
    for package in sorted(REVIEWS.glob('20260917-gt03-s55-*')):
        if not (package / 'invocation.json').exists():
            continue
        invocation = json.loads((package / 'invocation.json').read_bytes())
        if invocation.get('lane') not in controller.LANES:
            continue
        if not (package / 'capture.json').exists():
            rows.append({'package': package.name, 'lane': invocation['lane'], 'available_evidence_verified': False, 'pending': True,
                         'gap': 'outer capture/actual completion missing; active or incomplete run'})
            continue
        try:
            if json.loads((package / 'capture.json').read_bytes()).get('passed') is False:
                rows.append(failed_attempt(ev, package.resolve()))
                continue
            lane_ev, result = verify_lane(package.resolve(), files, mods)
            ev.files.update(lane_ev.files)
            rows.append(result)
        except (ValueError, KeyError, TypeError, OSError, AssertionError) as error:
            rows.append({'package': package.name, 'lane': invocation['lane'], 'available_evidence_verified': False,
                         'error': type(error).__name__ + ': ' + str(error)})
    observed = {row['lane'] for row in rows if row.get('available_evidence_verified')}
    gaps = ['lane pending: ' + lane for lane in controller.LANES if lane not in observed]
    gaps += [row['package'] + ': ' + gap for row in rows for gap in row.get('gaps', [])]
    gaps += [row['package'] + ': ' + row['error'] for row in rows if 'error' in row]
    effective = execution_manifest(ev, files, rows)
    need(controller.inventory() == files, 'shared source changed during audit')
    need(all(sha((ROOT / name).read_bytes()) == value for name, value in ev.files.items()), 'evidence changed during audit')
    report = {'schema': 'hh-s55-semantic-audit-1', 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'source_closure_sha256': CLOSURE, 'source_file_count': 176, 'lanes': rows, 'remaining_gaps': gaps,
              'supporting_evidence': supporting,
              'effective_execution_closure_sha256': effective['effective_execution_closure_sha256'],
              'effective_execution_manifest': 'effective-execution-manifest.json',
              'all_requested_evidence_complete': not gaps, 'native_processes_started': 0,
              'live_registry_or_storage_opened': False, 'gt03_acceptance': False,
              'limitations': ['Captured HTTP retry/auth assertions are not an independent full packet transcript.',
                              'Portable custody checksums detect alteration; they do not recreate native ACL authority.',
                              'Acceptance requires coordinator dependencies and two independent critics on this exact source.']}
    output.mkdir()
    (output / 'effective-execution-manifest.json').write_text(json.dumps(effective, indent=2) + '\n', encoding='utf-8', newline='\n')
    ev.add(output / 'effective-execution-manifest.json')
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    ev.add(output / 'verification.json')
    for name in ('export_native_evidence.py', 'test_semantic_evidence.py', 's55-gate-map.md'):
        if (HERE / name).exists():
            ev.add(HERE / name)
    for path in HERE.glob('semantic-corruption-tests*.json'):
        ev.add(path)
    manifest = {'source_closure_sha256': CLOSURE, 'files': ev.files, 'excluded_path_parts': sorted(EXCLUDED),
                'files_sha256': sha(''.join(name + '\0' + value + '\n' for name, value in sorted(ev.files.items())).encode()),
                'gt03_acceptance': False}
    (output / 'portable-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'lanes': rows, 'remaining_gaps': gaps, 'portable_files': len(ev.files)}, indent=2))
    return 1 if any('error' in row for row in rows) else 0


if __name__ == '__main__':
    raise SystemExit(main())
