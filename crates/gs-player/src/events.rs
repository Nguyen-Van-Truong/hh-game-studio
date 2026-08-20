//! Play event trace: in-memory ring + append-only `events.jsonl` (MASTER 6.3, T2.3).

use std::collections::VecDeque;
use std::fs::{File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

use gs_runtime_core::{PlayEvent, SystemEvent, World};
use gs_scene::format_entity_id;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

use crate::error::Error;

pub const EVENT_RING_CAP: usize = 65_536;
pub const OBS_LOG_TAIL_MAX: usize = 500;
pub const OBS_EVENTS_DEFAULT_LIMIT: usize = 256;
pub const OBS_EVENTS_MAX_LIMIT: usize = 4096;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct TraceEvent {
    pub seq: u64,
    pub frame: u64,
    pub name: String,
    #[serde(default)]
    pub data: Value,
    pub entity: Option<String>,
}

pub struct EventTrace {
    ring: VecDeque<TraceEvent>,
    next_seq: u64,
    events_path: Option<PathBuf>,
}

impl EventTrace {
    pub fn new(events_path: Option<PathBuf>) -> Result<Self, Error> {
        if let Some(path) = &events_path {
            if let Some(parent) = path.parent() {
                std::fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
            }
            File::create(path).map_err(|e| Error::io(path, e))?;
        }
        Ok(Self {
            ring: VecDeque::new(),
            next_seq: 0,
            events_path,
        })
    }

    pub fn events_path(&self) -> Option<&Path> {
        self.events_path.as_deref()
    }

    pub fn last_seq(&self) -> u64 {
        self.ring.back().map(|event| event.seq).unwrap_or(0)
    }

    pub fn ingest(&mut self, events: Vec<SystemEvent>) -> Result<(), Error> {
        for event in events {
            self.push_system(event)?;
        }
        Ok(())
    }

    pub fn drain_world_events(&mut self, world: &mut World) -> Result<(), Error> {
        let pending = std::mem::take(&mut world.events);
        self.ingest(pending)?;
        self.drain_play_events(world)
    }

    /// `gs.emit` / script play events (CoinPicked, SnakeDied, …) into the obs ring.
    pub fn drain_play_events(&mut self, world: &mut World) -> Result<(), Error> {
        let frame = world.frame;
        let pending = std::mem::take(&mut world.play_events);
        for event in pending {
            self.push_play(frame, event)?;
        }
        Ok(())
    }

    fn push_play(&mut self, frame: u64, event: PlayEvent) -> Result<(), Error> {
        self.push(TraceEvent {
            seq: 0,
            frame,
            name: event.name,
            data: event.data,
            entity: event.entity_id.map(format_entity_id),
        })
    }

    fn push_system(&mut self, event: SystemEvent) -> Result<(), Error> {
        let trace = match event {
            SystemEvent::FrameAdvanced { frame } => TraceEvent {
                seq: 0,
                frame,
                name: "FrameAdvanced".into(),
                data: json!({}),
                entity: None,
            },
        };
        self.push(trace)
    }

    fn push(&mut self, mut event: TraceEvent) -> Result<(), Error> {
        self.next_seq = self.next_seq.saturating_add(1);
        event.seq = self.next_seq;
        if self.ring.len() >= EVENT_RING_CAP {
            self.ring.pop_front();
        }
        self.ring.push_back(event.clone());
        if let Some(path) = &self.events_path {
            append_jsonl(path, &event)?;
        }
        Ok(())
    }

    pub fn query(&self, after_seq: u64, name: Option<&str>, limit: usize) -> Vec<TraceEvent> {
        let limit = limit.clamp(1, OBS_EVENTS_MAX_LIMIT);
        self.ring
            .iter()
            .filter(|e| e.seq > after_seq)
            .filter(|e| name.is_none_or(|n| e.name == n))
            .take(limit)
            .cloned()
            .collect()
    }
}

fn append_jsonl(path: &Path, event: &TraceEvent) -> Result<(), Error> {
    let line = serde_json::to_string(event).map_err(|e| Error::json(path, e))?;
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|e| Error::io(path, e))?;
    file.write_all(line.as_bytes())
        .and_then(|_| file.write_all(b"\n"))
        .and_then(|_| file.flush())
        .map_err(|e| Error::io(path, e))?;
    Ok(())
}

pub fn world_dump_value(world: &World) -> Value {
    let entities: Vec<Value> = world
        .entities
        .values()
        .map(|entity| {
            json!({
                "id": entity.id_str(),
                "parent": entity.parent.map(format_entity_id),
                "order": entity.order,
                "name": entity.name.as_ref().map(|n| &n.value),
                "transform": entity.transform.as_ref().map(|t| json!({
                    "x": t.x,
                    "y": t.y,
                    "rot": t.rot,
                    "sx": t.sx,
                    "sy": t.sy,
                    "z_index": t.z_index,
                })),
                "has_sprite": entity.extra.sprite.is_some(),
                "has_camera": entity.extra.camera.is_some(),
            })
        })
        .collect();
    json!({
        "frame": world.frame,
        "seed": world.seed,
        "entity_count": entities.len(),
        "entities": entities,
    })
}

pub fn write_artifact(path: &Path, value: &Value) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
    }
    let bytes = serde_json::to_vec_pretty(value).map_err(|e| Error::json(path, e))?;
    let tmp = path.with_extension("tmp");
    std::fs::write(&tmp, bytes).map_err(|e| Error::io(&tmp, e))?;
    if path.exists() {
        std::fs::remove_file(path).map_err(|e| Error::io(path, e))?;
    }
    std::fs::rename(&tmp, path).map_err(|e| Error::io(path, e))?;
    Ok(())
}

pub fn write_png_artifact(path: &Path, png: &[u8]) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
    }
    let tmp = path.with_extension("png.tmp");
    std::fs::write(&tmp, png).map_err(|e| Error::io(&tmp, e))?;
    if path.exists() {
        std::fs::remove_file(path).map_err(|e| Error::io(path, e))?;
    }
    std::fs::rename(&tmp, path).map_err(|e| Error::io(path, e))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use gs_runtime_core::{PlayEvent, World};
    use gs_scene::{Camera2D, Entity, Name, Scene, Transform2D};
    use serde_json::json;
    use tempfile::TempDir;

    fn camera_world() -> World {
        let mut scene = Scene::default();
        let mut entity = Entity::new(1, None, 0);
        entity.name = Some(Name {
            value: "cam".into(),
        });
        entity.transform = Some(Transform2D::identity());
        entity.extra.camera = Some(Camera2D {
            ortho_height: 10.0,
            active: true,
        });
        scene.entities.insert(1, entity);
        World::from_scene(scene, 1)
    }

    #[test]
    fn ring_and_file_stay_in_sync() {
        let dir = TempDir::new().expect("temp");
        let path = dir.path().join("events.jsonl");
        let mut trace = EventTrace::new(Some(path.clone())).expect("trace");
        let mut world = camera_world();
        world.events.push(SystemEvent::FrameAdvanced { frame: 1 });
        trace.drain_world_events(&mut world).expect("drain");
        assert_eq!(trace.last_seq(), 1);
        let text = std::fs::read_to_string(&path).expect("file");
        assert!(text.contains("FrameAdvanced"));
        let found = trace.query(0, None, 10);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].frame, 1);
    }

    #[test]
    fn drain_play_events_exposes_coin_picked() {
        let mut trace = EventTrace::new(None).expect("trace");
        let mut world = camera_world();
        world.frame = 4;
        world.play_events.push(PlayEvent {
            name: "CoinPicked".into(),
            entity_id: Some(1),
            data: json!({ "coin": "e_000001" }),
        });
        trace.drain_world_events(&mut world).expect("drain");
        assert!(world.play_events.is_empty());
        let found = trace.query(0, Some("CoinPicked"), 8);
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].name, "CoinPicked");
        assert_eq!(found[0].frame, 4);
        assert_eq!(found[0].entity.as_deref(), Some("e_000001"));
        assert_eq!(found[0].data["coin"], "e_000001");
    }
}
