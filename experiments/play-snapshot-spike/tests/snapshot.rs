use std::fs;
use std::path::PathBuf;
use std::process::Command;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use play_snapshot_spike::{build_snapshot, demo_request};

fn unique_root() -> PathBuf {
    static SEQ: AtomicU64 = AtomicU64::new(0);
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("clock")
        .as_nanos();
    let seq = SEQ.fetch_add(1, Ordering::Relaxed);
    let root = std::env::temp_dir().join(format!(
        "gs-play-snapshot-spike-{}-{}-{}",
        std::process::id(),
        nanos,
        seq
    ));
    fs::create_dir_all(&root).expect("create temp root");
    root
}

fn stub_exe() -> PathBuf {
    if let Some(path) = option_env!("CARGO_BIN_EXE_gs_player_stub") {
        return PathBuf::from(path);
    }
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("target");
    path.push("debug");
    if cfg!(windows) {
        path.push("gs-player-stub.exe");
    } else {
        path.push("gs-player-stub");
    }
    path
}

fn run_stub(manifest: &std::path::Path) -> std::process::Output {
    Command::new(stub_exe())
        .arg("--snapshot")
        .arg(manifest)
        .output()
        .expect("spawn gs-player-stub")
}

#[test]
fn build_snapshot_then_stub_loads_ok() {
    let root = unique_root();
    let built = build_snapshot(&root, &demo_request()).expect("build snapshot");

    let output = run_stub(&built.manifest_path);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        output.status.success(),
        "stub should accept a valid snapshot\nstdout={stdout}\nstderr={stderr}"
    );
    assert!(stdout.contains("OK"), "stdout={stdout}");
    assert!(stdout.contains("p-000001"), "stdout={stdout}");
    assert!(stdout.contains("r-000001"), "stdout={stdout}");

    let _ = fs::remove_dir_all(root);
}

#[test]
fn tampered_scene_is_rejected() {
    let root = unique_root();
    let built = build_snapshot(&root, &demo_request()).expect("build snapshot");

    let scene_path = built.play_dir.join("scene.json");
    let mut bytes = fs::read(&scene_path).expect("read scene.json");
    let flipped = bytes.iter_mut().find(|b| **b == b'2');
    match flipped {
        Some(b) => *b = b'3',
        None => bytes[0] ^= 0x01,
    }
    fs::write(&scene_path, &bytes).expect("write tampered scene.json");

    let output = run_stub(&built.manifest_path);
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(
        !output.status.success(),
        "stub must reject a 1-byte scene tamper\nstdout={stdout}\nstderr={stderr}"
    );
    assert!(
        stderr.contains("REJECT"),
        "stderr should start with REJECT\nstderr={stderr}"
    );

    let _ = fs::remove_dir_all(root);
}
