"""Owned-profile AppContainer experiment. No production mutation or capability.

Only fresh TEMP fixtures and one unique profile per run can be created. Profile
cleanup uses DeleteAppContainerProfile only. No account/elevation/service,
network exemption, desktop policy or existing ACL changes are made.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import uuid
import winreg

from windows_api import *

BASE = Path(__file__).resolve().parent
PRODUCT = BASE.parents[2]
RUN_ID = "GT02-S31-APPCONTAINER-01"
SCRIPT = r'''@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "CASE=%~1"
>"%CASE%-trace.txt" echo S31_CHILD_STARTED
>"%CASE%-positive.txt" echo S31_SCRATCH_OK
>>"%CASE%-trace.txt" echo scratch_error=!errorlevel!
type "..\%CASE%-private\read.bin" >"%CASE%-read.out" 2>"%CASE%-read.err"
>>"%CASE%-trace.txt" echo read_error=!errorlevel!
2>"%CASE%-write.err" echo S31_FORBIDDEN>>"..\%CASE%-private\write.bin"
>>"%CASE%-trace.txt" echo write_error=!errorlevel!
del /q "..\%CASE%-private\delete.bin" >"%CASE%-delete.out" 2>"%CASE%-delete.err"
>>"%CASE%-trace.txt" echo delete_error=!errorlevel!
ren "..\%CASE%-private\rename.bin" renamed.bin >"%CASE%-rename.out" 2>"%CASE%-rename.err"
>>"%CASE%-trace.txt" echo rename_error=!errorlevel!
mklink /h "%CASE%-hardlink" "..\%CASE%-private\link.bin" >"%CASE%-hardlink.out" 2>"%CASE%-hardlink.err"
>>"%CASE%-trace.txt" echo hardlink_error=!errorlevel!
>>"%CASE%-trace.txt" echo S31_CHILD_COMPLETE
exit /b 37
'''
CANARIES = {name: ("S31_SYNTHETIC_" + name.upper()).encode("ascii") for name in ("read", "write", "delete", "rename", "link")}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def registry_mapping_exists(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_READ):
            return True
    except FileNotFoundError:
        return False

def launch(exe, scratch, mode, package=None):
    assert mode in ("control", "appcontainer")
    attrs, caps, job, assigned = None, None, None, False
    pi, child_token, si = PI(), W.HANDLE(), SIEX()
    out = {"mode": mode, "application_name": str(exe), "cwd": str(scratch), "inherit_handles": False,
           "creation_suspended": True, "timeout_ms": 10000, "active_process_limit": 1,
           "memory_limit_bytes": 128 * 1024 * 1024, "kill_on_job_close": True}
    try:
        if package is not None:
            size = C.c_size_t()
            K.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
            attrs = C.create_string_buffer(size.value)
            checked(K.InitializeProcThreadAttributeList(attrs, 1, 0, C.byref(size)))
            caps = CAPS(package, None, 0, 0)
            checked(K.UpdateProcThreadAttribute(attrs, 0, 0x20009, C.byref(caps), C.sizeof(caps), None, None))
            si.attributes = C.addressof(attrs)
        si.si.cb = C.sizeof(SIEX) if package is not None else C.sizeof(SI)
        # Full unquoted application argument and mutable full command line.
        # A fixed basename in this exact cwd removes nested /c quote ambiguity.
        command = '"' + str(exe) + '" /d /q /e:on /v:on /c probe.cmd ' + mode
        out["command_line"] = command
        values = {"SystemRoot": os.environ["SystemRoot"], "WINDIR": os.environ["SystemRoot"],
                  "ComSpec": str(exe), "PATH": str(exe.parent), "TEMP": str(scratch), "TMP": str(scratch)}
        environment = C.create_unicode_buffer("\0".join(key + "=" + val for key, val in sorted(values.items(), key=lambda row: row[0].lower())) + "\0\0")
        flags = 0x08000404 | (0x80000 if package is not None else 0)
        checked(K.CreateProcessW(str(exe), C.create_unicode_buffer(command), None, None, False, flags,
                                 environment, str(scratch), C.byref(si), C.byref(pi)))
        out["pid"] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process, 8, C.byref(child_token)))
        out["token_is_appcontainer"] = token_number(child_token, 29)
        out["integrity_sid"] = token_sid(child_token, 25)
        out["capability_count"] = token_number(child_token, 30)
        if package is not None:
            out["token_package_sid"] = token_sid(child_token, 31)
            out["token_package_sid_matches"] = out["token_package_sid"] == sid_text(package)
            assert out["token_is_appcontainer"] == 1 and out["token_package_sid_matches"]
            assert out["integrity_sid"] == "S-1-16-4096" and out["capability_count"] == 0
        else:
            assert out["token_is_appcontainer"] == 0
        job = checked(K.CreateJobObjectW(None, None))
        limits = JEXT()
        limits.basic.flags, limits.basic.active_processes = 0x2000 | 0x8 | 0x100, 1
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
        exit_code = W.DWORD()
        checked(K.GetExitCodeProcess(pi.process, C.byref(exit_code)))
        out["host_captured_exit"] = int(exit_code.value)
        accounting = JACCOUNT()
        checked(K.QueryInformationJobObject(job, 1, C.byref(accounting), C.sizeof(accounting), None))
        out["job_active_processes_after_wait"] = int(accounting.active_processes)
        out["job_total_processes"] = int(accounting.total_processes)
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
    return out

def readback(base, scratch, mode):
    private = base / (mode + "-private")
    logs = {path.name: path.read_text(encoding="utf-8", errors="replace") for path in scratch.glob(mode + "-*") if path.is_file() and path.name != mode + "-hardlink"}
    contents = {name: (private / (name + ".bin")).read_bytes() if (private / (name + ".bin")).exists() else None for name in CANARIES}
    renamed = private / "renamed.bin"
    alias = scratch / (mode + "-hardlink")
    read_value = logs.get(mode + "-read.out", "").encode("utf-8")
    trace = logs.get(mode + "-trace.txt", "")
    result = {"logs": logs, "child_started": "S31_CHILD_STARTED" in trace, "child_completed": "S31_CHILD_COMPLETE" in trace,
              "scratch_positive": logs.get(mode + "-positive.txt", "").strip() == "S31_SCRATCH_OK",
              "private_read_observed": read_value == CANARIES["read"],
              "private_write_changed": contents["write"] != CANARIES["write"],
              "private_delete_effect": contents["delete"] is None,
              "private_rename_effect": contents["rename"] is None and renamed.exists() and renamed.read_bytes() == CANARIES["rename"],
              "private_hardlink_effect": alias.exists() and alias.read_bytes() == CANARIES["link"],
              "private_link_count": (private / "link.bin").stat().st_nlink,
              "private_contents_unchanged": all(contents[name] == payload for name, payload in CANARIES.items()) and not renamed.exists()}
    return result

def main():
    run_uuid = uuid.uuid4().hex
    moniker = "hh-gt02-s31-" + run_uuid
    package, created_sid, own = C.c_void_p(), C.c_void_p(), W.HANDLE()
    out = {"run_id": RUN_ID, "timestamp_utc": datetime.now(timezone.utc).isoformat(), "os": platform.platform(),
           "python": platform.python_version(), "pointer_bits": C.sizeof(C.c_void_p) * 8, "scope": "disposable profile and synthetic TEMP only",
           "probe_sha256": digest(Path(__file__).read_bytes()), "helper_sha256": digest((BASE / "windows_api.py").read_bytes()),
           "profile_name": moniker, "safe_write": "UNSUPPORTED_SAFE_OPEN_WINDOWS"}
    profile_created, base, profile_path, mapping, user = False, None, None, None, None
    try:
        checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(own)))
        user = token_sid(own, 1)
        hr = U.DeriveAppContainerSidFromAppContainerName(moniker, C.byref(package))
        if hr != 0:
            raise RuntimeError("Derive SID HRESULT 0x%08X" % (hr & 0xffffffff))
        package_string = sid_text(package)
        out["package_sid"] = package_string
        profile_path = (Path(os.environ["LOCALAPPDATA"]) / "Packages" / moniker).resolve()
        mapping = "Software\\Classes\\Local Settings\\Software\\Microsoft\\Windows\\CurrentVersion\\AppContainer\\Mappings\\" + package_string
        out["profile_path"] = str(profile_path)
        out["profile_folder_absent_before"] = not profile_path.exists()
        out["profile_mapping_absent_before"] = not registry_mapping_exists(mapping)
        assert out["profile_folder_absent_before"] and out["profile_mapping_absent_before"]
        exe = Path(os.environ["SystemRoot"]) / "System32" / "cmd.exe"
        out["cmd_executable_exists"] = exe.is_file()
        out["cmd_executable_sha256"] = digest(exe.read_bytes())
        with tempfile.TemporaryDirectory(prefix="gt02-s31-appcontainer-") as tmp:
            base = Path(tmp).resolve()
            base.relative_to(Path(tempfile.gettempdir()).resolve())
            assert base.name.startswith("gt02-s31-appcontainer-")
            out["fixture_root"] = str(base)
            common = "D:P(A;OICI;RC;;;OW)(A;OICI;FA;;;" + user + ")"
            scratch = base / "scratch"
            make_directory(scratch, common + "(A;OICI;0x1301bf;;;" + package_string + ")S:(ML;OICI;NW;;;LW)")
            for mode in ("control", "appcontainer"):
                private = base / (mode + "-private")
                make_directory(private, common)
                for name, payload in CANARIES.items():
                    (private / (name + ".bin")).write_bytes(payload)
            batch = scratch / "probe.cmd"
            batch.write_bytes(SCRIPT.replace("\n", "\r\n").encode("ascii"))
            out["batch_sha256"] = digest(batch.read_bytes())
            out["effective_sddl"] = {"scratch": security_readback(scratch, True), "batch": security_readback(batch),
                                     "private": security_readback(base / "appcontainer-private", True),
                                     "private_file": security_readback(base / "appcontainer-private" / "read.bin")}
            out["last_phase"] = "ordinary_control"
            out["control"] = launch(exe, scratch, "control")
            out["control"]["readback"] = readback(base, scratch, "control")
            control = out["control"]
            assert control.get("host_captured_exit") == 37 and control.get("job_active_processes_after_wait") == 0, "Ordinary control did not complete"
            rb = control["readback"]
            assert all(rb[key] for key in ("child_started", "child_completed", "scratch_positive", "private_read_observed", "private_write_changed", "private_delete_effect", "private_rename_effect", "private_hardlink_effect")), "Ordinary canary positive control failed"
            out["last_phase"] = "create_profile"
            # Exactly one unique owned profile per run. Never reuse/delete existing.
            assert not profile_path.exists() and not registry_mapping_exists(mapping)
            hr = U.CreateAppContainerProfile(moniker, moniker, "Owned S31 synthetic diagnostic", None, 0, C.byref(created_sid))
            out["create_profile_hresult"] = "0x%08X" % (hr & 0xffffffff)
            if hr != 0:
                raise RuntimeError("Owned profile creation failed")
            profile_created = True
            assert sid_text(created_sid) == package_string
            A.FreeSid(created_sid)
            created_sid = C.c_void_p()
            folder = W.LPWSTR()
            try:
                hr = U.GetAppContainerFolderPath(package_string, C.byref(folder))
                out["profile_api_path_matches"] = hr == 0 and Path(folder.value).resolve() == profile_path
                assert out["profile_api_path_matches"]
            finally:
                if folder:
                    O.CoTaskMemFree(folder)
            out["profile_folder_exists_after_create"] = profile_path.exists()
            out["profile_mapping_exists_after_create"] = registry_mapping_exists(mapping)
            assert out["profile_folder_exists_after_create"] and out["profile_mapping_exists_after_create"]
            out["last_phase"] = "appcontainer_launch"
            out["appcontainer"] = launch(exe, scratch, "appcontainer", package)
            out["appcontainer"]["readback"] = readback(base, scratch, "appcontainer")
            child = out["appcontainer"]
            assert child.get("host_captured_exit") == 37 and child.get("job_active_processes_after_wait") == 0, "AppContainer did not complete"
            rb = child["readback"]
            assert rb["child_started"] and rb["child_completed"] and rb["scratch_positive"], "AppContainer positive marker missing"
            assert not any(rb[key] for key in ("private_read_observed", "private_write_changed", "private_delete_effect", "private_rename_effect", "private_hardlink_effect")), "Forbidden private effect observed"
            assert rb["private_contents_unchanged"] and rb["private_link_count"] == 1
            out["marker"] = "GT02_S31_APPCONTAINER_DIAGNOSTIC_COMPLETE"
    except Exception as exc:
        out["error"] = {"type": type(exc).__name__, "message": str(exc), "winerror": getattr(exc, "winerror", None)}
    finally:
        if own:
            K.CloseHandle(own)
        if created_sid.value:
            A.FreeSid(created_sid)
        if package.value:
            A.FreeSid(package)
        if profile_created:
            hr = U.DeleteAppContainerProfile(moniker)
            out["delete_profile_hresult"] = "0x%08X" % (hr & 0xffffffff)
        if profile_path is not None and mapping is not None:
            out["profile_folder_absent_after"] = not profile_path.exists()
            out["profile_mapping_absent_after"] = not registry_mapping_exists(mapping)
        out["owned_temp_removed"] = base is not None and not base.exists()
    out["owned_profile_created_this_run"] = profile_created
    out["diagnostic_complete"] = bool(out.get("marker") and not out.get("error") and out.get("owned_temp_removed")
                                      and out.get("delete_profile_hresult") == "0x00000000"
                                      and out.get("profile_folder_absent_after") and out.get("profile_mapping_absent_after"))
    raw_root = PRODUCT / "studio/.local/review-raw/S31"
    # Parent explicitly authorized this ignored raw location; public copies redact.
    check = subprocess.run(["git", "check-ignore", "--quiet", str(raw_root / "probe.json")], cwd=PRODUCT, timeout=10)
    assert check.returncode == 0, "Raw evidence location must be git-ignored"
    raw_root.mkdir(parents=True, exist_ok=True)
    raw_path = raw_root / (RUN_ID + "-" + run_uuid + ".json")
    raw = json.dumps(out, indent=2, ensure_ascii=True).encode("utf-8")
    with raw_path.open("xb") as stream:
        stream.write(raw)
    replacements = [(str(base), "<OWNED_TEMP>") if base else ("", ""),
                    (str(profile_path), "<OWNED_PROFILE_PATH>") if profile_path else ("", ""),
                    (user or "", "<BROKER_SID>"), (out.get("package_sid", ""), "<APPCONTAINER_SID>"),
                    (moniker, "<OWNED_PROFILE_NAME>"), (os.environ.get("USERPROFILE", ""), "<USER_PROFILE>"),
                    (str(PRODUCT), "<PRODUCT_ROOT>"), (os.environ["SystemRoot"], "<SYSTEM_ROOT>")]
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
    public["private_raw_sha256"] = digest(raw)
    public["private_raw_relative_path"] = raw_path.relative_to(PRODUCT).as_posix()
    public["redaction"] = "Public paths, profile name and host/package SIDs replaced; raw exact bytes kept ignored"
    print(json.dumps(public, indent=2, ensure_ascii=True))
    return 0 if out["diagnostic_complete"] else 1

if __name__ == "__main__":
    sys.exit(main())
