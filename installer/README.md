# HH Game Studio installer (Inno Setup 6)

Packager notes for WP-M7B-1 / MASTER T7B.1. End-user install, uninstall, update, and leftover steps: [docs/INSTALL.md](../docs/INSTALL.md).

**Not verified on a clean VM** (same STOP S5 as M7A-2 / M7B). This folder is the script + docs only. Do not treat a local compile as T7B.1 acceptance.

Inno Setup is **not** a Cargo dependency. CI does **not** run ISCC.

## What the setup installs

Into `{autopf}\HH Game Studio` (typically `C:\Program Files\HH Game Studio`):

| File | Role |
|---|---|
| `gs-editor.exe` | Editor window + bus |
| `gs-player.exe` | Play process (I3); found next to the editor |
| `gs-cli.exe` | Bus CLI |
| `gs-mcp.exe` | stdio MCP server |

No sample games, no `.pfx`, no SignTool. Game export (`build.game`) stays unsigned (C13 / [docs/EXPORT_SIGNING.md](../docs/EXPORT_SIGNING.md)).

## AppId / version

- **AppId:** `{B2E665BE-E6BF-42C7-B5F5-DA82BF9F189E}` (permanent — do not regenerate)
- **AppVersion:** `0.1.0`

## Source of binaries

Default `{#SourceRoot}` is `installer/dist/`.

1. Build release exes at the repo root:

   ```
   cargo build -p gs-editor -p gs-player -p gs-cli -p gs-mcp --release
   ```

2. Stage them:

   ```
   powershell -File installer\stage.ps1
   ```

   That copies the four exes from `..\target\release\` into `installer\dist\`.

3. Or skip staging and point ISCC at the Cargo tree:

   ```
   ISCC /DSourceRoot=..\target\release installer\hh-game-studio.iss
   ```

`stage.ps1` does not build and is not wired into CI.

## Compile with ISCC

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) (6.0+; `ArchitecturesAllowed=x64` is the 6.0 form). Then, from `installer\`:

```
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" hh-game-studio.iss
```

Output: `installer\output\HHGameStudio-Setup-0.1.0.exe` (unsigned).

`installer\output\` and `installer\dist\*.exe` are gitignored.

## Start Menu

Shortcut **HH Game Studio** runs `gs-editor.exe` with working directory `{app}` and **no project argument**.

`{app}` has no `project.json` and no `games\` tree, so the editor prints `usage: gs-editor <project-dir>` and opens on demo IR (no `.gs/` under Program Files). Open a project later with `gs-editor <project-dir>` or by passing a folder. User projects are not installed here so uninstall cannot delete them.

## Uninstall

Add/Remove Programs or Start Menu **Uninstall HH Game Studio** removes `{app}` (the four exes + Inno uninstaller files) and the Start Menu group this script created.

It does **not** delete user projects, exported game folders, or repo `games\`.

It **does** delete the installer-created rollback folder `%LOCALAPPDATA%\HH Game Studio\rollback` (see update below).

## Update channel (no CDN)

There is no hosted feed, no auto-updater, and no invented download URL.

Whoever has the new `HHGameStudio-Setup-*.exe` (internal share, later a release page — not wired) runs it. Same AppId → Inno upgrades **in place** (`UsePreviousAppDir=yes`), replacing the four exes in `{app}`.

Before the new files are written, the script keeps **one** previous version in:

`%LOCALAPPDATA%\HH Game Studio\rollback\`

(`gs-*.exe` plus `unins000.*` if present). The next upgrade **replaces** that folder. That is the rollback window: one generation.

### Rollback

1. Close the editor and player.
2. Prefer re-running the **previous** setup exe if you still have it (same AppId).
3. Or copy `gs-*.exe` from the rollback folder over `{app}`.

Uninstalling the product removes the rollback folder. Keep the previous setup exe if you need a longer history.

## Reproduce (when a human has a VM)

Not run here. Checklist for later:

1. Compile the setup as above (or copy a prebuilt `HHGameStudio-Setup-0.1.0.exe`).
2. On a clean Win10/11 VM (no Rust/Python): run the setup; accept Program Files.
3. Start Menu → HH Game Studio → editor window, no project.
4. Optional: `gs-editor.exe` with a copied project folder (not under `{app}`).
5. Uninstall. Confirm `{app}` is gone. Confirm the project folder still exists.
6. Leftovers: [docs/INSTALL.md](../docs/INSTALL.md#leftover-checklist).

## Out of scope (this WP)

- Code signing / timestamp / `.pfx` (M7B-2)
- ISCC in CI
- SBOM / notices (M7B-3)
- Shipping `games\` inside `{app}`
