# Legacy Rust / `gs-*` engine archive

This directory is a **pointer only**. The frozen engine tree was not moved here.

## Recovery

- Annotated tag: `legacy-rust-engine-2026-08-20`
- Archive branch: `archive/legacy-rust-engine-2026-08-20`
- Full SHA (`legacy_base_commit`): `698e6088cc6d2c0a9a7b74021de409d46e5971aa`

Restore that tree:

```
git checkout legacy-rust-engine-2026-08-20
```

or:

```
git checkout archive/legacy-rust-engine-2026-08-20
```

Do **not** continue WP-M6 / M7 / M8 of the Rust engine. Do **not** delete this tree.
New product code goes under `godot/` + `bridge/` after later R0 work packages.

## Freeze facts (R0-WP1, 2026-08-20)

HEAD at freeze was already the full Rust engine (354 tracked files). The tag
points at that existing commit. Reboot working-tree files were dirty at freeze
time and are **not** in the tagged tree.

`git status --porcelain=v1` at freeze:

```
 M AGENTS.md
 M docs/DECISIONS.md
?? zdocs/20-8-godot-agent-autopilot-plan.txt
```

SHA-256 at freeze:

- `AGENTS.md` = `1629005e47c9a409bfb256f15eda71d94064fc7ec19df155bb574dd1edd66d21`
- `docs/DECISIONS.md` = `a3c5e706cf06d277a381dea9c298e3f831aaf7822ef61eb32e531f039a8081a5`
- `zdocs/20-8-godot-agent-autopilot-plan.txt` = `3ac917ea4ce88228c8ed5bda3146714fdb9f07f46e8be855b2659f49708aa82b`

The freeze-time diff of `AGENTS.md` and `docs/DECISIONS.md` vs the tagged commit
is `legacy/reboot-worktree.patch` (this file is in the R0-WP1 commit, not in
the tag). The 20-8 plan was untracked, so it is not inside that patch.

## Inventory of the tagged tree (354 files)

Crates (`crates/`, 187 files):

- `gs-cli`
- `gs-editor`
- `gs-jobs`
- `gs-mcp`
- `gs-player`
- `gs-protocol`
- `gs-registry`
- `gs-render2d`
- `gs-runtime-core`
- `gs-scene`

Games (`games/`, 56 files): `arena-brawl`, `platformer`, `scrap-yard`, `snake`.

Other product paths:

- `templates/` (7 files) — `2d-platformer/`, shared `scripts/`
- `experiments/` (47 files) — `luau-spike`, `matrix-spike`, `mcp-spike`, `play-snapshot-spike`, `render-spike`, `wal-spike`
- `installer/` (5 files) — Inno Setup script + stage
- `workers/` (3 files) — `workers/imagegen/`
- `hh-play.bat` (present; also `hh-game-studio.bat`, `Cargo.toml`, `Cargo.lock`, `rust-toolchain.toml`)
- 16-8 plans (history/audit only):
  - `zdocs/16-8-game-studio-execution-plan-cho-ai-agent.txt`
  - `zdocs/16-8-game-studio-ai-native-ide-2d-first-master-plan.txt`

The tagged tree does **not** contain `zdocs/20-8-godot-agent-autopilot-plan.txt`,
`legacy/README.md`, or the TRANSITION stanza in `AGENTS.md`.
