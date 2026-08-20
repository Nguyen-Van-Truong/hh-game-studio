//! Play-side `judge.*` helpers (MASTER 4.2 / 6.3 / T5.2 / GS-EC-35).
//!
//! Truth is the event ring and the in-memory world dump — never a live stream.

use std::fs;
use std::path::{Path, PathBuf};

use gs_protocol::{ErrorData, RpcError, APP, INVALID_PARAMS};
use serde_json::{json, Value};

use crate::events::{EventTrace, TraceEvent};

fn invalid_params(message: impl Into<String>) -> RpcError {
    RpcError::with_data(INVALID_PARAMS, message, ErrorData::new("E_VALIDATION"))
}

pub const APP_CODE_EVENT_MISS: &str = "GS-EC-35";
pub const APP_CODE_ASSERT: &str = "E_ASSERT";
pub const DEFAULT_EPSILON: f64 = 1e-5;

pub fn event_miss(message: impl Into<String>) -> RpcError {
    RpcError::with_data(APP, message, ErrorData::new(APP_CODE_EVENT_MISS))
}

pub fn assert_err(message: impl Into<String>) -> RpcError {
    RpcError::with_data(APP, message, ErrorData::new(APP_CODE_ASSERT))
}

pub fn required_name(params: &Value) -> Result<&str, RpcError> {
    match params.get("name").and_then(Value::as_str) {
        Some(name) if !name.is_empty() => Ok(name),
        _ => Err(invalid_params("name is required")),
    }
}

/// `timeout_frames` (user) or `max_frames` (MASTER 4.2). Capped at `cap`.
pub fn timeout_frames(params: &Value, cap: u32) -> Result<u32, RpcError> {
    match params
        .get("timeout_frames")
        .or_else(|| params.get("max_frames"))
    {
        None | Some(Value::Null) => Ok(cap),
        Some(v) => v
            .as_u64()
            .and_then(|n| u32::try_from(n).ok())
            .ok_or_else(|| invalid_params("timeout_frames must be a u32"))
            .map(|n| n.min(cap)),
    }
}

/// Register-time `after_seq`. Omitted → current ring tail so old events cannot pass.
pub fn run_until_after_seq(params: &Value, last_seq: u64) -> u64 {
    params
        .get("after_seq")
        .and_then(Value::as_u64)
        .unwrap_or(last_seq)
}

pub fn required_after_seq(params: &Value) -> Result<u64, RpcError> {
    params
        .get("after_seq")
        .and_then(Value::as_u64)
        .ok_or_else(|| invalid_params("after_seq is required"))
}

pub fn epsilon(params: &Value) -> Result<f64, RpcError> {
    match params.get("epsilon") {
        None | Some(Value::Null) => Ok(DEFAULT_EPSILON),
        Some(v) => {
            let n = v
                .as_f64()
                .ok_or_else(|| invalid_params("epsilon must be a number"))?;
            if n < 0.0 || !n.is_finite() {
                return Err(invalid_params("epsilon must be a finite number >= 0"));
            }
            Ok(n)
        }
    }
}

pub fn find_event(
    trace: &EventTrace,
    after_seq: u64,
    name: &str,
    matcher: Option<&Value>,
) -> Option<TraceEvent> {
    trace
        .query(after_seq, Some(name), crate::events::OBS_EVENTS_MAX_LIMIT)
        .into_iter()
        .find(|event| matcher.is_none_or(|m| data_matches(&event.data, m)))
}

pub fn event_hit(play_id: &str, event: &TraceEvent) -> Value {
    json!({
        "ok": true,
        "play_id": play_id,
        "name": event.name,
        "seq": event.seq,
        "frame": event.frame,
        "event": event,
    })
}

fn data_matches(data: &Value, matcher: &Value) -> bool {
    match matcher {
        Value::Object(want) => {
            let Some(got) = data.as_object() else {
                return false;
            };
            want.iter()
                .all(|(key, value)| got.get(key).is_some_and(|have| have == value))
        }
        other => data == other,
    }
}

pub fn load_expected(params: &Value, play_dir: Option<&Path>) -> Result<Value, RpcError> {
    if let Some(expected) = params.get("expected") {
        if !expected.is_null() {
            return Ok(expected.clone());
        }
    }
    let rel = params
        .get("path")
        .and_then(Value::as_str)
        .ok_or_else(|| invalid_params("judge.assert_world requires path or expected"))?;
    let path = resolve_expected_path(rel, play_dir)?;
    let text = fs::read_to_string(&path).map_err(|err| {
        RpcError::with_data(
            APP,
            format!("read {}: {err}", path.display()),
            ErrorData::new("E_IO"),
        )
    })?;
    serde_json::from_str(&text).map_err(|err| invalid_params(format!("expected JSON: {err}")))
}

fn resolve_expected_path(rel: &str, play_dir: Option<&Path>) -> Result<PathBuf, RpcError> {
    if rel.contains('\0') {
        return Err(invalid_params("path is invalid"));
    }
    let raw = Path::new(rel);
    if raw.is_absolute() {
        return Ok(raw.to_path_buf());
    }
    if rel.split(['/', '\\']).any(|part| part == "..") {
        return Err(invalid_params("path escapes play directory"));
    }
    match play_dir {
        Some(dir) => Ok(dir.join(rel)),
        None => Ok(raw.to_path_buf()),
    }
}

/// Compare two dumps. Numbers may differ by `epsilon`; everything else is exact.
pub fn values_within_epsilon(actual: &Value, expected: &Value, epsilon: f64) -> Result<(), String> {
    compare_at("$", actual, expected, epsilon)
}

fn compare_at(path: &str, actual: &Value, expected: &Value, epsilon: f64) -> Result<(), String> {
    match (actual, expected) {
        (Value::Number(a), Value::Number(b)) => {
            let (Some(af), Some(bf)) = (a.as_f64(), b.as_f64()) else {
                return Err(format!("{path}: non-finite number"));
            };
            if (af - bf).abs() <= epsilon {
                Ok(())
            } else {
                Err(format!("{path}: {af} vs {bf} exceeds epsilon {epsilon}"))
            }
        }
        (Value::Array(a), Value::Array(b)) => {
            if a.len() != b.len() {
                return Err(format!("{path}: array length {} vs {}", a.len(), b.len()));
            }
            for (idx, (av, ev)) in a.iter().zip(b.iter()).enumerate() {
                compare_at(&format!("{path}[{idx}]"), av, ev, epsilon)?;
            }
            Ok(())
        }
        (Value::Object(a), Value::Object(b)) => {
            for key in b.keys() {
                if !a.contains_key(key) {
                    return Err(format!("{path}.{key}: missing in actual"));
                }
            }
            for key in a.keys() {
                if !b.contains_key(key) {
                    return Err(format!("{path}.{key}: extra in actual"));
                }
            }
            for (key, ev) in b {
                compare_at(&format!("{path}.{key}"), &a[key], ev, epsilon)?;
            }
            Ok(())
        }
        (Value::Null, Value::Null) => Ok(()),
        (Value::Bool(a), Value::Bool(b)) if a == b => Ok(()),
        (Value::String(a), Value::String(b)) if a == b => Ok(()),
        _ => Err(format!(
            "{path}: mismatch actual={actual} expected={expected}"
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn epsilon_1e_minus_5_passes_and_1_fails() {
        let actual = json!({ "x": 0.0, "nested": { "y": 2.0 } });
        let close = json!({ "x": 1e-5, "nested": { "y": 2.0 } });
        let far = json!({ "x": 1.0, "nested": { "y": 2.0 } });
        assert!(
            values_within_epsilon(&actual, &close, 1e-5).is_ok(),
            "1e-5 must pass"
        );
        let err = values_within_epsilon(&actual, &far, 1e-5).expect_err("1.0 must fail");
        assert!(err.contains("epsilon"), "{err}");
    }
}
