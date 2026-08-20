//! M1 golden / perf / GS-EC harness (WP-M1-5).
//!
//! Offscreen scenes are tiny and integer-aligned (128×64, ortho 8) so a
//! nearest-filter GPU path stays stable. Compare uses MASTER 10.3 defaults:
//! per-channel Δ ≤ 8/255 and `max_bad_ratio` 0.2%. Missing goldens are written
//! on first run under `tests/fixtures/golden/`.

use std::fs;
use std::path::{Path, PathBuf};

use gs_render2d::{
    demo_atlas, pick, render_offscreen_png, world_to_clip, AtlasCpu, Camera2D, RenderItem,
    RenderSnapshot, TEX_BLOCK, TEX_HERO,
};
use serde_json::{json, Value};

/// Viewport used by all six golden scenes (8 px / world unit).
pub const GOLDEN_W: u32 = 128;
pub const GOLDEN_H: u32 = 64;
pub const GOLDEN_ORTHO: f32 = 8.0;

/// MASTER 10.3 default per-channel threshold (8/255).
pub const PER_PX: u8 = 8;
/// MASTER 10.3 default max fraction of pixels over [`PER_PX`].
pub const MAX_BAD_RATIO: f64 = 0.002;

pub const SPRITE_10K: usize = 10_000;
pub const FRAME_BUDGET_MS: f64 = 16.7;

/// Scene count targeted by GS-EC-05 warn (20k). Cap 50k is not implemented.
pub const GS_EC_05_WARN_COUNT: usize = 20_200;

pub fn crate_name() -> &'static str {
    "m1"
}

pub fn golden_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("fixtures")
        .join("golden")
}

pub fn default_camera() -> Camera2D {
    Camera2D {
        ortho_height: GOLDEN_ORTHO,
        position: [0.0, 0.0],
    }
}

pub fn atlas() -> AtlasCpu {
    demo_atlas()
}

/// One pixel in golden world units (128×64 / ortho 8).
const PX: f32 = GOLDEN_ORTHO / GOLDEN_H as f32;

pub fn scene_empty_grid() -> RenderSnapshot {
    let mut items = Vec::new();
    let mut id = 1u64;
    // Vertical lines at even x in [-6, 6]; 1 px thick.
    for i in -3..=3 {
        let x = (i * 2) as f32;
        items.push(RenderItem::new(
            id,
            0,
            x - PX * 0.5,
            -4.0,
            PX,
            8.0,
            [0.30, 0.34, 0.42, 1.0],
            None,
        ));
        id += 1;
    }
    // Horizontal lines at integer y in [-2, 2].
    for i in -2..=2 {
        let y = i as f32;
        items.push(RenderItem::new(
            id,
            0,
            -8.0,
            y - PX * 0.5,
            16.0,
            PX,
            [0.30, 0.34, 0.42, 1.0],
            None,
        ));
        id += 1;
    }
    RenderSnapshot {
        camera: default_camera(),
        items,
    }
}

pub fn scene_hero_block() -> RenderSnapshot {
    RenderSnapshot {
        camera: default_camera(),
        items: vec![
            RenderItem::new(1, 0, -8.0, -3.0, 16.0, 1.0, [0.18, 0.22, 0.38, 1.0], None),
            RenderItem::new(
                2,
                0,
                -3.0,
                -1.0,
                2.0,
                2.0,
                [1.0, 1.0, 1.0, 1.0],
                Some(TEX_BLOCK),
            ),
            RenderItem::new(
                3,
                1,
                0.0,
                -1.0,
                2.0,
                2.0,
                [1.0, 1.0, 1.0, 1.0],
                Some(TEX_HERO),
            ),
        ],
    }
}

/// Overlap: same-z later `entity_id` covers earlier; higher `z_index` covers both.
pub fn scene_overlap_zsort() -> RenderSnapshot {
    RenderSnapshot {
        camera: default_camera(),
        items: vec![
            RenderItem::new(1, 0, -2.0, -1.0, 3.0, 3.0, [0.85, 0.20, 0.18, 1.0], None),
            RenderItem::new(2, 0, -1.0, -1.0, 3.0, 3.0, [0.20, 0.75, 0.28, 1.0], None),
            RenderItem::new(3, 1, -1.5, 0.0, 3.0, 3.0, [0.20, 0.45, 0.90, 1.0], None),
        ],
    }
}

/// Hero with 2 px atlas gutter; used for PNG + CPU pick.
///
/// Platform sits *below* the hero AABB so a gutter miss is `None`, not a
/// hit on a quad behind the transparent border.
pub fn scene_gutter_pick() -> RenderSnapshot {
    RenderSnapshot {
        camera: default_camera(),
        items: vec![
            RenderItem::new(1, 0, -3.0, -3.0, 6.0, 1.5, [0.55, 0.22, 0.55, 1.0], None),
            RenderItem::new(
                2,
                1,
                -1.0,
                -1.0,
                2.0,
                2.0,
                [1.0, 1.0, 1.0, 1.0],
                Some(TEX_HERO),
            ),
        ],
    }
}

pub fn scene_camera_offset() -> RenderSnapshot {
    let mut snap = scene_hero_block();
    snap.camera.position = [3.0, 1.0];
    snap
}

pub fn scene_many_quads() -> RenderSnapshot {
    let mut items = Vec::with_capacity(32);
    let mut id = 1u64;
    for row in 0..4 {
        for col in 0..8 {
            let x = -4.0 + col as f32;
            let y = -2.0 + row as f32;
            let r = 0.15 + col as f32 / 8.0 * 0.75;
            let g = 0.20 + row as f32 / 4.0 * 0.60;
            items.push(RenderItem::new(
                id,
                0,
                x,
                y,
                0.875,
                0.875,
                [r, g, 0.70, 1.0],
                None,
            ));
            id += 1;
        }
    }
    RenderSnapshot {
        camera: default_camera(),
        items,
    }
}

pub fn all_golden_scenes() -> [(&'static str, RenderSnapshot); 6] {
    [
        ("01_empty_grid", scene_empty_grid()),
        ("02_hero_block", scene_hero_block()),
        ("03_overlap_zsort", scene_overlap_zsort()),
        ("04_gutter_pick", scene_gutter_pick()),
        ("05_camera_offset", scene_camera_offset()),
        ("06_many_quads", scene_many_quads()),
    ]
}

/// 10k solid quads in a 100×100 lattice (IR items, not atlas sprites).
pub fn scene_10k_sprites() -> RenderSnapshot {
    let mut items = Vec::with_capacity(SPRITE_10K);
    for i in 0..SPRITE_10K {
        let col = (i % 100) as f32;
        let row = (i / 100) as f32;
        items.push(RenderItem::new(
            i as u64 + 1,
            0,
            -8.0 + col * 0.16,
            -4.0 + row * 0.08,
            0.14,
            0.07,
            [
                0.20 + col / 100.0 * 0.70,
                0.25 + row / 100.0 * 0.55,
                0.80,
                1.0,
            ],
            None,
        ));
    }
    RenderSnapshot {
        camera: default_camera(),
        items,
    }
}

pub fn world_to_pixel(wx: f32, wy: f32, camera: &Camera2D) -> (f32, f32) {
    let vw = GOLDEN_W as f32;
    let vh = GOLDEN_H as f32;
    let [cx, cy] = world_to_clip(wx, wy, camera, vw, vh);
    let px = (cx + 1.0) * 0.5 * vw - 0.5;
    let py = (1.0 - cy) * 0.5 * vh - 0.5;
    (px, py)
}

pub fn pick_at(snapshot: &RenderSnapshot, atlas: &AtlasCpu, wx: f32, wy: f32) -> Option<u64> {
    let (px, py) = world_to_pixel(wx, wy, &snapshot.camera);
    pick(snapshot, atlas, px, py, GOLDEN_W as f32, GOLDEN_H as f32)
}

pub fn adapter_label() -> String {
    match gs_render2d::create_device_queue() {
        Ok((_, _, label)) => label,
        Err(e) => format!("unavailable: {e}"),
    }
}

pub fn render_scene(snapshot: &RenderSnapshot) -> Vec<u8> {
    render_offscreen_png(GOLDEN_W, GOLDEN_H, snapshot, &atlas()).expect("offscreen png")
}

pub fn decode_rgba(png: &[u8]) -> (u32, u32, Vec<u8>) {
    let img = image::load_from_memory(png).expect("decode png").to_rgba8();
    (img.width(), img.height(), img.into_raw())
}

#[derive(Debug)]
pub struct CompareResult {
    pub width: u32,
    pub height: u32,
    pub bad_pixels: usize,
    pub bad_ratio: f64,
    pub mean_abs: f64,
    pub exact_bytes: bool,
}

impl CompareResult {
    pub fn within_threshold(&self) -> bool {
        self.bad_ratio <= MAX_BAD_RATIO
    }
}

pub fn compare_png(got_png: &[u8], gold_png: &[u8]) -> CompareResult {
    let exact_bytes = got_png == gold_png;
    let (gw, gh, got) = decode_rgba(got_png);
    let (fw, fh, gold) = decode_rgba(gold_png);
    assert_eq!((gw, gh), (fw, fh), "golden size {fw}x{fh} vs got {gw}x{gh}");
    assert_eq!(got.len(), gold.len());
    let px = (gw * gh) as usize;
    let mut bad = 0usize;
    let mut abs_sum = 0u64;
    for i in 0..px {
        let o = i * 4;
        let dr = got[o].abs_diff(gold[o]);
        let dg = got[o + 1].abs_diff(gold[o + 1]);
        let db = got[o + 2].abs_diff(gold[o + 2]);
        let da = got[o + 3].abs_diff(gold[o + 3]);
        abs_sum += u64::from(dr) + u64::from(dg) + u64::from(db) + u64::from(da);
        if dr > PER_PX || dg > PER_PX || db > PER_PX || da > PER_PX {
            bad += 1;
        }
    }
    CompareResult {
        width: gw,
        height: gh,
        bad_pixels: bad,
        bad_ratio: bad as f64 / px as f64,
        mean_abs: abs_sum as f64 / (px as f64 * 4.0),
        exact_bytes,
    }
}

pub fn write_diff_heatmap(path: &Path, got_png: &[u8], gold_png: &[u8]) {
    let (w, h, got) = decode_rgba(got_png);
    let (_, _, gold) = decode_rgba(gold_png);
    let mut heat = vec![0u8; got.len()];
    for i in 0..(w * h) as usize {
        let o = i * 4;
        let dr = got[o].abs_diff(gold[o]);
        let dg = got[o + 1].abs_diff(gold[o + 1]);
        let db = got[o + 2].abs_diff(gold[o + 2]);
        let da = got[o + 3].abs_diff(gold[o + 3]);
        let max = dr.max(dg).max(db).max(da);
        if max > PER_PX {
            heat[o] = 255;
            heat[o + 1] = max;
            heat[o + 2] = 0;
            heat[o + 3] = 255;
        } else {
            heat[o] = gold[o] / 5;
            heat[o + 1] = gold[o + 1] / 5;
            heat[o + 2] = gold[o + 2] / 5;
            heat[o + 3] = 255;
        }
    }
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let img = image::RgbaImage::from_raw(w, h, heat).expect("heatmap");
    img.save(path).expect("write diff png");
}

pub fn sidecar_json(name: &str, snapshot: &RenderSnapshot, png_len: usize, gpu: &str) -> Value {
    json!({
        "name": name,
        "width": GOLDEN_W,
        "height": GOLDEN_H,
        "ortho_height": snapshot.camera.ortho_height,
        "camera": snapshot.camera.position,
        "item_count": snapshot.items.len(),
        "png_bytes": png_len,
        "compare": { "per_px": PER_PX, "max_bad_ratio": MAX_BAD_RATIO },
        "gpu": gpu,
    })
}

/// Render `name`, write the golden PNG (+ JSON sidecar) if missing, then compare.
pub fn assert_matches_golden(name: &str, snapshot: &RenderSnapshot) -> CompareResult {
    let dir = golden_dir();
    fs::create_dir_all(&dir).expect("golden dir");
    let png_path = dir.join(format!("{name}.png"));
    let json_path = dir.join(format!("{name}.json"));
    let got = render_scene(snapshot);
    if !png_path.exists() {
        fs::write(&png_path, &got).expect("write golden png");
        let gpu = adapter_label();
        let side = sidecar_json(name, snapshot, got.len(), &gpu);
        fs::write(
            &json_path,
            serde_json::to_string_pretty(&side).expect("sidecar"),
        )
        .expect("write golden json");
    }
    let gold = fs::read(&png_path).expect("read golden png");
    let result = compare_png(&got, &gold);
    if !result.within_threshold() {
        let diff = std::env::temp_dir().join(format!("m1-diff-{name}.png"));
        write_diff_heatmap(&diff, &got, &gold);
        panic!(
            "{name}: bad_ratio {:.4} ({} px) exceeds {}; mean_abs {:.3}; exact_bytes={}; diff {}",
            result.bad_ratio,
            result.bad_pixels,
            MAX_BAD_RATIO,
            result.mean_abs,
            result.exact_bytes,
            diff.display()
        );
    }
    result
}

#[cfg(test)]
mod crate_smoke {
    #[test]
    fn package_name() {
        assert_eq!(super::crate_name(), "m1");
        assert_eq!(super::all_golden_scenes().len(), 6);
        assert_eq!(super::SPRITE_10K, 10_000);
    }
}
