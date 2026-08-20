//! Editor-layer `asset.import` / `asset.list` (MASTER 8.1 / I7).
//!
//! `src_abs` may live outside the project root. `dest_rel` is jailed under the
//! project (canonicalize + prefix; `..` rejected). PNG only in this slice.

use std::fs::{self, File};
use std::io::{Read, Write};
use std::path::{Component, Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use gs_protocol::RpcError;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use crate::error::{app_err, invalid_params};

const PNG_MAGIC: &[u8] = &[0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A];
const MAX_PNG_BYTES: u64 = 20 * 1024 * 1024;
const MAX_DIM: u32 = 8192;
const MAX_REL_CHARS: usize = 200;
const IMPORTER_VERSION: u32 = 1;
const INDEX_REL: &str = "assets/index.json";

const RESERVED: &[&str] = &[
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
    "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AssetRecord {
    pub asset_id: String,
    pub dest_rel: String,
    pub kind: String,
    pub source_sha256: String,
    pub width: u32,
    pub height: u32,
    pub importer_version: u32,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct AssetCatalog {
    pub next_asset: u64,
    pub assets: Vec<AssetRecord>,
}

impl Default for AssetCatalog {
    fn default() -> Self {
        Self {
            next_asset: 1,
            assets: Vec::new(),
        }
    }
}

impl AssetCatalog {
    pub fn load(root: Option<&Path>) -> Self {
        let Some(root) = root else {
            return Self::default();
        };
        let path = root.join(INDEX_REL);
        let Ok(bytes) = fs::read(&path) else {
            return Self::default();
        };
        match serde_json::from_slice::<Value>(&bytes) {
            Ok(value) => parse_index(&value),
            Err(_) => Self::default(),
        }
    }

    pub fn get(&self, asset_id: &str) -> Option<&AssetRecord> {
        self.assets.iter().find(|a| a.asset_id == asset_id)
    }

    pub fn list(&self, kind: Option<&str>, folder: Option<&str>) -> Vec<&AssetRecord> {
        self.assets
            .iter()
            .filter(|a| kind.is_none_or(|k| a.kind == k))
            .filter(|a| folder.is_none_or(|f| a.dest_rel.replace('\\', "/").starts_with(f)))
            .collect()
    }

    pub fn import_png(
        &mut self,
        root: &Path,
        src_abs: &str,
        dest_rel: &str,
        min_next: u64,
    ) -> Result<AssetRecord, RpcError> {
        let src = validate_src_abs(src_abs)?;
        let dest_rel = normalize_rel(dest_rel);
        let dest_abs = jail_dest(root, &dest_rel)?;
        let bytes = read_png_bytes(&src)?;
        let (width, height) = png_header_size(&bytes)?;
        let sha = hex_sha256(&bytes);

        if self.next_asset < min_next {
            self.next_asset = min_next;
        }
        let existing = self.assets.iter().position(|a| a.dest_rel == dest_rel);
        let asset_id = if let Some(i) = existing {
            self.assets[i].asset_id.clone()
        } else {
            let id = format_asset_id(self.next_asset);
            self.next_asset = self.next_asset.saturating_add(1);
            id
        };

        if let Some(parent) = dest_abs.parent() {
            fs::create_dir_all(parent).map_err(|err| app_err("E_IO", err.to_string()))?;
        }
        write_tmp_rename(&dest_abs, &bytes)?;

        let meta_path = sidecar_path(&dest_abs);
        let imported_at = unix_secs();
        let meta = json!({
            "asset_id": asset_id,
            "kind": "png",
            "importer_version": IMPORTER_VERSION,
            "source_sha256": sha,
            "ppu": 16,
            "pivot": [0.5, 0.0],
            "filter": "nearest",
            "color_space": "srgb",
            "premultiplied": true,
            "imported_at": imported_at,
            "width": width,
            "height": height,
        });
        let meta_bytes =
            serde_json::to_vec_pretty(&meta).map_err(|err| invalid_params(err.to_string()))?;
        write_tmp_rename(&meta_path, &meta_bytes)?;

        let record = AssetRecord {
            asset_id,
            dest_rel,
            kind: "png".into(),
            source_sha256: sha,
            width,
            height,
            importer_version: IMPORTER_VERSION,
        };
        if let Some(i) = existing {
            self.assets[i] = record.clone();
        } else {
            self.assets.push(record.clone());
        }
        self.save(root)?;
        Ok(record)
    }

    fn save(&self, root: &Path) -> Result<(), RpcError> {
        let path = root.join(INDEX_REL);
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|err| app_err("E_IO", err.to_string()))?;
        }
        let value = json!({
            "schema_version": 1,
            "next_asset": self.next_asset,
            "assets": self.assets,
        });
        let bytes =
            serde_json::to_vec_pretty(&value).map_err(|err| invalid_params(err.to_string()))?;
        write_tmp_rename(&path, &bytes)
    }
}

pub fn format_asset_id(n: u64) -> String {
    format!("a_{n:06}")
}

fn parse_index(value: &Value) -> AssetCatalog {
    let next_asset = value
        .get("next_asset")
        .and_then(Value::as_u64)
        .unwrap_or(1)
        .max(1);
    let assets = value
        .get("assets")
        .and_then(Value::as_array)
        .map(|arr| {
            arr.iter()
                .filter_map(|v| serde_json::from_value::<AssetRecord>(v.clone()).ok())
                .collect()
        })
        .unwrap_or_default();
    AssetCatalog { next_asset, assets }
}

fn normalize_rel(rel: &str) -> String {
    rel.replace('\\', "/")
}

fn validate_src_abs(src_abs: &str) -> Result<PathBuf, RpcError> {
    if src_abs.is_empty() {
        return Err(invalid_params("missing src_abs"));
    }
    let lower = src_abs.to_ascii_lowercase();
    if lower.starts_with(r"\\.\") || lower.starts_with("//./") {
        return Err(invalid_params("src_abs must be a regular file"));
    }
    let path = PathBuf::from(src_abs);
    if let Some(name) = path.file_name() {
        reject_reserved(&name.to_string_lossy())?;
    }
    let meta = fs::metadata(&path).map_err(|_| invalid_params("src_abs is not a readable file"))?;
    if !meta.is_file() {
        return Err(invalid_params("src_abs must be a regular file"));
    }
    if meta.len() > MAX_PNG_BYTES {
        return Err(invalid_params("png larger than 20MB"));
    }
    Ok(path)
}

fn jail_dest(root: &Path, dest_rel: &str) -> Result<PathBuf, RpcError> {
    if dest_rel.is_empty() {
        return Err(invalid_params("missing dest_rel"));
    }
    if dest_rel.len() > MAX_REL_CHARS {
        return Err(invalid_params("dest_rel longer than 200 characters"));
    }
    if !dest_rel.to_ascii_lowercase().ends_with(".png") {
        return Err(invalid_params("dest_rel must end with .png"));
    }
    let rel = Path::new(dest_rel);
    if rel.is_absolute() {
        return Err(app_err(
            "E_PATH",
            format!("path {dest_rel} is not under the project root"),
        ));
    }
    for c in rel.components() {
        match c {
            Component::Normal(name) => {
                let name = name.to_string_lossy();
                reject_reserved(&name)?;
                reject_filename_chars(&name)?;
            }
            _ => {
                return Err(app_err(
                    "E_PATH",
                    format!("path {dest_rel} is not under the project root"),
                ));
            }
        }
    }
    let root_canon = root
        .canonicalize()
        .map_err(|err| app_err("E_IO", err.to_string()))?;
    let joined = root.join(rel);
    if let Some(parent) = joined.parent() {
        fs::create_dir_all(parent).map_err(|err| app_err("E_IO", err.to_string()))?;
        let parent_canon = parent
            .canonicalize()
            .map_err(|err| app_err("E_IO", err.to_string()))?;
        if !parent_canon.starts_with(&root_canon) {
            return Err(app_err(
                "E_PATH",
                format!("path {dest_rel} is not under the project root"),
            ));
        }
        let dest = parent_canon.join(joined.file_name().unwrap_or_default());
        if dest.exists() {
            let dest_canon = dest
                .canonicalize()
                .map_err(|err| app_err("E_IO", err.to_string()))?;
            if !dest_canon.starts_with(&root_canon) {
                return Err(app_err(
                    "E_PATH",
                    format!("path {dest_rel} is not under the project root"),
                ));
            }
            return Ok(dest_canon);
        }
        Ok(dest)
    } else {
        Err(app_err(
            "E_PATH",
            format!("path {dest_rel} is not under the project root"),
        ))
    }
}

fn reject_reserved(name: &str) -> Result<(), RpcError> {
    let stem = name.split('.').next().unwrap_or(name);
    if RESERVED.iter().any(|r| stem.eq_ignore_ascii_case(r)) {
        return Err(invalid_params(format!("Windows reserved name {name}")));
    }
    Ok(())
}

fn reject_filename_chars(name: &str) -> Result<(), RpcError> {
    let stem = name.rsplit_once('.').map(|(s, _)| s).unwrap_or(name);
    if stem.is_empty()
        || !stem
            .bytes()
            .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'_' || b == b'-')
    {
        return Err(invalid_params(
            "dest_rel file names must match [a-z0-9_-] (MASTER 8.1)",
        ));
    }
    Ok(())
}

fn read_png_bytes(path: &Path) -> Result<Vec<u8>, RpcError> {
    let mut file = File::open(path).map_err(|err| app_err("E_IO", err.to_string()))?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes)
        .map_err(|err| app_err("E_IO", err.to_string()))?;
    if bytes.len() as u64 > MAX_PNG_BYTES {
        return Err(invalid_params("png larger than 20MB"));
    }
    Ok(bytes)
}

/// Decode PNG signature + IHDR width/height. Does not upload a GPU atlas.
pub fn png_header_size(bytes: &[u8]) -> Result<(u32, u32), RpcError> {
    if bytes.len() < 24 || !bytes.starts_with(PNG_MAGIC) {
        return Err(invalid_params("src is not a PNG (magic bytes)"));
    }
    if &bytes[12..16] != b"IHDR" {
        return Err(invalid_params("png missing IHDR"));
    }
    let width = u32::from_be_bytes([bytes[16], bytes[17], bytes[18], bytes[19]]);
    let height = u32::from_be_bytes([bytes[20], bytes[21], bytes[22], bytes[23]]);
    if width == 0 || height == 0 || width > MAX_DIM || height > MAX_DIM {
        return Err(invalid_params(format!(
            "png dimensions {width}x{height} exceed 8192x8192"
        )));
    }
    let pixels = u64::from(width).saturating_mul(u64::from(height));
    if pixels.saturating_mul(4) > 256 * 1024 * 1024 {
        return Err(invalid_params("png decode would exceed 256MB"));
    }
    Ok((width, height))
}

fn sidecar_path(png: &Path) -> PathBuf {
    let mut meta = png.as_os_str().to_owned();
    meta.push(".meta.json");
    PathBuf::from(meta)
}

fn write_tmp_rename(path: &Path, bytes: &[u8]) -> Result<(), RpcError> {
    let mut tmp = path.as_os_str().to_owned();
    tmp.push(".tmp");
    let tmp = PathBuf::from(tmp);
    {
        let mut file = File::create(&tmp).map_err(|err| app_err("E_IO", err.to_string()))?;
        file.write_all(bytes)
            .map_err(|err| app_err("E_IO", err.to_string()))?;
        file.flush()
            .map_err(|err| app_err("E_IO", err.to_string()))?;
    }
    fs::rename(&tmp, path).map_err(|err| {
        let _ = fs::remove_file(&tmp);
        app_err("E_IO", err.to_string())
    })
}

fn hex_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    let mut hex = String::with_capacity(64);
    for byte in digest {
        let _ = std::fmt::Write::write_fmt(&mut hex, format_args!("{byte:02x}"));
    }
    hex
}

fn unix_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn png_header_reads_ihdr_size() {
        let mut bytes = vec![0u8; 24];
        bytes[..8].copy_from_slice(PNG_MAGIC);
        bytes[12..16].copy_from_slice(b"IHDR");
        bytes[16..20].copy_from_slice(&16u32.to_be_bytes());
        bytes[20..24].copy_from_slice(&32u32.to_be_bytes());
        assert_eq!(png_header_size(&bytes).expect("header"), (16, 32));
    }

    #[test]
    fn dest_parent_dir_is_rejected() {
        let err = jail_dest(Path::new("."), r"..\outside.png").expect_err("dotdot");
        assert!(
            err.message.contains("not under the project root")
                || err
                    .data
                    .as_ref()
                    .is_some_and(|d| d.app_code == "E_PATH" || d.app_code == "E_VALIDATION")
        );
    }
}
