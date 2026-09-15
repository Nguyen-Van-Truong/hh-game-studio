/* Fixed synthetic Win32 diagnostic; no generic command execution interface. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <wchar.h>
#include <stdlib.h>
#include <string.h>

static FILE *record;
static void number(const char *key, unsigned long long value) {
    fprintf(record, "\"%s\":%llu,\n", key, value);
}
static DWORD file_open(const wchar_t *path, DWORD access, DWORD flags) {
    HANDLE handle = CreateFileW(path, access, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                                NULL, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT | flags, NULL);
    DWORD error = handle == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle);
    return error;
}
static DWORD process_open(DWORD pid, DWORD access) {
    HANDLE handle = OpenProcess(access, FALSE, pid);
    DWORD error = handle == NULL ? GetLastError() : 0;
    if (handle != NULL) CloseHandle(handle);
    return error;
}
static int environment(wchar_t *out, DWORD cap, const wchar_t *key) {
    DWORD length = GetEnvironmentVariableW(key, out, cap);
    return length > 0 && length < cap;
}
static int same_hex_id(const FILE_ID_INFO *id, const wchar_t *expected) {
    static const wchar_t digits[] = L"0123456789abcdef";
    size_t i;
    if (wcslen(expected) != 32) return 0;
    for (i = 0; i < 16; i++) {
        if (expected[i * 2] != digits[id->FileId.Identifier[i] >> 4] ||
            expected[i * 2 + 1] != digits[id->FileId.Identifier[i] & 15]) return 0;
    }
    return 1;
}
/* Deliberately absent inherited handles may trigger strict-handle SEH rather
   than BOOL failure. Record only INVALID_HANDLE; never swallow other faults. */
static BOOL sentinel_info(HANDLE handle, DWORD *flags, FILE_ID_INFO *identity, int kind) {
    BOOL result = FALSE;
    DWORD caught = 0, error = 0;
    __try {
        result = kind == 0 ? GetHandleInformation(handle, flags) :
            GetFileInformationByHandleEx(handle, FileIdInfo, identity, sizeof(*identity));
        error = result ? 0 : GetLastError();
    } __except (GetExceptionCode() == 0xC0000008UL ? EXCEPTION_EXECUTE_HANDLER : EXCEPTION_CONTINUE_SEARCH) {
        caught = GetExceptionCode();
        error = ERROR_INVALID_HANDLE;
    }
    number(kind == 0 ? "sentinel_handle_exception" : "sentinel_file_exception", caught);
    SetLastError(error);
    return result;
}
int wmain(int argc, wchar_t **argv) {
    wchar_t base[1024], mode[64], path[1400], text[128], expected[64], volume_text[64];
    wchar_t executable[1400], command[1600];
    DWORD broker, count = 0, flags, error;
    HANDLE sentinel;
    FILE_ID_INFO identity;
    BOOL ok;
    int matches;
    char bytes[64] = {0};
    LARGE_INTEGER zero;
    PROCESS_MITIGATION_CHILD_PROCESS_POLICY policy;
    STARTUPINFOW startup;
    PROCESS_INFORMATION child;
    if (!environment(base, 1024, L"S32_FIXTURE") || !environment(mode, 64, L"S32_MODE")) return 91;
    if (wcsstr(base, L"gt02-s32-boundary-") == NULL) return 92;
    if (wcscmp(mode, L"control") != 0 && wcscmp(mode, L"inherit_control") != 0 &&
        wcscmp(mode, L"appcontainer") != 0 && wcscmp(mode, L"appcontainer_restricted") != 0) return 93;
    if (argc == 2 && wcscmp(argv[1], L"--sentinel-child") == 0) {
        swprintf_s(path, 1400, L"%ls\\scratch\\%ls-child-marker.txt", base, mode);
        if (_wfopen_s(&record, path, L"wb") != 0) return 94;
        fputs("S32_FIXED_CHILD_COMPLETE", record);
        fclose(record);
        return 43;
    }
    if (argc != 1) return 95;
    swprintf_s(path, 1400, L"%ls\\scratch\\%ls-native.json", base, mode);
    if (_wfopen_s(&record, path, L"wb") != 0) return 96;
    setvbuf(record, NULL, _IONBF, 0);
    fputs("{\"started\":\"S32_NATIVE_STARTED\",\n", record);
    swprintf_s(path, 1400, L"%ls\\%ls-private\\source.bin", base, mode);
    number("private_open_zero_error", file_open(path, 0, 0));
    number("private_open_write_dac_error", file_open(path, WRITE_DAC, 0));
    number("private_open_write_owner_error", file_open(path, WRITE_OWNER, 0));
    swprintf_s(path, 1400, L"%ls\\%ls-private", base, mode);
    number("directory_delete_child_open_error", file_open(path, FILE_DELETE_CHILD, FILE_FLAG_BACKUP_SEMANTICS));
    number("directory_add_file_open_error", file_open(path, FILE_ADD_FILE, FILE_FLAG_BACKUP_SEMANTICS));
    number("directory_add_subdirectory_open_error", file_open(path, FILE_ADD_SUBDIRECTORY, FILE_FLAG_BACKUP_SEMANTICS));
    swprintf_s(path, 1400, L"%ls\\%ls-private\\created-directory", base, mode);
    ok = CreateDirectoryW(path, NULL);
    number("private_create_directory_error", ok ? 0 : GetLastError());
    swprintf_s(path, 1400, L"%ls\\%ls-private\\delete.bin", base, mode);
    ok = DeleteFileW(path);
    number("private_delete_file_error", ok ? 0 : GetLastError());
    if (!environment(text, 128, L"S32_BROKER_PID")) { fclose(record); return 97; }
    broker = wcstoul(text, NULL, 10);
    number("broker_open_duplicate_handle_error", process_open(broker, PROCESS_DUP_HANDLE));
    number("broker_open_vm_write_error", process_open(broker, PROCESS_VM_WRITE | PROCESS_VM_OPERATION));
    number("broker_open_create_thread_error", process_open(broker, PROCESS_CREATE_THREAD));
    number("broker_open_create_process_error", process_open(broker, PROCESS_CREATE_PROCESS));
    number("broker_open_query_limited_error", process_open(broker, PROCESS_QUERY_LIMITED_INFORMATION));
    if (!environment(text, 128, L"S32_SENTINEL_HANDLE") || !environment(expected, 64, L"S32_SENTINEL_ID") ||
        !environment(volume_text, 64, L"S32_SENTINEL_VOLUME")) { fclose(record); return 98; }
    sentinel = (HANDLE)(uintptr_t)_wcstoui64(text, NULL, 10);
    ok = sentinel_info(sentinel, &flags, &identity, 0);
    number("sentinel_handle_information_error", ok ? 0 : GetLastError());
    ZeroMemory(&identity, sizeof(identity));
    ok = sentinel_info(sentinel, &flags, &identity, 1);
    error = ok ? 0 : GetLastError();
    number("sentinel_file_information_error", error);
    matches = ok && same_hex_id(&identity, expected) && identity.VolumeSerialNumber == _wcstoui64(volume_text, NULL, 10);
    number("sentinel_identity_matches", (unsigned long long)matches);
    /* A recycled numeric handle is never read unless its full identity matches. */
    if (matches) {
        zero.QuadPart = 0;
        ok = SetFilePointerEx(sentinel, zero, NULL, FILE_BEGIN);
        if (ok) ok = ReadFile(sentinel, bytes, sizeof(bytes) - 1, &count, NULL);
        number("sentinel_read_error", ok ? 0 : GetLastError());
        number("sentinel_payload_matches", ok && count == sizeof("S32_SENTINEL_PAYLOAD!") - 1 && memcmp(bytes, "S32_SENTINEL_PAYLOAD!", sizeof("S32_SENTINEL_PAYLOAD!") - 1) == 0);
    } else {
        number("sentinel_read_attempted", 0);
    }
    ZeroMemory(&policy, sizeof(policy));
    ok = GetProcessMitigationPolicy(GetCurrentProcess(), ProcessChildProcessPolicy, &policy, sizeof(policy));
    number("child_policy_query_error", ok ? 0 : GetLastError());
    number("child_policy_flags", policy.Flags);
    number("no_child_process_creation", policy.NoChildProcessCreation);
    if (!GetModuleFileNameW(NULL, executable, 1400)) { fclose(record); return 99; }
    swprintf_s(command, 1600, L"\"%ls\" --sentinel-child", executable);
    ZeroMemory(&startup, sizeof(startup));
    ZeroMemory(&child, sizeof(child));
    startup.cb = sizeof(startup);
    ok = CreateProcessW(executable, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &startup, &child);
    number("child_create_success", ok);
    number("child_create_error", ok ? 0 : GetLastError());
    if (ok) {
        DWORD wait = WaitForSingleObject(child.hProcess, 3000);
        DWORD code = STILL_ACTIVE;
        number("child_wait_result", wait);
        if (wait != WAIT_OBJECT_0) {
            TerminateProcess(child.hProcess, 124);
            WaitForSingleObject(child.hProcess, 1000);
        }
        GetExitCodeProcess(child.hProcess, &code);
        number("child_host_captured_exit", code);
        CloseHandle(child.hThread);
        CloseHandle(child.hProcess);
    }
    fputs("\"complete\":\"S32_NATIVE_COMPLETE\"}\n", record);
    fclose(record);
    return 47;
}
