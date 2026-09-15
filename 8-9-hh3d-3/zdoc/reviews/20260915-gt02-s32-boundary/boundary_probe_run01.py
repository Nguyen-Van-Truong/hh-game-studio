"""Finite S32 native boundary matrix; no production writer.

Lifecycle/launch sequence adapted from pinned S31 appcontainer_probe.py
681a051f57d436c68eb994c0d20bac6b9f8a486dc95c56e654de709a928a4755.
windows_api.py is an exact copy of pinned S31 helper 1afd34eb...bd3a50c4.
"""
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import winreg
from windows_api import *

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
RUN_ID = "GT02-S32-BOUNDARY-01"
MODES = ("control", "inherit_control", "appcontainer", "appcontainer_restricted")
SENTINEL = b"S32_SENTINEL_PAYLOAD!"
PRIVATE_ERRORS = ("private_open_zero_error", "private_open_write_dac_error", "private_open_write_owner_error",
                  "directory_delete_child_open_error", "directory_add_file_open_error", "directory_add_subdirectory_open_error",
                  "private_create_directory_error", "private_delete_file_error")
BROKER_ERRORS = ("broker_open_duplicate_handle_error", "broker_open_vm_write_error", "broker_open_create_thread_error", "broker_open_create_process_error")

class FILEID(C.Structure):
    _fields_ = [("volume", C.c_ulonglong), ("id", C.c_ubyte * 16)]
class PIDLIST(C.Structure):
    _fields_ = [("assigned", W.DWORD), ("count", W.DWORD), ("pids", C.c_size_t * 16)]
signature(K, "GetHandleInformation", [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
signature(K, "GetFileInformationByHandleEx", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def mapping_exists(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False

def compile_native(base, out):
    build = base / "build"
    build.mkdir()
    source = build / "boundary_child.c"
    source.write_bytes((BASE / "boundary_child.c").read_bytes())
    programs = Path(os.environ["ProgramFiles(x86)"])
    msvc = programs / "Microsoft Visual Studio/2022/BuildTools/VC/Tools/MSVC/14.44.35207"
    sdk = programs / "Windows Kits/10"
    tools = msvc / "bin/Hostx64/x64"
    includes = [msvc / "include"] + [sdk / "Include/10.0.26100.0" / name for name in ("shared", "um", "ucrt")]
    libraries = [msvc / "lib/x64", sdk / "Lib/10.0.26100.0/um/x64", sdk / "Lib/10.0.26100.0/ucrt/x64"]
    environment = {"SystemRoot": os.environ["SystemRoot"], "TEMP": str(build), "TMP": str(build),
                   "PATH": str(tools) + os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32")}
    obj, executable = build / "boundary_child.obj", build / "boundary_child.exe"
    compile_args = [str(tools / "cl.exe"), "/nologo", "/W4", "/WX", "/O1", "/MT", "/DUNICODE", "/D_UNICODE", "/D_WIN32_WINNT=0x0A00",
                    "/c", str(source), "/Fo" + str(obj)] + ["/I" + str(path) for path in includes]
    link_args = [str(tools / "link.exe"), "/NOLOGO", "/BREPRO", "/SUBSYSTEM:CONSOLE", "/OUT:" + str(executable), str(obj), "kernel32.lib"] + ["/LIBPATH:" + str(path) for path in libraries]
    out["compiler"] = {"cl_sha256": sha((tools / "cl.exe").read_bytes()), "link_sha256": sha((tools / "link.exe").read_bytes()),
                       "msvc_version": "14.44.35207", "sdk_version": "10.0.26100.0", "source_sha256": sha(source.read_bytes())}
    for stage, command in (("compile", compile_args), ("link", link_args)):
        result = subprocess.run(command, cwd=build, env=environment, capture_output=True, timeout=25)
        out["compiler"][stage] = {"host_exit": result.returncode, "stdout": result.stdout.decode(errors="replace"), "stderr": result.stderr.decode(errors="replace"), "timeout_seconds": 25}
        assert result.returncode == 0, "Native " + stage + " failed"
    return executable

def launch(executable, base, mode, sentinel, identity, package=None):
    assert mode in MODES
    inherited = mode == "inherit_control"
    restricted = mode == "appcontainer_restricted"
    attrs, caps, handle_list, policy, job, assigned = None, None, None, None, None, False
    pi, child_token, si = PI(), W.HANDLE(), SIEX()
    out = {"mode": mode, "inherit_handles": inherited, "inherited_handle_allowlist_count": 1 if inherited else 0,
           "creation_suspended": True, "timeout_ms": 10000, "active_process_limit": 3,
           "memory_limit_bytes": 128 * 1024 * 1024, "kill_on_job_close": True,
           "child_process_policy_requested": restricted}
    try:
        attribute_count = int(package is not None) + int(inherited) + int(restricted)
        if attribute_count:
            size = C.c_size_t()
            K.InitializeProcThreadAttributeList(None, attribute_count, 0, C.byref(size))
            attrs = C.create_string_buffer(size.value)
            checked(K.InitializeProcThreadAttributeList(attrs, attribute_count, 0, C.byref(size)))
            if package is not None:
                caps = CAPS(package, None, 0, 0)
                checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
            if inherited:
                handle_list = (W.HANDLE * 1)(sentinel)
                checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20002, handle_list, C.sizeof(handle_list), None, None))
            if restricted:
                policy = W.DWORD(1)
                checked(K.UpdateProcThreadAttribute(attrs, 0, 0x2000e, C.byref(policy), C.sizeof(policy), None, None))
            si.attributes = C.addressof(attrs)
        si.si.cb = C.sizeof(SIEX) if attribute_count else C.sizeof(SI)
        scratch = base / "scratch"
        values = {key: os.environ[key] for key in ("SystemRoot", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "SystemDrive")}
        values.update({"WINDIR": os.environ["SystemRoot"], "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
                       "TEMP": str(scratch), "TMP": str(scratch), "S32_FIXTURE": str(base), "S32_MODE": mode,
                       "S32_BROKER_PID": str(os.getpid()), "S32_SENTINEL_HANDLE": str(sentinel),
                       "S32_SENTINEL_ID": bytes(identity.id).hex(), "S32_SENTINEL_VOLUME": str(identity.volume)})
        block = C.create_unicode_buffer("\0".join(key + "=" + value for key, value in sorted(values.items(), key=lambda row: row[0].lower())) + "\0\0")
        flags = 0x08000404 | (0x80000 if attribute_count else 0)
        checked(K.CreateProcessW(str(executable), C.create_unicode_buffer('"' + str(executable) + '"'), None, None, inherited,
                                 flags, block, str(scratch), C.byref(si), C.byref(pi)))
        out["pid"] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process, 8, C.byref(child_token)))
        out["token_is_appcontainer"] = token_number(child_token, 29)
        out["integrity_sid"] = token_sid(child_token, 25)
        out["capability_count"] = token_number(child_token, 30)
        if package is not None:
            out["token_package_sid_matches"] = token_sid(child_token, 31) == sid_text(package)
            assert out["token_is_appcontainer"] == 1 and out["token_package_sid_matches"]
            assert out["integrity_sid"] == "S-1-16-4096" and out["capability_count"] == 0
        job = checked(K.CreateJobObjectW(None, None))
        limits = JEXT()
        limits.basic.flags, limits.basic.active_processes = 0x2000 | 0x8 | 0x100, out["active_process_limit"]
        limits.process_memory = out["memory_limit_bytes"]
        checked(K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job, pi.process))
        assigned = True
        if K.ResumeThread(pi.thread) == 0xffffffff:
            raise C.WinError(C.get_last_error())
        out["wait_result"] = int(K.WaitForSingleObject(pi.process, out["timeout_ms"]))
        if out["wait_result"] != 0:
            checked(K.TerminateJobObject(job, 126))
            checked(K.WaitForSingleObject(pi.process, 5000) == 0)
        code = W.DWORD()
        checked(K.GetExitCodeProcess(pi.process, C.byref(code)))
        out["host_captured_exit"] = int(code.value)
        account = JACCOUNT()
        out["job_drain_samples"] = []
        for _ in range(101):
            checked(K.QueryInformationJobObject(job, 1, C.byref(account), C.sizeof(account), None))
            out["job_drain_samples"].append(int(account.active_processes))
            if account.active_processes == 0:
                break
            time.sleep(0.02)
        out["job_active_processes_after_wait"] = int(account.active_processes)
        out["job_total_processes"] = int(account.total_processes)
        pids = PIDLIST()
        checked(K.QueryInformationJobObject(job, 3, C.byref(pids), C.sizeof(pids), None))
        out["job_process_ids_at_final"] = list(pids.pids)[:pids.count]
    except Exception as exc:
        out["error"] = {"type": type(exc).__name__, "message": str(exc), "winerror": getattr(exc, "winerror", None)}
    finally:
        if pi.process and K.WaitForSingleObject(pi.process, 0) != 0:
            if assigned:
                K.TerminateJobObject(job, 127)
            else:
                K.TerminateProcess(pi.process, 127)
            K.WaitForSingleObject(pi.process, 5000)
        for handle in (child_token, pi.thread, pi.process, job):
            if handle:
                K.CloseHandle(handle)
        if attrs is not None:
            K.DeleteProcThreadAttributeList(attrs)
    native = base / "scratch" / (mode + "-native.json")
    out["native"] = json.loads(native.read_bytes()) if native.exists() else None
    private = base / (mode + "-private")
    marker = base / "scratch" / (mode + "-child-marker.txt")
    out["host_readback"] = {"created_directory_exists": (private / "created-directory").exists(),
                            "delete_canary_exists": (private / "delete.bin").exists(),
                            "source_canary_unchanged": (private / "source.bin").read_bytes() == b"S32_PRIVATE_SOURCE",
                            "child_marker_present": marker.exists(),
                            "child_marker_matches": marker.exists() and marker.read_bytes() == b"S32_FIXED_CHILD_COMPLETE"}
    return out

def validate(result, mode):
    assert result.get("host_captured_exit") == 47 and result.get("wait_result") == 0, "Native root did not complete: " + mode
    assert result["job_active_processes_after_wait"] == 0 and result["job_process_ids_at_final"] == []
    native, rb = result["native"], result["host_readback"]
    assert native and native["complete"] == "S32_NATIVE_COMPLETE"
    expected_error = 5 if mode.startswith("appcontainer") else 0
    assert all(native[name] == expected_error for name in PRIVATE_ERRORS + BROKER_ERRORS), "Access-control matrix mismatch: " + mode
    assert native["sentinel_identity_matches"] == int(mode == "inherit_control"), "Sentinel identity mismatch"
    if mode == "inherit_control":
        assert native["sentinel_payload_matches"] == 1
    assert rb["created_directory_exists"] == (not mode.startswith("appcontainer"))
    assert rb["delete_canary_exists"] == mode.startswith("appcontainer") and rb["source_canary_unchanged"]
    assert native["child_policy_query_error"] == 0
    if mode == "appcontainer_restricted":
        assert native["no_child_process_creation"] == 1 and native["child_create_success"] == 0 and not rb["child_marker_present"]
    else:
        assert native["no_child_process_creation"] == 0 and native["child_create_success"] == 1
        assert native["child_host_captured_exit"] == 43 and native["child_wait_result"] == 0 and rb["child_marker_matches"]

def main():
    run_uuid = uuid.uuid4().hex
    moniker = "hh-gt02-s32-" + run_uuid
    out = {"run_id": RUN_ID, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "os": platform.platform(), "python": platform.python_version(),
           "probe_sha256": sha(Path(__file__).read_bytes()), "helper_sha256": sha((BASE / "windows_api.py").read_bytes()),
           "native_source_sha256": sha((BASE / "boundary_child.c").read_bytes()), "profile_name": moniker,
           "scope": "Fixed native diagnostics on owned TEMP/profile only", "safe_write": "UNSUPPORTED_SAFE_OPEN_WINDOWS"}
    own, package, created_sid = W.HANDLE(), C.c_void_p(), C.c_void_p()
    created, base, profile_path, mapping, user, native_bytes = False, None, None, None, None, None
    try:
        checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(own)))
        user = token_sid(own, 1)
        hr = U.DeriveAppContainerSidFromAppContainerName(moniker, C.byref(package))
        assert hr == 0
        package_string = sid_text(package)
        out["package_sid"] = package_string
        profile_path = (Path(os.environ["LOCALAPPDATA"]) / "Packages" / moniker).resolve()
        mapping = "Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\" + package_string
        out["profile_path"] = str(profile_path)
        out["profile_folder_absent_before"] = not profile_path.exists()
        out["profile_mapping_absent_before"] = not mapping_exists(mapping)
        assert out["profile_folder_absent_before"] and out["profile_mapping_absent_before"]
        with tempfile.TemporaryDirectory(prefix="gt02-s32-boundary-") as tmp, ExitStack() as stack:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s32-boundary-")
            out["fixture_root"] = str(base)
            built = compile_native(base, out)
            native_bytes = built.read_bytes()
            out["native_executable_sha256"] = sha(native_bytes)
            common = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user + ")"
            scratch = base / "scratch"
            make_directory(scratch, common + "(A;OICI;0x1301bf;;;" + package_string + ")S:(ML;OICI;NW;;;LW)")
            executable = scratch / "boundary_child.exe"
            executable.write_bytes(native_bytes)
            for mode in MODES:
                private = base / (mode + "-private")
                make_directory(private, common)
                (private / "source.bin").write_bytes(b"S32_PRIVATE_SOURCE")
                (private / "delete.bin").write_bytes(b"S32_DELETE_CANARY")
            broker_private = base / "broker-private"
            make_directory(broker_private, common)
            sentinel_path = broker_private / "sentinel.bin"
            sentinel_path.write_bytes(SENTINEL)
            sentinel = K.CreateFileW(str(sentinel_path), 0x80000000, 1, C.byref(SA(C.sizeof(SA), None, True)), 3, 0x00200000, None)
            if sentinel == BAD:
                raise C.WinError(C.get_last_error())
            stack.callback(K.CloseHandle, sentinel)
            flags, identity = W.DWORD(), FILEID()
            checked(K.GetHandleInformation(sentinel, C.byref(flags)))
            checked(K.GetFileInformationByHandleEx(sentinel, 18, C.byref(identity), C.sizeof(identity)))
            out["broker_sentinel_handle_inheritable"] = bool(flags.value & 1)
            assert out["broker_sentinel_handle_inheritable"]
            out["effective_sddl"] = {"scratch": security_readback(scratch, True), "native_executable": security_readback(executable),
                                     "private": security_readback(base / "appcontainer-private", True), "sentinel": security_readback(sentinel_path)}
            out["cases"] = {}
            for mode in MODES[:2]:
                out["last_phase"] = mode
                out["cases"][mode] = launch(executable, base, mode, sentinel, identity)
                validate(out["cases"][mode], mode)
            out["last_phase"] = "create_profile"
            assert not profile_path.exists() and not mapping_exists(mapping)
            hr = U.CreateAppContainerProfile(moniker, moniker, "Owned S32 finite native diagnostic", None, 0, C.byref(created_sid))
            out["create_profile_hresult"] = "0x%08X" % (hr & 0xffffffff)
            assert hr == 0
            created = True
            assert sid_text(created_sid) == package_string
            A.FreeSid(created_sid)
            created_sid = C.c_void_p()
            folder = W.LPWSTR()
            try:
                hr = U.GetAppContainerFolderPath(package_string, C.byref(folder))
                out["profile_api_path_matches"] = hr == 0 and Path(folder.value).resolve() == profile_path / "AC"
                assert out["profile_api_path_matches"]
            finally:
                if folder:
                    O.CoTaskMemFree(folder)
            out["profile_folder_exists_after_create"] = profile_path.exists()
            out["profile_mapping_exists_after_create"] = mapping_exists(mapping)
            assert out["profile_folder_exists_after_create"] and out["profile_mapping_exists_after_create"]
            for mode in MODES[2:]:
                out["last_phase"] = mode
                out["cases"][mode] = launch(executable, base, mode, sentinel, identity, package)
                validate(out["cases"][mode], mode)
            out["sentinel_bytes_unchanged"] = sentinel_path.read_bytes() == SENTINEL
            assert out["sentinel_bytes_unchanged"]
            out["marker"] = "GT02_S32_BOUNDARY_DIAGNOSTIC_COMPLETE"
    except Exception as exc:
        out["error"] = {"type": type(exc).__name__, "message": str(exc), "winerror": getattr(exc, "winerror", None)}
    finally:
        for pointer in (package, created_sid):
            if pointer.value:
                A.FreeSid(pointer)
        if own:
            K.CloseHandle(own)
        if created:
            hr = U.DeleteAppContainerProfile(moniker)
            out["delete_profile_hresult"] = "0x%08X" % (hr & 0xffffffff)
        if profile_path is not None and mapping is not None:
            out["profile_folder_absent_after"] = not profile_path.exists()
            out["profile_mapping_absent_after"] = not mapping_exists(mapping)
        out["owned_temp_removed"] = base is not None and not base.exists()
    out["owned_profile_created_this_run"] = created
    out["diagnostic_complete"] = bool(out.get("marker") and not out.get("error") and out.get("owned_temp_removed") and
                                      out.get("delete_profile_hresult") == "0x00000000" and out.get("profile_folder_absent_after") and out.get("profile_mapping_absent_after"))
    raw_root = PRODUCT / "studio/.local/review-raw/S32"
    assert subprocess.run(["git", "check-ignore", "--quiet", str(raw_root / "probe.json")], cwd=PRODUCT, timeout=10).returncode == 0
    raw_root.mkdir(parents=True, exist_ok=True)
    prefix = RUN_ID + "-" + run_uuid
    if native_bytes:
        raw_exe = raw_root / (prefix + ".exe")
        with raw_exe.open("xb") as stream:
            stream.write(native_bytes)
        out["native_executable_private_relative"] = raw_exe.relative_to(PRODUCT).as_posix()
    raw_path = raw_root / (prefix + ".json")
    raw = json.dumps(out, indent=2, ensure_ascii=True).encode()
    with raw_path.open("xb") as stream:
        stream.write(raw)
    replacements = [(str(base), "<OWNED_TEMP>") if base else ("", ""), (str(profile_path), "<OWNED_PROFILE_PATH>") if profile_path else ("", ""),
                    (user or "", "<BROKER_SID>"), (out.get("package_sid", ""), "<APPCONTAINER_SID>"), (moniker, "<OWNED_PROFILE_NAME>"),
                    (os.environ.get("USERPROFILE", ""), "<USER_PROFILE>"), (str(PRODUCT), "<PRODUCT_ROOT>"),
                    (os.environ["SystemRoot"], "<SYSTEM_ROOT>"), (os.environ["ProgramFiles(x86)"], "<PROGRAM_FILES_X86>")]
    def redact(value):
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, str):
            for old, new in replacements:
                if old:
                    value = value.replace(old, new)
            return re.sub(r"S-1-5-21-\d+-\d+-\d+-\d+", "<HOST_ACCOUNT_SID>", value)
        return value
    public = redact(out)
    public["private_raw_sha256"] = sha(raw)
    public["private_raw_relative_path"] = raw_path.relative_to(PRODUCT).as_posix()
    public["redaction"] = "Public machine paths/SIDs replaced; exact raw bytes and native binary kept ignored"
    print(json.dumps(public, indent=2, ensure_ascii=True))
    return 0 if out["diagnostic_complete"] else 1

if __name__ == "__main__":
    sys.exit(main())
