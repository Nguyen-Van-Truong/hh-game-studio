/* Fixed two-frame native fixture; no command execution or environment logging. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>
#include <string.h>

static int envw(const wchar_t *key, wchar_t *out, DWORD cap) {
    DWORD n = GetEnvironmentVariableW(key, out, cap);
    return n > 0 && n < cap;
}
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
static int send_frame(HANDLE pipe, char *data) {
    uint32_t n = (uint32_t)strlen(data);
    return transfer(pipe, &n, 4, 1) && transfer(pipe, data, n, 1);
}
static int receive(HANDLE pipe, char *data, DWORD cap) {
    uint32_t n;
    if (!transfer(pipe, &n, 4, 0) || n == 0 || n >= cap || !transfer(pipe, data, n, 0)) return 0;
    data[n] = 0;
    return 1;
}
static void hex_reply(FILE *log, const char *key, const char *value) {
    const unsigned char *cursor = (const unsigned char *)value;
    fprintf(log, "\"%s\":\"", key);
    while (*cursor) fprintf(log, "%02x", (unsigned)*cursor++);
    fputs("\",", log);
}
int wmain(void) {
    wchar_t work[256], control[256], logpath[1400], mode[32];
    char frame[32768], reply[8192], ack[] = "S35_FINAL_ACK";
    DWORD n, error;
    HANDLE wp = INVALID_HANDLE_VALUE, cp = INVALID_HANDLE_VALUE, probe;
    FILE *log = NULL;
    int code = 95;
    if (!envw(L"S35_WORK", work, 256) || !envw(L"S35_CONTROL", control, 256) ||
        !envw(L"S35_LOG", logpath, 1400) || !envw(L"S35_MODE", mode, 32) ||
        wcsstr(logpath, L"gt02-s35-native-") == NULL) return 91;
    if (_wfopen_s(&log, logpath, L"wb") != 0) return 92;
    setvbuf(log, NULL, _IONBF, 0);
    fputs("{\"started\":\"S35_NATIVE_STARTED\",", log);
    probe = CreateFileW(work, WRITE_DAC, 0, NULL, OPEN_EXISTING, 0, NULL);
    error = probe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"pipe_write_dac_error\":%lu,", error);
    if (probe != INVALID_HANDLE_VALUE) { CloseHandle(probe); goto done; }
    if (error != ERROR_ACCESS_DENIED) goto done;
    probe = CreateFileW(work, WRITE_OWNER, 0, NULL, OPEN_EXISTING, 0, NULL);
    error = probe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"pipe_write_owner_error\":%lu,", error);
    if (probe != INVALID_HANDLE_VALUE) { CloseHandle(probe); goto done; }
    if (error != ERROR_ACCESS_DENIED) goto done;
    probe = CreateNamedPipeW(work, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
                            PIPE_REJECT_REMOTE_CLIENTS, 1, 4096, 4096, 1000, NULL);
    error = probe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"second_instance_error\":%lu,", error);
    if (probe != INVALID_HANDLE_VALUE) { CloseHandle(probe); goto done; }
    if (error != ERROR_ACCESS_DENIED) goto done;
    wp = CreateFileW(work, FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE,
                    0, NULL, OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, NULL);
    cp = CreateFileW(control, FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE,
                    0, NULL, OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, NULL);
    if (wp == INVALID_HANDLE_VALUE || cp == INVALID_HANDLE_VALUE) goto done;
    n = GetEnvironmentVariableA("S35_FRAME0", frame, sizeof(frame));
    if (n == 0 || n >= sizeof(frame) || !send_frame(wp, frame)) goto done;
    if (wcscmp(mode, L"drop_reply") == 0) {
        CloseHandle(wp); wp = INVALID_HANDLE_VALUE;
        fputs("\"work_reply_received\":false,", log);
    } else {
        if (!receive(wp, reply, sizeof(reply))) goto done;
        fputs("\"work_reply_received\":true,", log);
        hex_reply(log, "work_reply_hex", reply);
    }
    n = GetEnvironmentVariableA("S35_FRAME1", frame, sizeof(frame));
    if (n == 0 || n >= sizeof(frame) || !send_frame(cp, frame) || !receive(cp, reply, sizeof(reply))) goto done;
    hex_reply(log, "control_reply_hex", reply);
    if (!send_frame(cp, ack) || !receive(cp, reply, sizeof(reply)) || strcmp(reply, "S35_FINAL_BYE") != 0) goto done;
    code = 57;
done:
    if (wp != INVALID_HANDLE_VALUE) CloseHandle(wp);
    if (cp != INVALID_HANDLE_VALUE) CloseHandle(cp);
    fprintf(log, "\"complete\":\"%s\"}", code == 57 ? "S35_NATIVE_COMPLETE" : "S35_NATIVE_FAILED");
    fclose(log);
    return code;
}
