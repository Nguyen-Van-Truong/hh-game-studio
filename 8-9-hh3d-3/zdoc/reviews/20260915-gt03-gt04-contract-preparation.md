# GT-03 / GT-04 contract preparation

PREPARATION_ONLY=1
AUTHORITY=0
RESEARCHED_AT_UTC=2026-09-15T16:12:59Z
CONSUMER_IMPLEMENTATION_OR_MUTATION=NONE
ENGINE_PROCESSES_STARTED=0
PLAN_OR_SOURCE_EDITS=NONE

Prepared under plan section 8.1. The current plan still holds GT-02 CANDIDATE
while TX15 safe-write proof is missing; its clarification expressly prevents
closing the gate from fixture PASS alone. The catalog below is a proposal for
later schema/fixture locking, not implemented capability or a change to GT-03/04.
The final S30 critic verdict remains untouched.

## Exact pin and reuse inventory

`studio/toolchain.lock.json` SHA-256:
`28bdce555e9a44ef68193723d512feda02c42a417ceb78faf0b29f52d095dca9`.

| Pin / path | Applicable reuse and limits |
|---|---|
| Godot 4.7.2-stable, commit `ed1daf0bf001b61586d9930840f2f1394092c079` | Console SHA `c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643`; GUI SHA `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`. Use matching 4.7 API docs; verify exact binary before probes. |
| Blender 5.2.1 | Executable SHA `8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06`; archive SHA `0e631dad7d0cad6d5d18abdd2e2550f6c0213215334eda00ddbd3d22b96ecb2c`. 5.2 documentation supports preparation; exact 5.2.1 behavior still needs native tests. Host Python 3.11.9 is OBSERVED_ONLY and is not evidence of Blender's bundled Python version. |
| `studio/protocol/{core,errors,names}.py`, `studio/host/core/{limits,journal,redaction}.py` | Reuse the accepted envelope/status/digest/domain and safety contracts after GT-02 closes. `transport.py` is a fixed counter fixture, not a ready Godot/Blender dispatch service. Do not amend the frozen protocol from an adapter lane. |
| `studio/fixtures/sample-game/addons/gt01_probe/{plugin.cfg,probe.gd}` | Reuse opt-in EditorPlugin lifecycle, deferred startup and actual edited-root/window readback. It contains no mutation, UndoRedo or save transaction. Main fixture root is Control; prepare a leased standalone authored 3D scene on a snapshot for adapter tests. |
| `studio/fixtures/sample-blender/{create_fixture.py,README.md}` | Reuse original 1 m cube, transform/material/unit assertions and save/reopen pattern. Its trusted-new-output path checks and `os.link` publication are GT01 bootstrap behavior, not reusable general safe-write authorization. |
| `studio/build/bootstrap/{run_fixture,lifecycle_probe}.py` | Reuse source hashing, isolated snapshots/user directories, true child exit and owned process-tree handling. Add adapter-specific postconditions; exit 0 alone is insufficient. |

At inventory time `studio/godot-addon`, `studio/blender-addon`,
`studio/host/blender`, `studio/tests/godot` and `studio/tests/blender` do not
exist. No external MCP addon was downloaded or assumed compatible.

## Proposed minimal semantic catalog

All mutations retain command ID/digest, project, stable target, expected
revision, lease/fencing, deadline and checkpoint. Resolve IDs anew at execution
and after undo/reload; engine ObjectID/Python object references are not durable
identity. Use a serialized adapter-owned stable ID with uniqueness checks.
Property names, class choices and payloads are allowlisted typed data, never
method names/callables supplied by the client.

| Proposed operation | Native mapping and required result |
|---|---|
| `godot.scene.inspect` | EditorInterface.get_edited_scene_root; bounded stable-ID tree and approved properties/resources, scene path/revision and canonical semantic hash. No selection-dependent target. |
| `godot.node.create`, `.properties.set`, `.remove` | Start with approved Node3D/MeshInstance3D types and finite transforms. Register complete do/undo changes in EditorUndoRedoManager, including parent order, owner, references and stable ID. Read back exact count/type/parent/owner/properties; removal must preserve enough state for undo. |
| `godot.resource.create`, `.properties.set`, `.remove` | Initially BoxMesh/StandardMaterial3D with bounded approved fields. Undo restores previous resource references/values; reject deletion while referenced unless the command explicitly includes a validated atomic relink. Prove save/reopen identity and references. |
| `script_text.replace` | Required GT-03 operation: allowlisted `.gd`, expected script hash, bounded UTF-8 text/patch, diff, staged parse/import in a disposable sandbox including @tool/import hooks. Read back the exact reloaded script hash. Scene and script share one revision/publish intent. Parse-only success does not authorize execution. |
| `godot.project.save`, `godot.history.undo`, `.redo` | Save only the leased staged project; pack owned nodes/resources, check save errors, reload/reopen and compare semantic state. Undo/redo operates the expected scene/history action, not arbitrary user history; each is a new semantic command and durable receipt. |
| `blender.scene.inspect`, `blender.mesh.create` | Resolve a stable-ID object/collection, inspect bounded mesh/material/transform data. Start with a trusted cube primitive; use bpy.data meshes/objects and collection links inside a registered UI operator. Counts, bounds, material slots and stable IDs must read back; same-ID retry cannot create a second object. |
| `blender.object.transform.set` | Typed location/rotation/scale in declared Object mode; direct data API within the UI operator. Check mode/context/revision before effect; read back matrix/bounds with a locked epsilon. Restore previous mode/active object/selection only when still valid. |
| `blender.source.save`, `blender.history.undo`, `.redo` | Save a leased staged copy and reopen it in an owned verifier process; compare geometry, transforms, materials and dependency closure. UI changes require proved undo support. Background jobs use checkpoint/recovery and must not claim a UI undo stack. |
| `blender.export.glb` | A fixed, hashed export script/config in a separate bounded background process, staged input/output and no arbitrary exporter options. Return output hash and structural/semantic readback. GT-05 still owns full GLB validation/import/asset-manifest acceptance; GT-04 export is not cross-app activation. |

The schemas must lock operation-specific counts, epsilon, script-size, UI
burst and job CPU/RAM/disk/time limits before dispatch. Preserve the stricter
of all negotiated caps: current host limits include 256 KiB envelope/result,
128 KiB payload, 16 pending jobs and separate control capacity; generic arrays
and strings remain capped by the protocol. Do not extend limits from the wire.

## API implications from official documentation

- Godot plugins obtain the editor undo manager via `get_undo_redo()`. Use
  an explicit scene custom_context and complete do/undo methods/properties;
  history is scene-specific or global, not a project publish transaction.
  New/deleted node references require correct lifetime handling. Engine API
  availability does not make arbitrary node-method dispatch safe.
  [EditorPlugin 4.7](https://docs.godotengine.org/en/4.7/classes/class_editorplugin.html),
  [EditorUndoRedoManager 4.7](https://docs.godotengine.org/en/4.7/classes/class_editorundoredomanager.html).
- Keep live scene operations on the main thread. `PackedScene.pack` includes
  owned descendants, so owner omission must be a regression case. ResourceSaver
  and EditorInterface saves require checked results and actual reopen; save
  signals or commit_action do not prove multi-file atomicity/durability.
  [Thread-safe APIs 4.7](https://docs.godotengine.org/en/4.7/tutorials/performance/thread_safe_apis.html),
  [PackedScene 4.7](https://docs.godotengine.org/en/4.7/classes/class_packedscene.html),
  [ResourceSaver 4.7](https://docs.godotengine.org/en/4.7/classes/class_resourcesaver.html),
  [EditorInterface 4.7](https://docs.godotengine.org/en/4.7/classes/class_editorinterface.html).
- Blender UI polls bounded serialized IPC from an external host using
  `bpy.app.timers.register`; unregister on unload and rebind deliberately on
  file load. Do not host persistent Python/network threads in Blender, including
  implicit feeder threads from multiprocessing.Queue. Long jobs belong in
  separate owned processes. [Timers 5.2](https://docs.blender.org/api/5.2/bpy.app.timers.html),
  [Threading warning 5.2](https://docs.blender.org/api/5.2/info_gotchas_threading.html).
- UI operators that modify data require REGISTER/UNDO and valid poll/context.
  CANCELLED is not rollback after a partial edit: restore and verify first or
  report uncertainty. `temp_override` needs consistent window/area/region and
  cannot restore destroyed context; retain values/IDs rather than stale bpy
  references across undo or load. [Operator 5.2](https://docs.blender.org/api/5.2/bpy.types.Operator.html),
  [Context 5.2](https://docs.blender.org/api/5.2/bpy.types.Context.html),
  [Mesh 5.2](https://docs.blender.org/api/5.2/bpy.types.Mesh.html).
- Use the pinned executable with explicit background/factory-startup,
  disable-autoexec, nonzero python-exit-code and a trusted script file; no
  arbitrary python-expr, system Python environment or remote addon install.
  These flags do not sandbox the file parser or OS access. The 5.2 threading
  and English CLI pages were retrieved directly over HTTPS after browser-tool
  retrieval errors; both returned HTTP 200. [CLI 5.2](https://docs.blender.org/manual/en/5.2/advanced/command_line/arguments.html).

## Ownership, failure probes and order

GT-03 owns `studio/godot-addon/`, its operation catalog,
`studio/tests/godot/` and explicitly leased fixture snapshots. GT-04 owns
`studio/blender-addon/`, `studio/host/blender/`, `studio/tests/blender/` and
its leased `.blend` fixture. Catalog/schema files must be assigned inside the
respective allowed scope before coding. One writer per file/project revision;
source addon is authority, generated fixture copies are hash-verified consumers.
No shared protocol, platform, Vault Fighters or game-source mutation is opened
by this preparation.

Mandatory small failure groups, each with before/after hash and real host exit:

1. **Both:** bad schema/types/NaN/range/root, expired/replaced lease, stale ID,
   owner edit, sensitive payload, duplicate ID with same/different digest;
   stop/reconnect, lost reply before/after admission and terminal receipt.
2. **Safe save prerequisite:** reparse/hardlink/ancestor/final-identity swaps,
   cross-volume/locked destination, write/flush/fsync/disk-full failure and
   crashes before/after publish/reload/ACK. Preserve last-good and newer owner
   edits; uncertain outcomes use lookup/reconcile, never a claimed no-effect.
3. **Godot:** create/set/remove → inspect → undo → redo → save → reopen;
   wrong scene/history, missing owner, referenced-resource deletion, scene
   reload between validation/apply, scene+script partial save, invalid/oversized
   script and malicious @tool/import hook. Editor and Play roles stay separate.
4. **Blender:** Object/Edit mode and selection/context mismatch; undo after
   object recreation/file load, duplicate create, timer unregister/load and
   no persistent threads; missing/external texture/library, driver/addon,
   invalid mesh and resource caps. Timeout/Stop/OOM/crash terminate only the
   owned job and leave diagnostics; fresh reopen validates `.blend` contents.

Concrete order: finish and accept GT-02 including its required safe-write proof;
freeze adapter catalogs/limits/leases; run native pin/API and read-only IPC
probes on independent snapshots; implement and prove one reversible edit plus
undo/readback per adapter; add staged save/reopen/crash recovery; add GT-03
script+scene transaction and GT-04 bounded background/export cases; only then
assemble each WP's exact-source candidate for two critics. GT-03 and GT-04 may
proceed independently after dependency acceptance and distinct leases. Keep
MCP compatibility experiments time-boxed after the native gates; GT-05/06/07
retain their own pipeline, Play/input and activation/recovery deliverables.

No native probe was executed in this preparation, so the API mapping is a
documented implementation proposal, not runtime or safety evidence.
