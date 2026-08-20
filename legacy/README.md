# Legacy Rust / `gs-*` engine archive

This directory is a **pointer only**. The frozen engine tree was not moved here.

## Recovery

- Annotated tag: `legacy-rust-engine-2026-08-20`
- Archive branch: `archive/legacy-rust-engine-2026-08-20`
- Full SHA (`legacy_base_commit`): `698e6088cc6d2c0a9a7b74021de409d46e5971aa`

Recover the engine in a **separate worktree** (checking out the tag on `main`
removes the now-tracked 20-8 plan from the worktree):

```
git worktree add ../hh-game-studio-legacy legacy-rust-engine-2026-08-20
```

or:

```
git worktree add ../hh-game-studio-legacy archive/legacy-rust-engine-2026-08-20
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

Reproducible hashes are **git blobs (LF)**. Windows worktree SHA-256 can differ
because of CRLF smudge; do not treat a worktree digest as the archive id.

| Path | git blob SHA-256 (LF) | notes |
| --- | --- | --- |
| tagged `docs/DECISIONS.md` (`698e608`) | `267bd5de41fdbe6c030a8af32e3cc8e357ac95b03310a11a850b8d782b24655e` | no GODOT-REBOOT heading |
| WP1 `docs/DECISIONS.md` (`7cf0a26` / `HEAD` blob) | `3d2699f6fe51221e190c513c3710b3dd1bd16953fff66fcaa6cd97dd64707d8c` | completed freeze pointers |
| `zdocs/20-8-godot-agent-autopilot-plan.txt` worktree | `3ac917ea4ce88228c8ed5bda3146714fdb9f07f46e8be855b2659f49708aa82b` | LF file; later committed on `50e06934`, not in the tag |

A freeze-time worktree SHA-256 `a3c5e706…` for DECISIONS was **not reproducible**
(mixed EOL vs patch vs later WP1 completion). Ignore it.

The freeze-time diff of `AGENTS.md` and pre-pointer `docs/DECISIONS.md` vs the
tagged commit is `legacy/reboot-worktree.patch` (in the R0-WP1 commit, not in
the tag). The 20-8 plan was untracked at freeze, so it is not inside that patch.
It entered git in `50e06934` (user commit of leftover reboot docs; **not** R0-WP2).

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
