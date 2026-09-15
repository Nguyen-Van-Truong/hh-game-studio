"""Report-only Windows access-check diagnostic. No production imports or writes.

Uses restricted impersonation only, NOT an isolation sandbox. The probe can
RevertToSelf, so its results never prove process isolation. Every filesystem
operation targets synthetic files in one owned TEMP directory. No existing
ACL, account, profile, privilege policy, or production file is changed.
"""
from __future__ import annotations
import ctypes as C
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import tempfile
import uuid

K = C.WinDLL("kernel32", use_last_error=True)
A = C.WinDLL("advapi32", use_last_error=True)
N = C.WinDLL("ntdll")
BAD = C.c_void_p(-1).value

class SA(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]

class SIDATTR(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("attributes", W.DWORD)]

class IOSB(C.Structure):
    _fields_ = [("status", C.c_void_p), ("information", C.c_size_t)]

def signature(dll, name, args, result):
    f = getattr(dll, name)
    f.argtypes, f.restype = args, result
    return f

signature(K, "GetCurrentProcess", [], W.HANDLE)
signature(K, "CloseHandle", [W.HANDLE], W.BOOL)
signature(K, "LocalFree", [C.c_void_p], C.c_void_p)
signature(K, "CreateDirectoryW", [W.LPCWSTR, C.POINTER(SA)], W.BOOL)
signature(K, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(SA), W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
signature(K, "CreateHardLinkW", [W.LPCWSTR, W.LPCWSTR, C.c_void_p], W.BOOL)
signature(A, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL)
signature(A, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL)
signature(A, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL)
signature(A, "ConvertStringSidToSidW", [W.LPCWSTR, C.POINTER(C.c_void_p)], W.BOOL)
signature(A, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL)
signature(A, "CreateRestrictedToken", [W.HANDLE, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, C.c_void_p, W.DWORD, C.POINTER(SIDATTR), C.POINTER(W.HANDLE)], W.BOOL)
signature(A, "ImpersonateLoggedOnUser", [W.HANDLE], W.BOOL)
signature(A, "RevertToSelf", [], W.BOOL)
signature(N, "NtSetInformationFile", [W.HANDLE, C.POINTER(IOSB), C.c_void_p, W.ULONG, C.c_int], C.c_long)

def checked(result):
    if not result:
        raise C.WinError(C.get_last_error())
    return result

def token_string(token):
    count = W.DWORD()
    A.GetTokenInformation(token, 1, None, 0, C.byref(count))
    buf = C.create_string_buffer(count.value)
    checked(A.GetTokenInformation(token, 1, buf, count, C.byref(count)))
    sid = C.cast(buf, C.POINTER(SIDATTR)).contents.sid
    text = W.LPWSTR()
    checked(A.ConvertSidToStringSidW(sid, C.byref(text)))
    try:
        return text.value
    finally:
        K.LocalFree(text)

def make_directory(path, sddl):
    descriptor = C.c_void_p()
    checked(A.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, C.byref(descriptor), None))
    try:
        checked(K.CreateDirectoryW(str(path), C.byref(SA(C.sizeof(SA), descriptor, False))))
    finally:
        K.LocalFree(descriptor)

def open_result(path, desired):
    handle = K.CreateFileW(str(path), desired, 7, None, 3, 0x00200000, None)
    return (None, C.get_last_error()) if handle == BAD else (handle, 0)

def native_link(handle, target):
    name = "\\??\\" + str(target)
    class LINK(C.Structure):
        _fields_ = [("replace", W.BYTE), ("root", W.HANDLE), ("length", W.ULONG), ("name", W.WCHAR * (len(name) + 1))]
    info = LINK()
    info.length, info.name = len(name.encode("utf-16-le")), name
    iosb = IOSB()
    status = N.NtSetInformationFile(handle, C.byref(iosb), C.byref(info), LINK.name.offset + info.length, 11)
    return "0x%08X" % (status & 0xffffffff)

def exercise(label, private, scratch):
    result = {"context": label, "source_opens_winerror": {}}
    source = private / "synthetic-source"
    handle0 = None
    for name, desired in (("zero", 0), ("attributes", 0x80), ("read", 0x80000000), ("write_dac", 0x40000), ("write_owner", 0x80000)):
        handle, error = open_result(source, desired)
        result["source_opens_winerror"][name] = error
        if name == "zero":
            handle0 = handle
        elif handle is not None:
            checked(K.CloseHandle(handle))
    link = scratch / (label + "-win32-link")
    ok = K.CreateHardLinkW(str(link), str(source), None)
    result["win32_hardlink_winerror"] = 0 if ok else C.get_last_error()
    if handle0 is not None:
        try:
            result["native_zero_handle_link_ntstatus"] = native_link(handle0, scratch / (label + "-native-link"))
        finally:
            checked(K.CloseHandle(handle0))
    else:
        result["native_zero_handle_link_ntstatus"] = "NOT_RUN_NO_HANDLE"
    child = K.CreateFileW(str(scratch / (label + "-positive-create")), 0x40000000, 0, None, 1, 0x00200000, None)
    result["scratch_create_winerror"] = C.get_last_error() if child == BAD else 0
    if child != BAD:
        checked(K.CloseHandle(child))
    return result

def main():
    assert os.name == "nt"
    out = {"run_id": "GT02-S29-RESTRICTED-ACL-01", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "os": platform.platform(), "python": platform.python_version(),
           "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "scope": "synthetic TEMP; restricted impersonation only; not process isolation", "cases": []}
    own = W.HANDLE()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 0xF01FF, C.byref(own)))
    sid = C.c_void_p()
    restricted_handles = []
    base = None
    try:
        user_sid = token_string(own)
        synthetic = "S-1-5-21-" + "-".join(str(int.from_bytes(uuid.uuid4().bytes[:4], "little")) for _ in range(3)) + "-11929"
        checked(A.ConvertStringSidToSidW(synthetic, C.byref(sid)))
        restriction = SIDATTR(sid, 0)
        with tempfile.TemporaryDirectory(prefix="gt02-s29-restricted-acl-") as tmp:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s29-restricted-acl-")
            private, scratch = base / "private", base / "scratch"
            # Protected DACLs at directory creation; inherited by synthetic children.
            # OWNER RIGHTS RC removes the implicit owner WRITE_DAC shortcut.
            private_sddl = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user_sid + ")"
            scratch_sddl = private_sddl + "(A;OICI;FA;;;" + synthetic + ")"
            make_directory(private, private_sddl)
            make_directory(scratch, scratch_sddl)
            source = private / "synthetic-source"
            source.write_bytes(b"synthetic-no-outside-data")
            out["cases"].append(exercise("unrestricted", private, scratch))
            for label, flags in (("full_restrict", 1), ("write_restrict", 9)):
                token = W.HANDLE()
                checked(A.CreateRestrictedToken(own, flags, 0, None, 0, None, 1, C.byref(restriction), C.byref(token)))
                restricted_handles.append(token)
                checked(A.ImpersonateLoggedOnUser(token))
                try:
                    case = exercise(label, private, scratch)
                finally:
                    checked(A.RevertToSelf())
                out["cases"].append(case)
            out["private_payload_unchanged"] = source.read_bytes() == b"synthetic-no-outside-data"
            out["final_source_link_count"] = source.stat().st_nlink
    finally:
        checked(A.RevertToSelf())
        for token in restricted_handles:
            checked(K.CloseHandle(token))
        if sid.value:
            K.LocalFree(sid)
        checked(K.CloseHandle(own))
    out["owned_temp_removed"] = base is not None and not base.exists()
    print(json.dumps(out, indent=2))

if __name__ == "__main__":
    main()
