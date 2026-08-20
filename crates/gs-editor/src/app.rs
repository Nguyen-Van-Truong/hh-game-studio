//! Thin eframe/wgpu 5-region shell (MASTER 9.1). Window entry is [`run_native_window`].
//!
//! Do **not** call [`run_native_window`] from `cargo test` — tests stay on [`crate::start`].

use std::time::{Duration, Instant};

use eframe::egui::{self, Color32, RichText};
use gs_render2d::{
    demo_atlas, demo_snapshot, install_sprite_gpu, pick, pixel_to_world, AtlasCpu, RenderSnapshot,
    ViewportCallback,
};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::gizmo::{gizmo_hit, GizmoDragUpdate, GizmoKind};
use crate::hierarchy::HierarchyNode;
use crate::inspector::InspectorField;
use crate::overlay::{
    paint_colliders, paint_gizmo, paint_grid, paint_script_badges, paint_selection,
};
use crate::play_keys::{actions_from_held, held_from_egui};
use crate::schema::{clamp_to_schema, spec_by_type, FieldKind};
use crate::snapshot::{
    apply_live_dump, entities_to_snapshot, use_demo_ir, ProjectChrome, ViewportEntity,
};
use crate::view_state::ViewState;
use crate::{BusHandle, Error};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum BottomTab {
    Console,
    Feed,
    Session,
}

/// Open the eframe wgpu window. Blocks until the window closes.
pub fn run_native_window(bus: BusHandle) -> Result<(), Error> {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default()
            .with_inner_size([1280.0, 800.0])
            .with_title("HH Game Studio"),
        renderer: eframe::Renderer::Wgpu,
        ..Default::default()
    };
    eframe::run_native(
        "HH Game Studio",
        options,
        Box::new(|cc| Ok(Box::new(EditorApp::new(cc, bus)))),
    )
    .map_err(|err| Error::Window(err.to_string()))
}

struct EditorApp {
    bus: BusHandle,
    view: ViewState,
    atlas: AtlasCpu,
    gpu_ready: bool,
    last_pick: Option<u64>,
    using_demo: bool,
    bottom: BottomTab,
    gizmo_kind: GizmoKind,
    gizmo_dragging: bool,
    gizmo_pointer_start: Option<[f32; 2]>,
    hierarchy_drag: Option<String>,
    add_component: String,
    play_id: Option<String>,
    play_alive: bool,
    play_paused: bool,
    play_hung: bool,
    play_banner: Option<String>,
    last_play_poll: Instant,
    view_fitted: bool,
    inputmap_cache: Option<Value>,
}

impl EditorApp {
    fn new(cc: &eframe::CreationContext<'_>, bus: BusHandle) -> Self {
        let atlas = demo_atlas();
        let mut gpu_ready = false;
        if let Some(rs) = cc.wgpu_render_state.as_ref() {
            let mut renderer = rs.renderer.write();
            install_sprite_gpu(
                &mut renderer.callback_resources,
                &rs.device,
                &rs.queue,
                rs.target_format,
                atlas.clone(),
            );
            gpu_ready = true;
        }
        Self {
            bus,
            view: ViewState::default(),
            atlas,
            gpu_ready,
            last_pick: None,
            using_demo: true,
            bottom: BottomTab::Feed,
            gizmo_kind: GizmoKind::Move,
            gizmo_dragging: false,
            gizmo_pointer_start: None,
            hierarchy_drag: None,
            add_component: "Visibility".into(),
            play_id: None,
            play_alive: false,
            play_paused: false,
            play_hung: false,
            play_banner: None,
            last_play_poll: Instant::now() - Duration::from_secs(2),
            view_fitted: false,
            inputmap_cache: None,
        }
    }

    fn chrome(&self) -> ProjectChrome {
        self.bus.ui().project_chrome()
    }

    fn scene_entities(&self) -> Vec<ViewportEntity> {
        self.bus.ui().viewport_entities()
    }

    fn build_snapshot(
        &mut self,
        chrome: &ProjectChrome,
        entities: &[ViewportEntity],
    ) -> RenderSnapshot {
        // Open session (even empty / all-invisible) never falls back to demo IR.
        if !use_demo_ir(chrome) {
            self.using_demo = false;
            if self.play_alive {
                if let Ok(dump) = self.bus.ui().live_view_snapshot() {
                    let mut live = entities.to_vec();
                    apply_live_dump(&mut live, &dump);
                    return entities_to_snapshot(&live, &self.view);
                }
            }
            return entities_to_snapshot(entities, &self.view);
        }
        self.using_demo = true;
        let mut snap = demo_snapshot();
        snap.camera = self.view.camera();
        snap
    }
}

impl eframe::App for EditorApp {
    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.read_gizmo_keys(ctx);
        let _ = self.bus.ui().poll_script_watcher();
        self.poll_play();
        if self.play_alive {
            self.inject_play_keys(ctx);
            ctx.request_repaint_after(Duration::from_millis(50));
        }
        let chrome = self.chrome();
        let entities = self.scene_entities();
        self.maybe_fit_document_camera(&chrome, &entities);
        self.toolbar(ctx, &chrome);
        self.bottom_tabs(ctx);
        self.hierarchy(ctx, &chrome);
        self.inspector(ctx);
        self.viewport(ctx, &chrome, &entities);
    }
}

impl EditorApp {
    fn toolbar(&mut self, ctx: &egui::Context, chrome: &ProjectChrome) {
        egui::TopBottomPanel::top("toolbar").show(ctx, |ui| {
            ui.horizontal(|ui| {
                if ui
                    .add_enabled(!self.play_alive, egui::Button::new("Play"))
                    .clicked()
                {
                    let _ = self.bus.ui().call(
                        "play.start",
                        json!({
                            "headless": true,
                            "command_id": Ulid::new().to_string(),
                        }),
                    );
                    self.last_play_poll = Instant::now() - Duration::from_secs(2);
                }
                let pause_label = if self.play_paused { "Resume" } else { "Pause" };
                if ui
                    .add_enabled(self.play_alive, egui::Button::new(pause_label))
                    .clicked()
                {
                    let method = if self.play_paused {
                        "play.resume"
                    } else {
                        "play.pause"
                    };
                    let _ = self.bus.ui().call(method, json!({}));
                    self.last_play_poll = Instant::now() - Duration::from_secs(2);
                }
                if ui
                    .add_enabled(self.play_alive, egui::Button::new("Step"))
                    .clicked()
                {
                    let _ = self.bus.ui().call("play.step_frames", json!({ "n": 1 }));
                    self.last_play_poll = Instant::now() - Duration::from_secs(2);
                }
                if ui
                    .add_enabled(self.play_alive || self.play_hung, egui::Button::new("Stop"))
                    .clicked()
                {
                    let _ = self.bus.ui().call("play.stop", json!({}));
                    self.last_play_poll = Instant::now() - Duration::from_secs(2);
                }
                if self.play_hung
                    && ui
                        .button(RichText::new("Kill").color(Color32::WHITE))
                        .clicked()
                {
                    let _ = self.bus.ui().call("play.stop", json!({ "force": true }));
                }
                if let Some(id) = &self.play_id {
                    ui.label(format!("play {id}"));
                }
                if self.play_alive {
                    ui.label("live 10Hz — WASD/arrows in this window");
                }
                if ui
                    .add_enabled(self.play_alive, egui::Button::new("Copy to scene"))
                    .clicked()
                {
                    self.copy_play_to_scene();
                }
                ui.separator();
                let scene = chrome.scene_id.as_deref().unwrap_or("(no scene)");
                let rev = chrome.revision.as_deref().unwrap_or("—");
                let name = chrome.name.as_deref().unwrap_or("(no project)");
                ui.label(format!("scene {scene}  {name}  {rev}"));
                ui.separator();
                if ui
                    .add(
                        egui::Button::new(RichText::new("TẠM DỪNG AGENT").color(Color32::WHITE))
                            .fill(Color32::from_rgb(180, 36, 36)),
                    )
                    .clicked()
                {
                    pause_all_agents(&self.bus);
                }
                ui.separator();
                let mut grid = self.view.grid_enabled;
                if ui.checkbox(&mut grid, "grid").changed() {
                    self.view.set_grid(grid);
                }
                let mut snap = self.view.snap_enabled;
                if ui.checkbox(&mut snap, "snap").changed() {
                    self.view.set_snap(snap);
                }
                ui.separator();
                ui.selectable_value(&mut self.gizmo_kind, GizmoKind::Move, "Move");
                ui.selectable_value(&mut self.gizmo_kind, GizmoKind::Rotate, "Rotate");
                ui.selectable_value(&mut self.gizmo_kind, GizmoKind::Scale, "Scale");
                ui.separator();
                if let Some(banner) = &self.play_banner {
                    ui.colored_label(Color32::from_rgb(220, 80, 40), banner);
                }
                if chrome.open && chrome.type_check != "ok" {
                    ui.colored_label(Color32::from_rgb(220, 160, 40), "type check off");
                }
                ui.separator();
                ui.label(format!(
                    "zoom {:.2}  pick {}  {}",
                    self.view.ortho_height,
                    self.last_pick
                        .map(|id| id.to_string())
                        .unwrap_or_else(|| "none".into()),
                    if self.using_demo {
                        "demo IR"
                    } else {
                        "document"
                    }
                ));
            });
        });
    }

    fn hierarchy(&mut self, ctx: &egui::Context, chrome: &ProjectChrome) {
        let tree = self.bus.ui().hierarchy();
        egui::SidePanel::left("hierarchy")
            .default_width(200.0)
            .show(ctx, |ui| {
                ui.heading("Hierarchy");
                ui.label(RichText::new("parent/order · drag to reparent (keep_world)").small());
                ui.separator();
                let root_resp = ui.selectable_label(false, "Scene (root)");
                if root_resp.hovered() && ui.input(|i| i.pointer.any_released()) {
                    if let Some(src) = self.hierarchy_drag.take() {
                        reparent_via_ui(&self.bus, &src, Value::Null);
                    }
                }
                if tree.is_empty() {
                    if chrome.open {
                        ui.label("empty scene — spawn via Hierarchy or bus");
                    } else {
                        ui.label("no project — pass games/snake");
                    }
                    return;
                }
                let dropped = std::cell::RefCell::new(None);
                egui::ScrollArea::vertical().show(ui, |ui| {
                    for node in &tree {
                        draw_hierarchy_node(
                            ui,
                            node,
                            &mut self.view.selected,
                            &mut self.hierarchy_drag,
                            &dropped,
                        );
                    }
                });
                if let Some((src, dest)) = dropped.into_inner() {
                    reparent_via_ui(&self.bus, &src, json!(dest));
                }
            });
    }

    fn inspector(&mut self, ctx: &egui::Context) {
        egui::SidePanel::right("inspector")
            .default_width(260.0)
            .show(ctx, |ui| {
                ui.heading("Inspector");
                ui.label(RichText::new("schema-driven · edits are component.set").small());
                ui.separator();
                let Some(id) = self.view.selected else {
                    ui.label("no selection");
                    return;
                };
                let entity_id = gs_scene::format_entity_id(id);
                let Ok(view) = self.bus.ui().inspector(&entity_id) else {
                    ui.label(format!("entity {entity_id} (demo or missing)"));
                    return;
                };
                ui.label(format!("id  {}", view.id));
                ui.label(format!("rev {}", view.revision));
                ui.separator();
                egui::ScrollArea::vertical().show(ui, |ui| {
                    for component in &view.components {
                        if !component.present {
                            continue;
                        }
                        ui.horizontal(|ui| {
                            ui.strong(&component.type_name);
                            if ui.small_button("remove").clicked() {
                                call_ui(
                                    &self.bus,
                                    "component.remove",
                                    json!({
                                        "id": entity_id,
                                        "type": component.type_name,
                                    }),
                                );
                            }
                        });
                        for field in &component.fields {
                            draw_inspector_field(
                                ui,
                                &self.bus,
                                &entity_id,
                                &component.type_name,
                                field,
                            );
                        }
                        ui.separator();
                    }
                    ui.horizontal(|ui| {
                        egui::ComboBox::from_id_salt("add_component")
                            .selected_text(&self.add_component)
                            .show_ui(ui, |ui| {
                                for spec in crate::schema::component_specs() {
                                    if view
                                        .components
                                        .iter()
                                        .any(|c| c.present && c.type_name == spec.type_name)
                                    {
                                        continue;
                                    }
                                    ui.selectable_value(
                                        &mut self.add_component,
                                        spec.type_name.to_owned(),
                                        spec.type_name,
                                    );
                                }
                            });
                        if ui.button("Add").clicked() {
                            call_ui(
                                &self.bus,
                                "component.add",
                                json!({
                                    "id": entity_id,
                                    "type": self.add_component,
                                }),
                            );
                        }
                    });
                });
            });
    }

    fn bottom_tabs(&mut self, ctx: &egui::Context) {
        egui::TopBottomPanel::bottom("bottom")
            .default_height(160.0)
            .show(ctx, |ui| {
                ui.horizontal(|ui| {
                    ui.selectable_value(&mut self.bottom, BottomTab::Console, "Console");
                    ui.selectable_value(&mut self.bottom, BottomTab::Feed, "Feed");
                    ui.selectable_value(&mut self.bottom, BottomTab::Session, "Session");
                });
                ui.separator();
                egui::ScrollArea::vertical().show(ui, |ui| match self.bottom {
                    BottomTab::Console => {
                        let log = self.bus.ui().heuristic_log();
                        if log.is_empty() {
                            ui.label("console: editor + player logs (placeholder until M3)");
                        }
                        for line in log {
                            ui.label(line);
                        }
                    }
                    BottomTab::Feed => {
                        let feed = self.bus.ui().feed();
                        if feed.is_empty() {
                            ui.label("activity feed is empty");
                        }
                        for entry in feed {
                            ui.label(format!(
                                "[{}] {}  {}  {}  {:?}",
                                entry.badge.feed_label(),
                                entry.actor,
                                entry.label,
                                entry.revision,
                                entry.entities
                            ));
                        }
                    }
                    BottomTab::Session => {
                        let panel = self.bus.ui().session_panel();
                        for actor in panel.actors {
                            ui.label(format!(
                                "{}  {}  {}  paused={}  cmds={}  connected={}",
                                actor.actor_id,
                                actor.client_name,
                                actor.principal,
                                actor.paused,
                                actor.command_count,
                                actor.connected
                            ));
                        }
                        for pending in panel.pending_confirmations {
                            ui.label(format!(
                                "confirm {}  {}  {}  {}s",
                                pending.confirmation_id,
                                pending.actor_id,
                                pending.summary,
                                pending.expires_in
                            ));
                        }
                    }
                });
            });
    }

    fn viewport(
        &mut self,
        ctx: &egui::Context,
        chrome: &ProjectChrome,
        entities: &[ViewportEntity],
    ) {
        egui::CentralPanel::default().show(ctx, |ui| {
            let avail = ui.available_size();
            let (rect, response) = ui.allocate_exact_size(avail, egui::Sense::click_and_drag());
            let ppp = ui.ctx().pixels_per_point();
            let width_px = rect.width() * ppp;
            let height_px = rect.height() * ppp;
            let snapshot = self.build_snapshot(chrome, entities);

            let pointer_world = response.interact_pointer_pos().map(|pos| {
                let px = (pos.x - rect.min.x) * ppp;
                let py = (pos.y - rect.min.y) * ppp;
                pixel_to_world(px, py, width_px, height_px, &self.view.camera())
            });

            if response.drag_stopped() && self.gizmo_dragging {
                let _ = self.bus.ui().end_gizmo_drag();
                self.gizmo_dragging = false;
                self.gizmo_pointer_start = None;
            } else if self.gizmo_dragging {
                if let Some(world) = pointer_world {
                    self.update_open_gizmo(world);
                }
            } else if response.drag_started() && !self.using_demo {
                if let Some(world) = pointer_world {
                    if self.try_begin_gizmo(entities, world) {
                        self.gizmo_dragging = true;
                        self.gizmo_pointer_start = Some(world);
                    }
                }
            }

            if !self.gizmo_dragging && response.dragged() {
                let delta = response.drag_delta();
                self.view
                    .pan_pixels(delta.x * ppp, delta.y * ppp, width_px, height_px);
            }

            if response.hovered() {
                let scroll = ui.input(|i| i.smooth_scroll_delta.y);
                if scroll.abs() > f32::EPSILON {
                    if let Some(pos) = response.hover_pos() {
                        let px = (pos.x - rect.min.x) * ppp;
                        let py = (pos.y - rect.min.y) * ppp;
                        let world =
                            pixel_to_world(px, py, width_px, height_px, &self.view.camera());
                        let factor = (1.0 - scroll * 0.002).clamp(0.5, 1.5);
                        self.view
                            .zoom_toward(factor, world, px, py, width_px, height_px);
                    }
                }
            }

            if !self.gizmo_dragging && response.clicked() {
                if let Some(pos) = response.interact_pointer_pos() {
                    let px = (pos.x - rect.min.x) * ppp;
                    let py = (pos.y - rect.min.y) * ppp;
                    self.last_pick = pick(&snapshot, &self.atlas, px, py, width_px, height_px);
                    self.view.selected = self.last_pick;
                }
            }

            if self.gpu_ready {
                let callback = ViewportCallback::new(snapshot, width_px, height_px);
                ui.painter().add(callback.into_paint_callback(rect));
            } else {
                ui.painter().text(
                    rect.center(),
                    egui::Align2::CENTER_CENTER,
                    "wgpu viewport unavailable",
                    egui::FontId::proportional(14.0),
                    Color32::WHITE,
                );
            }

            paint_grid(ui.painter(), rect, ppp, &self.view);
            if !self.using_demo {
                paint_colliders(ui.painter(), rect, ppp, &self.view, entities);
                paint_script_badges(ui.painter(), rect, ppp, &self.view, entities);
                paint_selection(ui.painter(), rect, ppp, &self.view, entities);
                paint_gizmo(
                    ui.painter(),
                    rect,
                    ppp,
                    &self.view,
                    entities,
                    self.gizmo_kind,
                );
            }
        });
    }

    fn maybe_fit_document_camera(&mut self, chrome: &ProjectChrome, entities: &[ViewportEntity]) {
        if self.view_fitted || !chrome.open {
            return;
        }
        let Some(cam) = entities.iter().find(|e| e.has_camera) else {
            return;
        };
        self.view.position = [cam.x, cam.y];
        self.view.ortho_height = 16.0;
        self.view_fitted = true;
    }

    fn inject_play_keys(&mut self, ctx: &egui::Context) {
        if self.play_paused || ctx.wants_keyboard_input() {
            return;
        }
        if self.inputmap_cache.is_none() {
            if let Ok(map) = self.bus.ui().call("inputmap.get", json!({})) {
                self.inputmap_cache = Some(map);
            }
        }
        let Some(map) = self.inputmap_cache.as_ref() else {
            return;
        };
        let held = held_from_egui(ctx);
        let actions = actions_from_held(map, &held);
        if actions.is_empty() {
            return;
        }
        let mut params = json!({ "actions": actions });
        if let Some(id) = &self.play_id {
            params["play_id"] = json!(id);
        }
        let _ = self.bus.ui().call("input.inject", params);
    }

    fn read_gizmo_keys(&mut self, ctx: &egui::Context) {
        if self.play_alive {
            return;
        }
        let mut space = false;
        ctx.input(|i| {
            if i.key_pressed(egui::Key::W) || i.key_pressed(egui::Key::Q) {
                self.gizmo_kind = GizmoKind::Move;
            }
            if i.key_pressed(egui::Key::E) {
                self.gizmo_kind = GizmoKind::Rotate;
            }
            if i.key_pressed(egui::Key::R) {
                self.gizmo_kind = GizmoKind::Scale;
            }
            space = i.key_pressed(egui::Key::Space);
        });
        if space {
            if self.play_alive {
                let method = if self.play_paused {
                    "play.resume"
                } else {
                    "play.pause"
                };
                let _ = self.bus.ui().call(method, json!({}));
            } else {
                let _ = self.bus.ui().call(
                    "play.start",
                    json!({
                        "headless": true,
                        "command_id": Ulid::new().to_string(),
                    }),
                );
            }
            self.last_play_poll = Instant::now() - Duration::from_secs(2);
        }
    }

    fn copy_play_to_scene(&mut self) {
        let Ok(stats) = self.bus.ui().call("scene.stats", json!({})) else {
            self.play_banner = Some("copy_to_scene: no open scene".into());
            return;
        };
        let Some(rev) = stats.get("revision").and_then(Value::as_str) else {
            self.play_banner = Some("copy_to_scene: missing document revision".into());
            return;
        };
        let mut params = json!({
            "command_id": Ulid::new().to_string(),
            "expected_revision": rev,
        });
        if let Some(id) = &self.play_id {
            params["play_id"] = json!(id);
        }
        match self.bus.ui().call("runtime.copy_to_scene", params) {
            Ok(_) => self.play_banner = None,
            Err(err) => {
                let code = err.data.as_ref().map(|d| d.app_code.as_str()).unwrap_or("");
                if code == "E_CONFLICT" {
                    self.play_banner = Some(format!(
                        "copy_to_scene conflict (document changed): {}",
                        err.message
                    ));
                } else {
                    self.play_banner = Some(format!("copy_to_scene: {}", err.message));
                }
            }
        }
    }

    fn poll_play(&mut self) {
        if self.last_play_poll.elapsed() < Duration::from_secs(1) {
            return;
        }
        self.last_play_poll = Instant::now();
        let Ok(status) = self.bus.ui().call("play.status", json!({})) else {
            return;
        };
        self.play_alive = status
            .get("alive")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        self.play_paused = status
            .get("paused")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        self.play_hung = status.get("hung").and_then(Value::as_bool).unwrap_or(false);
        self.play_id = status
            .get("play_id")
            .and_then(Value::as_str)
            .map(ToOwned::to_owned);
        if self.play_hung {
            self.play_banner =
                Some("treo? (no play.status for 5s) — Kill does not auto-run".into());
        } else if !self.play_alive {
            self.inputmap_cache = None;
            if let Some(report) = status.get("exit_report") {
                let code = report
                    .get("exit_code")
                    .and_then(Value::as_i64)
                    .unwrap_or(-1);
                self.play_banner = Some(format!("player stopped (exit {code})"));
            }
        } else {
            self.play_banner = None;
        }
    }

    fn try_begin_gizmo(&self, entities: &[ViewportEntity], world: [f32; 2]) -> bool {
        let Some(id) = self.view.selected else {
            return false;
        };
        let Some(entity) = entities.iter().find(|e| e.id == id) else {
            return false;
        };
        if !gizmo_hit(entity, self.gizmo_kind, world, self.view.ortho_height) {
            return false;
        }
        let entity_id = gs_scene::format_entity_id(id);
        self.bus
            .ui()
            .begin_gizmo_drag(entity_id, self.gizmo_kind)
            .is_ok()
    }

    fn update_open_gizmo(&self, world: [f32; 2]) {
        let Some(start_ptr) = self.gizmo_pointer_start else {
            return;
        };
        let Some(info) = self.bus.ui().gizmo_drag() else {
            return;
        };
        let update = match self.gizmo_kind {
            GizmoKind::Move => {
                let mut dx = world[0] - start_ptr[0];
                let mut dy = world[1] - start_ptr[1];
                if self.view.snap_enabled {
                    let snapped = self.view.snap_point([info.start.x + dx, info.start.y + dy]);
                    dx = snapped[0] - info.start.x;
                    dy = snapped[1] - info.start.y;
                }
                GizmoDragUpdate::move_by(dx, dy)
            }
            GizmoKind::Rotate => {
                let a0 = (start_ptr[1] - info.start.y).atan2(start_ptr[0] - info.start.x);
                let a1 = (world[1] - info.start.y).atan2(world[0] - info.start.x);
                GizmoDragUpdate::rotate(info.start.rot + (a1 - a0))
            }
            GizmoKind::Scale => {
                let c = [info.start.x, info.start.y];
                let r0 = dist2(start_ptr, c).max(0.001);
                let r1 = dist2(world, c);
                let factor = r1 / r0;
                GizmoDragUpdate::scale(info.start.sx * factor, info.start.sy * factor)
            }
        };
        let _ = self.bus.ui().update_gizmo_drag(update);
    }
}

fn dist2(a: [f32; 2], b: [f32; 2]) -> f32 {
    let dx = a[0] - b[0];
    let dy = a[1] - b[1];
    dx.hypot(dy)
}

fn call_ui(bus: &BusHandle, method: &str, mut params: Value) {
    if let Some(obj) = params.as_object_mut() {
        if !obj.contains_key("command_id") {
            obj.insert("command_id".into(), json!(Ulid::new().to_string()));
        }
    }
    let _ = bus.ui().call(method, params);
}

fn reparent_via_ui(bus: &BusHandle, src: &str, new_parent: Value) {
    call_ui(
        bus,
        "entity.reparent",
        json!({
            "ids": [src],
            "new_parent": new_parent,
            "keep_world": true,
        }),
    );
}

fn draw_hierarchy_node(
    ui: &mut egui::Ui,
    node: &HierarchyNode,
    selected: &mut Option<u64>,
    drag: &mut Option<String>,
    dropped: &std::cell::RefCell<Option<(String, String)>>,
) {
    let id_num = gs_scene::parse_entity_id(&node.id).ok();
    let is_sel = id_num.is_some_and(|n| *selected == Some(n));
    let label = format!("{}  #{}", node.name, node.order);
    let resp = ui.selectable_label(is_sel, label);
    if resp.clicked() {
        *selected = id_num;
    }
    if resp.drag_started() {
        *drag = Some(node.id.clone());
    }
    if resp.hovered() && ui.input(|i| i.pointer.any_released()) {
        if let Some(src) = drag.take() {
            if src != node.id {
                *dropped.borrow_mut() = Some((src, node.id.clone()));
            }
        }
    }
    if !node.children.is_empty() {
        ui.indent(egui::Id::new(("hier", &node.id)), |ui| {
            for child in &node.children {
                draw_hierarchy_node(ui, child, selected, drag, dropped);
            }
        });
    }
}

/// One widget per [`FieldKind`]. New component types reuse these — no per-type UI.
fn draw_inspector_field(
    ui: &mut egui::Ui,
    bus: &BusHandle,
    entity_id: &str,
    type_name: &str,
    field: &InspectorField,
) {
    let spec = spec_by_type(type_name).and_then(|s| s.fields.iter().find(|f| f.name == field.name));
    ui.horizontal(|ui| {
        ui.label(&field.name);
        match field.kind {
            FieldKind::Bool => {
                let mut v = field.value.as_bool().unwrap_or(false);
                if ui.checkbox(&mut v, "").changed() {
                    patch_field(bus, entity_id, type_name, &field.name, json!(v));
                }
            }
            FieldKind::F32 | FieldKind::I32 | FieldKind::U32 => {
                let mut v = field.value.as_f64().unwrap_or(0.0);
                let mut drag = egui::DragValue::new(&mut v).speed(0.05);
                if let (Some(min), Some(max)) = (field.min, field.max) {
                    drag = drag.range(min..=max);
                }
                if ui.add(drag).changed() {
                    if let Some(spec) = spec {
                        v = clamp_to_schema(spec, v);
                    }
                    let out = match field.kind {
                        FieldKind::I32 => json!(v as i32),
                        FieldKind::U32 => json!(v as u32),
                        _ => json!(v),
                    };
                    patch_field(bus, entity_id, type_name, &field.name, out);
                }
            }
            FieldKind::String | FieldKind::Tags | FieldKind::Enum => {
                let mut text = match field.kind {
                    FieldKind::Tags => field
                        .value
                        .as_array()
                        .map(|a| {
                            a.iter()
                                .filter_map(Value::as_str)
                                .collect::<Vec<_>>()
                                .join(",")
                        })
                        .unwrap_or_default(),
                    _ => field.value.as_str().unwrap_or("").to_owned(),
                };
                if ui.text_edit_singleline(&mut text).lost_focus() {
                    let out = if field.kind == FieldKind::Tags {
                        json!(text
                            .split(',')
                            .map(str::trim)
                            .filter(|s| !s.is_empty())
                            .collect::<Vec<_>>())
                    } else {
                        json!(text)
                    };
                    patch_field(bus, entity_id, type_name, &field.name, out);
                }
            }
            FieldKind::Color | FieldKind::Vec2 => {
                let mut nums = value_as_f32s(&field.value);
                let count = if field.kind == FieldKind::Color { 4 } else { 2 };
                nums.resize(count, 0.0);
                let mut changed = false;
                for n in &mut nums {
                    let mut v = f64::from(*n);
                    if ui.add(egui::DragValue::new(&mut v).speed(0.01)).changed() {
                        if let Some(spec) = spec {
                            v = clamp_to_schema(spec, v);
                        }
                        *n = v as f32;
                        changed = true;
                    }
                }
                if changed {
                    patch_field(bus, entity_id, type_name, &field.name, json!(nums));
                }
            }
            FieldKind::Asset => {
                let id = field
                    .value
                    .get("$asset")
                    .and_then(Value::as_str)
                    .unwrap_or("—");
                ui.label(id);
                if let Some(preview) = &field.preview {
                    ui.label(format!(
                        "{}×{} {}",
                        preview.width, preview.height, preview.kind
                    ));
                }
            }
            FieldKind::Object | FieldKind::Array => {
                let compact = field.value.to_string();
                ui.label(RichText::new(compact).small());
            }
        }
    });
}

fn value_as_f32s(value: &Value) -> Vec<f32> {
    value
        .as_array()
        .map(|a| {
            a.iter()
                .filter_map(|v| v.as_f64().map(|n| n as f32))
                .collect()
        })
        .unwrap_or_default()
}

fn patch_field(bus: &BusHandle, entity_id: &str, type_name: &str, field: &str, value: Value) {
    call_ui(
        bus,
        "component.set",
        json!({
            "id": entity_id,
            "type": type_name,
            "patch": { field: value },
        }),
    );
}

fn pause_all_agents(bus: &BusHandle) {
    let panel = bus.ui().session_panel();
    for actor in panel.actors {
        if actor.principal == "human_ui" || actor.paused {
            continue;
        }
        let _ = bus
            .ui()
            .call("session.pause_actor", json!({ "actor_id": actor.actor_id }));
    }
}
