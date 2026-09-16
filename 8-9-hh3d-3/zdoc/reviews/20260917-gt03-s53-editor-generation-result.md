# S53 owned editor generation result

AUTHORITY=0; component implementation evidence, not an independent critic or GT-03 acceptance.

The existing `EditorOwner` now retires its old native editor before starting a
successor with a trusted generation seed. The fixed plugin handshake accepts
that seed once before effects; public requests cannot choose it. The host
rejects overflow before retirement. The scene-only adoption path is unchanged.

The retirement receipt binds the command/digest/retirement intent, full old
snapshot, process creation identity, and actual clean exit plus checked Job zero
and closure. Starting a successor requires that exact registered receipt. The
new registered adoption binds the selected complete bundle, all eleven working
files, full semantic state, actual script source/disk hashes and typed defaults,
new process/session identity, old generation + 1, and empty editor history.
Re-observation checks these facts remain current. Root object IDs may repeat
between processes; process/session/generation provide the boundary.

## Verification

- `20260917-gt03-s53-editor-generation-04`: 17/17 native checks, actual old
  editor PID 42900 and successor PID 4540 exit 0; both checked Jobs closed and
  observed zero, without tainted or retained handles. Owned wrapper/child exit
  0, no timeout, process tree verified. Source map still matches current bytes.
- `20260917-gt03-s53-editor-owner-01`: original scene-only capture/adoption
  regression 19/19, native editor PID 27840 exit 0, checked Job clean; owned
  wrapper/child exit 0, no timeout, tree verified. Source map matches.
- `python -B studio/tests/godot/test_editor_owner.py`: 14/14 focused tests.

Both native runs use pinned Windows GUI executable
`ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`
with `--headless --editor`; they are actual EditorPlugin runs, not headed UI.
The generation component test derives its expected semantic state from the
old actual captured fixture with an explicit source-hash change. It is a pure
fixture oracle, not a Linux validation receipt. Native readback separately
observes changed default 9 while the scene override remains 23. No selector,
public auth, durable journal commit, or combined publication claim is made.

## Integration API

`old.retire_for_replacement(command_id, digest, retirement_intent_id=...,
expected_snapshot=..., deadline_ms=...)` returns `EditorRetirementReceipt`.
`old.retirement_observation(receipt)` returns schema
`hh-godot-editor-retirement-1`, including `before`, `editor`, `cleanup`,
`effect_started_ms`, `effect_completed_ms`, `close_completed_ms`,
`next_generation`, and the exact coordinator retirement intent ID.

`EditorOwner.open_selected_generation(old, retired, evidence_parent, bundle,
editor_binary=..., selection={generation, identity}, semantic_bytes=...)`
returns `(new_owner, EditorGenerationReceipt)`.
`new_owner.observation(receipt, bundle)` returns schema
`hh-godot-editor-generation-adoption-1`, including both identities, registered
retirement hash/ID, generations/roots, full semantic/script/file observations,
effect timing, selected logical identity and complete manifest hash.

The coordinator must already have durably selected the exact bundle and retain
the retired owner for reconciliation. Selection fields here are logical input
bindings, not native selector/FileVersion authority. All receipts have
`public_ack=false`; only coordinator durable commit may acknowledge publicly.

## Corrections retained as evidence

Generation attempts 01/02 exposed a wrong host assumption: a non-tool script in
the editor is a placeholder and `can_instantiate()` is false. Actual standalone
Linux validation remains responsible for instantiation. Attempt 03 exposed
nested JSON integral file sizes represented as floats; the plugin now strictly
validates and normalizes the complete file map before comparison. Attempt 04
passes both corrections. Failed attempts remain unchanged for diagnosis.

No shared validation baseline was reminted during concurrent S53 edits. Source
files are ready for the coordinator's combined v4 publication run.
