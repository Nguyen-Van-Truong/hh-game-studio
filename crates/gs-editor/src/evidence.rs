//! Evidence bundle writer (MASTER 10.3). Directory is tmp+rename (I6).

use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

use gs_protocol::RpcError;
use serde_json::{json, Value};
use ulid::Ulid;

use crate::error::app_err;
use crate::gtest::GTest;

#[derive(Clone, Debug)]
pub struct EvidenceDraft {
    pub hashes: Value,
    pub world_dump: Value,
    pub doc_hash: String,
    pub events: Value,
    pub logs: Value,
    pub screenshot: Value,
    pub screenshot_png: Option<Vec<u8>>,
    pub diff_png: Option<Vec<u8>>,
    pub perf: Value,
    pub engine: Value,
    pub passed: bool,
    pub failed_assert: Option<String>,
    pub evidence_ok: bool,
}

impl Default for EvidenceDraft {
    fn default() -> Self {
        Self {
            hashes: json!({}),
            world_dump: json!({}),
            doc_hash: String::new(),
            events: json!({ "events": [] }),
            logs: json!({ "lines": [] }),
            screenshot: json!({ "app_code": "no_gpu" }),
            screenshot_png: None,
            diff_png: None,
            perf: json!({}),
            engine: json!({}),
            passed: false,
            failed_assert: None,
            evidence_ok: true,
        }
    }
}

impl EvidenceDraft {
    pub fn result_json(&self) -> Value {
        json!({
            "passed": self.passed,
            "failed_assert": self.failed_assert,
            "evidence_ok": self.evidence_ok,
        })
    }
}

/// Write `{root}/.gs/runtime/evidence/<slug>-<ts>/` via a sibling tmp dir (I6).
pub fn write_bundle(
    root: &Path,
    gtest: &GTest,
    draft: &EvidenceDraft,
) -> Result<PathBuf, RpcError> {
    let parent = root.join(".gs").join("runtime").join("evidence");
    fs::create_dir_all(&parent).map_err(|err| app_err("E_IO", err.to_string()))?;
    let slug = slug_name(&gtest.name);
    let stamp = utc_stamp();
    let dest_name = unique_dir_name(&parent, &format!("{slug}-{stamp}"));
    let tmp = parent.join(format!(".tmp-{}", Ulid::new()));
    fs::create_dir_all(&tmp).map_err(|err| app_err("E_IO", err.to_string()))?;

    let write_json = |name: &str, value: &Value| -> Result<(), RpcError> {
        write_json_file(&tmp.join(name), value)
    };
    write_json("gtest.json", &gtest.to_value())?;
    write_json("hashes.json", &draft.hashes)?;
    let mut dump = draft.world_dump.clone();
    if let Some(obj) = dump.as_object_mut() {
        obj.insert("doc_hash".into(), json!(draft.doc_hash));
    }
    write_json("world_dump.json", &dump)?;
    write_events(&tmp.join("events.jsonl"), &draft.events)?;
    write_json("logs.json", &draft.logs)?;
    write_json("screenshot.json", &draft.screenshot)?;
    if let Some(png) = &draft.screenshot_png {
        write_bytes(&tmp.join("screenshot.png"), png)?;
    }
    if let Some(png) = &draft.diff_png {
        write_bytes(&tmp.join("screenshot_diff.png"), png)?;
    }
    write_json("perf.json", &draft.perf)?;
    write_json("engine.json", &draft.engine)?;
    write_json("result.json", &draft.result_json())?;

    let dest = parent.join(&dest_name);
    fs::rename(&tmp, &dest).map_err(|err| {
        let _ = fs::remove_dir_all(&tmp);
        app_err("E_IO", err.to_string())
    })?;
    Ok(dest)
}

fn write_events(path: &Path, events: &Value) -> Result<(), RpcError> {
    if let Some(text) = events.as_str() {
        return write_bytes(path, text.as_bytes());
    }
    if let Some(list) = events.get("events").and_then(Value::as_array) {
        let mut body = String::new();
        for event in list {
            body.push_str(
                &serde_json::to_string(event).map_err(|err| app_err("E_IO", err.to_string()))?,
            );
            body.push('\n');
        }
        return write_bytes(path, body.as_bytes());
    }
    write_json_file(path, events)
}

fn write_json_file(path: &Path, value: &Value) -> Result<(), RpcError> {
    let bytes = serde_json::to_vec_pretty(value).map_err(|err| app_err("E_IO", err.to_string()))?;
    write_bytes(path, &bytes)
}

fn write_bytes(path: &Path, bytes: &[u8]) -> Result<(), RpcError> {
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

fn slug_name(name: &str) -> String {
    let mut out = String::new();
    for ch in name.chars() {
        if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' {
            out.push(ch);
        } else if ch == ' ' {
            out.push('_');
        }
        if out.len() >= 64 {
            break;
        }
    }
    if out.is_empty() {
        "test".into()
    } else {
        out
    }
}

fn utc_stamp() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{secs}")
}

fn unique_dir_name(parent: &Path, base: &str) -> String {
    if !parent.join(base).exists() {
        return base.to_owned();
    }
    format!("{base}-{}", Ulid::new())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::gtest::GTest;

    #[test]
    fn write_bundle_renames_into_place() {
        let dir = tempfile::TempDir::new().expect("temp");
        let gtest = GTest::from_value(json!({
            "name": "coin_picked",
            "asserts": [{"event": {"name": "CoinPicked"}}]
        }))
        .expect("gtest");
        let draft = EvidenceDraft {
            passed: true,
            world_dump: json!({ "frame": 1, "entities": [] }),
            events: json!({ "events": [{"name": "CoinPicked"}] }),
            engine: json!({ "engine_build": "0.1.0" }),
            ..EvidenceDraft::default()
        };
        let dest = write_bundle(dir.path(), &gtest, &draft).expect("write");
        assert!(dest.join("result.json").is_file());
        assert!(dest.join("world_dump.json").is_file());
        assert!(dest.join("events.jsonl").is_file());
        let result: Value =
            serde_json::from_str(&fs::read_to_string(dest.join("result.json")).unwrap()).unwrap();
        assert_eq!(result["passed"], json!(true));
        assert!(!dir
            .path()
            .join(".gs/runtime/evidence")
            .read_dir()
            .unwrap()
            .any(|e| {
                e.ok()
                    .is_some_and(|e| e.file_name().to_string_lossy().starts_with(".tmp-"))
            }));
    }
}
