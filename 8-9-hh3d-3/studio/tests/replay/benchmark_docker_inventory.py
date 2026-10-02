"""Read-only Docker Desktop inventory over its fixed local pipe.

No caller-selected host, context, method, path or container command. Each fresh
query shares the caller's absolute deadline. OwnedPipe retains native buffers
if cancellation/close cannot be proven; such uncertainty forbids retry. A
transport timeout with a verified close is retryable within the same total
deadline because this request is a read-only GET. Its cancel drain is cleanup
only and cannot make a late response successful.
"""
from __future__ import annotations

import ctypes as C
from ctypes import wintypes as W
import json
import os
import re
import time

from studio.host.core.pipe_io import OwnedPipe, PipeIOError

ENDPOINT = r'\\.\pipe\dockerDesktopLinuxEngine'
REQUEST = (b'GET /containers/json?all=0 HTTP/1.1\r\nHost: docker\r\n'
           b'Accept: application/json\r\nConnection: close\r\n\r\n')
BODY_LIMIT = 65536
HEADER_LIMIT = 8192
WIRE_LIMIT = BODY_LIMIT + HEADER_LIMIT * 2
_RETAINED_PIPES = []
_RETAINED_HANDLES = []


class InventoryError(RuntimeError):
    def __init__(self, reason, *, detail=None, retryable=False):
        super().__init__('DOCKER_INVENTORY_' + reason.upper())
        self.reason, self.detail, self.retryable = reason, detail, retryable


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise InventoryError('timeout')


class ResponseReader:
    """Bound header, wire and body storage without relying on pipe EOF."""
    def __init__(self, receive, deadline):
        self.receive, self.deadline = receive, deadline
        self.buffer = bytearray()
        self.total = 0

    def more(self):
        check_deadline(self.deadline)
        data = self.receive()
        check_deadline(self.deadline)
        if type(data) is not bytes or not data or len(data) > 4096:
            raise InventoryError('bad_output')
        self.total += len(data)
        if self.total > WIRE_LIMIT:
            raise InventoryError('bad_output')
        self.buffer.extend(data)

    def line(self, limit):
        while True:
            end = self.buffer.find(b'\r\n')
            if end >= 0:
                if end + 2 > limit:
                    raise InventoryError('bad_output')
                value = bytes(self.buffer[:end])
                del self.buffer[:end + 2]
                return value
            if len(self.buffer) >= limit:
                raise InventoryError('bad_output')
            self.more()

    def exact(self, length):
        if not 0 <= length <= BODY_LIMIT:
            raise InventoryError('bad_output')
        while len(self.buffer) < length:
            self.more()
        value = bytes(self.buffer[:length])
        del self.buffer[:length]
        return value


def parse_response(receive, deadline):
    reader = ResponseReader(receive, deadline)
    status = reader.line(HEADER_LIMIT)
    match = re.fullmatch(rb'HTTP/1\.[01] ([0-9]{3})(?: [\x20-\x7e]*)?', status)
    if match is None:
        raise InventoryError('bad_output')
    code = int(match[1])
    if code != 200:
        raise InventoryError('nonzero', detail=code, retryable=True)
    headers, used = {}, len(status) + 2
    while True:
        line = reader.line(HEADER_LIMIT - used)
        used += len(line) + 2
        if not line:
            break
        name, separator, value = line.partition(b':')
        if (not separator or re.fullmatch(rb'[A-Za-z0-9-]+', name) is None
                or any(c < 32 or c > 126 for c in value)):
            raise InventoryError('bad_output')
        name, value = name.lower(), value.strip()
        if name in headers:
            raise InventoryError('bad_output')
        headers[name] = value
    if headers.get(b'content-encoding', b'identity').lower() != b'identity':
        raise InventoryError('bad_output')
    if headers.get(b'content-type', b'').split(b';')[0].lower() != b'application/json':
        raise InventoryError('bad_output')
    length, encoding = headers.get(b'content-length'), headers.get(b'transfer-encoding')
    if length is not None and encoding is None:
        if not re.fullmatch(rb'[0-9]{1,8}', length):
            raise InventoryError('bad_output')
        body = reader.exact(int(length))
    elif length is None and encoding == b'chunked':
        body = bytearray()
        # Chunk extensions and trailers are not needed by the pinned daemon.
        # Reject unexpected framing rather than guessing or waiting for EOF.
        for _ in range(1024):
            size = reader.line(32)
            if not re.fullmatch(rb'[0-9a-fA-F]{1,8}', size):
                raise InventoryError('bad_output')
            count = int(size, 16)
            if count == 0:
                if reader.line(2) != b'':
                    raise InventoryError('bad_output')
                break
            if len(body) + count > BODY_LIMIT:
                raise InventoryError('bad_output')
            body.extend(reader.exact(count))
            if reader.exact(2) != b'\r\n':
                raise InventoryError('bad_output')
        else:
            raise InventoryError('bad_output')
        body = bytes(body)
    else:
        raise InventoryError('bad_output')
    if reader.buffer:
        raise InventoryError('bad_output')
    check_deadline(deadline)
    return body


def parse_names(body):
    if type(body) is not bytes or len(body) > BODY_LIMIT:
        raise InventoryError('bad_output')
    def unique(pairs):
        row = {}
        for key, value in pairs:
            if key in row:
                raise ValueError('duplicate key')
            row[key] = value
        return row
    try:
        rows = json.loads(body.decode('utf-8', 'strict'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError):
        raise InventoryError('bad_output') from None
    if type(rows) is not list or len(rows) > 4096:
        raise InventoryError('bad_output')
    names, identifiers = [], set()
    for row in rows:
        if (type(row) is not dict or type(row.get('Names')) is not list or not row['Names']
                or type(row.get('Id')) is not str
                or re.fullmatch(r'[0-9a-f]{64}', row['Id']) is None
                or row['Id'] in identifiers or row.get('State') != 'running'):
            raise InventoryError('bad_output')
        identifiers.add(row['Id'])
        for name in row['Names']:
            if type(name) is not str or re.fullmatch(r'/[a-zA-Z0-9][a-zA-Z0-9_.-]*', name) is None:
                raise InventoryError('bad_output')
            names.append(name[1:])
    if len(names) != len(set(names)) or sum(len(name) + 1 for name in names) > BODY_LIMIT:
        raise InventoryError('bad_output')
    return sorted(names)


def query_containers(deadline):
    """One fresh GET; no cache, SDK, subprocess, restart or alternate daemon."""
    check_deadline(deadline)
    if os.name != 'nt' or _RETAINED_PIPES or _RETAINED_HANDLES:
        raise InventoryError('oserror')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, C.c_void_p,
                                   W.DWORD, W.DWORD, W.HANDLE]
    kernel.CreateFileW.restype = W.HANDLE
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [W.HANDLE], W.BOOL
    # OPEN_EXISTING | FILE_FLAG_OVERLAPPED; no inherited handle and no wait on
    # busy pipe. A quick failed open may be retried under the same deadline.
    handle = kernel.CreateFileW(ENDPOINT, 0xC0000000, 0, None, 3, 0x40000000, None)
    if handle in (None, C.c_void_p(-1).value):
        raise InventoryError('oserror', detail=C.get_last_error(), retryable=True)
    try:
        owner = OwnedPipe._adopt(handle)
    except BaseException:
        if not kernel.CloseHandle(handle):
            _RETAINED_HANDLES.append((kernel, handle))
        raise InventoryError('oserror') from None
    primary = None
    names = None
    try:
        # Raw bytes with ONE absolute deadline: public frame methods would
        # prepend the studio protocol length and reset a per-operation budget.
        owner._io('write', len(REQUEST), deadline, REQUEST)
        body = parse_response(lambda: owner._io('read', 4096, deadline), deadline)
        names = parse_names(body)
    except InventoryError as error:
        primary = error
    except PipeIOError as error:
        # A timed-out read/write is safe to retry only after owner.close()
        # proves that no native pipe remains retained.  Drain-pending and
        # other I/O failures stay non-retryable because their cleanup or
        # request boundary is not sufficiently known.
        primary = InventoryError('timeout' if error.code == 'PIPE_TIMEOUT' else 'oserror',
                                 retryable=error.code == 'PIPE_TIMEOUT')
    except Exception:
        # Native wrappers can raise before OwnedPipe normalizes their error.
        # Never persist an exception containing response bytes or OS text.
        primary = InventoryError('oserror')
    finally:
        try:
            owner.close()
        except BaseException:
            _RETAINED_PIPES.append(owner)
            primary = InventoryError('oserror')
    if primary is not None:
        raise primary from None
    check_deadline(deadline)
    return names
