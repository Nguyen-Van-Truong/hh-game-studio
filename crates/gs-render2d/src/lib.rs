//! One `RenderSnapshot` IR consumed by offscreen PNG, eframe viewport, and
//! winit/player surface. Independent of `gs-scene` / `gs-editor` (MASTER 2.3).

mod error;
mod gpu;
mod viewport;

pub use egui_wgpu;
pub use wgpu;

pub use error::Error;
pub use gpu::{
    clear_color, create_device_queue, render_offscreen_png, render_snapshot_to_surface,
    render_snapshot_to_view, SpriteGpu,
};
pub use viewport::{install_sprite_gpu, ViewportCallback};

/// Locked default pixels-per-world-unit (MASTER 2.3). A 16px sprite is 1 world unit.
pub const PPU_DEFAULT: f32 = 16.0;
/// Atlas gutter in texels (MASTER 2.3).
pub const ATLAS_PADDING_PX: u32 = 2;
/// Pick hit if sampled texel/color alpha is strictly greater than this.
pub const PICK_ALPHA_THRESHOLD: f32 = 0.1;

/// Opaque handle into the CPU/GPU atlas packed by this crate.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct TextureId(pub u32);

pub const TEX_SOLID: TextureId = TextureId(0);
pub const TEX_HERO: TextureId = TextureId(1);
pub const TEX_BLOCK: TextureId = TextureId(2);

/// Orthographic 2D camera. World Y-up. `position` is the world-space center.
#[derive(Clone, Debug, PartialEq)]
pub struct Camera2D {
    pub ortho_height: f32,
    pub position: [f32; 2],
}

impl Default for Camera2D {
    fn default() -> Self {
        Self {
            ortho_height: 10.0,
            position: [0.0, 0.0],
        }
    }
}

/// One sprite (or solid quad) in the IR.
///
/// `(x, y)` is the world position of the pivot. Pivot is in `[0, 1]^2` with
/// origin at the **bottom-left** of the sprite (MASTER 2.3). Default pivot is
/// `[0, 0]` so `(x, y)` is the bottom-left corner.
#[derive(Clone, Debug, PartialEq)]
pub struct RenderItem {
    pub entity_id: u64,
    pub z_index: i32,
    pub x: f32,
    pub y: f32,
    pub w: f32,
    pub h: f32,
    /// Straight-alpha RGBA in 0..1. Uploaded premultiplied to the GPU.
    pub color: [f32; 4],
    pub texture: Option<TextureId>,
    pub pivot: [f32; 2],
    pub flip_x: bool,
    pub flip_y: bool,
}

impl RenderItem {
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        entity_id: u64,
        z_index: i32,
        x: f32,
        y: f32,
        w: f32,
        h: f32,
        color: [f32; 4],
        texture: Option<TextureId>,
    ) -> Self {
        Self {
            entity_id,
            z_index,
            x,
            y,
            w,
            h,
            color,
            texture,
            pivot: [0.0, 0.0],
            flip_x: false,
            flip_y: false,
        }
    }
}

impl Default for RenderItem {
    fn default() -> Self {
        Self::new(0, 0, 0.0, 0.0, 1.0, 1.0, [1.0; 4], None)
    }
}

/// RGBA8, straight alpha, rows top-down.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SpriteSource {
    pub id: TextureId,
    pub w: u32,
    pub h: u32,
    pub pixels: Vec<u8>,
}

/// Decode a PNG into RGBA8 straight-alpha rows (top-down).
pub fn decode_png_rgba(bytes: &[u8]) -> Result<(u32, u32, Vec<u8>), Error> {
    let img = image::load_from_memory_with_format(bytes, image::ImageFormat::Png)
        .map_err(|e| Error::Png(e.to_string()))?;
    let rgba = img.to_rgba8();
    Ok((rgba.width(), rgba.height(), rgba.into_raw()))
}

/// Intermediate representation consumed by all three targets.
#[derive(Clone, Debug, PartialEq)]
pub struct RenderSnapshot {
    pub camera: Camera2D,
    pub items: Vec<RenderItem>,
}

/// Packed atlas on the CPU (sRGB bytes, straight alpha). GPU upload premultiplies.
#[derive(Clone, Debug)]
pub struct AtlasCpu {
    pub width: u32,
    pub height: u32,
    pub pixels: Vec<u8>,
    pub regions: Vec<AtlasRegion>,
}

#[derive(Clone, Copy, Debug)]
pub struct AtlasRegion {
    pub id: TextureId,
    pub x: u32,
    pub y: u32,
    pub w: u32,
    pub h: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, bytemuck::Pod, bytemuck::Zeroable)]
pub struct Vertex {
    pub position: [f32; 2],
    pub uv: [f32; 2],
    pub color: [f32; 4],
}

/// Sort key: `z_index` then `entity_id` (stable). Lower draws first (behind).
pub fn sort_items(items: &mut [RenderItem]) {
    items.sort_by(|a, b| {
        a.z_index
            .cmp(&b.z_index)
            .then(a.entity_id.cmp(&b.entity_id))
    });
}

/// World-space AABB of an item: `(left, bottom, right, top)` in Y-up.
pub fn item_world_rect(item: &RenderItem) -> [f32; 4] {
    let left = item.x - item.pivot[0] * item.w;
    let bottom = item.y - item.pivot[1] * item.h;
    [left, bottom, left + item.w, bottom + item.h]
}

/// Physical-pixel → world (Y-up). Pixel `(0,0)` is the top-left of the viewport.
pub fn pixel_to_world(
    px: f32,
    py: f32,
    viewport_w: f32,
    viewport_h: f32,
    camera: &Camera2D,
) -> [f32; 2] {
    let ndc_x = (px + 0.5) / viewport_w * 2.0 - 1.0;
    let ndc_y = 1.0 - (py + 0.5) / viewport_h * 2.0;
    let half_h = camera.ortho_height * 0.5;
    let half_w = half_h * (viewport_w / viewport_h);
    [
        camera.position[0] + ndc_x * half_w,
        camera.position[1] + ndc_y * half_h,
    ]
}

pub fn world_to_clip(
    x: f32,
    y: f32,
    camera: &Camera2D,
    viewport_w: f32,
    viewport_h: f32,
) -> [f32; 2] {
    let half_h = camera.ortho_height * 0.5;
    let half_w = half_h * (viewport_w / viewport_h);
    [
        (x - camera.position[0]) / half_w,
        (y - camera.position[1]) / half_h,
    ]
}

/// CPU pick: alpha > 0.1 on a small atlas/color sample (not GPU framebuffer
/// readback). Walks items front-to-back (reverse of draw sort).
pub fn pick(
    snapshot: &RenderSnapshot,
    atlas: &AtlasCpu,
    px: f32,
    py: f32,
    viewport_w: f32,
    viewport_h: f32,
) -> Option<u64> {
    let [wx, wy] = pixel_to_world(px, py, viewport_w, viewport_h, &snapshot.camera);
    let mut items = snapshot.items.clone();
    sort_items(&mut items);
    for item in items.iter().rev() {
        let [left, bottom, right, top] = item_world_rect(item);
        if wx < left || wx > right || wy < bottom || wy > top {
            continue;
        }
        let u = ((wx - left) / item.w).clamp(0.0, 1.0);
        let v = ((wy - bottom) / item.h).clamp(0.0, 1.0);
        let alpha = sample_item_alpha(atlas, item, u, v);
        if alpha > PICK_ALPHA_THRESHOLD {
            return Some(item.entity_id);
        }
    }
    None
}

fn sample_item_alpha(atlas: &AtlasCpu, item: &RenderItem, u: f32, v: f32) -> f32 {
    let tex_a = match item.texture {
        None => 1.0,
        Some(id) => match atlas.region(id) {
            None => 1.0,
            Some(r) => {
                let u = if item.flip_x { 1.0 - u } else { u };
                let v = if item.flip_y { 1.0 - v } else { v };
                let tx = (r.x as f32 + u * r.w as f32).floor() as u32;
                // v=0 is sprite bottom; atlas pixels are top-down.
                let ty = (r.y as f32 + (1.0 - v) * r.h as f32).floor() as u32;
                let tx = tx.min(r.x + r.w.saturating_sub(1));
                let ty = ty.min(r.y + r.h.saturating_sub(1));
                let idx = ((ty * atlas.width + tx) * 4 + 3) as usize;
                atlas.pixels.get(idx).copied().unwrap_or(255) as f32 / 255.0
            }
        },
    };
    tex_a * item.color[3]
}

impl AtlasCpu {
    pub fn region(&self, id: TextureId) -> Option<AtlasRegion> {
        self.regions.iter().copied().find(|r| r.id == id)
    }

    pub fn uv_rect(&self, id: TextureId) -> [f32; 4] {
        match self.region(id) {
            Some(r) => {
                let w = self.width as f32;
                let h = self.height as f32;
                [
                    r.x as f32 / w,
                    r.y as f32 / h,
                    (r.x + r.w) as f32 / w,
                    (r.y + r.h) as f32 / h,
                ]
            }
            None => [0.0, 0.0, 1.0, 1.0],
        }
    }
}

/// Build clip-space vertices for a snapshot. Draw order = sorted IR.
pub fn build_vertices(
    snapshot: &RenderSnapshot,
    atlas: &AtlasCpu,
    viewport_w: f32,
    viewport_h: f32,
) -> Vec<Vertex> {
    let mut items = snapshot.items.clone();
    sort_items(&mut items);
    let mut out = Vec::with_capacity(items.len() * 6);
    for item in &items {
        let [left, bottom, right, top] = item_world_rect(item);
        let bl = world_to_clip(left, bottom, &snapshot.camera, viewport_w, viewport_h);
        let br = world_to_clip(right, bottom, &snapshot.camera, viewport_w, viewport_h);
        let tl = world_to_clip(left, top, &snapshot.camera, viewport_w, viewport_h);
        let tr = world_to_clip(right, top, &snapshot.camera, viewport_w, viewport_h);
        let tex = item.texture.unwrap_or(TEX_SOLID);
        let [mut u0, mut v0, mut u1, mut v1] = atlas.uv_rect(tex);
        if item.flip_x {
            std::mem::swap(&mut u0, &mut u1);
        }
        if item.flip_y {
            std::mem::swap(&mut v0, &mut v1);
        }
        // Atlas v=0 is top of the image; sprite bottom uses v1.
        let a = item.color[3];
        let color = [item.color[0] * a, item.color[1] * a, item.color[2] * a, a];
        let quad = [
            Vertex {
                position: bl,
                uv: [u0, v1],
                color,
            },
            Vertex {
                position: br,
                uv: [u1, v1],
                color,
            },
            Vertex {
                position: tl,
                uv: [u0, v0],
                color,
            },
            Vertex {
                position: tl,
                uv: [u0, v0],
                color,
            },
            Vertex {
                position: br,
                uv: [u1, v1],
                color,
            },
            Vertex {
                position: tr,
                uv: [u1, v0],
                color,
            },
        ];
        out.extend_from_slice(&quad);
    }
    out
}

/// Shared demo scene used by tests and the offscreen bin (same IR).
pub fn demo_snapshot() -> RenderSnapshot {
    RenderSnapshot {
        camera: Camera2D {
            ortho_height: 10.0,
            position: [0.0, 0.0],
        },
        items: vec![
            RenderItem::new(1, 0, -8.0, -4.5, 16.0, 1.5, [0.18, 0.22, 0.38, 1.0], None),
            RenderItem::new(
                2,
                0,
                -3.5,
                -1.0,
                2.0,
                2.0,
                [1.0, 1.0, 1.0, 1.0],
                Some(TEX_BLOCK),
            ),
            RenderItem::new(
                3,
                1,
                -1.0,
                -1.0,
                2.0,
                2.0,
                [1.0, 1.0, 1.0, 1.0],
                Some(TEX_HERO),
            ),
            RenderItem::new(4, 1, 1.8, -0.5, 1.5, 1.5, [0.35, 0.75, 1.0, 0.55], None),
            RenderItem::new(5, 2, 3.4, 0.4, 1.2, 1.2, [1.0, 0.85, 0.2, 1.0], None),
            RenderItem::new(10, 0, 4.5, -1.0, 1.0, 1.0, [0.9, 0.3, 0.35, 1.0], None),
        ],
    }
}

pub fn demo_atlas() -> AtlasCpu {
    let solid = vec![255_u8, 255, 255, 255];
    let hero = make_hero_rgba();
    let block = make_block_rgba();
    pack_atlas(&[
        (TEX_SOLID, 1, 1, solid),
        (TEX_HERO, 16, 16, hero),
        (TEX_BLOCK, 16, 16, block),
    ])
}

/// Pack sprites in one row with [`ATLAS_PADDING_PX`] gutters.
pub fn pack_atlas(sprites: &[(TextureId, u32, u32, Vec<u8>)]) -> AtlasCpu {
    let pad = ATLAS_PADDING_PX;
    let mut x = pad;
    let mut row_h = 0u32;
    let mut placed = Vec::new();
    for (id, w, h, pixels) in sprites {
        placed.push((*id, x, pad, *w, *h, pixels.clone()));
        x += *w + pad;
        row_h = row_h.max(*h);
    }
    let width = x.max(1);
    let height = (row_h + pad * 2).max(1);
    let mut pixels = vec![0u8; (width * height * 4) as usize];
    let mut regions = Vec::new();
    for (id, px, py, w, h, src) in placed {
        blit_rgba(&mut pixels, width, &src, w, h, px, py);
        regions.push(AtlasRegion {
            id,
            x: px,
            y: py,
            w,
            h,
        });
    }
    AtlasCpu {
        width,
        height,
        pixels,
        regions,
    }
}

/// Maximum atlas edge used by [`pack_atlas_sources`].
const ATLAS_MAX_DIM: u32 = 2048;

/// Shelf-pack many sprites into rows. Gutters are [`ATLAS_PADDING_PX`].
/// Must handle 40+ sprites without exceeding 2048 px in either dimension.
pub fn pack_atlas_sources(sources: &[SpriteSource]) -> AtlasCpu {
    let pad = ATLAS_PADDING_PX;
    let mut x = pad;
    let mut y = pad;
    let mut row_h = 0u32;
    let mut max_w = pad;
    let mut placed: Vec<(TextureId, u32, u32, u32, u32, Vec<u8>)> = Vec::new();
    for src in sources {
        if x > pad && x.saturating_add(src.w).saturating_add(pad) > ATLAS_MAX_DIM {
            x = pad;
            y = y.saturating_add(row_h).saturating_add(pad);
            row_h = 0;
        }
        placed.push((src.id, x, y, src.w, src.h, src.pixels.clone()));
        x = x.saturating_add(src.w).saturating_add(pad);
        row_h = row_h.max(src.h);
        max_w = max_w.max(x);
    }
    let width = max_w.max(1);
    let height = y.saturating_add(row_h).saturating_add(pad).max(1);
    let mut pixels = vec![0u8; (width * height * 4) as usize];
    let mut regions = Vec::new();
    for (id, px, py, w, h, src) in placed {
        blit_rgba(&mut pixels, width, &src, w, h, px, py);
        regions.push(AtlasRegion {
            id,
            x: px,
            y: py,
            w,
            h,
        });
    }
    AtlasCpu {
        width,
        height,
        pixels,
        regions,
    }
}

fn blit_rgba(dst: &mut [u8], dst_w: u32, src: &[u8], w: u32, h: u32, x: u32, y: u32) {
    for row in 0..h {
        let src_off = (row * w * 4) as usize;
        let dst_off = (((y + row) * dst_w + x) * 4) as usize;
        let len = (w * 4) as usize;
        dst[dst_off..dst_off + len].copy_from_slice(&src[src_off..src_off + len]);
    }
}

fn make_hero_rgba() -> Vec<u8> {
    let mut p = vec![0u8; 16 * 16 * 4];
    for y in 0..16 {
        for x in 0..16 {
            let i = (y * 16 + x) * 4;
            // 2px transparent gutter so pick-alpha can miss the AABB edge.
            if !(2..=13).contains(&x) || !(2..=13).contains(&y) {
                continue;
            }
            let ink = (y == 6 || y == 7) && (x == 5 || x == 6 || x == 9 || x == 10)
                || (y == 11 && (5..=10).contains(&x));
            let (r, g, b, a) = if ink {
                (20, 24, 32, 255)
            } else if y == 3 || x == 2 || x == 13 {
                (28, 140, 120, 255)
            } else {
                (48, 196, 168, 255)
            };
            p[i] = r;
            p[i + 1] = g;
            p[i + 2] = b;
            p[i + 3] = a;
        }
    }
    p
}

fn make_block_rgba() -> Vec<u8> {
    let mut p = vec![0u8; 16 * 16 * 4];
    for y in 0..16 {
        for x in 0..16 {
            let i = (y * 16 + x) * 4;
            let mortar = x == 0 || y == 0 || x == 15 || y == 15 || y == 7 || x == 8;
            if mortar {
                p[i] = 92;
                p[i + 1] = 64;
                p[i + 2] = 48;
            } else {
                p[i] = 196;
                p[i + 1] = 118;
                p[i + 2] = 64;
            }
            p[i + 3] = 255;
        }
    }
    p
}

pub fn premultiply_srgb_rgba(pixels: &mut [u8]) {
    for px in pixels.chunks_exact_mut(4) {
        let a = px[3] as f32 / 255.0;
        px[0] = (px[0] as f32 * a + 0.5) as u8;
        px[1] = (px[1] as f32 * a + 0.5) as u8;
        px[2] = (px[2] as f32 * a + 0.5) as u8;
    }
}

pub fn out_dir() -> std::path::PathBuf {
    std::path::PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("out")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sort_is_z_then_entity_id() {
        let mut items = vec![
            RenderItem::new(9, 1, 0.0, 0.0, 1.0, 1.0, [1.0; 4], None),
            RenderItem::new(3, 0, 0.0, 0.0, 1.0, 1.0, [1.0; 4], None),
            RenderItem::new(1, 1, 0.0, 0.0, 1.0, 1.0, [1.0; 4], None),
            RenderItem::new(2, 0, 0.0, 0.0, 1.0, 1.0, [1.0; 4], None),
        ];
        sort_items(&mut items);
        let ids: Vec<u64> = items.iter().map(|i| i.entity_id).collect();
        assert_eq!(ids, vec![2, 3, 1, 9]);
    }

    #[test]
    fn default_camera_centers_world_origin() {
        let cam = Camera2D::default();
        assert_eq!(cam.position, [0.0, 0.0]);
        let clip = world_to_clip(0.0, 0.0, &cam, 640.0, 360.0);
        assert!((clip[0]).abs() < 1e-5);
        assert!((clip[1]).abs() < 1e-5);
    }

    #[test]
    fn pivot_origin_is_bottom_left() {
        let item = RenderItem::new(1, 0, 2.0, 3.0, 4.0, 5.0, [1.0; 4], None);
        assert_eq!(item.pivot, [0.0, 0.0]);
        assert_eq!(item_world_rect(&item), [2.0, 3.0, 6.0, 8.0]);
    }

    #[test]
    fn pick_hits_frontmost_opaque() {
        let snap = demo_snapshot();
        let atlas = demo_atlas();
        // Entity 5 is a solid yellow quad [3.4, 0.4] .. [4.6, 1.6], z=2 (front).
        let [cx, cy] = [3.4 + 0.6, 0.4 + 0.6];
        let (px, py) = world_to_pixel_for_test(cx, cy, 640.0, 360.0, &snap.camera);
        assert_eq!(pick(&snap, &atlas, px, py, 640.0, 360.0), Some(5));
    }

    #[test]
    fn pick_misses_transparent_hero_border() {
        let snap = demo_snapshot();
        let atlas = demo_atlas();
        // Hero entity 3 occupies [-1, -1] .. [1, 1]. A 2px gutter / 16px ≈ 0.125
        // of the sprite; sample near the bottom-left corner of the AABB.
        let [cx, cy] = [-1.0 + 0.04, -1.0 + 0.04];
        let (px, py) = world_to_pixel_for_test(cx, cy, 640.0, 360.0, &snap.camera);
        assert_eq!(pick(&snap, &atlas, px, py, 640.0, 360.0), None);
    }

    #[test]
    fn pick_hits_hero_center() {
        let snap = demo_snapshot();
        let atlas = demo_atlas();
        let (px, py) = world_to_pixel_for_test(0.0, 0.0, 640.0, 360.0, &snap.camera);
        assert_eq!(pick(&snap, &atlas, px, py, 640.0, 360.0), Some(3));
    }

    #[test]
    fn locked_constants() {
        assert_eq!(PPU_DEFAULT, 16.0);
        assert_eq!(ATLAS_PADDING_PX, 2);
        assert!((PICK_ALPHA_THRESHOLD - 0.1).abs() < f32::EPSILON);
    }

    #[test]
    fn offscreen_writes_real_png() {
        let dir = out_dir();
        std::fs::create_dir_all(&dir).expect("out dir");
        let path = dir.join("offscreen_test.png");
        let bytes = render_offscreen_png(320, 180, &demo_snapshot(), &demo_atlas())
            .expect("offscreen render");
        std::fs::write(&path, &bytes).expect("write png");
        assert!(bytes.len() > 64, "png too small: {} bytes", bytes.len());
        assert_eq!(&bytes[0..8], &[137, 80, 78, 71, 13, 10, 26, 10]);
    }

    #[test]
    fn viewport_callback_implements_callback_trait() {
        fn assert_callback<T: egui_wgpu::CallbackTrait>(_: &T) {}
        let cb = ViewportCallback::new(demo_snapshot(), 64.0, 36.0);
        assert_callback(&cb);
        let _ = cb.into_paint_callback(egui::Rect::from_min_size(
            egui::Pos2::ZERO,
            egui::vec2(64.0, 36.0),
        ));
    }

    #[test]
    fn surface_helper_typechecks() {
        fn assert_fn<F>(_: F) {}
        assert_fn(render_snapshot_to_view);
        assert_fn(render_snapshot_to_surface);
        assert_fn(install_sprite_gpu);
    }

    fn world_to_pixel_for_test(
        wx: f32,
        wy: f32,
        vw: f32,
        vh: f32,
        camera: &Camera2D,
    ) -> (f32, f32) {
        let [cx, cy] = world_to_clip(wx, wy, camera, vw, vh);
        let px = (cx + 1.0) * 0.5 * vw - 0.5;
        let py = (1.0 - cy) * 0.5 * vh - 0.5;
        (px, py)
    }

    fn item_uvs(item: RenderItem) -> Vec<[f32; 2]> {
        let snap = RenderSnapshot {
            camera: Camera2D::default(),
            items: vec![item],
        };
        build_vertices(&snap, &demo_atlas(), 64.0, 64.0)
            .into_iter()
            .map(|v| v.uv)
            .collect()
    }

    #[test]
    fn render_item_new_defaults_flips_false() {
        let item = RenderItem::new(1, 0, 0.0, 0.0, 1.0, 1.0, [1.0; 4], Some(TEX_HERO));
        assert!(!item.flip_x);
        assert!(!item.flip_y);
    }

    #[test]
    fn flip_mirrors_uvs_versus_unflipped() {
        let base = RenderItem::new(1, 0, 0.0, 0.0, 1.0, 1.0, [1.0; 4], Some(TEX_HERO));
        let unflipped = item_uvs(base.clone());

        let mut flip_x = base.clone();
        flip_x.flip_x = true;
        let flipped_x = item_uvs(flip_x);
        // bl/br swap u; v unchanged
        assert_eq!(unflipped[0][0], flipped_x[1][0]);
        assert_eq!(unflipped[1][0], flipped_x[0][0]);
        assert_eq!(unflipped[0][1], flipped_x[0][1]);
        assert_eq!(unflipped[1][1], flipped_x[1][1]);
        assert_ne!(unflipped, flipped_x);

        let mut flip_y = base.clone();
        flip_y.flip_y = true;
        let flipped_y = item_uvs(flip_y);
        // bl.v <-> tl.v
        assert_eq!(unflipped[0][1], flipped_y[2][1]);
        assert_eq!(unflipped[2][1], flipped_y[0][1]);
        assert_eq!(unflipped[0][0], flipped_y[0][0]);
        assert_ne!(unflipped, flipped_y);
    }

    fn encode_rgba_png(w: u32, h: u32, pixels: &[u8]) -> Vec<u8> {
        use image::ImageEncoder;
        let mut png = Vec::new();
        image::codecs::png::PngEncoder::new(&mut png)
            .write_image(pixels, w, h, image::ExtendedColorType::Rgba8)
            .expect("encode png");
        png
    }

    #[test]
    fn decode_png_rgba_round_trips_straight_alpha() {
        let pixels = vec![
            10, 20, 30, 255, 40, 50, 60, 128, 70, 80, 90, 0, 100, 110, 120, 255,
        ];
        let png = encode_rgba_png(2, 2, &pixels);
        let (w, h, out) = decode_png_rgba(&png).expect("decode");
        assert_eq!((w, h), (2, 2));
        assert_eq!(out, pixels);
    }

    #[test]
    fn pack_atlas_sources_shelves_forty_sprites_under_2048() {
        let mut sources = Vec::new();
        for i in 0..40u32 {
            let w = 32 + (i % 5) * 16;
            let h = 16 + (i % 7) * 8;
            sources.push(SpriteSource {
                id: TextureId(i),
                w,
                h,
                pixels: vec![u8::try_from(i % 256).unwrap(); (w * h * 4) as usize],
            });
        }
        let atlas = pack_atlas_sources(&sources);
        assert!(atlas.width <= 2048, "width {} exceeds 2048", atlas.width);
        assert!(atlas.height <= 2048, "height {} exceeds 2048", atlas.height);
        assert_eq!(
            atlas.pixels.len(),
            (atlas.width * atlas.height * 4) as usize
        );
        assert_eq!(atlas.regions.len(), 40);
        for (i, src) in sources.iter().enumerate() {
            let r = atlas.region(src.id).expect("region");
            assert_eq!((r.w, r.h), (src.w, src.h));
            assert!(
                r.x.saturating_add(r.w) <= atlas.width,
                "region {i} x overflow: {r:?} atlas {}x{}",
                atlas.width,
                atlas.height
            );
            assert!(
                r.y.saturating_add(r.h) <= atlas.height,
                "region {i} y overflow: {r:?} atlas {}x{}",
                atlas.width,
                atlas.height
            );
        }
        for (i, a) in atlas.regions.iter().enumerate() {
            for b in atlas.regions.iter().skip(i + 1) {
                let overlap_x = a.x < b.x + b.w && b.x < a.x + a.w;
                let overlap_y = a.y < b.y + b.h && b.y < a.y + a.h;
                assert!(!(overlap_x && overlap_y), "regions overlap: {a:?} vs {b:?}");
            }
        }
    }
}
