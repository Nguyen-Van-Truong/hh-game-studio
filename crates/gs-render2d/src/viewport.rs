//! Target 2: eframe / `egui_wgpu::CallbackTrait` viewport.
//! Game pixels are physical; egui points are only for chrome around the canvas.

use crate::{AtlasCpu, RenderSnapshot, SpriteGpu};

/// Paint callback that draws a [`RenderSnapshot`] into an egui rect.
///
/// Prepare vertices in **physical pixels**. `paint` sets viewport/scissor from
/// [`egui::PaintCallbackInfo::viewport_in_pixels`].
pub struct ViewportCallback {
    pub snapshot: RenderSnapshot,
    pub width_px: f32,
    pub height_px: f32,
}

impl ViewportCallback {
    pub fn new(snapshot: RenderSnapshot, width_px: f32, height_px: f32) -> Self {
        Self {
            snapshot,
            width_px,
            height_px,
        }
    }

    /// Wrap as an egui paint callback for `ui.painter().add(...)`.
    pub fn into_paint_callback(self, rect: egui::Rect) -> egui::PaintCallback {
        egui_wgpu::Callback::new_paint_callback(rect, self)
    }
}

/// Insert (or replace) the shared [`SpriteGpu`] in egui-wgpu callback resources.
/// Call once from the eframe `CreationContext` wgpu render state.
pub fn install_sprite_gpu(
    resources: &mut egui_wgpu::CallbackResources,
    device: &wgpu::Device,
    queue: &wgpu::Queue,
    format: wgpu::TextureFormat,
    atlas: AtlasCpu,
) {
    resources.insert(SpriteGpu::new(device, queue, format, atlas));
}

impl egui_wgpu::CallbackTrait for ViewportCallback {
    fn prepare(
        &self,
        device: &wgpu::Device,
        queue: &wgpu::Queue,
        _screen_descriptor: &egui_wgpu::ScreenDescriptor,
        _egui_encoder: &mut wgpu::CommandEncoder,
        resources: &mut egui_wgpu::CallbackResources,
    ) -> Vec<wgpu::CommandBuffer> {
        if let Some(gpu) = resources.get_mut::<SpriteGpu>() {
            gpu.prepare(device, queue, &self.snapshot, self.width_px, self.height_px);
        }
        Vec::new()
    }

    fn paint(
        &self,
        info: egui::PaintCallbackInfo,
        render_pass: &mut wgpu::RenderPass<'static>,
        resources: &egui_wgpu::CallbackResources,
    ) {
        let Some(gpu) = resources.get::<SpriteGpu>() else {
            return;
        };
        let vp = info.viewport_in_pixels();
        if vp.width_px <= 0 || vp.height_px <= 0 {
            return;
        }
        let left = vp.left_px.max(0) as f32;
        let top = vp.top_px.max(0) as f32;
        render_pass.set_viewport(left, top, vp.width_px as f32, vp.height_px as f32, 0.0, 1.0);
        render_pass.set_scissor_rect(
            vp.left_px.max(0) as u32,
            vp.top_px.max(0) as u32,
            vp.width_px as u32,
            vp.height_px as u32,
        );
        gpu.draw(render_pass);
    }
}
