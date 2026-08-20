//! Viewport camera / grid / snap / local selection — **view-state only** (I1).
//!
//! These helpers take [`ViewState`] and numbers. They have no [`gs_scene::Session`]
//! or dispatcher parameter, so they cannot write WAL.

use gs_render2d::{pixel_to_world, world_to_clip, Camera2D};

/// Smallest / largest ortho height (world units, Y-up).
pub const ORTHO_HEIGHT_MIN: f32 = 1.0;
pub const ORTHO_HEIGHT_MAX: f32 = 80.0;

/// Local UI camera and overlays. Not part of the project document.
#[derive(Clone, Debug, PartialEq)]
pub struct ViewState {
    /// World-space camera center (Y-up).
    pub position: [f32; 2],
    /// Visible world height. Smaller = zoomed in.
    pub ortho_height: f32,
    pub grid_enabled: bool,
    pub snap_enabled: bool,
    pub grid_size: f32,
    /// Local selection (I1 view-state). Gizmo mutation goes through [`crate::UiHandle`].
    pub selected: Option<u64>,
}

impl Default for ViewState {
    fn default() -> Self {
        Self {
            position: [0.0, 0.0],
            ortho_height: 10.0,
            grid_enabled: true,
            snap_enabled: false,
            grid_size: 1.0,
            selected: None,
        }
    }
}

impl ViewState {
    pub fn camera(&self) -> Camera2D {
        Camera2D {
            ortho_height: self.ortho_height,
            position: self.position,
        }
    }

    pub fn pan_world(&mut self, dx: f32, dy: f32) {
        self.position[0] += dx;
        self.position[1] += dy;
    }

    /// Pan by a pointer drag in **physical pixels** (Y-down screen).
    pub fn pan_pixels(&mut self, dx_px: f32, dy_px: f32, viewport_w: f32, viewport_h: f32) {
        if viewport_w <= 0.0 || viewport_h <= 0.0 {
            return;
        }
        let half_h = self.ortho_height * 0.5;
        let half_w = half_h * (viewport_w / viewport_h);
        self.position[0] -= dx_px / viewport_w * (half_w * 2.0);
        self.position[1] += dy_px / viewport_h * (half_h * 2.0);
    }

    pub fn zoom_by(&mut self, factor: f32) {
        if !factor.is_finite() || factor <= 0.0 {
            return;
        }
        self.ortho_height = (self.ortho_height * factor).clamp(ORTHO_HEIGHT_MIN, ORTHO_HEIGHT_MAX);
    }

    /// Zoom so `world` stays under the same physical pixel.
    pub fn zoom_toward(
        &mut self,
        factor: f32,
        world: [f32; 2],
        px: f32,
        py: f32,
        viewport_w: f32,
        viewport_h: f32,
    ) {
        self.zoom_by(factor);
        let after = pixel_to_world(px, py, viewport_w, viewport_h, &self.camera());
        self.position[0] += world[0] - after[0];
        self.position[1] += world[1] - after[1];
    }

    pub fn set_grid(&mut self, on: bool) {
        self.grid_enabled = on;
    }

    pub fn set_snap(&mut self, on: bool) {
        self.snap_enabled = on;
    }

    /// Snap a world point to the grid when snap is on. Used later by the gizmo.
    pub fn snap_point(&self, point: [f32; 2]) -> [f32; 2] {
        if !self.snap_enabled || self.grid_size <= 0.0 {
            return point;
        }
        let g = self.grid_size;
        [(point[0] / g).round() * g, (point[1] / g).round() * g]
    }
}

/// Pan + zoom helper with **no** Session / dispatcher argument (I1 / WP-M1-2 DoD).
pub fn apply_view_navigation(view: &mut ViewState, pan_world: [f32; 2], zoom_factor: f32) {
    view.pan_world(pan_world[0], pan_world[1]);
    view.zoom_by(zoom_factor);
}

/// Inverse of [`pixel_to_world`] for pick tests (physical px, Y-down).
pub fn world_to_pixel(
    wx: f32,
    wy: f32,
    viewport_w: f32,
    viewport_h: f32,
    camera: &Camera2D,
) -> [f32; 2] {
    let [cx, cy] = world_to_clip(wx, wy, camera, viewport_w, viewport_h);
    [
        (cx + 1.0) * 0.5 * viewport_w - 0.5,
        (1.0 - cy) * 0.5 * viewport_h - 0.5,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn snap_point_rounds_when_enabled() {
        let mut view = ViewState::default();
        view.set_snap(true);
        view.grid_size = 1.0;
        assert_eq!(view.snap_point([1.4, -0.6]), [1.0, -1.0]);
        view.set_snap(false);
        assert_eq!(view.snap_point([1.4, -0.6]), [1.4, -0.6]);
    }

    #[test]
    fn apply_view_navigation_changes_only_view_state() {
        let mut view = ViewState::default();
        let before = view.clone();
        apply_view_navigation(&mut view, [2.0, -1.0], 0.5);
        assert_eq!(view.position, [2.0, -1.0]);
        assert!((view.ortho_height - 5.0).abs() < f32::EPSILON);
        assert_eq!(view.grid_enabled, before.grid_enabled);
        assert_eq!(view.snap_enabled, before.snap_enabled);
    }
}
