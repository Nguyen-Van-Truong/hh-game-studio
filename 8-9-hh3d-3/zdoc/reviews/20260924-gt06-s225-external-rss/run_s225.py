"""Bounded S225 diagnostic: external identity-bound RSS/handle sampler."""
from __future__ import annotations
import argparse, ctypes, hashlib, json, os, shutil, subprocess, sys, time, zipfile
from ctypes import wintypes as w
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
STUDIO = ROOT / 'studio'
RAW = STUDIO / '.local/reviews/gt06-s225-external-rss'
PROJECT = RAW / 'project'
RUN_ID = 'gt06-s225-external-rss-01'

sys.path.insert(0, str(ROOT))
from studio.tests.replay import run_native_benchmark as native
from studio.tests.replay.benchmark_job import BenchmarkProcess, require
from studio.pipeline.native_job import run_trusted_stage, verify_captured_stage


def sha_bytes(raw): return hashlib.sha256(raw).hexdigest()
def sha(path): return sha_bytes(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    require(path.read_bytes() == raw, 'S225_READBACK')


def project_files():
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(PROJECT.rglob('*'))
            if p.is_file() and '.godot' not in p.parts}


def prepare():
    require(not RAW.exists(), 'S225_ALREADY_EXISTS')
    source = STUDIO / '.local/reviews/gt06-s194-external-sampler-01/project'
    require(source.is_dir(), 'S225_SOURCE_PROJECT')
    RAW.mkdir(parents=True)
    shutil.copytree(source, PROJECT, ignore=shutil.ignore_patterns('.godot'))
    # Keep only the accepted idle diagnostic plugin; no benchmark activation.
    files = project_files()
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    freeze = {'schema_id': 'hh-studio.gt06-s225-preflight', 'schema_version': '1.0.0',
        'run_id': RUN_ID, 'authority': 0, 'formal_acceptance': False,
        'binary': {'path': str(executable), 'sha256': lock['gui_sha256']},
        'source_files': files, 'duration_seconds': 90, 'sample_interval_seconds': .25,
        'sampler': 'external-process-retained-identity-handle-GetProcessMemoryInfo-and-GetProcessHandleCount',
        'hypothesis': 'Does an independent observer correlate idle editor RSS and handle variation without the campaign driver sampler?',
        'gate_unchanged': True}
    write(RAW / 'prepare.json', freeze)
    print(json.dumps({'prepared': RUN_ID, 'source_files': len(files), 'engine_started': False}))


def observer_api():
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    p = ctypes.WinDLL('psapi', use_last_error=True)
    k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]; k.OpenProcess.restype = w.HANDLE
    k.CloseHandle.argtypes = [w.HANDLE]; k.CloseHandle.restype = w.BOOL
    k.GetProcessTimes.argtypes = [w.HANDLE] + [ctypes.POINTER(w.FILETIME)] * 4; k.GetProcessTimes.restype = w.BOOL
    k.GetProcessHandleCount.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]; k.GetProcessHandleCount.restype = w.BOOL
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]; k.QueryFullProcessImageNameW.restype = w.BOOL
    k.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]; k.WaitForSingleObject.restype = w.DWORD
    class Memory(ctypes.Structure):
        _fields_ = [('cb', w.DWORD), ('page_faults', w.DWORD), ('peak_working_set', ctypes.c_size_t),
            ('working_set', ctypes.c_size_t), ('peak_paged', ctypes.c_size_t), ('paged', ctypes.c_size_t),
            ('peak_nonpaged', ctypes.c_size_t), ('nonpaged', ctypes.c_size_t), ('pagefile', ctypes.c_size_t),
            ('peak_pagefile', ctypes.c_size_t)]
    p.GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(Memory), w.DWORD]; p.GetProcessMemoryInfo.restype = w.BOOL
    return k, p, Memory


def sample_process(pid, executable, out, duration, interval):
    k, p, Memory = observer_api(); handle = None; started = time.monotonic(); rows = []
    out.mkdir(parents=False)
    try:
        while handle is None and time.monotonic() - started < 20:
            handle = k.OpenProcess(0x0400 | 0x1000 | 0x00100000, False, pid)
            if not handle: time.sleep(.05); continue
        require(handle, 'S225_OPEN')
        times = [w.FILETIME() for _ in range(4)]
        require(k.GetProcessTimes(handle, *(ctypes.byref(v) for v in times)), 'S225_START')
        identity = 'windows:' + str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        size, text = w.DWORD(32768), ctypes.create_unicode_buffer(32768)
        require(k.QueryFullProcessImageNameW(handle, 0, text, ctypes.byref(size)), 'S225_IMAGE')
        require(os.path.normcase(text.value) == os.path.normcase(str(executable.resolve())), 'S225_IMAGE_IDENTITY')
        deadline = time.monotonic() + duration
        with (out / 'samples.jsonl').open('x', encoding='utf-8') as log:
            while time.monotonic() < deadline:
                require(k.WaitForSingleObject(handle, 0) == 258, 'S225_TARGET_EXIT_EARLY')
                memory = Memory(); memory.cb = ctypes.sizeof(memory)
                require(p.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb), 'S225_RSS')
                count = w.DWORD(); require(k.GetProcessHandleCount(handle, ctypes.byref(count)), 'S225_HANDLES')
                row = {'sequence': len(rows), 'observer_pid': os.getpid(), 'target_pid': pid,
                    'target_process_start': identity, 'mono_us': time.perf_counter_ns() // 1000,
                    'rss_bytes': int(memory.working_set), 'held_handles': int(count.value)}
                rows.append(row); log.write(json.dumps(row, separators=(',', ':')) + '\n'); log.flush(); time.sleep(interval)
        write(out / 'sampler-result.json', {'schema_id': 'hh-studio.gt06-s225-sampler-result', 'schema_version': '1.0.0',
            'run_id': RUN_ID, 'target_pid': pid, 'target_process_start': identity, 'sample_count': len(rows),
            'target_wait_zero': k.WaitForSingleObject(handle, 0) == 0, 'samples_sha256': sha(out / 'samples.jsonl'),
            'formal_acceptance': False, 'provider': 'GetProcessMemoryInfo.WorkingSetSize',
            'handle_provider': 'GetProcessHandleCount'})
        return 0
    except BaseException as error:
        write(out / 'sampler-failure.json', {'schema_id': 'hh-studio.gt06-s225-sampler-failure', 'run_id': RUN_ID,
            'error_type': type(error).__name__, 'message': str(error), 'sample_count': len(rows), 'formal_acceptance': False})
        return 1
    finally:
        if handle is not None:
            require(k.CloseHandle(handle), 'S225_CLOSE')


def run():
    freeze = json.loads((RAW / 'prepare.json').read_bytes())
    executable = Path(freeze['binary']['path']); require(sha(executable) == freeze['binary']['sha256'], 'S225_BINARY')
    for role, args in [('parse', ['--headless', '--path', str(PROJECT), '--check-only', '--script', 'res://addons/hh_idle/idle.gd']),
                       ('import', ['--headless', '--editor', '--path', str(PROJECT), '--import'])]:
        out = RAW / (role + '-host'); run_trusted_stage([str(executable), *args], cwd=PROJECT, output=out,
            source_root=ROOT, source_files=freeze['source_files'], binary_sha256=freeze['binary']['sha256'])
        verify_captured_stage(out, sha(out / 'capture.json')); require(not (out / 'stderr.txt').read_bytes(), 'S225_PREFLIGHT_STDERR')
    owner = BenchmarkProcess([str(executable), '--editor', '--path', str(PROJECT), 'res://scenes/fixture.tscn', '--', '--hh-s194-idle'],
        cwd=PROJECT, output=RAW / 'editor-host', source_root=ROOT, source_files=freeze['source_files'], binary_sha256=freeze['binary']['sha256'])
    try:
        deadline = time.monotonic() + 20
        while not (owner.output / 'process-start.json').exists():
            require(owner.tick() is None and time.monotonic() < deadline, 'S225_EDITOR_START')
            time.sleep(.05)
        pid = json.loads((owner.output / 'process-start.json').read_bytes())['pid']
        sampler = subprocess.Popen([sys.executable, '-B', str(HERE / 'run_s225.py'), '--observe', str(pid)],
            cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
        while owner.tick() is None:
            require(time.monotonic() < deadline + freeze['duration_seconds'] + 40, 'S225_EDITOR_DEADLINE')
            time.sleep(.1)
        capture = owner.finish(); sampler_code = sampler.wait(timeout=20)
        write(RAW / 'sampler-process-exit.json', {'pid': sampler.pid, 'actual_exit': sampler_code})
        require(sampler_code == 0 and (RAW / 'external-sampler/sampler-result.json').is_file(), 'S225_SAMPLER_FAILED')
        stdout = (RAW / 'editor-host/stdout.txt').read_text(encoding='utf-8')
        complete = [json.loads(line.split(' ', 1)[1]) for line in stdout.splitlines() if line.startswith('HH_S194_COMPLETE ')]
        require(len(complete) == 1 and complete[0]['pid'] == pid and complete[0]['elapsed_us'] >= 90_000_000, 'S225_NATIVE_COMPLETION')
        require(not (RAW / 'editor-host/stderr.txt').read_bytes(), 'S225_EDITOR_STDERR')
        write(RAW / 'result.json', {'schema_id': 'hh-studio.gt06-s225-result', 'schema_version': '1.0.0',
            'run_id': RUN_ID, 'authority': 0, 'formal_acceptance': False, 'engine_started': True,
            'native_completion': complete[0], 'target_actual_exit': capture['actual_process_exit'],
            'helper_exit': capture['wrapper_exit_code'], 'sampler_exit': sampler_code, 'job': capture['job'],
            'sampler_result_sha256': sha(RAW / 'external-sampler/sampler-result.json')})
    finally:
        if 'sampler' in locals() and sampler.poll() is None: sampler.terminate(); sampler.wait(timeout=10)
        if not owner.closed: owner.close()


def observe(pid):
    freeze = json.loads((RAW / 'prepare.json').read_bytes())
    executable = Path(freeze['binary']['path'])
    return sample_process(pid, executable, RAW / 'external-sampler', freeze['duration_seconds'], freeze['sample_interval_seconds'])


def seal():
    files = []
    for path in sorted(RAW.rglob('*')):
        if path.is_file():
            rel = path.relative_to(RAW).as_posix(); raw = path.read_bytes(); files.append({'path': rel, 'bytes': len(raw), 'sha256': sha_bytes(raw)})
    manifest = {'schema_id': 'hh-studio.gt06-s225-manifest', 'schema_version': '1.0.0', 'authority': 0,
        'formal_acceptance': False, 'run_id': RUN_ID, 'files': files}
    write(RAW / 'raw-manifest.json', manifest)
    archive = STUDIO / '.local/archives/gt06-s225-external-rss-s226.zip'; archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for row in files: z.write(RAW / row['path'], 'raw/' + row['path'])
        z.write(RAW / 'raw-manifest.json', 'raw-manifest.json')
    print(json.dumps({'manifest_sha256': sha(RAW / 'raw-manifest.json'), 'archive_sha256': sha(archive), 'files': len(files)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--prepare', action='store_true'); parser.add_argument('--run', action='store_true'); parser.add_argument('--observe', type=int); parser.add_argument('--seal', action='store_true'); args = parser.parse_args()
    if args.prepare: prepare()
    elif args.run: run()
    elif args.observe is not None: raise SystemExit(observe(args.observe))
    elif args.seal: seal()
    else: parser.error('choose one bounded action')
