#include <windows.h>
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#pragma comment(lib, "advapi32.lib")

static wchar_t scratch[1024], target[1024], control[1024];
static unsigned long attempts, denied, allowed, unexpected;

static int write_file(const wchar_t *name, const char *bytes) {
    wchar_t path[1200]; DWORD count; HANDLE handle;
    if (swprintf_s(path, 1200, L"%ls\\%ls", scratch, name) < 0) return 0;
    handle = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW, 0, NULL);
    if (handle == INVALID_HANDLE_VALUE) return 0;
    if (!WriteFile(handle, bytes, (DWORD)strlen(bytes), &count, NULL)) { CloseHandle(handle); return 0; }
    if (count != (DWORD)strlen(bytes) || !FlushFileBuffers(handle)) { CloseHandle(handle); return 0; }
    return CloseHandle(handle) != 0;
}

static void record(LSTATUS status) {
    ++attempts;
    if (status == ERROR_ACCESS_DENIED) ++denied;
    else if (status == ERROR_SUCCESS) ++allowed;
    else ++unexpected;
}

int wmain(void) {
    HKEY handle = NULL; LSTATUS result; DWORD size, kind, disposition;
    wchar_t child[1200], stop[1200]; char buffer[64], report[512];
    unsigned long loops = 0; DWORD i;
    const REGSAM rights[] = {KEY_QUERY_VALUE, KEY_SET_VALUE, DELETE, WRITE_DAC, WRITE_OWNER, KEY_CREATE_SUB_KEY, READ_CONTROL};
    if (!GetEnvironmentVariableW(L"S45_SCRATCH", scratch, 1024) ||
        !GetEnvironmentVariableW(L"S45_TARGET", target, 1024) ||
        !GetEnvironmentVariableW(L"S45_CONTROL", control, 1024)) return 20;
    /* Same actual user-hive prefix: a deliberately package-granted positive key. */
    result = RegOpenKeyExW(HKEY_USERS, control, 0, KEY_QUERY_VALUE | KEY_SET_VALUE | KEY_WOW64_64KEY, &handle);
    if (result != ERROR_SUCCESS) return 21;
    size = sizeof(buffer); kind = 0;
    result = RegQueryValueExW(handle, L"State", NULL, &kind, (BYTE *)buffer, &size);
    if (result != ERROR_SUCCESS || kind != REG_BINARY || size != 7 || memcmp(buffer, "CONTROL", 7)) { RegCloseKey(handle); return 22; }
    result = RegSetValueExW(handle, L"State", 0, REG_BINARY, (const BYTE *)"CHILD_OK", 8);
    if (result != ERROR_SUCCESS) { RegCloseKey(handle); return 23; }
    if (RegCloseKey(handle) != ERROR_SUCCESS) return 24;
    if (!write_file(L"ready", "READY")) return 25;
    if (swprintf_s(child, 1200, L"%ls\\evil", target) < 0 || swprintf_s(stop, 1200, L"%ls\\stop", scratch) < 0) return 26;
    do {
        for (i = 0; i < sizeof(rights) / sizeof(rights[0]); ++i) {
            handle = NULL;
            result = RegOpenKeyExW(HKEY_USERS, target, REG_OPTION_OPEN_LINK, rights[i] | KEY_WOW64_64KEY, &handle);
            record(result);
            if (result == ERROR_SUCCESS) RegCloseKey(handle);
        }
        record(RegDeleteKeyExW(HKEY_USERS, target, KEY_WOW64_64KEY, 0));
        handle = NULL; disposition = 0;
        result = RegCreateKeyExW(HKEY_USERS, child, 0, NULL, REG_OPTION_NON_VOLATILE,
                                KEY_SET_VALUE | KEY_WOW64_64KEY, NULL, &handle, &disposition);
        record(result);
        if (result == ERROR_SUCCESS) RegCloseKey(handle);
        ++loops;
        Sleep(1);
    } while (GetFileAttributesW(stop) == INVALID_FILE_ATTRIBUTES && loops < 10000);
    if (sprintf_s(report, sizeof(report), "{\"complete\":\"S45_REGISTRY_BOUNDARY_COMPLETE\",\"loops\":%lu,\"attempts\":%lu,\"denied\":%lu,\"allowed\":%lu,\"unexpected\":%lu,\"control_read_write\":true}",
                  loops, attempts, denied, allowed, unexpected) < 0 || !write_file(L"result.json", report)) return 27;
    return allowed == 0 && unexpected == 0 && loops >= 2 ? 89 : 28;
}
