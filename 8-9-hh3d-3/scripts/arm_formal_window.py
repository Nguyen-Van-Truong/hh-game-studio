"""O8 one-window launcher. Outside studio's measured/imported source closure.

Read-only probes run in fresh processes. A single-use claim precedes dispatch;
an uncertain scheduler response is never retried. No acceptance is granted here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

TOOLS = Path(__file__).resolve().parents[1]
STUDIO = TOOLS / 'studio'
DEFAULT_CAMPAIGN = 'gt06-o4-formal-09'
PROFILE = '8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35'
HERE = Path(__file__).resolve()
POWERSHELL = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
CAMPAIGN_PATTERN = re.compile(r'gt06-o4-formal-(?:0[1-9]|[1-9][0-9])')
ARM_TASK_PATTERN = re.compile(r'HHStudio\.GT06\.arm-formal(?:0[1-9]|[1-9][0-9])-\d{8}')


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('WINDOW_TIME_REQUIRED')
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('WINDOW_TIMEZONE_REQUIRED')
    return parsed


def validate_config(config):
    if not isinstance(config, dict) or not isinstance(config.get('campaign_id'), str) or not CAMPAIGN_PATTERN.fullmatch(config['campaign_id']):
        raise ValueError('ARM_CAMPAIGN_ID')
    for name in ('source', 'profile', 'arm_sha256'):
        if not isinstance(config.get(name), str) or not re.fullmatch(r'[a-f0-9]{64}', config[name]):
            raise ValueError('ARM_HASH_' + name.upper())
    if config['profile'] != PROFILE:
        raise ValueError('ARM_PROFILE_CHANGED')
    if (stamp(config.get('end')) - stamp(config.get('start'))).total_seconds() < 4 * 3600:
        raise ValueError('WINDOW_TOO_SHORT')
    if hashlib.sha256(HERE.read_bytes()).hexdigest() != config['arm_sha256']:
        raise ValueError('ARM_SOURCE_CHANGED')


def arm_task_name(config):
    return 'HHStudio.GT06.arm-formal' + config['campaign_id'].rsplit('-', 1)[1] + '-' + stamp(config['start']).strftime('%Y%m%d')


def require_dry_run(config, request):
    receipt = json.loads((request.parent / 'dry-run-success.json').read_bytes())
    expected = {'schema': 'HH-GT06-ARM-DRY-RUN-1', 'campaign_id': config['campaign_id'],
                'request_sha256': hashlib.sha256(request.read_bytes()).hexdigest(),
                'arm_sha256': config['arm_sha256']}
    if any(receipt.get(key) != value for key, value in expected.items()) or receipt.get('decision') not in ('DISPATCH', 'BEFORE_WINDOW'):
        raise ValueError('ARM_DRY_RUN_NOT_VALID')


def keep_awake():
    sys.path.insert(0, str(TOOLS))
    from studio.tests.replay.benchmark_environment import KeepAwake
    return KeepAwake()


def write(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def decision(config, observation, at):
    """Only decide when to launch; never change the measured PASS/FAIL policy."""
    start, end = stamp(config['start']), stamp(config['end'])
    if (end - start).total_seconds() < 4 * 3600:
        return 'WINDOW_TOO_SHORT'
    if observation.get('source') != config['source'] or observation.get('profile') != PROFILE:
        return 'SOURCE_OR_PROFILE_CHANGED'
    for name in ('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'):
        if observation.get(name) is not True:
            return name.upper() + '_NOT_PASS'
    try:
        observed, finished = stamp(observation.get('observed_at')), stamp(observation.get('finished_at'))
    except (ValueError, TypeError):
        return 'OBSERVATION_NOT_FRESH'
    if observed > finished or not 0 <= (at - finished).total_seconds() <= 150:
        return 'OBSERVATION_NOT_FRESH'
    if at < start:
        return 'BEFORE_WINDOW'
    if (end - at).total_seconds() < 3.5 * 3600:
        return 'TOO_LATE'
    return 'DISPATCH'


def scheduler_idle(own_arm_task=None):
    if own_arm_task is not None and not ARM_TASK_PATTERN.fullmatch(own_arm_task):
        raise ValueError('ARM_TASK_NAME')
    # Inventory every GT06 task; exclude only the exact arm running this probe.
    # EnginePID identifies the scheduler host, not this Python process.
    code = "$ErrorActionPreference='Stop'; $s=New-Object -ComObject Schedule.Service; $s.Connect(); $rows=@($s.GetRunningTasks(0) | ForEach-Object { [ordered]@{name=[string]$_.Name; task_path=[string]$_.Path} }); ConvertTo-Json -InputObject $rows -Compress"
    result = subprocess.run([str(POWERSHELL), '-NoProfile', '-NonInteractive', '-Command', code],
                            capture_output=True, timeout=20, creationflags=0x08000000)
    if result.returncode != 0:
        raise RuntimeError('SCHEDULER_INVENTORY_FAILED')
    rows = json.loads(result.stdout.decode('utf-8-sig'))
    if not isinstance(rows, list):
        raise RuntimeError('SCHEDULER_INVENTORY_INVALID')
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str) or not isinstance(row.get('task_path'), str):
            raise RuntimeError('SCHEDULER_INVENTORY_INVALID')
        if not row['name'].casefold().startswith('hhstudio.gt06.'):
            continue
        if own_arm_task is not None and row['name'].casefold() == own_arm_task.casefold() and row['task_path'].casefold() == ('\\' + own_arm_task).casefold():
            continue
        return False
    return True


def probe(output, *, binding_only=False, own_arm_task=None):
    # A fresh interpreter ensures this is the actual campaign import closure,
    # not the import set of a test runner or a prior diagnostic in this process.
    sys.path.insert(0, str(TOOLS))
    from studio.tests.replay import run_benchmark_campaign as campaign
    from studio.tests.replay.measure_window import default_path
    campaign.load_fixture()
    files = campaign.source_files()
    value = {'source': campaign.closure(files), 'source_files': files,
             'profile': campaign.profile.PROFILE_SHA256, 'observed_at': now().isoformat()}
    if not binding_only:
        value.update(lock_absent=not default_path().exists(), scheduler_idle=scheduler_idle(own_arm_task),
                     budget_available=False, preflight_pass=False, cpu_minute_pass=False)
        try:
            campaign.environment.require_infra_budget(STUDIO / '.local/reviews', campaign.read_regular)
            value['budget_available'] = True
            if not value['lock_absent'] or not value['scheduler_idle']:
                raise RuntimeError('MEASUREMENT_ALREADY_ACTIVE')
            policy, percentages, first, previous = campaign.environment.Policy(), [], None, None
            with output.with_suffix('.samples.jsonl').open('x', encoding='utf-8') as samples:
                while True:
                    started = time.monotonic()
                    row = campaign.environment_snapshot()
                    samples.write(json.dumps(row, separators=(',', ':')) + '\n')
                    samples.flush()
                    failure = policy.observe(row)
                    campaign.require_environment_preflight(campaign.environment.preflight(row))
                    if failure:
                        raise RuntimeError('OBSERVATION_' + failure['reason'])
                    first = row if first is None else first
                    if previous is not None:
                        total = row['cpu_total_100ns'] - previous['cpu_total_100ns']
                        idle = row['cpu_idle_100ns'] - previous['cpu_idle_100ns']
                        if total <= 0:
                            raise RuntimeError('CPU_UNOBSERVED')
                        percentages.append(100 * (total - idle) / total)
                    previous = row
                    elapsed = (row['uptime_ms'] - first['uptime_ms']) / 1000
                    if elapsed >= 60:
                        break
                    time.sleep(max(0, 5 - (time.monotonic() - started)))
            value.update(preflight_pass=True, cpu_minute_pass=bool(percentages) and not all(p > 95 for p in percentages),
                         cpu_observed_seconds=elapsed, cpu_max_percent=max(percentages),
                         cpu_mean_percent=sum(percentages) / len(percentages),
                         available_gib=row['available_memory_bytes'] / 1024**3,
                         commit_percent=100 * row['commit_total_bytes'] / row['commit_limit_bytes'])
            # Recheck at the boundary, not just before the 60-second observation.
            value['lock_absent'] = not default_path().exists()
            value['scheduler_idle'] = scheduler_idle(own_arm_task)
            campaign.environment.require_infra_budget(STUDIO / '.local/reviews', campaign.read_regular)
            value['source'] = campaign.closure(campaign.source_files())
            if value['source'] != campaign.closure(files):
                raise RuntimeError('SOURCE_CHANGED_DURING_PROBE')
        except Exception as error:
            value['preflight_pass'] = False
            value['failure'] = getattr(error, 'code', str(error))
    value['finished_at'] = now().isoformat()
    write(output, value)


def fresh_probe(output, *, binding_only=False, own_arm_task=None):
    console = Path(sys.executable).with_name('python.exe')
    command = [str(console), '-B', str(HERE), '--probe', str(output)]
    if binding_only:
        command.append('--binding-only')
    if own_arm_task is not None:
        command.extend(['--own-arm-task', own_arm_task])
    result = subprocess.run(command, capture_output=True, timeout=150, creationflags=0x08000000)
    if result.returncode != 0:
        raise RuntimeError('FRESH_PROBE_EXIT_' + str(result.returncode))
    return json.loads(output.read_bytes())


def check(config, root, label, *, own_arm_task=None):
    try:
        observation = fresh_probe(root / (label + '.json'), own_arm_task=own_arm_task)
        verdict = decision(config, observation, now())
    except Exception as error:
        write(root / (label + '-failure.json'), {'reason': str(error), 'at': now().isoformat(), 'dispatched': False})
        verdict = 'PROBE_FAILED'
    write(root / (label + '-decision.json'), {'decision': verdict, 'observed_at': now().isoformat()})
    return verdict


def run(config, root, request=None):
    validate_config(config)
    require_dry_run(config, request or root / 'request.json')
    # Claim survives exceptions and prevents double-dispatch after a task restart.
    campaign_id = config['campaign_id']
    write(root / 'arm-claim.json', {'pid': os.getpid(), 'at': now().isoformat(), 'campaign_id': campaign_id})
    end = stamp(config['end'])
    verdict = 'NOT_CHECKED'
    with keep_awake():
        while now() < stamp(config['start']):
            time.sleep(min(30, (stamp(config['start']) - now()).total_seconds()))
        attempt = 0
        while (end - now()).total_seconds() >= 3.5 * 3600:
            attempt += 1
            verdict = check(config, root, f'attempt-{attempt:02d}', own_arm_task=arm_task_name(config))
            if verdict == 'DISPATCH':
                # Exclusive claim BEFORE calling the existing launcher. Timeout,
                # failure or an uncertain reply is a closeout, never a retry.
                write(root / 'dispatch-claim.json', {'at': now().isoformat(), 'campaign_id': campaign_id})
                command = [str(POWERSHELL), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                           '-File', str(STUDIO / 'tests/replay/campaign_task.ps1'),
                           '-Command', 'register-run', '-CampaignId', campaign_id, '-Mode', 'campaign']
                with (root / 'dispatch-stdout.txt').open('xb') as out, (root / 'dispatch-stderr.txt').open('xb') as err:
                    result = subprocess.run(command, stdout=out, stderr=err, timeout=60, creationflags=0x08000000)
                write(root / 'dispatch-return.json', {'exit_code': result.returncode, 'at': now().isoformat()})
                if result.returncode != 0:
                    raise RuntimeError('DISPATCH_FAILED_NO_RETRY')
                status_command = [str(POWERSHELL), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                  '-File', str(STUDIO / 'tests/replay/campaign_task.ps1'),
                                  '-Command', 'status', '-CampaignId', campaign_id]
                while now() < end:
                    result = subprocess.run(status_command,
                                            capture_output=True, timeout=30, creationflags=0x08000000)
                    if result.returncode != 0:
                        raise RuntimeError('CAMPAIGN_STATUS_UNKNOWN_NO_RETRY')
                    status = json.loads(result.stdout.decode('utf-8-sig'))
                    if not status['instances'] and status['state'] in (1, 3):
                        write(root / 'campaign-terminal-scheduler.json', status)
                        return
                    time.sleep(min(30, max(0, (end - now()).total_seconds())))
                write(root / 'window-ended.json', {'at': now().isoformat(), 'campaign_may_still_run': True})
                return
            if verdict in ('SOURCE_OR_PROFILE_CHANGED', 'TOO_LATE'):
                break
            remaining = (end - now()).total_seconds() - 3.5 * 3600
            if remaining <= 0:
                break
            time.sleep(min(600, remaining))
        write(root / 'no-dispatch.json', {'reason': verdict, 'at': now().isoformat()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--probe', type=Path)
    action.add_argument('--prepare', type=Path)
    action.add_argument('--dry-run', type=Path)
    action.add_argument('--run', type=Path)
    action.add_argument('--validate', type=Path, help='Read-only request, helper and successful dry-run validation')
    parser.add_argument('--binding-only', action='store_true')
    parser.add_argument('--campaign-id', default=DEFAULT_CAMPAIGN)
    parser.add_argument('--start')
    parser.add_argument('--end')
    parser.add_argument('--own-arm-task')
    args = parser.parse_args()
    if args.own_arm_task and not args.probe:
        parser.error('--own-arm-task is only used by a fresh probe')
    if args.probe:
        probe(args.probe, binding_only=args.binding_only, own_arm_task=args.own_arm_task)
        return 0
    if args.prepare:
        config = {'start': args.start, 'end': args.end, 'campaign_id': args.campaign_id,
                  'source': '0' * 64, 'profile': PROFILE, 'arm_sha256': hashlib.sha256(HERE.read_bytes()).hexdigest()}
        validate_config(config)
        root = args.prepare.resolve()
        root.mkdir(parents=True, exist_ok=False)
        binding = fresh_probe(root / 'binding.json', binding_only=True)
        config.update(binding)
        validate_config(config)
        write(root / 'request.json', config)
        print(str(root / 'request.json'))
        return 0
    request = (args.dry_run or args.run or args.validate).resolve()
    root = request.parent
    try:
        config = json.loads(request.read_bytes())
        validate_config(config)
        if args.validate:
            require_dry_run(config, request)
            print(json.dumps({'campaign_id': config['campaign_id'], 'start': config['start'], 'end': config['end'],
                              'arm_task_name': arm_task_name(config), 'request_sha256': hashlib.sha256(request.read_bytes()).hexdigest()}))
        elif args.dry_run:
            verdict = check(config, root, 'dry-run-' + uuid.uuid4().hex)
            print(verdict)
            if verdict not in ('DISPATCH', 'BEFORE_WINDOW'):
                return 1
            write(root / 'dry-run-success.json', {'schema': 'HH-GT06-ARM-DRY-RUN-1', 'campaign_id': config['campaign_id'],
                  'request_sha256': hashlib.sha256(request.read_bytes()).hexdigest(), 'arm_sha256': config['arm_sha256'],
                  'decision': verdict, 'observed_at': now().isoformat()})
        else:
            run(config, root, request)
    except Exception as error:
        if not args.validate:
            label = 'dry-run' if args.dry_run else 'arm'
            write(root / (label + '-failure-' + uuid.uuid4().hex + '.json'), {'reason': str(error), 'at': now().isoformat(), 'no_retry': True})
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
