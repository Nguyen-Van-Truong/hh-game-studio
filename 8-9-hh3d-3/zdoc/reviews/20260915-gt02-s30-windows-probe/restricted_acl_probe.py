"""Report-only Windows access-check diagnostic. No production imports or writes.

Tests restricted impersonation and attempts one primary-token child, NOT a
production isolation sandbox. Impersonation can RevertToSelf, so access-check
results alone never prove process isolation. Every filesystem operation targets
synthetic files in one owned TEMP directory. No existing user/system ACL,
account, profile, privilege policy, or production file is changed.
"""
from __future__ import annotations
import ctypes as C
from contextlib import ExitStack
from ctypes import wintypes as W
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
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
signature(K, "OpenProcess", [W.DWORD, W.BOOL, W.DWORD], W.HANDLE)
signature(K, "WriteFile", [W.HANDLE, C.c_void_p, W.DWORD, C.POINTER(W.DWORD), C.c_void_p], W.BOOL)
signature(K, "DeleteFileW", [W.LPCWSTR], W.BOOL)
signature(K, "MoveFileExW", [W.LPCWSTR, W.LPCWSTR, W.DWORD], W.BOOL)
signature(A, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL)
signature(A, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL)
signature(A, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL)
signature(A, "ConvertStringSidToSidW", [W.LPCWSTR, C.POINTER(C.c_void_p)], W.BOOL)
signature(A, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL)
signature(A, "CreateRestrictedToken", [W.HANDLE, W.DWORD, W.DWORD, C.c_void_p, W.DWORD, C.c_void_p, W.DWORD, C.POINTER(SIDATTR), C.POINTER(W.HANDLE)], W.BOOL)
signature(A, "ImpersonateLoggedOnUser", [W.HANDLE], W.BOOL)
signature(A, "RevertToSelf", [], W.BOOL)
signature(A, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD)
signature(A, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(W.LPWSTR), C.c_void_p], W.BOOL)
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

def security_readback(path, directory=False):
    handle = K.CreateFileW(str(path), 0x20000, 7, None, 3, 0x00200000 | (0x02000000 if directory else 0), None)
    if handle == BAD:
        raise C.WinError(C.get_last_error())
    descriptor, rendered = C.c_void_p(), W.LPWSTR()
    try:
        error = A.GetSecurityInfo(handle, 1, 7, None, None, None, None, C.byref(descriptor))
        if error:
            raise C.WinError(error)
        checked(A.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 7, C.byref(rendered), None))
        return rendered.value
    finally:
        if rendered:
            K.LocalFree(rendered)
        if descriptor.value:
            K.LocalFree(descriptor)
        checked(K.CloseHandle(handle))

def token_details(token):
    def information(kind):
        count = W.DWORD()
        A.GetTokenInformation(token, kind, None, 0, C.byref(count))
        buf = C.create_string_buffer(count.value)
        checked(A.GetTokenInformation(token, kind, buf, count, C.byref(count)))
        return buf
    class GROUPS(C.Structure):
        _fields_ = [("count", W.DWORD), ("first", SIDATTR)]
    buf = information(11)
    count = C.cast(buf, C.POINTER(W.DWORD)).contents.value
    entries = C.cast(C.addressof(buf) + GROUPS.first.offset, C.POINTER(SIDATTR))
    sids = []
    for index in range(count):
        rendered = W.LPWSTR()
        checked(A.ConvertSidToStringSidW(entries[index].sid, C.byref(rendered)))
        try:
            sids.append(rendered.value)
        finally:
            K.LocalFree(rendered)
    return {"token_type": int(C.cast(information(8), C.POINTER(W.DWORD)).contents.value),
            "restricted_sids": sids, "privilege_count": int(C.cast(information(3), C.POINTER(W.DWORD)).contents.value)}

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

def exercise(label, private, scratch, *, destructive_denial=False, broker_pid=None):
    result = {"context": label, "source_opens_winerror": {}}
    source = private / "synthetic-source"
    handle0 = None
    result["source_links_before"] = source.stat().st_nlink if label == "unrestricted" else None
    for name, desired in (("zero", 0), ("attributes", 0x80), ("read", 0x80000000), ("write", 0x40000000), ("delete", 0x10000), ("write_dac", 0x40000), ("write_owner", 0x80000)):
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
    if destructive_denial:
        child = K.CreateFileW(str(private / (label + "-forbidden-create")), 0x40000000, 0, None, 1, 0x00200000, None)
        result["private_create_winerror"] = C.get_last_error() if child == BAD else 0
        if child != BAD:
            checked(K.CloseHandle(child))
        result["private_delete_winerror"] = 0 if K.DeleteFileW(str(private / "delete-victim")) else C.get_last_error()
        result["private_rename_winerror"] = 0 if K.MoveFileExW(str(private / "rename-victim"), str(scratch / (label + "-renamed")), 0) else C.get_last_error()
        result["private_directory_rename_winerror"] = 0 if K.MoveFileExW(str(private), str(scratch / (label + "-moved-private")), 0) else C.get_last_error()
    if broker_pid:
        result["broker_process_open_winerror"] = {}
        for name, rights in (("duplicate_handle", 0x40), ("vm_write_operation", 0x28), ("create_thread", 2), ("query_limited", 0x1000)):
            handle = K.OpenProcess(rights, False, broker_pid)
            result["broker_process_open_winerror"][name] = 0 if handle else C.get_last_error()
            if handle:
                checked(K.CloseHandle(handle))
    return result

def child_main():
    base = Path(sys.argv[2]).resolve()
    base.relative_to(Path(tempfile.gettempdir()).resolve())
    assert base.name.startswith("gt02-s30-restricted-acl-")
    private, scratch = base / "private", base / "scratch"
    own = W.HANDLE()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(own)))
    try:
        details = token_details(own)
        assert details["token_type"] == 1 and len(details["restricted_sids"]) == 1
        # Revert removes thread impersonation, never this restricted primary token.
        checked(A.RevertToSelf())
        case = exercise("primary_write_restrict", private, scratch, destructive_denial=True, broker_pid=int(sys.argv[3]))
        result = {"marker": "GT02_S30_RESTRICTED_CHILD_COMPLETE", "pid": os.getpid(), "token": details, "after_revert_to_self": case}
        (scratch / "child-result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    finally:
        checked(K.CloseHandle(own))
    return 37

def main():
    assert os.name == "nt"
    out = {"run_id": "GT02-S30-RESTRICTED-ACL-05", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "os": platform.platform(), "python": platform.python_version(),
           "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "scope": "synthetic TEMP; restricted impersonation and primary process; not full sandbox acceptance", "cases": []}
    own = W.HANDLE()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 0xF01FF, C.byref(own)))
    sid = C.c_void_p()
    restricted_handles = []
    private_lock = None
    base = None
    try:
        user_sid = token_string(own)
        synthetic = "S-1-5-21-" + "-".join(str(int.from_bytes(uuid.uuid4().bytes[:4], "little")) for _ in range(3)) + "-11929"
        checked(A.ConvertStringSidToSidW(synthetic, C.byref(sid)))
        restriction = SIDATTR(sid, 0)
        with tempfile.TemporaryDirectory(prefix="gt02-s30-restricted-acl-") as tmp, ExitStack() as stack:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s30-restricted-acl-")
            private, scratch = base / "private", base / "scratch"
            # Protected DACLs at directory creation; inherited by synthetic children.
            # OWNER RIGHTS RC removes the implicit owner WRITE_DAC shortcut.
            private_sddl = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user_sid + ")"
            scratch_sddl = private_sddl + "(A;OICI;FA;;;" + synthetic + ")"
            make_directory(private, private_sddl)
            make_directory(scratch, scratch_sddl)
            # A protected object can still be removed through parent DELETE_CHILD.
            # Retain real directory data access, without delete sharing.
            private_lock = K.CreateFileW(str(private), 0x81, 1, None, 3, 0x02200000, None)
            if private_lock == BAD:
                raise C.WinError(C.get_last_error())
            stack.callback(K.CloseHandle, private_lock)
            source = private / "synthetic-source"
            source.write_bytes(b"synthetic-no-outside-data")
            (private / "delete-victim").write_bytes(b"delete-denial-canary")
            (private / "rename-victim").write_bytes(b"rename-denial-canary")
            out["effective_sddl"] = {"private": security_readback(private, True), "scratch": security_readback(scratch, True), "source": security_readback(source)}
            out["synthetic_restricting_sid"] = synthetic
            out["broker_token"] = token_details(own)
            out["cases"].append(exercise("unrestricted", private, scratch))
            for label, flags in (("full_restrict", 1), ("write_restrict", 9)):
                token = W.HANDLE()
                checked(A.CreateRestrictedToken(own, flags, 0, None, 0, None, 1, C.byref(restriction), C.byref(token)))
                restricted_handles.append(token)
                checked(A.ImpersonateLoggedOnUser(token))
                try:
                    case = exercise(label, private, scratch, destructive_denial=True, broker_pid=os.getpid())
                finally:
                    checked(A.RevertToSelf())
                out["cases"].append(case)
            # A retained write handle stays a capability after impersonation.
            preexisting = private / "preexisting-handle-canary"
            preexisting.write_bytes(b"before")
            handle, error = open_result(preexisting, 0x40000000)
            assert handle is not None and error == 0
            try:
                checked(A.ImpersonateLoggedOnUser(restricted_handles[0]))
                try:
                    count = W.DWORD()
                    success = K.WriteFile(handle, C.create_string_buffer(b"AFTER!"), 6, C.byref(count), None)
                    out["preexisting_handle_under_full_restriction"] = {"success": bool(success), "bytes_written": int(count.value), "winerror": 0 if success else C.get_last_error()}
                finally:
                    checked(A.RevertToSelf())
            finally:
                checked(K.CloseHandle(handle))
            out["preexisting_handle_effect_readback"] = preexisting.read_bytes().decode("ascii")
            from win_process import launch_restricted
            out["primary_process"] = launch_restricted(restricted_handles[1], base, Path(__file__).resolve(), os.getpid())
            child_result_path = scratch / "child-result.json"
            out["primary_process"]["child_result"] = json.loads(child_result_path.read_text(encoding="utf-8")) if child_result_path.exists() else "MISSING"
            out["directory_parent_delete_child_controls"] = []
            for index, token in enumerate(restricted_handles):
                for held in (False, True):
                    victim = base / ("root-victim-%d-%s" % (index, held))
                    destination = scratch / victim.name
                    make_directory(victim, private_sddl)
                    lock = K.CreateFileW(str(victim), 0x81, 1, None, 3, 0x02200000, None) if held else None
                    if lock == BAD:
                        raise C.WinError(C.get_last_error())
                    try:
                        checked(A.ImpersonateLoggedOnUser(token))
                        try:
                            ok = K.MoveFileExW(str(victim), str(destination), 0)
                            error = 0 if ok else C.get_last_error()
                        finally:
                            checked(A.RevertToSelf())
                        out["directory_parent_delete_child_controls"].append({"restriction": "full" if index == 0 else "write_only", "held_list_directory": held,
                                                                                "rename_winerror": error, "original_exists": victim.exists(), "destination_exists": destination.exists()})
                    finally:
                        if lock:
                            checked(K.CloseHandle(lock))
            out["private_payload_unchanged"] = source.read_bytes() == b"synthetic-no-outside-data"
            out["final_source_link_count"] = source.stat().st_nlink
            out["write_restricted_delete_effect_readback"] = not (private / "delete-victim").exists()
            out["write_restricted_rename_effect_readback"] = not (private / "rename-victim").exists() and (scratch / "write_restrict-renamed").read_bytes() == b"rename-denial-canary"
            full_case, write_case = out["cases"][1:]
            assert all(value == 5 for value in full_case["source_opens_winerror"].values())
            assert full_case["scratch_create_winerror"] == 0 and full_case["win32_hardlink_winerror"] == 5
            assert write_case["source_opens_winerror"]["write"] == 5 and write_case["source_opens_winerror"]["delete"] == 0
            assert out["write_restricted_delete_effect_readback"] and out["write_restricted_rename_effect_readback"]
            out["marker"] = "GT02_S30_RESTRICTED_ACL_OBSERVATIONS_COMPLETE"
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
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        sys.exit(child_main())
    main()
