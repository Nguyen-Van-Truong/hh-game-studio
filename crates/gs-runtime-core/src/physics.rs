//! Rapier2D play physics (WP-M4-1 / MASTER 6.2, T4.1).
//!
//! [`PhysicsHost`] is caller-owned, like [`crate::ScriptHost`]. It is **not**
//! stored on [`crate::World`]: `World` is `Clone` and the player copies it,
//! while a Rapier `RigidBodySet` should not be cloned every frame.
//!
//! After scripts commit, `Transform2D` is synced into Rapier (entity id
//! ascending). After `pipeline.step`, translation/rotation are written
//! **directly** onto `World` entity transforms (not a mutation buffer).
//! Collision enter/exit pairs are then queued with
//! [`World::queue_collision_enter`] / [`World::queue_collision_exit`].
//!
//! Scripts read last-frame bodies via [`PhysicsHost::physics_raycast`] /
//! [`PhysicsHost::physics_overlaps`] (`&PhysicsHost` is passed into
//! `script_on_update`). `gs.velocity` / `gs.impulse` land on
//! [`World::pending_velocities`] / [`World::pending_impulses`] and are
//! applied here before `pipeline.step`, then cleared.
//!
//! Solid tilemap layers are baked in [`PhysicsHost::integrate`]: one static
//! box per valid RLE run, parented to the tilemap entity (Rapier allows
//! multiple colliders). Rebuild uses a cheap fingerprint of transform +
//! tilemap. Bake order walks entity ids in `BTreeMap` order.

use std::collections::{BTreeMap, BTreeSet};

use gs_render2d::RenderSnapshot;
use gs_scene::{Collider2D, ColliderShape, Entity, Transform2D};
use rapier2d::prelude::{
    ActiveCollisionTypes, CCDSolver, ColliderBuilder, ColliderHandle, ColliderSet,
    DefaultBroadPhase, Group, ImpulseJointSet, IntegrationParameters, InteractionGroups,
    IslandManager, Isometry, MultibodyJointSet, NarrowPhase, PhysicsPipeline, Point, QueryFilter,
    QueryPipeline, Ray, RigidBodyBuilder, RigidBodyHandle, RigidBodySet, Vector,
};

use crate::error::Error;
use crate::script::format_play_id;
use crate::tilemap::{
    tilemap_bake_fingerprint, tilemap_bake_runs, tilemap_has_solid_bake, TilemapBakeRun,
};
use crate::world::{InputFrame, World, FIXED_DT};

const GRAVITY_Y: f32 = -9.81;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum BodyKind {
    Dynamic,
    Static,
    Kinematic,
}

impl BodyKind {
    fn parse(kind: &str) -> Self {
        match kind {
            "dynamic" => Self::Dynamic,
            "kinematic" => Self::Kinematic,
            _ => Self::Static,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
struct Pose {
    x: f32,
    y: f32,
    rot: f32,
}

#[derive(Clone, Debug, PartialEq)]
struct ColliderKey {
    shape: ColliderShape,
    is_sensor: bool,
    offset: [f32; 2],
    layer: u32,
    mask: u32,
    friction: f32,
    restitution: f32,
}

impl ColliderKey {
    fn from_component(c: &Collider2D) -> Self {
        Self {
            shape: c.shape.clone(),
            is_sensor: c.is_sensor,
            offset: c.offset,
            layer: c.layer,
            mask: c.mask,
            friction: c.friction,
            restitution: c.restitution,
        }
    }
}

struct BodyEntry {
    body: RigidBodyHandle,
    collider: Option<ColliderHandle>,
    kind: BodyKind,
    collider_key: Option<ColliderKey>,
    last_written: Pose,
    baked_colliders: Vec<ColliderHandle>,
    bake_fp: Option<u64>,
}

/// Last-frame query hit (`gs.raycast` shape, numeric id).
#[derive(Clone, Debug, PartialEq)]
pub struct RaycastHit {
    pub id: u64,
    pub x: f32,
    pub y: f32,
    pub nx: f32,
    pub ny: f32,
}

/// Long-lived Rapier world. The caller owns this (not [`World`]).
pub struct PhysicsHost {
    pipeline: PhysicsPipeline,
    gravity: Vector<f32>,
    integration: IntegrationParameters,
    islands: IslandManager,
    broad_phase: DefaultBroadPhase,
    narrow_phase: NarrowPhase,
    bodies: RigidBodySet,
    colliders: ColliderSet,
    impulse_joints: ImpulseJointSet,
    multibody_joints: MultibodyJointSet,
    ccd_solver: CCDSolver,
    query_pipeline: QueryPipeline,
    entries: BTreeMap<u64, BodyEntry>,
    last_valid: BTreeMap<u64, Pose>,
    active_pairs: BTreeSet<(u64, u64, bool)>,
}

impl Default for PhysicsHost {
    fn default() -> Self {
        Self::new()
    }
}

impl PhysicsHost {
    pub fn new() -> Self {
        Self {
            pipeline: PhysicsPipeline::new(),
            gravity: Vector::new(0.0, GRAVITY_Y),
            integration: IntegrationParameters {
                dt: FIXED_DT as f32,
                ..Default::default()
            },
            islands: IslandManager::new(),
            broad_phase: DefaultBroadPhase::new(),
            narrow_phase: NarrowPhase::new(),
            bodies: RigidBodySet::new(),
            colliders: ColliderSet::new(),
            impulse_joints: ImpulseJointSet::new(),
            multibody_joints: MultibodyJointSet::new(),
            ccd_solver: CCDSolver::new(),
            query_pipeline: QueryPipeline::new(),
            entries: BTreeMap::new(),
            last_valid: BTreeMap::new(),
            active_pairs: BTreeSet::new(),
        }
    }

    /// Same 6.2 schedule as [`crate::step`], keeping this Rapier world.
    pub fn step(&mut self, world: &mut World, input: &InputFrame) -> Result<RenderSnapshot, Error> {
        crate::schedule::step_with_physics(world, input, self)
    }

    /// Sync transforms, step Rapier, write poses back onto `World` (direct).
    pub fn integrate(&mut self, world: &mut World) {
        let snaps = collect_snaps(world);
        self.remove_stale(&snaps);
        self.insert_and_sync(&snaps, world);
        self.bake_tilemap_colliders(world);
        self.apply_pending(world);
        self.pipeline.step(
            &self.gravity,
            &self.integration,
            &mut self.islands,
            &mut self.broad_phase,
            &mut self.narrow_phase,
            &mut self.bodies,
            &mut self.colliders,
            &mut self.impulse_joints,
            &mut self.multibody_joints,
            &mut self.ccd_solver,
            Some(&mut self.query_pipeline),
            &(),
            &(),
        );
        self.write_transforms(world);
    }

    /// Diff contact/sensor pairs and queue enter/exit in sorted pair order.
    pub fn queue_collision_events(&mut self, world: &mut World) {
        let current = self.collect_pairs();
        let exits: Vec<(u64, u64, bool)> =
            self.active_pairs.difference(&current).copied().collect();
        let enters: Vec<(u64, u64, bool)> =
            current.difference(&self.active_pairs).copied().collect();
        for (a, b, sensor) in exits {
            world.queue_collision_exit(a, b, sensor);
            world.queue_collision_exit(b, a, sensor);
        }
        for (a, b, sensor) in enters {
            world.queue_collision_enter(a, b, sensor);
            world.queue_collision_enter(b, a, sensor);
        }
        self.active_pairs = current;
    }

    /// Closest hit along the segment, or `None`. `mask` filters collider layers.
    pub fn physics_raycast(
        &self,
        x1: f32,
        y1: f32,
        x2: f32,
        y2: f32,
        mask: Option<u32>,
    ) -> Option<RaycastHit> {
        let dx = x2 - x1;
        let dy = y2 - y1;
        if !dx.is_finite() || !dy.is_finite() || (dx == 0.0 && dy == 0.0) {
            return None;
        }
        let groups = InteractionGroups::new(
            Group::all(),
            Group::from_bits_retain(mask.unwrap_or(u32::MAX)),
        );
        let filter = QueryFilter::new().groups(groups);
        let ray = Ray::new(Point::new(x1, y1), Vector::new(dx, dy));
        let (handle, hit) = self.query_pipeline.cast_ray_and_get_normal(
            &self.bodies,
            &self.colliders,
            &ray,
            1.0,
            true,
            filter,
        )?;
        let collider = self.colliders.get(handle)?;
        let id = entity_id_from_user(collider.user_data)?;
        Some(RaycastHit {
            id,
            x: x1 + dx * hit.time_of_impact,
            y: y1 + dy * hit.time_of_impact,
            nx: hit.normal.x,
            ny: hit.normal.y,
        })
    }

    /// Last-frame linear velocity, or `None` if the body is not in this host.
    pub fn linear_velocity(&self, id: u64) -> Option<(f32, f32)> {
        let entry = self.entries.get(&id)?;
        let body = self.bodies.get(entry.body)?;
        let v = body.linvel();
        Some((v.x, v.y))
    }

    /// Entity ids currently overlapping `id` (contact or sensor), sorted.
    pub fn physics_overlaps(&self, id: u64) -> Vec<u64> {
        let mut ids = BTreeSet::new();
        for &(a, b, _) in &self.active_pairs {
            if a == id {
                ids.insert(b);
            } else if b == id {
                ids.insert(a);
            }
        }
        ids.into_iter().collect()
    }

    /// Test / CCD helper. No-op if the body is not in this host yet.
    pub fn set_linear_velocity(&mut self, entity_id: u64, vx: f32, vy: f32) {
        if !vx.is_finite() || !vy.is_finite() {
            return;
        }
        let Some(entry) = self.entries.get(&entity_id) else {
            return;
        };
        if let Some(body) = self.bodies.get_mut(entry.body) {
            body.set_linvel(Vector::new(vx, vy), true);
        }
    }

    fn apply_pending(&mut self, world: &mut World) {
        let velocities = std::mem::take(&mut world.pending_velocities);
        let impulses = std::mem::take(&mut world.pending_impulses);
        for (id, (vx, vy)) in velocities {
            self.apply_linvel(id, vx, vy);
        }
        for (id, (ix, iy)) in impulses {
            self.apply_impulse(id, ix, iy);
        }
    }

    fn apply_linvel(&mut self, entity_id: u64, vx: f32, vy: f32) {
        if !vx.is_finite() || !vy.is_finite() {
            return;
        }
        let Some(entry) = self.entries.get(&entity_id) else {
            return;
        };
        if !matches!(entry.kind, BodyKind::Dynamic | BodyKind::Kinematic) {
            return;
        }
        if let Some(body) = self.bodies.get_mut(entry.body) {
            body.set_linvel(Vector::new(vx, vy), true);
        }
    }

    fn apply_impulse(&mut self, entity_id: u64, ix: f32, iy: f32) {
        if !ix.is_finite() || !iy.is_finite() {
            return;
        }
        let Some(entry) = self.entries.get(&entity_id) else {
            return;
        };
        if let Some(body) = self.bodies.get_mut(entry.body) {
            body.apply_impulse(Vector::new(ix, iy), true);
        }
    }

    fn remove_stale(&mut self, snaps: &[PhysSnap]) {
        let live: BTreeSet<u64> = snaps.iter().map(|s| s.id).collect();
        let stale: Vec<u64> = self
            .entries
            .keys()
            .copied()
            .filter(|id| !live.contains(id))
            .collect();
        for id in stale {
            self.remove_body(id);
        }
    }

    fn insert_and_sync(&mut self, snaps: &[PhysSnap], world: &mut World) {
        for snap in snaps {
            if !snap.pose_ok {
                world.warnings.push(format!(
                    "GS-EC-01: NaN/Inf transform on {}; skipped rapier sync",
                    format_play_id(snap.id)
                ));
                continue;
            }
            let Some(pose) = snap.pose else {
                continue;
            };
            if self
                .entries
                .get(&snap.id)
                .is_some_and(|e| e.kind != snap.kind)
            {
                self.remove_body(snap.id);
            }
            if !self.entries.contains_key(&snap.id) {
                self.insert_body(snap, pose);
                continue;
            }
            self.sync_existing(snap, pose);
        }
    }

    fn insert_body(&mut self, snap: &PhysSnap, pose: Pose) {
        let mut builder = match snap.kind {
            BodyKind::Dynamic => RigidBodyBuilder::dynamic(),
            BodyKind::Static => RigidBodyBuilder::fixed(),
            BodyKind::Kinematic => RigidBodyBuilder::kinematic_position_based(),
        };
        builder = builder
            .translation(Vector::new(pose.x, pose.y))
            .rotation(pose.rot)
            .gravity_scale(snap.gravity_scale)
            .linear_damping(snap.linear_damping)
            .ccd_enabled(snap.ccd)
            .user_data(u128::from(snap.id));
        if snap.fixed_rotation {
            builder = builder.lock_rotations();
        }
        let body = self.bodies.insert(builder);
        let mut collider = None;
        let mut collider_key = None;
        if let Some(col) = &snap.collider {
            if let Some(built) = build_collider(snap.id, col) {
                let handle = self
                    .colliders
                    .insert_with_parent(built, body, &mut self.bodies);
                collider = Some(handle);
                collider_key = Some(ColliderKey::from_component(col));
            }
        }
        self.entries.insert(
            snap.id,
            BodyEntry {
                body,
                collider,
                kind: snap.kind,
                collider_key,
                last_written: pose,
                baked_colliders: Vec::new(),
                bake_fp: None,
            },
        );
        self.last_valid.insert(snap.id, pose);
    }

    fn sync_existing(&mut self, snap: &PhysSnap, pose: Pose) {
        let Some(entry) = self.entries.get(&snap.id) else {
            return;
        };
        let handle = entry.body;
        let last = entry.last_written;
        if let Some(body) = self.bodies.get_mut(handle) {
            body.set_gravity_scale(snap.gravity_scale, true);
            body.set_linear_damping(snap.linear_damping);
            body.enable_ccd(snap.ccd);
            body.lock_rotations(snap.fixed_rotation, true);
            let iso = Isometry::new(Vector::new(pose.x, pose.y), pose.rot);
            match snap.kind {
                BodyKind::Kinematic => {
                    body.set_next_kinematic_position(iso);
                }
                BodyKind::Dynamic | BodyKind::Static => {
                    if pose != last {
                        body.set_position(iso, true);
                    }
                }
            }
        }
        self.sync_collider(snap);
    }

    fn sync_collider(&mut self, snap: &PhysSnap) {
        let wanted = snap.collider.as_ref().map(ColliderKey::from_component);
        let Some(entry) = self.entries.get(&snap.id) else {
            return;
        };
        let body = entry.body;
        let current = entry.collider;
        let current_key = entry.collider_key.clone();
        match (current, wanted) {
            (None, None) => {}
            (Some(handle), None) => {
                self.colliders
                    .remove(handle, &mut self.islands, &mut self.bodies, true);
                if let Some(entry) = self.entries.get_mut(&snap.id) {
                    entry.collider = None;
                    entry.collider_key = None;
                }
            }
            (None, Some(key)) => {
                if let Some(col) = &snap.collider {
                    if let Some(built) = build_collider(snap.id, col) {
                        let handle =
                            self.colliders
                                .insert_with_parent(built, body, &mut self.bodies);
                        if let Some(entry) = self.entries.get_mut(&snap.id) {
                            entry.collider = Some(handle);
                            entry.collider_key = Some(key);
                        }
                    }
                }
            }
            (Some(handle), Some(key)) => {
                let shape_changed = current_key
                    .as_ref()
                    .is_none_or(|old| old.shape != key.shape || old.offset != key.offset);
                if shape_changed {
                    self.colliders
                        .remove(handle, &mut self.islands, &mut self.bodies, true);
                    if let Some(col) = &snap.collider {
                        if let Some(built) = build_collider(snap.id, col) {
                            let new_handle =
                                self.colliders
                                    .insert_with_parent(built, body, &mut self.bodies);
                            if let Some(entry) = self.entries.get_mut(&snap.id) {
                                entry.collider = Some(new_handle);
                                entry.collider_key = Some(key);
                            }
                        }
                    }
                } else if let Some(col) = self.colliders.get_mut(handle) {
                    col.set_sensor(key.is_sensor);
                    col.set_friction(key.friction);
                    col.set_restitution(key.restitution);
                    col.set_collision_groups(interaction_groups(key.layer, key.mask));
                    col.set_active_collision_types(ActiveCollisionTypes::all());
                    if let Some(entry) = self.entries.get_mut(&snap.id) {
                        entry.collider_key = Some(key);
                    }
                }
            }
        }
    }

    fn remove_body(&mut self, id: u64) {
        let Some(entry) = self.entries.remove(&id) else {
            return;
        };
        self.bodies.remove(
            entry.body,
            &mut self.islands,
            &mut self.colliders,
            &mut self.impulse_joints,
            &mut self.multibody_joints,
            true,
        );
        self.last_valid.remove(&id);
    }

    fn write_transforms(&mut self, world: &mut World) {
        let ids: Vec<u64> = self.entries.keys().copied().collect();
        for id in ids {
            let Some(entry) = self.entries.get(&id) else {
                continue;
            };
            let Some(body) = self.bodies.get(entry.body) else {
                continue;
            };
            let t = body.translation();
            let rot = body.rotation().angle();
            let pose = Pose {
                x: t.x,
                y: t.y,
                rot,
            };
            if !pose_finite(pose) {
                world.warnings.push(format!(
                    "GS-EC-01: physics produced NaN/Inf on {}; reset last valid pose",
                    format_play_id(id)
                ));
                if let Some(valid) = self.last_valid.get(&id).copied() {
                    if let Some(body) = self.bodies.get_mut(entry.body) {
                        body.set_position(
                            Isometry::new(Vector::new(valid.x, valid.y), valid.rot),
                            true,
                        );
                    }
                    write_pose(world, id, valid);
                    if let Some(entry) = self.entries.get_mut(&id) {
                        entry.last_written = valid;
                    }
                }
                continue;
            }
            write_pose(world, id, pose);
            self.last_valid.insert(id, pose);
            if let Some(entry) = self.entries.get_mut(&id) {
                entry.last_written = pose;
            }
        }
    }

    /// Rebuild static boxes for `layer.solid` RLE runs when the fingerprint changes.
    fn bake_tilemap_colliders(&mut self, world: &World) {
        let ids: Vec<u64> = self.entries.keys().copied().collect();
        for id in ids {
            let Some(entity) = world.entities.get(&id) else {
                continue;
            };
            if entity.extra.tilemap.is_none() {
                self.clear_baked_colliders(id, None);
                continue;
            }
            let fp = tilemap_bake_fingerprint(entity);
            if self.entries.get(&id).is_some_and(|e| e.bake_fp == Some(fp)) {
                continue;
            }
            let runs = tilemap_bake_runs(entity);
            self.rebake_tilemap(id, &runs, fp);
        }
    }

    fn clear_baked_colliders(&mut self, id: u64, next_fp: Option<u64>) {
        let Some(entry) = self.entries.get(&id) else {
            return;
        };
        let handles = entry.baked_colliders.clone();
        for handle in handles {
            self.colliders
                .remove(handle, &mut self.islands, &mut self.bodies, true);
        }
        if let Some(entry) = self.entries.get_mut(&id) {
            entry.baked_colliders.clear();
            entry.bake_fp = next_fp;
        }
    }

    fn rebake_tilemap(&mut self, id: u64, runs: &[TilemapBakeRun], fp: u64) {
        self.clear_baked_colliders(id, None);
        let Some(body) = self.entries.get(&id).map(|e| e.body) else {
            return;
        };
        let mut baked = Vec::with_capacity(runs.len());
        for run in runs {
            let built = ColliderBuilder::cuboid(run.half_w, run.half_h)
                .friction(0.5)
                .restitution(0.0)
                .collision_groups(interaction_groups(1, u32::MAX))
                .active_collision_types(ActiveCollisionTypes::all())
                .translation(Vector::new(run.offset_x, run.offset_y))
                .user_data(u128::from(id))
                .build();
            let handle = self
                .colliders
                .insert_with_parent(built, body, &mut self.bodies);
            baked.push(handle);
        }
        if let Some(entry) = self.entries.get_mut(&id) {
            entry.baked_colliders = baked;
            entry.bake_fp = Some(fp);
        }
    }

    fn collect_pairs(&self) -> BTreeSet<(u64, u64, bool)> {
        let mut pairs = BTreeSet::new();
        for pair in self.narrow_phase.contact_pairs() {
            if !pair.has_any_active_contact {
                continue;
            }
            if let Some(norm) = self.norm_pair(pair.collider1, pair.collider2, false) {
                pairs.insert(norm);
            }
        }
        for (h1, h2, intersecting) in self.narrow_phase.intersection_pairs() {
            if !intersecting {
                continue;
            }
            if let Some(norm) = self.norm_pair(h1, h2, true) {
                pairs.insert(norm);
            }
        }
        pairs
    }

    fn norm_pair(
        &self,
        h1: ColliderHandle,
        h2: ColliderHandle,
        sensor: bool,
    ) -> Option<(u64, u64, bool)> {
        let a = entity_id_from_user(self.colliders.get(h1)?.user_data)?;
        let b = entity_id_from_user(self.colliders.get(h2)?.user_data)?;
        if a == b {
            return None;
        }
        if a < b {
            Some((a, b, sensor))
        } else {
            Some((b, a, sensor))
        }
    }
}

struct PhysSnap {
    id: u64,
    kind: BodyKind,
    ccd: bool,
    gravity_scale: f32,
    fixed_rotation: bool,
    linear_damping: f32,
    pose: Option<Pose>,
    pose_ok: bool,
    collider: Option<Collider2D>,
}

fn collect_snaps(world: &World) -> Vec<PhysSnap> {
    world
        .entities
        .iter()
        .filter(|(_, e)| is_physics_entity(e))
        .map(|(id, entity)| snap_entity(*id, entity))
        .collect()
}

pub(crate) fn world_has_physics(world: &World) -> bool {
    world.entities.values().any(is_physics_entity)
}

fn is_physics_entity(entity: &Entity) -> bool {
    entity.extra.rigid_body.is_some()
        || entity.extra.collider.is_some()
        || tilemap_has_solid_bake(entity)
}

fn snap_entity(id: u64, entity: &Entity) -> PhysSnap {
    let (kind, ccd, gravity_scale, fixed_rotation, linear_damping) = match &entity.extra.rigid_body
    {
        Some(rb) => (
            BodyKind::parse(&rb.kind),
            rb.ccd,
            rb.gravity_scale,
            rb.fixed_rotation,
            rb.linear_damping,
        ),
        None => (BodyKind::Static, false, 1.0, false, 0.0),
    };
    let (pose, pose_ok) = match &entity.transform {
        Some(t) => {
            let pose = Pose {
                x: t.x,
                y: t.y,
                rot: t.rot,
            };
            (Some(pose), pose_finite(pose))
        }
        None if entity.extra.tilemap.is_some() => {
            let pose = Pose {
                x: 0.0,
                y: 0.0,
                rot: 0.0,
            };
            (Some(pose), true)
        }
        None => (None, true),
    };
    PhysSnap {
        id,
        kind,
        ccd,
        gravity_scale,
        fixed_rotation,
        linear_damping,
        pose,
        pose_ok,
        collider: entity.extra.collider.clone(),
    }
}

fn pose_finite(pose: Pose) -> bool {
    pose.x.is_finite() && pose.y.is_finite() && pose.rot.is_finite()
}

fn write_pose(world: &mut World, id: u64, pose: Pose) {
    if let Some(entity) = world.entities.get_mut(&id) {
        match &mut entity.transform {
            Some(t) => {
                t.x = pose.x;
                t.y = pose.y;
                t.rot = pose.rot;
            }
            None => {
                entity.transform = Some(Transform2D {
                    x: pose.x,
                    y: pose.y,
                    rot: pose.rot,
                    sx: 1.0,
                    sy: 1.0,
                    z_index: 0,
                });
            }
        }
    }
}

fn interaction_groups(layer: u32, mask: u32) -> InteractionGroups {
    InteractionGroups::new(
        Group::from_bits_retain(layer),
        Group::from_bits_retain(mask),
    )
}

fn build_collider(id: u64, c: &Collider2D) -> Option<rapier2d::prelude::Collider> {
    if !c.offset[0].is_finite() || !c.offset[1].is_finite() {
        return None;
    }
    let builder = match c.shape {
        ColliderShape::Box { w, h } => {
            if !w.is_finite() || !h.is_finite() || w <= 0.0 || h <= 0.0 {
                return None;
            }
            ColliderBuilder::cuboid(w * 0.5, h * 0.5)
        }
        ColliderShape::Circle { r } => {
            if !r.is_finite() || r <= 0.0 {
                return None;
            }
            ColliderBuilder::ball(r)
        }
        ColliderShape::Capsule { half_h, r } => {
            if !half_h.is_finite() || !r.is_finite() || half_h <= 0.0 || r <= 0.0 {
                return None;
            }
            ColliderBuilder::capsule_y(half_h, r)
        }
    };
    Some(
        builder
            .sensor(c.is_sensor)
            .friction(c.friction)
            .restitution(c.restitution)
            .collision_groups(interaction_groups(c.layer, c.mask))
            .active_collision_types(ActiveCollisionTypes::all())
            .translation(Vector::new(c.offset[0], c.offset[1]))
            .user_data(u128::from(id))
            .build(),
    )
}

fn entity_id_from_user(user: u128) -> Option<u64> {
    u64::try_from(user).ok()
}
