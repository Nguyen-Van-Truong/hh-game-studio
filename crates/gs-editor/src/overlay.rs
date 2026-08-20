//! Viewport overlays in world space (grid, collider, script badge). egui only.

use egui::{Color32, Pos2, Rect, Stroke, StrokeKind};
use gs_render2d::{world_to_clip, Camera2D};

use crate::gizmo::GizmoKind;
use crate::snapshot::{ColliderOverlay, ViewportEntity};
use crate::view_state::ViewState;

const MAX_GRID_LINES: f32 = 64.0;

pub fn world_to_screen(world: [f32; 2], camera: &Camera2D, rect: Rect, ppp: f32) -> Pos2 {
    let width_px = rect.width() * ppp;
    let height_px = rect.height() * ppp;
    if width_px <= 0.0 || height_px <= 0.0 {
        return rect.center();
    }
    let [cx, cy] = world_to_clip(world[0], world[1], camera, width_px, height_px);
    let px = (cx + 1.0) * 0.5 * width_px;
    let py = (1.0 - cy) * 0.5 * height_px;
    Pos2::new(rect.min.x + px / ppp, rect.min.y + py / ppp)
}

pub fn paint_grid(painter: &egui::Painter, rect: Rect, ppp: f32, view: &ViewState) {
    if !view.grid_enabled || view.grid_size <= 0.0 {
        return;
    }
    let camera = view.camera();
    let width_px = rect.width() * ppp;
    let height_px = rect.height() * ppp;
    if width_px <= 0.0 || height_px <= 0.0 {
        return;
    }
    let half_h = view.ortho_height * 0.5;
    let half_w = half_h * (width_px / height_px);
    let left = camera.position[0] - half_w;
    let right = camera.position[0] + half_w;
    let bottom = camera.position[1] - half_h;
    let top = camera.position[1] + half_h;

    let mut step = view.grid_size;
    let span = (right - left).max(top - bottom);
    while span / step > MAX_GRID_LINES {
        step *= 2.0;
    }

    let stroke = Stroke::new(1.0, Color32::from_rgba_unmultiplied(70, 80, 100, 90));
    let axis = Stroke::new(1.5, Color32::from_rgba_unmultiplied(120, 140, 180, 140));

    let mut x = (left / step).floor() * step;
    while x <= right + step * 0.5 {
        let a = world_to_screen([x, bottom], &camera, rect, ppp);
        let b = world_to_screen([x, top], &camera, rect, ppp);
        let s = if x.abs() < step * 0.01 { axis } else { stroke };
        painter.line_segment([a, b], s);
        x += step;
    }
    let mut y = (bottom / step).floor() * step;
    while y <= top + step * 0.5 {
        let a = world_to_screen([left, y], &camera, rect, ppp);
        let b = world_to_screen([right, y], &camera, rect, ppp);
        let s = if y.abs() < step * 0.01 { axis } else { stroke };
        painter.line_segment([a, b], s);
        y += step;
    }
}

pub fn paint_colliders(
    painter: &egui::Painter,
    rect: Rect,
    ppp: f32,
    view: &ViewState,
    entities: &[ViewportEntity],
) {
    let camera = view.camera();
    let stroke = Stroke::new(1.5, Color32::from_rgb(80, 220, 160));
    for entity in entities {
        if !entity.visible {
            continue;
        }
        let Some(collider) = &entity.collider else {
            continue;
        };
        match *collider {
            ColliderOverlay::Box { w, h, offset } => {
                let cx = entity.x + offset[0];
                let cy = entity.y + offset[1];
                let min = world_to_screen([cx - w * 0.5, cy - h * 0.5], &camera, rect, ppp);
                let max = world_to_screen([cx + w * 0.5, cy + h * 0.5], &camera, rect, ppp);
                painter.rect_stroke(
                    Rect::from_two_pos(min, max),
                    0.0,
                    stroke,
                    StrokeKind::Middle,
                );
            }
            ColliderOverlay::Circle { r, offset } => {
                let center = world_to_screen(
                    [entity.x + offset[0], entity.y + offset[1]],
                    &camera,
                    rect,
                    ppp,
                );
                let edge = world_to_screen(
                    [entity.x + offset[0] + r, entity.y + offset[1]],
                    &camera,
                    rect,
                    ppp,
                );
                painter.circle_stroke(center, (edge.x - center.x).abs(), stroke);
            }
            ColliderOverlay::Capsule { half_h, r, offset } => {
                let cx = entity.x + offset[0];
                let cy = entity.y + offset[1];
                let min = world_to_screen([cx - r, cy - half_h - r], &camera, rect, ppp);
                let max = world_to_screen([cx + r, cy + half_h + r], &camera, rect, ppp);
                painter.rect_stroke(
                    Rect::from_two_pos(min, max),
                    4.0,
                    stroke,
                    StrokeKind::Middle,
                );
            }
        }
    }
}

pub fn paint_script_badges(
    painter: &egui::Painter,
    rect: Rect,
    ppp: f32,
    view: &ViewState,
    entities: &[ViewportEntity],
) {
    let camera = view.camera();
    for entity in entities {
        if !entity.script_badge || !entity.visible {
            continue;
        }
        let w = entity.sx.abs().max(0.001);
        let h = entity.sy.abs().max(0.001);
        let left = entity.x - entity.pivot[0] * w;
        let bottom = entity.y - entity.pivot[1] * h;
        let corner = world_to_screen([left + w, bottom + h], &camera, rect, ppp);
        painter.circle_filled(corner, 5.0, Color32::from_rgb(220, 50, 50));
    }
}

pub fn paint_selection(
    painter: &egui::Painter,
    rect: Rect,
    ppp: f32,
    view: &ViewState,
    entities: &[ViewportEntity],
) {
    let Some(id) = view.selected else {
        return;
    };
    let Some(entity) = entities.iter().find(|e| e.id == id) else {
        return;
    };
    let camera = view.camera();
    let w = entity.sx.abs().max(0.001);
    let h = entity.sy.abs().max(0.001);
    let left = entity.x - entity.pivot[0] * w;
    let bottom = entity.y - entity.pivot[1] * h;
    let min = world_to_screen([left, bottom], &camera, rect, ppp);
    let max = world_to_screen([left + w, bottom + h], &camera, rect, ppp);
    painter.rect_stroke(
        Rect::from_two_pos(min, max),
        0.0,
        Stroke::new(1.5, Color32::from_rgb(255, 210, 70)),
        StrokeKind::Middle,
    );
}

/// Simple move (axes) / rotate (ring) / scale (corner boxes) handles.
pub fn paint_gizmo(
    painter: &egui::Painter,
    rect: Rect,
    ppp: f32,
    view: &ViewState,
    entities: &[ViewportEntity],
    kind: GizmoKind,
) {
    let Some(id) = view.selected else {
        return;
    };
    let Some(entity) = entities.iter().find(|e| e.id == id) else {
        return;
    };
    let camera = view.camera();
    let axis_len = (view.ortho_height * 0.18).max(0.25);
    let origin = world_to_screen([entity.x, entity.y], &camera, rect, ppp);
    let handle = (6.0_f32).max(4.0);
    match kind {
        GizmoKind::Move => {
            let x_end = world_to_screen([entity.x + axis_len, entity.y], &camera, rect, ppp);
            let y_end = world_to_screen([entity.x, entity.y + axis_len], &camera, rect, ppp);
            painter.line_segment(
                [origin, x_end],
                Stroke::new(2.0, Color32::from_rgb(220, 70, 70)),
            );
            painter.line_segment(
                [origin, y_end],
                Stroke::new(2.0, Color32::from_rgb(70, 200, 90)),
            );
            painter.rect_filled(
                Rect::from_center_size(origin, egui::vec2(handle, handle)),
                1.0,
                Color32::from_rgb(240, 240, 250),
            );
        }
        GizmoKind::Rotate => {
            let rim = world_to_screen([entity.x + axis_len, entity.y], &camera, rect, ppp);
            let radius = (rim.x - origin.x).abs().max(8.0);
            painter.circle_stroke(
                origin,
                radius,
                Stroke::new(1.5, Color32::from_rgb(90, 180, 255)),
            );
            painter.circle_filled(rim, 4.0, Color32::from_rgb(90, 180, 255));
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
            for corner in corners {
                let p = world_to_screen(corner, &camera, rect, ppp);
                painter.rect_filled(
                    Rect::from_center_size(p, egui::vec2(handle, handle)),
                    0.0,
                    Color32::from_rgb(255, 180, 70),
                );
            }
        }
    }
}
