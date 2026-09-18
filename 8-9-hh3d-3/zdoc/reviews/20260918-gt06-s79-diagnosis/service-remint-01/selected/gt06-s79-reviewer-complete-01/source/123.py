"""Internal harness for trusted GT05 stages, reusing existing Job ownership.

Not a public execution API. The coordinator binds a fixed trusted command and
its complete source before calling this; remote commands must never reach it.
Raw logs belong in a new private .local run directory, not portable evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import stat
from pathlib import Path
import subprocess
import sys
import threading
import time

from studio.host.blender.ui_host import HELPER, cli_job
from studio.host.blender.export_job import (
    configure_limits, DISK_BYTES, LOG_BYTES, WALL_SECONDS,
)


class StageFailed(RuntimeError):
    def __init__(self, code, *, cleanup_owner=None):
        super().__init__(code)
        self.cleanup_owner = cleanup_owner


def _write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def isolated_env(directory: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith(('PYTHON', 'BLENDER_', 'HH_', 'GODOT_', 'NODE_', 'NPM_CONFIG_'))}
    for key, folder in (
        ('BLENDER_USER_RESOURCES', 'blender-user'), ('APPDATA', 'appdata'),
        ('LOCALAPPDATA', 'localappdata'), ('TEMP', 'temp'), ('TMP', 'temp'),
    ):
        path = directory / folder
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def _workspace_size(root):
    size = 0
    for path in root.rglob('*'):
        try:
            info = path.stat(follow_symlinks=False)
        except FileNotFoundError:
            # Owned scratch files may be removed between enumeration and stat.
            # A polling watchdog is not a filesystem reservation/quota primitive.
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise StageFailed('STAGE_REPARSE')
        if stat.S_ISREG(info.st_mode):
            size += info.st_size
        if size > DISK_BYTES:
            raise StageFailed('STAGE_DISK_CAP')
    return size


def _combined_workspace_size(cwd, output):
    size = _workspace_size(cwd)
    if not output.is_relative_to(cwd):
        size += _workspace_size(output)
    if size > DISK_BYTES:
        raise StageFailed('STAGE_DISK_CAP')
    return size


def verify_captured_stage(output: Path, expected_sha256: str) -> dict:
    """Re-derive a completed stage from its exact captured process records."""
    raw = (output / 'capture.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise StageFailed('CAPTURE_HASH')
    report = json.loads(raw)
    required = {'stdout.txt', 'stderr.txt', 'process-start.json', 'process-exit.json'}
    if set(report.get('artifacts', {})) != required:
        raise StageFailed('CAPTURE_ARTIFACT_SET')
    for name, digest in report['artifacts'].items():
        if hashlib.sha256((output / name).read_bytes()).hexdigest() != digest:
            raise StageFailed('CAPTURE_ARTIFACT_HASH')
    started = json.loads((output / 'process-start.json').read_bytes())
    exited = json.loads((output / 'process-exit.json').read_bytes())
    job = report.get('job', {})
    if (set(started) != {'pid'} or type(started['pid']) is not int or started['pid'] <= 0
            or set(exited) != {'pid', 'exit_code'} or type(exited['pid']) is not int
            or type(exited['exit_code']) is not int or exited['exit_code'] != 0
            or exited['pid'] != started['pid'] or report.get('actual_process_exit') != exited
            or type(report.get('wrapper_exit_code')) is not int or report['wrapper_exit_code'] != 0
            or report.get('completed') is not True or report.get('natural_tree_exit') is not True
            or type(report.get('active_before_cleanup')) is not int or report['active_before_cleanup'] != 0
            or job.get('closed') is not True or job.get('zero_observed') is not True
            or job.get('tainted') is not False or job.get('handle_retained') is not False):
        raise StageFailed('CAPTURE_PROCESS_BINDING')
    return report


def run_trusted_stage(argv: list[str], *, cwd: Path, output: Path,
                      source_files: dict[str, str], source_root: Path,
                      binary_sha256: str, timeout_seconds: float = WALL_SECONDS,
                      stop: threading.Event | None = None) -> dict:
    """One fresh stage, 20s wall / 15s Job CPU / 2GiB memory / bounded streams.

    The command is internal and hash-bound by its caller. All paths must be in
    the coordinator's disposable workspace. No successful retry hides a failed
    attempt: use a new output directory and preserve the old capture.
    """
    if os.name != 'nt':
        raise StageFailed('STAGE_WINDOWS_REQUIRED')
    if not argv or not source_files or any(type(arg) is not str for arg in argv):
        raise StageFailed('STAGE_INVOCATION')
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or not 0 < timeout_seconds <= WALL_SECONDS):
        raise StageFailed('STAGE_TIMEOUT_RANGE')
    source_root = source_root.absolute()

    def check_sources():
        for name, digest in source_files.items():
            if (type(name) is not str or Path(name).is_absolute() or '\\' in name
                    or any(part in ('..', '.', '') for part in name.split('/'))):
                raise StageFailed('STAGE_SOURCE_PATH')
            path = source_root / name
            if (not path.is_file() or path.is_symlink()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
                raise StageFailed('STAGE_SOURCE_CHANGED')

    check_sources()
    if hashlib.sha256(Path(argv[0]).read_bytes()).hexdigest() != binary_sha256:
        raise StageFailed('STAGE_BINARY_PIN')
    output = output.absolute()
    cwd = cwd.absolute()
    for path in (cwd, output.parent, Path(argv[0]).absolute()):
        for part in (path, *path.parents):
            info = part.stat(follow_symlinks=False)
            if part.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise StageFailed('STAGE_REPARSE')
    output.mkdir(exist_ok=False)
    env = isolated_env(output)
    _write(output / 'invocation.json', {'argv': argv, 'source_files': source_files,
                                      'binary_sha256': binary_sha256,
                                      'cwd': str(cwd), 'formal_acceptance': False})
    overflow = threading.Event()
    drain_errors: list[str] = []
    process = job = None
    threads: list[threading.Thread] = []
    failure = cleanup_failure = None
    report = {'completed': False, 'formal_acceptance': False, 'public_ack': False}

    def drain(name, pipe):
        count = 0
        try:
            with (output / (name + '.txt')).open('xb') as target:
                while True:
                    raw = pipe.read1(4096)
                    if not raw:
                        break
                    target.write(raw[:max(0, LOG_BYTES - count)])
                    count += len(raw)
                    if count > LOG_BYTES:
                        overflow.set()
        except BaseException as exc:
            drain_errors.append(type(exc).__name__)
            overflow.set()
        finally:
            pipe.close()

    start = time.monotonic()
    try:
        process = subprocess.Popen(
            [sys.executable, '-B', '-c', HELPER, str(output / 'process'), *argv],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
        job = cli_job.create(process)
        report['limits'] = configure_limits(job)
        report['limits']['effective_wall_seconds'] = timeout_seconds
        for name, pipe in (('stdout', process.stdout), ('stderr', process.stderr)):
            thread = threading.Thread(target=drain, args=(name, pipe), daemon=True)
            threads.append(thread)
            thread.start()
        check_sources()
        if stop is not None and stop.is_set():
            raise StageFailed('STAGE_STOPPED')
        process.stdin.write(b'{}\n')
        process.stdin.close()
        while process.poll() is None:
            if time.monotonic() - start > timeout_seconds:
                raise StageFailed('STAGE_WALL_LIMIT')
            if stop is not None and stop.is_set():
                raise StageFailed('STAGE_STOPPED')
            if overflow.is_set():
                raise StageFailed('STAGE_LOG_CAP_OR_IO')
            _combined_workspace_size(cwd, output)
            time.sleep(.02)
        report['active_at_wrapper_exit'] = job.active_count()
        report['active_before_cleanup'] = report['active_at_wrapper_exit']
        # Observe natural drain only. Some exits signal the process handle just
        # before the Job accounting snapshot reaches zero. Never kill here and
        # then call that natural completion; cleanup below records failures.
        settle_deadline = min(start + timeout_seconds, time.monotonic() + .5)
        while report['active_before_cleanup'] and time.monotonic() < settle_deadline:
            time.sleep(.01)
            report['active_before_cleanup'] = job.active_count()
        report['natural_tree_exit'] = report['active_before_cleanup'] == 0
        if not report['natural_tree_exit']:
            raise StageFailed('STAGE_DESCENDANTS_REMAIN')
        for thread in threads:
            thread.join(2)
        if any(thread.is_alive() for thread in threads) or drain_errors or overflow.is_set():
            raise StageFailed('STAGE_STREAM_DRAIN')
        report['final_workspace_bytes'] = _combined_workspace_size(cwd, output)
        check_sources()
        actual = json.loads((output / 'process-exit.json').read_bytes())
        launched = json.loads((output / 'process-start.json').read_bytes())
        if (type(actual.get('exit_code')) is not int or actual['exit_code'] != 0
                or process.returncode != 0 or type(actual.get('pid')) is not int
                or actual['pid'] != launched.get('pid')):
            raise StageFailed('STAGE_NATIVE_EXIT')
        report.update(completed=True, actual_process_exit=actual)
    except BaseException as exc:
        failure = exc
        report['failure'] = str(exc) if isinstance(exc, StageFailed) else type(exc).__name__
    finally:
        try:
            if job is None and process is not None:
                job = cli_job.owner_for_process(process)
            if job is not None:
                job.close()
            elif process is not None and process.poll() is None:
                process.kill()  # Unreleased helper only, before a successful Job assignment.
            if process is not None:
                process.wait(timeout=3)
            for thread in threads:
                thread.join(2)
            if any(thread.is_alive() for thread in threads):
                raise StageFailed('STAGE_CLEANUP_DRAIN')
            if process is not None:
                for pipe in (process.stdin, process.stdout, process.stderr):
                    if pipe is not None and not pipe.closed:
                        pipe.close()
        except BaseException as exc:
            cleanup_failure = exc
            report['cleanup_failure'] = type(exc).__name__
        report.update(wrapper_exit_code=process.returncode if process else None,
                      job=job.snapshot() if job else None,
                      elapsed_seconds=time.monotonic() - start)
        if job is None or not job.closed or job.tainted or not job.zero_observed:
            report['completed'] = False
        if failure is not None or cleanup_failure is not None:
            report['completed'] = False
        for name in ('process-start.json', 'process-exit.json', 'stdout.txt', 'stderr.txt'):
            path = output / name
            if path.is_file():
                report.setdefault('artifacts', {})[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        _write(output / 'capture.json', report)
    if cleanup_failure is not None:
        raise StageFailed('STAGE_CLEANUP_HELD', cleanup_owner=job) from cleanup_failure
    if failure is not None:
        raise failure
    if report['completed'] is not True:
        raise StageFailed('STAGE_INCOMPLETE', cleanup_owner=job)
    return report
