# Godot Agent security / license docs (R0-WP4)

`addons/hh_agent` **exists** under `godot/plugin-project/addons/hh_agent`.
Vendor MCP addons and GUT stay out of that project. The 2D museum sidecar
is `godot/plugin-project/r5w7/` (same `project.godot`). There is no second
`godot/test-projects/coverage-2d/` Godot project.

| File | What it is |
|------|------------|
| [CAPABILITY_MATRIX.md](CAPABILITY_MATRIX.md) | Measurable 2D workflows. Supported = named action + official E2E ACK, or stock Godot CLI. Not every P0 is Supported. |
| [COVERAGE_2D.md](COVERAGE_2D.md) | R5-WP7 TRACE REPORT: every P0/P1 2D row → action + official test **or** Alternative/Gap + owner. |
| [MCP_BAKEOFF.md](MCP_BAKEOFF.md) | R1-WP2 audit + R1-WP3 E2E scorecard on disposable copies ([tests/e2e/bakeoff/](../../tests/e2e/bakeoff/)). Shortlist A+C Lite. Do not enable in `plugin-project`. |
| [THREAT_MODEL.md](THREAT_MODEL.md) | Threats → controls (reject / jail / strip / Pause). A8–A10. |
| [SBOM_BASELINE.md](SBOM_BASELINE.md) | Godot 4.7.1-stable, GUT 9.7.1, Node/TS pins, MCP candidate pins (R1-WP2). |
| [../../PROJECT_BRIEF.template.md](../../PROJECT_BRIEF.template.md) | Brief schema (not the dogfood brief). |
| [HOST.md](HOST.md) | R2-WP7: Agent Host session contract. Interactive IDE is the host; unattended uses `host/`. Sidecar never holds model keys. |
| [INSTALL.md](INSTALL.md) | R9-WP2: current-user package/install/doctor/rollback. Unsigned internal. CLEAN_VM unproven. |
| [COMPATIBILITY.md](COMPATIBILITY.md) | R9-WP3: pin/probe/lock migrate/downgrade. Newer stable is non-blocking. Mismatch is Observe/Doctor only. |
| [../../.hh-agent/policy.example.toml](../../.hh-agent/policy.example.toml) | `OWNER_AUTOPILOT` + E1–E4 + jail + process allowlist. Deny includes `godot/plugin-project/addons/` and `res://addons/`. |

Live policy is a **copy** to `.hh-agent/policy.toml` (gitignored). Tokens stay in
`%LOCALAPPDATA%/HHGodotAgent/`, never in git.

Validate:

```text
python tools/godot/policy_validate.py --self-test
python tests/bootstrap/test_policy.py
python tests/bootstrap/test_no_secrets.py
python tests/bootstrap/test_capability_matrix.py
python tests/bootstrap/test_coverage_2d.py
python tests/bootstrap/test_mcp_bakeoff.py
python tests/bootstrap/test_bakeoff_guard.py
python tests/bootstrap/test_compat_update.py
```
