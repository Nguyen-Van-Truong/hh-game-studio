//! Schema-driven component registry (MASTER 5.2). Inspector widgets iterate this
//! table — a new component type is a new row, not a new widget function.

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};

/// All MASTER 5.2 component type names, in table order.
pub const MASTER_5_2_TYPES: &[&str] = &[
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

/// Widget kind. The inspector matches on this, never on the component type name.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FieldKind {
    String,
    F32,
    I32,
    U32,
    Bool,
    Enum,
    Asset,
    Color,
    Vec2,
    Tags,
    Object,
    Array,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FieldSpec {
    pub name: &'static str,
    pub kind: FieldKind,
    pub min: Option<f64>,
    pub max: Option<f64>,
    pub exclusive_min: Option<f64>,
    pub abs_min: Option<f64>,
    pub abs_max: Option<f64>,
    pub max_len: Option<usize>,
    pub max_items: Option<usize>,
    pub variants: Option<&'static [&'static str]>,
    pub pattern: Option<&'static str>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ComponentSpec {
    pub type_name: &'static str,
    pub fields: &'static [FieldSpec],
}

const fn f32_range(name: &'static str, min: f64, max: f64) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::F32,
        min: Some(min),
        max: Some(max),
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn f32_gt(name: &'static str, exclusive_min: f64) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::F32,
        min: None,
        max: None,
        exclusive_min: Some(exclusive_min),
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn f32_plain(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::F32,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn f32_min(name: &'static str, min: f64) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::F32,
        min: Some(min),
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn i32_range(name: &'static str, min: f64, max: f64) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::I32,
        min: Some(min),
        max: Some(max),
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn u32_plain(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::U32,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn bool_field(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Bool,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn string_field(name: &'static str, max_len: usize) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::String,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: Some(max_len),
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn enum_field(name: &'static str, variants: &'static [&'static str]) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Enum,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: Some(variants),
        pattern: None,
    }
}

const fn asset_field(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Asset,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn color_field(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Color,
        min: Some(0.0),
        max: Some(1.0),
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn vec2_01(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Vec2,
        min: Some(0.0),
        max: Some(1.0),
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn vec2_plain(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Vec2,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn vec2_gt0(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Vec2,
        min: None,
        max: None,
        exclusive_min: Some(0.0),
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn object_field(name: &'static str) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Object,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: None,
        variants: None,
        pattern: None,
    }
}

const fn array_field(name: &'static str, max_items: usize) -> FieldSpec {
    FieldSpec {
        name,
        kind: FieldKind::Array,
        min: None,
        max: None,
        exclusive_min: None,
        abs_min: None,
        abs_max: None,
        max_len: None,
        max_items: Some(max_items),
        variants: None,
        pattern: None,
    }
}

const SCALE: FieldSpec = FieldSpec {
    name: "sx",
    kind: FieldKind::F32,
    min: None,
    max: None,
    exclusive_min: None,
    abs_min: Some(0.001),
    abs_max: Some(1000.0),
    max_len: None,
    max_items: None,
    variants: None,
    pattern: None,
};

const SCALE_Y: FieldSpec = FieldSpec {
    name: "sy",
    kind: FieldKind::F32,
    min: None,
    max: None,
    exclusive_min: None,
    abs_min: Some(0.001),
    abs_max: Some(1000.0),
    max_len: None,
    max_items: None,
    variants: None,
    pattern: None,
};

const TAGS: FieldSpec = FieldSpec {
    name: "values",
    kind: FieldKind::Tags,
    min: None,
    max: None,
    exclusive_min: None,
    abs_min: None,
    abs_max: None,
    max_len: Some(64),
    max_items: Some(32),
    variants: None,
    pattern: Some("^[a-z0-9_]+$"),
};

const NAME_FIELDS: &[FieldSpec] = &[string_field("value", 256)];
const TAGS_FIELDS: &[FieldSpec] = &[TAGS];
const TRANSFORM_FIELDS: &[FieldSpec] = &[
    f32_plain("x"),
    f32_plain("y"),
    f32_plain("rot"),
    SCALE,
    SCALE_Y,
    i32_range("z_index", -10_000.0, 10_000.0),
];
const SPRITE_FIELDS: &[FieldSpec] = &[
    asset_field("asset"),
    color_field("color"),
    bool_field("flip_x"),
    bool_field("flip_y"),
    vec2_01("pivot"),
];
const ANIM_FIELDS: &[FieldSpec] = &[
    array_field("frames", 256),
    f32_range("fps", 0.1, 120.0),
    bool_field("playing"),
    bool_field("loop"),
    u32_plain("frame_index"),
];
const CAMERA_FIELDS: &[FieldSpec] = &[f32_gt("ortho_height", 0.0), bool_field("active")];
const RIGID_FIELDS: &[FieldSpec] = &[
    enum_field("kind", &["static", "dynamic", "kinematic"]),
    bool_field("ccd"),
    f32_plain("gravity_scale"),
    bool_field("fixed_rotation"),
    f32_min("linear_damping", 0.0),
];
const COLLIDER_FIELDS: &[FieldSpec] = &[
    object_field("shape"),
    bool_field("is_sensor"),
    vec2_plain("offset"),
    u32_plain("layer"),
    u32_plain("mask"),
    f32_range("friction", 0.0, 2.0),
    f32_range("restitution", 0.0, 1.0),
];
const TILEMAP_FIELDS: &[FieldSpec] = &[
    asset_field("tileset"),
    vec2_gt0("cell_size"),
    array_field("layers", 8),
];
const TEXT_FIELDS: &[FieldSpec] = &[
    string_field("text", 4096),
    asset_field("font"),
    f32_range("size_pt", 4.0, 512.0),
    color_field("color"),
    enum_field("align", &["left", "center", "right"]),
];
const AUDIO_FIELDS: &[FieldSpec] = &[
    asset_field("asset"),
    f32_range("volume", 0.0, 2.0),
    f32_range("pan", -1.0, 1.0),
    bool_field("loop"),
    bool_field("autoplay"),
];
const SCRIPT_FIELDS: &[FieldSpec] = &[string_field("file", 200), object_field("props")];
const VIS_FIELDS: &[FieldSpec] = &[bool_field("visible")];

const SPECS: &[ComponentSpec] = &[
    ComponentSpec {
        type_name: "Name",
        fields: NAME_FIELDS,
    },
    ComponentSpec {
        type_name: "Tags",
        fields: TAGS_FIELDS,
    },
    ComponentSpec {
        type_name: "Transform2D",
        fields: TRANSFORM_FIELDS,
    },
    ComponentSpec {
        type_name: "Sprite",
        fields: SPRITE_FIELDS,
    },
    ComponentSpec {
        type_name: "AnimFlipbook",
        fields: ANIM_FIELDS,
    },
    ComponentSpec {
        type_name: "Camera2D",
        fields: CAMERA_FIELDS,
    },
    ComponentSpec {
        type_name: "RigidBody2D",
        fields: RIGID_FIELDS,
    },
    ComponentSpec {
        type_name: "Collider2D",
        fields: COLLIDER_FIELDS,
    },
    ComponentSpec {
        type_name: "Tilemap",
        fields: TILEMAP_FIELDS,
    },
    ComponentSpec {
        type_name: "Text2D",
        fields: TEXT_FIELDS,
    },
    ComponentSpec {
        type_name: "AudioSource",
        fields: AUDIO_FIELDS,
    },
    ComponentSpec {
        type_name: "Script",
        fields: SCRIPT_FIELDS,
    },
    ComponentSpec {
        type_name: "Visibility",
        fields: VIS_FIELDS,
    },
];

/// Owned schema table. Adding a type = append a [`ComponentSpec`], not a widget.
pub fn component_specs() -> &'static [ComponentSpec] {
    SPECS
}

pub fn spec_by_type(type_name: &str) -> Option<&'static ComponentSpec> {
    SPECS.iter().find(|s| s.type_name == type_name)
}

/// Clamp a numeric inspector edit to the field schema (MASTER 9.3).
pub fn clamp_to_schema(field: &FieldSpec, value: f64) -> f64 {
    let mut v = value;
    if let Some(min) = field.min {
        v = v.max(min);
    }
    if let Some(max) = field.max {
        v = v.min(max);
    }
    if let Some(emin) = field.exclusive_min {
        if v <= emin {
            v = emin + 0.001;
        }
    }
    if let (Some(amin), Some(amax)) = (field.abs_min, field.abs_max) {
        let sign = if v.is_sign_negative() { -1.0 } else { 1.0 };
        v = sign * v.abs().clamp(amin, amax);
    }
    v
}

pub fn default_component_value(type_name: &str) -> Value {
    match type_name {
        "Name" => json!({ "value": "New" }),
        "Tags" => json!({ "values": [] }),
        "Transform2D" => json!({
            "x": 0.0, "y": 0.0, "rot": 0.0, "sx": 1.0, "sy": 1.0, "z_index": 0
        }),
        "Sprite" => json!({
            "asset": { "$asset": "a_000001" },
            "color": [1.0, 1.0, 1.0, 1.0],
            "flip_x": false,
            "flip_y": false,
            "pivot": [0.5, 0.0]
        }),
        "AnimFlipbook" => json!({
            "frames": [],
            "fps": 12.0,
            "playing": true,
            "loop": true,
            "frame_index": 0
        }),
        "Camera2D" => json!({ "ortho_height": 10.0, "active": true }),
        "RigidBody2D" => json!({
            "kind": "dynamic",
            "ccd": false,
            "gravity_scale": 1.0,
            "fixed_rotation": false,
            "linear_damping": 0.0
        }),
        "Collider2D" => json!({
            "shape": { "box": { "w": 1.0, "h": 1.0 } },
            "is_sensor": false,
            "offset": [0.0, 0.0],
            "layer": 1,
            "mask": u32::MAX,
            "friction": 0.5,
            "restitution": 0.0
        }),
        "Tilemap" => json!({
            "tileset": { "$asset": "a_000001" },
            "cell_size": [1.0, 1.0],
            "layers": []
        }),
        "Text2D" => json!({
            "text": "",
            "font": null,
            "size_pt": 16.0,
            "color": [1.0, 1.0, 1.0, 1.0],
            "align": "left"
        }),
        "AudioSource" => json!({
            "asset": { "$asset": "a_000001" },
            "volume": 1.0,
            "pan": 0.0,
            "loop": false,
            "autoplay": false
        }),
        "Script" => json!({ "file": "scripts/new.luau", "props": {} }),
        "Visibility" => json!({ "visible": true }),
        _ => json!({}),
    }
}

pub fn registry_json() -> Value {
    let types: Vec<Value> = SPECS
        .iter()
        .map(|spec| {
            json!({
                "type": spec.type_name,
                "fields": spec.fields.iter().map(field_json).collect::<Vec<_>>(),
            })
        })
        .collect();
    json!({
        "names": MASTER_5_2_TYPES,
        "types": types,
    })
}

fn field_json(field: &FieldSpec) -> Value {
    json!({
        "name": field.name,
        "kind": field.kind,
        "min": field.min,
        "max": field.max,
        "exclusive_min": field.exclusive_min,
        "abs_min": field.abs_min,
        "abs_max": field.abs_max,
        "max_len": field.max_len,
        "max_items": field.max_items,
        "variants": field.variants,
        "pattern": field.pattern,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_covers_master_5_2_and_is_data() {
        assert_eq!(SPECS.len(), MASTER_5_2_TYPES.len());
        for (spec, name) in SPECS.iter().zip(MASTER_5_2_TYPES) {
            assert_eq!(spec.type_name, *name);
            assert!(
                !spec.fields.is_empty(),
                "{name} must declare fields for schema-driven widgets"
            );
        }
        let registry = registry_json();
        let names: Vec<&str> = registry["names"]
            .as_array()
            .expect("names")
            .iter()
            .map(|v| v.as_str().expect("name"))
            .collect();
        assert_eq!(names, MASTER_5_2_TYPES);
    }

    #[test]
    fn clamp_respects_scale_and_z_index() {
        let sx = spec_by_type("Transform2D")
            .and_then(|s| s.fields.iter().find(|f| f.name == "sx"))
            .expect("sx");
        assert!((clamp_to_schema(sx, 0.0) - 0.001).abs() < 1e-9);
        assert!((clamp_to_schema(sx, 5000.0) - 1000.0).abs() < 1e-9);
        let z = spec_by_type("Transform2D")
            .and_then(|s| s.fields.iter().find(|f| f.name == "z_index"))
            .expect("z");
        assert_eq!(clamp_to_schema(z, 20_000.0), 10_000.0);
    }
}
