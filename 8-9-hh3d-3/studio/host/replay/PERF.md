# Runtime performance artifact v1

`perf.py` owns local artifact validation. It never changes accepted shared
protocol caps, starts an engine, reads referenced evidence or authenticates a
caller-provided process/measurement. The runner owns native identity, snapshot,
capture, source closure, process-exit and leftover verification.

```python
from studio.host.replay.perf import (
    build_artifact, validate_artifact, parse_artifact, summarize, PerfError,
)

artifact = build_artifact(payload)  # raw payload, no claimed summary
checked = validate_artifact(artifact, expected={
    "provenance": {"source_closure_sha256": frozen_source_sha256},
    "process": {"pid": native_pid, "process_start": native_start_identity},
})
checked = parse_artifact(raw_utf8_bytes, expected=trusted_bindings)
statistics = summarize([10.0, 20.0, 30.0])
```

`studio/tests/replay/test_perf.py::sample_payload` contains a complete synthetic
example of every mandatory group. Its observations and hashes are test values,
never native evidence. The factory returns a detached copy and adds
`schema_id=hh-studio.perf-collector`, `schema_version=1.0.0`,
`artifact_kind=runtime_frame_capture` and a freshly calculated summary.
Supplying a summary to the factory is rejected. `PerfError` exposes stable
`code` and `path`; errors do not include payload values.

The schema's raw SHA-256 fields use 64 lowercase hex characters. A source-map
closure digest, a snapshot digest and a file-byte hash have different domains;
the runner must bind each to the correct frozen source. `references` are bounded
metadata only, not authority to open or trust a path. Validation without trusted
`expected` bindings proves internal consistency, not observation authenticity.

## Raw timing and counters

Each frame records consecutive `seq`, engine process/draw frame numbers,
`runtime_mono_us`, positive `frame_ms`, `sim_tick`, `ui_tick`, phase and readback
`state_hash`. `frame_ms` must equal the integer monotonic-microsecond difference
divided by 1000. The first difference begins at `clock.runtime_start_mono_us`;
the last sample equals `clock.runtime_end_mono_us`. No frame is trimmed during
summary calculation. Warm-up occurs before that measurement window and is
declared in the frozen sampling profile.

`frame_post_draw` captures consecutive drawn frame boundaries, not GPU-present
latency. `process_frame` can be used with an explicitly unavailable headless
window; its draw counter need only be nondecreasing. UI ticks must advance;
simulation ticks must not decrease or advance between adjacent PAUSED frames.
Real input, frozen bodies and transition correctness require separate native
readbacks. Native evidence cannot be inferred from these scalar checks.

Godot-counter rows align one-to-one with frames and repeat the exact frame
sequence and timestamp. Every metric has explicit availability, provider, unit,
scope and freshness. Unavailable counters are null with a reason; zero is an
observed value. `scene_triangles` means loaded, instanced, active-LOD topology
read back from mesh surfaces. It does not claim frustum-visible triangles.
For the global Performance variant, `render_primitives` preserves Godot's
vertices/indices and multi-pass semantics. Texture memory can be a cached native
monitor. Closed viewport variants match the fixture's actual APIs:

| Counter | Provider | Scope | Unit |
| --- | --- | --- | --- |
| scene_triangles | Mesh.get_faces | visible_in_tree_mesh_topology_excludes_ui_and_gpu_culling | triangles |
| draw_calls | RenderingServer.viewport_get_render_info | bound_viewport_visible_plus_shadow | calls |
| render_primitives | RenderingServer.viewport_get_render_info | bound_viewport_visible | points_lines_or_triangles |

The viewport variants use `native_monitor` freshness; Mesh.get_faces uses
`readback_topology`. The rendering-info metric is DRAW_CALLS_IN_FRAME for
draw_calls, PRIMITIVES_IN_FRAME for render_primitives. VISIBLE+SHADOW excludes
CANVAS; VISIBLE alone excludes shadows and CANVAS. Global and viewport fields
cannot be mixed. Neither native primitive counter is converted into triangles.
The runner must establish viewport readiness: Godot returns zero when fewer
than two frames have rendered and information is unavailable. See
[RenderingServer](https://docs.godotengine.org/en/4.7/classes/class_renderingserver.html).

RSS rows use their own host-monotonic timestamps and consecutive sample IDs.
They measure the bound runtime process (Windows working set or Linux resident
pages), not Godot static allocations or the host's memory. An unavailable RSS
provider requires an empty RSS array and a reason. Never fabricate per-frame
RSS by repeating an older host observation. Clock-domain timestamps cannot be
subtracted across processes without a separately verified synchronization.
UTC epoch milliseconds only anchor evidence; elapsed timing uses monotonic us.
Optional Android battery percentages carry host sampling times and charging
states; absence does not mean zero.

Godot 4.7.2 `TIME_PROCESS` stores the process maximum in an approximately
one-second window, with frame delay afterward. It is not the raw frame series.
Process delta can also be scaled/capped/smoothed/fixed. References:
[pinned main.cpp](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/main/main.cpp),
[Performance](https://docs.godotengine.org/en/4.7/classes/class_performance.html),
[Node timing](https://docs.godotengine.org/en/4.6/classes/class_node.html),
[monotonic Time](https://docs.godotengine.org/en/4.6/classes/class_time.html).

## Arithmetic, compatibility and limits

Quantiles use linear type 7: sorted samples x, h=(n-1)p, j=floor(h), interpolate
x[j] and x[min(j+1,n-1)]. For 1% low, k=ceil(n/100), take the k largest frame
times and calculate 1000/mean(k). No intermediate rounding. Summary and raw
microsecond-derived values are independently recomputed; numeric comparison
uses relative tolerance 1e-12 and absolute tolerance 1e-9 in the named unit.
Empty/nonpositive/nonfinite frames, bool-as-number, unsafe integers, duplicate
keys, invalid Unicode, unknown fields and unknown versions are rejected.

Artifact limits are 64 MiB, 120000 frames/counter rows, 12000 RSS samples and
600 seconds, with lower frozen-profile limits enforced too. Up to 32 relative
file references are allowed. Shared command arrays remain capped at 256 items;
commands carry artifact identity/hash/size, never these full arrays. Hitting a
cap must produce a separate gap/diagnostic, not truncate a `complete=true`
artifact. This schema accepts only complete, zero-drop captures. Structural
JSON Schema validation must be followed by `validate_artifact` for relational
and derived-value checks. New formats require explicit compatibility/version
tests; v1 artifacts are never silently migrated or reinterpreted.

## Benchmark boundary

Collector tests do not establish the tools-plan UX benchmark. The fixed
1000-command mix, 100 create/undo/save/reload cycles, 10 process runs and
warm-up/measured samples must be preserved. The conservative proposed profile
is 10 x (5 warm-up + 30 measured), frozen before a run. Existing 16-effect-slot
hosts require a new scoped bounded lifecycle per cycle; do not raise shared
caps or substitute mock cycles to claim acceptance. RSS-growth, latency and
HH World performance claims remain unproven until their native workload runs.
