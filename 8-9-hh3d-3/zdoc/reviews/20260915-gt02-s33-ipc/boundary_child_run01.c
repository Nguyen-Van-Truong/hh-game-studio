/* Fixed local IPC diagnostic, no command execution or production protocol. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>
#include <string.h>

static int transfer(HANDLE pipe, void *buffer, DWORD length, int writing) {
    DWORD done = 0, count;
    while (done < length) {
        BOOL ok = writing ? WriteFile(pipe, (char *)buffer + done, length - done, &count, NULL) :
            ReadFile(pipe, (char *)buffer + done, length - done, &count, NULL);
        if (!ok || count == 0) return 0;
        done += count;
    }
    return 1;
}
int wmain(void) {
    wchar_t endpoint[256], logpath[1400], root[1400], path[1500];
    char reply[192] = {0}, blob[64] = {0}, hash[65] = {0};
    char request[] = "S33_FIXED_STAGE_BYTES";
    uint32_t length = (uint32_t)strlen(request);
    DWORD error, count;
    HANDLE pipe, file;
    FILE *log = NULL;
    if (!GetEnvironmentVariableW(L"S33_PIPE", endpoint, 256) ||
        !GetEnvironmentVariableW(L"S33_LOG", logpath, 1400) ||
        !GetEnvironmentVariableW(L"S33_ROOT", root, 1400)) return 91;
    if (wcsstr(root, L"gt02-s33-ipc-") == NULL || wcsstr(logpath, L"gt02-s33-ipc-") == NULL) return 92;
    if (_wfopen_s(&log, logpath, L"wb") != 0) return 93;
    setvbuf(log, NULL, _IONBF, 0);
    fputs("{\"started\":\"S33_NATIVE_STARTED\",", log);
    pipe = CreateFileW(endpoint, FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE,
                       0, NULL, OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, NULL);
    error = pipe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"pipe_open_error\":%lu,", error);
    if (pipe == INVALID_HANDLE_VALUE) { fputs("\"complete\":false}", log); fclose(log); return 94; }
    if (!transfer(pipe, &length, 4, 1) || !transfer(pipe, request, length, 1) ||
        !transfer(pipe, &length, 4, 0) || length == 0 || length >= sizeof(reply) ||
        !transfer(pipe, reply, length, 0)) {
        CloseHandle(pipe); fputs("\"complete\":false}", log); fclose(log); return 95;
    }
    reply[length] = 0;
    fprintf(log, "\"reply\":\"%s\",", reply);
    if (sscanf_s(reply, "STAGED %63s %64s", blob, (unsigned)sizeof(blob), hash, (unsigned)sizeof(hash)) == 2) {
        size_t i;
        wchar_t wide[64];
        if (strlen(blob) != 37 || strncmp(blob, "blob-", 5) != 0 || strlen(hash) != 64) return 96;
        for (i = 5; i < strlen(blob); i++) if (!strchr("0123456789abcdef", blob[i])) return 97;
        for (i = 0; i <= strlen(blob); i++) wide[i] = (wchar_t)blob[i];
        swprintf_s(path, 1500, L"%ls\\%ls", root, wide);
        file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
        error = file == INVALID_HANDLE_VALUE ? GetLastError() : 0;
        fprintf(log, "\"direct_read_error\":%lu,", error);
        if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
        file = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_FLAG_OPEN_REPARSE_POINT, NULL);
        error = file == INVALID_HANDLE_VALUE ? GetLastError() : 0;
        fprintf(log, "\"direct_write_error\":%lu,", error);
        if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    }
    /* Final fixed acknowledgement keeps client identity alive through server readback. */
    count = 1;
    request[0] = '!';
    if (!transfer(pipe, request, count, 1)) return 98;
    CloseHandle(pipe);
    fputs("\"complete\":\"S33_NATIVE_COMPLETE\"}", log);
    fclose(log);
    return 53;
}
