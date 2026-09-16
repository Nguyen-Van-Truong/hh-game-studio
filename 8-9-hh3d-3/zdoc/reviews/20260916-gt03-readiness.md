# GT03 readiness — read-only preparation

2026-09-16. AUTHORITY=0. This is implementation preparation, not another plan,
gate opening, runtime evidence or acceptance. No source/plan edits, tool installs
or engine launches were performed. Initial HEAD was
`0de2ce0b0c9943d4ac8be5332c000c586b219e6c`; the coordinator advanced the tools
plan to S47 / GT03 during this review. The tools plan remains the sole progress
authority. Other critics' reports were not used as evidence for this preparation.

Read: local AGENTS.md; tools plan GT03, 2.2/2.3/2.5/2.6, TQ03,
TX02/03/06/09/13/15; current sample-game fixture, bootstrap runner/toolchain,
and relevant GT02 storage/transport boundaries. Primary Godot references below
were checked against the 4.7 documentation and, where available, the exact
4.7.2-stable source tag.

## What is ready, and what is missing

The smallest complete GT03 slice is **one real EditorPlugin operating on one
owned fixture project revision**, covering approved node/resource create,
update and remove; stable-ID inspect; guarded undo/redo; staged scene/resource
and script replacement; disposable validation; one Godot-only active manifest;
actual save/reopen/readback and crash/lost-response recovery. A node moving in
memory, a successful `commit_action()`, or a parser returning zero is not that
slice. Full-text-only `script_text.replace` is a reasonable initial declared
mode because the plan permits bounded patch/full text; arbitrary patch formats
need not be added.

Available locally:

| Component | Verified preparation observation |
| --- | --- |
| Godot pin | Lock is 4.7.2-stable, source `ed1daf0bf001b61586d9930840f2f1394092c079`; official archive exists. No pin change needed. |
| Console executable | Present under `studio/.local/tooling/godot-4.7.2-stable/`; SHA-256 `c8f0a6bc45a19b33541501e57f6f7cd972ab18453743266339d495cbbe846643` matches lock. |
| GUI executable | Present alongside console; SHA-256 `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424` matches lock. |
| Local tools | Python 3.11 executable, Node, Git and rg resolve locally. No Godot or Blender process was observed during inventory. |
| GT01 sample-game | Independent `project.godot`, `main.tscn`, main/trace scripts and an enabled `gt01_probe` plugin. Probe observes root/visibility and exits; it does not mutate or implement UndoRedo. UI children are built at runtime, so they are unsuitable as existing editor stable targets. |
| Bootstrap | `run_fixture.py` copies an isolated Unicode snapshot, separates user directories, captures actual exits and owns the process tree. It already demonstrates import/check-only/editor modes in prior work; no mode was run here. |
| GT02 | Reuse envelope/JCS/limits, auth/lease/fencing/dedupe semantics, private blobs/events, checked Windows file primitives and retained process/pipe ownership. Current public consumer remains the exact inert `fixture.active-release` contract. |
| Missing | No `studio/godot-addon/`, Godot operation catalog, `studio/tests/godot/`, Godot queue bridge, stable-ID/revision reducer, OS-confined script validator, or Godot project publish/recovery consumer exists in the examined tree. |

The official [4.7.2 archive](https://godotengine.org/download/archive/4.7.2-stable/)
confirms the pin. Hash equality above is a local observation, not a new runtime
version probe. The lock's `CANDIDATE` and template-not-installed fields are
historical bootstrap schema facts, not permission to refetch latest or block
GT03 on export-template work belonging to GT08.

## Godot API consequences

Use `@tool extends EditorPlugin` and its `get_undo_redo()` manager. Register
complete do/undo work, select the edited scene root as `custom_context`, and
disable command merging. Explicitly order undo operations: default undo order
is insertion order, not automatically reversed. New/removed nodes need the
appropriate do/undo reference ownership; those node lifetime helpers are not
for Resources. These API details are in the exact-tag
[EditorUndoRedoManager definition](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/EditorUndoRedoManager.xml).

All live scene/resource inspection, validation against current objects, mutation,
UndoRedo construction and semantic readback run on the editor main thread.
External work supplies a bounded queue of data; it must not retain Node/Object
references. A deferred call schedules work but does not preserve the lease,
revision or target validation performed earlier; recheck at execution. The
[thread-safety documentation](https://docs.godotengine.org/en/4.7/tutorials/performance/thread_safe_apis.html)
explicitly excludes active scene-tree mutation from thread safety.

Created nodes need `owner` set to the edited root after parenting, otherwise
they may exist visibly yet disappear after save. `PackedScene.pack()` stores
owned descendants, and `get_state()` permits structural readback. Preserve
ownership, sibling index and stable metadata on undo/recreate.
[PackedScene documentation](https://docs.godotengine.org/en/4.7/classes/class_packedscene.html)

`EditorInterface.save_scene()` returns an error; `save_scene_as()` and
`save_all_scenes()` do not provide a multi-file transaction receipt. Scene-save
signals and `mark_scene_as_unsaved()` are editor events/state, not disk barriers.
Use actual save results plus file/hash and independent reopen semantics. The
exact-tag [EditorInterface definition](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/EditorInterface.xml)
also exposes scene reload. Resource saves similarly return an Error and may
change resource-path ownership depending on flags; use explicit staged paths
and do not accidentally take over a live resource path.
[ResourceSaver documentation](https://docs.godotengine.org/en/4.7/classes/class_resourcesaver.html)

`_apply_changes()` can flush pending plugin edits before editor saves/tab changes;
`_clear()`/scene-change/scene-close handling must invalidate target caches.
`_build()` can refuse an unverified Play request, but is not the sandbox or the
complete Play lifecycle. [EditorPlugin documentation](https://docs.godotengine.org/en/stable/classes/class_editorplugin.html)

For readback, `ResourceLoader` may reuse cached resources, and `exists()` may
even succeed for a resource present only in cache. An independent fresh editor
process is the strongest simple fixture check. Where an in-process check is
needed, explicitly test the deep-ignore cache mode and dependencies; never use
an ordinary cached load as proof of newly saved bytes.
[ResourceLoader documentation](https://docs.godotengine.org/en/4.7/classes/class_resourceloader.html)

## Proposed bounded contract and ownership

Keep GT02 `studio/protocol/` read-only. Put the Godot descriptor/operation schema
with the addon, advertising only the operations actually implemented. A suitable
initial fixed catalog is inspect, approved-node create/update/remove,
approved-resource create/update/remove, script_text.replace, guarded undo/redo
and one project commit. Reject unknown classes, properties, method names,
resource loaders and caller-supplied executable paths. Use explicit constructors
and property setters for a small fixture vocabulary, such as Node3D,
MeshInstance3D, BoxMesh and StandardMaterial3D; no ClassDB-driven arbitrary class
construction or generic method invocation from a request.

Create a dedicated scene in the disposable sample-game snapshot instead of
rewriting the accepted GT01 fixture. It should contain a stable-ID root, one
editable child, one owned external `.tres`, and one allowlisted non-tool `.gd`.
Keep plugin/validator scripts outside the editable allowlist. The scenario can
create a node/resource, change a finite typed property, remove and undo/redo it,
then commit a scene/resource/script change together.

Persist logical IDs in scene/resource metadata and a versioned manifest; reject
missing or duplicate IDs. NodePath may be a resolver hint, never authority.
Resolve again from the current edited root after scene reload. Revision must
include the project file closure and the current semantic editor snapshot;
checking disk timestamps alone misses unsaved owner edits. Before apply and
publish, compare expected revision, scene identity, lease owner/fence and Stop.
Maintain finite numbers/ranges, payload/depth/array caps and result pagination.

An undo request is a new revision-checked semantic action. It may only undo the
expected top history/action and base state; after manual edits, preserve both
states and require reconciliation. UndoRedo methods are not a transactional
exception mechanism: prevalidate the whole action, constrain side-effecting
setters, retain before-state/checkpoint and verify semantic state afterward.
An unexpected partial action means UNKNOWN/recovery, not automatic success.

Suggested exclusive file owners after coordinator dispatch:

| Owner | New allowed paths and responsibility |
| --- | --- |
| Godot adapter | `studio/godot-addon/plugin.cfg`, plugin/queue/registry/operations/transaction/readback `.gd` files; main-thread state and real UndoRedo. |
| Godot host support | `studio/godot-addon/host/` for the typed catalog, revision/session orchestration, validator launcher and Godot publisher; imports GT02 primitives without changing their meaning. The coordinator may choose a different host path only after making the GT03 file lease explicit. |
| Fixture/evidence | `studio/tests/godot/` harness, native/engine tests and fixture overlays copied into disposable snapshots; actual process exits and complete source closure. |

The placement above stays within GT03's addon/catalog/tests scope. It is not
authorization for this reviewer to create those files.

## Scene + script publish and recovery

Prefer complete immutable Godot revisions with identical internal `res://`
layout. Editor working copies, validator copies, active release and Play copies
are distinct roles. The trusted host owns the one project lease, protected
manifest/journal and activation; Godot writes only its disposable candidate.
Once the editor exits/quiesces and validator processes drain, the host securely
imports the bounded allowed output set, rejects unexpected files/reparse aliases,
checks hashes, and stages the complete release. Do not replace a `.tscn` that is
still open in a separate editor.

Use one transaction record for all scene/resource/script files:
PREPARED (base revision, full affected-file set and checkpoint) → VALIDATED
(candidate hashes, parser/import and semantic result) → ACTIVATING (durable
intent, current lease/fence/base comparison) → active manifest swap on the proven
filesystem → fresh Godot reopen/readback → COMMITTED receipt. Scene and script
become eligible together through the manifest; there must be no sequential
in-place publication of half the project. Missing/uncertain barriers or readback
leave UNKNOWN with last-good/pending evidence. Restart resolves the manifest and
journal without rerunning the original mutation or clearing Stop.

This is a **new Godot-specific consumer**, not a cast of `ManagedFixtureOwner`.
The accepted S46 rearm checks exactly `.writer` plus `active.json`, and its
consumer serializes inert JSON. Do not add `.tscn`/`.gd` files to that root and
relax its gate. Reuse the lower-level durability/identity methods and bounded
event/custody design; specify the Godot manifest/recovery invariant separately.
GT03 owns Godot-only atomic publication now; cross-app Blender activation and
general multi-agent recovery remain GT07.

## script_text.replace and sandbox gaps

For the first catalog, target one stable script ID resolving to a known `.gd`,
with expected old SHA/project revision and a bounded UTF-8 full replacement
(for example a declared 64 KiB cap). Reject malformed UTF-8, oversized bytes,
outside/alias paths, stale script or scene revision and unknown fields before
staging. Compute and show bounded diff/affected files and retain checkpoint.
The live editor must not receive the new source before validation.

Stage the complete dependency closure into a separate OS-confined disposable
editor workspace. Parse every changed script and run actual project import,
then validate the saved scene/resource/script hashes together. `--check-only`
parses the `--script` target; it is not a complete project import. `--import`
starts the editor, imports resources and exits. Neither switch is an isolation
boundary. [Godot command-line documentation](https://docs.godotengine.org/en/4.7/tutorials/editor/command_line_tutorial.html)

Setting `Script.source_code` does not automatically reload implementation;
`reload()` returns an error and `is_tool()` identifies editor-executing scripts.
Use those checks only inside the validator or on already approved code.
[Script documentation](https://docs.godotengine.org/en/4.7/classes/class_script.html)
Tool scripts can execute in the editor, including while developing/importing
the staged project; a new script's successful parse does not grant execution
authority. New unreviewed tool/plugin/import-hook code must never enter the
owner's live editor. The first supported editable script may explicitly exclude
tool/plugin classes and dependency changes; still test hostile tool/import
inputs inside the disposable boundary before rejection.
[Running code in the editor](https://docs.godotengine.org/en/4.7/tutorials/plugins/running_code_in_the_editor.html)

The bootstrap's snapshot, user-directory redirection and Job timeout do **not**
provide network denial, file-access confinement, memory limits or disk quota.
The S46 AppContainer launcher proves a native fixture, not stock Godot's launch
compatibility. Before admitting generated source, prove an owned Godot validator
with narrowly granted read-only tool/input roots, disposable writable cache/output,
no network/child execution, memory/time/disk bounds and actual complete teardown.
Never pass a bearer through argv/environment or preserve ambient secrets.

A pin-specific trap: the Windows console executable is a wrapper that calls
CreateProcessW for the GUI binary and creates another Job. Launching that wrapper
under a child-process-denial policy prevents engine startup. Prefer the locked
GUI binary directly, including `--headless`, with explicit standard-handle
capture; prove it on the pin before claiming compatibility.
[4.7.2 console wrapper source](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/platform/windows/console_wrapper_windows.cpp)

The Godot command queue transport also needs a bounded pin-specific spike:
Python `OwnedPipe` cannot simply be instantiated by stock GDScript. The exact
OS API offers blocking stdin reads and nonblocking `execute_with_pipe()` for
Godot-created children; neither automatically gives the host-created two-role
endpoint ownership policy. A dedicated byte-I/O thread may bridge inherited
stdin to a main-thread data queue, with fixed framing/caps, external startup
deadline and owned teardown; prove shutdown behavior before adopting it. Never
call blocking stdin reads on the editor main thread. Do not introduce an
unreviewed TCP shortcut or launch a privileged helper from an untrusted validator.
[4.7.2 OS API definition](https://raw.githubusercontent.com/godotengine/godot/4.7.2-stable/doc/classes/OS.xml)

## Acceptance coverage and immediate bounded task

| Requirement | Concrete required check |
| --- | --- |
| TQ03 | Actual editor before/after/undo/redo/reopen, node and resource lifetimes, exact script preservation, semantic hash and saved bytes; all mutations on main thread. |
| TX02 | Close/reload scene; stale IDs/revisions and duplicate IDs reject; new object identities resolve from stable IDs. |
| TX03/TX15 | Wrong types/ranges/NaN/path aliases/schema/depth/size; malformed/oversized/stale script; parse/type/import failures; changed links at import/publish; no outside write or secret echo. |
| TX06 | Two writers, expired/replaced lease and late phase, owner edits in memory/on disk, undo after newer user edit; preserve checkpoint/candidate and reject stale publish. |
| TX09 | Real process cut before/after staged save, each activation barrier and readback; partial output, held target/antivirus-like sharing conflict, disk/quota and cross-volume refusal; never half-active scene/script. |
| TX13 | Separate editor/validator/Play PID/start/root/userdir roles; Play uses immutable approved revision; no runtime state mutation presented as editor proof. Real input/pause/capture remains GT06. |
| Receipt safety | Same ID exact retry, conflicting retry, lost response at every receipt point, crash lookup, Stop during work, bounded drain and actual process-tree-zero proof. |

First bounded task after explicit coordinator dispatch: add the small addon
catalog and disposable actual-editor harness, then prove one create/update/remove
transaction with stable-ID inspect and undo/redo/reopen on the pinned executable.
In parallel only where files are separately owned, prove the stock-Godot
validator/queue process boundary. Keep mutation/script capabilities unavailable
where a required boundary is unproved. Then connect the Godot-specific publisher
and script validation to complete the vertical slice and required crash matrix.
Do not tick GT03 after the initial plugin spike: scene+script validation,
publication/recovery and two critics are explicitly part of GT03, not deferrable
to GT07.
