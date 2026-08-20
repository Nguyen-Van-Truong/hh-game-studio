# Install / uninstall HH Game Studio (M7B-1)

Editor distribution via **Inno Setup 6** (G4). Script: [`installer/hh-game-studio.iss`](../installer/hh-game-studio.iss). How to compile: [`installer/README.md`](../installer/README.md).

**Not verified on a clean VM.** Same STOP S5 as M7A-2 / M7B: this environment has no Win10/11 machine without Rust/Python. WP-M7B-1 stays unticked until a human runs the checklist below and pastes evidence.

This installer is **unsigned** (no SignTool). Game export stays **unsigned** (C13). Do not put a `.pfx` in the repo or in a game pack. See [EXPORT_SIGNING.md](EXPORT_SIGNING.md).

## Identity

| | |
|---|---|
| AppId | `{B2E665BE-E6BF-42C7-B5F5-DA82BF9F189E}` |
| AppVersion | `0.1.0` |
| Default dir | `C:\Program Files\HH Game Studio` |
| Payload | `gs-editor.exe`, `gs-player.exe`, `gs-cli.exe`, `gs-mcp.exe` |

AppId is permanent. A new GUID would look like a different product and break in-place upgrade.

## Start Menu

**HH Game Studio** launches `gs-editor.exe` with **no project** (working directory = install dir). The editor prints `usage: gs-editor <project-dir>` and shows demo IR. It does not create `.gs/` under Program Files.

Sample games in the repo (`games\snake`, …) are **not** copied into the install dir. Keep projects somewhere you own (Documents, a clone of `games\`, etc.) so uninstall cannot remove them.

## Update channel

There is **no CDN and no auto-update service**.

1. Get a newer `HHGameStudio-Setup-*.exe` from the same place you got this one (file share, later a release page — not configured here).
2. Run it. Same AppId → upgrade **in place**; the previous install directory is reused.
3. Immediately before the new exes are written, the setup keeps **one** previous version in `%LOCALAPPDATA%\HH Game Studio\rollback\` (the four exes + Inno `unins000.*`). The next upgrade overwrites that folder.

### Rollback (one previous version)

Close the editor. Re-run the previous setup exe if you still have it, or copy `gs-*.exe` from the rollback folder over the install directory.

Uninstall deletes that rollback folder. Keep old setup exes yourself if you need more than one generation.

## Uninstall

Use Windows **Apps & features** or Start Menu **Uninstall HH Game Studio**.

Removes:

- the install directory (`gs-*.exe` and Inno uninstaller files)
- the Start Menu group this installer created
- optional desktop shortcut if that task was selected
- `%LOCALAPPDATA%\HH Game Studio\rollback\` (installer-created)

Does **not** remove:

- user project folders (`project.json`, scenes, scripts, `.gs/` WAL)
- exported game folders from `build.game` / `hh-play.bat`
- repo trees, `playground\`, or anything you created outside `{app}`

## Reproduce: install → run editor → uninstall

Requires a built unsigned setup (`installer/output/HHGameStudio-Setup-0.1.0.exe`). See `installer/README.md` for ISCC. **Not executed in this WP.**

1. Clean Windows 10 or 11 VM (no Rust, no Python, no prior HH Game Studio).
2. Copy the setup exe onto the VM. Run it. Default dir is fine (admin).
3. Start Menu → **HH Game Studio**. Expect an editor window and no project. SmartScreen / “Windows protected your PC” is expected for an unsigned exe.
4. Optional: copy a project folder onto the VM (not under Program Files) and run `"C:\Program Files\HH Game Studio\gs-editor.exe" <that-folder>`.
5. Uninstall from Apps & features.
6. Confirm `C:\Program Files\HH Game Studio` is gone.
7. Confirm the project folder from step 4 still exists.
8. Walk the leftover checklist.

## Leftover checklist

After a successful uninstall, these **must still exist** if you created them:

- [ ] Your project directory (and its `.gs\` if the editor wrote one)
- [ ] Any `build.game` / pack output folder

These **should be gone** (installer-owned):

- [ ] `C:\Program Files\HH Game Studio\`
- [ ] Start Menu `\HH Game Studio\` (current-user and all-users Programs)
- [ ] Desktop `HH Game Studio.lnk` if the installer created it
- [ ] `%LOCALAPPDATA%\HH Game Studio\rollback\`
- [ ] empty `%LOCALAPPDATA%\HH Game Studio\` (removed if empty)

These may remain and are **not** treated as install-dir junk. Delete by hand if you want a sterile VM:

- [ ] `%APPDATA%\hh-game-studio\` — not created by this installer; reserved for later per-user config (e.g. imagegen key file). Uninstall must not invent or wipe it.
- [ ] `%TEMP%\gs-editor-<pid>\` — ephemeral bus root when launched with no project
- [ ] Extra shortcuts you created yourself
- [ ] Copied setup exe, rollback copies you moved elsewhere, previous setup exes

## What this WP did not verify

- Clean-VM install, editor launch, or uninstall
- In-place upgrade from a previously installed build
- Rollback by copying exes or re-running an older setup
- SmartScreen / reputation
- ISCC in CI (intentionally not added)
- Code signing (M7B-2; no `.pfx` in tree)
