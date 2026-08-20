# Godot agent protocol (R2-WP1 + R2-WP2)

This is the in-house command contract. R2-WP1 is the typed **registry**.
R2-WP2 adds sidecar **session transport**: agent-facing MCP on **stdio**
(newline JSON-RPC) and plugin-facing WebSocket on **127.0.0.1** with an
OS-assigned port. Registry tools are listed but **not dispatched** — they
return `E_UNVERIFIED`, never a live Godot `{ok:true}` mutation.

## Versions

| Name | Value | Role |
|------|--------|------|
| Protocol | `hh-godot-agent/1` | Envelope `protocol`. `hh-godot-agent/2` is rejected (`E_PROTOCOL_VERSION`). |
| Action set | `hh-godot-actions/1` | Catalog generation identity. |
| Action version | `1` | Optional envelope `action_version`. Any other value is `E_ACTION_VERSION`. |
| Variant codec | `hh-godot-variant/1` | Encoded Variant object `{schema,type,value}`. Unknown types reject. |

Negotiation is fail-closed. There is no silent downgrade.

## Envelope (§5.1)

The client may send only intent fields:

```json
{
  "protocol": "hh-godot-agent/1",
  "command_id": "01ARZ3NDEKTSV4RRFFQ69G5FAV",
  "method": "godot.node",
  "action": "add",
  "params": {},
  "precondition": {
    "scene": "res://scenes/main.tscn",
    "scene_hash": "…",
    "target_uid": "…",
    "property_hash": "…"
  },
  "presentation": { "mode": "watch", "duration_ms": 250 }
}
```

`command_id` is a Crockford ULID. `method` is `godot.<group>`. `action` is the
verb. Together they select one ActionDef (`node.add`). `params` are validated
against that ActionDef with **`additionalProperties: false`**.

Optional `action_version` may be sent so a stale client is rejected. The
sidecar (later WP) binds `session_id`, `actor`, `project_id`, policy, and
capability grants after auth. Clients that set those fields are rejected
(`E_CLIENT_ESCALATION`): `session_id`, `actor`, `actor_id`, `project_id`,
`policy`, `profile`, `capability`, `capability_grant`, `grants`.

## Result

Success is schema-only in this WP (no Godot process). A result must include
`postcondition: { "verified": bool, "checks": [string] }`. `{ "ok": true }`
alone is invalid (`E_MISSING_REQUIRED`). `verified: true` is reserved for a
later readback WP; registry accept returns `verified: false` and names the
declared postcondition in `checks`.

## Tool shape (discriminated method + action)

R1 left the MCP surface open: flat tools, discriminated unions, or a lazy
registry. This WP chooses **few domain tools + an action discriminator**:

- one MCP tool per §5.2 group (`godot.project`, `godot.node`, …) — about 20
  tools, **not** one tool per verb
- `action` enum selects the verb
- `params` are then checked against the ActionDef input schema

Coverage is the action catalog, not the tool count. Generated
`bridge/generated/mcp-tools.json` is the surface; `plugin-validator.json` is
the data the future plugin will use to validate a second time.

## Catalog rules

Each ActionDef declares `side_effect`, `undo`, `timeout_ms`, `cancellable`,
`required_policy` (declaration only: `OBSERVE` / `EDIT` / `OWNER_AUTOPILOT`),
input/output JSON Schema, error codes, a postcondition **name**, and
`action_version`. `undo` may be `none` or `n/a` only for `read` / `view`.
Destructive actions declare `checkpoint_required`. Dispatch is registry
lookup. There are no live Godot handlers in this WP.

`capabilities.describe` requires `kind` ∈ `version` | `class` | `property` |
`method` | `action`. The contract matrix runs the four invalid lanes plus one
positive **for each kind**.

## Generated artifacts

One generator (`npm run generate` in `bridge/`):

| Path | What |
|------|------|
| `bridge/generated/mcp-tools.json` | Domain tools + discriminator |
| `bridge/generated/cli-help.txt` | Human catalog |
| `bridge/generated/plugin-validator.json` | Data-only schemas |
| `docs/godot-agent/ACTIONS.md` | Catalog table |
| `docs/godot-agent/CONTRACT_MATRIX.md` | Cases the tests **execute** |

All carry `AUTO-GENERATED` / `DO NOT EDIT`. Dirty files after generate fail CI.

## Vendor boundary (do not copy into `bridge/src`)

G1 chose in-house thin. Do **not** vendor or depend on
`@satelliteoflove/godot-mcp`, Beckett, KeeVeeG, or Sods2 packages. Product
trees must not grow `MCPGameBridge`, `godot_mcp`, `call_method`,
`Object.callv`, or `evaluate_expression` surfaces. Those names stay out of
`bridge/src/` (even comments). This file is the reject note; the registry
does not implement them.

Stdio MCP is an in-house JSON-RPC speaker. The official SDK is allowed only as
an exact pin if added later; this tree does not depend on it (the 1.30 line
pulls HTTP/SSE stacks this WP must not expose). Validation uses the stdlib
walker in `bridge/src/registry/schema.ts`. Session token lives only under
`%LOCALAPPDATA%/HHGodotAgent/` (current-user ACL), never in the git project,
`.godot/`, `.hh-agent/`, or logs.
