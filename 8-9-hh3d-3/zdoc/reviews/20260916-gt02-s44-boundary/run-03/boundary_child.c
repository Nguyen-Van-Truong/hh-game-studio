#include <windows.h>
#include <stdio.h>

static unsigned long attempts = 0, allowed = 0, unexpected = 0;
static void denied(BOOL ok) {
    DWORD error = ok ? 0 : GetLastError();
    ++attempts;
    if (ok) ++allowed;
    if (!ok && error != ERROR_ACCESS_DENIED) ++unexpected;
}
static void try_open(const wchar_t *path, DWORD access, DWORD flags) {
    HANDLE h = CreateFileW(path, access, 7, NULL, OPEN_EXISTING, flags, NULL);
    denied(h != INVALID_HANDLE_VALUE);
    if (h != INVALID_HANDLE_VALUE) CloseHandle(h);
}
static BOOL write_marker(const wchar_t *path, const char *bytes, DWORD length) {
    DWORD written = 0;
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 7, NULL, CREATE_NEW, 0, NULL);
    BOOL ok;
    if (h == INVALID_HANDLE_VALUE) return FALSE;
    ok = WriteFile(h, bytes, length, &written, NULL) && written == length && FlushFileBuffers(h);
    CloseHandle(h);
    return ok;
}
int wmain(void) {
    wchar_t root[32768], scratch[32768], target[32768], source[32768];
    wchar_t ready[32768], stop[32768], alias[32768], inward[32768], logpath[32768];
    wchar_t broker[32];
    DWORD n, pid, written;
    unsigned long loops = 0;
    ULONGLONG deadline;
    HANDLE h;
    char result[512];
    int length;
    if (!GetEnvironmentVariableW(L"S44_ROOT", root, 32768) ||
        !GetEnvironmentVariableW(L"S44_SCRATCH", scratch, 32768) ||
        !GetEnvironmentVariableW(L"S44_BROKER", broker, 32)) return 2;
    pid = wcstoul(broker, NULL, 10);
    if (swprintf_s(target, 32768, L"%s\\asset.txt", root) < 0 ||
        swprintf_s(inward, 32768, L"%s\\attacker-link", root) < 0 ||
        swprintf_s(source, 32768, L"%s\\attacker.txt", scratch) < 0 ||
        swprintf_s(alias, 32768, L"%s\\outward-link", scratch) < 0 ||
        swprintf_s(ready, 32768, L"%s\\ready", scratch) < 0 ||
        swprintf_s(stop, 32768, L"%s\\stop", scratch) < 0 ||
        swprintf_s(logpath, 32768, L"%s\\result.json", scratch) < 0) return 3;
    if (!write_marker(source, "ATTACKER", 8)) return 4;
    /* Positive control: hardlinks and rename work in the granted scratch. */
    if (!CreateHardLinkW(alias, source, NULL) || !DeleteFileW(alias)) return 5;
    if (!MoveFileExW(source, alias, 0) || !MoveFileExW(alias, source, 0)) return 6;
    h = CreateFileW(source, GENERIC_READ, 7, NULL, OPEN_EXISTING, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return 7;
    { char control[8];
      BOOL ok = ReadFile(h, control, 8, &n, NULL) && n == 8 && memcmp(control, "ATTACKER", 8) == 0;
      CloseHandle(h); if (!ok) return 8; }
    if (!write_marker(ready, "READY", 5)) return 9;
    deadline = GetTickCount64() + 8000;
    do {
        try_open(target, 0, FILE_FLAG_OPEN_REPARSE_POINT);
        try_open(target, GENERIC_WRITE, FILE_FLAG_OPEN_REPARSE_POINT);
        try_open(target, WRITE_DAC, FILE_FLAG_OPEN_REPARSE_POINT);
        try_open(root, FILE_ADD_FILE | FILE_DELETE_CHILD, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT);
        denied(CreateHardLinkW(alias, target, NULL));
        denied(CreateHardLinkW(inward, source, NULL));
        denied(MoveFileExW(source, target, MOVEFILE_REPLACE_EXISTING));
        denied(DeleteFileW(target));
        h = OpenProcess(PROCESS_DUP_HANDLE, FALSE, pid);
        denied(h != NULL); if (h) CloseHandle(h);
        ++loops;
        Sleep(1);
    } while (GetFileAttributesW(stop) == INVALID_FILE_ATTRIBUTES && GetTickCount64() < deadline);
    length = sprintf_s(result, sizeof(result),
        "{\"complete\":\"S44_NATIVE_COMPLETE\",\"scratch_control\":true,\"loops\":%lu,\"attempts\":%lu,\"allowed\":%lu,\"unexpected_errors\":%lu}",
        loops, attempts, allowed, unexpected);
    if (length <= 0) return 10;
    h = CreateFileW(logpath, GENERIC_WRITE, 0, NULL, CREATE_NEW, 0, NULL);
    if (h == INVALID_HANDLE_VALUE) return 11;
    if (!WriteFile(h, result, (DWORD)length, &written, NULL) || written != (DWORD)length || !FlushFileBuffers(h)) { CloseHandle(h); return 12; }
    CloseHandle(h);
    return allowed == 0 && unexpected == 0 && loops > 0 ? 67 : 13;
}
