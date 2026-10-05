"""GT-07 M5 host-only storage fault diagnostics.

The probe exercises only owned temporary files.  It does not start Godot or
Blender and it never turns a readable staging file into a ``COMMITTED``
receipt without an observed replace and readback.  A failure after staging is
reported as ``UNKNOWN`` and the previous last-good bytes remain selected.

Native lock and cross-volume checks are authority-zero diagnostics.  They are
kept behind ``--run`` (and an explicit environment opt-in for the unittest
suite) so normal tests remain deterministic and engine-free.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

STUDIO = Path(__file__).resolve().parents[2]
REVIEWS = STUDIO / ".local" / "reviews"
SCHEMA = "gt07-m5-storage-faults-1"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{2,96}$")
ERROR_SHARING_VIOLATION = 32
ERROR_LOCK_VIOLATION = 33
ERROR_ACCESS_DENIED = 5
MOVEFILE_REPLACE_EXISTING = 0x1
MOVEFILE_WRITE_THROUGH = 0x8
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
FILE_SHARE_DELETE = 0x4
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class DiagnosticError(RuntimeError):
    """A host observation was not strong enough for a PASS."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Windows refuses FlushFileBuffers through a read-only descriptor.  Keep
    # the descriptor writable while the owned temporary is being flushed.
    with pending.open("r+b") as stream:
        stream.flush()
        os.fsync(stream.fileno())
    pending.replace(path)


def _fresh_output(output_root: Path, run_id: str) -> Path:
    if not isinstance(run_id, str) or RUN_ID_RE.fullmatch(run_id) is None:
        raise ValueError("RUN_ID_INVALID")
    allowed = REVIEWS.expanduser().resolve()
    root = output_root.expanduser().resolve()
    try:
        root.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_ROOT_FORBIDDEN") from error
    output = (root / run_id).resolve()
    try:
        output.relative_to(allowed)
    except ValueError as error:
        raise ValueError("OUTPUT_PATH_TRAVERSAL") from error
    if output.exists():
        raise ValueError("RUN_ID_USED")
    output.mkdir(parents=True)
    return output


def _identity(path: Path) -> dict[str, int] | None:
    """Return a stable volume/file identity on Windows (or a dev/inode pair)."""
    if os.name != "nt":
        try:
            stat = path.stat()
        except OSError:
            return None
        return {"volume": int(stat.st_dev), "file_id": int(stat.st_ino),
                "size": int(stat.st_size)}
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                   wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    class _Info(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("creation_hi", wintypes.DWORD),
                    ("creation_lo", wintypes.DWORD), ("access_hi", wintypes.DWORD),
                    ("access_lo", wintypes.DWORD), ("write_hi", wintypes.DWORD),
                    ("write_lo", wintypes.DWORD), ("volume", wintypes.DWORD),
                    ("file_size_hi", wintypes.DWORD), ("file_size_lo", wintypes.DWORD),
                    ("n_links", wintypes.DWORD), ("index_hi", wintypes.DWORD),
                    ("index_lo", wintypes.DWORD)]

    handle = kernel.CreateFileW(str(path), GENERIC_READ,
                                FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                None, OPEN_EXISTING, 0, None)
    if handle == INVALID_HANDLE_VALUE:
        return None
    info = _Info()
    try:
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
            return None
        return {"volume": int(info.volume),
                "file_id": (int(info.index_hi) << 32) | int(info.index_lo),
                "size": (int(info.file_size_hi) << 32) | int(info.file_size_lo)}
    finally:
        kernel.CloseHandle(handle)


LOCK_WORKER = r'''import ctypes, json, pathlib, sys
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                               ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                               ctypes.c_void_p]
kernel.CreateFileW.restype = ctypes.c_void_p
kernel.GetFileInformationByHandle.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
kernel.GetFileInformationByHandle.restype = ctypes.c_bool
kernel.CloseHandle.argtypes = [ctypes.c_void_p]
kernel.CloseHandle.restype = ctypes.c_bool
path, marker = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
handle = kernel.CreateFileW(str(path), 0xC0000000, 0, None, 3, 0x80, None)
if handle == ctypes.c_void_p(-1).value:
    marker.write_text(json.dumps({"opened": False, "error": ctypes.get_last_error()}), encoding="utf-8")
    raise SystemExit(2)
marker.write_text(json.dumps({"opened": True, "pid": __import__("os").getpid()}), encoding="utf-8")
try:
    if sys.stdin.buffer.readline(64) != b"RELEASE\n":
        raise SystemExit(3)
finally:
    kernel.CloseHandle(handle)
'''


def _write_lock_worker(output: Path) -> Path:
    path = output / "m5_lock_worker.py"
    path.write_text(LOCK_WORKER, encoding="utf-8", newline="\n")
    return path


def _read_marker(path: Path, deadline: float) -> dict[str, Any]:
    while time.monotonic() < deadline:
        if path.is_file():
            value = json.loads(path.read_text(encoding="utf-8"))
            if type(value) is not dict:
                raise DiagnosticError("LOCK_MARKER_INVALID")
            return value
        time.sleep(0.02)
    raise DiagnosticError("LOCK_MARKER_TIMEOUT")


def _move_replace(source: Path, target: Path) -> tuple[bool, int | None]:
    """Replace with native MoveFileExW, retaining the real Win32 error."""
    if os.name != "nt":
        try:
            os.replace(source, target)
            return True, None
        except OSError as error:
            return False, int(getattr(error, "errno", 1) or 1)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.MoveFileExW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    kernel.MoveFileExW.restype = wintypes.BOOL
    result = kernel.MoveFileExW(str(source), str(target),
                                MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)
    if result:
        return True, None
    return False, int(ctypes.get_last_error())


def run_file_lock(output: Path, worker: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"scenario": "file-lock-denial", "verified": False,
                              "errors": [], "native": os.name == "nt"}
    target = output / "last-good.bin"
    stage = output / "candidate.bin"
    backup = output / "last-good.backup.bin"
    old = b"last-good-m5-v1\n"
    candidate = b"candidate-m5-v2\n"
    target.write_bytes(old); backup.write_bytes(old); stage.write_bytes(candidate)
    process = None
    try:
        if os.name != "nt":
            result.update({"status": "SKIPPED", "reason": "WINDOWS_REQUIRED"})
            return result
        marker = output / "lock-holder.json"
        process = subprocess.Popen([sys.executable, "-B", str(worker), str(target), str(marker)],
                                   stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        held = _read_marker(marker, time.monotonic() + 5)
        if held.get("opened") is not True:
            raise DiagnosticError(f"LOCK_HOLDER_OPEN:{held.get('error')}")
        before = _identity(target)
        replaced, error_code = _move_replace(stage, target)
        result.update({"status": "UNKNOWN" if not replaced else "UNEXPECTED_COMMIT",
                       "replace_succeeded": replaced, "replace_error": error_code,
                       "identity_before": before})
        if process.stdin is None:
            raise DiagnosticError("LOCK_HOLDER_STDIN_MISSING")
        process.stdin.write(b"RELEASE\n"); process.stdin.flush(); process.stdin.close()
        exit_code = process.wait(timeout=5)
        result["holder_exit"] = int(exit_code)
        after = _identity(target)
        result["identity_after"] = after
        result["target_sha256"] = _sha256(target)
        result["last_good_sha256"] = _sha256_bytes(old)
        result["identity_unchanged"] = before is not None and before == after
        result["last_good_preserved"] = target.read_bytes() == old
        expected_error = error_code in {ERROR_SHARING_VIOLATION, ERROR_LOCK_VIOLATION, ERROR_ACCESS_DENIED}
        result["verified"] = bool(not replaced and expected_error and exit_code == 0
                                   and result["identity_unchanged"]
                                   and result["last_good_preserved"])
        if replaced:
            # Restore the owned fixture so an unexpected host policy does not
            # leave a candidate selected.  This result remains a failure.
            backup.replace(target)
    except Exception as error:
        result["errors"].append(str(error))
    finally:
        if process is not None and process.poll() is None:
            try:
                if process.stdin is not None and not process.stdin.closed:
                    process.stdin.write(b"RELEASE\n"); process.stdin.flush(); process.stdin.close()
                process.wait(timeout=3)
            except Exception:
                try: process.kill(); process.wait(timeout=2)
                except Exception: pass
        for path in (target, stage, backup, output / "lock-holder.json"):
            try: path.unlink()
            except OSError: pass
    return result


def _candidate_drives(destination: Path) -> tuple[Path, Path] | None:
    roots: dict[str, Path] = {}
    for letter in ("C", "D", "E"):
        root = Path(f"{letter}:\\")
        if root.exists():
            roots.setdefault(letter, root)
    destination_drive = os.path.splitdrive(str(destination))[0].upper()
    source = roots.get("C")
    target_drive = destination_drive or "D:"
    target = roots.get(target_drive.rstrip(":"))
    if source is None or target is None or source.drive.upper() == target.drive.upper():
        pairs = [(roots[a], roots[b]) for a in roots for b in roots if a != b]
        return pairs[0] if pairs else None
    return source, target


def _temp_parent_for_drive(drive: Path, destination: Path) -> Path | None:
    """Choose a writable owned temp parent without assuming a writable root."""
    wanted = drive.drive.upper()
    candidates = [Path(os.environ.get("TEMP", "")),
                  Path(os.environ.get("TMP", "")), destination.parent,
                  drive / "Temp", drive / "Windows" / "Temp"]
    seen: set[str] = set()
    for candidate in candidates:
        if not str(candidate) or str(candidate) in seen:
            continue
        seen.add(str(candidate))
        try:
            if os.path.splitdrive(str(candidate.resolve()))[0].upper() != wanted:
                continue
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / (".gt07-m5-write-" + os.urandom(6).hex())
            with probe.open("xb"):
                pass
            probe.unlink()
            return candidate
        except OSError:
            continue
    return None


def run_cross_volume(output: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"scenario": "cross-volume-replace", "verified": False,
                              "errors": [], "native": os.name == "nt"}
    if os.name != "nt":
        result.update({"status": "SKIPPED", "reason": "WINDOWS_REQUIRED"})
        return result
    pair = _candidate_drives(output)
    if pair is None:
        result.update({"status": "SKIPPED", "reason": "TWO_VOLUMES_UNAVAILABLE"})
        return result
    source_dir = destination_dir = None
    try:
        source_parent = _temp_parent_for_drive(pair[0], output)
        destination_parent = _temp_parent_for_drive(pair[1], output)
        if source_parent is None or destination_parent is None:
            result.update({"status": "SKIPPED", "reason": "TWO_WRITABLE_VOLUMES_UNAVAILABLE"})
            return result
        source_dir = Path(tempfile.mkdtemp(prefix="gt07-m5-source-", dir=str(source_parent)))
        destination_dir = Path(tempfile.mkdtemp(prefix="gt07-m5-dest-", dir=str(destination_parent)))
        source = source_dir / "candidate.bin"
        target = destination_dir / "last-good.bin"
        old = b"cross-volume-last-good\n"
        source.write_bytes(b"cross-volume-candidate\n")
        target.write_bytes(old)
        before = _identity(target)
        replaced, error_code = _move_replace(source, target)
        after = _identity(target)
        result.update({"source_drive": source.drive.upper(), "target_drive": target.drive.upper(),
                       "replace_succeeded": replaced, "replace_error": error_code,
                       "identity_before": before, "identity_after": after,
                       "target_sha256": _sha256(target), "last_good_sha256": _sha256_bytes(old)})
        # A cross-volume rename is never an atomic replace.  The required
        # proof is that the primitive refuses it and the old target remains.
        result["status"] = "UNKNOWN" if not replaced else "UNEXPECTED_COMMIT"
        result["last_good_preserved"] = target.read_bytes() == old
        result["verified"] = bool(not replaced and error_code in {17, 18, ERROR_ACCESS_DENIED}
                                   and result["last_good_preserved"])
    except Exception as error:
        result["errors"].append(str(error))
    finally:
        for directory in (source_dir, destination_dir):
            if directory is not None:
                shutil.rmtree(directory, ignore_errors=True)
    return result


def _injected_write(output: Path, mode: str) -> dict[str, Any]:
    target = output / f"{mode}-last-good.json"
    pending = output / f"{mode}-candidate.json.pending"
    old = {"version": 1, "state": "last-good"}
    new = {"version": 2, "state": "candidate"}
    _json_write(target, old)
    result: dict[str, Any] = {"scenario": f"injected-{mode}", "mode": "INJECTED",
                              "verified": False, "errors": []}
    try:
        raw = json.dumps(new, sort_keys=True).encode("utf-8")
        with pending.open("wb") as stream:
            if mode == "diskfull":
                stream.write(raw[: max(1, len(raw) // 2)])
                stream.flush()
                raise OSError("INJECTED_DISKFULL")
            stream.write(raw)
            stream.flush()
            raise OSError("INJECTED_FSYNC_FAILURE")
    except OSError as error:
        code = str(error)
        result.update({"status": "UNKNOWN", "error": code, "receipt": "ABSENT"})
    finally:
        try: pending.unlink()
        except OSError: pass
    result["last_good_preserved"] = target.read_text(encoding="utf-8") == json.dumps(old, indent=2, sort_keys=True) + "\n"
    result["committed_proof"] = False
    result["verified"] = bool(result["status"] == "UNKNOWN" and result["receipt"] == "ABSENT"
                               and result["last_good_preserved"] and not (output / "receipt.json").exists())
    target.unlink(missing_ok=True)
    return result


def _source_hashes() -> dict[str, str]:
    values = {"studio/tests/jobs/gt07_storage_faults.py": _sha256(Path(__file__))}
    values["source_closure_sha256"] = hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return values


def run_diagnostic(output_root: Path, run_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    output = _fresh_output(output_root, run_id)
    report: dict[str, Any] = {"schema": SCHEMA, "authority": 0, "diagnostic_only": True,
                              "run_id": run_id, "engine_started": False,
                              "source_hashes": _source_hashes(), "platform": os.name}
    if dry_run:
        report.update({"dry_run": True, "native_required": True})
        _json_write(output / "report.json", report)
        return report
    try:
        worker = _write_lock_worker(output)
        report["scenarios"] = [run_file_lock(output, worker), run_cross_volume(output),
                               _injected_write(output, "fsync"), _injected_write(output, "diskfull")]
        report["verified"] = bool(report["scenarios"] and all(
            row.get("verified") is True or row.get("status") == "SKIPPED"
            for row in report["scenarios"]))
        report["worker_sha256"] = _sha256(worker)
    except Exception as error:
        report.update({"status": "ERROR", "errors": [str(error)], "verified": False})
    _json_write(output / "report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, default=REVIEWS)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true", help="run owned host-only diagnostics")
    args = parser.parse_args(argv)
    if not args.dry_run and not args.run:
        parser.error("--run is required for native host diagnostics")
    try:
        result = run_diagnostic(args.output, args.run_id, dry_run=args.dry_run)
    except Exception as error:
        print(json.dumps({"schema": SCHEMA, "authority": 0, "diagnostic_only": True,
                          "run_id": args.run_id, "status": "ERROR", "error": str(error)},
                         sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("dry_run") or result.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
