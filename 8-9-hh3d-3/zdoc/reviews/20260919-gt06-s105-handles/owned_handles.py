"""Bounded S105 handle-attribution runner.

This runner is diagnostic-only.  It imports the frozen S103 pin verifier,
creates a disposable child, and captures at most two PSS snapshots only after
the original screen gate has run.  The original gate is never changed and a
prefix can never become an acceptance sample.
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import textwrap
import time

HERE = Path(__file__).resolve().parent
HH3D = HERE.parents[2]
STUDIO = HH3D / 'studio'
S103 = HH3D / 'zdoc/reviews/20260919-gt06-s103-status-gap/owned_prefix.py'
_RUN_ID = re.compile(r'gt06-s105-handles-[a-z0-9][a-z0-9-]{0,30}\Z')
PREFIX_COUNT = 6
PREFLIGHT_TIMEOUT_SECONDS = 180
PREFIX_TIMEOUT_SECONDS = 1200


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError('S105_MODULE_SPEC')
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise RuntimeError('S105_EVIDENCE_READBACK')


def _child_code(overlay: bytes, limit: int) -> str:
    if limit not in (1, PREFIX_COUNT):
        raise ValueError('S105_LIMIT')
    encoded = base64.b64encode(overlay).decode('ascii')
    adapter_dir = str(HERE).replace('\\', '/')
    return textwrap.dedent(f'''\
        import base64, hashlib, importlib.util, json, os, sys
        from pathlib import Path
        root = Path(sys.argv[1]).resolve()
        studio = root.parents[2]
        sys.path.insert(0, str(studio.parent))
        for name in ('bundle_staging', 'bundle_v2', 'fixture_profile'):
            path = studio / 'godot-addon' / (name + '.py')
            spec = importlib.util.spec_from_file_location('_s105_' + name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
        from studio.tests.replay import run_benchmark_campaign as campaign
        adapter_spec = importlib.util.spec_from_file_location(
            '_s105_pss_adapter', Path(r'{adapter_dir}') / 'pss_adapter.py')
        adapter = importlib.util.module_from_spec(adapter_spec)
        adapter_spec.loader.exec_module(adapter)
        overlay = base64.b64decode({encoded!r})
        overlay_sha = {hashlib.sha256(overlay).hexdigest()!r}
        campaign._s105_root = root
        campaign._s105_probe = None
        campaign._s105_captures = 0
        campaign._s105_original_screen = campaign.screen_sample
        original_prepare = campaign.prepare
        def diagnostic_prepare(project, factory, trusted, binding):
            initial = original_prepare(project, factory, trusted, binding)
            target = project / 'addons/hh_benchmark/benchmark_native.gd'
            temp = target.with_name(target.name + '.s105-tmp')
            if temp.exists():
                raise RuntimeError('S105_TEMP_EXISTS')
            with temp.open('xb') as stream:
                stream.write(overlay); stream.flush(); os.fsync(stream.fileno())
            try:
                temp.replace(target)
            finally:
                if temp.exists(): temp.unlink()
            if hashlib.sha256(target.read_bytes()).hexdigest() != overlay_sha:
                raise RuntimeError('S105_OVERLAY_READBACK')
            initial['addons/hh_benchmark/benchmark_native.gd'] = overlay_sha
            return initial
        campaign.prepare = diagnostic_prepare
        original_open_probe = campaign.open_probe
        def diagnostic_open_probe(owner, executable):
            probe = original_open_probe(owner, executable)
            campaign._s105_probe = probe
            return probe
        campaign.open_probe = diagnostic_open_probe
        def capture_after_gate(sample, baseline, gate_error=None):
            if campaign._s105_captures >= 2:
                raise RuntimeError('S105_CAPTURE_LIMIT')
            if campaign._s105_probe is None:
                raise RuntimeError('S105_PROBE_MISSING')
            index = int(sample['index'])
            payload = {{
                'schema': 'gt06-s105-pss-gate-snapshot-v1',
                'run_id': json.loads((campaign._s105_root / 'context.json').read_bytes())['run_id'],
                'index': index,
                'source_closure_sha256': json.loads((campaign._s105_root / 'context.json').read_bytes())['source_closure_sha256'],
                'profile_sha256': json.loads((campaign._s105_root / 'context.json').read_bytes())['profile_sha256'],
                'sample_sha256': hashlib.sha256(json.dumps(
                    sample, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                'original_gate_recorded': gate_error is None or gate_error == 'CAMPAIGN_RETAINED_COUNTER_GROWTH',
                'original_gate_error': gate_error,
                'capture': adapter.capture_owned(campaign._s105_probe),
                'formal_acceptance': False, 'eligible_for_dataset': False,
            }}
            suffix = 'batch-{{:02d}}-after-gate.json'.format(index)
            campaign.write(campaign._s105_root / 'pss' / suffix, payload)
            campaign._s105_captures += 1
        def diagnostic_screen(sample, baseline):
            try:
                campaign._s105_original_screen(sample, baseline)
            except BaseException as error:
                code = getattr(error, 'code', type(error).__name__)
                if sample['index'] == 5 and code == 'CAMPAIGN_RETAINED_COUNTER_GROWTH':
                    capture_after_gate(sample, baseline, code)
                raise
            if sample['index'] == 4:
                capture_after_gate(sample, baseline)
            if sample['index'] >= {limit - 1}:
                error = RuntimeError('S105_PREFIX_BOUNDARY')
                error.code = 'S105_PREFIX_BOUNDARY'
                raise error
        campaign.screen_sample = diagnostic_screen
        campaign.run_child(root)
    ''').strip() + '\n'


def run(run_id: str, *, limit: int, timeout_seconds: int) -> dict:
    if not _RUN_ID.fullmatch(run_id):
        raise ValueError('S105_RUN_ID')
    if limit not in (1, PREFIX_COUNT):
        raise ValueError('S105_LIMIT')
    s103 = _load(S103, 's105_s103_owned_prefix')
    pins = s103.verify_pins()
    overlay = s103.generated_overlay()
    root = (STUDIO / '.local/reviews' / run_id).resolve()
    if not root.is_relative_to(STUDIO.resolve()) or root.exists():
        raise RuntimeError('S105_ROOT')
    root.mkdir(parents=True)
    child = HERE / 'owned' / (run_id + '.py')
    child.parent.mkdir(parents=True, exist_ok=True)
    code = _child_code(overlay, limit).encode()
    with child.open('xb') as stream:
        stream.write(code); stream.flush(); os.fsync(stream.fileno())
    if child.read_bytes() != code:
        raise RuntimeError('S105_CHILD_READBACK')
    context = {
        'schema': 'gt06-s105-owned-handles-context-v1', 'run_id': run_id,
        'source_files': pins['sources'],
        'source_closure_sha256': pins['source_closure_sha256'],
        'profile_sha256': pins['profile_sha256'],
        'generated_overlay_sha256': hashlib.sha256(overlay).hexdigest(),
        'child_script_sha256': hashlib.sha256(code).hexdigest(),
        'formal_acceptance': False, 'eligible_for_dataset': False,
        'limit_batches': limit, 'capture_boundaries': [4, 5] if limit == PREFIX_COUNT else [],
    }
    _write(root / 'context.json', context)
    _write(root / 'source-files.json', pins['sources'])
    from studio.tests.replay.benchmark_job import BenchmarkProcess
    owner = None; process_code = None; timed_out = False; started = time.monotonic()
    try:
        owner = BenchmarkProcess([sys.executable, '-B', str(child), str(root)],
            cwd=root, output=root / 'host-owner', source_root=STUDIO,
            source_files=pins['sources'], binary_sha256=pins['python_sha256'], campaign_host=True)
        while True:
            process_code = owner.tick()
            if process_code is not None:
                break
            if time.monotonic() - started > timeout_seconds:
                timed_out = True
                break
            time.sleep(.25)
    finally:
        if owner is not None:
            owner.close()
    failure = root / 'child-failure.json'
    terminal = root / 'child-terminal-cleanup.json'
    process_exit = root / 'host-owner/process-exit.json'
    terminal_value = json.loads(terminal.read_bytes()) if terminal.is_file() else None
    result = {
        'schema': 'gt06-s105-owned-handles-result-v1', 'run_id': run_id,
        'limit_batches': limit, 'formal_acceptance': False, 'eligible_for_dataset': False,
        'engine_started': True, 'timed_out': timed_out, 'child_wrapper_exit': process_code,
        'source_closure_sha256': pins['source_closure_sha256'], 'profile_sha256': pins['profile_sha256'],
        'child_failure_present': failure.is_file(), 'child_terminal_cleanup_present': terminal.is_file(),
        'owner_process_exit_present': process_exit.is_file(),
        'pss_snapshots': sorted(str(p.relative_to(root)).replace('\\','/')
                                for p in (root / 'pss').glob('*.json')) if (root/'pss').is_dir() else [],
        'terminal_errors': terminal_value.get('errors', []) if isinstance(terminal_value, dict) else ['MISSING_TERMINAL'],
    }
    result['status'] = ('GATE_RECORDED' if result['child_failure_present'] and
                        result['child_terminal_cleanup_present'] and result['owner_process_exit_present'] and
                        not result['terminal_errors'] else 'INCOMPLETE')
    _write(root / 'diagnostic-result.json', result)
    return result


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--preflight', action='store_true')
    group.add_argument('--prefix', action='store_true')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args(argv)
    if args.check:
        s103 = _load(S103, 's105_s103_owned_prefix_check')
        value = s103.plan('gt06-s103-prefix-static')
        print(json.dumps({'status': 'STATIC_OK', 'formal_acceptance': False,
                          'eligible_for_dataset': False, 'pins': value}, sort_keys=True))
        return 0
    value = run(args.run_id, limit=1 if args.preflight else PREFIX_COUNT,
                timeout_seconds=PREFLIGHT_TIMEOUT_SECONDS if args.preflight else PREFIX_TIMEOUT_SECONDS)
    print(json.dumps(value, sort_keys=True))
    return 0 if value['status'] == 'GATE_RECORDED' else 3


if __name__ == '__main__':
    raise SystemExit(main())
