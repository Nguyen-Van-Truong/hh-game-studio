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
