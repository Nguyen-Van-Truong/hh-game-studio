use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{Map, Value};

use crate::canonical::{canonical_bytes, parse_json_bytes};
use crate::error::SpikeError;
use crate::hash::sha256_hex;
use crate::manifest::{AssetRecord, Manifest, VerifiedSnapshot};

/// Verify every hash in `manifest.json` against sibling snapshot files.
/// Does not load or execute Luau (I3).
pub fn verify_snapshot(manifest_path: &Path) -> Result<VerifiedSnapshot, SpikeError> {
    let manifest_bytes = fs::read(manifest_path).map_err(|e| SpikeError::io(manifest_path, e))?;
    let manifest_value =
        parse_json_bytes(&manifest_bytes).map_err(|e| SpikeError::json(manifest_path, e))?;
    let manifest: Manifest =
        serde_json::from_value(manifest_value).map_err(|e| SpikeError::json(manifest_path, e))?;

    let play_dir = manifest_path
        .parent()
        .ok_or_else(|| SpikeError::reject("manifest path has no parent directory"))?;

    let scene_path = play_dir.join("scene.json");
    let input_map_path = play_dir.join("input-map.json");
    let asset_manifest_path = play_dir.join("asset-manifest.json");
    let scripts_dir = play_dir.join("scripts");

    let scene_hash = hash_json_file(&scene_path)?;
    let inputmap_hash = hash_json_file(&input_map_path)?;
    let assets_hash = hash_json_file(&asset_manifest_path)?;
    let scripts_hash = hash_scripts_dir(play_dir, &scripts_dir)?;

    check_hash("scene", &manifest.hashes.scene, &scene_hash)?;
    check_hash("scripts", &manifest.hashes.scripts, &scripts_hash)?;
    check_hash("assets", &manifest.hashes.assets, &assets_hash)?;
    check_hash("inputmap", &manifest.hashes.inputmap, &inputmap_hash)?;

    verify_asset_records(&asset_manifest_path)?;

    Ok(VerifiedSnapshot {
        play_id: manifest.play_id.clone(),
        document_revision: manifest.document_revision.clone(),
        manifest,
    })
}

fn hash_json_file(path: &Path) -> Result<String, SpikeError> {
    let bytes = fs::read(path).map_err(|e| SpikeError::io(path, e))?;
    let value = parse_json_bytes(&bytes).map_err(|e| SpikeError::json(path, e))?;
    let canonical = canonical_bytes(&value);
    if canonical != bytes {
        return Err(SpikeError::reject(format!(
            "{} is not canonical JSON (on-disk bytes differ from canonical form)",
            path.display()
        )));
    }
    Ok(sha256_hex(&bytes))
}

fn hash_scripts_dir(play_dir: &Path, scripts_dir: &Path) -> Result<String, SpikeError> {
    let mut files: BTreeMap<String, PathBuf> = BTreeMap::new();
    if scripts_dir.exists() {
        collect_luau(scripts_dir, play_dir, &mut files)?;
    }
    let mut listing = Map::new();
    for (rel, path) in files {
        let bytes = fs::read(&path).map_err(|e| SpikeError::io(&path, e))?;
        listing.insert(rel, Value::String(sha256_hex(&bytes)));
    }
    Ok(sha256_hex(&canonical_bytes(&Value::Object(listing))))
}

fn collect_luau(
    dir: &Path,
    play_dir: &Path,
    out: &mut BTreeMap<String, PathBuf>,
) -> Result<(), SpikeError> {
    let entries = fs::read_dir(dir).map_err(|e| SpikeError::io(dir, e))?;
    for entry in entries {
        let entry = entry.map_err(|e| SpikeError::io(dir, e))?;
        let path = entry.path();
        if path.is_dir() {
            collect_luau(&path, play_dir, out)?;
            continue;
        }
        if path.extension().and_then(|e| e.to_str()) != Some("luau") {
            continue;
        }
        let rel = path.strip_prefix(play_dir).map_err(|_| {
            SpikeError::reject(format!("script {} escapes play dir", path.display()))
        })?;
        let rel = rel.to_string_lossy().replace('\\', "/");
        out.insert(rel, path);
    }
    Ok(())
}

fn verify_asset_records(asset_manifest_path: &Path) -> Result<(), SpikeError> {
    let bytes =
        fs::read(asset_manifest_path).map_err(|e| SpikeError::io(asset_manifest_path, e))?;
    let value = parse_json_bytes(&bytes).map_err(|e| SpikeError::json(asset_manifest_path, e))?;
    let Value::Object(map) = value else {
        return Err(SpikeError::reject(
            "asset-manifest.json must be a JSON object",
        ));
    };
    for (asset_id, record_value) in map {
        let record: AssetRecord = serde_json::from_value(record_value)
            .map_err(|e| SpikeError::json(asset_manifest_path, e))?;
        let referenced = PathBuf::from(&record.path);
        if referenced.is_file() {
            let content = fs::read(&referenced).map_err(|e| SpikeError::io(&referenced, e))?;
            let actual = sha256_hex(&content);
            if actual != record.hash {
                return Err(SpikeError::reject(format!(
                    "asset {asset_id} hash mismatch: expected={} actual={actual}",
                    record.hash
                )));
            }
        }
    }
    Ok(())
}

fn check_hash(name: &str, expected: &str, actual: &str) -> Result<(), SpikeError> {
    if expected != actual {
        return Err(SpikeError::reject(format!(
            "{name} hash mismatch: expected={expected} actual={actual}"
        )));
    }
    Ok(())
}
