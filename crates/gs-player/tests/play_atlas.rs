//! Play atlas from snapshot PNGs: order, I7 jail, missing files, TEX_SOLID.

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

use gs_player::{load_play_atlas, run_headless_frames, sha256_hex};
use gs_render2d::{TextureId, TEX_SOLID};
use gs_scene::{to_canonical_vec, AssetRef, Camera2D, Entity, Name, Scene, Sprite, Transform2D};
use serde_json::{json, Value};
use tempfile::TempDir;

/// 2×2 RGBA PNG (R, G, B, Y).
const RED_PNG: &[u8] = &[
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x02, 0x08, 0x06, 0x00, 0x00, 0x00, 0x72, 0xb6, 0x0d,
    0x24, 0x00, 0x00, 0x00, 0x14, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda, 0x63, 0xf8, 0xcf, 0xc0, 0xf0,
    0x1f, 0x0c, 0x81, 0x34, 0x10, 0x30, 0xfc, 0x07, 0x00, 0x47, 0xca, 0x08, 0xf8, 0x5b, 0x9a, 0xa4,
    0xbe, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
];

/// 1×1 opaque blue PNG.
const BLUE_PNG: &[u8] = &[
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4,
    0x89, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x44, 0x41, 0x54, 0x78, 0xda, 0x63, 0x60, 0x60, 0xf8, 0xff,
    0x1f, 0x00, 0x03, 0x02, 0x01, 0xff, 0x39, 0x29, 0x19, 0xbe, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,
    0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
];

fn write_manifest(play_dir: &Path, entries: &[(&str, &str)]) {
    let mut map = serde_json::Map::new();
    for (id, rel) in entries {
        map.insert((*id).to_string(), json!({ "hash": "00", "path": rel }));
    }
    fs::write(
        play_dir.join("asset-manifest.json"),
        serde_json::to_vec(&Value::Object(map)).expect("manifest json"),
    )
    .expect("write manifest");
}

fn sample_region_rgba(atlas: &gs_render2d::AtlasCpu, id: TextureId) -> (u32, u32, [u8; 4]) {
    let region = atlas.region(id).expect("region");
    let idx = ((region.y * atlas.width + region.x) * 4) as usize;
    let px = [
        atlas.pixels[idx],
        atlas.pixels[idx + 1],
        atlas.pixels[idx + 2],
        atlas.pixels[idx + 3],
    ];
    (region.w, region.h, px)
}

#[test]
fn maps_asset_ids_in_ascending_order_deterministically() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(play_dir.join("assets")).expect("assets dir");
    fs::write(play_dir.join("assets").join("red.png"), RED_PNG).expect("red");
    fs::write(play_dir.join("assets").join("blue.png"), BLUE_PNG).expect("blue");
    // Deliberately list the higher id first so BTree order, not JSON order, wins.
    write_manifest(
        &play_dir,
        &[
            ("a_000020", "assets/blue.png"),
            ("a_000001", "assets/red.png"),
        ],
    );

    let (atlas, map) = load_play_atlas(&play_dir).expect("load");
    let expected: BTreeMap<String, u32> =
        BTreeMap::from([("a_000001".into(), 1), ("a_000020".into(), 2)]);
    assert_eq!(map, expected);

    let (w0, h0, white) = sample_region_rgba(&atlas, TEX_SOLID);
    assert_eq!((w0, h0, white), (1, 1, [255, 255, 255, 255]));
    let (w1, h1, _) = sample_region_rgba(&atlas, TextureId(1));
    assert_eq!((w1, h1), (2, 2));
    let (w2, h2, _) = sample_region_rgba(&atlas, TextureId(2));
    assert_eq!((w2, h2), (1, 1));

    let (atlas2, map2) = load_play_atlas(&play_dir).expect("reload");
    assert_eq!(map2, map);
    assert_eq!(atlas2.width, atlas.width);
    assert_eq!(atlas2.height, atlas.height);
    assert_eq!(atlas2.pixels, atlas.pixels);
}

#[test]
fn missing_png_is_skipped_without_error() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(play_dir.join("assets")).expect("assets dir");
    fs::write(play_dir.join("assets").join("red.png"), RED_PNG).expect("red");
    write_manifest(
        &play_dir,
        &[
            ("a_000001", "assets/red.png"),
            ("a_000002", "assets/missing.png"),
        ],
    );

    let (atlas, map) = load_play_atlas(&play_dir).expect("missing PNG must not reject");
    assert_eq!(map.get("a_000001"), Some(&1));
    assert!(!map.contains_key("a_000002"));
    assert!(atlas.region(TEX_SOLID).is_some());
    assert!(atlas.region(TextureId(1)).is_some());
    assert!(atlas.region(TextureId(2)).is_none());
}

#[test]
fn undecodable_png_is_skipped_without_error() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(play_dir.join("assets")).expect("assets dir");
    fs::write(play_dir.join("assets").join("bad.png"), b"not a png").expect("bad");
    write_manifest(&play_dir, &[("a_000001", "assets/bad.png")]);

    let (atlas, map) = load_play_atlas(&play_dir).expect("corrupt PNG must not reject");
    assert!(map.is_empty());
    let (w, h, white) = sample_region_rgba(&atlas, TEX_SOLID);
    assert_eq!((w, h, white), (1, 1, [255, 255, 255, 255]));
}

#[test]
fn texture_id_zero_is_always_one_by_one_white() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(&play_dir).expect("play dir");
    write_manifest(&play_dir, &[]);

    let (atlas, map) = load_play_atlas(&play_dir).expect("empty manifest");
    assert!(map.is_empty());
    let (w, h, white) = sample_region_rgba(&atlas, TEX_SOLID);
    assert_eq!(TEX_SOLID, TextureId(0));
    assert_eq!((w, h, white), (1, 1, [255, 255, 255, 255]));
}

#[test]
fn parent_dir_segment_is_refused() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(play_dir.join("assets")).expect("assets dir");
    let outside = tmp.path().join("outside.png");
    fs::write(&outside, BLUE_PNG).expect("outside png");
    write_manifest(&play_dir, &[("a_000001", "../outside.png")]);

    let err = load_play_atlas(&play_dir).expect_err(".. must be refused");
    assert_eq!(err.app_code(), "E_PATH");
    let msg = err.to_string();
    assert!(
        msg.contains("escapes") || msg.contains(".."),
        "unexpected error: {msg}"
    );
}

#[test]
fn absolute_manifest_path_is_refused() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play");
    fs::create_dir_all(&play_dir).expect("play dir");
    let outside = tmp.path().join("outside.png");
    fs::write(&outside, BLUE_PNG).expect("outside png");
    let abs = outside.to_string_lossy().replace('\\', "/");
    write_manifest(&play_dir, &[("a_000001", &abs)]);

    let err = load_play_atlas(&play_dir).expect_err("absolute path must be refused");
    assert_eq!(err.app_code(), "E_PATH");
}

fn write_canonical(path: &Path, value: &Value) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).expect("parent");
    }
    fs::write(path, to_canonical_vec(value)).expect("write canonical");
}

/// Headless path must bind `world.texture_ids` so the render IR matches the window.
#[test]
fn headless_run_emits_textured_render_item() {
    let tmp = TempDir::new().expect("tempdir");
    let play_dir = tmp.path().join("play").join("p-000001");
    fs::create_dir_all(play_dir.join("assets")).expect("assets");
    fs::create_dir_all(play_dir.join("scripts")).expect("scripts");
    fs::write(play_dir.join("assets").join("red.png"), RED_PNG).expect("red");

    let mut scene = Scene::default();
    let mut cam = Entity::new(1, None, 0);
    cam.name = Some(Name {
        value: "cam".into(),
    });
    cam.transform = Some(Transform2D {
        x: 0.0,
        y: 0.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    cam.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    let mut sprite = Entity::new(2, None, 1);
    sprite.name = Some(Name {
        value: "Hero".into(),
    });
    sprite.transform = Some(Transform2D {
        x: 1.0,
        y: 2.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    sprite.extra.sprite = Some(Sprite {
        asset: AssetRef {
            id: "a_000001".into(),
        },
        color: [1.0, 1.0, 1.0, 1.0],
        flip_x: false,
        flip_y: false,
        pivot: [0.0, 0.0],
    });
    scene.entities.insert(1, cam);
    scene.entities.insert(2, sprite);

    let scene_bytes = to_canonical_vec(&scene.to_canonical_value());
    fs::write(play_dir.join("scene.json"), &scene_bytes).expect("scene");
    write_canonical(
        &play_dir.join("project-settings.json"),
        &json!({ "fixed_dt": 1.0 / 60.0, "ppu": 16, "schema_version": 1 }),
    );
    write_canonical(&play_dir.join("input-map.json"), &json!({ "actions": [] }));
    write_canonical(
        &play_dir.join("asset-manifest.json"),
        &json!({
            "a_000001": { "hash": "00", "path": "assets/red.png" }
        }),
    );
    let script = b"-- fixture\n";
    fs::write(play_dir.join("scripts").join("noop.luau"), script).expect("script");
    let mut listing = serde_json::Map::new();
    listing.insert(
        "scripts/noop.luau".into(),
        Value::String(sha256_hex(script)),
    );
    let scripts_hash = sha256_hex(&to_canonical_vec(&Value::Object(listing)));
    let input_bytes = fs::read(play_dir.join("input-map.json")).expect("input");
    let assets_bytes = fs::read(play_dir.join("asset-manifest.json")).expect("assets");
    write_canonical(
        &play_dir.join("manifest.json"),
        &json!({
            "actor": "act_test",
            "created_at": "2026-08-16T00:00:00Z",
            "document_revision": "r-000001",
            "engine_ver": "0.1.0-m2-1",
            "hashes": {
                "assets": sha256_hex(&assets_bytes),
                "inputmap": sha256_hex(&input_bytes),
                "scene": sha256_hex(&scene_bytes),
                "scripts": scripts_hash,
            },
            "play_id": "p-000001",
            "protocol_ver": "1.0",
            "seed": 42,
        }),
    );

    let report = run_headless_frames(&play_dir.join("manifest.json"), 1).expect("headless");
    let item = report
        .snapshot
        .items
        .iter()
        .find(|i| i.entity_id == 2)
        .expect("sprite item");
    assert_eq!(item.texture, Some(TextureId(1)));
}
