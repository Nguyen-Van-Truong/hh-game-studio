# GT-02 S27 — Windows safe-write research

Status: **RESEARCH / GAP, NOT ACCEPTANCE.** No capability is unlocked. GT-02 remains IN_PROGRESS; this report does not change §2.2, open GT-03/GT-04, or approve a write implementation.

Recorded: 2026-09-14, Asia/Saigon. Research author: windows_write_research_s27, narrow report-only lease. Baseline Git HEAD: ebbee531e5db596eebee228bcd7edae89d8dd1f5. Other agents have active changes; the checkout is not a frozen acceptance source. No Godot process was launched, no user project was mutated, and no existing source or plan file was edited by this research task.

## Finding and practical decision

There is **no demonstrated safe one-line replacement for the current UNSUPPORTED mutation path**. CREATE_NEW plus share=0 protects data access by competing opens, but permits another hardlink to the staging object. A later write through the original handle changes the bytes visible through that alias. A before/after link-count check can detect the situation after damage; it cannot make the write atomic with the check.

The shortest defensible direction is an OS-enforced private staging/publish namespace, followed by a retained-source-handle rename. First prove the private namespace against the actual adversary; do not treat a random name, a per-user directory, a lease, or a held attributes-only directory handle as that proof. Implementing a generic replace against a directory writable by a hostile peer still needs an identity-conditional publication proof that the APIs examined here do not supply.

Keep safe_write=false, atomic_replace=false and UNSUPPORTED_SAFE_OPEN_WINDOWS until that proof and the original §2.2 tests exist. A successful rejection test is proof of fail-closed behavior, not proof of supported mutation.

## Original contract and inspected files

The authoritative tools plan §2.2, lines 445–455 at inspection, requires private staged roots, use-time race protection, final handle path/file identity, and rejection of reparse/junction/symlink, link count other than one, aliases and identity changes between validate/open/replace. TX15 calls unavailable safe-open a GAP. Nothing here narrows those requirements.

SHA-256 at inspection:

| Relative to 8-9-hh3d-3 | SHA-256 |
|---|---|
| studio/host/core/safe_open.py | 775be0ad2eb39d12346525f5dbe00a59bb877e1d09c04074fac8bb12092e50d2 |
| studio/tests/protocol/test_safe_open.py | ee98415e71dc0628b5f28c928e268d3516b72fedc06a2e7de14622b1e1e932a7 |
| zdoc/8-9-godot-blender-agent-studio-plan.txt | e66c5e2f9837623f2388c7a96e54b7c0623deed243a4981934b6990a26daa4f0 |

These are research inputs, not a complete frozen runtime closure. The plan/source may subsequently change under the coordinator's lease.

## Microsoft semantics and observed limits

1. **Exclusive sharing is not hardlink exclusion.** CreateFileW sharing governs subsequent read/write/delete access; attribute access is a documented exception. CREATE_NEW rejects an existing name but does not promise that the newly created file can never acquire another name. [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

   CreateHardLinkW creates another directory entry for the same file. Its statement about sharing means that another name cannot bypass the file's data-open sharing rules; it does not say that creating the name itself fails. Changes through the original handle affect all names. The file has one security descriptor, shared by its hardlinks. [CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw)

   The lower-level FILE_LINK_INFORMATION documentation specifies no particular access right for setting that information. This is an additional reason to test metadata/zero-access and handle-based link routes, instead of inferring safety from a blocked data-open or from denial of write-data alone. It does not establish that all path, destination-directory or token checks are bypassed. [FILE_LINK_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_link_information)

2. **Metadata checks observe, rather than reserve, identity/link state.** FileIdInfo supplies volume plus file identity; FileStandardInfo supplies current link count, size and deletion state. They do not document a combined conditional-write operation. [FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info), [FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info)

3. **The existing parent-handle access mask needs correction before any write proof.** The implementation opens directories with FILE_READ_ATTRIBUTES (0x80), share 1, and OPEN_REPARSE_POINT|BACKUP_SEMANTICS. On this host, that handle allowed its otherwise empty directory to be renamed; it also allowed child creation/deletion. A diagnostic handle adding FILE_LIST_DIRECTORY (mask 1, share 1) blocked the same directory rename with error 32. This is a narrow observed result, not a certification of every ancestor/reparse scenario. Retaining a directory identity is insufficient if its namespace can move; even a handle that blocks renaming the directory does not establish exclusive ownership of its children. The existing test involving a simultaneously open child does not isolate the directory-handle claim.

4. **Rename the staging handle, but do not call this destination CAS.** SetFileInformationByHandle identifies its source by handle. FILE_RENAME_INFO accepts a destination directory/name and replace flag; it has no expected-destination-file-ID field. The directory handle can anchor relative destination resolution. This removes a source-path reopen race but does not prove that the destination still has the identity previously inspected. [SetFileInformationByHandle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle), [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)

   In the disposable probe, ordinary FileRenameInfo replacement returned error 5 with the old target open using either share 1 or share 5; it succeeded once that target handle closed. Closing a protecting target handle creates a race interval in a hostile writable namespace. The native documentation includes open-target restrictions and newer POSIX replacement flags. Those flags change replacement semantics, not the absence of an expected target identity parameter; they were not tested here. [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information)

## Threat model: what must be proved

| Adversary / environment | Current finding |
|---|---|
| Malicious request paths, schema data, pre-existing hardlinks/reparse points | Existing resolver/read tests and fail-closed mutation have bounded evidence. This is not a general safe-write implementation. |
| Cooperative local workers obeying the host lease | Lease can serialize their commands, but does not constrain direct OS filesystem calls. |
| Hostile process with the same unrestricted token as the host | A per-user allow ACL does not distinguish it from the host. It reproduced hardlink creation here. Pure path/handle checks in the current library do not provide the required boundary. |
| Untrusted client under a distinct enforced account/service boundary, or a correctly contained client | A plausible design direction; no implementation or negative-token proof exists in this research. It must cover files, all parents, process/handle access, traversal bypass and pre-existing handles. |
| Administrator/kernel/backup/restore privilege or compromised trusted broker | Outside any ordinary user-mode library claim; the contract's trusted components and privilege assumptions must be explicit before claiming supported mutation. This report does not silently exclude a required adversary. |

Windows access checks compare token trustees with object ACLs, not a program's semantic role. Ordinary same-token peers therefore cannot be separated merely by granting the host user's SID. Stronger identity/container restrictions are a separate mechanism. [How AccessCheck works](https://learn.microsoft.com/en-us/windows/win32/secauthz/how-dacls-control-access-to-an-object)

A private parent ACL alone is also insufficient evidence: child object security matters, and normal traverse-bypass privilege can bypass directory traversal checks. Capture effective child and parent descriptors at creation/readback, not just a friendly root name. [File security and access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights)

Process access must also be part of the isolation design, because handle duplication/process tampering can bypass a filesystem-only boundary. AppContainer is a documented isolation mechanism for contained applications, but has not been deployed or validated here; creating one is not itself evidence that this workload is safely isolated. [Process security](https://learn.microsoft.com/en-us/windows/win32/procthread/process-security-and-access-rights), [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)

## Next implementation-sized investigation

1. Preserve the strict contract and add the newly isolated attributes-only-parent-rename case to the candidate tests under the implementation writer's lease. Review directory access masks and retained ancestor stability independently of open-child behavior.
2. Design a broker-controlled local staging/publish namespace. Define the untrusted token explicitly. Create security descriptors atomically with new objects; verify effective descriptors, volume, final paths, reparse state and ancestor identities through handles. Prove that the adversary cannot link, replace, open by file ID, change ACLs or obtain a usable pre-existing/duplicated handle. A same-token test process is not an adequate substitute for this boundary.
3. Start with an immutable, fresh-name CREATE_NEW object; retain its original handle for all writes and readback. Only after namespace protection is proven, write bounded bytes, flush/check return values and hash via the same object. Publish by that source handle within the protected same-volume namespace. Do not reopen the temporary pathname to publish.
4. Exercise create-only publication first with replace=false and collision rejection. This is a smaller primitive to prove, not authorization to skip the existing-target requirement. General replacement and active-manifest changes remain unsupported until hostile target substitution, owner edits, expected identity, crash/recovery and durability have complete evidence.
5. For replace=true, a broker-owned target namespace with all writers mediated by enforced rights is the practical way to eliminate the observed check/replace interval. If the intended live target must remain directly writable by a hostile equal-privilege peer, record that unresolved architectural conflict; neither an extra stat call nor POSIX rename flags resolve it. Do not weaken §2.2 or advertise acceptance.

No new account, ACL policy, container, privilege, filesystem or production writer was installed by this task. The proposed boundary remains unproven. GT-03/GT-04 cannot consume mutation on the strength of this report.

## Bounded diagnostics and reproduction

Existing regression command, run from the repository root:

~~~powershell
python 8-9-hh3d-3/studio/tests/protocol/test_safe_open.py WindowsSafeOpenTests.test_exclusive_handle_hardlink_counterexample_keeps_mutation_disabled -v
~~~

Observed: one test, OK; host-captured exit 0. This reproduces the known counterexample and disabled capability.

Additional standalone probe used only synthetic files in one uniquely named TEMP sandbox, with project/outside siblings. Its outside alias is intentionally an additional name to synthetic staging bytes, never a user file. The original outside sentinel remained unchanged. All native handles closed and TemporaryDirectory cleanup completed.

- Diagnostic -01: host exit 1, because the attributes-only parent rename unexpectedly succeeded and the next CreateFile used the now-absent original path. This failed attempt is not discarded as PASS.
- Diagnostic -02: host exit 0 after recording/restoring the successful rename; confirmed hardlink data visibility and both held-target replace failures.
- Diagnostic -03: host exit 0; additionally tested FILE_LIST_DIRECTORY and successful replacement after target close. Full output below.
- No polling loop, child application, full production mutation, Godot run, ACL alteration or privileged operation.

The final script follows. To reproduce without creating a source file, copy the Python block into a PowerShell single-quoted here-string and pipe it to python - from the repository root. It imports the inspected private Windows wrapper solely for this disposable experiment. Its exit 0 means the diagnostic completed; it does not mean safe-write PASS.

~~~json
{
  "run_id": "GT02-S27-WINDOWS-WRITE-DIAGNOSTIC-03",
  "timestamp_utc": "2026-09-14T14:03:23.868971+00:00",
  "os": "Windows-10-10.0.26200-SP0",
  "python": "3.11.9",
  "scope": "disposable TEMP sandbox; synthetic data only; no production calls",
  "parent_handle": {
    "child_create_delete_allowed": true,
    "parent_rename_winerror": "ALLOWED"
  },
  "list_directory_handle_rename": 32,
  "hardlink": {
    "links_before": 1,
    "links_after": 2,
    "alias_read_while_held_winerror": 32,
    "bytes_written": 23,
    "alias_bytes_equal_after_close": true
  },
  "replace_target_no_delete_share": {
    "success": false,
    "winerror": 5
  },
  "replace_target_with_delete_share": {
    "success": false,
    "winerror": 5
  },
  "replace_target_closed": {
    "success": true,
    "winerror": 0
  },
  "renamed_target_bytes": "new-data",
  "original_outside_sentinel_unchanged": true,
  "native_handles_closed": true,
  "temporary_root_removed": true
}
~~~

~~~python
import ctypes, json, os, platform, sys, tempfile
from ctypes import wintypes as W
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0, str(Path("8-9-hh3d-3/studio").resolve()))
from host.core.safe_open import _WindowsApi, _FileStandardInfo
api = _WindowsApi()
dll = api.dll
dll.WriteFile.argtypes = [W.HANDLE, ctypes.c_void_p, W.DWORD, ctypes.POINTER(W.DWORD), ctypes.c_void_p]
dll.WriteFile.restype = W.BOOL
dll.SetFileInformationByHandle.argtypes = [W.HANDLE, ctypes.c_int, ctypes.c_void_p, W.DWORD]
dll.SetFileInformationByHandle.restype = W.BOOL
bad = ctypes.c_void_p(-1).value
handles = []
def opening(path, access, share, disposition=3, flags=0x00200000):
    value = dll.CreateFileW(str(path), access, share, None, disposition, flags, None)
    if value == bad:
        raise ctypes.WinError(ctypes.get_last_error())
    handles.append(value)
    return value
def close(value):
    dll.CloseHandle(value)
    handles.remove(value)
def links(value):
    info = _FileStandardInfo()
    if not dll.GetFileInformationByHandleEx(value, 1, ctypes.byref(info), ctypes.sizeof(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return int(info.links)
def rename(value, target):
    name = str(target)
    class Rename(ctypes.Structure):
        _fields_ = [("flags", W.DWORD), ("root", W.HANDLE), ("length", W.DWORD),
                    ("name", ctypes.c_wchar * (len(name) + 1))]
    info = Rename()
    info.flags, info.root, info.length, info.name = 1, None, len(name.encode("utf-16-le")), name
    ok = dll.SetFileInformationByHandle(value, 3, ctypes.byref(info), ctypes.sizeof(info))
    return {"success": bool(ok), "winerror": 0 if ok else ctypes.get_last_error()}
out = {"run_id": "GT02-S27-WINDOWS-WRITE-DIAGNOSTIC-03",
       "timestamp_utc": datetime.now(timezone.utc).isoformat(),
       "os": platform.platform(), "python": platform.python_version(),
       "scope": "disposable TEMP sandbox; synthetic data only; no production calls"}
with tempfile.TemporaryDirectory(prefix="gt02-s27-safe-write-") as tmp:
    base = Path(tmp).resolve()
    base.relative_to(Path(tempfile.gettempdir()).resolve())
    assert base.name.startswith("gt02-s27-safe-write-")
    root, outside = base / "project", base / "outside"
    root.mkdir()
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_bytes(b"untouched-original-sentinel")
    try:
        parent = opening(root, 0x80, 1, flags=0x02200000)
        child = root / "created-while-parent-held"
        child.write_bytes(b"synthetic-child")
        child.unlink()
        try:
            root.rename(base / "moved")
            parent_rename = "ALLOWED"
            (base / "moved").rename(root)
        except OSError as error:
            parent_rename = error.winerror
        out["parent_handle"] = {"child_create_delete_allowed": True, "parent_rename_winerror": parent_rename}
        list_handle = opening(root, 1, 1, flags=0x02200000)
        try:
            root.rename(base / "moved")
            out["list_directory_handle_rename"] = "ALLOWED"
            (base / "moved").rename(root)
        except OSError as error:
            out["list_directory_handle_rename"] = error.winerror
        close(list_handle)
        stage, alias = root / "stage", outside / "stage-alias"
        handle = opening(stage, 0xC0010000, 0, 1)
        before = links(handle)
        os.link(stage, alias)
        after = links(handle)
        reader = dll.CreateFileW(str(alias), 0x80000000, 7, None, 3, 0x00200000, None)
        read_error = ctypes.get_last_error() if reader == bad else 0
        if reader != bad:
            dll.CloseHandle(reader)
        payload = b"synthetic-stage-payload"
        buffer, count = ctypes.create_string_buffer(payload), W.DWORD()
        assert dll.WriteFile(handle, buffer, len(payload), ctypes.byref(count), None)
        close(handle)
        out["hardlink"] = {"links_before": before, "links_after": after, "alias_read_while_held_winerror": read_error,
                           "bytes_written": count.value, "alias_bytes_equal_after_close": alias.read_bytes() == payload}
        alias.unlink()
        stage.unlink()
        close(parent)
        source, target = root / "rename-source", root / "rename-target"
        source.write_bytes(b"new-data")
        target.write_bytes(b"old-data")
        source_handle = opening(source, 0xC0010000, 0)
        target_handle = opening(target, 0x80000000, 1)
        out["replace_target_no_delete_share"] = rename(source_handle, target)
        close(target_handle)
        target_handle = opening(target, 0x80000000, 5)
        out["replace_target_with_delete_share"] = rename(source_handle, target)
        close(target_handle)
        out["replace_target_closed"] = rename(source_handle, target)
        close(source_handle)
        out["renamed_target_bytes"] = target.read_bytes().decode("ascii")
        out["original_outside_sentinel_unchanged"] = sentinel.read_bytes() == b"untouched-original-sentinel"
    finally:
        for handle in list(reversed(handles)):
            close(handle)
out["native_handles_closed"] = len(handles) == 0
out["temporary_root_removed"] = not base.exists()
print(json.dumps(out, indent=2))
~~~

Report-only result: **existing mutation UNSUPPORTED remains correct; private namespace, parent stability and destination identity publication remain unresolved gates.**

