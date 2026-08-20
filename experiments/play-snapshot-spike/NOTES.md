# Play-snapshot spike (WP-M-1-d)

Spike only. Not production. Layout and hash rules match MASTER 2.4 / 6.1 / I3.

Player stub does **not** load or execute `.luau` (I3). It only verifies hashes.

## Layout

Builder writes:

```
<out_root>/play/<play_id>/
  manifest.json
  scene.json
  project-settings.json
  input-map.json
  scripts/*.luau          # copies of source at this revision
  asset-manifest.json     # asset_id -> {path, hash}; binaries are NOT copied
```

Player stub:

```
gs-player-stub --snapshot <path-to-manifest.json>
```

- Success: prints `OK <play_id> <document_revision>` and exits 0.
- Any missing file, non-canonical JSON, or hash mismatch: prints `REJECT ...` on stderr and exits non-zero.

## `manifest.json` schema

Exact fields (MASTER 2.4). Extra field `play_id` is required by this spike so the stub can print identity without guessing from the directory name.

```json
{
  "actor": "act_spike",
  "created_at": "2026-08-16T00:00:00Z",
  "document_revision": "r-000001",
  "engine_ver": "0.0.0-m-1-d",
  "hashes": {
    "assets": "<sha256 hex>",
    "inputmap": "<sha256 hex>",
    "scene": "<sha256 hex>",
    "scripts": "<sha256 hex>"
  },
  "play_id": "p-000001",
  "protocol_ver": "1.0",
  "seed": 42
}
```

| Field | Type | Meaning |
|---|---|---|
| `play_id` | string | Play id (`p-` + digits). Directory name matches. |
| `document_revision` | string | Frozen document revision (`r-` + digits). |
| `engine_ver` | string | Engine / spike version that built the snapshot. |
| `protocol_ver` | string | Protocol version (spike uses `"1.0"`). |
| `seed` | u64 | Play RNG seed. |
| `hashes.scene` | string | SHA-256 hex of `scene.json` canonical bytes. |
| `hashes.scripts` | string | SHA-256 hex of the scripts listing (below). |
| `hashes.assets` | string | SHA-256 hex of `asset-manifest.json` canonical bytes. |
| `hashes.inputmap` | string | SHA-256 hex of `input-map.json` canonical bytes. |
| `created_at` | string | RFC3339 UTC timestamp. |
| `actor` | string | Actor that requested play. |

`project-settings.json` is written into the snapshot (MASTER 2.4) but is **not** one of the four manifest hashes.

## Canonical bytes

JSON files are written and hashed as **canonical bytes** (MASTER 5.4b, spike subset):

1. Parse to a JSON value.
2. Recursively sort every object’s keys **bytewise UTF-8**.
3. Normalize `-0.0` to `0.0` before write.
4. Pretty-print with 2-space indent, LF only, UTF-8 no BOM.
5. Exactly one trailing newline.

`hash = SHA-256(canonical_bytes)` encoded as lowercase hex (64 chars).

The verifier re-canonicalizes `scene.json`, `input-map.json`, and `asset-manifest.json` and **rejects** if on-disk bytes ≠ canonical form. A 1-byte edit (including whitespace) therefore fails even if the JSON still parses.

## How each hash is computed

### `hashes.scene`

`SHA-256(canonical_bytes(scene.json))`

### `hashes.inputmap`

`SHA-256(canonical_bytes(input-map.json))`

### `hashes.assets`

`SHA-256(canonical_bytes(asset-manifest.json))`

`asset-manifest.json` is an object:

```json
{
  "a_000007": {
    "hash": "<sha256 hex of asset content, or of the path UTF-8 if no content was supplied>",
    "path": "assets/door.png"
  }
}
```

Large binaries stay in the original store (`path`). They are not copied into the snapshot. If `path` exists as a file at verify time, the stub also checks that file’s SHA-256 against the record.

### `hashes.scripts`

Not a file hash. Builder/verifier build a canonical JSON object of every `*.luau` under `scripts/`, keys = path relative to the play directory using `/`:

```json
{
  "scripts/door.luau": "<sha256 hex of raw file bytes>"
}
```

Then `hashes.scripts = SHA-256(canonical_bytes(that object))`. Empty `scripts/` → hash of canonical `{}`.

## Writes

Snapshot files are written `tmp + rename` (I6).

## Tests

From this crate directory:

```
cargo test
```

1. Build demo snapshot → stub prints `OK p-000001 r-000001`.
2. Flip one byte in `scene.json` without updating the manifest → stub exits non-zero with `REJECT`.
