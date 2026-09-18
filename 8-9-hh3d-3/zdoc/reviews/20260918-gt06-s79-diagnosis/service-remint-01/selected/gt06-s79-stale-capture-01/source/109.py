"""Internal, fixed-slot GLB admission stage; invoke with one private root.

The trusted coordinator provisions/leases an existing local directory and
launches this source under the pinned Python Job's CPU/RAM/wall limits. This
script neither proves directory ACL privacy nor replaces that process owner.
Ordinary path replacement is checked using lstat/fstat identities; these are
not a hostile concurrent-writer safe-open primitive.

Inputs: fixture.glb (<=1 MiB), expected.json (<=4 KiB) containing exactly
artifact_sha256. Outputs are exclusive preflight.json (<=1 MiB) and
semantic.json (<=16 MiB), including their final LF. A failed stage may leave
partial exclusive outputs; preserve it and use a fresh root for a retry.
The completion marker hashes exact output file bytes. Its semantic_sha256 is
the FILE hash, distinct from preflight.json's canonical semantic fingerprint.
No native process, transport, import or public publication is performed here.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

if __package__ in (None, ""):
    # Source path is internal and pinned by the caller, never supplied by input.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from pipeline.preflight import inspect_asset
else:
    from .preflight import inspect_asset

MAX_GLB_BYTES = 1_048_576
MAX_EXPECTED_BYTES = 4096
MAX_PREFLIGHT_BYTES = 1_048_576
MAX_SEMANTIC_BYTES = 16 * 1_048_576
MARKER = "GT05_ADMISSION_COMPLETE "
_OUTPUTS = ("preflight.json", "semantic.json")
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,79}\Z")


class AdmissionRejected(ValueError):
    """Stable code, never candidate paths or data."""


def _need(ok: bool, code: str) -> None:
    if not ok:
        raise AdmissionRejected(code)


def _reparse(info) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def _root(value) -> Path:
    path = Path(value)
    _need(path.is_absolute() and path != Path(path.anchor) and ".." not in path.parts and
          not str(path).startswith(("\\\\", "//")), "ADMISSION_ROOT_LOCAL_ABSOLUTE")
    _need(all(":" not in part and not part.endswith((" ", ".")) for part in path.parts[1:]),
          "ADMISSION_ROOT_ALIAS")
    for component in (path, *path.parents):
        info = component.lstat()
        _need(stat.S_ISDIR(info.st_mode) and not _reparse(info), "ADMISSION_ROOT_DIRECTORY_OR_REPARSE")
    return path


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns,
            info.st_nlink, info.st_mode)


def _file_info(path: Path, limit: int):
    info = path.lstat()
    _need(stat.S_ISREG(info.st_mode) and not _reparse(info) and info.st_nlink == 1,
          "ADMISSION_REGULAR_SINGLE_LINK_REQUIRED")
    _need(0 < info.st_size <= limit, "ADMISSION_INPUT_SIZE_LIMIT")
    return info


def _read_bounded(path: Path, limit: int) -> bytes:
    entry = _file_info(path, limit)  # Refuse oversized/nonregular inputs BEFORE open/read.
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        _need(_identity(before) == _identity(entry) and not _reparse(before), "ADMISSION_INPUT_IDENTITY")
        raw = stream.read(entry.st_size + 1)
        after = os.fstat(stream.fileno())
    current = _file_info(path, limit)
    _need(len(raw) == entry.st_size and _identity(after) == _identity(entry) == _identity(current),
          "ADMISSION_INPUT_CHANGED")
    return raw


def _expected(raw: bytes) -> str:
    def pairs(items):
        value = {}
        for key, item in items:
            _need(key not in value, "ADMISSION_EXPECTED_DUPLICATE_KEY")
            value[key] = item
        return value

    def constant(_):
        raise AdmissionRejected("ADMISSION_EXPECTED_NONFINITE")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except AdmissionRejected:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise AdmissionRejected("ADMISSION_EXPECTED_JSON") from None
    _need(type(value) is dict and set(value) == {"artifact_sha256"} and
          type(value["artifact_sha256"]) is str and _HEX64.fullmatch(value["artifact_sha256"]) is not None,
          "ADMISSION_EXPECTED_FIELDS")
    return value["artifact_sha256"]


def _encoded(value, limit: int) -> bytes:
    """Check byte growth during serialization before creating either output."""
    result = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    try:
        for piece in encoder.iterencode(value):
            raw = piece.encode("ascii")
            _need(len(result) + len(raw) + 1 <= limit, "ADMISSION_OUTPUT_SIZE_LIMIT")
            result.extend(raw)
    except AdmissionRejected:
        raise
    except (ValueError, TypeError, RecursionError):
        raise AdmissionRejected("ADMISSION_OUTPUT_JSON") from None
    result.append(10)
    return bytes(result)


def _outputs_absent(root: Path) -> None:
    for name in _OUTPUTS:
        try:
            (root / name).lstat()
        except FileNotFoundError:
            continue
        raise AdmissionRejected("ADMISSION_OUTPUT_EXISTS")


def _write_exclusive(path: Path, raw: bytes) -> str:
    try:
        with path.open("xb") as stream:
            info = os.fstat(stream.fileno())
            _need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and not _reparse(info),
                  "ADMISSION_OUTPUT_IDENTITY")
            _need(stream.write(raw) == len(raw), "ADMISSION_OUTPUT_SHORT_WRITE")
            stream.flush()
    except FileExistsError:
        raise AdmissionRejected("ADMISSION_OUTPUT_EXISTS") from None
    digest = hashlib.sha256(raw).hexdigest()
    _need(hashlib.sha256(_read_bounded(path, len(raw))).hexdigest() == digest, "ADMISSION_OUTPUT_CHANGED")
    return digest


def run_admission(directory: Path) -> dict:
    """Internal helper; the CLI emits its marker only after all outputs verify."""
    root = _root(directory)
    _outputs_absent(root)
    # Precheck both slots before reading either. No caller controls their names.
    glb_path, expected_path = root / "fixture.glb", root / "expected.json"
    _file_info(glb_path, MAX_GLB_BYTES)
    _file_info(expected_path, MAX_EXPECTED_BYTES)
    expected_raw = _read_bounded(expected_path, MAX_EXPECTED_BYTES)
    expected_hash = _expected(expected_raw)
    raw = _read_bounded(glb_path, MAX_GLB_BYTES)
    artifact_hash = hashlib.sha256(raw).hexdigest()
    _need(artifact_hash == expected_hash, "ADMISSION_ARTIFACT_HASH")
    report, semantic = inspect_asset(raw)
    report_bytes = _encoded(report, MAX_PREFLIGHT_BYTES)
    semantic_bytes = _encoded(semantic, MAX_SEMANTIC_BYTES)
    # The byte snapshot used by inspection must still be the staged input.
    _root(root)
    _need(_read_bounded(expected_path, MAX_EXPECTED_BYTES) == expected_raw and
          _read_bounded(glb_path, MAX_GLB_BYTES) == raw, "ADMISSION_STAGED_INPUT_CHANGED")
    _outputs_absent(root)
    preflight_hash = _write_exclusive(root / "preflight.json", report_bytes)
    semantic_hash = _write_exclusive(root / "semantic.json", semantic_bytes)
    return {"artifact_sha256": artifact_hash, "preflight_sha256": preflight_hash, "semantic_sha256": semantic_hash}


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    try:
        _need(len(args) == 1 and type(args[0]) is str, "ADMISSION_ARGUMENTS")
        marker = run_admission(Path(args[0]))
        print(MARKER + json.dumps(marker, sort_keys=True, separators=(",", ":")), flush=True)
        return 0
    except Exception as exc:
        code = str(exc) if isinstance(exc, ValueError) and _CODE.fullmatch(str(exc)) else "ADMISSION_FAILED"
        print(code, file=sys.stderr, flush=True)
        return 17


if __name__ == "__main__":
    sys.exit(main())
