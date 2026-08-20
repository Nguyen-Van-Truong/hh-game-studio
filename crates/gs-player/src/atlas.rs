//! Play-process texture atlas from the snapshot's own PNG files (I3, I7).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use gs_render2d::{
    decode_png_rgba, pack_atlas_sources, AtlasCpu, SpriteSource, TextureId, TEX_SOLID,
};
use gs_runtime_core::World;
use gs_scene::resolve_under_root;

use crate::error::Error;
use crate::manifest::AssetRecord;

/// Build the play atlas from the snapshot's own PNG files.
/// Returns the atlas plus the `asset_id -> TextureId.0` map for `World`.
pub fn load_play_atlas(play_dir: &Path) -> Result<(AtlasCpu, BTreeMap<String, u32>), Error> {
    let manifest_path = play_dir.join("asset-manifest.json");
    let bytes = fs::read(&manifest_path).map_err(|e| Error::io(&manifest_path, e))?;
    let records: BTreeMap<String, AssetRecord> =
        serde_json::from_slice(&bytes).map_err(|e| Error::json(&manifest_path, e))?;

    let mut sources = vec![solid_white_source()];
    let mut texture_ids = BTreeMap::new();
    let mut next_id = 1u32;

    // BTreeMap walks keys in ascending order — TextureId(1..) is deterministic.
    for (asset_id, record) in records {
        let png_path = jail_asset_path(play_dir, &record.path)?;
        if !is_png_path(&png_path) {
            continue;
        }
        if !png_path.is_file() {
            eprintln!(
                "WARNING play atlas: missing PNG for {asset_id} ({})",
                record.path
            );
            continue;
        }
        refuse_if_canonical_escapes(play_dir, &png_path, &record.path)?;
        let png_bytes = match fs::read(&png_path) {
            Ok(bytes) => bytes,
            Err(err) => {
                eprintln!(
                    "WARNING play atlas: skip {asset_id} ({}): {err}",
                    record.path
                );
                continue;
            }
        };
        match decode_png_rgba(&png_bytes) {
            Ok((w, h, pixels)) => {
                sources.push(SpriteSource {
                    id: TextureId(next_id),
                    w,
                    h,
                    pixels,
                });
                texture_ids.insert(asset_id, next_id);
                next_id = next_id.saturating_add(1);
            }
            Err(err) => {
                eprintln!(
                    "WARNING play atlas: undecodable PNG for {asset_id} ({}): {err}",
                    record.path
                );
            }
        }
    }

    Ok((pack_atlas_sources(&sources), texture_ids))
}

/// Load the snapshot atlas and bind `asset_id → TextureId` onto `world`.
pub(crate) fn bind_play_atlas(world: &mut World, play_dir: &Path) -> Result<AtlasCpu, Error> {
    let (atlas, texture_ids) = load_play_atlas(play_dir)?;
    world.texture_ids = texture_ids;
    Ok(atlas)
}

pub(crate) fn solid_white_atlas() -> AtlasCpu {
    pack_atlas_sources(&[solid_white_source()])
}

fn solid_white_source() -> SpriteSource {
    SpriteSource {
        id: TEX_SOLID,
        w: 1,
        h: 1,
        pixels: vec![255, 255, 255, 255],
    }
}

/// I7: refuse absolute paths and any `..` segment. Never read outside `play_dir`.
fn jail_asset_path(play_dir: &Path, rel: &str) -> Result<PathBuf, Error> {
    if rel.contains('\0') {
        return Err(escape_err(rel));
    }
    let normalized = rel.replace('\\', "/");
    if Path::new(&normalized).is_absolute() || normalized.split('/').any(|part| part == "..") {
        return Err(escape_err(rel));
    }
    resolve_under_root(play_dir, &normalized).map_err(|_| escape_err(rel))
}

fn refuse_if_canonical_escapes(play_dir: &Path, path: &Path, rel: &str) -> Result<(), Error> {
    let Ok(root) = play_dir.canonicalize() else {
        return Ok(());
    };
    let Ok(canon) = path.canonicalize() else {
        return Ok(());
    };
    if canon == root || canon.starts_with(&root) {
        Ok(())
    } else {
        Err(escape_err(rel))
    }
}

fn escape_err(rel: &str) -> Error {
    Error::path(format!("asset path {rel} escapes the play directory"))
}

fn is_png_path(path: &Path) -> bool {
    path.extension()
        .and_then(|ext| ext.to_str())
        .is_some_and(|ext| ext.eq_ignore_ascii_case("png"))
}
