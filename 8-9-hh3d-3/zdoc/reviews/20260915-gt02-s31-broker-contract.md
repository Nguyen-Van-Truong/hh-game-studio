GT-02 Windows broker contract — report-only design input, 2026-09-15

AUTHORITY=0
PROPOSED_ONLY=1
PRODUCTION_SAFE_WRITE=UNSUPPORTED_SAFE_OPEN_WINDOWS
ACCEPTANCE=NONE

Use an actual primary AppContainer process for untrusted work, and a small
trusted broker that creates its own files from bounded IPC bytes. Do not adopt
worker paths, file objects or handles into the broker namespace. First prove
immutable create-only publication, then separately prove active-manifest
expected-identity/revision publication and recovery. Neither step, nor this
report, changes S30's FAIL/TICK=no or satisfies §2.2/TX15 by declaration.

The examined S30 diagnostics are
20260915-gt02-s30-windows-probe/handle-publish-06.stdout.json,
restricted-acl-05.stdout.json and verification.json. They report NTFS on Windows
build 26200; native root-relative create-only rename preserved source identity
and rejected collisions, but replacement after a same-token destination swap
still succeeded. Win32 root-relative publish returned error 87 in that probe.
Write-restricted impersonation still deleted/renamed; full restriction blocked
new protected opens, but a preexisting handle still wrote. The primary restricted
child exited 0xC0000142 without its result marker. AppContainer and OpenFileById
were not tested. These are useful counterexamples, not sandbox or durability
acceptance. The older denied cleanup remains recorded; two cleaned current
fixtures do not prove global leftover-zero.

Smallest trust and resource contract:

1. One broker owns a private root, its immutable release store, active manifest,
   command journal and a permanent single-writer guard. One untrusted worker
   starts with a distinct per-run AppContainer SID, zero optional capabilities,
   sanitized environment, explicit scratch/current directory and read-only
   staged input copies. The broker pins the Windows build and local NTFS volume
   actually tested; other filesystems, UNC/SMB and cross-volume publication
   remain unsupported. All untrusted adapter/code execution goes through this
   boundary; no unrestricted fallback after launch failure. Unpackaged legacy
   programs can use AppContainer, and the primary token can be queried for the
   AppContainer property. [Microsoft AppContainer for legacy apps](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-for-legacy-applications-)

2. Provision the private namespace before worker launch with a protected,
   explicit DACL; give the worker SID neither file access nor directory
   create/delete-child, rename, WRITE_DAC or WRITE_OWNER rights there. Do not
   grant ALL APPLICATION PACKAGES or the worker a capability covering that
   root. Inspect effective owner/DACL and inherited ACEs on every created
   broker object. Grant the SID access only to its scratch, exact runtime/input
   copies and one IPC endpoint. AppContainer changes access checks; permission
   is resource-specific, and a low integrity label alone is insufficient.
   [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)

   Here “broker-only” is relative to the OS-confined untrusted workers. The
   trusted OS user, administrators and kernel are not adversaries. An ordinary
   user SID shared by unrestricted processes is not a unique broker identity.
   If unrestricted same-user code is inside the intended threat model, a
   separate broker account/service identity and corresponding ACL boundary are
   required before claiming this contract. A secret/random directory name is
   never the access-control mechanism. No direct owner edits to the private
   release/manifest store; user-facing edits enter via revision-checked commands.

3. Create the worker suspended with SECURITY_CAPABILITIES, inspect the retained
   primary process token from the broker (AppContainer SID, integrity,
   capabilities and privileges), assign a kill-on-close Job Object, then resume.
   Use a one-process limit and restricted child-process policy for this minimal
   probe. Record exact executable/dependency hashes and a child completion
   marker plus actual host exit/tree result. A process that fails before its
   marker has proved no worker-side denial. AppContainer creation attributes
   and child-process restriction are documented separately from Job Object
   lifetime/resource control. [Process attributes](https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
   [Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)

4. Start with bInheritHandles=false and no broker file, directory, token,
   process, section/mapping, job, socket or console handles in the worker.
   Prefer a newly connected, ACL-bound local pipe. If a later design needs
   inherited IPC, its exact non-file handle allowlist becomes a separately
   tested launch contract; never switch on general inheritance. Removing
   permissions after handing out a handle does not revoke the original handle's
   access. Test preexisting/inherited handles explicitly rather than trusting
   a restricted-token label. [Process creation and inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/creating-processes),
   [Handle inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/inheritance)

5. Broker IPC accepts the existing typed request envelope and bounded bytes,
   not arbitrary paths, OS flags, access masks, SDDL, capabilities, code or
   handle numbers. Bind the pipe to the expected live process handle/token,
   project, run and session; a supplied PID is not identity. Set explicit pipe
   ACLs, local-only access and bounded framing/timeouts/queue; reserve Stop and
   lookup capacity. Do not grant filesystem rights merely because pipe
   authentication succeeded. Default pipe security is too broad for this use;
   validate the chosen AppContainer pipe namespace on the actual build.
   [Pipe security](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights),
   [Client PID query](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid),
   [App IPC constraints](https://learn.microsoft.com/en-us/windows/apps/develop/communication/interprocess-communication)

6. Receive worker output as data; calculate its byte length and hash inside the
   broker. Validate operation/schema/domain/size before admission, then keep
   existing lease/fencing, expected revision, command-ID/digest, deadline,
   reservation, checkpoint and UNKNOWN/lookup semantics. The minimal candidate
   operation is “create immutable release”; its target is a broker-minted
   object/release ID. Caller-supplied content hashes are claims to verify, not
   trusted paths. Stream larger outputs under fixed quotas; reject supplied
   filenames, file IDs and live worker handles. Materializing a consumer tree
   from the release is a later validated adapter operation, not an implicit
   import of worker scratch.

7. Pin canonical root/ancestor handles without delete sharing and inspect final
   paths, FileIdInfo, FileStandardInfo and reparse attributes. Create the private
   destination with CREATE_NEW, OPEN_REPARSE_POINT and a fresh broker handle;
   never truncate an existing file. Keep the handle through write, flush,
   readback and publication. Check complete writes and reject type, reparse,
   delete-pending, link-count !=1, volume or identity changes. Broker-minted
   basenames eliminate path parsing at publish; reject ADS, devices, UNC,
   traversal, case/short-name aliases and unapproved Unicode names at admission.
   Sharing flags are lifecycle constraints, not hardlink authorization; ACL
   isolation must prevent worker alias creation before any broker write.
   [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)

8. An immutable release is installed create-only and is never overwritten by
   retry. A destination collision preserves both objects and requires lookup or
   conflict handling; it is not permission to replace. Root-relative retained-
   handle rename is a candidate backend, but the exact API/ABI must be pinned
   and demonstrated; S30's native success does not erase Win32 error 87.
   FILE_RENAME_INFO provides replace/no-replace behavior and an optional root
   handle, but no expected-destination-file-ID comparison.
   [FILE_RENAME_INFO](https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info)

Active manifest is a separate transaction:

Store the current release ID, generation, content hash and predecessor in one
bounded manifest. Activation takes expected generation + manifest content hash
and broker-observed volume/file identity (or explicit absent identity for first
creation). Under the one broker writer guard, recheck those values and current
fence, persist an intent with old/new identities and hashes, create/flush the
new manifest, publish, then reopen/read back the selected release and manifest.
Preserve the old immutable release and recovery record. An arbitrary pathname
replace is not a compare-and-swap.

If the OS replacement call requires releasing or delete-sharing the old target
handle, that transition is permitted only inside the proven private namespace
with all mutators serialized by the broker. Worker denial must remain in force
through that interval. A competing broker command with the old expectation
must reject; an unexpected external identity change is a conflict/GAP. S30
proved why “inspect target, close it, replace by name” without that boundary is
insufficient. Generic atomic_replace remains false until its actual advertised
contract is proved; a successful create-only subset does not close the remaining
§2.2/TX15 activation requirement.

Data and namespace durability are separate proof obligations:

- Use a checked native write-through handle plus explicit FlushFileBuffers and
  readback, and define the namespace commit barrier for both release installation
  and manifest activation. Microsoft documents NTFS metadata flushing associated
  with write-through requests, including rename, and notes that empty-file
  metadata may need FlushFileBuffers. This is a concrete NTFS backend candidate
  to verify, not proof that an arbitrary native rename inherits the guarantee.
  [CreateFileW caching behavior](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
- FlushFileBuffers reports failure and requires an appropriate writable handle;
  flushing a pipe is not file persistence. Its volume-wide flush route requires
  administration. Do not introduce elevation/volume access as an unnoticed
  fallback, or call an invented POSIX-style directory fsync on Windows.
  [FlushFileBuffers](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers)
- MoveFileExW with WRITE_THROUGH is another documented candidate for a proven
  private namespace; it has explicit on-disk/copy-delete flush wording. Forbid
  COPY_ALLOWED and delayed reboot operations. Reconcile its handle-sharing,
  identity and exact same-volume semantics before selecting it. Do not borrow
  its guarantees for NtSetInformationFile. ReplaceFileW's WRITE_THROUGH option
  is explicitly unsupported; its failure outcomes can leave different names.
  [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw),
  [ReplaceFileW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-replacefilew)
- Only after durable release + selected manifest + terminal journal receipt
  and verified readback may COMMITTED be exposed. Any uncertain write, flush,
  rename, readback, close or terminal persistence result stays UNKNOWN and
  closes admission until fresh-process reconciliation. Recovery uses the
  journal and old/new manifest/release hashes, never automatically re-executes
  the old command or silently promotes a cached line. A missing/corrupt selected
  release cannot be acknowledged from a surviving terminal receipt alone.

All of these rows are required before advertising the corresponding v0.1
broker capability; failures must preserve diagnostics and remain explicit.

| Boundary / adversarial case | Required observable result |
| --- | --- |
| Primary launch and DLL/runtime access | Broker sees correct primary AppContainer token; child reaches marker and exits; read-only inputs work. No unrestricted retry, inherited full token or marker-only PASS. |
| Protected file and parent authority | Worker tries zero/read/attribute/write/delete/WRITE_DAC/WRITE_OWNER opens, parent DELETE_CHILD, create, rename and root replacement. No protected-content disclosure, mutation or ACL change; scratch positive control works. |
| Handles and mappings | Broker intentionally has inheritable protected file/section/token/process handles before launch. Production launcher withholds them; worker cannot use guessed/inherited handles or writable mappings. A deliberate control demonstrates that a leaked handle would matter. |
| Process/token escape | Attempt broker OpenProcess rights for DUP_HANDLE, VM_WRITE/OPERATION, CREATE_THREAD, token duplication/assignment/impersonation, RevertToSelf and child/breakaway creation. No broker authority; no unowned process. Broker/worker death closes only owned resources. |
| Reparse/name races | Seed traversal, junction/symlink/reparse, ADS/device/UNC, case/short/Unicode aliases; swap every ancestor/final component before create, write, rename and reopen. Reject or use the original verified object; outside sentinel bytes/identity unchanged. Unsupported test setup is not PASS. |
| Hardlinks and file-ID opens | Attack with Win32 hardlink, native link using zero-access handle, known file ID via OpenFileById, volume/device handles, source/destination aliases and races while broker writes. No new protected link, outside effect or leaked data; every accepted broker object retains link count 1. |
| IPC privilege transfer | Wrong AppContainer SID/process/session/project, forged PID/handle, replayed old token, pipe precreation, remote pipe access, oversized/malformed frames and open-lane/source-instruction payloads reject without rights changes or secret echo. |
| Network and secrets | Zero network capabilities and no loopback exemptions: attempt IPv4/IPv6 loopback, LAN/private/metadata/public targets, DNS, inherited sockets and alternate proxy access. Use owned canary credentials/files only; no secret in environment, argv, logs or crash output; no broker URL-fetch/eval proxy. |
| Create-only release | Complete write/hash/readback, absent destination, same-volume identity continuity, collision and duplicate command under concurrent attempts. One object/effect; no existing object overwritten. |
| Manifest expected identity | Wrong/stale generation, hash, volume/file ID, two competing activations and worker target swap in every handle-release interval. Only the expected generation wins; old release preserved; no uncontrolled namespace writer. |
| Durability/error phases | Inject short/partial write, ENOSPC, flush/rename/close/readback failure and broker termination before/after every data, namespace and journal barrier. Capture actual API return and host exit; fresh process recovers old or fully new state, or explicit UNKNOWN/GAP. No false no-effect/COMMITTED. |
| ACK loss, retention and Stop | Cut IPC before/after every ACK, expire token/lease and retry horizon, fill journal/queue and Stop mid-write/publish. Lookup/retry/archive never duplicates; reserved Stop remains effective; stopped work is not silently resumed. |
| Ownership and cleanup | Bounded Job Object memory/time/process count; observe child exit and job active=0; remove only owned profile/ACL/temp resources after handles close. Failed cleanup recorded; no global-zero claim from a partial inventory. |

OpenFileById accepts desired access and can interact with backup/restore
privileges, so pathname denial alone is not its test. Worker must lack those
privileges and protected volume/file handles. AppContainer's network/credential
isolation is the enforcement starting point; explicit grants and leaked handles
still define the real boundary. [OpenFileById](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-openfilebyid),
[AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)

Implement in this bounded order: prove the current disposable AppContainer
lifecycle and token/ACL/handle denials; add one authenticated bytes-only broker
operation and private CREATE_NEW/readback; prove immutable publication and its
NTFS durability backend; add manifest expectation/intent/recovery; then integrate
the existing GT-02 journal and fault/ACK matrix, freeze the complete source and
run two independent critics. Do not expose mutation between those stages.

Required scope is this Windows fixture boundary and existing protocol safety.
Linux openat2, networked brokers, many-worker scheduling, engine/editor publish
integration, multi-file consumer transactions, full package signing, VM/kernel
exploit defenses and universal filesystem/hardware certification are later
gates, not prerequisites invented here. LPAC and additional exploit mitigations
are follow-up hardening unless an actual access test shows ordinary AppContainer
cannot enforce the required boundary. Physical power-cut testing is distinct
from process-crash testing; do not claim it from the latter. The selected OS,
filesystem and storage flush assumptions must be stated, and uncertainty about
the namespace commit barrier must keep the capability unsupported.

This report performed only document/source/diagnostic inspection. It did not
create a process profile, change an ACL, run a sandbox worker, modify production
source or plan, commit, tick, or assess the concurrent S31 worker's unfinished
probe. Primary documentation was retrieved on 2026-09-15; the proposed contract
and ordering are engineering recommendations, not Microsoft certification.
