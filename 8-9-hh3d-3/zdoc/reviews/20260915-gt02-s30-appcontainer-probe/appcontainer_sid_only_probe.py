"""Report-only AppContainer launch with a derived SID and no profile API.

Launches only cmd.exe with fixed diagnostic commands; no Godot/Blender,
network exception, account, elevation or existing ACL edit. Only the unique
SID namespace is checked read-only before/after; no profile lifecycle is used.
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
import sys
import tempfile
import uuid
import winreg

from restricted_acl_probe import A, K, SA, checked, make_directory, signature, token_string

U = C.WinDLL("userenv", use_last_error=True)
O = C.WinDLL("ole32", use_last_error=True)
class CAPS(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("capabilities", C.c_void_p), ("count", W.DWORD), ("reserved", W.DWORD)]
class SI(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
                ("x", W.DWORD), ("y", W.DWORD), ("width", W.DWORD), ("height", W.DWORD),
                ("chars_x", W.DWORD), ("chars_y", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD), ("reserved2", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]
class SIEX(C.Structure):
    _fields_ = [("si", SI), ("attributes", C.c_void_p)]
class PI(C.Structure):
    _fields_ = [("process", W.HANDLE), ("thread", W.HANDLE), ("pid", W.DWORD), ("tid", W.DWORD)]
class JLIMIT(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong), ("flags", W.DWORD),
                ("minimum", C.c_size_t), ("maximum", C.c_size_t), ("active_processes", W.DWORD),
                ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]
class IO(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
class JEXT(C.Structure):
    _fields_ = [("basic", JLIMIT), ("io", IO), ("process_memory", C.c_size_t),
                ("job_memory", C.c_size_t), ("peak_process", C.c_size_t), ("peak_job", C.c_size_t)]

signature(U, "DeriveAppContainerSidFromAppContainerName", [W.LPCWSTR, C.POINTER(C.c_void_p)], C.c_long)
signature(U, "GetAppContainerFolderPath", [W.LPCWSTR, C.POINTER(W.LPWSTR)], C.c_long)
signature(O, "CoTaskMemFree", [C.c_void_p], None)
signature(A, "FreeSid", [C.c_void_p], C.c_void_p)
signature(K, "InitializeProcThreadAttributeList", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL)
signature(K, "UpdateProcThreadAttribute", [C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL)
signature(K, "DeleteProcThreadAttributeList", [C.c_void_p], None)
signature(K, "CreateProcessW", [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(SIEX), C.POINTER(PI)], W.BOOL)
signature(K, "CreateJobObjectW", [C.c_void_p, W.LPCWSTR], W.HANDLE)
signature(K, "SetInformationJobObject", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "AssignProcessToJobObject", [W.HANDLE, W.HANDLE], W.BOOL)
signature(K, "TerminateJobObject", [W.HANDLE, W.UINT], W.BOOL)
signature(K, "ResumeThread", [W.HANDLE], W.DWORD)
signature(K, "WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD)
signature(K, "GetExitCodeProcess", [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
signature(K, "TerminateProcess", [W.HANDLE, W.UINT], W.BOOL)

def get_info(token, kind):
    count = W.DWORD()
    A.GetTokenInformation(token, kind, None, 0, C.byref(count))
    buf = C.create_string_buffer(count.value)
    checked(A.GetTokenInformation(token, kind, buf, count, C.byref(count)))
    return buf

def sid_text(pointer):
    result = W.LPWSTR()
    checked(A.ConvertSidToStringSidW(pointer, C.byref(result)))
    try:
        return result.value
    finally:
        K.LocalFree(result)

def main():
    out = {"run_id": "GT02-S30-APPCONTAINER-SID-ONLY-02", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
           "os": platform.platform(), "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "scope": "TEMP synthetic cmd.exe diagnostic; SID-only, no profile lifecycle; not adapter acceptance"}
    own, childtoken = W.HANDLE(), W.HANDLE()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(own)))
    package = C.c_void_p()
    pi, job, attrs = PI(), None, None
    base, profile_created, profile_path, mapping_path, temp_context = None, False, None, None, None
    error = None
    def mapping_exists():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, mapping_path, 0, winreg.KEY_READ):
                return True
        except FileNotFoundError:
            return False
    try:
        user = token_string(own)
        moniker = "hh-gt02-s30-sidonly-" + uuid.uuid4().hex
        out["last_phase"] = "derive_sid"
        hr = U.DeriveAppContainerSidFromAppContainerName(moniker, C.byref(package))
        if hr != 0:
            raise RuntimeError("Derive SID HRESULT 0x%08X" % (hr & 0xffffffff))
        package_string = sid_text(package)
        profile_path = (Path(os.environ["LOCALAPPDATA"]) / "Packages" / moniker).resolve()
        mapping_path = "Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\" + package_string
        out["profile_name"] = moniker
        out["profile_folder_absent_before"] = not profile_path.exists()
        out["profile_mapping_absent_before"] = not mapping_exists()
        assert out["profile_folder_absent_before"] and out["profile_mapping_absent_before"]
        out["profile_api_calls"] = 0
        temp_context = tempfile.TemporaryDirectory(prefix="gt02-s30-appcontainer-")
        with temp_context as tmp:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s30-appcontainer-")
            private, scratch = base / "private", base / "scratch"
            common = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user + ")"
            out["last_phase"] = "create_private"
            make_directory(private, common)
            out["last_phase"] = "create_scratch"
            make_directory(scratch, common + "(A;OICI;0x1301bf;;;" + package_string + ")S:(ML;OICI;NW;;;LW)")
            source = private / "synthetic-source"
            source.write_bytes(b"SYNTHETIC-PRIVATE-CONTENT")
            resultfile = scratch / "child-result.txt"
            alias = scratch / "forbidden-link"
            positive = scratch / "positive.txt"
            size = C.c_size_t()
            K.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
            attrs = C.create_string_buffer(size.value)
            out["last_phase"] = "initialize_attributes"
            checked(K.InitializeProcThreadAttributeList(attrs, 1, 0, C.byref(size)))
            caps = CAPS(package, None, 0, 0)
            out["last_phase"] = "set_capabilities"
            checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
            si = SIEX()
            si.si.cb, si.attributes = C.sizeof(si), C.addressof(attrs)
            exe = str(Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe")
            # Every expansion below is a fresh Path chosen by this probe. /d
            # suppresses AutoRun. No caller text, secrets or arbitrary commands.
            command = '"' + exe + '" /d /q /c "(echo CHILD_STARTED & echo OK>' + '"' + str(positive) + '" & type "' + str(source) + '" & echo FORBIDDEN>>"' + str(source) + '" & mklink /h "' + str(alias) + '" "' + str(source) + '") >"' + str(resultfile) + '" 2>&1 & exit /b 37"'
            environment = C.create_unicode_buffer("\0".join(["SystemRoot=" + os.environ["SystemRoot"], "TEMP=" + str(scratch), "TMP=" + str(scratch)]) + "\0\0")
            out["last_phase"] = "create_process"
            checked(K.CreateProcessW(exe, C.create_unicode_buffer(command), None, None, False, 0x08080404, environment, str(scratch), C.byref(si), C.byref(pi)))
            out["last_phase"] = "inspect_child_token"
            checked(A.OpenProcessToken(pi.process, 8, C.byref(childtoken)))
            out["token_is_appcontainer"] = int(C.cast(get_info(childtoken, 29), C.POINTER(W.DWORD)).contents.value)
            # Keep the returned buffer alive while converting its embedded SID.
            sidbuf = get_info(childtoken, 31)
            out["token_package_sid_matches"] = sid_text(C.cast(sidbuf, C.POINTER(C.c_void_p)).contents.value) == package_string
            ilbuf = get_info(childtoken, 25)
            out["integrity_sid"] = sid_text(C.cast(ilbuf, C.POINTER(C.c_void_p)).contents.value)
            out["capability_count"] = int(C.cast(get_info(childtoken, 30), C.POINTER(W.DWORD)).contents.value)
            assert out["token_is_appcontainer"] == 1 and out["token_package_sid_matches"]
            assert out["integrity_sid"] == "S-1-16-4096" and out["capability_count"] == 0
            job = checked(K.CreateJobObjectW(None, None))
            limits = JEXT()
            limits.basic.flags, limits.basic.active_processes = 0x2000 | 0x8 | 0x100, 1
            limits.process_memory = 128 * 1024 * 1024
            checked(K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
            checked(K.AssignProcessToJobObject(job, pi.process))
            if K.ResumeThread(pi.thread) == 0xffffffff:
                raise C.WinError(C.get_last_error())
            wait = K.WaitForSingleObject(pi.process, 5000)
            out["wait_result"] = int(wait)
            if wait != 0:
                checked(K.TerminateJobObject(job, 126))
                checked(K.WaitForSingleObject(pi.process, 5000) == 0)
            exitcode = W.DWORD()
            checked(K.GetExitCodeProcess(pi.process, C.byref(exitcode)))
            out["host_captured_exit"] = int(exitcode.value)
            out["child_log"] = resultfile.read_text(errors="replace") if resultfile.exists() else "MISSING"
            out["scratch_positive_bytes"] = positive.read_text(errors="replace") if positive.exists() else "MISSING"
            out["forbidden_link_exists"] = alias.exists()
            out["private_payload_unchanged"] = source.read_bytes() == b"SYNTHETIC-PRIVATE-CONTENT"
            out["private_link_count"] = source.stat().st_nlink
            checked(K.CloseHandle(childtoken)); childtoken = W.HANDLE()
            checked(K.CloseHandle(pi.thread)); pi.thread = None
            checked(K.CloseHandle(pi.process)); pi.process = None
            checked(K.CloseHandle(job)); job = None
    except Exception as exc:
        error = {"type": type(exc).__name__, "message": str(exc), "winerror": getattr(exc, "winerror", None)}
    finally:
        if pi.process:
            K.TerminateProcess(pi.process, 127)
            K.WaitForSingleObject(pi.process, 5000)
        for handle in (childtoken, pi.thread, pi.process, job, own):
            if handle:
                K.CloseHandle(handle)
        if attrs is not None:
            K.DeleteProcThreadAttributeList(attrs)
        if package.value:
            A.FreeSid(package)
        if temp_context is not None:
            temp_context.cleanup()
        if profile_path is not None and mapping_path is not None:
            out["profile_folder_absent_after"] = not profile_path.exists()
            out["profile_mapping_absent_after"] = not mapping_exists()
            if profile_path.exists() or mapping_exists():
                error = {"type": "UnexpectedProfileState", "message": "SID-only activation changed profile state; preserve it for diagnosis"}
    out["owned_temp_removed"] = base is not None and not base.exists()
    out["diagnostic_complete"] = bool(
        out.get("host_captured_exit") == 37 and "CHILD_STARTED" in out.get("child_log", "")
        and out.get("scratch_positive_bytes", "").strip() == "OK"
        and out.get("private_payload_unchanged") is True
        and out.get("forbidden_link_exists") is False
        and out.get("private_link_count") == 1
        and out.get("profile_folder_absent_after") and out.get("profile_mapping_absent_after")
        and out.get("owned_temp_removed"))
    if error:
        out["error"] = error
    print(json.dumps(out, indent=2))
    return 1 if error else 0

if __name__ == "__main__":
    sys.exit(main())
