use std::collections::BTreeMap;
use std::fs;
use std::io::ErrorKind;
use std::path::{Path, PathBuf};

use gs_scene::to_canonical_vec;
use serde_json::{Map, Value};

use crate::error::Error;
use crate::hash::sha256_hex;
use crate::manifest::{AssetRecord, Manifest, VerifiedSnapshot};

/// Verify every hash in `manifest.json` against sibling snapshot files.
/// Copies `.luau` are hashed only — never compiled or executed (I3).
pub fn verify_snapshot(manifest_path: &Path) -> Result<VerifiedSnapshot, Error> {
    let manifest_bytes = read_required(manifest_path)?;
    let manifest_value = parse_json(manifest_path, &manifest_bytes)?;
    let manifest: Manifest =
        serde_json::from_value(manifest_value).map_err(|e| Error::json(manifest_path, e))?;

    let play_dir = manifest_path
        .parent()
        .ok_or_else(|| Error::reject("manifest path has no parent directory"))?;

    let scene_path = play_dir.join("scene.json");
    let input_map_path = play_dir.join("input-map.json");
    let asset_manifest_path = play_dir.join("asset-manifest.json");
    let settings_path = play_dir.join("project-settings.json");
    let scripts_dir = play_dir.join("scripts");

    // MASTER 2.4 lists project-settings.json; it is not one of the four hashes.
    let _settings = read_required(&settings_path)?;

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

fn read_required(path: &Path) -> Result<Vec<u8>, Error> {
    match fs::read(path) {
        Ok(bytes) => Ok(bytes),
        Err(err) if err.kind() == ErrorKind::NotFound => {
            Err(Error::reject(format!("missing file {}", path.display())))
        }
        Err(err) => Err(Error::io(path, err)),
    }
}

fn parse_json(path: &Path, bytes: &[u8]) -> Result<Value, Error> {
    serde_json::from_slice(bytes).map_err(|e| Error::json(path, e))
}

fn hash_json_file(path: &Path) -> Result<String, Error> {
    let bytes = read_required(path)?;
    let value = parse_json(path, &bytes)?;
    let canonical = to_canonical_vec(&value);
    if canonical != bytes {
        return Err(Error::reject(format!(
            "{} is not canonical JSON (on-disk bytes differ from canonical form)",
            path.display()
        )));
    }
    Ok(sha256_hex(&bytes))
}

fn hash_scripts_dir(play_dir: &Path, scripts_dir: &Path) -> Result<String, Error> {
    let mut files: BTreeMap<String, PathBuf> = BTreeMap::new();
    if scripts_dir.exists() {
        if !scripts_dir.is_dir() {
            return Err(Error::reject(format!(
                "{} must be a directory",
                scripts_dir.display()
            )));
        }
        collect_luau(scripts_dir, play_dir, &mut files)?;
    }
    let mut listing = Map::new();
    for (rel, path) in files {
        let bytes = fs::read(&path).map_err(|e| Error::io(&path, e))?;
        listing.insert(rel, Value::String(sha256_hex(&bytes)));
    }
    Ok(sha256_hex(&to_canonical_vec(&Value::Object(listing))))
}

fn collect_luau(
    dir: &Path,
    play_dir: &Path,
    out: &mut BTreeMap<String, PathBuf>,
) -> Result<(), Error> {
    let entries = fs::read_dir(dir).map_err(|e| Error::io(dir, e))?;
    for entry in entries {
        let entry = entry.map_err(|e| Error::io(dir, e))?;
        let path = entry.path();
        if path.is_dir() {
            collect_luau(&path, play_dir, out)?;
            continue;
        }
        if path.extension().and_then(|e| e.to_str()) != Some("luau") {
            continue;
        }
        let rel = path
            .strip_prefix(play_dir)
            .map_err(|_| Error::reject(format!("script {} escapes play dir", path.display())))?;
        let rel = rel.to_string_lossy().replace('\\', "/");
        out.insert(rel, path);
    }
    Ok(())
}

fn verify_asset_records(asset_manifest_path: &Path) -> Result<(), Error> {
    let bytes = read_required(asset_manifest_path)?;
    let value = parse_json(asset_manifest_path, &bytes)?;
    let Value::Object(map) = value else {
        return Err(Error::reject("asset-manifest.json must be a JSON object"));
    };
    for (asset_id, record_value) in map {
        let record: AssetRecord = serde_json::from_value(record_value)
            .map_err(|e| Error::json(asset_manifest_path, e))?;
        let referenced = PathBuf::from(&record.path);
        if referenced.is_file() {
            let content = fs::read(&referenced).map_err(|e| Error::io(&referenced, e))?;
            let actual = sha256_hex(&content);
            if actual != record.hash {
                return Err(Error::reject(format!(
                    "asset {asset_id} hash mismatch: expected={} actual={actual}",
                    record.hash
                )));
            }
        }
    }
    Ok(())
}

fn check_hash(name: &str, expected: &str, actual: &str) -> Result<(), Error> {
    if expected != actual {
        return Err(Error::reject(format!(
            "{name} hash mismatch: expected={expected} actual={actual}"
        )));
    }
    Ok(())
}
