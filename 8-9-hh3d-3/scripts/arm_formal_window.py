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
import subprocess
import sys
import time

TOOLS = Path(__file__).resolve().parents[1]
STUDIO = TOOLS / 'studio'
DEFAULT_CAMPAIGN = 'gt06-o4-formal-09'
PROFILE = '8a2e599c40f927ffaff5ded5e48b6bf2a0f0a6bb3a23de31434a695f4258cb35'
HERE = Path(__file__).resolve()
POWERSHELL = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def now():
    return datetime.now(timezone.utc)


def stamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('WINDOW_TIMEZONE_REQUIRED')
    return parsed


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
    if at < start:
        return 'BEFORE_WINDOW'
    if (end - at).total_seconds() < 3.5 * 3600:
        return 'TOO_LATE'
    if observation.get('source') != config['source'] or observation.get('profile') != PROFILE:
        return 'SOURCE_OR_PROFILE_CHANGED'
    for name in ('lock_absent', 'scheduler_idle', 'budget_available', 'preflight_pass', 'cpu_minute_pass'):
        if observation.get(name) is not True:
            return name.upper() + '_NOT_PASS'
    return 'DISPATCH'


def scheduler_idle():
    # The one-shot arm task is expected to be live while it probes. Only an
    # already-running formal09 demand task blocks dispatch; counting the arm
    # helper itself would make every valid window fail closed.
    code = "$ErrorActionPreference='Stop'; $s=New-Object -ComObject Schedule.Service; $s.Connect(); @($s.GetRunningTasks(0) | Where-Object { $_.Name -like 'HHStudio.GT06.gt06-o4-formal-*' }).Count"
    result = subprocess.run([str(POWERSHELL), '-NoProfile', '-NonInteractive', '-Command', code],
                            capture_output=True, timeout=20, creationflags=0x08000000)
    if result.returncode != 0:
        raise RuntimeError('SCHEDULER_INVENTORY_FAILED')
    return int(result.stdout.strip()) == 0


def probe(output, *, binding_only=False):
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
        value.update(lock_absent=not default_path().exists(), scheduler_idle=scheduler_idle(),
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
            value['scheduler_idle'] = scheduler_idle()
            campaign.environment.require_infra_budget(STUDIO / '.local/reviews', campaign.read_regular)
            value['source'] = campaign.closure(campaign.source_files())
            if value['source'] != campaign.closure(files):
                raise RuntimeError('SOURCE_CHANGED_DURING_PROBE')
        except Exception as error:
            value['preflight_pass'] = False
            value['failure'] = getattr(error, 'code', str(error))
    value['finished_at'] = now().isoformat()
    write(output, value)


def fresh_probe(output, *, binding_only=False):
    console = Path(sys.executable).with_name('python.exe')
    command = [str(console), '-B', str(HERE), '--probe', str(output)]
    if binding_only:
        command.append('--binding-only')
    result = subprocess.run(command, capture_output=True, timeout=150, creationflags=0x08000000)
    if result.returncode != 0:
        raise RuntimeError('FRESH_PROBE_EXIT_' + str(result.returncode))
    return json.loads(output.read_bytes())


def check(config, root, label):
    observation = fresh_probe(root / (label + '.json'))
    verdict = decision(config, observation, now())
    write(root / (label + '-decision.json'), {'decision': verdict, 'observed_at': now().isoformat()})
    return verdict


def run(config, root):
    sys.path.insert(0, str(TOOLS))
    from studio.tests.replay.benchmark_environment import KeepAwake
    # Claim survives exceptions and prevents double-dispatch after a task restart.
    campaign_id = config['campaign_id']
    if not isinstance(campaign_id, str) or not campaign_id.startswith('gt06-o4-formal-'):
        raise RuntimeError('ARM_CAMPAIGN_ID')
    write(root / 'arm-claim.json', {'pid': os.getpid(), 'at': now().isoformat(), 'campaign_id': campaign_id})
    if hashlib.sha256(HERE.read_bytes()).hexdigest() != config['arm_sha256']:
        raise RuntimeError('ARM_SOURCE_CHANGED')
    end = stamp(config['end'])
    verdict = 'NOT_CHECKED'
    with KeepAwake():
        while now() < stamp(config['start']):
            time.sleep(min(30, (stamp(config['start']) - now()).total_seconds()))
        attempt = 0
        while (end - now()).total_seconds() >= 3.5 * 3600:
            attempt += 1
            verdict = check(config, root, f'attempt-{attempt:02d}')
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
                while now() < end:
                    result = subprocess.run(command[:command.index('-Command') + 1] + ['status', '-CampaignId', CAMPAIGN],
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
    parser.add_argument('--binding-only', action='store_true')
    parser.add_argument('--campaign-id', default=DEFAULT_CAMPAIGN)
    parser.add_argument('--start')
    parser.add_argument('--end')
    args = parser.parse_args()
    if args.probe:
        probe(args.probe, binding_only=args.binding_only)
        return 0
    if args.prepare:
        root = args.prepare.resolve()
        root.mkdir(parents=True, exist_ok=False)
        binding = fresh_probe(root / 'binding.json', binding_only=True)
        if binding['profile'] != PROFILE or (stamp(args.end) - stamp(args.start)).total_seconds() < 4 * 3600:
            raise ValueError('ARM_BINDING_OR_WINDOW')
        if not args.campaign_id.startswith('gt06-o4-formal-'):
            raise ValueError('ARM_CAMPAIGN_ID')
        write(root / 'request.json', {**binding, 'start': args.start, 'end': args.end,
              'campaign_id': args.campaign_id, 'arm_sha256': hashlib.sha256(HERE.read_bytes()).hexdigest()})
        print(str(root / 'request.json'))
        return 0
    request = (args.dry_run or args.run).resolve()
    config, root = json.loads(request.read_bytes()), request.parent
    if not str(config.get('campaign_id', '')).startswith('gt06-o4-formal-'):
        raise ValueError('ARM_CAMPAIGN')
    if args.dry_run:
        verdict = check(config, root, 'dry-run')
        print(verdict)
        return 0 if verdict in ('DISPATCH', 'BEFORE_WINDOW') else 1
    try:
        run(config, root)
    except Exception as error:
        write(root / 'arm-failure.json', {'reason': str(error), 'at': now().isoformat(), 'no_retry': True})
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
