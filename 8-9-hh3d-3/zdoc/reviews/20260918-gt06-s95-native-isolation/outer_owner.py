"""One-use detached owner for fixed S95 native isolation; no self-exit claim.

Task Scheduler runs pythonw -B outer_owner.py --observe. A gated child becomes
native_isolation in the same PID after assignment to a checked seven-slot Job.
S93 ownership primitives observe its actual exit and close retained handles.
Scheduler observes this owner's own exit. Inner benchmark limits stay intact.
No task or engine is launched merely by importing this file.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import runpy
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[2]
STUDIO = ROOT / 'studio'
RUN_ID = 'gt06-s95-native-isolation-01'
REQUEST = BASE / 'launch-01/request.json'
OUTPUT = STUDIO / '.local/reviews' / (RUN_ID + '-outer')
NATIVE_OUTPUT = STUDIO / '.local/reviews' / RUN_ID
WALL_SECONDS = 2160
OWNERSHIP_SOURCE = ROOT / 'zdoc/reviews/20260918-gt06-s93-sparse-attribution/launch_observer.py'
FALSE_FLAGS = {'formal_acceptance': False, 'full_benchmark': False, 'eligible_for_dataset': False}


def need(value, code):
    if not value:
        raise RuntimeError(code)


def plain(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.exists():
            info = part.lstat()
            need(not part.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'OUTER_REPARSE')
    return path


def sha(path):
    return hashlib.sha256(plain(path).read_bytes()).hexdigest()


def read(path):
    path = plain(path)
    need(path.is_file() and 0 < path.stat().st_size <= 1024 * 1024, 'OUTER_JSON_SIZE')
    return json.loads(path.read_bytes())


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with plain(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def verify_request(request):
    need(set(request) == {'schema', 'run_id', 'source_sha256', 'helper_sha256', 'native_pins', 'outer_files',
                         'python', 'pythonw', 'python_sha256', 'pythonw_sha256', 'working_directory',
                         'wall_seconds', 'ownership_source_sha256', 'formal_acceptance'}, 'OUTER_REQUEST_FIELDS')
    need(request['schema'] == 'HH-GT06-S95-NATIVE-OUTER-1' and request['run_id'] == RUN_ID
         and request['wall_seconds'] == WALL_SECONDS and request['formal_acceptance'] is False
         and Path(request['working_directory']) == STUDIO, 'OUTER_REQUEST_BINDING')
    console, windowed = Path(request['python']), Path(request['pythonw'])
    need(console.is_absolute() and console.name.lower() == 'python.exe'
         and windowed == console.with_name('pythonw.exe')
         and sha(console) == request['python_sha256'] and sha(windowed) == request['pythonw_sha256'], 'OUTER_PYTHON_PIN')
    need(set(request['outer_files']) == {'outer_owner.py', 'register_task.ps1'}
         and all(sha(BASE / name) == digest for name, digest in request['outer_files'].items()), 'OUTER_HELPER_PIN')
    need(sha(OWNERSHIP_SOURCE) == request['ownership_source_sha256'], 'OUTER_OWNERSHIP_SOURCE_PIN')
    # Separate interpreter preserves the exact --describe closure: importing
    # this owner into that interpreter would add unrelated dependency modules.
    checked = subprocess.run([str(console), '-B', str(BASE / 'native_isolation.py'), '--describe'],
        cwd=ROOT, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    need(checked.returncode == 0 and not checked.stderr.strip(), 'OUTER_DESCRIBE_EXIT')
    description = json.loads(checked.stdout)
    pins = description['pins']
    need(description['launch_performed'] is False and pins == request['native_pins']
         and pins['source_closure_sha256'] == request['source_sha256']
         and pins['helper_closure_sha256'] == request['helper_sha256'], 'OUTER_NATIVE_PIN')
    return console, pins


def ownership_module():
    spec = importlib.util.spec_from_file_location('_s95_s93_ownership', OWNERSHIP_SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    need(module.OUTER_PROCESS_LIMIT == 7, 'OUTER_PRIMITIVE_PROCESS_LIMIT')
    return module


def fixed_native_argv(request):
    return [str(BASE / 'native_isolation.py'), '--mode', 'isolation', '--run-id', RUN_ID,
            '--source-sha256', request['source_sha256'], '--helper-sha256', request['helper_sha256']]


def gated_child():
    need(sys.stdin.buffer.readline(16) == b'START\n', 'OUTER_START_GATE')
    request = read(REQUEST)
    console, _ = verify_request(request)
    need(Path(sys.executable).resolve() == console.resolve(), 'OUTER_GATED_EXECUTABLE')
    # No extra wrapper PID: this exact retained process becomes the native
    # supervisor. Its subprocesses retain their unchanged HOST/editor quotas.
    sys.argv = fixed_native_argv(request)
    runpy.run_path(str(BASE / 'native_isolation.py'), run_name='__main__')
    return 0


def observe():
    need(os.name == 'nt' and Path(sys.executable).name.lower() == 'pythonw.exe', 'OUTER_WINDOWLESS_REQUIRED')
    request = read(REQUEST)
    console, pins = verify_request(request)
    need(Path(sys.executable).resolve() == Path(request['pythonw']).resolve(), 'OUTER_EXECUTABLE_IDENTITY')
    need(not os.path.lexists(NATIVE_OUTPUT), 'OUTER_NATIVE_RUN_ALREADY_USED')
    plain(OUTPUT).mkdir(exist_ok=False)
    write(OUTPUT / 'request-copy.json', request)
    sys.path.insert(0, str(ROOT))
    from studio.host.blender.ui_host import cli_job
    primitive = ownership_module()
    sources = {'studio/' + path: digest for path, digest in pins['source_files'].items()}
    sources.update({(BASE / name).relative_to(ROOT).as_posix(): digest for name, digest in pins['helper_files'].items()})
    sources.update({(BASE / name).relative_to(ROOT).as_posix(): digest for name, digest in request['outer_files'].items()})
    sources[OWNERSHIP_SOURCE.relative_to(ROOT).as_posix()] = request['ownership_source_sha256']
    for relative, digest in sources.items():
        need(sha(ROOT / relative) == digest, 'OUTER_SOURCE_CHANGED_BEFORE_DISPATCH')
    argv = [str(console), '-B', str(Path(__file__).resolve()), '--gated-child']
    write(OUTPUT / 'invocation.json', {**FALSE_FLAGS, 'run_id': RUN_ID, 'argv': argv,
        'source_files': sources, 'wall_seconds': WALL_SECONDS, 'ownership': 'S93_checked_seven_slot_outer_Job',
        'native_argv_after_gate': fixed_native_argv(request), 'extra_outer_helper_process': False,
        'request_sha256': sha(REQUEST), 'outer_self_exit_observed': False})
    process = job = target = None
    streams, errors = [], []
    limits = None
    supervisor_code = active_before = None
    timed_out = False
    popen_closed = False
    result = {**FALSE_FLAGS, 'run_id': RUN_ID, 'completed_diagnostic': False,
              'outer_self_exit_observed': False, 'outer_self_exit_source': 'Task Scheduler; not this report'}
    started = time.monotonic()
    try:
        streams = [(OUTPUT / name).open('xb') for name in ('supervisor-stdout.txt', 'supervisor-stderr.txt')]
        process = subprocess.Popen(argv, cwd=OUTPUT, stdin=subprocess.PIPE, stdout=streams[0], stderr=streams[1],
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        job = cli_job.create(process)
        reused = primitive.configure_outer(job)
        # configure_outer sets/readbacks only native Job flags and active count.
        # Its S93 wall field is descriptive, not a timer. This owner enforces its
        # own explicit 2160s watchdog and does not mutate the imported module.
        limits = {'native_limit_flags': reused['limit_flags'], 'process_limit': reused['process_limit'],
                  'wall_seconds': WALL_SECONDS, 'wall_enforcement': 's95_observer_watchdog',
                  'reused_s93_descriptive_wall_seconds': reused['wall_seconds'],
                  's93_descriptive_wall_is_not_applied': True, 'inner_benchmark_limits_changed': False}
        need(limits['process_limit'] == 7, 'OUTER_CHECKED_SEVEN_SLOT_LIMIT')
        target = primitive.Retained(process.pid, console, expected_parent=os.getpid())
        write(OUTPUT / 'supervisor-adoption.json', {**FALSE_FLAGS, 'process': target.row, 'limits': limits})
        process.stdin.write(b'START\n')
        process.stdin.close()
        while True:
            target.observe_exit()
            supervisor_code = process.poll()
            if supervisor_code is not None:
                break
            if time.monotonic() - started >= WALL_SECONDS:
                timed_out = True
                raise TimeoutError('OUTER_WALL_LIMIT')
            time.sleep(.05)
        # A natural target exit must also leave no descendants before cleanup.
        deadline = time.monotonic() + .5
        active_before = job.active_count()
        while active_before and time.monotonic() < deadline:
            time.sleep(.01)
            active_before = job.active_count()
        need(supervisor_code == 0 and target.observe_exit()
             and target.row['actual_exit']['exit_code_uint32'] == 0 and active_before == 0, 'OUTER_NATURAL_COMPLETION')
    except BaseException as error:
        errors.append({'stage': 'body', 'type': type(error).__name__, 'code': getattr(error, 'code', str(error))[:240]})
    finally:
        if process is not None and job is None:
            job = cli_job.owner_for_process(process)
        if job is not None:
            try:
                if active_before is None:
                    active_before = job.active_count()
                job.close()
            except BaseException as error:
                errors.append({'stage': 'job_close', 'code': str(error)[:240]})
        elif process is not None and process.poll() is None:
            # No START was sent without an assigned/configured Job. This exact
            # gated child cannot have spawned the native supervisor workload.
            process.kill()
        if process is not None:
            try:
                supervisor_code = process.wait(timeout=5)
            except BaseException as error:
                errors.append({'stage': 'supervisor_wait', 'code': str(error)[:240]})
        if target is not None:
            try:
                target.kernel.WaitForSingleObject(target.probe.handle, 1000)
                need(target.observe_exit(), 'OUTER_ACTUAL_EXIT_UNOBSERVED')
                write(OUTPUT / 'supervisor-exit.json', target.row)
            except BaseException as error:
                errors.append({'stage': 'retained_exit', 'code': str(error)[:240]})
            finally:
                try:
                    target.close()
                except BaseException as error:
                    errors.append({'stage': 'retained_handle_close', 'code': str(error)[:240]})
        for ordinal, stream in enumerate(streams):
            try:
                stream.close()
            except BaseException as error:
                errors.append({'stage': f'stream_close_{ordinal}', 'code': str(error)[:240]})
        if process is not None:
            try:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.close()
                primitive.close_popen_handle(process)
                popen_closed = True
            except BaseException as error:
                errors.append({'stage': 'popen_handle_close', 'code': str(error)[:240]})
        try:
            verify_request(request)
            need(read(REQUEST) == request, 'OUTER_REQUEST_CHANGED')
            native = read(NATIVE_OUTPUT / 'supervisor-result.json')
            need(native['completed_diagnostic'] is True and all(native[key] is False for key in FALSE_FLAGS), 'OUTER_NATIVE_RESULT')
        except BaseException as error:
            errors.append({'stage': 'final_binding', 'code': str(error)[:240]})
        clean = (not errors and not timed_out and supervisor_code == 0 and active_before == 0
                 and target is not None and target.row['actual_exit'] is not None
                 and target.row['actual_exit']['exit_code_uint32'] == 0 and target.row['handle_closed']
                 and popen_closed and job is not None and job.closed and job.zero_observed and not job.tainted)
        code = 0 if clean else 1
        result.update(completed_diagnostic=bool(clean), actual_supervisor_exit=target.row if target else None,
                      supervisor_popen_actual_exit_code=supervisor_code, popen_handle_closed=popen_closed,
                      actual_supervisor_exit_missing=target is None or target.row['actual_exit'] is None,
                      outer_job_active_before_cleanup=active_before, job=job.snapshot() if job else None,
                      limits=limits, errors=errors, timed_out=timed_out, extra_outer_helper_process=False)
        result['elapsed_seconds'] = time.monotonic() - started
        result['intended_outer_return_code'] = code
        write(OUTPUT / 'terminal.json', result)
    return code


if __name__ == '__main__':
    need(sys.argv[1:] in (['--observe'], ['--gated-child']), 'OUTER_FIXED_MODE')
    try:
        raise SystemExit(observe() if sys.argv[1:] == ['--observe'] else gated_child())
    except Exception as error:
        # May precede output creation; exclusive sibling error file preserves
        # startup failures without claiming this owner's eventual process exit.
        write(BASE / 'launch-01/outer-startup-failure.json', {**FALSE_FLAGS, 'run_id': RUN_ID,
            'type': type(error).__name__, 'code': str(error)[:240], 'outer_self_exit_observed': False})
        raise
