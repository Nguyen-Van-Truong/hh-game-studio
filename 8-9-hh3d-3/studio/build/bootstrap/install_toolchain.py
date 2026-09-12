"""Offline bootstrap in a private local root; not a hostile-code sandbox.

No downloads/PATH edits/executable launches. Failed stages and crash locks stay
for diagnosis. Activation and rollback journal share one atomic JSON document.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys
import uuid
import zipfile
import time

_spec = importlib.util.spec_from_file_location('hh_archive_verifier', Path(__file__).with_name('verify_archive.py'))
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)
MAX_FILES, MAX_FILE, MAX_TOTAL = 32, 512 * 1024**2, 1024**3
HEX = re.compile(r'[0-9a-f]{64}')
DEVICES = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}
STATE = 'toolchain.local.json'
LOCK_SCHEMA = 'HH3D-BOOTSTRAP-LEASE-2'
MAX_LOCK_AGE_SECONDS = 7 * 24 * 60 * 60

class InstallError(ValueError):
    pass

def require(ok, message):
    if not ok:
        raise InstallError(message)

def safe_path(path):
    path = Path(path)
    require('..' not in path.parts and not str(path).startswith(('\\\\','//')), 'traversal/network path refused')
    path = path.absolute()
    for part in path.parts[1:]:
        require(':' not in part and not part.endswith((' ','.')) and part.split('.')[0].upper() not in DEVICES,
                'device/alias/stream path refused')
    for parent in [*reversed(path.parents), path]:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0) & 0x400,
                'reparse/symlink refused')
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                'nonregular or hardlink path refused')
    return path

def sha(path):
    path = safe_path(path)
    before = verifier._identity(path)
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024**2), b''):
            h.update(chunk)
    require(before == verifier._identity(path), 'file changed during hash')
    return h.hexdigest()

def file_record(path):
    """Hash and size under one identity window; still cooperative, not safe-open."""
    path = safe_path(path)
    before = verifier._identity(path)
    digest = hashlib.sha256(); size = 0
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024**2), b''):
            size += len(chunk); digest.update(chunk)
    after = verifier._identity(path)
    require(before == after and size == after[2], 'file changed while recording manifest')
    return {'sha256': digest.hexdigest(), 'size_bytes': size}

def read_json(path):
    path = safe_path(path)
    before = verifier._identity(path)
    value = verifier._json_no_duplicates(verifier._read_bounded(path,128*1024))
    require(before == verifier._identity(path), 'JSON changed while reading')
    return value

def encode(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode()

def member_name(value):
    require(isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,119}',value), 'nonportable member')
    require(value.split('.')[0].upper() not in DEVICES and not value.endswith('.'), 'device/alias member')
    return value

def pin_details(lock):
    verifier._lock_details(lock)
    pin = lock['godot']
    names = [member_name(pin.get(k)) for k in ('console_executable','gui_executable')]
    require(len(set(n.casefold() for n in names)) == 2, 'duplicate executable names')
    for key in ('console_sha256','gui_sha256'):
        require(isinstance(pin.get(key),str) and HEX.fullmatch(pin[key]), 'invalid executable digest')
    return pin

def closure(package):
    result = {}
    for child in safe_path(package).iterdir():
        safe_path(child)
        require(child.is_file(), 'unexpected directory in package')
        member_name(child.name)
        if child.name != 'manifest.json':
            result[child.name] = file_record(child)
    return result

def read_package(root, receipt):
    require(isinstance(receipt,dict) and set(receipt)=={'package','manifest_sha256'}, 'invalid receipt')
    require(all(isinstance(v,str) and HEX.fullmatch(v) for v in receipt.values()), 'invalid receipt digest')
    package = safe_path(root/'packages'/receipt['package'])
    require(sha(package/'manifest.json') == receipt['manifest_sha256'], 'manifest differs from receipt')
    manifest = read_json(package/'manifest.json')
    require(manifest.get('schema')=='HH3D-BOOTSTRAP-PACKAGE-1' and manifest.get('package')==receipt['package'], 'invalid manifest')
    require(manifest.get('files')==closure(package), 'package closure changed')
    return manifest

def process_start(pid):
    """Read a live process's creation identity without ever sending a signal.

    None means the process is gone. Access denial and unsupported platforms
    fail closed. PID reuse is distinguished from the owner recorded in a lease.
    """
    require(type(pid) is int and 0 < pid < 0xFFFFFFFF, 'INVALID_PID')
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
        kernel.GetProcessTimes.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID absent.
                return None
            raise InstallError('lock owner cannot be inspected')
        try:
            wait = kernel.WaitForSingleObject(handle, 0)
            if wait == 0:
                return None
            require(wait == 258, 'lock owner wait failed')  # WAIT_TIMEOUT: alive.
            times = [wintypes.FILETIME() for _ in range(4)]
            require(kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)),
                    'lock owner creation time unavailable')
            created = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            return 'windows:' + str(created)
        finally:
            kernel.CloseHandle(handle)
    if sys.platform.startswith('linux'):
        try:
            raw = Path('/proc', str(pid), 'stat').read_text(encoding='ascii')
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise InstallError('lock owner cannot be inspected') from exc
        fields = raw[raw.rfind(')') + 2:].split()
        require(len(fields) > 19, 'lock owner creation time unavailable')
        if fields[0] in ('Z', 'X'):
            return None
        boot_id = Path('/proc/sys/kernel/random/boot_id').read_text(encoding='ascii').strip()
        return 'linux:' + boot_id + ':' + fields[19]
    raise InstallError('process identity unsupported on this platform')


@contextmanager
def mutation_guard(root):
    """Serialize cooperating writers/recovery; the OS releases this on crash.

    This persistent file must never be unlinked: replacing a guard would split
    the lock domain. It contains no PID or token and is not an active lease.
    """
    path = safe_path(root / '.mutation.guard')
    with path.open('a+b') as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'\0')
            handle.flush()
            os.fsync(handle.fileno())
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise InstallError('mutation guard busy') from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise InstallError('mutation guard busy') from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def lock_token(root):
    """Read the exact metadata token needed for explicit stale-lock recovery."""
    return sha(safe_path(Path(root) / '.mutation.lock'))


def require_lock_unchanged(path, identity, token):
    require(verifier._identity(path) == identity and sha(path) == token,
            'lock changed; refusing to remove replacement')


@contextmanager
def lease(root):
    root = safe_path(root)
    root.mkdir(parents=True, exist_ok=True)
    with mutation_guard(root):
        path = safe_path(root / '.mutation.lock')
        payload = {'schema': LOCK_SCHEMA, 'pid': os.getpid(),
                   'process_start': process_start(os.getpid()),
                   'created_ns': time.time_ns(), 'nonce': uuid.uuid4().hex}
        require(payload['process_start'] is not None, 'lease owner identity unavailable')
        with path.open('xb') as handle:
            handle.write(encode(payload))
            handle.flush()
            os.fsync(handle.fileno())
        identity = verifier._identity(path)
        token = hashlib.sha256(encode(payload)).hexdigest()
        try:
            yield root
        finally:
            # Refuse deletion if even a noncooperating edit replaced metadata.
            require_lock_unchanged(path, identity, token)
            path.unlink()


def sync_directory(path):
    """Do not turn a failed fsync into success or leak its file descriptor.

    Python's Windows CRT cannot open directories for fsync. Surface that
    limitation in successful results; file contents are still fsynced.
    """
    if os.name == 'nt':
        return 'FILE_FLUSHED_DIRECTORY_SYNC_UNAVAILABLE_WINDOWS'
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return 'FILE_AND_DIRECTORY_SYNCED'

def install(archive_path, sums_path, lock_path, root_path):
    archive_path,sums_path,lock_path = map(Path,(archive_path,sums_path,lock_path))
    observed = verifier.verify_archive(lock_path,archive_path,sums_path)
    lock_hash = sha(lock_path)
    pin = pin_details(read_json(lock_path))
    required = {pin['console_executable']:pin['console_sha256'],pin['gui_executable']:pin['gui_sha256']}
    metadata = {'license','license.txt','license.md','readme','readme.txt','readme.md'}
    package_id = observed['sha256']
    with lease(root_path) as root:
        for name in ('packages','stages'):
            safe_path(root/name).mkdir(exist_ok=True)
        destination = safe_path(root/'packages'/package_id)
        require(not destination.exists(), 'immutable package already exists')
        stage = root/'stages'/uuid.uuid4().hex
        stage.mkdir()
        with zipfile.ZipFile(archive_path) as zipped:
            infos = zipped.infolist()
            require(1<=len(infos)<=MAX_FILES, 'ZIP member count limit')
            names,total = set(),0
            for info in infos:
                name = member_name(info.filename)
                require(name.casefold() not in names, 'duplicate/case-colliding ZIP member')
                names.add(name.casefold())
                mode = stat.S_IFMT(info.external_attr>>16)
                require(mode in (0,stat.S_IFREG) and not info.is_dir() and not info.external_attr & 0x400, 'nonregular ZIP member')
                require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED), 'unsupported ZIP compression')
                require(name in required or name.lower() in metadata, 'unexpected ZIP member')
                total += info.file_size
                require(0<=info.file_size<=MAX_FILE and total<=MAX_TOTAL, 'ZIP expansion limit')
            require(set(n.casefold() for n in required).issubset(names), 'missing executable')
            for info in infos:
                copied = 0
                with zipped.open(info) as src,(stage/info.filename).open('xb') as dst:
                    for chunk in iter(lambda:src.read(1024**2),b''):
                        copied += len(chunk)
                        require(copied<=info.file_size, 'ZIP member exceeds declared length')
                        dst.write(chunk)
                    dst.flush(); os.fsync(dst.fileno())
                require(copied==info.file_size, 'short ZIP member')
        files = closure(stage)
        require(all(files[n]['sha256']==digest for n,digest in required.items()), 'executable digest mismatch')
        require(observed==verifier.verify_archive(lock_path,archive_path,sums_path) and sha(lock_path)==lock_hash, 'bootstrap inputs changed')
        manifest = {'schema':'HH3D-BOOTSTRAP-PACKAGE-1','package':package_id,'version':pin['version'],'lock_sha256':lock_hash,'files':files}
        with (stage/'manifest.json').open('xb') as handle:
            handle.write(encode(manifest)); handle.flush(); os.fsync(handle.fileno())
        receipt = {'package':package_id,'manifest_sha256':sha(stage/'manifest.json')}
        os.rename(stage,destination)  # Same volume, exclusive cooperative lease.
        durability = sync_directory(root/'packages')
        read_package(root,receipt)
    return {'status':'INSTALLED_NOT_ACTIVATED','receipt':receipt,'version':pin['version'],
            'durability':durability}

def state_token(root):
    path = safe_path(Path(root)/STATE)
    return sha(path) if path.exists() else 'NONE'

def read_state(root, expected):
    require(isinstance(expected,str) and (expected=='NONE' or HEX.fullmatch(expected)), 'explicit CAS token required')
    require(state_token(root)==expected, 'active state CAS mismatch')
    if expected=='NONE':
        return None
    state = read_json(root/STATE)
    require(state.get('schema')=='HH3D-BOOTSTRAP-ACTIVE-1' and type(state.get('revision')) is int and state['revision']>0
            and isinstance(state.get('transition_id'),str), 'invalid active state')
    require(state_token(root)==expected, 'active state changed while reading')
    if state.get('current') is not None:
        read_package(root,state['current'])
    return state

def publish(root, state, expected):
    temporary = safe_path(root/('.active-'+uuid.uuid4().hex+'.tmp'))
    with temporary.open('xb') as handle:
        handle.write(encode(state)); handle.flush(); os.fsync(handle.fileno())
    require(state_token(root)==expected, 'active state edited before publish')
    # Previous receipt and journal share this JSON; no two-file crash window.
    os.replace(temporary,root/STATE)
    durability = sync_directory(root)
    require((root/STATE).read_bytes()==encode(state), 'readback failed; inspect state before retry')
    return {'status':state['operation'],'state_token':state_token(root),'transition_id':state['transition_id'],
            'revision':state['revision'],'current':state['current'],'durability':durability}

def activate(root_path, receipt, expected_state):
    with lease(root_path) as root:
        current = read_state(root,expected_state)
        read_package(root,receipt)
        state = {'schema':'HH3D-BOOTSTRAP-ACTIVE-1','revision':(current['revision'] if current else 0)+1,
                 'transition_id':uuid.uuid4().hex,'operation':'ACTIVATED','current':receipt,
                 'previous':current['current'] if current else None}
        return publish(root,state,expected_state)

def rollback(root_path, expected_state, expected_transition):
    with lease(root_path) as root:
        current = read_state(root,expected_state)
        require(current is not None and current['operation']=='ACTIVATED' and current['transition_id']==expected_transition,
                'rollback edited/superseded/already applied')
        previous = current['previous']
        if previous is not None:
            read_package(root,previous)
        state = {'schema':'HH3D-BOOTSTRAP-ACTIVE-1','revision':current['revision']+1,'transition_id':uuid.uuid4().hex,
                 'operation':'ROLLED_BACK','current':previous,'previous':None}
        return publish(root,state,expected_state)

def recover_lock(root_path, *, expected_lock=None, max_age_seconds=300):
    """Reclaim one observed dead owner's metadata under the cooperative guard.

    Old metadata without a creation identity is intentionally not upgraded or
    deleted. Inspect it manually. TTL is a minimum age, never proof of death.
    """
    require(isinstance(expected_lock, str) and HEX.fullmatch(expected_lock),
            'explicit lock CAS token required')
    require(type(max_age_seconds) is int and 0 <= max_age_seconds <= MAX_LOCK_AGE_SECONDS,
            'invalid lock age threshold')
    root = safe_path(root_path)
    require(root.is_dir(), 'lock root unavailable')
    with mutation_guard(root):
        path = safe_path(root / '.mutation.lock')
        require(path.exists(), 'no stale lock exists')
        identity = verifier._identity(path)
        require(lock_token(root) == expected_lock, 'lock CAS mismatch')
        payload = read_json(path)
        require(type(payload.get('pid')) is int and 0 < payload['pid'] < 0xFFFFFFFF,
                'INVALID_PID')
        require(set(payload) == {'schema', 'pid', 'process_start', 'created_ns', 'nonce'}
                and payload['schema'] == LOCK_SCHEMA
                and isinstance(payload['nonce'], str)
                and re.fullmatch(r'[0-9a-f]{32}', payload['nonce'])
                and isinstance(payload['process_start'], str)
                and re.fullmatch(r'(?:windows:[1-9][0-9]{0,19}|linux:[0-9a-f-]{36}:[1-9][0-9]{0,19})', payload['process_start'])
                and type(payload['created_ns']) is int and payload['created_ns'] > 0,
                'lock metadata invalid; manual inspection required')
        age = time.time_ns() - payload['created_ns']
        require(age >= max_age_seconds * 1_000_000_000,
                'lock is too recent to reclaim')
        start = process_start(payload['pid'])
        require(start is None or start != payload['process_start'], 'lock owner is still running')
        require_lock_unchanged(path, identity, expected_lock)
        path.unlink()
        return {'status': 'STALE_LOCK_RECOVERED', 'pid': payload['pid'],
                'created_ns': payload['created_ns'], 'recovered_lock': expected_lock}

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    commands = ap.add_subparsers(dest='command',required=True)
    p = commands.add_parser('install')
    for name in ('archive','sums','lock','root'):
        p.add_argument('--'+name,type=Path,required=True)
    p = commands.add_parser('activate')
    p.add_argument('--root',type=Path,required=True); p.add_argument('--package',required=True)
    p.add_argument('--manifest-sha256',required=True); p.add_argument('--expected-state',required=True)
    p = commands.add_parser('rollback')
    p.add_argument('--root',type=Path,required=True); p.add_argument('--expected-state',required=True)
    p.add_argument('--expected-transition',required=True)
    p = commands.add_parser('recover-lock')
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--expected-lock',required=True)
    p.add_argument('--max-age-seconds',type=int,default=300)
    args = ap.parse_args(argv)
    try:
        if args.command=='install':
            result = install(args.archive,args.sums,args.lock,args.root)
        elif args.command=='activate':
            result = activate(args.root,{'package':args.package,'manifest_sha256':args.manifest_sha256},args.expected_state)
        elif args.command=='rollback':
            result = rollback(args.root,args.expected_state,args.expected_transition)
        else:
            result = recover_lock(args.root,expected_lock=args.expected_lock,max_age_seconds=args.max_age_seconds)
    except (ValueError,OSError,zipfile.BadZipFile,KeyError,TypeError):
        print('BOOTSTRAP_REJECTED: verify inputs and inspect current activation before retry',file=sys.stderr)
        return 2
    print(json.dumps(result)); return 0

if __name__=='__main__':
    raise SystemExit(main())
