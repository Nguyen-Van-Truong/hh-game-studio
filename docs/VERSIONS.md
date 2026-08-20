# Version matrix (WP-M-1-f / G1)

Pinned set that **compiled and tested together** on 2026-08-16
(Windows, rustc 1.93.1, `experiments/matrix-spike` + render/luau spikes).

Do **not** bump one crate to “latest” independently. Re-run
`cargo test --manifest-path experiments/matrix-spike/Cargo.toml` after any bump.

| Crate | Pin in Cargo.toml | Locked / proven | Notes |
|---|---|---|---|
| rustc | stable (1.93.1 this machine) | 1.93.1 | Propose `rust-toolchain.toml` = stable |
| egui | =0.31.1 | 0.31.1 | render-spike |
| eframe | =0.31.1 (`default_fonts`+`wgpu`, no glow) | 0.31.1 | WGPU backend |
| egui-wgpu | =0.31.1 | 0.31.1 | CallbackTrait viewport |
| wgpu | 24.0.3 (`wgsl`,`dx12`,`metal`,`vulkan-portability`) | 24.0.5 | Do not jump to wgpu 25+ without new egui line |
| winit | 0.30.9 | 0.30.13 | player window |
| glyphon | 0.8 | 0.8.0 | compile-only in matrix-spike (no text demo yet) |
| mlua | 0.11.6 `features=["luau"]` | 0.11.6 | auto-vendors Luau |
| luau (vendored) | via luau0-src | **0.709** (`0.18.3+luau709`) | Need VS `vcvars64` on Windows |
| bevy_ecs | 0.15 | 0.15.4 | standalone ECS — not full Bevy |
| rapier2d | 0.22 `enhanced-determinism` | 0.22.0 | insert order still required at runtime |
| rmcp (MCP) | =3.1.2 | 3.1.2 | experiments/mcp-spike; git `02c62aef` |
| kira | 0.10.8 (`cpal`,`ogg`,`wav`; no default extras) | 0.10.8 | gs-player; mock backend when no device (GS-EC-33) |
| gilrs | 0.11.2 | 0.11.2 | gs-player window path only |

## How to re-verify

```
cargo test --manifest-path experiments/render-spike/Cargo.toml
cargo test --manifest-path experiments/luau-spike/Cargo.toml
cargo test --manifest-path experiments/matrix-spike/Cargo.toml
```

## rust-toolchain.toml (proposed for M0)

```toml
[toolchain]
channel = "stable"
```

Record the exact rustc in CI logs. Do not pin 1.93.1 forever unless a later
stable breaks the set — then pin and write DECISIONS.md.
