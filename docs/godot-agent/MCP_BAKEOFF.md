# MCP candidate bake-off scorecard (R1-WP2)

Audit date: **2026-08-20** (Asia/Saigon). Method: GitHub API for pin SHA/tag/LICENSE,
then `git fetch --depth 1 origin <sha>` into `third_party/mcp-staging/<id>/`.
Source trees were scanned in place and **not** committed (LICENSE + `PIN.json` only).
**Not** copied into `godot/plugin-project/`. **Not** installed via `npx -y`, Asset
Library “latest”, or GitHub default-branch floating tip.

Our Godot pin: **4.7.1-stable** (`a13da4feb`). Invariants: A8–A9, A16, E2.
Threat model: [THREAT_MODEL.md](THREAT_MODEL.md) T1/T4/T5/T6.

This WP is **audit only**. R1-WP3 runs E2E on the shortlist using disposable copies.
Do not enable any candidate in the production fixture.

## Verdict

Spike shortlist is **not** permission to vendor or to enable `OWNER_AUTOPILOT`.
G1 must not ship either shortlist candidate as-is.

| ID | Candidate | Fail-hard bake-off? | Fail-hard enable as-is? | Spike shortlist? |
|----|-----------|---------------------|-------------------------|------------------|
| A | [satelliteoflove/godot-mcp](https://github.com/satelliteoflove/godot-mcp) | **no** | **yes** — no session token, `godot_exec`, no UndoRedo, empty success, runtime autoload in export | **yes** |
| B | [KeeVeeG/godot-mcp](https://github.com/KeeVeeG/godot-mcp) | **yes** — editor/game `evaluate_expression` + `OS.execute` git clone + no token + WebSocket listen without loopback host | **yes** | **no** |
| C | [beckettlab/beckett-godot-mcp](https://github.com/beckettlab/beckett-godot-mcp) **Lite** MIT tree | **no** | **yes** — `call_method`/`Object.callv` and missing token. **Full (itch): fail-hard E2** — do not buy | **yes (Lite only)** |
| D | [Sods2/godot-mcp](https://github.com/Sods2/godot-mcp) | **yes** — TCP `:6008` no token; disk-first `.tscn` writes | **yes** | **no** |

**Shortlist (max two):** A `satelliteoflove/godot-mcp`, C Beckett **Lite**.

**Fail-hard bake-off / eliminated from R1-WP3:** B KeeVeeG; D Sods2; Beckett **Full** (commercial, E2).

R1-WP3 may bake-off A and C on disposable copies with eval/`call_method` disabled
and token required. G1 (R1-WP5) must not vendor either as-is. Fallback remains
“write the minimal sidecar + plugin ourselves” if bake-off cannot close the
MUST-PATCH rows.

Do **not** run `npx` with `-y` against a floating `latest` tag, and do not
install `@satelliteoflove/godot-mcp` via unpinned `npx` (A16 / T5). Pin the SHA below.

---

## A — satelliteoflove/godot-mcp (primary)

### Pin

| Field | Value |
|-------|--------|
| Repo | https://github.com/satelliteoflove/godot-mcp |
| Pin SHA | `1b7d40537240fd54300f54bf6fda1ea91f06c878` (default `main` at fetch) |
| Commit date | 2026-08-11T01:12:35Z (dependabot bump of server lockfile) |
| Latest GitHub **release** tag | `godot-mcp-v4.1.0` at `59da3d0dae06c79cc970d83828e54b2fc16d0769` (2026-06-20) — **older than pin**; we pin the commit SHA, not “latest” |
| Addon `plugin.cfg` | version `4.1.0`, `godot_version_min="4.5"` |
| npm | `@satelliteoflove/godot-mcp` 4.1.0; lockfile resolved `@modelcontextprotocol/sdk` **1.30.0**, `ws` **8.21.2**, `zod` ^4.3.6 |
| Staging | `third_party/mcp-staging/satelliteoflove-godot-mcp/{LICENSE,PIN.json}` |

### LICENSE SPDX

**MIT** — `third_party/mcp-staging/satelliteoflove-godot-mcp/LICENSE` (upstream
`LICENSE`). File starts `MIT License` / `Copyright (c) 2025`. GitHub SPDX `MIT`.

### Godot version vs 4.7.1-stable

Claim: **Godot 4.5+** (Logger / `OS.add_logger`). Compatible with **4.7.1-stable**.
Not tested in *this* repo. Upstream CI is Node 20 unit/protocol tests, not Godot 4.7.1.

### Contributors / release / CI

- Contributors: `satelliteoflove` (173), bots, 3 small humans. Active through 2026-08.
- Releases: automated (`release-please` + `release.yml`); addon zip on each tag.
- CI: `.github/workflows/ci.yml` — `npm ci` / build / vitest coverage / protocol smoke on `main`.
- README documents `npx -y @satelliteoflove/godot-mcp` — **forbidden here** (T5).

### Threat checklist

| Check | Result | Evidence |
|-------|--------|----------|
| token / loopback | **FAIL** — loopback default, **no session token** | Addon `TCPServer.listen(port, bind_address)` defaults `127.0.0.1` (`godot/addons/godot_mcp/websocket_server.gd`). WSL/Custom bind modes allow non-loopback. No bearer/token handshake. Single-client 4001 is not auth. |
| port | **FAIL** — fixed **6550** | `DEFAULT_PORT := 6550`; server `GODOT_PORT` default 6550. Plan §2.2 wants random port + no fixed-port scan. |
| eval / shell / `Object.call` | **FAIL** — `godot_exec` runs GDScript in the **game**; PowerShell for WSL IP | `server/src/tools/exec.ts` + `game_bridge` `GDScript.new()` / `callv("_mcp_run")`. Denylist (`mcp_exec_guard.gd`) is documented **“accident guard, NOT a security boundary”**. `plugin.gd` `OS.execute("powershell", …)` with a fixed literal (WSL bind). |
| file write vs UndoRedo | **FAIL** — **zero** `EditorUndoRedoManager` in the tree | v4: create scene/node by writing `.tscn`. `update_node` does `node.set(key, …)` (`commands/node_commands.gd`). `reparent_node` calls `node.reparent` with no undo. |
| readback | **FAIL** on property set | `update_node` returns `_success({})` with no property echo. `get_node_properties` / `get_scene_tree` exist as separate tools (agent must remember to call them). Runtime digest/watch is strong when used. |
| export-strip | **FAIL** | `plugin.gd` registers autoload `MCPGameBridge`. Comment in `mcp_game_bridge.gd`: “The autoload ships in exports”. No `EditorExportPlugin` strip. |

### Fail-hard?

**No** for R1-WP3 bake-off (best self-verify: freeze/step, input, runtime digest, screenshots).
**Yes to enable as-is under OWNER_AUTOPILOT** until token + random port, `godot_exec` off,
UndoRedo (or atomic file + conflict check), postcondition readback, and export strip.

### Shortlist

**Yes — first shortlist.** Prefer as *reference* for runtime/self-verify, not a drop-in vendor.

---

## B — KeeVeeG/godot-mcp

### Pin

| Field | Value |
|-------|--------|
| Repo | https://github.com/KeeVeeG/godot-mcp |
| Pin SHA | `9ea1a41b9ed6cd819c602a37cc111c50017707d8` (`master` at fetch) |
| Commit date | 2026-07-12T14:54:56Z (favicon after the release) |
| Release tag | `v1.1.0` at `a08c705f66fd907e5b57ceed905d31496482b85d` (2026-07-12) |
| Addon `plugin.cfg` | version **`1.0.0`** (drifts from npm/package `1.1.0`) |
| npm | `@keeveeg/godot-mcp` 1.1.0; **no `package-lock.json`**; caret `@modelcontextprotocol/sdk` ^1.12.1, `ws` ^8.18.0, `zod` ^3.24.0 |
| Staging | `third_party/mcp-staging/keeveeg-godot-mcp/{LICENSE,PIN.json}` |

### LICENSE SPDX

**MIT** — `third_party/mcp-staging/keeveeg-godot-mcp/LICENSE` (`Copyright (c) 2026 KeeVeeG`).

### Godot version vs 4.7.1-stable

Claim: **Godot 4.x, tested with 4.7**. Compatible in principle. `variant_codec.gd` notes a
Godot 4.7 `Color.html()` bug workaround. No Godot CI.

### Contributors / release / CI

- Single contributor `KeeVeeG` (295). Last push 2026-07-12.
- One release `v1.1.0` with addons zip.
- `.github/workflows/deploy.yml` is **GitHub Pages only** — no test/build CI.
- README: 300+ tools; “download the latest addons zip” — we do not follow “latest”.

### Threat checklist

| Check | Result | Evidence |
|-------|--------|----------|
| token / loopback | **FAIL** — no token; plugin **scans** 6505–6514 | `addons/godot_mcp/websocket_client.gd` `ws://localhost:%d`. Node `WebSocketServer({ port })` **omits `host`**, so Node `ws` binds **all interfaces** (`::` / `0.0.0.0`), not loopback. |
| port | **FAIL** — fixed range **6505–6514** | `WS_BASE_PORT = 6505`, `MAX_SESSIONS = 10`. Plugin auto-scan is the anti-pattern in plan §2.2. |
| eval / shell / `Object.call` | **FAIL-HARD** | MCP tool `evaluate_expression` (`server/src/tools/debugging.ts`) → `debugging_commands.gd` `_execute_in_editor` (`GDScript.new()` + `func eval()`). Game-context eval via debugger `evaluate`. `OS.execute("git", ["clone", url, …])` and `godot --install-addon` in `addon_management_commands.gd`; `OS.execute("attrib", …)` / `git init` in `project_creation_commands.gd`. |
| file write vs UndoRedo | **PASS-WITH-GAPS** | Real `EditorUndoRedoManager` helper (`utils/undo_helper.gd`) on many scene/node tools. File/git/addon paths mutate disk directly. |
| readback | **PARTIAL** | Add-node returns `{name, path, type}`. `_update_property` returns a **message** only, not the stored value. |
| export-strip | **FAIL** | `add_autoload_singleton` for `mcp_runtime.gd` + `ProjectSettings.save()`. `export_commands.gd` can set `exclude_filter` to **empty**. |

### Fail-hard?

**Yes.** Arbitrary editor eval + subprocess git clone + unauthenticated
all-interface (or scan-range) socket. Plan already says: coverage inventory only,
do not copy 300+ tools. Not a bake-off candidate.

### Shortlist

**No.** Keep as a *capability list* to read, not to enable.

---

## C — Beckett Lite (`beckettlab/beckett-godot-mcp`) — MIT GitHub tree only

### Pin

| Field | Value |
|-------|--------|
| Repo | https://github.com/beckettlab/beckett-godot-mcp |
| Pin SHA | `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d` (`main` = tag `v1.13.0`) |
| Commit date | 2026-08-11T02:22:38Z |
| Release tag | **`v1.13.0`** (same SHA) |
| Addon `plugin.cfg` | version `1.13.0` |
| Commercial | **Full** is itch $15 (lifetime). **Not audited, not purchased, not used for core acceptance (E2).** |
| Staging | `third_party/mcp-staging/beckett-godot-mcp-lite/{LICENSE,PIN.json}` |

Lite trim check on this SHA: `addons/beckett/tools/runtime_tools.gd` (Full sentinel)
**absent**. Present: scene/script/reflection/runtime_observe. `call_method` still
ships in Lite `reflection_tools.gd`.

### LICENSE SPDX

**MIT** — `third_party/mcp-staging/beckett-godot-mcp-lite/LICENSE` (`Copyright (c) 2026 Beckett`).
Also `addons/beckett/LICENSE`. GitHub SPDX MIT applies to **this tree**, not Full.

### Godot version vs 4.7.1-stable

Claim: **Godot 4.2+**; verified 4.4.1 / 4.6.2 / **4.7**. CI matrix includes
**`4.7.1`** on Windows/Linux/macOS (`.github/workflows/ci.yml` comments pin exact
tags, “never latest”). Best version match of the four.

### Contributors / release / CI

- Single public contributor `beckettlab` (37).
- Frequent tags through v1.13.0.
- Strong CI: headless Godot + live HTTP MCP probe; engine pins include 4.7.1.
- Zero-sidecar (HTTP inside the editor). Conflicts with our chosen sidecar
  architecture, but is valid for a spike.

### Threat checklist

| Check | Result | Evidence |
|-------|--------|----------|
| token / loopback | **PARTIAL** | HTTP `127.0.0.1` + Origin/Host checks (`mcp_server.gd`). Token default-on for **fresh** setups; **upgrade path leaves auth off** if a tokenless `.mcp.json` already exists; `BECKETT_AUTH=0` kill-switch. Token file `res://.beckett/token` (gitignored by addon). Token rides in URL path. |
| port | **FAIL** — default **8770**, walk +0..9 | `client_config.gd` `DEFAULT_PORT := 8770`. Better than a hard fail-if-busy, still a well-known port. |
| eval / shell / `Object.call` | **FAIL** on Lite `call_method` | `reflection_tools.gd` `_call_method` → `obj.callv(method, prep["args"])`. `csharp_tools.gd` `OS.execute(dotnet, …)` (compile-check). `jobs.gd` `OS.create_process` for export (Full module; not in this Lite tree). `panel.gd` `OS.shell_open(UPGRADE_URL)` — opens itch, not a tool. Runtime `mcp_runtime.gd` also `callv` for Full `runtime_call` (observe tools remain). |
| file write vs UndoRedo | **PASS** for scene tools | `scene_tools.gd` / `set_property` use `EditorUndoRedoManager`. `write_script` / `write_file` are direct `FileAccess` (scripts: validate-before-write). |
| readback | **PARTIAL** | `set_property` returns the coerced value string, not a re-get. Scene ops return status text. `describe_object` exists. |
| export-strip | **FAIL** | `plugin.gd` `add_autoload_singleton` `MCPRuntime`. No export filter in Lite tree. |

### Fail-hard?

- **Beckett Full (itch/commercial): yes — E2 + T5.** Do not buy. Do not use Full
  tools (`simulate_input`, `runtime_call`, asserts, export jobs, skill packs) for
  core acceptance.
- **Lite MIT: no** for bake-off if `call_method` is disabled and token is on.
  **Yes as-is** if generic `Object.callv` stays on the OWNER_AUTOPILOT surface (T4).

### Shortlist

**Yes — second shortlist (Lite only).** Strong UndoRedo + validate-before-write +
4.7.1 CI. MUST-PATCH: disable `call_method`; require token; do not follow
`npx mcp-remote` in INSTALL.md; never enable Full.

---

## D — Sods2/godot-mcp

### Pin

| Field | Value |
|-------|--------|
| Repo | https://github.com/Sods2/godot-mcp |
| Pin SHA | `78b2cee00d697f117d6875e07675101b867efe70` (`main` at fetch) |
| Commit date | 2026-04-12T15:10:43Z |
| Release tag | **none** |
| Addon `plugin.cfg` | version `0.1.0` |
| npm | `godot-mcp` 0.1.0; lockfile present; `@modelcontextprotocol/sdk` ^1.12.0 |
| Staging | `third_party/mcp-staging/sods2-godot-mcp/{LICENSE,PIN.json}` |

### LICENSE SPDX

**MIT** — `third_party/mcp-staging/sods2-godot-mcp/LICENSE` and
`plugin/addons/godot_mcp_bridge/LICENSE` (`Copyright (c) 2026 Sods2`).

### Godot version vs 4.7.1-stable

Claim: **Godot 4.3+** (plugin README). Compatible in principle. Debugger comments
mention 4.5 log format. **No evidence of 4.7.1 testing.** Stale vs our pin date.

### Contributors / release / CI

- Single contributor `Sods2` (43). 0 stars. Last push **2026-04-12**.
- No GitHub releases.
- CI: Node 24 `npm install` (not `npm ci`) + build + vitest + eslint. No Godot job.

### Threat checklist

| Check | Result | Evidence |
|-------|--------|----------|
| token / loopback | **FAIL** — loopback, **no token** | `bridge_server.gd` `listen(port, "127.0.0.1")`. Any local process can speak JSON-RPC. |
| port | **FAIL** — fixed **6008** | `DEFAULT_PORT = 6008`; plugin always `start()` with that default. |
| eval / shell / `Object.call` | **PARTIAL** | No GDScript eval tool found. Node `execFile` for Godot CLI / tests / export / UID (`src/tools/*.ts`) — argv arrays, not `shell: true`. Still a Godot-binary subprocess surface. |
| file write vs UndoRedo | **FAIL** for the hybrid file path | Live editor handlers use UndoRedo (`inspector_handler.gd` `set_property`, `scene_handler.gd`). `file-tools.ts` `writeFile` / `godot_create_scene` mutate `.tscn` on disk **without** the editor. |
| readback | **PARTIAL** | `set_property` returns `{success, property, value: str(prop_value)}` (echo of input, not re-read). File writes have no editor postcondition. |
| export-strip | **N/A / weak** | No game-runtime autoload. Plugin is `@tool` editor-only (`headless` skip). Still ships if someone copies `addons/` into an export. |

### Fail-hard?

**Yes** for bake-off and vendor. Unauthenticated fixed port + first-class disk
mutation + no release pin + four months stale. Useful only as a hybrid
live-editor/file *reference*.

### Shortlist

**No.**

---

## Dependency / license scan (pin trees)

| ID | Direct runtime deps | SPDX notes |
|----|---------------------|------------|
| A | `@modelcontextprotocol/sdk` 1.30.0, `ws` 8.21.2, `zod` (lockfile) | npm `license: MIT` on lock entries sampled; addon MIT |
| B | same stack, **unlocked carets**, no lockfile | MIT addon; npm not reproducible |
| C Lite | none (GDScript in-editor). `glama/package.json` is a directory shim, not the product | MIT. `dotnet` invoked only if C# tools used |
| D | `@modelcontextprotocol/sdk` (lockfile) | MIT addon + MIT package.json |

No GPL/proprietary SPDX on the four GitHub LICENSE files. **Beckett Full is out of
scope and fail-hard** if required for acceptance.

---

## plugin-project

`godot/plugin-project/` has `project.godot` only (plus gitignored `.godot/`).
**No `addons/` tree, no MCP/GUT plugin enabled.** R1-WP3 must use disposable copies.

---

## What R1-WP3 must not do

- Enable plugins in `godot/plugin-project/`.
- `npx -y …`, Asset Library latest, or clone `main`/`master` without the SHAs above.
- Buy or demand Beckett Full to pass core acceptance.
- Score by tool count (KeeVeeG 300+ is not a point).
