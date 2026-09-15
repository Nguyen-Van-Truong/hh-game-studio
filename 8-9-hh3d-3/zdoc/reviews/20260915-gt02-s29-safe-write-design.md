# GT-02 S29 — Safe-write design research (report only)

**Date:** 2026-09-15 (Asia/Saigon)  
**Scope:** Design research only; no source, plan, ACL, account, profile, global configuration, or production file mutation.  
**Inputs:** `studio/host/core/safe_open.py` and S27 Windows write research. Existing implementation remains fail-closed (`safe_write=false`, `atomic_replace=false`, `UNSUPPORTED_SAFE_OPEN_WINDOWS`).

## Tested facts carried forward from S27

- `CreateFileW` with `CREATE_NEW` and share mode 0 prevents competing data opens, but does not prevent a same-token peer from creating a hardlink. A write through the retained handle is visible via the alias. Link-count inspection is observational and cannot be made atomic with the subsequent write. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew), [CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw), [FILE_LINK_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_link_information)
- The former attributes-only directory handle (`FILE_READ_ATTRIBUTES`) allowed directory rename. Adding `FILE_LIST_DIRECTORY` blocked that rename (observed `ERROR_SHARING_VIOLATION`/32), while child create/delete remained possible. This improves ancestor stability but does not establish exclusive ownership of descendants.
- `SetFileInformationByHandle(FileRenameInfo)` uses the source handle and destination directory/name, avoiding a source-path reopen. It has no expected-destination file-ID/CAS field. Replacing an open target failed (`ERROR_ACCESS_DENIED`/5) with either read share or delete share; replacement succeeded after target close, leaving a check/close/replace race in a hostile namespace. [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle), [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)
- `FILE_ID_INFO` and `FILE_STANDARD_INFO` expose volume/file identity and current link count, size, and deletion state. They provide no documented conditional write-and-publish primitive. [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info), [FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/ns-fileapi-file_standard_info)

## AppContainer / restricted-token broker design

A meaningful boundary must use a **distinct enforced token**, not merely an ACL granting the host user: Windows ACL evaluation is trustee/token based, so an equal-token peer is indistinguishable from the broker. [How DACLs control access](https://learn.microsoft.com/en-us/windows/win32/secauthz/how-dacls-control-access-to-an-object)

Recommended architecture:

1. A broker process, running with the trusted host token, creates a fresh per-operation staging directory and final release directory on one volume. It applies an explicit security descriptor at object creation and verifies the effective descriptor/readback, final handle path, volume/file IDs, reparse state, and link count through retained handles.
2. The untrusted worker runs in an AppContainer (or a separately provisioned restricted token) with only the minimum capability needed to submit bytes through an authenticated loopback IPC channel. It receives no writable handle to the broker's final namespace. AppContainer provides documented application isolation, but deployment/configuration alone is not proof; process-handle rights, handle duplication, traversal bypass, pre-existing handles, and reparse attacks must be tested adversarially. [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation), [Process security and access rights](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights)
3. The broker owns all writes: create immutable fresh-name staging with `CREATE_NEW`; retain the source handle; write bounded bytes; flush and hash via that handle; re-inspect identity/link count; then publish by handle-relative rename within the broker-only namespace. Start with `replace=false` collision rejection. Keep replacement of an existing active target unsupported until target identity and crash/recovery proofs exist.
4. The broker must authenticate and authorize each command (unique command ID, schema validation, lease/fencing, source hash), and ACK only after postcondition readback. This is an architectural boundary, not a relaxation of the existing contract.

## Exact limitations / unresolved gates

- No probe in this S29 task changed system state; S27's disposable TEMP probes are the only observations used. No evidence currently proves AppContainer or restricted-token behavior for this workload.
- AppContainer package/profile creation, capability declarations, ACL SDDL, broker IPC, and process mitigation settings are deployment-sensitive. They require a dedicated disposable test matrix covering same-token and distinct-token adversaries, inherited/pre-existing handles, hardlink and reparse attempts, directory rename/delete, file-ID opens, handle duplication, and traversal privileges.
- A private parent ACL is insufficient by itself: child security descriptors and effective rights must be captured, and `SeChangeNotifyPrivilege` can permit directory traversal. [File security and access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)
- `ReplaceFile`, POSIX rename flags, extra stat calls, or a held directory handle do not provide destination expected-identity CAS. A hostile equal-privilege writer therefore remains an unresolved architectural conflict.
- Until the boundary and the existing §2.2 race tests are implemented and independently verified, mutation must remain unsupported and no capability flag may advertise safe write.

## Concrete next implementation

Implement a broker prototype behind a new test-only feature gate, without changing `safe_open.py` capability defaults:

- Define the untrusted token model and security descriptor before code; create fresh staging/release roots atomically and record SDDL/effective descriptors.
- Add adversarial tests for hardlink, reparse/junction, ancestor rename, descendant replacement, duplicate-handle, file-ID open, and traversal-bypass attempts under both equal-token and restricted/AppContainer workers.
- Prove create-only publish (`replace=false`) using a retained source handle, same-volume check, flush, readback hash, and host-captured process exit. Add crash/restart journal recovery before considering replacement.
- Require two independent read-only critics on one frozen source hash; retain `UNSUPPORTED_SAFE_OPEN_WINDOWS` on any missing or ambiguous postcondition.

**Disposition:** S29 design research identifies a plausible broker/private-namespace direction, but no supported mutation mechanism has been demonstrated. Fail-closed behavior remains correct.
