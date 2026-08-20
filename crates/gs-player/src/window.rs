//! Optional winit Play window. Tests must not call [`run_window`].

use std::collections::BTreeSet;
use std::path::Path;
use std::sync::Arc;
use std::time::Instant;

use gs_render2d::{render_snapshot_to_surface, AtlasCpu, RenderSnapshot, SpriteGpu};
use gs_runtime_core::{InputFrame, PhysicsHost, ScriptHost, World, FIXED_DT};
use serde_json::Value;
use winit::application::ApplicationHandler;
use winit::event::{ElementState, WindowEvent};
use winit::event_loop::{ActiveEventLoop, ControlFlow, EventLoop};
use winit::keyboard::{KeyCode, PhysicalKey};
use winit::window::{Window, WindowId};

use crate::audio::AudioEngine;
use crate::error::Error;
use crate::gamepad::{
    apply_gamepad_sample, bindings_from_input_map, poll_gilrs, try_open_gilrs, GamepadBinding,
    GamepadSample,
};
use crate::input::{apply_held_keys, input_frame_from_map, load_input_map_value};
use crate::script_play::{
    load_play_scripts, make_physics_host, make_script_host, step_world, world_needs_host,
};
use crate::verify::verify_snapshot;

const MAX_STEPS_PER_DISPLAY_FRAME: u32 = 8;

/// Interactive 60Hz window. Not used by `cargo test` / `--headless` / `--frames`.
pub fn run_window(manifest: &Path) -> Result<(), Error> {
    let verified = verify_snapshot(manifest)?;
    let play_dir = manifest
        .parent()
        .ok_or_else(|| Error::reject("manifest path has no parent directory"))?;
    let mut world = World::from_scene_path(&play_dir.join("scene.json"), verified.manifest.seed)?;
    let atlas = crate::atlas::bind_play_atlas(&mut world, play_dir)?;
    load_play_scripts(&mut world, play_dir)?;
    let host = if world_needs_host(&world) {
        Some(make_script_host()?)
    } else {
        None
    };
    let physics = make_physics_host();
    let snapshot = gs_runtime_core::build_render_snapshot(&mut world)?;
    let input_map = load_input_map_value(play_dir)?;
    let input = input_frame_from_map(&input_map);
    let gamepad_bindings = bindings_from_input_map(&input_map);
    let audio = AudioEngine::window(play_dir);
    let title = window_title(play_dir);

    let event_loop = EventLoop::new().map_err(|e| Error::Window(e.to_string()))?;
    event_loop.set_control_flow(ControlFlow::Poll);
    let mut app = PlayerApp {
        title,
        world,
        host,
        physics,
        snapshot,
        input,
        input_map,
        held_keys: BTreeSet::new(),
        gamepad_bindings,
        gamepad_sample: GamepadSample::default(),
        gilrs: try_open_gilrs(),
        audio,
        atlas: Some(atlas),
        state: None,
        last_tick: Instant::now(),
        acc: 0.0,
        failed: None,
    };
    event_loop
        .run_app(&mut app)
        .map_err(|e| Error::Window(e.to_string()))?;
    match app.failed {
        Some(err) => Err(err),
        None => Ok(()),
    }
}

struct PlayerApp {
    title: String,
    world: World,
    host: Option<ScriptHost>,
    physics: PhysicsHost,
    snapshot: RenderSnapshot,
    input: InputFrame,
    input_map: Value,
    held_keys: BTreeSet<String>,
    gamepad_bindings: Vec<GamepadBinding>,
    gamepad_sample: GamepadSample,
    gilrs: Option<gilrs::Gilrs>,
    audio: AudioEngine,
    atlas: Option<AtlasCpu>,
    state: Option<PlayerState>,
    last_tick: Instant,
    acc: f64,
    failed: Option<Error>,
}

struct PlayerState {
    window: Arc<Window>,
    device: gs_render2d::wgpu::Device,
    queue: gs_render2d::wgpu::Queue,
    surface: gs_render2d::wgpu::Surface<'static>,
    config: gs_render2d::wgpu::SurfaceConfiguration,
    gpu: SpriteGpu,
}

fn window_title(play_dir: &Path) -> String {
    let path = play_dir.join("project-settings.json");
    if let Ok(bytes) = std::fs::read(path) {
        if let Ok(value) = serde_json::from_slice::<Value>(&bytes) {
            if let Some(title) = value.get("title").and_then(Value::as_str) {
                let title = title.trim();
                if !title.is_empty() && title.len() <= 80 {
                    return title.to_string();
                }
            }
        }
    }
    play_dir
        .file_name()
        .and_then(|s| s.to_str())
        .map(|name| format!("HH Game Studio — {name}"))
        .unwrap_or_else(|| "HH Game Studio — Player".into())
}

impl PlayerState {
    fn new(event_loop: &ActiveEventLoop, title: &str, atlas: AtlasCpu) -> Result<Self, Error> {
        let attrs = Window::default_attributes().with_title(title);
        let window = Arc::new(
            event_loop
                .create_window(attrs)
                .map_err(|e| Error::Window(e.to_string()))?,
        );
        let instance = gs_render2d::wgpu::Instance::new(&gs_render2d::wgpu::InstanceDescriptor {
            backends: gs_render2d::wgpu::Backends::PRIMARY | gs_render2d::wgpu::Backends::GL,
            ..Default::default()
        });
        let surface = instance
            .create_surface(window.clone())
            .map_err(|e| Error::Window(e.to_string()))?;
        let adapter = pollster::block_on(instance.request_adapter(
            &gs_render2d::wgpu::RequestAdapterOptions {
                power_preference: gs_render2d::wgpu::PowerPreference::HighPerformance,
                compatible_surface: Some(&surface),
                force_fallback_adapter: false,
            },
        ))
        .ok_or_else(|| Error::Window("no wgpu adapter for the player window".into()))?;
        let (device, queue) = pollster::block_on(adapter.request_device(
            &gs_render2d::wgpu::DeviceDescriptor {
                label: Some("gs-player"),
                required_features: gs_render2d::wgpu::Features::empty(),
                required_limits: gs_render2d::wgpu::Limits::downlevel_defaults(),
                memory_hints: gs_render2d::wgpu::MemoryHints::default(),
            },
            None,
        ))
        .map_err(|e| Error::Window(e.to_string()))?;

        let caps = surface.get_capabilities(&adapter);
        let format = caps
            .formats
            .iter()
            .copied()
            .find(gs_render2d::wgpu::TextureFormat::is_srgb)
            .unwrap_or(caps.formats[0]);
        let size = window.inner_size();
        let config = gs_render2d::wgpu::SurfaceConfiguration {
            usage: gs_render2d::wgpu::TextureUsages::RENDER_ATTACHMENT,
            format,
            width: size.width.max(1),
            height: size.height.max(1),
            present_mode: gs_render2d::wgpu::PresentMode::AutoVsync,
            alpha_mode: caps.alpha_modes[0],
            view_formats: vec![],
            desired_maximum_frame_latency: 2,
        };
        surface.configure(&device, &config);
        let gpu = SpriteGpu::new(&device, &queue, format, atlas);
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

    fn redraw(&mut self, snapshot: &RenderSnapshot) -> Result<(), Error> {
        render_snapshot_to_surface(
            &self.device,
            &self.queue,
            &mut self.gpu,
            &self.surface,
            snapshot,
            self.config.width,
            self.config.height,
        )?;
        Ok(())
    }
}

impl ApplicationHandler for PlayerApp {
    fn resumed(&mut self, event_loop: &ActiveEventLoop) {
        if self.state.is_some() {
            return;
        }
        let atlas = self
            .atlas
            .take()
            .unwrap_or_else(crate::atlas::solid_white_atlas);
        match PlayerState::new(event_loop, &self.title, atlas) {
            Ok(state) => self.state = Some(state),
            Err(err) => {
                self.failed = Some(err);
                event_loop.exit();
            }
        }
    }

    fn window_event(&mut self, event_loop: &ActiveEventLoop, _id: WindowId, event: WindowEvent) {
        match event {
            WindowEvent::CloseRequested => event_loop.exit(),
            WindowEvent::Resized(size) => {
                if let Some(state) = self.state.as_mut() {
                    state.resize(size.width, size.height);
                }
            }
            WindowEvent::RedrawRequested => {
                if let Err(err) = self.tick_and_draw() {
                    self.failed = Some(err);
                    event_loop.exit();
                }
            }
            WindowEvent::KeyboardInput { event, .. } => {
                let PhysicalKey::Code(code) = event.physical_key else {
                    return;
                };
                let Some(name) = keycode_name(code) else {
                    return;
                };
                match event.state {
                    ElementState::Pressed => {
                        self.held_keys.insert(name.to_string());
                    }
                    ElementState::Released => {
                        self.held_keys.remove(name);
                    }
                }
            }
            _ => {}
        }
    }

    fn about_to_wait(&mut self, _event_loop: &ActiveEventLoop) {
        if let Some(state) = &self.state {
            state.window.request_redraw();
        }
    }
}

impl PlayerApp {
    fn tick_and_draw(&mut self) -> Result<(), Error> {
        let dt = self.last_tick.elapsed().as_secs_f64();
        self.last_tick = Instant::now();
        self.acc += dt;
        if let Some(gilrs) = self.gilrs.as_mut() {
            poll_gilrs(gilrs, &mut self.gamepad_sample);
        }
        let mut input = self.input.clone();
        apply_held_keys(&self.input_map, &self.held_keys, &mut input);
        apply_gamepad_sample(&mut input, &self.gamepad_bindings, &self.gamepad_sample);
        let mut steps = 0;
        while self.acc >= FIXED_DT && steps < MAX_STEPS_PER_DISPLAY_FRAME {
            self.snapshot = step_world(
                &mut self.world,
                &input,
                self.host.as_mut(),
                Some(&mut self.physics),
            )?;
            self.audio.drain(&mut self.world);
            self.acc -= FIXED_DT;
            steps += 1;
        }
        if self.acc > FIXED_DT * f64::from(MAX_STEPS_PER_DISPLAY_FRAME) {
            self.acc = 0.0;
        }
        if let Some(state) = self.state.as_mut() {
            state.redraw(&self.snapshot)?;
        }
        Ok(())
    }
}

fn keycode_name(code: KeyCode) -> Option<&'static str> {
    Some(match code {
        KeyCode::KeyA => "A",
        KeyCode::KeyB => "B",
        KeyCode::KeyC => "C",
        KeyCode::KeyD => "D",
        KeyCode::KeyE => "E",
        KeyCode::KeyF => "F",
        KeyCode::KeyG => "G",
        KeyCode::KeyH => "H",
        KeyCode::KeyI => "I",
        KeyCode::KeyJ => "J",
        KeyCode::KeyK => "K",
        KeyCode::KeyL => "L",
        KeyCode::KeyM => "M",
        KeyCode::KeyN => "N",
        KeyCode::KeyO => "O",
        KeyCode::KeyP => "P",
        KeyCode::KeyQ => "Q",
        KeyCode::KeyR => "R",
        KeyCode::KeyS => "S",
        KeyCode::KeyT => "T",
        KeyCode::KeyU => "U",
        KeyCode::KeyV => "V",
        KeyCode::KeyW => "W",
        KeyCode::KeyX => "X",
        KeyCode::KeyY => "Y",
        KeyCode::KeyZ => "Z",
        KeyCode::Digit0 => "0",
        KeyCode::Digit1 => "1",
        KeyCode::Digit2 => "2",
        KeyCode::Digit3 => "3",
        KeyCode::Digit4 => "4",
        KeyCode::Digit5 => "5",
        KeyCode::Digit6 => "6",
        KeyCode::Digit7 => "7",
        KeyCode::Digit8 => "8",
        KeyCode::Digit9 => "9",
        KeyCode::Space => "Space",
        KeyCode::ArrowLeft => "Left",
        KeyCode::ArrowRight => "Right",
        KeyCode::ArrowUp => "Up",
        KeyCode::ArrowDown => "Down",
        KeyCode::ShiftLeft | KeyCode::ShiftRight => "Shift",
        KeyCode::ControlLeft | KeyCode::ControlRight => "Ctrl",
        KeyCode::Enter => "Enter",
        KeyCode::Escape => "Escape",
        KeyCode::Comma => "Comma",
        KeyCode::Period => "Period",
        KeyCode::Slash => "Slash",
        KeyCode::Numpad1 => "1",
        KeyCode::Numpad2 => "2",
        KeyCode::Numpad3 => "3",
        KeyCode::Numpad4 => "4",
        _ => return None,
    })
}
