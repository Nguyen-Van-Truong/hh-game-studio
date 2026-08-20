use std::path::PathBuf;

use crate::error::Error;

/// CLI for `gs-player`. `--frames` / `--headless` / `--no-render` never open a window.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Args {
    pub snapshot: Option<PathBuf>,
    /// Pack a project folder into `out` (no editor bus). Requires `--out`.
    pub project: Option<PathBuf>,
    pub out: Option<PathBuf>,
    pub include_debug: bool,
    pub headless: bool,
    /// Simulate + obs without GPU. `GS_GPU=none` / `GS_GPU=warp` also set this.
    pub no_render: bool,
    pub frames: Option<u32>,
    /// `Some(0)` binds an ephemeral 127.0.0.1 port (MASTER 6.1).
    pub control_port: Option<u16>,
    /// Write a `.tape.jsonl` while simulating (header first, then action lines).
    pub record: Option<PathBuf>,
    /// Drive `InputFrame` from this tape instead of device / inject.
    pub replay: Option<PathBuf>,
    /// Replay a mismatched tape with a loud warning; `evidence_ok` is false.
    pub force: bool,
}

impl Args {
    pub fn parse<I, S>(args: I) -> Result<Self, Error>
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut snapshot = None;
        let mut project = None;
        let mut out = None;
        let mut include_debug = false;
        let mut headless = false;
        let mut no_render = false;
        let mut frames = None;
        let mut control_port = None;
        let mut record = None;
        let mut replay = None;
        let mut force = false;
        let mut iter = args.into_iter().peekable();
        // Skip argv[0] when it looks like a program path.
        if let Some(first) = iter.peek() {
            let first = first.as_ref();
            if !first.starts_with('-') && !first.is_empty() && snapshot_flag_next(first) {
                iter.next();
            }
        }
        let raw: Vec<String> = iter.map(|s| s.as_ref().to_string()).collect();
        let mut i = 0;
        while i < raw.len() {
            match raw[i].as_str() {
                "--snapshot" => {
                    i += 1;
                    let path = raw.get(i).ok_or_else(|| {
                        Error::usage("--snapshot requires a path to manifest.json")
                    })?;
                    snapshot = Some(PathBuf::from(path));
                }
                "--project" => {
                    i += 1;
                    let path = raw
                        .get(i)
                        .ok_or_else(|| Error::usage("--project requires a project directory"))?;
                    project = Some(PathBuf::from(path));
                }
                "--out" => {
                    i += 1;
                    let path = raw
                        .get(i)
                        .ok_or_else(|| Error::usage("--out requires a directory"))?;
                    out = Some(PathBuf::from(path));
                }
                "--include-debug" => include_debug = true,
                "--headless" => headless = true,
                "--no-render" => no_render = true,
                "--frames" => {
                    i += 1;
                    let n = raw
                        .get(i)
                        .ok_or_else(|| Error::usage("--frames requires N"))?;
                    let n = n.parse::<u32>().map_err(|_| {
                        Error::usage(format!("--frames expects an integer, got {n}"))
                    })?;
                    frames = Some(n);
                }
                "--control-port" => {
                    i += 1;
                    let n = raw.get(i).ok_or_else(|| {
                        Error::usage("--control-port requires a port (0 = ephemeral)")
                    })?;
                    let n = n.parse::<u16>().map_err(|_| {
                        Error::usage(format!("--control-port expects a port, got {n}"))
                    })?;
                    control_port = Some(n);
                }
                "--record" => {
                    i += 1;
                    let path = raw
                        .get(i)
                        .ok_or_else(|| Error::usage("--record requires a path"))?;
                    record = Some(PathBuf::from(path));
                }
                "--replay" => {
                    i += 1;
                    let path = raw
                        .get(i)
                        .ok_or_else(|| Error::usage("--replay requires a path"))?;
                    replay = Some(PathBuf::from(path));
                }
                "--force" => force = true,
                "--help" | "-h" => {
                    return Err(Error::usage(help_text()));
                }
                other => {
                    return Err(Error::usage(format!("unknown argument: {other}")));
                }
            }
            i += 1;
        }
        let packing = project.is_some() || out.is_some();
        if packing {
            if project.is_none() || out.is_none() {
                return Err(Error::usage(
                    "pack mode requires both --project <dir> and --out <dir>",
                ));
            }
        } else if snapshot.is_none() {
            return Err(Error::usage(
                "missing --snapshot <path-to-manifest.json> (or --project + --out to pack)",
            ));
        }
        Ok(Self {
            snapshot,
            project,
            out,
            include_debug,
            headless,
            no_render,
            frames,
            control_port,
            record,
            replay,
            force,
        })
    }

    pub fn from_env() -> Result<Self, Error> {
        let mut parsed = Self::parse(std::env::args())?;
        parsed.apply_gpu_env();
        Ok(parsed)
    }

    fn apply_gpu_env(&mut self) {
        if crate::gpu::GpuMode::from_env().forces_no_render() {
            self.no_render = true;
        }
    }

    /// Pack a project into `out` without starting Play.
    pub fn wants_pack(&self) -> bool {
        self.project.is_some() && self.out.is_some()
    }

    /// Window path is only for interactive Play (no `--headless`, no `--frames`, no control).
    pub fn wants_window(&self) -> bool {
        !self.wants_pack()
            && self.snapshot.is_some()
            && !self.headless
            && !self.no_render
            && self.frames.is_none()
            && self.control_port.is_none()
            && self.record.is_none()
            && self.replay.is_none()
    }

    /// Control server is started when `--control-port` is present (M2-1 `--frames` stays standalone).
    pub fn wants_control(&self) -> bool {
        self.control_port.is_some()
    }

    /// Steps to run when not opening a window. `--headless` defaults to 1.
    pub fn frame_count(&self) -> u32 {
        self.frames.unwrap_or(1)
    }
}

fn snapshot_flag_next(first: &str) -> bool {
    // argv[0] is the exe; treat anything that is not a flag as the program name.
    !first.starts_with("--")
}

fn help_text() -> String {
    "gs-player --snapshot <manifest.json> [--headless] [--no-render] [--frames N] [--control-port 0]\n\
     [--record <tape.jsonl>] [--replay <tape.jsonl>] [--force]\n\
     gs-player --project <dir> --out <dir> [--include-debug]\n\
     env: GS_GPU=auto|warp|none  (warp is treated as no-render; no wgpu WARP adapter in this crate)\n\
     env: GS_TEST_HANG_MS=<ms>   (test-only: next step() uses fake elapsed; >2000 → exit 13)"
        .into()
}

#[cfg(test)]
mod tests {
    use super::Args;

    #[test]
    fn parses_headless_frames() {
        let args = Args::parse([
            "gs-player",
            "--snapshot",
            "play/manifest.json",
            "--headless",
            "--frames",
            "3",
        ])
        .expect("args");
        assert_eq!(
            args.snapshot.as_ref().map(|p| p.as_os_str()),
            Some(std::ffi::OsStr::new("play/manifest.json"))
        );
        assert!(args.headless);
        assert!(!args.no_render);
        assert_eq!(args.frames, Some(3));
        assert!(args.control_port.is_none());
        assert!(!args.wants_window());
        assert!(!args.wants_control());
        assert_eq!(args.frame_count(), 3);
    }

    #[test]
    fn parses_no_render() {
        let args = Args::parse([
            "gs-player",
            "--snapshot",
            "m.json",
            "--no-render",
            "--control-port",
            "0",
        ])
        .expect("args");
        assert!(args.no_render);
        assert!(args.wants_control());
        assert!(!args.wants_window());
    }

    #[test]
    fn parses_control_port_ephemeral() {
        let args = Args::parse([
            "gs-player",
            "--snapshot",
            "m.json",
            "--headless",
            "--control-port",
            "0",
        ])
        .expect("args");
        assert_eq!(args.control_port, Some(0));
        assert!(args.wants_control());
        assert!(!args.wants_window());
    }

    #[test]
    fn window_only_without_headless_or_frames() {
        let args = Args::parse(["gs-player", "--snapshot", "m.json"]).expect("args");
        assert!(args.wants_window());
        assert!(!args.wants_pack());
    }

    #[test]
    fn parses_pack_project_out() {
        let args = Args::parse([
            "gs-player",
            "--project",
            "games/snake",
            "--out",
            "C:/tmp/pack",
        ])
        .expect("args");
        assert!(args.wants_pack());
        assert!(!args.wants_window());
        assert_eq!(
            args.project.as_ref().map(|p| p.as_os_str()),
            Some(std::ffi::OsStr::new("games/snake"))
        );
    }
}
