//! Snapshot `input-map.json` + play-scoped injects (MASTER 6.4 / 4.2).
//!
//! The simulate thread owns the current [`InputFrame`]: known map names start
//! at `0`, and `input.inject` overlays values for matching `frame_offset`s.

use std::collections::{BTreeMap, BTreeSet};
use std::path::Path;

use gs_runtime_core::InputFrame;
use serde_json::Value;

use crate::error::Error;

#[derive(Clone, Debug, PartialEq)]
pub(crate) struct PendingInject {
    pub remaining: u32,
    pub action: String,
    pub value: f32,
}

/// Load whatever is in the snapshot `input-map.json`. Missing file → empty object.
pub(crate) fn load_input_map_value(play_dir: &Path) -> Result<Value, Error> {
    let path = play_dir.join("input-map.json");
    if !path.is_file() {
        return Ok(serde_json::json!({ "actions": [] }));
    }
    let bytes = std::fs::read(&path).map_err(|e| Error::io(&path, e))?;
    serde_json::from_slice(&bytes).map_err(|e| Error::json(&path, e))
}

/// Load whatever is in the snapshot `input-map.json`. Missing file → empty frame.
pub(crate) fn load_input_map(play_dir: &Path) -> Result<InputFrame, Error> {
    Ok(input_frame_from_map(&load_input_map_value(play_dir)?))
}

/// Canonical input-map key token (`A`, `Left`, `Space`, …).
pub(crate) fn normalize_key_name(raw: &str) -> String {
    match raw.trim() {
        "Left" | "ArrowLeft" => "Left".into(),
        "Right" | "ArrowRight" => "Right".into(),
        "Up" | "ArrowUp" => "Up".into(),
        "Down" | "ArrowDown" => "Down".into(),
        "Space" | "Spacebar" => "Space".into(),
        "," | "Comma" => "Comma".into(),
        "." | "Period" => "Period".into(),
        other if other.len() == 1 => other.to_ascii_uppercase(),
        other => other.to_string(),
    }
}

/// Apply currently held keyboard names onto `frame` using MASTER 6.4 `keys`.
pub(crate) fn apply_held_keys(map: &Value, held: &BTreeSet<String>, frame: &mut InputFrame) {
    let Some(arr) = map.get("actions").and_then(Value::as_array) else {
        return;
    };
    let held_norm: BTreeSet<String> = held.iter().map(|k| normalize_key_name(k)).collect();
    for item in arr {
        let Some(name) = item.get("name").and_then(Value::as_str) else {
            continue;
        };
        if name.is_empty() {
            continue;
        }
        let typ = item.get("type").and_then(Value::as_str).unwrap_or("button");
        let mut value = 0.0f32;
        if let Some(keys) = item.get("keys").and_then(Value::as_array) {
            for key in keys {
                match key {
                    Value::String(k) if held_norm.contains(&normalize_key_name(k)) => {
                        value = 1.0;
                    }
                    Value::Array(pair) if pair.len() >= 2 => {
                        if let (Some(k), Some(weight)) = (pair[0].as_str(), pair[1].as_f64()) {
                            if held_norm.contains(&normalize_key_name(k)) {
                                value += weight as f32;
                            }
                        }
                    }
                    _ => {}
                }
            }
        }
        if typ == "axis" {
            value = value.clamp(-1.0, 1.0);
        } else if value > 0.0 {
            value = 1.0;
        }
        frame.actions.insert(name.to_string(), value);
    }
}

pub(crate) fn input_frame_from_map(value: &Value) -> InputFrame {
    let mut actions = BTreeMap::new();
    if let Some(arr) = value.get("actions").and_then(Value::as_array) {
        for item in arr {
            if let Some(name) = item.get("name").and_then(Value::as_str) {
                if !name.is_empty() {
                    actions.insert(name.to_string(), 0.0);
                }
            }
        }
    }
    InputFrame { actions }
}

pub(crate) fn compose_input(base: &InputFrame, pending: &[PendingInject]) -> InputFrame {
    let mut frame = base.clone();
    for inj in pending {
        if inj.remaining == 0 {
            frame.actions.insert(inj.action.clone(), inj.value);
        }
    }
    frame
}

/// Drop injects that applied this step; decrement the rest.
pub(crate) fn advance_injects(pending: &mut Vec<PendingInject>) {
    pending.retain_mut(|inj| {
        if inj.remaining == 0 {
            false
        } else {
            inj.remaining -= 1;
            true
        }
    });
}

pub(crate) fn clamp_action_value(value: f64) -> f32 {
    if !value.is_finite() {
        return 0.0;
    }
    (value as f32).clamp(-1.0, 1.0)
}

pub(crate) fn parse_inject_actions(params: &Value) -> Result<Vec<PendingInject>, String> {
    let Some(arr) = params.get("actions").and_then(Value::as_array) else {
        return Err("actions must be an array".into());
    };
    let mut out = Vec::with_capacity(arr.len());
    for item in arr {
        let action = item
            .get("action")
            .and_then(Value::as_str)
            .ok_or_else(|| "action must be a string".to_string())?;
        if action.is_empty() {
            return Err("action must be a non-empty string".into());
        }
        let value = item
            .get("value")
            .and_then(Value::as_f64)
            .ok_or_else(|| "value must be a number".to_string())?;
        let remaining = match item.get("frame_offset") {
            None | Some(Value::Null) => 0u32,
            Some(v) => v
                .as_u64()
                .and_then(|n| u32::try_from(n).ok())
                .ok_or_else(|| "frame_offset must be a u32".to_string())?,
        };
        out.push(PendingInject {
            remaining,
            action: action.to_string(),
            value: clamp_action_value(value),
        });
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn map_names_start_at_zero_and_inject_overlays() {
        let base = input_frame_from_map(&json!({
            "actions": [
                { "name": "move_x", "type": "axis" },
                { "name": "interact", "type": "button" }
            ]
        }));
        assert_eq!(base.actions.get("move_x"), Some(&0.0));
        assert_eq!(base.actions.get("interact"), Some(&0.0));

        let pending = vec![PendingInject {
            remaining: 0,
            action: "move_x".into(),
            value: 1.0,
        }];
        let frame = compose_input(&base, &pending);
        assert_eq!(frame.actions.get("move_x"), Some(&1.0));
        assert_eq!(frame.actions.get("interact"), Some(&0.0));
    }

    #[test]
    fn unknown_inject_name_is_set_and_offset_then_drops() {
        let base = InputFrame::default();
        let mut pending = vec![
            PendingInject {
                remaining: 0,
                action: "move_x".into(),
                value: 1.0,
            },
            PendingInject {
                remaining: 1,
                action: "interact".into(),
                value: 1.0,
            },
        ];
        let first = compose_input(&base, &pending);
        assert_eq!(first.actions.get("move_x"), Some(&1.0));
        assert!(!first.actions.contains_key("interact"));
        advance_injects(&mut pending);
        let second = compose_input(&base, &pending);
        assert!(!second.actions.contains_key("move_x"));
        assert_eq!(second.actions.get("interact"), Some(&1.0));
        advance_injects(&mut pending);
        assert!(pending.is_empty());
    }

    #[test]
    fn clamp_and_parse_inject() {
        assert_eq!(clamp_action_value(2.0), 1.0);
        assert_eq!(clamp_action_value(-4.0), -1.0);
        let parsed = parse_inject_actions(&json!({
            "actions": [{ "frame_offset": 0, "action": "move_x", "value": 1 }]
        }))
        .expect("parse");
        assert_eq!(parsed.len(), 1);
        assert_eq!(parsed[0].action, "move_x");
        assert_eq!(parsed[0].value, 1.0);
        assert_eq!(parsed[0].remaining, 0);
    }

    #[test]
    fn held_keys_drive_axis_and_button() {
        let map = json!({
            "actions": [
                {
                    "name": "move_x",
                    "type": "axis",
                    "keys": [["A", -1.0], ["D", 1.0], ["Left", -1.0]]
                },
                { "name": "jump", "type": "button", "keys": ["Space", "W"] }
            ]
        });
        let mut frame = input_frame_from_map(&map);
        let mut held = BTreeSet::new();
        held.insert("D".into());
        apply_held_keys(&map, &held, &mut frame);
        assert_eq!(frame.actions.get("move_x"), Some(&1.0));
        assert_eq!(frame.actions.get("jump"), Some(&0.0));

        held.insert("A".into());
        apply_held_keys(&map, &held, &mut frame);
        assert_eq!(frame.actions.get("move_x"), Some(&0.0));

        held.clear();
        held.insert("ArrowLeft".into());
        apply_held_keys(&map, &held, &mut frame);
        assert_eq!(frame.actions.get("move_x"), Some(&-1.0));

        held.clear();
        held.insert("Spacebar".into());
        apply_held_keys(&map, &held, &mut frame);
        assert_eq!(frame.actions.get("jump"), Some(&1.0));
    }
}
