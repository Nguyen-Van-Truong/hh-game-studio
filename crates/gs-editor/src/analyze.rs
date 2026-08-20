//! `luau-analyze` discovery and parse (MASTER 7.3 / T3.4).
//!
//! The editor never loads Luau (I3). Type diagnostics come from the official
//! `luau-analyze` binary when present. v1 tries a short sync spawn (2s) and
//! returns immediately if the binary is missing.
//!
//! Resolve order:
//! 1. `GS_LUAU_ANALYZE` — exclusive absolute path (broken/missing → off)
//! 2. `tools/luau-analyze[.exe]` under the open project, then `runtime_root`
//! 3. `luau-analyze` on `PATH`
//!
//! Expected version when present: Luau **0.709** (`docs/VERSIONS.md`). A
//! mismatch does not block work. Findings are warnings and never block
//! run/save.

use std::env;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Output, Stdio};
use std::thread;
use std::time::{Duration, Instant};

use serde_json::{json, Value};

pub const ENV_ANALYZE: &str = "GS_LUAU_ANALYZE";
pub const ANALYZE_TIMEOUT: Duration = Duration::from_secs(2);
pub const TYPE_CHECK_OFF_MSG: &str = "type check off";
pub const GS_DEFS: &str = include_str!("../luau/gs.d.luau");

const TOOL_NAMES: &[&str] = &["luau-analyze.exe", "luau-analyze"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum TypeCheck {
    Off,
    Ok,
    Error,
}

impl TypeCheck {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Self::Off => "off",
            Self::Ok => "ok",
            Self::Error => "error",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct Diagnostic {
    pub file: String,
    pub line: u32,
    pub column: Option<u32>,
    pub message: String,
    /// Analyze findings are always warnings (MASTER 7.3); `"error"` reserved.
    pub kind: &'static str,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(crate) struct AnalyzeReport {
    pub type_check: TypeCheck,
    pub diagnostics: Vec<Diagnostic>,
}

impl AnalyzeReport {
    fn off(file: &str) -> Self {
        Self {
            type_check: TypeCheck::Off,
            diagnostics: vec![off_diagnostic(file)],
        }
    }

    fn failed(file: &str) -> Self {
        Self {
            type_check: TypeCheck::Error,
            diagnostics: vec![off_diagnostic(file)],
        }
    }
}

pub(crate) fn off_diagnostic(file: &str) -> Diagnostic {
    Diagnostic {
        file: file.to_owned(),
        line: 1,
        column: None,
        message: TYPE_CHECK_OFF_MSG.to_owned(),
        kind: "warning",
    }
}

pub(crate) fn diagnostic_json(diag: &Diagnostic) -> Value {
    let mut row = json!({
        "file": diag.file,
        "line": diag.line,
        "message": diag.message,
        "kind": diag.kind,
    });
    if let Some(column) = diag.column {
        row["column"] = json!(column);
    }
    row
}

pub(crate) fn report_json(report: &AnalyzeReport, path: Option<&str>) -> Value {
    let diagnostics: Vec<Value> = report.diagnostics.iter().map(diagnostic_json).collect();
    let mut out = json!({
        "diagnostics": diagnostics,
        "type_check": report.type_check.as_str(),
    });
    if let Some(path) = path {
        out["path"] = json!(path);
    }
    if report.type_check != TypeCheck::Ok {
        out["banner"] = json!(TYPE_CHECK_OFF_MSG);
    }
    out
}

/// Locate `luau-analyze`. Env, if set, is exclusive (no PATH fallback).
pub(crate) fn resolve_analyze_binary(
    project: Option<&Path>,
    runtime_root: &Path,
) -> Option<PathBuf> {
    if let Some(raw) = env::var_os(ENV_ANALYZE) {
        let path = PathBuf::from(raw);
        if path.is_absolute() && path.is_file() {
            return Some(path);
        }
        return None;
    }
    if let Some(project) = project {
        if let Some(found) = tools_binary(project) {
            return Some(found);
        }
    }
    if let Some(found) = tools_binary(runtime_root) {
        return Some(found);
    }
    find_on_path("luau-analyze")
}

fn tools_binary(root: &Path) -> Option<PathBuf> {
    let dir = root.join("tools");
    for name in TOOL_NAMES {
        let candidate = dir.join(name);
        if candidate.is_file() {
            return Some(candidate);
        }
    }
    None
}

fn find_on_path(name: &str) -> Option<PathBuf> {
    let path_var = env::var_os("PATH")?;
    for dir in env::split_paths(&path_var) {
        let plain = dir.join(name);
        if plain.is_file() {
            return Some(plain);
        }
        let exe = dir.join(format!("{name}.exe"));
        if exe.is_file() {
            return Some(exe);
        }
    }
    None
}

/// Write embedded `gs.d.luau` under `{project}/.gs/cache/` (I6 tmp+rename, I7).
pub(crate) fn write_gs_defs(project: &Path) -> Option<PathBuf> {
    let dir = project.join(".gs").join("cache");
    std::fs::create_dir_all(&dir).ok()?;
    let dest = dir.join("gs.d.luau");
    let tmp = dir.join("gs.d.luau.tmp");
    std::fs::write(&tmp, GS_DEFS).ok()?;
    if dest.exists() {
        let _ = std::fs::remove_file(&dest);
    }
    std::fs::rename(&tmp, &dest).ok()?;
    Some(dest)
}

pub(crate) fn run_luau_analyze(
    bin: &Path,
    files: &[PathBuf],
    defs: Option<&Path>,
    timeout: Duration,
) -> AnalyzeReport {
    if !bin.is_file() {
        return AnalyzeReport::off("");
    }
    let mut cmd = Command::new(bin);
    cmd.stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(defs) = defs {
        cmd.arg("--defs").arg(defs);
    }
    for file in files {
        cmd.arg(file);
    }
    let child = match cmd.spawn() {
        Ok(child) => child,
        Err(_) => return AnalyzeReport::off(""),
    };
    let output = match wait_child_timeout(child, timeout) {
        Ok(output) => output,
        Err(WaitErr::Timeout) => return AnalyzeReport::failed(""),
        Err(WaitErr::Io) => return AnalyzeReport::off(""),
    };
    let mut text = String::from_utf8_lossy(&output.stdout).into_owned();
    if !output.stderr.is_empty() {
        if !text.is_empty() && !text.ends_with('\n') {
            text.push('\n');
        }
        text.push_str(&String::from_utf8_lossy(&output.stderr));
    }
    let diagnostics = parse_analyze_output(&text);
    if !diagnostics.is_empty() {
        return AnalyzeReport {
            type_check: TypeCheck::Ok,
            diagnostics,
        };
    }
    if output.status.success() {
        AnalyzeReport {
            type_check: TypeCheck::Ok,
            diagnostics: Vec::new(),
        }
    } else {
        AnalyzeReport::failed("")
    }
}

enum WaitErr {
    Io,
    Timeout,
}

fn wait_child_timeout(
    mut child: std::process::Child,
    timeout: Duration,
) -> Result<Output, WaitErr> {
    let mut stdout = child.stdout.take().ok_or(WaitErr::Io)?;
    let mut stderr = child.stderr.take().ok_or(WaitErr::Io)?;
    let out_t = thread::spawn(move || {
        let mut buf = Vec::new();
        let _ = stdout.read_to_end(&mut buf);
        buf
    });
    let err_t = thread::spawn(move || {
        let mut buf = Vec::new();
        let _ = stderr.read_to_end(&mut buf);
        buf
    });
    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(status)) => {
                let stdout = out_t.join().unwrap_or_default();
                let stderr = err_t.join().unwrap_or_default();
                return Ok(Output {
                    status,
                    stdout,
                    stderr,
                });
            }
            Ok(None) if start.elapsed() >= timeout => {
                let _ = child.kill();
                let _ = child.wait();
                let _ = out_t.join();
                let _ = err_t.join();
                return Err(WaitErr::Timeout);
            }
            Ok(None) => thread::sleep(Duration::from_millis(20)),
            Err(_) => {
                let _ = child.kill();
                let _ = out_t.join();
                let _ = err_t.join();
                return Err(WaitErr::Io);
            }
        }
    }
}

pub(crate) fn parse_analyze_output(text: &str) -> Vec<Diagnostic> {
    text.lines().filter_map(parse_analyze_line).collect()
}

fn parse_analyze_line(line: &str) -> Option<Diagnostic> {
    let line = line.trim();
    if line.is_empty() {
        return None;
    }
    parse_default_line(line).or_else(|| parse_gnu_line(line))
}

/// `file(line,col): TypeError: message`
fn parse_default_line(line: &str) -> Option<Diagnostic> {
    let close = line.find("): ")?;
    let open = line[..close].rfind('(')?;
    let loc = &line[open + 1..close];
    let mut parts = loc.split(',');
    let line_no: u32 = parts.next()?.trim().parse().ok()?;
    let column: u32 = parts.next()?.trim().parse().ok()?;
    if parts.next().is_some() {
        return None;
    }
    let file = line[..open].trim();
    if file.is_empty() {
        return None;
    }
    let message = line[close + 3..].trim();
    if message.is_empty() {
        return None;
    }
    Some(analyze_finding(file, line_no, Some(column), message))
}

/// `file:line:col: error: message`
fn parse_gnu_line(line: &str) -> Option<Diagnostic> {
    let mut parts = line.splitn(4, ':');
    let file = parts.next()?.trim();
    let line_no: u32 = parts.next()?.trim().parse().ok()?;
    let column: u32 = parts.next()?.trim().parse().ok()?;
    let rest = parts.next()?.trim();
    if file.is_empty() || rest.is_empty() {
        return None;
    }
    let message = rest
        .strip_prefix("error:")
        .or_else(|| rest.strip_prefix("warning:"))
        .or_else(|| rest.strip_prefix("Error:"))
        .or_else(|| rest.strip_prefix("Warning:"))
        .unwrap_or(rest)
        .trim();
    if message.is_empty() {
        return None;
    }
    Some(analyze_finding(file, line_no, Some(column), message))
}

fn analyze_finding(file: &str, line: u32, column: Option<u32>, message: &str) -> Diagnostic {
    Diagnostic {
        file: file.replace('\\', "/"),
        line,
        column,
        message: message.to_owned(),
        kind: "warning",
    }
}

pub(crate) fn relativize_file(project: &Path, file: &str) -> String {
    let path = Path::new(file);
    if let Ok(rel) = path.strip_prefix(project) {
        return rel.to_string_lossy().replace('\\', "/");
    }
    file.replace('\\', "/")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;

    #[test]
    fn parse_default_and_gnu_lines() {
        let default = parse_analyze_line(
            "scripts/foo.luau(3,5): TypeError: Type 'number' could not be converted into 'string'",
        )
        .expect("default");
        assert_eq!(default.file, "scripts/foo.luau");
        assert_eq!(default.line, 3);
        assert_eq!(default.column, Some(5));
        assert!(default.message.contains("TypeError"));
        assert_eq!(default.kind, "warning");

        let gnu =
            parse_analyze_line("scripts/bar.luau:8:1: error: Unknown global 'gs'").expect("gnu");
        assert_eq!(gnu.file, "scripts/bar.luau");
        assert_eq!(gnu.line, 8);
        assert_eq!(gnu.column, Some(1));
        assert!(gnu.message.contains("Unknown global"));
        assert_eq!(gnu.kind, "warning");
    }

    #[test]
    fn missing_binary_is_type_check_off() {
        let report = run_luau_analyze(
            Path::new("/gs-missing-luau-analyze/luau-analyze"),
            &[],
            None,
            Duration::from_secs(1),
        );
        assert_eq!(report.type_check, TypeCheck::Off);
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.message.contains(TYPE_CHECK_OFF_MSG)));
    }

    #[test]
    fn exit_one_binary_is_off_or_error() {
        let dir = tempfile::tempdir().expect("tempdir");
        let fake = write_exit_one(dir.path());
        let dummy = dir.path().join("dummy.luau");
        fs::write(&dummy, "--!strict\nreturn {}\n").expect("dummy");
        let report = run_luau_analyze(&fake, &[dummy], None, Duration::from_secs(2));
        assert!(
            matches!(report.type_check, TypeCheck::Off | TypeCheck::Error),
            "expected off or error, got {:?}",
            report.type_check
        );
        assert!(report
            .diagnostics
            .iter()
            .any(|d| d.message.contains(TYPE_CHECK_OFF_MSG)));
    }

    fn write_exit_one(dir: &Path) -> PathBuf {
        #[cfg(windows)]
        {
            let path = dir.join("fake-analyze.cmd");
            let mut file = fs::File::create(&path).expect("cmd");
            writeln!(file, "@echo off").expect("write");
            writeln!(file, "exit /b 1").expect("write");
            path
        }
        #[cfg(not(windows))]
        {
            use std::os::unix::fs::PermissionsExt;
            let path = dir.join("fake-analyze");
            let mut file = fs::File::create(&path).expect("sh");
            writeln!(file, "#!/bin/sh").expect("write");
            writeln!(file, "exit 1").expect("write");
            let mut perms = fs::metadata(&path).expect("meta").permissions();
            perms.set_mode(0o755);
            fs::set_permissions(&path, perms).expect("chmod");
            path
        }
    }
}
