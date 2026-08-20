use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet};
use std::ptr::NonNull;
use std::rc::Rc;

use gs_scene::{AssetRef, Collider2D, ColliderShape, Script, Sprite, Tags, Transform2D};
use mlua::{Error as LuaError, Lua, Result as LuaResult, Table, Value};
use serde_json::Value as JsonValue;

use super::convert::{json_object_from_map, json_to_lua, lua_to_json};
use super::ids::{format_play_id, parse_play_id, runtime_id_from_seq, SPAWN_CAP_PER_FRAME};
use crate::physics::PhysicsHost;
use crate::world::{CameraShake, PlayEvent, SfxRequest, World, FIXED_DT};

const MAX_TAG_LEN: usize = 64;
const MAX_TAGS: usize = 32;
const FIND_BY_TAG_LIMIT: usize = 1000;
pub const LOG_RATE_PER_SCRIPT: u32 = 20;
pub const LOG_MSG_MAX_BYTES: usize = 2048;
pub const EMIT_MAX_BYTES: usize = 8 * 1024;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ScriptLog {
    pub entity_id: u64,
    pub level: String,
    pub message: String,
}

#[derive(Clone, Debug)]
enum PendingWrite {
    SetPos {
        id: u64,
        x: f32,
        y: f32,
    },
    SetTransform {
        id: u64,
        patch: TransformPatch,
    },
    SetCollider {
        id: u64,
        is_sensor: Option<bool>,
    },
    SetSprite {
        id: u64,
        asset_id: Option<String>,
        flip_x: Option<bool>,
        flip_y: Option<bool>,
    },
    AddTag {
        id: u64,
        tag: String,
    },
    RemoveTag {
        id: u64,
        tag: String,
    },
    Emit {
        name: String,
        data: JsonValue,
        entity_id: u64,
    },
    Spawn {
        id: u64,
        x: f32,
        y: f32,
    },
    Destroy {
        id: u64,
    },
    Velocity {
        id: u64,
        vx: f32,
        vy: f32,
    },
    Impulse {
        id: u64,
        ix: f32,
        iy: f32,
    },
    PlaySfx {
        asset_id: String,
        volume: f32,
        pan: f32,
    },
    CameraFollow {
        id: Option<u64>,
    },
    CameraShakeStart {
        amplitude: f32,
        seconds: f64,
    },
}

#[derive(Clone, Debug, Default)]
struct TransformPatch {
    x: Option<f32>,
    y: Option<f32>,
    rot: Option<f32>,
    sx: Option<f32>,
    sy: Option<f32>,
    z_index: Option<i32>,
}

#[derive(Clone, Debug)]
struct EntitySnap {
    transform: Transform2D,
    tags: Vec<String>,
    sprite: Option<Sprite>,
    collider: Option<Collider2D>,
    script: Option<Script>,
}

pub struct HostInner {
    exists: BTreeSet<u64>,
    snaps: BTreeMap<u64, EntitySnap>,
    buffer: Vec<PendingWrite>,
    dt: f64,
    frame: u64,
    seconds: f64,
    logs: Vec<ScriptLog>,
    log_count: u32,
    log_overflow: u32,
    current_id: u64,
    next_runtime_seq: u64,
    frame_spawn_count: u32,
    spawn_rejected: u32,
    warnings: Vec<String>,
    actions: BTreeMap<String, f32>,
    warned_missing_actions: BTreeSet<String>,
    physics: Option<NonNull<PhysicsHost>>,
}

impl HostInner {
    pub fn new() -> Self {
        Self {
            exists: BTreeSet::new(),
            snaps: BTreeMap::new(),
            buffer: Vec::new(),
            dt: FIXED_DT,
            frame: 0,
            seconds: 0.0,
            logs: Vec::new(),
            log_count: 0,
            log_overflow: 0,
            current_id: 0,
            next_runtime_seq: 0,
            frame_spawn_count: 0,
            spawn_rejected: 0,
            warnings: Vec::new(),
            actions: BTreeMap::new(),
            warned_missing_actions: BTreeSet::new(),
            physics: None,
        }
    }

    pub fn bind_physics(&mut self, physics: Option<&PhysicsHost>) {
        self.physics = physics.map(NonNull::from);
    }

    fn physics_host(&self) -> Option<&PhysicsHost> {
        self.physics.map(|p| {
            // SAFETY: `bind_physics` is only set from `ScriptVm::run_world_frame`
            // while that `&PhysicsHost` borrow is live. `Unbind` clears it
            // before the borrow ends.
            unsafe { p.as_ref() }
        })
    }

    pub fn discard(&mut self) {
        self.buffer.clear();
        self.spawn_rejected = 0;
    }

    pub fn reset_frame_spawns(&mut self) {
        self.frame_spawn_count = 0;
        self.spawn_rejected = 0;
    }

    pub fn take_logs(&mut self) -> (Vec<ScriptLog>, u32) {
        let logs = std::mem::take(&mut self.logs);
        let overflow = self.log_overflow;
        self.log_overflow = 0;
        (logs, overflow)
    }

    pub fn take_warnings(&mut self) -> Vec<String> {
        std::mem::take(&mut self.warnings)
    }
}

pub fn snapshot_world(world: &World, host: &mut HostInner) {
    host.exists.clear();
    host.snaps.clear();
    host.dt = FIXED_DT;
    host.frame = world.frame;
    host.seconds = world.frame as f64 * FIXED_DT;
    host.actions.clone_from(&world.input.actions);
    for (id, entity) in &world.entities {
        host.exists.insert(*id);
        host.snaps.insert(
            *id,
            EntitySnap {
                transform: entity
                    .transform
                    .clone()
                    .unwrap_or_else(Transform2D::identity),
                tags: entity
                    .tags
                    .as_ref()
                    .map(|t| t.values.clone())
                    .unwrap_or_default(),
                sprite: entity.extra.sprite.clone(),
                collider: entity.extra.collider.clone(),
                script: entity.extra.script.clone(),
            },
        );
    }
}

pub fn begin_callback(host: &mut HostInner, world: &World, entity_id: u64) {
    snapshot_world(world, host);
    host.current_id = entity_id;
    host.discard();
    host.logs.clear();
    host.log_count = 0;
    host.log_overflow = 0;
}

/// Apply the mutation buffer. Returns entity ids destroyed this commit.
pub fn commit_buffer(world: &mut World, host: &mut HostInner) -> Vec<u64> {
    let mut destroyed = Vec::new();
    for write in host.buffer.drain(..) {
        match write {
            PendingWrite::SetPos { id, x, y } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    let t = entity.transform.get_or_insert_with(Transform2D::identity);
                    t.x = x;
                    t.y = y;
                }
            }
            PendingWrite::SetTransform { id, patch } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    let t = entity.transform.get_or_insert_with(Transform2D::identity);
                    apply_transform_patch(t, &patch);
                }
            }
            PendingWrite::SetCollider { id, is_sensor } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    let collider = entity.extra.collider.get_or_insert_with(default_collider);
                    if let Some(sensor) = is_sensor {
                        collider.is_sensor = sensor;
                    }
                }
            }
            PendingWrite::SetSprite {
                id,
                asset_id,
                flip_x,
                flip_y,
            } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    apply_sprite_patch(&mut entity.extra.sprite, asset_id, flip_x, flip_y);
                }
            }
            PendingWrite::AddTag { id, tag } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    let tags = entity
                        .tags
                        .get_or_insert_with(|| Tags { values: Vec::new() });
                    if !tags.values.iter().any(|t| t == &tag) && tags.values.len() < MAX_TAGS {
                        tags.values.push(tag);
                    }
                }
            }
            PendingWrite::RemoveTag { id, tag } => {
                if let Some(entity) = world.entities.get_mut(&id) {
                    if let Some(tags) = entity.tags.as_mut() {
                        tags.values.retain(|t| t != &tag);
                    }
                }
            }
            PendingWrite::Emit {
                name,
                data,
                entity_id,
            } => {
                world.play_events.push(PlayEvent {
                    name,
                    entity_id: Some(entity_id),
                    data,
                });
            }
            PendingWrite::Spawn { id, x, y } => {
                if world.entities.contains_key(&id) {
                    continue;
                }
                let mut entity = gs_scene::Entity::new(id, None, 0);
                entity.transform = Some(Transform2D {
                    x,
                    y,
                    rot: 0.0,
                    sx: 1.0,
                    sy: 1.0,
                    z_index: 0,
                });
                world.entities.insert(id, entity);
            }
            PendingWrite::Destroy { id } => {
                world.entities.remove(&id);
                world.attached_scripts.remove(&id);
                world.script_bindings.remove(&id);
                destroyed.push(id);
            }
            PendingWrite::Velocity { id, vx, vy } => {
                if world.entities.contains_key(&id) {
                    world.pending_velocities.insert(id, (vx, vy));
                }
            }
            PendingWrite::Impulse { id, ix, iy } => {
                if world.entities.contains_key(&id) {
                    world.pending_impulses.insert(id, (ix, iy));
                }
            }
            PendingWrite::PlaySfx {
                asset_id,
                volume,
                pan,
            } => {
                world.sfx_queue.push(SfxRequest {
                    asset_id,
                    volume,
                    pan,
                    looping: false,
                });
            }
            PendingWrite::CameraFollow { id } => {
                world.camera_follow = id;
            }
            PendingWrite::CameraShakeStart { amplitude, seconds } => {
                world.camera_shake = Some(CameraShake {
                    amplitude,
                    remaining: seconds,
                    duration: seconds,
                });
            }
        }
    }
    destroyed
}

fn default_collider() -> Collider2D {
    Collider2D {
        shape: ColliderShape::Box { w: 1.0, h: 1.0 },
        is_sensor: false,
        offset: [0.0, 0.0],
        layer: 1,
        mask: u32::MAX,
        friction: 0.5,
        restitution: 0.0,
    }
}

fn apply_sprite_patch(
    slot: &mut Option<Sprite>,
    asset_id: Option<String>,
    flip_x: Option<bool>,
    flip_y: Option<bool>,
) {
    match slot {
        Some(sprite) => {
            if let Some(id) = asset_id {
                sprite.asset.id = id;
            }
            if let Some(fx) = flip_x {
                sprite.flip_x = fx;
            }
            if let Some(fy) = flip_y {
                sprite.flip_y = fy;
            }
        }
        None => {
            *slot = Some(Sprite {
                asset: AssetRef {
                    id: asset_id.unwrap_or_default(),
                },
                color: [1.0, 1.0, 1.0, 1.0],
                flip_x: flip_x.unwrap_or(false),
                flip_y: flip_y.unwrap_or(false),
                pivot: [0.5, 0.0],
            });
        }
    }
}

fn apply_sprite_to_snap(
    host: &mut HostInner,
    eid: u64,
    asset_id: Option<&str>,
    flip_x: Option<bool>,
    flip_y: Option<bool>,
) {
    if let Some(snap) = host.snaps.get_mut(&eid) {
        apply_sprite_patch(
            &mut snap.sprite,
            asset_id.map(str::to_string),
            flip_x,
            flip_y,
        );
    }
}

fn apply_transform_patch(t: &mut Transform2D, patch: &TransformPatch) {
    if let Some(x) = patch.x {
        t.x = x;
    }
    if let Some(y) = patch.y {
        t.y = y;
    }
    if let Some(rot) = patch.rot {
        t.rot = rot;
    }
    if let Some(sx) = patch.sx {
        t.sx = sx;
    }
    if let Some(sy) = patch.sy {
        t.sy = sy;
    }
    if let Some(z) = patch.z_index {
        t.z_index = z;
    }
}

fn apply_buffered_pos(host: &mut HostInner, id: u64, x: f32, y: f32) {
    if let Some(snap) = host.snaps.get_mut(&id) {
        snap.transform.x = x;
        snap.transform.y = y;
    }
}

pub fn install_gs(lua: &Lua, host: Rc<RefCell<HostInner>>) -> LuaResult<()> {
    let gs = lua.create_table()?;

    {
        let host = Rc::clone(&host);
        gs.set(
            "exists",
            lua.create_function(move |_, id: String| {
                let parsed = parse_play_id(&id);
                Ok(parsed.is_some_and(|n| host.borrow().exists.contains(&n)))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "get_pos",
            lua.create_function(move |lua, id: String| {
                let Some(eid) = parse_play_id(&id) else {
                    return empty_pos(lua);
                };
                let host = host.borrow();
                if !host.exists.contains(&eid) {
                    return empty_pos(lua);
                }
                match host.snaps.get(&eid) {
                    Some(snap) => pos_values(lua, snap.transform.x, snap.transform.y),
                    None => empty_pos(lua),
                }
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "get_transform",
            lua.create_function(move |lua, id: String| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(Value::Nil);
                };
                let host = host.borrow();
                if !host.exists.contains(&eid) {
                    return Ok(Value::Nil);
                }
                let Some(snap) = host.snaps.get(&eid) else {
                    return Ok(Value::Nil);
                };
                let t = lua.create_table()?;
                t.set("x", snap.transform.x)?;
                t.set("y", snap.transform.y)?;
                t.set("rot", snap.transform.rot)?;
                t.set("sx", snap.transform.sx)?;
                t.set("sy", snap.transform.sy)?;
                t.set("z_index", snap.transform.z_index)?;
                Ok(Value::Table(t))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "get_component",
            lua.create_function(move |lua, (id, ty): (String, String)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(Value::Nil);
                };
                let host = host.borrow();
                if !host.exists.contains(&eid) {
                    return Ok(Value::Nil);
                }
                let Some(snap) = host.snaps.get(&eid) else {
                    return Ok(Value::Nil);
                };
                component_table(lua, snap, &ty)
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "has_tag",
            lua.create_function(move |_, (id, tag): (String, String)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(false);
                };
                let host = host.borrow();
                if !host.exists.contains(&eid) {
                    return Ok(false);
                }
                Ok(host
                    .snaps
                    .get(&eid)
                    .is_some_and(|s| s.tags.iter().any(|t| t == &tag)))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "dt",
            lua.create_function(move |_, ()| Ok(host.borrow().dt))?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "time",
            lua.create_function(move |lua, ()| {
                let host = host.borrow();
                let t = lua.create_table()?;
                t.set("frame", host.frame)?;
                t.set("seconds", host.seconds)?;
                Ok(t)
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "action",
            lua.create_function(move |_, name: String| {
                Ok(read_action(&mut host.borrow_mut(), &name))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "log",
            lua.create_function(move |_, (level, msg): (String, String)| {
                let mut host = host.borrow_mut();
                if host.log_count >= LOG_RATE_PER_SCRIPT {
                    host.log_overflow = host.log_overflow.saturating_add(1);
                    return Ok(());
                }
                host.log_count = host.log_count.saturating_add(1);
                let entity_id = host.current_id;
                host.logs.push(ScriptLog {
                    entity_id,
                    level,
                    message: truncate_log(&msg),
                });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "set_pos",
            lua.create_function(move |_, (id, x, y): (String, f64, f64)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let mut host = host.borrow_mut();
                let x = x as f32;
                let y = y as f32;
                host.buffer.push(PendingWrite::SetPos { id: eid, x, y });
                apply_buffered_pos(&mut host, eid, x, y);
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "set_transform",
            lua.create_function(move |_, (id, patch): (String, Table)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let patch = read_transform_patch(&patch)?;
                let mut host = host.borrow_mut();
                apply_transform_to_snap(&mut host, eid, &patch);
                host.buffer
                    .push(PendingWrite::SetTransform { id: eid, patch });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "set_component",
            lua.create_function(move |_, (id, ty, patch): (String, String, Table)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let mut host = host.borrow_mut();
                match ty.as_str() {
                    "Collider2D" => {
                        let is_sensor = opt_bool(&patch, "is_sensor")?;
                        if let Some(snap) = host.snaps.get_mut(&eid) {
                            let collider = snap.collider.get_or_insert_with(default_collider);
                            if let Some(sensor) = is_sensor {
                                collider.is_sensor = sensor;
                            }
                        }
                        host.buffer
                            .push(PendingWrite::SetCollider { id: eid, is_sensor });
                    }
                    "Transform2D" => {
                        let tpatch = read_transform_patch(&patch)?;
                        apply_transform_to_snap(&mut host, eid, &tpatch);
                        host.buffer.push(PendingWrite::SetTransform {
                            id: eid,
                            patch: tpatch,
                        });
                    }
                    "Sprite" => {
                        let asset_id = match patch.get::<Value>("asset")? {
                            Value::Nil => None,
                            v => asset_id_from_value(&v),
                        };
                        let flip_x = opt_bool(&patch, "flip_x")?;
                        let flip_y = opt_bool(&patch, "flip_y")?;
                        if asset_id.is_none() && flip_x.is_none() && flip_y.is_none() {
                            return Ok(());
                        }
                        apply_sprite_to_snap(&mut host, eid, asset_id.as_deref(), flip_x, flip_y);
                        host.buffer.push(PendingWrite::SetSprite {
                            id: eid,
                            asset_id,
                            flip_x,
                            flip_y,
                        });
                    }
                    _ => {}
                }
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "set_sprite",
            lua.create_function(move |_, (id, asset_ref): (String, Value)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let Some(asset_id) = asset_id_from_value(&asset_ref) else {
                    return Ok(());
                };
                let mut host = host.borrow_mut();
                apply_sprite_to_snap(&mut host, eid, Some(asset_id.as_str()), None, None);
                host.buffer.push(PendingWrite::SetSprite {
                    id: eid,
                    asset_id: Some(asset_id),
                    flip_x: None,
                    flip_y: None,
                });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "set_flip",
            lua.create_function(
                move |_, (id, flip_x, flip_y): (String, bool, Option<bool>)| {
                    let Some(eid) = parse_play_id(&id) else {
                        return Ok(());
                    };
                    let mut host = host.borrow_mut();
                    apply_sprite_to_snap(&mut host, eid, None, Some(flip_x), flip_y);
                    host.buffer.push(PendingWrite::SetSprite {
                        id: eid,
                        asset_id: None,
                        flip_x: Some(flip_x),
                        flip_y,
                    });
                    Ok(())
                },
            )?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "add_tag",
            lua.create_function(move |_, (id, tag): (String, String)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                if tag.is_empty() || tag.len() > MAX_TAG_LEN {
                    return Ok(());
                }
                let mut host = host.borrow_mut();
                if let Some(snap) = host.snaps.get_mut(&eid) {
                    if !snap.tags.iter().any(|t| t == &tag) && snap.tags.len() < MAX_TAGS {
                        snap.tags.push(tag.clone());
                    }
                }
                host.buffer.push(PendingWrite::AddTag { id: eid, tag });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "remove_tag",
            lua.create_function(move |_, (id, tag): (String, String)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let mut host = host.borrow_mut();
                if let Some(snap) = host.snaps.get_mut(&eid) {
                    snap.tags.retain(|t| t != &tag);
                }
                host.buffer.push(PendingWrite::RemoveTag { id: eid, tag });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "emit",
            lua.create_function(move |_, (name, data): (String, Table)| {
                let json = lua_to_json(&Value::Table(data));
                let encoded = serde_json::to_vec(&json).unwrap_or_default();
                let mut host = host.borrow_mut();
                if encoded.len() > EMIT_MAX_BYTES {
                    host.warnings.push(format!(
                        "gs.emit {name} dropped: payload {} > {EMIT_MAX_BYTES} bytes",
                        encoded.len()
                    ));
                    return Ok(());
                }
                let entity_id = host.current_id;
                host.buffer.push(PendingWrite::Emit {
                    name,
                    data: json,
                    entity_id,
                });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "spawn",
            lua.create_function(move |lua, (_path, at): (String, Table)| {
                let x = opt_f32(&at, "x")?.unwrap_or(0.0);
                let y = opt_f32(&at, "y")?.unwrap_or(0.0);
                let mut host = host.borrow_mut();
                if host.frame_spawn_count >= SPAWN_CAP_PER_FRAME {
                    host.spawn_rejected = host.spawn_rejected.saturating_add(1);
                    host.warnings.push(format!(
                        "gs.spawn rejected: cap {SPAWN_CAP_PER_FRAME} per frame"
                    ));
                    return Ok(Value::Nil);
                }
                let next = host.next_runtime_seq.saturating_add(1);
                let Some(eid) = runtime_id_from_seq(next) else {
                    return Ok(Value::Nil);
                };
                host.next_runtime_seq = next;
                host.frame_spawn_count = host.frame_spawn_count.saturating_add(1);
                host.exists.insert(eid);
                host.snaps.insert(
                    eid,
                    EntitySnap {
                        transform: Transform2D {
                            x,
                            y,
                            rot: 0.0,
                            sx: 1.0,
                            sy: 1.0,
                            z_index: 0,
                        },
                        tags: Vec::new(),
                        sprite: None,
                        collider: None,
                        script: None,
                    },
                );
                host.buffer.push(PendingWrite::Spawn { id: eid, x, y });
                Ok(Value::String(lua.create_string(format_play_id(eid))?))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "destroy",
            lua.create_function(move |_, id: String| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let mut host = host.borrow_mut();
                host.exists.remove(&eid);
                host.snaps.remove(&eid);
                host.buffer.push(PendingWrite::Destroy { id: eid });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "velocity",
            lua.create_function(move |_, (id, vx, vy): (String, f64, f64)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let vx = vx as f32;
                let vy = vy as f32;
                if !vx.is_finite() || !vy.is_finite() {
                    return Ok(());
                }
                host.borrow_mut()
                    .buffer
                    .push(PendingWrite::Velocity { id: eid, vx, vy });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "impulse",
            lua.create_function(move |_, (id, ix, iy): (String, f64, f64)| {
                let Some(eid) = parse_play_id(&id) else {
                    return Ok(());
                };
                let ix = ix as f32;
                let iy = iy as f32;
                if !ix.is_finite() || !iy.is_finite() {
                    return Ok(());
                }
                host.borrow_mut()
                    .buffer
                    .push(PendingWrite::Impulse { id: eid, ix, iy });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "find_by_tag",
            lua.create_function(move |lua, (tag, limit): (String, Option<Value>)| {
                let cap = tag_search_limit(limit);
                let host = host.borrow();
                let mut ids = Vec::new();
                for (id, snap) in &host.snaps {
                    if snap.tags.iter().any(|t| t == &tag) {
                        ids.push(*id);
                    }
                    if ids.len() >= cap {
                        break;
                    }
                }
                ids_table(lua, &ids)
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "overlaps",
            lua.create_function(move |lua, id: String| {
                let Some(eid) = parse_play_id(&id) else {
                    return ids_table(lua, &[]);
                };
                let host = host.borrow();
                let Some(phys) = host.physics_host() else {
                    return ids_table(lua, &[]);
                };
                ids_table(lua, &phys.physics_overlaps(eid))
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "play_sfx",
            lua.create_function(move |_, (asset_ref, opts): (Value, Option<Value>)| {
                let Some(asset_id) = asset_id_from_value(&asset_ref) else {
                    return Ok(());
                };
                let (volume, pan) = read_sfx_opts(opts);
                host.borrow_mut().buffer.push(PendingWrite::PlaySfx {
                    asset_id,
                    volume,
                    pan,
                });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "camera_follow",
            lua.create_function(move |_, id: Value| {
                let follow = match id {
                    Value::Nil => None,
                    Value::String(s) => s.to_str().ok().and_then(|t| parse_play_id(t.as_ref())),
                    _ => return Ok(()),
                };
                host.borrow_mut()
                    .buffer
                    .push(PendingWrite::CameraFollow { id: follow });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "camera_shake",
            lua.create_function(move |_, (amplitude, seconds): (f64, f64)| {
                if !amplitude.is_finite() || !seconds.is_finite() || seconds <= 0.0 {
                    return Ok(());
                }
                host.borrow_mut()
                    .buffer
                    .push(PendingWrite::CameraShakeStart {
                        amplitude: amplitude as f32,
                        seconds,
                    });
                Ok(())
            })?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "raycast",
            lua.create_function(
                move |lua, (x1, y1, x2, y2, mask): (f64, f64, f64, f64, Option<Value>)| {
                    let host = host.borrow();
                    let Some(phys) = host.physics_host() else {
                        return Ok(Value::Nil);
                    };
                    let Some(hit) = phys.physics_raycast(
                        x1 as f32,
                        y1 as f32,
                        x2 as f32,
                        y2 as f32,
                        opt_u32(mask),
                    ) else {
                        return Ok(Value::Nil);
                    };
                    let hit_t = lua.create_table()?;
                    hit_t.set("id", format_play_id(hit.id))?;
                    hit_t.set("x", hit.x)?;
                    hit_t.set("y", hit.y)?;
                    hit_t.set("nx", hit.nx)?;
                    hit_t.set("ny", hit.ny)?;
                    let out = lua.create_table()?;
                    out.set("hit", hit_t)?;
                    Ok(Value::Table(out))
                },
            )?,
        )?;
    }

    {
        let host = Rc::clone(&host);
        gs.set(
            "get_velocity",
            lua.create_function(move |lua, id: String| {
                let Some(eid) = parse_play_id(&id) else {
                    return empty_pos(lua);
                };
                let host = host.borrow();
                if !host.exists.contains(&eid) {
                    return empty_pos(lua);
                }
                let Some(phys) = host.physics_host() else {
                    return empty_pos(lua);
                };
                match phys.linear_velocity(eid) {
                    Some((vx, vy)) => pos_values(lua, vx, vy),
                    None => empty_pos(lua),
                }
            })?,
        )?;
    }

    lua.globals().set("gs", gs)?;
    Ok(())
}

fn component_table(lua: &Lua, snap: &EntitySnap, ty: &str) -> LuaResult<Value> {
    match ty {
        "Transform2D" => {
            let t = lua.create_table()?;
            t.set("x", snap.transform.x)?;
            t.set("y", snap.transform.y)?;
            t.set("rot", snap.transform.rot)?;
            t.set("sx", snap.transform.sx)?;
            t.set("sy", snap.transform.sy)?;
            t.set("z_index", snap.transform.z_index)?;
            Ok(Value::Table(t))
        }
        "Sprite" => {
            let Some(sprite) = &snap.sprite else {
                return Ok(Value::Nil);
            };
            let t = lua.create_table()?;
            let asset = lua.create_table()?;
            asset.set("$asset", sprite.asset.id.as_str())?;
            asset.set("id", sprite.asset.id.as_str())?;
            t.set("asset", asset)?;
            t.set("color", vec4_table(lua, sprite.color)?)?;
            t.set("flip_x", sprite.flip_x)?;
            t.set("flip_y", sprite.flip_y)?;
            t.set("pivot", vec2_table(lua, sprite.pivot)?)?;
            Ok(Value::Table(t))
        }
        "Collider2D" => {
            let Some(c) = &snap.collider else {
                return Ok(Value::Nil);
            };
            let t = lua.create_table()?;
            t.set("shape", shape_table(lua, &c.shape)?)?;
            t.set("is_sensor", c.is_sensor)?;
            t.set("offset", vec2_table(lua, c.offset)?)?;
            t.set("layer", c.layer)?;
            t.set("mask", c.mask)?;
            t.set("friction", c.friction)?;
            t.set("restitution", c.restitution)?;
            Ok(Value::Table(t))
        }
        "Tags" => {
            let t = lua.create_table()?;
            let values = lua.create_table()?;
            for (i, tag) in snap.tags.iter().enumerate() {
                values.set(i + 1, tag.as_str())?;
            }
            t.set("values", values)?;
            Ok(Value::Table(t))
        }
        "Script" => {
            let Some(script) = &snap.script else {
                return Ok(Value::Nil);
            };
            let t = lua.create_table()?;
            t.set("file", script.file.as_str())?;
            t.set(
                "props",
                json_to_lua(lua, &json_object_from_map(&script.props))?,
            )?;
            Ok(Value::Table(t))
        }
        _ => Ok(Value::Nil),
    }
}

fn shape_table(lua: &Lua, shape: &ColliderShape) -> LuaResult<Table> {
    let t = lua.create_table()?;
    match shape {
        ColliderShape::Box { w, h } => {
            let b = lua.create_table()?;
            b.set("w", *w)?;
            b.set("h", *h)?;
            t.set("box", b)?;
        }
        ColliderShape::Circle { r } => {
            let c = lua.create_table()?;
            c.set("r", *r)?;
            t.set("circle", c)?;
        }
        ColliderShape::Capsule { half_h, r } => {
            let c = lua.create_table()?;
            c.set("half_h", *half_h)?;
            c.set("r", *r)?;
            t.set("capsule", c)?;
        }
    }
    Ok(t)
}

fn vec2_table(lua: &Lua, v: [f32; 2]) -> LuaResult<Table> {
    let t = lua.create_table()?;
    t.set(1, v[0])?;
    t.set(2, v[1])?;
    Ok(t)
}

fn vec4_table(lua: &Lua, v: [f32; 4]) -> LuaResult<Table> {
    let t = lua.create_table()?;
    t.set(1, v[0])?;
    t.set(2, v[1])?;
    t.set(3, v[2])?;
    t.set(4, v[3])?;
    Ok(t)
}

fn read_transform_patch(patch: &Table) -> LuaResult<TransformPatch> {
    Ok(TransformPatch {
        x: opt_f32(patch, "x")?,
        y: opt_f32(patch, "y")?,
        rot: opt_f32(patch, "rot")?,
        sx: opt_f32(patch, "sx")?,
        sy: opt_f32(patch, "sy")?,
        z_index: opt_i32(patch, "z_index")?,
    })
}

fn apply_transform_to_snap(host: &mut HostInner, eid: u64, patch: &TransformPatch) {
    if let (Some(x), Some(y)) = (patch.x, patch.y) {
        apply_buffered_pos(host, eid, x, y);
    } else if let Some(x) = patch.x {
        if let Some(snap) = host.snaps.get(&eid) {
            apply_buffered_pos(host, eid, x, snap.transform.y);
        }
    } else if let Some(y) = patch.y {
        if let Some(snap) = host.snaps.get(&eid) {
            apply_buffered_pos(host, eid, snap.transform.x, y);
        }
    }
    if let Some(snap) = host.snaps.get_mut(&eid) {
        apply_transform_patch(&mut snap.transform, patch);
    }
}

fn read_sfx_opts(opts: Option<Value>) -> (f32, f32) {
    let mut volume = 1.0;
    let mut pan = 0.0;
    if let Some(Value::Table(table)) = opts {
        if let Some(v) = opt_f32(&table, "volume").ok().flatten() {
            if v.is_finite() {
                volume = v.clamp(0.0, 2.0);
            }
        }
        if let Some(p) = opt_f32(&table, "pan").ok().flatten() {
            if p.is_finite() {
                pan = p.clamp(-1.0, 1.0);
            }
        }
    }
    (volume, pan)
}

fn asset_id_from_value(value: &Value) -> Option<String> {
    match value {
        Value::String(s) => s.to_str().ok().map(|t| t.to_string()),
        Value::Table(table) => {
            if let Ok(Value::String(s)) = table.get::<Value>("$asset") {
                if let Ok(text) = s.to_str() {
                    return Some(text.to_string());
                }
            }
            if let Ok(Value::String(s)) = table.get::<Value>("id") {
                if let Ok(text) = s.to_str() {
                    return Some(text.to_string());
                }
            }
            None
        }
        _ => None,
    }
}

fn read_action(host: &mut HostInner, name: &str) -> f64 {
    match host.actions.get(name) {
        Some(value) => f64::from(clamp_action(*value)),
        None => {
            if host.warned_missing_actions.insert(name.to_string()) {
                host.warnings
                    .push(format!("gs.action: unknown action {name}"));
            }
            0.0
        }
    }
}

fn clamp_action(value: f32) -> f32 {
    if !value.is_finite() {
        return 0.0;
    }
    value.clamp(-1.0, 1.0)
}

fn pos_values(_lua: &Lua, x: f32, y: f32) -> LuaResult<(Value, Value)> {
    Ok((Value::Number(f64::from(x)), Value::Number(f64::from(y))))
}

fn empty_pos(_lua: &Lua) -> LuaResult<(Value, Value)> {
    Ok((Value::Nil, Value::Nil))
}

fn ids_table(lua: &Lua, ids: &[u64]) -> LuaResult<Value> {
    let t = lua.create_table()?;
    let arr = lua.create_table()?;
    for (i, id) in ids.iter().enumerate() {
        arr.set(i + 1, format_play_id(*id))?;
    }
    t.set("ids", arr)?;
    Ok(Value::Table(t))
}

fn tag_search_limit(limit: Option<Value>) -> usize {
    match limit {
        None | Some(Value::Nil) => FIND_BY_TAG_LIMIT,
        Some(Value::Integer(n)) if n <= 0 => 0,
        Some(Value::Integer(n)) => (n as usize).min(FIND_BY_TAG_LIMIT),
        Some(Value::Number(n)) if n.is_finite() && n <= 0.0 => 0,
        Some(Value::Number(n)) if n.is_finite() => (n as usize).min(FIND_BY_TAG_LIMIT),
        _ => FIND_BY_TAG_LIMIT,
    }
}

fn opt_u32(value: Option<Value>) -> Option<u32> {
    match value {
        None | Some(Value::Nil) => None,
        Some(Value::Integer(n)) if n >= 0 => u32::try_from(n).ok(),
        Some(Value::Number(n)) if n.is_finite() && n >= 0.0 => Some(n as u32),
        _ => None,
    }
}

pub fn truncate_log(msg: &str) -> String {
    if msg.len() <= LOG_MSG_MAX_BYTES {
        return msg.to_string();
    }
    let mut end = LOG_MSG_MAX_BYTES;
    while end > 0 && !msg.is_char_boundary(end) {
        end -= 1;
    }
    msg[..end].to_string()
}

fn opt_f32(table: &Table, key: &str) -> LuaResult<Option<f32>> {
    match table.get::<Value>(key)? {
        Value::Nil => Ok(None),
        Value::Number(n) => Ok(Some(n as f32)),
        Value::Integer(n) => Ok(Some(n as f32)),
        other => Err(LuaError::FromLuaConversionError {
            from: other.type_name(),
            to: "number".into(),
            message: Some(format!("{key} must be a number")),
        }),
    }
}

fn opt_i32(table: &Table, key: &str) -> LuaResult<Option<i32>> {
    match table.get::<Value>(key)? {
        Value::Nil => Ok(None),
        Value::Integer(n) => {
            i32::try_from(n)
                .map(Some)
                .map_err(|_| LuaError::FromLuaConversionError {
                    from: "integer",
                    to: "i32".into(),
                    message: Some(format!("{key} out of range")),
                })
        }
        Value::Number(n) => Ok(Some(n as i32)),
        other => Err(LuaError::FromLuaConversionError {
            from: other.type_name(),
            to: "integer".into(),
            message: Some(format!("{key} must be an integer")),
        }),
    }
}

fn opt_bool(table: &Table, key: &str) -> LuaResult<Option<bool>> {
    match table.get::<Value>(key)? {
        Value::Nil => Ok(None),
        Value::Boolean(b) => Ok(Some(b)),
        other => Err(LuaError::FromLuaConversionError {
            from: other.type_name(),
            to: "boolean".into(),
            message: Some(format!("{key} must be a boolean")),
        }),
    }
}
