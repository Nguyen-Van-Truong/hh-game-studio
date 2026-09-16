# S47 actual Godot confinement startup diagnostic

AUTHORITY=0. Diagnostic only; no GT03 acceptance, hostile-script authorization, or public capability change.

The pinned stock Godot **4.7.2-stable** GUI executable started as a headless editor inside a zero-capability AppContainer, loaded a fixed trusted addon and scene, denied the tested private-root accesses, wrote the granted scratch positive control, and exited with the expected real code **87**. The enclosing owned runner exited **0** and verified its process tree empty. No engine binary or production source was changed.

The six first-run engine diagnostics were reduced to two by setting `HOME` only in the explicitly constructed child environment. Both attempts remain intact.

| Observation | run-01 | run-02 |
| --- | --- | --- |
| Child-only HOME points at owned scratch/profile | No | Yes |
| Actual Godot exit | 87 | 87 |
| Outer runner exit / timeout / tree verified | 0 / false / true | 0 / false / true |
| Probe elapsed seconds | 6.172 | 6.141 |
| Peak committed process/job memory bytes | 586088448 | 579502080 |
| Final inner Job active count / PID list | 0 / [] | 0 / [] |
| Private sentinel and readonly source hashes unchanged | true | true |
| Profile and exact owned temporary directory removed | true | true |
| Known-folder / volume-information engine errors | 4 / 2 | 0 / 2 |

`complete=true` in each `result.json` means this bounded diagnostic completed its specified startup and access checks. It does not mean clean stderr, a passing product gate, arbitrary-input safety, or completed sandbox hardening. The remaining two errors are preserved in `run-02/engine-stderr.txt`.

## Pin and launch evidence

The GUI executable hash was checked before copying and launching:

- Source commit: `ed1daf0bf001b61586d9930840f2f1394092c079`.
- GUI SHA-256: `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`.
- In-process `Engine.get_version_info()` matched the version and full commit.
- The console wrapper was bypassed because it creates a GUI child; the configured child-process prohibition would conflict with that wrapper. This is direct execution of the locked stock GUI binary, not an engine modification. [Pinned console wrapper source](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/platform/windows/console_wrapper_windows.cpp).

Each unique AppContainer profile was created with no capabilities. Before resuming the suspended child, the host retained its primary-token and process handles, checked token type, AppContainer flag, exact package SID, zero capabilities, owner SID and low integrity, captured PID plus creation time, and assigned the process to its owned Job. The Job readback recorded kill-on-close, active-process limit 1, process CPU time 20 seconds, and 1 GiB process/job committed-memory limits. These are actual configured limits; exhausting those limits was not tested. [Microsoft Job memory-limit documentation](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_extended_limit_information).

The child received only the enumerated environment keys and three explicit inherited standard handles. Source/image directories granted this unique package read/execute; `.godot` and scratch granted modify with low integrity; the private directory granted only the trusted owner. The fixed addon tested private file READ and WRITE, private directory opening, and project file creation; all failed. Godot's reported error numbers were 12, 1, 31 and 1 respectively; these are Godot errors, not captured Win32 last-error values. The scratch file contained the exact expected bytes. The trusted host independently compared private/source hashes and absence of the attempted new project file.

The outer runner had a 60-second total timeout. The inner child had a 30-second timeout and overall setup/run deadline. Neither run needed forced termination. No second Godot instance used either temporary project.

## Engine diagnostic attribution and repair

1. The original four `OS_Windows::get_system_dir` errors came from unsuccessful known-folder lookup. The exact pinned Windows method calls `SHGetKnownFolderPath`; the editor defaults choose child environment `HOME` before requesting the Documents folder. Adding HOME to the already granted scratch/profile removed all four in run-02. The host's environment and real user folders were untouched. [Pinned editor defaults](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/editor/settings/editor_settings.cpp), [pinned Windows OS method](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/platform/windows/os_windows.cpp).
2. `EditorFileSystem` initializes FAT32/EXFAT handling by querying filesystem type twice if the first result does not match. `DirAccessWindows::get_filesystem_type` reduces the current path to its drive root and calls `GetVolumeInformationW`; failure returns an empty string and logs the two remaining errors. The exact binary log locations are `drivers/windows/dir_access_windows.cpp:412`. There is no environment fallback in this method. No drive-root ACL, capability or engine-source change was made. [Pinned caller](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/editor/file_system/editor_file_system.cpp), [pinned Windows implementation](https://raw.githubusercontent.com/godotengine/godot/ed1daf0bf001b61586d9930840f2f1394092c079/drivers/windows/dir_access_windows.cpp).

The native `GetLastError` for the volume call was not captured, so this report does not claim its numeric failure reason. Microsoft documents its root-path input and separate last-error result. The call path is source-attributed; the exact OS cause remains unmeasured. [GetVolumeInformationW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw).

## Explicit limits and next boundary work

- **Hard scratch disk quota: absent.** The 16 MiB periodic observation covers scratch only; it is a soft stop, misses `.godot`, cannot prevent a burst, and is not a filesystem quota. The observed AppContainer profile also introduces OS-managed storage outside mere environment redirection. See `DISK-CAP-DECISION.md` for the practical prerequisite and recommended bounded volume contract.
- **Network:** zero capabilities are observed; direct TCP/UDP, DNS, listen, IPv4/IPv6 and loopback denials have not been exercised with reachable positive controls. No blanket network-denial claim follows from the startup test. AppContainer access can be granted separately and read-only file access is less restrictive, so it is not a universal unreadable filesystem. [Microsoft isolation model](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation).
- **Child execution:** the child-process policy and Job active-process limit were set; actual child-launch attempts were not tested.
- **Input:** only this hand-authored fixed addon and scene were opened. Arbitrary `@tool`, importers, native extensions and submitted scripts remain unauthorized until the complete sandbox and writable-surface limits are proven.
- **Publication:** scratch is untrusted output. This probe has no scene-command bridge, journal integration, semantic validation or managed publication. The GT03 trusted editor subset may proceed separately; this diagnostic does not satisfy script replacement's disposable validation boundary.
- **Scope of source binding:** each run stores exact diagnostic and copied-project hashes plus the locked engine hash. This is a prototype package, not a frozen full GT03 production closure. Its existing S32 Windows helper and GT01 owned-runner dependencies are listed by the capture script and belong to accepted checkpoint `0c3b00a` at this diagnostic's execution.

## Reproduction and evidence

From the repository root, use a new run label; the output directory must not already exist:

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260916-gt03-s47-sandbox/capture.py run-03
```

The current diagnostic source is the HOME-repaired run-02 version. Do not overwrite run-01 or run-02. `capture.json` and `godot-sandbox-host.json` hold outer host exit/tree evidence; `result.json` holds retained-child identity, token, Job, hashes and cleanup; `engine-result.json` holds the addon observations; both engine streams remain separate. Failed runs preserve their owned temporary path in the result rather than silently treating a reset as repair.

GT03 implementation readiness is recorded separately in `../20260916-gt03-readiness.md`; neither report is a new plan.
