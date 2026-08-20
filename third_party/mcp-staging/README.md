# MCP candidate staging (R1-WP2)

G1 (R1-WP5, `GODOT-G1-BASE-2026-08-20`) closed all four as production vendors.
This directory is audit pins only. The product base is in-house thin (future
`godot/plugin-project/addons/hh_agent/` + `bridge/` in R2 — not created here).

Audit clones of the four plan §2.3 MIT candidates. **LICENSE + `PIN.json` only**
are committed. Full source was fetched at the pin SHA, grepped for the threat
checklist, then discarded so this repo does not vendor addons.

Do **not** copy anything here into `godot/plugin-project/`.
Do **not** `npx -y latest` or clone GitHub default branch as the pin.

| Dir | Pin SHA | SPDX |
|-----|---------|------|
| `satelliteoflove-godot-mcp/` | `1b7d40537240fd54300f54bf6fda1ea91f06c878` | MIT |
| `keeveeg-godot-mcp/` | `9ea1a41b9ed6cd819c602a37cc111c50017707d8` | MIT |
| `beckett-godot-mcp-lite/` | `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d` | MIT (Lite tree) |
| `sods2-godot-mcp/` | `78b2cee00d697f117d6875e07675101b867efe70` | MIT |

Scorecard: [`docs/godot-agent/MCP_BAKEOFF.md`](../../docs/godot-agent/MCP_BAKEOFF.md).

Beckett **Full** (itch) is not staged and is fail-hard (E2).
