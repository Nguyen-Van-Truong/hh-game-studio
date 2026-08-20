# M1 offscreen 10k sprite measurement (WP-M1-5)

Date: 2026-08-16  
Machine: Windows 10.0.26200  
GPU: NVIDIA GeForce GTX 1660 Ti (Vulkan, DiscreteGpu)  
Method: `gs_render2d::render_offscreen_png(640, 360, snapshot, atlas)` with
10 000 solid `RenderItem`s (100×100 lattice). Each call creates a wgpu
device, uploads the atlas, draws, readbacks, and encodes PNG. This is
**not** a player present-loop frame (MASTER 12.3 / I13).

Warmup is the first call (includes adapter/device init). Samples are the
next three calls. Median is the middle sample after sorting.

## debug (`cargo test -p m1 --test perf`)

| sample | ms |
|---|---|
| warmup | 368.15 |
| 1 | 363.66 |
| 2 | 369.64 |
| 3 | 355.00 |

Median: **363.66 ms**

## release (`cargo test -p m1 --release --test perf`)

| sample | ms |
|---|---|
| warmup | 287.72 |
| 1 | 282.19 |
| 2 | 322.11 |
| 3 | 279.38 |

Median: **282.19 ms**

## Versus MASTER 12.3

Player budget cited in spec: p95 ≤ 16.7 ms for 10k sprites + 200 bodies +
50 scripts. This WP measured only the offscreen PNG helper.

**Target not met** (release median 282.19 ms ≫ 16.7 ms). Not claimed as
60 fps. Causes that are in this measurement and not a player frame:
device construction every call, CPU readback, PNG encode. No sprite
culling exists in `gs-render2d` yet.

RAM / editor-open-5k / command round-trip: not measured in this WP.
