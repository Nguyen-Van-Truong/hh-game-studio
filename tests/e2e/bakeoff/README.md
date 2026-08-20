# R1-WP3 MCP bake-off (disposable copies)

Same scenario on shortlist **A** (`satelliteoflove/godot-mcp`) and **C**
(Beckett **Lite**). Score by workflow correctness, self-verify, undo,
security, maintainability, and Godot **4.7.1-stable** compatibility —
**not** by tool count.

This is a spike. It is **not** permission to vendor either candidate or
to enable MCP in `godot/plugin-project/`.

## Pins (A16)

From [`docs/godot-agent/MCP_BAKEOFF.md`](../../../docs/godot-agent/MCP_BAKEOFF.md)
and [`pins.json`](pins.json):

| ID | Repo | SHA |
|----|------|-----|
| A | https://github.com/satelliteoflove/godot-mcp | `1b7d40537240fd54300f54bf6fda1ea91f06c878` |
| C Lite | https://github.com/beckettlab/beckett-godot-mcp | `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d` |

Do **not** `npx -y`, Asset Library “latest”, or clone floating `main`.
Do **not** buy Beckett Full (E2).

## Security constraints (spike patches on copies only)

Applied by `run_bakeoff.py` to gitignored work trees, never to
`godot/plugin-project/`:

- Bind **127.0.0.1** only.
- Require a **session token** (not logged, not committed).
- Disable **eval / `godot_exec` / `call_method` / `Object.callv`**.
- Wrong path / token / schema / those disabled actions must fail with a
  **typed error**.

## How to run

From the repo root (stdlib Python). Installs nothing via npm.

```text
python tools/godot/doctor.py --install
python tests/e2e/bakeoff/run_bakeoff.py
python tests/bootstrap/test_bakeoff_guard.py
```

The driver:

1. Refuses any path under `godot/plugin-project/` (especially `addons/`).
2. Copies `godot/test-projects/minimal-2d` into `tests/e2e/bakeoff/work/`
   (gitignored). The fixture itself is not mutated in place.
3. Fetches A and C at the pin SHAs into the same work tree.
4. Records every scenario row even when a step cannot run (honest
   `SKIP`/`FAIL`).
5. Rewrites [`SCORECARD.md`](SCORECARD.md).

Optional: `--gui` launches the Godot GUI binary for editor-visible
screenshots. Default is headless editor (same shape as Beckett’s own CI).

Work trees, `node_modules/`, `.godot/`, and large evidence blobs are
gitignored.

## Human Godot (no MCP)

Double-click [`hh-godot-editor.bat`](../../../hh-godot-editor.bat) — pin
4.7.1-stable on `godot/test-projects/minimal-2d`. No addon, no bake-off.

## Driver vs Node MCP

A’s production shape is Node stdio MCP → WebSocket `:6550`. This spike
talks to the **editor addon WebSocket JSON** directly (stdlib, no `npx`)
after the security patches. C is probed over **HTTP JSON-RPC** on
loopback, same as Beckett `tests/ci-smoke.ps1`, with token **on**
(`BECKETT_AUTH` kill-switch is not used).
