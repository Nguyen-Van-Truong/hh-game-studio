# GT-02 S30 — Windows safe-write feasibility observations

Date: 2026-09-15, Asia/Saigon. `REPORT_ONLY=1`, `AUTHORITY=0`, `TICK=no`.

**Disposition: `UNSUPPORTED_SAFE_OPEN_WINDOWS` remains required.** S30 proves useful ACL and retained-handle API behavior on this host. It also disproves using `WRITE_RESTRICTED` alone to protect the namespace: the restricted caller still deleted and renamed private files. A real restricted Python child was created, but exited before its completion marker. This is not sandbox, safe-write, atomic-replace, GT-02 acceptance, or GT-03/04 consumer authorization.

Only this report, adjacent scripts/logs, and synthetic owned TEMP fixtures were written. No production source, plan, existing user/system ACL, account, privilege policy, AppContainer profile, service, or engine was changed; no commit or tick was authorized for this assignment. The starting Git HEAD was `642d6f51158054a40862497c92d771512e8729d0`, with coordinator changes already present. `studio/host/core/safe_open.py` remained SHA-256 `efc083f1c4fa875d3f748602924a05712aa60fed3abcdb46d058672930201535` before and after the probes.

## Public derivative provenance

Before Git packaging, the coordinator retained every original report/artifact byte
under ignored `studio/.local/review-raw/20260915-gt02-s30-windows-probe/` and removed
absolute host paths from these public copies. `redaction-ledger.json` binds original
and derived hashes. Probe scripts retain their runtime behavior; the coordinator
changed the stored-evidence verifier to check the pinned manifest rather than
regenerate it. This derivative is not a new probe run or independent verdict.

## Evidence and host boundary

Final observations are in [restricted-acl-05.stdout.json](20260915-gt02-s30-windows-probe/restricted-acl-05.stdout.json) and [handle-publish-06.stdout.json](20260915-gt02-s30-windows-probe/handle-publish-06.stdout.json), paired with `.host.json` and empty `.stderr.txt`. Both parent probe exits were captured by `subprocess.run(..., timeout=30)` and were **0**. Exit 0 means these diagnostics completed; the nested worker failure below remains a failure.

Host: Windows build `10.0.26200`, x64 Python `3.11.9`, NTFS on the owned TEMP volume. Each fixture used fresh names. The child used suspended creation, no inherited handles, a Job Object with kill-on-close, active-process limit 1, 128 MiB memory limit, and a 10-second wait. No global desktop/console setting was changed.

[source-manifest.json](20260915-gt02-s30-windows-probe/source-manifest.json) records exact scripts, relevant logs, Python executable and production read-only input hashes. Script manifest digest: `1f20fc4d20c22bf7336dafe58ab0dda43b36a857abd435df8b480d52096b7ef7`.

| Script | SHA-256 |
|---|---|
| `restricted_acl_probe.py` | `f9e47ca27de4189d298d2822c1f4af0db9ed1aae809e5db366c7aa0398d3fb30` |
| `win_process.py` | `a5196a6c4e7e017067913831206852838162258eff0e3e7505a4cb39b61a527e` |
| `handle_publish_probe.py` | `9d86e838a48737e583689898d5149d8bfebf7024ea81902c55b752de5610c43e` |
| `verify_evidence.py` | `85b271afbc2103f6dbbb072bbd85675db4b6789005e58070585d644b2c573845` |

Repro from repository root, each command separately:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260915-gt02-s30-windows-probe/verify_evidence.py
python -c 'import subprocess,sys; subprocess.run([sys.executable,"-B","8-9-hh3d-3/zdoc/reviews/20260915-gt02-s30-windows-probe/restricted_acl_probe.py"],timeout=30,check=True)'
python -c 'import subprocess,sys; subprocess.run([sys.executable,"-B","8-9-hh3d-3/zdoc/reviews/20260915-gt02-s30-windows-probe/handle_publish_probe.py"],timeout=30,check=True)'
```

The first command checks the saved observations without launching a child or mutating a fixture. Future captured reruns must use new evidence filenames/run IDs and freeze their exact source closure; do not overwrite this package.

## ACL/token matrix

Directories were created atomically with protected DACLs. Private objects granted the broker user full access plus an OWNER RIGHTS read-control ACE; scratch additionally granted a fresh, unassigned synthetic restricting SID. Actual owner/group/DACL readback for the directories and source file is in the JSON. No Windows account was created for that SID.

The two token modes used `CreateRestrictedToken`: flags `1` (full restriction with maximum privileges removed) and `9` (the same plus `WRITE_RESTRICTED`). Tests in this table used impersonation; they do **not** establish process isolation. Microsoft documents the second restricting-SID access check, the privilege exception for `SeChangeNotifyPrivilege`, and the write-only meaning of `WRITE_RESTRICTED`. [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken)

| Attempt against synthetic private source/namespace | Ordinary broker token | Full restricted token | Write-restricted token |
|---|---|---|---|
| Open zero-access / attributes / read | Success | Denied 5 for all | Success |
| Open `GENERIC_WRITE`, `WRITE_DAC`, `WRITE_OWNER` | Success | Denied 5 | Denied 5 |
| Open `DELETE` | Success | Denied 5 | **Success** |
| Create a private child | Not attempted | Denied 5 | Denied 5 |
| `DeleteFileW` private canary | Not attempted | Denied 5 | **Success; absence read back** |
| `MoveFileExW` private canary to scratch | Not attempted | Denied 5 | **Success; destination bytes read back** |
| `CreateHardLinkW` to scratch | Success | Denied 5 | Denied 5 |
| Native hardlink using a zero-access source handle | Success | No handle obtainable | Denied `0xC0000022` |
| Create scratch positive-control file | Success | Success | Success |
| Open broker process for handle duplication / VM write / remote-thread creation | Not attempted | Denied 5 | Denied 5 |

The ordinary token created two aliases; the final source link count was **3**, intentionally. Therefore the ACL fixture is not evidence that a user-owned directory excludes another unrestricted process of the same user. Hardlinks share the underlying file security descriptor. [CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw)

Two additional controls matter:

- A write handle acquired before full restricted impersonation still wrote six bytes; broker readback was `AFTER!`. Restriction is not revocation of an existing handle. No such handle was inherited by the attempted worker.
- An unheld private directory could be renamed under write-only restriction. Holding it with `FILE_LIST_DIRECTORY|FILE_READ_ATTRIBUTES` and no delete sharing changed the outcome to sharing violation 32. Its descendants still remained deletable/renameable under write-only restriction. The fixture field `directory_parent_delete_child_controls` names the experiment; it does **not** isolate which parent/child ACE granted deletion.

**Primary process execution remains unproven.** `CreateProcessAsUserW` created PID 20372 with the expected restricted primary token and one remaining privilege, as inspected by the host before resume. It then exited `3221225794` / `0xC0000142`, with no child result or completion marker. Microsoft labels this `STATUS_DLL_INIT_FAILED`; S30 did not identify the failing DLL or infer a sandbox success from it. Job accounting showed active processes **0**, total processes **2**; the latter was not investigated and is not evidence of a second successfully running worker. [NTSTATUS values](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55)

The launch used the default desktop for a fixed trusted diagnostic only. Microsoft recommends a different desktop for restricted applications to avoid window-message attacks. That requirement remains unresolved for production. [Restricted Tokens](https://learn.microsoft.com/en-us/windows/win32/secauthz/restricted-tokens)

## Retained-handle publish matrix

The publish probe used fresh source handles with read/write/DELETE access and share mode 0; no source-path reopen was used for rename. It read volume/file ID, link count, reparse tag and final handle path, wrote bounded bytes, called `FlushFileBuffers`, and hashed a readback through the same source handle.

| Test | Observed result |
|---|---|
| Win32 `SetFileInformationByHandle(FileRenameInfo)` with destination `RootDirectory` and relative basename | **Error 87** on this host; no publish |
| Native `NtSetInformationFile(FileRenameInformation)` with retained destination directory, directory share READ only | **Sharing violation 32** in exploratory runs 03/04 |
| Same native operation, directory access LIST+ATTRIBUTES, share READ+WRITE but no DELETE | **Success** in final run 06 |
| Source identity across create-only publish | Same volume and file ID; link count 1, reparse tag 0; source name absent; final path matches Unicode basename |
| Source/readback SHA-256 before and after publish | Both `bb618baed5f264ed1a5d53b527b1234faa01583a1de34ec0f3069e9eaf2d7ce5` |
| Publish to existing destination with `replace=false` | Collision 183; both source and destination preserved |
| `replace=true` while destination handle held | Access denied 5 |
| Close destination, swap it using the same token, then retry replacement | **Success despite changed destination ID** |

The final swap experiment is deterministic sequencing on synthetic canaries, not concurrency fuzzing. It demonstrates why closing a checked target and then replacing it is not expected-identity CAS. Neither rename structure supplies an expected target file-ID parameter. Native relative rename success is a feasibility observation, not a supported product wrapper. [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info), [FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information), [NtSetInformationFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntsetinformationfile)

The necessary READ+WRITE directory sharing also leaves additional modification rights to be controlled by the isolation boundary. S30 does not recommend loosening production handles on the strength of this success. `FlushFileBuffers` plus immediate readback is not a crash/restart or power-loss proof of durable namespace publication.

## Most efficient next prototype

1. Keep the current fail-closed production capability. Discard `WRITE_RESTRICTED` as the sole namespace boundary. First prove a distinct **running** worker token, its effective broker/scratch ACLs, a completion marker and owned-process termination before implementing a writer.
2. A bounded **profile-free AppContainer** probe is a reasonable next experiment: derive a unique SID, pass zero capabilities through `PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES`, and run fixed synthetic commands with explicit scratch ACL and Low mandatory label. The API documents AppContainer process creation from the security attribute; it does not establish that SID derivation alone proves profile-free activation or no OS side effects. Record the unique package path/mapping absence before and after read-only; do not silently fall back to profile creation. This assignment did not run it. [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute), [DeriveAppContainerSidFromAppContainerName](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deriveappcontainersidfromappcontainername)
3. Once isolation runs, keep the broker as the sole writer and test immutable fresh-name, create-only publish. Reuse the native relative-rename measurement only behind a test-only platform probe with explicit rights/error handling. Verify every ancestor, actual child descriptors, file IDs, hashes, single link and post-publish final path. Add real restricted adversarial hardlink, reparse/junction swapping, `OpenFileById`, handle-duplication/inheritance, deletion and ancestor-rename tests. `OpenFileById` accepts any file handle on the volume as its hint; hiding names alone is not a boundary. [OpenFileById](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-openfilebyid)
4. Then add broker authentication/schema/lease/fencing/journal, crash points and restart reconciliation, followed by two independent exact-source reviews. Existing-target replacement stays unsupported until namespace authority and expected revision/identity recovery are proven. Do not send live Godot/Blender project mutations through this report prototype.

Not tested here: AppContainer execution, real full-restricted worker execution, network/IPC denial, reparse or junction swapping, file-ID opens, actual cross-process handle duplication, desktop isolation, concurrent adversaries, complete ancestor containment, remote/non-NTFS filesystems, crash/restart durability, or adapter mutations. The source retains `safe_write=false` and `atomic_replace=false`.

## Diagnostic history and cleanup exception

Exploratory logs are preserved. Restricted run 02 exposed namespace movement before robust result capture. Run 03 failed while collecting a missing child result and its directory lock outlived the temporary-directory cleanup scope; the final script closes file handles first with `ExitStack`. Publish runs 01–04 record assertion failures/API incompatibilities while the sharing matrix was being established. Final restricted run 05 and publish run 06 independently removed their own fixtures. No earlier failed run is promoted to acceptance.

**Global `leftover=0` is false.** One earlier owned path remains: `[TEMP]\gt02-s30-restricted-acl-y920imcz`. Read-only inspection showed `private/`, `scratch/`, and six synthetic scratch entries: `full_restrict-positive-create`, `unrestricted-native-link`, `unrestricted-positive-create`, `unrestricted-win32-link`, `write_restrict-positive-create`, `write_restrict-renamed`. No matching probe Python process remained during final process inspection. Do not treat the two final runs' cleanup flags as proof that this older directory was removed.

Automatic approval review rejected both cleanup of this exact owned TEMP tree and a subsequent narrower non-recursive list of its exact files/directories; the only stated reason was **“blocked by policy.”** No cleanup was retried through another tool or shell. The coordinator was informed and retained this cleanup gap.
