# GT04 trusted Blender fixture adapters

AUTHORITY=0. These private background/UI adapters are implementation work for GT04,
not a public protocol endpoint or accepted GT04 deliverable. It never emits a
public ACK. It is intended only for the runner's newly created original fixture;
it is not an admission mechanism for artist files or hostile `.blend` files.

`FixtureAdapter.execute(bytes)` accepts `HH-BLENDER-FIXTURE-COMMAND-1` with exact
fields `schema`, `command_id`, `operation`, `expected_revision`,
`expected_context`, and `payload`. Commands are capped at 4096 bytes. IDs are
ASCII `[a-z][a-z0-9_-]{0,47}`. Unknown fields, duplicate JSON keys, nonfinite
numbers, booleans as numbers, unsupported modes and arbitrary paths/scripts are
rejected. Supported operations are:

| Operation | Payload | Preconditions |
| --- | --- | --- |
| `scene.inspect` | `{}` | Both expected fields are null |
| `mesh.create_box` | `object_id`, `size: [x,y,z]` | Scene revision and exact context |
| `object.transform.set` | `object_id`, `location`, `rotation`, `scale` | Scene revision and exact context |

Size and positive scale are .001–1000; location is ±10000; XYZ Euler rotation is
±2π radians. Stable IDs reside in `hh_gt04_id`, are resolved again on the main
thread, and must be unique. At most 16 objects and 64 successful mutation IDs
are admitted. The scene revision hashes native mesh vertices/faces, names,
stable IDs, location/rotation/scale and units. It is a semantic revision of this
declared narrow profile, not a complete `.blend` dependency digest. Native
float vectors are compared with explicitly rounded IEEE binary32 values.

Object and Edit Mesh modes are supported. Mode/active ID/sorted selected IDs
must equal the command's expected context. Mode changes use a polled operator
with explicit context override; mesh construction and transforms use the data
API. The adapter leaves Edit Mode to flush its mesh representation, reacquires
RNA data, then restores object selection, active object and mode. It does not
preserve or promise arbitrary edit-mesh element selection/history. Unexpected
exceptions after beginning native mutation permanently hold that adapter;
there is no automatic retry, rollback, or partially successful ACK.

Same command ID and exact command digest return the detached original internal
receipt. A changed payload with that ID is an ordinary no-effect conflict.
Dedupe is process-local; it does not survive save/reopen. Stop rejects new
mutations and retains prior receipt lookup. There is no queue, network listener,
lease/fencing service, UndoRedo stack, UI extension, export, material operation,
asynchronous cancellation or persistent receipt journal yet. A stopped adapter
can still inspect. Deadline and crash boundaries belong to the bounded host
probe; no operation-level deadline claim is made.

That paragraph describes `FixtureAdapter`; the separate UI owner below provides
its own timer, native history and fixed save slots. The background adapter and
its native checks remain unchanged.

## Main-thread UI API

`ui_adapter.UIAdapter(owned_root=Path(...))` requires an exclusively owned fresh
Blender 5.2.1 GUI session, one window with a VIEW_3D area, enabled global undo
and at least 32 undo steps. `owned_root` is trusted host configuration, must be
an existing empty directory without reparse ancestors, and can be omitted to
disable saves. It is not a remote path parameter or a protected GT02 owner.
Do not construct this adapter in an artist's existing session.

On the main thread call `owner.queue.submit(raw_bytes, ttl_ms=1000)` and poll
`owner.queue.result(command_id)`. The exact command fields above apply with
schema `HH-BLENDER-UI-COMMAND-1`. In addition to inspect/create/transform, the UI
accepts `history.undo` / `history.redo` with `{}` and `checkpoint.save` with
`{"slot":"checkpoint"}` or `{"slot":"fixture"}`. All three require exact
expected revision/context. No operator name, Python source, arbitrary filename
or undo-stack index is accepted. Save slots resolve only to `checkpoint.blend`
and `fixture.blend`, reject an existing final/staged name, use a native staged
copy save, and publish with an exclusive hard link inside the owned root.

The queue admits at most 8 pending and 64 total request IDs, with commands of
at most 4096 bytes. One request is dispatched per 10 ms timer callback. TTL is
1–5000 ms measured by the host monotonic clock at enqueue; an expired request
has no native effect. An exact duplicate retains its original deadline and
detached receipt, including duplicate undo or save. Receipts are historical
observations, not claims that their old revision is still current. Changed
bytes under an existing ID are rejected. `stop()` cancels all pending work;
already completed receipt lookup remains available. A synchronous native call
cannot be interrupted by this timer. The external probe watchdog bounds the
whole owned process, not individual operator execution or disk/RAM usage.

The registered private `hh_gt04.apply_fixture('EXEC_DEFAULT', True)` operator
uses `REGISTER` and `UNDO`; successful data edits receive Blender's actual
undo step. History uses `bpy.ops.ed.undo()` / `redo()`, followed by exact native
snapshot and context comparison; it never reconstructs meshes from a receipt.
Stable IDs are resolved again after undo invalidates RNA. Object and Edit Mesh
create/transform are supported. Edit Mesh inspection reads BMesh without mode
switching. Transform/create push global object undo while in Object Mode,
then restore Edit Mode, active ID and selected object IDs. Individual mesh
element selections/history are not part of this contract.

An intervening manual context or scene change starts a new owned history
segment on the next admitted mutation. At most 16 mutation states are retained
per segment; native undo cannot cross its owned boundary. A new edit after undo
discards that redo branch. Unexpected post-effect failure holds the owner;
there is no automatic rollback claim. A strict private-session assumption is
still needed: hash equality alone does not prove no unrelated UI undo operator
ran. Loading files into a live owner is unsupported; close it first.

`close()` stops the queue, unregisters its nonpersistent timer and operator.
No Python thread, socket or listener is started in Blender. A future external
IPC host must provide authenticated, leased input to a nonblocking main-thread
poller; the current API has no authentication, journal, durable dedupe or public
ACK. Save receipt `durable_publication=false` is explicit. Fresh-process reopen
proves the recorded fixture bytes/readback only, not crash durability or atomic
cross-application publication.

Run the combined GUI/background capture with a new suffix:

```powershell
python 8-9-hh3d-3/studio/tests/blender/run_blender_ui_probe.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt04-ui-05
```

It freezes this complete Blender source scope, runs the 38 Python tests, then
three actual non-background GUI processes and the three original background
processes, sequentially (60 seconds each). GUI work runs after entering the
window event loop through real timers. The GUI checks cover native create and
transform undo/redo in both modes, two-step Edit history, branch invalidation,
duplicate create/undo/save, real queue expiry, Stop, fixed-slot save, fresh
final-file reopen and checkpoint reopen. Every phase retains host exit/PID,
wrapper exit and Job tree observations; these do not constitute GT04 acceptance.

Official API basis for this UI lane (checked 2026-09-17):

- [Operator undo](https://docs.blender.org/api/5.2/bpy.types.Operator.html)
  and [operator calling convention](https://docs.blender.org/api/5.3/bpy.ops.html):
  explicit Python undo argument and `UNDO` option are both used and tested on
  the pinned executable. Mode-switching cases need special undo handling.
- [Application timers](https://docs.blender.org/api/5.2/bpy.app.timers.html):
  one bounded callback returns its next interval; `None` removes it. Timers
  are nonpersistent across file load.
- [Context overrides](https://docs.blender.org/api/5.2/bpy.types.Context.html):
  window/area/region are resolved from the owned window and overridden only
  for each operation. No stale object RNA is retained across undo.
- [Native history operators](https://docs.blender.org/api/main/bpy.ops.ed.html):
  baseline push, undo and redo are native Blender operations; actual result
  and scene readback are required in addition to operator completion.

The trusted fixture excludes linked libraries, text blocks, materials, images,
worlds, node groups, animation, shape keys, modifiers, parents and constraints.
The adapter checks its supported representation but is **not** a complete
security validator for the many possible Blender datablocks. Unknown files
must not be opened to discover whether these checks pass.

Run from the repository root with Python 3.11:

```powershell
python 8-9-hh3d-3/studio/tests/blender/run_blender_probe.py --output 8-9-hh3d-3/zdoc/reviews/20260917-gt04-blender-01
```

Use a new output suffix for every attempt. The runner freezes all addon/test
files plus the unchanged accepted `build/bootstrap/run_fixture.py` and
toolchain lock. It checks Blender 5.2.1 executable SHA256
`8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`
before and after, runs Python tests (30 seconds), then independent edit,
final-file reopen, and checkpoint reopen processes (60 seconds each) using the
existing gated Windows Job runner. Raw logs, actual exit/PID/Job-tree results,
ordered native markers, source hashes, and output hashes are retained. Source
and frozen snapshot must remain unchanged. These captures prove historical
native observations, not independently trustworthy caller JSON.

Only fixed `checkpoint.blend` and `fixture.blend` files are saved, exclusively,
under the fresh owned fixture directory. A staged save is linked to a new name;
existing outputs are rejected. Both are reopened in new processes, with exact
input bytes checked first. No original/user file is overwritten. This is not a
GT02 protected filesystem owner, durable publication transaction, power-loss
proof, or race-resistant boundary against another writer. Retain exclusive
ownership of the review directory. The existing bootstrap's native handle
close return is not checked; no stronger close proof is inferred from its
`tree_verified` observation.

`--factory-startup --disable-autoexec --offline-mode` and isolated
`BLENDER_USER_RESOURCES` reduce accidental preference/script reuse. They do not
sandbox the Blender parser or arbitrary trusted Python. No memory/disk/CPU
quota, hostile file, external-library closure, missing texture, OOM, crash,
concurrent UI artist editing, or OS network-isolation test is claimed. Blender's
installed runtime dependencies are not exhaustively hashed by this source
closure; the executable is pinned separately.

Official API basis (checked 2026-09-17):

- [Python threading limitations](https://docs.blender.org/api/main/info_gotchas_threading.html):
  entry guards reject before importing/touching `bpy`; the only test thread
  exits and joins while the main thread waits. No persistent threads are used.
- [Mesh/Edit Mode representations](https://docs.blender.org/api/dev/info_gotchas_meshes.html):
  Edit Mode owns a separate mesh representation, so data must be synchronized
  and reacquired across mode changes.
- [Command-line switches](https://docs.blender.org/manual/en/4.2/advanced/command_line/arguments.html):
  background, autoexec suppression, offline preference and Python exception
  exit code are explicit; actual pin compatibility is checked by the probe.
- [Script execution security](https://docs.blender.org/manual/sv/5.2/advanced/scripting/security.html):
  disabling automatic scripts does not make all Python execution safe.
- [5.2 user resource directory](https://docs.blender.org/manual/en/latest/advanced/blender_directory_layout.html):
  the host supplies a fresh `BLENDER_USER_RESOURCES` directory.
