"""Verify the S48 editor/publication/Linux diagnostic checkpoint. This is not GT-03 acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys

AUDIT = Path(__file__).resolve().parent
ROOT = AUDIT.parents[2]
STUDIO = ROOT / 'studio'
PACKAGE = AUDIT.parent / '20260917-gt03-s48-editor-02'
LINUX = AUDIT.parent / '20260917-gt03-s48-linux-02'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def need(value, message):
    if not value:
        raise ValueError(message)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def verify_linux(files, closure):
    manifest = read(LINUX / 'source-closure.json')
    need(manifest['files'] == files and manifest['source_closure_sha256'] == closure,
         'Linux/editor complete source closures differ')
    for name, digest in files.items():
        need(sha(LINUX / 'source/studio' / name) == digest, 'Linux source mismatch: ' + name)
    source = LINUX / 'source/studio'
    probe = module('s48_frozen_linux_probe', source / 'tests/godot/run_linux_probe.py')
    fixtures = module('s48_frozen_linux_fixtures', source / 'tests/godot/linux_probe_fixtures.py')
    executor = module('s48_frozen_linux_executor', source / 'godot-addon/linux_executor.py')
    capture = read(LINUX / 'capture.json')
    need(capture['source_closure_sha256'] == closure and capture['source_unchanged'] is True,
         'Linux capture source mismatch')
    need(set(capture['cases']) == set(fixtures.FIXTURES) and len(capture['cases']) == 11,
         'Linux fixture omitted')
    for flag in ('sandbox_acceptance', 'public_ack', 'validation_attribution_proven'):
        need(capture.get(flag) is False, 'Linux diagnostic overclaims acceptance')
    for name, fixture in fixtures.FIXTURES.items():
        case = {**fixture, 'scene': fixtures.SCENE, 'project': executor.PROJECT_TEMPLATE}
        destination = LINUX / name
        observed = probe.resume_case(destination, LINUX / (name + '-observation.json'), case,
                                     name=name, binding=manifest)
        need(observed == capture['cases'][name] and observed['fixture_observed'] is True,
             'Linux raw case does not prove diagnostic expectation: ' + name)
        result = read(destination / 'result.json')
        host = read(destination / 'engine-host.json')
        need(host == result['command_host'] == result['commandhost'], 'Linux host summary differs from raw capture')
        actual_stdout = (destination / host['stdout']).read_bytes()
        actual_stderr = (destination / host['stderr']).read_bytes()
        need(all(len(raw) <= host['stream_cap_bytes_each'] for raw in (actual_stdout, actual_stderr)),
             'Linux stream bytes exceed capture cap')
        created = read(destination / 'created-inspect-stdout.txt')[0]
        exited = read(destination / 'cleanup-inspect-stdout.txt')[0]
        need(executor._owned_identity(created, result['run_id'], result['container_id']), 'Linux created identity')
        # Normal/timeout paths settle before cleanup. The raw final daemon
        # observation must agree with the result, not only a caller exit field.
        need(exited['State'] == result['container_state'] == result['state'], 'Linux actual exit state mismatch')
        need(executor._owned_identity(exited, result['run_id'], result['container_id']), 'Linux exited identity')
        mounts = {row['Destination']: Path(row['Source']) for row in created['Mounts']}
        image = read(destination / 'image-stdout.txt')[0]
        executor._validate_inspect(created, name=result['run_id'], container_id=result['container_id'],
            mode=case['mode'], tool=mounts['/tool'], snapshot=mounts['/project'],
            image_environment=image['Config']['Env'])
        need(read(destination / 'owned-remove-host.json')['exit_code'] == 0, 'Linux removal failed')
        gone = read(destination / 'removed-inspect-host.json')
        need(gone['exit_code'] == 1 and gone['job_active_count'] == 0 and gone['timed_out'] is False,
             'Linux missing removal observation')
        message = (destination / gone['stderr']).read_text(encoding='utf-8').lower()
        need('no such object: ' + result['container_id'] in message, 'Linux missing exact removed ID')
    return {'fixtures': len(fixtures.FIXTURES), 'public_ack': False, 'sandbox_acceptance': False,
            'validation_attribution_proven': False}


def host(value):
    captured = read(PACKAGE / value['host'])
    need(type(captured.get('target_pid')) is int and captured['target_pid'] > 0, 'missing actual child PID')
    need(captured.get('exit_code') == value.get('exit_code') == value.get('wrapper_exit_code') == 0, 'host exit mismatch')
    need(captured['target_pid'] == value.get('target_pid'), 'host PID mismatch')
    need(value.get('timed_out') is False and value.get('tree_verified') is True, 'unclean process ownership')


def verify():
    manifest = read(PACKAGE / 'source-closure.json')
    files = manifest['files']
    current_runner = module('gt03_current_runner', STUDIO / 'tests/godot/run_editor_probe.py')
    need(current_runner.inputs() == files, 'working source is not this frozen checkpoint')
    source = PACKAGE / 'source/studio'
    for name, digest in files.items():
        need(sha(source / name) == digest, 'frozen source mismatch: ' + name)
    owned = module('gt03_frozen_owned_runner', source / 'build/bootstrap/run_fixture.py')
    closure = owned.source_closure_sha256(files)
    need(closure == manifest['source_closure_sha256'], 'closure mismatch')
    checks = module('gt03_frozen_checks', source / 'tests/godot/evidence_checks.py')
    capture = read(PACKAGE / 'capture.json')
    need(capture['source_closure_sha256'] == closure, 'capture closure mismatch')
    for flag in ('passed', 'source_unchanged', 'snapshot_unchanged', 'binary_unchanged', 'temporary_removed'):
        need(capture.get(flag) is True, 'capture flag not true: ' + flag)
    for flag in ('production_save_verified', 'hostile_script_sandbox_verified'):
        need(capture.get(flag) is False, 'unsupported scope claimed: ' + flag)
    lock = read(source / 'toolchain.lock.json')['godot']
    need(capture['godot_sha256'] == lock['gui_sha256'], 'unlocked Godot binary')
    unit = capture['unit']
    host(unit['host'])
    unit_stdout = (PACKAGE / unit['host']['stdout']).read_text(encoding='utf-8')
    markers = [json.loads(line[len('GT03_UNIT_COMPLETE '):]) for line in unit_stdout.splitlines()
               if line.startswith('GT03_UNIT_COMPLETE ')]
    need(markers == [unit['counts']], 'unit marker/count mismatch')
    counts = unit['counts']
    need(counts['run'] == 130 and all(counts[key] == 0 for key in ('failures', 'errors', 'skips')), 'unit count/failure mismatch')
    unit_stderr = (PACKAGE / unit['host']['stderr']).read_text(encoding='utf-8')
    need(re.findall(r'Ran (\d+) tests? in ', unit_stderr) == [str(counts['run'])], 'unittest stderr count mismatch')
    need(unit_stderr.rstrip().endswith('OK'), 'unittest did not report success')
    need([lane['mode'] for lane in capture['lanes']] == ['edit', 'reopen', 'contract'], 'missing engine lane')
    expected_execution = read(PACKAGE / 'executed-inputs.json')
    frozen_mapping = {
        'addons/hh_studio/plugin.gd': 'godot-addon/addons/hh_studio/plugin.gd',
        'addons/hh_studio/scene_commands.gd': 'godot-addon/addons/hh_studio/scene_commands.gd',
        'addons/hh_studio/jcs_godot.gd': 'protocol/jcs_godot.gd',
        'addons/hh_studio/diagnostic_plugin.gd': 'tests/godot/diagnostic_plugin.gd',
        'tests/editor_probe.gd': 'tests/godot/editor_probe.gd',
    }
    for runtime_name, source_name in frozen_mapping.items():
        need(expected_execution[runtime_name] == files[source_name], 'runtime source copy mismatch')
    results = {}
    for lane in capture['lanes']:
        name = lane['mode']
        host(lane['host'])
        for flag in ('passed', 'clean_log', 'result_valid', 'execution_unchanged', 'exact_reopen_revision'):
            need(lane.get(flag) is True, name + ' invalid ' + flag)
        need(lane['execution_before'] == lane['execution_after'] == expected_execution, 'executed input map mismatch')
        result = read(PACKAGE / (name + '-result.json'))
        progress = [json.loads(line) for line in (PACKAGE / (name + '-progress.jsonl')).read_text(encoding='utf-8').splitlines()]
        need(checks.validate_result(name, result, progress) is True, 'invalid engine evidence')
        streams = [name + '-engine.log', lane['host']['stdout'], lane['host']['stderr']]
        for stream in streams:
            text = (PACKAGE / stream).read_text(encoding='utf-8', errors='strict')
            need(re.search(r'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', text) is None, 'unclean engine stream')
        results[name] = result
    need(results['edit']['saved_revision'] == results['reopen']['saved_revision'], 'reopened full-state revision differs')
    vectors = read(PACKAGE / 'contract-vectors.json')
    need(vectors['snapshot_mode'] == 'SUPPLIED_NATIVE_OBSERVATION' and vectors['file_hashes_observed'] is True, 'synthetic vector source')
    need(vectors['runtime_authorized'] is False and vectors['acceptance'] is False, 'vector overclaim')
    need(len(vectors['rejected']) == 14 and all(row['engine_projection'] is None for row in vectors['rejected']), 'invalid host wire reached engine')
    need(vectors['schema'] == 'hh-gt03-contract-vectors-2', 'legacy contract vectors')
    bundle = read(PACKAGE / 'contract-base-bundle.json')
    need(vectors['context']['project_revision'] == bundle['project_revision'], 'wire project revision mismatch')
    linux = verify_linux(files, closure)
    artifacts = read(AUDIT / 'artifact-manifest.json')['files']
    for name, digest in artifacts.items():
        path = ROOT / name
        need(path.resolve().is_relative_to(ROOT.resolve()) and sha(path) == digest, 'artifact mismatch: ' + name)
    summary = {'status': 'S48_DIAGNOSTIC_CHECKPOINT_VERIFIED', 'formal_acceptance': False,
               'source_closure_sha256': closure, 'source_files': len(files),
               'artifacts': len(artifacts), 'unit': counts, 'linux': linux,
               'engine_checks': {name: len(value['checks']) for name, value in results.items()}}
    return summary


if __name__ == '__main__':
    summary = verify()
    if len(sys.argv) == 2:
        ref = sys.argv[1]
        need(ref in ('index', 'HEAD'), 'expected index or HEAD')
        repo = ROOT.parent
        names = [ROOT.name + '/studio/' + name for name in read(PACKAGE / 'source-closure.json')['files']]
        names += [ROOT.name + '/' + name for name in read(AUDIT / 'artifact-manifest.json')['files']]
        # One bounded batch avoids thousands of Windows process launches while
        # retaining exact blob-byte verification (including binary/raw logs).
        selectors = [':' + name if ref == 'index' else 'HEAD:' + name for name in names]
        need(all('\n' not in item and '\r' not in item for item in selectors), 'invalid Git selector')
        completed = subprocess.run(['git', 'cat-file', '--batch'], cwd=repo,
            input=('\n'.join(selectors) + '\n').encode('utf-8'), capture_output=True,
            timeout=60, check=True)
        raw, offset = completed.stdout, 0
        for name in names:
            end = raw.find(b'\n', offset)
            need(end >= offset, 'missing Git blob header')
            fields = raw[offset:end].split()
            need(len(fields) == 3 and fields[1] == b'blob' and fields[2].isdigit(), 'invalid Git blob header')
            size = int(fields[2])
            offset = end + 1
            blob = raw[offset:offset + size]
            need(len(blob) == size and raw[offset + size:offset + size + 1] == b'\n', 'truncated Git blob')
            need(blob == (repo / name).read_bytes(), 'Git byte mismatch: ' + name)
            offset += size + 1
        need(offset == len(raw), 'extra Git batch bytes')
        summary.update(git_bytes=ref, verified_files=len(names))
        if ref == 'HEAD':
            summary['git_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    destination = AUDIT / ('verification.json' if len(sys.argv) == 1 else 'git-byte-verification-' + sys.argv[1] + '.json')
    destination.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))
