# Godot doctor (R0-WP3)

Installs and verifies the **frozen** Godot pin. Does not use GitHub `/releases/latest`,
`npx -y latest`, TuxFamily, Mono/.NET builds, 4.7.2*, or 4.8*.

Pin data lives in `pin.json`. `doctor.ps1` is a thin wrapper; hashing/version/refuse
logic is in `doctor.py`.

## Cache (gitignored, not in the repo)

`%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\`

```
downloads\   editor zip + export templates tpz
bin\         extracted Standard win64 editor + console exe
state.json   last successful verify
```

Do not commit zip / tpz / exe.

## Commands

From repo root:

```powershell
# Download if missing, checksum, extract, godot --version
.\tools\godot\doctor.ps1 -Install

# Verify cache already present
.\tools\godot\doctor.ps1

# Print console exe path (headless/CLI)
.\tools\godot\doctor.ps1 -PrintBin

# Must fail (refuse 4.7.2)
.\tools\godot\doctor.ps1 -RequestedVersion 4.7.2-stable
```

Expected `--version`: `4.7.1.stable.official.a13da4feb`

See `docs/VERSIONS_GODOT.md`.

## Package / install / launch (R9-WP2)

Business logic is Python (`package.py`, `install.py`, `launch.py`,
`studio_bundle.py`). The `.ps1` files are thin wrappers.

```powershell
python tools/godot/package.py --out "$env:LOCALAPPDATA\HHGodotAgent\packages\hh-godot-agent"
python tools/godot/install.py setup --from "$env:LOCALAPPDATA\HHGodotAgent\packages\hh-godot-agent" --project <user-project>
python tools/godot/install.py doctor --project <user-project>
python tools/godot/launch.py --project <user-project> --godot
```

Current-user only (`%LOCALAPPDATA%\HHGodotAgent\install`). No admin. Exact
addon/sidecar/launcher + checksums + licenses. No online-latest bootstrap.
Unsigned; signing is E3. Rollback keeps one previous version. Uninstall keeps
the user project.

Official verify: `python tests/bootstrap/test_package_install.py`
(`CLEAN_VM=unproven`). Details: `docs/godot-agent/INSTALL.md`.

## Compatibility / update matrix (R9-WP3)

`compat.py` keeps the exact 4.7.1-stable pin. Probe of a newer stable is
non-blocking and never applied. Capability-lock migration copies the
project first; downgrade restores the old lock. Version mismatch is
Observe/Doctor only. `--provider plan` stays. CLEAN_VM stays unproven.

```powershell
python tools/godot/compat.py probe
python tools/godot/compat.py mcp-sync
python tests/bootstrap/test_compat_update.py
```

Playbook: `docs/godot-agent/COMPATIBILITY.md`.

## Release / operations (R9-WP4)

`ops.py` is backup/restore, redacted log collection, crash recover,
token rotation, gate catalog, and the official disaster drill.
Signing/upload/publish are refused (E3). CLEAN_VM stays unproven.
Do not invent Hyper-V. `not_g6=1`.

```powershell
python tools/godot/ops.py drill --home "$env:LOCALAPPDATA\HHGodotAgent\release\r9-wp4"
python tests/bootstrap/test_release_handoff.py
```

Runbooks: `docs/godot-agent/RELEASE.md`, `OPERATIONS.md`.
