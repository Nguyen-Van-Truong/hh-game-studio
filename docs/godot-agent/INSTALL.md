# Install HH Godot Agent (R9-WP2)

Current-user studio bundle: exact addon, sidecar, launcher, checksums, and licenses.
No admin. No online-latest bootstrap. Signing/publish is E3 — unsigned internal
builds are allowed; do not invent a cert.

This is **not** a clean-VM proof. CLEAN_VM stays unproven on a Godot/Node
machine. Official smoke is not a VM. Do not map this WP to AC-20 — AC-20 is
Windows clean-VM **export** (G6), not install/connect. `not_g6=1`.

## One command

From a machine that already has the repo (or an unpacked bundle):

```powershell
python tools/godot/package.py --out "$env:LOCALAPPDATA\HHGodotAgent\packages\hh-godot-agent"
python tools/godot/install.py setup --from "$env:LOCALAPPDATA\HHGodotAgent\packages\hh-godot-agent" --project C:\Users\you\Games\my-game
python tools/godot/launch.py --project C:\Users\you\Games\my-game --godot
```

`setup` installs the studio under `%LOCALAPPDATA%\HHGodotAgent\install\current`
and enables `hh_agent` in the user project. You do **not** copy addon/sidecar/
host/pin folders by hand.

Thin wrappers: `tools/godot/package.ps1`, `install.ps1`, `launch.ps1`.

## What is installed

| Path | Role |
|------|------|
| `%LOCALAPPDATA%\HHGodotAgent\install\current\` | addon, sidecar, launcher, pin, checksums, licenses |
| `%LOCALAPPDATA%\HHGodotAgent\install\rollback\` | one previous version |
| user project `addons/hh_agent/` | copy enabled by `enable-project` |
| user project `.hh-agent/studio-install.json` | pointer at the current-user install |

User projects stay **outside** the install root so uninstall cannot delete them.

## Doctor

```powershell
python tools/godot/install.py doctor --project C:\Users\you\Games\my-game
```

Actionable `do:` lines cover missing install, tampered hashes (reject / Observe
only), Node pin `24.19.0` (not latest), and Godot pin
`4.7.1.stable.official.a13da4feb` via `python tools/godot/doctor.py --install`.

`--provider plan` stays. Do not invent an API key.

## Update / rollback / uninstall

```powershell
python tools/godot/install.py update --from <new-bundle>
python tools/godot/install.py rollback
python tools/godot/install.py uninstall
```

Update keeps **one** previous version. Rollback restores it. Uninstall removes
`install\current`, `install\rollback`, `state.json`, and the loopback
`session.json` token created for tracked user projects. It does **not** delete
user projects, Kho Bi An, or `%LOCALAPPDATA%\HHGodotAgent\tooling\`.

## Signing

Unsigned internal build. Public upload/sign/channel is E3 after G6. Do not add
a `.pfx` to the repo or the bundle.

## Official verify

```text
python tests/bootstrap/test_package_install.py
```

Labels: INSTALL, CONNECT, MICROGAME, UNINSTALL, ROLLBACK, TAMPER, CLEAN_VM.
`CLEAN_VM` stays unproven on a Godot/Node machine. `not_g6=1`.
Do not map this WP to AC-20.
