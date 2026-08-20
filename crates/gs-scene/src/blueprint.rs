//! Blueprint stamp (MASTER 5.3): local `b_N` ids, no back-link, no override.

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Component, Path, PathBuf};

use serde_json::{json, Value};

use crate::components::{remap_tagged_refs, validate_name};
use crate::document::{collect_cascade, entity_components_map, Entity, Scene};
use crate::error::Error;
use crate::id::{format_blueprint_id, format_entity_id};

const RESERVED: &[&str] = &[
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
    "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

pub fn resolve_under_root(root: &Path, rel: &str) -> Result<PathBuf, Error> {
    if rel.is_empty() {
        return Err(Error::invalid("path", "empty path"));
    }
    if rel.len() > 200 {
        return Err(Error::invalid("path", "path longer than 200 characters"));
    }
    let rel_path = Path::new(rel);
    if rel_path.is_absolute() {
        return Err(Error::PathEscapesRoot {
            path: rel.to_string(),
        });
    }
    for c in rel_path.components() {
        match c {
            Component::Normal(s) => {
                let name = s.to_string_lossy();
                let stem = name.split('.').next().unwrap_or(&name);
                if RESERVED.iter().any(|r| stem.eq_ignore_ascii_case(r)) {
                    return Err(Error::invalid(
                        "path",
                        format!("Windows reserved name {name}"),
                    ));
                }
            }
            _ => {
                return Err(Error::PathEscapesRoot {
                    path: rel.to_string(),
                });
            }
        }
    }
    Ok(root.join(rel_path))
}

pub fn validate_blueprint_rel(rel: &str) -> Result<(), Error> {
    if !rel.starts_with("blueprints/") || !rel.ends_with(".gbp.json") {
        return Err(Error::invalid(
            "blueprint",
            "path must be blueprints/*.gbp.json",
        ));
    }
    Ok(())
}

pub fn export_tree(scene: &Scene, root_id: u64) -> Result<Value, Error> {
    if !scene.entities.contains_key(&root_id) {
        return Err(Error::NotFound(format_entity_id(root_id)));
    }
    let mut ids = BTreeSet::new();
    collect_cascade(scene, root_id, &mut ids);
    let mut ordered: Vec<u64> = ids.iter().copied().collect();
    ordered.sort_by(|a, b| {
        let da = if *a == root_id { 0 } else { 1 };
        let db = if *b == root_id { 0 } else { 1 };
        da.cmp(&db).then(a.cmp(b))
    });
    let mut local: BTreeMap<u64, String> = BTreeMap::new();
    for (i, id) in ordered.iter().enumerate() {
        local.insert(*id, format_blueprint_id((i as u64).saturating_add(1)));
    }
    let str_map: BTreeMap<String, String> = local
        .iter()
        .map(|(k, v)| (format_entity_id(*k), v.clone()))
        .collect();

    let mut entities = Vec::new();
    for id in &ordered {
        let ent = scene
            .entities
            .get(id)
            .ok_or_else(|| Error::NotFound(format_entity_id(*id)))?;
        let parent = ent.parent.and_then(|p| local.get(&p).cloned());
        let comps = remap_tagged_refs(
            &Value::Object(entity_components_map(ent).into_iter().collect()),
            &str_map,
        );
        let mut obj = serde_json::Map::new();
        obj.insert("id".into(), json!(local[id].clone()));
        obj.insert(
            "parent".into(),
            parent.map(Value::String).unwrap_or(Value::Null),
        );
        obj.insert("order".into(), json!(ent.order));
        obj.insert("components".into(), comps);
        for (k, v) in &ent.unknown {
            obj.insert(k.clone(), v.clone());
        }
        entities.push(Value::Object(obj));
    }
    Ok(json!({
        "schema_version": 1,
        "entities": entities,
    }))
}

pub struct StampedEntity {
    pub id: u64,
    pub parent: Option<u64>,
    pub order: u32,
    pub components: Value,
    pub unknown: BTreeMap<String, Value>,
}

pub fn stamp_tree(
    gbp: &Value,
    next_entity: u64,
    at: Option<(f32, f32)>,
    name_prefix: Option<&str>,
) -> Result<(Vec<StampedEntity>, u64), Error> {
    let arr = gbp
        .get("entities")
        .and_then(Value::as_array)
        .ok_or_else(|| Error::invalid("blueprint.instantiate", "entities array required"))?;
    if arr.is_empty() {
        return Err(Error::invalid("blueprint.instantiate", "empty blueprint"));
    }
    let mut local_to_new: BTreeMap<String, String> = BTreeMap::new();
    let mut local_to_num: BTreeMap<String, u64> = BTreeMap::new();
    let mut next = next_entity;
    for e in arr.iter() {
        let local = e
            .get("id")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::invalid("blueprint.instantiate", "entity missing id"))?;
        let new_id = next;
        next = next.saturating_add(1);
        local_to_new.insert(local.to_string(), format_entity_id(new_id));
        local_to_num.insert(local.to_string(), new_id);
    }

    let mut out = Vec::new();
    for (i, e) in arr.iter().enumerate() {
        let local = e.get("id").and_then(Value::as_str).expect("checked");
        let id = local_to_num[local];
        let parent = match e.get("parent") {
            None | Some(Value::Null) => None,
            Some(Value::String(p)) => Some(
                *local_to_num
                    .get(p)
                    .ok_or_else(|| Error::invalid("blueprint.instantiate", "unknown parent"))?,
            ),
            _ => {
                return Err(Error::invalid(
                    "blueprint.instantiate",
                    "parent must be string or null",
                ))
            }
        };
        let order = e.get("order").and_then(Value::as_u64).unwrap_or(0) as u32;
        let mut comps = remap_tagged_refs(e.get("components").unwrap_or(&json!({})), &local_to_new);
        if i == 0 {
            if let Some((x, y)) = at {
                apply_at(&mut comps, x, y);
            }
        }
        if let Some(prefix) = name_prefix {
            apply_name_prefix(&mut comps, prefix)?;
        }
        let mut unknown = BTreeMap::new();
        if let Some(obj) = e.as_object() {
            for (k, v) in obj {
                if matches!(k.as_str(), "id" | "parent" | "order" | "components") {
                    continue;
                }
                unknown.insert(k.clone(), v.clone());
            }
        }
        out.push(StampedEntity {
            id,
            parent,
            order,
            components: comps,
            unknown,
        });
    }
    Ok((out, next))
}

fn apply_at(comps: &mut Value, x: f32, y: f32) {
    let obj = match comps {
        Value::Object(m) => m,
        _ => return,
    };
    let mut t = obj.get("Transform2D").cloned().unwrap_or_else(|| json!({}));
    if let Value::Object(tm) = &mut t {
        tm.insert("x".into(), json!(x));
        tm.insert("y".into(), json!(y));
    }
    obj.insert("Transform2D".into(), t);
}

fn apply_name_prefix(comps: &mut Value, prefix: &str) -> Result<(), Error> {
    let obj = match comps {
        Value::Object(m) => m,
        _ => return Ok(()),
    };
    let current = obj
        .get("Name")
        .and_then(|n| n.get("value"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let value = format!("{prefix}{current}");
    validate_name(&value)?;
    obj.insert("Name".into(), json!({ "value": value }));
    Ok(())
}

pub fn stamped_to_json(entities: &[StampedEntity]) -> Value {
    let arr: Vec<Value> = entities
        .iter()
        .map(|e| {
            let mut obj = serde_json::Map::new();
            obj.insert("id".into(), json!(format_entity_id(e.id)));
            obj.insert(
                "parent".into(),
                e.parent
                    .map(format_entity_id)
                    .map(Value::String)
                    .unwrap_or(Value::Null),
            );
            obj.insert("order".into(), json!(e.order));
            obj.insert("components".into(), e.components.clone());
            for (k, v) in &e.unknown {
                obj.insert(k.clone(), v.clone());
            }
            Value::Object(obj)
        })
        .collect();
    Value::Array(arr)
}

pub fn insert_stamped(scene: &mut Scene, entities: &[StampedEntity]) -> Result<(), Error> {
    for e in entities {
        let parsed = crate::components::parse_components(&e.components)?;
        let mut ent = Entity::new(e.id, e.parent, e.order);
        ent.name = parsed.name;
        ent.transform = parsed
            .transform
            .or_else(|| Some(crate::components::Transform2D::identity()));
        ent.tags = parsed.tags;
        ent.extra = parsed.extra;
        ent.component_unknown = parsed.field_unknown;
        ent.unknown = e.unknown.clone();
        scene.entities.insert(e.id, ent);
    }
    Ok(())
}

pub fn parse_at(value: Option<&Value>) -> Result<Option<(f32, f32)>, Error> {
    let Some(v) = value else {
        return Ok(None);
    };
    if v.is_null() {
        return Ok(None);
    }
    if let Some(arr) = v.as_array() {
        if arr.len() != 2 {
            return Err(Error::invalid("blueprint.instantiate", "at must be [x,y]"));
        }
        let x = crate::components::finite_f32_value(&arr[0], "at[0]", "blueprint.instantiate")?;
        let y = crate::components::finite_f32_value(&arr[1], "at[1]", "blueprint.instantiate")?;
        return Ok(Some((x, y)));
    }
    if v.is_object() {
        let x = crate::components::finite_f32(v, "x", "blueprint.instantiate")?;
        let y = crate::components::finite_f32(v, "y", "blueprint.instantiate")?;
        return Ok(Some((x, y)));
    }
    Err(Error::invalid(
        "blueprint.instantiate",
        "at must be {x,y} or [x,y]",
    ))
}
