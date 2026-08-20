//! Target 1: eframe + egui_wgpu::CallbackTrait viewport.
//! Game pixels are physical; egui points are only used for chrome around the canvas.

use eframe::egui_wgpu::{self, wgpu};
use render_spike::{demo_atlas, demo_snapshot, pick, RenderSnapshot, SpriteGpu};

fn main() -> eframe::Result<()> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([960.0, 600.0])
            .with_title("HH render-spike viewport (eframe)"),
        renderer: eframe::Renderer::Wgpu,
        ..Default::default()
    };
    eframe::run_native(
        "HH render-spike viewport",
        options,
        Box::new(|cc| Ok(Box::new(ViewportApp::new(cc)))),
    )
}

struct ViewportApp {
    snapshot: RenderSnapshot,
    last_pick: Option<u64>,
}

impl ViewportApp {
    fn new(cc: &eframe::CreationContext<'_>) -> Self {
        if let Some(rs) = cc.wgpu_render_state.as_ref() {
            let gpu = SpriteGpu::new(&rs.device, &rs.queue, rs.target_format, demo_atlas());
            rs.renderer.write().callback_resources.insert(gpu);
        }
        Self {
            snapshot: demo_snapshot(),
            last_pick: None,
        }
    }
}

impl eframe::App for ViewportApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        egui::TopBottomPanel::top("chrome").show(ctx, |ui| {
            ui.horizontal(|ui| {
                ui.label("HH render-spike — eframe viewport");
                ui.separator();
                ui.label(format!(
                    "pick: {}",
                    self.last_pick
                        .map(|id| format!("entity {id}"))
                        .unwrap_or_else(|| "none".into())
                ));
                ui.separator();
                ui.label(format!(
                    "ppp={:.2} (chrome in points; canvas in physical px)",
                    ui.ctx().pixels_per_point()
                ));
            });
        });

        egui::CentralPanel::default().show(ctx, |ui| {
            let avail = ui.available_size();
            let (rect, response) = ui.allocate_exact_size(avail, egui::Sense::click_and_drag());
            let ppp = ui.ctx().pixels_per_point();
            let width_px = rect.width() * ppp;
            let height_px = rect.height() * ppp;

            if let Some(pos) = response.hover_pos() {
                let px = (pos.x - rect.min.x) * ppp;
                let py = (pos.y - rect.min.y) * ppp;
                let atlas = demo_atlas();
                self.last_pick = pick(&self.snapshot, &atlas, px, py, width_px, height_px);
            }

            ui.painter().add(egui_wgpu::Callback::new_paint_callback(
                rect,
                ViewportCallback {
                    snapshot: self.snapshot.clone(),
                    width_px,
                    height_px,
                },
            ));
        });
    }
}

struct ViewportCallback {
    snapshot: RenderSnapshot,
    width_px: f32,
    height_px: f32,
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
