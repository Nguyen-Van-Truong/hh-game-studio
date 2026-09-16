# S52 owned editor IPC focused result

AUTHORITY=0. Internal fixture evidence, not GT-03 acceptance or public authorization.

## Result

`20260917-gt03-s52-editor-owner-04/native/result.json` records **19/19** checks passed. The bounded host returned actual probe exit 0, wrapper exit 0, no timeout and verified process tree. Actual Godot PID 2744 exited 0; checked editor Job recorded active_count=0, zero_observed=true, tainted=false, closed=true. The pinned Windows GUI executable SHA256 is `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`, launched with `--headless --editor`: this is an actual EditorPlugin session, not headed GUI evidence.

`python -B studio/tests/godot/test_editor_owner.py`: **9/9** focused issuer/shape tests passed. The native run confirms edit, capture actual scene bytes, unchanged live capture state, exact 11-file adoption, full semantic parity, same editor with new root/generation, cleared history, stale/copy/single-use denial, Stop denial, source stability and clean close.

## Corrections retained in diagnostics

- `-02`: `Engine.get_version_info().string` is exactly `4.7.2-stable (official)`, not the console banner string. Host now compares this exact display value in addition to independent executable SHA256 pinning.
- `-03`: Godot JSON decodes numbers as floats. The IPC bridge validates and converts only fixed-schema integer generation/steps fields before forwarding to existing strict SceneCommands validation. Other values and schema checks remain unchanged.
- `-01` through `-03` remain diagnostic, not passing evidence.

## Stable integration API

`EditorOwner(parent, initial_bundle, editor_binary=...)` owns one new private project, process Job, PID creation-time binding and authenticated internal loopback IPC. `identity` returns session_id, pid, creation_filetime, root_identity, engine_sha256 and installed_source_sha256.

`inspect()` returns the full actual editor snapshot. `apply_projection(projection)` takes an already authorized/validated fixed semantic projection. `prepare_effect(command_id, digest, 'capture'|'adopt', expected_generation=..., expected_revision=..., deadline_ms=...)` returns the exact registered single-use `EditorEffectIntent`; scratch_name is generated and fixed. `capture(intent)` returns a registered receipt; `capture_bytes(receipt)` and `captured_semantic(receipt)` revalidate owned artifacts. `adopt(intent, bundle, selection)` changes only the scene file and returns a registered receipt after same-session reload/full readback. `observation(receipt, bundle)` rechecks adoption's actual current revision, generation, root instance and working-file map. `stop()` latches future effects; `close()` owns process cleanup. Any uncertain sent effect holds the owner and retains cleanup ownership.

## Limits

This module is an internal engine owner, not a user grant issuer, durable publication coordinator, public ACK, or atomic protected selector. Existing selected-state durability remains the responsibility of PublicationJournal/ProtectedBundleStore. Its working scene is a disposable managed mirror. Adoption intentionally resets local UndoRedo history; it does not promise artist project history continuity. Stop is serialized through the owner mutex/channel; already admitted synchronous main-thread effects may finish before Stop returns, so the root coordinator must define and test admission/revocation accounting explicitly. The focused evidence is not the combined authenticated publication flow. Run directories contain native generated caches for diagnostics; do not commit `.godot` or engine cache outputs.

Source SHA256 at native -04:

- editor_owner.py: `a7e93cea935c14cb21c64f55b3bde486c49d5d052af77b7fabc400d6e78b12a7`
- addons/hh_studio/plugin.gd: `951b30efdc494b25117553d5bd34629ff7b5c29c5267c8df268a40c624acb157`

Installed editor source digest: `af3e86c125379829ccf21f5ba4fdf54482bf1b1c06e12b3901c9eaaa801e98b4`.
