//! `gs doctor` imagegen preflight (MASTER 8.5 B+C). Never prints secrets (I8).
//!
//! Exit 0 only when at least one provider is usable: Python on PATH **and**
//! (ComfyUI TCP reachable **or** remote C key present). Missing Python /
//! ComfyUI / C key with no usable provider → exit ≠ 0.
//!
//! `GS_IMAGEGEN_STUB` is a worker test switch — doctor never treats a stub
//! PNG as a real provider.

use std::env;
use std::fs;
use std::net::{TcpStream, ToSocketAddrs};
use std::path::{Path, PathBuf};
use std::time::Duration;

const DEFAULT_COMFY: &str = "http://127.0.0.1:8188";
const SECRET_FIELD_NAMES: &[&str] = &[
    "api_key",
    "apikey",
    "key",
    "token",
    "secret",
    "authorization",
];

#[derive(Clone, Debug)]
pub struct DoctorEnv {
    pub force: Option<String>,
    pub comfy_url: String,
    pub imagegen_config: PathBuf,
}

impl DoctorEnv {
    pub fn from_os() -> Self {
        Self {
            force: env::var("GS_DOCTOR_FORCE").ok().filter(|s| !s.is_empty()),
            comfy_url: env::var("GS_COMFY_URL").unwrap_or_else(|_| DEFAULT_COMFY.into()),
            imagegen_config: imagegen_config_path(),
        }
    }
}

#[derive(Clone, Debug)]
pub struct BinaryCheck {
    pub present: bool,
    pub detail: String,
}

#[derive(Clone, Debug)]
pub struct ComfyCheck {
    pub reachable: bool,
    pub detail: String,
}

#[derive(Clone, Debug)]
pub struct RemoteCCheck {
    pub config_present: bool,
    pub key_present: bool,
    pub path_display: String,
}

#[derive(Clone, Debug)]
pub struct DoctorReport {
    pub rustc: BinaryCheck,
    pub cargo: BinaryCheck,
    pub python: BinaryCheck,
    pub comfyui: ComfyCheck,
    pub remote_c: RemoteCCheck,
    pub usable: bool,
    pub force: Option<String>,
    pub reasons: Vec<String>,
}

impl DoctorReport {
    pub fn exit_ok(&self) -> bool {
        self.usable
    }
}

impl std::fmt::Display for DoctorReport {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        writeln!(f, "gs doctor — imagegen preflight (MASTER 8.5 B+C)")?;
        writeln!(
            f,
            "  rustc:    {} (optional) {}",
            present_word(self.rustc.present),
            self.rustc.detail
        )?;
        writeln!(
            f,
            "  cargo:    {} (optional) {}",
            present_word(self.cargo.present),
            self.cargo.detail
        )?;
        writeln!(
            f,
            "  python:   {} {}",
            present_word(self.python.present),
            self.python.detail
        )?;
        writeln!(
            f,
            "  comfyui:  {} {}",
            present_word(self.comfyui.reachable),
            self.comfyui.detail
        )?;
        let c_key = if !self.remote_c.config_present {
            "config absent"
        } else if self.remote_c.key_present {
            "key present"
        } else {
            "key absent"
        };
        writeln!(
            f,
            "  remote_c: {} {} ({})",
            present_word(self.remote_c.config_present && self.remote_c.key_present),
            c_key,
            self.remote_c.path_display
        )?;
        if let Some(force) = &self.force {
            writeln!(f, "  force:    GS_DOCTOR_FORCE={force}")?;
        }
        if self.usable {
            writeln!(f, "  result:   at least one provider usable")?;
        } else {
            writeln!(
                f,
                "  result:   no usable provider — {}",
                self.reasons.join("; ")
            )?;
        }
        Ok(())
    }
}

pub fn run_doctor() -> DoctorReport {
    run_doctor_with(&DoctorEnv::from_os())
}

pub fn run_doctor_with(env: &DoctorEnv) -> DoctorReport {
    let rustc = check_binary(&["rustc"]);
    let cargo = check_binary(&["cargo"]);
    let python = check_binary(&["python3", "python"]);
    let comfyui = check_comfy(&env.comfy_url);
    let remote_c = check_remote_c(&env.imagegen_config);

    let mut reasons = Vec::new();
    if !python.present {
        reasons.push("python missing on PATH".into());
    }
    if !comfyui.reachable {
        reasons.push(format!("ComfyUI not reachable ({})", env.comfy_url));
    }
    if !remote_c.key_present {
        reasons.push("remote C key absent".into());
    }

    let b = python.present && comfyui.reachable;
    let c = python.present && remote_c.key_present;
    let mut usable = b || c;
    let force = env.force.as_deref().map(str::to_ascii_lowercase);
    match force.as_deref() {
        Some("ok") => {
            usable = true;
            reasons.clear();
        }
        Some("missing") => {
            usable = false;
            if reasons.is_empty() {
                reasons.push("GS_DOCTOR_FORCE=missing".into());
            }
        }
        _ => {}
    }

    DoctorReport {
        rustc,
        cargo,
        python,
        comfyui,
        remote_c,
        usable,
        force: env.force.clone(),
        reasons,
    }
}

pub fn imagegen_config_path() -> PathBuf {
    if let Ok(p) = env::var("GS_IMAGEGEN_CONFIG") {
        if !p.is_empty() {
            return PathBuf::from(p);
        }
    }
    #[cfg(windows)]
    {
        if let Ok(appdata) = env::var("APPDATA") {
            return PathBuf::from(appdata)
                .join("hh-game-studio")
                .join("imagegen.json");
        }
    }
    let home = env::var("HOME")
        .or_else(|_| env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".into());
    PathBuf::from(home)
        .join(".config")
        .join("hh-game-studio")
        .join("imagegen.json")
}

fn present_word(ok: bool) -> &'static str {
    if ok {
        "present"
    } else {
        "absent"
    }
}

fn check_binary(names: &[&str]) -> BinaryCheck {
    match find_on_path(names) {
        Some(path) => {
            let detail = version_label(&path).unwrap_or_else(|| path.display().to_string());
            BinaryCheck {
                present: true,
                detail,
            }
        }
        None => BinaryCheck {
            present: false,
            detail: "not on PATH".into(),
        },
    }
}

fn find_on_path(names: &[&str]) -> Option<PathBuf> {
    let path = env::var_os("PATH")?;
    for dir in env::split_paths(&path) {
        for name in names {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
            #[cfg(windows)]
            {
                let exe = dir.join(format!("{name}.exe"));
                if exe.is_file() {
                    return Some(exe);
                }
            }
        }
    }
    None
}

fn version_label(exe: &Path) -> Option<String> {
    let out = std::process::Command::new(exe)
        .arg("--version")
        .output()
        .ok()?;
    let text = String::from_utf8_lossy(&out.stdout);
    let line = text.lines().next()?.trim();
    if line.is_empty() {
        None
    } else {
        Some(line.to_string())
    }
}

fn check_comfy(url: &str) -> ComfyCheck {
    match comfy_tcp(url) {
        Ok(()) => ComfyCheck {
            reachable: true,
            detail: format!("tcp {url}"),
        },
        Err(err) => ComfyCheck {
            reachable: false,
            detail: format!("tcp {url} — {err}"),
        },
    }
}

fn comfy_tcp(url: &str) -> Result<(), String> {
    let rest = url
        .trim()
        .strip_prefix("https://")
        .or_else(|| url.trim().strip_prefix("http://"))
        .unwrap_or(url.trim());
    let hostport = rest.split('/').next().unwrap_or(rest);
    let (host, port) = match hostport.rsplit_once(':') {
        Some((h, p)) => (
            h,
            p.parse::<u16>().map_err(|_| format!("bad port in {url}"))?,
        ),
        None => (hostport, 8188),
    };
    let addr = (host, port)
        .to_socket_addrs()
        .map_err(|e| e.to_string())?
        .next()
        .ok_or_else(|| format!("cannot resolve {host}:{port}"))?;
    TcpStream::connect_timeout(&addr, Duration::from_millis(400))
        .map(|_| ())
        .map_err(|e| e.to_string())
}

fn check_remote_c(path: &Path) -> RemoteCCheck {
    let path_display = path.display().to_string();
    if !path.is_file() {
        return RemoteCCheck {
            config_present: false,
            key_present: false,
            path_display,
        };
    }
    let key_present = match fs::read_to_string(path) {
        Ok(text) => config_has_key(&text),
        Err(_) => false,
    };
    RemoteCCheck {
        config_present: true,
        key_present,
        path_display,
    }
}

/// Detect a key without copying it into the report (I8).
fn config_has_key(text: &str) -> bool {
    let Ok(value) = serde_json::from_str::<serde_json::Value>(text) else {
        return false;
    };
    let Some(obj) = value.as_object() else {
        return false;
    };
    obj.iter().any(|(k, v)| {
        SECRET_FIELD_NAMES.iter().any(|n| k.eq_ignore_ascii_case(n))
            && v.as_str().is_some_and(|s| !s.is_empty())
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn force_ok_is_usable() {
        let report = run_doctor_with(&DoctorEnv {
            force: Some("ok".into()),
            comfy_url: "http://127.0.0.1:1".into(),
            imagegen_config: PathBuf::from("no-such-imagegen.json"),
        });
        assert!(report.usable);
        assert!(report.exit_ok());
        let text = report.to_string();
        assert!(text.contains("GS_DOCTOR_FORCE=ok"));
    }

    #[test]
    fn force_missing_is_not_usable() {
        let report = run_doctor_with(&DoctorEnv {
            force: Some("missing".into()),
            comfy_url: "http://127.0.0.1:1".into(),
            imagegen_config: PathBuf::from("no-such-imagegen.json"),
        });
        assert!(!report.usable);
        assert!(!report.exit_ok());
        let text = report.to_string();
        assert!(text.contains("no usable provider"));
    }

    #[test]
    fn remote_c_never_prints_api_key() {
        let dir = tempfile::tempdir().expect("tempdir");
        let cfg = dir.path().join("imagegen.json");
        let mut f = fs::File::create(&cfg).expect("create");
        writeln!(f, r#"{{"api_key":"sk-SUPER-SECRET-DO-NOT-PRINT"}}"#).expect("write");
        drop(f);
        let report = run_doctor_with(&DoctorEnv {
            force: Some("missing".into()),
            comfy_url: "http://127.0.0.1:1".into(),
            imagegen_config: cfg,
        });
        let text = report.to_string();
        assert!(!text.contains("sk-SUPER-SECRET-DO-NOT-PRINT"));
        assert!(!text.contains("SUPER-SECRET"));
        assert!(report.remote_c.config_present);
        assert!(report.remote_c.key_present);
        assert!(text.contains("key present"));
    }
}
