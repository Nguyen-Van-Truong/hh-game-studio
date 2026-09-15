"""Test-only Windows declarations, adapted from the inspected S29 draft."""
import ctypes as C
from ctypes import wintypes as W

K = C.WinDLL("kernel32", use_last_error=True)
A = C.WinDLL("advapi32", use_last_error=True)
U = C.WinDLL("userenv", use_last_error=True)
O = C.WinDLL("ole32", use_last_error=True)
BAD = C.c_void_p(-1).value

class SA(C.Structure):
    _fields_ = [("length", W.DWORD), ("descriptor", C.c_void_p), ("inherit", W.BOOL)]
class SIDATTR(C.Structure):
    _fields_ = [("sid", C.c_void_p), ("attributes", W.DWORD)]
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
class JACCOUNT(C.Structure):
    _fields_ = [("user_time", C.c_longlong), ("kernel_time", C.c_longlong), ("period_user", C.c_longlong), ("period_kernel", C.c_longlong),
                ("page_faults", W.DWORD), ("total_processes", W.DWORD), ("active_processes", W.DWORD), ("terminated_processes", W.DWORD)]

def signature(dll, name, args, result):
    function = getattr(dll, name)
    function.argtypes, function.restype = args, result
    return function

signature(K, "GetCurrentProcess", [], W.HANDLE)
signature(K, "CloseHandle", [W.HANDLE], W.BOOL)
signature(K, "LocalFree", [C.c_void_p], C.c_void_p)
signature(K, "CreateDirectoryW", [W.LPCWSTR, C.POINTER(SA)], W.BOOL)
signature(K, "CreateFileW", [W.LPCWSTR, W.DWORD, W.DWORD, C.POINTER(SA), W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
signature(A, "OpenProcessToken", [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)], W.BOOL)
signature(A, "GetTokenInformation", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.POINTER(W.DWORD)], W.BOOL)
signature(A, "ConvertSidToStringSidW", [C.c_void_p, C.POINTER(W.LPWSTR)], W.BOOL)
signature(A, "ConvertStringSecurityDescriptorToSecurityDescriptorW", [W.LPCWSTR, W.DWORD, C.POINTER(C.c_void_p), C.c_void_p], W.BOOL)
signature(A, "GetSecurityInfo", [W.HANDLE, C.c_int, W.DWORD, C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p, C.POINTER(C.c_void_p)], W.DWORD)
signature(A, "ConvertSecurityDescriptorToStringSecurityDescriptorW", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(W.LPWSTR), C.c_void_p], W.BOOL)
signature(U, "DeriveAppContainerSidFromAppContainerName", [W.LPCWSTR, C.POINTER(C.c_void_p)], C.c_long)
signature(U, "CreateAppContainerProfile", [W.LPCWSTR, W.LPCWSTR, W.LPCWSTR, C.c_void_p, W.DWORD, C.POINTER(C.c_void_p)], C.c_long)
signature(U, "DeleteAppContainerProfile", [W.LPCWSTR], C.c_long)
signature(U, "GetAppContainerFolderPath", [W.LPCWSTR, C.POINTER(W.LPWSTR)], C.c_long)
signature(O, "CoTaskMemFree", [C.c_void_p], None)
signature(A, "FreeSid", [C.c_void_p], C.c_void_p)
signature(K, "InitializeProcThreadAttributeList", [C.c_void_p, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)], W.BOOL)
signature(K, "UpdateProcThreadAttribute", [C.c_void_p, W.DWORD, C.c_size_t, C.c_void_p, C.c_size_t, C.c_void_p, C.c_void_p], W.BOOL)
signature(K, "DeleteProcThreadAttributeList", [C.c_void_p], None)
signature(K, "CreateProcessW", [W.LPCWSTR, W.LPWSTR, C.c_void_p, C.c_void_p, W.BOOL, W.DWORD, C.c_void_p, W.LPCWSTR, C.POINTER(SIEX), C.POINTER(PI)], W.BOOL)
signature(K, "CreateJobObjectW", [C.c_void_p, W.LPCWSTR], W.HANDLE)
signature(K, "SetInformationJobObject", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD], W.BOOL)
signature(K, "QueryInformationJobObject", [W.HANDLE, C.c_int, C.c_void_p, W.DWORD, C.c_void_p], W.BOOL)
signature(K, "AssignProcessToJobObject", [W.HANDLE, W.HANDLE], W.BOOL)
signature(K, "TerminateJobObject", [W.HANDLE, W.UINT], W.BOOL)
signature(K, "ResumeThread", [W.HANDLE], W.DWORD)
signature(K, "WaitForSingleObject", [W.HANDLE, W.DWORD], W.DWORD)
signature(K, "GetExitCodeProcess", [W.HANDLE, C.POINTER(W.DWORD)], W.BOOL)
signature(K, "TerminateProcess", [W.HANDLE, W.UINT], W.BOOL)

def checked(value):
    if not value:
        raise C.WinError(C.get_last_error())
    return value

def sid_text(pointer):
    rendered = W.LPWSTR()
    checked(A.ConvertSidToStringSidW(pointer, C.byref(rendered)))
    try:
        return rendered.value
    finally:
        K.LocalFree(rendered)

def token_info(token, kind):
    count = W.DWORD()
    A.GetTokenInformation(token, kind, None, 0, C.byref(count))
    buffer = C.create_string_buffer(count.value)
    checked(A.GetTokenInformation(token, kind, buffer, count, C.byref(count)))
    return buffer

def token_sid(token, kind):
    buffer = token_info(token, kind)
    return sid_text(C.cast(buffer, C.POINTER(C.c_void_p)).contents.value)

def token_number(token, kind):
    return int(C.cast(token_info(token, kind), C.POINTER(W.DWORD)).contents.value)

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
        error = A.GetSecurityInfo(handle, 1, 0x17, None, None, None, None, C.byref(descriptor))
        if error:
            raise C.WinError(error)
        checked(A.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 0x17, C.byref(rendered), None))
        return rendered.value
    finally:
        if rendered:
            K.LocalFree(rendered)
        if descriptor.value:
            K.LocalFree(descriptor)
        checked(K.CloseHandle(handle))
