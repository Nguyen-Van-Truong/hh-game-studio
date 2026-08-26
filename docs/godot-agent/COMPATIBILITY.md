# Compatibility / update playbook (R9-WP3)

Pin stays **4.7.1-stable** / `4.7.1.stable.official.a13da4feb`.
This is the upgrade matrix, not a bump. A16: Godot / upstream MCP upgrades
are a dedicated WP. Do not apply a newer stable because it exists.

Machine-readable copy: [`tools/godot/compatibility_matrix.json`](../../tools/godot/compatibility_matrix.json).
Tool: [`tools/godot/compat.py`](../../tools/godot/compat.py).
Lock: [`.hh-agent/capability-lock.json`](../../.hh-agent/capability-lock.json).

--provider plan stays. Do not invent an API key. CLEAN_VM stays unproven.
Real clean VM is G6. `not_g6=1`. Do not tick GX.

## What is supported

| Channel | Status |
|---|---|
| Godot `4.7.1-stable` standard (`a13da4feb`) | **Supported** — only production pin |
| Node `24.19.0` / TypeScript `5.9.3` | **Supported** — sidecar pin |
| Protocol `hh-godot-agent/1` + registry `hh-godot-actions/1` | **Supported** |
| In-house `hh_agent` + `bridge/` | **Supported** — `mcp_vendor=none` |
| Probe of a newer official stable | **Non-blocking** — record only, never apply |
| Patch / minor Godot or sidecar bump | **Blocked** until suites + human/WP approval |
| Vendor MCP A/B/C/D | **never-enable** — review PIN.json, do not vendor |
| Version / lock / protocol / schema mismatch | **Observe/Doctor only** (S7) |

## Probe latest (non-blocking)

```powershell
python tools/godot/compat.py probe --fixture tools/godot/probe_latest.fixture.json
```

The probe may report a newer tag. `approved=false`, `applied=false`,
`blocking=false`. `--apply` is refused. Doctor keeps launching the pin
binary. Do not change `tools/godot/pin.json` from a probe.

## Suites before any patch / minor apply

`compat.py apply` refuses unless every required suite is recorded `ok: true`.
Required (matrix):

1. contract — `python tests/bootstrap/test_registry.py`
2. e2e — `python tests/bootstrap/test_scene_lifecycle.py`
3. visible — `python tests/bootstrap/test_visible_e2e.py`
4. headless — `godot --headless --path <migration-copy> --quit`
5. export — `python tests/bootstrap/test_export_clean_build.py`

One Godot `--path` at a time. Kill leftover Godot first. This playbook
does **not** auto-run the full export/visible suites; it gates apply
until their evidence exists. Mid-session apply is always refused.

The broken-API fixture is a **minimal editor project** (addon only).
Do not `copytree` `godot/plugin-project` and do not copy a piled
`.hh-agent`. `--import` that editor project, then start one sidecar
and one `--path`.

## Capability-lock migration / downgrade

Always copy the project first. Do not rewrite the live repo lock.

```powershell
python tools/godot/compat.py candidate --new-lock $env:LOCALAPPDATA\HHGodotAgent\compat\new-lock.json
python tools/godot/compat.py migrate --project <src> --dest <copy> --new-lock <new-lock.json>
python tools/godot/compat.py downgrade --project <copy> --old-lock <old-lock.json>
```

Candidate locks keep the **same Godot pin**. A newer engine is a later
approved WP, not a lock_revision bump.

## Upstream MCP sync

```powershell
python tools/godot/compat.py mcp-sync
```

Reviews staging `PIN.json` SHAs, MIT LICENSE, `never-enable`, and schema
ownership `bridge/src/registry/`. `patch_queue` is `do-not-patch-vendor`,
so reapply is a no-op. Do not copy `third_party/mcp-staging/*` into
`godot/plugin-project/` or `bridge/src/`.

## Version mismatch → Observe / Doctor only

If a project plants a foreign protocol, schema, or capability-lock — or
the running Godot string is not the pin — mutations (`mutate` /
`destructive` / `external`) return `E_VERSION_SKEW`. `project.inspect`,
`project.doctor`, observer reads, and Pause still run. Doctor prints
`Observe/Doctor only`.

## Official verify

```text
python tests/bootstrap/test_compat_update.py
```

Labels: OLD_LOCK, NEW_LOCK, DOWNGRADE, MIGRATE, BROKEN_API, CLEAN_VM.
`CLEAN_VM` stays unproven. Plan stays R9-WP3 `[ ]` / 58/60 / G6 `[ ]`.
