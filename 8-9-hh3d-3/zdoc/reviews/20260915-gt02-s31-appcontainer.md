# GT-02 S31 — Disposable-profile AppContainer diagnostic

2026-09-15, Asia/Saigon. `REPORT_ONLY=1`, `AUTHORITY=0`, `TICK=no`.

**The fixed-command AppContainer diagnostic succeeded. Production safe-write remains `UNSUPPORTED_SAFE_OPEN_WINDOWS`.** In final run 04, an ordinary control and a real zero-capability AppContainer executed the same `cmd.exe` and batch script from the same scratch directory, using separate synthetic canaries. Both produced start/completion markers and host-captured exit **37**. The ordinary process performed all five private operations; the AppContainer performed none and still wrote its scratch positive control.

No production source, plan, Godot/Blender adapter, network exception, account, elevation, service, desktop setting or existing user/system ACL was changed. This assignment explicitly permitted one fresh AppContainer profile per run through the documented create/delete APIs. The earlier cleanup-denied S30 TEMP path was not accessed.

## Final observed matrix

Evidence: [run-04.stdout.json](20260915-gt02-s31-appcontainer/run-04.stdout.json), [host record](20260915-gt02-s31-appcontainer/run-04.host.json), and empty [stderr](20260915-gt02-s31-appcontainer/run-04.stderr.txt). Parent probe exit was **0**; the complete run took under one second on Windows build `10.0.26200`, 64-bit Python `3.11.9`.

| Check | Ordinary control | AppContainer |
|---|---|---|
| IsAppContainer | 0 | **1**, read from actual process token |
| Integrity | Medium | **Low**, `S-1-16-4096` |
| Capability count | 0 | **0** |
| Package SID | Not applicable | Matches this run's created profile |
| Start/completion marker | Both present | Both present |
| Host-captured process exit | 37 | 37 |
| Scratch file creation | Success | **Success** |
| Read private canary | Expected bytes obtained | **Denied; output empty** |
| Append private canary | Bytes changed | **Denied; bytes unchanged** |
| Delete private canary | File absent | **Denied; original present** |
| Rename private canary | Destination and bytes verified | **Denied; original present, destination absent** |
| Hardlink private canary into scratch | Alias bytes verified; link count 2 | **Denied; no alias, link count 1** |
| Job accounting after bounded drain | Active 0 | Active 0 |
| Job process-ID list at final query | Empty | Empty |

The AppContainer emitted access-denied errors for read/delete/rename/hardlink and nonzero command error levels for all five forbidden attempts. The append attempt's redirected stderr was empty, so its rejection is supported by its nonzero command result and the host's unchanged byte readback, not an invented Win32 error code. All private file contents matched the original canaries after the AppContainer exited.

The scratch directory was created with a protected broker ACL, an explicit profile-SID Modify grant, and a Low mandatory label inherited by its children. Private directories/files granted the broker user access without an AppContainer ACE. Effective owner/group/DACL/mandatory-label descriptors for scratch, the batch file and private objects were read back. Their public SID placeholders preserve the roles; exact values are in ignored raw evidence.

## Launch and cleanup details

The test passes a full explicit `lpApplicationName` and a mutable command line, with a fixed batch basename in an explicit cwd. It does not depend on nested `/c` quoting or executable search. Microsoft distinguishes successful process creation from completed initialization, which is why the token, marker, actual exit and file effects are all checked. [CreateProcessW](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createprocessw)

Each process starts suspended with handle inheritance disabled, then joins an owned Job Object configured for kill-on-close, one active process and a 128 MiB process-memory cap before resume. The process wait is bounded to 10 seconds, followed by at most about two seconds of Job accounting drain. Final run 04 observed `[1, 0]` across a 20 ms interval for each process, then independently obtained an empty Job process-ID list. `TotalProcesses=2` is preserved; the identity/cause of that accounting total was not isolated. It is not converted into a fictitious zero or a claim about a second running worker.

For the final profile, the unique package directory and registry SID mapping were absent before creation, present after `CreateAppContainerProfile`, and absent after `DeleteAppContainerProfile`. Both API HRESULTs were 0. `GetAppContainerFolderPath` returned the verified owned profile's **`AC` subdirectory**. Microsoft documents this layout and the AppContainer environment redirection. [Launch an AppContainer](https://learn.microsoft.com/en-us/windows/win32/secauthz/implementing-an-appcontainer)

All native process/token/job handles were closed before profile deletion. The API's success was accompanied by filesystem and registry absence readback, since deletion of an already absent profile can itself return success. No manual registry or profile-filesystem deletion was used. The owned TEMP fixture was removed. [DeleteAppContainerProfile](https://learn.microsoft.com/en-us/windows/win32/api/userenv/nf-userenv-deleteappcontainerprofile)

## Preserved diagnostic history

| Run | Actual observation | Owned profile / cleanup |
|---|---|---|
| 01 | Ordinary control completed every operation and exit 37; immediate Job accounting still reported active 1. The harness stopped before profile creation. | No profile created; TEMP removed. |
| 02 | A bounded Job drain reached zero. Profile creation succeeded; the harness incorrectly compared the returned `AC` subdirectory with its parent package root. | Fresh profile deleted through API; package/mapping absent; TEMP removed. |
| 03 | Correct profile-path check passed. AppContainer `CreateProcessW` failed with **WinError 203** before a child existed, using the sparse environment. | Fresh profile deleted through API; package/mapping absent; TEMP removed. |
| 04 | Adding the explicit standard-variable bundle `USERPROFILE`, `LOCALAPPDATA`, `APPDATA`, `SystemDrive` enabled the complete diagnostic. | Fresh profile deleted through API; package/mapping absent; TEMP removed. |

The original source for each failed run is retained under `appcontainer_probe_run01.py` through `...run03.py`, matched to its recorded source hash. No failed run is presented as a successful AppContainer test. The final environment contains only ten named standard variables; it does not inherit the host's full environment or log its values. Which individual added variable resolves error 203 was not isolated. Nor does S31 prove the earlier S30 SID-only error 2 was caused solely by an absent profile: the experiments also differed in environment and command construction.

Across these attempts, profiles were created only in runs 02, 03 and 04, at most one per run. Each run proved its unique name was initially absent and deleted only that profile through its API. No S31 cleanup action received an automatic approval rejection.

## Frozen evidence and redaction

- Final probe SHA-256: `681a051f57d436c68eb994c0d20bac6b9f8a486dc95c56e654de709a928a4755`.
- Windows helper SHA-256: `1afd34eb11fd5ab9a34c37de2a80aabcec04224826a092ff122d5212bd3a50c4`.
- [Pinned manifest](20260915-gt02-s31-appcontainer/pinned-manifest.json) SHA-256: `42a33a9206e5e855ee509aa32c0af1ea602b97da0c885a62074a7b9fef829784`.

The manifest pins 18 public source/log/host/verification-program artifacts and records each raw-to-public hash pair. Public records redact host paths, account SIDs, profile identity and package SID. Raw exact bytes reside only under ignored `studio/.local/review-raw/S31`; their relative filenames and SHA-256 values are in the ledger. No credential, token secret or host environment dump is collected.

[verify_package.py](20260915-gt02-s31-appcontainer/verify_package.py) is read-only: it checks the saved manifest, source/log hashes, typed observations and deterministic derivation from private raw bytes. It never regenerates or blesses a manifest. [Verification results](20260915-gt02-s31-appcontainer/verification.json) record local full verification exit 0, copied public-only verification exit 0, and a disposable copy with changed evidence rejected at its pinned hash with exit 1. Both the original and copied manifests remained unchanged, and the verifier fixture was removed.

```powershell
python -B 8-9-hh3d-3/zdoc/reviews/20260915-gt02-s31-appcontainer/verify_package.py
```

Use `--public-only` where ignored raw bytes are unavailable; its output explicitly reports that raw derivation was not checked. A future execution needs a new run ID and separately captured package; do not overwrite these records.

## What this unlocks, and what remains unproven

This establishes a working **fixed-command filesystem access boundary** for the measured process/profile/ACL combination. The next useful bounded experiment is a small native AppContainer adversary using the same proven lifecycle, to attempt reparse/junction swaps, file-ID opens, broker-process/handle duplication and inherited-handle misuse against disposable broker canaries. Then combine that boundary with create-only retained-handle publication and crash/restart readback.

This is not a sandbox security audit or proof of safe publication. It does not test arbitrary worker code, network/IPC restrictions, desktop attack resistance, broker authentication, hardlink/reparse races, `OpenFileById`, process-memory attacks, leaked handles, concurrent unrestricted same-user peers, destination-identity CAS, crash durability, or Godot/Blender behavior. A zero-capability token alone does not prove those properties. The GT-02 source and acceptance state are unchanged; safe-write and existing-target replacement remain unsupported.
