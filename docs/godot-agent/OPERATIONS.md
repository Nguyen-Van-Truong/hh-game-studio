# Operations runbooks — R9-WP4

Fresh-reviewer copy. fresh-reviewer. Every command below is the command. Do not invent a
second path. `--provider plan` stays. Do not invent an API key.

`CLEAN_VM` stays unproven on a Godot/Node/source machine. Real clean VM is G6.
`not_g6=1`. Do not invent Hyper-V. Do not tick G6 or GX.

Kill leftover Godot first. Sequential. One home at a time.

## Official disaster drill (this machine is not a clean VM)

```powershell
python tools/godot/ops.py drill --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

Expected: backup, crash recover, token rotation, redacted log collection,
package rollback. Banner includes `CLEAN_VM stays unproven` and `not_g6=1`.
Do not create a folder named `clean-vm`.

Thin wrapper: `tools/godot/ops.ps1`.

## Backup / restore

Isolated `--home` only. The drill does not copy `%LOCALAPPDATA%\HHGodotAgent\sessions`
from a live owner session.

```powershell
python tools/godot/ops.py backup --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
python tools/godot/ops.py restore --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

Backup covers: studio `install/current` + `state.json`, the user-project
`.hh-agent` pointer, isolated drill sessions, and logs. backup must not ship raw tokens: copied `session.json` tokens are wiped
and logs are redacted before the backup is durable. Restore is tmp+rename. User game
content outside `--home` is not deleted.

Package rollback (one previous studio version) is still:

```powershell
python tools/godot/install.py rollback --install-root "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4\install"
```

## Log collection / redaction

```powershell
python tools/godot/ops.py collect-logs --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

Redacts session token, home / profile paths, and credential-shaped prefixes
before writing `collected-logs/`. Raw logs stay under `--home` and are not
committed. A9: never log secrets.

## Crash recovery

Ledger rule (plan §5.4): crash in `applying` / `applied_volatile` does not
blind-replay. If the restored disk hash matches the backup, mark
`committed_durable`. If before and after both mismatch, return `E_UNCERTAIN`
and do **not** report success.

```powershell
python tools/godot/ops.py recover --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

Pause still wins (A14). After a suspected leak, rotate the token before resume.

## Token rotation

```powershell
python tools/godot/ops.py rotate-token --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

Writes a new 256-bit hex token into the isolated drill `session.json`.
The previous token is not kept in plaintext (hash only). This is a session
secret, not an API key. Do not invent an API key.

Live leftover path (`%LOCALAPPDATA%\HHGodotAgent\sessions\*\session.json`):

```powershell
python tools/godot/ops.py rotate-token --live
```

Official then wipes leftover session tokens (live + `--home` + backup):

```powershell
python tools/godot/ops.py wipe-tokens --live --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

backup must not ship raw tokens. Isolated `--home` backup redacts
`session.json` and raw logs before copy. leftover session tokens after
official must be 0.

## Gate / artifact catalog

```powershell
python tools/godot/ops.py catalog --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
```

G0–G5 must resolve to existing artifacts. G6 stays **unresolved**
(`CLEAN_VM` unproven). GX stays **locked**. AC-20 and AC-22 stay unproven.
AC-21 is partial (R9-WP2 TAMPER on this machine).

## Refused (E3 / G6 honesty)

```powershell
python tools/godot/ops.py sign
python tools/godot/ops.py upload
python tools/godot/ops.py publish
```

Each exits non-zero. Signing/publish/channel is E3. Unsigned internal only.

## Official verify

```text
python tests/bootstrap/test_release_handoff.py
```

A fresh reviewer follows this file, then that command. Labels:
EVIDENCE, RUNBOOK, DRILL, REVIEWER, GATES, CLEAN_VM.
RUNBOOK may be proven when this file is followable. Same PID/argv is
not a fresh reviewer: REVIEWER stays unproven. mkdir+copytree+planted
bytes is not a live Godot/sidecar kill: DRILL stays unproven. Heading-only
evidence is not a review: EVIDENCE stays unproven. G6 unresolved:
GATES stays unproven. `CLEAN_VM` stays unproven. `not_g6=1`.
CLEAN_VM stays unproven. --provider plan stays.
