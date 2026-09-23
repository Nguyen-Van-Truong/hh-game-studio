"""S187: fixed idle-editor control. Default prepares only, never launches an engine.

One fresh diagnostic ID, current accepted fixture, pinned binary, 720 s native
idle window, 780 s editor-owner deadline, original Job limits. Every 250 ms the
retained editor process handle provides GetProcessHandleCount. No fake handles,
counter adjustment, native-cycle/HTTP workload, or formal acceptance.
"""
from pathlib import Path
import argparse
import ctypes
from ctypes import wintypes as w
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDIO = ROOT / 'studio'
sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess
from studio.host.replay.process_probe import ProcessProbe
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage

RUN_ID = 'gt06-s187-idle-editor-01'
RAW = STUDIO / '.local/reviews' / RUN_ID
PROJECT = RAW / 'project'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def pinned_files():
    paths = [HERE / 'idle.gd', Path(__file__), STUDIO / 'toolchain.lock.json']
    paths += [p for p in PROJECT.rglob('*') if p.is_file() and '.godot' not in p.parts]
    for module in tuple(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            p = Path(name).resolve()
            if p.is_relative_to(STUDIO) and p.suffix == '.py':
                paths.append(p)
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))}


def verify(files):
    for rel, digest in files.items():
        if sha(ROOT / rel) != digest:
            raise RuntimeError('S187_FROZEN_SOURCE_CHANGED:' + rel)


def prepare():
    factory, trusted = native.load_fixture()
    if RAW.exists():
        raise RuntimeError('S187_ALREADY_PREPARED_INSPECT_EXISTING')
    PROJECT.mkdir(parents=True)
    files = dict(trusted)
    files['project.godot'] = native.benchmark_project_config(files['project.godot']).replace(
        b'res://addons/hh_benchmark/plugin.cfg', b'res://addons/hh_idle/plugin.cfg')
    files['scenes/fixture.tscn'] = factory.DEFAULT_SCENE
    files['scripts/fixture_actor.gd'] = factory.DEFAULT_SCRIPT
    files['addons/hh_idle/idle.gd'] = (HERE / 'idle.gd').read_bytes()
    files['addons/hh_idle/plugin.cfg'] = b'[plugin]\nname="S187 idle diagnostic"\ndescription="Diagnostic only"\nauthor="HH Studio"\nversion="1.0"\nscript="idle.gd"\n'
    for rel, value in files.items():
        dst = PROJECT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(value)
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    exe = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    if sha(exe) != lock['gui_sha256']:
        raise RuntimeError('S187_BINARY_PIN')
    freeze = {'run_id': RUN_ID, 'authority': 0, 'formal_acceptance': False,
        'executable': str(exe), 'binary_sha256': lock['gui_sha256'],
        'source_files': pinned_files(), 'native_seconds': 720,
        'editor_deadline_seconds': 780, 'sample_interval_seconds': .25,
        'hypothesis': 'Do editor handles fluctuate over 12 minutes without HTTP or native mutation cycles?',
        'limits': 'No attribution to specific kernel objects; no formal gate or root-cause claim.'}
    write(RAW / 'prepare.json', freeze)
    print(json.dumps({'prepared': RUN_ID, 'engine_started': False, 'files': len(freeze['source_files'])}))


def run():
    freeze = json.loads((RAW / 'prepare.json').read_bytes())
    verify(freeze['source_files'])
    write(RAW / 'run-claim.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    exe = freeze['executable']
    # Parse before any editor activation; import does not receive the opt-in flag.
    for role, args in (
        ('parse', ['--headless', '--path', str(PROJECT), '--check-only', '--script', 'res://addons/hh_idle/idle.gd']),
        ('import', ['--headless', '--editor', '--path', str(PROJECT), '--import'])):
        out = RAW / (role + '-host')
        run_trusted_stage([exe, *args], cwd=PROJECT, output=out, source_root=ROOT,
            source_files=freeze['source_files'], binary_sha256=freeze['binary_sha256'])
        verify_captured_stage(out, sha(out / 'capture.json'))
        if (out / 'stderr.txt').read_bytes().strip():
            raise RuntimeError('S187_PREFLIGHT_STDERR:' + role)
    # Import may add UID files. Freeze those before launching the long editor lane.
    verify(freeze['source_files'])
    runtime_files = pinned_files()
    write(RAW / 'runtime-freeze.json', {'files': runtime_files, 'formal_acceptance': False})
    owner = probe = None
    rows = 0
    try:
        owner = BenchmarkProcess([exe, '--editor', '--path', str(PROJECT),
            'res://scenes/fixture.tscn', '--', '--hh-s187-idle'], cwd=PROJECT,
            output=RAW / 'editor-host', source_root=ROOT,
            source_files=runtime_files, binary_sha256=freeze['binary_sha256'])
        launched = time.monotonic()
        while not (owner.output / 'process-start.json').exists():
            if owner.tick() is not None or time.monotonic() - launched > 15:
                raise RuntimeError('S187_START_FAILED')
            time.sleep(.05)
        pid = json.loads((owner.output / 'process-start.json').read_bytes())['pid']
        probe = ProcessProbe(pid, Path(exe))
        count = w.DWORD()
        api = probe.k.GetProcessHandleCount
        api.argtypes, api.restype = [w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL
        # Prove counter capability before waiting for the idle window.
        if not api(probe.handle, ctypes.byref(count)):
            raise ctypes.WinError(ctypes.get_last_error())
        write(RAW / 'sampling-start.json', {'pid': pid, 'process_start': probe.process_start,
            'executable': exe, 'initial_handles': count.value,
            'sampler': 'GetProcessHandleCount(retained ProcessProbe handle)',
            'helper_pid': owner.process.pid, 'observer_pid': os.getpid(), 'formal_acceptance': False})
        with (RAW / 'handles.jsonl').open('x', encoding='utf-8') as log:
            while owner.tick() is None:
                if time.monotonic() - launched > 780:
                    raise RuntimeError('S187_EDITOR_DEADLINE')
                sample = probe.sample()
                if sample is None:
                    time.sleep(.05)
                    continue
                if not api(probe.handle, ctypes.byref(count)):
                    raise ctypes.WinError(ctypes.get_last_error())
                sample.update(pid=pid, process_start=probe.process_start, held_handles=count.value)
                log.write(json.dumps(sample, separators=(',', ':')) + '\n')
                rows += 1
                if rows % 20 == 0:
                    log.flush()
                time.sleep(.25)
        capture = owner.finish()
        probe.close()
        output = (owner.output / 'stdout.txt').read_text(encoding='utf-8')
        completed = [json.loads(line.split(' ', 1)[1]) for line in output.splitlines() if line.startswith('HH_S187_COMPLETE ')]
        if len(completed) != 1 or completed[0]['pid'] != pid or completed[0]['elapsed_us'] < 720000000:
            raise RuntimeError('S187_NATIVE_COMPLETION')
        if (owner.output / 'stderr.txt').read_bytes().strip():
            raise RuntimeError('S187_EDITOR_STDERR')
        write(RAW / 'result.json', {'run_id': RUN_ID, 'authority': 0, 'formal_acceptance': False,
            'completed_idle_control': True, 'sample_count': rows, 'native_completion': completed[0],
            'actual_target_exit': capture['actual_process_exit'], 'helper_exit': capture['wrapper_exit_code'],
            'job': capture['job'], 'probe_released': probe.handle is None,
            'samples_sha256': sha(RAW / 'handles.jsonl'), 'capture_sha256': sha(owner.output / 'capture.json')})
    finally:
        # Existing owner retains cleanup evidence on failure; no foreign PID kill.
        if probe is not None and probe.handle is not None:
            probe.close()
        if owner is not None and not owner.closed:
            owner.close()


def supervise():
    # Detached supervisor captures this diagnostic driver's actual exit.
    write(RAW / 'supervisor-start.json', {'pid': os.getpid(), 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat()})
    with (RAW / 'driver-stdout.txt').open('xb') as out, (RAW / 'driver-stderr.txt').open('xb') as err:
        child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), '--run'],
            stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
        write(RAW / 'driver-start.json', {'pid': child.pid})
        timed_out = False
        try:
            code = child.wait(timeout=850)
        except subprocess.TimeoutExpired:
            timed_out = True
            child.terminate()  # This driver's Job handles close and kill its owned tree.
            code = child.wait(timeout=30)
        write(RAW / 'driver-exit.json', {'pid': child.pid, 'exit_code': code, 'timed_out': timed_out})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--run', action='store_true')
    mode.add_argument('--supervise', action='store_true')
    args = parser.parse_args()
    if args.supervise:
        supervise()
    elif args.run:
        try:
            run()
        except BaseException as error:
            write(RAW / 'driver-failure.json', {'error_type': type(error).__name__, 'message': str(error), 'formal_acceptance': False})
            raise
    else:
        prepare()
