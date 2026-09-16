# Complete managed fixture bundle v2

AUTHORITY=0. This is an internal, pure content codec. It does not enable save,
script execution, publication, a journal transition, or a public ACK. The v1
codec and its two-file revision retain their original meaning.

`create_bundle(files, *, scene_revision, engine_sha256)` and
`decode_bundle(manifest_bytes, files)` return an immutable
`CompleteFixtureBundle`. Direct construction also validates. Input bytearrays
are bounded before copying; returned mappings and bytes are immutable copies.
All eleven paths below are required, with exact spelling and no extras:

| Path | Fixed role | Byte cap |
| --- | --- | ---: |
| `scenes/fixture.tscn` | `managed_scene` | 1 MiB |
| `scripts/fixture_actor.gd` | `managed_script` | 16 KiB |
| `scripts/fixture_actor.gd.uid` | `managed_uid` | 128 |
| `project.godot` | `trusted_config` | 16 KiB |
| `addons/hh_studio/plugin.cfg` | `trusted_addon` | 4 KiB |
| `addons/hh_studio/plugin.gd` | `trusted_addon` | 128 KiB |
| `addons/hh_studio/plugin.gd.uid` | `trusted_uid` | 128 |
| `addons/hh_studio/scene_commands.gd` | `trusted_addon` | 128 KiB |
| `addons/hh_studio/scene_commands.gd.uid` | `trusted_uid` | 128 |
| `addons/hh_studio/jcs_godot.gd` | `trusted_addon` | 128 KiB |
| `addons/hh_studio/jcs_godot.gd.uid` | `trusted_uid` | 128 |

Every file is nonempty valid UTF-8. UID sidecars have bounded ASCII spelling
`uid://[a-z0-9]+` followed by exactly one LF. That screening does not prove a
valid Godot-generated UID, resource resolution, scene/script agreement, source
syntax or dependency closure. No diagnostic addon, `.godot` cache, report or
extra imported file is implicitly admitted. Manifest cap is 16 KiB; aggregate
content plus manifest cap is 2 MiB. Per-file caps are checked first and are
currently stricter than the aggregate cap.

The canonical JCS manifest has exactly these fields:

* `schema`: `hh-godot-fixture-bundle-2`.
* `profile`: `hh-godot-managed-fixture-1`.
* `files`: the exact path map, each entry containing `sha256`, `size_bytes` and
  the fixed `role` from this codec.
* `trusted_source_revision`: `sha256:` plus SHA256 of JCS
  `{profile, files: <only trusted_config/trusted_addon/trusted_uid entries>}`.
* `caller_observations`: exactly `scene_revision` and `engine_sha256`.
* `project_revision`: `sha256:` plus SHA256 of JCS of all preceding fields.

The manifest is not one of its own content entries. Its separate staging hash
avoids recursive hashing. Decode rejects noncanonical JSON, malformed hashes,
unknown fields, wrong roles, size/hash mismatches and wrong revisions. A v1
bundle cannot be upgraded without supplying every missing source byte.

`scene_revision` is a supplied semantic scene observation; `project_revision`
binds this complete byte set and its observations. UID/config/addon changes
alter the latter even if semantic scene state is unchanged. Session identity,
selection generation and live native file CAS remain separate concepts.

`replace_script(bundle, new_script, *, expected_project_revision,
expected_script_sha256, expected_uid_sha256)` checks all three old values and
creates a new inert bundle. It preserves every other byte, including the UID,
scene, trusted release subset and supplied observations. This is a pure value
operation, not a transaction or CAS on a live project. It does not authorize
arbitrary script execution or show that the semantic observation remains true
after executing changed code.

The word `trusted` in a role identifies intended file ownership. The codec
accepts self-consistent declared bytes, including different addon/config bytes;
it cannot attest to an approved release. A separate trusted factory must pin
and compare actual release/profile bytes, actual retained UID source and the
approved engine before this data can enter an execution boundary. Synthetic
test UIDs are explicitly synthetic and are not release defaults.

For native staging, use the source-bound `bundle_staging.bundle_codec` object
to construct the exact bundle class that its owner accepts. Independently
loading this file under another module name produces a different Python class;
structural similarity does not bypass exact-type admission.
