//! WP-M6-1 `gs doctor` exit codes (MASTER 8.5). Does not start the editor bus.

use std::process::Command;

fn gs_cli() -> Command {
    Command::new(env!("CARGO_BIN_EXE_gs-cli"))
}

#[test]
fn doctor_force_ok_exits_0() {
    let out = gs_cli()
        .env("GS_DOCTOR_FORCE", "ok")
        .env("GS_COMFY_URL", "http://127.0.0.1:1")
        .env("GS_IMAGEGEN_CONFIG", "no-such-imagegen-force-ok.json")
        .arg("doctor")
        .output()
        .expect("run doctor");
    assert_eq!(out.status.code(), Some(0), "stdout={}", text(&out.stdout));
    let stdout = text(&out.stdout);
    assert!(stdout.contains("GS_DOCTOR_FORCE=ok"));
    assert!(!stdout.to_ascii_lowercase().contains("api_key"));
}

#[test]
fn doctor_force_missing_exits_1() {
    let out = gs_cli()
        .env("GS_DOCTOR_FORCE", "missing")
        .env("GS_COMFY_URL", "http://127.0.0.1:1")
        .env("GS_IMAGEGEN_CONFIG", "no-such-imagegen-force-missing.json")
        .arg("doctor")
        .output()
        .expect("run doctor");
    assert_eq!(out.status.code(), Some(1), "stdout={}", text(&out.stdout));
    let stdout = text(&out.stdout);
    assert!(stdout.contains("no usable provider"));
    assert!(!stdout.contains("sk-"));
}

fn text(bytes: &[u8]) -> String {
    String::from_utf8_lossy(bytes).into_owned()
}
