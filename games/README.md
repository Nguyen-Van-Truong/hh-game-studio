# Games

Each folder is a project `Session::open` can load: `project.json` plus `scenes/main.gscene.json`. Open the **folder**, not the repo root.

## Play vs Edit

**Play** runs the packed game in a `gs-player` window. No editor, no `.gs/` WAL. Double-click `hh-play.bat` (menu: snake / platformer / scrap-yard / arena-brawl) or a game’s `play.bat`. The console stays open so a `REJECT` error is visible. If `gs-player.exe` is missing, run `hh-game-studio.bat` once to build, then play again.

```
hh-play.bat
hh-play.bat 1
hh-play.bat 2
hh-play.bat 3
hh-play.bat 4
hh-play.bat snake
hh-play.bat platformer
hh-play.bat scrap-yard
hh-play.bat arena-brawl
hh-play.bat games\snake
```

`hh-play.bat` builds `gs-player` (release), packs to `%TEMP%\hh-gs-play\<name>\` (outside the project), then starts `gs-player.exe --snapshot manifest.json` in a window. You can also double-click `games\<name>\play.bat`.

A folder that already has `gs-player.exe` + `manifest.json` (a previous pack, or a copy on a machine without Rust) runs with no cargo:

```
hh-play.bat %TEMP%\hh-gs-play\snake
```

`set GS_SKIP_BUILD=1` skips `cargo build` when `target\release\gs-player.exe` already exists. A clean PC without Rust still cannot *create* a pack from this repo; copy the packed folder.

**Edit** opens the same folder in `gs-editor` (document + Play-from-editor). Use `hh-game-studio.bat`, not `hh-play.bat`.

## Open in gs-editor

From the repo root, pass the game directory as the editor’s project path.

```
hh-game-studio.bat games\snake
hh-game-studio.bat games\platformer
hh-game-studio.bat games\scrap-yard
hh-game-studio.bat games\arena-brawl
```

```
cargo run -p gs-editor -- games/snake
cargo run -p gs-editor -- games/platformer
cargo run -p gs-editor -- games/scrap-yard
cargo run -p gs-editor -- games/arena-brawl
```

```
.\gs-editor.exe games\snake
.\gs-editor.exe games\platformer
.\gs-editor.exe games\scrap-yard
.\gs-editor.exe games\arena-brawl
```

Double-click `hh-game-studio.bat` with no args opens `games/snake`. Pass another folder to open that game.

The window loads that project. Press **Play** — the viewport switches to a 10Hz live view of the play process. Use **WASD / arrows** in the editor window (not a separate player window). Pause/Stop are toolbar buttons; Space is a game key while playing. Do not open the repo root as the project.

## Snake (`games/snake`)

Classic grid snake. **A/D** or arrows: `move_x`. **W/S** or arrows: `move_y`. The snake keeps the last non-zero direction and will not reverse 180°. Eat the orange food to grow; hit a wall or yourself and it stops.

## Platformer (`games/platformer`)

Walk/jump on a longer floor plus ledges and pick up **three** coins. Camera follows the player. **A/D** or arrows: walk. **Space / W / Up**: jump.

## Scrap Yard (`games/scrap-yard`)

Original 2-player night-market brawler (not a Superfighters clone). **Vela** (cyan, tall) vs **Rook** (rust, wide). Map, names, and silhouettes are ours. Button layout follows the public 2P stick-fighter scheme:

| | P1 Vela | P2 Rook (solo) |
|---|---|---|
| Move | Left / Right | A / D |
| Jump / aim up | Up | W |
| Crouch / aim down | Down | S |
| Melee / pickup (crouch+melee) | N | 1 |
| Hold to aim, release to shoot | M | 2 |
| Hold to aim, release grenade | Comma | 3 |
| Power (after clock pickup) | Period | 4 |

Double-tap left/right to sprint. Pick up the **pipe**, **blaster**, **scrap bomb**, or **clock**. Vela has light AI so one person can play Rook with WASD.

## Arena brawl (`games/arena-brawl`)

Smaller two-fighter ring. **P1** arrows + N/J. **P2** WASD + 1. They no longer share one input (that made both walk together).

## Add another game

Copy the same layout (`project.json`, `scenes/main.gscene.json`, `scripts/`, `inputmap.json`) under `games/<name>/`, then open that folder the same way.
