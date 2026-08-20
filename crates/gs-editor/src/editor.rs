//! In-process editor authority: session, capabilities, confirmation, feed.

use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};
use std::path::PathBuf;
use std::sync::mpsc::SyncSender;
use std::time::{Duration, Instant};

use gs_protocol::{Notification, RpcError, PROTOCOL_VER};
use gs_registry::{Capability, SideEffect};
use gs_scene::{to_canonical_string, Ack, Command, DispatchRequest, Session, DEFAULT_SCENE_ID};
use serde_json::{json, Map, Value};
use sha2::{Digest, Sha256};
use ulid::Ulid;

use crate::analyze::TypeCheck;
use crate::artifacts::is_artifact_method;
use crate::assets::AssetCatalog;
use crate::build::{build_is_mutating, is_build_method, BuildRecord};
use crate::error::{
    app_err, budget, conflict, invalid_params, locked, method_not_found, not_implemented, paused,
    scene_err, unauthorized,
};
use crate::gizmo::{
    agent_touches_locked, apply_preview, GizmoDrag, GizmoDragUpdate, GizmoKind, GizmoSession,
};
use crate::hierarchy::{build_hierarchy, HierarchyNode};
use crate::inspector::{build_inspector, entity_components_json, InspectorView};
use crate::play::{
    is_input_method, is_judge_method, is_obs_method, is_play_method, is_runtime_method,
    play_is_mutating, play_topic, PlayBridge,
};
use crate::schema::{default_component_value, registry_json};
use crate::scripts::{
    is_script_editor_layer, is_script_method, is_script_ui_only, ScriptBuffer, ScriptConflict,
    EVENT_SCRIPT,
};
use crate::snapshot::{collect_viewport_entities, ProjectChrome, ViewportEntity};
use crate::types::{ActorInfo, Badge, FeedEntry, PendingConfirmation, Principal, SessionPanel};

pub const HUMAN_UI_ID: &str = "act_01";
const CONFIRM_SECS: u64 = 120;
const DESTROY_D_THRESHOLD: usize = 20;
const SALAMI_MIN: usize = 16;
const SALAMI_HITS: usize = 3;
const BUDGET_PER_MIN: usize = 200;
const EVENT_SCENE: &str = "event.scene_changed";
const EVENT_SESSION: &str = "event.session_changed";
const EVENT_CONFIRM: &str = "event.confirmation_request";
const EVENT_ASSET: &str = "event.asset_changed";
const EVENT_PLAY: &str = "event.play_changed";

#[derive(Clone, Debug)]
pub enum Outbound {
    Response(gs_protocol::Response),
    Notification(Notification),
}

#[derive(Clone, Copy, Debug)]
pub struct CallContext<'a> {
    pub actor_id: &'a str,
    pub principal: Principal,
    pub skip_confirm: bool,
}

pub(crate) struct Actor {
    actor_id: String,
    client_name: String,
    pub(crate) principal: Principal,
    paused: bool,
    revoked: bool,
    pub(crate) command_count: u64,
    connected: bool,
}

struct GrantedCap {
    cap: String,
    scope: String,
    expiry: Option<Instant>,
    max_use: Option<u32>,
    used: u32,
}

struct HeldCommand {
    confirmation_id: String,
    actor_id: String,
    method: String,
    params: Value,
    params_hash: String,
    base_revision: String,
    created: Instant,
    summary: String,
}

struct Subscriber {
    topics: BTreeSet<String>,
    tx: SyncSender<Outbound>,
}

pub struct Editor {
    pub(crate) session: Option<Session>,
    pub(crate) project_path: Option<PathBuf>,
    pub(crate) runtime_root: PathBuf,
    project_name: Option<String>,
    next_actor: u32,
    pub(crate) actors: BTreeMap<String, Actor>,
    caps: HashMap<String, Vec<GrantedCap>>,
    pending: HashMap<String, HeldCommand>,
    pending_by_actor: HashMap<String, String>,
    pub(crate) feed: Vec<FeedEntry>,
    pub(crate) play: Option<PlayBridge>,
    notifications: Vec<Notification>,
    subscribers: HashMap<String, Subscriber>,
    salami: HashMap<String, VecDeque<Instant>>,
    budget: HashMap<String, VecDeque<Instant>>,
    budget_hits: HashMap<String, VecDeque<Instant>>,
    heuristic_log: Vec<String>,
    gizmo: Option<GizmoSession>,
    assets: AssetCatalog,
    pub(crate) script_buffers: BTreeMap<String, ScriptBuffer>,
    pub(crate) script_conflicts: BTreeMap<String, ScriptConflict>,
    pub(crate) analyze_bin: Option<Option<PathBuf>>,
    pub(crate) type_check: TypeCheck,
    pub(crate) builds: HashMap<String, BuildRecord>,
    pub(crate) build_by_command: HashMap<String, String>,
    /// Last successful `play.start` JSON per `command_id`. In-memory only — I11 WAL is still incomplete.
    pub(crate) play_start_by_command: HashMap<String, Value>,
    /// Last `judge.run_test` result (ok or error) per `command_id`. In-memory only — I11 WAL is still incomplete.
    pub(crate) judge_run_by_command: HashMap<String, Result<Value, RpcError>>,
}

impl Editor {
    pub fn new(runtime_root: PathBuf) -> Self {
        let mut actors = BTreeMap::new();
        actors.insert(
            HUMAN_UI_ID.to_owned(),
            Actor {
                actor_id: HUMAN_UI_ID.to_owned(),
                client_name: "editor".into(),
                principal: Principal::HumanUi,
                paused: false,
                revoked: false,
                command_count: 0,
                connected: true,
            },
        );
        let mut editor = Self {
            session: None,
            project_path: None,
            runtime_root,
            project_name: None,
            next_actor: 2,
            actors,
            caps: HashMap::new(),
            pending: HashMap::new(),
            pending_by_actor: HashMap::new(),
            feed: Vec::new(),
            play: None,
            notifications: Vec::new(),
            subscribers: HashMap::new(),
            salami: HashMap::new(),
            budget: HashMap::new(),
            budget_hits: HashMap::new(),
            heuristic_log: Vec::new(),
            gizmo: None,
            assets: AssetCatalog::default(),
            script_buffers: BTreeMap::new(),
            script_conflicts: BTreeMap::new(),
            analyze_bin: None,
            type_check: TypeCheck::Off,
            builds: HashMap::new(),
            build_by_command: HashMap::new(),
            play_start_by_command: HashMap::new(),
            judge_run_by_command: HashMap::new(),
        };
        let root = editor.runtime_root.clone();
        editor.load_build_persist(&root);
        editor
    }

    pub fn register_agent(&mut self, client_name: String, tx: SyncSender<Outbound>) -> Value {
        let actor_id = format!("act_{:02}", self.next_actor);
        self.next_actor = self.next_actor.saturating_add(1);
        self.actors.insert(
            actor_id.clone(),
            Actor {
                actor_id: actor_id.clone(),
                client_name: client_name.clone(),
                principal: Principal::Agent,
                paused: false,
                revoked: false,
                command_count: 0,
                connected: true,
            },
        );
        self.subscribers.insert(
            actor_id.clone(),
            Subscriber {
                topics: BTreeSet::new(),
                tx,
            },
        );
        self.emit_session(&format!("agent {client_name} connected as {actor_id}"));
        hello_result(&actor_id, Principal::Agent)
    }

    pub fn disconnect_agent(&mut self, actor_id: &str) {
        if let Some(actor) = self.actors.get_mut(actor_id) {
            actor.connected = false;
        }
        self.subscribers.remove(actor_id);
        if let Some(session) = &mut self.session {
            session.release_locks_for_actor(actor_id);
        }
    }

    pub fn is_revoked(&self, actor_id: &str) -> bool {
        self.actors.get(actor_id).is_some_and(|a| a.revoked)
    }

    pub fn feed(&self) -> &[FeedEntry] {
        &self.feed
    }

    pub fn notifications(&self) -> &[Notification] {
        &self.notifications
    }

    pub fn heuristic_log(&self) -> &[String] {
        &self.heuristic_log
    }

    pub(crate) fn gizmo_drag(&self) -> Option<GizmoDrag> {
        self.gizmo.as_ref().map(GizmoSession::info)
    }

    pub(crate) fn viewport_entities_with_preview(&self) -> Vec<ViewportEntity> {
        let mut entities = self
            .session
            .as_ref()
            .map(|session| collect_viewport_entities(session.document()))
            .unwrap_or_default();
        if let Some(gizmo) = &self.gizmo {
            for entity in &mut entities {
                if entity.id == gizmo.entity_num {
                    entity.x = gizmo.preview.x;
                    entity.y = gizmo.preview.y;
                    entity.rot = gizmo.preview.rot;
                    entity.sx = gizmo.preview.sx;
                    entity.sy = gizmo.preview.sy;
                }
            }
        }
        entities
    }

    pub(crate) fn begin_gizmo_drag(
        &mut self,
        entity_id: &str,
        kind: GizmoKind,
    ) -> Result<(), RpcError> {
        let n = gs_scene::parse_entity_id(entity_id)
            .map_err(|_| invalid_params("gizmo entity_id must be e_<digits>"))?;
        let session = self.session_ref()?;
        let entity = session
            .document()
            .entity(n)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("not found: {entity_id}")))?;
        let start = entity
            .transform
            .clone()
            .unwrap_or_else(gs_scene::Transform2D::identity);
        self.gizmo = Some(GizmoSession {
            entity_id: gs_scene::format_entity_id(n),
            entity_num: n,
            kind,
            owner: HUMAN_UI_ID.to_owned(),
            preview: start.clone(),
            start,
            last_touch: Instant::now(),
        });
        Ok(())
    }

    pub(crate) fn update_gizmo_drag(&mut self, update: GizmoDragUpdate) -> Result<(), RpcError> {
        let Some(session) = self.gizmo.as_mut() else {
            return Err(invalid_params("no gizmo drag is active"));
        };
        let preview =
            apply_preview(session.kind, &session.start, &update).map_err(invalid_params)?;
        session.preview = preview;
        session.touch();
        Ok(())
    }

    pub(crate) fn end_gizmo_drag(&mut self, ctx: CallContext<'_>) -> Result<Value, RpcError> {
        let session = self
            .gizmo
            .take()
            .ok_or_else(|| invalid_params("no gizmo drag is active"))?;
        let command = Command::set_transform(session.entity_id.clone(), session.preview.clone());
        let command_id = Ulid::new().to_string();
        let result = self.dispatch_request(
            ctx,
            command_id,
            None,
            vec![command],
            session.kind.feed_label(),
        );
        if result.is_err() {
            self.gizmo = Some(session);
        }
        result
    }

    fn gizmo_lock_error(
        &self,
        principal: Principal,
        method: &str,
        params: &Value,
    ) -> Option<RpcError> {
        if principal != Principal::Agent {
            return None;
        }
        let gizmo = self.gizmo.as_ref()?;
        if !gizmo.lock_held() {
            return None;
        }
        if !agent_touches_locked(method, params, gizmo.entity_num) {
            return None;
        }
        Some(locked(&gizmo.owner, "gizmo drag"))
    }

    pub(crate) fn hierarchy_tree(&self) -> Vec<HierarchyNode> {
        self.session
            .as_ref()
            .map(|session| build_hierarchy(session.document()))
            .unwrap_or_default()
    }

    pub(crate) fn inspector_view(&self, entity_id: &str) -> Result<InspectorView, RpcError> {
        let session = self.session_ref()?;
        let n = gs_scene::parse_entity_id(entity_id).map_err(scene_err)?;
        let entity = session
            .document()
            .entity(n)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("not found: {entity_id}")))?;
        Ok(build_inspector(
            entity_id,
            &session.document().revision_label(),
            entity,
            &self.assets,
        ))
    }

    pub(crate) fn project_chrome(&self) -> ProjectChrome {
        match &self.session {
            Some(session) => ProjectChrome {
                open: true,
                name: self.project_name.clone(),
                scene_id: Some(session.document().scene_id.clone()),
                revision: Some(session.document().revision_label()),
                entity_count: session.document().entity_count(),
                wal_seq: session.last_ack().seq,
                type_check: self.type_check_label().to_owned(),
            },
            None => ProjectChrome {
                open: false,
                name: self.project_name.clone(),
                scene_id: None,
                revision: None,
                entity_count: 0,
                wal_seq: 0,
                type_check: self.type_check_label().to_owned(),
            },
        }
    }

    pub fn session_panel(&self) -> SessionPanel {
        let now = Instant::now();
        let actors = self
            .actors
            .values()
            .map(|a| ActorInfo {
                actor_id: a.actor_id.clone(),
                client_name: a.client_name.clone(),
                principal: a.principal.as_str().to_owned(),
                paused: a.paused,
                command_count: a.command_count,
                connected: a.connected,
            })
            .collect();
        let pending_confirmations = self
            .pending
            .values()
            .map(|h| PendingConfirmation {
                confirmation_id: h.confirmation_id.clone(),
                actor_id: h.actor_id.clone(),
                method: h.method.clone(),
                summary: h.summary.clone(),
                expires_in: remaining_secs(h.created, now),
            })
            .collect();
        SessionPanel {
            actors,
            pending_confirmations,
        }
    }

    pub fn handle(
        &mut self,
        ctx: CallContext<'_>,
        method: &str,
        params: Value,
    ) -> Result<Value, RpcError> {
        let params = normalize_params(params)?;
        if method != "session.hello" {
            if let Some(actor) = self.actors.get(ctx.actor_id) {
                if actor.revoked {
                    return Err(unauthorized("actor has been revoked"));
                }
            }
        }

        if method == "session.hello" {
            return Ok(hello_result(ctx.actor_id, ctx.principal));
        }

        let spec = gs_registry::get(method);
        if spec.is_none() && !is_editor_layer_method(method) {
            return Err(method_not_found(method));
        }
        if (spec.is_some_and(|s| s.is_ui_only()) || is_script_ui_only(method))
            && ctx.principal != Principal::HumanUi
        {
            return Err(unauthorized(format!(
                "{method} is UI-only; agent principal cannot call it"
            )));
        }
        if is_unimplemented(method) {
            return Err(not_implemented(method));
        }

        let mutating = is_mutating(method, spec);
        if mutating && !ctx.skip_confirm && self.is_paused(ctx.actor_id) {
            return Err(paused());
        }

        if mutating && !ctx.skip_confirm {
            let cost = mutating_cost(method, &params);
            if let Some(ms) = self.check_budget(ctx.actor_id, cost) {
                return Err(budget(ms));
            }
        }

        if let Some(err) = self.gizmo_lock_error(ctx.principal, method, &params) {
            return Err(err);
        }

        if !ctx.skip_confirm {
            if let Some(summary) =
                self.needs_confirmation(ctx.actor_id, ctx.principal, method, &params)
            {
                return self.hold_confirmation(ctx.actor_id, method, params, summary);
            }
        }

        self.execute(ctx, method, params)
    }

    fn execute(
        &mut self,
        ctx: CallContext<'_>,
        method: &str,
        params: Value,
    ) -> Result<Value, RpcError> {
        match method {
            "session.ping" => self.session_ping(),
            "session.goodbye" => self.session_goodbye(ctx.actor_id),
            "session.subscribe" => self.session_subscribe(ctx.actor_id, &params),
            "session.list" => Ok(json!({ "actors": self.session_panel().actors })),
            "session.pause_actor" => self.pause_actor(&params, true),
            "session.resume_actor" => self.pause_actor(&params, false),
            "session.revoke" => self.revoke_actor(&params),
            "capability.grant" => self.cap_grant(&params),
            "capability.revoke" => self.cap_revoke(&params),
            "capability.list" => self.cap_list(&params),
            "confirmation.approve" => self.confirm_approve(&params),
            "confirmation.deny" => self.confirm_deny(&params),
            "project.create" => self.project_create(&params),
            "project.open" => self.project_open(&params),
            "project.info" => self.project_info(),
            "project.save_all" => self.project_save(ctx),
            "project.settings_get" => self.settings_get(),
            "project.settings_set" => self.dispatch_one(ctx, method, params),
            "scene.stats" => self.scene_stats(&params),
            "scene.dump" => self.scene_dump(&params),
            "entity.find" => self.entity_find(&params),
            "inputmap.get" => self.inputmap_get(),
            "inputmap.set" => self.dispatch_one(ctx, method, params),
            "entity.spawn"
            | "entity.destroy"
            | "entity.reparent"
            | "entity.set_order"
            | "entity.rename"
            | "entity.duplicate"
            | "entity.lock"
            | "component.set"
            | "tilemap.set_cells"
            | "tilemap.fill_rect"
            | "blueprint.create"
            | "blueprint.instantiate" => self.dispatch_one(ctx, method, params),
            "entity.unlock" => self.entity_unlock(ctx, params),
            "script.create" | "script.set_source" | "script.ingest_external" => {
                self.script_mutating(ctx, method, params)
            }
            "script.get_source" => self.script_get_source(&params),
            "script.diagnostics" => self.script_diagnostics(&params),
            "script.reload" => self.script_reload(&params),
            "script.buffer_set" => self.script_buffer_set(&params),
            "script.conflicts" => self.script_list_conflicts(),
            "script.conflict_resolve" => self.script_conflict_resolve(ctx, &params),
            "component.add" => self.component_add(ctx, params),
            "component.remove" => self.component_remove(ctx, params),
            "component.get" => self.component_get(&params),
            "component.registry" => Ok(registry_json()),
            "asset.import" => self.asset_import(ctx, &params),
            "asset.list" => self.asset_list(&params),
            "transaction.execute" => self.transaction_execute(ctx, params),
            "undo.perform" => self.undo_perform(ctx),
            "undo.revert_own" => self.undo_revert_own(ctx, &params),
            "play.start" => self.play_start(ctx, params),
            "play.stop" => self.play_stop(&params),
            "play.status" => self.play_status(),
            "play.pause" => self.play_pause(),
            "play.resume" => self.play_resume(),
            "play.step_frames" => self.play_step_frames(&params),
            "play.set_timescale" => self.play_set_timescale(&params),
            "input.inject" => self.input_inject(&params),
            "obs.events" => self.obs_events(&params),
            "obs.world_dump" => self.obs_world_dump(&params),
            "obs.logs_tail" => self.obs_logs_tail(&params),
            "obs.perf" => self.obs_perf(&params),
            "obs.screenshot" => self.obs_screenshot(&params),
            "judge.run_until_event" => self.judge_run_until_event(&params),
            "judge.wait_event" => self.judge_wait_event(&params),
            "judge.assert_world" => self.judge_assert_world(&params),
            "judge.assert_perf" => self.judge_assert_perf(&params),
            "judge.assert_screenshot" => self.judge_assert_screenshot(&params),
            "judge.run_test" => self.judge_run_test(ctx, params),
            "artifact.list" => self.artifact_list(&params),
            "artifact.get" => self.artifact_get(&params),
            "artifact.gc" => self.artifact_gc(params),
            "build.game" => self.build_game(ctx, params),
            "build.status" => self.build_status(&params),
            "build.cancel" => self.build_cancel(params),
            "runtime.copy_to_scene" => self.runtime_copy_to_scene(ctx, params),
            other => Err(not_implemented(other)),
        }
    }

    fn session_ping(&self) -> Result<Value, RpcError> {
        let mut out = json!({ "ok": true });
        if let Some(session) = &self.session {
            out["revision"] = json!(session.document().revision_label());
        }
        Ok(out)
    }

    fn session_goodbye(&mut self, actor_id: &str) -> Result<Value, RpcError> {
        self.disconnect_agent(actor_id);
        self.emit_session(&format!("{actor_id} goodbye"));
        Ok(json!({ "ok": true }))
    }

    fn session_subscribe(&mut self, actor_id: &str, params: &Value) -> Result<Value, RpcError> {
        let topics = string_list(params, "topics")?;
        let allowed = [
            "scene",
            "session",
            "job",
            "play",
            "script",
            "asset",
            "confirmation",
        ];
        for topic in &topics {
            if !allowed.contains(&topic.as_str()) {
                return Err(invalid_params(format!("unknown topic {topic}")));
            }
        }
        if let Some(sub) = self.subscribers.get_mut(actor_id) {
            sub.topics = topics.into_iter().collect();
        }
        Ok(json!({ "ok": true }))
    }

    fn pause_actor(&mut self, params: &Value, paused: bool) -> Result<Value, RpcError> {
        let actor_id = string_field(params, "actor_id")?;
        let actor = self
            .actors
            .get_mut(&actor_id)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("unknown actor {actor_id}")))?;
        if actor.principal == Principal::HumanUi {
            return Err(unauthorized("cannot pause or resume human_ui"));
        }
        actor.paused = paused;
        let label = if paused { "paused" } else { "resumed" };
        self.emit_session(&format!("{actor_id} {label}"));
        Ok(json!({ "ok": true, "actor_id": actor_id, "paused": paused }))
    }

    fn revoke_actor(&mut self, params: &Value) -> Result<Value, RpcError> {
        let actor_id = string_field(params, "actor_id")?;
        let actor = self
            .actors
            .get_mut(&actor_id)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("unknown actor {actor_id}")))?;
        if actor.principal == Principal::HumanUi {
            return Err(unauthorized("cannot revoke human_ui"));
        }
        actor.revoked = true;
        actor.paused = true;
        actor.connected = false;
        self.subscribers.remove(&actor_id);
        if let Some(old) = self.pending_by_actor.remove(&actor_id) {
            self.pending.remove(&old);
        }
        self.emit_session(&format!("{actor_id} revoked"));
        Ok(json!({ "ok": true, "actor_id": actor_id }))
    }

    fn cap_grant(&mut self, params: &Value) -> Result<Value, RpcError> {
        let actor_id = string_field(params, "actor_id")?;
        if !self.actors.contains_key(&actor_id) {
            return Err(app_err("E_NOT_FOUND", format!("unknown actor {actor_id}")));
        }
        let cap = string_field(params, "cap")?;
        let scope = optional_string(params, "scope").unwrap_or_else(|| cap.clone());
        let max_use = optional_u32(params, "max_use")?;
        let expiry = optional_expiry(params)?;
        self.caps
            .entry(actor_id.clone())
            .or_default()
            .push(GrantedCap {
                cap: cap.clone(),
                scope,
                expiry,
                max_use,
                used: 0,
            });
        self.emit_session(&format!("granted {cap} to {actor_id}"));
        Ok(json!({ "ok": true }))
    }

    fn cap_revoke(&mut self, params: &Value) -> Result<Value, RpcError> {
        let actor_id = string_field(params, "actor_id")?;
        let cap = string_field(params, "cap")?;
        if let Some(list) = self.caps.get_mut(&actor_id) {
            list.retain(|c| c.cap != cap);
        }
        self.emit_session(&format!("revoked {cap} from {actor_id}"));
        Ok(json!({ "ok": true }))
    }

    fn cap_list(&self, params: &Value) -> Result<Value, RpcError> {
        let actor_id = optional_string(params, "actor_id")
            .ok_or_else(|| invalid_params("missing actor_id"))?;
        if !self.actors.contains_key(&actor_id) {
            return Err(app_err("E_NOT_FOUND", format!("unknown actor {actor_id}")));
        }
        let now = Instant::now();
        let caps: Vec<Value> = self
            .caps
            .get(&actor_id)
            .into_iter()
            .flatten()
            .filter(|c| c.expiry.is_none_or(|e| e > now))
            .map(|c| {
                json!({
                    "cap": c.cap,
                    "scope": c.scope,
                    "max_use": c.max_use,
                    "used": c.used,
                })
            })
            .collect();
        Ok(json!({ "actor_id": actor_id, "capabilities": caps }))
    }

    fn confirm_approve(&mut self, params: &Value) -> Result<Value, RpcError> {
        let confirmation_id = string_field(params, "confirmation_id")?;
        let held = self
            .pending
            .remove(&confirmation_id)
            .ok_or_else(|| app_err("E_NOT_FOUND", "confirmation_id is invalid or already used"))?;
        if self.pending_by_actor.get(&held.actor_id) == Some(&confirmation_id) {
            self.pending_by_actor.remove(&held.actor_id);
        }
        if held.created.elapsed() > Duration::from_secs(CONFIRM_SECS) {
            return Err(app_err("E_VALIDATION", "confirmation expired"));
        }
        let current = self.current_revision();
        if held.base_revision != current {
            return Err(conflict(format!(
                "confirmation bound to revision {}, current {current}",
                held.base_revision
            )));
        }
        let hash = params_hash(&held.params);
        if hash != held.params_hash {
            return Err(app_err("E_VALIDATION", "confirmation params hash mismatch"));
        }
        let actor_id = held.actor_id.clone();
        let ctx = CallContext {
            actor_id: &actor_id,
            principal: Principal::Agent,
            skip_confirm: true,
        };
        self.execute(ctx, &held.method, held.params)
    }

    fn confirm_deny(&mut self, params: &Value) -> Result<Value, RpcError> {
        let confirmation_id = string_field(params, "confirmation_id")?;
        let held = self
            .pending
            .remove(&confirmation_id)
            .ok_or_else(|| app_err("E_NOT_FOUND", "confirmation_id is invalid or already used"))?;
        if self.pending_by_actor.get(&held.actor_id) == Some(&confirmation_id) {
            self.pending_by_actor.remove(&held.actor_id);
        }
        Ok(json!({ "ok": true, "denied": confirmation_id }))
    }

    fn project_create(&mut self, params: &Value) -> Result<Value, RpcError> {
        if self.session.is_some() {
            return Err(app_err(
                "E_PROJECT_OPEN",
                "a project is already open in this window",
            ));
        }
        let path = PathBuf::from(string_field(params, "path")?);
        let name = optional_string(params, "name");
        let session = Session::open(&path).map_err(scene_err)?;
        self.project_name =
            name.or_else(|| path.file_name().map(|s| s.to_string_lossy().into_owned()));
        self.project_path = Some(path.clone());
        self.session = Some(session);
        self.load_build_persist(&path);
        self.reload_assets();
        self.arm_script_watcher();
        self.ensure_analyze_resolved();
        self.emit_session("project created");
        self.project_info()
    }

    fn project_open(&mut self, params: &Value) -> Result<Value, RpcError> {
        if self.session.is_some() {
            return Err(app_err(
                "E_PROJECT_OPEN",
                "a project is already open in this window",
            ));
        }
        let path = PathBuf::from(string_field(params, "path")?);
        let session = Session::open(&path).map_err(scene_err)?;
        self.project_name = path.file_name().map(|s| s.to_string_lossy().into_owned());
        self.project_path = Some(path.clone());
        self.session = Some(session);
        self.load_build_persist(&path);
        self.reload_assets();
        self.arm_script_watcher();
        self.ensure_analyze_resolved();
        self.emit_session("project opened");
        self.project_info()
    }

    fn project_info(&self) -> Result<Value, RpcError> {
        let session = self
            .session
            .as_ref()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))?;
        Ok(json!({
            "path": self.project_path.as_ref().map(|p| p.to_string_lossy().into_owned()),
            "name": self.project_name,
            "revision": session.document().revision_label(),
            "open": true,
        }))
    }

    fn project_save(&mut self, ctx: CallContext<'_>) -> Result<Value, RpcError> {
        let session = self.session_mut()?;
        session.save().map_err(scene_err)?;
        if let Some(actor) = self.actors.get_mut(ctx.actor_id) {
            actor.command_count = actor.command_count.saturating_add(1);
        }
        Ok(json!({ "ok": true }))
    }

    fn scene_stats(&self, params: &Value) -> Result<Value, RpcError> {
        let session = self
            .session
            .as_ref()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))?;
        if let Some(scene_id) = optional_string(params, "scene_id") {
            if scene_id != session.document().scene_id {
                return Err(app_err("E_NOT_FOUND", format!("unknown scene {scene_id}")));
            }
        }
        let doc = session.document();
        Ok(json!({
            "scene_id": doc.scene_id,
            "entity_count": doc.entity_count(),
            "revision": doc.revision_label(),
        }))
    }

    fn scene_dump(&self, params: &Value) -> Result<Value, RpcError> {
        let session = self.session_ref()?;
        if let Some(scene_id) = optional_string(params, "scene_id") {
            if scene_id != session.document().scene_id {
                return Err(app_err("E_NOT_FOUND", format!("unknown scene {scene_id}")));
            }
        }
        serde_json::from_slice(&session.canonical_scene_bytes())
            .map_err(|e| app_err("E_IO", e.to_string()))
    }

    fn entity_find(&self, params: &Value) -> Result<Value, RpcError> {
        let session = self.session_ref()?;
        let name = optional_string(params, "name");
        let tag = optional_string(params, "tag");
        let mut ids = Vec::new();
        for entity in session.document().scene.entities.values() {
            if let Some(ref want) = name {
                let got = entity.name.as_ref().map(|n| n.value.as_str());
                if got != Some(want.as_str()) {
                    continue;
                }
            }
            if let Some(ref want) = tag {
                let has = entity
                    .tags
                    .as_ref()
                    .is_some_and(|t| t.values.iter().any(|v| v == want));
                if !has {
                    continue;
                }
            }
            ids.push(entity.id_str());
        }
        Ok(json!({ "ids": ids }))
    }

    fn inputmap_get(&self) -> Result<Value, RpcError> {
        let session = self.session_ref()?;
        session.read_inputmap().map_err(scene_err)
    }

    fn settings_get(&self) -> Result<Value, RpcError> {
        let session = self.session_ref()?;
        Ok(json!({
            "settings": session.read_project_settings(),
            "revision": session.document().revision_label(),
        }))
    }

    fn entity_unlock(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        if let Some(map) = params.as_object_mut() {
            map.insert("force".into(), json!(ctx.principal == Principal::HumanUi));
        }
        self.dispatch_one(ctx, "entity.unlock", params)
    }

    pub(crate) fn dispatch_one(
        &mut self,
        ctx: CallContext<'_>,
        method: &str,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        let expected = take_expected_revision(&mut params);
        strip_identity(&mut params);
        if method == "entity.spawn" {
            ensure_scene_id(&mut params);
        }
        if method == "entity.reparent" {
            ensure_reparent_keep_world(&mut params);
        }
        let command = Command::new(method, params);
        self.dispatch_request(ctx, command_id, expected, vec![command], method)
    }

    fn transaction_execute(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        let expected = take_expected_revision(&mut params);
        let dry_run = params
            .get("dry_run")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let label =
            optional_string(&params, "label").unwrap_or_else(|| "transaction.execute".into());
        let raw = params
            .get("commands")
            .and_then(Value::as_array)
            .ok_or_else(|| invalid_params("transaction.execute requires commands[]"))?;
        if raw.is_empty() {
            return Err(invalid_params(
                "transaction.execute commands must be non-empty",
            ));
        }
        if raw.len() > 200 {
            return Err(invalid_params(
                "transaction.execute allows at most 200 commands",
            ));
        }
        let mut commands = Vec::with_capacity(raw.len());
        for item in raw {
            let method = item
                .get("method")
                .and_then(Value::as_str)
                .ok_or_else(|| invalid_params("inner command missing method"))?;
            if is_unimplemented(method) {
                return Err(not_implemented(method));
            }
            if method == "project.settings_get" {
                return Err(invalid_params(
                    "cannot embed project.settings_get in a transaction",
                ));
            }
            if is_build_method(method) {
                return Err(invalid_params(format!(
                    "cannot embed {method} in a transaction"
                )));
            }
            if gs_registry::get(method).is_some_and(|s| s.is_ui_only()) || is_script_ui_only(method)
            {
                return Err(unauthorized(format!(
                    "cannot embed UI-only method {method} in a transaction"
                )));
            }
            let mut inner = item
                .get("params")
                .cloned()
                .unwrap_or(Value::Object(Map::new()));
            strip_identity(&mut inner);
            if method == "entity.spawn" {
                ensure_scene_id(&mut inner);
            }
            if method == "entity.reparent" {
                ensure_reparent_keep_world(&mut inner);
            }
            commands.push(Command::new(method, inner));
        }
        if dry_run {
            let session = self.session_ref()?;
            session.document().plan_txn(&commands).map_err(scene_err)?;
            return Ok(json!({
                "dry_run": true,
                "ok": true,
                "revision": session.document().revision_label(),
            }));
        }
        self.dispatch_request(ctx, command_id, expected, commands, &label)
    }

    fn undo_perform(&mut self, ctx: CallContext<'_>) -> Result<Value, RpcError> {
        let command_id = Ulid::new().to_string();
        let actor_id = ctx.actor_id.to_owned();
        let ack = {
            let session = self.session_mut()?;
            session
                .undo_last(&command_id, &actor_id)
                .map_err(scene_err)?
        };
        self.after_commit(ctx, "undo.perform", &ack, &[]);
        self.refresh_known_clean_scripts();
        Ok(ack_json(&ack))
    }

    fn undo_revert_own(&mut self, ctx: CallContext<'_>, params: &Value) -> Result<Value, RpcError> {
        let mut params = params.clone();
        let command_id = take_command_id(&mut params)?;
        let txn_id = string_field(&params, "txn_id")?;
        let actor_id = ctx.actor_id.to_owned();
        let ack = {
            let session = self.session_mut()?;
            session
                .revert_own(&command_id, &actor_id, &txn_id)
                .map_err(scene_err)?
        };
        self.after_commit(ctx, "undo.revert_own", &ack, &[]);
        self.refresh_known_clean_scripts();
        Ok(ack_json(&ack))
    }

    pub(crate) fn dispatch_request(
        &mut self,
        ctx: CallContext<'_>,
        command_id: String,
        expected: Option<String>,
        commands: Vec<Command>,
        summary: &str,
    ) -> Result<Value, RpcError> {
        let actor_id = ctx.actor_id.to_owned();
        let entities = entity_ids_from(&commands);
        let mut request = DispatchRequest::transaction(command_id, actor_id, commands);
        if let Some(rev) = expected {
            request = request.with_expected_revision(rev);
        }
        let ack = {
            let session = self.session_mut()?;
            session.dispatch(request).map_err(scene_err)?
        };
        self.after_commit(ctx, summary, &ack, &entities);
        Ok(ack_json(&ack))
    }

    fn after_commit(
        &mut self,
        ctx: CallContext<'_>,
        summary: &str,
        ack: &Ack,
        extra_entities: &[String],
    ) {
        if let Some(actor) = self.actors.get_mut(ctx.actor_id) {
            actor.command_count = actor.command_count.saturating_add(1);
        }
        let mut entities = ack.spawned_ids.clone();
        for id in extra_entities {
            if !entities.contains(id) {
                entities.push(id.clone());
            }
        }
        let badge = self
            .actors
            .get(ctx.actor_id)
            .map(|a| a.principal.badge())
            .unwrap_or(Badge::System);
        self.feed.push(FeedEntry {
            badge,
            actor: ctx.actor_id.to_owned(),
            label: summary.to_owned(),
            entities: entities.clone(),
            revision: ack.revision.clone(),
        });
        self.emit(Notification::new(
            EVENT_SCENE,
            json!({
                "seq": ack.seq,
                "actor_id": ctx.actor_id,
                "txn_id": ack.txn_id,
                "summary": summary,
                "entities": entities,
                "revision": ack.revision,
            }),
        ));
    }

    fn component_get(&self, params: &Value) -> Result<Value, RpcError> {
        let session = self.session_ref()?;
        let id = string_field(params, "id")?;
        let n = gs_scene::parse_entity_id(&id).map_err(scene_err)?;
        let entity = session
            .document()
            .entity(n)
            .ok_or_else(|| app_err("E_NOT_FOUND", format!("not found: {id}")))?;
        let revision = session.document().revision_label();
        let type_name = optional_string(params, "type");
        let components: Map<String, Value> = entity_components_json(entity).into_iter().collect();
        if let Some(type_name) = type_name {
            let value = components.get(&type_name).cloned().ok_or_else(|| {
                app_err("E_NOT_FOUND", format!("component {type_name} not on {id}"))
            })?;
            return Ok(json!({
                "id": id,
                "type": type_name,
                "value": value,
                "revision": revision,
            }));
        }
        Ok(json!({
            "id": id,
            "components": components,
            "revision": revision,
        }))
    }

    fn component_add(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        let expected = take_expected_revision(&mut params);
        let id = string_field(&params, "id")?;
        let type_name = string_field(&params, "type")?;
        let value = params
            .get("value")
            .cloned()
            .unwrap_or_else(|| default_component_value(&type_name));
        let mut set_params = json!({
            "command_id": command_id,
            "id": id,
            "type": type_name,
            "patch": value,
        });
        if let Some(rev) = expected {
            set_params["expected_revision"] = json!(rev);
        }
        self.dispatch_one(ctx, "component.set", set_params)
    }

    fn component_remove(
        &mut self,
        ctx: CallContext<'_>,
        mut params: Value,
    ) -> Result<Value, RpcError> {
        let command_id = take_command_id(&mut params)?;
        let expected = take_expected_revision(&mut params);
        let id = string_field(&params, "id")?;
        let type_name = string_field(&params, "type")?;
        let n = gs_scene::parse_entity_id(&id).map_err(scene_err)?;
        let (scene_id, parent, order, components, children) = {
            let session = self.session_ref()?;
            let entity = session
                .document()
                .entity(n)
                .ok_or_else(|| app_err("E_NOT_FOUND", format!("not found: {id}")))?;
            let mut components = entity_components_json(entity);
            if components.remove(&type_name).is_none() {
                return Err(app_err(
                    "E_NOT_FOUND",
                    format!("component {type_name} not on {id}"),
                ));
            }
            let children: Vec<String> = session
                .document()
                .scene
                .entities
                .values()
                .filter(|e| e.parent == Some(n))
                .map(gs_scene::Entity::id_str)
                .collect();
            (
                session.document().scene_id.clone(),
                entity.parent.map(gs_scene::format_entity_id),
                entity.order,
                components,
                children,
            )
        };
        let mut commands = Vec::new();
        for child in &children {
            commands.push(Command::entity_reparent(
                vec![child.clone()],
                parent.clone(),
                true,
            ));
        }
        commands.push(Command::entity_destroy(vec![id.clone()]));
        commands.push(Command::new(
            "entity.spawn",
            json!({
                "scene_id": scene_id,
                "id": id,
                "parent": parent,
                "order": order,
                "components": components,
            }),
        ));
        for child in &children {
            commands.push(Command::entity_reparent(
                vec![child.clone()],
                Some(id.clone()),
                true,
            ));
        }
        self.dispatch_request(ctx, command_id, expected, commands, "component.remove")
    }

    fn asset_import(&mut self, ctx: CallContext<'_>, params: &Value) -> Result<Value, RpcError> {
        let root = self
            .project_path
            .clone()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))?;
        let src_abs = string_field(params, "src_abs")?;
        let dest_rel = string_field(params, "dest_rel")?;
        let min_next = self
            .session
            .as_ref()
            .map(|s| s.document().next_asset)
            .unwrap_or(1);
        let record = self
            .assets
            .import_png(&root, &src_abs, &dest_rel, min_next)?;
        if let Some(actor) = self.actors.get_mut(ctx.actor_id) {
            actor.command_count = actor.command_count.saturating_add(1);
        }
        let badge = self
            .actors
            .get(ctx.actor_id)
            .map(|a| a.principal.badge())
            .unwrap_or(Badge::System);
        self.feed.push(FeedEntry {
            badge,
            actor: ctx.actor_id.to_owned(),
            label: "asset.import".into(),
            entities: Vec::new(),
            revision: self.current_revision(),
        });
        self.emit(Notification::new(
            EVENT_ASSET,
            json!({
                "asset_id": record.asset_id,
                "dest_rel": record.dest_rel,
                "actor_id": ctx.actor_id,
            }),
        ));
        Ok(json!({
            "asset_id": record.asset_id,
            "dest_rel": record.dest_rel,
            "width": record.width,
            "height": record.height,
        }))
    }

    fn asset_list(&self, params: &Value) -> Result<Value, RpcError> {
        let kind = optional_string(params, "kind");
        let folder = optional_string(params, "folder");
        let assets: Vec<Value> = self
            .assets
            .list(kind.as_deref(), folder.as_deref())
            .into_iter()
            .map(|a| {
                json!({
                    "asset_id": a.asset_id,
                    "dest_rel": a.dest_rel,
                    "kind": a.kind,
                    "width": a.width,
                    "height": a.height,
                })
            })
            .collect();
        Ok(json!({ "assets": assets }))
    }

    fn reload_assets(&mut self) {
        self.assets = AssetCatalog::load(self.project_path.as_deref());
    }

    fn hold_confirmation(
        &mut self,
        actor_id: &str,
        method: &str,
        params: Value,
        summary: String,
    ) -> Result<Value, RpcError> {
        let confirmation_id = format!("cnf_{}", Ulid::new());
        let params_hash = params_hash(&params);
        let base_revision = self.current_revision();
        if let Some(old) = self
            .pending_by_actor
            .insert(actor_id.to_owned(), confirmation_id.clone())
        {
            self.pending.remove(&old);
        }
        let held = HeldCommand {
            confirmation_id: confirmation_id.clone(),
            actor_id: actor_id.to_owned(),
            method: method.to_owned(),
            params,
            params_hash: params_hash.clone(),
            base_revision: base_revision.clone(),
            created: Instant::now(),
            summary: summary.clone(),
        };
        self.pending.insert(confirmation_id.clone(), held);
        self.emit(Notification::new(
            EVENT_CONFIRM,
            json!({
                "confirmation_id": confirmation_id,
                "actor_id": actor_id,
                "method": method,
                "params_canonical_hash": params_hash,
                "base_revision": base_revision,
                "summary": summary,
                "expires_in": CONFIRM_SECS,
            }),
        ));
        Ok(json!({
            "status": "pending_confirmation",
            "confirmation_id": confirmation_id,
            "expires_in": CONFIRM_SECS,
        }))
    }

    fn needs_confirmation(
        &mut self,
        actor_id: &str,
        principal: Principal,
        method: &str,
        params: &Value,
    ) -> Option<String> {
        if principal == Principal::HumanUi {
            return None;
        }
        let (is_d, summary) = self.classify_d(actor_id, method, params);
        if !is_d {
            return None;
        }
        if self.has_cap(actor_id, method, &summary) {
            self.consume_cap(actor_id, method);
            return None;
        }
        Some(summary)
    }

    fn classify_d(&mut self, actor_id: &str, method: &str, params: &Value) -> (bool, String) {
        if method == "undo.revert" {
            return (true, "undo.revert".into());
        }
        if method == "entity.destroy" {
            let n = ids_len(params);
            if n > DESTROY_D_THRESHOLD {
                return (true, format!("entity.destroy {n} ids (mass)"));
            }
            if (SALAMI_MIN..=19).contains(&n) && self.record_salami(actor_id, n) {
                return (true, format!("entity.destroy {n} ids (salami)"));
            }
            return (false, format!("entity.destroy {n} ids"));
        }
        if method == "transaction.execute" {
            if let Some(cmds) = params.get("commands").and_then(Value::as_array) {
                let mut d_parts = Vec::new();
                for cmd in cmds {
                    let inner_method = cmd.get("method").and_then(Value::as_str).unwrap_or("");
                    let inner_params = cmd.get("params").cloned().unwrap_or(Value::Null);
                    let (is_d, part) = self.classify_d(actor_id, inner_method, &inner_params);
                    if is_d {
                        d_parts.push(part);
                    }
                }
                if !d_parts.is_empty() {
                    return (
                        true,
                        format!("transaction contains D: {}", d_parts.join("; ")),
                    );
                }
            }
            return (false, "transaction.execute".into());
        }
        if let Some(spec) = gs_registry::get(method) {
            if matches!(spec.capability, Capability::Destructive(_)) && method != "entity.destroy" {
                return (true, method.to_owned());
            }
        }
        (false, method.to_owned())
    }

    fn record_salami(&mut self, actor_id: &str, size: usize) -> bool {
        let now = Instant::now();
        let window = Duration::from_secs(60);
        let q = self.salami.entry(actor_id.to_owned()).or_default();
        while q.front().is_some_and(|t| now.duration_since(*t) > window) {
            q.pop_front();
        }
        let elevate = q.len() >= SALAMI_HITS;
        q.push_back(now);
        if elevate {
            let line = format!(
                "salami heuristic: actor {actor_id} entity.destroy size {size} elevated to D ({} events in 60s)",
                q.len()
            );
            self.heuristic_log.push(line);
        }
        elevate
    }

    fn has_cap(&self, actor_id: &str, method: &str, summary: &str) -> bool {
        let now = Instant::now();
        let Some(list) = self.caps.get(actor_id) else {
            return false;
        };
        list.iter().any(|c| {
            if c.expiry.is_some_and(|e| e <= now) {
                return false;
            }
            if c.max_use.is_some_and(|m| c.used >= m) {
                return false;
            }
            cap_matches(c, method, summary)
        })
    }

    fn consume_cap(&mut self, actor_id: &str, method: &str) {
        let now = Instant::now();
        if let Some(list) = self.caps.get_mut(actor_id) {
            if let Some(c) = list.iter_mut().find(|c| {
                c.expiry.is_none_or(|e| e > now)
                    && c.max_use.is_none_or(|m| c.used < m)
                    && cap_matches(c, method, "")
            }) {
                c.used = c.used.saturating_add(1);
            }
        }
    }

    fn check_budget(&mut self, actor_id: &str, cost: usize) -> Option<u64> {
        if cost == 0 {
            return None;
        }
        let now = Instant::now();
        let window = Duration::from_secs(60);
        let q = self.budget.entry(actor_id.to_owned()).or_default();
        while q.front().is_some_and(|t| now.duration_since(*t) > window) {
            q.pop_front();
        }
        if q.len().saturating_add(cost) > BUDGET_PER_MIN {
            let retry = q
                .front()
                .map(|t| window.saturating_sub(now.duration_since(*t)).as_millis() as u64)
                .unwrap_or(0);
            let hits = self.budget_hits.entry(actor_id.to_owned()).or_default();
            let five = Duration::from_secs(300);
            while hits.front().is_some_and(|t| now.duration_since(*t) > five) {
                hits.pop_front();
            }
            hits.push_back(now);
            if hits.len() >= 3 {
                self.feed.push(FeedEntry {
                    badge: Badge::System,
                    actor: actor_id.to_owned(),
                    label: "budget warning: actor hit E_BUDGET 3 times in 5 minutes".into(),
                    entities: Vec::new(),
                    revision: self.current_revision(),
                });
            }
            return Some(retry);
        }
        for _ in 0..cost {
            q.push_back(now);
        }
        None
    }

    fn is_paused(&self, actor_id: &str) -> bool {
        self.actors.get(actor_id).is_some_and(|a| a.paused)
    }

    pub(crate) fn current_revision(&self) -> String {
        self.session
            .as_ref()
            .map(|s| s.document().revision_label())
            .unwrap_or_else(|| "r-000000".into())
    }

    fn session_mut(&mut self) -> Result<&mut Session, RpcError> {
        self.session
            .as_mut()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))
    }

    pub(crate) fn session_ref(&self) -> Result<&Session, RpcError> {
        self.session
            .as_ref()
            .ok_or_else(|| app_err("E_NOT_FOUND", "no project open"))
    }

    fn emit_session(&mut self, summary: &str) {
        self.emit(Notification::new(
            EVENT_SESSION,
            json!({ "summary": summary }),
        ));
    }

    pub(crate) fn emit(&mut self, notification: Notification) {
        self.notifications.push(notification.clone());
        let topic = topic_of(&notification.method);
        let mut dead = Vec::new();
        for (id, sub) in &self.subscribers {
            if sub.topics.contains(topic)
                && sub
                    .tx
                    .send(Outbound::Notification(notification.clone()))
                    .is_err()
            {
                dead.push(id.clone());
            }
        }
        for id in dead {
            self.subscribers.remove(&id);
        }
    }
}

fn hello_result(actor_id: &str, principal: Principal) -> Value {
    let methods: Vec<&str> = gs_registry::all_methods().iter().map(|m| m.name).collect();
    json!({
        "actor_id": actor_id,
        "principal": principal.as_str(),
        "protocol_ver": PROTOCOL_VER,
        "methods": methods,
        "capabilities": [],
    })
}

fn is_mutating(method: &str, spec: Option<&gs_registry::MethodSpec>) -> bool {
    if matches!(
        method,
        "session.ping"
            | "session.list"
            | "session.subscribe"
            | "session.goodbye"
            | "capability.list"
            | "project.info"
            | "scene.stats"
            | "component.get"
            | "component.registry"
            | "asset.list"
            | "play.status"
            | "obs.events"
            | "obs.world_dump"
            | "obs.logs_tail"
            | "obs.perf"
            | "obs.screenshot"
            | "script.get_source"
            | "script.conflicts"
            | "script.diagnostics"
            | "inputmap.get"
            | "scene.dump"
            | "entity.find"
            | "artifact.list"
            | "artifact.get"
            | "build.status"
    ) {
        return false;
    }
    if method == "artifact.gc" {
        return true;
    }
    if play_is_mutating(method) {
        return true;
    }
    if build_is_mutating(method) {
        return true;
    }
    if method == "asset.import" {
        return true;
    }
    spec.is_some_and(|s| s.side_effect != SideEffect::ReadOnly)
}

fn mutating_cost(method: &str, params: &Value) -> usize {
    if method == "transaction.execute" {
        params
            .get("commands")
            .and_then(Value::as_array)
            .map(|a| a.len())
            .unwrap_or(1)
            .max(1)
    } else if is_mutating(method, gs_registry::get(method)) {
        1
    } else {
        0
    }
}

fn is_editor_layer_method(method: &str) -> bool {
    matches!(method, "asset.import" | "asset.list")
        || is_script_editor_layer(method)
        || is_play_method(method)
        || is_input_method(method)
        || is_obs_method(method)
        || is_judge_method(method)
        || is_runtime_method(method)
        || is_artifact_method(method)
        || is_build_method(method)
}

fn is_wired_tilemap(method: &str) -> bool {
    matches!(method, "tilemap.set_cells" | "tilemap.fill_rect")
}

fn is_unimplemented(method: &str) -> bool {
    if is_editor_layer_method(method) || is_script_method(method) {
        return false;
    }
    if (method.starts_with("play.") && !is_play_method(method))
        || (method.starts_with("obs.") && !is_obs_method(method))
        || (method.starts_with("judge.") && !is_judge_method(method))
        || (method.starts_with("input.") && !is_input_method(method)) // not `inputmap.*`
        || method.starts_with("asset.")
        || method.starts_with("script.")
        || (method.starts_with("tilemap.") && !is_wired_tilemap(method))
        || (method.starts_with("build.") && !is_build_method(method))
        || method.starts_with("artifact.")
    {
        return true;
    }
    matches!(
        method,
        "undo.redo"
            | "undo.revert"
            | "undo.history"
            | "scene.new"
            | "scene.open"
            | "scene.save"
            | "scene.list"
            | "scene.rename"
            | "scene.duplicate"
            | "scene.delete"
    )
}

fn cap_matches(cap: &GrantedCap, method: &str, summary: &str) -> bool {
    if cap.scope == "*" || cap.scope == method || cap.cap == method {
        return true;
    }
    if method == "entity.destroy"
        && (cap.cap == "entity.destroy.mass" || cap.cap.contains("entity.destroy"))
    {
        return true;
    }
    if method == "undo.revert" && (cap.cap == "undo.others" || cap.scope == "undo.others") {
        return true;
    }
    if method == "transaction.execute" && summary.contains("entity.destroy") {
        return cap.cap.contains("entity.destroy") || cap.scope == "*";
    }
    false
}

fn normalize_params(params: Value) -> Result<Value, RpcError> {
    match params {
        Value::Null => Ok(Value::Object(Map::new())),
        Value::Object(_) => Ok(params),
        _ => Err(invalid_params("params must be a JSON object")),
    }
}

pub(crate) fn string_field(params: &Value, key: &str) -> Result<String, RpcError> {
    params
        .get(key)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .map(ToOwned::to_owned)
        .ok_or_else(|| invalid_params(format!("missing {key}")))
}

pub(crate) fn optional_string(params: &Value, key: &str) -> Option<String> {
    params
        .get(key)
        .and_then(Value::as_str)
        .filter(|s| !s.is_empty())
        .map(ToOwned::to_owned)
}

fn optional_u32(params: &Value, key: &str) -> Result<Option<u32>, RpcError> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .map(Some)
            .ok_or_else(|| invalid_params(format!("{key} must be a u32"))),
    }
}

fn optional_expiry(params: &Value) -> Result<Option<Instant>, RpcError> {
    match params.get("expiry") {
        None | Some(Value::Null) => Ok(None),
        Some(Value::Number(n)) => {
            let secs = n
                .as_u64()
                .ok_or_else(|| invalid_params("expiry must be unix seconds or duration secs"))?;
            Ok(Some(Instant::now() + Duration::from_secs(secs)))
        }
        Some(Value::String(s)) => {
            let secs: u64 = s
                .parse()
                .map_err(|_| invalid_params("expiry string must be seconds"))?;
            Ok(Some(Instant::now() + Duration::from_secs(secs)))
        }
        Some(_) => Err(invalid_params("expiry must be a number or string")),
    }
}

pub(crate) fn string_list(params: &Value, key: &str) -> Result<Vec<String>, RpcError> {
    match params.get(key) {
        None | Some(Value::Null) => Ok(Vec::new()),
        Some(Value::Array(items)) => items
            .iter()
            .map(|v| {
                v.as_str()
                    .map(ToOwned::to_owned)
                    .ok_or_else(|| invalid_params(format!("{key} must be an array of strings")))
            })
            .collect(),
        Some(_) => Err(invalid_params(format!("{key} must be an array"))),
    }
}

pub(crate) fn take_command_id(params: &mut Value) -> Result<String, RpcError> {
    let id = params
        .as_object_mut()
        .and_then(|m| m.remove("command_id"))
        .and_then(|v| v.as_str().map(ToOwned::to_owned))
        .ok_or_else(|| invalid_params("command_id is required and must be a ULID"))?;
    if Ulid::from_string(&id).is_err() {
        return Err(invalid_params("command_id is required and must be a ULID"));
    }
    Ok(id)
}

fn take_expected_revision(params: &mut Value) -> Option<String> {
    params
        .as_object_mut()
        .and_then(|m| m.remove("expected_revision"))
        .and_then(|v| v.as_str().map(ToOwned::to_owned))
}

fn strip_identity(params: &mut Value) {
    if let Some(map) = params.as_object_mut() {
        map.remove("actor_id");
        map.remove("principal");
        map.remove("token");
    }
}

fn ensure_reparent_keep_world(params: &mut Value) {
    if let Some(map) = params.as_object_mut() {
        if !map.contains_key("keep_world") {
            map.insert("keep_world".into(), json!(true));
        }
    }
}

fn ensure_scene_id(params: &mut Value) {
    if let Some(map) = params.as_object_mut() {
        if !map.contains_key("scene_id") {
            map.insert("scene_id".into(), json!(DEFAULT_SCENE_ID));
        }
    }
}

fn ids_len(params: &Value) -> usize {
    params
        .get("ids")
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0)
}

fn entity_ids_from(commands: &[Command]) -> Vec<String> {
    let mut out = Vec::new();
    for cmd in commands {
        if let Some(id) = cmd.params.get("id").and_then(Value::as_str) {
            if !out.iter().any(|e| e == id) {
                out.push(id.to_owned());
            }
        }
        if let Some(ids) = cmd.params.get("ids").and_then(Value::as_array) {
            for id in ids {
                if let Some(s) = id.as_str() {
                    if !out.iter().any(|e| e == s) {
                        out.push(s.to_owned());
                    }
                }
            }
        }
    }
    out
}

fn ack_json(ack: &Ack) -> Value {
    let mut out = json!({
        "seq": ack.seq,
        "txn_id": ack.txn_id,
        "command_id": ack.command_id,
        "revision": ack.revision,
        "spawned_ids": ack.spawned_ids,
    });
    if let Some(token) = &ack.owner_token {
        out["owner_token"] = json!(token);
    }
    out
}

fn params_hash(params: &Value) -> String {
    let canonical = to_canonical_string(params);
    let digest = Sha256::digest(canonical.as_bytes());
    let mut hex = String::with_capacity(64);
    for byte in digest {
        let _ = std::fmt::Write::write_fmt(&mut hex, format_args!("{byte:02x}"));
    }
    hex
}

fn remaining_secs(created: Instant, now: Instant) -> u64 {
    Duration::from_secs(CONFIRM_SECS)
        .saturating_sub(now.duration_since(created))
        .as_secs()
}

fn topic_of(method: &str) -> &'static str {
    if method == EVENT_SCENE {
        "scene"
    } else if method == EVENT_SESSION {
        "session"
    } else if method == EVENT_CONFIRM {
        "confirmation"
    } else if method == EVENT_ASSET {
        "asset"
    } else if method == EVENT_PLAY || play_topic(method) {
        "play"
    } else if method == EVENT_SCRIPT {
        "script"
    } else {
        "session"
    }
}
