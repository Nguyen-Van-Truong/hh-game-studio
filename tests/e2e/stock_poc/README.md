# R1-WP4 stock-only vertical slice

Disposable EditorPlugin + Python driver. **Not** MCP, **not** `hh_agent`, **not** GUT.
Never copied into `godot/plugin-project/`.

## Run

From the repo root:

```text
python tools/godot/doctor.py --install
python tests/e2e/stock_poc/run_slice.py --runs 20
python tests/bootstrap/test_stock_poc.py
```

`--runs 20` is the default. Each iteration copies `godot/test-projects/stock-poc/`
into gitignored `tests/e2e/stock_poc/work/run-NN/`.

The driver:

1. Refuses any path under `godot/plugin-project/`.
2. Launches pinned Godot **4.7.1-stable** headless editor.
3. Asks `addons/hh_stock_poc` (JSON-lines on 127.0.0.1 + session token) to
   create CharacterBody2D / sprite / camera / collision / Label via
   EditorUndoRedoManager, attach typed `player.gd`, set InputMap, save.
4. Starts a **separate** game process (`--fixed-fps 60`) that injects
   `move_right`, writes `play.json` position delta, attempts a screenshot.
5. Reopens the saved scene and asserts unique node names (no Player2).

Dummy/headless gray PNGs (the ~619-byte case) are **SKIP**, never PASS.
Headless Inspector-visible is recorded as **GAP**; gameplay 20/20 can still pass.

## Human launchers

- Default, no MCP: `hh-godot-editor.bat` → `godot/test-projects/minimal-2d`
- This fixture GUI: `hh-stock-poc.bat` → `godot/test-projects/stock-poc`
