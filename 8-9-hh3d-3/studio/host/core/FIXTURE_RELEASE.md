# Immutable fixture release graph

This internal layer stages and reads a whole declared fixture release. It does
not select an active generation, grant write capabilities, import engine assets
or acknowledge a command. The selector must persist intent before staging and
own admission, dedupe, leases, source revisions and reconciliation.

Each fixture asset is JSON with exactly `value` and `references`. References
are sorted unique asset IDs. IDs are lowercase ASCII identifiers, not paths.
The entrypoint must reach every declared asset; every edge must resolve in the
same release. Cycles are allowed and traversal is bounded by the visited set.
This closed fixture grammar makes completeness testable. It says nothing about
dependencies hidden inside a `.blend`, GLB, Godot script or engine resource;
those need the later adapter/importer validators.

Up to 16 assets, 64 KiB per canonical asset and 1 MiB total are accepted. The
entire input grammar and graph are validated/copied before the first write.
The private store mints each blob; callers cannot choose a path or ACL. A
canonical manifest binds release ID, project, source revision/hash, base game
revision, store root/volume identity, entrypoint and the sorted asset list,
including every blob's file ID, size, hash and references. Volume IDs use
decimal strings so unsigned 64-bit NTFS values never exceed JSON safe integers.

Manifest and assets are checked through the existing protected, retained-root
store. Staging returns a descriptor only after writing the manifest and reading
back the entire release. If any stage fails after writes may have begun, partial
files remain, the store is poisoned and the outcome is uncertain. A later quota
or validation-shaped error cannot claim no effect. No automatic cleanup or
repeat staging occurs. Whole-release quota reservation and durable orphan
ownership belong to the pending selector integration, not this helper.

`pin_fixture_release` verifies the expected project, store/release binding,
canonical manifest, exact field schemas, unique/sorted IDs and blob descriptors,
then reads every blob and checks its actual graph against the manifest. It
returns an immutable tuple of canonical asset bytes. There is no lazy "latest"
lookup per file: creating another release cannot change an existing pin. A
missing, corrupt or substituted file rejects the whole pin; no partial snapshot
is returned. `release_value`/`parse_release` encode local descriptors for the
future private selector log; decoding alone is not authorization or readback.

`source_revision`, `source_sha256` and `game_revision` are trusted producer
metadata here; they are not proof the external source remains unchanged. The
selector must compare current authoritative revisions/lease at selection and
adoption. The field `game_revision` is the producer's base revision, not the new
selected generation. New generation and selection-record hash will be separate.

Tests use actual private files for complete graphs, old/new pins, malformed
input with no creation, cycles, project/root/release substitution, missing or
invented edges, duplicate/out-of-order entries, missing/corrupt blobs, partial
staging, final readback failure and fresh-process pinning. Instruction-shaped
asset text remains data; no interpreter or external process executes it.
