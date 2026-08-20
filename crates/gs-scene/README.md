# gs-scene

Authoritative document + CommandDispatcher + WAL + undo + blueprint (I1).

This crate is the **only** mutator of the project model.

## Public API

| Type | Role |
|------|------|
| `Session::open` / `open_read_only` | Exclusive `editor.lock` (fs2) or read-only |
| `Session::dispatch` | I1 mutation entry (also `Session::dispatcher().execute`) |
| `Dispatcher::execute` | validate → WAL + fsync → apply → ACK (I2) |
| `Dispatcher::undo_last` | Undo newest txn (inverses as a new WAL txn) |
| `Dispatcher::revert_own` | Agent revert of own txn if no later entity conflict |
| `Session::canonical_scene_bytes` | MASTER 5.4b scene JSON |
| `Session::save` / `autosave` | tmp+rename project/scene; autosave + sidecar |
| `Session::inject_crash` | Fault points (a)(b)(c)(d) + fsync-fail |

`DispatchRequest` helpers: `spawn`, `transaction`, `set_transform`,
`reparent`, `as_dry_run`. `Command`: `entity_*`, `component_set`,
`blueprint_create`, `blueprint_instantiate`, `entity_duplicate`,
`script_create`, `script_set_source`, `script_ingest_external`,
`inputmap_set`, `tilemap_set_cells`, `tilemap_fill_rect`.

`Session::read_script_source` / `Document::read_script_source` implement
read-only `script.get_source` (not a WAL command). Mutating script file
commands persist via tmp+rename **after** WAL fsync (`persist_script_file`,
same hook as `blueprint.create`).

`Session::read_inputmap` / `Document::read_inputmap` implement read-only
`inputmap.get` (not a WAL command). Missing `inputmap.json` at the project
root returns the MASTER 6.4 sample. `inputmap.set` persists the same way
(`persist_inputmap_file`).

Every mutating request requires a ULID `command_id`. Retry returns the
previous `Ack` (I11). Dedup is rebuilt from **all** remaining WAL files
on open (GS-EC-57), LRU 100k / 24h.

## Canonical writer (5.4b)

Recursive UTF-8 key sort, entities sorted by **numeric** id after prefix,
`-0.0` → `0.0`, ryu shortest float, 2-space indent, LF, trailing newline.
Unknown fields (`x-unknown` internal maps) write back at every nesting
level (I5 / GS-EC-11).

## Component registry (5.2)

Name, Tags, Transform2D, Sprite, AnimFlipbook, Camera2D, RigidBody2D,
Collider2D, Tilemap, Text2D, AudioSource, Script, Visibility
(on `Entity` plus `Entity.extra: ExtraComponents`).
Unknown component types are kept, not dropped. `$entity` / `$asset`
tagged refs only — bare JSON strings are never ids.

## Blueprint (5.3)

`blueprint.create{from_entity,path}` writes `blueprints/*.gbp.json` with
local ids `b_1`, `b_2`, …. `blueprint.instantiate{path,at?,name_prefix?}`
stamps a **new** id tree (no back-link). WAL stores the stamped entities
so later edits to the `.gbp` do not change instances.

## WAL

Append-only `.gs/wal/wal.jsonl`, rotate to `<ts>.wal.jsonl` at 64MB,
keep 10 files. Truncated tail tolerated; corrupt middle → `Error::CorruptMiddle`.

## Crash / fail-stop

| Point | Meaning |
|-------|---------|
| `MidRecordWrite` | (a) partial JSONL line |
| `AfterFlushBeforeApply` | (b) flushed, not ACK'd |
| `MidAutosaveRename` | (c) tmp left, dest not replaced |
| `BetweenRecords` | (d) first ACK'd, second never written |
| `FsyncFail` | GS-EC-39 fail-stop; further mutating rejected |

## Gaps vs full WP-M0-3

- **entity.lock / redo:** not implemented (skipped this slice).
- **keep_world** edge cases remain minimal.
- **tilemap.set_cells / fill_rect:** patch cells through the dispatcher
  (I1/I2). `tile < 0` erases. Runs are re-encoded canonical RLE (sort by
  `(y, x)`, merge adjacent same-tile runs on a row). GS-EC-06 rejects
  `len <= 0`, `|x|`/`|y|` > 100_000, and more than 1_000_000 expanded
  cells (hint: split layers). Inline WAL patches >1MB are rejected.
- **WAL blob CAS** for payloads >1MB: not implemented.
- `gs-protocol` / `gs-registry` are declared; method handlers live here.
