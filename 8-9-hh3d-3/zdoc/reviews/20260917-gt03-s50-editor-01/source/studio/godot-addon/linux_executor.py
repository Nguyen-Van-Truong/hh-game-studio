"""Internal diagnostic executor. Child output is untrusted, never a publish ACK."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import threading
import time
from typing import Literal
import uuid
import ctypes

STUDIO = Path(__file__).resolve().parent.parent
DOCKER = 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
BINARY_NAME = 'Godot_v4.7.2-stable_linux.x86_64'
BINARY_SHA256 = '8d106cbe6144c2dc7e881d61d2429c1a8a76e6b22ef48bd5e48dcf934953f71e'
IMAGE_ID = 'sha256:581429e3df12d76e6af4be5ab7d0e7fc2013eb57dc23d2de691411c8efdbb970'
OWNED_RUNNER_SHA256 = 'ea522450acc46f90be5e2a7b9257e73ce8b619948105b2c9073aac1f881c7328'
LOCK_SHA256 = 'f9a5400b04be557b40514321bbfea31c9bee627845636db85ffacb363fe4f71d'
PROJECT_TEMPLATE = ('config_version=5\n[application]\nconfig/name="HH GT03 Linux validator"\n'
                    '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
                    '[threading]\nworker_pool/max_threads=4\n')
REQUIRED_FILES = ('project.godot', 'scenes/fixture.tscn', 'scripts/fixture_actor.gd')
FILE_LIMITS = {'project.godot': 4096, 'scenes/fixture.tscn': 1048576, 'scripts/fixture_actor.gd': 16384}
TMPFS = {path: 'rw,nosuid,nodev,noexec,size=' + size + ',nr_inodes=' + str(inodes) + ',uid=65532,gid=65532,mode=0700'
         for path, size, inodes in (('/tmp', '16m', 2048), ('/home/validator', '16m', 2048),
                                   ('/run', '4m', 512), ('/project/.godot', '64m', 8192))}
ENVIRONMENT = {'HOME': '/home/validator', 'TMPDIR': '/tmp', 'XDG_CACHE_HOME': '/home/validator/cache',
               'XDG_CONFIG_HOME': '/home/validator/config', 'XDG_DATA_HOME': '/home/validator/data',
               'XDG_RUNTIME_DIR': '/run'}
ULIMITS = {'fsize': 8388608, 'core': 0, 'cpu': 10, 'nofile': 256, 'msgqueue': 8192}
_HELPER = "import subprocess,sys; token=sys.stdin.readline(); sys.exit(125) if token != 'GO\\n' else None; p=subprocess.Popen(sys.argv[1:],stdin=subprocess.DEVNULL); sys.exit(p.wait())"
_INCOMPLETE_CLI_HOLDS: list = []
_INCOMPLETE_ADMISSION_HOLDS: list = []
PROFILE_BOOTSTRAP_SHA256 = '1e67888029b75945eb11d2730936e98a5028884d7746a4a2be9a7304cf5298cf'
_CLI_JOBS = None
SUPERVISOR_SHA256 = '5ef0eaaaa4220593add7716aad74da927ca3bb10605e964330de64fecc3ef15e'
EXECUTOR_CONTEXT = 'hh-gt03-linux-desktop-v1'
ADMISSION_MUTEX = 'Global\\HHStudio.GT03.Linux.desktop-linux.v1'
ADMISSION_WAIT_MS = 1000
SUPERVISOR_BOOTSTRAP = (
    "import os,pathlib,hashlib,sys; "
    "assert os.getpid()==1 and os.getuid()==65532; "
    "assert pathlib.Path('/proc/sys/kernel/yama/ptrace_scope').read_text().strip() in ('1','2','3'); "
    "assert hashlib.sha256(pathlib.Path('/usr/bin/timeout').read_bytes()).hexdigest()=='" + SUPERVISOR_SHA256 + "'; "
    "os.execv('/usr/bin/timeout',['/usr/bin/timeout',*sys.argv[1:]])"
)


class ExecutorError(ValueError):
    pass


def _need(condition: object, code: str) -> None:
    if not condition:
        raise ExecutorError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _no_links(path: Path) -> Path:
    absolute = path.absolute()
    for member in [absolute, *absolute.parents]:
        info = member.lstat()
        _need(not stat.S_ISLNK(info.st_mode) and not getattr(info, 'st_file_attributes', 0) & 0x400,
              'EXECUTOR_LINK_FORBIDDEN')
    return absolute


def _read_file(path: Path, maximum: int) -> bytes:
    _no_links(path)
    before = path.stat(follow_symlinks=False)
    _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= maximum,
          'EXECUTOR_FILE_SHAPE')
    with path.open('rb') as stream:
        raw = stream.read(maximum + 1)
    after = path.stat(follow_symlinks=False)
    _need(len(raw) <= maximum and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
          == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'EXECUTOR_SOURCE_CHANGED')
    return raw


def _names(path: Path, maximum: int = 8) -> set[str]:
    _no_links(path)
    _need(path.is_dir(), 'EXECUTOR_DIRECTORY_REQUIRED')
    names = set()
    for child in path.iterdir():
        names.add(child.name)
        _need(len(names) <= maximum, 'EXECUTOR_EXTRA_INPUT')
        _no_links(child)
    return names


def _project_bytes(project: Path) -> dict[str, bytes]:
    names = _names(project)
    _need(names in ({'project.godot', 'scenes', 'scripts'}, {'project.godot', 'scenes', 'scripts', '.godot'}),
          'EXECUTOR_EXTRA_INPUT')
    _need(_names(project / 'scenes') == {'fixture.tscn'} and _names(project / 'scripts') == {'fixture_actor.gd'},
          'EXECUTOR_EXTRA_INPUT')
    if '.godot' in names:
        _need(not _names(project / '.godot'), 'EXECUTOR_NONEMPTY_CACHE')
    values = {name: _read_file(project / name, FILE_LIMITS[name]) for name in REQUIRED_FILES}
    _need(values['project.godot'] == PROJECT_TEMPLATE.encode(), 'EXECUTOR_PROJECT_TEMPLATE')
    return values


def _manifest(values: dict[str, bytes]) -> dict[str, str]:
    return {name: _sha(value) for name, value in values.items()}


def _profile_factory():
    path = STUDIO / 'godot-addon/fixture_profile.py'
    raw = _read_file(path, 65536)
    key = '_hh_linux_fixture_' + _sha(str(path).encode() + b'\0' + raw)
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        try:
            exec(compile(raw, str(path), 'exec'), module.__dict__)
        except BaseException:
            del sys.modules[key]
            raise
    return sys.modules[key]


def _cli_jobs():
    global _CLI_JOBS
    if _CLI_JOBS is None:
        path = STUDIO / 'godot-addon/cli_job.py'
        raw = _read_file(path, 65536)
        key = '_hh_linux_cli_job_' + _sha(str(path).encode() + b'\0' + raw)
        if key not in sys.modules:
            spec = importlib.util.spec_from_file_location(key, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[key] = module
            try:
                exec(compile(raw, str(path), 'exec'), module.__dict__)
            except BaseException:
                del sys.modules[key]
                raise
        _CLI_JOBS = sys.modules[key]
    return _CLI_JOBS


def _profile_project_bytes(project: Path) -> dict[str, bytes]:
    """Exact complete fixture, qualified before the engine can parse any file."""
    factory = _profile_factory()
    codec = factory.bundle_codec
    names = _names(project)
    _need(names in ({'project.godot', 'scenes', 'scripts', 'addons'},
                   {'project.godot', 'scenes', 'scripts', 'addons', '.godot'}), 'EXECUTOR_EXTRA_INPUT')
    _need(_names(project / 'scenes') == {'fixture.tscn'}
          and _names(project / 'scripts') == {'fixture_actor.gd', 'fixture_actor.gd.uid'}
          and _names(project / 'addons') == {'hh_studio'}
          and _names(project / 'addons/hh_studio') == {
              'plugin.cfg','plugin.gd','plugin.gd.uid','scene_commands.gd','scene_commands.gd.uid',
              'jcs_godot.gd','jcs_godot.gd.uid'}, 'EXECUTOR_EXTRA_INPUT')
    if '.godot' in names:
        _need(not _names(project / '.godot'), 'EXECUTOR_NONEMPTY_CACHE')
    values = {name: _read_file(project / name, codec.FILE_PROFILE[name][1]) for name in codec.PATHS}
    # Only input eligibility is asserted here. This observation is not a scene
    # semantic revision or a publication receipt; the complete content is bound.
    candidate = codec.create_bundle(values,
        scene_revision='sha256:' + _sha(values[codec.SCENE_PATH]), engine_sha256=BINARY_SHA256)
    factory.qualify(candidate)
    return values


def _inputs(project: Path, mode: str) -> dict[str, bytes]:
    return _profile_project_bytes(project) if mode == 'profile-validate' else _project_bytes(project)


def _profile_harness() -> bytes:
    raw = _read_file(STUDIO / 'godot-addon/validation_bootstrap.gd', 65536)
    _need(_sha(raw) == PROFILE_BOOTSTRAP_SHA256, 'EXECUTOR_PROFILE_HARNESS_PIN')
    return raw


def _profile_driver() -> str:
    binary = '/tool/' + BINARY_NAME
    commands = [
        ('parse', [binary, *_command('parse')]),
        ('import', [binary, *_command('import')]),
        ('readback', [binary, '--headless', '--path', '/project', '--log-file', '/tmp/readback.log',
                      '--script', '/harness/validation_bootstrap.gd']),
    ]
    return ('import subprocess,sys\n' + 'commands=' + repr(commands) + '\n'
        'for name,argv in commands:\n'
        ' print("HH_PROFILE_PHASE_BEGIN "+name,flush=True)\n'
        ' code=subprocess.run(argv,stdin=subprocess.DEVNULL).returncode\n'
        ' print("HH_PROFILE_PHASE_END "+name+" "+str(code),flush=True)\n'
        ' if code!=0:sys.exit(45)\n')


def _supervised_command(mode: str, timeout_seconds: int = 20) -> list[str]:
    _need(type(timeout_seconds) is int and 1 <= timeout_seconds <= 20, 'EXECUTOR_TIMEOUT')
    command = (['/usr/local/bin/python3', '-I', '-B', '-c', _profile_driver()]
               if mode == 'profile-validate' else ['/tool/' + BINARY_NAME, *_command(mode)])
    return ['-I', '-B', '-c', SUPERVISOR_BOOTSTRAP, '--signal=TERM', '--kill-after=1s',
            str(max(1, timeout_seconds - 1)) + 's', *command]


class _Admission:
    """One machine-wide named mutex; durable local record survives its owner."""
    def __init__(self):
        _need(os.name == 'nt', 'EXECUTOR_WINDOWS_DOCKER_HOST_REQUIRED')
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
        self.kernel.ReleaseMutex.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL
        self.handle = None
        self.acquired = False
        self.abandoned = False
        start = time.monotonic()
        _INCOMPLETE_ADMISSION_HOLDS.append(self)
        try:
            self.handle = self.kernel.CreateMutexW(None, False, ADMISSION_MUTEX)
            _need(self.handle, 'EXECUTOR_ADMISSION_HANDLE')
            self.acquired = None  # Wait may acquire before an interrupted reply.
            status = self.kernel.WaitForSingleObject(self.handle, ADMISSION_WAIT_MS)
            self.wait_ms = round((time.monotonic() - start) * 1000)
            self.acquired = status in (0, 0x80)
            if not self.acquired:
                if not self.kernel.CloseHandle(self.handle):
                    raise ExecutorError('EXECUTOR_ADMISSION_HANDLE_CLOSE_UNCERTAIN')
                self.handle = None
                raise ExecutorError('EXECUTOR_ADMISSION_BUSY' if status == 0x102 else 'EXECUTOR_ADMISSION_WAIT')
            self.abandoned = status == 0x80
        except BaseException as error:
            if self.handle is None and isinstance(error, Exception):
                _INCOMPLETE_ADMISSION_HOLDS.remove(self)
            raise
        _INCOMPLETE_ADMISSION_HOLDS.remove(self)

    def close(self):
        if self.handle:
            try:
                if self.acquired is None:
                    raise ExecutorError('EXECUTOR_ADMISSION_OWNERSHIP_UNKNOWN')
                if self.acquired:
                    self.acquired = None  # A cancelled native result may hide release.
                    released = self.kernel.ReleaseMutex(self.handle)
                    if not released:
                        self.acquired = True
                        raise ExecutorError('EXECUTOR_ADMISSION_RELEASE_UNCERTAIN')
                    self.acquired = False
                if not self.kernel.CloseHandle(self.handle):
                    raise ExecutorError('EXECUTOR_ADMISSION_HANDLE_CLOSE_UNCERTAIN')
                self.handle = None
            except BaseException:
                if self not in _INCOMPLETE_ADMISSION_HOLDS:
                    _INCOMPLETE_ADMISSION_HOLDS.append(self)
                raise


def _owner_path() -> Path:
    # Fixed host configuration, shared by every source checkout/frozen copy.
    root = Path(os.environ['LOCALAPPDATA']) / 'HHGodotAgent' / 'linux-executor' / 'desktop-linux'
    root.mkdir(parents=True, exist_ok=True)
    _no_links(root)
    _need(_names(root, 2) <= {'owner.json', 'owner.pending'}, 'EXECUTOR_OWNER_STORE_SHAPE')
    return root / 'owner.json'


def _persist_owner(path: Path, record: dict) -> None:
    raw = (json.dumps(record, sort_keys=True) + '\n').encode()
    _need(len(raw) <= 8192, 'EXECUTOR_OWNER_RECORD_SIZE')
    _no_links(path.parent)
    pending = path.with_name('owner.pending')
    if pending.exists():
        _read_file(pending, 8192)
    with pending.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_ulong]
    kernel.MoveFileExW.restype = ctypes.c_int
    _need(kernel.MoveFileExW(str(pending), str(path), 0x1 | 0x8), 'EXECUTOR_OWNER_DURABILITY')


def _read_owner(path: Path) -> dict | None:
    if not path.exists():
        # A pending file without a canonical owner is ambiguous after a crash.
        _need(not path.with_name('owner.pending').exists(), 'EXECUTOR_OWNER_PENDING_AMBIGUOUS')
        return None
    value = json.loads(_read_file(path, 8192))
    _need(isinstance(value, dict) and value.get('schema') == 'hh-linux-owner-1'
          and value.get('context') == EXECUTOR_CONTEXT and value.get('image') == IMAGE_ID
          and re.fullmatch(r'hh-gt03-[0-9a-f]{32}', value.get('name', ''))
          and (value.get('container_id') is None or re.fullmatch(r'[0-9a-f]{64}', value['container_id']))
          and value.get('phase') in ('prepared', 'create_pending', 'created', 'start_pending', 'running'),
          'EXECUTOR_OWNER_RECORD')
    return value


def _clear_owner(path: Path):
    for target in (path, path.with_name('owner.pending')):
        if target.exists():
            _read_file(target, 8192)
            target.unlink()


def _missing(row: dict, output: Path, selector: str) -> bool:
    return (_cli_done(row, 1)
            and ('no such object: ' + selector) in _read_file(output / row['stderr'], 262144).decode(errors='replace').lower())


def _reconcile_owner(path: Path, call, output: Path) -> dict:
    record = _read_owner(path)
    recovery = {'previous_owner': record, 'reconciled': False, 'removed': False}
    if record:
        selector = record['container_id'] or record['name']
        row, raw = call(['inspect', selector], 'admission-owner-inspect', timeout=5)
        if _missing(row, output, selector):
            _need(record['container_id'] is not None or record['phase'] == 'prepared',
                  'EXECUTOR_OWNER_CREATE_AMBIGUOUS')
        else:
            _need(_cli_clean(row), 'EXECUTOR_OWNER_INSPECT_UNAVAILABLE')
            values = json.loads(raw)
            value = values[0] if len(values) == 1 else None
            _need(value and _owned_identity(value, record['name'], record['container_id'])
                  and value.get('Config', {}).get('Labels', {}).get('hh.gt03.executor') == EXECUTOR_CONTEXT,
                  'EXECUTOR_OWNER_RECONCILE_IDENTITY')
            cid = value['Id']
            if value['State']['Running']:
                call(['kill', cid], 'admission-owner-kill', timeout=5, cap=4096)
                call(['wait', cid], 'admission-owner-wait', timeout=5, cap=4096)
                row, raw = call(['inspect', cid], 'admission-owner-exited', timeout=5)
                _need(_cli_clean(row), 'EXECUTOR_OWNER_EXIT_UNAVAILABLE')
                value = json.loads(raw)[0]
            _need(_owned_identity(value, record['name'], cid) and not value['State']['Running']
                  and value['State']['Pid'] == 0, 'EXECUTOR_OWNER_STILL_RUNNING')
            recovery['state'] = value['State']
            row, _ = call(['rm', cid], 'admission-owner-remove', timeout=5, cap=4096)
            _need(_cli_clean(row), 'EXECUTOR_OWNER_REMOVE_UNCERTAIN')
            row, _ = call(['inspect', cid], 'admission-owner-missing', timeout=5, cap=4096)
            _need(_missing(row, output, cid), 'EXECUTOR_OWNER_REMOVE_UNPROVEN')
            recovery['removed'] = True
        _clear_owner(path)
    # Never clean an unknown container merely because it carries our label.
    row, raw = call(['ps', '--all', '--no-trunc', '--filter', 'label=hh.gt03.executor=' + EXECUTOR_CONTEXT,
                     '--format', '{{.ID}}'], 'admission-inventory', timeout=5, cap=4096)
    _need(_cli_clean(row) and not raw.strip(), 'EXECUTOR_UNRECORDED_CONTAINER')
    recovery['reconciled'] = True
    return recovery


def _command(mode: str) -> list[str]:
    _need(type(mode) is str and mode in ('parse', 'import', 'profile-validate'), 'EXECUTOR_MODE')
    if mode == 'profile-validate':
        return ['-I', '-B', '-c', _profile_driver()]
    if mode == 'parse':
        return ['--headless', '--path', '/project', '--log-file', '/tmp/engine.log',
                '--check-only', '--script', 'res://scripts/fixture_actor.gd']
    return ['--headless', '--editor', '--import', '--path', '/project', '--log-file', '/tmp/engine.log',
            'res://scenes/fixture.tscn']


def _lock() -> dict:
    path = Path(__file__).with_name('validator-toolchain.lock.json')
    raw = _read_file(path, 16384)
    _need(_sha(raw) == LOCK_SHA256, 'EXECUTOR_LOCK_BYTES')
    value = json.loads(raw)
    _need(value.get('schema') == 'hh-gt03-linux-validator-1' and value.get('status') == 'diagnostic_only'
          and value.get('binary_name') == BINARY_NAME and value.get('binary_sha256') == BINARY_SHA256
          and value.get('image_id') == IMAGE_ID and value.get('image_repo_digest') == 'python@' + IMAGE_ID
          and value.get('owned_runner_sha256') == OWNED_RUNNER_SHA256
          and value.get('supervisor_sha256') == SUPERVISOR_SHA256
          and value.get('supervisor_bootstrap_sha256') == _sha(SUPERVISOR_BOOTSTRAP.encode())
          and value.get('profile_bootstrap_sha256') == PROFILE_BOOTSTRAP_SHA256
          and value.get('profile_mode') == 'profile-validate'
          and value.get('docker_context') == 'desktop-linux'
          and value.get('docker_endpoint') == 'npipe:////./pipe/dockerDesktopLinuxEngine', 'EXECUTOR_PIN_MISMATCH')
    return value


def _binary() -> Path:
    # Trusted host configuration for frozen-source runs. It is not request authority.
    value = os.environ.get('HH_STUDIO_LINUX_GODOT')
    path = Path(value) if value else STUDIO / '.local/tooling/godot-4.7.2-stable-linux' / BINARY_NAME
    _need(path.is_absolute(), 'EXECUTOR_BINARY_ABSOLUTE_REQUIRED')
    _need(path.name == BINARY_NAME and _names(path.parent) == {BINARY_NAME}, 'EXECUTOR_TOOL_ROOT')
    _need(_sha(_read_file(path, 251658240)) == BINARY_SHA256, 'EXECUTOR_BINARY_PIN')
    return path.absolute()


def _owned_runner():
    path = STUDIO / 'build/bootstrap/run_fixture.py'
    _need(_sha(_read_file(path, 262144)) == OWNED_RUNNER_SHA256, 'EXECUTOR_RUNNER_PIN')
    spec = importlib.util.spec_from_file_location('hh_gt03_owned_cli_' + uuid.uuid4().hex, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cli(owned, args: list[str], output: Path, label: str, *, timeout: int = 20,
         cap: int = 262144) -> tuple[dict, bytes]:
    _need(re.fullmatch(r'[a-z0-9-]+', label) is not None, 'EXECUTOR_LABEL')
    argv = [DOCKER, '--context', 'desktop-linux', *args]
    row = {'argv': ['docker.exe', '--context', 'desktop-linux', *args], 'exit_code': None,
           'timeout_seconds': timeout, 'timed_out': False, 'stream_cap_exceeded': False,
           'stream_cap_bytes_each': cap, 'stdout': label + '-stdout.txt', 'stderr': label + '-stderr.txt',
           'job_active_count': None, 'readers_stopped': False}
    buffers = [bytearray(), bytearray()]
    counts = [0, 0]
    readers = []
    reader_eof = [False, False]
    reader_errors = [None, None]
    exceeded = threading.Event()
    process = None
    job = None
    cancellation = None
    start = time.monotonic()
    def failed(error, prefix=''):
        nonlocal cancellation
        row['host_error'] = prefix + type(error).__name__
        if not isinstance(error, Exception):
            if cancellation is None:
                cancellation = error
            row['host_cancelled'] = type(cancellation).__name__
    def drain(stream, index):
        try:
            while True:
                chunk = stream.read1(4096)
                if not chunk:
                    reader_eof[index] = True
                    return
                counts[index] += len(chunk)
                buffers[index].extend(chunk[:max(0, cap - len(buffers[index]))])
                if counts[index] > cap:
                    exceeded.set()
        except BaseException as error:
            reader_errors[index] = type(error).__name__
            if not isinstance(error, Exception):
                failed(error, 'CLI_READER_')
    def join_readers():
        for thread in readers:
            # Thread.start may fail before any native thread exists. Cleanup
            # must still close unused pipes and record the original failure.
            if thread.ident is None:
                continue
            try:
                thread.join(timeout=1)
            except BaseException as error:
                failed(error, 'CLI_READER_JOIN_')
    try:
        _cli_jobs().require_no_holds()
        process = subprocess.Popen([sys.executable, '-B', '-c', _HELPER, *argv], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        job = _cli_jobs().create(process)
        for index, stream in enumerate((process.stdout, process.stderr)):
            thread = threading.Thread(target=drain, args=(stream, index), daemon=True)
            readers.append(thread)
            thread.start()
        process.stdin.write(b'GO\n')
        process.stdin.close()
        while process.poll() is None:
            row['timed_out'] = time.monotonic() - start >= timeout
            if row['timed_out'] or exceeded.is_set() or any(reader_errors):
                job.terminate()
                break
            time.sleep(0.02)
        process.wait(timeout=3)
        join_readers()
        deadline = time.monotonic() + 1
        active = job.active_count()
        while active != 0 and time.monotonic() < deadline:
            time.sleep(0.02)
            active = job.active_count()
        row.update(exit_code=process.returncode, job_active_count=active,
                   readers_stopped=all(not thread.is_alive() for thread in readers))
    except BaseException as error:
        failed(error)
        if job is None:
            job = getattr(error, 'cleanup_owner', None)
    finally:
        if process is not None and job is None:
            try:
                # Also covers interruption after create returned but before the
                # caller's assignment. Lookup uses exact process object identity.
                lookup = getattr(_cli_jobs(), 'owner_for_process', None)
                job = lookup(process) if lookup is not None else None
            except BaseException as error:
                failed(error, 'CLI_JOB_LOOKUP_')
        if job:
            try:
                if job.active_count() != 0:
                    job.terminate()
            except BaseException as error:
                failed(error)
        helper_exited = process is None
        if process:
            try:
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=3)
                helper_exited = process.poll() is not None
            except BaseException as error:
                failed(error, 'CLI_HELPER_CLEANUP_')
        if job:
            try:
                row['job_active_count'] = job.active_count()
            except BaseException as error:
                failed(error, 'CLI_JOB_QUERY_')
            try:
                job.close()
            except BaseException as error:
                failed(error)
            try:
                row['job_owner'] = job.snapshot()
                if job.tainted or not job.closed or not job.zero_observed:
                    row['host_error'] = 'CLI_JOB_OWNERSHIP_UNCERTAIN'
            except BaseException as error:
                failed(error, 'CLI_JOB_SNAPSHOT_')
        if process and not helper_exited and job and job.closed and job.zero_observed:
            try:
                process.wait(timeout=1)
                helper_exited = process.poll() is not None
            except BaseException as error:
                failed(error, 'CLI_HELPER_REAP_')
        join_readers()
        row['readers_stopped'] = len(readers) == 2 and all(not thread.is_alive() for thread in readers)
        pipes_closed = False
        if process and helper_exited and all(not thread.is_alive() for thread in readers):
            # A constructor failure before reader creation is not a stuck reader.
            # Keep that row dirty, but close every unused pipe after helper exit.
            pipes_closed = True
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    if stream is not None and not stream.closed:
                        stream.close()
                except BaseException as error:
                    pipes_closed = False
                    failed(error, 'CLI_PIPE_CLEANUP_')
        if process and not pipes_closed:
            # Keep unfinished reader/pipe ownership explicit rather than letting
            # garbage collection silently discard handles after a failed drain.
            _INCOMPLETE_CLI_HOLDS.append((process, readers, buffers))
        row.update(stream_cap_exceeded=exceeded.is_set(), stream_byte_counts=counts,
                   stream_reader_eof=reader_eof, stream_reader_errors=reader_errors,
                   elapsed_seconds=round(time.monotonic() - start, 3))
        for index, name in enumerate(('stdout', 'stderr')):
            try:
                (output / row[name]).write_bytes(bytes(buffers[index]))
            except BaseException as error:
                row['evidence_write_error'] = type(error).__name__
                if not isinstance(error, Exception):
                    failed(error, 'CLI_EVIDENCE_')
        try:
            _write(output / (label + '-host.json'), row)
        except BaseException as error:
            row['evidence_write_error'] = type(error).__name__
            if not isinstance(error, Exception):
                failed(error, 'CLI_EVIDENCE_')
    if cancellation is not None:
        cancellation.cli_result = row
        raise cancellation
    return row, bytes(buffers[0])


def _cli_done(row: dict, exit_code: int) -> bool:
    job = row.get('job_owner') or {}
    eof = row.get('stream_reader_eof')
    return (type(row.get('exit_code')) is int and row['exit_code'] == exit_code
            and row.get('timed_out') is False and row.get('stream_cap_exceeded') is False
            and type(row.get('job_active_count')) is int and row['job_active_count'] == 0
            and row.get('readers_stopped') is True and row.get('host_error') is None
            and row.get('host_cancelled') is None
            and type(eof) is list and len(eof) == 2 and all(item is True for item in eof)
            and row.get('stream_reader_errors') == [None, None] and row.get('evidence_write_error') is None
            and all(job.get(key) is True for key in ('configured','assigned','closed','zero_observed'))
            and all(job.get(key) is False for key in ('tainted','handle_retained'))
            and not job.get('create_uncertain') and not job.get('close_uncertain')
            and type(job.get('active_count')) is int and job['active_count'] == 0
            and job.get('failed_operations') == [] and job.get('native_error') is None)


def _cli_clean(row: dict) -> bool:
    return _cli_done(row, 0)


def _owned_identity(value: dict, name: str, container_id: str | None = None) -> bool:
    return (isinstance(value, dict) and re.fullmatch(r'[0-9a-f]{64}', value.get('Id', '')) is not None
            and (container_id is None or value['Id'] == container_id) and value.get('Name') == '/' + name
            and value.get('Image') == IMAGE_ID
            and value.get('Config', {}).get('Labels', {}).get('hh.gt03.owner') == name)


def _create_args(name: str, mode: str, tool: Path, snapshot: Path, timeout_seconds: int = 20) -> list[str]:
    _need(re.fullmatch(r'hh-gt03-[0-9a-f]{32}', name) is not None, 'EXECUTOR_OWNER_NAME')
    args = ['create', '--pull=never', '--name', name, '--label', 'hh.gt03.owner=' + name,
            '--label', 'hh.gt03.executor=' + EXECUTOR_CONTEXT,
            '--platform', 'linux/amd64', '--read-only', '--network', 'none', '--ipc', 'private',
            '--cgroupns', 'private', '--user', '65532:65532', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges=true', '--security-opt', 'seccomp=builtin',
            '--memory', '1g', '--memory-swap', '1g', '--cpus', '1', '--pids-limit', '64',
            '--log-driver', 'none', '--restart', 'no', '--no-healthcheck', '--stop-timeout', '2',
            '--shm-size', '16m', '--workdir', '/project']
    for name_, limit in ULIMITS.items():
        args += ['--ulimit', name_ + '=' + str(limit) + ':' + str(limit)]
    for name_, value in ENVIRONMENT.items():
        args += ['--env', name_ + '=' + value]
    for destination, options in TMPFS.items():
        args += ['--tmpfs', destination + ':' + options]
    for source, destination in ((tool, '/tool'), (snapshot, '/project')):
        args += ['--mount', 'type=bind,src=' + str(source) + ',dst=' + destination + ',readonly,bind-propagation=rprivate']
    if mode == 'profile-validate':
        args += ['--mount', 'type=bind,src=' + str(snapshot.parent / 'harness')
                 + ',dst=/harness,readonly,bind-propagation=rprivate']
    return args + ['--entrypoint', '/usr/local/bin/python3', IMAGE_ID, *_supervised_command(mode, timeout_seconds)]


def _validate_inspect(value: dict, *, name: str, container_id: str, mode: str,
                      tool: Path, snapshot: Path, image_environment: list[str], timeout_seconds: int = 20) -> None:
    _need(_owned_identity(value, name, container_id), 'EXECUTOR_OWNER_IDENTITY')
    host, config = value['HostConfig'], value['Config']
    expected_environment = dict(entry.split('=', 1) for entry in image_environment)
    expected_environment.update(ENVIRONMENT)
    received_environment = config.get('Env', [])
    _need(len(received_environment) == len(expected_environment)
          and dict(entry.split('=', 1) for entry in received_environment) == expected_environment,
          'EXECUTOR_ENVIRONMENT')
    _need(config.get('User') == '65532:65532' and config.get('WorkingDir') == '/project'
          and config.get('Entrypoint') == ['/usr/local/bin/python3']
          and config.get('Cmd') == _supervised_command(mode, timeout_seconds)
          and config.get('Labels', {}).get('hh.gt03.executor') == EXECUTOR_CONTEXT,
          'EXECUTOR_COMMAND')
    _need(host.get('ReadonlyRootfs') is True and host.get('NetworkMode') == 'none'
          and host.get('IpcMode') == 'private' and host.get('CgroupnsMode') == 'private'
          and host.get('PidMode', '') == '' and host.get('UsernsMode', '') == ''
          and host.get('CapDrop') == ['ALL'] and not host.get('CapAdd')
          and host.get('Privileged') is False and not host.get('Init')
          and not host.get('Devices') and not host.get('DeviceRequests')
          and set(host.get('SecurityOpt', [])) == {'no-new-privileges=true', 'seccomp=builtin'}, 'EXECUTOR_CONFINEMENT')
    _need(host.get('Memory') == 1073741824 and host.get('MemorySwap') == 1073741824
          and host.get('NanoCpus') == 1000000000 and host.get('PidsLimit') == 64
          and host.get('ShmSize') == 16777216 and host.get('LogConfig') == {'Type': 'none', 'Config': {}}
          and host.get('RestartPolicy', {}).get('Name') == 'no' and host.get('AutoRemove') is False
          and config.get('Healthcheck', {}).get('Test') == ['NONE'], 'EXECUTOR_RESOURCE_CONFIG')
    _need(host.get('Tmpfs') == TMPFS, 'EXECUTOR_TMPFS_CONFIG')
    limits = host.get('Ulimits', [])
    _need(len(limits) == len(ULIMITS) and {x['Name']: (x['Soft'], x['Hard']) for x in limits}
          == {key: (number, number) for key, number in ULIMITS.items()}, 'EXECUTOR_ULIMITS')
    expected_mounts = {'/tool': str(tool), '/project': str(snapshot)}
    if mode == 'profile-validate':
        expected_mounts['/harness'] = str(snapshot.parent / 'harness')
    mounts = value.get('Mounts', [])
    _need(len(mounts) == len(expected_mounts) and {mount.get('Destination') for mount in mounts} == set(expected_mounts),
          'EXECUTOR_MOUNTS')
    for mount in mounts:
        _need(mount.get('Type') == 'bind' and mount.get('Source') == expected_mounts[mount['Destination']]
              and mount.get('RW') is False and mount.get('Propagation') == 'rprivate', 'EXECUTOR_MOUNTS')
    _need(not host.get('PortBindings') and not host.get('VolumesFrom') and not host.get('Links'), 'EXECUTOR_EXTRA_ACCESS')
    _need({'/proc/bus', '/proc/fs', '/proc/irq', '/proc/sys', '/proc/sysrq-trigger'}
          <= set(host.get('ReadonlyPaths', []))
          and {'/proc/acpi', '/proc/kcore', '/proc/keys', '/proc/scsi', '/sys/firmware'}
          <= set(host.get('MaskedPaths', [])), 'EXECUTOR_SYSTEM_PATHS')


def run(project: Path, *, mode: Literal['parse', 'import', 'profile-validate'], output: Path, timeout_seconds: int = 20) -> dict:
    """Run fixed Godot diagnostics; raises only during argument/input/output preflight.

    Remote requests must never choose paths, environment or engine modes directly.
    diagnostic_process_clean does not authenticate child claims or accept a script.
    """
    _command(mode)
    _need(not _INCOMPLETE_CLI_HOLDS, 'EXECUTOR_UNFINISHED_CLI_HELD')
    _cli_jobs().require_no_holds()
    _need(not _INCOMPLETE_ADMISSION_HOLDS, 'EXECUTOR_UNFINISHED_ADMISSION_HELD')
    _need(type(timeout_seconds) is int and 1 <= timeout_seconds <= 20, 'EXECUTOR_TIMEOUT')
    _need(isinstance(project, Path) and isinstance(output, Path), 'EXECUTOR_PATH_TYPE')
    project, output = project.absolute(), output.absolute()
    initial = _inputs(project, mode)
    profile_harness = _profile_harness() if mode == 'profile-validate' else None
    _no_links(output.parent)
    _need(not output.exists() and output != project and project not in output.parents and output not in project.parents,
          'EXECUTOR_OUTPUT_SCOPE')
    output.mkdir()
    snapshot = output / 'snapshot'
    snapshot.mkdir()
    for relative, raw in initial.items():
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (snapshot / '.godot').mkdir()
    if profile_harness is not None:
        (output / 'harness').mkdir()
        (output / 'harness/validation_bootstrap.gd').write_bytes(profile_harness)
    before = _manifest(initial)
    _write(output / 'input-manifest.json', before)
    name = 'hh-gt03-' + uuid.uuid4().hex
    result = {'schema': 'hh-gt03-linux-diagnostic-1', 'run_id': name, 'mode': mode,
              'public_ack': False, 'sandbox_acceptance': False, 'diagnostic_process_clean': False,
              'container_id': None, 'state': None, 'owned_removed': False, 'input_unchanged': False,
              'snapshot_unchanged': False, 'commandhost': None, 'input_hashes_before': before,
              'stdout': 'engine-stdout.txt', 'stderr': 'engine-stderr.txt', 'errors': [],
              'profile_eligible': profile_harness is not None,
              'profile_harness_sha256': _sha(profile_harness) if profile_harness is not None else None,
              'profile_harness_unchanged': profile_harness is None,
              'admission': {'acquired': False}, 'owner_record_retained': False,
              'supervisor': {'path': '/usr/bin/timeout', 'sha256': SUPERVISOR_SHA256,
                             'term_after_seconds': max(1, timeout_seconds - 1), 'kill_after_seconds': 1,
                             'total_deadline_seconds': max(2, timeout_seconds), 'pid': 1,
                             'requires_yama_scope': [1, 2, 3], 'host_death_acceptance': False}}
    owned = None
    binary = None
    container_id = None
    image_environment = None
    admission = None
    owner_path = None
    owner_record = None
    create_attempted = False
    cancellation = None
    def failed(error, prefix='EXECUTOR_HOST_'):
        nonlocal cancellation
        result['errors'].append(str(error) if isinstance(error, ExecutorError) else prefix + type(error).__name__)
        if not isinstance(error, Exception):
            if cancellation is None:
                cancellation = error
            result['host_cancelled'] = type(cancellation).__name__
    def call(args, label, timeout=20, cap=262144):
        return _cli(owned, args, output, label, timeout=timeout, cap=cap)
    def inspect(selector, label):
        row, raw = call(['inspect', selector], label, timeout=5)
        if not _cli_clean(row):
            return None
        values = json.loads(raw)
        return values[0] if len(values) == 1 else None
    try:
        result['toolchain'] = _lock()
        _need(os.name == 'nt', 'EXECUTOR_WINDOWS_DOCKER_HOST_REQUIRED')
        admission = _Admission()
        result['admission'] = {'acquired': True, 'wait_ms': admission.wait_ms,
                               'abandoned_mutex': admission.abandoned, 'maximum_active': 1}
        binary = _binary()
        owned = _owned_runner()
        row, raw = call(['context', 'inspect', 'desktop-linux', '--format', '{{json .Endpoints.docker.Host}}'], 'context')
        _need(_cli_clean(row) and json.loads(raw) == result['toolchain']['docker_endpoint'], 'EXECUTOR_DAEMON_ENDPOINT')
        owner_path = _owner_path()
        result['admission']['recovery'] = _reconcile_owner(owner_path, call, output)
        row, raw = call(['image', 'inspect', IMAGE_ID], 'image')
        _need(_cli_clean(row), 'EXECUTOR_IMAGE_UNAVAILABLE')
        image = json.loads(raw)[0]
        _need(image['Id'] == IMAGE_ID and image.get('Os') == 'linux' and image.get('Architecture') == 'amd64'
              and not image.get('Config', {}).get('Volumes'), 'EXECUTOR_IMAGE_PIN')
        image_environment = image['Config'].get('Env', [])
        _need({entry.split('=', 1)[0] for entry in image_environment}
              == {'PATH', 'LANG', 'GPG_KEY', 'PYTHON_VERSION', 'PYTHON_SHA256'}, 'EXECUTOR_BASE_ENVIRONMENT')
        args = _create_args(name, mode, binary.parent, snapshot, timeout_seconds)
        _write(output / 'create-argv.json', args)
        owner_record = {'schema': 'hh-linux-owner-1', 'context': EXECUTOR_CONTEXT, 'image': IMAGE_ID,
                        'name': name, 'container_id': None, 'phase': 'prepared', 'host_pid': os.getpid()}
        _persist_owner(owner_path, owner_record)
        owner_record['phase'] = 'create_pending'
        _persist_owner(owner_path, owner_record)
        create_attempted = True
        row, raw = call(args, 'create', cap=4096)
        candidate = raw.decode('ascii', errors='replace').strip()
        if _cli_clean(row) and re.fullmatch(r'[0-9a-f]{64}', candidate):
            container_id = candidate
        else:
            recovered = inspect(name, 'create-reconcile')
            if recovered and _owned_identity(recovered, name):
                container_id = recovered['Id']
            raise ExecutorError('EXECUTOR_CREATE_UNCERTAIN')
        result['container_id'] = container_id
        owner_record.update(container_id=container_id, phase='created')
        _persist_owner(owner_path, owner_record)
        created = inspect(container_id, 'created-inspect')
        _need(created is not None, 'EXECUTOR_CREATED_INSPECT_UNAVAILABLE')
        _validate_inspect(created, name=name, container_id=container_id, mode=mode,
                          tool=binary.parent, snapshot=snapshot, image_environment=image_environment,
                          timeout_seconds=timeout_seconds)
        _need(_manifest(_inputs(project, mode)) == before and _manifest(_inputs(snapshot, mode)) == before,
              'EXECUTOR_PRESTART_INPUT_CHANGED')
        if profile_harness is not None:
            _need(_names(output / 'harness') == {'validation_bootstrap.gd'} and
                  _read_file(output / 'harness/validation_bootstrap.gd', 65536) == profile_harness,
                  'EXECUTOR_PROFILE_HARNESS_CHANGED')
        owner_record['phase'] = 'start_pending'
        _persist_owner(owner_path, owner_record)
        row, _ = call(['start', '--attach', container_id], 'engine', timeout=timeout_seconds + 2)
        result['commandhost'] = row
        if not _cli_clean(row):
            result['errors'].append('EXECUTOR_ENGINE_OR_HOST_NOT_CLEAN')
        # A stopped attach client does not stop a daemon-owned container.
        state = inspect(container_id, 'after-command-inspect')
        _need(state is not None and _owned_identity(state, name, container_id), 'EXECUTOR_AFTER_IDENTITY')
        if state['State']['Running']:
            call(['kill', container_id], 'watchdog-kill', timeout=5, cap=4096)
        wait_row, wait_raw = call(['wait', container_id], 'wait', timeout=5, cap=4096)
        result['docker_wait_exit'] = int(wait_raw.strip()) if _cli_clean(wait_row) else None
        final = inspect(container_id, 'exited-inspect')
        _need(final is not None and _owned_identity(final, name, container_id), 'EXECUTOR_FINAL_IDENTITY')
        result['state'] = final['State']
    except BaseException as error:
        failed(error)
    finally:
        try:
            if owned and create_attempted and container_id is None:
                recovered = inspect(name, 'final-create-reconcile')
                if recovered and _owned_identity(recovered, name):
                    container_id = recovered['Id']
            if owned and container_id:
                result['container_id'] = container_id
                current = inspect(container_id, 'cleanup-inspect')
                _need(current is not None and _owned_identity(current, name, container_id), 'EXECUTOR_CLEANUP_IDENTITY')
                if current['State']['Running']:
                    call(['kill', container_id], 'cleanup-kill', timeout=5, cap=4096)
                    call(['wait', container_id], 'cleanup-wait', timeout=5, cap=4096)
                    current = inspect(container_id, 'cleanup-exited-inspect')
                _need(current is not None and _owned_identity(current, name, container_id), 'EXECUTOR_CLEANUP_FINAL_IDENTITY')
                result['state'] = current['State']
                _need(current['State']['Running'] is False and current['State']['Pid'] == 0,
                      'EXECUTOR_CONTAINER_STILL_RUNNING')
                row, _ = call(['rm', container_id], 'owned-remove', timeout=5, cap=4096)
                gone, message = call(['inspect', container_id], 'removed-inspect', timeout=5, cap=4096)
                stderr = (output / gone['stderr']).read_text(errors='replace')
                result['owned_removed'] = (_cli_clean(row) and _cli_done(gone, 1)
                    and ('no such object: ' + container_id) in stderr.lower())
            if owner_record and (result['owned_removed'] or not create_attempted):
                _clear_owner(owner_path)
        except BaseException as error:
            failed(error, 'EXECUTOR_CLEANUP_')
        if admission:
            try:
                admission.close()
                result['admission']['released'] = True
            except BaseException as error:
                result['admission']['released'] = False
                failed(error, 'EXECUTOR_ADMISSION_CLOSE_')
                # Once ReleaseMutex succeeded another process may own the store.
                # Never overwrite its record merely because CloseHandle failed.
                if owner_path and owner_record and admission.acquired is True:
                    owner_record['phase'] = 'admission_uncertain'
                    try:
                        _persist_owner(owner_path, owner_record)
                    except BaseException as error:
                        failed(error, 'EXECUTOR_ADMISSION_UNCERTAINTY_PERSIST_')
        result['owner_record_retained'] = bool(owner_path and owner_path.exists())
        for path, field in ((project, 'input_unchanged'), (snapshot, 'snapshot_unchanged')):
            try:
                after = _manifest(_inputs(path, mode))
                result[field] = after == before
                result[field.replace('_unchanged', '_hashes_after')] = after
            except BaseException as error:
                result[field] = False
                if not isinstance(error, Exception):
                    failed(error, 'EXECUTOR_INPUT_FINALIZE_')
        try:
            result['binary_unchanged'] = binary is not None and _sha(_read_file(binary, 251658240)) == BINARY_SHA256
        except BaseException as error:
            result['binary_unchanged'] = False
            if not isinstance(error, Exception):
                failed(error, 'EXECUTOR_BINARY_FINALIZE_')
        if profile_harness is not None:
            try:
                result['profile_harness_unchanged'] = (
                    _names(output / 'harness') == {'validation_bootstrap.gd'} and
                    _read_file(output / 'harness/validation_bootstrap.gd', 65536) == profile_harness == _profile_harness())
            except BaseException as error:
                result['profile_harness_unchanged'] = False
                if not isinstance(error, Exception):
                    failed(error, 'EXECUTOR_HARNESS_FINALIZE_')
        try:
            for stream in ('stdout', 'stderr'):
                log = output / result[stream]
                if not log.exists():
                    log.write_bytes(b'')
            combined = b'\n'.join(_read_file(output / result[field], 262144) for field in ('stdout', 'stderr'))
            result['log_clean'] = re.search(rb'(?m)^(?:SCRIPT ERROR|ERROR|WARNING):|ObjectDB instances leaked', combined) is None
        except BaseException as error:
            result['log_clean'] = False
            result['errors'].append('EXECUTOR_EVIDENCE_LOG_UNAVAILABLE')
            if not isinstance(error, Exception):
                failed(error, 'EXECUTOR_LOG_FINALIZE_')
        state = result['state'] or {}
        result['diagnostic_process_clean'] = bool(result['commandhost'] and _cli_clean(result['commandhost'])
            and state.get('ExitCode') == 0 and state.get('Running') is False and state.get('Pid') == 0
            and state.get('OOMKilled') is False and result.get('docker_wait_exit') == 0
            and result['owned_removed'] and result['input_unchanged'] and result['snapshot_unchanged']
            and result['binary_unchanged'] and result['profile_harness_unchanged']
            and result['log_clean'] and not result['errors'])
        result['command_host'] = result['commandhost']
        result['container_state'] = result['state']
        try:
            _write(output / 'result.json', result)
        except BaseException as error:
            result['errors'].append('EXECUTOR_RESULT_WRITE_FAILED')
            result['diagnostic_process_clean'] = False
            if not isinstance(error, Exception):
                failed(error, 'EXECUTOR_RESULT_FINALIZE_')
    if cancellation is not None:
        cancellation.executor_result = result
        raise cancellation
    return result
