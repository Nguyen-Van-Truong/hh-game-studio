//! Target 2: standalone winit window. Same `RenderSnapshot` as the other bins.

use std::sync::Arc;

use render_spike::{demo_atlas, demo_snapshot, pick, RenderSnapshot, SpriteGpu};
use winit::application::ApplicationHandler;
use winit::event::WindowEvent;
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::window::{Window, WindowId};

fn main() {
    let event_loop = EventLoop::new().expect("event loop");
    event_loop.set_control_flow(ControlFlow::Wait);
    let mut app = PlayerApp {
        snapshot: demo_snapshot(),
        state: None,
        last_pick: None,
    };
    event_loop.run_app(&mut app).expect("run player");
}

struct PlayerApp {
    snapshot: RenderSnapshot,
    state: Option<PlayerState>,
    last_pick: Option<u64>,
}

struct PlayerState {
    window: Arc<Window>,
    device: wgpu::Device,
    queue: wgpu::Queue,
    surface: wgpu::Surface<'static>,
    config: wgpu::SurfaceConfiguration,
    gpu: SpriteGpu,
}

impl PlayerState {
    fn new(window: Arc<Window>) -> Result<Self, String> {
        let instance = wgpu::Instance::new(&wgpu::InstanceDescriptor {
            backends: wgpu::Backends::PRIMARY | wgpu::Backends::GL,
            ..Default::default()
        });
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| format!("create_surface: {e}"))?;
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: Some(&surface),
            force_fallback_adapter: false,
        }))
        .ok_or_else(|| "no adapter for winit surface".to_string())?;
        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("player"),
                required_features: wgpu::Features::empty(),
                required_limits: wgpu::Limits::downlevel_defaults(),
                memory_hints: wgpu::MemoryHints::default(),
            },
            None,
        ))
        .map_err(|e| format!("request_device: {e}"))?;

        let caps = surface.get_capabilities(&adapter);
        let format = caps
            .formats
            .iter()
            .copied()
            .find(wgpu::TextureFormat::is_srgb)
            .unwrap_or(caps.formats[0]);
        let size = window.inner_size();
        let config = wgpu::SurfaceConfiguration {
            usage: wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: wgpu::PresentMode::AutoVsync,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);
        let gpu = SpriteGpu::new(&device, &queue, format, demo_atlas());
        Ok(Self {
            window,
            device,
            queue,
            surface,
            config,
            gpu,
        })
    }

    fn resize(&mut self, width: u32, height: u32) {
        if width == 0 || height == 0 {
            return;
        }
        self.config.width = width;
        self.config.height = height;
        self.surface.configure(&self.device, &self.config);
    }

    fn redraw(&mut self, snapshot: &RenderSnapshot) -> Result<(), String> {
        self.gpu.prepare(
            &self.device,
            &self.queue,
            snapshot,
            self.config.width as f32,
            self.config.height as f32,
        );
        let frame = self
            .surface
            .get_current_texture()
            .map_err(|e| format!("surface: {e}"))?;
        let view = frame
            .texture
            .create_view(&wgpu::TextureViewDescriptor::default());
        let mut encoder = self
            .device
            .create_command_encoder(&wgpu::CommandEncoderDescriptor {
                label: Some("player"),
            });
        {
            let mut pass = encoder.begin_render_pass(&wgpu::RenderPassDescriptor {
                label: Some("player"),
                color_attachments: &[Some(wgpu::RenderPassColorAttachment {
                    view: &view,
                    resolve_target: None,
                    ops: wgpu::Operations {
                        load: wgpu::LoadOp::Clear(render_spike::gpu_clear_color()),
                        store: wgpu::StoreOp::Store,
                    },
                })],
                depth_stencil_attachment: None,
                timestamp_writes: None,
                occlusion_query_set: None,
            });
            self.gpu.draw(&mut pass);
        }
        self.queue.submit(Some(encoder.finish()));
        frame.present();
        Ok(())
    }
}

impl ApplicationHandler for PlayerApp {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.state.is_some() {
            return;
        }
        let attrs = Window::default_attributes()
            .with_title("HH render-spike player (winit)")
            .with_inner_size(winit::dpi::PhysicalSize::new(640, 360));
        let window = match event_loop.create_window(attrs) {
            Ok(w) => Arc::new(w),
            Err(e) => {
                eprintln!("create_window: {e}");
                event_loop.exit();
                return;
            }
        };
        match PlayerState::new(window) {
            Ok(state) => {
                state.window.request_redraw();
                self.state = Some(state);
            }
            Err(e) => {
                eprintln!("player GPU init FAILED: {e}");
                event_loop.exit();
            }
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        let Some(state) = self.state.as_mut() else {
            return;
        };
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Resized(size) => {
                state.resize(size.width, size.height);
                state.window.request_redraw();
            }
            WindowEvent::ScaleFactorChanged { .. } => {
                let size = state.window.inner_size();
                state.resize(size.width, size.height);
                state.window.request_redraw();
            }
            WindowEvent::CursorMoved { position, .. } => {
                let hit = pick(
                    &self.snapshot,
                    &state.gpu.atlas,
                    position.x as f32,
                    position.y as f32,
                    state.config.width as f32,
                    state.config.height as f32,
                );
                if hit != self.last_pick {
                    self.last_pick = hit;
                    state.window.set_title(&match hit {
                        Some(id) => format!("HH render-spike player — pick entity {id}"),
                        None => "HH render-spike player (winit)".into(),
                    });
                }
            }
            WindowEvent::RedrawRequested => {
                if let Err(e) = state.redraw(&self.snapshot) {
                    eprintln!("redraw: {e}");
                }
            }
            _ => {}
        }
    }
}
