//! Pack a project folder into a standalone Play directory (T7A.1 / I6 / I7).
//!
//! Does **not** open a `Session` (no `.gs/` WAL). `out_dir` must sit outside
//! the project root. Certificates (`.pfx` / `.cer` / …) are never copied.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Component, Path, PathBuf};

use gs_protocol::PROTOCOL_VER;
use gs_scene::{default_inputmap, resolve_under_root, Scene, SceneFile, MAX_SCRIPT_SOURCE_BYTES};
use serde_json::{json, Value};
use ulid::Ulid;

use crate::builder::{is_cert_rel, write_atomic, write_snapshot_dir, AssetInput, SnapshotRequest};
use crate::error::Error;
use crate::exe::find_player_exe;
use crate::player_file::utc_now_rfc3339;

const SCENE_REL: &str = "scenes/main.gscene.json";
const PROJECT_REL: &str = "project.json";
const ASSET_INDEX_REL: &str = "assets/index.json";

/// Options for [`pack_project`].
#[derive(Clone, Debug)]
pub struct PackOptions {
    pub include_debug: bool,
    pub actor: String,
    pub build_id: Option<String>,
}

impl Default for PackOptions {
    fn default() -> Self {
        Self {
            include_debug: false,
            actor: "pack".into(),
            build_id: None,
        }
    }
}

/// Result of a successful pack. The folder runs with `gs-player --snapshot manifest.json`.
#[derive(Clone, Debug)]
pub struct PackedGame {
    pub build_id: String,
    pub play_id: String,
    pub out_dir: PathBuf,
    pub manifest_path: PathBuf,
    pub player_exe: PathBuf,
}

/// Pack `project` into `out_dir` (must not be inside `project`).
///
/// Validates Script files and imported asset paths **before** creating files
/// in `out_dir`. `$asset` ids with no PNG are allowed (solid-color quads).
pub fn pack_project(
    project: impl AsRef<Path>,
    out_dir: impl AsRef<Path>,
) -> Result<PackedGame, Error> {
    pack_project_with(project, out_dir, PackOptions::default())
}

/// [`pack_project`] with actor / debug / build_id options.
pub fn pack_project_with(
    project: impl AsRef<Path>,
    out_dir: impl AsRef<Path>,
    opts: PackOptions,
) -> Result<PackedGame, Error> {
    let project = project.as_ref();
    let out_dir = out_dir.as_ref();
    if !project.is_dir() {
        return Err(Error::validation(format!(
            "project {} is not a directory",
            project.display()
        )));
    }
    reject_out_dir_inside_project(project, out_dir)?;

    let loaded = load_project_for_pack(project)?;
    let player_src = find_player_exe()?;
    if is_cert_rel(&player_src.to_string_lossy()) {
        return Err(Error::validation(
            "player exe path looks like a certificate; refusing to pack",
        ));
    }

    let build_id = opts
        .build_id
        .clone()
        .unwrap_or_else(|| format!("b_{}", Ulid::new()));
    let play_id = play_id_from_build(&build_id);
    let request = SnapshotRequest {
        play_id: play_id.clone(),
        document_revision: loaded.revision,
        engine_ver: env!("CARGO_PKG_VERSION").to_owned(),
        protocol_ver: PROTOCOL_VER.to_owned(),
        seed: 0,
        created_at: utc_now_rfc3339(),
        actor: opts.actor,
        scene: loaded.scene,
        project_settings: loaded.project_settings,
        input_map: loaded.input_map,
        scripts: loaded.scripts,
        assets: loaded.assets,
    };

    let built = write_snapshot_dir(out_dir, &request)?;
    let player_dest = out_dir.join(player_bin_name());
    copy_atomic(&player_src, &player_dest)?;
    if opts.include_debug {
        copy_debug_sidecar(&player_src, out_dir)?;
    }
    write_run_bat(out_dir)?;
    write_build_json(out_dir, &build_id, &play_id)?;
    copy_icon_if_present(project, out_dir)?;
    refuse_if_certs_present(out_dir)?;

    Ok(PackedGame {
        build_id,
        play_id,
        out_dir: out_dir.to_path_buf(),
        manifest_path: built.manifest_path,
        player_exe: player_dest,
    })
}

/// I7: `out_dir` must not be the project root or a path under it.
pub fn reject_out_dir_inside_project(project: &Path, out_dir: &Path) -> Result<(), Error> {
    let project_abs = abs_normalized(project)?;
    let out_abs = abs_normalized(out_dir)?;
    if out_abs == project_abs || out_abs.starts_with(&project_abs) {
        return Err(Error::path(format!(
            "out_dir {} must not be inside the project root {}",
            out_dir.display(),
            project.display()
        )));
    }
    Ok(())
}

struct LoadedProject {
    scene: Value,
    revision: String,
    input_map: Value,
    scripts: BTreeMap<String, Vec<u8>>,
    assets: BTreeMap<String, AssetInput>,
    project_settings: Value,
}

fn load_project_for_pack(root: &Path) -> Result<LoadedProject, Error> {
    let scene_path = root.join(SCENE_REL.replace('/', std::path::MAIN_SEPARATOR_STR));
    if !scene_path.is_file() {
        return Err(Error::validation(format!(
            "missing {SCENE_REL} under {}",
            root.display()
        )));
    }
    let scene_text = fs::read_to_string(&scene_path).map_err(|e| Error::io(&scene_path, e))?;
    let file: SceneFile =
        serde_json::from_str(&scene_text).map_err(|e| Error::json(&scene_path, e))?;
    let scene = Scene::from_file(file).map_err(|e| Error::validation(e.to_string()))?;
    validate_script_files(root, &scene)?;
    let assets = load_imported_assets(root)?;
    let scripts = collect_scripts(root, &scene)?;
    let input_map = load_input_map(root)?;
    let meta = load_project_meta(root);
    Ok(LoadedProject {
        scene: scene.to_canonical_value(),
        revision: meta.revision,
        input_map,
        scripts,
        assets,
        project_settings: meta.settings,
    })
}

fn validate_script_files(root: &Path, scene: &Scene) -> Result<(), Error> {
    for entity in scene.entities.values() {
        let Some(script) = &entity.extra.script else {
            continue;
        };
        let rel = script.file.replace('\\', "/");
        let abs = jail_project_rel(root, &rel)?;
        if !abs.is_file() {
            return Err(Error::validation(format!(
                "missing script {} (entity {})",
                script.file,
                entity.id_str()
            )));
        }
    }
    Ok(())
}

fn collect_scripts(root: &Path, scene: &Scene) -> Result<BTreeMap<String, Vec<u8>>, Error> {
    let mut scripts = BTreeMap::new();
    let dir = root.join("scripts");
    if dir.is_dir() {
        collect_luau_dir(&dir, &dir, root, &mut scripts)?;
    }
    for entity in scene.entities.values() {
        let Some(script) = &entity.extra.script else {
            continue;
        };
        let rel = script.file.replace('\\', "/");
        let key = snapshot_script_key(&rel);
        if scripts.contains_key(&key) {
            continue;
        }
        let abs = jail_project_rel(root, &rel)?;
        let bytes = fs::read(&abs).map_err(|e| Error::io(&abs, e))?;
        if bytes.len() > MAX_SCRIPT_SOURCE_BYTES {
            return Err(Error::validation(format!(
                "script {} exceeds {MAX_SCRIPT_SOURCE_BYTES} bytes",
                script.file
            )));
        }
        scripts.insert(key, bytes);
    }
    Ok(scripts)
}

fn collect_luau_dir(
    dir: &Path,
    scripts_root: &Path,
    project_root: &Path,
    out: &mut BTreeMap<String, Vec<u8>>,
) -> Result<(), Error> {
    let entries = fs::read_dir(dir).map_err(|e| Error::io(dir, e))?;
    for entry in entries {
        let entry = entry.map_err(|e| Error::io(dir, e))?;
        let path = entry.path();
        if path.is_dir() {
            collect_luau_dir(&path, scripts_root, project_root, out)?;
            continue;
        }
        let Some(name) = path.file_name().and_then(|s| s.to_str()) else {
            continue;
        };
        if !name.ends_with(".luau") || name.contains("..") {
            continue;
        }
        let rel = path
            .strip_prefix(scripts_root)
            .map(|p| p.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|_| name.to_owned());
        let dest = format!("scripts/{rel}");
        let abs = jail_project_rel(project_root, &dest)?;
        let bytes = fs::read(&abs).map_err(|e| Error::io(&abs, e))?;
        if bytes.len() > MAX_SCRIPT_SOURCE_BYTES {
            continue;
        }
        out.insert(rel, bytes);
    }
    Ok(())
}

fn snapshot_script_key(file: &str) -> String {
    file.strip_prefix("scripts/")
        .unwrap_or(file)
        .replace('\\', "/")
}

fn load_imported_assets(root: &Path) -> Result<BTreeMap<String, AssetInput>, Error> {
    let index = root.join(ASSET_INDEX_REL.replace('/', std::path::MAIN_SEPARATOR_STR));
    if !index.is_file() {
        return Ok(BTreeMap::new());
    }
    let bytes = fs::read(&index).map_err(|e| Error::io(&index, e))?;
    let value: Value = serde_json::from_slice(&bytes).map_err(|e| Error::json(&index, e))?;
    let mut out = BTreeMap::new();
    let Some(arr) = value.get("assets").and_then(Value::as_array) else {
        return Ok(out);
    };
    for rec in arr {
        let id = rec
            .get("asset_id")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned();
        if id.is_empty() {
            continue;
        }
        let dest = rec
            .get("dest_rel")
            .or_else(|| rec.get("path"))
            .and_then(Value::as_str)
            .unwrap_or("")
            .replace('\\', "/");
        if dest.is_empty() {
            continue;
        }
        if is_cert_rel(&dest) {
            return Err(Error::validation(format!(
                "imported asset {id} path {dest} looks like a certificate"
            )));
        }
        let abs = jail_project_rel(root, &dest)?;
        if !abs.is_file() {
            return Err(Error::validation(format!(
                "imported asset {id} is missing file {dest}"
            )));
        }
        let content = fs::read(&abs).map_err(|e| Error::io(&abs, e))?;
        out.insert(
            id,
            AssetInput {
                path: dest,
                content: Some(content),
            },
        );
    }
    Ok(out)
}

fn load_input_map(root: &Path) -> Result<Value, Error> {
    let path = root.join(gs_scene::INPUTMAP_REL);
    if !path.is_file() {
        return Ok(default_inputmap());
    }
    let text = fs::read_to_string(&path).map_err(|e| Error::io(&path, e))?;
    serde_json::from_str(&text).map_err(|e| Error::json(&path, e))
}

struct ProjectMeta {
    revision: String,
    settings: Value,
}

fn load_project_meta(root: &Path) -> ProjectMeta {
    let mut settings = json!({
        "fixed_dt": 1.0 / 60.0,
        "ppu": 16,
        "schema_version": 1,
    });
    let path = root.join(PROJECT_REL);
    let Ok(text) = fs::read_to_string(&path) else {
        return ProjectMeta {
            revision: "r-000000".into(),
            settings,
        };
    };
    let Ok(value) = serde_json::from_str::<Value>(&text) else {
        return ProjectMeta {
            revision: "r-000000".into(),
            settings,
        };
    };
    if let Some(Value::Number(n)) = value.get("fixed_dt") {
        settings["fixed_dt"] = Value::Number(n.clone());
    }
    if let Some(Value::Number(n)) = value.get("ppu") {
        settings["ppu"] = Value::Number(n.clone());
    }
    if let Some(Value::String(title)) = value.get("title") {
        let title = title.trim();
        if !title.is_empty() && title.len() <= 80 {
            settings["title"] = json!(title);
        }
    }
    let revision = match value.get("revision") {
        Some(Value::Number(n)) => format!("r-{:06}", n.as_u64().unwrap_or(0)),
        Some(Value::String(s)) if s.starts_with("r-") => s.clone(),
        _ => "r-000000".into(),
    };
    ProjectMeta { revision, settings }
}

fn play_id_from_build(build_id: &str) -> String {
    if let Some(rest) = build_id.strip_prefix("b_") {
        format!("p_{rest}")
    } else {
        format!("p_{build_id}")
    }
}

fn player_bin_name() -> &'static str {
    if cfg!(windows) {
        "gs-player.exe"
    } else {
        "gs-player"
    }
}

fn copy_atomic(src: &Path, dest: &Path) -> Result<(), Error> {
    if is_cert_rel(&dest.to_string_lossy()) || is_cert_rel(&src.to_string_lossy()) {
        return Err(Error::validation("refusing to copy a certificate file"));
    }
    let bytes = fs::read(src).map_err(|e| Error::io(src, e))?;
    write_atomic(dest, &bytes)
}

fn copy_icon_if_present(project: &Path, out_dir: &Path) -> Result<(), Error> {
    let src = match jail_project_rel(project, "icon.png") {
        Ok(path) => path,
        Err(err) if err.app_code() == "E_PATH" => return Err(err),
        Err(_) => return Ok(()),
    };
    if !src.is_file() {
        return Ok(());
    }
    let Ok(canon) = src.canonicalize() else {
        return Ok(());
    };
    let root = abs_normalized(project)?;
    if canon != root && !canon.starts_with(&root) {
        return Err(Error::path("path icon.png is not under the project root"));
    }
    copy_atomic(&src, &out_dir.join("icon.png"))
}

fn copy_debug_sidecar(player_src: &Path, out_dir: &Path) -> Result<(), Error> {
    let pdb = player_src.with_extension("pdb");
    if pdb.is_file() {
        copy_atomic(&pdb, &out_dir.join(pdb.file_name().unwrap_or_default()))?;
    }
    Ok(())
}

fn write_run_bat(out_dir: &Path) -> Result<(), Error> {
    let exe = player_bin_name();
    let body = format!(
        "@echo off\r\ncd /d \"%~dp0\"\r\nstart \"\" \"%~dp0{exe}\" --snapshot \"%~dp0manifest.json\"\r\n"
    );
    write_atomic(&out_dir.join("run.bat"), body.as_bytes())
}

fn write_build_json(out_dir: &Path, build_id: &str, play_id: &str) -> Result<(), Error> {
    let value = json!({
        "build_id": build_id,
        "play_id": play_id,
        "signed": false,
        "schema_version": 1,
    });
    let bytes = serde_json::to_vec_pretty(&value).map_err(|e| Error::json(out_dir, e))?;
    write_atomic(&out_dir.join("build.json"), &bytes)
}

fn refuse_if_certs_present(out_dir: &Path) -> Result<(), Error> {
    if let Some(path) = find_cert_file(out_dir)? {
        return Err(Error::validation(format!(
            "packed output must not contain certificates ({})",
            path.display()
        )));
    }
    Ok(())
}

fn find_cert_file(dir: &Path) -> Result<Option<PathBuf>, Error> {
    if !dir.is_dir() {
        return Ok(None);
    }
    let entries = fs::read_dir(dir).map_err(|e| Error::io(dir, e))?;
    for entry in entries {
        let entry = entry.map_err(|e| Error::io(dir, e))?;
        let path = entry.path();
        if path.is_dir() {
            if let Some(found) = find_cert_file(&path)? {
                return Ok(Some(found));
            }
            continue;
        }
        if is_cert_rel(&path.to_string_lossy()) {
            return Ok(Some(path));
        }
    }
    Ok(None)
}

/// I7: reject `..`, absolute paths, Windows reserved names; keep the result under root.
fn jail_project_rel(root: &Path, rel: &str) -> Result<PathBuf, Error> {
    let dest = rel.replace('\\', "/");
    let abs = resolve_under_root(root, &dest).map_err(map_root_escape)?;
    ensure_stays_under_root(root, &abs, &dest)?;
    Ok(abs)
}

fn map_root_escape(err: gs_scene::Error) -> Error {
    match err {
        gs_scene::Error::PathEscapesRoot { path } => {
            Error::path(format!("path {path} is not under the project root"))
        }
        other => Error::path(other.to_string()),
    }
}

fn ensure_stays_under_root(root: &Path, abs: &Path, rel: &str) -> Result<(), Error> {
    let root_abs = abs_normalized(root)?;
    let resolved = match abs.canonicalize() {
        Ok(p) => p,
        Err(_) => abs_normalized(abs)?,
    };
    if resolved == root_abs || resolved.starts_with(&root_abs) {
        Ok(())
    } else {
        Err(Error::path(format!(
            "path {rel} is not under the project root"
        )))
    }
}

fn abs_normalized(path: &Path) -> Result<PathBuf, Error> {
    if path.exists() {
        return path.canonicalize().map_err(|e| Error::io(path, e));
    }
    let abs = if path.is_absolute() {
        path.to_path_buf()
    } else {
        std::env::current_dir()
            .map_err(|e| Error::io(path, e))?
            .join(path)
    };
    let mut missing = Vec::new();
    let mut cur = abs.as_path();
    loop {
        if cur.exists() {
            let mut canon = cur.canonicalize().map_err(|e| Error::io(cur, e))?;
            for part in missing.iter().rev() {
                canon.push(part);
            }
            return Ok(canon);
        }
        match cur.file_name() {
            Some(name) => {
                missing.push(name.to_os_string());
                match cur.parent() {
                    Some(parent) => cur = parent,
                    None => break,
                }
            }
            None => break,
        }
    }
    Ok(normalize_components(&abs))
}

fn normalize_components(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for c in path.components() {
        match c {
            Component::Prefix(p) => out.push(p.as_os_str()),
            Component::RootDir => out.push(c.as_os_str()),
            Component::CurDir => {}
            Component::ParentDir => {
                let _ = out.pop();
            }
            Component::Normal(s) => out.push(s),
        }
    }
    out
}
