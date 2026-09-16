# Inert fixture bundle codec

`bundle.py` validates and copies exactly two content blobs in memory:

| Relative path | Maximum UTF-8 bytes |
| --- | --- |
| `scenes/fixture.tscn` | 1,048,576 |
| `scripts/fixture_actor.gd` | 16,384 |

It performs no filesystem operation, Godot parse, import, execution, activation, journal write, safe replacement or publication. A valid bundle is not evidence that its contents are a valid scene or script. Runtime capability flags and the parser-sandbox gate are unaffected.

## API

```python
bundle = create_bundle(scene_bytes, script_bytes,
    scene_revision=observed_scene_revision,
    engine_sha256=observed_engine_digest)
copy = decode_bundle(bundle.manifest_bytes, bundle.files)
new_bundle = replace_script(bundle, new_script_bytes,
    expected_project_revision=bundle.project_revision,
    expected_script_sha256=bundle.script_sha256)
```

The frozen `FixtureBundle` contains `manifest_bytes`, `scene_bytes` and `script_bytes`. Bytearray inputs are copied to immutable bytes; other coercions and arbitrary buffer types are rejected. `files` returns a read-only mapping of the exact two paths to immutable bytes. Properties expose `project_revision`, `script_sha256`, `scene_revision` and `engine_sha256`. Direct `FixtureBundle` construction applies the same validation as decoding.

Replacement checks both the expected prior project revision and prior script hash before returning a new bundle. It preserves the scene bytes and caller observations. Changing the scene while retaining the same script still invalidates the old project precondition. Replacing with identical bytes produces the same deterministic bundle revision. This is an in-memory check, not cross-process CAS, a writer lease, command deduplication or authority to publish.

## Manifest and revision

The maximum manifest is 4,096 bytes. The wire form is the shared protocol's `canonical_bytes` JCS encoding, parsed with its strict `parse_json`. Decoding rejects noncanonical whitespace/key representation, duplicate fields, malformed UTF-8, unknown or missing fields, extra paths, incorrect schema, invalid digest syntax, mismatched content lengths/hashes and a mismatched project revision. Paths are matched exactly; no normalization, traversal resolution, URI conversion or filesystem lookup occurs.

The manifest has exactly these fields:

```json
{
  "schema": "hh-godot-fixture-bundle-1",
  "files": {
    "scenes/fixture.tscn": {"sha256": "<64 lowercase hex>", "size_bytes": 0},
    "scripts/fixture_actor.gd": {"sha256": "<64 lowercase hex>", "size_bytes": 0}
  },
  "caller_observations": {
    "scene_revision": "sha256:<64 lowercase hex>",
    "engine_sha256": "<64 lowercase hex>"
  },
  "project_revision": "sha256:<64 lowercase hex>"
}
```

This display is explanatory; an encoded manifest has canonical JCS layout and actual lengths/digests. Each file hash covers its exact raw UTF-8 bytes. Project revision is `sha256:` plus SHA-256 of the shared-JCS encoding of the complete manifest **excluding only `project_revision`**. It therefore covers both files, both lengths, schema and observations without circular hashing. Scene semantic revision is distinct from this bundle project revision.

`caller_observations.scene_revision` may bind an actual readback observation from the editor; `engine_sha256` may bind a verified pinned executable digest. This codec only checks syntax and incorporates the supplied values in the revision. It cannot prove that Godot produced the observation, that scene semantics match the serialized bytes, or that the executable was observed or launched. A self-consistent manifest can be created for arbitrary bytes by anyone.

Content is strict UTF-8 without normalization or implicit BOM/line-ending conversion. Empty blobs, NUL, BOM, arbitrary valid Unicode and syntactically invalid Godot text are permitted by this storage codec. The command contract and sandbox parser must apply their stricter text and semantic policies independently; preserving bytes here does not relax them. Caps are checked before decoding/copying and are byte counts, not character counts.

## Required external work

Before arbitrary `script_text.replace`, a trusted dispatcher must validate the semantic command and writer lease, establish the actual prior revision, checkpoint and parse/import the candidate in the proven disposable sandbox. The current codec supplies none of those steps. Candidate observation, parser success and script execution authority must stay distinct.

Scene and script become visible together only after a later journal-controlled immutable bundle publication and verified readback. Two separate file writes are not an atomic bundle commit. Recovery, revision fencing, high-water custody, rollback, clean engine logs and ACK-after-postcondition remain the publishing layer's responsibilities. No existing GT02 managed-fixture consumer has been expanded by this module.

`studio/tests/godot/test_bundle.py` verifies roundtrip identity, immutable ownership, raw-byte caps/Unicode, both replacement preconditions, revision binding, malformed manifests/paths and lack of I/O effects. The tests use inert bytes and do not constitute a Godot parser or sandbox test.
