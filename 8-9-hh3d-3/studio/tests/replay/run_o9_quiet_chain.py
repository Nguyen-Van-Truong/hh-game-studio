"""Gated O9 quiet-window chain for one fresh source closure.

The default operation is a read-only plan/dry-run.  ``--execute`` is the only
mode that can start the host residency with watchdog, and finally a
fresh formal Task Scheduler demand run.  Every stage gets an exclusive
receipt; a missing result, closure drift, failed metric, or status gap at or
above one second stops the chain without retrying blindly.  This coordinator
never changes O1/O4 thresholds and never marks acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))
from studio.tests.replay import run_benchmark_campaign as campaign
from studio.tests.replay import run_watchdog_soak as watchdog_soak
from studio.tests.replay import residency_metrics

SCHEMA = 'HH-GT06-O9-QUIET-CHAIN-1'
FORMAL_RE = re.compile(r'^gt06-o4-formal-([0-9]{1,2})$')
CHAIN_RE = re.compile(r'^gt06-o9-chain-[a-z0-9-]{1,15}$')
REVIEWS = STUDIO / '.local' / 'reviews'
O7_PROBE = REVIEWS / 'journal-latency-seed-20261001-03/result.json'
O7_SEEDS = REVIEWS / 'journal-latency-seed-20261001-01'
O7_REFERENCE_SOAK = REVIEWS / 'gt06-o6-soak-20261001-05'


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb', buffering=0) as stream:
        raw = (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
               + '\n').encode()
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def require(condition: bool, code: str) -> None:
    if not condition:
        raise RuntimeError(code)


def finite_nonnegative(value: object) -> bool:
    try:
        return (type(value) in (int, float) and type(value) is not bool
                and math.isfinite(value) and value >= 0)
    except (OverflowError, TypeError, ValueError):
        return False


def source_manifest() -> dict[str, str]:
    campaign.load_fixture()
    return campaign.source_files()


def context(chain_id: str, formal_id: str, files: dict[str, str]) -> dict:
    return {
        'schema': SCHEMA,
        'chain_id': chain_id,
        'formal_id': formal_id,
        'source_files': files,
        'source_closure_sha256': campaign.closure(files),
        'profile_sha256': campaign.profile.PROFILE_SHA256,
        'formal_acceptance': False,
    }


def validate_ids(chain_id: str, formal_id: str) -> None:
    require(CHAIN_RE.fullmatch(chain_id) is not None, 'CHAIN_ID')
    match = FORMAL_RE.fullmatch(formal_id)
    require(match is not None and int(match.group(1)) >= 22, 'FORMAL_ID')


def formal_id_for(chain_id: str) -> str:
    match = re.fullmatch(r'gt06-o9-chain-f([0-9]{2})-[a-z0-9]{1,5}', chain_id)
    require(match is not None, 'SCHEDULED_CHAIN_ID')
    formal_id = 'gt06-o4-formal-' + match.group(1)
    validate_ids(chain_id, formal_id)
    return formal_id


def validate_output(path: Path, chain_id: str) -> Path:
    """Keep chain receipts under the owned reviews directory and reject links."""
    reviews = REVIEWS.resolve()
    lexical = path if path.is_absolute() else (Path.cwd() / path)
    lexical = Path(os.path.abspath(os.fspath(lexical)))
    cursor = lexical
    while True:
        if cursor.exists():
            require(not cursor.is_symlink(), 'CHAIN_OUTPUT_REPARSE')
        if cursor == reviews or cursor.parent == cursor:
            break
        cursor = cursor.parent
    candidate = lexical.resolve(strict=False)
    require(candidate != reviews and candidate.name == chain_id, 'CHAIN_OUTPUT_PATH')
    try:
        relative = candidate.relative_to(reviews)
    except ValueError:
        raise RuntimeError('CHAIN_OUTPUT_PATH')
    require(relative.parts and all(part not in ('', '.', '..') for part in relative.parts),
            'CHAIN_OUTPUT_PATH')
    require(reviews.is_dir() and not reviews.is_symlink(), 'CHAIN_REVIEWS_ROOT')
    return candidate


def o7_readiness() -> dict:
    """Reject known stale control before a costly full-chain launch.

    This is a prerequisite check. Current host counters are verified separately
    after exit; the original seeds stay bound to the original control soak.
    """
    from studio.tests.replay.journal_scaling_metrics import read_retained_control
    try:
        control = read_retained_control(O7_PROBE, O7_SEEDS, source_root=STUDIO,
                                        reference_soak=O7_REFERENCE_SOAK)
        evidence = control['evidence_binding']
        ready = all(control['checks'].values())
        return {'ready': ready, 'code': None if ready else 'O7_CONTROL_METRICS_FAIL',
                'probe_sha256': sha(O7_PROBE), 'reference_soak': O7_REFERENCE_SOAK.name,
                'current_probe_source_closure': evidence['current_probe_source_closure'],
                'reviewed_byte_normalizations': evidence['reviewed_byte_normalizations'],
                'checks': control['checks'], 'formal_acceptance': False}
    except (OSError, ValueError, KeyError, TypeError) as error:
        return {'ready': False, 'code': 'O7_CONTROL_UNAVAILABLE',
                'reason': str(error) if type(error) is ValueError else type(error).__name__,
                'formal_acceptance': False}


def dry_run(chain_id: str, formal_id: str, root: Path, *, host_only=False) -> dict:
    validate_ids(chain_id, formal_id)
    root = validate_output(root, chain_id)
    require(not root.exists(), 'CHAIN_OUTPUT_EXISTS')
    readiness = o7_readiness()
    files = source_manifest()
    value = context(chain_id, formal_id, files)
    value.update({'mode': 'dry-run', 'stage_order': [
        'O4.1_CPU_MINUTE', 'O9.4C_HOST_RESIDENCY_WITH_WATCHDOG',
        'O6.3_METRICS', 'O4.1_CPU_MINUTE_FINAL', 'FORMAL_DISPATCH'],
        'commands_started': False, 'host_only': host_only,
        'executable': host_only or readiness['ready'], 'o7_readiness': readiness})
    if host_only:
        value['stage_order'] = value['stage_order'][:2]
    return value


def _run_cpu_minute(root: Path, binding: dict, stage_name: str) -> dict:
    """Reuse the campaign's bounded per-pair observation implementation."""
    require(re.fullmatch(r'o4\.1-cpu-minute-(?:before|final)', stage_name) is not None,
            'CPU_STAGE_NAME')
    output = root / stage_name
    output.mkdir(exist_ok=False)
    preflight = campaign.environment_preflight()
    campaign.require_environment_preflight(preflight)
    campaign.write(output / 'environment-preflight-initial.json', preflight)
    live = {'run_id': binding['chain_id'] + '.preflight',
            'source_closure_sha256': binding['source_closure_sha256'],
            'campaign_sha256': hashlib.sha256(binding['chain_id'].encode()).hexdigest(),
            'source_files': binding['source_files']}
    campaign.observe_pair_launch(output, live, lambda: None)
    return campaign.reference(root, output / 'environment-preflight-initial.json')


def _require_residency(root: Path, run_id: str, expected: dict) -> Path:
    result_root = STUDIO / '.local/reviews' / run_id
    result = result_root / 'result.json'
    require(result.is_file(), 'HOST_RESIDENCY_RESULT_MISSING')
    value = json.loads(result.read_bytes())
    require(value.get('completed') is True and value.get('formal_acceptance') is False
            and value.get('run_id') == run_id,
            'HOST_RESIDENCY_NOT_COMPLETE')
    require(value.get('source_closure_sha256') == expected['source_closure_sha256'],
            'HOST_RESIDENCY_SOURCE_DRIFT')
    batches = value.get('batches')
    require(type(batches) is list and 35 <= len(batches) <= 64
            and value.get('source_unchanged') is True and value.get('full_benchmark') is False,
            'HOST_RESIDENCY_COVERAGE')
    capture_path = result_root / 'owner' / 'capture.json'
    require(capture_path.is_file(), 'HOST_RESIDENCY_CAPTURE_MISSING')
    capture = json.loads(capture_path.read_bytes())
    elapsed = capture.get('elapsed_seconds')
    require(capture.get('schema') == 'HH-GT06-BENCHMARK-CAPTURE-2'
            and capture.get('completed') is True
            and capture.get('actual_process_exit', {}).get('exit_code') == 0
            and capture.get('natural_tree_exit') is True
            and capture.get('source_unchanged') is True
            and capture.get('formal_acceptance') is False
            and finite_nonnegative(elapsed) and elapsed >= 1800,
            'HOST_RESIDENCY_CAPTURE_INVALID')
    campaign.verify_capture(result_root / 'owner', sha(capture_path), source_root=STUDIO,
                            expected_source_files=expected['source_files'],
                            expected_binary_sha256=sha(Path(sys.executable)))
    elapsed = value.get('active_elapsed_seconds')
    require(finite_nonnegative(elapsed) and elapsed >= 1800, 'HOST_ACTIVE_DURATION')
    # O6.3 uses the first 35 batches; O9.4c applies to the entire active run.
    identity = batches[0].get('host_process')
    require(type(identity) is dict, 'HOST_PROCESS_IDENTITY')
    active_start, active_end = None, None
    for index, summary in enumerate(batches):
        raw = json.loads((result_root / f'batch-{index:02d}.json').read_bytes())
        gap = summary.get('max_status_gap_ms')
        require(summary.get('index') == index and raw.get('index') == index
                and summary.get('host_process') == raw.get('host_process') == identity
                and raw.get('run_id') == run_id and type(raw.get('commands')) is list
                and len(raw['commands']) == 1000
                and raw.get('max_status_gap_ms') == gap and finite_nonnegative(gap),
                'HOST_BATCH_BINDING')
        require(gap < 1000, 'HOST_STATUS_GAP_ONE_SECOND')
        start, end = raw.get('started_mono_us'), raw.get('ended_mono_us')
        require(type(start) is int and type(end) is int and 0 <= start <= end
                and (active_end is None or start >= active_end), 'HOST_ACTIVE_CLOCK')
        active_start = start if active_start is None else active_start
        active_end = end
    require((active_end - active_start) / 1_000_000 == elapsed
            and value.get('active_started_mono_us') == active_start
            and value.get('active_ended_mono_us') == active_end, 'HOST_ACTIVE_DURATION_BINDING')
    return result_root


def _require_watchdog(root: Path, expected: dict) -> None:
    result = root / 'soak-result.json'
    require(result.is_file(), 'WATCHDOG_RESULT_MISSING')
    value = json.loads(result.read_bytes())
    context = json.loads((root / 'soak-context.json').read_bytes())
    elapsed = value.get('elapsed_seconds')
    require(value.get('schema') == watchdog_soak.SOAK_SCHEMA
            and value.get('actual_exit_code') == 0 and value.get('verified_watchdog') is True
            and value.get('formal_acceptance') is False
            and value.get('run_id') == expected['watchdog_id']
            and finite_nonnegative(elapsed) and elapsed >= 1800
            and value.get('sample_stream_closed') is True
            and value.get('event_stream_closed') is True,
            'WATCHDOG_NOT_VERIFIED')
    require(value.get('source_closure_sha256') == expected['source_closure_sha256'],
            'WATCHDOG_SOURCE_DRIFT')
    require(context.get('schema') == watchdog_soak.SOAK_SCHEMA
            and context.get('run_id') == expected['watchdog_id']
            and context.get('source_closure_sha256') == expected['source_closure_sha256']
            and context.get('source_files') == expected['source_files']
            and context.get('formal_acceptance') is False,
            'WATCHDOG_CONTEXT_BINDING')
    require(value.get('owner_capture_sha256') == sha(root / 'owner/capture.json')
            and value.get('result_sha256') == sha(root / 'result.json'),
            'WATCHDOG_HOST_CAPTURE_BINDING')
    campaign.environment.verify_watchdog(root, campaign.read_regular,
        elapsed_seconds=elapsed,
        expected_binding={key: context[key] for key in
                          ('run_id', 'source_closure_sha256', 'campaign_sha256')},
        require_docker_inventory=True)


def _dispatch_formal(formal_id: str, output: Path, binding: dict) -> None:
    script = STUDIO / 'tests/replay/campaign_task.ps1'
    command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script),
               '-Command', 'register-run', '-CampaignId', formal_id, '-Mode', 'campaign',
               '-SourceClosure', binding['source_closure_sha256'],
               '-ProfileHash', binding['profile_sha256']]
    completed = subprocess.run(command, cwd=STUDIO, capture_output=True, text=True,
                               timeout=120, check=False,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    supervisor = REVIEWS / (formal_id + '-supervisor')
    start_receipt = supervisor / 'task-start.json'
    require(completed.returncode == 0 and start_receipt.is_file(), 'FORMAL_DISPATCH_UNPROVEN')
    start = json.loads(start_receipt.read_bytes())
    require(start.get('schema') == 'HH-GT06-TASK-START-1'
            and start.get('campaign_id') == formal_id and start.get('mode') == 'campaign'
            and start.get('formal_acceptance') is False
            and type(start.get('instance_guid')) is str and bool(start['instance_guid']),
            'FORMAL_DISPATCH_UNPROVEN')
    write_new(output / 'formal-dispatch.json', {
        'schema': 'HH-GT06-O9-FORMAL-DISPATCH-1', 'formal_id': formal_id,
        'actual_launcher_exit': completed.returncode,
        'task_start': {'file': start_receipt.relative_to(STUDIO).as_posix(),
                       'sha256': sha(start_receipt)},
        'stdout': completed.stdout[-8192:], 'stderr': completed.stderr[-8192:],
        'formal_acceptance': False})


def execute(chain_id: str, formal_id: str, root: Path, *, frozen_plan: dict) -> int:
    validate_ids(chain_id, formal_id)
    root = validate_output(root, chain_id)
    require(not root.exists(), 'CHAIN_OUTPUT_EXISTS')
    require(type(frozen_plan) is dict and type(frozen_plan.get('host_only')) is bool,
            'CHAIN_PLAN_SHAPE')
    require(frozen_plan == dry_run(chain_id, formal_id, root, host_only=frozen_plan['host_only']),
            'CHAIN_FROZEN_PLAN_CHANGED')
    require(frozen_plan['executable'] is True, 'CHAIN_PREREQUISITE_NOT_READY')
    files = frozen_plan['source_files']
    binding = context(chain_id, formal_id, files)
    root.mkdir(parents=True)
    write_new(root / 'chain-context.json', {**binding, 'mode': 'execute',
                                            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
    campaign.environment.require_infra_budget(REVIEWS, campaign.read_regular)
    initial_preflight = _run_cpu_minute(root, binding, 'o4.1-cpu-minute-before')
    write_new(root / 'stage-01-preflight.json', {'stage': 'O4.1_CPU_MINUTE', 'passed': True,
                                                  'initial_preflight': initial_preflight,
                                                  'formal_acceptance': False})

    host_id = chain_id.replace('chain-', 'host-')[:35]
    from studio.tests.replay import run_command_residency
    host_code = run_command_residency.run(host_id, minimum_seconds=1800)
    require(host_code == 0, 'HOST_RESIDENCY_EXIT')
    host_root = _require_residency(root, host_id, binding)
    write_new(root / 'stage-02-host-residency.json', {'stage': 'O9.4C_HOST_RESIDENCY',
                                                       'run_id': host_id, 'root': str(host_root),
                                                       'passed': True, 'formal_acceptance': False})

    # The host run's continuous verified stream qualifies under O9.5; do not
    # spend another 30 minutes on a duplicate observer-only run.
    _require_watchdog(host_root, {'source_closure_sha256': binding['source_closure_sha256'],
                                      'source_files': binding['source_files'],
                                      'watchdog_id': host_id})
    write_new(root / 'stage-03-watchdog.json', {'stage': 'O9.1D_COMBINED_HOST_WATCHDOG',
                                                 'run_id': host_id, 'passed': True,
                                                 'formal_acceptance': False})

    if frozen_plan['host_only']:
        write_new(root / 'chain-complete.json', {**binding, 'formal_dispatched': False,
                  'host_only': True, 'host_result': campaign.reference(host_root, host_root / 'result.json'),
                  'next_action': 'OFFLINE_O7_METRICS_AND_TELEMETRY_REVIEW'})
        return 0

    report = residency_metrics.from_run_with_retained_control(host_root,
        interleaved_probe=O7_PROBE, seed_directory=O7_SEEDS, reference_soak=O7_REFERENCE_SOAK)
    write_new(root / 'stage-04-metrics.json', {**report, 'formal_acceptance': False})
    status_gap = report.get('status_gap_max_ms')
    require(finite_nonnegative(status_gap),
            'O6_3_STATUS_GAP_SHAPE')
    require(report.get('metrics_pass') is True and report.get('additional_soak_required') is False,
            'O6_3_METRICS_NOT_PASS')
    require(status_gap < 1000, 'HOST_STATUS_GAP_ONE_SECOND')

    final_preflight = _run_cpu_minute(root, binding, 'o4.1-cpu-minute-final')
    write_new(root / 'stage-05-final-preflight.json', {'stage': 'O4.1_CPU_MINUTE_FINAL',
                                                        'initial_preflight': final_preflight,
                                                        'passed': True, 'formal_acceptance': False})
    require(source_manifest() == binding['source_files'], 'SOURCE_DRIFT_BEFORE_DISPATCH')
    _dispatch_formal(formal_id, root, binding)
    dispatch = json.loads((root / 'formal-dispatch.json').read_bytes())
    write_new(root / 'chain-complete.json', {'schema': SCHEMA, 'chain_id': chain_id,
                                             'formal_id': formal_id, 'formal_dispatched': True,
                                             'source_closure_sha256': binding['source_closure_sha256'],
                                             'profile_sha256': binding['profile_sha256'],
                                             'dispatch': dispatch,
                                             'formal_acceptance': False})
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--chain-id', required=True)
    parser.add_argument('--formal-id', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--host-only', action='store_true')
    parser.add_argument('--frozen-plan', type=Path)
    args = parser.parse_args()
    require(args.dry_run ^ args.execute, 'CHAIN_MODE')
    root = validate_output(args.output or (REVIEWS / args.chain_id), args.chain_id)
    if args.dry_run:
        print(json.dumps(dry_run(args.chain_id, args.formal_id, root, host_only=args.host_only), indent=2, sort_keys=True))
        return 0
    require(args.frozen_plan is not None, 'CHAIN_FROZEN_PLAN_REQUIRED')
    return execute(args.chain_id, args.formal_id, root,
                   frozen_plan=json.loads(args.frozen_plan.read_bytes()))


if __name__ == '__main__':
    raise SystemExit(main())
