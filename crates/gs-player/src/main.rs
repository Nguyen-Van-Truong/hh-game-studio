//! `gs-player --snapshot <manifest.json> [--headless] [--no-render] [--frames N] [--control-port 0]`

use std::net::{IpAddr, Ipv4Addr, SocketAddr};
use std::process::ExitCode;

use gs_player::{
    control_ready_line, install_panic_exit_report, pack_project_with, run_headless_frames_with,
    run_window, Args, ControlConfig, ControlServer, Error, PackOptions, PlaySource,
};

fn main() -> ExitCode {
    match run() {
        Ok(code) => ExitCode::from(code),
        Err(err) => {
            eprintln!("REJECT {err}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<u8, Error> {
    install_panic_exit_report();
    let args = Args::from_env()?;
    if args.wants_pack() {
        return run_pack(&args);
    }
    let snapshot = args
        .snapshot
        .as_ref()
        .ok_or_else(|| Error::usage("missing --snapshot <path-to-manifest.json>"))?;
    if args.wants_control() {
        return run_controlled(&args);
    }
    if args.wants_window() {
        run_window(snapshot)?;
        return Ok(0);
    }
    let report = run_headless_frames_with(
        snapshot,
        args.frame_count(),
        args.replay.as_deref(),
        args.record.as_deref(),
        args.force,
    )?;
    if !report.evidence_ok {
        for warning in &report.warnings {
            eprintln!("WARNING {warning}");
        }
    }
    println!(
        "OK {} {} frames={}",
        report.play_id, report.document_revision, report.frames
    );
    Ok(0)
}

fn run_controlled(args: &Args) -> Result<u8, Error> {
    let port = args.control_port.unwrap_or(0);
    let bind = SocketAddr::new(IpAddr::V4(Ipv4Addr::LOCALHOST), port);
    let mut config = ControlConfig::from_env();
    if args.no_render {
        config.no_render = true;
    }
    config.record_tape = args.record.clone();
    config.replay_tape = args.replay.clone();
    config.force_tape = args.force;
    let handle = ControlServer::start_with_config(
        PlaySource::Snapshot(
            args.snapshot
                .clone()
                .ok_or_else(|| Error::usage("missing --snapshot <path-to-manifest.json>"))?,
        ),
        bind,
        None,
        config,
    )?;
    println!(
        "{}",
        control_ready_line(
            &handle.status().play_id,
            handle.local_addr().port(),
            std::process::id()
        )
    );
    let report = handle.run_until_stop()?;
    let code = u8::try_from(report.exit_code.clamp(0, 255)).unwrap_or(1);
    Ok(code)
}

fn run_pack(args: &Args) -> Result<u8, Error> {
    let project = args
        .project
        .as_ref()
        .ok_or_else(|| Error::usage("missing --project"))?;
    let out = args
        .out
        .as_ref()
        .ok_or_else(|| Error::usage("missing --out"))?;
    let packed = pack_project_with(
        project,
        out,
        PackOptions {
            include_debug: args.include_debug,
            actor: "gs-player".into(),
            build_id: None,
        },
    )?;
    println!("OK {} {}", packed.build_id, packed.manifest_path.display());
    Ok(0)
}
