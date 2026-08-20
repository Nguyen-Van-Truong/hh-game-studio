# tests/bootstrap

Governance checks for the Godot cutover. Do **not** run `cargo test` for these.

    python tests/bootstrap/test_authoritative_plan.py

Exit 0 = pass. Non-zero = `AUTHORITATIVE_PLAN` markers are missing or duplicated.
