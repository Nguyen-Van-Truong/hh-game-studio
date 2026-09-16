# GT-03 Godot adapter — implementation in progress

The S52 candidate now joins authenticated loopback `scene.save` to the actual
owned Windows EditorPlugin, isolated Linux validation, a twelve-object native
bundle, selector CAS, same-editor reload and full semantic readback. The happy
integration probe has run successfully; this is not GT-03 acceptance. See
`PUBLICATION_OWNER.md` for the active path and its limits. Gate progress lives
only in the tools plan.

Active publication uses `publication_owner.py`, `publication_session.py`,
`publication_transport.py`, `editor_owner.py`, `validation_owner.py`,
`publication_journal_v3.py` and `protected_bundle.py`. The v1/v2 codecs and
journals below remain earlier component contracts and regression dependencies;
their individual observations must never be presented as public save receipts.

The internal `EditorPlugin` binds the actual edited fixture scene and the
editor's `EditorUndoRedoManager`. Main-thread calls inspect, preview, create,
update and remove approved nodes; guarded undo/redo preserves manual edits.
The catalog and pure Python validator project the shared GT-02 Request into
this fixed operation set. Mutating requests bind both the scene revision and
the complete selected eleven-file project revision. Static discovery defaults
to no capabilities; the live publication owner enables its completed methods.

Direct in-memory scene commands return `SCENE_APPLIED_IN_MEMORY`. Only the
outer publication owner can issue a committed save response after durable
native selection and registered live-editor readback. The immutable
scene/script bundle codec itself describes bytes and caller observations only.
`publication_state.py` validates bounded phase history; `publication_journal.py`
persists that history through the accepted native event log and Registry
custody. Their internal `COMMITTED` observation does not prove that Godot ran,
that candidate blobs exist, or that a selection became active. Reopened
journals remain read-only until a separate recovery owner is implemented.

`plugin.gd` checks the main thread before accessing `EditorInterface`. A scene
reload creates a new adapter generation; old IDs require fresh inspection.
The host must authenticate and validate the original wire, own/recheck the
lease at effect time, and reconcile manual edits before supplying projections.
The installed bounded internal IPC decodes only fixed operations. Public
requests are separately parsed, authenticated and schema checked by the host.

The actual-editor diagnostic is `tests/godot/run_editor_probe.py`. It freezes
inputs, checks the pinned GUI executable hash, and owns each fresh editor
process through the accepted bounded Job runner. It records actual exit and
process-tree cleanup, full-state revision across pack/reopen, native undo/redo,
manual-edit protection, a fixed trusted script attachment/exported value and
Python-to-GDScript contract projections. Its direct
`ResourceSaver` call is fixture-only serialization and does not prove a
production save transaction. Previous failed runs remain diagnostic evidence.

The AppContainer startup spike has separate evidence and limits. The internal
`linux_executor.py` provides fixed parse/import diagnostics in an owned Docker
container with a read-only filesystem and bounded temporary storage, output,
memory, CPU, process count and time. It does not interpret child success
markers as trusted validation or expose an execution capability. Its hostile
fixtures live in `tests/godot/linux_probe_fixtures.py` and must only run through
that confined executor. Public script activation remains disabled.

The early two-content-blob codec is not a deployable Godot project. S52 uses
codec v2's complete eleven inputs plus the manifest, including fixed UIDs and
trusted project/addon metadata. Script replacement, writable restart/recovery,
artist-project saves and final gate conformance remain unfinished. Readiness
and progress authority remain in the tools plan, not this document.

Engine API references: [EditorPlugin](https://docs.godotengine.org/en/stable/classes/class_editorplugin.html),
[EditorUndoRedoManager](https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html),
[EditorInterface](https://docs.godotengine.org/en/stable/classes/class_editorinterface.html).
