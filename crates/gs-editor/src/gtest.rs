//! `.gtest.json` parse + I7 path jail (MASTER 10.3 / T5.3).
//!
//! Unknown object keys are kept on [`GTest::extra`] / assert extras (I5).

use std::fs;
use std::path::{Path, PathBuf};

use gs_protocol::RpcError;
use gs_scene::{resolve_under_root, Collider2D, Entity, Error as SceneError, Session};
use serde_json::{json, Map, Value};

use crate::error::{app_err, invalid_params, scene_err};

pub const DEFAULT_MAX_FRAMES: u32 = 600;
pub const DEFAULT_PER_PX: u32 = 8;
pub const DEFAULT_MAX_BAD_RATIO: f64 = 0.002;
pub const WORLD_EPSILON: f64 = 1e-5;

#[derive(Clone, Debug, PartialEq)]
pub struct GTest {
    pub name: String,
    pub scene: Option<String>,
    pub seed: u64,
    pub tape: Option<String>,
    pub max_frames: u32,
    pub asserts: Vec<GAssert>,
    pub expect_diagnostics_max: u32,
    pub extra: Map<String, Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub enum GAssert {
    Event(EventAssert),
    World(WorldAssert),
    Screenshot(ScreenshotAssert),
    Unknown(Value),
}

#[derive(Clone, Debug, PartialEq)]
pub struct EventAssert {
    pub name: String,
    pub after: Option<String>,
    pub extra: Map<String, Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct WorldAssert {
    pub entity_tag: String,
    pub component: String,
    pub field: String,
    pub equals: Value,
    pub extra: Map<String, Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ScreenshotAssert {
    pub golden: Option<String>,
    pub per_px: u32,
    pub max_bad_ratio: f64,
    pub mask: Option<String>,
    pub extra: Map<String, Value>,
}

impl GTest {
    pub fn load(root: &Path, gtest_rel: &str) -> Result<Self, RpcError> {
        let path = resolve_project_rel(root, gtest_rel, true)?;
        let text = fs::read_to_string(&path).map_err(|err| app_err("E_IO", err.to_string()))?;
        let value: Value = serde_json::from_str(&text)
            .map_err(|err| invalid_params(format!("gtest JSON: {err}")))?;
        let gtest = Self::from_value(value)?;
        gtest.validate_paths(root)?;
        Ok(gtest)
    }

    pub fn from_value(value: Value) -> Result<Self, RpcError> {
        let mut obj = match value {
            Value::Object(map) => map,
            _ => return Err(invalid_params("gtest must be a JSON object")),
        };
        let name = take_string(&mut obj, "name")?
            .ok_or_else(|| invalid_params("gtest.name is required"))?;
        if name.is_empty() {
            return Err(invalid_params("gtest.name is required"));
        }
        let scene = take_string(&mut obj, "scene")?;
        let tape = take_string(&mut obj, "tape")?;
        let seed = take_u64(&mut obj, "seed")?.unwrap_or(0);
        let max_frames = take_u64(&mut obj, "max_frames")?
            .unwrap_or(u64::from(DEFAULT_MAX_FRAMES))
            .min(u64::from(u32::MAX)) as u32;
        let expect_diagnostics_max = take_u64(&mut obj, "expect_diagnostics_max")?
            .unwrap_or(0)
            .min(u64::from(u32::MAX)) as u32;
        let asserts_val = obj
            .remove("asserts")
            .ok_or_else(|| invalid_params("gtest.asserts must be an array"))?;
        let raw_asserts = asserts_val
            .as_array()
            .ok_or_else(|| invalid_params("gtest.asserts must be an array"))?;
        let mut asserts = Vec::with_capacity(raw_asserts.len());
        for item in raw_asserts {
            asserts.push(parse_assert(item)?);
        }
        Ok(Self {
            name,
            scene,
            seed,
            tape,
            max_frames,
            asserts,
            expect_diagnostics_max,
            extra: obj,
        })
    }

    fn validate_paths(&self, root: &Path) -> Result<(), RpcError> {
        if let Some(scene) = &self.scene {
            // Jail only: play uses the open session (scene.open is not in this slice).
            let _ = resolve_project_rel(root, scene, false)?;
        }
        if let Some(tape) = &self.tape {
            let _ = resolve_project_rel(root, tape, true)?;
        }
        for assert in &self.asserts {
            if let GAssert::Screenshot(shot) = assert {
                if let Some(golden) = &shot.golden {
                    let _ = resolve_project_rel(root, golden, true)?;
                }
                if let Some(mask) = &shot.mask {
                    let _ = resolve_project_rel(root, mask, true)?;
                }
            }
        }
        Ok(())
    }

    pub fn to_value(&self) -> Value {
        let mut obj = self.extra.clone();
        obj.insert("name".into(), json!(self.name));
        if let Some(scene) = &self.scene {
            obj.insert("scene".into(), json!(scene));
        }
        obj.insert("seed".into(), json!(self.seed));
        if let Some(tape) = &self.tape {
            obj.insert("tape".into(), json!(tape));
        }
        obj.insert("max_frames".into(), json!(self.max_frames));
        obj.insert(
            "expect_diagnostics_max".into(),
            json!(self.expect_diagnostics_max),
        );
        let asserts: Vec<Value> = self.asserts.iter().map(GAssert::to_value).collect();
        obj.insert("asserts".into(), json!(asserts));
        Value::Object(obj)
    }
}

impl GAssert {
    fn to_value(&self) -> Value {
        match self {
            Self::Event(event) => {
                let mut inner = event.extra.clone();
                inner.insert("name".into(), json!(event.name));
                if let Some(after) = &event.after {
                    inner.insert("after".into(), json!(after));
                }
                json!({ "event": Value::Object(inner) })
            }
            Self::World(world) => {
                let mut inner = world.extra.clone();
                inner.insert("entity_tag".into(), json!(world.entity_tag));
                inner.insert("component".into(), json!(world.component));
                inner.insert("field".into(), json!(world.field));
                inner.insert("equals".into(), world.equals.clone());
                json!({ "world": Value::Object(inner) })
            }
            Self::Screenshot(shot) => {
                let mut inner = shot.extra.clone();
                if let Some(golden) = &shot.golden {
                    inner.insert("golden".into(), json!(golden));
                }
                inner.insert("per_px".into(), json!(shot.per_px));
                inner.insert("max_bad_ratio".into(), json!(shot.max_bad_ratio));
                if let Some(mask) = &shot.mask {
                    inner.insert("mask".into(), json!(mask));
                }
                json!({ "screenshot": Value::Object(inner) })
            }
            Self::Unknown(value) => value.clone(),
        }
    }

    pub fn label(&self) -> String {
        match self {
            Self::Event(event) => format!("event {}", event.name),
            Self::World(world) => format!(
                "world {}.{}.{}",
                world.entity_tag, world.component, world.field
            ),
            Self::Screenshot(_) => "screenshot".into(),
            Self::Unknown(_) => "unknown".into(),
        }
    }
}

fn parse_assert(value: &Value) -> Result<GAssert, RpcError> {
    let obj = value
        .as_object()
        .ok_or_else(|| invalid_params("gtest assert must be an object"))?;
    if let Some(event) = obj.get("event") {
        return Ok(GAssert::Event(parse_event(event)?));
    }
    if let Some(world) = obj.get("world") {
        return Ok(GAssert::World(parse_world(world)?));
    }
    if let Some(shot) = obj.get("screenshot") {
        return Ok(GAssert::Screenshot(parse_screenshot(shot)?));
    }
    Ok(GAssert::Unknown(value.clone()))
}

fn parse_event(value: &Value) -> Result<EventAssert, RpcError> {
    let mut obj = match value {
        Value::Object(map) => map.clone(),
        _ => return Err(invalid_params("event assert must be an object")),
    };
    let name =
        take_string(&mut obj, "name")?.ok_or_else(|| invalid_params("event.name is required"))?;
    let after = take_string(&mut obj, "after")?;
    Ok(EventAssert {
        name,
        after,
        extra: obj,
    })
}

fn parse_world(value: &Value) -> Result<WorldAssert, RpcError> {
    let mut obj = match value {
        Value::Object(map) => map.clone(),
        _ => return Err(invalid_params("world assert must be an object")),
    };
    let entity_tag = take_string(&mut obj, "entity_tag")?
        .ok_or_else(|| invalid_params("world.entity_tag is required"))?;
    let component = take_string(&mut obj, "component")?
        .ok_or_else(|| invalid_params("world.component is required"))?;
    let field =
        take_string(&mut obj, "field")?.ok_or_else(|| invalid_params("world.field is required"))?;
    let equals = obj
        .remove("equals")
        .ok_or_else(|| invalid_params("world.equals is required"))?;
    Ok(WorldAssert {
        entity_tag,
        component,
        field,
        equals,
        extra: obj,
    })
}

fn parse_screenshot(value: &Value) -> Result<ScreenshotAssert, RpcError> {
    let mut obj = match value {
        Value::Object(map) => map.clone(),
        _ => return Err(invalid_params("screenshot assert must be an object")),
    };
    let golden = take_string(&mut obj, "golden")?;
    let mask = take_string(&mut obj, "mask")?;
    let per_px = take_u64(&mut obj, "per_px")?
        .unwrap_or(u64::from(DEFAULT_PER_PX))
        .min(u64::from(u32::MAX)) as u32;
    let max_bad_ratio = match obj.remove("max_bad_ratio") {
        None | Some(Value::Null) => DEFAULT_MAX_BAD_RATIO,
        Some(v) => v
            .as_f64()
            .ok_or_else(|| invalid_params("screenshot.max_bad_ratio must be a number"))?,
    };
    Ok(ScreenshotAssert {
        golden,
        per_px,
        max_bad_ratio,
        mask,
        extra: obj,
    })
}

/// Jail `rel` under `root` via [`resolve_under_root`] (I7).
pub fn resolve_project_rel(root: &Path, rel: &str, must_exist: bool) -> Result<PathBuf, RpcError> {
    if rel.is_empty() || rel.contains('\0') {
        return Err(invalid_params("path is invalid"));
    }
    let normalized = rel.replace('\\', "/");
    let joined = match resolve_under_root(root, &normalized) {
        Ok(path) => path,
        Err(SceneError::PathEscapesRoot { path }) => {
            return Err(app_err(
                "E_PATH",
                format!("path {path} is not under the project root"),
            ));
        }
        Err(other) => return Err(scene_err(other)),
    };
    if must_exist && !joined.exists() {
        return Err(app_err("E_NOT_FOUND", format!("not found: {rel}")));
    }
    if let Ok(resolved) = joined.canonicalize() {
        if let Ok(root_abs) = root.canonicalize() {
            if resolved != root_abs && !resolved.starts_with(&root_abs) {
                return Err(app_err(
                    "E_PATH",
                    format!("path {rel} is not under the project root"),
                ));
            }
        }
    }
    Ok(joined)
}

pub fn rel_from_root(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .unwrap_or(path)
        .to_string_lossy()
        .replace('\\', "/")
}

/// Compare a `{entity_tag,component,field,equals}` check against the live dump
/// (runtime) and, if needed, the open document (tags / components not in dump).
pub fn check_world_assert(
    dump: &Value,
    session: Option<&Session>,
    spec: &WorldAssert,
) -> Result<(), String> {
    let entity = find_dump_entity(dump, session, &spec.entity_tag)
        .ok_or_else(|| format!("no entity with tag/name {}", spec.entity_tag))?;
    let actual = field_from_dump(&entity, &spec.component, &spec.field)
        .or_else(|| {
            session.and_then(|s| {
                document_entity(s, &spec.entity_tag)
                    .and_then(|ent| field_from_entity(ent, &spec.component, &spec.field))
            })
        })
        .ok_or_else(|| {
            format!(
                "missing {}.{} on {}",
                spec.component, spec.field, spec.entity_tag
            )
        })?;
    if values_close(&actual, &spec.equals, WORLD_EPSILON) {
        Ok(())
    } else {
        Err(format!(
            "{}.{} actual={actual} expected={}",
            spec.component, spec.field, spec.equals
        ))
    }
}

fn find_dump_entity(dump: &Value, session: Option<&Session>, tag: &str) -> Option<Value> {
    let entities = dump.get("entities")?.as_array()?;
    if let Some(found) = entities.iter().find(|ent| dump_matches_tag(ent, tag)) {
        return Some(found.clone());
    }
    let id = session.and_then(|s| document_entity(s, tag).map(|e| e.id_str()))?;
    entities
        .iter()
        .find(|ent| ent.get("id").and_then(Value::as_str) == Some(id.as_str()))
        .cloned()
}

fn dump_matches_tag(entity: &Value, tag: &str) -> bool {
    if entity.get("name").and_then(Value::as_str) == Some(tag) {
        return true;
    }
    entity
        .get("tags")
        .and_then(Value::as_array)
        .is_some_and(|tags| tags.iter().any(|t| t.as_str() == Some(tag)))
}

fn document_entity<'a>(session: &'a Session, tag: &str) -> Option<&'a Entity> {
    session.document().scene.entities.values().find(|entity| {
        entity.name.as_ref().is_some_and(|n| n.value == tag)
            || entity
                .tags
                .as_ref()
                .is_some_and(|tags| tags.values.iter().any(|t| t == tag))
    })
}

fn field_from_dump(entity: &Value, component: &str, field: &str) -> Option<Value> {
    match component {
        "Name" if field == "value" => entity.get("name").cloned(),
        "Transform2D" => entity.get("transform")?.get(field).cloned(),
        "Collider2D" => entity.get("collider")?.get(field).cloned(),
        "Tags" if field == "values" => entity.get("tags").cloned(),
        _ => entity
            .get(component)
            .and_then(|c| c.get(field))
            .cloned()
            .or_else(|| entity.get(field).cloned()),
    }
}

fn field_from_entity(entity: &Entity, component: &str, field: &str) -> Option<Value> {
    match component {
        "Name" if field == "value" => entity.name.as_ref().map(|n| json!(n.value)),
        "Tags" if field == "values" => entity.tags.as_ref().map(|t| json!(t.values)),
        "Transform2D" => {
            let t = entity.transform.as_ref()?;
            match field {
                "x" => Some(json!(t.x)),
                "y" => Some(json!(t.y)),
                "rot" => Some(json!(t.rot)),
                "sx" => Some(json!(t.sx)),
                "sy" => Some(json!(t.sy)),
                "z_index" => Some(json!(t.z_index)),
                _ => None,
            }
        }
        "Collider2D" => {
            let c = entity.extra.collider.as_ref()?;
            collider_field(c, field)
        }
        _ => None,
    }
}

fn collider_field(c: &Collider2D, field: &str) -> Option<Value> {
    match field {
        "is_sensor" => Some(json!(c.is_sensor)),
        "layer" => Some(json!(c.layer)),
        "mask" => Some(json!(c.mask)),
        "friction" => Some(json!(c.friction)),
        "restitution" => Some(json!(c.restitution)),
        _ => None,
    }
}

fn values_close(actual: &Value, expected: &Value, epsilon: f64) -> bool {
    match (actual, expected) {
        (Value::Number(a), Value::Number(b)) => {
            let (Some(af), Some(bf)) = (a.as_f64(), b.as_f64()) else {
                return false;
            };
            (af - bf).abs() <= epsilon
        }
        _ => actual == expected,
    }
}

fn take_string(obj: &mut Map<String, Value>, key: &str) -> Result<Option<String>, RpcError> {
    match obj.remove(key) {
        None | Some(Value::Null) => Ok(None),
        Some(Value::String(s)) => Ok(Some(s)),
        Some(_) => Err(invalid_params(format!("{key} must be a string"))),
    }
}

fn take_u64(obj: &mut Map<String, Value>, key: &str) -> Result<Option<u64>, RpcError> {
    match obj.remove(key) {
        None | Some(Value::Null) => Ok(None),
        Some(v) => v
            .as_u64()
            .map(Some)
            .ok_or_else(|| invalid_params(format!("{key} must be a u64"))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[test]
    fn parse_keeps_unknown_fields() {
        let value = json!({
            "name": "door_opens_with_key",
            "scene": "scenes/main.gscene.json",
            "seed": 7,
            "tape": "tapes/get_key.tape.jsonl",
            "max_frames": 600,
            "asserts": [
                {"event": {"name": "KeyPicked"}},
                {"event": {"name": "DoorOpened", "after": "KeyPicked"}},
                {"world": {
                    "entity_tag": "door",
                    "component": "Collider2D",
                    "field": "is_sensor",
                    "equals": true
                }},
                {"screenshot": {
                    "golden": "golden/door_open.png",
                    "per_px": 8,
                    "max_bad_ratio": 0.002,
                    "mask": "golden/door_open.mask.png"
                }}
            ],
            "expect_diagnostics_max": 0,
            "note": "agent-written"
        });
        let gtest = GTest::from_value(value).expect("parse");
        assert_eq!(gtest.name, "door_opens_with_key");
        assert_eq!(gtest.seed, 7);
        assert_eq!(gtest.asserts.len(), 4);
        assert_eq!(gtest.extra.get("note"), Some(&json!("agent-written")));
        match &gtest.asserts[1] {
            GAssert::Event(event) => assert_eq!(event.after.as_deref(), Some("KeyPicked")),
            other => panic!("expected event, got {other:?}"),
        }
    }

    #[test]
    fn resolve_rejects_dotdot() {
        let dir = TempDir::new().expect("temp");
        let err =
            resolve_project_rel(dir.path(), "../secret.gtest.json", false).expect_err("dotdot");
        assert_eq!(
            err.data.as_ref().map(|d| d.app_code.as_str()),
            Some("E_PATH")
        );
        let err = resolve_project_rel(dir.path(), "tests/../../x.gtest.json", false)
            .expect_err("nested dotdot");
        assert_eq!(
            err.data.as_ref().map(|d| d.app_code.as_str()),
            Some("E_PATH")
        );
    }

    #[test]
    fn resolve_accepts_nested_rel() {
        let dir = TempDir::new().expect("temp");
        let dest = dir.path().join("tests");
        fs::create_dir_all(&dest).expect("mkdir");
        let file = dest.join("coin.gtest.json");
        fs::write(&file, "{}").expect("write");
        let got = resolve_project_rel(dir.path(), "tests/coin.gtest.json", true).expect("ok");
        assert_eq!(got, file);
    }
}
