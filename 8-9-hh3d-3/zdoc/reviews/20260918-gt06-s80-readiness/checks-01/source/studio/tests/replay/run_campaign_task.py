"""Demand-only Task Scheduler entry point for the bounded GT06 campaign.

This trusted local launcher has no arbitrary-command interface. The scheduler
starts this process directly in the current user's interactive session. Each
campaign run still owns its original checked, kill-on-close Windows Job.
This file never registers a task, restarts an interrupted run, or grants PASS.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as w
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import traceback

STUDIO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(STUDIO.parent))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def launch_suffix(launch_number):
    if type(launch_number) is not int or not 1 <= launch_number <= 99:
        raise ValueError('TASK_LAUNCH_NUMBER')
    return '' if launch_number == 1 else f'-launch-{launch_number:02d}'


def validate_request(value, campaign_id, mode, script, windowed, console, *, launch_number=1):
    launch_suffix(launch_number)
    expected = {'schema': 'HH-GT06-TASK-REQUEST-1', 'campaign_id': campaign_id,
        'mode': mode, 'script_sha256': sha(script),
        'pythonw_sha256': sha(windowed), 'python_sha256': sha(console)}
    if launch_number > 1:
        expected['launch_number'] = launch_number
        if type(value) is not dict or type(value.get('launch_number')) is not int:
            raise ValueError('TASK_REQUEST_BINDING')
    if type(value) is not dict or value != expected:
        raise ValueError('TASK_REQUEST_BINDING')


def process_observation():
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.GetPriorityClass.argtypes, kernel.GetPriorityClass.restype = [w.HANDLE], w.DWORD
    kernel.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4
    kernel.GetProcessTimes.restype = w.BOOL
    current = kernel.GetCurrentProcess()
    created, exited, system, user = (w.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(current, ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(system), ctypes.byref(user)):
        raise OSError(ctypes.get_last_error(), 'TASK_PROCESS_TIMES')
    priority = int(kernel.GetPriorityClass(current))
    if priority != 0x20:
        raise ValueError('TASK_PRIORITY_NOT_NORMAL')
    return {'pid': os.getpid(), 'parent_pid': os.getppid(), 'priority_class': priority,
        'process_start': 'windows:' + str(created.dwLowDateTime | created.dwHighDateTime << 32)}


def execute(campaign_id, mode, output, request_sha, *, launch_number=1):
    from studio.tests.replay import run_benchmark_campaign as campaign
    from studio.tests.replay.benchmark_job import BenchmarkProcess, HELD_OWNERS, verify_capture
    if mode == 'campaign':
        # Calling in this scheduler-owned process preserves the accepted run
        # owner hierarchy and does not add a fifth process to its four-slot Job.
        return campaign.run_campaign(campaign_id, STUDIO / '.local/reviews' / campaign_id)
    campaign.load_fixture()
    sources = campaign.source_files()
    owner = None
    try:
        owner = BenchmarkProcess([sys.executable, '-B', '-c',
            "import time; time.sleep(12); print('HH_GT06_TASK_PROBE_COMPLETE',flush=True)"],
            cwd=output, output=output / 'probe-owner', source_root=STUDIO,
            source_files=sources, binary_sha256=sha(Path(sys.executable)))
        binding = {'run_id': campaign_id + '.probe' + launch_suffix(launch_number),
            'source_closure_sha256': campaign.closure(sources), 'campaign_sha256': request_sha}
        write(output / 'probe-context.json', binding)
        campaign.wait_owned_run(owner, output, **binding)
        owner.finish()
        capture = output / 'probe-owner/capture.json'
        verify_capture(capture.parent, sha(capture), source_root=STUDIO,
            expected_source_files=sources, expected_binary_sha256=sha(Path(sys.executable)))
        write(output / 'probe-result.json', {'verified': True, 'capture_sha256': sha(capture),
            'held_owners': len(HELD_OWNERS), 'formal_acceptance': False})
        return 0
    except BaseException as error:
        owner = owner or getattr(error, 'cleanup_owner', None)
        raise
    finally:
        if owner is not None:
            owner.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--mode', choices=('probe', 'campaign'), required=True)
    parser.add_argument('--launch-number', type=int, default=1)
    args = parser.parse_args()
    if os.name != 'nt' or not re.fullmatch(r'gt06-[a-z0-9-]{1,25}', args.campaign_id):
        raise ValueError('TASK_ID_OR_PLATFORM')
    suffix = launch_suffix(args.launch_number)
    output = STUDIO / '.local/reviews' / (args.campaign_id + '-supervisor' + suffix)
    launch_fields = {} if args.launch_number == 1 else {'launch_number': args.launch_number}
    # Single-use claim precedes logs. Duplicate manual task starts cannot
    # overwrite evidence or silently resume an earlier invocation.
    with (output / 'claim').open('xb') as claim:
        claim.write(b'HH-GT06-TASK-SINGLE-USE\n')
        claim.flush()
        os.fsync(claim.fileno())
    with (output / 'stdout.txt').open('x', encoding='utf-8', buffering=1) as stdout, \
         (output / 'stderr.txt').open('x', encoding='utf-8', buffering=1) as stderr:
        sys.stdout, sys.stderr = stdout, stderr
        code = 1
        started = time.monotonic()
        try:
            windowed = Path(sys.executable).absolute()
            console = windowed.with_name('python.exe')
            if windowed.name.lower() != 'pythonw.exe':
                raise ValueError('TASK_WINDOWED_INTERPRETER_REQUIRED')
            request = output / 'request.json'
            value = json.loads(request.read_bytes())
            validate_request(value, args.campaign_id, args.mode, Path(__file__), windowed, console,
                launch_number=args.launch_number)
            # The scheduler console stays hidden; owned helpers use the
            # checked console companion with their existing redirected pipes.
            sys.executable = str(console)
            observation = process_observation()
            write(output / 'start.json', {**observation, **launch_fields, 'campaign_id': args.campaign_id,
                'mode': args.mode, 'started_at': datetime.now(timezone.utc).isoformat(),
                'request_sha256': sha(request), 'supervisor_script_sha256': sha(Path(__file__)),
                'scheduler_result_still_required': True, 'formal_acceptance': False})
            code = execute(args.campaign_id, args.mode, output, sha(request), launch_number=args.launch_number)
            validate_request(value, args.campaign_id, args.mode, Path(__file__), windowed, console,
                launch_number=args.launch_number)
        except BaseException as error:
            code = 1
            traceback.print_exc()
            write(output / 'failure.json', {**launch_fields, 'code': getattr(error, 'code', type(error).__name__),
                'formal_acceptance': False})
        finally:
            write(output / 'return.json', {**launch_fields, 'returned_exit_code': code,
                'elapsed_seconds': time.monotonic() - started,
                'actual_process_exit_not_yet_observed': True,
                'scheduler_result_still_required': True, 'formal_acceptance': False})
            stdout.flush()
            stderr.flush()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
