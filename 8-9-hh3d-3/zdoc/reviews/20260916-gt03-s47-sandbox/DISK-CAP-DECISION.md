# S47 Windows hard disk-cap decision

AUTHORITY=0. Read-only design finding, 2026-09-16. No virtual disk, quota, mount, account, driver, elevation, installation or shared ACL was created or changed.

**Decision:** the present unprivileged Windows 11 Pro host cannot yet claim a hard bound on arbitrary Godot scratch writes. Keep arbitrary submitted script/importer execution disabled. The smallest practical candidate is an externally provisioned, fixed-size, dedicated sandbox volume, with every child-writable storage surface confined to it or explicitly denied. Ordinary trusted GT03 editor fixtures can continue on isolated projects.

## Why the current controls are insufficient

The actual startup diagnostic configured memory, CPU, wall time and child/process limits. None bounds total disk allocation. Its periodic 16 MiB scratch scan is advisory: a process can write more between scans, `.godot` is elsewhere, sparse/alternate-stream/metadata behavior differs from ordinary file-size sums, and inherited handles bypass path checks. The child also has a per-app profile with folders and registry storage; changing HOME/APPDATA does not establish that this whole OS-managed surface moved. [AppContainer profile contract](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-createappcontainerprofile).

The read-only local snapshot is Windows 11 Pro build 26200 with ordinary NTFS C/D/E volumes. `read-only-privileges.txt` contains the inherited host token's enumerated privileges; `SeManageVolumePrivilege` is absent, not merely disabled. `read-only-host-storage.json` captures the OS/volume inventory. This is evidence about this session, not a claim about all accounts or future provisioning.

## Options

| Option | What it actually bounds | Decision for this host |
| --- | --- | --- |
| Periodic directory size checks / Job limits | Observed file sizes / committed memory or process time | Retain as diagnostics; not a hard disk guarantee. |
| NTFS per-user enforced quota on existing C/D | User-owned data streams across the volume, not a single worker directory | Reject as a local workaround: current AppContainer retains the same user SID; quota changes would affect the user's other files. Administrator provisioning is required. |
| FSRM folder hard quota | Administrator-managed folder/volume space | Supported server option; not a native Windows 11 Pro prerequisite we can silently assume or install. |
| Dedicated fixed-size VHD sandbox volume | Finite guest volume capacity and preallocated backing storage | Recommended candidate after external provisioning and writable-surface proof. No mount attempted here. |

NTFS charging follows each file owner's SID and counts data streams; it does not charge all filesystem metadata. Its quota settings require enforcement, not merely tracking. These properties make a shared-user quota unsuitable for the current same-user per-worker contract. [Quota accounting](https://learn.microsoft.com/en-us/windows/win32/fileio/disk-quota-limits), [administrator configuration and enforcement states](https://learn.microsoft.com/en-us/windows/win32/fileio/system-level-administration-of-disk-quotas). FSRM folder quotas are documented for Windows Server. [FSRM scope](https://learn.microsoft.com/en-us/windows-server/storage/fsrm/quota-management).

Microsoft's `CREATE_VIRTUAL_DISK_FLAG_FULL_PHYSICAL_ALLOCATION` creates a fixed VHD and preallocates its physical space. `AttachVirtualDisk` requires `SE_MANAGE_VOLUME_PRIVILEGE`; this session does not expose that privilege. Thus an unprivileged launcher cannot rely on creating and attaching a worker volume here without an external administrator/provisioner. No privilege enablement or elevation was attempted. [Fixed allocation](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ne-virtdisk-create_virtual_disk_flag), [attachment requirement](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-attachvirtualdisk).

## Minimal provisioned-volume contract

This is a proposed acceptance contract, not implemented behavior:

1. A trusted provisioner allocates and formats a fixed-size dedicated VHD of an explicitly approved capacity, for example 256 MiB for the initial tiny script-validation fixture. The provisioner protects the backing file, raw disk access, mount point and lifecycle from the worker, and records disk/volume identity, virtual capacity and backing-file allocation. No differencing chain, auto-grow or shared product-data volume. Engine and trusted source can remain read-only outside it.
2. A host-owned volume lease retains the exact attachment and verified mount/volume identity for the worker lifetime. A requested arbitrary path is not sufficient authority. If attached through a held virtual-disk handle, avoid permanent-lifetime mode for transient work; that flag deliberately separates attachment lifetime from handle closure. The provisioner must still verify safe detach/cleanup after the Job is empty. [Attachment lifetime flags](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/ne-virtdisk-attach_virtual_disk_flag).
3. Put `.godot`, imports, generated files, HOME, APPDATA, LOCALAPPDATA, USERPROFILE, TEMP/TMP and writable stdio destinations on that volume. Every explicitly inherited write handle must target bounded storage or a broker that enforces a byte cap. Protect mount ancestry and reject unapproved reparse paths. Host evidence copied out later must be length-limited and parsed as untrusted.
4. Audit and test the real AppContainer profile and registry storage separately. Either their writable backing storage is also within the bound or the worker is denied those writes without breaking startup. Child environment redirection alone is insufficient. A separately provisioned sandbox account whose whole writable profile lives on the bounded volume is an alternative, but changes token/account ownership and needs a separate reviewed launcher contract. It is not a silent adjustment to the accepted same-user boundary.
5. Before untrusted use, run a finite native/actual-Godot disk-full matrix inside a disposable *small* volume: ordinary file extension, parallel files, streams, sparse allocation and file-count/metadata pressure; confirm writes fail within the bound, no host-volume growth via any remaining writable surface, correct main-thread cancellation/recovery, retained evidence and Job PID0. Confirm the previous valid product state stays unchanged. Test rerun/recovery using preserved failure state rather than assuming deletion repairs a publication.

The volume capacity places a finite bound on writes *within that volume*. It does not by itself prove a whole-process host-disk bound: off-volume AppContainer storage, registry hives, inherited handles or other granted objects remain escape routes until accounted for. Nor does a fixed volume prove network denial or safe result publication. Those checks remain distinct.

## Bounded next work

First define the host preflight result `DISK_BOUNDARY_UNAVAILABLE` and keep arbitrary script/import execution fail-closed when no trusted bounded-volume lease exists. Continue trusted editor command/UndoRedo and journal work independently. Do not add an automatic elevation prompt or mutate existing user-volume quotas.

If an owner-provisioned volume becomes available, the next diagnostic is one finite capacity-exhaustion run against its exact disposable identity, followed by cleanup verification; it does not require widening capabilities or an engine fork. Until then the external prerequisite is explicit and testable: a trusted provisioned bounded storage surface plus proof that this Godot worker cannot write outside it.
