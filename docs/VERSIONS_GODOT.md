# Godot / sidecar toolchain pin (R0-WP3)

Frozen **2026-08-20**. Do not bump because a newer patch exists.

Machine-readable copy: [`tools/godot/pin.json`](../tools/godot/pin.json).
Install/verify: [`tools/godot/README.md`](../tools/godot/README.md).

## Godot Engine — 4.7.1-stable Standard

| Field | Value |
|---|---|
| Flavor | Standard (not Mono / .NET) |
| Tag | `4.7.1-stable` |
| `--version` (exact) | `4.7.1.stable.official.a13da4feb` |
| Commit (short) | `a13da4feb` |
| Commit (full) | `a13da4feb8d8aefc283c3763d33a2f170a18d541` |
| Official SHA-512 list | https://github.com/godotengine/godot-builds/releases/download/4.7.1-stable/SHA512-SUMS.txt |

Prefer GitHub `godotengine/godot-builds`. Do not vendor the engine tree.

### Downloads (Windows)

| File | Bytes | SHA-512 (official `SHA512-SUMS.txt`) | SHA-256 |
|---|---|---|---|
| `Godot_v4.7.1-stable_win64.exe.zip` | 84198557 | `a6b02c527c18ba9936e63562032701432b2dc57d98d6483ceaccb00fe14af16af5773ae8a55e7b4d614edf121c4d9e420d870f804edb1dac16362298a01ce6c4` | `c7a289051eaefb460b0106b60e9cd5bee0ef55fd102dcb2bed1eb356cf3d90a1` (computed locally 2026-08-20, matches research) |
| `Godot_v4.7.1-stable_export_templates.tpz` | 1280486955 | `afcc83d8d3d298038f19c58744a0d660fa75dd4baa33cb55d1011bb2565a2a8c2381728924564cb909e37c205a23f21b521b23bd057993afd43ae4da0b2f9d47` | `86409db6200b6f8fd3230989c2d2002851f3dd18acf11d7bdbafddf5a0dd0f72` (**locally hashed 2026-08-20**; matches GitHub digest) |

URLs:

- https://github.com/godotengine/godot-builds/releases/download/4.7.1-stable/Godot_v4.7.1-stable_win64.exe.zip
- https://github.com/godotengine/godot-builds/releases/download/4.7.1-stable/Godot_v4.7.1-stable_export_templates.tpz

### Cache path (not git)

`%LOCALAPPDATA%\HHGodotAgent\tooling\godot-4.7.1-stable\`

Optional in-repo cache (also gitignored): `.godot-cache/`.

Doctor extracts:

- `bin\Godot_v4.7.1-stable_win64.exe` (visible editor)
- `bin\Godot_v4.7.1-stable_win64_console.exe` (CLI / `--headless` / `--version`)

### License (do not vendor the engine)

MIT. Pointers on tag `4.7.1-stable` (same commit as the binary):

- https://raw.githubusercontent.com/godotengine/godot/4.7.1-stable/LICENSE.txt
- https://raw.githubusercontent.com/godotengine/godot/4.7.1-stable/COPYRIGHT.txt
- https://godotengine.org/license/
- Trademark: https://godot.foundation/policies-and-procedures/trademark-policy

## Plan §12 is stale — still freeze 4.7.1

`zdocs/20-8-godot-agent-autopilot-plan.txt` §12 said (plan date 20-8-2026): “4.7.1-stable là stable; **4.7.2 chỉ RC1**, 4.8 là dev.”

That sentence is **stale**. **4.7.2-stable already exists** as of **18-8-2026**, commit `ed1daf0bf`. This repo still freezes **4.7.1-stable** (`a13da4feb`). Upgrade is a later WP (plan: R9-WP3), not a drive-by bump (invariant A16).

## Refuse list

Doctor must exit non-zero if asked to accept any of:

- any **4.7.2\*** including **4.7.2-stable**
- any **4.8\*** (dev or stable)
- Mono / .NET builds (`*_mono_*`)
- TuxFamily 4.7.1 (404; not an official source for this pin)
- GitHub `/releases/latest`
- `npx -y latest`

## Node.js (Active LTS) + TypeScript sidecar

Fetched from https://nodejs.org/dist/index.json on **2026-08-20**.

| Field | Pin |
|---|---|
| Line | **24** Active LTS (codename **Krypton**) — not Current 26, not Maintenance 22 |
| Exact version | **24.19.0** (`.nvmrc` + `bridge/package.json` `engines.node`) |
| Verify machine | Node **v24.10.0** / npm 11.6.1 (same 24 Active LTS line; `npm ci` warns EBADENGINE, build still succeeds) |
| npm | lockfile `bridge/package-lock.json` (npm); no Yarn/pnpm |
| TypeScript | **5.9.3** exact (Apache-2.0) — not `typescript@latest` (7.x as of fetch) |
| `@types/node` | **24.13.3** exact (MIT) — 24.x types, not `@types/node@latest` (26.x) |

`npx -y latest` is refused. `npm ci && npm run build` in `bridge/` is the verify.

## Godot test runner pin (license check)

**Chosen: GUT 9.7.1** (Godot Unit Test).

| Field | Value |
|---|---|
| Project | https://github.com/bitwes/Gut |
| Version / tag | **9.7.1** / `v9.7.1` |
| Commit | `aeb5d4f3f7f0a6c9b5e178876d6c99b791fda605` (`godot_4_7` branch) |
| Godot compat | 4.7.x (explicit GUT matrix; not “latest”) |
| License | **MIT** — `addons/gut/LICENSE.md`; copy at [`third_party/gut/LICENSE.md`](../third_party/gut/LICENSE.md) |
| Archive (not latest) | https://github.com/bitwes/Gut/archive/refs/tags/v9.7.1.zip |

**Not vendored into `godot/plugin-project/` in R0-WP3** (no hh_agent yet; avoid dead addon tree). Copy from the pinned tag in a later test WP. Do not `git clone` default branch / Asset Library “latest”.

### Alternatives considered

| Runner | License | Why not |
|---|---|---|
| GdUnit4 (godot-gdunit-labs/gdUnit4) | MIT | No clean tagged pin for **4.7.1-stable** at freeze (4.7 support was master / 4.7.1-rc1). |
| Godot built-in | MIT (engine) | No first-party GDScript unit-test runner comparable to GUT/GdUnit4. Engine C++ tests are not a game/plugin runner. |

## Checksum commands (Windows)

```powershell
Get-FileHash -Algorithm SHA512 $zip
Get-FileHash -Algorithm SHA256 $zip
# or: python tools/godot/doctor.py --install
```
