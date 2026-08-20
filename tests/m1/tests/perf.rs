//! 10k-sprite offscreen measure (MASTER 12.3 / I13 / T1.5).
//!
//! Records real milliseconds. Does **not** claim the 16.7 ms player-frame
//! target is met. `render_offscreen_png` creates a device and encodes PNG
//! on every call.

use std::time::Instant;

use gs_render2d::render_offscreen_png;
use m1::{adapter_label, atlas, scene_10k_sprites, FRAME_BUDGET_MS, SPRITE_10K};

const BENCH_W: u32 = 640;
const BENCH_H: u32 = 360;
const SAMPLES: usize = 3;

#[test]
fn measure_10k_sprites_offscreen() {
    let snap = scene_10k_sprites();
    assert_eq!(snap.items.len(), SPRITE_10K);
    let atlas = atlas();
    let gpu = adapter_label();

    let t0 = Instant::now();
    let warmup = render_offscreen_png(BENCH_W, BENCH_H, &snap, &atlas).expect("warmup");
    let warmup_ms = t0.elapsed().as_secs_f64() * 1000.0;
    assert!(
        warmup.len() > 64 && warmup.starts_with(&[137, 80, 78, 71, 13, 10, 26, 10]),
        "warmup png invalid ({} bytes)",
        warmup.len()
    );

    let mut samples = Vec::with_capacity(SAMPLES);
    for _ in 0..SAMPLES {
        let t = Instant::now();
        let png = render_offscreen_png(BENCH_W, BENCH_H, &snap, &atlas).expect("sample");
        samples.push(t.elapsed().as_secs_f64() * 1000.0);
        assert_eq!(&png[0..8], &[137, 80, 78, 71, 13, 10, 26, 10]);
    }
    let mut sorted = samples.clone();
    sorted.sort_by(|a, b| a.partial_cmp(b).expect("finite ms"));
    let median = sorted[SAMPLES / 2];
    let met = median <= FRAME_BUDGET_MS;
    let verdict = if met { "target met" } else { "target not met" };

    println!(
        "m1 10k sprites: gpu={gpu}; viewport={BENCH_W}x{BENCH_H}; warmup_ms={warmup_ms:.2}; samples_ms={samples:?}; median_ms={median:.2}; budget_ms={FRAME_BUDGET_MS}; {verdict}"
    );
    assert!(
        median.is_finite() && median > 0.0,
        "elapsed must be a real positive measurement"
    );
}
