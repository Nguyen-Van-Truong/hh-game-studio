# GT-01 / S21 addendum review — 2026-09-13

## Decision

The external critique is directionally correct about sequencing, but it does
not justify replacing the current host or safety model. The plan keeps the
typed CLI/host as the core and treats third-party MCP implementations as
optional adapters. A bounded fixture spike will compare
`NPGameDev/godot-mcp-toolkit` and `hybridindie/godot-mcp` on protocol mapping,
safety defaults, reconnect behavior, latency, license notices, and maintenance.
README tool counts, stars, and self-reported CI numbers are hypotheses only.

The plan now makes GT-06 the first end-to-end vertical slice
(Blender edit → validated GLB → Godot import/readback → real Play/input →
observe/capture → seeded repair/replay). GT-09 remains the complete conformance
run. Android remains a physical-device target gate in GT-08 and is still
required before GT-10 and the HH World handoff. v0.1 uses hash/manifest and a
local test trust key; advanced signing is staged later. Open arbitrary-code
lanes remain disabled by default and require a separate ADR and isolation.

These decisions are recorded in the S21 addendum in the tools plan. No GT
checkbox or GT-01 acceptance status changed.

## Evidence in this review

- `test_tq01_portability.py`: portable lock/provenance checks, Unicode-and-space
  path archive verification, and fail-before-side-effect digest mismatch.
- `test_lifecycle_candidate.py`: two distinct synthetic packages, activation,
  CAS-protected rollback, stale transition rejection, and replacement-lock
  rejection. The generated report is explicitly `CANDIDATE`; live-owner,
  crash-recovery, and manual-edit reconciliation probes remain unexecuted.
- Bootstrap suite: 48 tests passed.
- Static S21 plan validator: 41 mutation tests passed (`PASS_STATIC_ONLY`).

The candidate uses synthetic packages and does not prove official engine
execution, hostile-process safety, or GT-01 acceptance. A final source freeze,
official runtime remint, complete closure manifest, and two independent critics
on one frozen hash are still required.

## Source references

- https://github.com/NPGameDev/godot-mcp-toolkit
- https://github.com/hybridindie/godot-mcp
- https://docs.godotengine.org/en/4.7/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html
- https://docs.blender.org/api/main/info_gotchas_threading.html
- https://www.blender.org/lab/mcp-server/
