"""Fixed internal GT06 execution-binding reader; no acceptance authority.

The installed coordinator supplies the binding path, its frozen exact-byte hash,
the source map already authenticated by native_runner.accepted_inputs(), and the
explicit required dependency set. None is a remote request field. The original
GT05 asset verifier remains responsible for accepted payload provenance.

This reader validates cooperative frozen source files; it is not a new hostile
filesystem sandbox. The launch owner must keep its existing before/after source
checks, source snapshots, native ownership and postcondition checks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat


SCHEMA = 'HH-GT06-EXECUTION-BINDING-1'
GT05_MANIFEST_SHA256 = 'fd0b4a984c7bee261c083c07d461baf55325e936d66df2eeab897b422ee0a02b'
GT05_SOURCE_PREFIX = '8-9-hh3d-3/studio/'
MAX_BINDING_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_FILES = 2048
_TOP_KEYS = {'schema', 'accepted_gt05_manifest_sha256', 'source_files'}
_DEVICE = re.compile(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])\Z', re.IGNORECASE)


class BindingRejected(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _need(condition: bool, code: str) -> None:
    if not condition:
        raise BindingRejected(code)


def _digest(value: object) -> str:
    _need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value) is not None,
          'BINDING_DIGEST')
    return value


def _name(value: object) -> str:
    _need(type(value) is str and 0 < len(value) <= 1024, 'BINDING_SOURCE_PATH')
    _need(not any(ord(char) < 32 or ord(char) == 127 or 0xD800 <= ord(char) <= 0xDFFF
                  or char in '\\:<>"|?*' for char in value),
          'BINDING_SOURCE_PATH')
    parts = value.split('/')
    _need(all(part not in ('', '.', '..') and part == part.rstrip(' .')
              and _DEVICE.fullmatch(part.split('.', 1)[0]) is None for part in parts),
          'BINDING_SOURCE_PATH')
    _need(parts[0].casefold() != '.local', 'BINDING_GENERATED_SOURCE')
    return value


def _source_map(value: object) -> dict[str, str]:
    _need(type(value) is dict and 0 < len(value) <= MAX_SOURCE_FILES,
          'BINDING_SOURCE_MAP')
    result: dict[str, str] = {}
    aliases: set[str] = set()
    for name, digest in value.items():
        _name(name)
        _need(name.casefold() not in aliases, 'BINDING_SOURCE_ALIAS')
        aliases.add(name.casefold())
        result[name] = _digest(digest)
    return dict(sorted(result.items()))


def _absolute(path: Path) -> Path:
    path = Path(path)
    _need('..' not in path.parts, 'BINDING_PATH')
    return path.absolute()


def _checked_stat(path: Path, *, file: bool):
    try:
        for component in (path, *path.parents):
            info = component.lstat()
            _need(not stat.S_ISLNK(info.st_mode)
                  and not getattr(info, 'st_file_attributes', 0) & 0x400,
                  'BINDING_REPARSE')
            if component == path:
                leaf = info
                expected = stat.S_ISREG(info.st_mode) if file else stat.S_ISDIR(info.st_mode)
                _need(expected, 'BINDING_FILE_TYPE')
            else:
                _need(stat.S_ISDIR(info.st_mode), 'BINDING_FILE_TYPE')
        return leaf
    except OSError:
        raise BindingRejected('BINDING_FILE_MISSING_OR_UNREADABLE') from None


def _identity(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read(path: Path, cap: int) -> bytes:
    before = _checked_stat(path, file=True)
    _need(0 <= before.st_size <= cap, 'BINDING_FILE_SIZE')
    try:
        with path.open('rb') as stream:
            opened = os.fstat(stream.fileno())
            _need(_identity(opened) == _identity(before), 'BINDING_FILE_CHANGED')
            raw = stream.read(cap + 1)
            _need(_identity(os.fstat(stream.fileno())) == _identity(before),
                  'BINDING_FILE_CHANGED')
    except OSError:
        raise BindingRejected('BINDING_FILE_MISSING_OR_UNREADABLE') from None
    _need(_identity(_checked_stat(path, file=True)) == _identity(before),
          'BINDING_FILE_CHANGED')
    _need(0 <= len(raw) == before.st_size <= cap, 'BINDING_FILE_SIZE')
    return raw


def _json_object(raw: bytes) -> dict:
    def pairs(rows):
        result = {}
        for key, value in rows:
            _need(key not in result, 'BINDING_JSON_DUPLICATE_KEY')
            result[key] = value
        return result

    def constant(_value):
        raise BindingRejected('BINDING_JSON_NONFINITE')

    try:
        # Explicit UTF-8 decoding also rejects the JSON decoder's UTF-16/32 fallback.
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                           parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise BindingRejected('BINDING_JSON') from None
    _need(type(value) is dict, 'BINDING_SCHEMA')
    return value


def _object(raw: bytes) -> dict:
    value = _json_object(raw)
    _need(set(value) == _TOP_KEYS, 'BINDING_SCHEMA')
    _need(value['schema'] == SCHEMA, 'BINDING_SCHEMA')
    _need(value['accepted_gt05_manifest_sha256'] == GT05_MANIFEST_SHA256,
          'BINDING_GT05_ANCHOR')
    return value


def read_execution_binding(studio: Path, binding_path: Path, *, expected_sha256: str,
                           accepted_source_files: dict[str, str],
                           required_sources: frozenset[str]) -> dict[str, str]:
    """Return the verified current map, never a reminted map or success receipt.

    ``accepted_source_files`` must come from the existing pinned GT05 manifest
    reader. Its hashes describe historical source and are not current-source
    expectations. Every historical key remains mandatory in this initial design.
    ``required_sources`` is the installed entrypoint dependency inventory; it is
    deliberately not inferred from the candidate document or a remote caller.
    A separate coordinator-owned freeze pins this file and every runtime reader.
    """
    expected_sha256 = _digest(expected_sha256)
    studio, binding_path = _absolute(studio), _absolute(binding_path)
    _checked_stat(studio, file=False)
    _need(type(accepted_source_files) is dict and 0 < len(accepted_source_files) <= MAX_SOURCE_FILES,
          'BINDING_ACCEPTED_SOURCE_MAP')
    inherited = {}
    for name, digest in accepted_source_files.items():
        _need(type(name) is str and name.startswith(GT05_SOURCE_PREFIX),
              'BINDING_ACCEPTED_SOURCE_DOMAIN')
        inherited[name[len(GT05_SOURCE_PREFIX):]] = digest
    inherited = _source_map(inherited)
    _need(type(required_sources) is frozenset and 0 < len(required_sources) <= MAX_SOURCE_FILES,
          'BINDING_REQUIRED_SOURCES')
    required = _source_map({_name(name): '0' * 64 for name in required_sources})

    raw = _read(binding_path, MAX_BINDING_BYTES)
    _need(hashlib.sha256(raw).hexdigest() == expected_sha256, 'BINDING_MANIFEST_HASH')
    value = _object(raw)
    files = _source_map(value['source_files'])
    _need(set(inherited) | set(required) <= set(files), 'BINDING_MISSING_DEPENDENCY')
    for name, digest in files.items():
        data = _read(studio / name, MAX_SOURCE_BYTES)
        _need(hashlib.sha256(data).hexdigest() == digest, 'REPLAY_REUSE_SOURCE_CHANGED')
    # Detect a persistent change to the binding while its source files were read.
    _need(_read(binding_path, MAX_BINDING_BYTES) == raw, 'BINDING_FILE_CHANGED')
    return dict(files)
