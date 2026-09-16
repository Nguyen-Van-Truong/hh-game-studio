# External MCP adapter sequencing

AUTHORITY=0. Read-only design input, not fixture compatibility evidence.
No upstream addon, bridge, dependency or service was installed or executed.

Pinned upstream references inspected on 2026-09-17:

- NPGameDev/godot-mcp-toolkit: `10a4508e880244c66a3f04861b2e22872c307247`.
  Its [architecture](https://github.com/NPGameDev/godot-mcp-toolkit/blob/10a4508e880244c66a3f04861b2e22872c307247/docs/architecture/README.md)
  separates editor/runtime channels and uses a separate npm bridge. Loopback
  and a per-instance token are described, with an editor-side trust boundary;
  see the pinned [security policy](https://github.com/NPGameDev/godot-mcp-toolkit/blob/10a4508e880244c66a3f04861b2e22872c307247/SECURITY.md).
  The bridge still needs its own exact pin before any measured comparison.
- hybridindie/godot-mcp: `48f34e7d28d65cfea456cc2641e13c3058caa3d6`.
  Its [README](https://github.com/hybridindie/godot-mcp/blob/48f34e7d28d65cfea456cc2641e13c3058caa3d6/README.md)
  describes inspection enabled by default and other toolsets enabled explicitly.
  Stdio and loopback HTTP do not require its HTTP bearer token by default;
  non-loopback HTTP does. These upstream defaults do not establish the HH
  session/catalog/lease contract. The [safety layer](https://github.com/hybridindie/godot-mcp/blob/48f34e7d28d65cfea456cc2641e13c3058caa3d6/mcp_server/safety.py)
  is a separate part of that server, not an HH authority grant.

The coordinator's inference: neither repository's documentation can substitute
for measured fixture conformance. Replacing the working typed host during
GT-03 would also require a new authority, receipt and recovery integration.
Keep the implemented host and finish its editor/Blender gates first. Perform
the bounded native compatibility comparison in GT-09, where client adapters
are verified against stable operation contracts. This changes sequencing only;
it does not accept or reject either upstream implementation on README claims.

GT-09 still owes exact addon/bridge/dependency pins, a private fixture, read-only
default, denial of arbitrary code/node calls, authenticated transport mapping,
measured postconditions and unchanged-source/exit evidence. Any chosen adapter
must preserve existing command IDs, revisions, leases, response replay and Stop
semantics. Unsupported mappings must be explicit. No external adapter is
advertised as supported before those checks and the gate's independent reviews.
