use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::{json, Map, Value};

use crate::canonical::canonical_bytes;
use crate::error::SpikeError;
use crate::hash::sha256_hex;
use crate::manifest::{AssetRecord, Manifest, SnapshotHashes};

/// In-memory project fragment the builder freezes into a play snapshot.
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
    /// Relative path under `scripts/` (e.g. `door.luau`) -> source text.
    pub scripts: BTreeMap<String, String>,
    /// asset_id -> record. `content` is hashed but never copied into the snapshot.
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

/// Writes `<out_root>/play/<play_id>/` with MASTER 2.4 layout.
pub fn build_snapshot(out_root: &Path, req: &SnapshotRequest) -> Result<BuiltSnapshot, SpikeError> {
    validate_play_id(&req.play_id)?;

    let play_dir = out_root.join("play").join(&req.play_id);
    fs::create_dir_all(play_dir.join("scripts")).map_err(|e| SpikeError::io(&play_dir, e))?;

    let scene_bytes = canonical_bytes(&req.scene);
    let settings_bytes = canonical_bytes(&req.project_settings);
    let input_map_bytes = canonical_bytes(&req.input_map);

    write_atomic(&play_dir.join("scene.json"), &scene_bytes)?;
    write_atomic(&play_dir.join("project-settings.json"), &settings_bytes)?;
    write_atomic(&play_dir.join("input-map.json"), &input_map_bytes)?;

    let mut script_hashes = Map::new();
    for (rel, source) in &req.scripts {
        let rel = rel.replace('\\', "/");
        let dest = play_dir.join("scripts").join(&rel);
        if let Some(parent) = dest.parent() {
            fs::create_dir_all(parent).map_err(|e| SpikeError::io(parent, e))?;
        }
        let bytes = source.as_bytes();
        write_atomic(&dest, bytes)?;
        let key = format!("scripts/{rel}");
        script_hashes.insert(key, Value::String(sha256_hex(bytes)));
    }
    let scripts_hash = sha256_hex(&canonical_bytes(&Value::Object(script_hashes)));

    let mut asset_manifest = Map::new();
    for (asset_id, asset) in &req.assets {
        let hash = match &asset.content {
            Some(bytes) => sha256_hex(bytes),
            None => sha256_hex(asset.path.as_bytes()),
        };
        let record = serde_json::to_value(AssetRecord {
            path: asset.path.clone(),
            hash,
        })
        .expect("AssetRecord is always serializable");
        asset_manifest.insert(asset_id.clone(), record);
    }
    let asset_manifest_bytes = canonical_bytes(&Value::Object(asset_manifest));
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

    let manifest_value = serde_json::to_value(&manifest).expect("Manifest is always serializable");
    let manifest_bytes = canonical_bytes(&manifest_value);
    let manifest_path = play_dir.join("manifest.json");
    write_atomic(&manifest_path, &manifest_bytes)?;

    Ok(BuiltSnapshot {
        play_dir,
        manifest_path,
        manifest,
    })
}

/// Minimal 2D fixture used by tests (door/camera from MASTER 5.4, trimmed).
pub fn demo_request() -> SnapshotRequest {
    let mut scripts = BTreeMap::new();
    scripts.insert(
        "door.luau".to_string(),
        "-- spike fixture\nlocal locked = true\n".to_string(),
    );

    let mut assets = BTreeMap::new();
    assets.insert(
        "a_000007".to_string(),
        AssetInput {
            path: "assets/door.png".to_string(),
            content: Some(b"not-a-real-png".to_vec()),
        },
    );

    SnapshotRequest {
        play_id: "p-000001".to_string(),
        document_revision: "r-000001".to_string(),
        engine_ver: "0.0.0-m-1-d".to_string(),
        protocol_ver: "1.0".to_string(),
        seed: 42,
        created_at: "2026-08-16T00:00:00Z".to_string(),
        actor: "act_spike".to_string(),
        scene: json!({
            "schema_version": 1,
            "mode": "2d",
            "entities": [
                {
                    "id": "e_000001",
                    "parent": null,
                    "order": 0,
                    "components": {
                        "Name": { "value": "MainCamera" },
                        "Camera2D": { "ortho_height": 10.0, "active": true },
                        "Transform2D": {
                            "x": 0, "y": 0, "rot": 0, "sx": 1, "sy": 1, "z_index": 0
                        }
                    }
                }
            ]
        }),
        project_settings: json!({
            "schema_version": 1,
            "ppu": 16,
            "fixed_dt": 1.0 / 60.0
        }),
        input_map: json!({
            "actions": [
                {
                    "name": "interact",
                    "type": "button",
                    "keys": ["E"],
                    "gamepad_button": "south"
                }
            ]
        }),
        scripts,
        assets,
    }
}

fn validate_play_id(play_id: &str) -> Result<(), SpikeError> {
    if play_id.is_empty()
        || play_id.contains('/')
        || play_id.contains('\\')
        || play_id.contains("..")
    {
        return Err(SpikeError::Usage(format!(
            "invalid play_id {play_id:?}: must be a single path segment"
        )));
    }
    Ok(())
}

fn write_atomic(path: &Path, bytes: &[u8]) -> Result<(), SpikeError> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| SpikeError::io(parent, e))?;
    }
    let mut tmp = path.as_os_str().to_os_string();
    tmp.push(".tmp");
    let tmp = PathBuf::from(tmp);
    fs::write(&tmp, bytes).map_err(|e| SpikeError::io(&tmp, e))?;
    if path.exists() {
        fs::remove_file(path).map_err(|e| SpikeError::io(path, e))?;
    }
    fs::rename(&tmp, path).map_err(|e| SpikeError::io(path, e))?;
    Ok(())
}
