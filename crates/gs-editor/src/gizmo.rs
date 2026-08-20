//! Gizmo move/rotate/scale: preview locally, one dispatcher txn on release (WP-M1-3).
//!
//! Soft lock lives in the editor layer (TTL 2s, renew on update). `entity.lock`
//! is not implemented in gs-scene yet.

use std::time::{Duration, Instant};

use gs_scene::{parse_entity_id, Transform2D};
use serde_json::Value;

use crate::snapshot::ViewportEntity;

/// Soft-lock TTL while a gizmo drag is open (GS-EC-12). Renewed on each update.
pub const GIZMO_LOCK_TTL: Duration = Duration::from_secs(2);

const SCALE_ABS_MIN: f32 = 0.001;
const SCALE_ABS_MAX: f32 = 1000.0;

/// Viewport gizmo tool (MASTER 9.2 / 9.8).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum GizmoKind {
    #[default]
    Move,
    Rotate,
    Scale,
}

impl GizmoKind {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Move => "move",
            Self::Rotate => "rotate",
            Self::Scale => "scale",
        }
    }

    /// Activity-feed label for the commit (`gizmo move` / rotate / scale).
    pub fn feed_label(self) -> &'static str {
        match self {
            Self::Move => "gizmo move",
            Self::Rotate => "gizmo rotate",
            Self::Scale => "gizmo scale",
        }
    }
}

/// Preview values for an in-flight drag. Move uses `world_delta` from the
/// pose captured at [`crate::UiHandle::begin_gizmo_drag`]; rotate/scale use
/// absolute `rot` / `sx` / `sy` when set.
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct GizmoDragUpdate {
    pub world_delta: [f32; 2],
    pub rot: Option<f32>,
    pub sx: Option<f32>,
    pub sy: Option<f32>,
}

impl GizmoDragUpdate {
    pub fn move_by(dx: f32, dy: f32) -> Self {
        Self {
            world_delta: [dx, dy],
            rot: None,
            sx: None,
            sy: None,
        }
    }

    pub fn rotate(rot: f32) -> Self {
        Self {
            world_delta: [0.0, 0.0],
            rot: Some(rot),
            sx: None,
            sy: None,
        }
    }

    pub fn scale(sx: f32, sy: f32) -> Self {
        Self {
            world_delta: [0.0, 0.0],
            rot: None,
            sx: Some(sx),
            sy: Some(sy),
        }
    }
}

/// Read-only snapshot of an open gizmo drag (preview is not on the document).
#[derive(Clone, Debug, PartialEq)]
pub struct GizmoDrag {
    pub entity_id: String,
    pub kind: GizmoKind,
    pub start: Transform2D,
    pub preview: Transform2D,
}

#[derive(Clone, Debug)]
pub(crate) struct GizmoSession {
    pub entity_id: String,
    pub entity_num: u64,
    pub kind: GizmoKind,
    pub owner: String,
    pub start: Transform2D,
    pub preview: Transform2D,
    pub last_touch: Instant,
}

impl GizmoSession {
    pub fn info(&self) -> GizmoDrag {
        GizmoDrag {
            entity_id: self.entity_id.clone(),
            kind: self.kind,
            start: self.start.clone(),
            preview: self.preview.clone(),
        }
    }

    pub fn touch(&mut self) {
        self.last_touch = Instant::now();
    }

    pub fn lock_held(&self) -> bool {
        self.last_touch.elapsed() < GIZMO_LOCK_TTL
    }
}

pub(crate) fn apply_preview(
    kind: GizmoKind,
    start: &Transform2D,
    update: &GizmoDragUpdate,
) -> Result<Transform2D, &'static str> {
    if !update.world_delta[0].is_finite() || !update.world_delta[1].is_finite() {
        return Err("gizmo world_delta must be finite");
    }
    if update.rot.is_some_and(|v| !v.is_finite()) {
        return Err("gizmo rot must be finite");
    }
    if update.sx.is_some_and(|v| !v.is_finite()) || update.sy.is_some_and(|v| !v.is_finite()) {
        return Err("gizmo scale must be finite");
    }

    let mut preview = start.clone();
    match kind {
        GizmoKind::Move => {
            preview.x = start.x + update.world_delta[0];
            preview.y = start.y + update.world_delta[1];
        }
        GizmoKind::Rotate => {
            preview.rot = update.rot.unwrap_or(start.rot + update.world_delta[0]);
        }
        GizmoKind::Scale => {
            preview.sx = clamp_scale(update.sx.unwrap_or(start.sx + update.world_delta[0]));
            preview.sy = clamp_scale(update.sy.unwrap_or(start.sy + update.world_delta[1]));
        }
    }
    Ok(preview)
}

fn clamp_scale(v: f32) -> f32 {
    let sign = if v.is_sign_negative() { -1.0 } else { 1.0 };
    let mag = v.abs().clamp(SCALE_ABS_MIN, SCALE_ABS_MAX);
    sign * mag
}

/// World-space hit test for gizmo handles (no window required).
pub fn gizmo_hit(
    entity: &ViewportEntity,
    kind: GizmoKind,
    world: [f32; 2],
    ortho_height: f32,
) -> bool {
    let slop = (ortho_height * 0.04).max(0.05);
    let axis = (ortho_height * 0.18).max(0.25);
    let origin = [entity.x, entity.y];
    match kind {
        GizmoKind::Move => {
            dist(world, origin) <= slop * 1.4
                || point_to_seg(world, origin, [origin[0] + axis, origin[1]]) <= slop
                || point_to_seg(world, origin, [origin[0], origin[1] + axis]) <= slop
        }
        GizmoKind::Rotate => {
            let radius = axis;
            (dist(world, origin) - radius).abs() <= slop
        }
        GizmoKind::Scale => {
            let w = entity.sx.abs().max(0.001);
            let h = entity.sy.abs().max(0.001);
            let left = entity.x - entity.pivot[0] * w;
            let bottom = entity.y - entity.pivot[1] * h;
            let corners = [
                [left, bottom],
                [left + w, bottom],
                [left, bottom + h],
                [left + w, bottom + h],
            ];
            corners.iter().any(|c| dist(world, *c) <= slop * 1.2)
        }
    }
}

fn dist(a: [f32; 2], b: [f32; 2]) -> f32 {
    let dx = a[0] - b[0];
    let dy = a[1] - b[1];
    dx.hypot(dy)
}

fn point_to_seg(p: [f32; 2], a: [f32; 2], b: [f32; 2]) -> f32 {
    let ab = [b[0] - a[0], b[1] - a[1]];
    let ap = [p[0] - a[0], p[1] - a[1]];
    let len2 = ab[0] * ab[0] + ab[1] * ab[1];
    if len2 <= f32::EPSILON {
        return dist(p, a);
    }
    let t = ((ap[0] * ab[0] + ap[1] * ab[1]) / len2).clamp(0.0, 1.0);
    dist(p, [a[0] + ab[0] * t, a[1] + ab[1] * t])
}

pub(crate) fn agent_touches_locked(method: &str, params: &Value, locked: u64) -> bool {
    match method {
        "component.set" | "component.add" | "component.remove" | "entity.destroy"
        | "entity.reparent" | "entity.set_order" | "entity.rename" => {
            params_mention_entity(params, locked)
        }
        "transaction.execute" => params
            .get("commands")
            .and_then(Value::as_array)
            .is_some_and(|cmds| {
                cmds.iter().any(|cmd| {
                    let inner_method = cmd.get("method").and_then(Value::as_str).unwrap_or("");
                    let inner = cmd.get("params").unwrap_or(&Value::Null);
                    agent_touches_locked(inner_method, inner, locked)
                })
            }),
        _ => false,
    }
}

fn params_mention_entity(params: &Value, locked: u64) -> bool {
    if id_is(params.get("id"), locked) {
        return true;
    }
    if let Some(ids) = params.get("ids").and_then(Value::as_array) {
        if ids.iter().any(|v| id_is(Some(v), locked)) {
            return true;
        }
    }
    for key in ["parent", "new_parent", "from_entity"] {
        if id_is(params.get(key), locked) {
            return true;
        }
    }
    false
}

fn id_is(value: Option<&Value>, locked: u64) -> bool {
    value
        .and_then(Value::as_str)
        .and_then(|s| parse_entity_id(s).ok())
        .is_some_and(|n| n == locked)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn move_preview_is_offset_from_start() {
        let start = Transform2D::identity();
        let preview = apply_preview(
            GizmoKind::Move,
            &start,
            &GizmoDragUpdate::move_by(2.0, -1.0),
        )
        .expect("preview");
        assert_eq!(preview.x, 2.0);
        assert_eq!(preview.y, -1.0);
        assert_eq!(preview.rot, 0.0);
    }

    #[test]
    fn rotate_and_scale_use_absolute_values() {
        let start = Transform2D::identity();
        let rotated =
            apply_preview(GizmoKind::Rotate, &start, &GizmoDragUpdate::rotate(1.25)).expect("rot");
        assert!((rotated.rot - 1.25).abs() < f32::EPSILON);
        let scaled = apply_preview(GizmoKind::Scale, &start, &GizmoDragUpdate::scale(2.0, 0.5))
            .expect("scale");
        assert_eq!(scaled.sx, 2.0);
        assert_eq!(scaled.sy, 0.5);
    }
}
