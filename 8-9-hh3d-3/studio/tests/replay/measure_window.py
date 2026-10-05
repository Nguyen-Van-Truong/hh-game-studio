"""Cooperative measurement lease across repository agents (O5.6).

The permanent kernel guard prevents racing owners. The visible marker is
single-use and remains on uncertain cleanup; expiry alone never steals a live
owner. Other agents must check the marker before launching engines or Docker.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import errno
import json
import os
from pathlib import Path
import stat
import uuid

from studio.host.core.journal import Journal
from studio.tests.replay.benchmark_job import require


def default_path():
    base = os.environ.get('LOCALAPPDATA')
    require(bool(base), 'MEASURE_WINDOW_LOCALAPPDATA_MISSING')
    return Path(base) / 'HHGodotAgent/measure-window.lock'


def plain(path):
    for part in (path, *path.absolute().parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode)
                and not getattr(info, 'st_file_attributes', 0) & 0x400,
                'MEASURE_WINDOW_UNSAFE_PATH')
        if part == path:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                    'MEASURE_WINDOW_UNSAFE_PATH')


@contextmanager
def measurement_window(run_id, purpose, *, path=None, safe_to_release=lambda: True):
    path = Path(path) if path is not None else default_path()
    plain(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    guard = path.with_suffix('.guard')
    plain(guard)
    fd = os.open(guard, os.O_CREAT | os.O_RDWR | getattr(os, 'O_BINARY', 0)
                 | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    held = False
    marker = None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                'MEASURE_WINDOW_UNSAFE_GUARD')
        try:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            held = True
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                require(False, 'MEASURE_WINDOW_BUSY')
            raise
        if path.exists():
            plain(path)
            require(path.stat().st_size <= 4096, 'MEASURE_WINDOW_INVALID_MARKER')
            old = json.loads(path.read_bytes())
            require(type(old) is dict and type(old.get('pid')) is int
                    and old['pid'] > 0, 'MEASURE_WINDOW_INVALID_MARKER')
            # Unknown/access-denied and PID reuse stay occupied. Recovery only
            # proves death; every new launch still has its engine preflight.
            require(not Journal._pid_alive(old['pid']), 'MEASURE_WINDOW_BUSY')
            path.unlink()
        now = datetime.now(timezone.utc)
        value = {'schema': 'HH-MEASURE-WINDOW-1', 'owner': 'hh3d-coordinator',
                 'pid': os.getpid(), 'run_id': run_id, 'purpose': purpose,
                 'claimed_utc': now.isoformat(),
                 'expires_utc': (now + timedelta(hours=24)).isoformat(),
                 'nonce': uuid.uuid4().hex}
        marker = (json.dumps(value, sort_keys=True) + '\n').encode()
        with path.open('xb') as stream:
            stream.write(marker)
            stream.flush()
            os.fsync(stream.fileno())
        require(path.read_bytes() == marker, 'MEASURE_WINDOW_READBACK')
        yield value
    finally:
        try:
            if marker is not None and safe_to_release():
                plain(path)
                require(path.read_bytes() == marker, 'MEASURE_WINDOW_OWNER_CHANGED')
                path.unlink()
        finally:
            try:
                if held:
                    if os.name == 'nt':
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
