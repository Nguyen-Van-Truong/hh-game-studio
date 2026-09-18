"""Fixed S97 sharing-state probe. --describe is read-only; --run launches Godot.

No production source or native ACK behavior is patched. One fresh project and
one owned pinned Godot process compare a held DELETE handle with its release.
"""
import ctypes
from ctypes import wintypes as w
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
STUDIO = ROOT / 'studio'
OUTPUT = BASE / 'run-01'
RUN_ID = 'gt06-s97-rename-probe-01'
FIXTURE = b'{"probe":"S97_RENAME_READ","version":1}\n'
PROJECT = b'config_version=5\n\n[application]\nconfig/name="S97 sharing probe"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
FLAGS = {'formal_acceptance': False, 'eligible_for_dataset': False, 's96_cause_proven': False}
sys.path.insert(0, str(ROOT))
from studio.tests.replay.benchmark_job import BenchmarkProcess, verify_capture


def need(value, code):
    if not value:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def plain(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.exists():
            info = item.lstat()
            need(not item.is_symlink() and not getattr(info, 'st_file_attributes', 0) & 0x400, 'PROBE_REPARSE')
    return path


def write(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with plain(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def sources():
    # Only the imported local module graph, plus explicitly executed script and
    # toolchain. No repository walk or claim about the formal campaign closure.
    paths = {BASE / 'rename_probe.py', BASE / 'reader.gd', STUDIO / 'toolchain.lock.json'}
    for module in list(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.is_relative_to(ROOT) and path.suffix == '.py':
                paths.add(path)
    return {path.relative_to(ROOT).as_posix(): sha(plain(path).read_bytes()) for path in sorted(paths)}


def pins():
    files = sources()
    lock = json.loads((STUDIO / 'toolchain.lock.json').read_bytes())['godot']
    need(lock['version'] == '4.7.2-stable', 'PROBE_ENGINE_VERSION')
    executable = STUDIO / '.local/tooling/godot-4.7.2-stable' / lock['gui_executable']
    need(sha(plain(executable).read_bytes()) == lock['gui_sha256'], 'PROBE_ENGINE_PIN')
    return {'run_id': RUN_ID, 'source_files': files,
        'godot': str(executable), 'godot_sha256': lock['gui_sha256'], 'godot_source_commit': lock['source_commit'],
        'python_sha256': sha(plain(Path(sys.executable)).read_bytes()), 'fixture_sha256': sha(FIXTURE),
        'fixture_size': len(FIXTURE), 'parent_watchdog_seconds': 30, 'reader_watchdog_seconds': 15, **FLAGS}


class Windows:
    def __init__(self):
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
        self.k.CreateFileW.restype = w.HANDLE
        self.k.CloseHandle.argtypes, self.k.CloseHandle.restype = [w.HANDLE], w.BOOL
        self.k.SetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.k.SetFileInformationByHandle.restype = w.BOOL
        self.k.ReadFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD), ctypes.c_void_p]
        self.k.ReadFile.restype = w.BOOL
        self.handles = []

    def open(self, path, access, share, role, *, allow_failure=False):
        ctypes.set_last_error(0)
        handle = self.k.CreateFileW(str(path), access, share, None, 3, 0x80, None)
        error = ctypes.get_last_error()
        if handle == ctypes.c_void_p(-1).value:
            need(allow_failure, 'PROBE_CREATE_FILE')
            return None, error
        row = {'role': role, 'closed': False, 'close_error': None, 'handle': handle}
        self.handles.append(row)
        return row, 0

    def close(self, row):
        if row is not None and not row['closed']:
            ok = self.k.CloseHandle(row['handle'])
            row['close_error'] = None if ok else ctypes.get_last_error()
            need(ok, 'PROBE_CLOSE_HANDLE')
            row['closed'] = True

    def rename(self, row, target):
        name = str(target)
        encoded_name = name.encode('utf-16-le')
        class RenameInfo(ctypes.Structure):
            _fields_ = [('ReplaceIfExists', w.BOOL), ('RootDirectory', w.HANDLE),
                        ('FileNameLength', w.DWORD), ('FileName', w.WCHAR * (len(encoded_name) // 2 + 1))]
        info = RenameInfo()
        info.ReplaceIfExists, info.RootDirectory = False, None
        info.FileNameLength, info.FileName = len(encoded_name), name
        need(self.k.SetFileInformationByHandle(row['handle'], 3, ctypes.byref(info), ctypes.sizeof(info)),
             'PROBE_RENAME')

    def read_shared(self, path):
        row, _ = self.open(path, 0x80000000, 7, 'shared_delete_reader')
        try:
            buffer, count = ctypes.create_string_buffer(len(FIXTURE) + 1), w.DWORD()
            need(self.k.ReadFile(row['handle'], buffer, len(buffer), ctypes.byref(count), None), 'PROBE_READ_FILE')
            return buffer.raw[:count.value]
        finally:
            self.close(row)

    def evidence(self):
        return [{key: value for key, value in row.items() if key != 'handle'} for row in self.handles]


def rows(path):
    if not path.exists():
        return {}
    raw = path.read_bytes()
    need(len(raw) <= 65536, 'PROBE_LOG_CAP')
    result = {}
    for line in raw.split(b'\n')[:-1]:
        if line.startswith(b'HH_S97_'):
            tag, body = line.split(b' ', 1)
            key = tag.decode('ascii')
            need(key not in result, 'PROBE_DUPLICATE_RESULT')
            result[key] = json.loads(body)
    return result


def exact_read(row):
    return (row['exists'] is True and row['opened'] is True and row['open_error'] == 0
        and row['size'] == row['read_size'] == len(FIXTURE) and row['sha256'] == sha(FIXTURE)
        and row['read_error'] == 0 and row['closed'] is True)


def error_row(error):
    return {'exception_class': type(error).__name__,
            'frames': [{'file': Path(frame.filename).name, 'line': frame.lineno}
                       for frame in traceback.extract_tb(error.__traceback__)[-12:]]}


def run():
    need(os.name == 'nt', 'PROBE_WINDOWS_ONLY')
    frozen = pins()
    plain(OUTPUT).mkdir(exist_ok=False)
    project = OUTPUT / 'project'
    project.mkdir()
    write(OUTPUT / 'freeze.json', frozen)
    write(project / 'project.godot', PROJECT)
    write(project / 'reader.gd', (BASE / 'reader.gd').read_bytes())
    write(project / 'control.json', FIXTURE)
    write(project / 'staged.json', FIXTURE)
    files = dict(frozen['source_files'])
    for path in (project / 'project.godot', project / 'reader.gd'):
        files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for name in files:
        write(OUTPUT / 'source' / name, (ROOT / name).read_bytes())
    windows, owner, holder, control = Windows(), None, None, None
    result = {**FLAGS, 'run_id': RUN_ID, 'completed_probe': False,
              'orchestrator_own_actual_exit_not_yet_observed': True, 'errors': []}
    code = 1
    start = time.monotonic()
    try:
        control = (project / 'control.json').open('rb')
        holder, _ = windows.open(project / 'staged.json', 0x10000, 7, 'rename_delete_holder')
        windows.rename(holder, project / 'renamed.json')
        need(not (project / 'staged.json').exists() and (project / 'renamed.json').exists(), 'PROBE_RENAME_READBACK')
        compatible = windows.read_shared(project / 'renamed.json')
        denied, denied_error = windows.open(project / 'renamed.json', 0x80000000, 3,
            'no_delete_share_control', allow_failure=True)
        windows.close(denied)
        result['windows_controls'] = {'actual_rename': True, 'holder_delete_access': True,
            'holder_share_read_write_delete': True, 'read_with_share_delete_sha256': sha(compatible),
            'read_with_share_delete_size': len(compatible), 'read_without_share_delete_opened': denied is not None,
            'read_without_share_delete_error': denied_error}
        need(compatible == FIXTURE, 'PROBE_HELD_BYTES')
        owner = BenchmarkProcess([frozen['godot'], '--headless', '--path', str(project), '--script', 'res://reader.gd'],
            cwd=project, output=OUTPUT / 'native-owner', source_root=ROOT,
            source_files=files, binary_sha256=frozen['godot_sha256'])
        released = False
        while owner.tick() is None:
            need(time.monotonic() - start < 30, 'PROBE_WALL_LIMIT')
            observed = rows(OUTPUT / 'native-owner/stdout.txt')
            if 'HH_S97_HELD' in observed and not released:
                result['held_observation'] = observed['HH_S97_HELD']
                # Release only after the actual native open result is retained.
                windows.close(holder)
                result['holder_release_mono_ns'] = time.perf_counter_ns()
                write(project / 'release.flag', b'released\n')
                released = True
            time.sleep(.02)
        capture = owner.finish()
        verify_capture(OUTPUT / 'native-owner', sha((OUTPUT / 'native-owner/capture.json').read_bytes()),
            source_root=ROOT, expected_source_files=files, expected_binary_sha256=frozen['godot_sha256'])
        observed = rows(OUTPUT / 'native-owner/stdout.txt')
        need(set(observed) == {'HH_S97_HELD', 'HH_S97_RELEASED'}, 'PROBE_NATIVE_RESULTS')
        held, after = observed['HH_S97_HELD'], observed['HH_S97_RELEASED']
        need(held['pid'] == after['pid'] == capture['actual_process_exit']['pid']
             and held['engine']['hash'] == frozen['godot_source_commit'], 'PROBE_NATIVE_IDENTITY')
        result['native_observations'] = observed
        result['actual_native_exit'] = capture['actual_process_exit']
        result['native_helper_pid'] = owner.process.pid
        result['native_helper_exit'] = owner.process.returncode
        result['checks'] = {'python_read_handle_allows_native_read': exact_read(held['control']),
            'held_delete_blocks_native_open': held['held']['exists'] is True
                and held['held']['opened'] is False and held['held']['open_error'] != 0,
            'windows_no_delete_share_error_is_32': denied is None and denied_error == 32,
            'released_same_file_reads_exact': exact_read(after['released']),
            'retained_bytes_unchanged': (project / 'renamed.json').read_bytes() == FIXTURE,
            'source_unchanged': sources() == frozen['source_files'],
            'native_stderr_empty': not (OUTPUT / 'native-owner/stderr.txt').read_bytes().strip()}
        result['completed_probe'] = True
        result['mechanism_observed'] = all(result['checks'].values())
        code = 0 if result['mechanism_observed'] else 2
    except BaseException as error:
        owner = owner or getattr(error, 'cleanup_owner', None)
        result['errors'].append(error_row(error))
    finally:
        for row in windows.handles:
            try:
                windows.close(row)
            except BaseException as error:
                result['errors'].append(error_row(error))
        if control is not None:
            control.close()
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                result['errors'].append(error_row(error))
            result['native_owner'] = {'closed': owner.closed,
                'helper_pid': owner.process.pid if owner.process else None,
                'helper_exit': owner.process.returncode if owner.process else None,
                'job': owner.job.snapshot() if owner.job else None,
                'wrapper_handle_closed': owner._process_handle_closed,
                'wrapper_handle_close_uncertain': owner._process_handle_close_uncertain,
                'drain_threads_alive': [thread.is_alive() for thread in owner.threads]}
        result['windows_handles'] = windows.evidence()
        result['python_control_closed'] = control is None or control.closed
        result['elapsed_seconds'] = time.monotonic() - start
        if result['errors']:
            code = 1
        result['returned_exit_code'] = code
        write(OUTPUT / 'result.json', result)
    return code


if __name__ == '__main__':
    need(sys.argv[1:] in (['--describe'], ['--run']), 'PROBE_FIXED_MODE')
    if sys.argv[1:] == ['--describe']:
        print(json.dumps({'pins': pins(), 'launch_performed': False}, sort_keys=True))
    else:
        raise SystemExit(run())
