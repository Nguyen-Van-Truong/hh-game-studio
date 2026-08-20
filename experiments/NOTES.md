# M-1 spike rollup (for GATE G1)

Date: 2026-08-16. Parent reviewed each crate with `cargo test` (not agent report alone).

| WP | Crate | Result |
|---|---|---|
| M-1-a | render-spike | GO — 1 IR, 3 targets; offscreen PNG real |
| M-1-b | luau-spike | GO — deadline pierces pcall; buffer discard |
| M-1-c | wal-spike | GO — 4 crash cases + I6 middle-corrupt |
| M-1-d | play-snapshot-spike | GO — tamper reject |
| M-1-e | mcp-spike | GO compile/stdio; Inspector/Cursor not run |
| M-1-f | matrix-spike + docs/VERSIONS.md | GO — set compiles together |

Details live in each crate’s NOTES.md. Do not delete `experiments/` until G1 ticks
and lessons are copied into `docs/DECISIONS.md`.
