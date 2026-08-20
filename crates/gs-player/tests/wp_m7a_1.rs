//! WP-M7A-1: `pack_project` without the editor bus (T7A.1 / I7).

use std::fs;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::time::{Duration, Instant};

use gs_player::{
    pack_project, pack_project_with, run_headless_frames, verify_snapshot, PackOptions,
};
use gs_scene::{Camera2D, Entity, Name, Scene, SceneFile, Script, Transform2D};
use serde_json::json;
use tempfile::TempDir;

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn player_name() -> &'static str {
    if cfg!(windows) {
        "gs-player.exe"
    } else {
        "gs-player"
    }
}

fn write_min_project(root: &Path, script_file: Option<&str>) {
    fs::create_dir_all(root.join("scenes")).expect("scenes");
    fs::create_dir_all(root.join("scripts")).expect("scripts");
    fs::write(
        root.join("project.json"),
        r#"{"schema_version":1,"revision":0,"next_entity":3,"next_asset":1}"#,
    )
    .expect("project.json");
    fs::write(
        root.join("inputmap.json"),
        r#"{"actions":[{"name":"move_x","type":"axis","keys":[["A",-1.0],["D",1.0]]}]}"#,
    )
    .expect("inputmap");

    let mut scene = Scene::default();
    let mut cam = Entity::new(1, None, 0);
    cam.name = Some(Name {
        value: "cam".into(),
    });
    cam.transform = Some(Transform2D {
        x: 0.0,
        y: 0.0,
        rot: 0.0,
        sx: 1.0,
        sy: 1.0,
        z_index: 0,
    });
    cam.extra.camera = Some(Camera2D {
        ortho_height: 10.0,
        active: true,
    });
    scene.entities.insert(1, cam);

    if let Some(file) = script_file {
        let mut ent = Entity::new(2, None, 1);
        ent.name = Some(Name {
            value: "scripted".into(),
        });
        ent.extra.script = Some(Script {
            file: file.into(),
            props: Default::default(),
        });
        scene.entities.insert(2, ent);
        if file == "scripts/ok.luau" {
            fs::write(
                root.join("scripts").join("ok.luau"),
                "local M = {}\nfunction M.on_update(self)\nend\nreturn M\n",
            )
            .expect("script");
        }
    }

    let file = SceneFile {
        schema_version: 1,
        mode: "2d".into(),
        entities: scene.to_file().entities,
        unknown: Default::default(),
    };
    let bytes = serde_json::to_vec_pretty(&file).expect("scene json");
    fs::write(root.join("scenes").join("main.gscene.json"), bytes).expect("scene");
}

#[test]
fn pack_project_snake_verifies() {
    let snake = repo_root().join("games").join("snake");
    assert!(
        snake.join("project.json").is_file(),
        "games/snake must exist"
    );
    let out = TempDir::new().expect("out");
    let packed = pack_project(&snake, out.path()).expect("pack snake");
    assert!(packed.player_exe.is_file());
    assert!(packed.manifest_path.is_file());
    verify_snapshot(&packed.manifest_path).expect("verify_snapshot");
    assert!(out.path().join("run.bat").is_file());
    assert!(out.path().join("scripts").join("snake.luau").is_file());
    assert!(!out.path().join(".gs").join("wal").exists());
}

#[test]
fn pack_project_rejects_out_dir_inside_project() {
    let project = TempDir::new().expect("project");
    write_min_project(project.path(), Some("scripts/ok.luau"));
    let inside = project.path().join("releases");
    let err = pack_project(project.path(), &inside).expect_err("inside");
    assert_eq!(err.app_code(), "E_PATH");
    assert!(!inside.join(player_name()).exists());
}

#[test]
fn pack_project_missing_script_does_not_copy_player() {
    let project = TempDir::new().expect("project");
    write_min_project(project.path(), Some("scripts/nope.luau"));
    let out = TempDir::new().expect("out");
    let err = pack_project(project.path(), out.path()).expect_err("missing script");
    assert_eq!(err.app_code(), "E_VALIDATION");
    assert!(err.to_string().contains("nope.luau"));
    assert!(!out.path().join(player_name()).exists());
    let leftover: Vec<_> = fs::read_dir(out.path())
        .expect("read")
        .filter_map(|e| e.ok())
        .collect();
    assert!(leftover.is_empty(), "out_dir not empty: {leftover:?}");
}

#[test]
fn pack_project_does_not_copy_pfx() {
    let project = TempDir::new().expect("project");
    write_min_project(project.path(), Some("scripts/ok.luau"));
    fs::write(project.path().join("editor.pfx"), b"not-a-cert").expect("pfx");
    let out = TempDir::new().expect("out");
    pack_project_with(
        project.path(),
        out.path(),
        PackOptions {
            include_debug: false,
            actor: "test".into(),
            build_id: Some("b_testpack01".into()),
        },
    )
    .expect("pack");
    assert!(!out.path().join("editor.pfx").exists());
    let build = fs::read_to_string(out.path().join("build.json")).expect("build.json");
    let value: serde_json::Value = serde_json::from_str(&build).expect("json");
    assert_eq!(value["signed"], false);
    assert_eq!(value["build_id"], "b_testpack01");
}

#[test]
fn pack_project_imported_asset_missing_file_fails_early() {
    let project = TempDir::new().expect("project");
    write_min_project(project.path(), Some("scripts/ok.luau"));
    fs::create_dir_all(project.path().join("assets")).expect("assets");
    fs::write(
        project.path().join("assets").join("index.json"),
        json!({
            "schema_version": 1,
            "next_asset": 2,
            "assets": [{
                "asset_id": "a_000001",
                "dest_rel": "assets/missing.png",
                "kind": "png"
            }]
        })
        .to_string(),
    )
    .expect("index");
    let out = TempDir::new().expect("out");
    let err = pack_project(project.path(), out.path()).expect_err("missing png");
    assert_eq!(err.app_code(), "E_VALIDATION");
    assert!(!out.path().join(player_name()).exists());
}

#[test]
fn pack_project_rejects_dest_rel_escape() {
    let workspace = TempDir::new().expect("workspace");
    let project = workspace.path().join("game");
    fs::create_dir_all(&project).expect("project dir");
    write_min_project(&project, Some("scripts/ok.luau"));
    fs::write(workspace.path().join("secret.png"), b"not-inside").expect("outside png");
    fs::create_dir_all(project.join("assets")).expect("assets");
    fs::write(
        project.join("assets").join("index.json"),
        json!({
            "schema_version": 1,
            "next_asset": 2,
            "assets": [{
                "asset_id": "a_000001",
                "dest_rel": "../secret.png",
                "kind": "png"
            }]
        })
        .to_string(),
    )
    .expect("index");
    let out = TempDir::new().expect("out");
    let err = pack_project(&project, out.path()).expect_err("escape dest_rel");
    assert_eq!(err.app_code(), "E_PATH");
    assert!(!out.path().join(player_name()).exists());
    let leftover: Vec<_> = fs::read_dir(out.path())
        .expect("read")
        .filter_map(|e| e.ok())
        .collect();
    assert!(leftover.is_empty(), "out_dir not empty: {leftover:?}");
}

#[test]
fn pack_project_snake_runs_headless() {
    let snake = repo_root().join("games").join("snake");
    assert!(
        snake.join("project.json").is_file(),
        "games/snake must exist"
    );
    let out = TempDir::new().expect("out");
    let packed = pack_project(&snake, out.path()).expect("pack snake");
    let report = run_headless_frames(&packed.manifest_path, 30).expect("packed snake headless");
    assert!(
        report.frames >= 30,
        "packed snake must simulate >= 30 frames without the editor, got {}",
        report.frames
    );
}

/// Proof the **copied** `gs-player.exe` runs the packed snapshot (not in-process).
#[test]
fn pack_project_snake_spawns_packed_exe() {
    let snake = repo_root().join("games").join("snake");
    assert!(
        snake.join("project.json").is_file(),
        "games/snake must exist"
    );
    let out = TempDir::new().expect("out");
    let packed = pack_project(&snake, out.path()).expect("pack snake");
    assert!(
        packed.player_exe.is_file(),
        "packed exe missing: {}",
        packed.player_exe.display()
    );
    assert_eq!(
        packed.player_exe.file_name().and_then(|n| n.to_str()),
        Some(player_name()),
        "must spawn the copied packed player, not CARGO_BIN_EXE"
    );
    let cwd = packed
        .player_exe
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| packed.out_dir.clone());

    let child = Command::new(&packed.player_exe)
        .arg("--snapshot")
        .arg(&packed.manifest_path)
        .arg("--headless")
        .arg("--frames")
        .arg("8")
        .current_dir(&cwd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("spawn packed player exe");
    let mut guard = KillOnDrop(Some(child));
    let status = wait_or_kill(guard.0.as_mut().expect("child"), Duration::from_secs(60));
    let mut child = guard.0.take().expect("child");
    let stdout = read_pipe(child.stdout.take());
    let stderr = read_pipe(child.stderr.take());
    // `wait_or_kill` already reaped it; this repeat wait is what tells clippy the
    // child cannot become a zombie.
    let _ = child.wait();

    assert!(
        status.success(),
        "packed exe exit {:?}\nstdout:\n{stdout}\nstderr:\n{stderr}",
        status.code()
    );
    assert!(
        stdout.contains("frames="),
        "stdout must contain frames=: {stdout}"
    );
    let frames = frames_from_stdout(&stdout).expect("frames=N in stdout");
    assert!(
        frames >= 8,
        "packed exe must report frames>=8, got {frames}; stdout={stdout}"
    );
}

struct KillOnDrop(Option<Child>);

impl Drop for KillOnDrop {
    fn drop(&mut self) {
        if let Some(mut child) = self.0.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }
}

fn wait_or_kill(child: &mut Child, limit: Duration) -> std::process::ExitStatus {
    let start = Instant::now();
    loop {
        if let Some(status) = child.try_wait().expect("try_wait packed exe") {
            return status;
        }
        if start.elapsed() >= limit {
            let _ = child.kill();
            let _ = child.wait();
            panic!("packed player exe exceeded {limit:?}; killed");
        }
        std::thread::sleep(Duration::from_millis(50));
    }
}

fn read_pipe(pipe: Option<impl Read>) -> String {
    let mut buf = String::new();
    if let Some(mut r) = pipe {
        let _ = r.read_to_string(&mut buf);
    }
    buf
}

fn frames_from_stdout(stdout: &str) -> Option<u64> {
    let rest = stdout.split("frames=").nth(1)?;
    let digits: String = rest.chars().take_while(|c| c.is_ascii_digit()).collect();
    digits.parse().ok()
}
