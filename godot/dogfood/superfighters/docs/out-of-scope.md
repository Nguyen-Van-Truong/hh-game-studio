# Vault Fighters — OUT_OF_SCOPE classification (VF0-WP1)

Frozen with HEAD `094822467edfe97d20f99890366a0103dc93b9b1`.
These paths must **not** be staged into a Vault Fighters product
commit. They are listed so every agent sees the same boundary.

## Snake (explicit VF0-WP1 requirement)

Untracked Snake dogfood and drive scripts. Out of product scope.
Not VF evidence. Not a VF work package.

| Path | Classification |
|---|---|
| `godot/plugin-project/snake/` | `OUT_OF_SCOPE` |
| `godot/plugin-project/snake/snake.tscn` | `OUT_OF_SCOPE` |
| `godot/plugin-project/snake/snake_game.gd` | `OUT_OF_SCOPE` |
| `tools/godot/drive_snake.py` | `OUT_OF_SCOPE` |
| `tools/godot/drive_snake_polish.py` | `OUT_OF_SCOPE` |
| `tools/godot/drive_snake_reload.py` | `OUT_OF_SCOPE` |
| `tools/godot/drive_snake_show.py` | `OUT_OF_SCOPE` |

## Other products / platform closeout (do not mix into VF0-WP1)

| Path / topic | Classification |
|---|---|
| `godot/dogfood/kho-bi-an/` | `OUT_OF_SCOPE` (other dogfood; do not modify) |
| `.hh-agent/evidence/*KBA*` and Kho Bí Ẩn dumps | `OUT_OF_SCOPE` (not VF evidence) |
| Parent plan `zdocs/20-8-godot-agent-autopilot-plan.txt` checkboxes | `OUT_OF_SCOPE` to tick (R9-WP4, G6, GX, 60/60 stay frozen) |
| Rust `gs-*` / Hoan Hao social | `OUT_OF_SCOPE` |
| `testnewcodex/` | `OUT_OF_SCOPE` |
| `artifacts/` | `OUT_OF_SCOPE` unless a later VF WP owns a named artifact |

## Local / generated (never ship)

| Path | Classification |
|---|---|
| `**/.godot/` | generated editor cache |
| `godot/dogfood/superfighters/.evidence/` | local run output (plan §18.3); hash in `docs/baseline-manifest.json` |
| tokens, `.env`, session secrets | never in evidence or commits |

## Working-tree overlay (not this WP’s files)

Leave in place; do **not** reset. Do **not** fold into the VF0-WP1
commit unless a later owner WP says so.

| Path | Notes |
|---|---|
| `godot/dogfood/superfighters/src/game_session.gd` | Dirty vs HEAD. Unpublished VF0-WP2 test-mode audio mute. |
| `godot/dogfood/superfighters/src/sfx_bank.gd` | Dirty vs HEAD. Unpublished VF0-WP2 mute/teardown helper. |
| `AGENTS.md`, `docs/DECISIONS.md`, `tests/bootstrap/test_vault_fighters_plan.py` | Audit/VF0-WP3 routing. |
| `zdocs/29-8-vault-fighters-y8-parity-plan.txt` | Product plan (untracked at freeze). Implementer must not tick. |
| `tools/godot/gen_vault_fighters_art.py` | Product art generator, untracked; not Snake. |

`tools/godot/ops.py`, `ops.ps1`, `studio_bundle.py`, godot-agent docs,
and similar platform files are **not** VF0-WP1 scope.
