//! Minimal immutable play-snapshot builder (MASTER 2.4 / 6.1).
//!
//! Writes `.gs/runtime/play/<play_id>/` and hashes with the same rules as
//! [`crate::verify_snapshot`] so the editor and player cannot drift.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use gs_scene::to_canonical_vec;
use serde_json::{Map, Value};

use crate::error::Error;
use crate::hash::sha256_hex;
use crate::manifest::{AssetRecord, Manifest, SnapshotHashes};
use crate::verify::verify_snapshot;

/// In-memory project fragment frozen into a play snapshot.
#[derive(Debug, Clone)]
pub struct SnapshotRequest {
    pub play_id: String,
    pub document_revision: String,
    pub engine_ver: String,
    pub protocol_ver: String,
    pub seed: u64,
    pub created_at: String,
    pub actor: String,
    pub scene: Value,
    pub project_settings: Value,
    pub input_map: Value,
    /// Relative path under `scripts/` (e.g. `door.luau`) → source bytes.
    pub scripts: BTreeMap<String, Vec<u8>>,
    /// asset_id → record. Content is hashed but never copied into the snapshot.
    pub assets: BTreeMap<String, AssetInput>,
}

#[derive(Debug, Clone)]
pub struct AssetInput {
    pub path: String,
    pub content: Option<Vec<u8>>,
}

#[derive(Debug, Clone)]
pub struct BuiltSnapshot {
    pub play_dir: PathBuf,
    pub manifest_path: PathBuf,
    pub manifest: Manifest,
}

/// Writes `<out_root>/.gs/runtime/play/<play_id>/` (MASTER 2.4) and verifies it.
pub fn build_snapshot(out_root: &Path, req: &SnapshotRequest) -> Result<BuiltSnapshot, Error> {
    validate_play_id(&req.play_id)?;
    let play_dir = out_root
        .join(".gs")
        .join("runtime")
        .join("play")
        .join(&req.play_id);
    write_snapshot_dir(&play_dir, req)
}

/// Writes snapshot files directly into `play_dir` (no `.gs/` nesting) and verifies.
pub fn write_snapshot_dir(play_dir: &Path, req: &SnapshotRequest) -> Result<BuiltSnapshot, Error> {
    validate_play_id(&req.play_id)?;
    fs::create_dir_all(play_dir.join("scripts"))
        .map_err(|e| Error::io(play_dir.join("scripts"), e))?;

    let scene_bytes = to_canonical_vec(&req.scene);
    let settings_bytes = to_canonical_vec(&req.project_settings);
    let input_map_bytes = to_canonical_vec(&req.input_map);

    write_atomic(&play_dir.join("scene.json"), &scene_bytes)?;
    write_atomic(&play_dir.join("project-settings.json"), &settings_bytes)?;
    write_atomic(&play_dir.join("input-map.json"), &input_map_bytes)?;

    let mut script_hashes = Map::new();
    for (rel, source) in &req.scripts {
        let rel = rel.replace('\\', "/");
        let dest = play_dir.join("scripts").join(&rel);
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
        }
        write_atomic(&dest, source)?;
        let key = format!("scripts/{rel}");
        script_hashes.insert(key, Value::String(sha256_hex(source)));
    }
    let scripts_hash = sha256_hex(&to_canonical_vec(&Value::Object(script_hashes)));

    let mut asset_manifest = Map::new();
    for (asset_id, asset) in &req.assets {
        if is_cert_rel(&asset.path) {
            return Err(Error::validation(format!(
                "refusing to pack certificate path {}",
                asset.path
            )));
        }
        let hash = match &asset.content {
            Some(bytes) => sha256_hex(bytes),
            None => sha256_hex(asset.path.as_bytes()),
        };
        let record = serde_json::to_value(AssetRecord {
            path: asset.path.clone(),
            hash,
        })
        .map_err(|e| Error::json(play_dir.join("asset-manifest.json"), e))?;
        asset_manifest.insert(asset_id.clone(), record);
        if let Some(bytes) = &asset.content {
            if !asset.path.is_empty() {
                let dest = play_dir.join(&asset.path);
                if dest_escapes(play_dir, &dest) {
                    return Err(Error::path(format!(
                        "asset path {} escapes the pack directory",
                        asset.path
                    )));
                }
                write_atomic(&dest, bytes)?;
            }
        }
    }
    let asset_manifest_bytes = to_canonical_vec(&Value::Object(asset_manifest));
    write_atomic(&play_dir.join("asset-manifest.json"), &asset_manifest_bytes)?;

    let manifest = Manifest {
        play_id: req.play_id.clone(),
        document_revision: req.document_revision.clone(),
        engine_ver: req.engine_ver.clone(),
        protocol_ver: req.protocol_ver.clone(),
        seed: req.seed,
        hashes: SnapshotHashes {
            scene: sha256_hex(&scene_bytes),
            scripts: scripts_hash,
            assets: sha256_hex(&asset_manifest_bytes),
            inputmap: sha256_hex(&input_map_bytes),
        },
        created_at: req.created_at.clone(),
        actor: req.actor.clone(),
    };

    let manifest_value = serde_json::to_value(&manifest)
        .map_err(|e| Error::json(play_dir.join("manifest.json"), e))?;
    let manifest_bytes = to_canonical_vec(&manifest_value);
    let manifest_path = play_dir.join("manifest.json");
    write_atomic(&manifest_path, &manifest_bytes)?;

    verify_snapshot(&manifest_path)?;

    Ok(BuiltSnapshot {
        play_dir: play_dir.to_path_buf(),
        manifest_path,
        manifest,
    })
}

fn validate_play_id(play_id: &str) -> Result<(), Error> {
    if play_id.is_empty()
        || play_id.contains('/')
        || play_id.contains('\\')
        || play_id.contains("..")
    {
        return Err(Error::reject(format!(
            "invalid play_id {play_id:?}: must be a single path segment"
        )));
    }
    Ok(())
}

pub(crate) fn is_cert_rel(path: &str) -> bool {
    let lower = path.replace('\\', "/").to_ascii_lowercase();
    matches!(
        lower.rsplit('.').next(),
        Some("pfx" | "p12" | "cer" | "crt" | "pem" | "p7b" | "p7c")
    )
}

fn dest_escapes(root: &Path, dest: &Path) -> bool {
    dest.components()
        .any(|c| matches!(c, std::path::Component::ParentDir))
        || match dest.strip_prefix(root) {
            Ok(rel) => rel
                .components()
                .any(|c| matches!(c, std::path::Component::ParentDir)),
            Err(_) => true,
        }
}

pub(crate) fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), Error> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| Error::io(parent, e))?;
    }
    let mut tmp = path.as_os_str().to_os_string();
    tmp.push(".tmp");
    let tmp = PathBuf::from(tmp);
    fs::write(&tmp, bytes).map_err(|e| Error::io(&tmp, e))?;
    if path.exists() {
        fs::remove_file(path).map_err(|e| Error::io(path, e))?;
    }
    fs::rename(&tmp, path).map_err(|e| Error::io(path, e))?;
    Ok(())
}
