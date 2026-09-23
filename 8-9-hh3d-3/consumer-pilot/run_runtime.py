"""Freeze a pilot runtime consuming retained, verified GT03/GT04 artifacts.

Preparation is the default. --run launches only parse and runtime stages in
sequence, both bounded and Job-owned. No Blender or editor authoring rerun.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

from collect_existing import need, read, safe, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STUDIO = ROOT / 'studio'
CHECKS = {'authored_map_loaded', 'blender_asset_instantiated', 'movement_live_frames',
          'pause_live_frames', 'resume_live_frames', 'pickup_and_ui', 'save_via_input',
          'changed_since_save', 'load_restores_runtime', 'corrupt_latest_recovers_prior',
          'deterministic_replay_live_frames'}


def write(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def host_ok(root, host):
    raw = read(root / host['host'])
    return (host['exit_code'] == raw['exit_code'] == host['wrapper_exit_code'] == 0
            and host['target_pid'] == raw['target_pid'] and host['tree_verified'] is True
            and not host['timed_out'] and not (root / host['stderr']).read_bytes())


def verify_report(report, manifest, host):
    need(report['run_id'] == manifest['run_id'] and report['pid'] == host['target_pid'], 'runtime identity')
    need(report['map_sha256'] == manifest['inputs']['map.json']['sha256']
         and report['pickup_glb_sha256'] == manifest['inputs']['pickup.glb']['sha256'], 'runtime input bytes')
    need(report['authority'] == 0 and report['gt06_acceptance'] is False, 'pilot scope')
    need(set(report['checks']) == CHECKS and all(v is True for v in report['checks'].values())
         and report['passed'] is True, 'all runtime checks required')
    paused = report['observations']['pause']
    need(paused['before'] == paused['after'] and paused['frames_advanced'] >= 12, 'live pause')
    first, second, changed = report['observations']['replays']
    need(first == second and first['frames'] == 60 and first['final']['collected'] is True
         and re.fullmatch('[0-9a-f]{64}', first['sha256']) and first['sha256'] != changed['sha256'], 'runtime replay/control')


def verify_terminal(output, manifest, hosts):
    for label in ('parse', 'runtime'):
        need(host_ok(output, hosts[label]), label + ' exit/stderr/tree failed')
    project = output / 'project'
    for name, digest in manifest['runtime_sources'].items():
        need(sha(safe(project, name)) == digest, 'executed runtime source drift')
    for name, row in manifest['inputs'].items():
        need(sha(safe(project / 'input', name)) == row['sha256'], 'executed input drift')
    report_path = project / 'out/report.json'
    verify_report(read(report_path), manifest, hosts['runtime'])
    # Windows GUI builds write print() to Godot's own log, not inherited stdout.
    # The user directory belongs to this fresh run and is never reused.
    log = output / 'godot-user/Roaming/Godot/app_userdata/HH Consumer Pilot/logs/godot.log'
    lines = log.read_text(encoding='utf-8').splitlines()
    need(lines.count('HH_CONSUMER_PILOT_PASS') == 1, 'unique completion marker in engine log')
    need(not any(re.search(r'\b(?:ERROR|WARNING|SCRIPT ERROR)\b', line) for line in lines), 'engine log diagnostics')
    return {'report_sha256': sha(report_path), 'engine_log_sha256': sha(log)}


def verify_existing(output, destination):
    need(not destination.exists(), 'fresh derived result required')
    manifest, original = read(output / 'manifest.json'), read(output / 'result.json')
    need(original['run_id'] == manifest['run_id'] and original['source_unchanged'] is True
         and original['inputs_unchanged'] is True, 'original run binding')
    verified = verify_terminal(output, manifest, original['hosts'])
    result = {'run_id': manifest['run_id'], 'authority': 0, 'engine_started': False,
        'runtime_checks_passed': True, 'pilot_acceptance': False, 'gt06_acceptance': False,
        'original_result_sha256': sha(output / 'result.json'), 'original_failure': original.get('failure'),
        'manifest_sha256': sha(output / 'manifest.json'), **verified,
        'reason': 'Read actual GUI engine log; preserve original stdout collector failure and all upstream gaps.'}
    write(destination, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--binding', type=Path, required=True)
    parser.add_argument('--godot-raw', type=Path, required=True)
    parser.add_argument('--blender-raw', type=Path, required=True)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    need(re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id), 'safe run ID')
    output = HERE / '.local/runs' / args.run_id
    need(not output.exists(), 'fresh runtime ID required')
    binding = read(args.binding)
    need(binding['authority'] == 0 and binding['engine_started'] is False, 'derived artifact binding')
    roots = {'godot': args.godot_raw.resolve(), 'blender': args.blender_raw.resolve()}
    # Verify exact raw evidence used for the handoff before any new engine.
    for lane, files in binding['raw_manifest'].items():
        for relative, digest in files.items():
            need(sha(safe(roots[lane], relative)) == digest, 'retained raw drift: ' + relative)
    binary_lock = read(STUDIO / 'toolchain.lock.json')
    local = read(STUDIO / '.local/toolchain.local.json')
    binary = Path(local['godot_console']).with_name(binary_lock['godot']['gui_executable'])
    need(sha(binary) == binary_lock['godot']['gui_sha256'], 'Godot GUI binary pin')
    inputs = {'map.json': roots['godot'] / 'map.json',
              'pickup.glb': safe(roots['blender'], binding['blender']['assets']['scene.glb']['path'])}
    need(sha(inputs['map.json']) == binding['godot']['map_sha256'], 'map input binding')
    need(sha(inputs['pickup.glb']) == binding['blender']['assets']['scene.glb']['sha256'], 'GLB input binding')
    output.mkdir(parents=True)
    project = output / 'project'
    (project / 'scripts').mkdir(parents=True)
    (project / 'input').mkdir()
    sources = {}
    for relative in ('project.godot', 'main.tscn', 'scripts/pilot_runtime.gd'):
        origin = HERE / relative
        shutil.copyfile(origin, project / relative)
        sources[relative] = sha(origin)
    for name, path in inputs.items():
        shutil.copyfile(path, project / 'input' / name)
    manifest = {'schema': 1, 'run_id': args.run_id, 'authority': 0, 'formal_acceptance': False,
        'runtime_sources': sources, 'driver_sha256': sha(Path(__file__)),
        'runner_sha256': sha(STUDIO / 'build/bootstrap/run_fixture.py'),
        'binding_sha256': sha(args.binding),
        'inputs': {name: {'path': str(path), 'sha256': sha(path)} for name, path in inputs.items()},
        'binary': {'path': str(binary), 'sha256': sha(binary)},
        'limits_seconds': {'parse': 30, 'runtime': 60},
        'source_scope': 'consumer-pilot only; frozen GT06 unchanged',
        'upstream_gaps': {'godot': binding['godot']['gaps'], 'blender': binding['blender']['gaps']}}
    write(output / 'manifest.json', manifest)
    if not args.run:
        print(json.dumps({'prepared': str(output), 'engine_started': False}))
        return 0
    spec = importlib.util.spec_from_file_location('owned_pilot_runner', STUDIO / 'build/bootstrap/run_fixture.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    env = runner._isolated_user_env(output)
    hosts = {}
    result = {'run_id': args.run_id, 'authority': 0, 'gt06_acceptance': False, 'pilot_acceptance': False,
              'hosts': hosts, 'runtime_checks_passed': False}
    try:
        hosts['parse'] = runner.run_process([str(binary), '--headless', '--path', str(project),
            '--check-only', '--script', 'res://scripts/pilot_runtime.gd'], cwd=project, output=output,
            timeout=30, label='parse', env=env)
        need(host_ok(output, hosts['parse']), 'bounded GDScript parse failed; retain original logs')
        hosts['runtime'] = runner.run_process([str(binary), '--headless', '--path', str(project),
            '--', '--pilot-test', '--run-id=' + args.run_id], cwd=project, output=output,
            timeout=60, label='runtime', env=env)
        need(host_ok(output, hosts['runtime']), 'runtime exit/stderr/tree failed')
        verified = verify_terminal(output, manifest, hosts)
        result['runtime_checks_passed'] = True
        result.update(verified)
    except Exception as error:
        result['failure'] = str(error)
    finally:
        result['source_unchanged'] = all(sha(HERE / name) == digest == sha(project / name) for name, digest in sources.items())
        result['inputs_unchanged'] = all(sha(project / 'input' / name) == row['sha256'] for name, row in manifest['inputs'].items())
        result['runtime_checks_passed'] &= result['source_unchanged'] and result['inputs_unchanged']
        write(output / 'result.json', result)
    print(json.dumps(result))
    return 0 if result['runtime_checks_passed'] else 1


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--verify-existing':
        print(json.dumps(verify_existing(Path(sys.argv[2]), Path(sys.argv[3]))))
    else:
        raise SystemExit(main())
