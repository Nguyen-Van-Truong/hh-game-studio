# Godot Agent security / license docs (R0-WP4)

Baseline **before** any third-party Godot MCP plugin is enabled in
`godot/plugin-project/` (that bake-off is R1; `addons/hh_agent` is R2).

| File | What it is |
|------|------------|
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threats → controls (reject / jail / strip / Pause). A8–A10. |
| [SBOM_BASELINE.md](SBOM_BASELINE.md) | Godot 4.7.1-stable, GUT 9.7.1, Node/TS pins, MCP candidates **to-audit**. |
| [../../PROJECT_BRIEF.template.md](../../PROJECT_BRIEF.template.md) | Brief schema (not the dogfood brief). |
| [../../.hh-agent/policy.example.toml](../../.hh-agent/policy.example.toml) | `OWNER_AUTOPILOT` + E1–E4 + jail + process allowlist. Deny includes `godot/plugin-project/addons/`. |

Live policy is a **copy** to `.hh-agent/policy.toml` (gitignored). Tokens stay in
`%LOCALAPPDATA%/HHGodotAgent/`, never in git.

Validate:

```text
python tools/godot/policy_validate.py --self-test
python tests/bootstrap/test_policy.py
python tests/bootstrap/test_no_secrets.py
```
