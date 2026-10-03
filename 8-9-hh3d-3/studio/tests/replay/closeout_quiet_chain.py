"""Bounded O9.6 closeout for failed quiet chains before formal dispatch.

Default: read-only validation. --write exports hashes and observations to a new
fixed closeout directory; --delete-task additionally retires the exact terminal
task through campaign_task.ps1. Raw evidence stays in place. This is neither an
acceptance verifier nor a dependency of the frozen runtime closure. Missing child
exit evidence is UNKNOWN, including when wrapper and Scheduler returns exist.
"""
from __future__ import annotations

import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys

STUDIO = Path(__file__).resolve().parents[2]
ID = re.compile(r'gt06-o9-chain-f([2-9][0-9])-[a-z0-9]{1,5}')
HASH = re.compile(r'[a-f0-9]{64}')
MAX_FILES = 10000
MAX_BYTES = 512 * 1024 * 1024


def require(condition, code):
    if not condition:
        raise ValueError(code)


def plain(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not getattr(info, 'st_file_attributes', 0) & 0x400, 'REPARSE_PATH')
    return path


def digest(path):
    path = plain(path)
    require(path.is_file() and path.stat().st_size <= MAX_BYTES, 'FILE_BOUND')
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read_json(path):
    path = plain(path)
    require(path.is_file() and 0 < path.stat().st_size <= 1024 * 1024, 'JSON_BOUND')
    value = json.loads(path.read_bytes())
    require(type(value) is dict, 'JSON_OBJECT')
    return value


def closure(files):
    return hashlib.sha256(''.join(name + '\0' + files[name] + '\n'
                                 for name in sorted(files)).encode()).hexdigest()


def verify_sources(studio, plan):
    files = plan.get('source_files')
    require(type(files) is dict and 0 < len(files) <= 2000, 'SOURCE_MANIFEST')
    total = 0
    for name, expected in files.items():
        require(type(name) is str and name and '\\' not in name and ':' not in name
                and not PurePosixPath(name).is_absolute()
                and all(part not in ('', '.', '..') for part in name.split('/')),
                'SOURCE_PATH')
        require(type(expected) is str and HASH.fullmatch(expected), 'SOURCE_HASH')
        path = plain(studio / name)
        total += path.stat().st_size
        require(total <= MAX_BYTES and digest(path) == expected, 'FROZEN_SOURCE_CHANGED')
    require(closure(files) == plan.get('source_closure_sha256'), 'SOURCE_CLOSURE')


def task_command(studio, campaign_id, command):
    """Only the existing authenticated exact-task status/delete API is callable."""
    require(os.name == 'nt' and ID.fullmatch(campaign_id), 'TASK_PLATFORM_OR_ID')
    require(command in ('status', 'delete'), 'TASK_COMMAND')
    powershell = plain(Path(os.environ['WINDIR']) /
                       'System32/WindowsPowerShell/v1.0/powershell.exe')
    script = plain(studio / 'tests/replay/campaign_task.ps1')
    result = subprocess.run([str(powershell), '-NoProfile', '-NonInteractive',
                             '-File', str(script), '-Command', command,
                             '-CampaignId', campaign_id, '-Mode', 'quiet-chain'],
                            cwd=studio, capture_output=True, timeout=45,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    require(len(result.stdout) + len(result.stderr) <= 1024 * 1024, 'TASK_RESPONSE_BOUND')
    require(result.returncode == 0, 'TASK_' + command.upper() + '_FAILED:' +
            result.stderr.decode('utf-8-sig', errors='replace')[:1000])
    value = json.loads(result.stdout.decode('utf-8-sig'))
    require(type(value) is dict, 'TASK_RESPONSE')
    return value, {'exit_code': result.returncode,
                   'stdout': result.stdout.decode('utf-8-sig'),
                   'stderr': result.stderr.decode('utf-8-sig')}


def observe_pid(pid):
    """Open a read-only kernel handle; no PID-based signal, wait loop or kill."""
    require(os.name == 'nt' and type(pid) is int and pid > 0, 'PID_INPUT')
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        return {'pid': pid, 'state': 'absent' if error == 87 else 'unknown',
                'native_error': error, 'process_start': None}
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        require(kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)), 'PID_TIMES')
        created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        wait = kernel.WaitForSingleObject(handle, 0)
        return {'pid': pid, 'state': {0: 'exited', 258: 'live'}.get(wait, 'unknown'),
                'process_start': 'windows:' + str(created), 'native_error': None}
    finally:
        require(kernel.CloseHandle(handle), 'PID_HANDLE_CLOSE')


def raw_manifest(studio, roots):
    rows, total, entries = {}, 0, 0
    for root in roots:
        plain(root)
        require(root.is_dir(), 'RAW_ROOT_MISSING')
        for directory, subdirs, files in os.walk(root, followlinks=False):
            entries += len(subdirs) + len(files)
            require(entries <= MAX_FILES, 'RAW_BOUND')
            for name in subdirs:
                plain(Path(directory) / name)
            for name in sorted(files):
                path = plain(Path(directory) / name)
                size = path.stat().st_size
                total += size
                require(len(rows) < MAX_FILES and total <= MAX_BYTES, 'RAW_BOUND')
                rows[path.relative_to(studio).as_posix()] = {'bytes': size, 'sha256': digest(path)}
    return rows


def cleanup_valid(value):
    job, handle = value.get('job', {}), value.get('wrapper_process_handle', {})
    return (value.get('closed') is True and value.get('completed') is False
            and type(job) is dict and type(handle) is dict
            and all(job.get(k) is True for k in ('configured', 'assigned', 'closed', 'zero_observed'))
            and all(job.get(k) is False for k in ('tainted', 'handle_retained', 'close_uncertain', 'create_uncertain'))
            and type(job.get('active_count')) is int and job['active_count'] == 0
            and job.get('failed_operations') == [] and job.get('native_error') is None
            and handle == {'required': True, 'closed': True, 'close_uncertain': False, 'handle_retained': False})


def collect(studio, campaign_id, *, scheduler=task_command, probe=observe_pid):
    """Validate stored bindings and gather fresh status without writing anything."""
    require(type(campaign_id) is str and ID.fullmatch(campaign_id), 'CAMPAIGN_ID')
    studio = plain(studio)
    reviews = plain(studio / '.local/reviews')
    supervisor, chain = reviews / (campaign_id + '-supervisor'), reviews / campaign_id
    host_id = campaign_id.replace('chain-', 'host-')
    host = reviews / host_id
    roots = (supervisor, chain, host)
    raw = raw_manifest(studio, roots)
    require(not (chain / 'formal-dispatch.json').exists()
            and not (chain / 'chain-complete.json').exists(), 'DISPATCHED_OR_COMPLETE_CHAIN_UNSUPPORTED')
    request = read_json(supervisor / 'request.json')
    registration = read_json(supervisor / 'task-registration.json')
    start = read_json(supervisor / 'start.json')
    dispatch = read_json(supervisor / 'task-start.json')
    returned = read_json(supervisor / 'return.json')
    plan = read_json(supervisor / 'quiet-chain-plan.json')
    context = read_json(chain / 'chain-context.json')
    invocation = read_json(host / 'owner/invocation.json')
    host_context = read_json(host / 'soak-context.json')
    failure = read_json(host / 'owner-failure.json')
    cleanup = read_json(host / 'owner/cleanup-001.json')
    launched = read_json(host / 'owner/process-start.json')
    task_path = '\\HHStudio.GT06.' + campaign_id
    request_hash, xml_hash = digest(supervisor / 'request.json'), digest(supervisor / 'task-definition.xml')
    require(request.get('schema') == 'HH-GT06-TASK-REQUEST-1'
            and registration.get('schema') == 'HH-GT06-TASK-REGISTRATION-1'
            and dispatch.get('schema') == 'HH-GT06-TASK-START-1', 'TASK_RECEIPT_SCHEMA')
    for receipt in (request, registration, dispatch, start):
        require(receipt.get('campaign_id') == campaign_id and receipt.get('mode') == 'quiet-chain'
                and receipt.get('launch_number', 1) == 1, 'TASK_RECEIPT_BINDING')
    for receipt in (registration, dispatch):
        require(receipt.get('task_path') == task_path
                and receipt.get('task_definition_sha256') == xml_hash, 'TASK_XML_BINDING')
    require(all(r.get('request_sha256') == request_hash for r in (registration, dispatch, start)), 'REQUEST_HASH')
    require((supervisor / 'task-definition.sha256').read_text().strip() == xml_hash, 'XML_HASH')
    require(request.get('chain_plan_sha256') == digest(supervisor / 'quiet-chain-plan.json'), 'PLAN_HASH')
    script = studio / 'tests/replay/run_campaign_task.py'
    require(Path(registration.get('script_path', '')) == script
            and request.get('script_sha256') == start.get('supervisor_script_sha256') == digest(script), 'SCRIPT_HASH')
    for key, name in (('python', 'python.exe'), ('pythonw', 'pythonw.exe')):
        binary = Path(registration.get(key + '_path', ''))
        require(binary.is_absolute() and binary.name.lower() == name
                and request.get(key + '_sha256') == digest(binary), 'BINARY_HASH')
    require(plan.get('chain_id') == campaign_id and plan.get('formal_acceptance') is False
            and plan.get('formal_id') == 'gt06-o4-formal-' + ID.fullmatch(campaign_id).group(1), 'PLAN_BINDING')
    verify_sources(studio, plan)
    require(all(context.get(k) == plan.get(k) for k in
                ('chain_id', 'formal_id', 'source_files', 'source_closure_sha256', 'profile_sha256')), 'CHAIN_BINDING')
    require(host_context.get('run_id') == host_id
            and host_context.get('source_closure_sha256') == plan['source_closure_sha256']
            and host_context.get('source_files') == plan['source_files'], 'HOST_CONTEXT_BINDING')
    require(invocation.get('source_files') == plan['source_files']
            and Path(invocation.get('source_root', '')) == studio
            and Path(invocation.get('cwd', '')) == host
            and invocation.get('binary_sha256') == request['python_sha256']
            and invocation.get('argv') == [registration['python_path'], '-B',
                str(studio / 'tests/replay/run_command_residency.py'), '--child', '--run-id', host_id,
                '--minimum-seconds', '1800'], 'OWNER_INVOCATION_BINDING')
    require(failure.get('formal_acceptance') is False and failure.get('completed') is False
            and failure.get('classification') in ('INFRA_ABORT', 'FAIL')
            and type(failure.get('code')) is str and failure['code'], 'FAILURE_CLASSIFICATION')
    require(cleanup_valid(cleanup) and failure.get('job') == cleanup['job'], 'CLEANUP_UNPROVEN')
    require(type(returned.get('returned_exit_code')) is int and returned['returned_exit_code'] != 0
            and returned.get('formal_acceptance') is False
            and returned.get('actual_process_exit_not_yet_observed') is True
            and type(returned.get('elapsed_seconds')) in (int, float)
            and math.isfinite(returned['elapsed_seconds']) and returned['elapsed_seconds'] > 0, 'WRAPPER_RETURN')
    require(type(start.get('pid')) is int and start['pid'] > 0
            and re.fullmatch(r'windows:[1-9][0-9]*', start.get('process_start', ''))
            and type(launched.get('pid')) is int and launched['pid'] > 0, 'PROCESS_IDENTITY')
    status, status_raw = scheduler(studio, campaign_id, 'status')
    require(status.get('schema') == 'HH-GT06-TASK-STATUS-1'
            and status.get('campaign_id') == campaign_id and status.get('task_path') == task_path
            and status.get('mode') == 'quiet-chain' and status.get('launch_number') == 1
            and Path(status.get('output_directory', '')) == supervisor
            and status.get('state') in (1, 3) and status.get('instances') == []
            and type(status.get('last_task_result')) is int
            and status['last_task_result'] == returned['returned_exit_code'], 'SCHEDULER_NOT_TERMINAL')
    processes = []
    for role, pid, expected in (('supervisor', start['pid'], start['process_start']),
                                ('child', launched['pid'], None)):
        row = probe(pid)
        require(type(row) is dict and row.get('pid') == pid
                and row.get('state') in ('absent', 'exited'), 'LIVE_OR_UNKNOWN_OWNED_PID')
        processes.append({'role': role, 'expected_process_start': expected, **row})
    child_exit_path = host / 'owner/process-exit.json'
    child_exit = {'status': 'UNKNOWN', 'exit_code': None, 'reason': 'actual child receipt missing'}
    if child_exit_path.exists():
        observed = read_json(child_exit_path)
        require(observed.get('pid') == launched['pid'] and type(observed.get('exit_code')) is int,
                'CHILD_EXIT_BINDING')
        child_exit = {'status': 'RECORDED', 'exit_code': observed['exit_code'],
                      'receipt': child_exit_path.relative_to(studio).as_posix()}
    require(raw_manifest(studio, roots) == raw, 'RAW_CHANGED_DURING_COLLECTION')
    verify_sources(studio, plan)
    report = {'schema': 'HH-GT06-O9-CLOSEOUT-1', 'campaign_id': campaign_id, 'host_id': host_id,
              'observed_utc': datetime.now(timezone.utc).isoformat(), 'formal_acceptance': False,
              'scope': 'Failed pre-formal quiet chain; administrative closeout only',
              'classification': failure['classification'], 'failure_code': failure['code'],
              'classification_source': (host / 'owner-failure.json').relative_to(studio).as_posix(),
              'source_closure_sha256': plan['source_closure_sha256'], 'frozen_source_rehashed': True,
              'wrapper_return_code': returned['returned_exit_code'],
              'owner_helper_wrapper_exit_code': cleanup.get('wrapper_exit_code'),
              'actual_child_exit': child_exit, 'child_capture_present': (host / 'owner/capture.json').is_file(),
              'natural_child_exit': 'UNPROVEN', 'scheduler': status, 'process_observations': processes,
              'cleanup': cleanup, 'cleanup_binding': 'exact host path, invocation, source manifest and raw hashes',
              'task_retirement_eligible': True, 'task_deleted': False,
              'acceptance_verified': False, 'utility_sha256': digest(Path(__file__)),
              'task_control_sha256': digest(studio / 'tests/replay/campaign_task.ps1')}
    return report, raw, status_raw


def write_new(path, value):
    plain(path.parent)
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    require(digest(path) == hashlib.sha256(raw).hexdigest(), 'WRITE_READBACK')


def closeout(studio, campaign_id, *, write=False, delete_task=False,
             scheduler=task_command, probe=observe_pid):
    require(not delete_task or write, 'DELETE_REQUIRES_WRITE')
    report, raw, status_raw = collect(studio, campaign_id, scheduler=scheduler, probe=probe)
    if not write:
        return report
    output = plain(studio / '.local/reviews' / (campaign_id + '-closeout'))
    require(not output.exists(), 'CLOSEOUT_ALREADY_EXISTS')
    output.mkdir()
    write_new(output / 'raw-manifest.json', {'schema': 'HH-GT06-O9-RAW-HASHES-1',
              'campaign_id': campaign_id, 'files': raw, 'raw_retained_in_place': True})
    write_new(output / 'scheduler-status.json', status_raw)
    write_new(output / 'closeout.json', report)
    if delete_task:
        # Revalidate immediately before mutation; a restarted task or changed
        # source/evidence cannot be retired using an earlier snapshot.
        again, fresh_raw, _ = collect(studio, campaign_id, scheduler=scheduler, probe=probe)
        require(fresh_raw == raw and again['task_retirement_eligible'], 'PREDELETE_DRIFT')
        deleted, deleted_raw = scheduler(studio, campaign_id, 'delete')
        receipt = read_json(studio / '.local/reviews' / (campaign_id + '-supervisor/task-deleted.json'))
        require(deleted == receipt and receipt.get('schema') == 'HH-GT06-TASK-DELETED-1'
                and receipt.get('campaign_id') == campaign_id
                and receipt.get('task_path') == report['scheduler']['task_path']
                and receipt.get('task_definition_sha256') == read_json(
                    studio / '.local/reviews' / (campaign_id + '-supervisor/task-registration.json'))['task_definition_sha256']
                and receipt.get('launch_number') == 1 and receipt.get('formal_acceptance') is False,
                'DELETE_RECEIPT_UNPROVEN')
        write_new(output / 'task-deletion.json', {'receipt': receipt, 'command': deleted_raw,
                  'receipt_sha256': digest(studio / '.local/reviews' /
                                           (campaign_id + '-supervisor/task-deleted.json'))})
        report = {**report, 'task_deleted': True}
        write_new(output / 'closeout-after-delete.json', report)
    return {**report, 'output_directory': str(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-id', required=True)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--delete-task', action='store_true')
    args = parser.parse_args(argv)
    try:
        result = closeout(STUDIO, args.campaign_id, write=args.write, delete_task=args.delete_task)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({'closeout_error': str(error), 'formal_acceptance': False}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
