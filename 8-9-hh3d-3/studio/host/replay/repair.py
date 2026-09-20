"""Fixed GT06 movement repair through the accepted GT03 authenticated tool.

Internal coordinator lane, never an arbitrary script/file execution endpoint.
The returned script comes from the committed managed bundle and native editor
readback. Only a later immutable Play replay can establish the repair worked.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.host.replay import native_runner as native
from studio.host.replay.observation import validate_observation
from studio.host.replay.trace import validate_trace
from studio.protocol.core import Request, canonical_bytes, parse_json
from studio.host.core.transport import epoch_ms


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def verified_fault(root: Path, expected_capture_sha256: str):
    """Require an externally bound complete fault observation, never a banner."""
    raw = native.read_regular(root / 'capture.json')
    native.need(native.sha(raw) == expected_capture_sha256, 'REPAIR_FAULT_CAPTURE_HASH')
    capture = json.loads(raw)
    native.need(capture['completed_native'] is True and capture['source_unchanged'] is True,
                'REPAIR_FAULT_INCOMPLETE')
    stages = {}
    for phase in ('import', 'runtime'):
        stages[phase] = native.verify_captured_stage(root / (phase + '-host'), capture[phase + '_capture_sha256'])
    native.need(stages['runtime']['actual_process_exit']['pid'] == capture['process']['pid'], 'REPAIR_FAULT_PID')
    source_map = json.loads(native.read_regular(root / 'source-files.json'))
    native.need(native.closure(source_map) == capture['binding']['source_closure_sha256'], 'REPAIR_FAULT_SOURCE_CLOSURE')
    for index, (name, digest) in enumerate(source_map.items()):
        native.need(native.sha(native.read_regular(root / 'source' / (str(index) + Path(name).suffix))) == digest,
                    'REPAIR_FAULT_SOURCE_BYTES')
    snapshot = json.loads(native.read_regular(root / 'runtime-snapshot.json'))
    native.need(native.closure(snapshot) == capture['binding']['runtime_snapshot_sha256'], 'REPAIR_FAULT_SNAPSHOT')
    for name, digest in snapshot.items():
        native.need(type(name) is str and not Path(name).is_absolute() and '\\' not in name
                    and all(part not in ('', '.', '..') for part in name.split('/')), 'REPAIR_FAULT_SNAPSHOT_PATH')
        native.need(native.sha(native.read_regular(root / 'project' / name)) == digest, 'REPAIR_FAULT_SNAPSHOT_BYTES')
    report_raw = native.read_regular(root / 'project/out/report.json')
    process_raw = native.read_regular(root / 'process-metrics.json')
    native.need(native.sha(report_raw) == capture['report_sha256']
                and native.sha(process_raw) == capture['process_metrics_sha256'], 'REPAIR_FAULT_ARTIFACT_HASH')
    project = root / 'project'
    trace = validate_trace(native.read_regular(project / 'input/trace.json'))
    checks = validate_observation(report_raw, trace=trace, binding=capture['binding'],
        config_speed=0.0, project=project, process=json.loads(process_raw))
    native.need(checks['movement_fault_observed'] is True, 'REPAIR_FAULT_NOT_OBSERVED')
    config = native.read_regular(project / 'config/fixture_actor.gd')
    native.need(config == native.configuration('0.0'), 'REPAIR_FAULT_CONFIG')
    return config, capture, checks


def execute(output: Path, fault_root: Path, fault_hash: str, binary: Path, source_closure: str):
    config, fault_capture, checks = verified_fault(fault_root, fault_hash)
    native.write(output / 'fault-binding.json', {'capture_sha256': fault_hash,
        'binding': fault_capture['binding'], 'checks': checks, 'config_sha256': native.sha(config)})
    model = load('gt06_repair_publication', STUDIO / 'godot-addon/publication_owner.py')
    validation = model._load('validation_owner')
    factory = validation.factory
    initial = factory.compose(factory.DEFAULT_SCENE, config,
        scene_revision='sha256:' + native.sha(factory.DEFAULT_SCENE),
        engine_sha256=validation.executor.BINARY_SHA256)
    parent = output / 'owned'
    parent.mkdir()
    owner = server = None
    editors = []
    result = None
    try:
        owner = model.GodotPublicationOwner.create(parent, project_id='project.gt06.repair',
            initial_bundle=initial, editor_binary=binary, source_closure_sha256=source_closure)
        credential = owner.sessions.issue()
        server = model._load('publication_transport').PublicationTransport(owner).start()

        def call(path, body, *, control=False):
            connection = http.client.HTTPConnection('127.0.0.1',
                server.control_port if control else server.port, timeout=95)
            try:
                connection.request('POST', path, canonical_bytes(body), {
                    'Content-Type': 'application/json', 'Authorization': 'Bearer ' + credential.bearer,
                    'X-HH-Catalog': owner.contract.CATALOG_DIGEST})
                response = connection.getresponse()
                raw = response.read(1024 * 1024 + 1)
                native.need(len(raw) <= 1024 * 1024, 'REPAIR_RESPONSE_CAP')
                return response.status, parse_json(raw), raw
            finally:
                connection.close()

        before = owner.inspect()
        old_editor = owner._editor
        old_identity = old_editor.identity
        editors.append((old_editor, old_identity))
        before_script = old_editor.script_observation()
        native.write(output / 'before.json', before)
        native.write(output / 'before-script.json', before_script)
        native.write(output / 'old-editor-identity.json', old_identity)
        native.need(before_script['script']['defaults']['move_speed']['value'] == 0.0
                    and before_script['script']['disk_sha256'] == native.sha(config), 'REPAIR_OLD_NATIVE_CONFIG')
        status, lease, _ = call('/v1/lease', {'project_id': owner.project_id, 'ttl_ms': 90_000})
        native.need(status == 200, 'REPAIR_LEASE')
        replacement = native.configuration('3.0')
        payload = {'expected_generation': before['generation'],
            'expected_project_revision': before['project_revision'],
            'expected_sha256': native.sha(config), 'text': replacement.decode('utf-8')}
        command = Request(command_id='gt06.repair.move-speed', project_id=owner.project_id,
            operation='script_text.replace', lease_id=lease['lease_id'], fencing_epoch=lease['fencing_epoch'],
            expected_revision=before['revision'], target={'path': owner.contract.SCRIPT_PATH}, payload=payload,
            payload_hash='sha256:' + native.sha(canonical_bytes(payload)),
            deadline_ms=min(lease['expires_ms'], epoch_ms() + 89_000))
        native.write(output / 'request.json', command.as_dict())
        status, response, wire = call('/v1/commands', command.as_dict())
        native.write(output / 'response.json', response)
        native.write(output / 'response-wire.json', wire)
        native.need(status == 200 and response.get('status') == 'COMMITTED'
                    and response.get('code') == 'GODOT_MANAGED_SCRIPT_REPLACED'
                    and response.get('postconditions', {}).get('public_ack') is True, 'REPAIR_NOT_COMMITTED')
        new_editor = owner._editor
        new_identity = new_editor.identity
        editors.append((new_editor, new_identity))
        readback = new_editor.script_observation()
        selected = owner._journal.read_selected_bundle()
        selected_config = selected.files[owner.contract.SCRIPT_PATH]
        native.need(selected_config == replacement
                    and readback['script']['source_sha256'] == native.sha(selected_config)
                    and readback['script']['disk_sha256'] == native.sha(selected_config)
                    and readback['script']['defaults']['move_speed']['value'] == 3.0,
                    'REPAIR_SELECTED_NATIVE_MISMATCH')
        native.need(new_identity['session_id'] != old_identity['session_id']
                    and int(new_identity['creation_filetime']) > int(old_identity['creation_filetime']),
                    'REPAIR_EDITOR_SUCCESSION')
        native.write(output / 'selected-config.gd', selected_config)
        native.write(output / 'selected-manifest.json', selected.manifest_bytes)
        native.write(output / 'native-readback.json', readback)
        native.write(output / 'new-editor-identity.json', new_identity)
        native.write(output / 'after.json', owner.inspect())
        native.write(output / 'validator.json', owner._validator.snapshot())
        native.write(output / 'journal.json', owner._journal.snapshot())
        native.write(output / 'events.json', [parse_json(raw) for raw in owner._journal._state.events])
        status, retry, retry_wire = call('/v1/commands', command.as_dict())
        native.need(status == 200 and retry_wire == wire and retry == response, 'REPAIR_RETRY_CHANGED')
        status, lookup, lookup_wire = call('/v1/lookup', {'project_id': owner.project_id,
            'command_id': command.command_id}, control=True)
        native.need(status == 200 and lookup_wire == wire and lookup == response, 'REPAIR_LOOKUP_CHANGED')
        native.write(output / 'retry-response.json', retry)
        native.write(output / 'lookup-response.json', lookup)
        result = {'schema': 'HH-GT06-MANAGED-REPAIR-1', 'managed_script_repaired': True,
            'runtime_repair_proven': False, 'formal_acceptance': False,
            'fault_capture_sha256': fault_hash, 'fault_binding': fault_capture['binding'],
            'before_config_sha256': native.sha(config), 'selected_config_sha256': native.sha(selected_config),
            'response_sha256': native.sha(wire), 'selected_project_revision': selected.project_revision,
            'source_closure_sha256': source_closure}
    finally:
        # Preserve all owners on any failed drain; the outer bounded process
        # owns the complete tree, while each EditorOwner checks its own identity.
        failures = []
        for resource in (server, owner):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as exc:
                    failures.append(exc)
        for index, (editor, identity) in enumerate(editors):
            try:
                closed = editor.close()
                model._load('editor_owner').EditorOwner._clean_closed(closed, identity['pid'])
                native.write(output / ('editor-close-' + str(index) + '.json'), closed)
            except BaseException as exc:
                failures.append(exc)
        if failures:
            raise failures[0]
    native.write(output / 'repair.json', result)
    print('HH_GT06_REPAIR_COMPLETE ' + json.dumps(result), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--fault-run', required=True)
    parser.add_argument('--fault-capture-sha256', required=True)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--binary', type=Path)
    parser.add_argument('--closure')
    args = parser.parse_args()
    for value in (args.run_id, args.fault_run):
        native.need(re.fullmatch('gt06-[a-z0-9-]{1,80}', value), 'REPAIR_RUN_ID')
    native.need(re.fullmatch('[0-9a-f]{64}', args.fault_capture_sha256), 'REPAIR_ANCHOR')
    output = STUDIO / '.local/reviews' / args.run_id
    fault = STUDIO / '.local/reviews' / args.fault_run
    if args.child:
        execute(output, fault, args.fault_capture_sha256, args.binary, args.closure)
        return 0
    output.mkdir(exist_ok=False)
    _, accepted = native.accepted_inputs()
    before = native.sources(accepted)
    digest = native.closure(before)
    native.write(output / 'source-files.json', before)
    for index, name in enumerate(before):
        native.write(output / 'source' / (str(index) + Path(name).suffix), native.read_regular(STUDIO / name))
    runner = load('gt06_repair_owned_runner', STUDIO / 'build/bootstrap/run_fixture.py')
    lock = json.loads(native.read_regular(STUDIO / 'toolchain.lock.json'))['godot']
    binary = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    native.need(native.sha(native.read_regular(binary, 256 * 1024 * 1024)) == lock['gui_sha256'], 'REPAIR_BINARY_PIN')
    env = dict(os.environ)
    env['HH_STUDIO_LINUX_GODOT'] = str(STUDIO / '.local/tooling/godot-4.7.2-stable-linux/Godot_v4.7.2-stable_linux.x86_64')
    host = runner.run_process([sys.executable, '-B', str(Path(__file__).resolve()), '--child',
        '--run-id', args.run_id, '--fault-run', args.fault_run, '--fault-capture-sha256', args.fault_capture_sha256,
        '--binary', str(binary), '--closure', digest], cwd=STUDIO, output=output,
        timeout=240, label='repair', env=env)
    unchanged = all(native.sha(native.read_regular(STUDIO / name)) == value for name, value in before.items())
    passed = (host['exit_code'] == host['wrapper_exit_code'] == 0 and host['tree_verified']
        and not host['timed_out'] and unchanged)
    if passed:
        stdout = (output / 'repair-stdout.txt').read_bytes()
        stderr = (output / 'repair-stderr.txt').read_bytes()
        report = json.loads(native.read_regular(output / 'repair.json'))
        markers = [json.loads(row.split(' ', 1)[1]) for row in stdout.decode('utf-8').splitlines()
            if row.startswith('HH_GT06_REPAIR_COMPLETE ')]
        passed = (not stderr and not re.search(rb'\b(?:WARNING|ERROR)\b|\bError:', stdout)
                  and len(markers) == 1 and markers[0] == report)
    artifacts = {p.name: native.sha(native.read_regular(p)) for p in output.iterdir()
        if p.is_file() and p.name not in ('capture.json',) and p.stat().st_size > 0}
    native.write(output / 'capture.json', {'schema': 'HH-GT06-REPAIR-CAPTURE-1', 'host': host,
        'source_unchanged': unchanged, 'source_closure_sha256': digest, 'completed': passed,
        'artifacts': artifacts, 'formal_acceptance': False})
    print(json.dumps({'completed': passed, 'host': host}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
