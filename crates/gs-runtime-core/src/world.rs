use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use gs_scene::{Entity, Scene, SceneFile, Transform2D};
use serde_json::Value;

use crate::error::Error;
use crate::phase::Phase;
use crate::script::{
    format_play_id, run_init, RunReport, ScriptError, ScriptFailure, ScriptFrameReport, ScriptLog,
    ScriptTimeHook,
};

/// Fixed simulate step (MASTER 6.2). The frame accumulator lives in the player.
pub const FIXED_DT: f64 = 1.0 / 60.0;

/// Abstract input for one simulate step (MASTER 6.4). Empty until tape / control.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct InputFrame {
    pub actions: BTreeMap<String, f32>,
}

/// System-generated play events. Gameplay `gs.emit` goes to [`World::play_events`]
/// so this enum stays a single variant (gs-player matches it exhaustively).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SystemEvent {
    FrameAdvanced { frame: u64 },
}

/// Script-facing play event (`gs.emit`, `script_disabled`). Not a bus method.
#[derive(Clone, Debug, PartialEq)]
pub struct PlayEvent {
    pub name: String,
    pub entity_id: Option<u64>,
    pub data: Value,
}

/// Queued `on_event` payload (collision mock until M4).
#[derive(Clone, Debug, PartialEq)]
pub struct QueuedScriptEvent {
    pub target_id: u64,
    pub name: String,
    pub data: Value,
}

/// Scene Script component projection (file + props). Source is loaded separately.
#[derive(Clone, Debug, PartialEq)]
pub struct ScriptBinding {
    pub file: String,
    pub props: BTreeMap<String, Value>,
}

/// One-shot or looping play request (`gs.play_sfx` / AudioSource). `Send`.
#[derive(Clone, Debug, PartialEq)]
pub struct SfxRequest {
    pub asset_id: String,
    pub volume: f32,
    pub pan: f32,
    pub looping: bool,
}

/// Decaying camera shake (MASTER 7.2). Offset is applied to the render camera.
#[derive(Clone, Debug, PartialEq)]
pub struct CameraShake {
    pub amplitude: f32,
    pub remaining: f64,
    pub duration: f64,
}

/// Frozen play world: entities keyed by numeric id (no HashMap on this path).
#[derive(Clone, Debug)]
pub struct World {
    pub entities: BTreeMap<u64, Entity>,
    pub frame: u64,
    pub seed: u64,
    pub input: InputFrame,
    pub events: Vec<SystemEvent>,
    pub play_events: Vec<PlayEvent>,
    pub warnings: Vec<String>,
    /// Phases recorded by the last [`crate::step`] (test / observe).
    pub last_phases: Vec<Phase>,
    /// Entity ids visited during `script_on_update` (ascending).
    pub script_visit_order: Vec<u64>,
    /// Luau source attached for play (keyed by entity id). Empty = visit-id stub.
    pub attached_scripts: BTreeMap<u64, String>,
    /// Script component file + props from the scene (no `enabled` field).
    pub script_bindings: BTreeMap<u64, ScriptBinding>,
    /// Pending `on_event` deliveries (collision mock, custom).
    pub queued_script_events: Vec<QueuedScriptEvent>,
    /// Scripts skipped by the global hard budget last frame (round-robin).
    pub starved_scripts: Vec<u64>,
    /// Scripts that ran in the last `script_on_update`.
    pub scripts_ran: Vec<u64>,
    pub script_logs: Vec<ScriptLog>,
    pub script_errors: Vec<ScriptFailure>,
    pub last_script_frame: ScriptFrameReport,
    /// Test hook: inject elapsed time so budget tests do not sleep.
    pub script_time_hook: Option<ScriptTimeHook>,
    /// Test hook: disable-policy clock (milliseconds). `None` = wall clock.
    pub script_now_ms: Option<u64>,
    /// `gs.velocity` commits here; [`crate::PhysicsHost::integrate`] applies then clears.
    pub pending_velocities: BTreeMap<u64, (f32, f32)>,
    /// `gs.impulse` commits here; [`crate::PhysicsHost::integrate`] applies then clears.
    pub pending_impulses: BTreeMap<u64, (f32, f32)>,
    /// `gs.play_sfx` / AudioSource autoplay. Player drains; tests assert the list.
    pub sfx_queue: Vec<SfxRequest>,
    /// AudioSource entities already enqueued (avoid repeating every step).
    pub started_audio: BTreeSet<u64>,
    /// `gs.camera_follow(id|nil)` — copy that entity's x,y onto the active camera.
    pub camera_follow: Option<u64>,
    /// Active shake; ticked with [`FIXED_DT`] after physics.
    pub camera_shake: Option<CameraShake>,
    /// Current decaying shake offset (world units). Added to the render camera.
    pub camera_shake_offset: [f32; 2],
    /// Scene `$asset` id (e.g. `a_000020`) → `TextureId.0`. Empty = untextured.
    pub texture_ids: BTreeMap<String, u32>,
}

impl World {
    pub fn from_scene(scene: Scene, seed: u64) -> Self {
        let mut script_bindings = BTreeMap::new();
        for (id, entity) in &scene.entities {
            if let Some(script) = &entity.extra.script {
                script_bindings.insert(
                    *id,
                    ScriptBinding {
                        file: script.file.clone(),
                        props: script.props.clone(),
                    },
                );
            }
        }
        let mut world = Self {
            entities: scene.entities,
            frame: 0,
            seed,
            input: InputFrame::default(),
            events: Vec::new(),
            play_events: Vec::new(),
            warnings: Vec::new(),
            last_phases: Vec::new(),
            script_visit_order: Vec::new(),
            attached_scripts: BTreeMap::new(),
            script_bindings,
            queued_script_events: Vec::new(),
            starved_scripts: Vec::new(),
            scripts_ran: Vec::new(),
            script_logs: Vec::new(),
            script_errors: Vec::new(),
            last_script_frame: ScriptFrameReport::default(),
            script_time_hook: None,
            script_now_ms: None,
            pending_velocities: BTreeMap::new(),
            pending_impulses: BTreeMap::new(),
            sfx_queue: Vec::new(),
            started_audio: BTreeSet::new(),
            camera_follow: None,
            camera_shake: None,
            camera_shake_offset: [0.0, 0.0],
            texture_ids: BTreeMap::new(),
        };
        world.enqueue_autoplay_audio();
        world
    }

    /// AudioSource with `autoplay` or `loop`: enqueue a looping request once.
    pub fn enqueue_autoplay_audio(&mut self) {
        let mut started = Vec::new();
        let mut requests = Vec::new();
        for (id, entity) in &self.entities {
            if self.started_audio.contains(id) {
                continue;
            }
            let Some(audio) = &entity.extra.audio else {
                continue;
            };
            if !audio.autoplay && !audio.loop_play {
                continue;
            }
            requests.push(SfxRequest {
                asset_id: audio.asset.id.clone(),
                volume: audio.volume,
                pan: audio.pan,
                looping: true,
            });
            started.push(*id);
        }
        self.started_audio.extend(started);
        self.sfx_queue.extend(requests);
    }

    /// Copy the follow target's x,y onto the active camera entity transform.
    pub fn apply_camera_follow(&mut self) {
        let Some(follow_id) = self.camera_follow else {
            return;
        };
        let Some((x, y)) = self
            .entities
            .get(&follow_id)
            .and_then(|e| e.transform.as_ref().map(|t| (t.x, t.y)))
        else {
            return;
        };
        let Some(cam_id) = self.entities.iter().find_map(|(id, entity)| {
            entity
                .extra
                .camera
                .as_ref()
                .filter(|cam| cam.active)
                .map(|_| *id)
        }) else {
            return;
        };
        if let Some(camera) = self.entities.get_mut(&cam_id) {
            let transform = camera.transform.get_or_insert_with(Transform2D::identity);
            transform.x = x;
            transform.y = y;
        }
    }

    /// Linear decay: offset = (amplitude * remaining/duration, 0). Time uses [`FIXED_DT`].
    pub fn tick_camera_shake(&mut self) {
        let Some(shake) = self.camera_shake.as_mut() else {
            self.camera_shake_offset = [0.0, 0.0];
            return;
        };
        if !shake.amplitude.is_finite()
            || !shake.remaining.is_finite()
            || !shake.duration.is_finite()
            || shake.duration <= 0.0
            || shake.remaining <= 0.0
        {
            self.camera_shake = None;
            self.camera_shake_offset = [0.0, 0.0];
            return;
        }
        let t = (shake.remaining / shake.duration) as f32;
        self.camera_shake_offset = [shake.amplitude * t, 0.0];
        shake.remaining -= FIXED_DT;
        if shake.remaining <= 0.0 {
            shake.remaining = 0.0;
        }
    }

    /// Attach Luau source text to an entity. Compiled at run time (I4).
    pub fn attach_script(&mut self, entity_id: u64, source: impl Into<String>) {
        self.attached_scripts.insert(entity_id, source.into());
    }

    /// Read each binding's `file` as UTF-8 from `root.join(file)`.
    pub fn load_script_sources(&mut self, root: &Path) -> Result<(), Error> {
        let bindings: Vec<(u64, String)> = self
            .script_bindings
            .iter()
            .map(|(id, b)| (*id, b.file.clone()))
            .collect();
        for (id, file) in bindings {
            let path = root.join(&file);
            let source = std::fs::read_to_string(&path)?;
            self.attached_scripts.insert(id, source);
        }
        Ok(())
    }

    pub fn queue_script_event(&mut self, target_id: u64, name: impl Into<String>, data: Value) {
        self.queued_script_events.push(QueuedScriptEvent {
            target_id,
            name: name.into(),
            data,
        });
    }

    pub fn queue_collision_enter(&mut self, target_id: u64, other_id: u64, is_sensor: bool) {
        self.queue_script_event(
            target_id,
            "collision_enter",
            serde_json::json!({
                "other": format_play_id(other_id),
                "is_sensor": is_sensor,
            }),
        );
    }

    pub fn queue_collision_exit(&mut self, target_id: u64, other_id: u64, is_sensor: bool) {
        self.queue_script_event(
            target_id,
            "collision_exit",
            serde_json::json!({
                "other": format_play_id(other_id),
                "is_sensor": is_sensor,
            }),
        );
    }

    /// Run one attached script with the 100 ms `on_init` budget (MASTER 7.3).
    pub fn run_init(&mut self, entity_id: u64) -> Result<RunReport, ScriptError> {
        run_init(self, entity_id)
    }

    pub fn from_scene_bytes(bytes: &[u8], seed: u64) -> Result<Self, Error> {
        let file: SceneFile = serde_json::from_slice(bytes)?;
        let scene = Scene::from_file(file)?;
        Ok(Self::from_scene(scene, seed))
    }

    pub fn from_scene_path(path: &Path, seed: u64) -> Result<Self, Error> {
        let bytes = std::fs::read(path)?;
        Self::from_scene_bytes(&bytes, seed)
    }

    pub fn last_phase_names(&self) -> Vec<&'static str> {
        self.last_phases
            .iter()
            .copied()
            .map(Phase::as_str)
            .collect()
    }
}
