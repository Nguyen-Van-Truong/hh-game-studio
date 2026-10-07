"""Fail-closed offline conformance check for the two GT09 gameplay fixtures.

This reads only completed O2 publication evidence.  It never starts Godot,
Blender, Docker, or a replay, and it never turns AUTHORITY=0 diagnostics into
an acceptance signature.  A report is useful for finding the next gap; the
coordinator and two independent critics still own GT09 acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOM_REQUIRED = {
    'ticks': 60, 'movement_observed': True, 'camera_follow': True,
    'switch_used': True, 'pickup_collected': True, 'ui_visible': True,
    'input_trace_ok': True, 'replay_hash_equal': True,
    'avatar_asset_loaded': True, 'sprite_asset_loaded': True,
    'perf_samples': 60, 'perf_budget_ms': 33.333,
    'perf_budget_ok': True, 'topology_ok': True,
    'topology_components': {
        'avatar_shape': True, 'trigger_shape': True, 'pickup_shape': True,
        'camera': True, 'hud': True,
    },
}

ARENA_REQUIRED = {
    'ticks': 150, 'health': 4, 'bot_health': 0, 'pickups': 1, 'hits': 1,
    'jump_started': True, 'apex_seen': True, 'landed': True,
    'wall_blocked': True, 'input_released': True, 'stopped': True,
    'camera_follow': True, 'hud_win': True, 'round_won': True,
    'avatar_asset_loaded': True, 'sprite_asset_loaded': True,
    'replay_hash_equal': True, 'checkpoint_reload_observed': True,
    'muzzle_flash_count': 1, 'hit_ray_count': 1,
    'dust_burst_count': 1, 'explosion_count': 1,
    'effect_kind_count': 4, 'effect_emitters_readback': True,
    'effect_particles_peak': 30, 'effect_particle_limit': 64,
    'effect_budget_ok': True,
    'perf_samples': 150, 'perf_budget_ms': 33.333,
    'perf_budget_ok': True,
}


def _load(path: Path) -> dict:
    value = json.loads(path.read_text(encoding='utf-8'))
    if type(value) is not dict:
        raise ValueError(f'object required: {path}')
    return value


def _row(raw: Path) -> dict:
    result = _load(raw / 'result.json')
    observation = _load(raw / 'native-observation.json')
    return {'raw': str(raw), 'result': result, 'observation': observation}


def _check(name: str, row: dict) -> list[str]:
    result = row['result']
    observation = row['observation']
    errors: list[str] = []
    if result.get('status') != 'DIAGNOSTIC_PASS':
        errors.append(f'{name}:result_status:{result.get("status")}')
    if result.get('authority') != 0 or result.get('public_ack') is not False:
        errors.append(f'{name}:authority_or_ack')
    handoff = result.get('blender_handoff')
    if result.get('blender_handoff_verified') is not True:
        errors.append(f'{name}:result_blender_handoff_verified')
    elif (type(handoff) is not dict or handoff.get('schema') != 'hh-blender-godot-handoff-1'
          or handoff.get('authority') != 0 or handoff.get('public_ack') is not False
          or not isinstance(handoff.get('producer_run_id'), str)
          or not isinstance(handoff.get('manifest_sha256'), str)
          or type(handoff.get('artifact')) is not dict
          or handoff['artifact'].get('path') != 'scene.glb'
          or not isinstance(handoff['artifact'].get('sha256'), str)
          or not isinstance(handoff['artifact'].get('bytes'), int)
          or type(handoff.get('producer_receipts')) is not dict
          or set(handoff['producer_receipts']) != {
              'queue-native.json', 'native-child.json', 'native-host.json'}):
        errors.append(f'{name}:blender_handoff_receipt')
    for key in ('native_run_count', 'native_fixture_observed', 'live_retry_equal',
                'reopened_retry_equal', 'durable_state_unchanged', 'source_unchanged'):
        if result.get(key) != (1 if key == 'native_run_count' else True):
            errors.append(f'{name}:result_{key}')
    required_observations = ('fixture_observed', 'confinement_lifecycle_observed',
                             'supervisor_binding_verified')
    if name in ('arena_2d', 'room_3d'):
        required_observations += ('asset_import_observed',)
    for key in required_observations:
        if observation.get(key) is not True:
            errors.append(f'{name}:observation_{key}')
    details = observation.get('untrusted_child_observation')
    if type(details) is not dict:
        errors.append(f'{name}:child_details_missing')
    elif name == 'room_3d':
        for key, expected in ROOM_REQUIRED.items():
            if details.get(key) != expected:
                errors.append(f'{name}:state_{key}')
    elif name == 'arena_2d':
        for key, expected in ARENA_REQUIRED.items():
            if details.get(key) != expected:
                errors.append(f'{name}:state_{key}')
    return errors


def build_report(arena: Path, room: Path) -> dict:
    rows = {'arena_2d': _row(arena), 'room_3d': _row(room)}
    errors = _check('arena_2d', rows['arena_2d']) + _check('room_3d', rows['room_3d'])
    closures = {row['result'].get('source_closure_sha256') for row in rows.values()}
    if len(closures) != 1 or None in closures:
        errors.append('source_closure_mismatch')
    handoffs = [rows[name]['result'].get('blender_handoff')
                for name in ('arena_2d', 'room_3d')]
    if any(type(value) is not dict for value in handoffs):
        errors.append('blender_handoff_missing')
        handoff_summary = None
    else:
        identity = {(value.get('producer_run_id'), value.get('manifest_sha256'),
                     value.get('artifact', {}).get('sha256')) for value in handoffs}
        if len(identity) != 1:
            errors.append('blender_handoff_identity_mismatch')
        handoff_summary = {
            'producer_run_id': handoffs[0].get('producer_run_id'),
            'manifest_sha256': handoffs[0].get('manifest_sha256'),
            'artifact_sha256': handoffs[0].get('artifact', {}).get('sha256'),
        }
    return {
        'schema': 'hh-gt09-fixture-conformance-1',
        'authority': 0,
        'status': 'CANDIDATE_PASS' if not errors else 'INCOMPLETE',
        'acceptance': False,
        'source_closure_sha256': next(iter(closures)) if len(closures) == 1 else None,
        'fixtures': {name: {
            'raw': row['raw'],
            'run_id': row['result'].get('run_id'),
            'result_sha256': hashlib.sha256(
                (Path(row['raw']) / 'result.json').read_bytes()).hexdigest(),
            'observation_sha256': hashlib.sha256(
                (Path(row['raw']) / 'native-observation.json').read_bytes()).hexdigest(),
        } for name, row in rows.items()},
        'errors': errors,
        'blender_handoff': handoff_summary,
        'requirements': {
            '2d_arena': 'native input/physics/pickup/bot/replay/save-readback fixture',
            '3d_room': 'native CharacterBody3D/Area3D/Camera3D/assets/input/replay/perf fixture',
            'blender_handoff': ('bound to one native Blender export and verified by both fixtures'
                                if handoff_summary and 'blender_handoff_missing' not in errors
                                and 'blender_handoff_identity_mismatch' not in errors
                                else 'pending'),
            'owner_playtest': 'pending',
            'critics': 'pending two independent critics on one final hash',
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--arena', type=Path, required=True)
    parser.add_argument('--room', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    report = build_report(args.arena, args.room)
    encoded = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8', newline='\n')
    print(encoded, end='')
    return 0 if report['status'] == 'CANDIDATE_PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
