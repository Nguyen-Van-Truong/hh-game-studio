"""Trusted Linux/x86-64 launcher, layered over the pinned Docker confinement.

Install before Godot parses any candidate (including static initialization).
This filter does not replace the read-only mounts, network namespace, resource
limits or PID-1 deadline. It is not a public script execution capability.
"""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import socket
import sys

ARCH_X86_64 = 0xC000003E
ALLOW, KILL, ERRNO = 0x7FFF0000, 0x80000000, 0x00050000
CLONE_THREAD = 0x10000
BINARY = '/tool/Godot_v4.7.2-stable_linux.x86_64'
STAGED_PROJECT = '/tmp/gameplay-project'
# Linux x86-64 syscall table. Other ABIs (including x32) are rejected first.
DENIED = (41, 53, 57, 58, 62, 101, 200, 272, 308, 310, 311, 438)


def instructions():
    # sock_filter: code, true jump, false jump, operand.
    rows = [(0x20, 0, 0, 4), (0x15, 1, 0, ARCH_X86_64), (0x06, 0, 0, KILL),
            (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, KILL)]
    for number in DENIED:
        rows.extend(((0x15, 0, 1, number), (0x06, 0, 0, ERRNO | errno.EPERM)))
    # clone3 uses an indirect structure that classic BPF cannot inspect.
    # ENOSYS lets libc fall back to clone for engine threads, not processes.
    rows.extend(((0x15, 0, 1, 435), (0x06, 0, 0, ERRNO | errno.ENOSYS),
                 (0x15, 0, 3, 56), (0x20, 0, 0, 16),
                 (0x45, 1, 0, CLONE_THREAD), (0x06, 0, 0, ERRNO | errno.EPERM),
                 (0x06, 0, 0, ALLOW)))
    return rows


def install():
    if sys.platform != 'linux' or platform.machine() != 'x86_64' or os.getuid() != 65532:
        raise RuntimeError('GAMEPLAY_SANDBOX_PLATFORM')
    if len(list(Path('/proc/self/task').iterdir())) != 1:
        raise RuntimeError('GAMEPLAY_SANDBOX_MUST_PRECEDE_THREADS')

    class Filter(ctypes.Structure):
        _fields_ = [('code', ctypes.c_ushort), ('jt', ctypes.c_ubyte),
                    ('jf', ctypes.c_ubyte), ('k', ctypes.c_uint)]

    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filter', ctypes.POINTER(Filter))]

    rows = instructions()
    array = (Filter * len(rows))(*(Filter(*row) for row in rows))
    program = Program(len(rows), array)
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.restype = ctypes.c_int
    # Seccomp is inherited across execve and subsequent engine threads.
    if libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'GAMEPLAY_NO_NEW_PRIVILEGES')
    if libc.prctl(22, 2, ctypes.byref(program), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'GAMEPLAY_SECCOMP_INSTALL')


def verify_denials():
    """Fixed trusted OS probes, executed before any candidate code is loaded."""
    try:
        pid = os.fork()
    except OSError as error:
        if error.errno != errno.EPERM:
            raise RuntimeError('GAMEPLAY_FORK_WRONG_ERRNO') from error
    else:
        if pid == 0:
            os._exit(91)
        os.waitpid(pid, 0)
        raise RuntimeError('GAMEPLAY_FORK_NOT_BLOCKED')
    for family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
        try:
            channel = socket.socket(family, socket.SOCK_STREAM)
        except OSError as error:
            if error.errno != errno.EPERM:
                raise RuntimeError('GAMEPLAY_SOCKET_WRONG_ERRNO') from error
        else:
            channel.close()
            raise RuntimeError('GAMEPLAY_SOCKET_NOT_BLOCKED')


def command(phase, *, parse_script=None):
    common = [BINARY, '--headless', '--path', STAGED_PROJECT, '--log-file', '/tmp/engine.log']
    if parse_script is not None:
        if (phase != 'parse' or type(parse_script) is not str
                or not parse_script.startswith('scripts/') or not parse_script.endswith('.gd')
                or any(ord(char) < 32 or char in '\\:' for char in parse_script)
                or any(part in ('', '.', '..') for part in parse_script.split('/'))
                or PurePosixPath(parse_script).as_posix() != parse_script):
            raise ValueError('GAMEPLAY_SANDBOX_SCRIPT_PATH')
    if phase == 'parse':
        return common + ['--check-only', '--script', 'res://' + (parse_script or 'scripts/fixture_actor.gd')]
    if phase == 'import':
        return common + ['--editor', '--import', 'res://scenes/fixture.tscn']
    if phase == 'play':
        return common + ['res://scenes/fixture.tscn']
    if phase == 'readback':
        return common + ['--script', '/harness/validation_bootstrap.gd']
    raise ValueError('GAMEPLAY_SANDBOX_PHASE')


def stage_project():
    """Stage the immutable host snapshot once in a disposable writable tmpfs.

    Godot's importer writes adjacent ``.import`` sidecars. The source bind is
    intentionally read-only, so the staged copy permits import without
    allowing candidate code to mutate the measured input or its host snapshot.
    The same container runs parse, import and play as separate child processes;
    retaining this directory lets the play phase consume import sidecars.
    Before every phase, all source bytes are compared with the immutable bind;
    only Godot's disposable cache/sidecar files may differ.
    """
    source = Path('/project')
    destination = Path(STAGED_PROJECT)
    if not destination.exists():
        shutil.copytree(source, destination, symlinks=False)
        return destination
    def source_file(path, root):
        relative = path.relative_to(root)
        return (path.is_file() and '.godot' not in relative.parts
                and not path.name.endswith(('.import', '.uid')))
    source_files = sorted(path.relative_to(source).as_posix() for path in source.rglob('*')
                          if source_file(path, source))
    staged_files = sorted(path.relative_to(destination).as_posix() for path in destination.rglob('*')
                          if source_file(path, destination))
    if source_files != staged_files:
        raise RuntimeError('GAMEPLAY_STAGE_SOURCE_CHANGED')
    for relative in source_files:
        if (source / relative).read_bytes() != (destination / relative).read_bytes():
            raise RuntimeError('GAMEPLAY_STAGE_SOURCE_CHANGED')
    return destination


def main():
    if len(sys.argv) not in (2, 3):
        raise ValueError('GAMEPLAY_SANDBOX_ARGUMENTS')
    phase = sys.argv[1]
    parse_script = sys.argv[2] if len(sys.argv) == 3 else None
    stage_project()
    argv = command(phase, parse_script=parse_script)
    install()
    verify_denials()
    print('HH_GAMEPLAY_OS_GUARD fork=EPERM socket=EPERM', flush=True)
    os.execv(argv[0], argv)


if __name__ == '__main__':
    main()
