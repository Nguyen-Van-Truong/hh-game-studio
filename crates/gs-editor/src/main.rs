//! Thin process entry: start the bus, then the eframe/wgpu 5-region shell.
//!
//! Integration tests use [`gs_editor::start`] only — they never call
//! [`gs_editor::run_native_window`].

use serde_json::json;
use std::path::PathBuf;

fn main() {
    if let Err(err) = run() {
        eprintln!("gs-editor failed: {err}");
        std::process::exit(1);
    }
}

fn run() -> Result<(), gs_editor::Error> {
    let cwd = std::env::current_dir()?;
    let argv1 = std::env::args().nth(1).map(PathBuf::from);
    let project = gs_editor::resolve_startup_project(&cwd, argv1.as_deref());

    let (runtime_root, open_path) = match project {
        Some(path) => (path.clone(), Some(path)),
        None => {
            eprintln!("usage: gs-editor <project-dir>");
            (ephemeral_runtime_root()?, None)
        }
    };

    let bus = gs_editor::start(&runtime_root)?;
    println!("gs-editor bus bound to 127.0.0.1:{}", bus.endpoint().port);
    println!("endpoint file: {}", bus.endpoint_path().display());
    if let Some(path) = open_path {
        let path = path.to_string_lossy().into_owned();
        if let Err(err) = bus.ui().call("project.open", json!({ "path": path })) {
            eprintln!("project.open skipped: {}", err.message);
        }
    }
    gs_editor::run_native_window(bus)
}

/// Bus files go under `%TEMP%/gs-editor-<pid>` so a no-project launch does not
/// create `.gs/` in the repo root.
fn ephemeral_runtime_root() -> Result<PathBuf, gs_editor::Error> {
    let dir = std::env::temp_dir().join(format!("gs-editor-{}", std::process::id()));
    std::fs::create_dir_all(&dir)?;
    Ok(dir)
}

#[cfg(test)]
mod tests {
    #[test]
    fn smoke_bin_name() {
        assert!(env!("CARGO_PKG_NAME").contains("gs-editor"));
    }
}
