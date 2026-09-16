"""Verify the S47 trusted-editor checkpoint. This is not GT-03 acceptance."""
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
PACKAGE = AUDIT.parent / '20260916-gt03-s47-editor-08'


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
    spec.loader.exec_module(result)
    return result


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
    need(counts['run'] > 34 and all(counts[key] == 0 for key in ('failures', 'errors', 'skips')), 'unit failures/omitted evidence tests')
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
    artifacts = read(AUDIT / 'artifact-manifest.json')['files']
    for name, digest in artifacts.items():
        path = ROOT / name
        need(path.resolve().is_relative_to(ROOT.resolve()) and sha(path) == digest, 'artifact mismatch: ' + name)
    summary = {'status': 'TRUSTED_EDITOR_CHECKPOINT_VERIFIED', 'formal_acceptance': False,
               'source_closure_sha256': closure, 'source_files': len(files),
               'artifacts': len(artifacts), 'unit': counts,
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
        for name in names:
            selector = ':' + name if ref == 'index' else 'HEAD:' + name
            blob = subprocess.check_output(['git', 'show', selector], cwd=repo)
            need(blob == (repo / name).read_bytes(), 'Git byte mismatch: ' + name)
        summary.update(git_bytes=ref, verified_files=len(names))
        if ref == 'HEAD':
            summary['git_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    destination = AUDIT / ('verification.json' if len(sys.argv) == 1 else 'git-byte-verification-' + sys.argv[1] + '.json')
    destination.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary))
