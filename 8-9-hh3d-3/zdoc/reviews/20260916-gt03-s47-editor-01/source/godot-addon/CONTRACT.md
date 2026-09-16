# GT-03 Godot operation catalog

This is a declaration, pure validator and dry-run projection. It does not
authorize a runtime command, open a project file, call Godot, parse/import a
script, save a scene, publish a release or emit a COMMITTED receipt. GT-02's
shared `Request`, `Discovery`, RFC 8785 canonical serializer, payload hash and
operation/target/payload/schema digest are reused without changes.

The fixed disposable fixture paths are `scenes/fixture.tscn` and
`scripts/fixture_actor.gd`. Wire paths never use `res://`, absolute/native
paths, backslashes, aliases or user-chosen filenames. Exact script-path
comparison precedes any downstream parser. The native host must still check
actual handles/reparse/link identity under its protected snapshot root;
string validation here is not safe-open proof.

`operations.json` defines nine operations. Its static `implemented` and
`runtime_enabled` flags are all false. `catalog()` returns a detached copy.
`discovery(project_id, implemented=frozenset(), runtime_enabled=frozenset())`
returns a shared `Discovery`: only explicitly enabled operations are present,
and enabled must be a subset of implemented. Both sets are trusted backend
configuration, not request fields. The default advertises no capabilities.
In particular, declaring save/script operations does not enable them before
their staged native backends exist. `CATALOG_DIGEST` is the shared canonical
SHA-256 of the complete declaration, distinct from a request's own digest.

## Envelope and trusted observations

Every call uses the existing shared `Request` envelope. `expected_revision`
is `sha256:` followed by 64 lowercase hex characters, representing the
observed semantic scene revision. `expected_generation` is an integer reload
epoch in every payload; it must match the trusted observation. It does not
replace the project revision. The real host must cover scene and script edits
with one project revision/publish journal, and must refresh the revision when
either changes. There is no additional wire schema or token in this catalog.

`ValidationContext` is a frozen trusted-call structure containing project,
revision, generation, lease ID/fence/expiry, current epoch milliseconds,
`tuple[NodeState, ...]`, the two allowlisted file hashes as a tuple of pairs,
history availability and stopped state. Remote payloads must never construct
this context. Its observations are checked for internal consistency; they are
not proof that an OS lease, live editor state or source file currently matches.
The dispatcher authenticates separately and rechecks identity/revision/lease
at effect time on the main thread. Duplicate receipt lookup precedes new
admission there; this validator does not implement a journal/deduplication.

`validate_request(request, context)` accepts an exact shared `Request` or its
wire dictionary, validates through the shared parser, makes detached copies,
and returns a frozen `ValidatedCommand`. The `projection` and `preview`
properties return new dictionaries on every access. Mutating either result
cannot change retained input or a later accessor result. Failed validation has
no scene/file effect. Errors use fixed codes and do not echo script text.

New admission requires matching project, revision, generation, lease and
fence, with `now < deadline <= min(lease expiry, now + 30000ms)`. Stop permits
inspection only. The host must authenticate reads too; inspection does not
imply a write scope. A successful validation is neither an ACK nor permission
to call an arbitrary native/API method.

## Exact operation shapes

All rows include `expected_generation` in their payload. The stable root ID is
`root`; editor node metadata is `hh_studio_id`. Stable IDs match
`[a-z][a-z0-9._-]{0,63}` and names `[A-Za-z][A-Za-z0-9_]{0,47}`. Runtime objects
must be resolved again by stable ID after reload; ObjectID and selection are
not wire targets.

| Operation | Shared Request target | Additional exact payload fields |
| --- | --- | --- |
| `scene.inspect` | `{"stable_id":"root"}` | `offset` integer 0–64, `limit` integer 1–64 |
| `scene.node.create` | Existing parent's stable ID | `stable_id`, `node_type`, `name`, `position`, `rotation_degrees`, `scale`; `box_size` required only for MeshInstance3D |
| `scene.node.update` | Existing node's stable ID | Nonempty `changes` containing only name/position/rotation_degrees/scale/box_size |
| `scene.node.remove` | Existing nonroot leaf's stable ID | No additional fields |
| `script_text.replace` | `{"path":"scripts/fixture_actor.gd"}` | `expected_sha256` lowercase 64 hex and `text` |
| `scene.undo`, `scene.redo` | `{"stable_id":"root"}` | `steps` exactly integer 1 |
| `scene.preview` | `{"stable_id":"root"}` | `operation`, `target`, `payload` for one mutation above; nested generation must agree |
| `scene.save` | `{"stable_id":"root"}` | `expected_files`, exactly both fixed paths mapped to their current lowercase SHA-256 hex |

No unknown fields are accepted. `scene.preview` cannot nest itself, inspect
or save. Preview checks the same proposed mutation against current context;
it neither applies an effect nor consumes undo history. Its root-side result
contains a `preview_command` with the six direct projection fields (including
the outer command ID/revision), for the engine's preview path only. It must
not be sent to the engine's apply path as if the outer operation were a mutation.

The direct scene engine projection is exactly:

```json
{
  "operation": "scene.node.update",
  "command_id": "command.example",
  "expected_revision": "sha256:<64 lowercase hex>",
  "expected_generation": 1,
  "target_stable_id": "box",
  "payload": {"expected_generation": 1, "changes": {"position": [1, 2, 3]}}
}
```

Script projection additionally contains `target_path` and a null
`target_stable_id`; it belongs to the staged script host, not the scene engine
module. Envelope lease/project/deadline fields are checked by the host and not
turned into engine authority by this projection.

## Limits and preview meaning

The managed graph has at most 64 nodes, depth 16 including root, no duplicate
stable IDs or sibling names, no orphan/cycle and a Node3D root. Approved types
are Node3D and MeshInstance3D; the latter owns a BoxMesh. No arbitrary classes,
resources, signals, properties, methods or script attachments are exposed.

All vectors have exactly three finite numeric components; booleans are not
numbers. Position is bounded to [-10000,10000], rotation degrees to [-360,360],
scale and BoxMesh size to [0.001,1000]. A Node3D cannot carry `box_size`.
Remove is leaf-only and requires a checkpoint. Parent changes/reparenting and
bulk subtree deletion are unsupported.

Script replacement is full-text only, UTF-8 at most 16384 bytes, with LF line
endings and no NUL. Shared protocol character/depth limits also apply. `@tool`,
imports and syntactically invalid source remain inert text here; validation
does not falsely claim a successful parser result. The preview explicitly
reports `script_parse_status=NOT_RUN`. A trusted owned disposable editor must
perform real parse/type/import checks and actual hash readback before publish;
the source must not execute in a live editor just because this validator passed.

Dry-run output contains `affected_files`, a structured `diff`, checkpoint and
recovery requirements, `changes_applied=false`, `runtime_authorized=false`,
the exact request digest and observed revision/generation. Node diffs contain
before/after semantic properties. Script diff is a hash/UTF-8-byte/line-count
summary, not a fabricated textual diff against an unread file. The launcher
must provide a source diff from verified staged bytes when presenting script
changes. Save and history diffs explicitly defer unknown contents to staged
Godot save/readback or revision-bound runtime history. Payload and returned
projection/preview are each bounded to 65536 canonical bytes.

Scene undo/redo uses the editor's exact revision-bound history; it must not
overwrite a newer manual edit. Scene/script save still requires checkpoint,
staged complete output, journaled same-volume publish/recovery and reload
readback. Neither UndoRedo commit nor process exit alone meets that gate.
Editor and Play remain separate processes, with immutable Play input.

`studio/tests/godot/test_contract.py` checks meaningful rejection and copying
properties without a Godot process. It is not editor/UndoRedo/save/reopen,
native confinement, script parsing or GT-03 acceptance evidence.
