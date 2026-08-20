//! Component registry v1 (MASTER 5.2) plus unknown-field maps (I5 / GS-EC-11).

use std::collections::BTreeMap;

use serde_json::{json, Map, Value};

use crate::canonical::json_f32;
use crate::error::Error;
use crate::id::{parse_asset_id, parse_entity_id};

pub const MAX_NAME_LEN: usize = 256;
pub const MAX_TAG_LEN: usize = 64;
pub const MAX_TAGS: usize = 32;
pub const SCALE_MIN: f32 = 0.001;
pub const SCALE_MAX: f32 = 1000.0;
pub const Z_INDEX_MIN: i32 = -10_000;
pub const Z_INDEX_MAX: i32 = 10_000;
pub const MAX_FLIPBOOK_FRAMES: usize = 256;
pub const MAX_TILEMAP_LAYERS: usize = 8;
/// GS-EC-06: sum of RLE run lengths across the whole tilemap.
pub const MAX_TILEMAP_EXPANDED_CELLS: i64 = 1_000_000;
/// GS-EC-06: reject absurd cell coordinates (hint: split layers).
pub const MAX_TILEMAP_COORD: i64 = 100_000;
/// MASTER 5.5 blob CAS is not implemented; reject inline WAL patches over 1 MiB.
pub const MAX_TILEMAP_INLINE_WAL_BYTES: usize = 1_048_576;
pub const MAX_TEXT_LEN: usize = 4096;
pub const MAX_SCRIPT_PROPS: usize = 64;
pub const MAX_SCRIPT_ARRAY: usize = 64;

pub const KNOWN_COMPONENT_TYPES: &[&str] = &[
    "Name",
    "Tags",
    "Transform2D",
    "Sprite",
    "AnimFlipbook",
    "Camera2D",
    "RigidBody2D",
    "Collider2D",
    "Tilemap",
    "Text2D",
    "AudioSource",
    "Script",
    "Visibility",
];

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AssetRef {
    pub id: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EntityRef {
    pub id: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Name {
    pub value: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Tags {
    pub values: Vec<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Transform2D {
    pub x: f32,
    pub y: f32,
    pub rot: f32,
    pub sx: f32,
    pub sy: f32,
    pub z_index: i32,
}

impl Transform2D {
    pub fn identity() -> Self {
        Self {
            x: 0.0,
            y: 0.0,
            rot: 0.0,
            sx: 1.0,
            sy: 1.0,
            z_index: 0,
        }
    }

    pub fn validate(&self) -> Result<(), Error> {
        validate_transform(self)
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct Sprite {
    pub asset: AssetRef,
    pub color: [f32; 4],
    pub flip_x: bool,
    pub flip_y: bool,
    pub pivot: [f32; 2],
}

#[derive(Clone, Debug, PartialEq)]
pub struct AnimFlipbook {
    pub frames: Vec<AssetRef>,
    pub fps: f32,
    pub playing: bool,
    pub loop_play: bool,
    pub frame_index: u32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Camera2D {
    pub ortho_height: f32,
    pub active: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct RigidBody2D {
    pub kind: String,
    pub ccd: bool,
    pub gravity_scale: f32,
    pub fixed_rotation: bool,
    pub linear_damping: f32,
}

#[derive(Clone, Debug, PartialEq)]
pub enum ColliderShape {
    Box { w: f32, h: f32 },
    Circle { r: f32 },
    Capsule { half_h: f32, r: f32 },
}

#[derive(Clone, Debug, PartialEq)]
pub struct Collider2D {
    pub shape: ColliderShape,
    pub is_sensor: bool,
    pub offset: [f32; 2],
    pub layer: u32,
    pub mask: u32,
    pub friction: f32,
    pub restitution: f32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct TilemapLayer {
    pub name: String,
    pub solid: bool,
    pub cells: Vec<[i64; 4]>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Tilemap {
    pub tileset: AssetRef,
    pub cell_size: [f32; 2],
    pub layers: Vec<TilemapLayer>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Text2D {
    pub text: String,
    pub font: Option<AssetRef>,
    pub size_pt: f32,
    pub color: [f32; 4],
    pub align: String,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AudioSource {
    pub asset: AssetRef,
    pub volume: f32,
    pub pan: f32,
    pub loop_play: bool,
    pub autoplay: bool,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Script {
    pub file: String,
    pub props: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Visibility {
    pub visible: bool,
}

#[derive(Clone, Debug, PartialEq, Default)]
pub struct ExtraComponents {
    pub sprite: Option<Sprite>,
    pub anim_flipbook: Option<AnimFlipbook>,
    pub camera: Option<Camera2D>,
    pub rigid_body: Option<RigidBody2D>,
    pub collider: Option<Collider2D>,
    pub tilemap: Option<Tilemap>,
    pub text: Option<Text2D>,
    pub audio: Option<AudioSource>,
    pub script: Option<Script>,
    pub visibility: Option<Visibility>,
    pub unknown: BTreeMap<String, Value>,
}

#[derive(Clone, Debug, PartialEq, Default)]
pub struct ParsedComponents {
    pub name: Option<Name>,
    pub transform: Option<Transform2D>,
    pub tags: Option<Tags>,
    pub extra: ExtraComponents,
    pub field_unknown: BTreeMap<String, BTreeMap<String, Value>>,
}

pub fn is_known_component(type_name: &str) -> bool {
    KNOWN_COMPONENT_TYPES.contains(&type_name)
}

pub fn parse_components(value: &Value) -> Result<ParsedComponents, Error> {
    let obj = value
        .as_object()
        .ok_or_else(|| Error::invalid("components", "must be an object"))?;
    let mut parsed = ParsedComponents::default();
    for (key, val) in obj {
        apply_component_json(&mut parsed, key, val)?;
    }
    Ok(parsed)
}

fn apply_component_json(
    parsed: &mut ParsedComponents,
    type_name: &str,
    value: &Value,
) -> Result<(), Error> {
    if !is_known_component(type_name) {
        parsed
            .extra
            .unknown
            .insert(type_name.to_string(), value.clone());
        return Ok(());
    }
    let (known, unknown) = split_unknown(type_name, value)?;
    if !unknown.is_empty() {
        parsed.field_unknown.insert(type_name.to_string(), unknown);
    }
    match type_name {
        "Name" => {
            let name = merge_name(None, &known)?;
            validate_name(&name.value)?;
            parsed.name = Some(name);
        }
        "Tags" => {
            let tags = merge_tags(None, &known)?;
            validate_tags(&tags)?;
            parsed.tags = Some(tags);
        }
        "Transform2D" => {
            let t = merge_transform(None, &known)?;
            t.validate()?;
            parsed.transform = Some(t);
        }
        "Sprite" => parsed.extra.sprite = Some(parse_sprite(&known)?),
        "AnimFlipbook" => parsed.extra.anim_flipbook = Some(parse_anim(&known)?),
        "Camera2D" => parsed.extra.camera = Some(parse_camera(&known)?),
        "RigidBody2D" => parsed.extra.rigid_body = Some(parse_rigid_body(&known)?),
        "Collider2D" => parsed.extra.collider = Some(parse_collider(&known)?),
        "Tilemap" => parsed.extra.tilemap = Some(parse_tilemap(&known)?),
        "Text2D" => parsed.extra.text = Some(parse_text(&known)?),
        "AudioSource" => parsed.extra.audio = Some(parse_audio(&known)?),
        "Script" => parsed.extra.script = Some(parse_script(&known)?),
        "Visibility" => parsed.extra.visibility = Some(parse_visibility(&known)?),
        _ => {}
    }
    Ok(())
}

pub fn components_to_json(p: &ParsedComponents) -> Value {
    let mut map = Map::new();
    insert_known(&mut map, p);
    for (k, v) in &p.extra.unknown {
        map.insert(k.clone(), v.clone());
    }
    Value::Object(map)
}

fn insert_known(map: &mut Map<String, Value>, p: &ParsedComponents) {
    if let Some(ref n) = p.name {
        map.insert("Name".into(), merge_unknown("Name", name_json(Some(n)), p));
    }
    if let Some(ref t) = p.tags {
        map.insert("Tags".into(), merge_unknown("Tags", tags_json(Some(t)), p));
    }
    if let Some(ref t) = p.transform {
        map.insert(
            "Transform2D".into(),
            merge_unknown("Transform2D", transform_json(Some(t)), p),
        );
    }
    if let Some(ref s) = p.extra.sprite {
        map.insert("Sprite".into(), merge_unknown("Sprite", sprite_json(s), p));
    }
    if let Some(ref a) = p.extra.anim_flipbook {
        map.insert(
            "AnimFlipbook".into(),
            merge_unknown("AnimFlipbook", anim_json(a), p),
        );
    }
    if let Some(ref c) = p.extra.camera {
        map.insert(
            "Camera2D".into(),
            merge_unknown("Camera2D", camera_json(c), p),
        );
    }
    if let Some(ref r) = p.extra.rigid_body {
        map.insert(
            "RigidBody2D".into(),
            merge_unknown("RigidBody2D", rigid_body_json(r), p),
        );
    }
    if let Some(ref c) = p.extra.collider {
        map.insert(
            "Collider2D".into(),
            merge_unknown("Collider2D", collider_json(c), p),
        );
    }
    if let Some(ref t) = p.extra.tilemap {
        map.insert(
            "Tilemap".into(),
            merge_unknown("Tilemap", tilemap_json(t), p),
        );
    }
    if let Some(ref t) = p.extra.text {
        map.insert("Text2D".into(), merge_unknown("Text2D", text_json(t), p));
    }
    if let Some(ref a) = p.extra.audio {
        map.insert(
            "AudioSource".into(),
            merge_unknown("AudioSource", audio_json(a), p),
        );
    }
    if let Some(ref s) = p.extra.script {
        map.insert("Script".into(), merge_unknown("Script", script_json(s), p));
    }
    if let Some(ref v) = p.extra.visibility {
        map.insert(
            "Visibility".into(),
            merge_unknown("Visibility", visibility_json(v), p),
        );
    }
}

fn merge_unknown(type_name: &str, mut known: Value, p: &ParsedComponents) -> Value {
    if let Some(unk) = p.field_unknown.get(type_name) {
        if let Value::Object(map) = &mut known {
            for (k, v) in unk {
                map.insert(k.clone(), v.clone());
            }
        }
    }
    known
}

pub fn name_json(name: Option<&Name>) -> Value {
    json!({ "value": name.map(|n| n.value.as_str()).unwrap_or("") })
}

pub fn tags_json(tags: Option<&Tags>) -> Value {
    json!({ "values": tags.map(|t| t.values.clone()).unwrap_or_default() })
}

pub fn transform_json(t: Option<&Transform2D>) -> Value {
    let t = t.cloned().unwrap_or_else(Transform2D::identity);
    let mut m = Map::new();
    m.insert("rot".into(), json_f32(t.rot));
    m.insert("sx".into(), json_f32(t.sx));
    m.insert("sy".into(), json_f32(t.sy));
    m.insert("x".into(), json_f32(t.x));
    m.insert("y".into(), json_f32(t.y));
    m.insert("z_index".into(), json!(t.z_index));
    Value::Object(m)
}

fn sprite_json(s: &Sprite) -> Value {
    json!({
        "asset": s.asset.to_value(),
        "color": s.color.iter().copied().map(json_f32).collect::<Vec<_>>(),
        "flip_x": s.flip_x,
        "flip_y": s.flip_y,
        "pivot": s.pivot.iter().copied().map(json_f32).collect::<Vec<_>>(),
    })
}

fn anim_json(a: &AnimFlipbook) -> Value {
    json!({
        "frames": a.frames.iter().map(AssetRef::to_value).collect::<Vec<_>>(),
        "fps": json_f32(a.fps),
        "playing": a.playing,
        "loop": a.loop_play,
        "frame_index": a.frame_index,
    })
}

fn camera_json(c: &Camera2D) -> Value {
    json!({
        "ortho_height": json_f32(c.ortho_height),
        "active": c.active,
    })
}

fn rigid_body_json(r: &RigidBody2D) -> Value {
    json!({
        "kind": r.kind,
        "ccd": r.ccd,
        "gravity_scale": json_f32(r.gravity_scale),
        "fixed_rotation": r.fixed_rotation,
        "linear_damping": json_f32(r.linear_damping),
    })
}

fn collider_json(c: &Collider2D) -> Value {
    let shape = match c.shape {
        ColliderShape::Box { w, h } => json!({ "box": { "w": json_f32(w), "h": json_f32(h) } }),
        ColliderShape::Circle { r } => json!({ "circle": { "r": json_f32(r) } }),
        ColliderShape::Capsule { half_h, r } => {
            json!({ "capsule": { "half_h": json_f32(half_h), "r": json_f32(r) } })
        }
    };
    json!({
        "shape": shape,
        "is_sensor": c.is_sensor,
        "offset": c.offset.iter().copied().map(json_f32).collect::<Vec<_>>(),
        "layer": c.layer,
        "mask": c.mask,
        "friction": json_f32(c.friction),
        "restitution": json_f32(c.restitution),
    })
}

fn tilemap_json(t: &Tilemap) -> Value {
    let layers: Vec<Value> = t
        .layers
        .iter()
        .map(|l| {
            json!({
                "name": l.name,
                "solid": l.solid,
                "cells": l.cells,
            })
        })
        .collect();
    json!({
        "tileset": t.tileset.to_value(),
        "cell_size": t.cell_size.iter().copied().map(json_f32).collect::<Vec<_>>(),
        "layers": layers,
    })
}

fn text_json(t: &Text2D) -> Value {
    json!({
        "text": t.text,
        "font": t.font.as_ref().map(AssetRef::to_value).unwrap_or(Value::Null),
        "size_pt": json_f32(t.size_pt),
        "color": t.color.iter().copied().map(json_f32).collect::<Vec<_>>(),
        "align": t.align,
    })
}

fn audio_json(a: &AudioSource) -> Value {
    json!({
        "asset": a.asset.to_value(),
        "volume": json_f32(a.volume),
        "pan": json_f32(a.pan),
        "loop": a.loop_play,
        "autoplay": a.autoplay,
    })
}

fn script_json(s: &Script) -> Value {
    json!({
        "file": s.file,
        "props": Value::Object(s.props.iter().map(|(k, v)| (k.clone(), v.clone())).collect()),
    })
}

fn visibility_json(v: &Visibility) -> Value {
    json!({ "visible": v.visible })
}

pub fn merge_name(old: Option<&Name>, patch: &Value) -> Result<Name, Error> {
    let value = if let Some(v) = patch.get("value") {
        v.as_str()
            .ok_or_else(|| Error::invalid("Name", "value must be a string"))?
            .to_string()
    } else {
        old.map(|n| n.value.clone()).unwrap_or_default()
    };
    Ok(Name { value })
}

pub fn merge_tags(old: Option<&Tags>, patch: &Value) -> Result<Tags, Error> {
    let values = if let Some(v) = patch.get("values") {
        let arr = v
            .as_array()
            .ok_or_else(|| Error::invalid("Tags", "values must be an array"))?;
        let mut out = Vec::new();
        for item in arr {
            let s = item
                .as_str()
                .ok_or_else(|| Error::invalid("Tags", "tag must be a string"))?;
            out.push(s.to_string());
        }
        out
    } else {
        old.map(|t| t.values.clone()).unwrap_or_default()
    };
    Ok(Tags { values })
}

pub fn merge_transform(old: Option<&Transform2D>, patch: &Value) -> Result<Transform2D, Error> {
    let mut t = old.cloned().unwrap_or_else(Transform2D::identity);
    if patch.get("x").is_some() {
        t.x = finite_f32(patch, "x", "Transform2D")?;
    }
    if patch.get("y").is_some() {
        t.y = finite_f32(patch, "y", "Transform2D")?;
    }
    if patch.get("rot").is_some() {
        t.rot = finite_f32(patch, "rot", "Transform2D")?;
    }
    if patch.get("sx").is_some() {
        t.sx = finite_f32(patch, "sx", "Transform2D")?;
    }
    if patch.get("sy").is_some() {
        t.sy = finite_f32(patch, "sy", "Transform2D")?;
    }
    if patch.get("z_index").is_some() {
        t.z_index = i32_field(patch, "z_index", "Transform2D")?;
    }
    Ok(t)
}

pub fn validate_transform(t: &Transform2D) -> Result<(), Error> {
    for (name, v) in [
        ("x", t.x),
        ("y", t.y),
        ("rot", t.rot),
        ("sx", t.sx),
        ("sy", t.sy),
    ] {
        if v.is_nan() {
            return Err(Error::invalid(
                "Transform2D",
                format!("{name} must be finite (NaN rejected)"),
            ));
        }
        if v.is_infinite() {
            return Err(Error::invalid(
                "Transform2D",
                format!("{name} must be finite (Inf rejected)"),
            ));
        }
    }
    for (name, v) in [("sx", t.sx), ("sy", t.sy)] {
        let a = v.abs();
        if !(SCALE_MIN..=SCALE_MAX).contains(&a) {
            return Err(Error::invalid(
                "Transform2D",
                format!("{name} scale {v} rejected (need |s| in {SCALE_MIN}..{SCALE_MAX})"),
            ));
        }
    }
    if !(Z_INDEX_MIN..=Z_INDEX_MAX).contains(&t.z_index) {
        return Err(Error::invalid(
            "Transform2D",
            format!("z_index {} out of range", t.z_index),
        ));
    }
    Ok(())
}

pub fn validate_name(name: &str) -> Result<(), Error> {
    if name.len() > MAX_NAME_LEN {
        return Err(Error::invalid(
            "Name",
            format!("value longer than {MAX_NAME_LEN}"),
        ));
    }
    Ok(())
}

pub fn validate_tags(tags: &Tags) -> Result<(), Error> {
    if tags.values.len() > MAX_TAGS {
        return Err(Error::invalid("Tags", format!("more than {MAX_TAGS} tags")));
    }
    for t in &tags.values {
        if t.len() > MAX_TAG_LEN {
            return Err(Error::invalid(
                "Tags",
                format!("tag longer than {MAX_TAG_LEN}"),
            ));
        }
        if !t
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_')
        {
            return Err(Error::invalid(
                "Tags",
                format!("tag {t:?} must match [a-z0-9_]"),
            ));
        }
    }
    Ok(())
}

fn known_keys(type_name: &str) -> &'static [&'static str] {
    match type_name {
        "Name" => &["value"],
        "Tags" => &["values"],
        "Transform2D" => &["x", "y", "rot", "sx", "sy", "z_index"],
        "Sprite" => &["asset", "color", "flip_x", "flip_y", "pivot"],
        "AnimFlipbook" => &["frames", "fps", "playing", "loop", "frame_index"],
        "Camera2D" => &["ortho_height", "active"],
        "RigidBody2D" => &[
            "kind",
            "ccd",
            "gravity_scale",
            "fixed_rotation",
            "linear_damping",
        ],
        "Collider2D" => &[
            "shape",
            "is_sensor",
            "offset",
            "layer",
            "mask",
            "friction",
            "restitution",
        ],
        "Tilemap" => &["tileset", "cell_size", "layers"],
        "Text2D" => &["text", "font", "size_pt", "color", "align"],
        "AudioSource" => &["asset", "volume", "pan", "loop", "autoplay"],
        "Script" => &["file", "props"],
        "Visibility" => &["visible"],
        _ => &[],
    }
}

fn split_unknown(
    type_name: &str,
    value: &Value,
) -> Result<(Value, BTreeMap<String, Value>), Error> {
    let obj = value
        .as_object()
        .ok_or_else(|| Error::invalid(type_name, "component value must be an object"))?;
    let keys = known_keys(type_name);
    let mut known = Map::new();
    let mut unknown = BTreeMap::new();
    for (k, v) in obj {
        if keys.contains(&k.as_str()) {
            known.insert(k.clone(), v.clone());
        } else {
            unknown.insert(k.clone(), v.clone());
        }
    }
    Ok((Value::Object(known), unknown))
}

impl AssetRef {
    pub fn parse(value: &Value, ctx: &str) -> Result<Self, Error> {
        if value.is_string() {
            return Err(Error::invalid(
                ctx,
                "bare JSON string is never an asset id (need {$asset})",
            ));
        }
        let obj = value
            .as_object()
            .ok_or_else(|| Error::invalid(ctx, "asset ref must be {\"$asset\":\"a_…\"}"))?;
        let id = obj
            .get("$asset")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::invalid(ctx, "missing $asset"))?;
        parse_asset_id(id)?;
        Ok(Self { id: id.to_string() })
    }

    pub fn to_value(&self) -> Value {
        json!({ "$asset": self.id })
    }
}

impl EntityRef {
    pub fn parse(value: &Value, ctx: &str) -> Result<Self, Error> {
        if value.is_string() {
            return Err(Error::invalid(
                ctx,
                "bare JSON string is never an entity id (need {$entity})",
            ));
        }
        let obj = value
            .as_object()
            .ok_or_else(|| Error::invalid(ctx, "entity ref must be {\"$entity\":\"e_…\"}"))?;
        let id = obj
            .get("$entity")
            .and_then(Value::as_str)
            .ok_or_else(|| Error::invalid(ctx, "missing $entity"))?;
        parse_entity_id(id)?;
        Ok(Self { id: id.to_string() })
    }

    pub fn to_value(&self) -> Value {
        json!({ "$entity": self.id })
    }
}

fn parse_sprite(v: &Value) -> Result<Sprite, Error> {
    let asset = AssetRef::parse(
        v.get("asset")
            .ok_or_else(|| Error::invalid("Sprite", "missing asset"))?,
        "Sprite.asset",
    )?;
    let color = opt_color(v, "color", [1.0, 1.0, 1.0, 1.0], "Sprite")?;
    let flip_x = opt_bool(v, "flip_x", false, "Sprite")?;
    let flip_y = opt_bool(v, "flip_y", false, "Sprite")?;
    let pivot = opt_vec2(v, "pivot", [0.5, 0.0], "Sprite")?;
    for (i, c) in color.iter().enumerate() {
        if !(0.0..=1.0).contains(c) {
            return Err(Error::invalid(
                "Sprite",
                format!("color[{i}] must be in 0..1"),
            ));
        }
    }
    for (i, p) in pivot.iter().enumerate() {
        if !(0.0..=1.0).contains(p) {
            return Err(Error::invalid(
                "Sprite",
                format!("pivot[{i}] must be in 0..1"),
            ));
        }
    }
    Ok(Sprite {
        asset,
        color,
        flip_x,
        flip_y,
        pivot,
    })
}

fn parse_anim(v: &Value) -> Result<AnimFlipbook, Error> {
    let frames_v = v
        .get("frames")
        .and_then(Value::as_array)
        .ok_or_else(|| Error::invalid("AnimFlipbook", "frames must be an array"))?;
    if frames_v.len() > MAX_FLIPBOOK_FRAMES {
        return Err(Error::invalid(
            "AnimFlipbook",
            format!("more than {MAX_FLIPBOOK_FRAMES} frames"),
        ));
    }
    let mut frames = Vec::new();
    for (i, f) in frames_v.iter().enumerate() {
        frames.push(AssetRef::parse(f, &format!("AnimFlipbook.frames[{i}]"))?);
    }
    let fps = finite_f32(v, "fps", "AnimFlipbook")?;
    if !(0.1..=120.0).contains(&fps) {
        return Err(Error::invalid("AnimFlipbook", "fps must be in 0.1..120"));
    }
    Ok(AnimFlipbook {
        frames,
        fps,
        playing: opt_bool(v, "playing", true, "AnimFlipbook")?,
        loop_play: opt_bool(v, "loop", true, "AnimFlipbook")?,
        frame_index: opt_u32(v, "frame_index", 0, "AnimFlipbook")?,
    })
}

fn parse_camera(v: &Value) -> Result<Camera2D, Error> {
    let ortho_height = finite_f32(v, "ortho_height", "Camera2D")?;
    if ortho_height <= 0.0 {
        return Err(Error::invalid("Camera2D", "ortho_height must be > 0"));
    }
    Ok(Camera2D {
        ortho_height,
        active: opt_bool(v, "active", true, "Camera2D")?,
    })
}

fn parse_rigid_body(v: &Value) -> Result<RigidBody2D, Error> {
    let kind = v
        .get("kind")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::invalid("RigidBody2D", "missing kind"))?;
    if !matches!(kind, "static" | "dynamic" | "kinematic") {
        return Err(Error::invalid(
            "RigidBody2D",
            "kind must be static|dynamic|kinematic",
        ));
    }
    let gravity_scale = opt_finite(v, "gravity_scale", 1.0, "RigidBody2D")?;
    let linear_damping = opt_finite(v, "linear_damping", 0.0, "RigidBody2D")?;
    if linear_damping < 0.0 {
        return Err(Error::invalid("RigidBody2D", "linear_damping must be >= 0"));
    }
    Ok(RigidBody2D {
        kind: kind.to_string(),
        ccd: opt_bool(v, "ccd", false, "RigidBody2D")?,
        gravity_scale,
        fixed_rotation: opt_bool(v, "fixed_rotation", false, "RigidBody2D")?,
        linear_damping,
    })
}

fn parse_collider(v: &Value) -> Result<Collider2D, Error> {
    let shape_v = v
        .get("shape")
        .ok_or_else(|| Error::invalid("Collider2D", "missing shape"))?;
    let shape = parse_shape(shape_v)?;
    let friction = opt_finite(v, "friction", 0.5, "Collider2D")?;
    if !(0.0..=2.0).contains(&friction) {
        return Err(Error::invalid("Collider2D", "friction must be in 0..2"));
    }
    let restitution = opt_finite(v, "restitution", 0.0, "Collider2D")?;
    if !(0.0..=1.0).contains(&restitution) {
        return Err(Error::invalid("Collider2D", "restitution must be in 0..1"));
    }
    Ok(Collider2D {
        shape,
        is_sensor: opt_bool(v, "is_sensor", false, "Collider2D")?,
        offset: opt_vec2(v, "offset", [0.0, 0.0], "Collider2D")?,
        layer: opt_u32(v, "layer", 1, "Collider2D")?,
        mask: opt_u32(v, "mask", u32::MAX, "Collider2D")?,
        friction,
        restitution,
    })
}

fn parse_shape(v: &Value) -> Result<ColliderShape, Error> {
    let obj = v
        .as_object()
        .ok_or_else(|| Error::invalid("Collider2D", "shape must be an object"))?;
    if let Some(b) = obj.get("box") {
        let w = finite_f32(b, "w", "Collider2D.box")?;
        let h = finite_f32(b, "h", "Collider2D.box")?;
        if w <= 0.0 || h <= 0.0 {
            return Err(Error::invalid("Collider2D", "box w/h must be > 0"));
        }
        return Ok(ColliderShape::Box { w, h });
    }
    if let Some(c) = obj.get("circle") {
        let r = finite_f32(c, "r", "Collider2D.circle")?;
        if r <= 0.0 {
            return Err(Error::invalid("Collider2D", "circle r must be > 0"));
        }
        return Ok(ColliderShape::Circle { r });
    }
    if let Some(c) = obj.get("capsule") {
        let half_h = finite_f32(c, "half_h", "Collider2D.capsule")?;
        let r = finite_f32(c, "r", "Collider2D.capsule")?;
        if half_h <= 0.0 || r <= 0.0 {
            return Err(Error::invalid("Collider2D", "capsule half_h/r must be > 0"));
        }
        return Ok(ColliderShape::Capsule { half_h, r });
    }
    Err(Error::invalid(
        "Collider2D",
        "shape must be box|circle|capsule",
    ))
}

fn parse_tilemap(v: &Value) -> Result<Tilemap, Error> {
    let tileset = AssetRef::parse(
        v.get("tileset")
            .ok_or_else(|| Error::invalid("Tilemap", "missing tileset"))?,
        "Tilemap.tileset",
    )?;
    let cell_size = opt_vec2(v, "cell_size", [1.0, 1.0], "Tilemap")?;
    if cell_size[0] <= 0.0 || cell_size[1] <= 0.0 {
        return Err(Error::invalid("Tilemap", "cell_size must be > 0"));
    }
    let mut layers = Vec::new();
    let mut expanded = 0i64;
    if let Some(arr) = v.get("layers") {
        let arr = arr
            .as_array()
            .ok_or_else(|| Error::invalid("Tilemap", "layers must be an array"))?;
        if arr.len() > MAX_TILEMAP_LAYERS {
            return Err(Error::invalid(
                "Tilemap",
                format!("more than {MAX_TILEMAP_LAYERS} layers"),
            ));
        }
        for layer in arr {
            let name = layer
                .get("name")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let solid = opt_bool(layer, "solid", false, "Tilemap.layer")?;
            let mut cells = Vec::new();
            if let Some(c) = layer.get("cells").and_then(Value::as_array) {
                for run in c {
                    let run = run
                        .as_array()
                        .ok_or_else(|| Error::invalid("Tilemap", "RLE run must be an array"))?;
                    if run.len() != 4 {
                        return Err(Error::invalid("Tilemap", "RLE run must be [x,y,len,tile]"));
                    }
                    let x = run[0]
                        .as_i64()
                        .ok_or_else(|| Error::invalid("Tilemap", "RLE x must be int"))?;
                    let y = run[1]
                        .as_i64()
                        .ok_or_else(|| Error::invalid("Tilemap", "RLE y must be int"))?;
                    let len = run[2]
                        .as_i64()
                        .ok_or_else(|| Error::invalid("Tilemap", "RLE len must be int"))?;
                    let tile = run[3]
                        .as_i64()
                        .ok_or_else(|| Error::invalid("Tilemap", "RLE tile must be int"))?;
                    crate::tilemap::validate_rle_run(x, y, len, tile, "Tilemap", false)?;
                    expanded = expanded
                        .checked_add(len)
                        .ok_or_else(|| crate::tilemap::too_many_cells("Tilemap"))?;
                    if expanded > MAX_TILEMAP_EXPANDED_CELLS {
                        return Err(crate::tilemap::too_many_cells("Tilemap"));
                    }
                    cells.push([x, y, len, tile]);
                }
            }
            cells = crate::tilemap::canonicalize_cells(&cells);
            layers.push(TilemapLayer { name, solid, cells });
        }
    }
    Ok(Tilemap {
        tileset,
        cell_size,
        layers,
    })
}

fn parse_text(v: &Value) -> Result<Text2D, Error> {
    let text = v
        .get("text")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::invalid("Text2D", "missing text"))?
        .to_string();
    if text.len() > MAX_TEXT_LEN {
        return Err(Error::invalid(
            "Text2D",
            format!("text longer than {MAX_TEXT_LEN}"),
        ));
    }
    let font = match v.get("font") {
        None | Some(Value::Null) => None,
        Some(f) => Some(AssetRef::parse(f, "Text2D.font")?),
    };
    let size_pt = opt_finite(v, "size_pt", 16.0, "Text2D")?;
    if !(4.0..=512.0).contains(&size_pt) {
        return Err(Error::invalid("Text2D", "size_pt must be in 4..512"));
    }
    let color = opt_color(v, "color", [1.0, 1.0, 1.0, 1.0], "Text2D")?;
    let align = v
        .get("align")
        .and_then(Value::as_str)
        .unwrap_or("left")
        .to_string();
    if !matches!(align.as_str(), "left" | "center" | "right") {
        return Err(Error::invalid("Text2D", "align must be left|center|right"));
    }
    Ok(Text2D {
        text,
        font,
        size_pt,
        color,
        align,
    })
}

fn parse_audio(v: &Value) -> Result<AudioSource, Error> {
    let asset = AssetRef::parse(
        v.get("asset")
            .ok_or_else(|| Error::invalid("AudioSource", "missing asset"))?,
        "AudioSource.asset",
    )?;
    let volume = opt_finite(v, "volume", 1.0, "AudioSource")?;
    if !(0.0..=2.0).contains(&volume) {
        return Err(Error::invalid("AudioSource", "volume must be in 0..2"));
    }
    let pan = opt_finite(v, "pan", 0.0, "AudioSource")?;
    if !(-1.0..=1.0).contains(&pan) {
        return Err(Error::invalid("AudioSource", "pan must be in -1..1"));
    }
    Ok(AudioSource {
        asset,
        volume,
        pan,
        loop_play: opt_bool(v, "loop", false, "AudioSource")?,
        autoplay: opt_bool(v, "autoplay", false, "AudioSource")?,
    })
}

fn parse_script(v: &Value) -> Result<Script, Error> {
    let file = v
        .get("file")
        .and_then(Value::as_str)
        .ok_or_else(|| Error::invalid("Script", "missing file"))?
        .to_string();
    validate_script_path(&file)?;
    let mut props = BTreeMap::new();
    if let Some(p) = v.get("props") {
        let obj = p
            .as_object()
            .ok_or_else(|| Error::invalid("Script", "props must be an object"))?;
        if obj.len() > MAX_SCRIPT_PROPS {
            return Err(Error::invalid(
                "Script",
                format!("more than {MAX_SCRIPT_PROPS} props"),
            ));
        }
        for (k, val) in obj {
            validate_script_prop(val, k)?;
            props.insert(k.clone(), val.clone());
        }
    }
    Ok(Script { file, props })
}

fn parse_visibility(v: &Value) -> Result<Visibility, Error> {
    Ok(Visibility {
        visible: opt_bool(v, "visible", true, "Visibility")?,
    })
}

pub fn validate_script_path(file: &str) -> Result<(), Error> {
    if !file.starts_with("scripts/") || !file.ends_with(".luau") {
        return Err(Error::invalid(
            "Script",
            "file must be a .luau path under scripts/",
        ));
    }
    if file.contains("..") || file.contains('\\') {
        return Err(Error::invalid("Script", "file path escapes scripts/"));
    }
    Ok(())
}

fn validate_script_prop(value: &Value, key: &str) -> Result<(), Error> {
    match value {
        Value::Null | Value::Bool(_) | Value::Number(_) | Value::String(_) => Ok(()),
        Value::Array(items) => {
            if items.len() > MAX_SCRIPT_ARRAY {
                return Err(Error::invalid(
                    "Script",
                    format!("prop {key} array longer than {MAX_SCRIPT_ARRAY}"),
                ));
            }
            for item in items {
                validate_script_prop(item, key)?;
            }
            Ok(())
        }
        Value::Object(map) => {
            if map.contains_key("$entity") {
                EntityRef::parse(value, &format!("Script.props.{key}"))?;
                return Ok(());
            }
            if map.contains_key("$asset") {
                AssetRef::parse(value, &format!("Script.props.{key}"))?;
                return Ok(());
            }
            Err(Error::invalid(
                "Script",
                format!("prop {key} must be scalar, {{$entity}}, {{$asset}}, or array"),
            ))
        }
    }
}

pub fn merge_json_objects(base: Value, patch: &Value) -> Value {
    match (base, patch) {
        (Value::Object(mut a), Value::Object(b)) => {
            for (k, v) in b {
                a.insert(k.clone(), v.clone());
            }
            Value::Object(a)
        }
        (_, patch) => patch.clone(),
    }
}

pub fn remap_tagged_refs(value: &Value, entity_map: &BTreeMap<String, String>) -> Value {
    match value {
        Value::Array(items) => Value::Array(
            items
                .iter()
                .map(|i| remap_tagged_refs(i, entity_map))
                .collect(),
        ),
        Value::Object(map) => {
            if let Some(id) = map.get("$entity").and_then(Value::as_str) {
                if let Some(new_id) = entity_map.get(id) {
                    return json!({ "$entity": new_id });
                }
                return value.clone();
            }
            let mut out = Map::new();
            for (k, v) in map {
                out.insert(k.clone(), remap_tagged_refs(v, entity_map));
            }
            Value::Object(out)
        }
        other => other.clone(),
    }
}

pub fn finite_f32(params: &Value, key: &str, ctx: &str) -> Result<f32, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(ctx, format!("missing {key}")));
    };
    finite_f32_value(v, key, ctx)
}

pub fn finite_f32_value(v: &Value, key: &str, ctx: &str) -> Result<f32, Error> {
    if let Some(s) = v.as_str() {
        return Err(Error::invalid(
            ctx,
            format!("{key} must be finite ({s} rejected)"),
        ));
    }
    let Some(f) = v.as_f64() else {
        return Err(Error::invalid(ctx, format!("{key} must be a number")));
    };
    if !f.is_finite() {
        return Err(Error::invalid(
            ctx,
            format!("{key} must be finite (NaN/Inf rejected)"),
        ));
    }
    Ok(f as f32)
}

fn opt_finite(params: &Value, key: &str, default: f32, ctx: &str) -> Result<f32, Error> {
    if params.get(key).is_none() {
        return Ok(default);
    }
    finite_f32(params, key, ctx)
}

fn opt_bool(params: &Value, key: &str, default: bool, ctx: &str) -> Result<bool, Error> {
    match params.get(key) {
        None => Ok(default),
        Some(v) => v
            .as_bool()
            .ok_or_else(|| Error::invalid(ctx, format!("{key} must be bool"))),
    }
}

fn opt_u32(params: &Value, key: &str, default: u32, ctx: &str) -> Result<u32, Error> {
    match params.get(key) {
        None => Ok(default),
        Some(v) => v
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| Error::invalid(ctx, format!("{key} must be u32"))),
    }
}

fn opt_vec2(params: &Value, key: &str, default: [f32; 2], ctx: &str) -> Result<[f32; 2], Error> {
    let Some(v) = params.get(key) else {
        return Ok(default);
    };
    let arr = v
        .as_array()
        .ok_or_else(|| Error::invalid(ctx, format!("{key} must be [x,y]")))?;
    if arr.len() != 2 {
        return Err(Error::invalid(ctx, format!("{key} must have 2 elements")));
    }
    Ok([
        finite_f32_value(&arr[0], &format!("{key}[0]"), ctx)?,
        finite_f32_value(&arr[1], &format!("{key}[1]"), ctx)?,
    ])
}

fn opt_color(params: &Value, key: &str, default: [f32; 4], ctx: &str) -> Result<[f32; 4], Error> {
    let Some(v) = params.get(key) else {
        return Ok(default);
    };
    let arr = v
        .as_array()
        .ok_or_else(|| Error::invalid(ctx, format!("{key} must be [r,g,b,a]")))?;
    if arr.len() != 4 {
        return Err(Error::invalid(ctx, format!("{key} must have 4 elements")));
    }
    Ok([
        finite_f32_value(&arr[0], &format!("{key}[0]"), ctx)?,
        finite_f32_value(&arr[1], &format!("{key}[1]"), ctx)?,
        finite_f32_value(&arr[2], &format!("{key}[2]"), ctx)?,
        finite_f32_value(&arr[3], &format!("{key}[3]"), ctx)?,
    ])
}

fn i32_field(params: &Value, key: &str, method: &str) -> Result<i32, Error> {
    let Some(v) = params.get(key) else {
        return Err(Error::invalid(method, format!("missing {key}")));
    };
    if let Some(n) = v.as_i64() {
        return i32::try_from(n).map_err(|_| Error::invalid(method, format!("{key} out of range")));
    }
    Err(Error::invalid(method, format!("{key} must be i32")))
}
