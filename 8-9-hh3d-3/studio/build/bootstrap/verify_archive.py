"""Offline, bytes-only verification for the pinned Godot archive.

This module deliberately does not extract or install anything.  It checks the
lock, the detached sums file, and the archive, and returns observations only.
The lstat checks reduce ordinary replacement mistakes; they are not a
race-proof safe-open primitive.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import urlsplit


class VerificationError(ValueError):
    """A sanitized, expected verification failure."""


_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")
_HEX128 = re.compile(r"^[0-9a-fA-F]{128}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-stable$")
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*\.zip$")
_SUM_ROW = re.compile(r"^\s*([0-9a-fA-F]{128})\s+\*?([^\s]+)\s*$")
_MAX_LOCK = 64 * 1024
_MAX_SUMS = 1024 * 1024
_MAX_ARCHIVE = 8 * 1024 * 1024 * 1024
_REPARSE = 0x400


def _fail(message: str) -> None:
    raise VerificationError(message)


def _identity(path: Path) -> tuple[int, int, int, int, int, int]:
    """lstat every component and return the final file identity."""
    p = Path(path)
    if '..' in p.parts or str(p).startswith(('\\\\', '//')):
        _fail("traversal or network path is not allowed")
    p = p.absolute()
    for component in p.parts[1:]:
        if ':' in component or component.endswith((' ', '.')):
            _fail("alias or alternate stream path is not allowed")
    current = Path(p.anchor) if p.anchor else Path.cwd()
    parts = p.parts[1:] if p.anchor else p.parts
    try:
        for part in parts:
            current = current / part
            info = os.lstat(current)
            if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & _REPARSE):
                _fail("symlink or reparse point is not allowed")
        info = os.lstat(p)
    except (OSError, ValueError):
        _fail("input path is unavailable")
    if not stat.S_ISREG(info.st_mode):
        _fail("input is not a regular file")
    if info.st_nlink != 1:
        _fail("input has unexpected hard links")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def _read_bounded(path: Path, limit: int) -> bytes:
    try:
        with path.open("rb") as handle:
            data = handle.read(limit + 1)
    except OSError:
        _fail("input cannot be read")
    if len(data) > limit:
        _fail("input exceeds permitted size")
    return data


def _json_no_duplicates(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("lock contains duplicate keys")
            result[key] = value
        return result
    try:
        text = data.decode("utf-8")
        value = json.loads(text, object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError):
        _fail("lock is not valid UTF-8 JSON")
    if not isinstance(value, dict):
        _fail("lock root must be an object")
    return value


def _lock_details(lock: dict) -> tuple[str, str, str, str, int, str, str]:
    if lock.get('schema') != 'HH-STUDIO-TOOLCHAIN-LOCK-2' or lock.get('status') != 'CANDIDATE':
        _fail('unsupported lock schema or status')
    try:
        godot = lock["godot"]
        version = godot["version"]
        archive = godot["archive"]
        name, url = archive["name"], archive["url"]
        sha256, sha512, size = archive["sha256"], archive["sha512"], archive["size_bytes"]
        sums_sha256 = godot["sha512_sums"]["sha256"]
    except (KeyError, TypeError):
        _fail("lock is missing archive fields")
    if not isinstance(version, str) or not _VERSION.fullmatch(version):
        _fail("lock version is invalid")
    if not isinstance(name, str) or not _NAME.fullmatch(name) or "/" in name or "\\" in name:
        _fail("lock archive name is invalid")
    expected_url = f"https://github.com/godotengine/godot-builds/releases/download/{version}/{name}"
    if not isinstance(url, str):
        _fail('lock archive URL is invalid')
    try:
        parsed = urlsplit(url)
    except ValueError:
        _fail("lock archive URL is invalid")
    if url != expected_url or parsed.query or parsed.fragment or parsed.username or parsed.password:
        _fail("lock archive URL is invalid")
    if not isinstance(sha256, str) or not _HEX64.fullmatch(sha256):
        _fail("lock archive SHA256 is invalid")
    if not isinstance(sha512, str) or not _HEX128.fullmatch(sha512):
        _fail("lock archive SHA512 is invalid")
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= _MAX_ARCHIVE:
        _fail("lock archive size is invalid")
    if not isinstance(sums_sha256, str) or not _HEX64.fullmatch(sums_sha256):
        _fail("lock sums SHA256 is invalid")
    return version, name, url, sha256.lower(), size, sha512.lower(), sums_sha256.lower()


def _verify_sums(raw: bytes, name: str, expected: str, pinned_sha256: str) -> str:
    observed = hashlib.sha256(raw).hexdigest()
    if observed != pinned_sha256:
        _fail("sums SHA256 does not match lock")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        _fail("sums file is not UTF-8")
    matches = 0
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _SUM_ROW.fullmatch(line)
        if not match:
            _fail("sums file contains a malformed row")
        digest, filename = match.groups()
        if filename == name:
            matches += 1
            if digest.lower() != expected:
                _fail("sums archive digest does not match lock")
    if matches != 1:
        _fail("sums file must contain exactly one archive row")
    return observed


def verify_archive(lock_path: Path, archive_path: Path, sums_path: Path) -> dict:
    """Verify three local files and return a portable VERIFIED_BYTES_ONLY record."""
    paths = [Path(lock_path), Path(archive_path), Path(sums_path)]
    before = [_identity(path) for path in paths]
    lock = _json_no_duplicates(_read_bounded(paths[0], _MAX_LOCK))
    version, name, _url, expected256, expected_size, expected512, pinned_sums = _lock_details(lock)
    if paths[1].name != name:
        _fail("archive filename does not match lock")
    sums_raw = _read_bounded(paths[2], _MAX_SUMS)
    sums_sha = _verify_sums(sums_raw, name, expected512, pinned_sums)
    digest256, digest512 = hashlib.sha256(), hashlib.sha512()
    total = 0
    try:
        with paths[1].open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > expected_size or total > _MAX_ARCHIVE:
                    _fail("archive exceeds locked size")
                digest256.update(chunk)
                digest512.update(chunk)
    except OSError:
        _fail("archive cannot be read")
    after = [_identity(path) for path in paths]
    if before != after:
        _fail("input identity changed while verifying")
    observed256, observed512 = digest256.hexdigest(), digest512.hexdigest()
    if total != expected_size or observed256 != expected256 or observed512 != expected512:
        _fail("archive bytes do not match lock")
    return {"schema": "HH3D-ARCHIVE-VERIFIED-1", "artifact": "godot.archive",
            "name": name, "version": version, "size_bytes": total,
            "sha256": observed256, "sha512": observed512, "sums_sha256": sums_sha,
            "status": "VERIFIED_BYTES_ONLY",
            "limits": ["offline bytes only", "not race-proof handle security", "no extraction or bootstrap"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("lock_path")
    parser.add_argument("archive_path")
    parser.add_argument("sums_path")
    args = parser.parse_args(argv)
    try:
        result = verify_archive(Path(args.lock_path), Path(args.archive_path), Path(args.sums_path))
    except (VerificationError, OSError, ValueError):
        print("archive verification failed", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
