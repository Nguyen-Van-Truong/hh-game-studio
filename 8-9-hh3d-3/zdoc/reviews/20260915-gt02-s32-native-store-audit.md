# GT-02 S32 native store — adversarial design preparation

2026-09-15, Asia/Saigon. `PREPARATION_ONLY=1`, `INDEPENDENT_ACCEPTANCE=0`,
`AUTHORITY=0`, `TICK=no`. Read-only source/evidence inspection and primary
Microsoft documentation research; no runtime probe, test, engine or worker was
launched. Only this new report was written. Existing S30 verdicts remain immutable.

The smallest defensible experiment is a broker-owned, fresh-name immutable
blob store in a proven private local NTFS namespace. A successful retained-handle
write is useful implementation evidence, but does not by itself satisfy TX15,
authorize consumer mutation, or establish atomic replacement. Preserve the public
`safe_write=false` / `atomic_replace=false` gates until the complete contract is
proved. The current implementation correctly keeps these gates closed.

## Inspected boundary

Inspection HEAD: `52def92255c3639a75f154eb6e0c168edcb83b70`; the first `git status
--short` was empty. SHA-256 values below bind the bytes inspected, not a frozen S32
candidate or subsequent coordinator changes. Paths are relative to `8-9-hh3d-3/`.

| Input | SHA-256 |
|---|---|
| `studio/host/core/safe_open.py` | `efc083f1c4fa875d3f748602924a05712aa60fed3abcdb46d058672930201535` |
| `studio/protocol/core.py` | `e8153f5a4dcf639f4d1cbce2fa74f7866d963a692c68e4e8d1477136889bd93e` |
| `studio/host/core/limits.py` | `9d01ce56f5976bb034e60e33bf4b7986cdc44b3a8ffad46da738a6ed1b143f3f` |
| `zdoc/8-9-godot-blender-agent-studio-plan.txt` | `73dce0041b048238fc03ad5bdf5c4b7ff307141bfc5ca0c21820bc5e5f8d67b6` |
| `zdoc/reviews/20260915-gt02-s30-windows-probe/handle_publish_probe.py` | `9d86e838a48737e583689898d5149d8bfebf7024ea81902c55b752de5610c43e` |
| `zdoc/reviews/20260915-gt02-s30-windows-probe/restricted_acl_probe.py` | `f9e47ca27de4189d298d2822c1f4af0db9ed1aae809e5db366c7aa0398d3fb30` |
| `zdoc/reviews/20260915-gt02-s30-windows-probe/handle-publish-06.stdout.json` | `51f99bce8385104e8479e20aaece336ce3cbd821a552e73e5bb1779b5d07cf34` |
| `zdoc/reviews/20260915-gt02-s30-windows-probe/restricted-acl-05.stdout.json` | `e52dcc2d8b9067059fc82b91dc0d505b069d2f280458a09cc2e963e67216c4bd` |

Plan §2.2 lines 336–347 requires protection at use time, private staging, retained
OS identity/final-path checks and rejection of links/aliases; lines 355–358 require
lease/revision/dedupe/readback/checkpoint/token before the first consumer mutation.
GT-02 lines 534–547 explicitly retains the safe-write availability gap. TX15 lines
842–845 requires adversarial swaps across validate/open/replace with no outside
mutation or secret leakage. An experimental API behind a closed capability does
not discharge those requirements.

`safe_open.py:96–137` supplies useful Windows read-handle inspection;
`:187–209` retains ancestor handles during an operation; `:235–246` rejects every
write API. `limits.py:242–248` and `core.py:425–438` explicitly state that a
resolved `Path` grants no mutation authority. Keep that separation.

## Prioritized design hazards

1. **P1: a checked path, DACL string or share mode is not namespace authority.**
   S30's ordinary broker token obtained zero-access handles and made native links;
   its write-restricted token deleted and renamed private descendants. A handle
   acquired before restriction still wrote afterward. A DACL granting the current
   user full access cannot distinguish another unrestricted process of that user.
   Such a process is broker-equivalent unless a separate OS boundary excludes it.
   Restricting the broker's thread temporarily is not a hostile-worker boundary.
   `WRITE_RESTRICTED` limits the second SID check to write access, as documented by
   [CreateRestrictedToken](https://learn.microsoft.com/en-us/windows/win32/api/securitybaseapi/nf-securitybaseapi-createrestrictedtoken).

2. **P1: link-count sampling cannot repair an untrusted namespace.** A transient
   external hardlink between checks can return the count to one. That is a link
   escape, even if a new data-read handle remains blocked by sharing. S30 does not
   prove that such a read bypasses share mode; test it separately. Hardlinks share
   a file's security descriptor and underlying contents. Prevent unauthorized
   link creation, including native zero-access-handle routes, rather than relying
   only on detecting an extra link later.
   [CreateHardLinkW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createhardlinkw)

3. **P1: rename success is neither expected-target CAS nor durable commit.** S30
   changed a destination's file ID after closing its checked handle; replacement
   then succeeded. Neither rename structure accepts an expected destination ID.
   Use `replace=false` for this experiment and preserve both files on collision.
   Do not close a checked existing target and infer it stayed unchanged.
   [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)

4. **P2: the diagnostic wrapper is not ready for direct promotion.** Its write
   path uses one `WriteFile`, its reader has a fixed 4096-byte buffer, and security
   conditions use Python `assert`. Rename allocation uses `len(name)+1` WCHARs
   while the native length uses UTF-16 bytes; supplementary characters need a
   units-based allocation. Safety must survive `python -O`. These are constraints
   to address in the new implementation, not acceptance findings against the
   explicitly diagnostic S30 script.

## Minimal validation sequence

**A. Establish namespace authority before creating bytes.** A broker factory
should mint a fresh directory with a protected DACL at creation and retain its
handle/identity. Do not adopt an arbitrary existing directory because its current
ACL appears restrictive, or accept `trusted=True` / a manifest field as proof.
Preexisting handles and inherited capabilities would survive that observation.
For experimental trusted-broker-only runs, declare that boundary explicitly;
connecting an untrusted worker requires proof of its actual primary token,
restricted access, handle inheritance/duplication exclusion and lifecycle.

Read owner/group/DACL from retained handles using `GetSecurityInfo` with
`READ_CONTROL`. Require the expected owner and a non-null, protected, strictly
allowlisted DACL on the store, staging/release directories and created files.
Reject unknown ACE types, unreviewed inheritance, broad principals or failed
descriptor queries. Prefer matching a small parsed descriptor policy over trying
to infer safety from arbitrary ACLs. Descriptor readback itself is a snapshot,
not a lock against concurrent security changes.
[GetSecurityInfo](https://learn.microsoft.com/en-us/windows/win32/api/aclapi/nf-aclapi-getsecurityinfo)

Account for worker user/groups/restricting/package SIDs and owner rights, not just
its display SID. Deny untrusted data/append/attribute/EA writes, `DELETE`,
`WRITE_DAC`, `WRITE_OWNER`, and parent `FILE_ADD_FILE`, `FILE_ADD_SUBDIRECTORY`,
`FILE_DELETE_CHILD`. Verify the boundary on relevant ancestors too; a protected
child DACL does not establish the parent's deletion policy. Also exclude borrowed
broker handles/tokens and privileges capable of bypassing that boundary.
[File access rights](https://learn.microsoft.com/en-us/windows/win32/fileio/file-access-rights-constants)

**B. Bind path policy to retained OS objects.** Use generated bounded basenames
for the first store, not client filesystem paths. Retain every ancestor needed by
the chosen path-based `CreateFileW` operation, validate reparse/type/final spelling
and identity, and prohibit untrusted namespace changes throughout. The final
component's `OPEN_REPARSE_POINT` flag alone is insufficient ancestor policy.
Keep lexical rejection of traversal, UNC/device/ADS, empty/dot components,
case/short-name aliases and trailing dots/spaces. No normalization should silently
turn a rejected client spelling into authority.

Query the filesystem from a retained handle with
`GetVolumeInformationByHandleW`: require NTFS, persistent ACL support, writable
local-volume provenance and the expected volume; reject unknown/remote/non-NTFS
results. Compare identities using the same `FileIdInfo` representation, not a
32-bit volume API serial against its 64-bit field. Use bounded normalized final
path queries, ideally also binding the volume GUID, rather than trusting a drive
letter alone. Any unavailable required query means unsupported.
[Volume information by handle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationbyhandlew),
[Final path by handle](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew)

**C. Create exactly once and retain the returned handle.** Use `CREATE_NEW`,
explicit secure `SECURITY_ATTRIBUTES` with `bInheritHandle=false`, synchronous
I/O, `OPEN_REPARSE_POINT`, and no write/delete sharing. Start with share mode 0
for the blob. Request read/write plus `READ_CONTROL`; request `DELETE` only if
retained-handle rename is implemented. Do not return raw writable handles or
Paths to consumers. Fail on collision; never retry with `OPEN_ALWAYS`, truncate,
path copy, or replacement. The descriptor must apply at creation, not after an
initial permissive interval.
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

Immediately inspect the file: expected regular disk file, no reparse tag/attribute,
not delete-pending, one link, zero initial length, exact staged final path and
same volume as its trusted directory. Record `(volume, FileId128)` as identity.
Compare identity independently of size: zero-to-payload-length is an intended
transition. After each phase require the identity unchanged and the expected
size, rather than treating size as immutable file identity.
[FILE_ID_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info),
[FILE_STANDARD_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_standard_info)

**D. Write, flush, read back, seal.** Freeze a bounded bytes payload before I/O.
Check each `WriteFile` BOOL and count; a positive short write may either advance
exactly that count within bounded work, or poison/fail without a staged result.
Zero progress or count greater than remaining is failure. Never restart a partial
write at offset zero as an implicit retry.
Use explicit exceptions, not assertions. Flush only after the full payload and
check `FlushFileBuffers`. Reset the same handle's pointer, read bounded chunks to
exact length plus an EOF check, and verify bytes/hash, metadata and identity again.
Empty payload still needs create/flush/readback inspection. A positive write count
or matching immediate readback alone is not a commit.
[WriteFile](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-writefile),
[FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)

**E. If publishing by rename, keep it create-only.** S30 observed native relative
rename success with a retained destination directory opened LIST+ATTRIBUTES and
share READ|WRITE, no DELETE; its Win32 form returned error 87. Do not silently
broaden production sharing or switch to absolute-path replacement. Validate the
chosen ABI, architecture, source `DELETE` access and destination rights. Native
relative names must be a single basename and remain on the same volume; calculate
buffer size from UTF-16 code units and checked offsets, and set only supported
flags. Missing APIs, unhandled NTSTATUS, or pending completion cannot be success.
[FILE_RENAME_INFORMATION](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/ns-ntifs-_file_rename_information),
[NtSetInformationFile](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntifs/nf-ntifs-ntsetinformationfile)

After rename, the same source handle must have its original volume/ID, one link,
expected size/hash, no reparse/delete-pending state, and the exact published path.
Reinspect parent identities and descriptors; verify the old name is absent and
destination lookup resolves to that identity under the still-protected namespace.
Share mode 0 prevents an ordinary second data-read open while retained; do not
weaken it merely to make a readback test pass. A post-close reopen belongs to a
separate namespace-authority/recovery check.

**F. Keep storage outcome separate from protocol outcome.** An unpublished blob
is not an activated project revision. Namespace denial before a fresh command's
admission can reject; an error after writes/rename, or before recovering an
existing command's history, must not become a blanket no-effect rejection.
Preserve diagnostic phase, identity and hash and require reconciliation; uncertain
publication is `UNKNOWN`. Do not delete a possibly published object by pathname
as generic cleanup. Data flush plus rename/readback does not establish a journaled
crash/restart or power-loss guarantee. Prove recovery/barrier ordering and durable
terminal results before a public `COMMITTED` response.

## Must-run fault matrix after implementation, before any activation

These are proposed tests, none executed by this audit. Fault injection supplements
real Windows adversarial processes; mocks cannot prove ACL or filesystem isolation.

| Case | Required observation |
|---|---|
| Arbitrary existing root; forged trusted flag; changed owner/null or inherited broad DACL; unreadable descriptor; FAT/ReFS/SMB | Reject before blob creation; no fallback or capability enablement. |
| Ancestor junction/reparse/rename swap before open and after validation; drive/short/case/ADS/device aliases | No outside write; rejection or pinned authorized object, with identity evidence at each phase. |
| Directory held with attributes only versus LIST+ATTRIBUTES; broad parent delete-child right | Positive controls expose insufficient locking/policy; supported route blocks actual hostile mutation. |
| Same unrestricted token attempts native zero-access link; actual restricted worker tries Win32/native links and link insert/remove between checks | Broker-equivalent positive control may succeed and must never qualify as isolation; supported worker is denied before alias creation. No invented read-exfiltration claim. |
| Worker `OpenFileById` with a scratch-volume hint; inherited/duplicated file/directory/process/token handles; handle acquired before restriction | Denied or admission blocked. Hiding names is insufficient: any file on the volume can provide the documented hint. [OpenFileById](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-openfilebyid) |
| Worker changes file ACL/owner/attributes, deletes child, renames ancestor, or accesses blob after broker close | Denied throughout lifecycle; actual token and completion marker captured, not impersonation-only assertions. |
| Write returns partial positive, zero, impossible count, false after earlier bytes, disk-full, or aborted I/O | Exact loop offsets; bounded failure; no false seal/commit, no implicit second creation. |
| Flush, pointer reset, read, EOF, hash, identity, link count or final-path query fails after write | No successful result; phase retained; private partial artifact quarantined/reconciled using owned identity. |
| Empty/exact-limit/over-limit payload; BMP and supplementary names; invalid surrogate; Python optimized mode | Bounds enforced before I/O; correct UTF-16 layout or explicit name rejection; safety unchanged under `-O`. |
| Create/publish collision; cross-volume target; existing target swaps after check; rename error or synthetic pending NTSTATUS | Both known objects preserved on collision; no replace fallback; no false successful publication. |
| Kill/restart at create, partial write, pre/post flush, pre/post rename, post-readback, journal terminal barrier, lost response | Lookup/retry returns reconciled original result or UNKNOWN; no duplicate blob effects, lost terminal result or ACK for unproven durability. |
| Public discovery/dispatch receives any experimental store operation or toggled legacy flag | Existing capability/schema gates still reject; no raw path/handle exposed, no engine consumer activated. |

Implement the namespace factory and its negative policy tests first, then retained
create/write/flush/readback with injected failures. Add optional create-only
publication and restart reconciliation next. Only a later frozen candidate with
real OS adversaries, journal integration, complete evidence and independent
critics can revisit GT-02 acceptance. Existing-target replacement and GT-03/04
consumer activation are outside this preparation.

## Coordinator-requested review of the new draft

This additional static review covers `studio/host/core/private_store.py` SHA-256
`f1b40040b7a2430d48cfb75504a1b88d02ad1793c70279a306988467ce11453f`
and `studio/tests/protocol/test_private_store.py` SHA-256
`a8bf1bd9cf9b4bc23634a11b0b64e064be2076fb32f544da5be3ed30a1e05a22`.
The coordinator is actively editing these files; these are inspected draft bytes,
not a freeze or the final implementation. No reported test count is independently
validated here.

The draft deliberately exposes no transport operation or activation. It creates
private roots/files with explicit protected owner DACLs, holds a share=0 writer
guard, validates root/blob identity and security, caps bytes/object count, fails a
short write without replay, and compares same-handle bytes/hash after flush. The
inspected revision also checks NTFS before mkdir, classifies failures after root
creation as uncertain, and rechecks ancestor/guard identity before operations.
Those choices fit the proposed experiment's limited scope.

**Actionable P2: ancestor close failures are still untracked.** The owned-handle
registry in `_StoreApi.close_owned` covers store root/guard/blob handles, but
`PrivateBlobStore.__init__` obtains its retained ancestor chain from a separate
`SafeFileAccess._api`. That object's `_WindowsApi.close` (`safe_open.py:110–111`)
ignores the native BOOL. An injected false return without actually closing an
ancestor can therefore be silently discarded by `_parents`/`ExitStack`; the store
can finish close while the directory remains held. Track and verify closure of
all owned handles, including ancestor handles and constructor-failure cleanup,
without broad cleanup or guessed handle ownership. Preserve failure status and
owned resources for explicit cleanup/reconciliation. A test that invokes the real
close and then raises does not exercise a handle that remains open.

**Required close/phase tests still missing from the inspected test file:** inject
failure before actual close separately for blob, root, guard and an ancestor;
prove a second cleanup can account for every still-owned handle, and that normal
closing does not falsely report leftover zero. Cover `read_blob` and quota-scan
close failures as well as `put_bytes`. Add constructor faults after mkdir and
after guard create, asserting the new directory is preserved with uncertain
outcome; unsupported volume must leave the parent unchanged. Do not blindly retry
an invalid/unowned numeric handle: record the native error and retain ownership
discipline. These tests must cover native-return behavior, not only exceptions
raised after successful OS calls.

**Recovery boundary:** `reopen(root, expected_root)` proves a root identity and
acquires the guard; it does not prove that a previous poisoned/crashed instance
was reconciled. `_check_quota` accepts correctly named/secured partial blobs within
size limits and a new instance starts unpoisoned. This is consistent only with the
module's explicit absence of automatic recovery. Require trusted broker recovery
state before exposing it to an activation flow; do not count the fresh-process
readback test as crash recovery or safe retry after a failed put.

**Namespace boundary:** root/file owner+DACL checks are concrete, while ancestor
inspection currently checks identity/path/reparse state, not effective ancestor
ACL authority. The draft's documented exclusion of unrestricted same-account
peers and requirement that all untrusted workers be OS-confined remain external
preconditions. Rechecks and the observed `os.link` sharing violation do not prove
those preconditions. The proposed actual-worker/native-link/parent-rights tests
remain necessary before broadening capability. This report supplies design
feedback only and leaves GT-02/TX15 acceptance open.
