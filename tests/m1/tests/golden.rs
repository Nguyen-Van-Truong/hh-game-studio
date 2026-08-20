//! Six offscreen golden scenes (MASTER 10.3 / 12.1 / T1.5).

use m1::{
    all_golden_scenes, assert_matches_golden, atlas, pick_at, scene_gutter_pick, GOLDEN_H, GOLDEN_W,
};

fn assert_named(name: &str) {
    let snap = all_golden_scenes()
        .into_iter()
        .find(|(n, _)| *n == name)
        .unwrap_or_else(|| panic!("unknown scene {name}"))
        .1;
    let result = assert_matches_golden(name, &snap);
    assert_eq!(result.width, GOLDEN_W);
    assert_eq!(result.height, GOLDEN_H);
}

#[test]
fn golden_01_empty_grid() {
    assert_named("01_empty_grid");
}

#[test]
fn golden_02_hero_block() {
    assert_named("02_hero_block");
}

#[test]
fn golden_03_overlap_zsort() {
    assert_named("03_overlap_zsort");
}

#[test]
fn golden_04_gutter_pick() {
    assert_named("04_gutter_pick");
}

#[test]
fn golden_05_camera_offset() {
    assert_named("05_camera_offset");
}

#[test]
fn golden_06_many_quads() {
    assert_named("06_many_quads");
}

#[test]
fn pick_misses_transparent_hero_gutter_hits_center() {
    let snap = scene_gutter_pick();
    let atlas = atlas();
    // Hero AABB [-1, -1]..[1, 1]; 2px/16px gutter ≈ 0.125 of sprite (0.25 wu).
    assert_eq!(
        pick_at(&snap, &atlas, -1.0 + 0.04, -1.0 + 0.04),
        None,
        "atlas gutter must miss (alpha ≤ 0.1)"
    );
    assert_eq!(
        pick_at(&snap, &atlas, 0.0, 0.0),
        Some(2),
        "hero center must hit"
    );
}
