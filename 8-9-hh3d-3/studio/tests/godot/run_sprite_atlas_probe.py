"""Pinned Godot import/save/fresh-process reload of the Blender atlas.

Trusted asset diagnostic only. No adapter/public ACK or gameplay-source claim.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil

STUDIO = Path(__file__).resolve().parents[2]
SOURCES = ('build/bootstrap/run_fixture.py', 'toolchain.lock.json',
           'tests/godot/sprite_atlas_probe.gd', 'tests/godot/run_sprite_atlas_probe.py')
PROJECT = '''config_version=5
[application]
config/name="O2 atlas diagnostic"
run/main_scene="res://main.tscn"
[rendering]
renderer/rendering_method="gl_compatibility"
[threading]
worker_pool/max_threads=2
[debug]
gdscript/warnings/untyped_declaration=2
gdscript/warnings/inference_on_variant=2
'''
SCENE = '''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://main.gd" id="1"]
[node name="AtlasProbe" type="Node"]
script = ExtResource("1")
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def preflight_valid(value):
    """Check the saved launch observation, including freshness; not an O1 gate."""
    try:
        age = (datetime.now(timezone.utc) - datetime.strptime(
            value['observed_utc'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)).total_seconds()
        return (value['schema_id'] == 'hh-studio.benchmark-environment-preflight'
                and value['schema_version'] == '1.2.0' and value['pass'] is True
                and value['foreign_engines'] == [] and 0 <= age <= 120
                and type(value['available_memory_bytes']) is int
                and value['available_memory_bytes'] >= 4 * 1024**3
                and type(value['commit_total_bytes']) is int
                and type(value['commit_limit_bytes']) is int and value['commit_limit_bytes'] > 0
                and value['commit_total_bytes'] * 100 <= value['commit_limit_bytes'] * 85)
    except (KeyError, TypeError, ValueError):
        return False


def verify_samples(samples):
    """Assert native 8fps progression and pause, at fixed 60fps observation."""
    if type(samples) is not list or len(samples) != 100:
        return False
    for tick, row in enumerate(samples, 1):
        if (type(row) is not dict or set(row) != {'tick', 'delta', 'frame', 'progress', 'playing'}
                or type(row['tick']) is not int or row['tick'] != tick
                or type(row['frame']) is not int or not 0 <= row['frame'] < 4
                or type(row['playing']) is not bool or row['playing'] != (not 38 <= tick <= 49)):
            return False
        for key in ('delta', 'progress'):
            if type(row[key]) not in (float, int) or not math.isfinite(row[key]):
                return False
        if abs(row['delta'] - 1/60) > 1e-6 or not 0 <= row['progress'] <= 1:
            return False
    transitions = 0
    for previous, current in zip(samples, samples[1:]):
        # Pause starts after observation 37 and ends after 49.
        # tick 50 records the resume call itself; the first resumed advance is
        # observed at tick 51, just as input callbacks can cross a tick edge.
        active = current['tick'] not in range(38, 51)
        expected_step = 8/60 if active else 0
        observed_step = (current['frame'] + current['progress']
                         - previous['frame'] - previous['progress']) % 4
        if not math.isclose(observed_step, expected_step, abs_tol=2e-5):
            return False
        if current['frame'] != previous['frame']:
            if current['frame'] != (previous['frame'] + 1) % 4:
                return False
            transitions += 1
    return transitions >= 10


def marker(log, prefix):
    rows = [line[len(prefix):] for line in log.splitlines() if line.startswith(prefix)]
    return json.loads(rows[0]) if len(rows) == 1 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--godot', type=Path, required=True)
    parser.add_argument('--sheet', type=Path, required=True)
    parser.add_argument('--preflight', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or not re.fullmatch(r'[a-z0-9-]{1,80}', args.run_id):
        raise ValueError('FRESH_OUTPUT_AND_RUN_ID_REQUIRED')
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    binary = args.godot.resolve(strict=True)
    gui = binary.with_name(lock['gui_executable'])
    if (binary.name != lock['console_executable'] or sha(binary) != lock['console_sha256']
            or sha(gui) != lock['gui_sha256']):
        raise ValueError('PIN_HASH')
    preflight = json.loads(args.preflight.read_bytes())
    if not preflight_valid(preflight):
        raise ValueError('FRESH_PREFLIGHT_REQUIRED')
    source = {name: sha(STUDIO / name) for name in SOURCES}
    sheet_hash = sha(args.sheet)
    output.mkdir(parents=True)
    snapshot = output / 'source'
    for name in SOURCES:
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(STUDIO / name, target)
    spec = importlib.util.spec_from_file_location('atlas_bootstrap', snapshot / SOURCES[0])
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    project = output / 'project'
    project.mkdir()
    (project / 'main.gd').write_bytes((snapshot / 'tests/godot/sprite_atlas_probe.gd').read_bytes())
    (project / 'project.godot').write_text(PROJECT, encoding='utf-8')
    (project / 'main.tscn').write_text(SCENE, encoding='utf-8')
    shutil.copyfile(args.sheet, project / 'sprite_sheet.png')
    shutil.copyfile(args.preflight, output / 'preflight.json')
    immutable = {p.name: sha(p) for p in project.iterdir()}
    env = bootstrap._isolated_user_env(output)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    base = [str(binary), '--headless', '--path', str(project)]
    runs = []
    artifacts = {}
    for phase, argv in [('import', base + ['--import']),
                        ('author', base + ['--fixed-fps', '60', '--', 'author']),
                        ('reload', base + ['--fixed-fps', '60', '--', 'reload'])]:
        run = bootstrap.run_process(argv, cwd=project, output=output, timeout=45, label=phase, env=env)
        runs.append(run)
        if (run['exit_code'] != 0 or run['wrapper_exit_code'] != 0
                or run['timed_out'] or not run['tree_verified']
                or not bootstrap._streams_clean(output, [run])):
            break
        if phase == 'author':
            artifacts = {name: sha(project / 'generated' / name) for name in ('frames.tres', 'actor.tscn')}
    author = marker((output / 'author-stdout.txt').read_text(encoding='utf-8'), 'HH_ATLAS_AUTHOR ') if len(runs) >= 2 else None
    reload = marker((output / 'reload-stdout.txt').read_text(encoding='utf-8'), 'HH_ATLAS_RELOAD ') if len(runs) == 3 else None
    same_source = source == {name: sha(STUDIO / name) for name in SOURCES}
    same_snapshot = source == {name: sha(snapshot / name) for name in SOURCES}
    same_project = all(sha(project / name) == digest for name, digest in immutable.items())
    same_artifacts = bool(artifacts) and artifacts == {name: sha(project / 'generated' / name) for name in artifacts}
    hashes = {'sheet_sha256': sheet_hash, 'frames_sha256': artifacts.get('frames.tres'),
              'scene_sha256': artifacts.get('actor.tscn')}
    passed = bool(len(runs) == 3 and all(r['exit_code'] == r['wrapper_exit_code'] == 0
                  and r['tree_verified'] is True and r['timed_out'] is False for r in runs)
                  and bootstrap._streams_clean(output, runs) and same_source and same_snapshot
                  and same_project and same_artifacts and author == dict(hashes, frames=4, fps=8, loop=True)
                  and type(reload) is dict and set(reload) == set(hashes) | {'samples'}
                  and all(reload[key] == value for key, value in hashes.items())
                  and verify_samples(reload['samples'])
                  and sha(binary) == lock['console_sha256'] and sha(gui) == lock['gui_sha256'])
    report = {'schema': 'hh-o2-sprite-atlas-1', 'run_id': args.run_id, 'passed': passed,
              'authority': 0, 'public_ack': False, 'formal_acceptance': False,
              'source_files': source, 'source_closure_sha256': bootstrap.source_closure_sha256(source),
              'binary_sha256': lock['console_sha256'], 'input_sheet_sha256': sheet_hash,
              'source_unchanged': same_source, 'snapshot_unchanged': same_snapshot,
              'project_source_unchanged': same_project, 'saved_artifacts_unchanged': same_artifacts,
              'runs': runs, 'author': author, 'reload': reload}
    (output / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'run_id': args.run_id, 'passed': passed,
                      'exits': [r['exit_code'] for r in runs]}), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
