"""Synthetic owned-TEMP retained-handle rename experiment, not a safe writer.

Contains an intentional same-token replacement race simulation on synthetic
canaries to establish the absence of expected-destination identity CAS.
"""
from contextlib import ExitStack
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

from restricted_acl_probe import A, K, N, IOSB, BAD, checked, make_directory, security_readback, signature, token_string

class FILE_ID(C.Structure):
    _fields_ = [("volume", C.c_ulonglong), ("id", C.c_ubyte * 16)]
class STANDARD(C.Structure):
    _fields_ = [("allocation", C.c_longlong), ("size", C.c_longlong), ("links", W.DWORD), ("deleted", W.BYTE), ("directory", W.BYTE)]
class ATTR(C.Structure):
    _fields_ = [("attributes", W.DWORD), ("reparse_tag", W.DWORD)]

signature(K, "GetFileInformationByHandleEx", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "SetFileInformationByHandle", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "GetFinalPathNameByHandleW", [W.HANDLE, W.LPWSTR, W.DWORD, W.DWORD], W.DWORD)
signature(K, "SetFilePointerEx", [W.HANDLE, C.c_longlong, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "ReadFile", [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p], W.BOOL)
signature(K, "FlushFileBuffers", [W.HANDLE], W.BOOL)
signature(K, "GetVolumeInformationW", [W.LPCWSTR, W.LPWSTR, W.DWORD, C.POINTER(W.DWORD), C.POINTER(W.DWORD), C.POINTER(W.DWORD), W.LPWSTR, W.DWORD], W.BOOL)
signature(N, "RtlNtStatusToDosError", [C.c_long], W.ULONG)

def inspect(handle):
    identity, standard, attrs = FILE_ID(), STANDARD(), ATTR()
    for kind, value in ((18, identity), (1, standard), (9, attrs)):
        checked(K.GetFileInformationByHandleEx(handle, kind, C.byref(value), C.sizeof(value)))
    path = C.create_unicode_buffer(32768)
    count = K.GetFinalPathNameByHandleW(handle, path, len(path), 0)
    assert 0 < count < len(path)
    return {"volume": int(identity.volume), "file_id": bytes(identity.id).hex(), "size": int(standard.size),
            "links": int(standard.links), "delete_pending": bool(standard.deleted), "directory": bool(standard.directory),
            "attributes": int(attrs.attributes), "reparse_tag": int(attrs.reparse_tag), "final_path": path.value}

def write_flush_read(handle, payload):
    count = W.DWORD()
    checked(K.WriteFile(handle, C.create_string_buffer(payload), len(payload), C.byref(count), None))
    assert count.value == len(payload)
    checked(K.FlushFileBuffers(handle))
    data = read(handle)
    assert data == payload
    return {"bytes_written": int(count.value), "flush_file_buffers_success": True, "readback_sha256": hashlib.sha256(data).hexdigest()}

def read(handle):
    checked(K.SetFilePointerEx(handle, 0, None, 0))
    buffer, count = C.create_string_buffer(4096), W.DWORD()
    checked(K.ReadFile(handle, buffer, len(buffer), C.byref(count), None))
    return buffer.raw[:count.value]

def rename(source, directory, name, replace, backend="native"):
    assert Path(name).name == name and ":" not in name and name not in (".", "..")
    class RENAME(C.Structure):
        _fields_ = [("flags", W.DWORD), ("root", W.HANDLE), ("length", W.DWORD), ("name", W.WCHAR * (len(name) + 1))]
    info = RENAME()
    info.flags, info.root, info.length, info.name = int(replace), directory, len(name.encode("utf-16-le")), name
    if backend == "win32":
        ok = K.SetFileInformationByHandle(source, 3, C.byref(info), RENAME.name.offset + info.length)
        error = 0 if ok else C.get_last_error()
        status = None
    else:
        iosb = IOSB()
        status = N.NtSetInformationFile(source, C.byref(iosb), C.byref(info), RENAME.name.offset + info.length, 10)
        ok = status >= 0
        error = 0 if ok else int(N.RtlNtStatusToDosError(status))
    return {"success": bool(ok), "winerror": error, "ntstatus": None if status is None else "0x%08X" % (status & 0xffffffff), "backend": backend, "replace_if_exists": replace,
            "root_directory_handle": True, "relative_basename": name, "source_reopened_by_path": False,
            "has_expected_destination_id_parameter": False}

def main():
    result = {"run_id": "GT02-S30-HANDLE-PUBLISH-06", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "os": platform.platform(), "python": platform.python_version(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "scope": "Owned TEMP only; API observations; no sandbox/durability/capability acceptance", "seed": 30,
              "directory_access": "FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES", "directory_share": "READ|WRITE; no DELETE"}
    own = W.HANDLE()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(own)))
    base = None
    try:
        user = token_string(own)
        descriptor = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user + ")"
        with tempfile.TemporaryDirectory(prefix="gt02-s30-handle-publish-") as tmp, ExitStack() as stack:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s30-handle-publish-")
            handles = set()
            def close(handle):
                if handle in handles:
                    checked(K.CloseHandle(handle))
                    handles.remove(handle)
            def open_file(path, directory=False, fresh=False):
                handle = K.CreateFileW(str(path), 0x81 if directory else 0xC0010000, 3 if directory else 0,
                                       None, 1 if fresh else 3, 0x00200000 | (0x02000000 if directory else 0), None)
                if handle == BAD:
                    raise C.WinError(C.get_last_error())
                handles.add(handle)
                stack.callback(close, handle)
                return handle
            staging, release = base / "staging", base / "release"
            make_directory(staging, descriptor)
            make_directory(release, descriptor)
            stage_dir, release_dir = open_file(staging, True), open_file(release, True)
            filesystem = C.create_unicode_buffer(256)
            checked(K.GetVolumeInformationW(base.anchor, None, 0, None, None, None, filesystem, len(filesystem)))
            result["filesystem"] = filesystem.value
            result["effective_sddl"] = {"staging": security_readback(staging, True), "release": security_readback(release, True)}
            src = open_file(staging / "fresh-stage.bin", fresh=True)
            result["create_identity"] = inspect(src)
            result["write"] = write_flush_read(src, b"S30-ORIGINAL-FROZEN-PAYLOAD")
            before = inspect(src)
            result["pre_publish_identity"] = before
            result["destination_directory_identity"] = inspect(release_dir)
            result["win32_root_relative_publish"] = rename(src, release_dir, "published-đích.bin", False, "win32")
            assert not result["win32_root_relative_publish"]["success"], "Probe expects this host's observed Win32 RootDirectory rejection; investigate behavior change"
            result["create_only_publish"] = rename(src, release_dir, "published-đích.bin", False)
            after = inspect(src)
            result["post_publish_identity"] = after
            result["same_source_identity"] = (before["volume"], before["file_id"]) == (after["volume"], after["file_id"])
            result["same_volume"] = before["volume"] == inspect(release_dir)["volume"]
            result["source_name_absent"] = not (staging / "fresh-stage.bin").exists()
            result["post_publish_readback_sha256"] = hashlib.sha256(read(src)).hexdigest()
            assert result["create_only_publish"]["success"]
            assert result["same_source_identity"] and result["same_volume"] and result["source_name_absent"]
            assert after["links"] == 1 and not after["delete_pending"] and after["reparse_tag"] == 0
            assert after["final_path"] == "\\\\?\\" + str(release / "published-đích.bin")
            contender = open_file(staging / "contender.bin", fresh=True)
            write_flush_read(contender, b"S30-CONTENDER-PAYLOAD")
            result["create_only_collision"] = rename(contender, release_dir, "published-đích.bin", False)
            result["collision_kept_destination"] = inspect(src)["file_id"] == after["file_id"] and read(src) == b"S30-ORIGINAL-FROZEN-PAYLOAD"
            result["collision_kept_source"] = inspect(contender)["final_path"] == "\\\\?\\" + str(staging / "contender.bin")
            result["replace_while_target_open"] = rename(contender, release_dir, "published-đích.bin", True)
            close(src)
            raced = open_file(staging / "attacker.bin", fresh=True)
            write_flush_read(raced, b"S30-SAME-TOKEN-SWAP")
            result["same_token_target_swap"] = rename(raced, release_dir, "published-đích.bin", True)
            result["changed_target_identity_before_replace"] = inspect(raced)
            close(raced)
            result["replace_after_target_identity_changed"] = rename(contender, release_dir, "published-đích.bin", True)
            result["replacement_identity"] = inspect(contender)
            result["replacement_readback_sha256"] = hashlib.sha256(read(contender)).hexdigest()
            assert not result["create_only_collision"]["success"] and result["collision_kept_destination"] and result["collision_kept_source"]
            assert not result["replace_while_target_open"]["success"]
            assert result["same_token_target_swap"]["success"] and result["replace_after_target_identity_changed"]["success"]
            assert result["changed_target_identity_before_replace"]["file_id"] != after["file_id"]
            result["marker"] = "GT02_S30_HANDLE_PUBLISH_OBSERVATIONS_COMPLETE"
    except Exception as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc), "winerror": getattr(exc, "winerror", None)}
    finally:
        checked(K.CloseHandle(own))
    result["owned_temp_removed"] = base is not None and not base.exists()
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 1 if "error" in result else 0

if __name__ == "__main__":
    sys.exit(main())
