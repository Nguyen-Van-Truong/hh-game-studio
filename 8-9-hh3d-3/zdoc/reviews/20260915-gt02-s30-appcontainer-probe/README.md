# S30 SID-only AppContainer diagnostic

No CreateAppContainerProfile/DeleteAppContainerProfile calls, profile edits,
account changes, existing ACL changes, or production mutation were performed.
Both unique profile names were absent at their expected Packages directory and
registry mapping before and after the probe. Those checks cover the named locations,
not arbitrary OS side effects. Temporary synthetic directories were removed.

Runs 01 and 02 exited 1. Run 02 adds phase instrumentation: deriving a SID, creating
private/scratch directories with explicit descriptors and setting process security
capabilities succeeded; CreateProcessW failed with WinError 2 before any child token
or completion marker existed. No sandbox, command effect or safe writer was proven.
No profile-creation fallback was attempted. Run 01 source was preserved and verified
against its recorded SHA; run 02 script and host/stream hashes are separate.

This does not establish that a missing profile is the cause: the error is only a
bounded diagnostic observation. The next launch experiment needs a separately scoped
owned profile lifecycle and exact child dependency/desktop diagnostics. Capability
flags must remain disabled until positive and negative process tests prove the boundary.

References: [SECURITY_CAPABILITIES process attribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute),
[DeriveAppContainerSidFromAppContainerName](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deriveappcontainersidfromappcontainername),
[AppContainer for legacy applications](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-for-legacy-applications-).

These are research artifacts outside the frozen GT-02 source closure. They do not
change the S30 candidate or its independent review scope. The separate restricted
ACL run03 TEMP cleanup rejection is recorded in the Windows probe report; this
probe never accessed that directory.
