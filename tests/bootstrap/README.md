# tests/bootstrap

Governance checks for the Godot cutover. Do **not** run `cargo test` for these.

```text
python tests/bootstrap/test_authoritative_plan.py
python tests/bootstrap/test_policy.py
python tests/bootstrap/test_no_secrets.py
python tests/bootstrap/test_capability_matrix.py
python tests/bootstrap/test_mcp_bakeoff.py
python tests/bootstrap/test_bakeoff_guard.py
python tests/bootstrap/test_stock_poc.py
```

Equivalent policy command:

```text
python tools/godot/policy_validate.py --self-test
python tools/godot/policy_validate.py .hh-agent/policy.example.toml
```

Exit 0 = pass.

- `test_authoritative_plan.py` — exactly one `AUTHORITATIVE_PLAN=1` (the 20-8 plan).
- `test_policy.py` — `.hh-agent/policy.example.toml` valid; `tests/bootstrap/policy/fail_*.toml` rejected (`..`, absolute path, arbitrary shell, placeholder token, addon jail).
- `test_no_secrets.py` — tree scan (skips `.git`, `target`, `node_modules`, `.godot`). Policy fail fixtures must not contain PAT-shaped blobs.
- `test_capability_matrix.py` — `docs/godot-agent/CAPABILITY_MATRIX.md` has ≥100 unique `CM-xxx` workflows, all R1-WP1 groups, R8 traces, and no fake Supported P0 rows.
- `test_mcp_bakeoff.py` — R1-WP2 scorecard + four MIT PIN.json SHAs; Beckett Full not bought; `godot/plugin-project` has no addon `plugin.cfg`.
- `test_bakeoff_guard.py` — R1-WP3: plugin-project still has no addons; `tests/e2e/bakeoff/SCORECARD.md` has A+C rows; eval/`call_method` PASS only as a disabled refusal.
- `test_stock_poc.py` — R1-WP4: plugin-project still has no addons/MCP/GUT; `godot/test-projects/stock-poc` has the disposable plugin; `hh-godot-editor.bat` still opens minimal-2d; recorded 20/20 RESULT.
