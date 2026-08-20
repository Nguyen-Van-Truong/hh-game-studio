//! Inspector payload: schema fields + current document values (MASTER 9.3).

use std::collections::BTreeMap;

use gs_scene::Entity;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};

use crate::assets::{AssetCatalog, AssetRecord};
use crate::schema::{component_specs, FieldKind, FieldSpec};

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AssetPreview {
    pub width: u32,
    pub height: u32,
    pub kind: String,
    pub dest_rel: String,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InspectorField {
    pub name: String,
    pub kind: FieldKind,
    pub value: Value,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub exclusive_min: Option<f64>,
    pub abs_min: Option<f64>,
    pub abs_max: Option<f64>,
    pub max_len: Option<usize>,
    pub max_items: Option<usize>,
    pub variants: Option<Vec<String>>,
    pub preview: Option<AssetPreview>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InspectorComponent {
    pub type_name: String,
    pub present: bool,
    pub value: Value,
    pub fields: Vec<InspectorField>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InspectorView {
    pub id: String,
    pub revision: String,
    pub components: Vec<InspectorComponent>,
}

/// JSON map of every component currently on the entity (known + unknown).
pub fn entity_components_json(entity: &Entity) -> BTreeMap<String, Value> {
    let mut map = BTreeMap::new();
    if let Some(n) = &entity.name {
        map.insert("Name".into(), json!({ "value": n.value }));
    }
    if let Some(t) = &entity.tags {
        map.insert("Tags".into(), json!({ "values": t.values }));
    }
    if let Some(t) = &entity.transform {
        map.insert(
            "Transform2D".into(),
            json!({
                "x": t.x,
                "y": t.y,
                "rot": t.rot,
                "sx": t.sx,
                "sy": t.sy,
                "z_index": t.z_index,
            }),
        );
    }
    if let Some(s) = &entity.extra.sprite {
        map.insert(
            "Sprite".into(),
            json!({
                "asset": s.asset.to_value(),
                "color": s.color,
                "flip_x": s.flip_x,
                "flip_y": s.flip_y,
                "pivot": s.pivot,
            }),
        );
    }
    if let Some(a) = &entity.extra.anim_flipbook {
        map.insert(
            "AnimFlipbook".into(),
            json!({
                "frames": a.frames.iter().map(gs_scene::AssetRef::to_value).collect::<Vec<_>>(),
                "fps": a.fps,
                "playing": a.playing,
                "loop": a.loop_play,
                "frame_index": a.frame_index,
            }),
        );
    }
    if let Some(c) = &entity.extra.camera {
        map.insert(
            "Camera2D".into(),
            json!({
                "ortho_height": c.ortho_height,
                "active": c.active,
            }),
        );
    }
    if let Some(r) = &entity.extra.rigid_body {
        map.insert(
            "RigidBody2D".into(),
            json!({
                "kind": r.kind,
                "ccd": r.ccd,
                "gravity_scale": r.gravity_scale,
                "fixed_rotation": r.fixed_rotation,
                "linear_damping": r.linear_damping,
            }),
        );
    }
    if let Some(c) = &entity.extra.collider {
        let shape = match &c.shape {
            gs_scene::ColliderShape::Box { w, h } => json!({ "box": { "w": w, "h": h } }),
            gs_scene::ColliderShape::Circle { r } => json!({ "circle": { "r": r } }),
            gs_scene::ColliderShape::Capsule { half_h, r } => {
                json!({ "capsule": { "half_h": half_h, "r": r } })
            }
        };
        map.insert(
            "Collider2D".into(),
            json!({
                "shape": shape,
                "is_sensor": c.is_sensor,
                "offset": c.offset,
                "layer": c.layer,
                "mask": c.mask,
                "friction": c.friction,
                "restitution": c.restitution,
            }),
        );
    }
    if let Some(t) = &entity.extra.tilemap {
        let layers: Vec<Value> = t
            .layers
            .iter()
            .map(|layer| {
                json!({
                    "name": layer.name,
                    "solid": layer.solid,
                    "cells": layer.cells,
                })
            })
            .collect();
        map.insert(
            "Tilemap".into(),
            json!({
                "tileset": t.tileset.to_value(),
                "cell_size": t.cell_size,
                "layers": layers,
            }),
        );
    }
    if let Some(t) = &entity.extra.text {
        map.insert(
            "Text2D".into(),
            json!({
                "text": t.text,
                "font": t.font.as_ref().map(gs_scene::AssetRef::to_value),
                "size_pt": t.size_pt,
                "color": t.color,
                "align": t.align,
            }),
        );
    }
    if let Some(a) = &entity.extra.audio {
        map.insert(
            "AudioSource".into(),
            json!({
                "asset": a.asset.to_value(),
                "volume": a.volume,
                "pan": a.pan,
                "loop": a.loop_play,
                "autoplay": a.autoplay,
            }),
        );
    }
    if let Some(s) = &entity.extra.script {
        map.insert(
            "Script".into(),
            json!({
                "file": s.file,
                "props": s.props,
            }),
        );
    }
    if let Some(v) = &entity.extra.visibility {
        map.insert("Visibility".into(), json!({ "visible": v.visible }));
    }
    for (k, v) in &entity.extra.unknown {
        map.insert(k.clone(), v.clone());
    }
    for (type_name, unk) in &entity.component_unknown {
        if let Some(Value::Object(obj)) = map.get_mut(type_name) {
            for (k, v) in unk {
                obj.entry(k.clone()).or_insert_with(|| v.clone());
            }
        }
    }
    map
}

pub fn build_inspector(
    entity_id: &str,
    revision: &str,
    entity: &Entity,
    assets: &AssetCatalog,
) -> InspectorView {
    let values = entity_components_json(entity);
    let mut components = Vec::new();
    for spec in component_specs() {
        let present = values.contains_key(spec.type_name);
        let value = values
            .get(spec.type_name)
            .cloned()
            .unwrap_or(Value::Object(Map::new()));
        let fields = spec
            .fields
            .iter()
            .map(|field| field_view(field, &value, assets))
            .collect();
        components.push(InspectorComponent {
            type_name: spec.type_name.to_owned(),
            present,
            value,
            fields,
        });
    }
    for (type_name, value) in &values {
        if component_specs().iter().any(|s| s.type_name == type_name) {
            continue;
        }
        components.push(InspectorComponent {
            type_name: type_name.clone(),
            present: true,
            value: value.clone(),
            fields: vec![InspectorField {
                name: "value".into(),
                kind: FieldKind::Object,
                value: value.clone(),
                min: None,
                max: None,
                exclusive_min: None,
                abs_min: None,
                abs_max: None,
                max_len: None,
                max_items: None,
                variants: None,
                preview: None,
            }],
        });
    }
    InspectorView {
        id: entity_id.to_owned(),
        revision: revision.to_owned(),
        components,
    }
}

fn field_view(field: &FieldSpec, component: &Value, assets: &AssetCatalog) -> InspectorField {
    let value = component.get(field.name).cloned().unwrap_or(Value::Null);
    let preview = if field.kind == FieldKind::Asset {
        asset_id_from_value(&value).and_then(|id| assets.get(&id).map(preview_of))
    } else {
        None
    };
    InspectorField {
        name: field.name.to_owned(),
        kind: field.kind,
        value,
        min: field.min,
        max: field.max,
        exclusive_min: field.exclusive_min,
        abs_min: field.abs_min,
        abs_max: field.abs_max,
        max_len: field.max_len,
        max_items: field.max_items,
        variants: field
            .variants
            .map(|v| v.iter().map(|s| (*s).to_owned()).collect()),
        preview,
    }
}

fn asset_id_from_value(value: &Value) -> Option<String> {
    value
        .get("$asset")
        .and_then(Value::as_str)
        .map(ToOwned::to_owned)
}

fn preview_of(record: &AssetRecord) -> AssetPreview {
    AssetPreview {
        width: record.width,
        height: record.height,
        kind: record.kind.clone(),
        dest_rel: record.dest_rel.clone(),
    }
}
