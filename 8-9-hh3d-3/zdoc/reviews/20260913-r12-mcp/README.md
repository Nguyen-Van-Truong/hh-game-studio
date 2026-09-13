# GT-03/GT-04 MCP adapter bake-off (read-only review)

Date: 2026-09-13  |  Status: DESIGN INPUT / NOT ACCEPTANCE
Scope: compare external MCP bridges only as optional adapters over the typed host. The native host, semantic commands, postcondition/readback, hash, lease and critic gates remain authoritative.

## Decision

Do not select an external repository as the studio core from README claims. Run a time-boxed fixture spike after GT-01 and GT-02 foundations are accepted. Default transport is localhost, read-only, with explicit tool allow-list. `execute_code`, arbitrary GDScript, `node_call`, shell/process execution, filesystem escape and destructive tools are denied in the default profile. Any write profile must pass the same semantic-command, unique-command-id, lease, atomic-save, postcondition and evidence gates as the native path.

The current plan is consistent with this approach: its S21 addendum keeps MCP adapter-only, schedules the spike in GT-03/GT-04, keeps Blender export as an explicit Blender-to-GLB job, and leaves the first full Blender→GLB→Godot→Play→observe→repair demo in GT-06. No checkbox or WP order should change for this review.

## Candidate matrix (claims require measurement)

| Criterion | NPGameDev/godot-mcp-toolkit | hybridindie/godot-mcp | Acceptance interpretation |
|---|---|---|---|
| Architecture | Godot plugin + Node/npm bridge, editor/runtime channels | Godot addon + Python MCP server, local stdio/HTTP and websocket bridge | Adapter boundary must map into typed host; no direct privileged bypass |
| Transport | Local websocket bridge is documented; exact version must be pinned | Local stdio/HTTP; token required for non-loopback according to README | Bind loopback only for spike; reject non-loopback and missing/weak token |
| Capability surface | README advertises many operations/tools | README advertises many tools/categories and safety classes | Counts/stars are not proof; enumerate only the allow-listed read operations |
| Safety | Read/write annotations are claimed | Read-only/mutating/destructive/runtime classes are claimed; README warns arbitrary code can write files/run binaries | Verify enforcement experimentally; deny execute_code/node_call even if exposed |
| Runtime separation | Editor and Runtime channels are described | Runtime operations are described | Runtime observation must be immutable/readback; no editor mutation during Play |
| Reconnect/latency | Measure handshake, timeout, reconnect and duplicate command behavior | Same measurements; include token/session expiry | Record p50/p95, bounded retry, idempotency and no lost ACK |
| Maintenance | Public repository activity and version must be frozen at tested commit | Public repository activity and version must be frozen at tested commit | Do not infer reliability from commit/star counts; require reproducible lockfile and offline replay |
| License/notices | Verify repository/plugin/bridge licenses and transitive npm dependencies | Verify repository/addon/server licenses and transitive Python dependencies | Manifest each component before redistribution; legal review for incompatible terms |

The external agent's exact CI/test/star/tool-count numbers are self-reported and were not independently established here. They must not be used as a selection criterion.

## Fixture spike acceptance checklist

1. Record repository URL, exact commit/tag, addon/bridge versions, lockfiles, runtime versions and SHA-256/SHA-512 hashes.
2. Run one isolated sample fixture and one adapter process at a time; no install into the product core and no network after dependencies are cached.
3. Prove localhost binding; reject public interfaces, malformed origin/token, replayed or expired token, and path traversal/UNC/ADS/reparse/symlink escapes.
4. Enumerate tools from the bridge and assert default deny for `execute_code`, `eval`, `node_call`, shell/process, arbitrary file write/delete, project import/export and destructive runtime controls.
5. Exercise read-only operations: project/scene metadata, node tree, property read, runtime status and captured observation. Compare canonical JSON and source/hash with the native host.
6. If a write profile is tested, require semantic command schema, unique `command_id`, dedup on retry, lease ownership/fencing, atomic save, postcondition readback and rollback checkpoint. A bridge ACK before readback is a failure.
7. Verify editor and Play are separate processes; pause/stop priority, cancellation/drain, no editor mutation of live runtime state, and no leaked secret in logs/screenshots.
8. Measure 30 cold and 100 warm calls: p50/p95 latency, timeout, reconnect, duplicate delivery, ordering and bounded resource use. Set fixture-specific budgets before comparing candidates.
9. Kill/restart bridge and Godot during an in-flight request; prove no partial write, stale lease or false success. Capture host exit and leftover-process proof.
10. Run offline replay from the frozen manifest on a clean machine/profile. Any undeclared download, telemetry or non-deterministic output is a gap.
11. Produce redacted evidence with run id, command id, seed, source hash, bridge hash, timestamps and repro commands. Two independent read-only critics must review the same frozen source/evidence before adapter acceptance.
12. Keep a fallback native-host path and a kill switch. Adapter failure must degrade to “unavailable” without blocking local editing or corrupting the fixture.

## Sources and limits

- [NPGameDev/godot-mcp-toolkit](https://github.com/NPGameDev/godot-mcp-toolkit) — repository README and code are candidates, not proof of the claims above.
- [hybridindie/godot-mcp](https://github.com/hybridindie/godot-mcp) — repository README explicitly describes broad capabilities and warns that arbitrary-code operations can write files/run binaries; this is why default deny is mandatory.
- [Godot 4.7 3D formats](https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html) — GLB/glTF is the portable handoff; Blender export remains outside MCP.
- [Blender Python threading guidance](https://docs.blender.org/api/main/info_gotchas_threading.html) — do not assume unsafe background `bpy` threading; use a bounded process/CLI job.

This report does not install, run, import or redistribute either repository and does not change plan state.
