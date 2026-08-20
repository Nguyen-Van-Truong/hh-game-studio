# SBOM baseline (R0-WP4)

Not a vendor SBOM and **not** a CycloneDX dump. This is the license/pin baseline
before R1 clones anything into `third_party/`. Pins come from
[`docs/VERSIONS_GODOT.md`](../VERSIONS_GODOT.md) and `tools/godot/pin.json`.
Fetched **2026-08-20**. Do not bump Godot to 4.7.2.

Upgrade of Godot or an upstream MCP is its own WP (A16).

---

## In-tree / pinned toolchain

| Component | Version | SPDX | License URL | Notes |
|-----------|---------|------|-------------|--------|
| Godot Engine Standard | **4.7.1-stable** (`a13da4feb` / `4.7.1.stable.official.a13da4feb`) | MIT | https://raw.githubusercontent.com/godotengine/godot/4.7.1-stable/LICENSE.txt | Also https://raw.githubusercontent.com/godotengine/godot/4.7.1-stable/COPYRIGHT.txt — **do not vendor the engine tree**. |
| GUT (Godot Unit Test) | **9.7.1** / `v9.7.1` commit `aeb5d4f3f7f0a6c9b5e178876d6c99b791fda605` | MIT | https://raw.githubusercontent.com/bitwes/Gut/v9.7.1/addons/gut/LICENSE.md | Copy in-repo: `third_party/gut/LICENSE.md`. Addon **not** copied into `godot/plugin-project/` in R0. |
| Node.js Active LTS | **24.19.0** (line 24, Krypton) | MIT | https://raw.githubusercontent.com/nodejs/node/v24.19.0/LICENSE | Sidecar runtime pin. Doctor does not install Node in R0-WP3. |
| TypeScript | **5.9.3** exact (`bridge/package.json`) | Apache-2.0 | https://raw.githubusercontent.com/microsoft/TypeScript/v5.9.3/LICENSE.txt | Compiler only. Not an MCP candidate. |
| `@types/node` | **24.13.3** exact | MIT | https://raw.githubusercontent.com/DefinitelyTyped/DefinitelyTyped/master/LICENSE | DevDependency. |

Godot trademark: https://godot.foundation/policies-and-procedures/trademark-policy

---

## MCP candidates — status **to-audit** (do not clone)

R1-WP2 pins commits, walks dependencies, and may **fail-hard**. R0 only records
GitHub SPDX + LICENSE URL. None of the four public repos is marked fail-hard
today (all SPDX **MIT** on 2026-08-20).

Do **not** copy these into `third_party/` or enable them in `plugin-project`.

| ID | Repository | GitHub SPDX (2026-08-20) | LICENSE URL | Status | Fail-hard later if |
|----|------------|--------------------------|-------------|--------|--------------------|
| A | [satelliteoflove/godot-mcp](https://github.com/satelliteoflove/godot-mcp) | MIT | https://raw.githubusercontent.com/satelliteoflove/godot-mcp/main/LICENSE | **to-audit** | Arbitrary eval/shell/`Object.call`, no token, fixed-port bind, runtime left in export, or LICENSE drift off MIT. |
| B | [KeeVeeG/godot-mcp](https://github.com/KeeVeeG/godot-mcp) | MIT | https://raw.githubusercontent.com/KeeVeeG/godot-mcp/master/LICENSE | **to-audit** | Same security checklist; 300+ tools must not skip UndoRedo/readback. |
| C | [beckettlab/beckett-godot-mcp](https://github.com/beckettlab/beckett-godot-mcp) **Lite** | MIT (this GitHub tree) | https://raw.githubusercontent.com/beckettlab/beckett-godot-mcp/main/LICENSE | **to-audit** (Lite only) | **Full** edition is a **separate commercial** product (itch). Using Full for core acceptance is **E2** + **fail-hard** (non-MIT / paid). Plan: Lite only; do not buy. |
| D | [Sods2/godot-mcp](https://github.com/Sods2/godot-mcp) | MIT | https://raw.githubusercontent.com/Sods2/godot-mcp/main/LICENSE | **to-audit** | Same checklist as A/B. |

Plan references: §2.3, §12 MCP baseline URLs. README stars are not evidence.

---

## What this baseline is not

- Not a recursive npm/Godot addon SBOM (that is release / R9).
- Not permission to `npx -y latest` or Asset Library latest.
- Not a clone of candidates (R1-WP2).
