# SBOM baseline (R0-WP4)

Not a vendor SBOM and **not** a CycloneDX dump. MCP candidate SHAs are R1-WP2
pins (LICENSE + `PIN.json` only). Toolchain pins come from
[`docs/VERSIONS_GODOT.md`](../VERSIONS_GODOT.md) and `tools/godot/pin.json`.
Fetched **2026-08-20**. Do not bump Godot to 4.7.2.

Upgrade of Godot is its own WP (A16). G1 (`GODOT-G1-BASE-2026-08-20`) chose
**in-house thin**; there is no product-upstream MCP to bump. A later WP that
proposes vendor/depend must re-audit; a vendor MCP will not land from this baseline.

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

## MCP candidates — R1-WP2 pins (G1 closed as production vendors)

Scorecard: [MCP_BAKEOFF.md](MCP_BAKEOFF.md) + G1 section. Staging:
`third_party/mcp-staging/<id>/{LICENSE,PIN.json}` only — source was grepped then
discarded. **Not** copied into `plugin-project`. G1 base is **in-house thin**;
these SHAs are reference-only, not product dependencies.

| ID | Repository | Pin SHA (2026-08-20) | SPDX | Status |
|----|------------|----------------------|------|--------|
| A | [satelliteoflove/godot-mcp](https://github.com/satelliteoflove/godot-mcp) | `1b7d40537240fd54300f54bf6fda1ea91f06c878` | MIT | **G1 rejected vendor** (reference-only). Enable-as-is fail-hard remains **yes**. Spike shortlist does not authorize vendor. |
| B | [KeeVeeG/godot-mcp](https://github.com/KeeVeeG/godot-mcp) | `9ea1a41b9ed6cd819c602a37cc111c50017707d8` | MIT | **fail-hard** (eval + `OS.execute` git clone + no token); inventory only |
| C | [beckettlab/beckett-godot-mcp](https://github.com/beckettlab/beckett-godot-mcp) **Lite** | `efb81dec03ba0af2b7a6dce0e4678bdbde5e454d` (`v1.13.0`) | MIT (Lite tree) | **G1 rejected vendor** (reference-only). **Full itch = E2 fail-hard** (do not buy). Enable-as-is fail-hard remains **yes**. |
| D | [Sods2/godot-mcp](https://github.com/Sods2/godot-mcp) | `78b2cee00d697f117d6875e07675101b867efe70` | MIT | **fail-hard** (no token, TCP 6008, disk-first writes); inventory only |

Plan references: §2.3, §12 MCP baseline URLs. README stars are not evidence.
G1 lock: [`G1_BASE.md`](G1_BASE.md). NOTICE: we did not copy A/C/B/D source.

---

## What this baseline is not

- Not a recursive npm/Godot addon SBOM (that is release / R9).
- Not permission to `npx -y latest` or Asset Library latest.
- Not a vendor of MCP addon source (R1-WP2 keeps LICENSE + PIN.json only;
  R1-WP5 / G1 confirmed `mcp_vendor=none`, in-house thin).
