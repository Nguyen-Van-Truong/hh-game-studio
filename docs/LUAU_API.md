# Luau host API (gs-runtime-core, WP-M3-2)

Play scripts compile from **source text only** (I4). The editor must not
depend on this host (I3). This page documents functions that exist in the
runtime today — not the full MASTER 7.2 wishlist.

## Lifecycle (MASTER 7.1)

A play script is a module that `return`s a table:

```
{ on_init(self), on_update(self, dt), on_event(self, name, data), on_destroy(self) }
```

Missing callbacks are no-ops.

`self = { id, props, state }`

- `id` — string. Document entities: `e_000042`. Runtime-spawned: `rt_1`, `rt_2`, …
- `props` — copy of `Script.props` (JSON → Luau table). Tagged refs stay tables
  (`{["$asset"]="a_000008"}`).
- `state` — table that persists on the long-lived `ScriptHost` instance
  (survives frames and `host.reload`; 7.4).

Call order per instance:

1. First time or after reload: `on_init(self)` with a **100ms** budget, once.
2. Each frame in `script_on_update`: `on_update(self, dt)` with the 2/4ms
   per-script and 6/12ms global scheduler from M3-1.
3. Queued events: `on_event(self, name, data)` (same per-script budget).
4. Destroy / disable / reload-out: `on_destroy(self)` then the instance stops
   (reload keeps `self.state`).

Sources that do **not** return a table still run as an implicit `on_update`
body (M3-1 `attach_script` tests).

`on_init` / lifecycle / `self.state` require a **long-lived** [`ScriptHost`]
owned by the caller. `step(&mut World, &InputFrame)` without a host creates
an ephemeral VM when scripts are attached (state does not persist).

## IDs

| Kind | Public string | Internal u64 |
| --- | --- | --- |
| Document | `e_000001` | `1` (scene id) |
| Runtime spawn | `rt_1`, `rt_2`, … | `RUNTIME_ID_BASE + N` (`1<<40`) |

`gs.*` id arguments accept both `e_000001` and `rt_1`. Dead ids: reads return
`nil` / `false` and **do not error** (GS-EC-25).

## Mutation buffer

Mutating `gs.*` writes a per-callback buffer. The buffer commits only if the
callback returns OK and the deadline flag is clear. Error or deadline →
discard the whole buffer (no half-applied door). Reads see this callback's
buffer (read-your-writes).

## Disable (MASTER 7.3 / T3.2)

The **script instance** is disabled (entity stays) after:

- 3 consecutive hard-deadline failures, or
- 10 runtime errors in a rolling 10 seconds (`World.script_now_ms` is the
  test clock).

On disable: best-effort `on_destroy`, stop running, record play event
`script_disabled` with `{file, line?, stack?}`. `ScriptHost::reload(id)`
re-enables, keeps `self.state`, runs `on_init` again.

## Diagnostics

Lua errors fill `ScriptFailure.{file,line,stack}` from the chunk name
(`update:e_000042`) and mlua traceback when present. Missing line is `None`,
never a panic.

## Implemented `gs.*`

### Reads

| Function | Returns |
| --- | --- |
| `gs.exists(id)` | `bool` |
| `gs.get_pos(id)` | `x, y` or `nil, nil` |
| `gs.get_transform(id)` | `{x,y,rot,sx,sy,z_index}` or `nil` |
| `gs.get_component(id, type)` | table copy or `nil`. Types: `Transform2D`, `Sprite`, `Collider2D`, `Tags`, `Script` |
| `gs.has_tag(id, tag)` | `bool` (dead id → `false`) |
| `gs.dt()` | fixed dt (`1/60`) |
| `gs.time()` | `{frame, seconds}` |
| `gs.action(name)` | this frame's `InputFrame`: button `0`/`1`, axis `-1..1` (clamped). Missing name → `0` + one warning per name (not an error). |
| `gs.find_by_tag(tag, limit<=1000)` | `{ids}` play-string ids, sorted ascending. `limit` defaults to 1000 and is capped at 1000. |
| `gs.overlaps(id)` | `{ids}` last-frame contacts/sensors, sorted. Dead id or no `PhysicsHost` → `{ids={}}`. |
| `gs.raycast(x1,y1,x2,y2, mask?)` | `{hit:{id,x,y,nx,ny}}` or `nil`. `id` is a play string (`e_000001` / `rt_1`). Reads the previous integrated `PhysicsHost` (physics runs after scripts). No host → `nil`. |
| `gs.get_velocity(id)` | `vx, vy` or `nil, nil`. Last-frame linear velocity from the bound `PhysicsHost` (same borrow as `gs.raycast`). Dead id, no host, or no body → `nil, nil`, never an error. |

### Mutating (buffered)

| Function | Notes |
| --- | --- |
| `gs.set_pos(id, x, y)` | |
| `gs.set_transform(id, patch)` | optional `x,y,rot,sx,sy,z_index` |
| `gs.set_component(id, type, patch)` | `Collider2D` `{is_sensor=true}`; also `Transform2D`; `Sprite` accepts `asset`, `flip_x`, `flip_y` |
| `gs.set_flip(id, flip_x, flip_y?)` | buffered; writes `Sprite.flip_x` / `flip_y`. `flip_y` optional (omit or `nil` → leave `flip_y` unchanged). Dead id: no error. |
| `gs.set_sprite(id, asset_ref)` | `asset_ref` is `{["$asset"]=...}` or `{id=...}` |
| `gs.add_tag(id, tag)` / `gs.remove_tag(id, tag)` | |
| `gs.emit(name, data_table)` | after commit → `World.play_events` (≤8KB) |
| `gs.spawn(blueprint_path, {x,y})` | play-only entity, returns `rt_N` in commit order; cap **1000/frame** (excess → `nil` + warning). Minimal spawn: empty entity at `x,y`. Does not allocate `e_*`. |
| `gs.velocity(id, vx, vy)` | buffer; applied as linvel on dynamic/kinematic at `PhysicsHost::integrate`, then cleared. Dead id: no error. |
| `gs.impulse(id, ix, iy)` | buffer; applied as impulse at integrate, then cleared. Dead id: no error. |
| `gs.destroy(id)` | remove entity; later reads are nil/false |
| `gs.log(level, msg)` | ≤2KB, 20 lines/callback |
| `gs.play_sfx(asset_ref, {volume?,pan?})` | one-shot; queues `SfxRequest` (player plays via kira). `volume` 0..2 default 1; `pan` -1..1 default 0. Missing file is a warning, not an error. Looping audio uses the `AudioSource` component (`autoplay` / `loop`). No spatial audio. |
| `gs.camera_follow(id or nil)` | follow entity copies x,y onto the active camera transform after physics. `nil` clears follow. Dead id: no error. |
| `gs.camera_shake(amplitude, seconds)` | decaying offset on the render camera; time uses fixed dt (`1/60`). |

## Collision mock

`World::queue_collision_enter(target, other, is_sensor)` (and `_exit`)
enqueues `on_event` with `{other, is_sensor}`. Used to test `door.luau`
before rapier (M4).
