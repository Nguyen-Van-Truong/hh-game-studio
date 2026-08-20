# G1 base lock (R1-WP5)

`decision_id: GODOT-G1-BASE-2026-08-20`
`status: approved` (architecture gate G1, not a human E1–E4)
`g1_base: in-house-thin`
`mcp_vendor: none`

Machine pin: [`.hh-agent/capability-lock.json`](../../.hh-agent/capability-lock.json).
Decision record: [`docs/DECISIONS.md`](../DECISIONS.md).
Bake-off: [`MCP_BAKEOFF.md`](MCP_BAKEOFF.md) (verdict table unchanged; enable-as-is
fail-hard stays **yes**). License: [`NOTICE`](NOTICE).

This WP does **not** create `godot/plugin-project/addons/hh_agent/` and does **not**
add an MCP SDK to `bridge/`. Those trees are named for R2.

## Chosen base — (3) in-house thin

| Field | Pin |
|-------|-----|
| Engine | Godot **4.7.1-stable** only. `4.7.1.stable.official.a13da4feb` / commit `a13da4feb8d8aefc283c3763d33a2f170a18d541`. Refuse `4.7.2*` and 4.8. |
| Future plugin | `godot/plugin-project/addons/hh_agent/` — **not created this WP** |
| Future sidecar | `bridge/` TypeScript MCP — scaffold `hh-godot-bridge` 0.0.0, Node 24.19.0, existing lockfile. No MCP SDK / `npx` this WP. |
| Schema ownership | Ours, R2 `bridge/src/registry/` |
| Upstream boundary | **none** (reference-only) |
| Patch queue | **do not patch-vendor** |
| Update cadence | **none** for MCP candidates (re-audit only if a later WP proposes vendor) |

## Rejected

- **(1) vendor exact MIT commit** — do not copy A/C/B/D source into product trees.
- **(2) depend exact package** — do not `npx -y`; do not depend
  `@satelliteoflove/godot-mcp` (or Beckett / KeeVeeG / Sods2 packages).
  npm `@satelliteoflove/godot-mcp@4.1.0` (tag `godot-mcp-v4.1.0`, SHA
  `59da3d0dae06c79cc970d83828e54b2fc16d0769`) is **not** candidate A.

Plan default was satelliteoflove **if** self-verify/security **đạt**. They did
**not** đạt for enable-as-is. MUST-PATCH leftover stays open. Weighted C>A and
spike shortlist do **not** authorize vendor. This is the WP-allowed fallback,
not a silent rewrite of plan §0.2.

## Why not vendor A / C

- **A** `1b7d40537240fd54300f54bf6fda1ea91f06c878`: no session token, fixed port
  6550, `godot_exec`, **zero UndoRedo**, empty `update_node` success, `MCPGameBridge`
  ships in export. Spike security was patched **in our driver**, not upstream.
- **C Lite** `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d`: `call_method` /
  `Object.callv`, missing token on upgrade path, zero-sidecar **conflicts** with
  the chosen TypeScript sidecar (§0.2 / §2.2). Full itch = E2 fail-hard (do not buy).
- Bake-off: agent-driven undo/redo **FAIL for both** (undo=0). Dummy PNG = SKIP.

## Reference-only SHAs (must not appear as vendored product source)

| ID | SHA | Role |
|----|-----|------|
| A | `1b7d40537240fd54300f54bf6fda1ea91f06c878` | reference: runtime freeze/step/input/digest |
| C | `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d` | reference: validate-before-write + live EditorUndoRedoManager on scene tools |
| B | `9ea1a41b9ed6cd819c602a37cc111c50017707d8` | fail-hard / coverage inventory only |
| D | `78b2cee00d697f117d6875e07675101b867efe70` | fail-hard / coverage inventory only |

Staging stays `third_party/mcp-staging/<id>/{LICENSE,PIN.json}` only.

## Production fixture

`godot/plugin-project/` has **no** `addons/` and **no** `plugin.cfg`. G1 closed
every remaining MCP plugin candidate as a production vendor. No fork Godot C++.
