"""Bound one trusted synthetic probe child to an owned kill-on-close Job Object.

No service/account/profile/policy operation. No elevation or inherited handles.
This is a diagnostic launcher, deliberately not a production sandbox.
"""
import ctypes as C
from ctypes import wintypes as W
import os
from pathlib import Path
import subprocess
import sys

from restricted_acl_probe import A, K, checked, signature, token_details

class SI(C.Structure):
    _fields_ = [("cb", W.DWORD), ("reserved", W.LPWSTR), ("desktop", W.LPWSTR), ("title", W.LPWSTR),
                ("x", W.DWORD), ("y", W.DWORD), ("width", W.DWORD), ("height", W.DWORD),
                ("chars_x", W.DWORD), ("chars_y", W.DWORD), ("fill", W.DWORD), ("flags", W.DWORD),
                ("show", W.WORD), ("reserved_size", W.WORD), ("reserved2", C.c_void_p),
                ("stdin", W.HANDLE), ("stdout", W.HANDLE), ("stderr", W.HANDLE)]

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

class JACCOUNT(C.Structure):
    _fields_ = [("user_time", C.c_longlong), ("kernel_time", C.c_longlong), ("period_user", C.c_longlong), ("period_kernel", C.c_longlong),
                ("page_faults", W.DWORD), ("total_processes", W.DWORD), ("active_processes", W.DWORD), ("terminated_processes", W.DWORD)]

signature(A, "CreateProcessAsUserW", [W.HANDLE, W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(SI), C.POINTER(PI)], W.BOOL)
signature(K, "CreateJobObjectW", [C.c_void_p, W.LPCWSTR], W.HANDLE)
signature(K, "SetInformationJobObject", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "QueryInformationJobObject", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL)
signature(K, "AssignProcessToJobObject", [W.HANDLE, W.HANDLE], W.BOOL)
signature(K, "TerminateJobObject", [W.HANDLE, W.UINT], W.BOOL)
signature(K, "ResumeThread", [W.HANDLE], W.DWORD)
signature(K, "WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD)
signature(K, "GetExitCodeProcess", [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
signature(K, "TerminateProcess", [W.HANDLE, W.UINT], W.BOOL)

def launch_restricted(token, base, script, broker_pid):
    si, pi, child_token = SI(), PI(), W.HANDLE()
    si.cb = C.sizeof(si)
    job, assigned = None, False
    result = {"inherit_handles": False, "creation_suspended": True, "kill_on_job_close": True,
              "active_process_limit": 1, "memory_limit_bytes": 128 * 1024 * 1024,
              "timeout_ms": 10000, "isolation_scope": "primary restricted token; default desktop; synthetic trusted probe only"}
    try:
        scratch = base / "scratch"
        env = {"SystemRoot": os.environ["SystemRoot"], "TEMP": str(scratch), "TMP": str(scratch),
               "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        block = C.create_unicode_buffer("\0".join(k + "=" + v for k, v in sorted(env.items())) + "\0\0")
        command = subprocess.list2cmdline([sys.executable, "-B", "-I", str(script), "--child", str(base), str(broker_pid)])
        checked(A.CreateProcessAsUserW(token, sys.executable, C.create_unicode_buffer(command), None, None, False,
                                      0x08000404, block, str(scratch), C.byref(si), C.byref(pi)))
        result["pid"] = int(pi.pid)
        checked(A.OpenProcessToken(pi.process, 8, C.byref(child_token)))
        result["host_read_child_token"] = token_details(child_token)
        job = checked(K.CreateJobObjectW(None, None))
        limits = JEXT()
        limits.basic.flags, limits.basic.active_processes = 0x2000 | 0x8 | 0x100, 1
        limits.process_memory = result["memory_limit_bytes"]
        checked(K.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)))
        checked(K.AssignProcessToJobObject(job, pi.process))
        assigned = True
        if K.ResumeThread(pi.thread) == 0xffffffff:
            raise C.WinError(C.get_last_error())
        result["wait_result"] = int(K.WaitForSingleObject(pi.process, result["timeout_ms"]))
        if result["wait_result"] != 0:
            checked(K.TerminateJobObject(job, 126))
            checked(K.WaitForSingleObject(pi.process, 5000) == 0)
        code = W.DWORD()
        checked(K.GetExitCodeProcess(pi.process, C.byref(code)))
        result["host_captured_exit"] = int(code.value)
        account = JACCOUNT()
        checked(K.QueryInformationJobObject(job, 1, C.byref(account), C.sizeof(account), None))
        result["job_active_processes_after_wait"] = int(account.active_processes)
        result["job_total_processes"] = int(account.total_processes)
        return result
    finally:
        if pi.process and K.WaitForSingleObject(pi.process, 0) != 0:
            if assigned:
                K.TerminateJobObject(job, 127)
            else:
                K.TerminateProcess(pi.process, 127)
            K.WaitForSingleObject(pi.process, 5000)
        for handle in (child_token, pi.thread, pi.process, job):
            if handle:
                checked(K.CloseHandle(handle))
