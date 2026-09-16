/* Bounded diagnostic fixture only; this parser is not a production JSON client. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <bcrypt.h>
#include <stdio.h>
#include <wchar.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "advapi32.lib")

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
static int send_frame(HANDLE pipe, const char *data) {
    uint32_t n = (uint32_t)strlen(data);
    return n > 0 && n < 16384 && transfer(pipe, &n, 4, 1) && transfer(pipe, (void *)data, n, 1);
}
static int receive(HANDLE pipe, char *data, DWORD cap) {
    uint32_t n;
    if (!transfer(pipe, &n, 4, 0) || n == 0 || n >= cap || !transfer(pipe, data, n, 0)) return 0;
    data[n] = 0;
    return 1;
}
/* Fixed canonical server fields only; reject escaping/control/oversized values. */
static const char *field(const char *json, const char *key) {
    char needle[100];
    if (sprintf_s(needle, sizeof(needle), "\"%s\":", key) <= 0) return NULL;
    return strstr(json, needle) ? strstr(json, needle) + strlen(needle) : NULL;
}
static int string_field(const char *json, const char *key, char *out, size_t cap) {
    const char *p = field(json, key); size_t n = 0;
    if (!p || *p++ != '"') return 0;
    while (*p && *p != '"') {
        if ((unsigned char)*p < 32 || *p == '\\' || n + 1 >= cap) return 0;
        out[n++] = *p++;
    }
    if (*p != '"') return 0;
    out[n] = 0; return 1;
}
static int number_field(const char *json, const char *key, unsigned long long *out) {
    const char *p = field(json, key); char *end;
    if (!p || *p < '0' || *p > '9') return 0;
    *out = _strtoui64(p, &end, 10);
    return (*end == ',' || *end == '}') && *out <= 9007199254740991ULL;
}
static int hash_payload(const char *payload, char *out) {
    BCRYPT_ALG_HANDLE algorithm = NULL; BCRYPT_HASH_HANDLE hash = NULL;
    unsigned char object[4096], digest[32]; DWORD size = 0, count = 0; unsigned i; int ok = 0;
    if (BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, NULL, 0) < 0) goto done;
    if (BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, (PUCHAR)&size, sizeof(size), &count, 0) < 0 || size > sizeof(object)) goto done;
    if (BCryptCreateHash(algorithm, &hash, object, size, NULL, 0, 0) < 0) goto done;
    if (BCryptHashData(hash, (PUCHAR)payload, (ULONG)strlen(payload), 0) < 0) goto done;
    if (BCryptFinishHash(hash, digest, sizeof(digest), 0) < 0) goto done;
    for (i = 0; i < sizeof(digest); ++i) sprintf_s(out + i * 2, 3, "%02x", (unsigned)digest[i]);
    ok = 1;
done:
    if (hash) BCryptDestroyHash(hash);
    if (algorithm) BCryptCloseAlgorithmProvider(algorithm, 0);
    return ok;
}
static unsigned long long now_ms(void) {
    FILETIME ft; ULARGE_INTEGER value;
    GetSystemTimeAsFileTime(&ft); value.LowPart = ft.dwLowDateTime; value.HighPart = ft.dwHighDateTime;
    return value.QuadPart / 10000ULL - 11644473600000ULL;
}
static int exchange(HANDLE pipe, const char *bearer, const char *route, const char *body, char *reply, DWORD cap) {
    char frame[16384];
    if (sprintf_s(frame, sizeof(frame), "Bearer %s\n%s\n%s", bearer, route, body) <= 0) return 0;
    return send_frame(pipe, frame) && receive(pipe, reply, cap);
}
static void hex_reply(FILE *log, const char *key, const char *value) {
    const unsigned char *cursor = (const unsigned char *)value;
    fprintf(log, "\"%s\":\"", key);
    while (*cursor) fprintf(log, "%02x", (unsigned)*cursor++);
    fputs("\",", log);
}
static int denied(FILE *log, const char *name, const wchar_t *path, DWORD rights, DWORD flags) {
    HANDLE handle = CreateFileW(path, rights, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                               NULL, OPEN_EXISTING, flags, NULL);
    DWORD error = handle == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"%s\":%lu,", name, error);
    if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle);
    return error == ERROR_ACCESS_DENIED;
}
int wmain(void) {
    wchar_t work[256], control[256], logpath[1400], mode[32], root[1400], events[1400], regpath[512];
    char bootstrap[2048], bearer[64], project[128], session[128], reply[16384], body[8192], request[8192];
    char lease[128], selection[65], source_revision[128], source_sha[65], game_revision[128], payload[4096], digest[65], status[40];
    char command[128], lookup[512], frame[16384];
    unsigned long long generation, fence, deadline; ULONGLONG until;
    HANDLE wp = INVALID_HANDLE_VALUE, cp = INVALID_HANDLE_VALUE, probe; HKEY reg = NULL;
    FILE *log = NULL; LONG reg_error; DWORD error; int code = 95, drop, stopping;
    if (!envw(L"S46_WORK", work, 256) || !envw(L"S46_CONTROL", control, 256) ||
        !envw(L"S46_LOG", logpath, 1400) || !envw(L"S46_MODE", mode, 32) ||
        !envw(L"S46_PRIVATE_ROOT", root, 1400) || !envw(L"S46_EVENTS", events, 1400) ||
        !envw(L"S46_REGISTRY", regpath, 512) || wcsstr(logpath, L"gt02-s46-native-") == NULL) return 91;
    if (_wfopen_s(&log, logpath, L"wb") != 0) return 92;
    setvbuf(log, NULL, _IONBF, 0); fputs("{\"started\":\"S46_NATIVE_STARTED\",", log);
    drop = wcscmp(mode, L"drop_reply") == 0; stopping = wcscmp(mode, L"create") != 0;
    if (!denied(log, "pipe_write_dac_error", work, WRITE_DAC, 0) ||
        !denied(log, "pipe_write_owner_error", work, WRITE_OWNER, 0)) goto done;
    probe = CreateNamedPipeW(work, PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
                            PIPE_REJECT_REMOTE_CLIENTS, 1, 4096, 4096, 1000, NULL);
    error = probe == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    fprintf(log, "\"second_instance_error\":%lu,", error);
    if (probe != INVALID_HANDLE_VALUE) CloseHandle(probe);
    if (error != ERROR_ACCESS_DENIED) goto done;
    if (!denied(log, "private_read_error", root, FILE_LIST_DIRECTORY, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT) ||
        !denied(log, "private_write_error", root, FILE_ADD_FILE, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT) ||
        !denied(log, "events_access_error", events, FILE_READ_DATA | FILE_WRITE_DATA, FILE_FLAG_OPEN_REPARSE_POINT)) goto done;
    reg_error = RegOpenKeyExW(HKEY_USERS, regpath, REG_OPTION_OPEN_LINK, KEY_QUERY_VALUE | KEY_SET_VALUE | KEY_WOW64_64KEY, &reg);
    fprintf(log, "\"registry_read_write_error\":%ld,", reg_error);
    if (reg) { RegCloseKey(reg); reg = NULL; }
    if (reg_error != ERROR_ACCESS_DENIED) goto done;
    wp = CreateFileW(work, FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE,
                    0, NULL, OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, NULL);
    cp = CreateFileW(control, FILE_READ_DATA | FILE_WRITE_DATA | READ_CONTROL | SYNCHRONIZE,
                    0, NULL, OPEN_EXISTING, SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION, NULL);
    if (wp == INVALID_HANDLE_VALUE || cp == INVALID_HANDLE_VALUE || !receive(wp, bootstrap, sizeof(bootstrap))) goto done;
    if (!string_field(bootstrap, "bearer", bearer, sizeof(bearer)) || strlen(bearer) != 43 ||
        !string_field(bootstrap, "project_id", project, sizeof(project)) ||
        !string_field(bootstrap, "session_id", session, sizeof(session)) ||
        !strstr(bootstrap, "\"schema\":\"hh-selector-session-1\"")) goto done;
    SecureZeroMemory(bootstrap, sizeof(bootstrap)); fputs("\"bootstrap_received_not_logged\":true,", log);
    sprintf_s(body, sizeof(body), "{\"project_id\":\"%s\",\"protocol_version\":\"1.0\"}", project);
    if (!exchange(wp, bearer, "/v1/discovery", body, reply, sizeof(reply)) || !strstr(reply, "fixture.release.activate")) goto done;
    hex_reply(log, "discovery_hex", reply);
    if (!exchange(cp, bearer, "/v1/inspect", body, reply, sizeof(reply))) goto done;
    hex_reply(log, "initial_inspect_hex", reply);
    if (!number_field(reply, "generation", &generation) || !string_field(reply, "selection_hash", selection, sizeof(selection)) ||
        !string_field(reply, "source_revision", source_revision, sizeof(source_revision)) ||
        !string_field(reply, "source_sha256", source_sha, sizeof(source_sha)) ||
        !string_field(reply, "game_revision", game_revision, sizeof(game_revision))) goto done;
    sprintf_s(body, sizeof(body), "{\"project_id\":\"%s\",\"ttl_ms\":30000}", project);
    if (!exchange(wp, bearer, "/v1/lease", body, reply, sizeof(reply))) goto done;
    hex_reply(log, "lease_hex", reply);
    if (!string_field(reply, "lease_id", lease, sizeof(lease)) || !number_field(reply, "fencing_epoch", &fence)) goto done;
    sprintf_s(payload, sizeof(payload), "{\"assets\":{\"leaf\":{\"references\":[],\"value\":\"inert native leaf\"},\"scene\":{\"references\":[\"leaf\"],\"value\":\"native generation %llu\"}},\"entrypoint\":\"scene\",\"expected_game_revision\":\"%s\",\"expected_generation\":%llu,\"expected_selection_hash\":\"%s\",\"expected_source_revision\":\"%s\",\"expected_source_sha256\":\"%s\"}",
        generation + 1, game_revision, generation, selection, source_revision, source_sha);
    if (!hash_payload(payload, digest)) goto done;
    sprintf_s(command, sizeof(command), "s46.native.%llu", generation + 1);
    deadline = now_ms() + 15000;
    sprintf_s(request, sizeof(request), "{\"command_id\":\"%s\",\"deadline_ms\":%llu,\"expected_revision\":\"%s\",\"fencing_epoch\":%llu,\"lease_id\":\"%s\",\"operation\":\"fixture.release.activate\",\"payload\":%s,\"payload_hash\":\"sha256:%s\",\"project_id\":\"%s\",\"schema_version\":\"hh-studio-0.1\",\"target\":{\"stable_id\":\"active-release\"}}",
        command, deadline, game_revision, fence, lease, payload, digest, project);
    sprintf_s(lookup, sizeof(lookup), "{\"command_id\":\"%s\",\"project_id\":\"%s\"}", command, project);
    if (drop) {
        sprintf_s(frame, sizeof(frame), "Bearer %s\n/v1/commands\n%s", bearer, request);
        if (!send_frame(wp, frame)) goto done;
        CloseHandle(wp); wp = INVALID_HANDLE_VALUE;
        fputs("\"work_reply_received\":false,", log); Sleep(100);
    } else {
        if (!exchange(wp, bearer, "/v1/commands", request, reply, sizeof(reply))) goto done;
        hex_reply(log, "submit_hex", reply);
        if (!string_field(reply, "status", status, sizeof(status)) ||
            (strcmp(status, "ACCEPTED_PENDING") != 0 && strcmp(status, "COMMITTED") != 0)) goto done;
        fputs("\"work_reply_received\":true,", log);
    }
    until = GetTickCount64() + 5000;
    do {
        if (!exchange(cp, bearer, "/v1/lookup", lookup, reply, sizeof(reply)) || !string_field(reply, "status", status, sizeof(status))) goto done;
        if (drop || strcmp(status, "COMMITTED") == 0 || strcmp(status, "REJECTED") == 0 || strcmp(status, "CANCELED") == 0) break;
        Sleep(10);
    } while (GetTickCount64() < until);
    hex_reply(log, "lookup_hex", reply);
    if (!drop && strcmp(status, "COMMITTED") != 0) goto done;
    if (drop && strcmp(status, "COMMITTED") != 0 && strcmp(status, "UNKNOWN") != 0) goto done;
    if (!drop) {
        if (!exchange(wp, bearer, "/v1/commands", request, reply, sizeof(reply)) || !strstr(reply, "\"status\":\"COMMITTED\"")) goto done;
        hex_reply(log, "retry_hex", reply);
    }
    sprintf_s(body, sizeof(body), "{\"project_id\":\"%s\",\"protocol_version\":\"1.0\"}", project);
    if (!exchange(cp, bearer, "/v1/inspect", body, reply, sizeof(reply))) goto done;
    hex_reply(log, "final_inspect_hex", reply);
    if (stopping) {
        if (!exchange(cp, bearer, "/v1/stop", lookup, reply, sizeof(reply)) || !strstr(reply, "\"stopped\":true")) goto done;
        hex_reply(log, "stop_hex", reply);
    }
    code = 86;
done:
    SecureZeroMemory(bearer, sizeof(bearer)); SecureZeroMemory(frame, sizeof(frame));
    if (wp != INVALID_HANDLE_VALUE) CloseHandle(wp);
    if (cp != INVALID_HANDLE_VALUE) CloseHandle(cp);
    fprintf(log, "\"complete\":\"%s\"}", code == 86 ? "S46_NATIVE_COMPLETE" : "S46_NATIVE_FAILED");
    fclose(log); return code;
}
