# GT06 fixed native observation lane

The supervisor composes a **new** snapshot from `fixtures/play-observe/` at its
root, this directory's three `.gd` files at `res://observe/`, and the unchanged
GT05 `authored.gd` / `authored_material.tres` at `res://gt05/`. No editor code is
activated in Play and no runtime source is replaced during a run.

Required fixed inputs are `input/fixture.glb`, its admitted `input/manifest.json`
and `input/producer-report.json`, `input/trace.json`, `input/run.json`, and the
host-validated GT03 declarative `config/fixture_actor.gd`. The config must
declare `move_speed`; no scene override can mask its default. `move_speed=0`
is an observable seeded movement fault; `3.0` is the normal demonstration.
An independent host must establish an actual managed repair; copying these
two configurations alone does not prove the editor repair path.

The host completes import with the pinned GUI executable:

```text
Godot_v4.7.2-stable_win64.exe --headless --editor --path SNAPSHOT --import
Godot_v4.7.2-stable_win64.exe --path SNAPSHOT
```

Use separate bounded owned launches and isolated user directories. The output
directory `out/` must exist and be empty; no caller selects an output path.
Runtime captures require a real headed window. `captures=[]` permits a
headless diagnostic, whose frame rows explicitly do not claim rendered proof.

`input/run.json` has exactly `run_id`, `command_id`, `runtime_instance_id`,
`source_closure_sha256`, `runtime_snapshot_sha256`, `trace_sha256`, `glb_sha256`,
and `generation`. The host supplies and checks these bindings; native code
checks actual input bytes and repeats their hashes before finalizing evidence.
The runtime snapshot hash excludes the self-referential run JSON. Engine PID,
creation time and HWND ownership need independent host verification.

Input schema is `hh-studio.input-trace` / `1.0.0`: 60 Hz, uint32 seed, 1–600
consecutive frame rows, each with `tick`, `pressed`, `held`, `released`, and
0–16 capture requests `{tick,label}`. Edge events alone are emitted with
`Input.parse_input_event`; an explicit `Input.flush_buffered_events()` dispatches
that tick before the controller and held-state readback. At each physics
step the bridge runs at priority -100, fixture at 0 and observer at +100.
UI, bridge and observation continue while the world is paused. Native report
records contain the actual UI/input callback ledger, not synthesized actions.
The trace remains inactive in MENU until at least two frame-post-draw callbacks
and a rendered-frame counter of at least two. `trace_start` binds that actual
readiness boundary, so setup catch-up cannot consume the menu screenshot before
the first image is ready. Callback retention is capped at 8192 rows.
Quit enters `QUITTING`; remaining trace releases and pending captures drain
before the engine exits naturally.

`out/report.json` uses `hh-studio.play-observation` / `1.0.0`; its shape is the
literal construction in `trace_bridge.gd::_complete`. `observations` contain
the after-physics state and its exact `state_json` plus `snapshot_sha256`.
`native_frames` are sampled at frame-post-draw and carry clock, trace, UI,
simulation, state and native counter bindings. Captures use the same rendered
state and require both process/render counters to advance beyond the request's
fence, with unchanged requested phase and camera. Multiple labels at the same
requested tick may share one actual frame.
`state_json` is hashed as its raw UTF-8 bytes (`native-json-utf8`), without JCS
re-encoding. Host verification must also compare its parsed value to the
adjacent observation, phase/tick/camera and other fields where present.
`requested_camera_json` likewise preserves the exact native camera string for
its adjacent hash; parse it to bind both the request observation and actual
capture camera without guessing Godot's numeric formatting.

All startup frame rows are retained. Before render readiness, `counters` has
null values and `counter_readiness.qualified=false`; `raw_counter_readback`
retains the actual unqualified native readings for diagnosis. The first
qualified frame is the measurement anchor, with `measurement_eligible=false`.
`perf_measurement_start_monotonic_us` and `perf_measurement_start_frame_index`
declare the subsequent measured suffix; every row there is qualified and
eligible, with its first delta starting at the preceding anchor. Original
frame start/end anchors still cover every retained row. Headless diagnostics
are never eligible render-performance evidence.

The final `HH_GT06_COMPLETE` marker contains exactly `run_id`, `command_id`,
`runtime_instance_id`, `pid`, and the byte hash `report_sha256`. A report or
exit-zero alone is not acceptance. The host must bind the exact marker to
captured stdout, the actual engine exit, clean owned trees, immutable inputs,
fresh image bytes, callbacks and independent expected postconditions. Native
`completed=true` means evidence delivery completed, including a reproducible
seeded fault; it does not mean gameplay or repair passed.

`trace_bridge.inspect_target(stable_id, runtime_instance_id, generation)` is
read-only and supports only `fixture` and `review.camera`. It rejects stale
context; it offers no general node-call or property-write mechanism. Runtime
and editor ObjectIDs are not exchanged. Stop/cancel ownership and durable
receipts belong to the host lane; this fixed trace program is not a public
network listener or a claim of the later GT07 activation feature.

The first native diagnostic exposed the input queue boundary and a PrimitiveMesh
API mismatch. The implementation follows the pinned
[Input queue/flush implementation](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/core/input/input.cpp#L1410)
and the common
[Mesh.get_faces binding](https://github.com/godotengine/godot/blob/ed1daf0bf001b61586d9930840f2f1394092c079/scene/resources/mesh.cpp#L754).
Bounded `out/failure.json` records the failing trace tick and actual input state;
it has no completion marker and cannot substitute for a successful report.
