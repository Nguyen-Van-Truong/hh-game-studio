# GT04 first trusted Blender fixture slice

AUTHORITY=0. This private background adapter is implementation work for GT04,
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
