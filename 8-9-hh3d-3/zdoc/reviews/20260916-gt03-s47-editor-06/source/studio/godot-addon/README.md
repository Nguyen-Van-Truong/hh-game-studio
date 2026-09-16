# GT-03 Godot adapter — implementation in progress

The internal `EditorPlugin` binds the actual edited fixture scene and the
editor's `EditorUndoRedoManager`. Main-thread calls inspect, preview, create,
update and remove approved nodes; guarded undo/redo preserves manual edits.
The catalog and pure Python validator project the shared GT-02 Request into
this fixed operation set. Discovery defaults to no enabled capabilities.

This layer returns `SCENE_APPLIED_IN_MEMORY`, not a protocol `COMMITTED`
receipt. It does not implement public IPC, runtime authorization, durable
multi-file publication, script parsing or untrusted execution. The immutable
scene/script bundle codec describes bytes and caller observations only.

`plugin.gd` checks the main thread before accessing `EditorInterface`. A scene
reload creates a new adapter generation; old IDs require fresh inspection.
The host must authenticate and validate the original wire, own/recheck the
lease at effect time, and reconcile manual edits before supplying projections.
Typed fixture JSON decoding is diagnostic code, not a public parser.

The actual-editor diagnostic is `tests/godot/run_editor_probe.py`. It freezes
inputs, checks the pinned GUI executable hash, and owns each fresh editor
process through the accepted bounded Job runner. It records actual exit and
process-tree cleanup, full-state revision across pack/reopen, native undo/redo,
manual-edit protection and Python-to-GDScript contract projections. Its direct
`ResourceSaver` call is fixture-only serialization and does not prove a
production save transaction. Previous failed runs remain diagnostic evidence.

The AppContainer startup spike has separate evidence and limits. Arbitrary
script execution remains disabled until all writable surfaces have a proven
disk bound in addition to memory, CPU, process and time bounds. Readiness and
progress authority remain in the tools plan, not this document.

Engine API references: [EditorPlugin](https://docs.godotengine.org/en/stable/classes/class_editorplugin.html),
[EditorUndoRedoManager](https://docs.godotengine.org/en/stable/classes/class_editorundoredomanager.html),
[EditorInterface](https://docs.godotengine.org/en/stable/classes/class_editorinterface.html).
